"use client";

import Link from "next/link";
import { Check } from "lucide-react";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import type { ResearchProject } from "@/lib/types";

const steps = [
  { key: "materials", label: "材料", path: "materials" },
  { key: "profile", label: "研究画像", path: "profile" },
  { key: "preferences", label: "投稿偏好", path: "preferences" },
  { key: "recommendations", label: "智能推荐", path: "recommendations" }
] as const;

function completed(project: ResearchProject, key: string) {
  if (key === "materials") return project.materialIds.length > 0;
  if (key === "profile") return Boolean(project.profile);
  if (key === "preferences") return ["preferences_ready", "recommending", "recommendations_ready", "venue_selected"].includes(project.status);
  if (key === "recommendations") return project.recommendationRun?.status === "ready";
  return false;
}

export function ProjectStepper({ project }: { project: ResearchProject }) {
  const pathname = usePathname();
  return <div className="surface rounded-2xl px-4 py-3"><div className="grid grid-cols-4 gap-2">{steps.map((step, index) => {
    const href = `/app/projects/${project.id}/${step.path}`;
    const active = pathname.includes(`/${step.path}`);
    const done = completed(project, step.key);
    return <Link href={href} key={step.key} className={cn("relative flex items-center gap-2.5 rounded-xl px-3 py-2.5 transition", active ? "bg-[#edf0ff]" : "hover:bg-[#f5f7fa]")}>
      <div className={cn("grid size-7 shrink-0 place-items-center rounded-full border text-xs font-semibold", done ? "border-[#5970f2] bg-[#5970f2] text-white" : active ? "border-[#8792ff] bg-white text-[#5262d9]" : "border-[#dce1ea] bg-white text-[#8c96a8]")}>{done ? <Check className="size-3.5"/> : index + 1}</div>
      <div className="min-w-0"><div className={cn("truncate text-xs font-semibold", active ? "text-[#3746bf]" : "text-[#4f5a70]")}>{step.label}</div><div className="mt-0.5 hidden text-[10px] text-[#9aa3b2] sm:block">{done ? "已完成" : active ? "当前步骤" : "待处理"}</div></div>
    </Link>;
  })}</div></div>;
}
