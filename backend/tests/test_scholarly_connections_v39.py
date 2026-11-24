from __future__ import annotations

import httpx
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import ScholarlyDataSettings
from app.security import decrypt_secret
from app.services.openalex import SourceResolutionRequest, hydrate_sources, resolve_candidate_sources
from app.services.scholarly_settings import ScholarlyRuntime
from app.services.semantic_scholar import SemanticScholarPaper, SemanticScholarSearchResult, search_papers
from app.services.venue_recommendation import _source_matches_venue, rank_venues
from app.services.openalex import SemanticSearchResult


def runtime(**overrides) -> ScholarlyRuntime:
    values = dict(
        openalex_enabled=True,
        openalex_api_key="oa-test-key",
        openalex_max_results=50,
        crossref_enabled=True,
        crossref_email="researcher@example.test",
        crossref_api_key="",
        semantic_scholar_enabled=True,
        semantic_scholar_api_key="s2-test-key",
        dblp_enabled=True,
        clarivate_enabled=False,
        clarivate_api_key="",
        clarivate_journal_limit=36,
        request_timeout_seconds=20,
        source="ui",
    )
    values.update(overrides)
    return ScholarlyRuntime(**values)


def conference(title: str, description: str) -> dict:
    return {
        "type": "conference", "id": f"conference:{title.lower()}:2099", "title": title,
        "description": description, "sub": "AI", "ccf": "A", "core": "A*", "dblp": title.lower(),
        "year": 2099, "editionId": f"{title.lower()}99", "link": "https://example.test",
        "deadline": "2099-11-15 23:59:59", "abstractDeadline": None, "timezone": "UTC-12",
        "date": "2099", "place": "TBD", "source": "CCFDDL",
    }


def profile() -> dict:
    return {
        "summary": "Boundary-aware surgical semantic segmentation using differentiable superpixels and efficient refinement.",
        "researchProblem": {"text": "How can surgical semantic segmentation preserve boundaries while remaining real-time?"},
        "coreIdea": {"text": "A differentiable superpixel gate selectively refines semantic boundaries."},
        "primaryArea": "AI", "secondaryAreas": ["CG"],
        "topics": ["semantic segmentation", "medical image analysis", "computer vision", "superpixels"],
        "methods": ["boundary refinement", "contrastive learning"], "datasets": ["EndoVis18"],
        "models": ["U-Net"], "metrics": ["mIoU", "Boundary F1", "FPS"],
    }


def preferences() -> dict:
    return {"targetType": "conference", "topN": 12}


def cleanup() -> None:
    with SessionLocal() as db:
        row = db.get(ScholarlyDataSettings, 1)
        if row:
            db.delete(row)
            db.commit()


def test_scholarly_settings_encrypt_and_mask_all_secrets() -> None:
    with TestClient(app) as client:
        cleanup()
        try:
            response = client.put("/api/v1/settings/scholarly", json={
                "openalex_enabled": True,
                "openalex_api_key": "oa-secret-123456789",
                "openalex_max_results": 50,
                "crossref_enabled": True,
                "crossref_email": "scholar@example.org",
                "crossref_api_key": "crossref-secret-token",
                "semantic_scholar_enabled": True,
                "semantic_scholar_api_key": "s2-secret-token",
                "dblp_enabled": True,
                "clarivate_enabled": True,
                "clarivate_api_key": "clarivate-secret-token",
                "clarivate_journal_limit": 24,
                "request_timeout_seconds": 25,
            })
            assert response.status_code == 200, response.text
            body = response.json()
            assert body["openalexApiKeyConfigured"] is True
            assert body["crossrefApiKeyConfigured"] is True
            assert body["semanticScholarApiKeyConfigured"] is True
            assert body["clarivateApiKeyConfigured"] is True
            assert body["clarivateJournalLimit"] == 24
            assert "oa-secret-123456789" not in response.text
            assert "crossref-secret-token" not in response.text
            assert "s2-secret-token" not in response.text
            assert "clarivate-secret-token" not in response.text

            fetched = client.get("/api/v1/settings/scholarly")
            assert fetched.status_code == 200
            assert "secret-token" not in fetched.text
            assert fetched.json()["crossrefEmail"] == "scholar@example.org"

            with SessionLocal() as db:
                row = db.get(ScholarlyDataSettings, 1)
                assert row is not None
                assert decrypt_secret(row.openalex_api_key_encrypted) == "oa-secret-123456789"
                assert decrypt_secret(row.crossref_api_key_encrypted) == "crossref-secret-token"
                assert decrypt_secret(row.semantic_scholar_api_key_encrypted) == "s2-secret-token"
                assert decrypt_secret(row.clarivate_api_key_encrypted) == "clarivate-secret-token"
        finally:
            cleanup()


def test_openalex_source_hydration_uses_documented_ids_openalex_and_parses_topic_share() -> None:
    seen_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_urls.append(str(request.url))
        assert request.url.path == "/sources"
        filter_value = request.url.params.get("filter") or ""
        assert filter_value.startswith("ids.openalex:")
        assert "openalex_id:" not in filter_value
        assert "https://openalex.org/S123" in filter_value
        return httpx.Response(200, json={
            "results": [{
                "id": "https://openalex.org/S123",
                "display_name": "Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition",
                "type": "conference",
                "alternate_titles": ["CVPR"],
                "abbreviated_title": "CVPR",
                "works_count": 1000,
                "topic_share": [
                    {"topic": {"id": "https://openalex.org/T1", "display_name": "Semantic Segmentation"}, "share": 0.42},
                    {"topic": {"id": "https://openalex.org/T2", "display_name": "Computer Vision"}, "share": 0.31},
                ],
                "topics": [
                    {"id": "https://openalex.org/T2", "display_name": "Computer Vision", "count": 700},
                ],
            }]
        }, request=request)

    async def run() -> None:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            result = await hydrate_sources(client, ["S123"], runtime())
        assert result.error is None
        assert result.sources["S123"].abbreviated_title == "CVPR"
        names = [topic.name for topic in result.sources["S123"].topics]
        assert names[:2] == ["Semantic Segmentation", "Computer Vision"]
        assert len([x for x in names if x == "Computer Vision"]) == 1

    import asyncio
    asyncio.run(run())
    assert seen_urls


def test_conservative_source_matching_does_not_cross_match_unrelated_cs_venues() -> None:
    wacv = conference("WACV", "IEEE/CVF Winter Conference on Applications of Computer Vision")
    www = conference("WWW", "The Web Conference")
    ubicomp = conference("UbiComp", "ACM International Joint Conference on Pervasive and Ubiquitous Computing")
    source = "IEEE/CVF Winter Conference on Applications of Computer Vision"
    assert _source_matches_venue(source, wacv) is True
    assert _source_matches_venue(source, www) is False
    assert _source_matches_venue(source, ubicomp) is False


def test_semantic_scholar_is_independent_evidence_and_unavailable_sources_are_null() -> None:
    venues = [
        conference("CVPR", "IEEE/CVF Conference on Computer Vision and Pattern Recognition"),
        conference("COLING", "International Conference on Computational Linguistics"),
    ]
    openalex = SemanticSearchResult(query="surgical segmentation", works=[], source_url="x", error="offline")
    secondary = SemanticScholarSearchResult(
        query="surgical segmentation",
        source_url="s2",
        papers=[
            SemanticScholarPaper(
                paper_id="P1", title="Boundary-aware surgical semantic segmentation", year=2026,
                venue="CVPR", publication_venue_name="IEEE/CVF Conference on Computer Vision and Pattern Recognition",
                publication_venue_id="CVPR", publication_venue_type="conference", url="https://example.test/p1",
            ),
            SemanticScholarPaper(
                paper_id="P2", title="Differentiable superpixels for image segmentation", year=2025,
                venue="CVPR", publication_venue_name="CVPR", publication_venue_id="CVPR",
                publication_venue_type="conference", url="https://example.test/p2",
            ),
        ],
    )
    ranked = rank_venues(profile(), preferences(), venues, openalex, secondary=secondary)
    by_name = {row["venue"]["title"]: row for row in ranked}
    assert by_name["CVPR"]["semanticMatch"] is None
    assert by_name["CVPR"]["secondaryMatch"] is not None and by_name["CVPR"]["secondaryMatch"] > 0
    assert by_name["COLING"]["secondaryMatch"] == 0
    assert by_name["CVPR"]["researchMatch"] > by_name["COLING"]["researchMatch"] + 20


def test_overall_health_ignores_not_applicable_optional_sources():
    from app.services.venue_recommendation import _overall_health

    status, message = _overall_health({
        "openalexWorks": {"status": "ready", "enabled": True},
        "openalexSources": {"status": "ready", "enabled": True},
        "semanticScholar": {"status": "ready", "enabled": True},
        "crossref": {"status": "not_applicable", "enabled": True},
        "dblp": {"status": "not_applicable", "enabled": True},
        "conferenceCatalog": {"status": "ready", "enabled": True},
        "journalCatalog": {"status": "disabled", "enabled": False},
    })
    assert status == "ready"
    assert "完整可用" in message


def test_openalex_fully_oa_source_is_not_mislabeled_as_hybrid_or_subscription():
    from app.services.openalex import SourceProfile
    from app.services.venue_recommendation import _dynamic_source_venue

    source = SourceProfile(
        id="S1",
        display_name="Example Fully OA Journal",
        source_type="journal",
        is_oa=True,
    )
    venue = _dynamic_source_venue(source, {"primaryArea": "AI"})
    assert venue is not None
    assert venue["metrics"]["oaType"] == "Fully Open Access"


def test_candidate_openalex_source_resolution_attaches_conference_topics() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/sources"
        assert request.url.params.get("filter") == "type:conference"
        assert "Winter Conference on Applications of Computer Vision" in (request.url.params.get("search") or "")
        return httpx.Response(200, json={
            "results": [{
                "id": "https://openalex.org/SWACV",
                "display_name": "IEEE/CVF Winter Conference on Applications of Computer Vision",
                "type": "conference",
                "alternate_titles": ["WACV"],
                "abbreviated_title": "WACV",
                "works_count": 2000,
                "topics": [
                    {"id": "https://openalex.org/T-CV", "display_name": "Computer Vision", "count": 1200},
                    {"id": "https://openalex.org/T-SEG", "display_name": "Semantic Segmentation", "count": 420},
                ],
            }]
        }, request=request)

    async def run() -> None:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            result = await resolve_candidate_sources(client, [SourceResolutionRequest(
                venue_id="conference:wacv:2027",
                venue_type="conference",
                names=("WACV", "IEEE/CVF Winter Conference on Applications of Computer Vision"),
            )], runtime())
        source = result.matches.get("conference:wacv:2027")
        assert source is not None
        assert source.id == "SWACV"
        assert result.confidence["conference:wacv:2027"] >= 0.78
        assert result.resolved_with_topics == 1
        assert any(topic.name == "Computer Vision" for topic in source.topics)

    import asyncio
    asyncio.run(run())


def test_candidate_openalex_source_resolution_rejects_unrelated_search_result() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "results": [{
                "id": "https://openalex.org/SBAD",
                "display_name": "International Conference on Computational Linguistics",
                "type": "conference",
                "alternate_titles": ["COLING"],
                "abbreviated_title": "COLING",
                "topics": [{"id": "https://openalex.org/T-NLP", "display_name": "Natural Language Processing", "count": 500}],
            }]
        }, request=request)

    async def run() -> None:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            result = await resolve_candidate_sources(client, [SourceResolutionRequest(
                venue_id="conference:wacv:2027",
                venue_type="conference",
                names=("WACV", "IEEE/CVF Winter Conference on Applications of Computer Vision"),
            )], runtime())
        assert result.attempted == 1
        assert result.matches == {}

    import asyncio
    asyncio.run(run())


def test_semantic_scholar_anonymous_429_is_reported_as_rate_limited() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "x-api-key" not in request.headers
        return httpx.Response(429, text="Too Many Requests", request=request)

    async def run() -> None:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            result = await search_papers(client, "surgical segmentation", runtime(semantic_scholar_api_key=""), limit=3)
        assert result.papers == []
        assert result.error_kind == "rate_limited"
        assert result.status_code == 429
        assert result.error and "API Key" in result.error

    import asyncio
    asyncio.run(run())


def test_overall_health_surfaces_partial_candidate_source_coverage_as_limited() -> None:
    from app.services.venue_recommendation import _overall_health

    status, message = _overall_health({
        "openalexWorks": {"status": "ready", "enabled": True},
        "openalexSources": {"status": "ready", "enabled": True},
        "openalexCandidateSources": {"status": "limited", "enabled": True},
        "semanticScholar": {"status": "ready", "enabled": True},
        "crossref": {"status": "not_applicable", "enabled": True},
        "dblp": {"status": "ready", "enabled": True},
    })
    assert status == "limited"
    assert "受限" in message
