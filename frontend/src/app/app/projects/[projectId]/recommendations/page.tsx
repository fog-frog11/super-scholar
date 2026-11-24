"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowUpRight, CalendarDays, Check, CheckCircle2, CircleAlert, Clock3, GitCompareArrows, Globe2, Info, MapPin, RefreshCw, ShieldCheck, Sparkles, X, XCircle } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Badge, Button, Card, EmptyState, Modal, ProgressBar } from "@/components/ui";
import { CCF_AREAS } from "@/lib/constants";
import { requestVenueRecommendations } from "@/lib/backend-client";
import type { DataSourceStatus, RecommendationResult, RecommendationRun, SemanticVenueEvidence } from "@/lib/types";
import { daysUntil, formatDate, safeHostname, uid } from "@/lib/utils";
import { useAppStore } from "@/store/use-app-store";

function statusIcon(status:RecommendationResult["constraints"][number]["status"]){if(status==="pass")return <CheckCircle2 className="size-3.5 text-[#148158]"/>;if(status==="fail")return <XCircle className="size-3.5 text-[#b74152]"/>;if(status==="unknown")return <CircleAlert className="size-3.5 text-[#b17a20]"/>;return <Info className="size-3.5 text-[#8c96a8]"/>}

function displayVenue(v:RecommendationResult["venue"]){return v.type==="conference"?`${v.title}${v.year?` ${v.year}`:""}`:v.shortName}
function evidenceValue(value:number|null|undefined){return value==null?"—":String(value)}

function healthTone(status:DataSourceStatus|undefined):"success"|"warning"|"danger"|"neutral"{return status==="ready"?"success":status==="error"?"danger":status==="degraded"||status==="limited"?"warning":"neutral"}
function healthLabel(status:DataSourceStatus|undefined){return status==="ready"?"Ready":status==="degraded"?"Degraded":status==="limited"?"Limited":status==="error"?"Error":status==="not_applicable"?"N/A":status==="disabled"?"Disabled":"Unknown"}
const SOURCE_LABELS:Record<string,string>={openalexWorks:"OpenAlex Works",openalexSources:"OpenAlex 论文 Sources",openalexCandidateSources:"OpenAlex 候选 Venue Sources",openalexVenueConditioned:"OpenAlex Venue 内语义验证",semanticScholar:"Semantic Scholar",crossref:"Crossref",dblp:"DBLP",clarivateJournals:"Clarivate JIF/JCR/WoS",ecbFx:"ECB APC 汇率",reviewSpeed:"审稿速度元数据",conferenceCatalog:"CCFDDL/会议目录",journalCatalog:"CCF 期刊目录"};

function OpenAlexEvidenceList({title,items,subtitle}:{title:string;items:SemanticVenueEvidence[];subtitle?:(item:SemanticVenueEvidence)=>string}){
  const [expanded,setExpanded]=useState(false); const visible=expanded?items:items.slice(0,5);
  if(!items.length)return null;
  return <div className="mt-5"><div className="flex items-center justify-between gap-3"><div className="text-xs font-semibold">{title} <span className="font-normal text-[#98a1b0]">({items.length})</span></div>{items.length>5&&<button type="button" className="text-[11px] font-semibold text-[#5968d4]" onClick={()=>setExpanded(v=>!v)}>{expanded?"收起":"展开全部"}</button>}</div><div className="mt-2 space-y-2">{visible.map(item=><a key={`${item.workId}-${item.semanticRank??0}`} href={item.url} target="_blank" rel="noreferrer" className="block rounded-xl border border-[#e7eaf0] p-3 hover:bg-[#fafbff]"><div className="text-xs font-semibold leading-5 text-[#566176]">{item.title}</div><div className="mt-1 text-[10px] text-[#929bad]">{subtitle?subtitle(item):`OpenAlex rank #${item.semanticRank??"—"} · ${item.year??"year n/a"} · ${item.sourceName??"source n/a"}`}</div></a>)}</div>{items.length>5&&<div className="mt-2 text-[10px] text-[#98a1b0]">默认展示前 5 篇；{expanded?`当前已展示全部 ${items.length} 篇。`:`还有 ${items.length-5} 篇已隐藏。`}</div>}</div>
}

function SecondaryEvidenceList({items}:{items:NonNullable<RecommendationResult["secondaryEvidence"]>}){
  const [expanded,setExpanded]=useState(false); const visible=expanded?items:items.slice(0,5); if(!items.length)return null;
  return <div className="mt-5"><div className="flex items-center justify-between"><div className="text-xs font-semibold">Semantic Scholar 独立论文证据 <span className="font-normal text-[#98a1b0]">({items.length})</span></div>{items.length>5&&<button type="button" className="text-[11px] font-semibold text-[#5968d4]" onClick={()=>setExpanded(v=>!v)}>{expanded?"收起":"展开全部"}</button>}</div><div className="mt-2 space-y-2">{visible.map(item=>{const row=<><div className="text-xs font-semibold leading-5 text-[#566176]">{item.title}</div><div className="mt-1 text-[10px] text-[#929bad]">Semantic Scholar rank #{item.searchRank??"—"} · {item.year??"year n/a"} · {item.publicationVenueName??item.venue??"venue n/a"}</div></>;return item.url?<a key={item.paperId} href={item.url as string} target="_blank" rel="noreferrer" className="block rounded-xl border border-[#e7eaf0] p-3 hover:bg-[#fafbff]">{row}</a>:<div key={item.paperId} className="rounded-xl border border-[#e7eaf0] p-3">{row}</div>})}</div></div>
}

function VenueCard({result,compared,selected,onCompare,onDetails,onSelect}:{result:RecommendationResult;compared:boolean;selected:boolean;onCompare:()=>void;onDetails:()=>void;onSelect:()=>void}){
  const v=result.venue; const days=v.type==="conference"?daysUntil(v.deadline,v.timezone):undefined;
  const signals=[
    ["Venue 近期论文",result.venueConditionedMatch],
    ["全局 OpenAlex",result.semanticMatch],
    ["CS scope",result.scopeMatch],
    ["Semantic Scholar",result.secondaryMatch],
    ["References",result.referenceMatch]
  ] as const;
  return <Card className={result.eligible?"overflow-hidden":"overflow-hidden opacity-72"}>
    <div className="p-5">
      <div className="flex items-start gap-4">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={result.eligible?"brand":"warning"}>{displayVenue(v)}</Badge>
            <Badge>{CCF_AREAS[v.sub].en}</Badge>
            {v.ccf!=="N"&&v.ccf!=="U"&&<Badge tone="success">CCF {v.ccf}</Badge>}{v.ccf==="U"&&<Badge>CCF 未核验</Badge>}
            {v.type==="conference"&&v.core!=="N"&&<Badge>CORE {v.core}</Badge>}
            {v.openalexDynamic&&<Badge>OpenAlex discovery</Badge>}
            <Badge tone={result.semanticConfidence==="high"?"success":"neutral"}>Evidence {result.semanticConfidence}</Badge>
            {selected&&<Badge tone="success">当前目标</Badge>}
          </div>
          <h3 className="mt-3 text-base font-semibold leading-6">{v.type==="conference"?v.description:v.name}</h3>
          <p className="mt-2 text-xs text-[#8b95a6]">{v.type==="conference"?`${v.place||"地点未核验"} · ${v.date||"日期未核验"}`:`${v.publisher||"Publisher 未标注"} · ${safeHostname(v.link)}`}</p>
        </div>
        <div className="text-right"><div className="text-3xl font-semibold tracking-[-.045em] text-[#3444b7]">{result.academicScore??result.finalScore}</div><div className="mt-0.5 text-[10px] font-semibold uppercase tracking-[.12em] text-[#98a1b0]">Academic Fit</div><div className="mt-1 text-[9px] text-[#a0a8b7]">Research {result.researchMatch}</div></div>
      </div>
      <div className="mt-5 grid gap-3 sm:grid-cols-3">{v.type==="conference"?<>
        <div className="rounded-xl bg-[#f7f8fb] p-3"><CalendarDays className="size-4 text-[#6976d6]"/><div className="mt-2 text-xs font-semibold">{v.deadline&&v.deadline!=="TBD"?v.deadline.slice(0,10):"TBD"}</div><div className="mt-1 text-[10px] text-[#98a1b0]">Submission deadline</div></div>
        <div className="rounded-xl bg-[#f7f8fb] p-3"><Clock3 className="size-4 text-[#6976d6]"/><div className="mt-2 text-xs font-semibold">{days===undefined?"Unknown":days<0?`已截止 ${Math.abs(days)} 天`:`约 ${days} 天`}</div><div className="mt-1 text-[10px] text-[#98a1b0]">Time remaining</div></div>
        <div className="rounded-xl bg-[#f7f8fb] p-3"><MapPin className="size-4 text-[#6976d6]"/><div className="mt-2 truncate text-xs font-semibold">{v.place||"TBD"}</div><div className="mt-1 text-[10px] text-[#98a1b0]">Location</div></div>
      </>:<>
        <div className="rounded-xl bg-[#f7f8fb] p-3"><ShieldCheck className="size-4 text-[#6976d6]"/><div className="mt-2 text-xs font-semibold">{v.ccf==="U"?"CCF 未核验":v.ccf==="N"?"Not in current CCF catalog":`CCF ${v.ccf}`}</div><div className="mt-1 text-[10px] text-[#98a1b0]">CCF rank</div></div>
        <div className="rounded-xl bg-[#f7f8fb] p-3"><Globe2 className="size-4 text-[#6976d6]"/><div className="mt-2 text-xs font-semibold">{v.metrics.impactFactor!=null?`JIF ${Number(v.metrics.impactFactor).toFixed(2)}`:v.metrics.oaType??"权威 JIF 未配置"}</div><div className="mt-1 text-[10px] text-[#98a1b0]">{v.metrics.jcrQuartile?`JCR ${v.metrics.jcrQuartile}`:v.metrics.isInDoaj?"DOAJ · OpenAlex":"Journal metadata"}</div></div>
        <div className="rounded-xl bg-[#f7f8fb] p-3"><Clock3 className="size-4 text-[#6976d6]"/><div className="mt-2 text-xs font-semibold">{v.metrics.apcCny!=null?`约 ¥${Math.round(Number(v.metrics.apcCny)).toLocaleString()}`:v.metrics.openalex2yrMeanCitedness!=null?Number(v.metrics.openalex2yrMeanCitedness).toFixed(2):v.metrics.apcUsd!=null?`$${Number(v.metrics.apcUsd).toLocaleString()}`:"暂无公开 APC"}</div><div className="mt-1 text-[10px] text-[#98a1b0]">{v.metrics.apcCny!=null?"OpenAlex APC · ECB CNY":v.metrics.openalex2yrMeanCitedness!=null?"OpenAlex 2yr mean citedness（非 JIF）":"Public metadata"}</div></div>
      </>}</div>
      <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-5">{signals.map(([label,value])=><div key={label} className="rounded-xl border border-[#e9edf3] bg-white px-3 py-2"><div className="text-sm font-semibold text-[#4b5872]">{evidenceValue(value)}</div><div className="mt-0.5 text-[9px] text-[#98a1b0]">{label}</div></div>)}</div>
      {v.type==="conference"&&result.actionability&&<div className={`mt-4 rounded-xl px-3 py-2 text-[11px] ${result.isCurrentlyActionable?"bg-[#eef9f4] text-[#26705a]":"bg-[#f8f8fa] text-[#7f899b]"}`}>当前可投状态：{result.actionability.status} · {result.actionability.reason}</div>}
      <div className="mt-5 border-t border-[#edf0f4] pt-4"><div className="text-[11px] font-semibold text-[#8791a4]">为什么进入推荐</div><div className="mt-2 space-y-1.5">{result.reasons.slice(0,4).map(r=><div key={r} className="flex gap-2 text-xs leading-5 text-[#687388]"><Check className="mt-1 size-3 shrink-0 text-[#168158]"/>{r}</div>)}</div></div>
    </div>
    <div className="flex flex-wrap items-center gap-2 border-t border-[#e9edf2] bg-[#fbfcfd] px-5 py-3"><Button variant="ghost" size="sm" onClick={onDetails}>查看依据</Button>{v.link&&<a href={v.link} target="_blank" rel="noreferrer"><Button variant="ghost" size="sm">{v.type==="conference"?"Venue 页面":"期刊页面"} <ArrowUpRight className="size-3.5"/></Button></a>}<div className="ml-auto flex gap-2"><Button variant={compared?"primary":"secondary"} size="sm" onClick={onCompare}><GitCompareArrows className="size-3.5"/>{compared?"已加入对比":"加入对比"}</Button><Button size="sm" onClick={onSelect}>{selected?"重新确认":"选择"}</Button></div></div>
  </Card>
}


function RecommendationActivityVisual(){
  const orbit = [
    { x: 0, y: -42, delay: 0 },
    { x: 36, y: 22, delay: .35 },
    { x: -36, y: 22, delay: .7 }
  ];
  return <div className="relative mx-auto h-28 w-28" aria-hidden="true">
    <motion.div
      className="absolute inset-3 rounded-full border border-[#dfe4ff]"
      animate={{ rotate: 360 }}
      transition={{ duration: 8, repeat: Infinity, ease: "linear" }}
    >
      {orbit.map((dot,index)=><motion.span
        key={index}
        className="absolute left-1/2 top-1/2 size-2.5 rounded-full bg-[#6474ed] shadow-[0_0_18px_rgba(100,116,237,.45)]"
        style={{ marginLeft: -5, marginTop: -5, x: dot.x, y: dot.y }}
        animate={{ scale: [1,.7,1], opacity: [.95,.45,.95] }}
        transition={{ duration: 1.8, repeat: Infinity, delay: dot.delay }}
      />)}
    </motion.div>
    <motion.div
      className="absolute inset-[22px] rounded-full border border-dashed border-[#bfc8fb]"
      animate={{ rotate: -360 }}
      transition={{ duration: 5.5, repeat: Infinity, ease: "linear" }}
    />
    <motion.div
      className="absolute inset-[31px] grid place-items-center rounded-2xl bg-[#edf0ff] text-[#5b6ae0] shadow-[0_10px_30px_rgba(87,103,223,.12)]"
      animate={{ scale: [1,1.055,1], boxShadow: ["0 10px 30px rgba(87,103,223,.12)","0 14px 38px rgba(87,103,223,.22)","0 10px 30px rgba(87,103,223,.12)"] }}
      transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
    >
      <Sparkles className="size-6"/>
    </motion.div>
    <motion.div
      className="absolute left-1/2 top-1/2 h-[1px] w-11 origin-left bg-[linear-gradient(90deg,rgba(78,95,219,.58),transparent)]"
      animate={{ rotate: 360 }}
      transition={{ duration: 2.4, repeat: Infinity, ease: "linear" }}
    />
  </div>;
}

export default function RecommendationsPage(){
  const {projectId}=useParams<{projectId:string}>(); const store=useAppStore(); const project=store.projects.find(p=>p.id===projectId);
  const autoRef=useRef(false); const [details,setDetails]=useState<RecommendationResult|undefined>(); const [selecting,setSelecting]=useState<RecommendationResult|undefined>(); const [sort,setSort]=useState<"academic"|"actionable"|"fit"|"deadline"|"rank">("academic"); const [elapsedSeconds,setElapsedSeconds]=useState(0);

  useEffect(()=>{
    if(project?.recommendationRun?.status!=="running"){setElapsedSeconds(0);return;}
    const started=Date.parse(project.recommendationRun.createdAt);
    const update=()=>setElapsedSeconds(Math.max(0,Math.floor((Date.now()-started)/1000)));
    update(); const timer=window.setInterval(update,1000); return()=>window.clearInterval(timer);
  },[project?.recommendationRun?.id,project?.recommendationRun?.status,project?.recommendationRun?.createdAt]);

  const runRecommendation=useCallback(async()=>{
    if(!project?.profile)return;
    const run:RecommendationRun={id:uid("run"),createdAt:new Date().toISOString(),progress:5,stage:"semantic_retrieval",status:"running",message:"正在构建 CS Venue 候选：OpenAlex 相似论文/Source topics + CCF/CCFDDL 元数据 + 稿件 References + 用户偏好",candidateCount:0,eligibleCount:0,results:[]};
    store.setRecommendationRun(projectId,run);
    try{
      const completed=await requestVenueRecommendations(projectId,project.profile,project.preferences);
      store.setRecommendationRun(projectId,completed);
    }catch(error){
      store.updateRecommendationRun(projectId,{progress:100,stage:"error",status:"error",message:"推荐失败",error:error instanceof Error?error.message:String(error)});
    }
  },[project,projectId,store]);

  useEffect(()=>{const shouldRun=typeof window!=="undefined"&&new URLSearchParams(window.location.search).get("run")==="1";if(shouldRun&&!autoRef.current&&project?.profile){autoRef.current=true;void runRecommendation()}},[project?.profile,runRecommendation]);
  if(!project)return null; const run=project.recommendationRun;
  if(!project.profile)return <Card className="p-8"><EmptyState icon={<Sparkles className="size-5"/>} title="需要研究画像" description="请先完成 Research Profile，再启动投稿推荐。" action={<Link href={`/app/projects/${projectId}/profile`}><Button>返回研究画像</Button></Link>}/></Card>;
  if(!run||run.status==="idle")return <Card className="p-8"><EmptyState icon={<Sparkles className="size-5"/>} title="准备寻找投稿目标" description="会先用 OpenAlex 相似论文扩展 Venue 候选，再融合 Source topics、计算机细分方向、稿件 References、CCF/CCFDDL 元数据和你的投稿偏好。CCF 不再限制候选宇宙。" action={<Button onClick={()=>void runRecommendation()}>开始推荐</Button>}/></Card>;
  if(run.status==="running")return <div className="mx-auto max-w-3xl py-8"><Card className="relative overflow-hidden p-8"><motion.div className="absolute inset-x-0 top-0 h-1 bg-[linear-gradient(90deg,#596bff,#7664ec,#20b7bd,#596bff)] bg-[length:220%_100%]" animate={{backgroundPosition:["0% 50%","220% 50%"]}} transition={{duration:2.2,repeat:Infinity,ease:"linear"}}/><div className="pointer-events-none absolute inset-0 overflow-hidden"><motion.div className="absolute -left-24 top-16 h-52 w-52 rounded-full bg-[#6374ff]/[.055] blur-3xl" animate={{x:[0,180,40,0],y:[0,30,-10,0],scale:[1,1.2,.95,1]}} transition={{duration:8,repeat:Infinity,ease:"easeInOut"}}/><motion.div className="absolute -right-20 bottom-10 h-48 w-48 rounded-full bg-[#20b7bd]/[.05] blur-3xl" animate={{x:[0,-150,-50,0],y:[0,-20,18,0],scale:[1,.9,1.15,1]}} transition={{duration:9,repeat:Infinity,ease:"easeInOut"}}/></div><RecommendationActivityVisual/><div className="relative mt-3 text-center"><h2 className="text-xl font-semibold">Finding the right venues</h2><p className="mt-2 text-sm text-[#7f899b]">{run.message}</p><div className="mt-2 text-[11px] tabular-nums text-[#a0a8b7]">已运行 {elapsedSeconds}s · 后端会一次完成候选构建、OpenAlex 语义检索与重排，完成后直接返回最终结果</div><div className="mt-5 text-5xl font-semibold tracking-[-.05em] tabular-nums text-[#3444b7]">{run.progress}%</div><ProgressBar value={run.progress} active className="mx-auto mt-5 max-w-xl"/></div><div className="relative mx-auto mt-7 max-w-xl space-y-2 text-xs">{[
  ["研究画像",4,true],
  ["CCF/CCFDDL + OpenAlex Source 候选",12,true],
  ["OpenAlex 语义论文检索",18,true],
  ["Venue-conditioned / References / Scope",64,true],
  ["Required / Preferred 约束",82,true],
  ["语义重排与解释",94,true]
].filter(([, , applies])=>applies).map(([label,threshold],index,array)=>{const numeric=Number(threshold);const done=run.progress>=numeric;const previous=index>0?Number(array[index-1][1]):0;const active=!done&&run.progress>=previous;return <motion.div key={String(label)} className={`relative flex items-center gap-2 overflow-hidden rounded-xl px-3 py-2.5 ${active?"bg-[#f3f5ff]":"bg-[#f7f8fb]"}`} animate={active?{scale:[1,1.006,1]}:{scale:1}} transition={{duration:1.5,repeat:active?Infinity:0}}>{active&&<motion.div className="absolute inset-y-0 w-24 bg-[linear-gradient(90deg,transparent,rgba(99,116,237,.08),transparent)]" initial={{x:"-120%"}} animate={{x:"720%"}} transition={{duration:1.8,repeat:Infinity,ease:"linear"}}/>}<span className="relative">{done?<CheckCircle2 className="size-4 text-[#18835c]"/>:active?<motion.span className="block size-4 rounded-full border-2 border-[#7583ef] border-t-transparent" animate={{rotate:360}} transition={{duration:.9,repeat:Infinity,ease:"linear"}}/>:<span className="block size-4 rounded-full border border-[#d4d9e2]"/>}</span><span className={`relative ${done?"text-[#526075]":active?"font-medium text-[#5865c7]":"text-[#9aa3b2]"}`}>{String(label)}</span>{active&&<span className="relative ml-auto text-[10px] text-[#8e98b6]">处理中</span>}</motion.div>})}</div>{run.candidateCount>0&&<div className="relative mt-5 text-center text-[11px] text-[#939cad]">候选由 CCF/CCFDDL 与 OpenAlex Source 动态合并；排序不会因“同属 CCF AI”并列</div>}</Card></div>;
  if(run.status==="error")return <Card className="p-8"><EmptyState icon={<XCircle className="size-5"/>} title="推荐数据加载失败" description={run.error??"未知错误"} action={<Button onClick={()=>void runRecommendation()}><RefreshCw className="size-4"/>重新尝试</Button>}/></Card>;

  const academicPool=run.academicResults??run.results; const actionablePool=run.actionableResults??[]; const showingActionable=sort==="actionable";
  const eligible=(showingActionable?actionablePool:academicPool).filter(r=>showingActionable?r.isCurrentlyActionable:r.eligible); const close=showingActionable?[]:academicPool.filter(r=>!r.eligible); const compared=project.comparisonVenueIds;
  const sorted=(list:RecommendationResult[])=>[...list].sort((a,b)=>{if(sort==="fit")return b.researchMatch-a.researchMatch;if(sort==="rank"){const rank={A:3,B:2,C:1,N:0,U:-1};return rank[b.venue.ccf]-rank[a.venue.ccf]}if(sort==="deadline"||sort==="actionable"){const da=a.venue.type==="conference"?daysUntil(a.venue.deadline,a.venue.timezone)??99999:99999;const db=b.venue.type==="conference"?daysUntil(b.venue.deadline,b.venue.timezone)??99999:99999;return da-db}return (b.academicScore??b.finalScore)-(a.academicScore??a.finalScore)});
  const types=showingActionable?["conference"] as const:project.preferences.targetType==="both"?["conference","journal"] as const:[project.preferences.targetType] as const;
  const health=run.dataSourceHealth;
  const healthStatus=health?.overallStatus??"limited";
  return <div className="space-y-5"><Card className="p-5"><div className="flex flex-col gap-4 lg:flex-row lg:items-center"><div><div className="flex items-center gap-2"><Badge tone={healthTone(healthStatus)}>{healthStatus==="ready"?<Check className="mr-1 size-3"/>:<CircleAlert className="mr-1 size-3"/>}{healthLabel(healthStatus)}</Badge><span className="text-xs text-[#8f99aa]">{formatDate(run.createdAt)}</span></div><h2 className="mt-3 text-xl font-semibold tracking-[-.025em]">{showingActionable?`当前核验可投稿 ${actionablePool.length} 个会议`:`学术适配候选 ${academicPool.filter(r=>r.eligible).length} 个`}</h2><p className="mt-1.5 text-xs leading-5 text-[#8993a4]">V3.11 保留“学术上适不适合”与“现在能不能投”的分离，并补齐可核验的期刊元数据。Academic Fit 以候选 Venue 自身近年论文的语义检索为主信号，再结合全局 OpenAlex、CS scope、Semantic Scholar、结构化 References；Source topics 只作辅助，CCF 不参与内容匹配分。</p><p className="mt-1 text-[10px] text-[#a0a8b7]">候选库：CCF/CCFDDL {run.catalogCandidateCount??run.candidateCount} 个 + OpenAlex 动态发现 {run.dynamicCandidateCount??0} 个；候选 Venue 会再主动解析到 OpenAlex Source，不能可靠确认身份时保持 Unknown，不会猜测绑定。动态会议若没有核验到当前 edition，会明确显示 TBD/未核验。</p></div><div className="ml-auto flex flex-wrap gap-2">{[["academic","学术适配"],["actionable","当前可投"],["fit","研究匹配"],["rank","CCF 等级"],["deadline","最近截止"]].map(([key,label])=><button key={key} onClick={()=>setSort(key as typeof sort)} className={`rounded-lg px-3 py-2 text-xs font-semibold ${sort===key?"bg-[#edf0ff] text-[#4d5cd2]":"bg-[#f5f6f8] text-[#808a9c]"}`}>{label}</button>)}<Button variant="secondary" size="sm" onClick={()=>void runRecommendation()}><RefreshCw className="size-3.5"/>重新推荐</Button></div></div></Card>

  {health&&<Card className={healthStatus==="ready"?"border-[#d7ebe2] bg-[#fbfefc] p-4":"border-[#efdfbb] bg-[#fffdf7] p-4"}><div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between"><div><div className="flex items-center gap-2 text-sm font-semibold">{healthStatus==="ready"?<CheckCircle2 className="size-4 text-[#19805d]"/>:<CircleAlert className="size-4 text-[#b27a22]"/>}推荐数据源健康状态</div><p className="mt-1 text-xs leading-5 text-[#7d8798]">{health.message}</p></div><Link href="/app/settings"><Button variant="secondary" size="sm">配置 / 诊断学术数据源</Button></Link></div><div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">{Object.entries(health.sources).map(([key,item])=><div key={key} className="rounded-xl border border-[#e5e9ef] bg-white px-3 py-2.5"><div className="flex items-center justify-between gap-2"><span className="text-[11px] font-semibold text-[#59647a]">{SOURCE_LABELS[key]??key}</span><Badge tone={healthTone(item.status)}>{healthLabel(item.status)}</Badge></div><p className="mt-1.5 line-clamp-2 text-[10px] leading-4 text-[#8b95a6]">{item.message}</p>{key==="openalexWorks"&&item.enabled&&item.configured===false&&<div className="mt-1 text-[9px] font-semibold text-[#a47324]">匿名模式：建议在设置中配置免费 API Key</div>}</div>)}</div></Card>}

  {run.semanticRetrieval&&run.semanticRetrieval.status!=="unavailable"&&<div className="rounded-xl border border-[#dbe7e5] bg-[#f8fcfb] px-4 py-3 text-xs leading-5 text-[#59756f]">OpenAlex 本轮返回 {run.semanticRetrieval.workCount??0} 篇语义相似论文；另外主动解析候选 Venue Source {run.semanticRetrieval.candidateSourceResolvedCount??0}/{run.semanticRetrieval.candidateSourceResolutionAttempted??0}，其中 {run.semanticRetrieval.candidateSourceTopicsCount??0} 个候选拿到 Source topics；随后对 {run.semanticRetrieval.venueConditionedAttempted??0} 个高优先级候选执行 Venue 内近期论文语义验证，成功 {run.semanticRetrieval.venueConditionedSuccessful??0} 个。</div>}

  {run.semanticRetrieval?.works&&run.semanticRetrieval.works.length>0&&<Card className="p-5"><div className="flex items-start justify-between gap-3"><div><h3 className="text-sm font-semibold">OpenAlex 全局语义近邻</h3><p className="mt-1 text-[11px] leading-5 text-[#8791a4]">这是本轮 Research Query 直接返回的全部语义近邻，用于发现学术社区和候选 Venue。默认显示前 5 篇，可展开查看本轮返回的全部 {run.semanticRetrieval.works.length} 篇；它们不是推荐 Venue 本身。</p></div><Badge>{run.semanticRetrieval.works.length} works</Badge></div><OpenAlexEvidenceList title="全局相似论文" items={run.semanticRetrieval.works}/></Card>}

  {run.semanticRetrieval?.status==="unavailable"&&<div className="rounded-xl border border-[#f0d7a8] bg-[#fff9ed] px-4 py-3 text-xs leading-5 text-[#8a6528]">OpenAlex 语义检索本轮不可用，因此系统明确降级为低置信回退；同一 CCF 大类不会再自动获得高 Research Match。{run.semanticRetrieval.error?` 原因：${run.semanticRetrieval.error}`:""}</div>}{run.semanticRetrieval?.sourceEnrichmentError&&<div className="rounded-xl border border-[#dbe1f6] bg-[#f7f8ff] px-4 py-3 text-xs leading-5 text-[#6671a4]">OpenAlex Source topic 补全本轮未成功；排序仍保留相似论文发表分布、CS scope 和稿件 References 信号，不会把缺失 topic 当作 0 分。</div>}{run.error&&<div className="rounded-xl border border-[#f0d7a8] bg-[#fff9ed] px-4 py-3 text-xs leading-5 text-[#8a6528]">部分 Venue 数据源本次刷新未成功：{run.error}</div>}

  {types.map(type=>{const list=sorted(eligible.filter(r=>r.venue.type===type)).slice(0,project.preferences.topN);return <section key={type}><div className="mb-3 flex items-end justify-between"><div><h3 className="text-base font-semibold">{showingActionable?"Currently Actionable Conferences":type==="conference"?"Academic Best-fit Conferences":"Academic Best-fit Journals"}</h3><p className="mt-1 text-xs text-[#949dac]">{list.length} 个结果</p></div></div>{list.length?<div className="grid gap-4 lg:grid-cols-2">{list.map(r=><VenueCard key={r.venue.id} result={r} compared={compared.includes(r.venue.id)} selected={project.selectedVenueId===r.venue.id} onCompare={()=>store.toggleCompareVenue(projectId,r.venue.id)} onDetails={()=>setDetails(r)} onSelect={()=>setSelecting(r)}/>)}</div>:<EmptyState icon={<CircleAlert className="size-5"/>} title={`没有可核验的${type==="conference"?"会议":"期刊"}结果`} description={showingActionable?"当前没有同时满足“已核验、未截止”和 Required actionability 条件的会议。学术适配榜仍会保留未来可考虑的 Venue。":"如果 Academic Required 条件依赖当前数据源没有提供的字段，Unknown 会按硬条件处理；可以返回投稿偏好调整。"} action={<Link href={`/app/projects/${projectId}/preferences`}><Button variant="secondary">调整投稿偏好</Button></Link>}/>}</section>})}

  {close.length>0&&<section><div className="mb-3"><h3 className="text-base font-semibold">Close alternatives</h3><p className="mt-1 text-xs text-[#949dac]">研究相关，但至少有一项 Required 条件失败或无法核验。</p></div><div className="grid gap-4 lg:grid-cols-2">{sorted(close).slice(0,6).map(r=><VenueCard key={r.venue.id} result={r} compared={compared.includes(r.venue.id)} selected={project.selectedVenueId===r.venue.id} onCompare={()=>store.toggleCompareVenue(projectId,r.venue.id)} onDetails={()=>setDetails(r)} onSelect={()=>setSelecting(r)}/>)}</div></section>}

  <AnimatePresence>{compared.length>0&&<motion.div className="fixed bottom-5 left-1/2 z-40 w-[min(720px,calc(100%-32px))] -translate-x-1/2 rounded-2xl border border-white/70 bg-[#17203a]/95 px-4 py-3 text-white shadow-[0_20px_60px_rgba(17,25,49,.28)] backdrop-blur-xl" initial={{opacity:0,y:18}} animate={{opacity:1,y:0}} exit={{opacity:0,y:18}}><div className="flex items-center gap-3"><GitCompareArrows className="size-4 text-[#9eabff]"/><div className="flex min-w-0 flex-1 gap-2 overflow-hidden">{compared.map(id=>{const r=academicPool.find(x=>x.venue.id===id);return r?<span key={id} className="truncate rounded-lg bg-white/10 px-2.5 py-1.5 text-xs">{r.venue.type==="conference"?displayVenue(r.venue):r.venue.shortName}</span>:null})}</div><Link href={`/app/projects/${projectId}/compare`}><Button size="sm" className="bg-white text-[#18213b] hover:bg-[#f1f3f8]">对比 {compared.length} 个 →</Button></Link></div></motion.div>}</AnimatePresence>

  <Modal open={Boolean(details)} onClose={()=>setDetails(undefined)} title="推荐依据">{details&&<div>
    <div className="flex items-start justify-between gap-4"><div><div className="text-lg font-semibold">{displayVenue(details.venue)}</div><div className="mt-1 text-xs text-[#8c96a8]">Academic Fit {details.academicScore??details.finalScore} / 100 · Research Match {details.researchMatch} · 不是录用概率</div></div><div className="text-3xl font-semibold text-[#4252c3]">{details.academicScore??details.finalScore}</div></div>
    <div className="mt-5 grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
      {[["Venue 近期论文",details.venueConditionedMatch],["全局 OpenAlex",details.semanticMatch],["CS scope",details.scopeMatch],["Semantic Scholar",details.secondaryMatch],["References",details.referenceMatch],["Source topics 辅助",details.topicMatch]].map(([label,value])=><div key={String(label)} className="rounded-xl bg-[#f7f8fb] p-4"><div className="text-xl font-semibold text-[#4050c0]">{value==null?"—":String(value)}</div><div className="mt-1 text-[10px] text-[#919aac]">{String(label)}</div></div>)}
    </div>
    {details.matchedScopes.length>0&&<div className="mt-4 flex flex-wrap gap-2">{details.matchedScopes.map(x=><Badge key={x} tone="brand">{x}</Badge>)}</div>}
    {details.referenceCount>0&&<div className="mt-4 rounded-xl bg-[#f7faf9] p-3 text-xs leading-5 text-[#587064]">稿件 References 中识别到该 Venue/系列 {details.referenceCount} 次。该信号只作为社区先验，不代表作者必须沿用参考文献中的投稿去向。</div>}
    <OpenAlexEvidenceList title="该 Venue/Series 近期语义近邻" items={details.venueConditionedEvidence??[]} subtitle={item=>`Venue-conditioned rank #${item.semanticRank??"—"} · ${item.year??"year n/a"} · ${item.sourceName??"source n/a"}`}/>
    <OpenAlexEvidenceList title="全局相似论文中直接发表于该 Venue 的证据" items={details.semanticEvidence??[]}/>
    <SecondaryEvidenceList items={details.secondaryEvidence??[]}/>
    <div className="mt-5"><div className="text-xs font-semibold">约束判定</div><div className="mt-2 space-y-2">{details.constraints.length?details.constraints.map((c,i)=><div key={i} className="flex items-start gap-2 rounded-xl border border-[#e7eaf0] p-3">{statusIcon(c.status)}<div className="min-w-0"><div className="text-xs font-semibold">{c.label} · {c.mode}</div><div className="mt-1 text-[11px] text-[#8b95a6]">{c.detail}</div></div><Badge className="ml-auto">{c.status}</Badge></div>):<div className="text-xs text-[#929bad]">没有启用针对该类型的额外约束。</div>}</div></div>
    <div className="mt-5 rounded-xl bg-[#f4f6ff] p-4 text-[11px] leading-5 text-[#6772a8]">候选来源：{details.venue.source}{details.venue.openalexSourceName?` · OpenAlex: ${details.venue.openalexSourceName}`:""}。Academic Fit 与 Current Actionability 分离；Venue-conditioned 近期论文检索是内容适配主信号，缺失身份时保持 Unknown。</div>
  </div>}</Modal>
  <Modal open={Boolean(selecting)} onClose={()=>setSelecting(undefined)} title="设为目标投稿 venue" footer={<><Button variant="secondary" onClick={()=>setSelecting(undefined)}>取消</Button><Button onClick={()=>{if(selecting){store.selectVenue(projectId,selecting.venue);setSelecting(undefined)}}}>确认选择</Button></>}>{selecting&&<div><p className="text-sm leading-6 text-[#687388]">将 <b>{selecting.venue.type==="conference"?displayVenue(selecting.venue):selecting.venue.name}</b> 设为这个研究项目当前的目标投稿 venue。你仍然可以返回推荐页重新选择。</p>{!selecting.eligible&&<div className="mt-4 rounded-xl bg-[#fff7ea] p-3 text-xs leading-5 text-[#8a662a]">注意：这个候选没有通过全部 Required 条件。系统允许你手动选择，但不会把它标记为“完全满足约束”。</div>}</div>}</Modal>
  </div>;
}
