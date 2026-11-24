"use client";

import {
  ArrowLeft, Bot, BrainCircuit, CheckCircle2, CircleHelp, Cpu, ExternalLink,
  Eye, EyeOff, FileText, KeyRound, LoaderCircle, LockKeyhole, RefreshCw,
  RadioTower, ScanText, ServerCog, ShieldCheck, SlidersHorizontal, Sparkles, TriangleAlert
} from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Badge, Button, Card, Input, Switch } from "@/components/ui";
import { ScholarlyDataSettingsPanel } from "@/components/scholarly-data-settings";
import {
  getIntegrationSettings, saveIntegrationSettings, testAIIntegration, testOCRIntegration
} from "@/lib/backend-client";
import type {
  AIConnectionTest, AIOutputMode, AIProtocol, AIProviderName, AIProviderProfileSettings, IntegrationSettings,
  IntegrationSettingsUpdate, OCRConnectionTest
} from "@/lib/types";
import { cn } from "@/lib/utils";

const PROVIDERS: Record<AIProviderName, {label:string; sub:string; icon:typeof BrainCircuit}> = {
  openai: { label:"OpenAI", sub:"原生 Responses、多模态与 Files API", icon:Sparkles },
  deepseek: { label:"DeepSeek", sub:"OpenAI-compatible，适合文本研究理解", icon:BrainCircuit },
  custom: { label:"自定义", sub:"任意 OpenAI-compatible API 网关", icon:ServerCog },
};

const defaults: Record<AIProviderName, Partial<IntegrationSettings>> = {
  openai: { baseUrl:"https://api.openai.com/v1", model:"gpt-5.6", protocol:"responses", outputMode:"json_schema", reasoningEffort:"medium", reasoningEnabled:true, streamingEnabled:true, supportsVision:true, supportsFiles:true, sendDirectPdf:false },
  deepseek: { baseUrl:"https://api.deepseek.com", model:"deepseek-v4-pro", protocol:"chat_completions", outputMode:"json_object", reasoningEffort:"high", reasoningEnabled:true, streamingEnabled:true, supportsVision:false, supportsFiles:false, sendDirectPdf:false },
  custom: { baseUrl:"", model:"", protocol:"responses", outputMode:"json_object", reasoningEffort:"medium", reasoningEnabled:true, streamingEnabled:true, supportsVision:false, supportsFiles:false, sendDirectPdf:false },
};

function defaultProfile(provider:AIProviderName):AIProviderProfileSettings{
  const d=defaults[provider];
  return {
    provider, baseUrl:String(d.baseUrl??""), model:String(d.model??""),
    protocol:(d.protocol??"responses") as AIProtocol, outputMode:(d.outputMode??"json_object") as AIOutputMode,
    reasoningEffort:(d.reasoningEffort??"medium") as AIProviderProfileSettings["reasoningEffort"],
    reasoningEnabled:d.reasoningEnabled??true, streamingEnabled:d.streamingEnabled??true,
    transportProfile:"auto", apiKeyConfigured:false, apiKeyHint:undefined,
    supportsVision:d.supportsVision??false, supportsFiles:d.supportsFiles??false, sendDirectPdf:false,
    source:"default", lastAiTest:null,
  };
}

function profileFromCfg(cfg:IntegrationSettings, existing?:AIProviderProfileSettings):AIProviderProfileSettings{
  return {
    ...(existing??defaultProfile(cfg.provider)), provider:cfg.provider, baseUrl:cfg.baseUrl, model:cfg.model,
    protocol:cfg.protocol, outputMode:cfg.outputMode, reasoningEffort:cfg.reasoningEffort,
    reasoningEnabled:cfg.reasoningEnabled, streamingEnabled:cfg.streamingEnabled, transportProfile:cfg.transportProfile,
    apiKeyConfigured:cfg.apiKeyConfigured, apiKeyHint:cfg.apiKeyHint, supportsVision:cfg.supportsVision,
    supportsFiles:cfg.supportsFiles, sendDirectPdf:cfg.sendDirectPdf, source:cfg.source, lastAiTest:cfg.lastAiTest??null,
  };
}

function Select({value,onChange,children}:{value:string;onChange:(v:string)=>void;children:ReactNode}){
  return <select value={value} onChange={e=>onChange(e.target.value)} className="focus-ring h-11 w-full rounded-[11px] border border-[#dce1ea] bg-white px-3.5 text-sm text-[#273149] outline-none">{children}</select>;
}

function Field({label,help,children}:{label:string;help?:React.ReactNode;children:ReactNode}){
  return <label className="block"><div className="mb-2 flex items-center justify-between gap-3"><span className="text-xs font-semibold text-[#566075]">{label}</span>{help&&<span className="text-[11px] text-[#929bad]">{help}</span>}</div>{children}</label>;
}

function CheckResult({result}:{result?:AIConnectionTest}){
  if(!result)return null;
  const optionalFailures=result.optionalFailures??[];
  const headline=result.ok?(optionalFailures.length?"当前研究理解配置可用，存在可选能力未通过":"连接与结构化输出测试通过"):"必需能力测试未通过";
  return <Card className={cn("mt-5 border p-5",result.ok?"border-[#cfe9de] bg-[#f8fdfb]":"border-[#f0d6d9] bg-[#fffafb]")}>
    <div className="flex items-start gap-3"><div className={cn("mt-0.5 grid size-8 shrink-0 place-items-center rounded-xl",result.ok?"bg-[#e8f8f1] text-[#14805b]":"bg-[#fff0f2] text-[#b34656]")}>{result.ok?<CheckCircle2 className="size-4"/>:<TriangleAlert className="size-4"/>}</div><div className="min-w-0 flex-1"><div className="text-sm font-semibold">{headline}</div><div className="mt-1 text-xs text-[#7a8497]">{result.provider} · {result.model} · {result.protocol}</div>{result.ok&&optionalFailures.length>0&&<p className="mt-2 text-[11px] leading-5 text-[#7d886a]">可选能力 {optionalFailures.join(", ")} 未通过，但当前配置没有要求这些能力，因此不会阻止研究理解。比如关闭“直接发送原始 PDF”后，Files API 失败不再被视为主链路失败。</p>}</div></div>
    <div className="mt-4 grid gap-2 md:grid-cols-2">{Object.entries(result.checks).map(([name,item])=>{const optional=item.required===false;const tone=item.ok===true?"success":item.ok===false?(optional?"warning":"danger"):"neutral";const label=item.ok===true?"通过":item.ok===false?(optional?"可选失败":"失败"):"未测试";return <div key={name} className="rounded-xl border border-[#e7eaf0] bg-white px-3 py-3"><div className="flex items-center justify-between gap-2"><span className="text-xs font-semibold capitalize text-[#566075]">{name}</span><div className="flex items-center gap-1.5">{optional&&<span className="text-[9px] text-[#98a1af]">optional</span>}<Badge tone={tone}>{label}</Badge></div></div><p className="mt-2 break-words text-[11px] leading-5 text-[#7f899b]">{item.message}</p></div>})}</div>
  </Card>;
}

export default function SettingsPage(){
  const [cfg,setCfg]=useState<IntegrationSettings>();
  const [providerDrafts,setProviderDrafts]=useState<Record<AIProviderName,AIProviderProfileSettings>>();
  const [keyDrafts,setKeyDrafts]=useState<Record<AIProviderName,string>>({openai:"",deepseek:"",custom:""});
  const [showKey,setShowKey]=useState(false);
  const [clearKeys,setClearKeys]=useState<Record<AIProviderName,boolean>>({openai:false,deepseek:false,custom:false});
  const [loading,setLoading]=useState(true);
  const [saving,setSaving]=useState(false);
  const [testing,setTesting]=useState(false);
  const [testingOcr,setTestingOcr]=useState(false);
  const [aiTest,setAiTest]=useState<AIConnectionTest>();
  const [ocrTest,setOcrTest]=useState<OCRConnectionTest>();
  const [message,setMessage]=useState<string>();
  const [returnTo,setReturnTo]=useState<string>();

  const refresh=async()=>{setLoading(true);try{const next=await getIntegrationSettings();const profiles={openai:next.providerProfiles?.openai??defaultProfile("openai"),deepseek:next.providerProfiles?.deepseek??defaultProfile("deepseek"),custom:next.providerProfiles?.custom??defaultProfile("custom")};setCfg(next);setProviderDrafts(profiles);setAiTest(profiles[next.provider]?.lastAiTest??next.lastAiTest??undefined);}catch(e){setMessage(e instanceof Error?e.message:String(e));}finally{setLoading(false)}};
  useEffect(()=>{void refresh();const candidate=new URLSearchParams(window.location.search).get("from");if(candidate?.startsWith("/app/"))setReturnTo(candidate)},[]);

  const applyProvider=(provider:AIProviderName)=>{
    if(!cfg)return;
    const currentDraft=profileFromCfg(cfg,providerDrafts?.[cfg.provider]);
    const nextDrafts={openai:providerDrafts?.openai??defaultProfile("openai"),deepseek:providerDrafts?.deepseek??defaultProfile("deepseek"),custom:providerDrafts?.custom??defaultProfile("custom"),[cfg.provider]:currentDraft};
    const target=nextDrafts[provider]??defaultProfile(provider);
    setProviderDrafts(nextDrafts);
    setCfg({...cfg,provider,baseUrl:target.baseUrl,model:target.model,protocol:target.protocol,outputMode:target.outputMode,reasoningEffort:target.reasoningEffort,reasoningEnabled:target.reasoningEnabled,streamingEnabled:target.streamingEnabled,transportProfile:target.transportProfile,apiKeyConfigured:target.apiKeyConfigured,apiKeyHint:target.apiKeyHint,supportsVision:target.supportsVision,supportsFiles:target.supportsFiles,sendDirectPdf:target.sendDirectPdf,lastAiTest:target.lastAiTest??null});
    setAiTest(target.lastAiTest??undefined); setMessage(undefined); setShowKey(false);
  };

  const payload=():IntegrationSettingsUpdate=>({
    provider:cfg!.provider, base_url:cfg!.baseUrl.trim(), model:cfg!.model.trim(), protocol:cfg!.protocol,
    output_mode:cfg!.outputMode, reasoning_effort:cfg!.reasoningEffort, reasoning_enabled:cfg!.reasoningEnabled, streaming_enabled:cfg!.streamingEnabled, transport_profile:cfg!.transportProfile,
    api_key:clearKeys[cfg!.provider]?"":keyDrafts[cfg!.provider].trim()?keyDrafts[cfg!.provider].trim():undefined,
    supports_vision:cfg!.supportsVision, supports_files:cfg!.supportsFiles,
    send_direct_pdf:false,
    max_text_chars:cfg!.maxTextChars,max_visual_assets:cfg!.maxVisualAssets,max_pdf_files:cfg!.maxPdfFiles,
    max_output_tokens:cfg!.maxOutputTokens,chunk_text_chars:cfg!.chunkTextChars,chunk_output_tokens:cfg!.chunkOutputTokens,
    synthesis_max_chars:cfg!.synthesisMaxChars,max_provider_calls:cfg!.maxProviderCalls,visuals_per_chunk:cfg!.visualsPerChunk,
    request_timeout_seconds:cfg!.requestTimeoutSeconds,tesseract_cmd:cfg!.tesseractCmd,ocr_languages:cfg!.ocrLanguages,
    ocr_min_native_text_chars:cfg!.ocrMinNativeTextChars,
  });

  const absorbSavedProvider=(next:IntegrationSettings)=>{const saved=next.providerProfiles?.[next.provider]??profileFromCfg(next);setProviderDrafts(prev=>({openai:prev?.openai??next.providerProfiles?.openai??defaultProfile("openai"),deepseek:prev?.deepseek??next.providerProfiles?.deepseek??defaultProfile("deepseek"),custom:prev?.custom??next.providerProfiles?.custom??defaultProfile("custom"),[next.provider]:saved}));setKeyDrafts(prev=>({...prev,[next.provider]:""}));setClearKeys(prev=>({...prev,[next.provider]:false}));};
  const save=async()=>{if(!cfg)return;setSaving(true);setMessage(undefined);try{const next=await saveIntegrationSettings(payload());setCfg(next);absorbSavedProvider(next);setMessage(`${PROVIDERS[next.provider].label} 配置已单独保存并设为当前 Provider；其他 Provider 的已保存配置不会被覆盖。`);}catch(e){setMessage(e instanceof Error?e.message:String(e));}finally{setSaving(false)}};
  const saveAndTest=async()=>{if(!cfg)return;setTesting(true);setMessage(undefined);try{const next=await saveIntegrationSettings(payload());setCfg(next);absorbSavedProvider(next);const result=await testAIIntegration();setAiTest(result);const refreshed=await getIntegrationSettings();setCfg(refreshed);setProviderDrafts(prev=>({
      openai:prev?.openai??refreshed.providerProfiles?.openai??defaultProfile("openai"),
      deepseek:prev?.deepseek??refreshed.providerProfiles?.deepseek??defaultProfile("deepseek"),
      custom:prev?.custom??refreshed.providerProfiles?.custom??defaultProfile("custom"),
      [refreshed.provider]:refreshed.providerProfiles?.[refreshed.provider]??profileFromCfg(refreshed),
    }));}catch(e){setMessage(e instanceof Error?e.message:String(e));}finally{setTesting(false)}};
  const testOcr=async()=>{if(!cfg)return;setTestingOcr(true);setMessage(undefined);try{const next=await saveIntegrationSettings(payload());setCfg(next);const result=await testOCRIntegration();setOcrTest(result);}catch(e){setMessage(e instanceof Error?e.message:String(e));}finally{setTestingOcr(false)}};

  const providerHelp=useMemo(()=>cfg?.provider==="openai"?{text:"如何获取 OpenAI API Key？",url:"https://platform.openai.com/api-keys",note:"进入 OpenAI API Platform 的 API Keys 页面，创建新的 Secret Key；模型调用会按 API 平台用量计费。"}:cfg?.provider==="deepseek"?{text:"如何获取 DeepSeek API Key？",url:"https://platform.deepseek.com/",note:"登录 DeepSeek 开放平台，在 API Keys 中创建密钥，并确认账户额度可用。"}:{text:"如何填写自定义服务？",url:"",note:"按服务商文档原样填写 Base URL、模型 ID 和 API Key；不要猜测 /v1、Responses、Vision 或 Files 能力，保存后逐项测试。"},[cfg?.provider]);

  if(loading||!cfg)return <div className="mx-auto max-w-[1180px] px-5 py-10 lg:px-8"><Card className="grid min-h-64 place-items-center"><div className="text-center"><LoaderCircle className="mx-auto size-6 animate-spin text-[#5f6ee3]"/><p className="mt-3 text-sm text-[#7d8798]">正在读取本地集成配置…</p></div></Card></div>;

  return <div className="mx-auto max-w-[1180px] px-5 py-8 lg:px-8 lg:py-10">
    <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between"><div>{returnTo&&<a href={returnTo} className="mb-3 inline-flex items-center gap-1.5 text-xs font-semibold text-[#6571d8] hover:text-[#3f4dbb]"><ArrowLeft className="size-3.5"/>返回上一页</a>}<div className="text-xs font-semibold uppercase tracking-[.16em] text-[#8791a5]">Settings · Integrations</div><h1 className="mt-2 text-3xl font-semibold tracking-[-.045em]">系统连接与解析</h1><p className="mt-2 max-w-3xl text-sm leading-6 text-[#7d8799]">集中管理 AI Provider、学术数据源与 OCR。每个外部连接都可以单独保存和真实诊断；推荐阶段只使用已经返回的可核验证据，数据源缺失会显式降级而不会伪造。</p></div><div className="flex gap-2"><Button variant="secondary" onClick={()=>void refresh()}><RefreshCw className="size-4"/>重新读取</Button><Button onClick={()=>void save()} disabled={saving||testing}>{saving?<LoaderCircle className="size-4 animate-spin"/>:<ShieldCheck className="size-4"/>}保存配置</Button></div></div>

    {message&&<motion.div initial={{opacity:0,y:-6}} animate={{opacity:1,y:0}} className="mt-5 rounded-xl border border-[#dfe4ee] bg-white px-4 py-3 text-sm text-[#667186]">{message}</motion.div>}

    <section className="mt-8"><div className="mb-3 flex items-center gap-2 text-sm font-semibold"><Bot className="size-4 text-[#6170df]"/>AI Provider</div><div className="grid gap-3 md:grid-cols-3">{(Object.keys(PROVIDERS) as AIProviderName[]).map(provider=>{const item=PROVIDERS[provider],Icon=item.icon,active=cfg.provider===provider,profile=providerDrafts?.[provider];return <motion.button whileHover={{y:-2}} whileTap={{scale:.992}} key={provider} onClick={()=>applyProvider(provider)} className={cn("relative rounded-2xl border p-5 text-left transition",active?"border-[#8d98ef] bg-[#f3f4ff] shadow-[0_8px_28px_rgba(71,85,190,.10)]":"border-[#e1e5ec] bg-white hover:border-[#cfd5df]")}><div className={cn("grid size-10 place-items-center rounded-xl",active?"bg-[#626fe2] text-white":"bg-[#f1f3f7] text-[#6f798b]")}><Icon className="size-5"/></div><div className="mt-4 flex items-center gap-2"><span className="text-sm font-semibold">{item.label}</span>{active&&<Badge tone="brand">当前</Badge>}{profile?.apiKeyConfigured&&<Badge tone="success">Key 已保存</Badge>}</div><p className="mt-1.5 text-xs leading-5 text-[#8490a2]">{item.sub}</p>{profile?.model&&<p className="mt-2 truncate text-[10px] font-medium text-[#737f94]">{profile.model}</p>}</motion.button>})}</div><p className="mt-3 text-[11px] leading-5 text-[#818b9d]">OpenAI、DeepSeek、自定义各自保存独立的 Base URL、模型、协议、能力开关与加密 API Key。切换 Provider 只切换当前编辑视图；不会再覆盖其他 Provider 的配置，本页尚未保存的编辑也会在切换回来时保留。</p></section>

    <section className="mt-6"><ScholarlyDataSettingsPanel/></section>

    <div className="mt-6 grid items-start gap-5 xl:grid-cols-[minmax(0,1.55fr)_minmax(300px,.85fr)]">
      <div className="space-y-5">
        <Card className="p-6"><div className="flex items-start justify-between gap-4"><div><div className="flex items-center gap-2 text-base font-semibold"><KeyRound className="size-4 text-[#6573e3]"/>连接配置</div><p className="mt-1.5 text-xs leading-5 text-[#8a94a6]">API Key 只保存在这台后端机器上，并使用本地生成的密钥加密后写入数据库。页面不会回传完整密钥。</p></div>{cfg.source==="environment"&&<Badge tone="warning">来自环境变量</Badge>}</div>
          <div className="mt-6 grid gap-5 md:grid-cols-2"><Field label="API Key" help={cfg.apiKeyConfigured?`已保存 ${cfg.apiKeyHint??""}`:"尚未配置"}><div><div className="relative"><Input type={showKey?"text":"password"} value={keyDrafts[cfg.provider]} disabled={clearKeys[cfg.provider]} onChange={e=>{setKeyDrafts(prev=>({...prev,[cfg.provider]:e.target.value}));setClearKeys(prev=>({...prev,[cfg.provider]:false}))}} placeholder={clearKeys[cfg.provider]?"保存后将清除密钥":cfg.apiKeyConfigured?"留空表示继续使用已保存密钥":"粘贴 API Key"}/><button type="button" onClick={()=>setShowKey(!showKey)} className="absolute right-2 top-1/2 -translate-y-1/2 rounded-lg p-2 text-[#8b95a5] hover:bg-[#f0f2f6]">{showKey?<EyeOff className="size-4"/>:<Eye className="size-4"/>}</button></div>{cfg.apiKeyConfigured&&<button type="button" onClick={()=>{setClearKeys(prev=>({...prev,[cfg.provider]:!prev[cfg.provider]}));setKeyDrafts(prev=>({...prev,[cfg.provider]:""}))}} className="mt-2 text-[11px] font-semibold text-[#9b5460] hover:text-[#813845]">{clearKeys[cfg.provider]?"取消清除":"清除已保存密钥"}</button>}</div></Field><Field label="Base URL" help="填写 SDK 基地址"><Input value={cfg.baseUrl} onChange={e=>setCfg({...cfg,baseUrl:e.target.value})} placeholder="https://api.example.com/v1"/></Field><Field label="模型名"><Input value={cfg.model} onChange={e=>setCfg({...cfg,model:e.target.value})} placeholder="模型 ID"/></Field><Field label="调用协议"><Select value={cfg.protocol} onChange={v=>setCfg({...cfg,protocol:v as AIProtocol})}><option value="responses">Responses API</option><option value="chat_completions">Chat Completions</option></Select></Field><Field label="结构化输出"><Select value={cfg.outputMode} onChange={v=>setCfg({...cfg,outputMode:v as AIOutputMode})}><option value="json_schema">JSON Schema</option><option value="json_object">JSON Object（兼容模式）</option></Select></Field><Field label="推理强度"><div className="flex gap-2"><div className="flex flex-1 items-center justify-between rounded-[11px] border border-[#dce1ea] bg-white px-3.5"><span className="text-xs text-[#667185]">发送 reasoning 参数</span><Switch label="发送 reasoning 参数" checked={cfg.reasoningEnabled} onCheckedChange={v=>setCfg({...cfg,reasoningEnabled:v})}/></div><div className="w-32"><Select value={cfg.reasoningEffort} onChange={v=>setCfg({...cfg,reasoningEffort:v as IntegrationSettings["reasoningEffort"]})}><option value="low">low</option><option value="medium">medium</option><option value="high">high</option><option value="xhigh">xhigh</option><option value="max">max</option></Select></div></div></Field></div>
          {providerHelp&&<div className="mt-5 rounded-xl border border-[#e4e7f1] bg-[#fafbff] p-4"><div className="flex items-start gap-2"><CircleHelp className="mt-0.5 size-4 shrink-0 text-[#6773dc]"/><div><div className="text-xs font-semibold text-[#566176]">{providerHelp.text}</div><p className="mt-1 text-[11px] leading-5 text-[#8791a3]">{providerHelp.note}</p>{providerHelp.url&&<a href={providerHelp.url} target="_blank" rel="noreferrer" className="mt-2 inline-flex items-center gap-1 text-[11px] font-semibold text-[#5c69d7] hover:text-[#3948be]">打开官方页面<ExternalLink className="size-3"/></a>}</div></div></div>}
          {cfg.provider==="deepseek"&&<div className="mt-5 rounded-xl border border-[#e6e2ca] bg-[#fffcf2] p-4 text-xs leading-5 text-[#776d46]">DeepSeek 预设现在优先使用 Chat Completions + JSON Object：这是 V4-Flash / V4-Pro 都支持的文本接口，更适合稳定的研究文本抽取。DeepSeek 仍按纯文本 Provider 使用，Vision / Files 默认关闭；扫描稿先由本地 OCR 转成文本。</div>}
          {cfg.provider==="custom"&&<div className="mt-5 rounded-xl border border-[#dfe4ec] bg-[#fafbfd] p-4 text-xs leading-5 text-[#7c8698]">自定义网关不会被假定拥有任何高级能力。Base URL 不会自动补 <code>/v1</code>。默认“自动”分析策略会把自定义网关切到 Edge-safe：文本小块、短输出、图片单独逐张请求，避免把文字和视觉混在一个长请求里。</div>}
        </Card>

        <Card className="p-6"><div className="flex items-center gap-2 text-base font-semibold"><SlidersHorizontal className="size-4 text-[#6573e3]"/>输入能力与隐私</div><div className="mt-5 divide-y divide-[#edf0f4]">
          <div className="flex items-center justify-between gap-6 py-4"><div className="min-w-0 pr-4"><div className="flex items-center gap-2"><RadioTower className="size-4 text-[#6573e3]"/><div className="text-sm font-medium text-[#3e485f]">流式传输（推荐）</div><Badge tone="success">SSE</Badge></div><p className="mt-1 text-xs leading-5 text-[#8a94a6]">让 Provider 在生成过程中持续返回事件。对于 Tencent EdgeOne、Cloudflare 或反向代理后的自定义网关，这可以避免等待完整模型结果时触发回源超时（例如 EdgeOne 524/554）。</p></div><Switch label="流式传输" checked={cfg.streamingEnabled} onCheckedChange={v=>setCfg({...cfg,streamingEnabled:v})}/></div>
          <div className="flex items-center justify-between gap-6 py-4"><div><div className="text-sm font-medium text-[#3e485f]">视觉输入</div><p className="mt-1 text-xs leading-5 text-[#8a94a6]">允许把提取出的论文 Figure / 页面渲染 / 上传图片发送给模型。</p></div><Switch label="视觉输入" checked={cfg.supportsVision} onCheckedChange={v=>setCfg({...cfg,supportsVision:v})} disabled={cfg.provider==="deepseek"}/></div>
          <div className="flex items-center justify-between gap-6 py-4"><div><div className="text-sm font-medium text-[#3e485f]">Files API</div><p className="mt-1 text-xs leading-5 text-[#8a94a6]">声明当前 Provider 支持兼容的 Files API。自定义网关默认关闭。</p></div><Switch label="Files API" checked={cfg.supportsFiles} onCheckedChange={v=>setCfg({...cfg,supportsFiles:v,sendDirectPdf:v?cfg.sendDirectPdf:false})} disabled={cfg.provider==="deepseek"}/></div>
          <div className="flex items-center justify-between gap-6 py-4"><div><div className="flex items-center gap-2"><div className="text-sm font-medium text-[#3e485f]">原始 PDF 直传</div><Badge tone="neutral">当前分层模式固定关闭</Badge></div><p className="mt-1 text-xs leading-5 text-[#8a94a6]">研究理解只发送本地抽取后的受控证据块和视觉资产，不上传整份原始 PDF。这样单次请求规模和成本边界可预测，也不会依赖 Files API。</p></div><Switch label="原始 PDF 直传" checked={false} onCheckedChange={()=>{}} disabled/></div>
        </div>
          <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-3"><Field label="项目文本选择上限"><Input type="number" value={cfg.maxTextChars} onChange={e=>setCfg({...cfg,maxTextChars:Number(e.target.value)})}/></Field><Field label="项目视觉资产总上限"><Input type="number" value={cfg.maxVisualAssets} onChange={e=>setCfg({...cfg,maxVisualAssets:Number(e.target.value)})}/></Field><Field label="最终画像输出 tokens 上限"><Input type="number" value={cfg.maxOutputTokens} onChange={e=>setCfg({...cfg,maxOutputTokens:Number(e.target.value)})}/></Field></div>
        </Card>

        <Card className="relative overflow-hidden p-6"><div className="absolute inset-x-0 top-0 h-0.5 bg-[linear-gradient(90deg,#6676ff,#8d6ef1,#1fb6bd)]"/><div className="flex items-start justify-between gap-4"><div><div className="flex items-center gap-2 text-base font-semibold"><ShieldCheck className="size-4 text-[#6573e3]"/>研究理解传输与成本保护</div><p className="mt-1.5 max-w-2xl text-xs leading-5 text-[#8a94a6]">V3.6 固定采用 Text-first：文件先在本机解析；文字只以小块文本请求发送；图片在文字成功之后逐张单独分析；最后只把压缩后的研究事实做一次文本汇总。不会再把“长文本 + 图片”混在同一个请求里。</p></div><Badge tone="success">Text-first</Badge></div><div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3"><Field label="分析策略" help="自定义网关建议自动"><Select value={cfg.transportProfile} onChange={v=>setCfg({...cfg,transportProfile:v as IntegrationSettings["transportProfile"]})}><option value="auto">自动（推荐）</option><option value="standard">标准</option><option value="edge_safe">兼容网关 / Edge-safe</option></Select></Field><Field label="单块文本字符" help={cfg.transportProfile==="edge_safe"|| (cfg.transportProfile==="auto"&&cfg.provider==="custom")?"Edge-safe 实际最多 2,800":"DeepSeek 实际最多 6,000；其他按配置"}><Input type="number" value={cfg.chunkTextChars} onChange={e=>setCfg({...cfg,chunkTextChars:Number(e.target.value)})}/></Field><Field label="最大真实 API 请求数" help="文本 + 图片 + 最终汇总"><Input type="number" value={cfg.maxProviderCalls} onChange={e=>setCfg({...cfg,maxProviderCalls:Number(e.target.value)})}/></Field><Field label="单块输出 tokens"><Input type="number" value={cfg.chunkOutputTokens} onChange={e=>setCfg({...cfg,chunkOutputTokens:Number(e.target.value)})}/></Field><Field label="最终汇总输入字符"><Input type="number" value={cfg.synthesisMaxChars} onChange={e=>setCfg({...cfg,synthesisMaxChars:Number(e.target.value)})}/></Field><Field label="单请求超时（秒）"><Input type="number" value={cfg.requestTimeoutSeconds} onChange={e=>setCfg({...cfg,requestTimeoutSeconds:Number(e.target.value)})}/></Field></div><div className="mt-5 grid gap-3 md:grid-cols-3"><div className="rounded-xl border border-[#e4e7f1] bg-white p-4"><div className="text-[11px] font-semibold text-[#59647a]">① 文本抽取</div><p className="mt-1 text-[11px] leading-5 text-[#8791a3]">只发送文本，不带图片；使用更小、更简单的 JSON 合约。</p></div><div className="rounded-xl border border-[#e4e7f1] bg-white p-4"><div className="text-[11px] font-semibold text-[#59647a]">② 视觉抽取</div><p className="mt-1 text-[11px] leading-5 text-[#8791a3]">Vision 开启时一张图一次请求；失败不会丢掉已完成的文本理解。</p></div><div className="rounded-xl border border-[#e4e7f1] bg-white p-4"><div className="text-[11px] font-semibold text-[#59647a]">③ 最终汇总</div><p className="mt-1 text-[11px] leading-5 text-[#8791a3]">只上传压缩后的事实；若最终汇总失败，会保留已付费的抽取结果并本地组装画像。</p></div></div><div className="mt-5 rounded-xl border border-[#dfe4f4] bg-[#f8f9ff] p-4 text-[11px] leading-5 text-[#6f7891]"><b className="text-[#505b78]">自动策略：</b> OpenAI / DeepSeek 使用标准模式；自定义 Provider 自动使用 Edge-safe（文本块最多 2,800 字符、短输出、最多 1 个独立视觉请求、最终汇总关闭 reasoning），以降低 CDN 首字节超时风险。SDK 自动重试仍为 0。</div></Card>

        <Card className="p-6"><div className="flex items-start justify-between gap-4"><div><div className="flex items-center gap-2 text-base font-semibold"><ScanText className="size-4 text-[#168f92]"/>OCR</div><p className="mt-1.5 text-xs leading-5 text-[#8a94a6]">优先读取 PDF 原生文本；只有文字不足的页面和独立图片才尝试 OCR，不对正常电子论文重复识别。</p></div><Badge tone={ocrTest?.ok?"success":"neutral"}>{ocrTest?.ok?"可用":ocrTest?"需处理":"未检测"}</Badge></div><div className="mt-6 grid gap-5 md:grid-cols-2"><Field label="Tesseract 可执行文件" help="留空自动从 PATH 检测"><Input value={cfg.tesseractCmd} onChange={e=>setCfg({...cfg,tesseractCmd:e.target.value})} placeholder="C:/Program Files/Tesseract-OCR/tesseract.exe"/></Field><Field label="OCR 语言"><Input value={cfg.ocrLanguages} onChange={e=>setCfg({...cfg,ocrLanguages:e.target.value})} placeholder="eng 或 eng+chi_sim"/></Field><Field label="触发 OCR 的原生文本阈值"><Input type="number" value={cfg.ocrMinNativeTextChars} onChange={e=>setCfg({...cfg,ocrMinNativeTextChars:Number(e.target.value)})}/></Field><div className="flex items-end"><Button variant="secondary" className="w-full" onClick={()=>void testOcr()} disabled={testingOcr}>{testingOcr?<LoaderCircle className="size-4 animate-spin"/>:<Cpu className="size-4"/>}保存并检测 OCR</Button></div></div>{ocrTest&&<div className={cn("mt-4 rounded-xl border p-4 text-xs leading-5",ocrTest.ok?"border-[#cee8dd] bg-[#f7fcfa] text-[#4d7769]":"border-[#f0d8d9] bg-[#fffafa] text-[#8a5a60]")}><div className="font-semibold">{ocrTest.message}</div>{ocrTest.version&&<div className="mt-1">Version: {ocrTest.version}</div>}{ocrTest.installedLanguages&&<div className="mt-1 break-words">Installed languages: {ocrTest.installedLanguages.join(", ")}</div>}</div>}<div className="mt-4 rounded-xl border border-[#dfe9e9] bg-[#f8fcfc] p-4 text-[11px] leading-5 text-[#708589]"><b className="text-[#4c6f74]">配置提示：</b> 安装 Tesseract 后可以留空路径让系统从 PATH 自动检测；Windows 常见路径为 <code>C:/Program Files/Tesseract-OCR/tesseract.exe</code>。英文使用 <code>eng</code>，中英混合可使用 <code>eng+chi_sim</code>，前提是对应语言包已经安装。</div><a href="https://github.com/tesseract-ocr/tessdoc/blob/main/Downloads.md" target="_blank" rel="noreferrer" className="mt-4 inline-flex items-center gap-1.5 text-xs font-semibold text-[#4d7d83]"><CircleHelp className="size-3.5"/>查看 Tesseract 安装说明<ExternalLink className="size-3"/></a></Card>
      </div>

      <aside className="min-w-0 space-y-5">
        <Card className="overflow-hidden p-0"><div className="border-b border-[#edf0f4] bg-[linear-gradient(135deg,#f6f7ff,#f4fbfb)] p-5"><div className="flex items-center gap-2 text-sm font-semibold"><BrainCircuit className="size-4 text-[#6270df]"/>连接诊断</div><p className="mt-2 text-xs leading-5 text-[#7e899b]">不是只测试“Key 能不能用”。Super Scholar 会分别检查基础文本、结构化输出，以及你声明启用的视觉与 Files / PDF 能力。这里使用真实小型兼容性请求，并单独检测 SSE Streaming 与首事件延迟。真实研究理解采用“本地解析 → 文本小块 → 图片逐张 → 压缩事实汇总”，SDK 自动重试已关闭；任意 Provider 请求失败都会立即停止，不会在后台继续重复扣费。</p></div><div className="p-5"><div className="space-y-3 text-xs">{[["Provider",PROVIDERS[cfg.provider].label],["Model",cfg.model||"未填写"],["Protocol",cfg.protocol],["Output",cfg.outputMode],["Transport",cfg.streamingEnabled?"SSE Streaming":"Non-streaming"],["Analysis",cfg.transportProfile==="auto"?(cfg.provider==="custom"?"Auto · Edge-safe":"Auto · Standard"):cfg.transportProfile],["API Key",cfg.apiKeyConfigured||Boolean(keyDrafts[cfg.provider])?"已配置":"未配置"]].map(([k,v])=><div key={k} className="flex items-center justify-between gap-3"><span className="text-[#929bad]">{k}</span><span className="max-w-[210px] truncate font-medium text-[#465168]">{v}</span></div>)}</div><Button className="mt-5 w-full" size="lg" onClick={()=>void saveAndTest()} disabled={testing||saving}>{testing?<LoaderCircle className="size-4 animate-spin"/>:<RefreshCw className="size-4"/>}{testing?"正在真实测试…":"保存并测试连接"}</Button><p className="mt-3 text-center text-[10px] leading-4 text-[#9aa3b1]">测试会产生极少量真实 API 请求与 token 消耗。</p></div></Card>
        <CheckResult result={aiTest}/>
        <Card className="p-5"><div className="flex items-center gap-2 text-sm font-semibold"><LockKeyhole className="size-4 text-[#6d788b]"/>数据边界</div><p className="mt-3 text-xs leading-5 text-[#828d9f]">API Key 由本机后端使用，浏览器不会读取完整密钥。研究材料是否被外部服务保存、用于何种目的仍取决于你选择的服务商政策；自定义网关尤其应自行核对。</p></Card>
        <Card className="p-5"><div className="flex items-center gap-2 text-sm font-semibold"><FileText className="size-4 text-[#6d788b]"/>推荐配置</div><p className="mt-3 text-xs leading-5 text-[#828d9f]">自定义网关建议保持 <b>自动 / Edge-safe</b>，并先让新的 <b>researchProbe</b> 通过。DeepSeek 推荐 Chat Completions + JSON Object。研究理解不依赖 Files API；Vision 与文本已经彻底拆成独立阶段。</p></Card>
      </aside>
    </div>
  </div>;
}
