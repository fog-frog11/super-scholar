"use client";

import { X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import type { ButtonHTMLAttributes, HTMLAttributes, InputHTMLAttributes, ReactNode, TextareaHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export function Button({ className, variant = "primary", size = "md", ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "ghost" | "danger"; size?: "sm" | "md" | "lg" }) {
  const variants = {
    primary: "bg-[#17203a] text-white hover:bg-[#253052] shadow-[0_6px_18px_rgba(18,24,45,.14)]",
    secondary: "border border-[#dce1ea] bg-white text-[#25304b] hover:bg-[#f7f8fb]",
    ghost: "text-[#5f697d] hover:bg-[#f0f2f7] hover:text-[#192139]",
    danger: "bg-[#fff0f2] text-[#b63547] hover:bg-[#ffe4e8]"
  };
  const sizes = { sm: "h-8 px-3 text-xs rounded-lg", md: "h-10 px-4 text-sm rounded-[10px]", lg: "h-12 px-5 text-sm rounded-xl" };
  return <button className={cn("focus-ring inline-flex items-center justify-center gap-2 font-medium transition disabled:pointer-events-none disabled:opacity-45", variants[variant], sizes[size], className)} {...props} />;
}


export function Switch({ checked, onCheckedChange, disabled = false, label }: { checked:boolean; onCheckedChange:(value:boolean)=>void; disabled?:boolean; label?:string }) {
  return <button
    type="button"
    role="switch"
    aria-checked={checked}
    aria-label={label}
    disabled={disabled}
    onClick={()=>onCheckedChange(!checked)}
    className={cn(
      "focus-ring relative inline-flex h-7 w-12 shrink-0 items-center rounded-full border transition-colors duration-200 disabled:cursor-not-allowed disabled:opacity-45",
      checked ? "border-[#5b69df] bg-[#6271e5] shadow-[inset_0_0_0_1px_rgba(255,255,255,.08)]" : "border-[#cfd5df] bg-[#e7eaf0]"
    )}
  >
    <motion.span
      className="pointer-events-none absolute left-[3px] top-[3px] size-5 rounded-full border border-black/[.04] bg-white shadow-[0_2px_6px_rgba(25,32,56,.20)]"
      animate={{ x: checked ? 20 : 0 }}
      transition={{ type:"spring", stiffness:520, damping:34, mass:.55 }}
    />
  </button>;
}

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) { return <div className={cn("surface rounded-2xl", className)} {...props} />; }
export function Badge({ children, tone = "neutral", className }: { children: ReactNode; tone?: "neutral"|"brand"|"success"|"warning"|"danger"; className?: string }) {
  const tones = { neutral:"bg-[#f1f3f7] text-[#667084]", brand:"bg-[#edf0ff] text-[#5262dd]", success:"bg-[#eaf8f2] text-[#138158]", warning:"bg-[#fff6e8] text-[#a66c11]", danger:"bg-[#fff0f2] text-[#b93d4f]" };
  return <span className={cn("inline-flex items-center rounded-full px-2.5 py-1 text-[11px] font-semibold", tones[tone], className)}>{children}</span>;
}
export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) { return <input className={cn("focus-ring h-11 w-full rounded-[11px] border border-[#dce1ea] bg-white px-3.5 text-sm outline-none placeholder:text-[#a5adbc]", className)} {...props} />; }
export function Textarea({ className, ...props }: TextareaHTMLAttributes<HTMLTextAreaElement>) { return <textarea className={cn("focus-ring min-h-28 w-full resize-y rounded-[11px] border border-[#dce1ea] bg-white px-3.5 py-3 text-sm leading-6 outline-none placeholder:text-[#a5adbc]", className)} {...props} />; }
export function ProgressBar({ value, className, active = false }: { value: number; className?: string; active?: boolean }) {
  const safeValue = Math.max(0, Math.min(100, value));
  return <div className={cn("relative h-2 overflow-hidden rounded-full bg-[#e8ebf1]", className)}>
    <motion.div className="relative h-full overflow-hidden rounded-full bg-[linear-gradient(90deg,#5367ff,#7862f0,#22b8bf)]" animate={{ width: `${safeValue}%` }} transition={{ type:"spring", stiffness:150, damping:24 }}>
      {active && safeValue > 0 && <motion.div
        className="absolute inset-y-0 w-24 bg-[linear-gradient(90deg,transparent,rgba(255,255,255,.72),transparent)] blur-[1px]"
        initial={{ x: "-120%" }}
        animate={{ x: "420%" }}
        transition={{ duration: 1.35, repeat: Infinity, ease: "linear" }}
      />}
    </motion.div>
    {active && <motion.div
      className="absolute inset-y-0 w-20 bg-[linear-gradient(90deg,transparent,rgba(91,106,224,.12),transparent)]"
      initial={{ x: "-120%" }}
      animate={{ x: "900%" }}
      transition={{ duration: 2.1, repeat: Infinity, ease: "linear" }}
    />}
  </div>;
}

export function Modal({ open, onClose, title, children, footer, size="md" }: { open:boolean; onClose:()=>void; title:string; children:ReactNode; footer?:ReactNode; size?:"md"|"xl"|"full" }) {
  const width=size==="full"?"max-w-[96vw]":size==="xl"?"max-w-5xl":"max-w-xl";
  return <AnimatePresence>{open && <motion.div className="fixed inset-0 z-[100] grid place-items-center bg-[#10162a]/30 p-4 backdrop-blur-[2px]" initial={{opacity:0}} animate={{opacity:1}} exit={{opacity:0}} onMouseDown={(e)=>{if(e.target===e.currentTarget)onClose();}}><motion.div className={`w-full ${width} max-h-[94vh] overflow-hidden rounded-[20px] border border-white/60 bg-white shadow-[0_30px_90px_rgba(18,25,50,.22)]`} initial={{opacity:0,y:14,scale:.98}} animate={{opacity:1,y:0,scale:1}} exit={{opacity:0,y:10,scale:.985}} transition={{duration:.2}}><div className="flex items-center justify-between border-b border-[#edf0f4] px-6 py-5"><h2 className="text-base font-semibold tracking-[-.01em]">{title}</h2><Button variant="ghost" size="sm" className="size-8 p-0" onClick={onClose} aria-label="关闭"><X className="size-4"/></Button></div><div className="max-h-[calc(94vh-132px)] overflow-auto px-6 py-5">{children}</div>{footer && <div className="flex justify-end gap-2 border-t border-[#edf0f4] px-6 py-4">{footer}</div>}</motion.div></motion.div>}</AnimatePresence>;
}

export function EmptyState({ icon, title, description, action }: { icon:ReactNode; title:string; description:string; action?:ReactNode }) { return <div className="grid min-h-72 place-items-center rounded-2xl border border-dashed border-[#d9dee8] bg-white/55 p-8 text-center"><div><div className="mx-auto grid size-12 place-items-center rounded-2xl bg-[#edf0ff] text-[#5968e8]">{icon}</div><h3 className="mt-4 text-base font-semibold">{title}</h3><p className="mx-auto mt-2 max-w-md text-sm leading-6 text-[#758095]">{description}</p>{action && <div className="mt-5">{action}</div>}</div></div>; }
