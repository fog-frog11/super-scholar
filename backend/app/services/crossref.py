from __future__ import annotations

from dataclasses import dataclass
import asyncio
from typing import Any, Iterable

import httpx

from .scholarly_settings import ScholarlyRuntime

CROSSREF_BASE_URL = "https://api.crossref.org"


@dataclass(frozen=True)
class CrossrefJournalProfile:
    issn: str
    title: str
    publisher: str | None
    issns: tuple[str, ...] = ()
    url: str | None = None

    @property
    def aliases(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(x for x in (self.title,) if x))


def _headers(runtime: ScholarlyRuntime) -> dict[str, str]:
    agent = "SuperScholar/3.11.0"
    if runtime.crossref_email:
        agent += f" (mailto:{runtime.crossref_email})"
    headers = {"User-Agent": agent, "Accept": "application/json"}
    if runtime.crossref_api_key:
        headers["Crossref-Plus-API-Token"] = f"Bearer {runtime.crossref_api_key}"
    return headers


def _params(runtime: ScholarlyRuntime) -> dict[str, str]:
    return {"mailto": runtime.crossref_email} if runtime.crossref_email else {}


def _parse_journal_message(message: Any, requested_issn: str) -> CrossrefJournalProfile | None:
    if not isinstance(message, dict):
        return None
    title = str(message.get("title") or message.get("container-title") or "").strip()
    if not title:
        return None
    issns = tuple(dict.fromkeys(str(x).strip() for x in (message.get("ISSN") or message.get("issn") or []) if str(x).strip()))
    if not issns:
        issns = (requested_issn,)
    return CrossrefJournalProfile(
        issn=requested_issn,
        title=title,
        publisher=str(message.get("publisher") or "").strip() or None,
        issns=issns,
        url=str(message.get("URL") or message.get("url") or "").strip() or None,
    )


async def resolve_journal(client: httpx.AsyncClient, issn: str, runtime: ScholarlyRuntime) -> CrossrefJournalProfile | None:
    if not runtime.crossref_enabled or not issn.strip():
        return None
    url = f"{CROSSREF_BASE_URL}/journals/{issn.strip()}"
    response = await client.get(url, params=_params(runtime), headers=_headers(runtime), follow_redirects=True)
    response.raise_for_status()
    payload = response.json()
    return _parse_journal_message(payload.get("message"), issn.strip())


async def resolve_journals(
    client: httpx.AsyncClient,
    source_issns: dict[str, Iterable[str]],
    runtime: ScholarlyRuntime,
    *,
    limit: int = 12,
) -> tuple[dict[str, CrossrefJournalProfile], str | None]:
    if not runtime.crossref_enabled:
        return {}, "Crossref disabled"

    candidates: list[tuple[str, list[str]]] = []
    for source_id, raw_values in source_issns.items():
        values = list(dict.fromkeys(str(x).strip() for x in raw_values if str(x).strip()))
        if values:
            candidates.append((source_id, values[:2]))
        if len(candidates) >= limit:
            break

    semaphore = asyncio.Semaphore(3)

    async def resolve_one(source_id: str, values: list[str]) -> tuple[str, CrossrefJournalProfile | None, list[str]]:
        errors: list[str] = []
        async with semaphore:
            for issn in values:
                try:
                    profile = await resolve_journal(client, issn, runtime)
                    if profile is not None:
                        return source_id, profile, errors
                except Exception as exc:
                    errors.append(f"{issn}: {exc}")
        return source_id, None, errors

    results = await asyncio.gather(*(resolve_one(source_id, values) for source_id, values in candidates)) if candidates else []
    output: dict[str, CrossrefJournalProfile] = {}
    errors: list[str] = []
    for source_id, profile, item_errors in results:
        if profile is not None:
            output[source_id] = profile
        errors.extend(item_errors)
    return output, ("；".join(errors[:3]) if errors and not output else None)


async def test_crossref(client: httpx.AsyncClient, runtime: ScholarlyRuntime) -> dict[str, Any]:
    if not runtime.crossref_enabled:
        return {"status": "disabled", "ok": None, "checks": {}, "message": "Crossref 已禁用"}
    checks: dict[str, Any] = {}
    try:
        response = await client.get(
            f"{CROSSREF_BASE_URL}/works",
            params={"rows": 1, "query.title": "semantic segmentation", **_params(runtime)},
            headers=_headers(runtime),
            follow_redirects=True,
        )
        response.raise_for_status()
        payload = response.json()
        items = ((payload.get("message") or {}).get("items") or []) if isinstance(payload, dict) else []
        checks["works"] = {"ok": bool(items), "status": "ready" if items else "degraded", "message": f"Works 查询返回 {len(items)} 条记录"}
        sample = items[0] if items else {}
        issns = (sample.get("ISSN") or []) if isinstance(sample, dict) else []
        journal = None
        if issns:
            journal = await resolve_journal(client, str(issns[0]), runtime)
        checks["journalResolution"] = {
            "ok": journal is not None,
            "status": "ready" if journal is not None else "degraded",
            "message": f"期刊身份解析：{journal.title}" if journal else "样本记录未能完成 ISSN → journal 解析",
        }
        ok = checks["works"]["ok"] is True
        return {
            "status": "ready" if ok else "degraded",
            "ok": ok,
            "mode": "metadata-plus" if runtime.crossref_api_key else ("polite" if runtime.crossref_email else "public"),
            "checks": checks,
            "message": "Crossref 元数据接口可用" if ok else "Crossref 元数据接口未完整通过",
        }
    except Exception as exc:
        return {"status": "error", "ok": False, "checks": checks, "message": str(exc)}
