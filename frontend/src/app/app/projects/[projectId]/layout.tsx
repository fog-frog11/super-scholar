"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { FolderX, LoaderCircle, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";
import { ProjectHeader } from "@/components/project-header";
import { ProjectStepper } from "@/components/project-stepper";
import { Button, EmptyState } from "@/components/ui";
import { recoverProjectFromServer } from "@/lib/project-recovery";
import { useAppStore } from "@/store/use-app-store";

export default function ProjectLayout({ children }: { children: React.ReactNode }) {
  const { projectId } = useParams<{ projectId:string }>();
  const hydrated = useAppStore((s)=>s.hydrated);
  const project = useAppStore((s)=>s.projects.find((p)=>p.id===projectId));
  const [recoveryState,setRecoveryState]=useState<"idle"|"loading"|"done"|"offline">("idle");
  const [recoveryNonce,setRecoveryNonce]=useState(0);

  useEffect(()=>{
    if(!hydrated || project || recoveryState==="loading") return;
    let cancelled=false;
    setRecoveryState("loading");
    void recoverProjectFromServer(projectId)
      .then((result)=>{ if(!cancelled) setRecoveryState(result?"done":"done"); })
      .catch(()=>{ if(!cancelled) setRecoveryState("offline"); });
    return ()=>{ cancelled=true; };
    // recoveryNonce intentionally allows the Retry button to trigger one fresh lookup.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  },[hydrated,project,projectId,recoveryNonce]);

  if (!hydrated || (!project && (recoveryState==="idle" || recoveryState==="loading"))) {
    return <div className="mx-auto max-w-[1320px] px-5 py-10 lg:px-8"><div className="surface grid min-h-[360px] place-items-center rounded-2xl"><div className="text-center"><LoaderCircle className="mx-auto size-6 animate-spin text-[#6070df]"/><div className="mt-3 text-sm font-semibold text-[#4b566d]">正在恢复研究项目…</div><p className="mt-1 text-xs text-[#8b95a6]">先读取浏览器状态；如果本地不存在，再从后端恢复项目与材料索引。</p></div></div></div>;
  }

  if (!project) return <div className="mx-auto max-w-[1320px] px-5 py-10 lg:px-8"><EmptyState icon={<FolderX className="size-5"/>} title="找不到这个研究项目" description={recoveryState==="offline"?"当前后端不可达，而且浏览器本地也没有这份项目数据。你的项目不会因为页面刷新而被自动删除；恢复后端连接后可以重新尝试。":"浏览器与后端都没有找到这个项目。它可能已经被删除，或者你打开的是另一套数据目录。"} action={<div className="flex flex-wrap justify-center gap-2"><Button variant="secondary" onClick={()=>{setRecoveryState("idle");setRecoveryNonce((v)=>v+1)}}><RefreshCw className="size-4"/>重新恢复</Button><Link href="/app/projects"><Button>返回项目列表</Button></Link></div>}/></div>;

  return <div className="mx-auto max-w-[1320px] px-5 py-8 lg:px-8 lg:py-9"><ProjectHeader project={project}/><ProjectStepper project={project}/><div className="mt-5">{children}</div></div>;
}
