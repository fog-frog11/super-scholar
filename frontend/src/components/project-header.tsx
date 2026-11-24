"use client";

import Link from "next/link";
import { ChevronLeft } from "lucide-react";
import { Badge, Button } from "./ui";
import { STATUS_LABELS } from "@/lib/constants";
import type { ResearchProject } from "@/lib/types";

export function ProjectHeader({ project }: { project: ResearchProject }) {
  return <div className="mb-5 flex items-start gap-4"><Link href="/app/projects"><Button variant="secondary" size="sm" className="mt-1 size-9 p-0"><ChevronLeft className="size-4"/></Button></Link><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><h1 className="truncate text-2xl font-semibold tracking-[-.035em]">{project.name}</h1><Badge tone={project.status === "venue_selected" ? "success" : "brand"}>{STATUS_LABELS[project.status]}</Badge></div>{project.brief && <p className="mt-1.5 max-w-3xl truncate text-sm text-[#7b8597]">{project.brief}</p>}</div></div>;
}
