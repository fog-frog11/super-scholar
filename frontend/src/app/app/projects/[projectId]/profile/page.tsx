"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowRight, BarChart3, BrainCircuit, CheckCircle2, Database, Edit3, Eye,
  FileCode2, FlaskConical, ImageIcon, Layers3, LoaderCircle, Plus, Save,
  ScanText, ShieldCheck, Sparkles, X
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Badge, Button, Card, EmptyState, Input, Modal, ProgressBar, Textarea } from "@/components/ui";
import { CCF_AREAS } from "@/lib/constants";
import { buildResearchProfile } from "@/lib/research-profiler";
import {
  getResearchAnalysis, getResearchCapabilities, getLatestResearchAnalysis,
  loadMaterialTextFromServer, materialPageImageUrl, materialPreviewUrl, researchArtifactUrl, startResearchAnalysis, uploadMaterialToServer
} from "@/lib/backend-client";
import { loadBlob, loadText, saveText } from "@/lib/storage";
import type {
  CcfAreaCode, GroundedClaim, ResearchAnalysisRun, ResearchCapabilities,
  ResearchProfile, ResearchVisualArtifact
} from "@/lib/types";
import { useAppStore } from "@/store/use-app-store";

function TagEditor({ values, onChange, placeholder }: { values:string[]; onChange:(v:string[])=>void; placeholder:string }) {
  const [draft,setDraft]=useState("");
  const add=()=>{const v=draft.trim();if(v&&!values.includes(v))onChange([...values,v]);setDraft("")};
  return <div><div className="flex flex-wrap gap-2">{values.map(v=><span key={v} title={v} className="inline-flex max-w-full min-w-0 items-center gap-1 rounded-full bg-[#f0f2ff] px-2.5 py-1.5 text-xs font-medium text-[#5362d2]"><span className="min-w-0 truncate">{v}</span><button onClick={()=>onChange(values.filter(x=>x!==v))} className="rounded-full p-0.5 hover:bg-[#dfe3ff]"><X className="size-3"/></button></span>)}</div><div className="mt-3 flex gap-2"><Input value={draft} onChange={e=>setDraft(e.target.value)} onKeyDown={e=>{if(e.key==="Enter"){e.preventDefault();add()}}} placeholder={placeholder}/><Button variant="secondary" onClick={add}><Plus className="size-4"/>添加</Button></div></div>;
}

function ListEditor({ values,onChange,placeholder }: {values:string[];onChange:(v:string[])=>void;placeholder:string}) {
  const [draft,setDraft]=useState("");
  return <div className="space-y-2">{values.map((v,i)=><div key={`${i}-${v.slice(0,12)}`} className="flex gap-2 rounded-xl border border-[#e5e9ef] bg-[#fbfcfd] p-3"><div className="mt-0.5 grid size-6 shrink-0 place-items-center rounded-lg bg-[#edf0ff] text-[10px] font-bold text-[#5968d9]">{String(i+1).padStart(2,"0")}</div><textarea className="min-h-12 flex-1 resize-y bg-transparent text-sm leading-6 outline-none" value={v} onChange={e=>onChange(values.map((x,j)=>j===i?e.target.value:x))}/><button onClick={()=>onChange(values.filter((_,j)=>j!==i))} className="self-start rounded-lg p-1.5 text-[#9ba4b4] hover:bg-[#fff0f2] hover:text-[#b74152]"><X className="size-3.5"/></button></div>)}<div className="flex gap-2"><Input value={draft} onChange={e=>setDraft(e.target.value)} placeholder={placeholder}/><Button variant="secondary" onClick={()=>{if(draft.trim()){onChange([...values,draft.trim()]);setDraft("")}}}><Plus className="size-4"/>添加</Button></div></div>;
}

function EvidenceChips({ claim, compact=false, labelForEvidence, hoverForEvidence, onOpenEvidence }: {claim?: GroundedClaim; compact?:boolean; labelForEvidence?:(id:string)=>string; hoverForEvidence?:(id:string)=>string; onOpenEvidence?:(id:string)=>void}) {
  if(!claim?.evidenceIds?.length)return null;
  return <div className={`flex flex-wrap gap-1.5 ${compact?"mt-1.5":"mt-3"}`}>{claim.evidenceIds.map(id=>{const label=labelForEvidence?.(id)??"项目证据";const hover=hoverForEvidence?.(id)??label;return <span key={id} className="group relative inline-flex"><button type="button" aria-label={`查看证据 ${label}`} onClick={()=>onOpenEvidence?.(id)} className="max-w-[260px] truncate rounded-full border border-[#dfe5ef] bg-white px-2 py-1 text-[9px] font-medium text-[#778299] transition hover:border-[#bcc6f5] hover:bg-[#f7f8ff] hover:text-[#5362d2]">{label}</button><span className="pointer-events-none invisible absolute bottom-[calc(100%+7px)] left-0 z-40 w-72 translate-y-1 rounded-xl border border-[#dfe4ef] bg-[#192238] px-3 py-2 text-left text-[10px] font-normal leading-4 text-white opacity-0 shadow-xl transition group-hover:visible group-hover:translate-y-0 group-hover:opacity-100"><span className="whitespace-pre-line">{hover}</span><span className="mt-1 block text-[#b8c3dd]">点击查看证据并定位原始材料</span></span></span>})}</div>;
}

function GroundedList({ values, empty, labelForEvidence, hoverForEvidence, onOpenEvidence }: {values?:GroundedClaim[];empty:string;labelForEvidence?:(id:string)=>string; hoverForEvidence?:(id:string)=>string; onOpenEvidence?:(id:string)=>void}) {
  if(!values?.length)return <div className="rounded-xl border border-dashed border-[#dfe4ec] bg-[#fafbfd] p-4 text-xs leading-5 text-[#8b95a6]">{empty}</div>;
  return <div className="space-y-2">{values.map((item,i)=><div key={`${i}-${item.text.slice(0,20)}`} className="rounded-xl bg-[#f8f9fc] p-4"><div className="flex gap-3"><div className="grid size-7 shrink-0 place-items-center rounded-lg bg-[#edf0ff] text-[10px] font-bold text-[#5d6cdf]">{String(i+1).padStart(2,"0")}</div><div className="min-w-0"><p className="break-words text-sm leading-6 text-[#5d687c]">{item.text}</p><div className="mt-2 flex items-center gap-2"><Badge tone={item.confidence==="high"?"success":item.confidence==="low"?"warning":"neutral"}>{item.confidence??"grounded"}</Badge></div><EvidenceChips claim={item} compact labelForEvidence={labelForEvidence} hoverForEvidence={hoverForEvidence} onOpenEvidence={onOpenEvidence}/></div></div></div>)}</div>;
}

type EvidenceView = {
  id:string;
  label:string;
  hover:string;
  materialName?:string;
  kind:string;
  page?:number;
  path?:string;
  sheet?:string;
  excerpt?:string;
  previewUrl?:string;
  pageImageUrl?:string;
  sourceUrl?:string;
  caption?:string;
  regionLabel?:string;
};

export default function ProfilePage() {
  const {projectId}=useParams<{projectId:string}>();
  const router=useRouter();
  const store=useAppStore();
  const project=store.projects.find(p=>p.id===projectId);
  const materials=project?.materialIds.map(id=>store.materials[id]).filter(Boolean)??[];
  const readyMaterials=materials.filter(m=>m.analysis.status==="ready");
  const [working,setWorking]=useState<ResearchProfile|undefined>(project?.profile);
  const [generating,setGenerating]=useState(false);
  const [editing,setEditing]=useState(false);
  const [capabilities,setCapabilities]=useState<ResearchCapabilities>();
  const [run,setRun]=useState<ResearchAnalysisRun|null>(null);
  const [consentOpen,setConsentOpen]=useState(false);
  const [aiError,setAiError]=useState<string>();
  const [syncing,setSyncing]=useState(false);
  const [selectedEvidenceId,setSelectedEvidenceId]=useState<string>();

  const aiRunning=run?.status==="queued"||run?.status==="running";

  const generateLocal=useCallback(async()=>{
    if(!project)return;
    setGenerating(true);
    try{
      const materialTexts=await Promise.all(readyMaterials.map(async(m)=>{
        const local=await loadText(m.textStorageKey);
        if(local)return local;
        if(m.serverSync==="synced"){
          try{const remote=await loadMaterialTextFromServer(m.id);const key=m.textStorageKey??`text:${m.id}`;await saveText(key,remote);store.updateMaterial(m.id,{textStorageKey:key});return remote;}catch{return undefined;}
        }
        return undefined;
      }));
      const texts=[project.brief,...materialTexts].filter((value): value is string=>Boolean(value));
      const profile=buildResearchProfile(texts,readyMaterials);
      setWorking(profile); store.setProfile(projectId,profile);
    } finally {setGenerating(false)}
  },[project,projectId,readyMaterials,store]);

  useEffect(()=>{setWorking(project?.profile)},[project?.profile]);
  useEffect(()=>{
    void getResearchCapabilities().then(setCapabilities).catch(()=>setCapabilities(undefined));
    void getLatestResearchAnalysis(projectId).then(latest=>{
      if(!latest)return;
      // Keep the run for progress/artifacts/diagnostics, but never revive an old AI profile
      // after materials were changed and the current project profile was intentionally invalidated.
      setRun(latest);
      if(latest.status==="error"&&(!project?.updatedAt||latest.updatedAt>=project.updatedAt))setAiError(latest.error||"AI 深度理解失败");
    }).catch(()=>{});
  },[projectId]);

  useEffect(()=>{
    if(!run || !["queued","running"].includes(run.status))return;
    const timer=window.setInterval(()=>{
      void getResearchAnalysis(run.id).then(next=>{
        setRun(next);
        if(next.status==="ready"&&next.result?.profile){
          setWorking(next.result.profile); store.setProfile(projectId,next.result.profile); setAiError(undefined);
        }
        if(next.status==="error")setAiError(next.error||"AI 深度理解失败");
      }).catch(error=>setAiError(String(error)));
    },1400);
    return ()=>window.clearInterval(timer);
  },[run?.id,run?.status,projectId,store]);

  // Local understanding is the default first pass. It runs automatically once the
  // project has a brief or at least one parsed material. AI remains an explicit upgrade.
  useEffect(()=>{
    if(!project || project.profile || working || generating || aiRunning)return;
    if(readyMaterials.length===0&&!project.brief.trim())return;
    void generateLocal();
  },[project?.id,project?.profile,project?.brief,readyMaterials.length,working,generating,aiRunning,generateLocal]);

  const ensureServerMaterials=async()=>{
    if(!project)return;
    setSyncing(true);
    try{
      for(const material of materials){
        if(material.serverSync==="synced")continue;
        const blob=await loadBlob(material.storageKey);
        if(!blob)throw new Error(`材料 ${material.name} 的浏览器原文件已不可用，请在 Materials 页面重新上传。`);
        const file=new File([blob],material.name,{type:material.mimeType||blob.type});
        await uploadMaterialToServer(projectId,material,file);
        store.updateMaterial(material.id,{serverSync:"synced",serverSyncError:undefined});
      }
    } finally {setSyncing(false)}
  };

  const startAI=async()=>{
    if(!project)return;
    setConsentOpen(false); setAiError(undefined);
    try{
      await ensureServerMaterials();
      const next=await startResearchAnalysis(projectId);
      setRun(next);
    }catch(error){setAiError(error instanceof Error?error.message:String(error));}
  };

  const save=()=>{if(working){store.setProfile(projectId,working);setEditing(false)}};
  const areaRanking=useMemo<[CcfAreaCode, number][]>(()=>working?(Object.entries(working.areaScores) as [CcfAreaCode, number][]).filter(([,score])=>score>0).sort((a,b)=>b[1]-a[1]).slice(0,4):[],[working]);
  const artifacts=(run?.result?.artifacts??[]) as ResearchVisualArtifact[];
  const evidenceItems=run?.result?.evidence??[];
  const evidenceViews=useMemo(()=>{
    const map=new Map<string,EvidenceView>();
    const materialById=new Map(materials.map(m=>[m.id,m]));
    const prefixFor=(materialId:string)=>{const kind=materialById.get(materialId)?.kind;return kind==="manuscript"?"论文":kind==="source"?"代码":kind==="data"?"结果":kind==="image"?"图片":"材料"};
    for(const item of evidenceItems){
      const meta=item.metadata??{}; const prefix=prefixFor(item.material_id); const material=materialById.get(item.material_id);
      const page=typeof meta.page==="number"?meta.page:undefined; const path=typeof meta.path==="string"?meta.path:undefined; const sheet=typeof meta.sheet==="string"?meta.sheet:undefined;
      let label=page?`${prefix} · p.${page}`:path?`${prefix} · ${path}`:sheet?`${prefix} · ${sheet}`:item.kind==="repository_summary"?`${prefix} · 项目结构`:prefix;
      if(item.kind==="table"&&page)label+=` · Table`;
      const excerpt=String(item.text??"").replace(/\s+/g," ").trim();
      const hover=[label,material?.name,excerpt?excerpt.slice(0,180):undefined].filter(Boolean).join("\n");
      map.set(item.id,{
        id:item.id,label,hover,materialName:material?.name,kind:item.kind,page,path,sheet,
        excerpt:String(item.text??"").slice(0,3000),
        sourceUrl:page&&material?.kind==="manuscript"?materialPreviewUrl(item.material_id,page):undefined,
        pageImageUrl:page&&material?.kind==="manuscript"?materialPageImageUrl(item.material_id,page):undefined,
      });
    }
    for(const artifact of artifacts){
      const prefix=prefixFor(artifact.material_id); const material=materialById.get(artifact.material_id);
      const region=artifact.region_label??(artifact.kind==="figure_crop"?"Figure":artifact.kind==="table_crop"?"Table":artifact.kind==="page_render"?"页面":undefined);
      const label=artifact.page?`${prefix} · ${region?`${region} · `:""}p.${artifact.page}`:`${prefix} · ${region??"视觉证据"}`;
      const hover=[label,material?.name,artifact.caption].filter(Boolean).join("\n");
      map.set(artifact.id,{
        id:artifact.id,label,hover,materialName:material?.name,kind:artifact.kind,page:artifact.page,
        previewUrl:researchArtifactUrl(artifact.url),
        sourceUrl:artifact.page&&material?.kind==="manuscript"?materialPreviewUrl(artifact.material_id,artifact.page):undefined,
        pageImageUrl:artifact.page&&material?.kind==="manuscript"?materialPageImageUrl(artifact.material_id,artifact.page):undefined,
        caption:artifact.caption,regionLabel:artifact.region_label,
      });
    }
    return map;
  },[evidenceItems,artifacts,materials]);
  const labelForEvidence=useCallback((id:string)=>evidenceViews.get(id)?.label??"项目证据",[evidenceViews]);
  const hoverForEvidence=useCallback((id:string)=>evidenceViews.get(id)?.hover??labelForEvidence(id),[evidenceViews,labelForEvidence]);
  const openEvidence=useCallback((id:string)=>{if(evidenceViews.has(id))setSelectedEvidenceId(id)},[evidenceViews]);
  const selectedEvidence=selectedEvidenceId?evidenceViews.get(selectedEvidenceId):undefined;
  const displayArtifacts=useMemo(()=>{
    const primary=artifacts.filter(a=>["figure_crop","table_crop","uploaded_image","docx_image"].includes(a.kind));
    const fallback=artifacts.filter(a=>a.kind==="page_render");
    const source=primary.length?primary:fallback;
    const priority=(x:ResearchVisualArtifact)=>x.kind==="figure_crop"?0:x.kind==="table_crop"?1:x.kind==="uploaded_image"?2:x.kind==="docx_image"?3:4;
    return [...source].sort((a,b)=>priority(a)-priority(b)||(a.page??9999)-(b.page??9999)).slice(0,12)
  },[artifacts]);
  const requestPlan=(run?.result?.requestPlan ?? run?.result?.diagnostics?.pipeline) as any;
  const callTrace=(run?.result?.callTrace??run?.result?.diagnostics?.callTrace??[]) as Array<Record<string,unknown>>;

  if(!project)return null;

  const handleAIAction=()=>{
    setAiError(undefined);
    if(capabilities?.aiConfigured)setConsentOpen(true);
    else router.push(`/app/settings?from=${encodeURIComponent(`/app/projects/${projectId}/profile`)}`);
  };

  if(!working && !aiRunning){
    if(generating || readyMaterials.length || project.brief.trim())return <Card className="relative overflow-hidden p-8"><div className="absolute inset-x-0 top-0 h-1 bg-[linear-gradient(90deg,#6676ff,#8d6ef1,#1fb6bd)]"/><div className="mx-auto max-w-2xl text-center"><div className="relative mx-auto grid size-14 place-items-center rounded-2xl bg-[#edf0ff] text-[#5c6be1]"><span className="absolute inset-0 animate-ping rounded-2xl bg-[#6878f1]/10"/><LoaderCircle className="relative size-7 animate-spin"/></div><h2 className="mt-5 text-2xl font-semibold">正在自动建立本地研究画像</h2><p className="mt-2 text-sm leading-6 text-[#7a8498]">Super Scholar 正在汇总已经真实解析完成的本地文本与材料信号。这个过程不显示虚假的百分比，也不会把材料发送到外部 AI。</p><div className="mx-auto mt-6 flex max-w-md items-center justify-center gap-2 rounded-xl border border-[#e4e7f4] bg-[#fafbff] px-4 py-3 text-xs text-[#69758c]"><span className="size-2 animate-pulse rounded-full bg-[#6878f1]"/>正在构建结构化本地基线…</div></div></Card>;
    return <div className="space-y-4"><Card className="p-8"><EmptyState icon={<BrainCircuit className="size-5"/>} title="还没有可建立画像的材料" description="请先补充项目研究说明，或返回 Materials 页面上传并完成解析。"/></Card></div>;
  }

  if(aiRunning&&!working)return <Card className="relative overflow-hidden p-8"><div className="absolute inset-x-0 top-0 h-1 bg-[linear-gradient(90deg,#6676ff,#8d6ef1,#1fb6bd)]"/><div className="mx-auto max-w-2xl text-center"><div className="mx-auto grid size-14 place-items-center rounded-2xl bg-[#edf0ff] text-[#5c6be1]"><LoaderCircle className="size-7 animate-spin"/></div><h2 className="mt-5 text-2xl font-semibold">正在理解你的研究</h2><p className="mt-2 text-sm text-[#7a8498]">{run.message}</p><div className="mt-6 text-5xl font-semibold tracking-[-.05em] text-[#3f50c8]">{run.progress}%</div><ProgressBar value={run.progress} active className="mt-5"/><div className="mt-5 rounded-2xl bg-[#f7f8fb] p-4 text-left text-xs leading-5 text-[#7d8799]">当前阶段：<b className="text-[#46526b]">{run.stage}</b><br/>百分比只在真实解析 / 模型 / 校验阶段完成时推进；等待外部模型期间动画会持续但不会伪造进度。</div></div></Card>;

  if(!working)return null;

  const isAI=working.sourceMode==="ai_deep"||working.sourceMode==="ai_extracted_partial";
  const aiPartial=working.sourceMode==="ai_extracted_partial";
  const analysisWarnings=(run?.result?.analysisWarnings??[]) as Array<{message?:string}>;
  const analysisNotes=(run?.result?.analysisNotes??[]) as Array<{message?:string;fields?:string[]}>;
  return <div className="space-y-5">
    <Card className="overflow-hidden"><div className="relative border-b border-[#e8ebf1] bg-[linear-gradient(135deg,#f5f6ff,#fbfcff_55%,#effafa)] px-6 py-7"><div className="absolute right-8 top-5 size-32 rounded-full bg-[#7482ff]/10 blur-3xl"/><div className="relative flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between"><div><div className="flex items-center gap-2 text-xs font-bold uppercase tracking-[.16em] text-[#6472df]">{isAI?<BrainCircuit className="size-3.5"/>:<Sparkles className="size-3.5"/>} Research Profile</div><h2 className="mt-3 text-3xl font-semibold tracking-[-.045em]">{working.primaryArea?CCF_AREAS[working.primaryArea].zh:"领域尚不确定"}</h2><div className="mt-3 flex flex-wrap gap-2"><Badge tone={isAI?"success":"neutral"}>{isAI?(aiPartial?"AI Extracted · Local Synthesis":"AI Deep · Evidence Grounded"):"Local Baseline"}</Badge>{working.topics.slice(0,5).map(t=><Badge key={t} tone="brand">{t}</Badge>)}</div></div><div className="flex flex-wrap gap-2">{editing?<><Button variant="secondary" onClick={()=>{setWorking(project.profile);setEditing(false)}}>取消</Button><Button onClick={save}><Save className="size-4"/>保存修改</Button></>:<><Button variant="secondary" onClick={()=>setEditing(true)}><Edit3 className="size-4"/>人工校正</Button>{isAI&&<Button variant="secondary" disabled={aiRunning||syncing} onClick={handleAIAction}><BrainCircuit className="size-4"/>{aiRunning?"AI 正在理解…":"重新 AI 分析"}</Button>}</>}</div></div></div>
      <div className="p-6"><div className="grid gap-6 lg:grid-cols-[1.3fr_.7fr]"><div><div className="text-xs font-semibold text-[#8791a4]">研究摘要</div>{editing?<Textarea className="mt-2 min-h-40" value={working.summary} onChange={e=>setWorking({...working,summary:e.target.value})}/>:<><p className="mt-2 text-sm leading-7 text-[#515d73]">{working.summary}</p><EvidenceChips claim={working.summaryGrounding} labelForEvidence={labelForEvidence} hoverForEvidence={hoverForEvidence} onOpenEvidence={openEvidence}/></>}</div><div className="rounded-2xl border border-[#e5e9ef] bg-[#fafbfd] p-4"><div className="text-xs font-semibold text-[#8791a4]">材料证据覆盖</div><div className="mt-4 grid grid-cols-2 gap-3">{[["材料",working.evidence.materialCount],["文本字符",working.evidence.parsedTextChars.toLocaleString("zh-CN")],["数据集",working.evidence.datasetCount],["视觉资产",working.evidence.visualAssetCount??(working.evidence.hasImages?1:0)]].map(([k,v])=><div key={String(k)}><div className="text-xl font-semibold">{v}</div><div className="mt-1 text-[10px] text-[#9aa3b2]">{k}</div></div>)}</div></div></div></div>
    </Card>

    {!isAI&&<Card className="relative overflow-hidden border border-[#dfe3ff] bg-[linear-gradient(135deg,#fbfbff,#f7f8ff_48%,#f1fbfb)] p-0"><div className="absolute inset-x-0 top-0 h-[3px] bg-[linear-gradient(90deg,#5f70ff,#8a65ef,#22b7bd)]"/><div className="relative flex flex-col gap-5 p-5 md:flex-row md:items-center md:justify-between"><div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><Badge tone="brand">推荐</Badge><span className="text-xs font-semibold uppercase tracking-[.14em] text-[#7580a0]">AI Research Understanding</span></div><h3 className="mt-2 text-base font-semibold tracking-[-.02em]">在本地画像基础上进行 AI 深度理解</h3><p className="mt-1.5 max-w-3xl text-xs leading-5 text-[#788397]">本地第一轮识别已经自动完成。AI 模式会进一步结合正文、表格、代码与视觉证据理解研究问题、核心思路和贡献，并执行 evidence grounding。只有你主动确认后才会调用外部 Provider。</p><div className="mt-2 flex flex-wrap gap-2 text-[10px] text-[#8b95a6]"><span>{capabilities?.aiConfigured?`已配置 · ${capabilities.model??capabilities.provider??"AI Provider"}`:"尚未配置 Provider"}</span>{capabilities?.ocrAvailable&&<span>· OCR {capabilities.ocrLanguages}</span>}</div></div><Button type="button" size="lg" disabled={aiRunning||syncing} onClick={handleAIAction} className="shrink-0 bg-[linear-gradient(135deg,#5367f3,#745fe8)] shadow-[0_10px_26px_rgba(83,103,243,.24)] hover:opacity-95"><BrainCircuit className="size-4"/>{syncing?"正在同步材料…":aiRunning?"AI 正在理解…":capabilities?.aiConfigured?"使用 AI 深度理解":"配置并使用 AI"}<ArrowRight className="size-4"/></Button></div></Card>}

    {aiError&&<Card className="min-w-0 overflow-hidden border border-[#f3c8ce] bg-[#fff7f8] p-4 text-sm leading-6 text-[#9d3e4d]"><div className="min-w-0 break-words"><b>AI 深度理解未完成：</b> <span className="whitespace-pre-wrap">{aiError.split("\n")[0]}</span></div><p className="mt-2 text-xs leading-5 text-[#9a6570]">Provider / 传输级失败会立即停止且不会自动重试；已经成功返回但局部 JSON 不合约的文本块会在本地保留有效字段或降级为证据摘要，不会额外发送修复请求。</p>{callTrace.length>0&&<details className="mt-3 rounded-xl border border-[#f0d8dc] bg-white/80 p-3"><summary className="cursor-pointer text-xs font-semibold">查看 Provider 调用诊断 · {callTrace.length} 次真实请求</summary><div className="mt-3 space-y-2">{callTrace.map((item,i)=><div key={i} className="rounded-lg border border-[#f1e0e3] bg-white p-3 text-[11px] leading-5 text-[#765b62]"><div className="flex flex-wrap items-center justify-between gap-2"><b>{String(item.phase??`call ${i+1}`)}</b><Badge tone={item.status==="success"?"success":item.status==="warning"?"warning":"danger"}>{String(item.status??"unknown")}</Badge></div><div className="mt-1 break-words">input {String(item.inputChars??0)} chars · visuals {String(item.visualAssets??0)} · elapsed {String(item.elapsedMs??0)} ms{item.statusCode?` · HTTP ${String(item.statusCode)}`:""}</div>{Boolean(item.requestId)&&<div className="mt-1 break-all">request_id: {String(item.requestId)}</div>}{Boolean(item.errorKind)&&<div className="mt-1 break-words"><b>kind:</b> {String(item.errorKind)}</div>}{Boolean(item.message)&&<div className="mt-1 max-h-36 overflow-auto whitespace-pre-wrap break-words rounded bg-[#fff1f3] p-2 font-mono text-[10px]">{String(item.message)}</div>}{item.rawOutputChars!=null&&<div className="mt-1 break-words">raw output: {String(item.rawOutputChars)} chars</div>}{Boolean(item.responseBody)&&<div className="mt-1 max-h-28 overflow-auto whitespace-pre-wrap break-words rounded bg-[#fff7f8] p-2">{String(item.responseBody)}</div>}{Boolean(item.responseTail)&&<details className="mt-1"><summary className="cursor-pointer text-[10px] font-semibold">查看返回尾部</summary><div className="mt-1 max-h-28 overflow-auto whitespace-pre-wrap break-words rounded bg-[#faf7f8] p-2 font-mono text-[10px]">{String(item.responseTail)}</div></details>}{Boolean(item.responseHeaders)&&Object.keys(item.responseHeaders as Record<string,unknown>).length>0&&<div className="mt-1 max-h-28 overflow-auto break-all rounded bg-[#faf7f8] p-2 text-[10px]">{Object.entries(item.responseHeaders as Record<string,unknown>).map(([k,v])=><div key={k}><b>{k}:</b> {String(v)}</div>)}</div>}</div>)}</div></details>}<div className="mt-3 flex flex-wrap gap-2"><button onClick={handleAIAction} className="inline-flex items-center gap-1.5 rounded-lg border border-[#ebc8ce] bg-white px-3 py-1.5 text-xs font-semibold text-[#9d3e4d] hover:bg-[#fff4f5]">手动重新尝试</button><button onClick={()=>router.push(`/app/settings?from=${encodeURIComponent(`/app/projects/${projectId}/profile`)}`)} className="inline-flex items-center gap-1.5 rounded-lg border border-[#ebc8ce] bg-white px-3 py-1.5 text-xs font-semibold text-[#9d3e4d] hover:bg-[#fff4f5]">检查模型与 OCR 配置 →</button></div></Card>}
    {aiRunning&&<Card className="p-5"><div className="flex items-center gap-3"><LoaderCircle className="size-5 animate-spin text-[#5b6adf]"/><div className="min-w-0 flex-1"><div className="flex items-center justify-between gap-4 text-sm"><b className="min-w-0 truncate">{run.message}</b><span className="shrink-0">{run.progress}%</span></div><ProgressBar value={run.progress} active className="mt-3"/><p className="mt-2 text-[10px] leading-4 text-[#939cad]">分块请求逐次执行；任意 Provider 错误会立即停止。不会进行后台参数降级重试。</p></div></div></Card>}
    {isAI&&requestPlan&&<Card className="border border-[#dce7f5] bg-[#f7fbff] p-4 text-xs leading-5 text-[#66758a]"><div className="flex flex-wrap items-center gap-2"><Badge tone={aiPartial?"warning":"success"}>{aiPartial?"AI 提取完成 · 本地证据汇总":"Text-first 理解完成"}</Badge><b className="text-[#40506a]">{run?.result?.providerCallsUsed??callTrace.length} 次真实 Provider 请求</b>{!aiPartial&&analysisNotes.length>0&&<Badge tone="neutral">局部字段已自动规范化</Badge>}</div><div className="mt-2 grid gap-2 sm:grid-cols-2 lg:grid-cols-7"><div>文本请求：<b>{requestPlan.textCallsPlanned??requestPlan.plannedChunkCalls??"—"}</b></div><div>视觉请求：<b>{requestPlan.visualCallsPlanned??0}</b></div><div>文本块：<b>{requestPlan.effectiveChunkTextChars??requestPlan.chunkTextChars??"—"}</b> chars</div><div title="有页码的 PDF 证据中，有多少页面至少进入过一个文本块。"><span>页覆盖：</span><b>{requestPlan.pageCoverageRatio!=null?`${Math.round(Number(requestPlan.pageCoverageRatio)*100)}%`:"—"}</b>{requestPlan.availablePages?` (${requestPlan.selectedPages??0}/${requestPlan.availablePages})`:""}</div><div title="结构化证据条目中，有多少条至少进入过一个文本块。"><span>证据覆盖：</span><b>{requestPlan.evidenceCoverageRatio!=null?`${Math.round(Number(requestPlan.evidenceCoverageRatio)*100)}%`:"—"}</b>{requestPlan.availableEvidenceItems?` (${requestPlan.selectedEvidenceItems??0}/${requestPlan.availableEvidenceItems})`:""}</div><div title="为控制 Provider 调用长度而发送的字符占全部可用解析文本的比例；这不是页面覆盖率。"><span>字符采样：</span><b>{(requestPlan.characterSamplingRatio??requestPlan.textCoverageRatio)!=null?`${Math.round(Number(requestPlan.characterSamplingRatio??requestPlan.textCoverageRatio)*100)}%`:"—"}</b></div><div>策略：<b>{requestPlan.transportProfile??"standard"}</b></div></div><div className="mt-2 text-[11px] text-[#8290a4]">页覆盖 / 证据覆盖表示是否触达材料；字符采样表示在调用预算内发送给 Provider 的压缩文本比例，两者不是同一个概念。</div>{analysisNotes.length>0&&<details className="mt-3 rounded-lg border border-[#dfe5ef] bg-white/75 p-3 text-[#708096]"><summary className="cursor-pointer font-semibold text-[#5b6880]">本地规范化记录 · {analysisNotes.length}</summary><div className="mt-2 space-y-1">{analysisNotes.map((n,i)=><div key={i}>· {n.message??"局部输出已按证据规则规范化"}{n.fields?.length?`（${n.fields.join(", ")}）`:""}</div>)}</div></details>}{analysisWarnings.length>0&&<div className="mt-3 space-y-1 rounded-lg border border-[#eadfbe] bg-[#fffaf0] p-3 text-[#7e6837]">{analysisWarnings.map((w,i)=><div key={i}>△ {w.message??"分析过程中有可选阶段未完成"}</div>)}</div>}</Card>}

    {isAI&&<div className="grid gap-5 lg:grid-cols-2"><Card className="p-6"><div className="flex items-center gap-2"><ScanText className="size-4 text-[#5868dc]"/><h3 className="text-sm font-semibold">研究问题</h3></div><p className="mt-3 text-sm leading-7 text-[#59657a]">{working.researchProblem?.text||"未获得有证据支撑的研究问题概括。"}</p><EvidenceChips claim={working.researchProblem} labelForEvidence={labelForEvidence} hoverForEvidence={hoverForEvidence} onOpenEvidence={openEvidence}/></Card><Card className="p-6"><div className="flex items-center gap-2"><BrainCircuit className="size-4 text-[#5868dc]"/><h3 className="text-sm font-semibold">核心思路</h3></div><p className="mt-3 text-sm leading-7 text-[#59657a]">{working.coreIdea?.text||"未获得有证据支撑的核心思路概括。"}</p><EvidenceChips claim={working.coreIdea} labelForEvidence={labelForEvidence} hoverForEvidence={hoverForEvidence} onOpenEvidence={openEvidence}/></Card></div>}

    <div className="grid gap-5 xl:grid-cols-[1fr_360px]">
      <div className="space-y-5"><Card className="p-6"><div className="flex items-center gap-2"><Layers3 className="size-4 text-[#6170db]"/><h3 className="text-sm font-semibold">研究领域</h3></div>{editing?<div className="mt-4"><label className="text-xs font-semibold text-[#7e889a]">Primary CCF Area</label><select value={working.primaryArea??""} onChange={e=>setWorking({...working,primaryArea:e.target.value?e.target.value as CcfAreaCode:null})} className="mt-2 h-11 w-full rounded-xl border border-[#dce1ea] bg-white px-3 text-sm"><option value="">领域尚不确定</option>{(Object.entries(CCF_AREAS) as [CcfAreaCode, (typeof CCF_AREAS)[CcfAreaCode]][]).map(([code,v])=><option key={code} value={code}>{code} · {v.zh}</option>)}</select></div>:isAI?<div className="mt-4"><div className="flex flex-wrap gap-2">{working.primaryArea&&<Badge tone="brand">Primary · {CCF_AREAS[working.primaryArea].zh}</Badge>}{working.secondaryAreas.map(code=><Badge key={code}>Secondary · {CCF_AREAS[code].zh}</Badge>)}</div>{working.areaRationale&&<><p className="mt-4 text-xs leading-6 text-[#748095]">{working.areaRationale.text}</p><EvidenceChips claim={working.areaRationale} labelForEvidence={labelForEvidence} hoverForEvidence={hoverForEvidence} onOpenEvidence={openEvidence}/></>}</div>:<div className="mt-4 space-y-3">{areaRanking.map(([code,score],i)=>{const max=Math.max(1,areaRanking[0]?.[1] as number);return <div key={code}><div className="mb-1.5 flex justify-between text-xs"><span className={i===0?"font-semibold text-[#3543b4]":"text-[#6f7a8e]"}>{CCF_AREAS[code].zh}</span><span className="text-[#9ba4b4]">{score}</span></div><div className="h-1.5 rounded-full bg-[#edf0f4]"><div className="h-full rounded-full bg-[#6676e8]" style={{width:`${Math.max(8,(Number(score)/max)*100)}%`}}/></div></div>})}</div>}</Card>
        <Card className="p-6"><h3 className="text-sm font-semibold">主题与方法</h3><div className="mt-5"><div className="mb-2 text-xs font-semibold text-[#8791a4]">Topics</div>{editing?<TagEditor values={working.topics} onChange={topics=>setWorking({...working,topics})} placeholder="添加研究主题"/>:<div className="flex flex-wrap gap-2">{working.topics.length?working.topics.map(t=><Badge key={t} tone="brand">{t}</Badge>):<span className="text-xs text-[#9aa3b2]">未识别到高置信主题</span>}</div>}</div><div className="mt-5"><div className="mb-2 text-xs font-semibold text-[#8791a4]">Methods</div>{editing?<TagEditor values={working.methods} onChange={methods=>setWorking({...working,methods})} placeholder="添加方法"/>:<div className="flex flex-wrap gap-2">{working.methods.length?working.methods.map(t=><Badge key={t}>{t}</Badge>):<span className="text-xs text-[#9aa3b2]">未识别到高置信方法</span>}</div>}</div></Card>
        <Card className="p-6"><div className="flex items-center gap-2"><CheckCircle2 className="size-4 text-[#1a9367]"/><h3 className="text-sm font-semibold">贡献</h3></div><p className="mt-2 text-xs leading-5 text-[#8b95a6]">AI 模式只保留引用当前项目有效 evidence ID 的贡献；本地模式只抽取显式贡献句。人工修改后属于用户确认内容。</p><div className="mt-4">{editing?<ListEditor values={working.contributions} onChange={contributions=>setWorking({...working,contributions})} placeholder="补充贡献点"/>:isAI?<GroundedList values={working.groundedContributions} empty="模型没有返回可通过证据校验的贡献项。" labelForEvidence={labelForEvidence} hoverForEvidence={hoverForEvidence} onOpenEvidence={openEvidence}/>:working.contributions.length?<div className="space-y-2">{working.contributions.map((text,i)=><div key={i} className="rounded-xl bg-[#f8f9fc] p-4 text-sm leading-6 text-[#5d687c]">{text}</div>)}</div>:<div className="rounded-xl border border-dashed border-[#dfe4ec] bg-[#fafbfd] p-4 text-xs leading-5 text-[#8b95a6]">未检测到可可靠抽取的显式贡献句。</div>}</div></Card>
        {isAI&&<Card className="p-6"><div className="flex items-center gap-2"><ShieldCheck className="size-4 text-[#8a641e]"/><h3 className="text-sm font-semibold">材料支持的创新主张</h3></div><p className="mt-2 text-xs leading-5 text-[#8b95a6]">这里表示上传材料声称或直接支持的 novelty，不等同于完成了全局文献检索后的“已验证创新”。</p><div className="mt-4"><GroundedList values={working.claimedNovelty} empty="没有保留下来可由当前材料直接支撑的创新主张。" labelForEvidence={labelForEvidence} hoverForEvidence={hoverForEvidence} onOpenEvidence={openEvidence}/></div></Card>}
        <Card className="p-6"><h3 className="text-sm font-semibold">研究问题列表</h3><div className="mt-4">{editing?<ListEditor values={working.researchQuestions} onChange={researchQuestions=>setWorking({...working,researchQuestions})} placeholder="补充研究问题"/>:isAI?<GroundedList values={working.groundedResearchQuestions} empty="没有通过证据校验的研究问题列表项。" labelForEvidence={labelForEvidence} hoverForEvidence={hoverForEvidence} onOpenEvidence={openEvidence}/>:working.researchQuestions.length?<div className="space-y-2">{working.researchQuestions.map((q,i)=><div key={i} className="rounded-xl bg-[#f8f9fc] p-4 text-sm leading-6 text-[#5d687c]">{q}</div>)}</div>:<div className="rounded-xl border border-dashed border-[#dfe4ec] bg-[#fafbfd] p-4 text-xs leading-5 text-[#8b95a6]">未检测到显式研究问题句。</div>}</div></Card>
        <Card className="p-6"><div className="flex items-center gap-2"><FlaskConical className="size-4 text-[#9a6f21]"/><h3 className="text-sm font-semibold">实验与技术证据</h3></div><div className="mt-5 grid gap-5 md:grid-cols-3">{[["Datasets","datasets",working.datasets],["Models","models",working.models],["Metrics","metrics",working.metrics]].map(([label,key,values])=><div key={String(label)}><div className="text-xs font-semibold text-[#8791a4]">{String(label)}</div>{editing?<div className="mt-2"><TagEditor values={values as string[]} onChange={next=>setWorking({...working,[key as "datasets"|"models"|"metrics"]:next})} placeholder={`添加 ${String(label)}`}/></div>:<div className="mt-2 flex flex-wrap gap-1.5">{(values as string[]).length?(values as string[]).map(v=><Badge key={v}>{v}</Badge>):<span className="text-xs text-[#a0a8b6]">未检测到</span>}</div>}</div>)}</div></Card>
        {working.gaps.length>0&&<Card className="p-6"><h3 className="text-sm font-semibold">Current signals to consider</h3><p className="mt-2 text-xs leading-5 text-[#8b95a6]">这些是当前材料覆盖信号，不是审稿结论。</p><div className="mt-4">{isAI?<GroundedList values={working.groundedGaps} empty="没有通过证据校验的 gap 观察。" labelForEvidence={labelForEvidence} hoverForEvidence={hoverForEvidence} onOpenEvidence={openEvidence}/>:<div className="space-y-2">{working.gaps.map((g,i)=><div key={i} className="rounded-xl border border-[#f0e7d5] bg-[#fffaf0] px-4 py-3 text-xs leading-5 text-[#80653a]">△ {g}</div>)}</div>}</div></Card>}
        {isAI&&displayArtifacts.length>0&&<Card className="p-6"><div className="flex items-center gap-2"><Eye className="size-4 text-[#5969dc]"/><h3 className="text-sm font-semibold">视觉证据</h3></div><p className="mt-2 text-xs leading-5 text-[#8b95a6]">优先展示按 Figure / Table caption 重建的局部科研图，而不是整页截图或 PDF 内部碎片。点击任意卡片可查看大图，并可继续定位到原论文对应页。</p><div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{displayArtifacts.map(artifact=><button type="button" key={artifact.id} onClick={()=>openEvidence(artifact.id)} title={hoverForEvidence(artifact.id)} className="group overflow-hidden rounded-xl border border-[#e4e8ef] bg-[#fafbfd] text-left transition hover:-translate-y-0.5 hover:border-[#cbd2f5] hover:shadow-[0_10px_28px_rgba(48,61,118,.08)]"><div className="aspect-[4/3] overflow-hidden bg-white p-2"><img src={researchArtifactUrl(artifact.url)} alt={artifact.label} className="h-full w-full object-contain transition group-hover:scale-[1.015]"/></div><div className="p-3"><div className="truncate text-xs font-semibold text-[#566176]">{labelForEvidence(artifact.id)}</div><div className="mt-1 line-clamp-2 min-h-8 text-[9px] leading-4 text-[#929bad]">{artifact.caption??(artifact.kind==="page_render"?"未检测到可稳定裁剪的 Figure/Table，显示页面级 fallback。":"局部视觉证据")}</div></div></button>)}</div></Card>}
      </div>
      <aside className="space-y-4 xl:sticky xl:top-24 xl:self-start"><Card className="p-5"><div className="text-xs font-semibold uppercase tracking-[.14em] text-[#8b95a6]">Research Stage</div><div className="mt-3 text-xl font-semibold capitalize">{working.stage.replace("_"," ")}</div><div className="mt-4 grid grid-cols-4 gap-1">{["idea","early","experimental","manuscript"].map((s,i)=><div key={s} className={`h-1.5 rounded-full ${["idea","early","experimental","manuscript","submission_ready"].indexOf(working.stage)>=i?"bg-[#6171e4]":"bg-[#e7eaf0]"}`}/>)}</div>{working.stageRationale?<><p className="mt-3 text-[11px] leading-5 text-[#8d97a8]">{working.stageRationale.text}</p><EvidenceChips claim={working.stageRationale} labelForEvidence={labelForEvidence} hoverForEvidence={hoverForEvidence} onOpenEvidence={openEvidence}/></>:<p className="mt-3 text-[11px] leading-5 text-[#8d97a8]">阶段只表示当前材料成熟度，不等同于论文质量或录用概率。</p>}</Card><Card className="p-5"><div className="grid grid-cols-2 gap-3 text-center">{[[FileCode2,working.evidence.hasSource,"Source"],[Database,working.evidence.hasData,"Data"],[ImageIcon,working.evidence.hasImages,"Visual"],[CheckCircle2,working.evidence.hasManuscript,"Manuscript"]].map(([Icon,yes,label])=>{const I=Icon as typeof FileCode2;return <div key={String(label)} className={`rounded-xl p-3 ${yes?"bg-[#eef9f4] text-[#187e59]":"bg-[#f5f6f8] text-[#9aa3b2]"}`}><I className="mx-auto size-4"/><div className="mt-2 text-[10px] font-semibold">{String(label)}</div></div>})}</div></Card><Card className="p-5"><h3 className="text-sm font-semibold">解析能力</h3><div className="mt-3 space-y-2 text-xs text-[#7e899b]"><div className="flex items-center justify-between"><span>OCR</span><Badge tone={capabilities?.ocrAvailable?"success":"neutral"}>{capabilities?.ocrAvailable?`Available · ${capabilities.ocrLanguages}`:"Unavailable"}</Badge></div><div className="flex items-center justify-between"><span>AI</span><Badge tone={capabilities?.aiConfigured?"success":"neutral"}>{capabilities?.aiConfigured?(capabilities.model??"Configured"):"Not configured"}</Badge></div></div></Card><Card className="p-5"><h3 className="text-sm font-semibold">确认后继续</h3><p className="mt-2 text-xs leading-5 text-[#818b9d]">推荐会使用这里的主领域、主题、方法与研究证据信号。任何不准确字段都应先人工校正。</p><Link href={`/app/projects/${projectId}/preferences`}><Button className="mt-4 w-full">进入投稿偏好 <ArrowRight className="size-4"/></Button></Link></Card></aside>
    </div>

    <Modal open={Boolean(selectedEvidence)} onClose={()=>setSelectedEvidenceId(undefined)} title={selectedEvidence?.label??"项目证据"} size="xl" footer={<>{selectedEvidence?.sourceUrl&&<Button variant="secondary" onClick={()=>window.open(selectedEvidence.sourceUrl,"_blank","noopener,noreferrer")}>打开原始材料{selectedEvidence.page?` · p.${selectedEvidence.page}`:""}</Button>}<Button onClick={()=>setSelectedEvidenceId(undefined)}>关闭</Button></>}>
      {selectedEvidence&&<div className="space-y-4"><div className="flex flex-wrap gap-2"><Badge tone="brand">{selectedEvidence.kind}</Badge>{selectedEvidence.materialName&&<Badge>{selectedEvidence.materialName}</Badge>}{selectedEvidence.page&&<Badge>p.{selectedEvidence.page}</Badge>}{selectedEvidence.path&&<Badge>{selectedEvidence.path}</Badge>}{selectedEvidence.sheet&&<Badge>{selectedEvidence.sheet}</Badge>}</div>{selectedEvidence.caption&&<div className="rounded-xl border border-[#e4e8ef] bg-[#fafbfd] px-4 py-3 text-xs leading-5 text-[#667286]"><b className="text-[#4d596e]">Caption：</b>{selectedEvidence.caption}</div>}{selectedEvidence.previewUrl?<div className="overflow-hidden rounded-2xl border border-[#e2e6ee] bg-[#f7f8fb] p-3"><img src={selectedEvidence.previewUrl} alt={selectedEvidence.label} className="mx-auto max-h-[58vh] w-auto max-w-full object-contain"/></div>:selectedEvidence.pageImageUrl?<div className="overflow-auto rounded-2xl border border-[#e2e6ee] bg-[#f7f8fb] p-3"><img src={selectedEvidence.pageImageUrl} alt={selectedEvidence.label} className="mx-auto max-h-[62vh] w-auto max-w-full object-contain"/></div>:null}{selectedEvidence.excerpt&&<div className="rounded-xl border border-[#e4e8ef] bg-white p-4"><div className="text-[10px] font-semibold uppercase tracking-[.12em] text-[#8993a4]">Evidence excerpt</div><p className="mt-2 whitespace-pre-wrap break-words text-xs leading-6 text-[#5d687a]">{selectedEvidence.excerpt}</p></div>}<details className="rounded-xl border border-[#edf0f4] bg-[#fafbfd] px-4 py-3 text-[10px] leading-5 text-[#939cad]"><summary className="cursor-pointer font-semibold">技术追溯信息</summary><div className="mt-2 break-all">Internal evidence ID: {selectedEvidence.id}</div></details></div>}
    </Modal>

    <Modal open={consentOpen} onClose={()=>setConsentOpen(false)} title="启动 AI 深度研究理解" footer={<><Button variant="secondary" onClick={()=>setConsentOpen(false)}>取消</Button><Button onClick={()=>void startAI()}><BrainCircuit className="size-4"/>确认并开始</Button></>}><div className="space-y-4 text-sm leading-6 text-[#697589]"><p>这一步会调用你在“系统连接与解析”中选择的 AI Provider，并且只有在你点击确认后才会开始。</p><div className="rounded-xl bg-[#f7f8fb] p-4 text-xs leading-5"><b className="text-[#46526b]">发送策略：</b> 不上传整份原始 PDF。先在本地读取正文 / 表格 / OCR / 代码并重建 Figure / Table 局部视觉证据，然后只发送受限文本块；文字抽取成功后，Vision Provider 才会把少量高优先级科研图逐张单独发送，最终汇总只使用已经压缩过的研究事实。<br/><br/><b className="text-[#46526b]">硬调用预算：</b> 最多 {capabilities?.maxProviderCalls??"—"} 次真实 Provider 请求。自定义网关在“自动”策略下会使用 Edge-safe 小块；SDK 自动重试为 0。图片阶段失败不会丢掉已经成功的文本理解；最终汇总失败也不会再次调用 Provider，而会保留抽取结果并在本地组装画像。</div><p>模型输出还会经过 evidence ID 校验；没有当前项目有效证据引用的贡献、研究问题、创新主张、gap 与视觉观察会被后端丢弃。</p></div></Modal>
  </div>;
}
