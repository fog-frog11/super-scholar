"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowRight, Database, Edit3, FileStack, Goal, Sparkles } from "lucide-react";
import { Badge, Button, Card, Input, Modal, Textarea } from "@/components/ui";
import { CCF_AREAS } from "@/lib/constants";
import { useAppStore } from "@/store/use-app-store";
import { useEffect, useState } from "react";

export default function ProjectOverviewPage() {
  const { projectId } = useParams<{projectId:string}>();
  const project = useAppStore((s)=>s.projects.find(p=>p.id===projectId));
  const updateProject = useAppStore((s)=>s.updateProject);
  const [editing,setEditing]=useState(false);
  const [name,setName]=useState("");
  const [brief,setBrief]=useState("");
  useEffect(()=>{if(project){setName(project.name);setBrief(project.brief)}},[project]);
  if (!project) return null;
  const cards = [
    { title:"研究材料", icon:FileStack, value:`${project.materialIds.length} 份`, detail:project.materialIds.length?"已加入项目":"等待添加", href:`/app/projects/${projectId}/materials` },
    { title:"研究画像", icon:Sparkles, value:project.profile?(project.profile.primaryArea?CCF_AREAS[project.profile.primaryArea].zh:"领域待确认"):"尚未生成", detail:project.profile?project.profile.topics.slice(0,2).join(" · "):"需要先解析材料", href:`/app/projects/${projectId}/profile` },
    { title:"投稿偏好", icon:Goal, value:project.preferences.targetType==="both"?"期刊 + 会议":project.preferences.targetType==="journal"?"期刊":"会议", detail:project.status==="draft"?"尚未确认":"偏好可随时调整", href:`/app/projects/${projectId}/preferences` },
    { title:"推荐结果", icon:Database, value:project.recommendationRun?.status==="ready"?`${project.recommendationRun.results.length} 个候选`:"尚未运行", detail:project.selectedVenueId?"已选择目标 venue":"等待推荐", href:`/app/projects/${projectId}/recommendations` }
  ];
  const saveInfo=()=>{if(!name.trim())return;const briefChanged=brief.trim()!==project.brief;updateProject(projectId,{name:name.trim(),brief:brief.trim(),...(briefChanged?{profile:undefined,recommendationRun:undefined,comparisonVenueIds:[],selectedVenueId:undefined,status:project.materialIds.length?"materials":"draft" as const}:{})});setEditing(false)};
  return <div><div className="mb-5 flex items-center justify-between gap-4 rounded-2xl border border-[#e2e6ed] bg-white px-5 py-4"><div className="min-w-0"><div className="text-xs font-semibold uppercase tracking-[.14em] text-[#9099aa]">Project details</div><div className="mt-1 truncate text-sm text-[#647086]">{project.brief||"尚未填写研究简述；可以只用材料，也可以补充研究说明。"}</div></div><Button variant="secondary" size="sm" onClick={()=>setEditing(true)}><Edit3 className="size-3.5"/>编辑项目信息</Button></div><div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">{cards.map(({title,icon:Icon,value,detail,href})=><Link key={title} href={href}><Card className="h-full p-5 transition hover:-translate-y-0.5 hover:shadow-[0_14px_36px_rgba(31,42,72,.08)]"><div className="flex items-center justify-between"><div className="text-xs font-semibold text-[#808a9c]">{title}</div><div className="grid size-8 place-items-center rounded-xl bg-[#f0f2ff] text-[#5f6de0]"><Icon className="size-4"/></div></div><div className="mt-5 text-lg font-semibold">{value}</div><div className="mt-1 truncate text-xs text-[#98a1b0]">{detail}</div><div className="mt-4 inline-flex items-center gap-1 text-xs font-semibold text-[#5a68d7]">打开 <ArrowRight className="size-3.5"/></div></Card></Link>)}</div><Card className="mt-5 p-6"><div className="flex flex-col gap-5 sm:flex-row sm:items-center"><div className="flex-1"><div className="flex items-center gap-2"><h2 className="text-base font-semibold">继续你的研究项目</h2>{project.selectedVenueId && <Badge tone="success">已选择投稿目标</Badge>}</div><p className="mt-2 text-sm leading-6 text-[#7c8799]">Super Scholar 会保留每一步状态。你可以返回任何阶段补充材料、修改研究画像或调整投稿偏好，再重新运行推荐。</p></div><Link href={project.materialIds.length===0?`/app/projects/${projectId}/materials`:!project.profile?`/app/projects/${projectId}/profile`:project.recommendationRun?.status!=="ready"?`/app/projects/${projectId}/preferences`:`/app/projects/${projectId}/recommendations`}><Button>继续 <ArrowRight className="size-4"/></Button></Link></div></Card><Modal open={editing} onClose={()=>setEditing(false)} title="编辑项目信息" footer={<><Button variant="secondary" onClick={()=>setEditing(false)}>取消</Button><Button disabled={!name.trim()} onClick={saveInfo}>保存修改</Button></>}><div className="space-y-4"><label className="block"><div className="mb-2 text-sm font-semibold">项目名称</div><Input value={name} onChange={e=>setName(e.target.value)}/></label><label className="block"><div className="mb-2 text-sm font-semibold">研究简述 / 你的要求</div><Textarea value={brief} onChange={e=>setBrief(e.target.value)}/></label><div className="rounded-xl bg-[#f7f8fb] p-3 text-xs leading-5 text-[#7f899b]">修改研究简述会使已有研究画像和推荐失效，因为研究简述本身也是画像输入；重新进入 Research Profile 即可生成新的结果。</div></div></Modal></div>;
}
