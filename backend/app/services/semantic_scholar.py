from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx

from .scholarly_settings import ScholarlyRuntime

S2_GRAPH_BASE = "https://api.semanticscholar.org/graph/v1"


@dataclass(frozen=True)
class SemanticScholarPaper:
    paper_id: str
    title: str
    year: int | None
    venue: str | None
    publication_venue_name: str | None
    publication_venue_id: str | None
    publication_venue_type: str | None
    alternate_venue_names: tuple[str, ...] = ()
    external_ids: dict[str, str] = field(default_factory=dict)
    fields_of_study: tuple[str, ...] = ()
    url: str | None = None

    @property
    def venue_names(self) -> tuple[str, ...]:
        values = [self.publication_venue_name or "", self.venue or "", *self.alternate_venue_names]
        return tuple(dict.fromkeys(" ".join(x.split()).strip() for x in values if x and x.strip()))

    def as_dict(self) -> dict[str, Any]:
        return {
            "paperId": self.paper_id,
            "title": self.title,
            "year": self.year,
            "venue": self.venue,
            "publicationVenueName": self.publication_venue_name,
            "publicationVenueId": self.publication_venue_id,
            "publicationVenueType": self.publication_venue_type,
            "alternateVenueNames": list(self.alternate_venue_names),
            "externalIds": self.external_ids,
            "fieldsOfStudy": list(self.fields_of_study),
            "url": self.url,
        }


@dataclass(frozen=True)
class SemanticScholarSearchResult:
    query: str
    papers: list[SemanticScholarPaper]
    source_url: str
    error: str | None = None
    error_kind: str | None = None
    status_code: int | None = None


def _headers(runtime: ScholarlyRuntime) -> dict[str, str]:
    headers = {"Accept": "application/json", "User-Agent": "SuperScholar/3.11.0 scholarly-venue-recommender"}
    if runtime.semantic_scholar_api_key:
        headers["x-api-key"] = runtime.semantic_scholar_api_key
    return headers


def _parse_paper(item: Any) -> SemanticScholarPaper | None:
    if not isinstance(item, dict):
        return None
    paper_id = str(item.get("paperId") or "").strip()
    title = str(item.get("title") or "").strip()
    if not paper_id or not title:
        return None
    publication_venue = item.get("publicationVenue") if isinstance(item.get("publicationVenue"), dict) else {}
    alternate = publication_venue.get("alternate_names") or publication_venue.get("alternateNames") or []
    try:
        year = int(item.get("year")) if item.get("year") is not None else None
    except (TypeError, ValueError):
        year = None
    external = item.get("externalIds") if isinstance(item.get("externalIds"), dict) else {}
    return SemanticScholarPaper(
        paper_id=paper_id,
        title=title,
        year=year,
        venue=str(item.get("venue") or "").strip() or None,
        publication_venue_name=str(publication_venue.get("name") or "").strip() or None,
        publication_venue_id=str(publication_venue.get("id") or "").strip() or None,
        publication_venue_type=str(publication_venue.get("type") or "").strip() or None,
        alternate_venue_names=tuple(dict.fromkeys(str(x).strip() for x in alternate if str(x).strip())),
        external_ids={str(k): str(v) for k, v in external.items() if v is not None},
        fields_of_study=tuple(str(x) for x in (item.get("fieldsOfStudy") or []) if str(x).strip()),
        url=str(item.get("url") or "").strip() or None,
    )


async def search_papers(client: httpx.AsyncClient, query: str, runtime: ScholarlyRuntime, *, limit: int = 20) -> SemanticScholarSearchResult:
    clean = " ".join(query.split()).strip()[:500]
    url = f"{S2_GRAPH_BASE}/paper/search"
    if not runtime.semantic_scholar_enabled:
        return SemanticScholarSearchResult(query=clean, papers=[], source_url=url, error="Semantic Scholar disabled")
    if not clean:
        return SemanticScholarSearchResult(query="", papers=[], source_url=url, error="empty query")
    params = {
        "query": clean,
        "limit": max(1, min(limit, 100)),
        "fields": "paperId,title,year,venue,publicationVenue,externalIds,fieldsOfStudy,url",
    }
    try:
        response = await client.get(url, params=params, headers=_headers(runtime), follow_redirects=True)
        response.raise_for_status()
        payload = response.json()
        papers: list[SemanticScholarPaper] = []
        for item in payload.get("data") or []:
            parsed = _parse_paper(item)
            if parsed is not None:
                papers.append(parsed)
        return SemanticScholarSearchResult(query=clean, papers=papers, source_url=str(response.url))
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        kind = "rate_limited" if status == 429 else "authentication" if status in {401, 403} else "http_error"
        if status == 429 and not runtime.semantic_scholar_api_key:
            message = "Semantic Scholar 匿名公共请求池触发 429 限流；建议申请并配置官方 API Key"
        elif status == 429:
            message = "Semantic Scholar API Key 已配置，但当前请求触发 429 限流；请降低请求频率或等待额度恢复"
        elif status in {401, 403}:
            message = "Semantic Scholar API Key 无效或当前账户无权访问该 endpoint"
        else:
            message = f"Semantic Scholar HTTP {status}: {exc.response.text[:300]}"
        return SemanticScholarSearchResult(query=clean, papers=[], source_url=str(exc.request.url), error=message, error_kind=kind, status_code=status)
    except Exception as exc:
        return SemanticScholarSearchResult(query=clean, papers=[], source_url=url, error=str(exc), error_kind="transport")


async def test_semantic_scholar(client: httpx.AsyncClient, runtime: ScholarlyRuntime) -> dict[str, Any]:
    if not runtime.semantic_scholar_enabled:
        return {"status": "disabled", "ok": None, "checks": {}, "message": "Semantic Scholar 已禁用"}
    result = await search_papers(client, "surgical semantic segmentation", runtime, limit=3)
    ok = bool(result.papers) and not result.error
    status = "ready" if ok else ("limited" if result.error_kind == "rate_limited" else "degraded")
    return {
        "status": status,
        "ok": ok,
        "authenticated": bool(runtime.semantic_scholar_api_key),
        "checks": {
            "paperSearch": {
                "ok": ok,
                "status": "ready" if ok else ("limited" if result.error_kind == "rate_limited" else "degraded"),
                "message": f"Paper Search 返回 {len(result.papers)} 条记录" if ok else (result.error or "未返回记录"),
                "count": len(result.papers),
                "statusCode": result.status_code,
                "errorKind": result.error_kind,
            }
        },
        "message": "Semantic Scholar 论文检索可用" if ok else "Semantic Scholar 本轮检索不可用",
    }
