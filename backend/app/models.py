from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    name: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    brief: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="draft", index=True)
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    profile_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    preferences_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    recommendation_run_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    comparison_venue_ids_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    selected_venue_id: Mapped[str | None] = mapped_column(String(320), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow, index=True)

    materials: Mapped[list["Material"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True
    )


class Material(Base):
    __tablename__ = "materials"

    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(160), nullable=False, default="application/octet-stream")
    extension: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False, default="other")
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    text_storage_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    analysis_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    project: Mapped[Project] = relationship(back_populates="materials")


class VenueCache(Base):
    __tablename__ = "venue_cache"

    kind: Mapped[str] = mapped_column(String(32), primary_key=True)
    payload_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_label: Mapped[str] = mapped_column(String(240), nullable=False)
    source_tier: Mapped[str] = mapped_column(String(40), nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class ResearchAnalysisRun(Base):
    __tablename__ = "research_analysis_runs"

    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    mode: Mapped[str] = mapped_column(String(32), nullable=False, default="ai")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued", index=True)
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stage: Mapped[str] = mapped_column(String(80), nullable=False, default="queued")
    message: Mapped[str] = mapped_column(Text, nullable=False, default="等待分析")
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    result_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow, index=True)


class IntegrationSettings(Base):
    __tablename__ = "integration_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    ai_provider: Mapped[str] = mapped_column(String(32), nullable=False, default="openai")
    ai_base_url: Mapped[str] = mapped_column(Text, nullable=False, default="https://api.openai.com/v1")
    ai_model: Mapped[str] = mapped_column(String(160), nullable=False, default="gpt-5.6")
    ai_protocol: Mapped[str] = mapped_column(String(32), nullable=False, default="responses")
    ai_output_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="json_schema")
    ai_reasoning_effort: Mapped[str] = mapped_column(String(24), nullable=False, default="medium")
    ai_reasoning_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    ai_streaming_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    ai_transport_profile: Mapped[str] = mapped_column(String(32), nullable=False, default="auto")
    ai_api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_supports_vision: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    ai_supports_files: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    ai_send_direct_pdf: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ai_max_text_chars: Mapped[int] = mapped_column(Integer, nullable=False, default=220000)
    ai_max_visual_assets: Mapped[int] = mapped_column(Integer, nullable=False, default=8)
    ai_max_pdf_files: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    ai_max_output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=12000)
    ai_chunk_text_chars: Mapped[int] = mapped_column(Integer, nullable=False, default=10000)
    ai_chunk_output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=1800)
    ai_synthesis_max_chars: Mapped[int] = mapped_column(Integer, nullable=False, default=24000)
    ai_max_provider_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=8)
    ai_visuals_per_chunk: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    ai_request_timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=180)
    tesseract_cmd: Mapped[str] = mapped_column(Text, nullable=False, default="")
    ocr_languages: Mapped[str] = mapped_column(String(120), nullable=False, default="eng")
    ocr_min_native_text_chars: Mapped[int] = mapped_column(Integer, nullable=False, default=80)
    last_ai_test_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class AIProviderProfile(Base):
    __tablename__ = "ai_provider_profiles"

    provider: Mapped[str] = mapped_column(String(32), primary_key=True)
    base_url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    model: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    protocol: Mapped[str] = mapped_column(String(32), nullable=False, default="responses")
    output_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="json_object")
    reasoning_effort: Mapped[str] = mapped_column(String(24), nullable=False, default="medium")
    reasoning_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    streaming_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    transport_profile: Mapped[str] = mapped_column(String(32), nullable=False, default="auto")
    api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    supports_vision: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    supports_files: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    send_direct_pdf: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_test_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class ScholarlyDataSettings(Base):
    __tablename__ = "scholarly_data_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    openalex_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    openalex_api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    openalex_max_results: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    crossref_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    crossref_email: Mapped[str] = mapped_column(String(320), nullable=False, default="")
    crossref_api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    semantic_scholar_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    semantic_scholar_api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    dblp_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    clarivate_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    clarivate_api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    clarivate_journal_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=36)
    request_timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    last_test_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
