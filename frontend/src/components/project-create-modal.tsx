"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button, Input, Modal, Textarea } from "./ui";
import { useAppStore } from "@/store/use-app-store";

export function ProjectCreateModal({ open, onClose }: { open:boolean; onClose:()=>void }) {
  const [name, setName] = useState("");
  const [brief, setBrief] = useState("");
  const createProject = useAppStore((s)=>s.createProject);
  const router = useRouter();
  const submit = () => {
    if (!name.trim()) return;
    const project = createProject(name, brief);
    setName(""); setBrief(""); onClose();
    router.push(`/app/projects/${project.id}/materials`);
  };
  return <Modal open={open} onClose={onClose} title="创建研究项目" footer={<><Button variant="secondary" onClick={onClose}>取消</Button><Button onClick={submit} disabled={!name.trim()}>创建项目</Button></>}>
    <div className="space-y-5">
      <label className="block"><div className="mb-2 text-sm font-semibold">项目名称 <span className="text-[#d34c5c]">*</span></div><Input value={name} onChange={(e)=>setName(e.target.value)} placeholder="例如：Efficient Federated Semantic Segmentation" autoFocus /></label>
      <label className="block"><div className="mb-2 text-sm font-semibold">研究简述 / 你的要求 <span className="font-normal text-[#9aa3b2]">可选</span></div><Textarea value={brief} onChange={(e)=>setBrief(e.target.value)} placeholder="简单说明你在做什么、目前有什么材料，或者你希望寻找什么类型的投稿目标。后续可以继续修改。" /></label>
      <div className="rounded-xl bg-[#f6f7fb] px-4 py-3 text-xs leading-5 text-[#7e889a]">项目名称是用户可见的主标识；内部使用稳定 UUID 作为主键，因此重命名不会破坏材料、研究画像、投稿偏好、推荐结果或对比关系。</div>
    </div>
  </Modal>;
}
