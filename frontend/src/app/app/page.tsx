"use client";

import { ArrowRight, FolderPlus, Layers3, Plus, Sparkles } from "lucide-react";
import { useMemo, useState } from "react";
import Link from "next/link";
import { Button, Card, EmptyState } from "@/components/ui";
import { ProjectCreateModal } from "@/components/project-create-modal";
import { ProjectCard } from "@/components/project-card";
import { useAppStore } from "@/store/use-app-store";

export default function WorkspacePage() {
  const [create, setCreate] = useState(false);
  const projects = useAppStore((s)=>s.projects).filter((p)=>!p.archived);
  const stats = useMemo(()=>({ active:projects.length, profiled:projects.filter(p=>p.profile).length, ready:projects.filter(p=>p.recommendationRun?.status==="ready").length, selected:projects.filter(p=>p.selectedVenueId).length }),[projects]);
  return <div className="mx-auto max-w-[1380px] px-5 py-8 lg:px-8 lg:py-10">
    <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between"><div><div className="text-xs font-semibold uppercase tracking-[.16em] text-[#8791a5]">Workspace</div><h1 className="mt-2 text-3xl font-semibold tracking-[-.045em]">你的研究，从这里开始。</h1><p className="mt-2 text-sm text-[#7d8799]">创建项目，整理材料，确认研究画像，再进入投稿推荐。</p></div><Button size="lg" onClick={()=>setCreate(true)}><Plus className="size-4"/>新建研究项目</Button></div>
    <div className="mt-8 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{[["研究项目",stats.active,"Active projects"],["研究画像",stats.profiled,"Profiles ready"],["推荐完成",stats.ready,"Recommendation ready"],["已选目标",stats.selected,"Venue selected"]].map(([label,value,sub],i)=><Card key={String(label)} className="p-5"><div className="flex items-center justify-between"><div className="text-xs font-medium text-[#8490a2]">{label}</div><div className={`grid size-8 place-items-center rounded-xl ${i===0?"bg-[#edf0ff] text-[#5868e4]":i===1?"bg-[#edf8f7] text-[#168a91]":i===2?"bg-[#fff6e8] text-[#a56c12]":"bg-[#eaf8f2] text-[#17815a]"}`}>{i===0?<Layers3 className="size-4"/>:i===1?<Sparkles className="size-4"/>:i===2?<ArrowRight className="size-4"/>:<span className="text-xs font-bold">✓</span>}</div></div><div className="mt-5 text-3xl font-semibold tracking-[-.04em]">{value}</div><div className="mt-1 text-[11px] text-[#a0a8b6]">{sub}</div></Card>)}</div>
    <div className="mt-10 flex items-center justify-between"><div><h2 className="text-lg font-semibold tracking-[-.02em]">最近项目</h2><p className="mt-1 text-xs text-[#929bad]">最近更新的研究项目</p></div>{projects.length>0 && <Link href="/app/projects" className="text-xs font-semibold text-[#5a68d7] hover:text-[#3948bf]">查看全部 →</Link>}</div>
    <div className="mt-4">{projects.length ? <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{projects.slice(0,6).map((project)=><ProjectCard key={project.id} project={project}/>)}</div> : <EmptyState icon={<FolderPlus className="size-5"/>} title="开始建立第一个研究项目" description="项目会保存材料、研究画像、投稿偏好、推荐结果和最终选择。所有材料在当前前端阶段优先保存在浏览器本地。" action={<Button onClick={()=>setCreate(true)}><Plus className="size-4"/>新建研究项目</Button>} />}</div>
    <ProjectCreateModal open={create} onClose={()=>setCreate(false)}/>
  </div>;
}
