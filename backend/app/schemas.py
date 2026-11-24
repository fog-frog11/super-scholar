from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProjectCreate(BaseModel):
    id: str | None = Field(default=None, min_length=3, max_length=96, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=240)
    brief: str = Field(default="", max_length=50_000)
    preferences: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Project name cannot be blank")
        return value


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=240)
    brief: str | None = Field(default=None, max_length=50_000)
    status: str | None = None
    archived: bool | None = None
    profile: dict[str, Any] | None = None
    clear_profile: bool = False
    preferences: dict[str, Any] | None = None
    recommendation_run: dict[str, Any] | None = None
    clear_recommendation_run: bool = False
    comparison_venue_ids: list[str] | None = None
    selected_venue_id: str | None = None
    clear_selected_venue: bool = False

    @field_validator("name")
    @classmethod
    def validate_optional_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Project name cannot be blank")
        return value


class ProjectSnapshot(BaseModel):
    id: str = Field(min_length=3, max_length=96, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=240)
    brief: str = ""
    status: str = "draft"
    archived: bool = False
    profile: dict[str, Any] | None = None
    preferences: dict[str, Any] = Field(default_factory=dict)
    recommendationRun: dict[str, Any] | None = None
    comparisonVenueIds: list[str] = Field(default_factory=list)
    selectedVenueId: str | None = None
    createdAt: datetime | None = None
    updatedAt: datetime | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Project name cannot be blank")
        return value


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    brief: str
    status: str
    archived: bool
    profile: dict[str, Any] | None = None
    preferences: dict[str, Any]
    recommendationRun: dict[str, Any] | None = None
    comparisonVenueIds: list[str]
    selectedVenueId: str | None = None
    materialIds: list[str] = Field(default_factory=list)
    createdAt: datetime
    updatedAt: datetime


class MaterialAnalysisUpdate(BaseModel):
    analysis: dict[str, Any]
    extracted_text: str | None = None


class MaterialOut(BaseModel):
    id: str
    projectId: str
    name: str
    mimeType: str
    extension: str
    size: int
    kind: str
    sha256: str
    analysis: dict[str, Any]
    createdAt: datetime
    updatedAt: datetime
    downloadUrl: str
    textAvailable: bool


class CatalogMeta(BaseModel):
    kind: Literal["journal", "conference"]
    source: str
    sourceLabel: str
    sourceTier: Literal["official", "verified_mirror", "aggregator", "cache"]
    fetchedAt: datetime
    stale: bool
    checksum: str
    lastRefreshError: str | None = None


class CatalogResponse(BaseModel):
    count: int
    items: list[dict[str, Any]]
    meta: CatalogMeta


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    environment: str
    database: Literal["ok"]
    storage: Literal["ok"]


class ResearchAnalysisStart(BaseModel):
    consent_external_processing: bool = False


class ResearchAnalysisCapabilities(BaseModel):
    aiConfigured: bool
    provider: str | None = None
    model: str | None = None
    ocrAvailable: bool
    ocrLanguages: str
    directPdfLimit: int
    visualAssetLimit: int
    maxTextChars: int
    chunkTextChars: int
    maxProviderCalls: int
    visualsPerChunk: int


class ResearchAnalysisRunOut(BaseModel):
    id: str
    projectId: str
    mode: str
    status: Literal["queued", "running", "ready", "error"]
    progress: int
    stage: str
    message: str
    model: str | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    createdAt: datetime
    updatedAt: datetime

class IntegrationSettingsUpdate(BaseModel):
    provider: Literal["openai", "deepseek", "custom"]
    base_url: str = Field(default="", max_length=1000)
    model: str = Field(default="", max_length=160)
    protocol: Literal["responses", "chat_completions"] = "responses"
    output_mode: Literal["json_schema", "json_object"] = "json_schema"
    reasoning_effort: Literal["low", "medium", "high", "xhigh", "max"] = "medium"
    reasoning_enabled: bool = True
    streaming_enabled: bool = True
    transport_profile: Literal["auto", "standard", "edge_safe"] = "auto"
    api_key: str | None = Field(default=None, max_length=1000)
    supports_vision: bool = False
    supports_files: bool = False
    send_direct_pdf: bool = False
    max_text_chars: int = Field(default=220000, ge=10000, le=1000000)
    max_visual_assets: int = Field(default=8, ge=0, le=32)
    max_pdf_files: int = Field(default=2, ge=0, le=8)
    max_output_tokens: int = Field(default=12000, ge=1000, le=64000)
    chunk_text_chars: int = Field(default=10000, ge=1200, le=50000)
    chunk_output_tokens: int = Field(default=1800, ge=800, le=8000)
    synthesis_max_chars: int = Field(default=24000, ge=8000, le=100000)
    max_provider_calls: int = Field(default=8, ge=2, le=20)
    visuals_per_chunk: int = Field(default=1, ge=0, le=4)
    request_timeout_seconds: int = Field(default=180, ge=30, le=600)
    tesseract_cmd: str = Field(default="", max_length=2000)
    ocr_languages: str = Field(default="eng", max_length=120)
    ocr_min_native_text_chars: int = Field(default=80, ge=0, le=5000)


class AIProviderProfileOut(BaseModel):
    provider: Literal["openai", "deepseek", "custom"]
    baseUrl: str
    model: str
    protocol: Literal["responses", "chat_completions"]
    outputMode: Literal["json_schema", "json_object"]
    reasoningEffort: str
    reasoningEnabled: bool
    streamingEnabled: bool
    transportProfile: Literal["auto", "standard", "edge_safe"]
    apiKeyConfigured: bool
    apiKeyHint: str | None = None
    supportsVision: bool
    supportsFiles: bool
    sendDirectPdf: bool
    source: Literal["ui", "environment", "default"]
    lastAiTest: dict[str, Any] | None = None


class IntegrationSettingsOut(BaseModel):
    provider: Literal["openai", "deepseek", "custom"]
    baseUrl: str
    model: str
    protocol: Literal["responses", "chat_completions"]
    outputMode: Literal["json_schema", "json_object"]
    reasoningEffort: str
    reasoningEnabled: bool
    streamingEnabled: bool
    transportProfile: Literal["auto", "standard", "edge_safe"]
    apiKeyConfigured: bool
    apiKeyHint: str | None = None
    supportsVision: bool
    supportsFiles: bool
    sendDirectPdf: bool
    maxTextChars: int
    maxVisualAssets: int
    maxPdfFiles: int
    maxOutputTokens: int
    chunkTextChars: int
    chunkOutputTokens: int
    synthesisMaxChars: int
    maxProviderCalls: int
    visualsPerChunk: int
    requestTimeoutSeconds: int
    tesseractCmd: str
    ocrLanguages: str
    ocrMinNativeTextChars: int
    source: Literal["ui", "environment"]
    lastAiTest: dict[str, Any] | None = None
    providerProfiles: dict[str, AIProviderProfileOut] = Field(default_factory=dict)


class ScholarlyDataSettingsUpdate(BaseModel):
    openalex_enabled: bool = True
    openalex_api_key: str | None = Field(default=None, max_length=1000)
    openalex_max_results: int = Field(default=50, ge=10, le=50)
    crossref_enabled: bool = True
    crossref_email: str = Field(default="", max_length=320)
    crossref_api_key: str | None = Field(default=None, max_length=2000)
    semantic_scholar_enabled: bool = True
    semantic_scholar_api_key: str | None = Field(default=None, max_length=2000)
    dblp_enabled: bool = True
    clarivate_enabled: bool = False
    clarivate_api_key: str | None = Field(default=None, max_length=2000)
    clarivate_journal_limit: int = Field(default=36, ge=6, le=80)
    request_timeout_seconds: int = Field(default=20, ge=5, le=120)


class ScholarlyDataSettingsOut(BaseModel):
    openalexEnabled: bool
    openalexApiKeyConfigured: bool
    openalexApiKeyHint: str | None = None
    openalexMaxResults: int
    crossrefEnabled: bool
    crossrefEmail: str
    crossrefApiKeyConfigured: bool
    crossrefApiKeyHint: str | None = None
    semanticScholarEnabled: bool
    semanticScholarApiKeyConfigured: bool
    semanticScholarApiKeyHint: str | None = None
    dblpEnabled: bool
    clarivateEnabled: bool
    clarivateApiKeyConfigured: bool
    clarivateApiKeyHint: str | None = None
    clarivateJournalLimit: int
    requestTimeoutSeconds: int
    source: Literal["ui", "environment"]
    lastTest: dict[str, Any] | None = None
