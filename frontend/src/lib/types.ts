export type ProjectStatus =
  | "draft"
  | "materials"
  | "analyzing"
  | "profile_ready"
  | "preferences_ready"
  | "recommending"
  | "recommendations_ready"
  | "venue_selected";

export type MaterialKind = "manuscript" | "source" | "data" | "image" | "other";
export type AnalysisStatus = "queued" | "reading" | "parsing" | "understanding" | "indexing" | "ready" | "error";
export type VenueType = "conference" | "journal";
export type CcfAreaCode = "DS" | "NW" | "SC" | "SE" | "DB" | "CT" | "CG" | "AI" | "HI" | "MX";
export type CcfRank = "A" | "B" | "C" | "N" | "U";
export type CoreRank = "A*" | "A" | "B" | "C" | "N";
export type ConstraintMode = "required" | "preferred";

export interface MaterialAnalysis {
  status: AnalysisStatus;
  progress: number;
  stage: string;
  message: string;
  pages?: number;
  sections?: number;
  references?: number;
  figures?: number;
  sheets?: number;
  rows?: number;
  codeFiles?: number;
  textChars?: number;
  imageWidth?: number;
  imageHeight?: number;
  error?: string;
}

export interface MaterialRecord {
  id: string;
  projectId: string;
  name: string;
  mimeType: string;
  extension: string;
  size: number;
  kind: MaterialKind;
  storageKey: string;
  textStorageKey?: string;
  createdAt: string;
  updatedAt: string;
  analysis: MaterialAnalysis;
  serverSync?: "pending" | "synced" | "error";
  serverSyncError?: string;
}

export interface GroundedClaim {
  text: string;
  evidenceIds: string[];
  confidence?: "high" | "medium" | "low";
}

export interface ResearchProfile {
  generatedAt: string;
  sourceMode?: "local_baseline" | "ai_deep" | "ai_extracted_partial";
  summary: string;
  summaryGrounding?: GroundedClaim;
  researchProblem?: GroundedClaim;
  coreIdea?: GroundedClaim;
  areaRationale?: GroundedClaim;
  primaryArea: CcfAreaCode | null;
  areaScores: Record<CcfAreaCode, number>;
  secondaryAreas: CcfAreaCode[];
  topics: string[];
  methods: string[];
  datasets: string[];
  models: string[];
  metrics: string[];
  contributions: string[];
  researchQuestions: string[];
  gaps: string[];
  groundedContributions?: GroundedClaim[];
  groundedResearchQuestions?: GroundedClaim[];
  groundedGaps?: GroundedClaim[];
  claimedNovelty?: GroundedClaim[];
  visualObservations?: GroundedClaim[];
  stageRationale?: GroundedClaim;
  stage: "idea" | "early" | "experimental" | "manuscript" | "submission_ready";
  evidence: {
    materialCount: number;
    parsedTextChars: number;
    hasManuscript: boolean;
    hasSource: boolean;
    hasData: boolean;
    hasImages: boolean;
    ablationMentioned: boolean;
    limitationMentioned: boolean;
    datasetCount: number;
    metricCount: number;
    ocrPages?: number;
    tables?: number;
    visualAssetCount?: number;
  };
}

export interface PreferenceValue<T> {
  enabled: boolean;
  mode: ConstraintMode;
  value: T;
}

export interface PublicationPreferences {
  targetType: "conference" | "journal" | "both";
  ccfRanks: PreferenceValue<CcfRank[]>;
  coreRanks: PreferenceValue<CoreRank[]>;
  deadlineMonths: PreferenceValue<number>;
  locations: PreferenceValue<string[]>;
  wosIndexes: PreferenceValue<string[]>;
  jcrQuartiles: PreferenceValue<string[]>;
  impactFactor: PreferenceValue<{ min?: number; max?: number }>;
  openAccess: PreferenceValue<"any" | "preferred" | "required">;
  apcCny: PreferenceValue<{ min?: number; max?: number }>;
  reviewDays: PreferenceValue<number>;
  chinaIndexes: PreferenceValue<string[]>;
  topN: number;
}

export interface ConferenceVenue {
  type: "conference";
  id: string;
  seriesId?: string;
  title: string;
  description: string;
  sub: CcfAreaCode;
  ccf: CcfRank;
  ccfVerified?: boolean;
  ccfEntries?: Array<{ sub: CcfAreaCode; ccf: Exclude<CcfRank, "N" | "U">; source?: string; sourceVersion?: string }>;
  core: CoreRank;
  dblp: string;
  year?: number;
  editionId: string;
  link: string;
  deadline?: string;
  abstractDeadline?: string;
  timeline?: Array<{deadline?: string; abstractDeadline?: string; comment?: string}>;
  timezone: string;
  date: string;
  place: string;
  source: string;
  openalexSourceId?: string;
  openalexSourceIds?: string[];
  openalexSourceName?: string;
  openalexAliases?: string[];
  openalexTopics?: string[];
  openalexDynamic?: boolean;
  sourceUpdatedAt?: string;
  ccfSource?: string;
  ccfSourceVersion?: string;
  ccfOfficialLink?: string;
}

export interface JournalVenue {
  type: "journal";
  id: string;
  seriesId?: string;
  shortName: string;
  name: string;
  publisher: string;
  sub: CcfAreaCode;
  ccf: CcfRank;
  ccfVerified?: boolean;
  ccfEntries?: Array<{ sub: CcfAreaCode; ccf: Exclude<CcfRank, "N" | "U">; source?: string; sourceVersion?: string }>;
  link?: string;
  source: string;
  openalexSourceId?: string;
  openalexSourceIds?: string[];
  openalexSourceName?: string;
  openalexAliases?: string[];
  openalexTopics?: string[];
  openalexDynamic?: boolean;
  sourceVersion: string;
  metrics: {
    wosIndex?: string;
    wosIndexes?: string[];
    jcrQuartile?: string;
    jcrQuartiles?: string[];
    impactFactor?: number;
    jci?: number;
    jcrYear?: number;
    clarivateJournalId?: string;
    clarivateSourceUrl?: string;
    oaType?: string;
    oaFullyOpen?: boolean;
    isInDoaj?: boolean;
    isHighOaRate?: boolean;
    oaFlipYear?: number;
    apcCny?: number;
    apcUsd?: number;
    openalexApcUsd?: number;
    apcPrices?: Array<{price:number;currency:string}>;
    apcFx?: {cnyPerUsd:number;date:string;sourceUrl:string;provider:string};
    openalex2yrMeanCitedness?: number;
    openalexSourceUpdatedDate?: string;
    reviewDays?: number;
    [key:string]: unknown;
  };
}

export type Venue = ConferenceVenue | JournalVenue;

export interface ConstraintResult {
  label: string;
  status: "pass" | "fail" | "unknown" | "not_applicable";
  detail: string;
  mode: ConstraintMode;
}

export interface SemanticVenueEvidence {
  workId: string;
  title: string;
  year?: number;
  relevanceScore?: number;
  sourceId?: string;
  sourceName?: string;
  sourceType?: string;
  topics: string[];
  keywords: string[];
  url?: string;
  semanticRank?: number;
}

export interface RecommendationResult {
  venue: Venue;
  researchMatch: number;
  academicScore?: number;
  actionability?: { status: "open" | "closed" | "unknown" | "blocked" | "continuous"; score: number | null; daysUntil?: number | null; reason: string };
  isCurrentlyActionable?: boolean;
  venueConditionedMatch?: number | null;
  venueConditionedEvidenceCount?: number;
  venueConditionedEvidence?: SemanticVenueEvidence[];
  semanticMatch: number | null;
  semanticConfidence: "high" | "medium" | "low" | "unavailable";
  semanticEvidenceCount: number;
  semanticEvidence: SemanticVenueEvidence[];
  secondaryMatch?: number | null;
  secondaryEvidenceCount?: number;
  secondaryEvidence?: Array<{ paperId: string; title: string; year?: number; venue?: string; publicationVenueName?: string; url?: string; searchRank?: number; [key:string]: unknown }>;
  evidenceSources?: number;
  matchedTopics: string[];
  topicMatch?: number | null;
  scopeMatch?: number | null;
  referenceMatch?: number | null;
  referenceCount: number;
  matchedScopes: string[];
  areaMatch: number;
  keywordMatch: number;
  preferenceScore: number;
  finalScore: number;
  eligible: boolean;
  reasons: string[];
  constraints: ConstraintResult[];
  matchedKeywords: string[];
}

export interface RecommendationRun {
  id: string;
  createdAt: string;
  progress: number;
  stage: string;
  status: "idle" | "running" | "ready" | "error";
  message: string;
  candidateCount: number;
  catalogCandidateCount?: number;
  dynamicCandidateCount?: number;
  eligibleCount: number;
  results: RecommendationResult[];
  academicResults?: RecommendationResult[];
  actionableResults?: RecommendationResult[];
  error?: string;
  semanticRetrieval?: {
    provider: "OpenAlex" | string;
    status: "ready" | "unavailable";
    query: string;
    workCount: number;
    works?: SemanticVenueEvidence[];
    sourceCount: number;
    hydratedSourceCount?: number;
    candidateSourceResolutionAttempted?: number;
    candidateSourceResolvedCount?: number;
    candidateSourceTopicsCount?: number;
    venueConditionedAttempted?: number;
    venueConditionedSuccessful?: number;
    dynamicCandidateCount?: number;
    referenceChars?: number;
    sourceEnrichmentError?: string;
    error?: string;
    sourceUrl?: string;
    openalexAuthenticated?: boolean;
    semanticScholarPaperCount?: number;
    semanticScholarError?: string;
    semanticScholarErrorKind?: string;
    semanticScholarStatusCode?: number;
  };
  dataSourceHealth?: RecommendationDataSourceHealth;
  sourceMeta?: Array<Record<string, unknown>>;
  rankingVersion?: string;
}

export interface ResearchProject {
  id: string;
  name: string;
  brief: string;
  createdAt: string;
  updatedAt: string;
  status: ProjectStatus;
  archived: boolean;
  materialIds: string[];
  profile?: ResearchProfile;
  preferences: PublicationPreferences;
  recommendationRun?: RecommendationRun;
  comparisonVenueIds: string[];
  selectedVenueId?: string;
}


export interface ResearchCapabilities {
  aiConfigured: boolean;
  provider?: string;
  model?: string;
  ocrAvailable: boolean;
  ocrLanguages: string;
  directPdfLimit: number;
  visualAssetLimit: number;
  maxTextChars: number;
  chunkTextChars: number;
  maxProviderCalls: number;
  visualsPerChunk: number;
}

export interface ResearchEvidenceItem {
  id: string;
  material_id: string;
  kind: string;
  label: string;
  text: string;
  metadata: Record<string, unknown>;
}

export interface ResearchVisualArtifact {
  id: string;
  material_id: string;
  kind: string;
  label: string;
  mime_type: string;
  url: string;
  width?: number;
  height?: number;
  page?: number;
  source?: string;
  caption?: string;
  bbox?: number[];
  region_label?: string;
}

export interface ResearchAnalysisRun {
  id: string;
  projectId: string;
  mode: string;
  status: "queued" | "running" | "ready" | "error";
  progress: number;
  stage: string;
  message: string;
  model?: string;
  error?: string;
  result?: {
    profile?: ResearchProfile;
    model?: string;
    evidence?: ResearchEvidenceItem[];
    artifacts?: ResearchVisualArtifact[];
    parserMetadata?: Record<string, unknown>;
    requestPlan?: {
      strategy?: string;
      sdkRetries?: number;
      maxProviderCalls?: number;
      chunkTextChars?: number;
      plannedChunkCalls?: number;
      plannedTotalCalls?: number;
      selectedTextChars?: number;
      availableTextChars?: number;
      textCoverageRatio?: number;
      visualsPerChunk?: number;
      synthesisChunkCoverage?: string;
      failFast?: boolean;
    };
    callTrace?: Array<Record<string, unknown>>;
    providerCallsUsed?: number;
    analysisWarnings?: Array<{message?:string;fields?:string[]}>;
    analysisNotes?: Array<{message?:string;fields?:string[]}>;
    synthesisFallback?: boolean;
    synthesisNormalizedFields?: string[];
    diagnostics?: {
      pipeline?: Record<string, unknown>;
      failedAt?: string;
      provider?: string;
      model?: string;
      protocol?: string;
      callTrace?: Array<Record<string, unknown>>;
      chunkResultsCompleted?: number;
    };
  };
  createdAt: string;
  updatedAt: string;
}

export type AIProviderName = "openai" | "deepseek" | "custom";
export type AIProtocol = "responses" | "chat_completions";
export type AITransportProfile = "auto" | "standard" | "edge_safe";
export type AIOutputMode = "json_schema" | "json_object";

export interface AIProviderProfileSettings {
  provider: AIProviderName;
  baseUrl: string;
  model: string;
  protocol: AIProtocol;
  outputMode: AIOutputMode;
  reasoningEffort: "low" | "medium" | "high" | "xhigh" | "max";
  reasoningEnabled: boolean;
  streamingEnabled: boolean;
  transportProfile: AITransportProfile;
  apiKeyConfigured: boolean;
  apiKeyHint?: string;
  supportsVision: boolean;
  supportsFiles: boolean;
  sendDirectPdf: boolean;
  source: "ui" | "environment" | "default";
  lastAiTest?: AIConnectionTest | null;
}

export interface IntegrationSettings {
  provider: AIProviderName;
  baseUrl: string;
  model: string;
  protocol: AIProtocol;
  outputMode: AIOutputMode;
  reasoningEffort: "low" | "medium" | "high" | "xhigh" | "max";
  reasoningEnabled: boolean;
  streamingEnabled: boolean;
  transportProfile: AITransportProfile;
  apiKeyConfigured: boolean;
  apiKeyHint?: string;
  supportsVision: boolean;
  supportsFiles: boolean;
  sendDirectPdf: boolean;
  maxTextChars: number;
  maxVisualAssets: number;
  maxPdfFiles: number;
  maxOutputTokens: number;
  chunkTextChars: number;
  chunkOutputTokens: number;
  synthesisMaxChars: number;
  maxProviderCalls: number;
  visualsPerChunk: number;
  requestTimeoutSeconds: number;
  tesseractCmd: string;
  ocrLanguages: string;
  ocrMinNativeTextChars: number;
  source: "ui" | "environment";
  lastAiTest?: AIConnectionTest | null;
  providerProfiles: Record<AIProviderName, AIProviderProfileSettings>;
}

export interface IntegrationSettingsUpdate {
  provider: AIProviderName;
  base_url: string;
  model: string;
  protocol: AIProtocol;
  output_mode: AIOutputMode;
  reasoning_effort: "low" | "medium" | "high" | "xhigh" | "max";
  reasoning_enabled: boolean;
  streaming_enabled: boolean;
  transport_profile: AITransportProfile;
  api_key?: string | null;
  supports_vision: boolean;
  supports_files: boolean;
  send_direct_pdf: boolean;
  max_text_chars: number;
  max_visual_assets: number;
  max_pdf_files: number;
  max_output_tokens: number;
  chunk_text_chars: number;
  chunk_output_tokens: number;
  synthesis_max_chars: number;
  max_provider_calls: number;
  visuals_per_chunk: number;
  request_timeout_seconds: number;
  tesseract_cmd: string;
  ocr_languages: string;
  ocr_min_native_text_chars: number;
}

export interface AIConnectionTest {
  ok: boolean;
  provider: string;
  baseUrl: string;
  model: string;
  protocol: string;
  testedAt: string;
  checks: Record<string, { ok: boolean | null; required?: boolean; message: string }>;
  optionalFailures?: string[];
  fullyCompatible?: boolean;
}

export interface OCRConnectionTest {
  ok: boolean;
  autoDetect: boolean;
  configuredPath?: string | null;
  languages: string;
  message: string;
  version?: string;
  installedLanguages?: string[];
  configuredLanguagesPresent?: boolean;
}

export type DataSourceStatus = "ready" | "degraded" | "error" | "disabled" | "limited" | "not_applicable";

export interface ScholarlyDataSettings {
  openalexEnabled: boolean;
  openalexApiKeyConfigured: boolean;
  openalexApiKeyHint?: string;
  openalexMaxResults: number;
  crossrefEnabled: boolean;
  crossrefEmail: string;
  crossrefApiKeyConfigured: boolean;
  crossrefApiKeyHint?: string;
  semanticScholarEnabled: boolean;
  semanticScholarApiKeyConfigured: boolean;
  semanticScholarApiKeyHint?: string;
  dblpEnabled: boolean;
  clarivateEnabled: boolean;
  clarivateApiKeyConfigured: boolean;
  clarivateApiKeyHint?: string;
  clarivateJournalLimit: number;
  requestTimeoutSeconds: number;
  source: "ui" | "environment";
  lastTest?: ScholarlyConnectionTest | null;
}

export interface ScholarlyDataSettingsUpdate {
  openalex_enabled: boolean;
  openalex_api_key?: string | null;
  openalex_max_results: number;
  crossref_enabled: boolean;
  crossref_email: string;
  crossref_api_key?: string | null;
  semantic_scholar_enabled: boolean;
  semantic_scholar_api_key?: string | null;
  dblp_enabled: boolean;
  clarivate_enabled: boolean;
  clarivate_api_key?: string | null;
  clarivate_journal_limit: number;
  request_timeout_seconds: number;
}

export interface ScholarlySourceTest {
  status: DataSourceStatus;
  ok: boolean | null;
  message: string;
  authenticated?: boolean;
  mode?: string;
  checks?: Record<string, { ok?: boolean | null; status?: DataSourceStatus; message: string; count?: number; [key:string]: unknown }>;
}

export interface ScholarlyConnectionTest {
  ok: boolean;
  overallStatus: DataSourceStatus;
  testedAt: string;
  message: string;
  sources: {
    openalex: ScholarlySourceTest;
    crossref: ScholarlySourceTest;
    semanticScholar: ScholarlySourceTest;
    dblp: ScholarlySourceTest;
    clarivate: ScholarlySourceTest;
  };
  summary: Array<{ name: string; required: boolean; status: DataSourceStatus; ok: boolean | null; message: string }>;
}

export interface RecommendationDataSourceHealth {
  overallStatus: DataSourceStatus;
  message: string;
  sources: Record<string, {
    status: DataSourceStatus;
    enabled: boolean;
    configured?: boolean | null;
    message: string;
    details?: Record<string, unknown>;
  }>;
}

