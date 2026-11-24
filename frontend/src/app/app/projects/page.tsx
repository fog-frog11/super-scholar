"use client";

import { ArchiveRestore, FolderPlus, Plus, Search } from "lucide-react";
import { useEffect, useState } from "react";
import { Button, EmptyState, Input } from "@/components/ui";
import { ProjectCreateModal } from "@/components/project-create-modal";
import { ProjectCard } from "@/components/project-card";
import { useAppStore } from "@/store/use-app-store";

export default function ProjectsPage() {
  
  const [create,setCreate]=useState(false); const [query,setQuery]=useState(""); const [archived,setArchived]=useState(false);
  useEffect(()=>{if(typeof window!=="undefined")setArchived(new URLSearchParams(window.location.search).get("view")==="archived")},[]);
  const projects=useAppStore((s)=>s.projects).filter(p=>p.archived===archived && `${p.name} ${p.brief}`.toLowerCase().includes(query.toLowerCase()));
  return <div className="mx-auto max-w-[1380px] px-5 py-8 lg:px-8 lg:py-10"><div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between"><div><div className="text-xs font-semibold uppercase tracking-[.16em] text-[#8791a5]">Projects</div><h1 className="mt-2 text-3xl font-semibold tracking-[-.045em]">研究项目</h1><p className="mt-2 text-sm text-[#7d8799]">项目是 Super Scholar 中材料、分析和投稿决策的持久容器。</p></div><Button onClick={()=>setCreate(true)}><Plus className="size-4"/>新建项目</Button></div><div className="mt-8 flex flex-col gap-3 sm:flex-row"><div className="relative max-w-md flex-1"><Search className="absolute left-3.5 top-3.5 size-4 text-[#9ca5b5]"/><Input className="pl-10" value={query} onChange={(e)=>setQuery(e.target.value)} placeholder="搜索名称或研究简述"/></div><div className="flex rounded-xl border border-[#dfe4ec] bg-white p-1"><button onClick={()=>setArchived(false)} className={`rounded-lg px-4 py-2 text-xs font-semibold ${!archived?"bg-[#edf0ff] text-[#4c5bd1]":"text-[#7f899b]"}`}>进行中</button><button onClick={()=>setArchived(true)} className={`rounded-lg px-4 py-2 text-xs font-semibold ${archived?"bg-[#edf0ff] text-[#4c5bd1]":"text-[#7f899b]"}`}>已归档</button></div></div><div className="mt-5">{projects.length?<div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{projects.map(p=><ProjectCard key={p.id} project={p}/>)}</div>:<EmptyState icon={archived?<ArchiveRestore className="size-5"/>:<FolderPlus className="size-5"/>} title={archived?"没有归档项目":"没有符合条件的项目"} description={archived?"归档的研究项目会显示在这里。":"可以清除搜索条件，或者创建一个新的研究项目。"} action={!archived?<Button onClick={()=>setCreate(true)}>新建项目</Button>:undefined}/>}</div><ProjectCreateModal open={create} onClose={()=>setCreate(false)}/></div>;
}
