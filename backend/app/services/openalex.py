from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Iterable

import httpx

from .scholarly_settings import ScholarlyRuntime

OPENALEX_BASE_URL = "https://api.openalex.org"
OPENALEX_WORKS_URL = f"{OPENALEX_BASE_URL}/works"
OPENALEX_SOURCES_URL = f"{OPENALEX_BASE_URL}/sources"
OPENALEX_RATE_LIMIT_URL = f"{OPENALEX_BASE_URL}/rate-limit"


def _compact_id(value: str | None) -> str:
    if not value:
        return ""
    return value.rstrip("/").rsplit("/", 1)[-1]


def _rate_limit_from_response(response: httpx.Response) -> dict[str, Any]:
    headers = response.headers
    def _int(name: str) -> int | None:
        raw = headers.get(name)
        try:
            return int(raw) if raw is not None else None
        except (TypeError, ValueError):
            return None
    return {
        "limit": _int("X-RateLimit-Limit"),
        "remaining": _int("X-RateLimit-Remaining"),
        "creditsUsed": _int("X-RateLimit-Credits-Used"),
        "resetSeconds": _int("X-RateLimit-Reset"),
    }


@dataclass(frozen=True)
class SemanticWork:
    id: str
    title: str
    year: int | None
    relevance_score: float | None
    source_id: str | None
    source_name: str | None
    source_type: str | None
    topics: tuple[str, ...]
    keywords: tuple[str, ...]
    doi: str | None = None
    source_names: tuple[str, ...] = ()
    topic_ids: tuple[str, ...] = ()
    topic_scores: tuple[float, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "workId": self.id,
            "title": self.title,
            "year": self.year,
            "relevanceScore": self.relevance_score,
            "doi": self.doi,
            "sourceId": self.source_id,
            "sourceName": self.source_name,
            "sourceType": self.source_type,
            "topics": list(self.topics),
            "keywords": list(self.keywords),
            "sourceNames": list(self.source_names),
            "topicIds": list(self.topic_ids),
            "topicScores": list(self.topic_scores),
            "url": self.id if self.id.startswith("http") else f"https://openalex.org/{self.id}",
        }


@dataclass(frozen=True)
class SemanticSearchResult:
    query: str
    works: list[SemanticWork]
    source_url: str
    error: str | None = None
    rate_limit: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SourceTopic:
    id: str
    name: str
    score: float = 0.0


@dataclass(frozen=True)
class ApcPrice:
    price: int
    currency: str

    def as_dict(self) -> dict[str, Any]:
        return {"price": self.price, "currency": self.currency}


@dataclass(frozen=True)
class SourceProfile:
    id: str
    display_name: str
    source_type: str | None
    alternate_titles: tuple[str, ...] = ()
    abbreviated_title: str | None = None
    canonical_aliases: tuple[str, ...] = ()
    homepage_url: str | None = None
    host_organization_name: str | None = None
    issn_l: str | None = None
    issn: tuple[str, ...] = ()
    is_oa: bool | None = None
    is_in_doaj: bool | None = None
    is_high_oa_rate: bool | None = None
    oa_flip_year: int | None = None
    apc_prices: tuple[ApcPrice, ...] = ()
    apc_usd: int | None = None
    two_year_mean_citedness: float | None = None
    works_count: int | None = None
    updated_date: str | None = None
    topics: tuple[SourceTopic, ...] = ()

    @property
    def aliases(self) -> tuple[str, ...]:
        values = [self.display_name, self.abbreviated_title or "", *self.alternate_titles, *self.canonical_aliases]
        return tuple(dict.fromkeys(" ".join(v.split()).strip() for v in values if v and v.strip()))

    def with_canonical_aliases(self, aliases: Iterable[str]) -> "SourceProfile":
        clean = tuple(dict.fromkeys(" ".join(str(x).split()).strip() for x in aliases if str(x).strip()))
        return replace(self, canonical_aliases=tuple(dict.fromkeys((*self.canonical_aliases, *clean))))

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "displayName": self.display_name,
            "type": self.source_type,
            "alternateTitles": list(self.alternate_titles),
            "abbreviatedTitle": self.abbreviated_title,
            "canonicalAliases": list(self.canonical_aliases),
            "homepageUrl": self.homepage_url,
            "hostOrganizationName": self.host_organization_name,
            "issnL": self.issn_l,
            "issn": list(self.issn),
            "isOa": self.is_oa,
            "isInDoaj": self.is_in_doaj,
            "isHighOaRate": self.is_high_oa_rate,
            "oaFlipYear": self.oa_flip_year,
            "apcPrices": [x.as_dict() for x in self.apc_prices],
            "apcUsd": self.apc_usd,
            "openalex2yrMeanCitedness": self.two_year_mean_citedness,
            "worksCount": self.works_count,
            "updatedDate": self.updated_date,
            "topics": [{"id": x.id, "name": x.name, "score": x.score} for x in self.topics],
        }


@dataclass(frozen=True)
class SourceHydrationResult:
    sources: dict[str, SourceProfile] = field(default_factory=dict)
    source_url: str = OPENALEX_SOURCES_URL
    error: str | None = None
    rate_limit: dict[str, Any] = field(default_factory=dict)


def _parse_work(item: Any) -> SemanticWork | None:
    if not isinstance(item, dict):
        return None
    work_id = _compact_id(str(item.get("id") or ""))
    title = str(item.get("title") or "").strip()
    if not work_id or not title:
        return None

    location = item.get("primary_location") or {}
    primary_source = location.get("source") if isinstance(location, dict) else None
    primary_source = primary_source if isinstance(primary_source, dict) else {}
    all_sources: list[dict[str, Any]] = []
    if primary_source:
        all_sources.append(primary_source)
    for loc in item.get("locations") or []:
        if not isinstance(loc, dict):
            continue
        candidate = loc.get("source")
        if isinstance(candidate, dict) and candidate.get("display_name"):
            all_sources.append(candidate)
    source = next((src for src in all_sources if str(src.get("type") or "").lower() not in {"repository", "preprint"}), primary_source)
    source_names = tuple(dict.fromkeys(str(src.get("display_name") or "").strip() for src in all_sources if str(src.get("display_name") or "").strip()))

    topic_names: list[str] = []
    topic_ids: list[str] = []
    topic_scores: list[float] = []
    for topic in item.get("topics") or []:
        if not isinstance(topic, dict):
            continue
        name = str(topic.get("display_name") or "").strip()
        topic_id = _compact_id(str(topic.get("id") or ""))
        if name:
            topic_names.append(name)
            topic_ids.append(topic_id)
            try:
                topic_scores.append(float(topic.get("score") or 0.0))
            except (TypeError, ValueError):
                topic_scores.append(0.0)
        if len(topic_names) >= 8:
            break

    keyword_names: list[str] = []
    for keyword in item.get("keywords") or []:
        if isinstance(keyword, dict) and keyword.get("display_name"):
            keyword_names.append(str(keyword["display_name"]))
        if len(keyword_names) >= 10:
            break

    try:
        year = int(item["publication_year"]) if item.get("publication_year") is not None else None
    except (TypeError, ValueError):
        year = None
    try:
        relevance = float(item["relevance_score"]) if item.get("relevance_score") is not None else None
    except (TypeError, ValueError):
        relevance = None

    doi = str(item.get("doi") or "").strip() or None
    return SemanticWork(
        id=work_id,
        title=title,
        year=year,
        relevance_score=relevance,
        doi=doi,
        source_id=_compact_id(str(source.get("id") or "")) or None,
        source_name=str(source.get("display_name") or "").strip() or None,
        source_type=str(source.get("type") or "").strip() or None,
        topics=tuple(topic_names),
        keywords=tuple(keyword_names),
        source_names=source_names,
        topic_ids=tuple(topic_ids),
        topic_scores=tuple(topic_scores),
    )


def _parse_source_topic(raw: Any) -> SourceTopic | None:
    if not isinstance(raw, dict):
        return None
    topic_obj = raw.get("topic") if isinstance(raw.get("topic"), dict) else {}
    topic_id = _compact_id(str(raw.get("id") or topic_obj.get("id") or ""))
    name = str(raw.get("display_name") or topic_obj.get("display_name") or "").strip()
    if not topic_id and not name:
        return None
    score_value = raw.get("score")
    if score_value is None:
        score_value = raw.get("share")
    if score_value is None:
        score_value = raw.get("count")
    try:
        score = float(score_value or 0.0)
    except (TypeError, ValueError):
        score = 0.0
    return SourceTopic(id=topic_id, name=name, score=score)


def _parse_source(item: Any) -> SourceProfile | None:
    if not isinstance(item, dict):
        return None
    source_id = _compact_id(str(item.get("id") or ""))
    display_name = str(item.get("display_name") or "").strip()
    if not source_id or not display_name:
        return None
    alternate = tuple(dict.fromkeys(" ".join(str(x).split()).strip() for x in (item.get("alternate_titles") or []) if str(x).strip()))
    abbreviated = str(item.get("abbreviated_title") or "").strip() or None
    # `topic_share` is more venue-specific than raw topic frequency when OpenAlex
    # provides it. Merge it first, then backfill with `topics`, deduplicating by
    # OpenAlex topic id/name. This keeps the recommender useful for broad venues
    # whose most frequent topics alone can be generic.
    topics: list[SourceTopic] = []
    seen_topics: set[str] = set()
    for bucket in (item.get("topic_share") or [], item.get("topics") or []):
        for raw in bucket:
            parsed = _parse_source_topic(raw)
            if parsed is None:
                continue
            key = parsed.id or parsed.name.casefold()
            if key in seen_topics:
                continue
            seen_topics.add(key)
            topics.append(parsed)
            if len(topics) >= 30:
                break
        if len(topics) >= 30:
            break
    try:
        apc = int(item["apc_usd"]) if item.get("apc_usd") is not None else None
    except (TypeError, ValueError):
        apc = None
    try:
        works_count = int(item["works_count"]) if item.get("works_count") is not None else None
    except (TypeError, ValueError):
        works_count = None
    apc_prices: list[ApcPrice] = []
    for raw in item.get("apc_prices") or []:
        if not isinstance(raw, dict):
            continue
        currency = str(raw.get("currency") or "").strip().upper()
        try:
            price = int(raw.get("price"))
        except (TypeError, ValueError):
            continue
        if currency and price >= 0:
            apc_prices.append(ApcPrice(price=price, currency=currency))
    summary = item.get("summary_stats") if isinstance(item.get("summary_stats"), dict) else {}
    try:
        two_year = float(summary.get("2yr_mean_citedness")) if summary.get("2yr_mean_citedness") is not None else None
    except (TypeError, ValueError):
        two_year = None
    try:
        flip_year = int(item.get("oa_flip_year")) if item.get("oa_flip_year") is not None else None
    except (TypeError, ValueError):
        flip_year = None
    issn = tuple(dict.fromkeys(str(x).strip() for x in (item.get("issn") or []) if str(x).strip()))
    return SourceProfile(
        id=source_id,
        display_name=display_name,
        source_type=str(item.get("type") or "").strip() or None,
        alternate_titles=alternate,
        abbreviated_title=abbreviated,
        homepage_url=str(item.get("homepage_url") or "").strip() or None,
        host_organization_name=str(item.get("host_organization_name") or "").strip() or None,
        issn_l=str(item.get("issn_l") or "").strip() or None,
        issn=issn,
        is_oa=item.get("is_oa") if isinstance(item.get("is_oa"), bool) else None,
        is_in_doaj=item.get("is_in_doaj") if isinstance(item.get("is_in_doaj"), bool) else None,
        is_high_oa_rate=item.get("is_high_oa_rate") if isinstance(item.get("is_high_oa_rate"), bool) else None,
        oa_flip_year=flip_year,
        apc_prices=tuple(apc_prices),
        apc_usd=apc,
        two_year_mean_citedness=two_year,
        works_count=works_count,
        updated_date=str(item.get("updated_date") or "").strip() or None,
        topics=tuple(topics),
    )


def _common_params(runtime: ScholarlyRuntime) -> dict[str, Any]:
    return {"api_key": runtime.openalex_api_key} if runtime.openalex_api_key.strip() else {}


def _headers() -> dict[str, str]:
    return {"User-Agent": "SuperScholar/3.11.0 scholarly-venue-recommender", "Accept": "application/json"}


async def rate_limit_status(client: httpx.AsyncClient, runtime: ScholarlyRuntime) -> dict[str, Any]:
    if not runtime.openalex_enabled:
        return {"ok": None, "status": "disabled", "message": "OpenAlex 已禁用"}
    try:
        response = await client.get(OPENALEX_RATE_LIMIT_URL, params=_common_params(runtime), headers=_headers(), follow_redirects=True)
        response.raise_for_status()
        payload = response.json() if response.content else {}
        authenticated = bool(runtime.openalex_api_key)
        return {
            "ok": True,
            "status": "ready" if authenticated else "limited",
            "message": "OpenAlex API Key 已认证，额度端点可访问" if authenticated else "OpenAlex 匿名访问可用，但额度更低；建议配置免费 API Key",
            "authenticated": authenticated,
            "rateLimit": {**_rate_limit_from_response(response), "payload": payload},
            "url": str(response.url),
        }
    except Exception as exc:
        return {"ok": False, "status": "error", "message": str(exc), "authenticated": bool(runtime.openalex_api_key)}


async def semantic_search(client: httpx.AsyncClient, query: str, runtime: ScholarlyRuntime) -> SemanticSearchResult:
    clean_query = " ".join(query.split()).strip()[:2000]
    if not runtime.openalex_enabled:
        return SemanticSearchResult(query=clean_query, works=[], source_url=OPENALEX_WORKS_URL, error="OpenAlex disabled")
    if not clean_query:
        return SemanticSearchResult(query="", works=[], source_url=OPENALEX_WORKS_URL, error="empty semantic query")

    params: dict[str, Any] = {
        "search.semantic": clean_query,
        "per_page": max(10, min(int(runtime.openalex_max_results), 50)),
        "select": "id,doi,title,publication_year,relevance_score,primary_location,locations,topics,keywords",
        **_common_params(runtime),
    }
    try:
        response = await client.get(OPENALEX_WORKS_URL, params=params, headers=_headers(), follow_redirects=True)
        response.raise_for_status()
        payload = response.json()
        works: list[SemanticWork] = []
        for item in payload.get("results") or []:
            parsed = _parse_work(item)
            if parsed is not None:
                works.append(parsed)
        return SemanticSearchResult(query=clean_query, works=works, source_url=str(response.url), rate_limit=_rate_limit_from_response(response))
    except Exception as exc:
        return SemanticSearchResult(query=clean_query, works=[], source_url=OPENALEX_WORKS_URL, error=str(exc))


async def hydrate_sources(client: httpx.AsyncClient, source_ids: Iterable[str], runtime: ScholarlyRuntime) -> SourceHydrationResult:
    ids = list(dict.fromkeys(_compact_id(str(x)) for x in source_ids if _compact_id(str(x))))[:100]
    if not runtime.openalex_enabled:
        return SourceHydrationResult(sources={}, source_url=OPENALEX_SOURCES_URL, error="OpenAlex disabled")
    if not ids:
        return SourceHydrationResult(sources={}, source_url=OPENALEX_SOURCES_URL)

    # `ids.openalex` is a documented Source filter. OpenAlex supports OR values
    # with `|`, so the common path hydrates all source identities in one request.
    # If a provider-side schema change or partial response omits an ID, we
    # conservatively resolve a bounded number through the documented single
    # entity endpoint `/sources/S…` rather than silently treating the missing
    # source as "no topics".
    openalex_values = "|".join(f"https://openalex.org/{sid}" for sid in ids)
    select = (
        "id,display_name,type,alternate_titles,abbreviated_title,homepage_url,"
        "host_organization_name,issn_l,issn,is_oa,is_in_doaj,is_high_oa_rate,oa_flip_year,"
        "apc_prices,apc_usd,summary_stats,works_count,updated_date,topics,topic_share"
    )
    params: dict[str, Any] = {
        "filter": f"ids.openalex:{openalex_values}",
        "per_page": min(100, len(ids)),
        "select": select,
        **_common_params(runtime),
    }
    sources: dict[str, SourceProfile] = {}
    errors: list[str] = []
    rate_limit: dict[str, Any] = {}
    source_url = OPENALEX_SOURCES_URL

    try:
        response = await client.get(OPENALEX_SOURCES_URL, params=params, headers=_headers(), follow_redirects=True)
        response.raise_for_status()
        source_url = str(response.url)
        rate_limit = _rate_limit_from_response(response)
        payload = response.json()
        for item in payload.get("results") or []:
            parsed = _parse_source(item)
            if parsed is not None:
                sources[parsed.id] = parsed
    except Exception as exc:
        errors.append(f"batch Source hydration failed: {exc}")

    missing = [sid for sid in ids if sid not in sources]
    # Normally this is zero. Keep fallback bounded because recommendation must not
    # explode into dozens of extra provider calls if the batch endpoint is down.
    for sid in missing[:12]:
        try:
            response = await client.get(
                f"{OPENALEX_SOURCES_URL}/{sid}",
                params={"select": select, **_common_params(runtime)},
                headers=_headers(),
                follow_redirects=True,
            )
            response.raise_for_status()
            parsed = _parse_source(response.json())
            if parsed is not None:
                sources[parsed.id] = parsed
            rate_limit = _rate_limit_from_response(response) or rate_limit
        except Exception as exc:
            errors.append(f"{sid}: {exc}")

    still_missing = [sid for sid in ids if sid not in sources]
    if still_missing:
        errors.append(f"resolved {len(sources)}/{len(ids)} requested OpenAlex Sources")
    error = "；".join(errors[:4]) or None
    return SourceHydrationResult(sources=sources, source_url=source_url, error=error, rate_limit=rate_limit)


@dataclass(frozen=True)
class SourceResolutionRequest:
    venue_id: str
    venue_type: str
    names: tuple[str, ...]
    issns: tuple[str, ...] = ()


@dataclass(frozen=True)
class CandidateSourceResolutionResult:
    matches: dict[str, SourceProfile] = field(default_factory=dict)
    confidence: dict[str, float] = field(default_factory=dict)
    attempted: int = 0
    resolved_with_topics: int = 0
    errors: tuple[str, ...] = ()
    rate_limit: dict[str, Any] = field(default_factory=dict)


def _source_select_fields() -> str:
    return (
        "id,display_name,type,alternate_titles,abbreviated_title,homepage_url,"
        "host_organization_name,issn_l,issn,is_oa,is_in_doaj,is_high_oa_rate,oa_flip_year,"
        "apc_prices,apc_usd,summary_stats,works_count,updated_date,topics,topic_share"
    )


def _name_tokens(value: str) -> set[str]:
    generic = {
        "acm", "ieee", "cvf", "international", "conference", "conferences", "journal",
        "journals", "proceedings", "symposium", "workshop", "annual", "transactions",
        "association", "society", "on", "of", "the", "for", "and", "in", "to", "with",
    }
    import re
    return {x for x in re.findall(r"[a-z0-9]+", value.lower()) if len(x) >= 2 and x not in generic}


def _compact_name(value: str) -> str:
    import re
    return "".join(re.findall(r"[a-z0-9]+", value.lower()))


def _is_acronym_name(value: str) -> bool:
    import re
    clean = value.strip()
    return bool(2 <= len(clean) <= 20 and re.fullmatch(r"[A-Z][A-Z0-9*+&/-]{1,19}", clean))


def _source_identity_score(request: SourceResolutionRequest, source: SourceProfile) -> float:
    expected = request.venue_type.lower()
    actual = str(source.source_type or "").lower()
    if expected == "journal" and actual != "journal":
        return 0.0
    if expected == "conference" and actual != "conference":
        return 0.0

    requested_issn = {x.replace("-", "").upper() for x in request.issns if x}
    source_issn = {x.replace("-", "").upper() for x in ((source.issn_l,) if source.issn_l else ()) + source.issn}
    if requested_issn and requested_issn & source_issn:
        return 1.0

    source_aliases = source.aliases
    best = 0.0
    for requested in request.names:
        requested = " ".join(requested.split()).strip()
        if not requested:
            continue
        rc = _compact_name(requested)
        rt = _name_tokens(requested)
        for alias in source_aliases:
            ac = _compact_name(alias)
            if not ac:
                continue
            if rc == ac:
                best = max(best, 1.0)
                continue
            if _is_acronym_name(requested) and any(requested.upper() == x.upper() for x in source_aliases):
                best = max(best, 0.99)
                continue
            if min(len(rc), len(ac)) >= 18 and (rc in ac or ac in rc):
                short, long = min(len(rc), len(ac)), max(len(rc), len(ac))
                if short / long >= 0.72:
                    best = max(best, 0.90)
            at = _name_tokens(alias)
            if not rt or not at:
                continue
            inter = len(rt & at)
            union = len(rt | at)
            if not union:
                continue
            min_shared = 2 if min(len(rt), len(at)) <= 3 else 3
            jaccard = inter / union
            if inter >= min_shared and jaccard >= 0.72:
                best = max(best, min(0.96, 0.68 + 0.32 * jaccard))
    return best


async def search_sources(
    client: httpx.AsyncClient,
    query: str,
    runtime: ScholarlyRuntime,
    *,
    source_type: str | None = None,
    limit: int = 8,
) -> tuple[list[SourceProfile], dict[str, Any]]:
    if not runtime.openalex_enabled:
        return [], {}
    clean = " ".join(query.split()).strip()[:300]
    if not clean:
        return [], {}
    params: dict[str, Any] = {
        "search": clean,
        "per_page": max(1, min(int(limit), 50)),
        "select": _source_select_fields(),
        **_common_params(runtime),
    }
    if source_type in {"journal", "conference"}:
        params["filter"] = f"type:{source_type}"
    response = await client.get(OPENALEX_SOURCES_URL, params=params, headers=_headers(), follow_redirects=True)
    response.raise_for_status()
    payload = response.json()
    output: list[SourceProfile] = []
    for item in payload.get("results") or []:
        parsed = _parse_source(item)
        if parsed is not None:
            output.append(parsed)
    return output, _rate_limit_from_response(response)


async def source_by_issn(client: httpx.AsyncClient, issn: str, runtime: ScholarlyRuntime) -> SourceProfile | None:
    if not runtime.openalex_enabled or not issn.strip():
        return None
    response = await client.get(
        f"{OPENALEX_SOURCES_URL}/issn:{issn.strip()}",
        params={"select": _source_select_fields(), **_common_params(runtime)},
        headers=_headers(),
        follow_redirects=True,
    )
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return _parse_source(response.json())


async def resolve_candidate_sources(
    client: httpx.AsyncClient,
    requests: Iterable[SourceResolutionRequest],
    runtime: ScholarlyRuntime,
    *,
    max_candidates: int = 36,
    min_confidence: float = 0.78,
) -> CandidateSourceResolutionResult:
    """Resolve catalog candidates to OpenAlex Sources without inventing identities.

    Journals prefer exact ISSN resolution. Remaining candidates use the documented
    `/sources?search=` endpoint, which searches display_name, alternate_titles, and
    abbreviated_title. A conservative local identity score and source-type match are
    required before attaching an OpenAlex Source ID.
    """
    import asyncio

    if not runtime.openalex_enabled:
        return CandidateSourceResolutionResult(errors=("OpenAlex disabled",))
    items = [r for r in requests if r.venue_id and r.names][:max_candidates]
    if not items:
        return CandidateSourceResolutionResult()

    semaphore = asyncio.Semaphore(6)

    async def resolve_one(req: SourceResolutionRequest) -> tuple[str, SourceProfile | None, float, str | None, dict[str, Any]]:
        try:
            async with semaphore:
                if req.venue_type == "journal":
                    for issn in req.issns[:2]:
                        source = await source_by_issn(client, issn, runtime)
                        if source is not None:
                            score = _source_identity_score(req, source)
                            if score >= min_confidence:
                                return req.venue_id, source, score, None, {}
                # Prefer the longest descriptive name; acronyms alone can be ambiguous.
                query = max(req.names, key=lambda x: len(x.strip()))
                hits, rate = await search_sources(client, query, runtime, source_type=req.venue_type, limit=8)
                scored = sorted(((_source_identity_score(req, source), source) for source in hits), key=lambda x: x[0], reverse=True)
                if scored and scored[0][0] >= min_confidence:
                    return req.venue_id, scored[0][1], scored[0][0], None, rate
                return req.venue_id, None, 0.0, None, rate
        except Exception as exc:
            return req.venue_id, None, 0.0, str(exc), {}

    resolved = await asyncio.gather(*(resolve_one(item) for item in items))
    matches: dict[str, SourceProfile] = {}
    confidence: dict[str, float] = {}
    errors: list[str] = []
    rate_limit: dict[str, Any] = {}
    for venue_id, source, score, error, rate in resolved:
        if source is not None:
            matches[venue_id] = source
            confidence[venue_id] = score
        if error:
            errors.append(f"{venue_id}: {error}")
        if rate:
            rate_limit = rate
    return CandidateSourceResolutionResult(
        matches=matches,
        confidence=confidence,
        attempted=len(items),
        resolved_with_topics=sum(1 for source in matches.values() if source.topics),
        errors=tuple(errors[:6]),
        rate_limit=rate_limit,
    )


async def test_openalex(client: httpx.AsyncClient, runtime: ScholarlyRuntime) -> dict[str, Any]:
    if not runtime.openalex_enabled:
        return {"status": "disabled", "ok": None, "checks": {}, "message": "OpenAlex 已禁用"}
    checks: dict[str, Any] = {}
    auth = await rate_limit_status(client, runtime)
    checks["authentication"] = auth

    semantic = await semantic_search(client, "surgical semantic segmentation boundary-aware medical imaging", runtime)
    checks["semanticWorks"] = {
        "ok": bool(semantic.works) and not semantic.error,
        "status": "ready" if semantic.works and not semantic.error else "error",
        "message": f"返回 {len(semantic.works)} 篇相似论文" if semantic.works else (semantic.error or "未返回相似论文"),
        "count": len(semantic.works),
        "rateLimit": semantic.rate_limit,
    }

    first_source = next((w.source_id for w in semantic.works if w.source_id), None)
    if first_source:
        hydrated = await hydrate_sources(client, [first_source], runtime)
        source = hydrated.sources.get(first_source)
        checks["sourceHydration"] = {
            "ok": source is not None,
            "status": "ready" if source is not None else "error",
            "message": f"成功解析 Source：{source.display_name}" if source else (hydrated.error or "Source 未解析"),
            "sourceId": first_source,
        }
        checks["sourceTopics"] = {
            "ok": bool(source and source.topics),
            "status": "ready" if source and source.topics else "degraded",
            "message": f"Source 提供 {len(source.topics)} 个聚合 topics" if source and source.topics else "Source 可解析，但当前样本未提供聚合 topics",
            "count": len(source.topics) if source else 0,
        }
        if source is not None and str(source.source_type or "").lower() in {"conference", "journal"}:
            probe = SourceResolutionRequest(
                venue_id="diagnostic-source",
                venue_type=str(source.source_type).lower(),
                names=source.aliases or (source.display_name,),
                issns=tuple(x for x in (((source.issn_l,) if source.issn_l else ()) + source.issn) if x),
            )
            resolved_probe = await resolve_candidate_sources(
                client, [probe], runtime, max_candidates=1, min_confidence=0.78
            )
            resolved = resolved_probe.matches.get("diagnostic-source")
            checks["candidateSourceResolution"] = {
                "ok": resolved is not None,
                "status": "ready" if resolved is not None else "degraded",
                "message": (
                    f"候选 Venue → Source 解析链可用：{resolved.display_name}"
                    if resolved is not None
                    else "Source hydration 可用，但候选 Venue → Source 名称/ISSN 解析未达到保守身份阈值"
                ),
                "confidence": resolved_probe.confidence.get("diagnostic-source"),
            }
        else:
            checks["candidateSourceResolution"] = {
                "ok": None,
                "status": "not_applicable",
                "message": f"诊断样本 Source 类型 {source.source_type if source else 'unknown'} 不属于 journal/conference 候选解析范围",
            }
    else:
        checks["sourceHydration"] = {"ok": False, "status": "error", "message": "相似论文没有可解析的 primary Source"}
        checks["sourceTopics"] = {"ok": False, "status": "degraded", "message": "无法测试 Source topics"}
        checks["candidateSourceResolution"] = {"ok": False, "status": "degraded", "message": "无法测试候选 Venue → OpenAlex Source 解析"}

    required = [checks["semanticWorks"].get("ok") is True, checks["sourceHydration"].get("ok") is True]
    if checks["candidateSourceResolution"].get("ok") is not None:
        required.append(checks["candidateSourceResolution"].get("ok") is True)
    ok = all(required)
    authenticated = bool(runtime.openalex_api_key)
    return {
        "status": ("ready" if authenticated else "limited") if ok else "degraded",
        "ok": ok,
        "authenticated": authenticated,
        "checks": checks,
        "message": (
            "OpenAlex Works + Sources + 候选 Venue Source 解析主链路可用" if authenticated
            else "OpenAlex Works + Sources + 候选 Venue Source 解析可用，但当前为匿名额度；建议配置免费 API Key"
        ) if ok else "OpenAlex 部分能力不可用，请查看分项诊断",
    }

# ---------------------------------------------------------------------------
# V3.10 venue-conditioned retrieval and conference-series resolution
# ---------------------------------------------------------------------------

EXCLUDED_CONFERENCE_SOURCE_TERMS = (
    "workshop", "workshops", "companion", "doctoral consortium", "demo track",
    "demonstration track", "tutorial", "tutorials", "poster session", "short papers",
    "industry track", "student research", "adjunct proceedings", "supplemental proceedings",
)


@dataclass(frozen=True)
class CandidateSeriesResolutionResult:
    matches: dict[str, tuple[SourceProfile, ...]] = field(default_factory=dict)
    confidence: dict[str, tuple[float, ...]] = field(default_factory=dict)
    attempted: int = 0
    errors: tuple[str, ...] = ()
    rate_limit: dict[str, Any] = field(default_factory=dict)


def _looks_like_excluded_conference_source(source: SourceProfile) -> bool:
    hay = " ".join(source.aliases).casefold()
    return any(term in hay for term in EXCLUDED_CONFERENCE_SOURCE_TERMS)


def _conference_source_year(source: SourceProfile) -> int | None:
    import re
    years: list[int] = []
    for alias in source.aliases:
        for value in re.findall(r"\b(20\d{2})\b", alias):
            year = int(value)
            if 2000 <= year <= 2100:
                years.append(year)
    return max(years) if years else None


async def resolve_candidate_source_series(
    client: httpx.AsyncClient,
    requests: Iterable[SourceResolutionRequest],
    runtime: ScholarlyRuntime,
    *,
    max_candidates: int = 30,
    min_confidence: float = 0.78,
    max_sources_per_conference: int = 6,
) -> CandidateSeriesResolutionResult:
    """Resolve journals to one Source and conferences to a recent Source series.

    OpenAlex can model conferences as yearly proceedings Sources rather than one eternal
    venue identity. V3.10 therefore keeps multiple high-confidence recent proceedings
    Sources for a conference series. Workshop/companion/tutorial variants are rejected.
    No identity is attached when the local confidence threshold is not met.
    """
    import asyncio

    if not runtime.openalex_enabled:
        return CandidateSeriesResolutionResult(errors=("OpenAlex disabled",))
    items = [r for r in requests if r.venue_id and r.names][:max_candidates]
    if not items:
        return CandidateSeriesResolutionResult()

    semaphore = asyncio.Semaphore(4)

    async def resolve_one(req: SourceResolutionRequest):
        try:
            async with semaphore:
                if req.venue_type == "journal":
                    # Exact ISSN first, then conservative Source search.
                    for issn in req.issns[:3]:
                        source = await source_by_issn(client, issn, runtime)
                        if source is not None:
                            score = _source_identity_score(req, source)
                            if score >= min_confidence:
                                return req.venue_id, (source,), (score,), None, {}
                    query = max(req.names, key=lambda x: len(x.strip()))
                    hits, rate = await search_sources(client, query, runtime, source_type="journal", limit=10)
                    scored = sorted(
                        ((_source_identity_score(req, source), source) for source in hits),
                        key=lambda x: x[0], reverse=True,
                    )
                    if scored and scored[0][0] >= min_confidence:
                        return req.venue_id, (scored[0][1],), (scored[0][0],), None, rate
                    return req.venue_id, (), (), None, rate

                # Conference: query both long name and acronym when available because OpenAlex
                # yearly proceedings often place the year before the canonical conference name.
                queries = list(dict.fromkeys(sorted(req.names, key=lambda x: len(x.strip()), reverse=True)[:3]))
                candidates: dict[str, tuple[float, SourceProfile]] = {}
                rate_limit: dict[str, Any] = {}
                for query in queries:
                    hits, rate = await search_sources(client, query, runtime, source_type="conference", limit=18)
                    if rate:
                        rate_limit = rate
                    for source in hits:
                        if _looks_like_excluded_conference_source(source):
                            continue
                        score = _source_identity_score(req, source)
                        if score < min_confidence:
                            continue
                        prev = candidates.get(source.id)
                        if prev is None or score > prev[0]:
                            candidates[source.id] = (score, source)
                ranked = sorted(
                    candidates.values(),
                    key=lambda pair: (_conference_source_year(pair[1]) or 0, pair[0], pair[1].works_count or 0),
                    reverse=True,
                )[:max_sources_per_conference]
                return (
                    req.venue_id,
                    tuple(source for _, source in ranked),
                    tuple(score for score, _ in ranked),
                    None,
                    rate_limit,
                )
        except Exception as exc:
            return req.venue_id, (), (), str(exc), {}

    resolved = await asyncio.gather(*(resolve_one(item) for item in items))
    matches: dict[str, tuple[SourceProfile, ...]] = {}
    confidence: dict[str, tuple[float, ...]] = {}
    errors: list[str] = []
    rate_limit: dict[str, Any] = {}
    for venue_id, sources, scores, error, rate in resolved:
        if sources:
            matches[venue_id] = sources
            confidence[venue_id] = scores
        if error:
            errors.append(f"{venue_id}: {error}")
        if rate:
            rate_limit = rate
    return CandidateSeriesResolutionResult(
        matches=matches,
        confidence=confidence,
        attempted=len(items),
        errors=tuple(errors),
        rate_limit=rate_limit,
    )


async def semantic_search_within_sources(
    client: httpx.AsyncClient,
    query: str,
    source_ids: Iterable[str],
    runtime: ScholarlyRuntime,
    *,
    from_year: int | None = None,
    limit: int = 8,
) -> SemanticSearchResult:
    """Semantic-search the manuscript query inside one resolved venue/series.

    This is the principal V3.10 venue-fit verification signal. It asks whether the
    candidate venue itself has published semantically close work recently, rather than
    inferring fit from a broad Source topic histogram.
    """
    from datetime import datetime, timezone

    clean_query = " ".join(query.split()).strip()[:2000]
    ids = list(dict.fromkeys(_compact_id(str(x)) for x in source_ids if _compact_id(str(x))))[:20]
    if not runtime.openalex_enabled:
        return SemanticSearchResult(query=clean_query, works=[], source_url=OPENALEX_WORKS_URL, error="OpenAlex disabled")
    if not clean_query:
        return SemanticSearchResult(query="", works=[], source_url=OPENALEX_WORKS_URL, error="empty semantic query")
    if not ids:
        return SemanticSearchResult(query=clean_query, works=[], source_url=OPENALEX_WORKS_URL, error="candidate venue has no verified OpenAlex Source identity")
    start_year = int(from_year or (datetime.now(timezone.utc).year - 4))
    source_filter = "|".join(ids)
    params: dict[str, Any] = {
        "search.semantic": clean_query,
        "filter": f"primary_location.source.id:{source_filter},from_publication_date:{start_year}-01-01",
        "per_page": max(1, min(int(limit), 20)),
        "select": "id,doi,title,publication_year,relevance_score,primary_location,locations,topics,keywords",
        **_common_params(runtime),
    }
    try:
        response = await client.get(OPENALEX_WORKS_URL, params=params, headers=_headers(), follow_redirects=True)
        response.raise_for_status()
        payload = response.json()
        works: list[SemanticWork] = []
        for item in payload.get("results") or []:
            parsed = _parse_work(item)
            if parsed is not None:
                works.append(parsed)
        return SemanticSearchResult(
            query=clean_query,
            works=works,
            source_url=str(response.url),
            rate_limit=_rate_limit_from_response(response),
        )
    except Exception as exc:
        return SemanticSearchResult(query=clean_query, works=[], source_url=OPENALEX_WORKS_URL, error=str(exc))
