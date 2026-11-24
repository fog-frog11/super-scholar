"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowRight, Check, Cloud, CloudOff, FileArchive, FileCode2, FileImage, FileSpreadsheet, FileText, RefreshCw, Trash2, UploadCloud, XCircle } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Badge, Button, Card, EmptyState, ProgressBar } from "@/components/ui";
import { inferMaterialKind, fileExtension, parseMaterialFile } from "@/lib/file-parser";
import { buildResearchProfile } from "@/lib/research-profiler";
import { downloadMaterialFromServer, loadMaterialTextFromServer, syncMaterialAnalysis, syncProjectSnapshot, uploadMaterialToServer } from "@/lib/backend-client";
import { deleteStored, loadBlob, loadText, saveBlob, saveText } from "@/lib/storage";
import type { MaterialRecord } from "@/lib/types";
import { formatBytes, uid } from "@/lib/utils";
import { useAppStore } from "@/store/use-app-store";

function iconFor(material: MaterialRecord) {
  if (material.kind === "manuscript") return FileText;
  if (material.kind === "source") return material.extension === "zip" ? FileArchive : FileCode2;
  if (material.kind === "data") return FileSpreadsheet;
  if (material.kind === "image") return FileImage;
  return FileText;
}

function detail(material: MaterialRecord) {
  const a = material.analysis;
  const parts: string[] = [];
  if (a.pages) parts.push(`${a.pages} 页`);
  if (a.sections) parts.push(`${a.sections} 个结构段`);
  if (a.references) parts.push(`${a.references} 个引用信号`);
  if (a.sheets) parts.push(`${a.sheets} 个表`);
  if (a.rows) parts.push(`${a.rows} 行数据`);
  if (a.codeFiles) parts.push(`${a.codeFiles} 个代码文件`);
  if (a.imageWidth && a.imageHeight) parts.push(`${a.imageWidth} × ${a.imageHeight}`);
  if (a.textChars) parts.push(`${a.textChars.toLocaleString("zh-CN")} 字符`);
  return parts.join(" · ") || (a.status === "ready" ? "已完成可用信息提取" : a.message);
}

export default function MaterialsPage() {
  const { projectId } = useParams<{projectId:string}>();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging,setDragging]=useState(false);
  const [busy,setBusy]=useState(false);
  const [autoProfiling,setAutoProfiling]=useState(false);
  const store=useAppStore();
  const project=store.projects.find(p=>p.id===projectId);
  const materials=project?.materialIds.map(id=>store.materials[id]).filter(Boolean) ?? [];
  const readyCount=materials.filter(m=>m.analysis.status==="ready").length;
  const processing=materials.some(m=>!["ready","error"].includes(m.analysis.status));

  const buildAutomaticLocalProfile=useCallback(async()=>{
    const state=useAppStore.getState();
    const currentProject=state.projects.find(p=>p.id===projectId);
    if(!currentProject || currentProject.profile)return;
    const currentMaterials=currentProject.materialIds.map(id=>state.materials[id]).filter(Boolean);
    const ready=currentMaterials.filter(m=>m.analysis.status==="ready");
    if(ready.length===0&&!currentProject.brief.trim())return;
    setAutoProfiling(true);
    try{
      const materialTexts=await Promise.all(ready.map(async material=>{
        const local=await loadText(material.textStorageKey);
        if(local)return local;
        if(material.serverSync==="synced"){
          try{
            const remote=await loadMaterialTextFromServer(material.id);
            const key=material.textStorageKey??`text:${material.id}`;
            await saveText(key,remote);
            useAppStore.getState().updateMaterial(material.id,{textStorageKey:key});
            return remote;
          }catch{return undefined;}
        }
        return undefined;
      }));
      const texts=[currentProject.brief,...materialTexts].filter((value): value is string=>Boolean(value));
      if(texts.length===0)return;
      const profile=buildResearchProfile(texts,ready);
      useAppStore.getState().setProfile(projectId,profile);
      const refreshed=useAppStore.getState().projects.find(p=>p.id===projectId);
      if(refreshed)await syncProjectSnapshot(refreshed).catch(()=>undefined);
    } finally {
      setAutoProfiling(false);
    }
  },[projectId]);

  const analyzeRecord = useCallback(async (record: MaterialRecord, file: File) => {
    try {
      store.updateMaterial(record.id,{analysis:{...record.analysis,status:"reading",progress:5,stage:"local_storage",message:"正在保存到浏览器本地材料库"}});
      await saveBlob(record.storageKey,file);
      store.updateMaterial(record.id,{analysis:{...record.analysis,status:"reading",progress:10,stage:"local_storage",message:"材料已保存，开始解析"}});
      const parsed=await parseMaterialFile(file,(patch)=>{
        const current=useAppStore.getState().materials[record.id];
        if(current) useAppStore.getState().updateMaterial(record.id,{analysis:{...current.analysis,...patch}});
      });
      const textKey=`text:${record.id}`;
      await saveText(textKey,parsed.text);
      store.updateMaterial(record.id,{textStorageKey:textKey,analysis:parsed.analysis});
      return parsed;
    } catch(error) {
      const current=useAppStore.getState().materials[record.id];
      store.updateMaterial(record.id,{analysis:{...(current?.analysis ?? record.analysis),status:"error",progress:100,stage:"error",message:"解析失败",error:error instanceof Error?error.message:String(error)}});
      return null;
    }
  },[store]);

  const addFiles=useCallback(async(files:File[])=>{
    if(!files.length) return;
    setBusy(true);
    store.updateProject(projectId,{profile:undefined,recommendationRun:undefined,comparisonVenueIds:[],selectedVenueId:undefined,status:"analyzing"});
    if(project) await syncProjectSnapshot(useAppStore.getState().projects.find(p=>p.id===projectId)??project).catch(()=>undefined);
    for(const file of files){
      const id=uid("material"); const now=new Date().toISOString();
      const record:MaterialRecord={id,projectId,name:file.name,mimeType:file.type,extension:fileExtension(file.name),size:file.size,kind:inferMaterialKind(file),storageKey:`blob:${id}`,createdAt:now,updatedAt:now,analysis:{status:"queued",progress:0,stage:"queued",message:"等待解析"},serverSync:"pending"};
      store.addMaterial(record);
      let serverUploaded=false;
      const uploadPromise=uploadMaterialToServer(projectId,record,file).then(()=>{serverUploaded=true;store.updateMaterial(id,{serverSync:"synced",serverSyncError:undefined})}).catch((error)=>{store.updateMaterial(id,{serverSync:"error",serverSyncError:error instanceof Error?error.message:String(error)})});
      const parsed=await analyzeRecord(record,file);
      await uploadPromise;
      if(parsed&&serverUploaded){
        await syncMaterialAnalysis(id,parsed.analysis,parsed.text).catch((error)=>{store.updateMaterial(id,{serverSync:"error",serverSyncError:error instanceof Error?error.message:String(error)})});
      }
    }
    store.updateProject(projectId,{status:"materials"}); setBusy(false);
  },[projectId,store,analyzeRecord,project]);

  const reanalyze=async(material:MaterialRecord)=>{
    let blob=await loadBlob(material.storageKey);
    if(!blob&&material.serverSync==="synced"){
      try{blob=await downloadMaterialFromServer(material.id);await saveBlob(material.storageKey,blob)}catch{/* handled below */}
    }
    if(!blob){store.updateMaterial(material.id,{analysis:{...material.analysis,status:"error",message:"找不到可恢复的原始文件",error:"浏览器本地原始文件不存在，并且后端也无法恢复该材料；请重新上传。"}});return;}
    const file=new File([blob],material.name,{type:material.mimeType});
    store.updateProject(projectId,{profile:undefined,recommendationRun:undefined,comparisonVenueIds:[],selectedVenueId:undefined,status:"analyzing"});
    const parsed=await analyzeRecord(material,file);
    if(parsed){
      await syncMaterialAnalysis(material.id,parsed.analysis,parsed.text).then(()=>store.updateMaterial(material.id,{serverSync:"synced",serverSyncError:undefined})).catch((error)=>store.updateMaterial(material.id,{serverSync:"error",serverSyncError:error instanceof Error?error.message:String(error)}));
    }
    store.updateProject(projectId,{status:"materials"});
  };

  const remove=async(material:MaterialRecord)=>{
    store.removeMaterial(material.id); await deleteStored(material.storageKey); await deleteStored(material.textStorageKey);
    store.updateProject(projectId,{profile:undefined,recommendationRun:undefined,comparisonVenueIds:[],selectedVenueId:undefined,status:"materials"});
  };

  useEffect(()=>{
    if(!project || project.profile || processing || busy || autoProfiling)return;
    if(readyCount===0&&!project.brief.trim())return;
    void buildAutomaticLocalProfile();
  },[project?.id,project?.profile,project?.brief,readyCount,processing,busy,autoProfiling,buildAutomaticLocalProfile]);

  if(!project) return null;
  return <div className="grid gap-5 xl:grid-cols-[1fr_320px]">
    <div className="space-y-5">
      <Card className="p-6"><div className="flex items-start justify-between gap-4"><div><h2 className="text-lg font-semibold tracking-[-.02em]">研究材料</h2><p className="mt-1.5 text-sm leading-6 text-[#7c8799]">添加所有能帮助 Super Scholar 理解研究的内容。解析仍在浏览器本地执行；后端在线时，原始材料和解析结果会同步到项目存储。</p></div><Badge tone="brand">{readyCount} / {materials.length} Ready</Badge></div>
        <input ref={inputRef} className="hidden" type="file" multiple accept=".pdf,.docx,.tex,.zip,.xlsx,.xls,.csv,.tsv,.png,.jpg,.jpeg,.webp,.gif,.md,.txt,.py,.js,.ts,.tsx,.cpp,.c,.java,.json,.yaml,.yml" onChange={(e)=>{const files=[...(e.target.files??[])];void addFiles(files);e.target.value="";}}/>
        <motion.div onDragOver={(e)=>{e.preventDefault();setDragging(true)}} onDragLeave={()=>setDragging(false)} onDrop={(e)=>{e.preventDefault();setDragging(false);void addFiles([...e.dataTransfer.files])}} animate={{scale:dragging?1.008:1}} className={`mt-6 grid min-h-56 place-items-center rounded-[18px] border border-dashed p-8 text-center transition ${dragging?"border-[#7c8af2] bg-[#f0f2ff] shadow-[0_0_0_5px_rgba(85,104,255,.06)]":"border-[#cfd5df] bg-[#fafbfd] hover:border-[#aeb7c8] hover:bg-[#f8f9fc]"}`}>
          <div><motion.div animate={dragging?{y:-5}:{y:0}} className="mx-auto grid size-12 place-items-center rounded-2xl bg-white text-[#5968e6] shadow-[0_8px_25px_rgba(44,55,90,.08)]"><UploadCloud className="size-5"/></motion.div><h3 className="mt-4 text-sm font-semibold">{dragging?"松开即可添加材料":"拖入你的研究材料"}</h3><p className="mt-2 text-xs leading-5 text-[#8d97a8]">PDF · DOCX · LaTeX / Code ZIP · XLSX / CSV · PNG / JPG · 文本与常见源码</p><Button className="mt-5" variant="secondary" onClick={()=>inputRef.current?.click()} disabled={busy}>浏览文件</Button></div>
        </motion.div>
      </Card>

      <Card className="p-6"><div className="flex items-center justify-between"><div><h2 className="text-base font-semibold">Material Library</h2><p className="mt-1 text-xs text-[#929bad]">{materials.length} 份材料 · 可重新解析或删除</p></div></div>
        {materials.length===0?<div className="mt-5"><EmptyState icon={<FileText className="size-5"/>} title="还没有材料" description="先上传至少一份可解析材料。你也可以只上传代码、实验表格或一份早期研究说明。"/></div>:<div className="mt-5 divide-y divide-[#edf0f4]">{materials.map(material=>{const Icon=iconFor(material);const a=material.analysis;return <div key={material.id} className="py-4 first:pt-0 last:pb-0"><div className="flex min-w-0 items-start gap-3 overflow-hidden"><div className="grid size-10 shrink-0 place-items-center rounded-xl bg-[#f1f3f8] text-[#6471d8]"><Icon className="size-4.5"/></div><div className="min-w-0 flex-1"><div className="flex min-w-0 items-center gap-2 overflow-hidden"><div title={material.name} className="min-w-0 flex-1 truncate text-sm font-semibold">{material.name}</div>{a.status==="ready"&&<Badge tone="success" className="shrink-0"><Check className="mr-1 size-3"/>Ready</Badge>}{a.status==="error"&&<Badge tone="danger" className="shrink-0"><XCircle className="mr-1 size-3"/>Needs attention</Badge>}{material.serverSync==="synced"&&<Badge className="shrink-0"><Cloud className="mr-1 size-3"/>Server</Badge>}{material.serverSync==="error"&&<Badge tone="warning" className="shrink-0"><CloudOff className="mr-1 size-3"/>Local only</Badge>}</div><div title={`${material.extension.toUpperCase() || "FILE"} · ${formatBytes(material.size)} · ${detail(material)}`} className="mt-1 max-w-full truncate text-[11px] text-[#9aa3b2]">{material.extension.toUpperCase() || "FILE"} · {formatBytes(material.size)} · {detail(material)}</div>{!["ready","error"].includes(a.status)&&<div className="mt-3 max-w-xl"><div className="mb-1.5 flex items-center justify-between text-[11px]"><span className="font-medium text-[#657087]">{a.message}</span><span className="tabular-nums text-[#8d97a8]">{a.progress}%</span></div><ProgressBar value={a.progress}/></div>}{a.status==="error"&&<div className="mt-2 rounded-lg bg-[#fff3f4] px-3 py-2 text-[11px] leading-5 text-[#a44351]">{a.error}</div>}{material.serverSync==="error"&&<div className="mt-2 text-[10px] leading-4 text-[#9a6b2b]" title={material.serverSyncError}>服务器未同步；浏览器本地材料仍可继续使用。</div>}</div><div className="flex shrink-0 items-center gap-1"><Button variant="ghost" size="sm" className="size-8 p-0" onClick={()=>void reanalyze(material)} title="重新解析"><RefreshCw className="size-3.5"/></Button><Button variant="ghost" size="sm" className="size-8 p-0 text-[#a24a58]" onClick={()=>void remove(material)} title="删除"><Trash2 className="size-3.5"/></Button></div></div></div>})}</div>}
      </Card>
    </div>
    <aside className="space-y-4 xl:sticky xl:top-24 xl:self-start"><Card className="p-5"><div className="text-xs font-semibold uppercase tracking-[.14em] text-[#8b95a6]">解析状态</div><div className="mt-4 text-3xl font-semibold tracking-[-.04em]">{materials.length?Math.round(materials.reduce((s,m)=>s+m.analysis.progress,0)/materials.length):0}%</div><ProgressBar value={materials.length?materials.reduce((s,m)=>s+m.analysis.progress,0)/materials.length:0} className="mt-3"/><div className="mt-4 space-y-2 text-xs text-[#788397]"><div className="flex justify-between"><span>已就绪</span><b className="text-[#27304a]">{readyCount}</b></div><div className="flex justify-between"><span>处理中</span><b className="text-[#27304a]">{materials.filter(m=>!["ready","error"].includes(m.analysis.status)).length}</b></div><div className="flex justify-between"><span>需要处理</span><b className="text-[#27304a]">{materials.filter(m=>m.analysis.status==="error").length}</b></div></div></Card><Card className="relative overflow-hidden p-5"><div className="absolute inset-x-0 top-0 h-[3px] bg-[linear-gradient(90deg,#6676ff,#8a68ef,#22b7bd)]"/><div className="flex items-center justify-between gap-2"><h3 className="text-sm font-semibold">本地研究画像</h3>{project.profile?<Badge tone="success">已自动生成</Badge>:autoProfiling?<Badge tone="brand">正在生成</Badge>:<Badge>等待材料</Badge>}</div><p className="mt-2 text-xs leading-5 text-[#818b9d]">材料解析完成后会自动建立本地快速画像，不需要额外点击。进入画像页后，如需更深入的跨材料理解，再由你主动启用 AI。</p>{autoProfiling&&<div className="mt-4 flex items-center gap-2 text-xs text-[#66728a]"><span className="size-2 animate-pulse rounded-full bg-[#6676ff]"/>正在汇总本地证据…</div>}<Link href={`/app/projects/${projectId}/profile`}><Button className="mt-4 w-full" disabled={(readyCount===0&&!project.brief.trim())||processing||autoProfiling}>{project.profile?"查看研究画像":"等待本地画像"} <ArrowRight className="size-4"/></Button></Link>{processing&&<p className="mt-2 text-center text-[10px] text-[#9aa3b2]">等待当前解析完成</p>}</Card><Card className="p-5"><div className="text-xs font-semibold">隐私说明</div><p className="mt-2 text-[11px] leading-5 text-[#8a94a5]">本地快速画像不会把材料发送到外部 LLM。只有你在研究画像页主动确认“AI 深度理解”后，才会调用已配置的外部 Provider。</p></Card></aside>
  </div>;
}
