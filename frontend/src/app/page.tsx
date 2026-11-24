"use client";

import Link from "next/link";
import {
  ArrowRight,
  Check,
  DatabaseZap,
  FileCode2,
  FileText,
  FlaskConical,
  GitCompareArrows,
  RefreshCcw,
  Search,
  Sparkles,
  UploadCloud,
} from "lucide-react";
import { motion, useReducedMotion, useScroll, useTransform } from "motion/react";
import { Logo } from "@/components/logo";
import { LandingScrollProgress, ScrollReveal } from "@/components/scroll-reveal";
import { Button } from "@/components/ui";

const venues = [
  { name: "NeurIPS", x: "18%", y: "21%" },
  { name: "CVPR", x: "77%", y: "25%" },
  { name: "ACL", x: "82%", y: "68%" },
  { name: "SIGMOD", x: "17%", y: "70%" },
  { name: "ICML", x: "50%", y: "8%" },
  { name: "T-PAMI", x: "50%", y: "84%" },
];

function ResearchOrbit() {
  const reduced = useReducedMotion();
  const { scrollYProgress } = useScroll();
  const orbitY = useTransform(scrollYProgress, [0, 0.3], [0, 36]);
  const orbitRotate = useTransform(scrollYProgress, [0, 1], [0, 14]);

  return (
    <motion.div
      className="relative mx-auto aspect-square w-full max-w-[520px]"
      style={reduced ? undefined : { y: orbitY, rotate: orbitRotate }}
    >
      <div className="glow absolute inset-[8%] rounded-full" />
      <motion.div
        className="absolute inset-[14%] rounded-full border border-[#8b96ff]/20"
        animate={reduced ? undefined : { rotate: 360 }}
        transition={{ duration: 42, repeat: Infinity, ease: "linear" }}
      />
      <motion.div
        className="absolute inset-[25%] rounded-full border border-dashed border-[#6f7ee8]/25"
        animate={reduced ? undefined : { rotate: -360 }}
        transition={{ duration: 28, repeat: Infinity, ease: "linear" }}
      />
      {venues.map((venue, index) => (
        <motion.div
          key={venue.name}
          className="absolute z-10 rounded-xl border border-white/90 bg-white/85 px-3 py-2 text-xs font-semibold text-[#3e4962] shadow-[0_12px_32px_rgba(48,59,95,.12)] backdrop-blur-xl"
          style={{ left: venue.x, top: venue.y, transform: "translate(-50%,-50%)" }}
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{
            opacity: 1,
            scale: 1,
            y: reduced ? 0 : [0, index % 2 ? 5 : -5, 0],
          }}
          transition={{
            opacity: { delay: 0.35 + index * 0.07 },
            scale: { delay: 0.35 + index * 0.07 },
            y: { duration: 4 + index * 0.3, repeat: Infinity, ease: "easeInOut" },
          }}
        >
          <span className="mr-2 inline-block size-1.5 rounded-full bg-[#6172ff]" />
          {venue.name}
        </motion.div>
      ))}
      <motion.div
        className="surface-strong absolute left-1/2 top-1/2 z-20 w-[58%] -translate-x-1/2 -translate-y-1/2 rounded-[24px] p-5"
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        <div className="flex items-center gap-3">
          <div className="grid size-10 place-items-center rounded-xl bg-[#edf0ff] text-[#5364df]"><FileText className="size-5" /></div>
          <div><div className="text-sm font-semibold">Your research</div><div className="mt-1 text-[11px] text-[#8b94a5]">paper · code · experiments</div></div>
        </div>
        <div className="my-4 h-px bg-[#edf0f4]" />
        <div className="space-y-2"><div className="h-2 w-[72%] rounded bg-[#e7eaf1]" /><div className="h-2 w-[90%] rounded bg-[#eff1f5]" /><div className="h-2 w-[58%] rounded bg-[#eff1f5]" /></div>
        <div className="mt-4 flex gap-2"><span className="rounded-full bg-[#edf0ff] px-2 py-1 text-[9px] font-semibold text-[#5364df]">AI</span><span className="rounded-full bg-[#edf8f7] px-2 py-1 text-[9px] font-semibold text-[#178992]">Method</span></div>
      </motion.div>
      <svg className="absolute inset-0 size-full opacity-45" viewBox="0 0 500 500" aria-hidden="true">
        <defs><linearGradient id="lines" x1="0" x2="1"><stop stopColor="#8290ff" stopOpacity=".12" /><stop offset=".5" stopColor="#6575ff" stopOpacity=".6" /><stop offset="1" stopColor="#33bcc3" stopOpacity=".12" /></linearGradient></defs>
        {[[90, 105], [385, 125], [410, 340], [90, 350], [250, 45], [250, 420]].map(([x, y], index) => (
          <motion.line key={index} x1="250" y1="250" x2={x} y2={y} stroke="url(#lines)" strokeWidth="1.5" strokeDasharray="5 7" initial={{ pathLength: 0, opacity: 0 }} animate={{ pathLength: 1, opacity: 1 }} transition={{ duration: 1.1, delay: 0.25 + index * 0.08 }} />
        ))}
      </svg>
    </motion.div>
  );
}

const workflow = [
  { icon: UploadCloud, n: "01", title: "Upload", text: "上传论文、代码、实验数据与图片，材料进入真实解析与持久化流程。" },
  { icon: Sparkles, n: "02", title: "Understand", text: "把分散材料组织成可编辑的研究画像：领域、主题、方法、贡献与证据信号。" },
  { icon: Search, n: "03", title: "Configure", text: "按期刊或会议设置 CCF、CORE、截止时间、费用与其他投稿偏好。" },
  { icon: GitCompareArrows, n: "04", title: "Discover", text: "读取公开 venue 数据，筛选、排序、解释并横向对比投稿目标。" },
];

export default function LandingPage() {
  return (
    <main className="overflow-hidden bg-[#fbfcfe]">
      <LandingScrollProgress />
      <div className="fixed inset-x-0 top-0 z-50 border-b border-white/50 bg-white/70 backdrop-blur-2xl">
        <div className="mx-auto flex h-[68px] max-w-7xl items-center px-5 lg:px-8">
          <Link href="/"><Logo /></Link>
          <nav className="ml-12 hidden gap-7 text-sm text-[#697386] md:flex">
            <a href="#product" className="transition hover:text-[#1d2538]">产品</a>
            <a href="#workflow" className="transition hover:text-[#1d2538]">工作方式</a>
            <a href="#data" className="transition hover:text-[#1d2538]">数据基础</a>
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <Link href="/app"><Button variant="ghost">进入工作台</Button></Link>
            <Link href="/app"><Button>开始分析 <ArrowRight className="size-4" /></Button></Link>
          </div>
        </div>
      </div>

      <section className="relative min-h-[820px] pt-[68px]">
        <div className="hero-grid absolute inset-0" />
        <div className="absolute left-1/2 top-[110px] h-[420px] w-[760px] -translate-x-1/2 rounded-full bg-[#7b7dff]/[.08] blur-[100px]" />
        <div className="relative mx-auto grid max-w-7xl items-center gap-10 px-5 pb-20 pt-20 lg:grid-cols-[1.06fr_.94fr] lg:px-8 lg:pt-28">
          <div className="max-w-2xl">
            <motion.div className="inline-flex items-center gap-2 rounded-full border border-[#dfe3fb] bg-white/80 px-3 py-1.5 text-xs font-semibold text-[#5967d7] shadow-sm" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}><Sparkles className="size-3.5" /> Evidence-grounded venue discovery</motion.div>
            <motion.h1 className="mt-7 text-[48px] font-semibold leading-[1.02] tracking-[-.055em] text-[#12182a] sm:text-[62px] lg:text-[72px]" initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.08 }}>Find where your<br /><span className="brand-text">research belongs.</span></motion.h1>
            <motion.p className="mt-7 max-w-xl text-[17px] leading-8 text-[#6b758a]" initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }}>Super Scholar 面向计算机研究，把论文、源代码、实验结果和投稿要求组织成一条清晰的决策流程：理解研究，筛选真实 venue，解释推荐依据，最后完成选择。</motion.p>
            <motion.div className="mt-8 flex flex-wrap gap-3" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.22 }}><Link href="/app"><Button size="lg" className="px-6">创建研究项目 <ArrowRight className="size-4" /></Button></Link><a href="#workflow"><Button variant="secondary" size="lg">查看工作方式</Button></a></motion.div>
            <motion.div className="mt-8 flex flex-wrap gap-x-6 gap-y-2 text-xs font-medium text-[#8791a4]" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.35 }}><span className="inline-flex items-center gap-1.5"><Check className="size-3.5 text-[#1aa16a]" />材料解析</span><span className="inline-flex items-center gap-1.5"><Check className="size-3.5 text-[#1aa16a]" />CCF 第七版目录</span><span className="inline-flex items-center gap-1.5"><Check className="size-3.5 text-[#1aa16a]" />CCFDDL 会议数据</span></motion.div>
          </div>
          <ResearchOrbit />
        </div>
      </section>

      <section id="workflow" className="border-y border-[#e9ecf2] bg-white py-24">
        <div className="mx-auto max-w-7xl px-5 lg:px-8">
          <ScrollReveal className="max-w-2xl"><div className="text-xs font-bold uppercase tracking-[.18em] text-[#6977e6]">Workflow</div><h2 className="mt-3 text-3xl font-semibold tracking-[-.04em] sm:text-4xl">一条完整而克制的投稿决策路径</h2><p className="mt-4 text-sm leading-7 text-[#758095]">不把复杂度丢给用户。四步完成从材料到候选 venue 的结构化决策。</p></ScrollReveal>
          <div className="mt-12 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {workflow.map(({ icon: Icon, n, title, text }, index) => (
              <ScrollReveal key={title} delay={index * 0.05} distance={22}>
                <div className="h-full rounded-2xl border border-[#e4e8ef] bg-[#fbfcfe] p-6 transition duration-300 hover:-translate-y-1 hover:border-[#ccd3ef] hover:shadow-[0_18px_50px_rgba(45,57,96,.08)]">
                  <div className="flex items-center justify-between"><div className="grid size-10 place-items-center rounded-xl bg-white text-[#5968e6] shadow-sm"><Icon className="size-5" /></div><span className="text-xs font-semibold text-[#b0b7c4]">{n}</span></div><h3 className="mt-6 text-lg font-semibold">{title}</h3><p className="mt-2 text-sm leading-6 text-[#778196]">{text}</p>
                </div>
              </ScrollReveal>
            ))}
          </div>
        </div>
      </section>

      <section id="product" className="py-24">
        <div className="mx-auto grid max-w-7xl gap-10 px-5 lg:grid-cols-2 lg:px-8">
          <ScrollReveal distance={34}>
            <div className="surface-strong rounded-[28px] p-6 sm:p-8">
              <div className="flex items-center gap-3"><div className="grid size-10 place-items-center rounded-xl bg-[#edf0ff] text-[#5968e6]"><FileText className="size-5" /></div><div><div className="font-semibold">Research Materials</div><div className="text-xs text-[#929bad]">真实文件类型，不只看摘要</div></div></div>
              <div className="mt-7 grid gap-3">{[[FileText, "Manuscript", "PDF / DOCX"], [FileCode2, "Source package", "ZIP / TEX / Code"], [FlaskConical, "Experiment data", "XLSX / CSV"]].map(([Icon, name, meta]) => { const ItemIcon = Icon as typeof FileText; return <div key={String(name)} className="flex items-center gap-3 rounded-xl border border-[#e8ebf0] bg-[#fbfcfd] px-4 py-3"><ItemIcon className="size-4 text-[#6d79d9]" /><div className="text-sm font-medium">{String(name)}</div><div className="ml-auto text-xs text-[#98a1b0]">{String(meta)}</div></div>; })}</div>
            </div>
          </ScrollReveal>
          <ScrollReveal className="flex flex-col justify-center" distance={34}><div className="text-xs font-bold uppercase tracking-[.18em] text-[#6977e6]">Multi-material understanding</div><h2 className="mt-3 text-3xl font-semibold tracking-[-.04em]">研究不是一个摘要文本框。</h2><p className="mt-4 text-sm leading-7 text-[#758095]">Super Scholar 把论文、代码、实验表格和图片放在同一个研究项目里管理。解析过程有明确阶段和状态，后端负责持久化原始材料与项目数据，前端继续提供即时反馈。</p></ScrollReveal>
        </div>
      </section>

      <section id="data" className="relative overflow-hidden bg-[#151b2f] py-24 text-white">
        <div className="absolute inset-0 opacity-30 [background-image:radial-gradient(circle_at_20%_20%,rgba(116,132,255,.24),transparent_32%),radial-gradient(circle_at_80%_70%,rgba(25,181,190,.14),transparent_30%)]" />
        <div className="relative mx-auto max-w-7xl px-5 lg:px-8">
          <div className="grid gap-10 lg:grid-cols-[.9fr_1.1fr]">
            <ScrollReveal distance={30}><div className="text-xs font-bold uppercase tracking-[.18em] text-[#97a5ff]">Data foundation</div><h2 className="mt-3 text-3xl font-semibold tracking-[-.04em] sm:text-4xl">每一条关键数据，都知道自己从哪里来。</h2><p className="mt-4 max-w-lg text-sm leading-7 text-[#abb4c6]">Venue 数据通过独立后端统一读取、校验、缓存和记录更新时间。CCF 目录优先读取官方页面，会议日程由 CCFDDL 提供；推荐界面能够保留数据来源与刷新状态，而不是把数据来源藏在模型回答里。</p></ScrollReveal>
            <div className="grid gap-3 sm:grid-cols-3">
              {[
                [DatabaseZap, "Source-aware", "来源、版本与更新时间进入数据层"],
                [RefreshCcw, "Resilient cache", "远端短暂不可用时使用最近一次成功缓存"],
                [Check, "Verified flow", "公开目录经过结构与完整性校验后再进入推荐"],
              ].map(([Icon, title, text], index) => { const ItemIcon = Icon as typeof Check; return <ScrollReveal key={String(title)} delay={index * 0.05} distance={22}><div className="h-full rounded-2xl border border-white/10 bg-white/[.045] p-5 backdrop-blur-sm"><ItemIcon className="size-5 text-[#9eabff]" /><div className="mt-5 text-sm font-semibold">{String(title)}</div><div className="mt-2 text-xs leading-5 text-[#aeb7c8]">{String(text)}</div></div></ScrollReveal>; })}
            </div>
          </div>
        </div>
      </section>

      <section className="py-24">
        <ScrollReveal className="mx-auto max-w-5xl px-5 text-center" distance={30}><h2 className="text-4xl font-semibold tracking-[-.05em]">Your research already has a direction.</h2><p className="mt-4 text-sm text-[#7c879a]">让 Super Scholar 帮你把这个方向变成一组可以验证、比较和选择的投稿目标。</p><div className="mt-7"><Link href="/app"><Button size="lg" className="px-7">开始建立研究项目 <ArrowRight className="size-4" /></Button></Link></div></ScrollReveal>
      </section>
      <footer className="border-t border-[#e8ebf0] bg-white"><div className="mx-auto flex max-w-7xl flex-col gap-4 px-5 py-8 text-xs text-[#929bad] sm:flex-row sm:items-center lg:px-8"><Logo /><span className="sm:ml-auto">Super Scholar · Computer Science</span></div></footer>
    </main>
  );
}
