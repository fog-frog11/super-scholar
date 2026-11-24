import type { CcfAreaCode, PublicationPreferences } from "./types";

export const CCF_AREAS: Record<CcfAreaCode, { zh: string; en: string }> = {
  DS: { zh: "体系结构 / 并行与分布 / 存储", en: "Architecture · Parallel · Storage" },
  NW: { zh: "计算机网络", en: "Computer Networks" },
  SC: { zh: "网络与信息安全", en: "Security" },
  SE: { zh: "软件工程 / 系统软件 / 程序设计语言", en: "Software · Systems · PL" },
  DB: { zh: "数据库 / 数据挖掘 / 内容检索", en: "Data · Mining · Retrieval" },
  CT: { zh: "计算机科学理论", en: "Theory" },
  CG: { zh: "计算机图形学与多媒体", en: "Graphics · Multimedia" },
  AI: { zh: "人工智能", en: "Artificial Intelligence" },
  HI: { zh: "人机交互与普适计算", en: "HCI · Ubiquitous Computing" },
  MX: { zh: "交叉 / 综合 / 新兴", en: "Interdisciplinary · Emerging" }
};

export const DEFAULT_PREFERENCES: PublicationPreferences = {
  targetType: "both",
  ccfRanks: { enabled: true, mode: "preferred", value: ["A", "B", "C"] },
  coreRanks: { enabled: false, mode: "preferred", value: ["A*", "A", "B"] },
  deadlineMonths: { enabled: true, mode: "preferred", value: 12 },
  locations: { enabled: false, mode: "preferred", value: [] },
  wosIndexes: { enabled: false, mode: "preferred", value: ["SCIE"] },
  jcrQuartiles: { enabled: false, mode: "preferred", value: ["Q1", "Q2"] },
  impactFactor: { enabled: false, mode: "preferred", value: {} },
  openAccess: { enabled: false, mode: "preferred", value: "any" },
  apcCny: { enabled: false, mode: "preferred", value: {} },
  reviewDays: { enabled: false, mode: "preferred", value: 90 },
  chinaIndexes: { enabled: false, mode: "preferred", value: [] },
  topN: 12
};

export const STATUS_LABELS = {
  draft: "草稿",
  materials: "材料已添加",
  analyzing: "解析中",
  profile_ready: "研究画像已就绪",
  preferences_ready: "投稿偏好已设置",
  recommending: "推荐中",
  recommendations_ready: "推荐已就绪",
  venue_selected: "已选择目标"
} as const;
