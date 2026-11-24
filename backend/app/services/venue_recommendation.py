from __future__ import annotations

import math
import re
import uuid
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Iterable

import httpx
from sqlalchemy.orm import Session

from ..config import Settings
from ..models import Project
from .ccfddl import _deadline_in_utc
from .openalex import (
    SemanticSearchResult,
    SemanticWork,
    SourceProfile,
    SourceResolutionRequest,
    CandidateSourceResolutionResult,
    CandidateSeriesResolutionResult,
    hydrate_sources,
    resolve_candidate_sources,
    resolve_candidate_source_series,
    semantic_search,
    semantic_search_within_sources,
)
from .semantic_scholar import SemanticScholarSearchResult, SemanticScholarPaper, search_papers as s2_search_papers
from .dblp import canonicalize_sources as dblp_canonicalize_sources
from .crossref import CrossrefJournalProfile, resolve_journals as crossref_resolve_journals
from .clarivate_journals import ClarivateBatchResult, ClarivateJournalProfile, resolve_journals as clarivate_resolve_journals
from .ecb_fx import FxRate, latest_cny_per_usd
from .scholarly_settings import ScholarlyRuntime, load_scholarly_runtime
from .venue_catalog import VenueCatalogService
from .venue_intelligence import (
    extract_reference_text,
    infer_ccf_area,
    matched_scope_labels,
    reference_scores,
    research_scope_vector,
    research_topic_vector,
    topic_fit_score,
    venue_scope_vector,
    cosine_score,
)

# Keep CCF display names local to recommendation so the intelligence module remains
# independent of one evaluation system.
AREA_NAMES = {
    "DS": "计算机体系结构/并行与分布计算/存储系统",
    "NW": "计算机网络",
    "SC": "网络与信息安全",
    "SE": "软件工程/系统软件/程序设计语言",
    "DB": "数据库/数据挖掘/内容检索",
    "CT": "计算机科学理论",
    "CG": "计算机图形学与多媒体",
    "AI": "人工智能",
    "HI": "人机交互与普适计算",
    "MX": "交叉/综合/新兴",
}

GENERIC_VENUE_WORDS = {
    "acm", "ieee", "cvf", "international", "conference", "conferences", "journal", "journals",
    "transactions", "proceedings", "symposium", "workshop", "annual", "association", "society",
    "on", "of", "the", "for", "and", "in", "to", "with", "computer", "computing", "science",
    "sciences", "systems", "research", "letters", "magazine", "communications",
}

REGION_TERMS: dict[str, tuple[str, ...]] = {
    "asia": ("china", "japan", "korea", "singapore", "vietnam", "thailand", "malaysia", "indonesia", "india", "taiwan", "hong kong", "macau", "philippines", "tokyo", "kyoto", "osaka", "beijing", "shanghai", "shenzhen", "seoul", "bangkok", "taipei"),
    "europe": ("united kingdom", "uk", "france", "germany", "italy", "spain", "austria", "switzerland", "netherlands", "belgium", "portugal", "greece", "cyprus", "ireland", "sweden", "norway", "denmark", "finland", "poland", "czech", "romania", "london", "paris", "vienna", "milan"),
    "north america": ("usa", "united states", "canada", "mexico", "california", "new york", "washington", "montreal", "toronto", "vancouver"),
    "oceania": ("australia", "new zealand", "melbourne", "sydney", "brisbane", "auckland"),
    "china mainland": ("china", "beijing", "shanghai", "shenzhen", "guangzhou", "hangzhou", "nanjing", "wuhan", "chengdu", "xi'an", "xian"),
}


def _pref(preferences: dict[str, Any], key: str) -> dict[str, Any]:
    value = preferences.get(key)
    return value if isinstance(value, dict) else {}


def _claim_text(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("text") or "").strip()
    return str(value or "").strip()


def _sanitize_research_text(text: str) -> str:
    clean = " ".join(str(text or "").split())
    # Remove publication-status boilerplate that can leak the known answer when a published
    # paper is used as a regression sample. Research content remains intact.
    clean = re.sub(r"(?i)this\s+[A-Z0-9/&.-]{2,20}\s+paper\s+is\s+the\s+open\s+access\s+version[^.]*\.?", " ", clean)
    clean = re.sub(r"(?i)identical\s+to\s+the\s+accepted\s+version[^.]*\.?", " ", clean)
    clean = re.sub(r"(?i)final\s+published\s+version[^.]*proceedings[^.]*\.?", " ", clean)
    return " ".join(clean.split())


def build_semantic_query(profile: dict[str, Any]) -> str:
    """Build a research-only query and deliberately exclude publication-stage metadata."""
    pieces: list[str] = []
    for key in ("researchProblem", "coreIdea"):
        text = _sanitize_research_text(_claim_text(profile.get(key)))
        if text:
            pieces.append(text)
    summary = _sanitize_research_text(_claim_text(profile.get("summary")))
    if summary:
        pieces.append(summary)
    for label, key in (
        ("Topics", "topics"), ("Methods", "methods"), ("Datasets", "datasets"),
        ("Models", "models"), ("Metrics", "metrics"),
    ):
        values = [_sanitize_research_text(str(x)) for x in profile.get(key, []) if _sanitize_research_text(str(x))]
        if values:
            pieces.append(f"{label}: {', '.join(values[:12])}.")
    query = " ".join(" ".join(pieces).split())
    return query[:1950]


def _tokens(text: str, *, remove_generic: bool = False) -> set[str]:
    tokens = {t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) >= 2}
    return tokens - GENERIC_VENUE_WORDS if remove_generic else tokens


def _compact(text: str) -> str:
    return "".join(re.findall(r"[a-z0-9]+", text.lower()))


def _venue_aliases(venue: dict[str, Any]) -> list[str]:
    if venue.get("type") == "conference":
        raw = [str(venue.get("title") or ""), str(venue.get("description") or "")]
    else:
        raw = [str(venue.get("shortName") or ""), str(venue.get("name") or "")]
    for key in ("openalexAliases", "dblpAliases", "crossrefAliases"):
        raw.extend(str(x) for x in venue.get(key) or [])
    return list(dict.fromkeys(" ".join(x.split()).strip() for x in raw if x and x.strip()))


def _is_acronym(value: str) -> bool:
    clean = value.strip()
    return bool(2 <= len(clean) <= 18 and re.fullmatch(r"[A-Z][A-Z0-9*+&/-]{1,17}", clean))


def _distinctive_tokens(text: str) -> set[str]:
    return _tokens(text, remove_generic=True)


def _source_matches_venue(source_name: str | None, venue: dict[str, Any]) -> bool:
    """Conservative source identity matching.

    Exact OpenAlex IDs are handled by the caller. Name matching deliberately avoids broad
    subset rules that can make unrelated conferences share the same direct-paper evidence.
    """
    if not source_name:
        return False
    source_compact = _compact(source_name)
    source_distinct = _distinctive_tokens(source_name)
    source_raw_tokens = _tokens(source_name)
    for alias in _venue_aliases(venue):
        alias_compact = _compact(alias)
        if not alias_compact:
            continue
        if alias_compact == source_compact:
            return True
        if _is_acronym(alias) and alias.lower() in source_raw_tokens:
            return True
        alias_distinct = _distinctive_tokens(alias)
        if not alias_distinct or not source_distinct:
            continue
        inter = len(alias_distinct & source_distinct)
        union = len(alias_distinct | source_distinct)
        # Long-form venue names must share multiple distinctive content words and a high
        # Jaccard ratio. Two generic words such as "computer vision" are not enough unless
        # they constitute most of both names.
        min_shared = 2 if min(len(alias_distinct), len(source_distinct)) <= 3 else 3
        if inter >= min_shared and union and inter / union >= 0.72:
            return True
    return False


def _source_profile_matches_venue(source: SourceProfile, venue: dict[str, Any]) -> bool:
    return any(_source_matches_venue(alias, venue) for alias in source.aliases)


def _profile_tokens(profile: dict[str, Any]) -> set[str]:
    values: list[str] = [str(profile.get("summary") or "")]
    for key in ("topics", "methods", "datasets", "models", "metrics"):
        values.extend(str(x) for x in profile.get(key, []) if x)
    return _tokens(" ".join(values), remove_generic=True)


def _lexical_fit(profile_tokens: set[str], venue: dict[str, Any]) -> tuple[int, list[str]]:
    text = " ".join(_venue_aliases(venue))
    venue_tokens = _tokens(text, remove_generic=True)
    matched = sorted(profile_tokens & venue_tokens)
    denominator = max(4, min(len(profile_tokens), 16))
    score = min(100, round(100 * len(matched) / denominator))
    return score, matched[:8]


def _area_fit(profile: dict[str, Any], venue: dict[str, Any]) -> int:
    sub = str(venue.get("sub") or "")
    primary = profile.get("primaryArea")
    secondary = profile.get("secondaryAreas") or []
    if primary and sub == primary:
        return 100
    if sub in secondary:
        return 65
    return 0


def _semantic_evidence_raw(works: list[SemanticWork], venue: dict[str, Any]) -> tuple[float, list[dict[str, Any]], list[str]]:
    matched: list[tuple[int, SemanticWork]] = []
    venue_source_id = str(venue.get("openalexSourceId") or "")
    for rank, work in enumerate(works, start=1):
        source_names = work.source_names or ((work.source_name,) if work.source_name else ())
        id_match = bool(venue_source_id and work.source_id and venue_source_id == work.source_id)
        if id_match or any(_source_matches_venue(name, venue) for name in source_names):
            matched.append((rank, work))
    if not matched:
        return 0.0, [], []
    weight = sum(1.0 / math.log2(rank + 1.0) for rank, _ in matched)
    topic_counter: Counter[str] = Counter()
    evidence: list[dict[str, Any]] = []
    for rank, work in matched:
        for topic in (*work.topics, *work.keywords):
            if topic:
                topic_counter[topic] += 1
        item = work.as_dict()
        item["semanticRank"] = rank
        evidence.append(item)
    topics = [name for name, _ in topic_counter.most_common(6)]
    return weight, evidence, topics




def _s2_evidence_raw(papers: list[SemanticScholarPaper], venue: dict[str, Any]) -> tuple[float, list[dict[str, Any]]]:
    matched: list[tuple[int, SemanticScholarPaper]] = []
    for rank, paper in enumerate(papers, start=1):
        if any(_source_matches_venue(name, venue) for name in paper.venue_names):
            matched.append((rank, paper))
    if not matched:
        return 0.0, []
    weight = sum(1.0 / math.log2(rank + 1.0) for rank, _ in matched)
    evidence: list[dict[str, Any]] = []
    for rank, paper in matched:
        item = paper.as_dict()
        item["searchRank"] = rank
        evidence.append(item)
    return weight, evidence

def _minimal_source_profiles(works: Iterable[SemanticWork]) -> dict[str, SourceProfile]:
    profiles: dict[str, SourceProfile] = {}
    for work in works:
        if not work.source_id or not work.source_name:
            continue
        if work.source_id in profiles:
            continue
        profiles[work.source_id] = SourceProfile(
            id=work.source_id,
            display_name=work.source_name,
            source_type=work.source_type,
        )
    return profiles


def _dynamic_source_venue(source: SourceProfile, profile: dict[str, Any]) -> dict[str, Any] | None:
    source_type = str(source.source_type or "").lower()
    if source_type not in {"journal", "conference"}:
        return None
    source_scope = venue_scope_vector({
        "type": "conference" if source_type == "conference" else "journal",
        "title": source.abbreviated_title or source.display_name,
        "description": source.display_name,
        "shortName": source.abbreviated_title or source.display_name,
        "name": source.display_name,
        "openalexAliases": list(source.aliases),
    }, source)
    area = infer_ccf_area(source_scope) if source_scope else (str(profile.get("primaryArea") or "MX"))
    link = source.homepage_url or f"https://openalex.org/{source.id}"
    common = {
        "id": f"openalex:{source.id}",
        "seriesId": f"openalex:{source.id}",
        "sub": area,
        "ccf": "U",
        "link": link,
        "source": "OpenAlex Source",
        "openalexSourceId": source.id,
        "openalexSourceName": source.display_name,
        "openalexAliases": list(source.aliases),
        "dblpAliases": list(source.canonical_aliases),
        "openalexTopics": [x.name for x in source.topics[:10]],
        "openalexDynamic": True,
    }
    if source_type == "conference":
        short = source.abbreviated_title or source.display_name
        return {
            **common,
            "type": "conference",
            "title": short,
            "description": source.display_name,
            "core": "N",
            "dblp": "",
            "year": None,
            "editionId": f"openalex:{source.id}",
            "deadline": "TBD",
            "abstractDeadline": None,
            "timeline": [],
            "timezone": "UTC",
            "date": "当前 edition 尚未由 CCFDDL 核验",
            "place": "地点未核验",
        }
    return {
        **common,
        "type": "journal",
        "shortName": source.abbreviated_title or source.display_name,
        "name": source.display_name,
        "publisher": source.host_organization_name or "Publisher 未核验",
        "sourceVersion": "live",
        "issnL": source.issn_l,
        "issn": list(source.issn),
        "metrics": {"oaType": "Fully Open Access" if source.is_oa is True else None, "openalexApcUsd": source.apc_usd},
    }


def merge_openalex_sources(
    venues: list[dict[str, Any]],
    semantic: SemanticSearchResult,
    hydrated: dict[str, SourceProfile],
    profile: dict[str, Any],
    target: str,
    crossref_profiles: dict[str, CrossrefJournalProfile] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, SourceProfile], int]:
    source_profiles = {**_minimal_source_profiles(semantic.works), **hydrated}
    crossref_profiles = crossref_profiles or {}
    merged = [dict(v) for v in venues]

    for source_id, source in source_profiles.items():
        match_index: int | None = None
        for idx, venue in enumerate(merged):
            if _source_profile_matches_venue(source, venue):
                match_index = idx
                break
        crossref = crossref_profiles.get(source_id)
        if match_index is not None:
            venue = dict(merged[match_index])
            existing_source_ids = list(venue.get("openalexSourceIds") or [])
            if source_id not in existing_source_ids:
                existing_source_ids.append(source_id)
            venue["openalexSourceIds"] = existing_source_ids
            venue["openalexSourceId"] = existing_source_ids[0]
            venue["openalexSourceName"] = source.display_name
            venue["openalexAliases"] = list(source.aliases)
            venue["dblpAliases"] = list(source.canonical_aliases)
            venue["openalexTopics"] = [x.name for x in source.topics[:10]]
            venue["openalexDynamic"] = False
            if source.issn_l:
                venue["issnL"] = source.issn_l
            if source.issn:
                venue["issn"] = list(source.issn)
            if crossref is not None:
                venue["crossrefAliases"] = list(crossref.aliases)
                venue["crossrefVerified"] = True
                if venue.get("type") == "journal" and crossref.publisher:
                    venue["publisher"] = crossref.publisher
            if not venue.get("link") and source.homepage_url:
                venue["link"] = source.homepage_url
            merged[match_index] = venue
            continue

        dynamic = _dynamic_source_venue(source, profile)
        if dynamic is None:
            continue
        if target == "conference" and dynamic["type"] != "conference":
            continue
        if target == "journal" and dynamic["type"] != "journal":
            continue
        if crossref is not None and dynamic["type"] == "journal":
            dynamic["crossrefAliases"] = list(crossref.aliases)
            dynamic["crossrefVerified"] = True
            if crossref.publisher:
                dynamic["publisher"] = crossref.publisher
        merged.append(dynamic)

    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    for venue in merged:
        key = str(venue.get("id"))
        if key in seen:
            continue
        seen.add(key)
        output.append(venue)
    dynamic_count = sum(1 for v in output if v.get("openalexDynamic"))
    return output, source_profiles, dynamic_count


def _candidate_resolution_shortlist(
    profile: dict[str, Any],
    preferences: dict[str, Any],
    venues: list[dict[str, Any]],
    *,
    per_type_limit: int,
) -> list[dict[str, Any]]:
    """Choose a bounded, research-relevant catalog slice for OpenAlex identity resolution.

    This happens before Source topics are available, so it uses only local evidence:
    curated CS scope, CCF area, lexical signal, preferences, and hard-constraint status.
    Dynamic OpenAlex candidates and already-resolved catalog entries are skipped.
    """
    research_scopes = research_scope_vector(profile)
    profile_words = _profile_tokens(profile)
    by_type: dict[str, list[tuple[float, dict[str, Any]]]] = {"conference": [], "journal": []}
    for venue in venues:
        venue_type = str(venue.get("type") or "")
        if venue_type not in by_type or venue.get("openalexDynamic"):
            continue
        if venue_type == "journal" and venue.get("openalexSourceId"):
            continue
        if venue_type == "conference" and venue.get("openalexSourceIds"):
            continue
        constraints = evaluate_constraints(venue, preferences)
        if any(c.get("mode") == "required" and c.get("status") in {"fail", "unknown"} for c in constraints):
            continue
        scope = cosine_score(research_scopes, venue_scope_vector(venue)) or 0
        area = _area_fit(profile, venue)
        lexical, _ = _lexical_fit(profile_words, venue)
        preference = _preference_score(venue, constraints)
        # Research scope dominates. Same-area/preference terms only ensure that a venue
        # with sparse naming metadata can still enter the resolution slice.
        score = 0.64 * scope + 0.14 * area + 0.08 * lexical + 0.14 * preference
        by_type[venue_type].append((score, venue))

    output: list[dict[str, Any]] = []
    for venue_type in ("conference", "journal"):
        ranked = sorted(by_type[venue_type], key=lambda pair: (pair[0], str(pair[1].get("ccf") or "N")), reverse=True)
        output.extend(venue for _, venue in ranked[:per_type_limit])
    return output


def _source_resolution_requests(venues: Iterable[dict[str, Any]]) -> list[SourceResolutionRequest]:
    output: list[SourceResolutionRequest] = []
    for venue in venues:
        names = tuple(dict.fromkeys(x for x in _venue_aliases(venue) if x))
        if not names:
            continue
        raw_issn = venue.get("issn") or []
        if isinstance(raw_issn, str):
            raw_issn = [raw_issn]
        issns = tuple(dict.fromkeys(
            str(x).strip() for x in ([venue.get("issnL")] + list(raw_issn)) if x and str(x).strip()
        ))
        output.append(SourceResolutionRequest(
            venue_id=str(venue.get("id") or ""),
            venue_type=str(venue.get("type") or ""),
            names=names,
            issns=issns,
        ))
    return output


def _attach_resolved_candidate_sources(
    venues: list[dict[str, Any]],
    resolution: CandidateSourceResolutionResult,
    source_profiles: dict[str, SourceProfile],
) -> tuple[list[dict[str, Any]], dict[str, SourceProfile]]:
    by_id = {str(v.get("id") or ""): dict(v) for v in venues}
    profiles = dict(source_profiles)
    for venue_id, source in resolution.matches.items():
        venue = by_id.get(venue_id)
        if venue is None:
            continue
        profiles[source.id] = source
        venue["openalexSourceId"] = source.id
        venue["openalexSourceName"] = source.display_name
        venue["openalexAliases"] = list(source.aliases)
        venue["openalexTopics"] = [x.name for x in source.topics[:10]]
        venue["openalexResolutionConfidence"] = round(float(resolution.confidence.get(venue_id, 0.0)), 3)
        venue["openalexDynamic"] = False
        if source.issn_l:
            venue["issnL"] = source.issn_l
        if source.issn:
            venue["issn"] = list(source.issn)
        if not venue.get("link") and source.homepage_url:
            venue["link"] = source.homepage_url
        by_id[venue_id] = venue
    return [by_id[str(v.get("id") or "")] for v in venues], profiles



def _attach_resolved_candidate_series(
    venues: list[dict[str, Any]],
    resolution: CandidateSeriesResolutionResult,
    source_profiles: dict[str, SourceProfile],
) -> tuple[list[dict[str, Any]], dict[str, SourceProfile]]:
    by_id = {str(v.get("id") or ""): dict(v) for v in venues}
    profiles = dict(source_profiles)
    for venue_id, sources in resolution.matches.items():
        venue = by_id.get(venue_id)
        if venue is None or not sources:
            continue
        ids: list[str] = []
        aliases: list[str] = []
        topics: list[str] = []
        for source in sources:
            profiles[source.id] = source
            ids.append(source.id)
            aliases.extend(source.aliases)
            topics.extend(x.name for x in source.topics[:8])
        venue["openalexSourceIds"] = list(dict.fromkeys(ids))
        venue["openalexSourceId"] = ids[0]
        venue["openalexSourceName"] = sources[0].display_name
        venue["openalexAliases"] = list(dict.fromkeys(aliases))
        venue["openalexTopics"] = list(dict.fromkeys(topics))[:16]
        venue["openalexResolutionConfidence"] = round(max(resolution.confidence.get(venue_id, (0.0,))), 3)
        venue["openalexDynamic"] = False
        if venue.get("type") == "journal":
            source = sources[0]
            if source.issn_l:
                venue["issnL"] = source.issn_l
            if source.issn:
                venue["issn"] = list(source.issn)
            if not venue.get("link") and source.homepage_url:
                venue["link"] = source.homepage_url
        by_id[venue_id] = venue
    return [by_id[str(v.get("id") or "")] for v in venues], profiles

def _public_source_metrics(source: SourceProfile, fx: FxRate | None = None) -> dict[str, Any]:
    metrics: dict[str, Any] = {
        "oaFullyOpen": source.is_oa,
        "isInDoaj": source.is_in_doaj,
        "isHighOaRate": source.is_high_oa_rate,
        "oaFlipYear": source.oa_flip_year,
        "openalexApcUsd": source.apc_usd,
        "apcUsd": source.apc_usd,
        "apcPrices": [x.as_dict() for x in source.apc_prices],
        "openalex2yrMeanCitedness": source.two_year_mean_citedness,
        "openalexSourceUpdatedDate": source.updated_date,
    }
    if source.is_oa is True:
        metrics["oaType"] = "Fully Open Access"
    elif source.is_oa is False:
        # OpenAlex can prove the source is not fully OA, but this alone does not
        # distinguish Hybrid from Subscription. Keep that distinction honest.
        metrics["oaType"] = "Not fully OA / mixed"
    if source.apc_usd is not None and fx is not None:
        metrics["apcCny"] = round(float(source.apc_usd) * fx.cny_per_usd)
        metrics["apcFx"] = fx.as_dict()
    metrics["openalexMetadataSource"] = f"https://openalex.org/{source.id}"
    return {k: v for k, v in metrics.items() if v is not None and v != []}


def _apply_public_journal_metrics(
    venues: list[dict[str, Any]],
    sources: dict[str, SourceProfile],
    fx: FxRate | None,
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for raw in venues:
        venue = dict(raw)
        if venue.get("type") != "journal":
            output.append(venue)
            continue
        source_id = str(venue.get("openalexSourceId") or "")
        source = sources.get(source_id)
        metrics = dict(venue.get("metrics") or {})
        if source is not None:
            metrics.update(_public_source_metrics(source, fx))
        venue["metrics"] = metrics
        output.append(venue)
    return output


def _apply_clarivate_metrics(
    venues: list[dict[str, Any]],
    profiles: dict[str, ClarivateJournalProfile],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for raw in venues:
        venue = dict(raw)
        profile = profiles.get(str(venue.get("id") or ""))
        if venue.get("type") != "journal" or profile is None:
            output.append(venue)
            continue
        metrics = dict(venue.get("metrics") or {})
        indexes = list(profile.wos_indexes)
        quartiles = list(profile.quartiles)
        metrics.update({
            "wosIndexes": indexes,
            "wosIndex": indexes[0] if len(indexes) == 1 else (" / ".join(indexes) if indexes else None),
            "jcrQuartiles": quartiles,
            "jcrQuartile": quartiles[0] if len(quartiles) == 1 else (" / ".join(quartiles) if quartiles else None),
            "impactFactor": profile.impact_factor,
            "jci": profile.jci,
            "jcrYear": profile.jcr_year,
            "clarivateJournalId": profile.id,
            "clarivateSourceUrl": profile.source_url,
            "clarivateRanks": [x.as_dict() for x in profile.ranks],
        })
        venue["metrics"] = {k: v for k, v in metrics.items() if v is not None}
        output.append(venue)
    return output


def _metadata_enrichment_preferences(preferences: dict[str, Any]) -> dict[str, Any]:
    # Required journal metadata must not stop the research-only pre-ranking before
    # the authoritative enrichment APIs have had a chance to run. Final ranking
    # receives the user's original modes unchanged.
    import copy
    out = copy.deepcopy(preferences)
    for key in ("wosIndexes", "jcrQuartiles", "impactFactor", "openAccess", "apcCny", "reviewDays"):
        value = out.get(key)
        if isinstance(value, dict) and value.get("enabled"):
            value["mode"] = "preferred"
    return out


def _apply_identity_enrichment(
    venues: list[dict[str, Any]],
    sources: dict[str, SourceProfile],
    crossref_profiles: dict[str, CrossrefJournalProfile],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for raw in venues:
        venue = dict(raw)
        source_id = str(venue.get("openalexSourceId") or "")
        source = sources.get(source_id)
        if source is not None:
            venue["openalexSourceName"] = source.display_name
            venue["openalexAliases"] = list(source.aliases)
            venue["dblpAliases"] = list(source.canonical_aliases)
            venue["openalexTopics"] = [x.name for x in source.topics[:10]]
            if source.issn_l:
                venue["issnL"] = source.issn_l
            if source.issn:
                venue["issn"] = list(source.issn)
            if not venue.get("link") and source.homepage_url:
                venue["link"] = source.homepage_url
        crossref = crossref_profiles.get(source_id)
        if crossref is not None:
            venue["crossrefAliases"] = list(crossref.aliases)
            venue["crossrefVerified"] = True
            if venue.get("type") == "journal" and crossref.publisher:
                venue["publisher"] = crossref.publisher
        output.append(venue)
    return output


def _constraint(label: str, mode: str, condition: bool | None, detail: str, *, unknown_is_na: bool = False) -> dict[str, Any]:
    if condition is None:
        status = "not_applicable" if unknown_is_na else "unknown"
    else:
        status = "pass" if condition else "fail"
    return {"label": label, "mode": mode if mode in {"required", "preferred"} else "preferred", "status": status, "detail": detail}


def _location_matches(place: str, requested: Iterable[str]) -> bool:
    hay = place.lower()
    for raw in requested:
        needle = str(raw).strip().lower()
        if not needle:
            continue
        if needle in hay:
            return True
        if any(token in hay for token in REGION_TERMS.get(needle, ())):
            return True
    return False


def _days_until(venue: dict[str, Any]) -> int | None:
    deadline = str(venue.get("deadline") or "")
    zone = str(venue.get("timezone") or "UTC")
    parsed = _deadline_in_utc(deadline, zone)
    if parsed is None:
        return None
    now = datetime.now(timezone.utc)
    return math.floor((parsed - now).total_seconds() / 86400)


def evaluate_constraints(venue: dict[str, Any], preferences: dict[str, Any]) -> list[dict[str, Any]]:
    """Evaluate user constraints without inventing a hidden actionability requirement.

    V3.10 separates academic suitability from whether a currently verified conference
    edition is open. Deadline/location preferences remain visible constraints, but they
    no longer erase an academically excellent venue from the best-fit list.
    """
    results: list[dict[str, Any]] = []

    ccf = _pref(preferences, "ccfRanks")
    if ccf.get("enabled"):
        allowed = ccf.get("value") or []
        current = venue.get("ccf") or "U"
        verified = venue.get("ccfVerified") is True or current in {"A", "B", "C"}
        condition = None if current == "U" or not verified else current in allowed
        detail = "当前 CCF 目录状态未核验" if condition is None else f"当前：{current}"
        results.append(_constraint("CCF 等级", str(ccf.get("mode") or "preferred"), condition, detail))

    if venue.get("type") == "conference":
        days = _days_until(venue)
        core = _pref(preferences, "coreRanks")
        if core.get("enabled"):
            current_core = venue.get("core") or "N"
            condition = None if current_core in {None, "U", "Unknown"} else current_core in (core.get("value") or [])
            results.append(_constraint("CORE 等级", str(core.get("mode") or "preferred"), condition, f"当前：{current_core}" if condition is not None else "CORE 等级未核验"))
        deadline = _pref(preferences, "deadlineMonths")
        if deadline.get("enabled"):
            months = float(deadline.get("value") or 0)
            ok = None if days is None else days >= 0 and days <= months * 31
            detail = "截止时间未公布或无法核验" if days is None else (f"已截止 {abs(days)} 天" if days < 0 else f"距截止约 {days} 天")
            results.append(_constraint("投稿窗口", str(deadline.get("mode") or "preferred"), ok, detail))
        locations = _pref(preferences, "locations")
        requested = locations.get("value") or []
        if locations.get("enabled") and requested:
            place = str(venue.get("place") or "")
            unverified = not place or "未核验" in place or place.lower() in {"tbd", "unknown"}
            ok = None if unverified else _location_matches(place, requested)
            results.append(_constraint("会议地点", str(locations.get("mode") or "preferred"), ok, place or "地点未核验"))
    else:
        metrics = venue.get("metrics") if isinstance(venue.get("metrics"), dict) else {}
        wos = _pref(preferences, "wosIndexes")
        if wos.get("enabled"):
            values = metrics.get("wosIndexes") or ([] if metrics.get("wosIndex") is None else [metrics.get("wosIndex")])
            values = [str(x) for x in values if x]
            ok = None if not values else bool(set(values) & set(wos.get("value") or []))
            detail = "未配置/未命中 Clarivate Web of Science Journals API；本项不作为 Preferred 已满足" if not values else " / ".join(values)
            results.append(_constraint("WoS / SCI", str(wos.get("mode") or "preferred"), ok, detail, unknown_is_na=str(wos.get("mode") or "preferred")=="preferred"))
        jcr = _pref(preferences, "jcrQuartiles")
        if jcr.get("enabled"):
            values = metrics.get("jcrQuartiles") or ([] if metrics.get("jcrQuartile") is None else [metrics.get("jcrQuartile")])
            values = [str(x) for x in values if x]
            ok = None if not values else bool(set(values) & set(jcr.get("value") or []))
            detail = "未配置/未命中 Clarivate JCR 权威数据；本项不作为 Preferred 已满足" if not values else " / ".join(values)
            results.append(_constraint("JCR 分区", str(jcr.get("mode") or "preferred"), ok, detail, unknown_is_na=str(jcr.get("mode") or "preferred")=="preferred"))
        impact = _pref(preferences, "impactFactor")
        if impact.get("enabled"):
            value = metrics.get("impactFactor")
            rng = impact.get("value") or {}
            ok = None if value is None else (rng.get("min") is None or value >= rng["min"]) and (rng.get("max") is None or value <= rng["max"])
            results.append(_constraint("Impact Factor", str(impact.get("mode") or "preferred"), ok, "未配置/未命中 Clarivate JIF 权威数据；OpenAlex 2yr mean citedness 不会冒充 JIF" if value is None else f"JIF {value:g}", unknown_is_na=str(impact.get("mode") or "preferred")=="preferred"))
        apc = _pref(preferences, "apcCny")
        if apc.get("enabled"):
            value = metrics.get("apcCny")
            rng = apc.get("value") or {}
            ok = None if value is None else (rng.get("min") is None or value >= rng["min"]) and (rng.get("max") is None or value <= rng["max"])
            results.append(_constraint("APC 预算", str(apc.get("mode") or "preferred"), ok, "OpenAlex 当前未提供该期刊 APC list price，或 ECB 汇率暂不可用" if value is None else f"OpenAlex list APC 经 ECB 汇率折算：约 ¥{int(value):,}", unknown_is_na=str(apc.get("mode") or "preferred")=="preferred"))
        review = _pref(preferences, "reviewDays")
        if review.get("enabled"):
            value = metrics.get("reviewDays")
            ok = None if value is None else value <= float(review.get("value") or 0)
            results.append(_constraint("审稿速度", str(review.get("mode") or "preferred"), ok, "当前未接入可统一核验口径的 publisher review-time source；本项不参与 Preferred 排序" if value is None else f"约 {value} 天", unknown_is_na=str(review.get("mode") or "preferred")=="preferred"))
        oa = _pref(preferences, "openAccess")
        if oa.get("enabled"):
            value = metrics.get("oaType")
            choice = str(oa.get("value") or "any")
            if value is None:
                ok = None
            elif choice == "any":
                ok = True
            elif choice == "required":
                ok = bool(re.search(r"gold|open", str(value), re.I))
            else:
                ok = bool(re.search(r"gold|hybrid|open", str(value), re.I))
            results.append(_constraint("Open Access", str(oa.get("mode") or "preferred"), ok, str(value or "OpenAlex Source 当前未提供可核验的 fully-OA 状态"), unknown_is_na=str(oa.get("mode") or "preferred")=="preferred"))
        china = _pref(preferences, "chinaIndexes")
        if china.get("enabled") and (china.get("value") or []):
            results.append(_constraint("国内评价体系", str(china.get("mode") or "preferred"), None, "当前版本未接入可核验的国内核心目录数据"))
    return results


def _is_actionability_constraint(item: dict[str, Any]) -> bool:
    return item.get("label") in {"投稿窗口", "会议地点"}


def _preference_score(venue: dict[str, Any], constraints: list[dict[str, Any]], *, academic_only: bool = False) -> int:
    values: list[float] = []
    ccf_weight = {"A": 100.0, "B": 78.0, "C": 58.0, "N": 25.0, "U": 50.0}
    core_weight = {"A*": 100.0, "A": 86.0, "B": 70.0, "C": 50.0, "N": 25.0, "U": 50.0}
    days = _days_until(venue) if venue.get("type") == "conference" else None
    for item in constraints:
        if item.get("mode") != "preferred" or item.get("status") == "not_applicable":
            continue
        if academic_only and _is_actionability_constraint(item):
            continue
        status = item.get("status")
        label = item.get("label")
        if status == "unknown":
            values.append(50.0)
        elif status == "fail":
            values.append(0.0)
        elif label == "CCF 等级":
            values.append(ccf_weight.get(str(venue.get("ccf") or "U"), 50.0))
        elif label == "CORE 等级":
            values.append(core_weight.get(str(venue.get("core") or "U"), 50.0))
        elif label == "投稿窗口" and days is not None:
            values.append(100.0 if days >= 14 else 82.0 if days >= 7 else 62.0)
        else:
            values.append(90.0)
    return round(sum(values) / len(values)) if values else 50


def actionability_for_venue(venue: dict[str, Any], constraints: list[dict[str, Any]]) -> dict[str, Any]:
    if venue.get("type") != "conference":
        return {"status": "continuous", "score": 100, "daysUntil": None, "reason": "期刊按连续投稿处理；具体 special issue 截止日期需另行核验"}
    days = _days_until(venue)
    if days is None:
        return {"status": "unknown", "score": None, "daysUntil": None, "reason": "当前 conference edition 的正式截止时间尚未核验"}
    if days < 0:
        return {"status": "closed", "score": 0, "daysUntil": days, "reason": f"当前 edition 已截止 {abs(days)} 天"}
    required_action = [c for c in constraints if _is_actionability_constraint(c) and c.get("mode") == "required"]
    if any(c.get("status") in {"fail", "unknown"} for c in required_action):
        return {"status": "blocked", "score": 0, "daysUntil": days, "reason": "当前 edition 已开放，但未满足 Required 的截止窗口/地点条件"}
    score = 100 if days >= 14 else 85 if days >= 7 else 65
    return {"status": "open", "score": score, "daysUntil": days, "reason": f"当前 edition 已核验且尚未截止，约 {days} 天"}

def _weighted_available(components: list[tuple[float, int | None]]) -> int:
    available = [(weight, score) for weight, score in components if score is not None]
    denom = sum(weight for weight, _ in available)
    if denom <= 0:
        return 0
    return round(sum(weight * float(score) for weight, score in available) / denom)


def _semantic_result_score(result: SemanticSearchResult | None) -> tuple[int | None, list[dict[str, Any]]]:
    if result is None or result.error:
        return None, []
    if not result.works:
        return 0, []
    similarity_values: list[float] = []
    for work in result.works[:8]:
        value = work.relevance_score
        if value is None:
            continue
        try:
            raw = float(value)
        except (TypeError, ValueError):
            continue
        if 0.0 <= raw <= 1.2:
            similarity_values.append(max(0.0, min(100.0, raw * 100.0)))
    coverage = min(100.0, 28.0 + 12.0 * min(len(result.works), 6))
    if similarity_values:
        similarity_values.sort(reverse=True)
        quality = sum(similarity_values[:3]) / min(3, len(similarity_values))
        score = round(0.72 * quality + 0.28 * coverage)
    else:
        score = round(coverage)
    evidence: list[dict[str, Any]] = []
    for rank_index, work in enumerate(result.works, start=1):
        item = work.as_dict()
        item["semanticRank"] = rank_index
        evidence.append(item)
    return max(0, min(100, score)), evidence


def rank_venues(
    profile: dict[str, Any],
    preferences: dict[str, Any],
    venues: list[dict[str, Any]],
    semantic: SemanticSearchResult,
    source_profiles: dict[str, SourceProfile] | None = None,
    reference_text: str = "",
    secondary: SemanticScholarSearchResult | None = None,
    conditioned: dict[str, SemanticSearchResult] | None = None,
) -> list[dict[str, Any]]:
    source_profiles = source_profiles or {}
    conditioned = conditioned or {}
    profile_words = _profile_tokens(profile)
    semantic_available = bool(semantic.works) and not semantic.error
    secondary = secondary or SemanticScholarSearchResult(query="", papers=[], source_url="", error="not configured")
    secondary_available = bool(secondary.papers) and not secondary.error
    research_scopes = research_scope_vector(profile)
    research_topics, _ = research_topic_vector(semantic.works)
    refs = reference_scores(reference_text, venues)
    has_reference_signal = bool(reference_text.strip()) and any(count > 0 for count, _ in refs.values())

    features: list[dict[str, Any]] = []
    for venue in venues:
        source_ids = list(venue.get("openalexSourceIds") or [])
        if not source_ids and venue.get("openalexSourceId"):
            source_ids = [str(venue.get("openalexSourceId"))]
        source = next((source_profiles.get(str(sid)) for sid in source_ids if source_profiles.get(str(sid)) is not None), None)
        raw_direct, evidence, direct_topics = _semantic_evidence_raw(semantic.works, venue) if semantic_available else (0.0, [], [])
        raw_secondary, secondary_evidence = _s2_evidence_raw(secondary.papers, venue) if secondary_available else (0.0, [])
        topic_match, source_topic_names = topic_fit_score(research_topics, source)
        v_scope = venue_scope_vector(venue, source)
        scope_match = cosine_score(research_scopes, v_scope)
        scope_labels = matched_scope_labels(research_scopes, v_scope)
        ref_count, ref_score = refs.get(str(venue.get("id")), (0, 0))
        lexical, matched_keywords = _lexical_fit(profile_words, venue)
        conditioned_score, conditioned_evidence = _semantic_result_score(conditioned.get(str(venue.get("id"))))
        features.append({
            "venue": venue,
            "rawDirect": raw_direct,
            "evidence": evidence,
            "rawSecondary": raw_secondary,
            "secondaryEvidence": secondary_evidence,
            "directTopics": direct_topics,
            "topicMatch": topic_match,
            "sourceTopicNames": source_topic_names,
            "scopeMatch": scope_match,
            "matchedScopes": scope_labels,
            "referenceCount": ref_count,
            "referenceMatch": ref_score,
            "keywordMatch": lexical,
            "matchedKeywords": matched_keywords,
            "conditionedMatch": conditioned_score,
            "conditionedEvidence": conditioned_evidence,
        })

    max_direct = max((float(f["rawDirect"]) for f in features), default=0.0)
    max_secondary = max((float(f["rawSecondary"]) for f in features), default=0.0)
    results: list[dict[str, Any]] = []
    for f in features:
        venue = f["venue"]
        semantic_score = min(100, round(100.0 * float(f["rawDirect"]) / 2.5)) if max_direct > 0 else 0
        secondary_score = min(100, round(100.0 * float(f["rawSecondary"]) / 2.2)) if max_secondary > 0 else 0
        topic_match = f["topicMatch"]
        scope_match = f["scopeMatch"]
        reference_match = f["referenceMatch"] if has_reference_signal else None
        conditioned_match = f["conditionedMatch"]

        # V3.10: venue-conditioned recent-work retrieval is the principal content signal.
        # Source topic histograms are retained only as a 4% auxiliary signal; CCF does not
        # contribute to research content fit at all.
        components: list[tuple[float, int | None]] = [
            (0.48, conditioned_match),
            (0.14, semantic_score if semantic_available and max_direct > 0 else None),
            (0.18, scope_match),
            (0.08, secondary_score if secondary_available and max_secondary > 0 else None),
            (0.08, reference_match),
            (0.04, topic_match if semantic_available else None),
        ]
        research_match = _weighted_available(components)
        if conditioned_match is None and not semantic_available and not secondary_available:
            research_match = min(70, research_match)

        constraints = evaluate_constraints(venue, preferences)
        academic_required = [
            c for c in constraints
            if c.get("mode") == "required" and not _is_actionability_constraint(c)
            and c.get("status") in {"fail", "unknown"}
        ]
        academic_eligible = not academic_required
        academic_preference = _preference_score(venue, constraints, academic_only=True)
        academic_score = round(research_match * 0.90 + academic_preference * 0.10)
        actionability = actionability_for_venue(venue, constraints)
        actionable = academic_eligible and actionability.get("status") in {"open", "continuous"}
        if venue.get("type") == "conference":
            required_action = [c for c in constraints if _is_actionability_constraint(c) and c.get("mode") == "required"]
            if any(c.get("status") in {"fail", "unknown"} for c in required_action):
                actionable = False

        evidence_count = len(f["evidence"])
        secondary_count = len(f["secondaryEvidence"])
        conditioned_count = len(f["conditionedEvidence"])
        independent_sources = sum([
            1 if conditioned_match is not None and conditioned_match > 0 else 0,
            1 if semantic_score > 0 else 0,
            1 if secondary_score > 0 else 0,
            1 if f["referenceCount"] > 0 else 0,
            1 if (scope_match or 0) >= 65 else 0,
        ])
        confidence = (
            "high" if research_match >= 72 and independent_sources >= 2 else
            "medium" if research_match >= 42 and independent_sources >= 1 else
            "unavailable" if conditioned_match is None and not semantic_available and not secondary_available and not has_reference_signal and scope_match is None else
            "low"
        )

        reasons: list[str] = []
        if conditioned_match is not None:
            if conditioned_count:
                examples = "；".join(item["title"] for item in f["conditionedEvidence"][:2])
                reasons.append(f"Venue-conditioned 近期论文适配 {conditioned_match}/100：该 venue/series 最近论文中检索到 {conditioned_count} 篇语义近邻，例如：{examples}")
            else:
                reasons.append("已在该 venue/series 的近期论文中执行语义检索，但未找到足够接近的论文；该主信号记为 0")
        else:
            reasons.append("该候选尚未可靠绑定 OpenAlex Source/series，Venue-conditioned 主信号保持 Unknown")
        if f["evidence"]:
            examples = "；".join(item["title"] for item in f["evidence"][:2])
            reasons.append(f"全局 OpenAlex 相似论文中有 {evidence_count} 篇直接发表于该 venue，例如：{examples}")
        if scope_match is not None:
            reasons.append(f"计算机细分方向适配 {scope_match}/100" + (f"：{'、'.join(f['matchedScopes'][:3])}" if f["matchedScopes"] else ""))
        if secondary_count:
            reasons.append(f"Semantic Scholar 独立检索有 {secondary_count} 篇该 venue 论文命中")
        if f["referenceCount"] > 0:
            reasons.append(f"稿件 References 中结构化识别到该 venue/community {f['referenceCount']} 次，仅作为 8% 社区先验")
        if topic_match is not None:
            reasons.append(f"OpenAlex Source topics 仅作 4% 辅助信号：{topic_match}/100")
        if venue.get("ccf") in {"A", "B", "C"}:
            reasons.append(f"CCF {venue.get('ccf')} 仅作为用户偏好/元数据，不参与内容匹配分")

        matched_topics = list(dict.fromkeys([*f["sourceTopicNames"], *f["directTopics"]]))[:6]
        results.append({
            "venue": venue,
            "researchMatch": max(0, min(100, research_match)),
            "academicScore": max(0, min(100, academic_score)),
            "actionability": actionability,
            "isCurrentlyActionable": actionable,
            "venueConditionedMatch": conditioned_match,
            "venueConditionedEvidenceCount": conditioned_count,
            "venueConditionedEvidence": f["conditionedEvidence"],
            "semanticMatch": semantic_score if semantic_available else None,
            "semanticConfidence": confidence,
            "semanticEvidenceCount": evidence_count,
            "semanticEvidence": f["evidence"],
            "secondaryMatch": secondary_score if secondary_available else None,
            "secondaryEvidenceCount": secondary_count,
            "secondaryEvidence": f["secondaryEvidence"],
            "matchedTopics": matched_topics,
            "topicMatch": topic_match,
            "scopeMatch": scope_match,
            "referenceMatch": reference_match,
            "referenceCount": f["referenceCount"],
            "matchedScopes": f["matchedScopes"],
            "areaMatch": _area_fit(profile, venue),
            "keywordMatch": f["keywordMatch"],
            "preferenceScore": max(0, min(100, academic_preference)),
            "finalScore": max(0, min(100, academic_score)),
            "eligible": academic_eligible,
            "reasons": reasons,
            "constraints": constraints,
            "matchedKeywords": f["matchedKeywords"],
            "evidenceSources": independent_sources,
        })

    ccf_value = {"A": 3, "B": 2, "C": 1, "N": 0, "U": -1}
    results.sort(key=lambda item: (
        1 if item["eligible"] else 0,
        item["academicScore"], item["researchMatch"], item["evidenceSources"],
        item["venueConditionedMatch"] if item["venueConditionedMatch"] is not None else -1,
        item["scopeMatch"] if item["scopeMatch"] is not None else -1,
        item["semanticMatch"] if item["semanticMatch"] is not None else -1,
        ccf_value.get(str(item["venue"].get("ccf") or "U"), -1),
    ), reverse=True)
    return results

def _health_entry(status: str, message: str, *, enabled: bool = True, configured: bool | None = None, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "status": status,
        "enabled": enabled,
        "configured": configured,
        "message": message,
        "details": details or {},
    }


def _overall_health(sources: dict[str, dict[str, Any]]) -> tuple[str, str]:
    openalex = sources.get("openalexWorks", {})
    if openalex.get("status") in {"ready", "limited"}:
        active = [(k, v) for k, v in sources.items() if k != "openalexWorks" and v.get("enabled", True)]
        degraded = any(v.get("status") in {"degraded", "error"} for _, v in active)
        if degraded:
            return "degraded", "OpenAlex 相似论文主链可用，但一个或多个增强/元数据源降级"
        limited = openalex.get("status") == "limited" or any(v.get("status") == "limited" for _, v in active)
        if limited:
            return "limited", "推荐主链可用，但至少一个数据源处于额度/覆盖受限状态；请查看分项诊断"
        return "ready", "推荐证据数据链完整可用"
    secondary = sources.get("semanticScholar", {})
    if secondary.get("status") == "ready":
        return "degraded", "OpenAlex 主链不可用，正在依赖 Semantic Scholar + CS scope + References 降级推荐"
    return "limited", "实时学术图谱证据不足；当前结果主要依赖本地 CS scope / References / Venue 元数据"


async def recommend(
    db: Session,
    settings: Settings,
    project: Project,
    profile: dict[str, Any],
    preferences: dict[str, Any],
) -> dict[str, Any]:
    import asyncio

    target = str(preferences.get("targetType") or "both")
    service = VenueCatalogService(db, settings)
    scholarly = load_scholarly_runtime(db, settings)
    catalog_venues: list[dict[str, Any]] = []
    source_meta: list[dict[str, Any]] = []
    source_errors: list[str] = []
    catalog_health: dict[str, dict[str, Any]] = {}

    for kind in ("conference", "journal"):
        if target == "conference" and kind == "journal":
            continue
        if target == "journal" and kind == "conference":
            continue
        try:
            catalog = await service.get(kind)
            catalog_venues.extend(catalog.items)
            source_meta.append({
                "kind": kind, "count": len(catalog.items), "source": catalog.source_url,
                "sourceLabel": catalog.source_label, "stale": catalog.stale,
                "lastRefreshError": catalog.last_error,
            })
            catalog_health[kind] = _health_entry(
                "degraded" if catalog.stale else "ready",
                f"{catalog.source_label}：{len(catalog.items)} 个候选" + ("（使用缓存）" if catalog.stale else ""),
                details={"count": len(catalog.items), "source": catalog.source_url, "stale": catalog.stale, "error": catalog.last_error},
            )
        except Exception as exc:
            source_errors.append(f"{kind}: {exc}")
            catalog_health[kind] = _health_entry("error", str(exc), details={"count": 0})

    query = build_semantic_query(profile)
    reference_text = extract_reference_text(project)
    top_n = max(3, min(30, int(preferences.get("topN") or 12)))
    timeout = httpx.Timeout(max(float(scholarly.request_timeout_seconds), 10.0))
    fx_rate: FxRate | None = None
    fx_error: str | None = None
    clarivate_result = ClarivateBatchResult()
    async with httpx.AsyncClient(timeout=timeout) as client:
        semantic = await semantic_search(client, query, scholarly)
        source_ids = [w.source_id for w in semantic.works if w.source_id]
        hydrated_result = await hydrate_sources(client, source_ids, scholarly) if source_ids else None
        hydrated = hydrated_result.sources if hydrated_result else {}
        base_sources = {**_minimal_source_profiles(semantic.works), **hydrated}

        # First merge Sources actually seen in the semantic neighborhood. Then resolve a
        # bounded slice of the catalog candidates themselves to OpenAlex Sources. This
        # prevents the old failure mode where Works retrieval was healthy but every catalog
        # candidate still showed Source topics = Unknown simply because none of the top 50
        # papers happened to publish in that venue.
        venues, source_profiles, dynamic_count = merge_openalex_sources(
            catalog_venues, semantic, base_sources, profile, target, {}
        )
        # Candidate Source resolution is deliberately bounded. Authenticated OpenAlex
        # users get a wider enrichment slice; anonymous/basic mode stays conservative
        # so one recommendation run cannot burn a disproportionate share of the public budget.
        per_type_resolution_limit = (
            max(16, min(22, top_n * 2)) if scholarly.openalex_api_key
            else max(8, min(12, top_n))
        )
        resolution_slice = _candidate_resolution_shortlist(
            profile, preferences, venues, per_type_limit=per_type_resolution_limit
        )
        resolution_requests = _source_resolution_requests(resolution_slice)
        candidate_resolution_task = resolve_candidate_source_series(
            client, resolution_requests, scholarly, max_candidates=len(resolution_requests) or 1
        )
        secondary_task = s2_search_papers(client, query, scholarly, limit=20)
        candidate_resolution, secondary = await asyncio.gather(candidate_resolution_task, secondary_task)
        venues, source_profiles = _attach_resolved_candidate_series(venues, candidate_resolution, source_profiles)

        # Canonical aliases and bibliographic journal verification now run over both the
        # semantic-neighborhood Sources and the newly resolved candidate Sources.
        source_issns = {
            sid: tuple(x for x in ([source.issn_l] if source.issn_l else []) + list(source.issn) if x)
            for sid, source in source_profiles.items()
            if str(source.source_type or "").lower() == "journal" and (source.issn_l or source.issn)
        }
        dblp_task = dblp_canonicalize_sources(client, source_profiles, scholarly, limit=16)
        crossref_task = crossref_resolve_journals(client, source_issns, scholarly, limit=16)
        (canonical_sources, dblp_matches, dblp_error), (crossref_profiles, crossref_error) = await asyncio.gather(
            dblp_task, crossref_task
        )
        source_profiles = canonical_sources
        venues = _apply_identity_enrichment(venues, source_profiles, crossref_profiles)

        # OpenAlex supplies public OA/APC metadata. Convert its comparable USD list
        # price to CNY only with a timestamped ECB reference rate; if ECB is unavailable
        # the original OpenAlex amount is preserved and CNY stays Unknown.
        if any(src.apc_usd is not None for src in source_profiles.values() if str(src.source_type or "").lower() == "journal"):
            try:
                fx_rate = await latest_cny_per_usd(client)
            except Exception as exc:
                fx_error = str(exc)
        venues = _apply_public_journal_metrics(venues, source_profiles, fx_rate)

        # Pre-ranking must not be killed by Required JCR/WoS/APC fields before their
        # authoritative enrichers run. The final ranking below uses the original modes.
        enrichment_preferences = _metadata_enrichment_preferences(preferences)

        # Pre-rank with all non-conditioned evidence, then spend bounded OpenAlex semantic
        # calls only on the strongest research candidates. OpenAlex documents semantic
        # search at roughly one request/second, so calls are intentionally sequential.
        preliminary = rank_venues(
            profile, enrichment_preferences, venues, semantic, source_profiles, reference_text, secondary, {}
        )
        conditioned: dict[str, SemanticSearchResult] = {}
        conditioned_attempted = 0
        conditioned_success = 0
        conditioned_limit = max(6, min(16, top_n + 4)) if scholarly.openalex_api_key else max(4, min(8, top_n))
        candidates_for_conditioned = [
            item for item in preliminary
            if item.get("eligible")
            and (item["venue"].get("openalexSourceIds") or item["venue"].get("openalexSourceId"))
        ][:conditioned_limit]
        for index, item in enumerate(candidates_for_conditioned):
            venue = item["venue"]
            ids = list(venue.get("openalexSourceIds") or [])
            if not ids and venue.get("openalexSourceId"):
                ids = [str(venue.get("openalexSourceId"))]
            if not ids:
                continue
            conditioned_attempted += 1
            result = await semantic_search_within_sources(
                client, query, ids, scholarly, limit=50
            )
            conditioned[str(venue.get("id"))] = result
            if not result.error:
                conditioned_success += 1
            # Respect OpenAlex semantic-search rate guidance without sleeping after the last call.
            if index + 1 < len(candidates_for_conditioned):
                await asyncio.sleep(1.02)

        # Optional official journal metrics. Clarivate is the authority for JIF/JCR/WoS
        # edition; without an entitled key these fields deliberately remain unavailable.
        if target != "conference" and scholarly.clarivate_enabled and scholarly.clarivate_api_key:
            research_ranked = rank_venues(
                profile, enrichment_preferences, venues, semantic, source_profiles, reference_text, secondary, conditioned
            )
            journal_shortlist = [
                item["venue"] for item in research_ranked if item["venue"].get("type") == "journal"
            ][: max(6, min(scholarly.clarivate_journal_limit, max(top_n * 2, 16)))]
            clarivate_result = await clarivate_resolve_journals(
                client, journal_shortlist, scholarly, limit=len(journal_shortlist)
            )
            venues = _apply_clarivate_metrics(venues, clarivate_result.profiles)

    if not venues:
        raise RuntimeError("没有可用的 Venue 候选：CCF/CCFDDL 目录与实时学术源均未产生候选。")

    ranked = rank_venues(profile, preferences, venues, semantic, source_profiles, reference_text, secondary, conditioned)
    academic_results: list[dict[str, Any]] = []
    actionable_results: list[dict[str, Any]] = []
    for venue_type in ("conference", "journal"):
        if target == "conference" and venue_type == "journal":
            continue
        if target == "journal" and venue_type == "conference":
            continue
        academic = [r for r in ranked if r["eligible"] and r["venue"].get("type") == venue_type][:top_n]
        academic_results.extend(academic)
        if venue_type == "conference":
            actionable_results.extend([r for r in ranked if r["isCurrentlyActionable"] and r["venue"].get("type") == "conference"][:top_n])
    result_items = academic_results

    enrichment_error = hydrated_result.error if hydrated_result else None
    candidate_sources_flat = [src for group in candidate_resolution.matches.values() for src in group]
    candidate_sources_with_topics = sum(1 for src in candidate_sources_flat if src.topics)
    source_health: dict[str, dict[str, Any]] = {
        "openalexWorks": _health_entry(
            "disabled" if not scholarly.openalex_enabled else (
                "error" if semantic.error else (
                    ("ready" if scholarly.openalex_api_key else "limited") if semantic.works else "degraded"
                )
            ),
            "OpenAlex 已禁用" if not scholarly.openalex_enabled else (
                semantic.error or (
                    f"返回 {len(semantic.works)} 篇语义相似论文" + ("；已使用 API Key" if scholarly.openalex_api_key else "；匿名低额度模式")
                )
            ),
            enabled=scholarly.openalex_enabled,
            configured=bool(scholarly.openalex_api_key),
            details={"workCount": len(semantic.works), "rateLimit": semantic.rate_limit, "authenticated": bool(scholarly.openalex_api_key)},
        ),
        "openalexSources": _health_entry(
            "disabled" if not scholarly.openalex_enabled else (
                "error" if enrichment_error and not hydrated else (
                    "degraded" if enrichment_error or not hydrated or sum(1 for s in hydrated.values() if s.topics) == 0 else "ready"
                )
            ),
            "OpenAlex 已禁用" if not scholarly.openalex_enabled else (
                enrichment_error or f"解析 {len(hydrated)} 个 Source；其中 {sum(1 for s in hydrated.values() if s.topics)} 个含聚合 topics/topic_share"
            ),
            enabled=scholarly.openalex_enabled,
            configured=bool(scholarly.openalex_api_key),
            details={"hydratedSourceCount": len(hydrated), "sourcesWithTopics": sum(1 for s in hydrated.values() if s.topics)},
        ),
        "openalexCandidateSources": _health_entry(
            "disabled" if not scholarly.openalex_enabled else (
                "not_applicable" if candidate_resolution.attempted == 0 else (
                    "degraded" if not candidate_resolution.matches else (
                        "ready" if (
                            len(candidate_resolution.matches) / max(1, candidate_resolution.attempted) >= 0.5
                            and candidate_sources_with_topics > 0
                        ) else "limited"
                    )
                )
            ),
            "OpenAlex 已禁用" if not scholarly.openalex_enabled else (
                "本轮没有需要解析的 catalog Venue" if candidate_resolution.attempted == 0 else (
                    f"候选 Venue Source 解析 {len(candidate_resolution.matches)}/{candidate_resolution.attempted}；"
                    f"其中 {candidate_sources_with_topics} 个含 Source topics"
                    + (f"；部分请求错误：{candidate_resolution.errors[0]}" if candidate_resolution.errors else "")
                )
            ),
            enabled=scholarly.openalex_enabled,
            configured=bool(scholarly.openalex_api_key),
            details={
                "attemptedCandidateCount": candidate_resolution.attempted,
                "resolvedCandidateCount": len(candidate_resolution.matches),
                "resolvedCandidatesWithTopics": candidate_sources_with_topics,
                "errors": list(candidate_resolution.errors),
                "rateLimit": candidate_resolution.rate_limit,
            },
        ),
        "openalexVenueConditioned": _health_entry(
            "disabled" if not scholarly.openalex_enabled else (
                "not_applicable" if conditioned_attempted == 0 else (
                    "ready" if conditioned_success == conditioned_attempted else ("limited" if conditioned_success else "degraded")
                )
            ),
            "OpenAlex 已禁用" if not scholarly.openalex_enabled else (
                "没有已解析 Source 的候选进入 Venue-conditioned 验证" if conditioned_attempted == 0 else
                f"对 {conditioned_attempted} 个候选执行 venue 内近期论文语义检索；{conditioned_success} 个请求成功"
            ),
            enabled=scholarly.openalex_enabled,
            configured=bool(scholarly.openalex_api_key),
            details={"attempted": conditioned_attempted, "successful": conditioned_success},
        ),
        "semanticScholar": _health_entry(
            "disabled" if not scholarly.semantic_scholar_enabled else (
                "limited" if secondary.error_kind == "rate_limited" else (
                    "error" if secondary.error and not secondary.papers else ("ready" if secondary.papers else "degraded")
                )
            ),
            "Semantic Scholar 已禁用" if not scholarly.semantic_scholar_enabled else (secondary.error or f"返回 {len(secondary.papers)} 篇独立检索论文"),
            enabled=scholarly.semantic_scholar_enabled,
            configured=bool(scholarly.semantic_scholar_api_key),
            details={
                "paperCount": len(secondary.papers),
                "authenticated": bool(scholarly.semantic_scholar_api_key),
                "errorKind": secondary.error_kind,
                "statusCode": secondary.status_code,
            },
        ),
        "crossref": _health_entry(
            "disabled" if not scholarly.crossref_enabled else (
                "not_applicable" if not source_issns else (
                    "error" if crossref_error and not crossref_profiles else ("ready" if crossref_profiles else "degraded")
                )
            ),
            "Crossref 已禁用" if not scholarly.crossref_enabled else (
                "本轮没有带 ISSN 的 journal Source 需要 Crossref 核验" if not source_issns else (
                    crossref_error or (f"核验 {len(crossref_profiles)} 个 journal Source" if crossref_profiles else "存在 journal Source，但本轮未完成 Crossref 身份核验")
                )
            ),
            enabled=scholarly.crossref_enabled,
            configured=bool(scholarly.crossref_email or scholarly.crossref_api_key),
            details={"applicableJournalSourceCount": len(source_issns), "verifiedJournalCount": len(crossref_profiles), "mode": "metadata-plus" if scholarly.crossref_api_key else ("polite" if scholarly.crossref_email else "public")},
        ),
        "clarivateJournals": _health_entry(
            "disabled" if not scholarly.clarivate_enabled else (
                "degraded" if not scholarly.clarivate_api_key else (
                    "limited" if clarivate_result.attempted and len(clarivate_result.profiles) < clarivate_result.attempted else "ready"
                )
            ),
            "Clarivate WoS Journals API 未启用；JIF/JCR/WoS edition 将保持未核验，不会由 OpenAlex 代替" if not scholarly.clarivate_enabled else (
                "已启用但未配置有权限的 Clarivate Web of Science Journals API Key" if not scholarly.clarivate_api_key else
                f"权威期刊指标核验 {len(clarivate_result.profiles)}/{clarivate_result.attempted}" + (f"；部分错误：{clarivate_result.errors[0]}" if clarivate_result.errors else "")
            ),
            enabled=scholarly.clarivate_enabled,
            configured=bool(scholarly.clarivate_api_key),
            details={"attempted": clarivate_result.attempted, "resolved": len(clarivate_result.profiles), "errors": list(clarivate_result.errors)},
        ),
        "ecbFx": _health_entry(
            "not_applicable" if not any(src.apc_usd is not None for src in source_profiles.values()) else (
                "ready" if fx_rate is not None else "degraded"
            ),
            "本轮没有 OpenAlex APC USD 需要换算" if not any(src.apc_usd is not None for src in source_profiles.values()) else (
                f"ECB 汇率可用：1 USD ≈ {fx_rate.cny_per_usd:.4f} CNY（{fx_rate.date}）" if fx_rate is not None else f"ECB 汇率暂不可用：{fx_error or 'no observation'}"
            ),
            enabled=True, configured=True,
            details=fx_rate.as_dict() if fx_rate is not None else {"error": fx_error},
        ),
        "reviewSpeed": _health_entry(
            "not_applicable",
            "未接入统一且可核验口径的出版社审稿速度源；不会用论坛/第三方估值填充该字段",
            enabled=False, configured=False,
        ),
        "dblp": _health_entry(
            "disabled" if not scholarly.dblp_enabled else (
                "not_applicable" if not any(str(src.source_type or "").lower() == "conference" for src in source_profiles.values()) else (
                    "error" if dblp_error and not dblp_matches else "ready"
                )
            ),
            "DBLP 已禁用" if not scholarly.dblp_enabled else (
                "本轮没有 OpenAlex conference Source 需要 DBLP 规范化" if not any(str(src.source_type or "").lower() == "conference" for src in source_profiles.values()) else (
                    dblp_error or (f"规范化 {len(dblp_matches)} 个 conference Source" if dblp_matches else "DBLP 查询已完成；本轮没有达到保守阈值的 canonical alias")
                )
            ),
            enabled=scholarly.dblp_enabled,
            configured=True,
            details={"applicableConferenceSourceCount": sum(1 for src in source_profiles.values() if str(src.source_type or "").lower() == "conference"), "canonicalizedSourceCount": len(dblp_matches)},
        ),
        "conferenceCatalog": catalog_health.get("conference", _health_entry("disabled", "本次目标不需要会议目录", enabled=False)),
        "journalCatalog": catalog_health.get("journal", _health_entry("disabled", "本次目标不需要期刊目录", enabled=False)),
    }
    overall_status, health_message = _overall_health(source_health)

    message = "推荐完成"
    if overall_status != "ready":
        message = f"推荐完成 · 数据源状态 {overall_status}：{health_message}"

    return {
        "id": f"rec_{uuid.uuid4()}",
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "progress": 100,
        "stage": "ready",
        "status": "ready",
        "message": message,
        "candidateCount": len(venues),
        "catalogCandidateCount": len(catalog_venues),
        "dynamicCandidateCount": dynamic_count,
        "eligibleCount": sum(1 for r in ranked if r["eligible"]),
        "results": result_items,
        "academicResults": academic_results,
        "actionableResults": actionable_results,
        "error": "；".join(source_errors) or None,
        "semanticRetrieval": {
            "provider": "OpenAlex",
            "status": "unavailable" if semantic.error else "ready",
            "query": semantic.query,
            "workCount": len(semantic.works),
            "works": [dict(work.as_dict(), semanticRank=index) for index, work in enumerate(semantic.works, start=1)],
            "sourceCount": len({w.source_id or w.source_name for w in semantic.works if w.source_id or w.source_name}),
            "hydratedSourceCount": len(hydrated),
            "candidateSourceResolutionAttempted": candidate_resolution.attempted,
            "candidateSourceResolvedCount": len(candidate_resolution.matches),
            "candidateSourceTopicsCount": candidate_sources_with_topics,
            "venueConditionedAttempted": conditioned_attempted,
            "venueConditionedSuccessful": conditioned_success,
            "dynamicCandidateCount": dynamic_count,
            "referenceChars": len(reference_text),
            "error": semantic.error,
            "sourceEnrichmentError": enrichment_error,
            "sourceUrl": semantic.source_url,
            "openalexAuthenticated": bool(scholarly.openalex_api_key),
            "semanticScholarPaperCount": len(secondary.papers),
            "semanticScholarError": secondary.error,
            "semanticScholarErrorKind": secondary.error_kind,
            "semanticScholarStatusCode": secondary.status_code,
        },
        "dataSourceHealth": {
            "overallStatus": overall_status,
            "message": health_message,
            "sources": source_health,
        },
        "sourceMeta": source_meta,
        "rankingVersion": "v3.11-journal-metadata-evidence-explorer",
    }
