from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Iterable

import httpx

from .scholarly_settings import ScholarlyRuntime

BASE_URL = "https://api.clarivate.com/apis/wos-journals/v1"
JOURNALS_URL = f"{BASE_URL}/journals"
DEVELOPER_URL = "https://developer.clarivate.com/apis/wos-journal"


def _compact(value: str) -> str:
    return "".join(re.findall(r"[a-z0-9]+", value.casefold()))


def _tokens(value: str) -> set[str]:
    generic = {"the", "of", "and", "in", "on", "for", "journal", "international", "transactions", "letters"}
    return {x for x in re.findall(r"[a-z0-9]+", value.casefold()) if len(x) >= 2 and x not in generic}


def _as_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class ClarivateRank:
    category: str | None
    edition: str | None
    rank: str | None
    quartile: str | None

    def as_dict(self) -> dict[str, Any]:
        return {"category": self.category, "edition": self.edition, "rank": self.rank, "quartile": self.quartile}


@dataclass(frozen=True)
class ClarivateJournalProfile:
    id: str
    name: str
    impact_factor: float | None = None
    jci: float | None = None
    ranks: tuple[ClarivateRank, ...] = ()
    jcr_year: int | None = None
    source_url: str = JOURNALS_URL

    @property
    def wos_indexes(self) -> tuple[str, ...]:
        allowed = {"SCIE", "SSCI", "AHCI", "ESCI"}
        return tuple(dict.fromkeys(x.edition for x in self.ranks if x.edition in allowed))

    @property
    def quartiles(self) -> tuple[str, ...]:
        allowed = {"Q1", "Q2", "Q3", "Q4"}
        return tuple(dict.fromkeys(x.quartile for x in self.ranks if x.quartile in allowed))

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "impactFactor": self.impact_factor,
            "jci": self.jci,
            "wosIndexes": list(self.wos_indexes),
            "jcrQuartiles": list(self.quartiles),
            "ranks": [x.as_dict() for x in self.ranks],
            "jcrYear": self.jcr_year,
            "sourceUrl": self.source_url,
        }


@dataclass(frozen=True)
class ClarivateBatchResult:
    profiles: dict[str, ClarivateJournalProfile] = field(default_factory=dict)
    attempted: int = 0
    errors: tuple[str, ...] = ()


def _headers(runtime: ScholarlyRuntime) -> dict[str, str]:
    return {
        "Accept": "application/json",
        "X-ApiKey": runtime.clarivate_api_key,
        "User-Agent": "SuperScholar/3.11.0 journal-metadata-enrichment",
    }


def _identity_score(name: str, issns: Iterable[str], hit: dict[str, Any]) -> float:
    hit_name = str(hit.get("name") or "").strip()
    if not hit_name:
        return 0.0
    a, b = _compact(name), _compact(hit_name)
    if a and a == b:
        return 1.0
    ta, tb = _tokens(name), _tokens(hit_name)
    if ta and tb:
        overlap = len(ta & tb) / max(1, len(ta | tb))
        if overlap >= 0.82:
            return 0.95
        if overlap >= 0.70 and len(ta & tb) >= 3:
            return 0.88
    # Clarivate search may include matches metadata. An exact ISSN match in the
    # returned highlights is stronger than fuzzy title text, but never invent it.
    expected = {str(x).replace("-", "").upper() for x in issns if x}
    match_values: list[str] = []
    for item in hit.get("matches") or []:
        if isinstance(item, dict):
            match_values.extend(str(v) for v in item.values() if isinstance(v, (str, int)))
    hay = " ".join(match_values).replace("-", "").upper()
    if expected and any(x in hay for x in expected):
        return 0.99
    return 0.0


def _parse_profile(hit: dict[str, Any], source_url: str) -> ClarivateJournalProfile | None:
    if not isinstance(hit, dict):
        return None
    name = str(hit.get("name") or "").strip()
    journal_id = str(hit.get("id") or "").strip()
    if not name or not journal_id:
        return None
    metrics = hit.get("metrics") if isinstance(hit.get("metrics"), dict) else {}
    impact = metrics.get("impactMetrics") if isinstance(metrics.get("impactMetrics"), dict) else {}
    jif = _as_float(impact.get("jif"))
    jci = _as_float(impact.get("jci"))
    rank_root = hit.get("ranks") if isinstance(hit.get("ranks"), dict) else {}
    ranks: list[ClarivateRank] = []
    for raw in rank_root.get("jif") or []:
        if not isinstance(raw, dict):
            continue
        edition = str(raw.get("edition") or "").strip().upper() or None
        quartile = str(raw.get("quartile") or "").strip().upper() or None
        ranks.append(ClarivateRank(
            category=str(raw.get("category") or "").strip() or None,
            edition=edition,
            rank=str(raw.get("rank") or "").strip() or None,
            quartile=quartile,
        ))
    reports = hit.get("journalCitationReports") if isinstance(hit.get("journalCitationReports"), list) else []
    years: list[int] = []
    for report in reports:
        if not isinstance(report, dict):
            continue
        year = _as_int(report.get("year") or report.get("jcrYear"))
        if year:
            years.append(year)
    return ClarivateJournalProfile(
        id=journal_id,
        name=name,
        impact_factor=jif,
        jci=jci,
        ranks=tuple(ranks),
        jcr_year=max(years) if years else None,
        source_url=source_url,
    )


def _merge_report(profile: ClarivateJournalProfile, payload: dict[str, Any], source_url: str) -> ClarivateJournalProfile:
    metrics = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else {}
    impact = metrics.get("impactMetrics") if isinstance(metrics.get("impactMetrics"), dict) else {}
    jif = _as_float(impact.get("jif"))
    jci = _as_float(impact.get("jci"))
    rank_root = payload.get("ranks") if isinstance(payload.get("ranks"), dict) else {}
    ranks: list[ClarivateRank] = []
    for raw in rank_root.get("jif") or []:
        if not isinstance(raw, dict):
            continue
        ranks.append(ClarivateRank(
            category=str(raw.get("category") or "").strip() or None,
            edition=str(raw.get("edition") or "").strip().upper() or None,
            rank=str(raw.get("rank") or "").strip() or None,
            quartile=str(raw.get("quartile") or "").strip().upper() or None,
        ))
    year = _as_int(payload.get("year"))
    return ClarivateJournalProfile(
        id=profile.id, name=profile.name,
        impact_factor=jif if jif is not None else profile.impact_factor,
        jci=jci if jci is not None else profile.jci,
        ranks=tuple(ranks) if ranks else profile.ranks,
        jcr_year=year or profile.jcr_year, source_url=source_url,
    )


async def _latest_report(client: httpx.AsyncClient, profile: ClarivateJournalProfile, runtime: ScholarlyRuntime) -> ClarivateJournalProfile:
    # JCR report years refer to the cited-data year; in a calendar-year release the
    # latest normally available year is current_year-1. Try that first and then one
    # year back to tolerate release timing without inventing a metric.
    from datetime import datetime, timezone
    start = datetime.now(timezone.utc).year - 1
    for year in (start, start - 1):
        response = await client.get(
            f"{JOURNALS_URL}/{profile.id}/reports/year/{year}",
            headers=_headers(runtime), follow_redirects=True,
        )
        if response.status_code == 404:
            continue
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict):
            return _merge_report(profile, payload, str(response.url))
    return profile


async def resolve_journal(
    client: httpx.AsyncClient,
    *,
    name: str,
    issns: Iterable[str],
    runtime: ScholarlyRuntime,
) -> ClarivateJournalProfile | None:
    if not runtime.clarivate_enabled or not runtime.clarivate_api_key.strip():
        return None
    queries = [x for x in dict.fromkeys([*(str(i).strip() for i in issns if str(i).strip()), name.strip()]) if x]
    best: tuple[float, ClarivateJournalProfile] | None = None
    for query in queries[:3]:
        response = await client.get(
            JOURNALS_URL,
            params={"q": query, "limit": 10, "page": 1},
            headers=_headers(runtime),
            follow_redirects=True,
        )
        response.raise_for_status()
        payload = response.json()
        for hit in payload.get("hits") or []:
            if not isinstance(hit, dict):
                continue
            score = _identity_score(name, issns, hit)
            if score < 0.88:
                continue
            profile = _parse_profile(hit, str(response.url))
            if profile is not None and (best is None or score > best[0]):
                best = (score, profile)
        if best and best[0] >= 0.99:
            break
    if best is None:
        return None
    return await _latest_report(client, best[1], runtime)


async def resolve_journals(
    client: httpx.AsyncClient,
    venues: Iterable[dict[str, Any]],
    runtime: ScholarlyRuntime,
    *,
    limit: int | None = None,
) -> ClarivateBatchResult:
    import asyncio

    if not runtime.clarivate_enabled:
        return ClarivateBatchResult(errors=("Clarivate disabled",))
    if not runtime.clarivate_api_key.strip():
        return ClarivateBatchResult(errors=("Clarivate API key not configured",))
    rows = [v for v in venues if v.get("type") == "journal"][: max(1, int(limit or runtime.clarivate_journal_limit))]
    semaphore = asyncio.Semaphore(4)

    async def one(venue: dict[str, Any]):
        name = str(venue.get("name") or venue.get("shortName") or "").strip()
        raw_issn = venue.get("issn") or []
        if isinstance(raw_issn, str):
            raw_issn = [raw_issn]
        issns = tuple(dict.fromkeys(str(x).strip() for x in ([venue.get("issnL")] + list(raw_issn)) if x and str(x).strip()))
        try:
            async with semaphore:
                return str(venue.get("id") or ""), await resolve_journal(client, name=name, issns=issns, runtime=runtime), None
        except Exception as exc:
            return str(venue.get("id") or ""), None, str(exc)

    results = await asyncio.gather(*(one(v) for v in rows))
    profiles: dict[str, ClarivateJournalProfile] = {}
    errors: list[str] = []
    for venue_id, profile, error in results:
        if profile is not None:
            profiles[venue_id] = profile
        if error:
            errors.append(f"{venue_id}: {error}")
    return ClarivateBatchResult(profiles=profiles, attempted=len(rows), errors=tuple(errors[:8]))


async def test_clarivate(client: httpx.AsyncClient, runtime: ScholarlyRuntime) -> dict[str, Any]:
    if not runtime.clarivate_enabled:
        return {"status": "disabled", "ok": None, "message": "Clarivate WoS Journals API 已禁用"}
    if not runtime.clarivate_api_key.strip():
        return {
            "status": "degraded", "ok": False,
            "message": "已启用 Clarivate，但尚未配置有权限的 Web of Science Journals API Key",
            "helpUrl": DEVELOPER_URL,
        }
    try:
        response = await client.get(
            JOURNALS_URL,
            params={"q": "Nature Genetics", "limit": 1, "page": 1},
            headers=_headers(runtime), follow_redirects=True,
        )
        response.raise_for_status()
        payload = response.json()
        hits = payload.get("hits") or []
        return {
            "status": "ready" if hits else "degraded",
            "ok": bool(hits),
            "message": "Clarivate Web of Science Journals API 已认证，可查询 JIF/JCR/WoS edition" if hits else "Clarivate API 已响应，但诊断查询未返回期刊",
            "checks": {
                "journals": {"ok": bool(hits), "status": "ready" if hits else "degraded", "message": f"诊断查询返回 {len(hits)} 个 journal record"}
            },
            "helpUrl": DEVELOPER_URL,
        }
    except httpx.HTTPStatusError as exc:
        code = exc.response.status_code
        message = "API Key 无效或未获 WoS Journals API 权限" if code in {401, 403} else f"Clarivate HTTP {code}"
        return {"status": "error", "ok": False, "message": message, "statusCode": code, "helpUrl": DEVELOPER_URL}
    except Exception as exc:
        return {"status": "error", "ok": False, "message": str(exc), "helpUrl": DEVELOPER_URL}
