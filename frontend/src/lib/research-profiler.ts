import type { CcfAreaCode, MaterialRecord, ResearchProfile } from "./types";
import { normalizeText } from "./utils";

const AREA_TERMS: Record<CcfAreaCode, string[]> = {
  DS: ["architecture", "microarchitecture", "gpu", "fpga", "parallel", "distributed system", "storage", "filesystem", "cache", "memory", "accelerator", "edge computing", "云计算", "体系结构", "并行", "分布式系统", "存储"],
  NW: ["network", "routing", "wireless", "5g", "6g", "traffic", "congestion", "sdn", "internet", "mobile network", "计算机网络", "无线网络", "路由", "拥塞"],
  SC: ["security", "privacy", "cryptography", "malware", "attack", "vulnerability", "authentication", "adversarial", "安全", "隐私", "密码", "攻击", "漏洞"],
  SE: ["software engineering", "program analysis", "compiler", "operating system", "programming language", "testing", "debugging", "verification", "软件工程", "编译", "程序分析", "操作系统", "程序设计语言", "测试"],
  DB: ["database", "data mining", "information retrieval", "recommendation", "knowledge graph", "query", "retrieval", "search engine", "数据库", "数据挖掘", "信息检索", "推荐系统", "知识图谱"],
  CT: ["algorithm", "complexity", "theorem", "proof", "graph theory", "optimization theory", "formal language", "算法", "复杂度", "定理", "证明", "图论", "理论"],
  CG: ["graphics", "rendering", "image processing", "multimedia", "video", "3d", "geometry", "visualization", "图形学", "渲染", "多媒体", "视频", "三维", "可视化"],
  AI: ["artificial intelligence", "machine learning", "deep learning", "neural network", "llm", "large language model", "computer vision", "nlp", "reinforcement learning", "segmentation", "detection", "classification", "生成模型", "人工智能", "机器学习", "深度学习", "大语言模型", "计算机视觉", "自然语言处理", "语义分割"],
  HI: ["human-computer", "hci", "user study", "interaction", "usability", "ubiquitous", "wearable", "interface", "人机交互", "用户研究", "可用性", "普适计算", "可穿戴"],
  MX: ["bioinformatics", "computational biology", "robotics", "autonomous", "iot", "cyber physical", "quantum computing", "digital twin", "interdisciplinary", "机器人", "物联网", "量子计算", "数字孪生", "交叉"]
};

const TOPIC_TERMS: Record<string, string[]> = {
  "Large Language Models": ["large language model", "llm", "transformer", "instruction tuning", "prompting"],
  "Computer Vision": ["computer vision", "image classification", "object detection", "semantic segmentation", "instance segmentation", "vision transformer", "image recognition"],
  "Natural Language Processing": ["natural language processing", "nlp", "machine translation", "language modeling", "named entity", "text classification"],
  "Federated Learning": ["federated learning", "federated optimization", "fedavg", "non-iid", "client drift", "联邦学习"],
  "Model Compression": ["quantization", "pruning", "compression", "knowledge distillation", "low-bit", "int8", "int4", "量化", "剪枝"],
  "Efficient AI": ["efficient", "lightweight", "latency", "memory footprint", "edge ai", "mobile inference", "parameter-efficient"],
  "Information Retrieval": ["information retrieval", "retrieval", "ranking", "search", "reranking", "dense retrieval"],
  "Recommender Systems": ["recommender", "recommendation system", "collaborative filtering"],
  "Knowledge Graphs": ["knowledge graph", "graph neural network", "gnn", "graph representation"],
  "Cybersecurity": ["security", "privacy", "cryptography", "malware", "vulnerability", "intrusion detection"],
  "Distributed Systems": ["distributed system", "distributed computing", "consensus", "replication", "fault tolerance"],
  "Software Engineering": ["software engineering", "program repair", "testing", "bug", "code generation", "program analysis"],
  "Human-Computer Interaction": ["human-computer interaction", "user study", "usability", "interaction design"],
  "Computer Graphics": ["rendering", "graphics", "3d reconstruction", "geometry processing", "neural rendering"],
  "Robotics": ["robot", "robotics", "slam", "navigation", "manipulation", "embodied"]
};

const METHOD_TERMS: Record<string, string[]> = {
  Transformer: ["transformer"],
  CNN: ["convolutional neural network", "cnn"],
  GNN: ["graph neural network", "gnn"],
  LoRA: ["lora", "low-rank adaptation"],
  "Parameter-Efficient Fine-Tuning": ["parameter-efficient", "peft", "adapter tuning"],
  Quantization: ["quantization", "int8", "int4", "low-bit", "w4a16", "w8a16"],
  Pruning: ["pruning", "sparsity"],
  Distillation: ["knowledge distillation", "teacher-student", "teacher student"],
  "Contrastive Learning": ["contrastive learning", "contrastive loss"],
  "Reinforcement Learning": ["reinforcement learning", "policy gradient", "q-learning", "ppo"],
  "Federated Optimization": ["fedavg", "federated optimization", "federated learning"],
  "Self-Supervised Learning": ["self-supervised", "self supervised"],
  "Retrieval-Augmented Generation": ["retrieval-augmented", "retrieval augmented", "rag"],
  "Mixture of Experts": ["mixture of experts", "moe"],
  "Diffusion Models": ["diffusion model", "diffusion-based"]
};

const DATASETS = ["ImageNet", "CIFAR-10", "CIFAR-100", "COCO", "Cityscapes", "ADE20K", "Pascal VOC", "KITTI", "nuScenes", "Waymo", "SQuAD", "GLUE", "SuperGLUE", "MMLU", "GSM8K", "HumanEval", "MBPP", "WikiText", "C4", "LibriSpeech", "MovieLens", "Amazon Reviews"];
const MODELS = ["ResNet", "ViT", "Swin Transformer", "SegFormer", "BERT", "RoBERTa", "T5", "LLaMA", "Llama", "Mistral", "GPT", "CLIP", "DINO", "YOLO", "Mask R-CNN", "DETR", "Whisper"];
const METRICS = ["accuracy", "precision", "recall", "f1", "f1-score", "auc", "roc-auc", "miou", "iou", "dice", "bleu", "rouge", "meteor", "perplexity", "ppl", "map", "mrr", "ndcg", "hit@", "latency", "throughput", "flops", "parameters"];

function occurrences(text: string, term: string) {
  const hay = text.toLowerCase();
  const needle = term.toLowerCase();
  let count = 0;
  let pos = 0;
  while ((pos = hay.indexOf(needle, pos)) !== -1) {
    count += 1;
    pos += needle.length;
  }
  return count;
}

function scoreDictionary(text: string, dict: Record<string, string[]>) {
  return Object.entries(dict)
    .map(([label, terms]) => ({ label, score: terms.reduce((sum, t) => sum + Math.min(occurrences(text, t), 12), 0) }))
    .filter((x) => x.score > 0)
    .sort((a, b) => b.score - a.score);
}

function extractContributionSentences(text: string) {
  const sentences = text.split(/(?<=[.!?。！？])\s+/).map((s) => s.trim()).filter((s) => s.length >= 35 && s.length <= 420);
  const patterns = [
    /\bwe (?:propose|present|introduce|develop|design|make the following contributions)/i,
    /\bour (?:method|approach|framework|model|contributions?)/i,
    /(?:本文|本研究|我们)(?:提出|设计|构建|开发|实现|贡献)/
  ];
  return sentences.filter((s) => patterns.some((p) => p.test(s))).slice(0, 5);
}

function extractResearchQuestions(text: string) {
  const sentences = text.split(/(?<=[?？.!。])\s+/).map((s) => s.trim()).filter((s) => s.length >= 30 && s.length <= 360);
  const explicit = sentences.filter((s) => /research question|we investigate|we study whether|we ask|研究问题|本文研究|我们研究|旨在解决/i.test(s));
  return explicit.slice(0, 3);
}

function summarize(text: string) {
  const abstractMatch = text.match(/(?:abstract|摘要)\s*[:：]?\s*([\s\S]{120,1800}?)(?=\n\s*(?:keywords?|关键词|1\.?\s*introduction|引言)\b)/i);
  if (abstractMatch) return normalizeText(abstractMatch[1]).slice(0, 750);
  const paragraphs = text.split(/\n{2,}/).map((x) => normalizeText(x)).filter((x) => x.length > 120 && x.length < 1500);
  if (paragraphs.length) return paragraphs[0].slice(0, 750);
  return normalizeText(text).slice(0, 750) || "当前材料没有可提取的文本内容；研究画像只基于文件类型与可读取的结构信息生成。";
}

export function buildResearchProfile(texts: string[], materials: MaterialRecord[]): ResearchProfile {
  const text = normalizeText(texts.filter(Boolean).join("\n\n"));
  const areaScores = {} as Record<CcfAreaCode, number>;
  (Object.keys(AREA_TERMS) as CcfAreaCode[]).forEach((code) => {
    areaScores[code] = AREA_TERMS[code].reduce((sum, term) => sum + Math.min(occurrences(text, term), 20), 0);
  });
  const rankedAreas = (Object.entries(areaScores) as [CcfAreaCode, number][]).sort((a, b) => b[1] - a[1]);
  const primaryArea: CcfAreaCode | null = rankedAreas[0]?.[1] > 0 ? rankedAreas[0][0] : null;
  const secondaryAreas = rankedAreas.filter(([, score]) => score > 0).slice(1, 3).map(([code]) => code);

  const topics = scoreDictionary(text, TOPIC_TERMS).slice(0, 8).map((x) => x.label);
  const methods = scoreDictionary(text, METHOD_TERMS).slice(0, 8).map((x) => x.label);
  const lower = text.toLowerCase();
  const datasets = DATASETS.filter((name) => lower.includes(name.toLowerCase())).slice(0, 12);
  const models = MODELS.filter((name) => lower.includes(name.toLowerCase())).slice(0, 12);
  const metrics = METRICS.filter((name) => lower.includes(name.toLowerCase())).map((x) => x.toUpperCase()).slice(0, 12);
  const contributions = extractContributionSentences(text);
  const researchQuestions = extractResearchQuestions(text);

  const hasManuscript = materials.some((m) => m.kind === "manuscript" && m.analysis.status === "ready");
  const hasSource = materials.some((m) => m.kind === "source" && m.analysis.status === "ready");
  const hasData = materials.some((m) => m.kind === "data" && m.analysis.status === "ready");
  const hasImages = materials.some((m) => m.kind === "image" && m.analysis.status === "ready");
  const ablationMentioned = /ablation|消融/.test(lower);
  const limitationMentioned = /limitations?|局限|不足/.test(lower);
  const references = materials.reduce((sum, m) => sum + (m.analysis.references ?? 0), 0);

  const gaps: string[] = [];
  if (!ablationMentioned && hasManuscript) gaps.push("当前可解析材料中未检测到明确的消融实验描述。这个结论只表示“未检测到”，不代表研究一定没有消融实验。");
  if (datasets.length <= 1 && hasManuscript) gaps.push(`当前文本中识别到的公开数据集数量为 ${datasets.length}；若论文实际包含更多数据集，可在研究画像中手动补充。`);
  if (metrics.length <= 1 && hasData) gaps.push(`当前文本中识别到的评价指标数量为 ${metrics.length}；推荐时会把证据覆盖度视为一个保守信号。`);
  if (!limitationMentioned && hasManuscript) gaps.push("当前材料中未检测到明确的 limitations / 局限性讨论。该项仅作为稿件成熟度信号，不用于否定研究质量。");
  if (text.length < 3000 && hasManuscript) gaps.push("可解析正文较少，当前研究画像置信信息有限；建议补充更完整的正文或研究说明。 ");

  let stage: ResearchProfile["stage"] = "idea";
  if (hasManuscript && hasData && references >= 15 && text.length > 12_000 && (ablationMentioned || datasets.length >= 2)) stage = "submission_ready";
  else if (hasManuscript) stage = "manuscript";
  else if (hasSource || hasData) stage = "experimental";
  else if (text.length > 1500) stage = "early";

  return {
    generatedAt: new Date().toISOString(),
    sourceMode: "local_baseline",
    summary: summarize(text),
    primaryArea,
    areaScores,
    secondaryAreas,
    topics,
    methods,
    datasets,
    models,
    metrics,
    contributions,
    researchQuestions,
    gaps,
    stage,
    evidence: {
      materialCount: materials.length,
      parsedTextChars: text.length,
      hasManuscript,
      hasSource,
      hasData,
      hasImages,
      ablationMentioned,
      limitationMentioned,
      datasetCount: datasets.length,
      metricCount: metrics.length
    }
  };
}
