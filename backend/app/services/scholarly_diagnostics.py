from __future__ import annotations

from datetime import datetime, timezone
import asyncio
from typing import Any

import httpx

from .crossref import test_crossref
from .dblp import test_dblp
from .openalex import test_openalex
from .scholarly_settings import ScholarlyRuntime
from .semantic_scholar import test_semantic_scholar
from .clarivate_journals import test_clarivate


def _source_summary(name: str, result: dict[str, Any], *, required: bool) -> dict[str, Any]:
    status = str(result.get("status") or "error")
    ok = result.get("ok")
    return {
        "name": name,
        "required": required,
        "status": status,
        "ok": ok,
        "message": str(result.get("message") or ""),
    }


async def test_scholarly_sources(runtime: ScholarlyRuntime) -> dict[str, Any]:
    timeout = httpx.Timeout(runtime.request_timeout_seconds)
    async with httpx.AsyncClient(timeout=timeout) as client:
        openalex, crossref, semantic_scholar, dblp, clarivate = await asyncio.gather(
            test_openalex(client, runtime),
            test_crossref(client, runtime),
            test_semantic_scholar(client, runtime),
            test_dblp(client, runtime),
            test_clarivate(client, runtime),
        )

    sources = {
        "openalex": openalex,
        "crossref": crossref,
        "semanticScholar": semantic_scholar,
        "dblp": dblp,
        "clarivate": clarivate,
    }
    enabled_required = []
    if runtime.openalex_enabled:
        enabled_required.append(openalex.get("ok") is True)
    # Crossref/S2/DBLP are enrichers, not hard requirements for the recommender to run.
    if not enabled_required:
        overall = "degraded"
        ok = False
        message = "OpenAlex 未启用；推荐仍可使用本地 CS scope/References，但缺少主要语义学术图谱证据"
    elif all(enabled_required):
        optional_bad = any(
            result.get("status") in {"degraded", "error"}
            for key, result in sources.items()
            if key != "openalex" and result.get("status") not in {"disabled", "not_applicable"}
        )
        anonymous_limited = openalex.get("status") == "limited"
        overall = "degraded" if optional_bad else ("limited" if anonymous_limited else "ready")
        ok = True
        if optional_bad:
            message = "OpenAlex 主链可用；一个或多个可选增强数据源处于降级状态"
        elif anonymous_limited:
            message = "推荐主链可用，但 OpenAlex 当前使用匿名低额度；建议配置免费 API Key"
        else:
            message = "主要推荐数据链可用"
    else:
        overall = "degraded"
        ok = False
        message = "OpenAlex 主推荐链未完整通过；请查看 Works / Sources 分项诊断"

    return {
        "ok": ok,
        "overallStatus": overall,
        "testedAt": datetime.now(timezone.utc).isoformat(),
        "message": message,
        "sources": sources,
        "summary": [
            _source_summary("OpenAlex", openalex, required=True),
            _source_summary("Crossref", crossref, required=False),
            _source_summary("Semantic Scholar", semantic_scholar, required=False),
            _source_summary("DBLP", dblp, required=False),
            _source_summary("Clarivate WoS Journals", clarivate, required=False),
        ],
    }
