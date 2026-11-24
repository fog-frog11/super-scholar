"use client";

import Link from "next/link";
import { Archive, ArchiveRestore, MoreHorizontal, Pencil, Trash2 } from "lucide-react";
import { useState } from "react";
import { Badge, Button, Input, Modal } from "./ui";
import { STATUS_LABELS } from "@/lib/constants";
import { formatDate } from "@/lib/utils";
import type { ResearchProject } from "@/lib/types";
import { useAppStore } from "@/store/use-app-store";
import { deleteStored } from "@/lib/storage";

export function ProjectCard({ project }: { project: ResearchProject }) {
  const [menu, setMenu] = useState(false);
  const [rename, setRename] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [name, setName] = useState(project.name);
  const store = useAppStore();
  const href = project.status === "draft" || project.status === "materials" || project.status === "analyzing" ? `/app/projects/${project.id}/materials` : project.status === "profile_ready" ? `/app/projects/${project.id}/profile` : project.status === "preferences_ready" ? `/app/projects/${project.id}/preferences` : `/app/projects/${project.id}/recommendations`;
  const remove = async () => {
    const materials = store.deleteProject(project.id);
    for (const material of materials) { await deleteStored(material.storageKey); await deleteStored(material.textStorageKey); }
    setConfirmDelete(false);
  };
  return <>
    <div className="surface group relative rounded-2xl p-5 transition hover:-translate-y-0.5 hover:border-[#d8ddeb] hover:shadow-[0_14px_38px_rgba(34,44,72,.08)]">
      <Link href={href} className="block pr-7"><div className="flex flex-wrap items-center gap-2"><Badge tone={project.status === "venue_selected" ? "success" : "brand"}>{STATUS_LABELS[project.status]}</Badge><span className="text-[11px] text-[#9ba4b3]">{formatDate(project.updatedAt)}</span></div><h3 className="mt-4 truncate text-base font-semibold tracking-[-.015em]">{project.name}</h3><p className="mt-2 line-clamp-2 min-h-10 text-xs leading-5 text-[#7d8799]">{project.brief || "尚未填写研究简述。进入项目后可以直接添加论文、代码、实验数据或图片。"}</p><div className="mt-5 flex items-center gap-3 text-[11px] text-[#929bad]"><span>{project.materialIds.length} 份材料</span>{project.profile && <><span>·</span><span>{project.profile.topics.length} 个主题信号</span></>}{project.recommendationRun?.status === "ready" && <><span>·</span><span>{project.recommendationRun.results.length} 个推荐</span></>}</div></Link>
      <div className="absolute right-3 top-3"><Button variant="ghost" size="sm" className="size-8 p-0" onClick={()=>setMenu(v=>!v)}><MoreHorizontal className="size-4"/></Button>{menu && <div className="absolute right-0 top-9 z-20 w-40 rounded-xl border border-[#e2e6ed] bg-white p-1.5 shadow-[0_14px_36px_rgba(24,31,52,.14)]"><button onClick={()=>{setRename(true);setMenu(false)}} className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-xs text-[#4f5a70] hover:bg-[#f4f6f9]"><Pencil className="size-3.5"/>重命名</button><button onClick={()=>{store.archiveProject(project.id,!project.archived);setMenu(false)}} className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-xs text-[#4f5a70] hover:bg-[#f4f6f9]">{project.archived?<ArchiveRestore className="size-3.5"/>:<Archive className="size-3.5"/>}{project.archived?"恢复项目":"归档"}</button><button onClick={()=>{setConfirmDelete(true);setMenu(false)}} className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-xs text-[#b83c4e] hover:bg-[#fff1f3]"><Trash2 className="size-3.5"/>删除</button></div>}</div>
    </div>
    <Modal open={rename} onClose={()=>setRename(false)} title="重命名项目" footer={<><Button variant="secondary" onClick={()=>setRename(false)}>取消</Button><Button onClick={()=>{if(name.trim()){store.renameProject(project.id,name);setRename(false)}}}>保存</Button></>}><Input value={name} onChange={(e)=>setName(e.target.value)} autoFocus /></Modal>
    <Modal open={confirmDelete} onClose={()=>setConfirmDelete(false)} title="删除研究项目" footer={<><Button variant="secondary" onClick={()=>setConfirmDelete(false)}>取消</Button><Button variant="danger" onClick={remove}>永久删除</Button></>}><p className="text-sm leading-6 text-[#697487]">将删除 <b>{project.name}</b> 及其 {project.materialIds.length} 份项目材料、解析结果、研究画像、偏好和推荐记录。此操作不可恢复。</p></Modal>
  </>;
}
