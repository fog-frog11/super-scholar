from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import httpx

from app.services.ccf import _canonicalize_journal_placements
from app.services.openalex import (
    SemanticSearchResult,
    SemanticWork,
    SourceProfile,
    _conference_source_year,
    _looks_like_excluded_conference_source,
    semantic_search_within_sources,
)
from app.services.scholarly_settings import ScholarlyRuntime
from app.services.venue_intelligence import reference_count
from app.services.venue_recommendation import actionability_for_venue, evaluate_constraints, rank_venues


def _profile() -> dict:
    return {
        "summary": "Boundary-aware surgical semantic segmentation using differentiable superpixels with real-time inference.",
        "researchProblem": {"text": "Efficient high-precision surgical semantic segmentation."},
        "coreIdea": {"text": "Boundary-responsive differentiable gating refines only uncertain superpixel boundaries."},
        "primaryArea": "AI",
        "secondaryAreas": ["CG"],
        "topics": ["semantic segmentation", "surgical scene segmentation", "medical image analysis", "superpixels"],
        "methods": ["differentiable gating", "boundary contrastive learning"],
        "datasets": ["EndoVis18", "Cityscapes"],
        "models": ["BRDG"],
        "metrics": ["mIoU", "Boundary F1", "FPS"],
    }


def _prefs() -> dict:
    return {
        "targetType": "conference",
        "ccfRanks": {"enabled": False, "mode": "preferred", "value": ["A", "B", "C"]},
        "coreRanks": {"enabled": False, "mode": "preferred", "value": []},
        "deadlineMonths": {"enabled": False, "mode": "preferred", "value": 3},
        "locations": {"enabled": False, "mode": "preferred", "value": []},
        "topN": 10,
    }


def _venue(title: str, description: str, *, deadline: str | None = None, ccf: str = "U") -> dict:
    return {
        "type": "conference", "id": f"conference:{title.lower()}", "seriesId": f"conference:{title.lower()}",
        "title": title, "description": description, "sub": "AI", "ccf": ccf, "core": "N", "dblp": title.lower(),
        "year": 2027, "editionId": f"{title.lower()}27", "link": "https://example.test", "deadline": deadline,
        "timeline": [], "timezone": "UTC", "date": "2027", "place": "TBD", "source": "test",
    }


def _work(index: int, title: str, source: str) -> SemanticWork:
    return SemanticWork(
        id=f"W{index}", title=title, year=2026, relevance_score=0.86 - index * 0.01,
        source_id=f"S{index}", source_name=source, source_type="conference",
        topics=("Medical Image Segmentation", "Computer Vision"), keywords=("semantic segmentation",),
    )


def test_ccf_295_placements_can_canonicalize_to_291_unique_identities() -> None:
    items = []
    # 291 stable identities plus four cross-domain duplicate placements.
    for i in range(291):
        items.append({
            "id": f"journal:j{i}", "type": "journal", "seriesId": f"journal:j{i}",
            "shortName": f"J{i}", "name": f"Journal {i}", "publisher": "P",
            "sub": "AI" if i % 2 else "CG", "ccf": "B", "source": "official", "sourceVersion": "2026",
        })
    for i in range(4):
        dup = dict(items[i])
        dup["sub"] = "MX"
        items.append(dup)
    assert len(items) == 295
    canonical = _canonicalize_journal_placements(items)
    assert len(canonical) == 291
    assert canonical[0]["ccfVerified"] is True
    assert len(canonical[0]["ccfEntries"]) == 2


def test_fast_word_is_not_usenix_fast_reference_but_explicit_in_fast_is() -> None:
    fast = _venue("FAST", "USENIX Conference on File and Storage Technologies", ccf="A")
    unrelated = "References\n[1] A fast semantic segmentation network for real-time medical images. In CVPR, 2025."
    explicit = "References\n[1] Storage systems at scale. In FAST, 2025."
    assert reference_count(unrelated, fast) == 0
    assert reference_count(explicit, fast) == 1


def test_unknown_deadline_keeps_academic_candidate_but_not_currently_actionable() -> None:
    venue = _venue("MICCAI", "Medical Image Computing and Computer Assisted Intervention", deadline="TBD")
    constraints = evaluate_constraints(venue, _prefs())
    action = actionability_for_venue(venue, constraints)
    assert action["status"] == "unknown"
    semantic = SemanticSearchResult(query="x", works=[], source_url="x", error="offline")
    ranked = rank_venues(_profile(), _prefs(), [venue], semantic)
    assert ranked[0]["eligible"] is True
    assert ranked[0]["isCurrentlyActionable"] is False


def test_venue_conditioned_recent_work_signal_dominates_noisy_auxiliary_topics() -> None:
    miccai = _venue("MICCAI", "Medical Image Computing and Computer Assisted Intervention")
    acl = _venue("ACL", "Annual Meeting of the Association for Computational Linguistics", ccf="A")
    semantic = SemanticSearchResult(query="x", works=[], source_url="x", error=None)
    conditioned = {
        miccai["id"]: SemanticSearchResult(
            query="x", source_url="x",
            works=[_work(i, f"Surgical segmentation {i}", "MICCAI") for i in range(1, 6)],
        ),
        acl["id"]: SemanticSearchResult(query="x", source_url="x", works=[]),
    }
    ranked = rank_venues(_profile(), _prefs(), [miccai, acl], semantic, conditioned=conditioned)
    by = {r["venue"]["title"]: r for r in ranked}
    assert by["MICCAI"]["venueConditionedMatch"] > 60
    assert by["ACL"]["venueConditionedMatch"] == 0
    assert by["MICCAI"]["researchMatch"] > by["ACL"]["researchMatch"] + 30
    assert ranked[0]["venue"]["title"] == "MICCAI"


def test_conference_source_helpers_reject_workshops_and_prefer_recent_year() -> None:
    workshop = SourceProfile(id="S1", display_name="CVPR 2026 Workshop Proceedings", source_type="conference")
    main = SourceProfile(id="S2", display_name="2026 IEEE/CVF Conference on Computer Vision and Pattern Recognition", source_type="conference")
    old = SourceProfile(id="S3", display_name="2022 IEEE/CVF Conference on Computer Vision and Pattern Recognition", source_type="conference")
    assert _looks_like_excluded_conference_source(workshop) is True
    assert _looks_like_excluded_conference_source(main) is False
    assert _conference_source_year(main) == 2026
    assert _conference_source_year(old) == 2022


def test_venue_conditioned_openalex_request_uses_source_and_recent_date_filters() -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, json={"results": []}, request=request)

    runtime = ScholarlyRuntime(
        openalex_enabled=True,
        openalex_api_key="test",
        openalex_max_results=50,
        crossref_enabled=False,
        crossref_email="",
        crossref_api_key="",
        semantic_scholar_enabled=False,
        semantic_scholar_api_key="",
        dblp_enabled=False,
        clarivate_enabled=False,
        clarivate_api_key="",
        clarivate_journal_limit=36,
        request_timeout_seconds=30,
        source="ui",
    )

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await semantic_search_within_sources(
                client, "surgical segmentation", ["S123", "S456"], runtime, from_year=2022, limit=8
            )
            assert result.error is None
            assert result.works == []

    asyncio.run(run())
    url = captured["url"]
    assert "search.semantic=surgical+segmentation" in url
    assert "primary_location.source.id%3AS123%7CS456" in url
    assert "from_publication_date%3A2022-01-01" in url
