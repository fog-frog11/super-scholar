"use client";

import { Server, ServerOff } from "lucide-react";
import { useEffect, useState } from "react";
import { checkBackendHealth } from "@/lib/backend-client";

export function BackendStatus() {
  const [state, setState] = useState<"checking" | "online" | "offline">("checking");

  useEffect(() => {
    let cancelled = false;
    const check = async () => {
      try {
        await checkBackendHealth();
        if (!cancelled) setState("online");
      } catch {
        if (!cancelled) setState("offline");
      }
    };
    void check();
    const timer = window.setInterval(check, 30_000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  if (state === "checking") {
    return <div className="flex items-center gap-2 px-3 py-2 text-[11px] text-[#9099aa]"><span className="size-1.5 animate-pulse rounded-full bg-[#9ca6b7]" />连接数据服务…</div>;
  }
  if (state === "online") {
    return <div className="flex items-center gap-2 px-3 py-2 text-[11px] font-medium text-[#4d7868]"><Server className="size-3.5" />数据服务已连接</div>;
  }
  return <div className="flex items-center gap-2 px-3 py-2 text-[11px] font-medium text-[#9a6b2b]" title="后端未运行时项目仍保留在浏览器本地，但 Venue 数据和服务器持久化不可用。"><ServerOff className="size-3.5" />本地模式</div>;
}
