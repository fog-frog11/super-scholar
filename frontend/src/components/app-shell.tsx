"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Archive, ChevronRight, Home, Layers3, Search, Settings2 } from "lucide-react";
import { Logo } from "./logo";
import { BackendStatus } from "./backend-status";
import { BackendHydrator } from "./backend-hydrator";
import { cn } from "@/lib/utils";

const nav = [
  { href: "/app", label: "工作台", icon: Home },
  { href: "/app/projects", label: "研究项目", icon: Layers3 },
  { href: "/app/settings", label: "连接与解析", icon: Settings2 }
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  return (
    <div className="min-h-screen bg-[#f7f8fb]">
      <BackendHydrator />
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-[236px] border-r border-[#e4e8ef] bg-[#fbfcfe] px-4 py-4 lg:block">
        <Link href="/" className="block rounded-xl px-2 py-1"><Logo /></Link>
        <nav className="mt-8 space-y-1">
          {nav.map((item) => {
            const active = item.href === "/app" ? pathname === item.href : pathname.startsWith(item.href);
            const Icon = item.icon;
            return <Link key={item.href} href={item.href} className={cn("group flex h-10 items-center gap-3 rounded-xl px-3 text-sm font-medium transition", active ? "bg-[#edf0ff] text-[#3948c7]" : "text-[#687287] hover:bg-[#f0f2f7] hover:text-[#1f2941]")}><Icon className="size-4"/><span>{item.label}</span>{active && <ChevronRight className="ml-auto size-3.5 opacity-55"/>}</Link>;
          })}
        </nav>
        <div className="absolute bottom-4 left-4 right-4 border-t border-[#eceff4] pt-3">
          <BackendStatus />
          <Link href="/app/projects?view=archived" className="flex h-10 w-full items-center gap-3 rounded-xl px-3 text-sm font-medium text-[#7a8497] hover:bg-[#f0f2f7]"><Archive className="size-4"/>归档项目</Link>
        </div>
      </aside>
      <div className="lg:pl-[236px]">
        <header className="sticky top-0 z-30 flex h-16 items-center border-b border-[#e5e9f0] bg-[#f7f8fb]/88 px-5 backdrop-blur-xl lg:px-8">
          <Link href="/app" className="lg:hidden"><Logo compact /></Link>
          <div className="ml-auto flex items-center gap-2">
            <Link href="/app/projects" className="focus-ring hidden h-9 min-w-56 items-center gap-2 rounded-xl border border-[#dfe4ec] bg-white px-3 text-left text-sm text-[#929bad] shadow-[0_1px_2px_rgba(12,18,32,.03)] md:flex"><Search className="size-4"/>搜索项目 <span className="ml-auto text-[10px] text-[#a3abb9]">Projects</span></Link>
            <Link href="/app/projects" className="grid size-9 place-items-center rounded-xl bg-[#17203a] text-xs font-semibold text-white" aria-label="本地工作区项目">SS</Link>
          </div>
        </header>
        <main>{children}</main>
      </div>
    </div>
  );
}
