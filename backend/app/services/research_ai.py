from __future__ import annotations

import base64
import io
import json
import re
import time
from collections import Counter
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable, Literal

from PIL import Image
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..config import Settings
from ..models import Material, Project
from .integration_settings import RuntimeIntegration
from .research_documents import EvidenceItem, VisualArtifact
from .research_provider import ProviderCallError, generate_structured_json, make_client, sdk_available

CCF_CODES = ["DS", "NW", "SC", "SE", "DB", "CT", "CG", "AI", "HI", "MX"]
FactCategory = Literal[
    "research_problem", "core_idea", "topic", "method", "dataset", "model", "metric",
    "contribution", "research_question", "claimed_novelty", "gap", "stage_signal", "visual_observation",
]


class GroundedText(BaseModel):
    model_config = ConfigDict(extra="ignore")
    text: str = ""
    evidence_ids: list[str] = Field(default_factory=list)


class GroundedItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    text: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"] = "medium"


class ExtractedFact(BaseModel):
    model_config = ConfigDict(extra="ignore")
    category: FactCategory
    text: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"] = "medium"


class TextChunkOutput(BaseModel):
    """Compact text-first extraction. Intentionally much smaller than the final profile schema."""

    model_config = ConfigDict(extra="ignore")
    summary: GroundedText | None = None
    area_candidates: list[Literal["DS", "NW", "SC", "SE", "DB", "CT", "CG", "AI", "HI", "MX"]] = Field(default_factory=list)
    facts: list[ExtractedFact] = Field(default_factory=list)


class VisualChunkOutput(BaseModel):
    """One-image-at-a-time visual extraction."""

    model_config = ConfigDict(extra="ignore")
    facts: list[ExtractedFact] = Field(default_factory=list)


class AIResearchOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    summary: GroundedText
    research_problem: GroundedText
    core_idea: GroundedText
    primary_area: Literal["DS", "NW", "SC", "SE", "DB", "CT", "CG", "AI", "HI", "MX"] | None
    secondary_areas: list[Literal["DS", "NW", "SC", "SE", "DB", "CT", "CG", "AI", "HI", "MX"]] = Field(default_factory=list)
    area_rationale: GroundedText
    topics: list[str] = Field(default_factory=list)
    methods: list[str] = Field(default_factory=list)
    datasets: list[str] = Field(default_factory=list)
    models: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    contributions: list[GroundedItem] = Field(default_factory=list)
    research_questions: list[GroundedItem] = Field(default_factory=list)
    claimed_novelty: list[GroundedItem] = Field(default_factory=list)
    gaps: list[GroundedItem] = Field(default_factory=list)
    visual_observations: list[GroundedItem] = Field(default_factory=list)
    stage: Literal["idea", "early", "experimental", "manuscript", "submission_ready"]
    stage_rationale: GroundedText


class GroundingError(RuntimeError):
    pass


class ResearchPipelineError(RuntimeError):
    def __init__(self, message: str, diagnostics: dict[str, Any]):
        self.diagnostics = diagnostics
        super().__init__(message)


@dataclass(frozen=True)
class _EvidenceSegment:
    evidence_id: str
    material_id: str
    kind: str
    label: str
    text: str
    metadata: dict[str, Any]


@dataclass
class _ResearchChunk:
    id: str
    segments: list[_EvidenceSegment]
    text_chars: int
    material_ids: set[str]
    pages: set[tuple[str, int]]


@dataclass(frozen=True)
class _EffectivePlan:
    mode: Literal["standard", "edge_safe"]
    chunk_text_chars: int
    chunk_output_tokens: int
    synthesis_max_chars: int
    synthesis_output_tokens: int
    synthesis_reasoning: bool
    visual_limit: int
    image_max_edge: int
    image_quality: int


PRIORITIES = {
    "project_brief": 0,
    "repository_summary": 1,
    "document_text": 2,
    "ocr_text": 2,
    "table": 2,
    "source_code": 4,
}

SALIENCE_TERMS = [
    "abstract", "introduction", "contribution", "we propose", "we present", "our method", "method", "approach",
    "framework", "architecture", "algorithm", "objective", "loss", "experiment", "dataset", "baseline", "result",
    "ablation", "analysis", "conclusion", "limitation", "future work", "提出", "贡献", "方法", "框架", "模型",
    "算法", "目标函数", "损失", "实验", "数据集", "基线", "结果", "消融", "结论", "局限",
]

TEXT_CHUNK_INSTRUCTIONS = """You are the text-evidence extraction stage of Super Scholar for a computer-science research project.
Read only the supplied text evidence. Do not use outside literature. Extract concise research facts and keep every fact grounded in one or more supplied evidence IDs.
Do not discuss images in this stage. Do not claim global literature novelty; claimed_novelty means only what the uploaded project itself claims.
CCF codes: DS=architecture/parallel/distributed/storage, NW=networks, SC=security, SE=software engineering/systems/programming languages, DB=database/data mining/information retrieval, CT=theory, CG=graphics/multimedia, AI=artificial intelligence, HI=HCI/ubiquitous, MX=cross/interdisciplinary/emerging.
Return at most 12 facts. Keep each fact short and research-level; do not enumerate every dataset column, configuration field, log line, or implementation detail.
Use ONLY the listed fact categories and confidence values in the contract. If a detail does not fit an allowed category, omit it rather than inventing a new category.
Prefer research_problem, core_idea, topic, method, dataset, model, metric, contribution, research_question, claimed_novelty, gap, and stage_signal facts that can help later venue recommendation.
Return compact JSON only."""

TEXT_CHUNK_CONTRACT = r'''{
  "summary":{"text":"one concise grounded summary","evidence_ids":["ev_id"]},
  "area_candidates":["AI"],
  "facts":[
    {"category":"research_problem|core_idea|topic|method|dataset|model|metric|contribution|research_question|claimed_novelty|gap|stage_signal","text":"concise fact","evidence_ids":["ev_id"],"confidence":"high|medium|low"}
  ]
}'''

VISUAL_INSTRUCTIONS = """You are the visual-evidence extraction stage of Super Scholar.
Inspect exactly ONE supplied research image/page rendering. Report only observations visible in that image. Do not infer external literature novelty.
Every returned fact must cite the supplied visual artifact ID. Return compact JSON only."""

VISUAL_CONTRACT = r'''{
  "facts":[
    {"category":"visual_observation|method|metric|contribution|gap","text":"concise observation visible in the image","evidence_ids":["artifact_id"],"confidence":"high|medium|low"}
  ]
}'''

SYNTHESIS_INSTRUCTIONS = """You are the final research-understanding stage of Super Scholar.
You receive compact text facts and optional one-image visual observations extracted from the user's project. Synthesize one coherent research profile using ONLY these extracted facts.
All final evidence_ids must be ORIGINAL evidence/artifact IDs already present in the supplied facts. Never invent IDs. Do not use external literature to claim novelty.
claimed_novelty means only what the uploaded project claims or directly supports. Gaps describe current material coverage, not reviewer verdicts.
CCF codes: DS=architecture/parallel/distributed/storage, NW=networks, SC=security, SE=software engineering/systems/programming languages, DB=database/data mining/information retrieval, CT=theory, CG=graphics/multimedia, AI=artificial intelligence, HI=HCI/ubiquitous, MX=cross/interdisciplinary/emerging.
Prefer concise Chinese output when the project is mainly Chinese; retain standard English technical terms where useful. Return JSON only."""

SYNTHESIS_CONTRACT = r'''{
  "summary":{"text":"...","evidence_ids":["ev_id"]},
  "research_problem":{"text":"...","evidence_ids":["ev_id"]},
  "core_idea":{"text":"...","evidence_ids":["ev_id"]},
  "primary_area":"AI|null",
  "secondary_areas":[],
  "area_rationale":{"text":"...","evidence_ids":["ev_id"]},
  "topics":[],"methods":[],"datasets":[],"models":[],"metrics":[],
  "contributions":[{"text":"...","evidence_ids":["ev_id"],"confidence":"high|medium|low"}],
  "research_questions":[],"claimed_novelty":[],"gaps":[],"visual_observations":[],
  "stage":"idea|early|experimental|manuscript|submission_ready",
  "stage_rationale":{"text":"...","evidence_ids":["ev_id"]}
}'''


def _valid_refs(refs: list[str], valid_ids: set[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for ref in refs:
        if ref in valid_ids and ref not in seen:
            result.append(ref)
            seen.add(ref)
    return result


def _grounded_text(item: GroundedText, valid_ids: set[str], label: str) -> dict[str, Any]:
    refs = _valid_refs(item.evidence_ids, valid_ids)
    text = item.text.strip()
    if not text or not refs:
        raise GroundingError(f"{label} was returned without valid current-project evidence")
    return {"text": text, "evidenceIds": refs}


def _grounded_list(items: list[GroundedItem], valid_ids: set[str]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        text = item.text.strip()
        refs = _valid_refs(item.evidence_ids, valid_ids)
        key = text.lower()
        if not text or not refs or key in seen:
            continue
        seen.add(key)
        output.append({"text": text, "evidenceIds": refs, "confidence": item.confidence})
    return output


def validate_and_build_profile(
    raw: AIResearchOutput,
    valid_ids: set[str],
    *,
    material_count: int,
    parsed_text_chars: int,
    has_manuscript: bool,
    has_source: bool,
    has_data: bool,
    has_images: bool,
    parser_metadata: dict[str, Any],
    generated_at: str,
    source_mode: str = "ai_deep",
) -> dict[str, Any]:
    summary = _grounded_text(raw.summary, valid_ids, "summary")
    research_problem = _grounded_text(raw.research_problem, valid_ids, "research_problem")
    core_idea = _grounded_text(raw.core_idea, valid_ids, "core_idea")
    area_rationale = _grounded_text(raw.area_rationale, valid_ids, "area_rationale")
    stage_rationale = _grounded_text(raw.stage_rationale, valid_ids, "stage_rationale")

    contributions = _grounded_list(raw.contributions, valid_ids)
    questions = _grounded_list(raw.research_questions, valid_ids)
    novelty = _grounded_list(raw.claimed_novelty, valid_ids)
    gaps = _grounded_list(raw.gaps, valid_ids)
    visual = _grounded_list(raw.visual_observations, valid_ids)
    secondary = [code for code in raw.secondary_areas if code != raw.primary_area][:3]

    all_area_scores = {code: 0 for code in CCF_CODES}
    return {
        "generatedAt": generated_at,
        "sourceMode": source_mode,
        "summary": summary["text"],
        "summaryGrounding": summary,
        "researchProblem": research_problem,
        "coreIdea": core_idea,
        "primaryArea": raw.primary_area,
        "areaScores": all_area_scores,
        "secondaryAreas": secondary,
        "areaRationale": area_rationale,
        "topics": list(dict.fromkeys(x.strip() for x in raw.topics if x.strip()))[:16],
        "methods": list(dict.fromkeys(x.strip() for x in raw.methods if x.strip()))[:16],
        "datasets": list(dict.fromkeys(x.strip() for x in raw.datasets if x.strip()))[:20],
        "models": list(dict.fromkeys(x.strip() for x in raw.models if x.strip()))[:20],
        "metrics": list(dict.fromkeys(x.strip() for x in raw.metrics if x.strip()))[:20],
        "contributions": [item["text"] for item in contributions],
        "researchQuestions": [item["text"] for item in questions],
        "gaps": [item["text"] for item in gaps],
        "claimedNovelty": novelty,
        "visualObservations": visual,
        "groundedContributions": contributions,
        "groundedResearchQuestions": questions,
        "groundedGaps": gaps,
        "stage": raw.stage,
        "stageRationale": stage_rationale,
        "evidence": {
            "materialCount": material_count,
            "parsedTextChars": parsed_text_chars,
            "hasManuscript": has_manuscript,
            "hasSource": has_source,
            "hasData": has_data,
            "hasImages": has_images,
            "ablationMentioned": any("ablation" in item["text"].lower() or "消融" in item["text"] for item in contributions + gaps),
            "limitationMentioned": bool(gaps),
            "datasetCount": len(raw.datasets),
            "metricCount": len(raw.metrics),
            "ocrPages": sum(int(meta.get("ocrPages", 0) or 0) for meta in parser_metadata.values()),
            "tables": sum(int(meta.get("tables", 0) or 0) for meta in parser_metadata.values()),
            "visualAssetCount": sum(
                int(meta.get("figureCrops", 0) or 0)
                + int(meta.get("tableCrops", 0) or 0)
                + int(meta.get("pageRenders", 0) or 0)
                + int(meta.get("embeddedImages", 0) or 0)
                for meta in parser_metadata.values()
            ),
        },
    }


def openai_sdk_available() -> bool:
    return sdk_available()


def _parse_json_object(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        value = json.loads(text)
        if isinstance(value, dict):
            return value
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        value = json.loads(text[start : end + 1])
        if isinstance(value, dict):
            return value
    raise ValueError("provider returned text that could not be parsed as one JSON object")


def _ordered_evidence(evidence: list[EvidenceItem]) -> list[EvidenceItem]:
    return sorted(
        [item for item in evidence if item.text.strip()],
        key=lambda x: (PRIORITIES.get(x.kind, 9), x.material_id, int(x.metadata.get("page", 0) or 0), x.id),
    )


def _paragraph_units(text: str) -> list[tuple[int, str]]:
    parts = [p.strip() for p in re.split(r"\n\s*\n|(?<=[.!?。！？])\s+(?=[A-Z0-9\u4e00-\u9fff])", text) if p.strip()]
    return [(idx, p) for idx, p in enumerate(parts)]


def _salient_excerpt(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    units = _paragraph_units(text)
    if not units:
        return text[:limit]
    scored: list[tuple[float, int, str]] = []
    total = max(1, len(units) - 1)
    for idx, part in units:
        low = part.lower()
        keyword_score = sum(1 for term in SALIENCE_TERMS if term in low)
        edge_bonus = 2.2 if idx == 0 else (1.4 if idx == len(units) - 1 else 0.0)
        position_bonus = 0.6 if idx / total < 0.15 or idx / total > 0.85 else 0.0
        scored.append((keyword_score * 2.0 + edge_bonus + position_bonus, idx, part))
    selected: list[tuple[int, str]] = []
    used = 0
    for _, idx, part in sorted(scored, key=lambda x: (-x[0], x[1])):
        if used >= limit:
            break
        take = min(len(part), max(120, limit - used))
        if take <= 0:
            break
        selected.append((idx, part[:take]))
        used += take + 2
    selected.sort(key=lambda x: x[0])
    result = "\n\n".join(part for _, part in selected)
    return result[:limit]


def _effective_plan(runtime: RuntimeIntegration, *, has_visuals: bool) -> _EffectivePlan:
    mode: Literal["standard", "edge_safe"]
    if runtime.transport_profile == "edge_safe":
        mode = "edge_safe"
    elif runtime.transport_profile == "standard":
        mode = "standard"
    else:
        mode = "edge_safe" if runtime.provider == "custom" else "standard"

    if mode == "edge_safe":
        return _EffectivePlan(
            mode=mode,
            chunk_text_chars=min(runtime.chunk_text_chars, 2_800),
            # 700 tokens proved too tight for a realistic compact chunk response through
            # JSON-object compatible gateways: the provider can complete successfully yet
            # still truncate or deform the last fact. Keep the request small for EdgeOne/
            # reverse-proxy safety, but leave enough room for <=12 concise facts.
            chunk_output_tokens=min(runtime.chunk_output_tokens, 1_100),
            synthesis_max_chars=min(runtime.synthesis_max_chars, 7_000),
            synthesis_output_tokens=min(runtime.max_output_tokens, 2_000),
            synthesis_reasoning=False,
            visual_limit=min(runtime.max_visual_assets, 1 if has_visuals else 0),
            image_max_edge=640,
            image_quality=60,
        )
    if runtime.provider == "deepseek":
        return _EffectivePlan(
            mode=mode,
            chunk_text_chars=min(runtime.chunk_text_chars, 6_000),
            chunk_output_tokens=min(runtime.chunk_output_tokens, 900),
            synthesis_max_chars=min(runtime.synthesis_max_chars, 10_000),
            synthesis_output_tokens=min(runtime.max_output_tokens, 2_000),
            synthesis_reasoning=runtime.reasoning_enabled,
            visual_limit=0,
            image_max_edge=768,
            image_quality=68,
        )
    return _EffectivePlan(
        mode=mode,
        chunk_text_chars=runtime.chunk_text_chars,
        chunk_output_tokens=runtime.chunk_output_tokens,
        synthesis_max_chars=runtime.synthesis_max_chars,
        synthesis_output_tokens=min(runtime.max_output_tokens, 5_000),
        synthesis_reasoning=runtime.reasoning_enabled,
        visual_limit=min(runtime.max_visual_assets, 2 if has_visuals else 0),
        image_max_edge=1024,
        image_quality=74,
    )


def _segments(evidence: list[EvidenceItem], *, total_limit: int, segment_limit: int) -> tuple[list[_EvidenceSegment], int, int]:
    ordered = _ordered_evidence(evidence)
    total_available = sum(len(item.text.strip()) for item in ordered)
    if not ordered or total_limit <= 0:
        return [], 0, total_available
    per_item = max(240, min(segment_limit, total_limit // max(1, len(ordered))))
    remaining = total_limit
    out: list[_EvidenceSegment] = []
    selected_chars = 0
    # First pass gives every evidence item/page a chance to contribute.
    for item in ordered:
        if remaining <= 0:
            break
        budget = min(per_item, remaining)
        if item.kind == "project_brief":
            budget = min(segment_limit, remaining, max(budget, min(len(item.text), 900)))
        excerpt = _salient_excerpt(item.text, budget).strip()
        if excerpt:
            out.append(_EvidenceSegment(item.id, item.material_id, item.kind, item.label, excerpt, dict(item.metadata)))
            selected_chars += len(excerpt)
            remaining -= len(excerpt)
    # Second pass spends leftover budget on bounded continuation windows. This matters
    # for a single long PDF page/code file: the first salience pass should not collapse
    # the whole project into only one provider chunk when the call budget allows more.
    if remaining > 300:
        for item in ordered:
            if remaining <= 0:
                break
            source = item.text.strip()
            cursor = min(segment_limit, len(source))
            continuation_index = 1
            while cursor < len(source) and remaining > 300:
                window = source[cursor : cursor + segment_limit].strip()
                cursor += segment_limit
                if not window:
                    continue
                extra_budget = min(len(window), segment_limit, remaining)
                extra = window[:extra_budget].strip()
                if not extra:
                    continue
                out.append(_EvidenceSegment(item.id, item.material_id, item.kind, item.label + f" · continuation {continuation_index}", extra, dict(item.metadata)))
                continuation_index += 1
                selected_chars += len(extra)
                remaining -= len(extra)
    return out, selected_chars, total_available


def _build_text_chunks(evidence: list[EvidenceItem], runtime: RuntimeIntegration, effective: _EffectivePlan, *, max_chunks: int) -> tuple[list[_ResearchChunk], dict[str, Any]]:
    target = max(1_200, effective.chunk_text_chars)
    segment_limit = max(800, target - 500)
    total_limit = min(runtime.max_text_chars, target * max_chunks)
    segments, _selected, total_available = _segments(evidence, total_limit=total_limit, segment_limit=segment_limit)

    chunks: list[_ResearchChunk] = []
    current: list[_EvidenceSegment] = []
    current_chars = 0

    def flush() -> None:
        nonlocal current, current_chars
        if not current:
            return
        pages: set[tuple[str, int]] = set()
        material_ids = {seg.material_id for seg in current}
        for seg in current:
            page = int(seg.metadata.get("page", 0) or 0)
            if page > 0:
                pages.add((seg.material_id, page))
        chunks.append(_ResearchChunk(f"text_{len(chunks)+1}", current, current_chars, material_ids, pages))
        current = []
        current_chars = 0

    for segment in segments:
        if current and current_chars + len(segment.text) > target:
            flush()
            if len(chunks) >= max_chunks:
                break
        if len(chunks) >= max_chunks:
            break
        current.append(segment)
        current_chars += len(segment.text)
    if len(chunks) < max_chunks:
        flush()

    selected_chars = sum(chunk.text_chars for chunk in chunks)
    character_sampling_ratio = 1.0 if total_available <= 0 else min(1.0, selected_chars / total_available)

    # ``selected_chars / available_chars`` is a compression / sampling ratio, not a
    # document-coverage metric.  The first pass in ``_segments`` deliberately gives
    # every evidence item (and therefore every parsed PDF page, when page evidence is
    # available) a chance to contribute before continuation windows are added.  Keep
    # these concepts separate so the UI never tells a user that only e.g. 19% of a
    # paper was "covered" when in fact every page supplied grounded evidence and 19%
    # merely describes how much raw text was sent through the bounded provider calls.
    ordered_evidence = [item for item in _ordered_evidence(evidence) if item.text.strip()]
    available_evidence_ids = {item.id for item in ordered_evidence}
    selected_evidence_ids = {seg.evidence_id for chunk in chunks for seg in chunk.segments}

    def page_key_from_item(item: EvidenceItem) -> tuple[str, int] | None:
        try:
            page = int(item.metadata.get("page", 0) or 0)
        except Exception:
            page = 0
        return (item.material_id, page) if page > 0 else None

    available_pages = {key for item in ordered_evidence if (key := page_key_from_item(item)) is not None}
    selected_pages = {page for chunk in chunks for page in chunk.pages}
    evidence_coverage_ratio = (
        1.0 if not available_evidence_ids else min(1.0, len(selected_evidence_ids) / len(available_evidence_ids))
    )
    page_coverage_ratio = 1.0 if not available_pages else min(1.0, len(selected_pages) / len(available_pages))
    return chunks, {
        "strategy": "text_first_vision_separate",
        "transportProfile": effective.mode,
        "sdkRetries": 0,
        "maxProviderCalls": runtime.max_provider_calls,
        "effectiveChunkTextChars": target,
        "effectiveChunkOutputTokens": effective.chunk_output_tokens,
        "plannedChunkCalls": len(chunks),
        "selectedTextChars": selected_chars,
        "availableTextChars": total_available,
        # Backward compatibility for persisted runs.  New clients should use
        # ``characterSamplingRatio`` and the explicit evidence/page coverage fields.
        "textCoverageRatio": round(character_sampling_ratio, 4),
        "characterSamplingRatio": round(character_sampling_ratio, 4),
        "selectedEvidenceItems": len(selected_evidence_ids),
        "availableEvidenceItems": len(available_evidence_ids),
        "evidenceCoverageRatio": round(evidence_coverage_ratio, 4),
        "selectedPages": len(selected_pages),
        "availablePages": len(available_pages),
        "pageCoverageRatio": round(page_coverage_ratio, 4),
        "directPdfUsed": False,
        "failFastText": True,
        "visualsAreSeparateCalls": True,
        "streamingEnabled": runtime.streaming_enabled,
    }


def _chunk_text(chunk: _ResearchChunk, *, index: int, total: int, project: Project) -> str:
    blocks = [f"[{seg.evidence_id}] kind={seg.kind} label={seg.label}\n{seg.text}" for seg in chunk.segments]
    return f"Project name: {project.name}\nText evidence chunk: {index}/{total}\n\n" + "\n\n".join(blocks)


def _image_data_url(path: Path, *, max_edge: int, quality: int) -> str | None:
    try:
        with Image.open(path) as image:
            image = image.convert("RGB")
            image.thumbnail((max_edge, max_edge))
            out = io.BytesIO()
            image.save(out, format="JPEG", quality=quality, optimize=True)
        return "data:image/jpeg;base64," + base64.b64encode(out.getvalue()).decode("ascii")
    except Exception:
        return None


def _fallback_text_chunk(fallback_id: str, fallback_text: str) -> dict[str, Any]:
    """Build a grounded local fallback without inventing AI facts.

    This is intentionally conservative. A provider call may have completed and been billed
    even when a compatibility gateway returns malformed/truncated JSON. We preserve the
    evidence coverage for later deterministic synthesis instead of discarding the whole run
    or paying for an automatic repair request.
    """
    text = fallback_text.strip()[:600] or "Uploaded research evidence"
    return {
        "summary": {"text": text, "evidenceIds": [fallback_id]},
        "areaCandidates": [],
        "facts": [],
    }


def _parse_text_chunk(
    raw_text: str,
    valid_ids: set[str],
    fallback_id: str,
    fallback_text: str,
) -> tuple[dict[str, Any], list[str]]:
    """Parse one paid text extraction call with item-level salvage.

    JSON-object mode promises JSON shape much less strongly than JSON-schema Structured
    Outputs. A single non-enum category/confidence must therefore not invalidate 10 other
    grounded facts from the same successful provider call. The outer JSON still has to be a
    parseable object; within it, each field/fact is validated independently and unsupported
    items are dropped with diagnostics.
    """
    payload = _parse_json_object(raw_text)
    warnings: list[str] = []

    summary = GroundedText(text=fallback_text[:260], evidence_ids=[fallback_id])
    raw_summary = payload.get("summary")
    if raw_summary is not None:
        try:
            candidate = GroundedText.model_validate(raw_summary)
            candidate_refs = _valid_refs(candidate.evidence_ids, valid_ids)
            if candidate.text.strip() and candidate_refs:
                summary = GroundedText(text=candidate.text, evidence_ids=candidate_refs)
            else:
                warnings.append("summary lacked usable current-project evidence and was replaced locally")
        except ValidationError as exc:
            warnings.append(f"summary did not match the contract and was replaced locally: {exc.errors()[0].get('msg', 'validation error')}")
    else:
        warnings.append("summary was missing and was replaced locally")

    summary_refs = _valid_refs(summary.evidence_ids, valid_ids) or [fallback_id]

    raw_areas = payload.get("area_candidates", [])
    areas: list[str] = []
    if isinstance(raw_areas, list):
        for value in raw_areas:
            if isinstance(value, str) and value in CCF_CODES and value not in areas:
                areas.append(value)
            elif value not in (None, ""):
                warnings.append(f"dropped unsupported CCF area candidate: {value!r}")
    elif raw_areas is not None:
        warnings.append("area_candidates was not an array and was ignored")

    facts: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    raw_facts = payload.get("facts", [])
    if not isinstance(raw_facts, list):
        if raw_facts is not None:
            warnings.append("facts was not an array and was ignored")
        raw_facts = []
    for idx, item in enumerate(raw_facts):
        try:
            fact = ExtractedFact.model_validate(item)
        except ValidationError as exc:
            detail = exc.errors()[0] if exc.errors() else {}
            loc = ".".join(str(x) for x in detail.get("loc", [])) or "fact"
            warnings.append(f"dropped facts[{idx}] ({loc}): {detail.get('msg', 'validation error')}")
            continue
        refs = _valid_refs(fact.evidence_ids, valid_ids)
        text = fact.text.strip()
        key = (fact.category, text.lower())
        if not text:
            warnings.append(f"dropped facts[{idx}] because text was empty")
            continue
        if not refs:
            warnings.append(f"dropped facts[{idx}] because no evidence_id belongs to this chunk")
            continue
        if key in seen:
            continue
        seen.add(key)
        facts.append({"category": fact.category, "text": text[:420], "evidenceIds": refs, "confidence": fact.confidence})

    # Keep the packet deliberately compact so the final synthesis request stays stable.
    return ({
        "summary": {"text": summary.text.strip()[:600], "evidenceIds": summary_refs},
        "areaCandidates": areas[:4],
        "facts": facts[:12],
    }, warnings[:20])


def _parse_visual(raw_text: str, artifact_id: str) -> dict[str, Any]:
    payload = _parse_json_object(raw_text)
    parsed = VisualChunkOutput.model_validate(payload)
    facts: list[dict[str, Any]] = []
    for fact in parsed.facts:
        text = fact.text.strip()
        refs = _valid_refs(fact.evidence_ids, {artifact_id})
        if not text or not refs:
            continue
        facts.append({"category": fact.category, "text": text[:500], "evidenceIds": refs, "confidence": fact.confidence})
    return {"artifactId": artifact_id, "facts": facts[:24]}


def _compact_packet(text_results: list[dict[str, Any]], visual_results: list[dict[str, Any]], max_chars: int) -> tuple[str, set[str]]:
    packet = {"textChunks": [], "visuals": []}
    ids: set[str] = set()
    for item in text_results:
        result = item["result"]
        compact = {
            "summary": result.get("summary"),
            "areaCandidates": result.get("areaCandidates", []),
            "facts": result.get("facts", [])[:24],
        }
        encoded = json.dumps(compact, ensure_ascii=False, separators=(",", ":"))
        current = json.dumps(packet, ensure_ascii=False, separators=(",", ":"))
        if len(current) + len(encoded) > max_chars and packet["textChunks"]:
            break
        packet["textChunks"].append(compact)
        ids.update(item.get("evidenceIds", []))
    for item in visual_results:
        encoded = json.dumps(item, ensure_ascii=False, separators=(",", ":"))
        current = json.dumps(packet, ensure_ascii=False, separators=(",", ":"))
        if len(current) + len(encoded) > max_chars:
            break
        packet["visuals"].append(item)
        ids.add(str(item.get("artifactId")))
    return json.dumps(packet, ensure_ascii=False, separators=(",", ":")), ids


def _facts_by_category(text_results: list[dict[str, Any]], visual_results: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for item in text_results:
        for fact in item["result"].get("facts", []):
            groups.setdefault(fact["category"], []).append(fact)
    for item in visual_results:
        for fact in item.get("facts", []):
            groups.setdefault(fact["category"], []).append(fact)
    return groups


def _first_grounded(groups: dict[str, list[dict[str, Any]]], category: str, fallback: dict[str, Any]) -> GroundedText:
    items = groups.get(category, [])
    if items:
        return GroundedText(text=items[0]["text"], evidence_ids=list(items[0]["evidenceIds"]))
    return GroundedText(text=str(fallback.get("text", "")), evidence_ids=list(fallback.get("evidenceIds", [])))


def _to_grounded_items(groups: dict[str, list[dict[str, Any]]], category: str, limit: int = 12) -> list[GroundedItem]:
    return [GroundedItem(text=x["text"], evidence_ids=x["evidenceIds"], confidence=x.get("confidence", "medium")) for x in groups.get(category, [])[:limit]]


def _deterministic_final(text_results: list[dict[str, Any]], visual_results: list[dict[str, Any]], *, has_manuscript: bool, has_data: bool) -> AIResearchOutput:
    if text_results:
        fallback = text_results[0]["result"]["summary"]
    elif visual_results and visual_results[0].get("facts"):
        f = visual_results[0]["facts"][0]
        fallback = {"text": f["text"], "evidenceIds": f["evidenceIds"]}
    else:
        raise GroundingError("no grounded facts were available for deterministic synthesis")
    groups = _facts_by_category(text_results, visual_results)
    areas: list[str] = []
    for item in text_results:
        areas.extend(item["result"].get("areaCandidates", []))
    primary = Counter(areas).most_common(1)[0][0] if areas else None
    secondary = [a for a, _ in Counter(areas).most_common(4) if a != primary][:3]
    summary = GroundedText(text=fallback["text"], evidence_ids=fallback["evidenceIds"])
    stage = "manuscript" if has_manuscript else ("experimental" if has_data else "early")
    stage_items = groups.get("stage_signal", [])
    if stage_items:
        low = " ".join(x["text"].lower() for x in stage_items)
        if "submission" in low or "camera-ready" in low or "投稿" in low:
            stage = "submission_ready"
        elif "experiment" in low or "实验" in low or "result" in low:
            stage = "experimental"
    return AIResearchOutput(
        summary=summary,
        research_problem=_first_grounded(groups, "research_problem", fallback),
        core_idea=_first_grounded(groups, "core_idea", fallback),
        primary_area=primary if primary in CCF_CODES else None,
        secondary_areas=[a for a in secondary if a in CCF_CODES],
        area_rationale=summary,
        topics=[x["text"] for x in groups.get("topic", [])[:16]],
        methods=[x["text"] for x in groups.get("method", [])[:16]],
        datasets=[x["text"] for x in groups.get("dataset", [])[:20]],
        models=[x["text"] for x in groups.get("model", [])[:20]],
        metrics=[x["text"] for x in groups.get("metric", [])[:20]],
        contributions=_to_grounded_items(groups, "contribution"),
        research_questions=_to_grounded_items(groups, "research_question"),
        claimed_novelty=_to_grounded_items(groups, "claimed_novelty"),
        gaps=_to_grounded_items(groups, "gap"),
        visual_observations=_to_grounded_items(groups, "visual_observation"),
        stage=stage,
        stage_rationale=GroundedText(text=(stage_items[0]["text"] if stage_items else fallback["text"]), evidence_ids=(stage_items[0]["evidenceIds"] if stage_items else fallback["evidenceIds"])),
    )


def _extraction_evidence_ids(text_results: list[dict[str, Any]], visual_results: list[dict[str, Any]]) -> set[str]:
    """All evidence IDs retained by successful paid extraction calls.

    This set can be larger than the IDs placed into the bounded final-synthesis packet.
    Deterministic fallback is allowed to use all successfully extracted evidence; the AI
    final synthesis is only allowed to use IDs it actually saw in its compact prompt.
    """
    ids: set[str] = set()
    for item in text_results:
        ids.update(str(x) for x in item.get("evidenceIds", []) if x)
        result = item.get("result", {})
        ids.update(str(x) for x in result.get("summary", {}).get("evidenceIds", []) if x)
        for fact in result.get("facts", []):
            ids.update(str(x) for x in fact.get("evidenceIds", []) if x)
    for item in visual_results:
        artifact_id = item.get("artifactId")
        if artifact_id:
            ids.add(str(artifact_id))
        for fact in item.get("facts", []):
            ids.update(str(x) for x in fact.get("evidenceIds", []) if x)
    return ids


def _validated_grounded_candidate(value: Any, valid_ids: set[str]) -> GroundedText | None:
    try:
        candidate = GroundedText.model_validate(value)
    except ValidationError:
        return None
    refs = _valid_refs(candidate.evidence_ids, valid_ids)
    text = candidate.text.strip()
    if not text or not refs:
        return None
    return GroundedText(text=text, evidence_ids=refs)


def _salvage_grounded_items(value: Any, valid_ids: set[str]) -> tuple[list[GroundedItem] | None, int]:
    if not isinstance(value, list):
        return None, 0
    output: list[GroundedItem] = []
    invalid = 0
    seen: set[str] = set()
    for raw in value:
        try:
            item = GroundedItem.model_validate(raw)
        except ValidationError:
            invalid += 1
            continue
        refs = _valid_refs(item.evidence_ids, valid_ids)
        text = item.text.strip()
        key = text.lower()
        if not text or not refs:
            invalid += 1
            continue
        if key in seen:
            continue
        seen.add(key)
        output.append(GroundedItem(text=text, evidence_ids=refs, confidence=item.confidence))
    return output, invalid


def _salvage_final_payload(
    payload: dict[str, Any],
    fallback: AIResearchOutput,
    *,
    synthesis_valid_ids: set[str],
) -> tuple[AIResearchOutput, list[str]]:
    """Field-level salvage for the final synthesis response.

    The final provider response is valuable even when one field (most commonly
    stage_rationale) cites a misspelled / omitted evidence ID. V3.7 validated the whole
    object atomically, which turned one bad field into a full local synthesis fallback.
    This function keeps every valid AI field and replaces only invalid fields from the
    deterministic, already-grounded extraction result. No extra provider request is sent.
    """
    normalized: list[str] = []

    def grounded(name: str, fb: GroundedText) -> GroundedText:
        candidate = _validated_grounded_candidate(payload.get(name), synthesis_valid_ids)
        if candidate is not None:
            return candidate
        normalized.append(name)
        return fb

    def string_list(name: str, fb: list[str], limit: int) -> list[str]:
        raw = payload.get(name)
        if raw is None:
            normalized.append(name)
            return fb
        if not isinstance(raw, list):
            normalized.append(name)
            return fb
        values = [x.strip() for x in raw if isinstance(x, str) and x.strip()]
        return list(dict.fromkeys(values))[:limit]

    def grounded_list(name: str, fb: list[GroundedItem], limit: int = 12) -> list[GroundedItem]:
        raw = payload.get(name)
        parsed, invalid = _salvage_grounded_items(raw, synthesis_valid_ids)
        if parsed is None:
            normalized.append(name)
            return fb[:limit]
        if invalid:
            normalized.append(f"{name}[{invalid} invalid item(s)]")
        # An explicit empty array is meaningful. If the model returned only invalid items,
        # use the extraction-backed fallback rather than silently erasing known evidence.
        if raw and not parsed:
            return fb[:limit]
        return parsed[:limit]

    raw_primary = payload.get("primary_area")
    if "primary_area" not in payload:
        primary = fallback.primary_area
        normalized.append("primary_area")
    elif raw_primary is None:
        primary = None
    elif isinstance(raw_primary, str) and raw_primary in CCF_CODES:
        primary = raw_primary
    else:
        primary = fallback.primary_area
        normalized.append("primary_area")

    raw_secondary = payload.get("secondary_areas")
    if isinstance(raw_secondary, list):
        secondary = [x for x in raw_secondary if isinstance(x, str) and x in CCF_CODES and x != primary][:3]
    else:
        secondary = [x for x in fallback.secondary_areas if x != primary][:3]
        normalized.append("secondary_areas")

    raw_stage = payload.get("stage")
    if raw_stage in {"idea", "early", "experimental", "manuscript", "submission_ready"}:
        stage = raw_stage
    else:
        stage = fallback.stage
        normalized.append("stage")

    output = AIResearchOutput(
        summary=grounded("summary", fallback.summary),
        research_problem=grounded("research_problem", fallback.research_problem),
        core_idea=grounded("core_idea", fallback.core_idea),
        primary_area=primary,
        secondary_areas=secondary,
        area_rationale=grounded("area_rationale", fallback.area_rationale),
        topics=string_list("topics", fallback.topics, 16),
        methods=string_list("methods", fallback.methods, 16),
        datasets=string_list("datasets", fallback.datasets, 20),
        models=string_list("models", fallback.models, 20),
        metrics=string_list("metrics", fallback.metrics, 20),
        contributions=grounded_list("contributions", fallback.contributions),
        research_questions=grounded_list("research_questions", fallback.research_questions),
        claimed_novelty=grounded_list("claimed_novelty", fallback.claimed_novelty),
        gaps=grounded_list("gaps", fallback.gaps),
        visual_observations=grounded_list("visual_observations", fallback.visual_observations),
        stage=stage,
        stage_rationale=grounded("stage_rationale", fallback.stage_rationale),
    )
    return output, normalized


def _safe_error_details(exc: Exception, *, raw_output: str | None = None) -> dict[str, Any]:
    if isinstance(exc, ProviderCallError):
        return {
            "errorKind": "provider_transport",
            "statusCode": exc.status_code,
            "message": (exc.provider_message or str(exc))[:500],
            "providerPhase": exc.phase,
            "requestId": exc.request_id,
            "responseBody": (exc.response_body or "")[:1000] or None,
            "responseHeaders": dict(exc.response_headers or {}),
        }
    raw = raw_output or ""
    return {
        "errorKind": "local_output_validation",
        "statusCode": None,
        "message": str(exc)[:1500],
        "requestId": None,
        "responseBody": raw[:1600] or None,
        "responseHead": raw[:1000] or None,
        "responseTail": raw[-700:] or None,
        "rawOutputChars": len(raw),
        "responseHeaders": {},
    }


def _call_trace(
    *, index: int, phase: str, input_chars: int, visual_assets: int, approximate_payload_bytes: int,
    runtime: RuntimeIntegration, max_output_tokens: int, started: float, status: str,
    error: Exception | None = None, raw_output: str | None = None,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "callIndex": index,
        "phase": phase,
        "status": status,
        "inputChars": input_chars,
        "visualAssets": visual_assets,
        "approxPayloadBytes": approximate_payload_bytes,
        "maxOutputTokens": max_output_tokens,
        "reasoningEnabled": runtime.reasoning_enabled,
        "streamingEnabled": runtime.streaming_enabled,
        "outputMode": runtime.output_mode,
        "elapsedMs": round((time.monotonic() - started) * 1000),
    }
    if error is not None:
        item.update(_safe_error_details(error, raw_output=raw_output))
    elif raw_output is not None:
        item["rawOutputChars"] = len(raw_output)
    return item


def _provider_failure_message(trace: dict[str, Any], *, call_count: int, plan: dict[str, Any]) -> str:
    phase = trace.get("phase", "AI request")
    if trace.get("errorKind") == "local_output_validation":
        return (
            f"AI request for {phase} completed, but the returned JSON could not be validated locally. "
            f"Super Scholar stopped without sending another provider request. Real provider calls used: {call_count}/{plan.get('maxProviderCalls')}. "
            "Open the provider diagnostics to inspect the returned output excerpt."
        )
    status = trace.get("statusCode")
    code = f"HTTP {status}" if status else "provider/transport error"
    request_id = trace.get("requestId")
    suffix = f" request_id={request_id}" if request_id else ""
    base = (
        f"AI provider failed during {phase}: {code}. Super Scholar stopped immediately; "
        f"no automatic provider retry was sent. Real provider calls used: {call_count}/{plan.get('maxProviderCalls')}.{suffix}"
    )
    if status == 554:
        headers = trace.get("responseHeaders") or {}
        server = " ".join(str(v) for k, v in headers.items() if str(k).lower() == "server")
        if "tencentedgeone" in server.lower():
            base += (
                " Tencent EdgeOne returned an origin-response timeout. This V3.6 request is already text-first, small-output and contains no image in the text stage. "
                "If Edge-safe mode is enabled and this still happens, the remaining failure is in the gateway/origin path rather than PDF parsing."
            )
    return base


def analyze_with_provider(
    project: Project,
    materials: list[Material],
    evidence: list[EvidenceItem],
    artifacts: list[VisualArtifact],
    parser_metadata: dict[str, Any],
    settings: Settings,
    runtime: RuntimeIntegration,
    generated_at: str,
    on_attempt: Callable[[int, int, str], None] | None = None,
) -> dict[str, Any]:
    """Text-first, vision-separate research understanding.

    1. Files are parsed locally.
    2. Text is sent in small text-only calls.
    3. Images, if supported, are sent one at a time after text succeeds.
    4. Only compact extracted facts are sent to final synthesis.
    5. SDK retries remain disabled; a text provider failure is fail-fast.
    """
    if not runtime.ai_configured:
        raise RuntimeError("AI provider is not configured")
    if not sdk_available():
        raise RuntimeError("The OpenAI-compatible Python SDK is not installed")

    available_artifacts = [a for a in artifacts if Path(a.path).is_file()] if runtime.supports_vision else []
    # Prefer logical Figure / Table crops reconstructed from PDF caption geometry. Full-page
    # renders are only a fallback; raw embedded PDF image blocks are last because they are
    # frequently just one component (legend/photo/box) of a composite academic figure.
    visual_priority = {
        "figure_crop": 0,
        "table_crop": 1,
        "uploaded_image": 2,
        "docx_image": 3,
        "page_render": 4,
        "pdf_image": 5,
    }
    available_artifacts.sort(key=lambda a: (visual_priority.get(a.kind, 9), a.page or 10**9, a.id))
    effective = _effective_plan(runtime, has_visuals=bool(available_artifacts))

    reserve_visual = effective.visual_limit if available_artifacts else 0
    text_slots = max(0, runtime.max_provider_calls - 1 - reserve_visual)
    text_chunks, plan = _build_text_chunks(evidence, runtime, effective, max_chunks=max(1, text_slots) if evidence else 0) if evidence else ([], {
        "strategy": "text_first_vision_separate", "transportProfile": effective.mode, "sdkRetries": 0,
        "maxProviderCalls": runtime.max_provider_calls, "selectedTextChars": 0, "availableTextChars": 0,
        "textCoverageRatio": 1.0, "characterSamplingRatio": 1.0,
        "selectedEvidenceItems": 0, "availableEvidenceItems": 0, "evidenceCoverageRatio": 1.0,
        "selectedPages": 0, "availablePages": 0, "pageCoverageRatio": 1.0,
        "directPdfUsed": False, "failFastText": True,
        "visualsAreSeparateCalls": True, "streamingEnabled": runtime.streaming_enabled,
    })

    # Actual visual budget is whatever remains after the text plan and one synthesis call.
    visual_budget = min(effective.visual_limit, max(0, runtime.max_provider_calls - len(text_chunks) - 1))
    selected_artifacts = available_artifacts[:visual_budget]
    if not text_chunks and not selected_artifacts:
        if artifacts and not runtime.supports_vision:
            raise RuntimeError("The project contains visual evidence but this provider has Vision disabled. Enable OCR or use a vision-capable provider.")
        raise RuntimeError("No valid text or visual evidence could be prepared for AI research understanding")

    plan.update({
        "textCallsPlanned": len(text_chunks),
        "visualCallsPlanned": len(selected_artifacts),
        "synthesisCallsPlanned": 1,
        "plannedTotalCalls": len(text_chunks) + len(selected_artifacts) + 1,
        "effectiveChunkOutputTokens": effective.chunk_output_tokens,
        "effectiveSynthesisChars": effective.synthesis_max_chars,
        "effectiveSynthesisOutputTokens": effective.synthesis_output_tokens,
        "synthesisReasoning": effective.synthesis_reasoning,
    })

    client = make_client(runtime)
    call_trace: list[dict[str, Any]] = []
    text_results: list[dict[str, Any]] = []
    visual_results: list[dict[str, Any]] = []
    text_warnings: list[dict[str, Any]] = []
    text_notes: list[dict[str, Any]] = []

    text_runtime = replace(runtime, reasoning_enabled=False, max_output_tokens=effective.chunk_output_tokens, send_direct_pdf=False)

    for chunk_index, chunk in enumerate(text_chunks, start=1):
        call_index = len(call_trace) + 1
        if on_attempt:
            on_attempt(call_index, int(plan["plannedTotalCalls"]), f"text:{chunk_index}/{len(text_chunks)}")
        prompt = _chunk_text(chunk, index=chunk_index, total=len(text_chunks), project=project)
        content = [{"type": "input_text", "text": prompt}]
        valid_ids = {seg.evidence_id for seg in chunk.segments}
        fallback_id = next(iter(valid_ids))
        fallback_text = chunk.segments[0].text if chunk.segments else project.name
        approx_payload = len(prompt) + len(TEXT_CHUNK_CONTRACT) + 800
        started = time.monotonic()
        raw: str | None = None
        try:
            raw = generate_structured_json(
                text_runtime, client,
                instructions=TEXT_CHUNK_INSTRUCTIONS,
                content=content,
                schema=TextChunkOutput.model_json_schema(),
                name="super_scholar_text_chunk",
                phase=f"text research chunk {chunk_index}/{len(text_chunks)}",
                compact_contract=TEXT_CHUNK_CONTRACT,
            )
        except Exception as exc:
            trace = _call_trace(
                index=call_index, phase=f"text research chunk {chunk_index}/{len(text_chunks)}", input_chars=len(prompt),
                visual_assets=0, approximate_payload_bytes=approx_payload, runtime=text_runtime,
                max_output_tokens=text_runtime.max_output_tokens, started=started, status="error", error=exc, raw_output=raw,
            )
            call_trace.append(trace)
            diagnostics = {"pipeline": plan, "failedAt": f"text chunk {chunk_index}/{len(text_chunks)}", "provider": runtime.provider, "model": runtime.model, "protocol": runtime.protocol, "callTrace": call_trace, "textChunksCompleted": len(text_results)}
            raise ResearchPipelineError(_provider_failure_message(trace, call_count=len(call_trace), plan=plan), diagnostics) from exc

        # The network/provider call above succeeded. From here on, contract imperfections are
        # local compatibility issues, not transport failures. Do not throw away a paid result
        # and do not send a repair retry. Salvage valid items or preserve this chunk as a
        # grounded local summary so later chunks and final synthesis can still proceed.
        try:
            result, validation_notes = _parse_text_chunk(raw, valid_ids, fallback_id, fallback_text)
            text_results.append({"chunkId": chunk.id, "evidenceIds": sorted(valid_ids), "result": result})
            trace = _call_trace(
                index=call_index, phase=f"text research chunk {chunk_index}/{len(text_chunks)}", input_chars=len(prompt),
                visual_assets=0, approximate_payload_bytes=approx_payload, runtime=text_runtime,
                max_output_tokens=text_runtime.max_output_tokens, started=started,
                status="warning" if validation_notes else "success", raw_output=raw,
            )
            if validation_notes:
                trace.update({
                    "errorKind": "local_output_salvaged",
                    "message": "; ".join(validation_notes)[:1500],
                    "responseHead": raw[:1000] or None,
                    "responseTail": raw[-700:] or None,
                })
                text_notes.append({
                    "message": f"Text chunk {chunk_index}/{len(text_chunks)} had a few contract-level field issues. Valid grounded facts were preserved and invalid items were ignored locally; no retry was sent.",
                    "trace": trace,
                })
            call_trace.append(trace)
        except Exception as exc:
            result = _fallback_text_chunk(fallback_id, fallback_text)
            text_results.append({"chunkId": chunk.id, "evidenceIds": sorted(valid_ids), "result": result})
            trace = _call_trace(
                index=call_index, phase=f"text research chunk {chunk_index}/{len(text_chunks)}", input_chars=len(prompt),
                visual_assets=0, approximate_payload_bytes=approx_payload, runtime=text_runtime,
                max_output_tokens=text_runtime.max_output_tokens, started=started, status="warning", error=exc, raw_output=raw,
            )
            trace["message"] = (
                "Provider returned output, but the outer JSON could not be parsed locally. "
                "This paid call was preserved as a grounded local-summary fallback; no repair request was sent. "
                + str(exc)
            )[:1500]
            call_trace.append(trace)
            text_warnings.append({
                "message": f"Text chunk {chunk_index}/{len(text_chunks)} returned malformed JSON. Super Scholar kept a grounded local fallback and continued without retrying that provider call.",
                "trace": trace,
            })

    # Vision is explicitly separate: one image == one provider request. A vision failure does not discard
    # already-completed text understanding; it stops the optional vision stage and continues text-only.
    visual_warning: dict[str, Any] | None = None
    if selected_artifacts:
        vision_runtime = replace(runtime, reasoning_enabled=False, max_output_tokens=min(500, effective.chunk_output_tokens), send_direct_pdf=False)
        for visual_index, artifact in enumerate(selected_artifacts, start=1):
            call_index = len(call_trace) + 1
            if on_attempt:
                on_attempt(call_index, int(plan["plannedTotalCalls"]), f"visual:{visual_index}/{len(selected_artifacts)}")
            url = _image_data_url(Path(artifact.path), max_edge=effective.image_max_edge, quality=effective.image_quality)
            if not url:
                visual_warning = {"message": f"Visual artifact {artifact.id} could not be decoded locally; skipped without provider call."}
                continue
            prompt = (
                f"Project: {project.name}\n"
                f"Visual artifact ID: {artifact.id}\n"
                f"Label: {artifact.label}\n"
                f"Page: {artifact.page or 'n/a'}\n"
                f"Region: {artifact.region_label or artifact.kind}\n"
                f"Caption: {artifact.caption or 'not available'}"
            )
            content = [
                {"type": "input_text", "text": prompt},
                {"type": "input_image", "image_url": url, "detail": "low"},
            ]
            visual_bytes = max(0, (len(url) - url.find(",") - 1) * 3 // 4)
            started = time.monotonic()
            raw: str | None = None
            try:
                raw = generate_structured_json(
                    vision_runtime, client,
                    instructions=VISUAL_INSTRUCTIONS,
                    content=content,
                    schema=VisualChunkOutput.model_json_schema(),
                    name="super_scholar_visual_chunk",
                    phase=f"visual research asset {visual_index}/{len(selected_artifacts)}",
                    compact_contract=VISUAL_CONTRACT,
                )
                result = _parse_visual(raw, artifact.id)
                visual_results.append(result)
                call_trace.append(_call_trace(
                    index=call_index, phase=f"visual research asset {visual_index}/{len(selected_artifacts)}", input_chars=len(prompt),
                    visual_assets=1, approximate_payload_bytes=len(prompt) + visual_bytes + len(VISUAL_CONTRACT), runtime=vision_runtime,
                    max_output_tokens=vision_runtime.max_output_tokens, started=started, status="success",
                ))
            except Exception as exc:
                trace = _call_trace(
                    index=call_index, phase=f"visual research asset {visual_index}/{len(selected_artifacts)}", input_chars=len(prompt),
                    visual_assets=1, approximate_payload_bytes=len(prompt) + visual_bytes + len(VISUAL_CONTRACT), runtime=vision_runtime,
                    max_output_tokens=vision_runtime.max_output_tokens, started=started, status="error", error=exc, raw_output=raw,
                )
                call_trace.append(trace)
                visual_warning = {"message": "Visual analysis stopped after its first failed image request; text understanding is preserved.", "trace": trace}
                if not text_results:
                    diagnostics = {"pipeline": plan, "failedAt": f"visual {visual_index}/{len(selected_artifacts)}", "provider": runtime.provider, "model": runtime.model, "protocol": runtime.protocol, "callTrace": call_trace}
                    raise ResearchPipelineError(_provider_failure_message(trace, call_count=len(call_trace), plan=plan), diagnostics) from exc
                break

    extraction_valid_ids = _extraction_evidence_ids(text_results, visual_results)
    packet, synthesis_valid_ids = _compact_packet(text_results, visual_results, effective.synthesis_max_chars)
    if not synthesis_valid_ids:
        raise RuntimeError("AI extraction completed but produced no grounded evidence IDs")

    deterministic_final = _deterministic_final(
        text_results,
        visual_results,
        has_manuscript=any(m.kind == "manuscript" for m in materials),
        has_data=any(m.kind == "data" for m in materials),
    )

    call_index = len(call_trace) + 1
    if call_index > runtime.max_provider_calls:
        profile = validate_and_build_profile(
            deterministic_final, extraction_valid_ids, material_count=len(materials), parsed_text_chars=int(plan.get("selectedTextChars", 0)),
            has_manuscript=any(m.kind == "manuscript" for m in materials), has_source=any(m.kind == "source" for m in materials),
            has_data=any(m.kind == "data" for m in materials), has_images=bool(visual_results) or any(m.kind == "image" for m in materials),
            parser_metadata=parser_metadata, generated_at=generated_at, source_mode="ai_extracted_partial",
        )
        return {"profile": profile, "model": runtime.model, "provider": runtime.provider, "protocol": runtime.protocol, "evidenceIdsUsed": sorted(extraction_valid_ids), "directPdfCount": 0, "visualAssetCount": len(visual_results), "requestPlan": plan, "callTrace": call_trace, "providerCallsUsed": len(call_trace), "textChunkResults": text_results, "visualResults": visual_results, "analysisNotes": text_notes, "analysisWarnings": text_warnings + [{"message": "Final synthesis was skipped because the hard provider-call budget was exhausted; the profile was assembled deterministically from successful AI extractions."}] + ([visual_warning] if visual_warning else [])}

    if on_attempt:
        on_attempt(call_index, int(plan["plannedTotalCalls"]), "synthesis")
    synthesis_runtime = replace(
        runtime,
        reasoning_enabled=effective.synthesis_reasoning,
        max_output_tokens=effective.synthesis_output_tokens,
        send_direct_pdf=False,
    )
    synthesis_prompt = f"Project name: {project.name}\n\nExtracted grounded research facts:\n{packet}"
    started = time.monotonic()
    raw: str | None = None
    synthesis_fallback = False
    synthesis_warning: dict[str, Any] | None = None
    synthesis_notes: list[dict[str, Any]] = []
    synthesis_normalized_fields: list[str] = []
    try:
        raw = generate_structured_json(
            synthesis_runtime, client,
            instructions=SYNTHESIS_INSTRUCTIONS,
            content=[{"type": "input_text", "text": synthesis_prompt}],
            schema=AIResearchOutput.model_json_schema(),
            name="super_scholar_research_profile",
            phase="final research synthesis",
            compact_contract=SYNTHESIS_CONTRACT,
        )
        payload = _parse_json_object(raw)
        parsed, synthesis_normalized_fields = _salvage_final_payload(
            payload,
            deterministic_final,
            synthesis_valid_ids=synthesis_valid_ids,
        )
        profile = validate_and_build_profile(
            # AI-returned fields were already checked against synthesis_valid_ids above;
            # deterministic field-level fallbacks may legally cite any successful extraction
            # ID, including chunks omitted from the bounded final prompt.
            parsed, extraction_valid_ids, material_count=len(materials), parsed_text_chars=int(plan.get("selectedTextChars", 0)),
            has_manuscript=any(m.kind == "manuscript" for m in materials), has_source=any(m.kind == "source" for m in materials),
            has_data=any(m.kind == "data" for m in materials), has_images=bool(visual_results) or any(m.kind == "image" for m in materials),
            parser_metadata=parser_metadata, generated_at=generated_at,
        )
        status = "warning" if synthesis_normalized_fields else "success"
        call_trace.append(_call_trace(
            index=call_index, phase="final research synthesis", input_chars=len(synthesis_prompt), visual_assets=0,
            approximate_payload_bytes=len(synthesis_prompt) + len(SYNTHESIS_CONTRACT), runtime=synthesis_runtime,
            max_output_tokens=synthesis_runtime.max_output_tokens, started=started, status=status,
        ))
        if synthesis_normalized_fields:
            synthesis_notes.append({
                "message": "Final synthesis completed. A few fields had invalid or missing evidence references and were filled locally from already-grounded extraction facts; no retry was sent.",
                "fields": synthesis_normalized_fields,
            })
    except Exception as exc:
        # Important reliability rule: if text/visual extraction already succeeded, a final-synthesis
        # failure does NOT throw away those paid results and does NOT trigger another provider call.
        trace = _call_trace(
            index=call_index, phase="final research synthesis", input_chars=len(synthesis_prompt), visual_assets=0,
            approximate_payload_bytes=len(synthesis_prompt) + len(SYNTHESIS_CONTRACT), runtime=synthesis_runtime,
            max_output_tokens=synthesis_runtime.max_output_tokens, started=started, status="error", error=exc, raw_output=raw,
        )
        call_trace.append(trace)
        synthesis_fallback = True
        synthesis_warning = {"message": "Final AI synthesis failed; no retry was sent. Super Scholar preserved successful extraction calls and assembled the profile deterministically.", "trace": trace}
        profile = validate_and_build_profile(
            deterministic_final, extraction_valid_ids, material_count=len(materials), parsed_text_chars=int(plan.get("selectedTextChars", 0)),
            has_manuscript=any(m.kind == "manuscript" for m in materials), has_source=any(m.kind == "source" for m in materials),
            has_data=any(m.kind == "data" for m in materials), has_images=bool(visual_results) or any(m.kind == "image" for m in materials),
            parser_metadata=parser_metadata, generated_at=generated_at, source_mode="ai_extracted_partial",
        )

    warnings = text_warnings + [x for x in [visual_warning, synthesis_warning] if x]
    notes = text_notes + synthesis_notes
    return {
        "profile": profile,
        "model": runtime.model,
        "provider": runtime.provider,
        "protocol": runtime.protocol,
        "evidenceIdsUsed": sorted(extraction_valid_ids),
        "directPdfCount": 0,
        "visualAssetCount": len(visual_results),
        "requestPlan": plan,
        "callTrace": call_trace,
        "providerCallsUsed": len(call_trace),
        "textChunkResults": text_results,
        "visualResults": visual_results,
        "synthesisFallback": synthesis_fallback,
        "synthesisNormalizedFields": synthesis_normalized_fields,
        "analysisNotes": notes,
        "analysisWarnings": warnings,
    }
