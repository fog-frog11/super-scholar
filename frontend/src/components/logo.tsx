import { cn } from "@/lib/utils";

export function Logo({ compact = false, className }: { compact?: boolean; className?: string }) {
  return (
    <div className={cn("flex items-center gap-2.5", className)}>
      <div className="relative grid size-9 place-items-center rounded-[11px] bg-[#151b31] shadow-[0_8px_24px_rgba(28,35,70,.16)]">
        <svg viewBox="0 0 32 32" className="size-6" aria-hidden="true">
          <defs><linearGradient id="ssg" x1="3" y1="3" x2="29" y2="29"><stop stopColor="#9facff"/><stop offset=".55" stopColor="#7268ff"/><stop offset="1" stopColor="#55d0d4"/></linearGradient></defs>
          <path d="M7 9.2 16 5l9 4.2-9 4.2L7 9.2Z" fill="none" stroke="url(#ssg)" strokeWidth="2" strokeLinejoin="round"/>
          <path d="M10 13.4v5.9c0 2.3 2.7 4.4 6 4.4s6-2.1 6-4.4v-5.9" fill="none" stroke="url(#ssg)" strokeWidth="2" strokeLinecap="round"/>
          <path d="M25 10v7" stroke="#7d8cff" strokeWidth="2" strokeLinecap="round"/>
          <circle cx="25" cy="19" r="1.4" fill="#55d0d4"/>
        </svg>
      </div>
      {!compact && <div className="leading-none"><div className="text-[15px] font-semibold tracking-[-.02em]">Super Scholar</div><div className="mt-1 text-[10px] font-medium tracking-[.16em] text-[#8993a7]">RESEARCH INTELLIGENCE</div></div>}
    </div>
  );
}
