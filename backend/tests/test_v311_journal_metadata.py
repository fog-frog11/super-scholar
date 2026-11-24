from __future__ import annotations

import asyncio

import httpx

from app.services.clarivate_journals import resolve_journal
from app.services.ecb_fx import FxRate, latest_cny_per_usd
from app.services.openalex import SemanticSearchResult, SemanticWork, _parse_source
from app.services.scholarly_settings import ScholarlyRuntime
from app.services.venue_recommendation import (
    _public_source_metrics,
    _semantic_result_score,
    evaluate_constraints,
)


def runtime(**overrides) -> ScholarlyRuntime:
    values = dict(
        openalex_enabled=True,
        openalex_api_key="oa-test",
        openalex_max_results=50,
        crossref_enabled=True,
        crossref_email="test@example.org",
        crossref_api_key="",
        semantic_scholar_enabled=True,
        semantic_scholar_api_key="s2-test",
        dblp_enabled=True,
        clarivate_enabled=True,
        clarivate_api_key="clarivate-test",
        clarivate_journal_limit=36,
        request_timeout_seconds=20,
        source="ui",
    )
    values.update(overrides)
    return ScholarlyRuntime(**values)


def test_openalex_source_public_journal_metadata_is_parsed_without_turning_citedness_into_jif() -> None:
    source = _parse_source({
        "id": "https://openalex.org/S123",
        "display_name": "Example Journal",
        "type": "journal",
        "issn_l": "1234-5678",
        "issn": ["1234-5678", "8765-4321"],
        "is_oa": True,
        "is_in_doaj": True,
        "is_high_oa_rate": True,
        "oa_flip_year": 2022,
        "apc_prices": [{"price": 2500, "currency": "USD"}, {"price": 2200, "currency": "EUR"}],
        "apc_usd": 2500,
        "summary_stats": {"2yr_mean_citedness": 4.25},
        "updated_date": "2026-08-30T00:00:00",
        "works_count": 12345,
    })
    assert source is not None
    assert source.is_oa is True
    assert source.is_in_doaj is True
    assert source.apc_usd == 2500
    assert source.apc_prices[0].currency == "USD"
    assert source.two_year_mean_citedness == 4.25

    metrics = _public_source_metrics(source, FxRate(cny_per_usd=7.2, date="2026-09-01", source_url="https://ecb.example"))
    assert metrics["oaType"] == "Fully Open Access"
    assert metrics["apcCny"] == 18000
    assert metrics["openalex2yrMeanCitedness"] == 4.25
    assert "impactFactor" not in metrics
    assert metrics["apcFx"]["provider"] == "ECB"


def test_openalex_is_oa_false_is_not_fabricated_as_hybrid_or_subscription() -> None:
    source = _parse_source({
        "id": "https://openalex.org/S124",
        "display_name": "Mixed Access Journal",
        "type": "journal",
        "is_oa": False,
    })
    assert source is not None
    metrics = _public_source_metrics(source)
    assert metrics["oaType"] == "Not fully OA / mixed"
    assert "Hybrid" not in metrics["oaType"]
    assert "Subscription" not in metrics["oaType"]


def test_ecb_cny_per_usd_uses_two_eur_reference_rates_and_keeps_date() -> None:
    csv_text = """KEY,FREQ,CURRENCY,CURRENCY_DENOM,EXR_TYPE,EXR_SUFFIX,TIME_PERIOD,OBS_VALUE\nEXR.D.USD.EUR.SP00.A,D,USD,EUR,SP00,A,2026-09-01,1.2000\nEXR.D.CNY.EUR.SP00.A,D,CNY,EUR,SP00,A,2026-09-01,8.4000\n"""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/EXR/D.USD+CNY.EUR.SP00.A")
        assert request.url.params.get("format") == "csvdata"
        return httpx.Response(200, text=csv_text, headers={"content-type": "text/csv"}, request=request)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await latest_cny_per_usd(client)

    rate = asyncio.run(run())
    assert rate is not None
    assert rate.cny_per_usd == 7.0
    assert rate.date == "2026-09-01"
    assert "data-api.ecb.europa.eu" in rate.source_url


def test_clarivate_resolver_uses_real_journal_search_then_latest_report_metrics() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("X-ApiKey") == "clarivate-test"
        if request.url.path == "/apis/wos-journals/v1/journals":
            return httpx.Response(200, json={
                "metadata": {"total": 1, "page": 1, "limit": 10},
                "hits": [{
                    "id": "J_PARALLEL_DISTR_COMPUT",
                    "name": "Journal of Parallel and Distributed Computing",
                    "matches": [{"field": "ISSN", "value": "0743-7315"}],
                }],
            }, request=request)
        if request.url.path.endswith("/J_PARALLEL_DISTR_COMPUT/reports/year/2025"):
            return httpx.Response(200, json={
                "year": 2025,
                "metrics": {"impactMetrics": {"jif": "4.2", "jci": "1.05"}},
                "ranks": {"jif": [
                    {"category": "COMPUTER SCIENCE, THEORY & METHODS", "edition": "SCIE", "rank": "35/145", "quartile": "Q1"},
                    {"category": "COMPUTER SCIENCE, HARDWARE & ARCHITECTURE", "edition": "SCIE", "rank": "22/90", "quartile": "Q1"},
                ]},
            }, request=request)
        raise AssertionError(str(request.url))

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await resolve_journal(
                client,
                name="Journal of Parallel and Distributed Computing",
                issns=["0743-7315"],
                runtime=runtime(),
            )

    profile = asyncio.run(run())
    assert profile is not None
    assert profile.impact_factor == 4.2
    assert profile.jci == 1.05
    assert profile.wos_indexes == ("SCIE",)
    assert profile.quartiles == ("Q1",)
    assert profile.jcr_year == 2025


def test_preferred_unavailable_journal_metadata_is_not_applicable_but_required_remains_unknown() -> None:
    venue = {"type": "journal", "id": "j", "metrics": {}}
    preferred = {
        "wosIndexes": {"enabled": True, "mode": "preferred", "value": ["SCIE"]},
        "jcrQuartiles": {"enabled": True, "mode": "preferred", "value": ["Q1"]},
        "impactFactor": {"enabled": True, "mode": "preferred", "value": {"min": 3}},
        "apcCny": {"enabled": True, "mode": "preferred", "value": {"max": 30000}},
        "reviewDays": {"enabled": True, "mode": "preferred", "value": 90},
    }
    statuses = {x["label"]: x["status"] for x in evaluate_constraints(venue, preferred)}
    assert all(value == "not_applicable" for value in statuses.values())

    required = {**preferred, "impactFactor": {"enabled": True, "mode": "required", "value": {"min": 3}}}
    status = next(x for x in evaluate_constraints(venue, required) if x["label"] == "Impact Factor")
    assert status["status"] == "unknown"


def test_openalex_evidence_retains_every_returned_work_for_expand_all() -> None:
    works = [SemanticWork(
        id=f"W{i}", title=f"Paper {i}", year=2026, relevance_score=0.9 - i * 0.005,
        source_id="S1", source_name="Example Journal", source_type="journal",
        topics=("Distributed Systems",), keywords=("federated learning",),
    ) for i in range(1, 18)]
    score, evidence = _semantic_result_score(SemanticSearchResult(query="x", works=works, source_url="x"))
    assert score is not None and score > 0
    assert len(evidence) == 17
    assert evidence[0]["semanticRank"] == 1
    assert evidence[-1]["semanticRank"] == 17
