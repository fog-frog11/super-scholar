from __future__ import annotations

from dataclasses import dataclass
import asyncio
import re
from typing import Any, Iterable

import httpx

from .openalex import SourceProfile
from .scholarly_settings import ScholarlyRuntime

DBLP_VENUE_SEARCH_URL = "https://dblp.org/search/venue/api"

_GENERIC = {
    "acm", "ieee", "cvf", "international", "conference", "journal", "symposium", "workshop",
    "proceedings", "annual", "on", "of", "the", "for", "and", "in", "computer", "computing",
}


@dataclass(frozen=True)
class DblpVenue:
    name: str
    acronym: str | None
    venue_type: str | None
    url: str | None

    @property
    def aliases(self) -> tuple[str, ...]:
        values = [self.name, self.acronym or ""]
        return tuple(dict.fromkeys(" ".join(x.split()).strip() for x in values if x and x.strip()))


def _tokens(text: str) -> set[str]:
    return {x for x in re.findall(r"[a-z0-9]+", text.lower()) if len(x) >= 2 and x not in _GENERIC}


def _compact(text: str) -> str:
    return "".join(re.findall(r"[a-z0-9]+", text.lower()))


def _similarity(query: str, venue: DblpVenue) -> float:
    q = _compact(query)
    if not q:
        return 0.0
    for alias in venue.aliases:
        a = _compact(alias)
        if q == a:
            return 1.0
        if len(q) <= 12 and query.upper() == query and venue.acronym and query.upper() == venue.acronym.upper():
            return 1.0
    qt = _tokens(query)
    vt = _tokens(" ".join(venue.aliases))
    if not qt or not vt:
        return 0.0
    inter = len(qt & vt)
    union = len(qt | vt)
    if inter < 2:
        return 0.0
    return inter / union if union else 0.0


def _parse_hit(raw: Any) -> DblpVenue | None:
    if not isinstance(raw, dict):
        return None
    info = raw.get("info") if isinstance(raw.get("info"), dict) else {}
    name = str(info.get("venue") or "").strip()
    if not name:
        return None
    return DblpVenue(
        name=name,
        acronym=str(info.get("acronym") or "").strip() or None,
        venue_type=str(info.get("type") or "").strip() or None,
        url=str(info.get("url") or "").strip() or None,
    )


async def search_venues(client: httpx.AsyncClient, query: str, runtime: ScholarlyRuntime, *, limit: int = 5) -> list[DblpVenue]:
    if not runtime.dblp_enabled:
        return []
    clean = " ".join(query.split()).strip()[:240]
    if not clean:
        return []
    response = await client.get(
        DBLP_VENUE_SEARCH_URL,
        params={"q": clean, "format": "json", "h": max(1, min(limit, 20)), "f": 0, "c": 0},
        headers={"Accept": "application/json", "User-Agent": "SuperScholar/3.11.0 scholarly-venue-recommender"},
        follow_redirects=True,
    )
    response.raise_for_status()
    payload = response.json()
    hits = (((payload.get("result") or {}).get("hits") or {}).get("hit") or []) if isinstance(payload, dict) else []
    if isinstance(hits, dict):
        hits = [hits]
    output: list[DblpVenue] = []
    for hit in hits:
        parsed = _parse_hit(hit)
        if parsed is not None:
            output.append(parsed)
    return output


async def canonicalize_sources(
    client: httpx.AsyncClient,
    sources: dict[str, SourceProfile],
    runtime: ScholarlyRuntime,
    *,
    limit: int = 10,
) -> tuple[dict[str, SourceProfile], dict[str, DblpVenue], str | None]:
    if not runtime.dblp_enabled:
        return sources, {}, "DBLP disabled"
    updated = dict(sources)
    matches: dict[str, DblpVenue] = {}
    errors: list[str] = []
    candidates = [s for s in sources.values() if str(s.source_type or "").lower() == "conference"][:limit]
    semaphore = asyncio.Semaphore(3)

    async def resolve(source: SourceProfile) -> tuple[str, DblpVenue | None, str | None]:
        query = source.abbreviated_title or source.display_name
        try:
            async with semaphore:
                hits = await search_venues(client, query, runtime, limit=5)
        except Exception as exc:
            return source.id, None, str(exc)
        scored = sorted(((_similarity(query, hit), hit) for hit in hits), key=lambda x: x[0], reverse=True)
        if not scored or scored[0][0] < 0.58:
            return source.id, None, None
        return source.id, scored[0][1], None

    resolved = await asyncio.gather(*(resolve(source) for source in candidates)) if candidates else []
    for source_id, hit, error in resolved:
        if error:
            errors.append(f"{source_id}: {error}")
            continue
        if hit is None:
            continue
        source = sources[source_id]
        matches[source_id] = hit
        updated[source_id] = source.with_canonical_aliases(hit.aliases)
    return updated, matches, ("；".join(errors[:3]) if errors and not matches else None)


async def test_dblp(client: httpx.AsyncClient, runtime: ScholarlyRuntime) -> dict[str, Any]:
    if not runtime.dblp_enabled:
        return {"status": "disabled", "ok": None, "checks": {}, "message": "DBLP 已禁用"}
    try:
        hits = await search_venues(client, "CVPR", runtime, limit=3)
        ok = bool(hits)
        first = hits[0] if hits else None
        return {
            "status": "ready" if ok else "degraded",
            "ok": ok,
            "checks": {
                "venueSearch": {
                    "ok": ok,
                    "status": "ready" if ok else "degraded",
                    "message": f"Venue Search 返回 {len(hits)} 个结果" + (f"；首项：{first.name}" if first else ""),
                    "count": len(hits),
                }
            },
            "message": "DBLP Venue Search 可用" if ok else "DBLP Venue Search 未返回结果",
        }
    except Exception as exc:
        return {"status": "error", "ok": False, "checks": {}, "message": str(exc)}
