from __future__ import annotations

import pytest

from app.services.research_ai import (
    AIResearchOutput,
    GroundedItem,
    GroundedText,
    GroundingError,
    _compact_packet,
    _extraction_evidence_ids,
    _salvage_final_payload,
    validate_and_build_profile,
)


def base_output(**overrides):
    data = dict(
        summary=GroundedText(text="A grounded summary", evidence_ids=["ev1"]),
        research_problem=GroundedText(text="A grounded problem", evidence_ids=["ev1"]),
        core_idea=GroundedText(text="A grounded idea", evidence_ids=["ev2"]),
        primary_area="AI",
        secondary_areas=["DS"],
        area_rationale=GroundedText(text="AI evidence", evidence_ids=["ev1"]),
        topics=["Computer Vision"], methods=["Transformer"], datasets=["Cityscapes"], models=["SegFormer"], metrics=["mIoU"],
        contributions=[GroundedItem(text="Valid contribution", evidence_ids=["ev2"], confidence="high"), GroundedItem(text="Ungrounded contribution", evidence_ids=["bad"], confidence="high")],
        research_questions=[], claimed_novelty=[], gaps=[], visual_observations=[],
        stage="experimental", stage_rationale=GroundedText(text="Experiments exist", evidence_ids=["ev2"]),
    )
    data.update(overrides)
    return AIResearchOutput(**data)


def build(raw):
    return validate_and_build_profile(raw, {"ev1", "ev2"}, material_count=2, parsed_text_chars=1000, has_manuscript=True, has_source=True, has_data=False, has_images=False, parser_metadata={}, generated_at="2026-08-26T00:00:00+00:00")


def test_grounding_drops_unsupported_claims():
    profile = build(base_output())
    assert profile["contributions"] == ["Valid contribution"]
    assert profile["sourceMode"] == "ai_deep"


def test_grounding_rejects_ungrounded_summary():
    with pytest.raises(GroundingError):
        build(base_output(summary=GroundedText(text="No support", evidence_ids=["bad"])))


def test_claimed_novelty_is_kept_separate_from_verified_novelty():
    raw = base_output(claimed_novelty=[GroundedItem(text="Materials claim a new adapter", evidence_ids=["ev2"], confidence="medium")])
    profile = build(raw)
    assert profile["claimedNovelty"][0]["text"] == "Materials claim a new adapter"
    assert "verifiedNovelty" not in profile


def test_final_synthesis_salvages_only_invalid_stage_rationale():
    fallback = base_output(stage_rationale=GroundedText(text="Manuscript evidence", evidence_ids=["ev2"]))
    payload = fallback.model_dump()
    payload["summary"] = {"text": "AI final summary", "evidence_ids": ["ev1"]}
    payload["stage_rationale"] = {"text": "Looks like a manuscript", "evidence_ids": ["invented_id"]}

    parsed, normalized = _salvage_final_payload(payload, fallback, synthesis_valid_ids={"ev1", "ev2"})
    assert parsed.summary.text == "AI final summary"
    assert parsed.stage_rationale.text == "Manuscript evidence"
    assert parsed.stage_rationale.evidence_ids == ["ev2"]
    assert "stage_rationale" in normalized
    # The mixed AI + local result must remain fully groundable instead of failing the run.
    profile = build(parsed)
    assert profile["summary"] == "AI final summary"
    assert profile["stageRationale"]["text"] == "Manuscript evidence"


def test_deterministic_fallback_can_use_grounded_ids_omitted_from_bounded_synthesis_packet():
    text_results = [
        {
            "chunkId": "c1",
            "evidenceIds": ["ev1"],
            "result": {"summary": {"text": "first", "evidenceIds": ["ev1"]}, "areaCandidates": ["AI"], "facts": []},
        },
        {
            "chunkId": "c2",
            "evidenceIds": ["ev_stage"],
            "result": {
                "summary": {"text": "later", "evidenceIds": ["ev_stage"]},
                "areaCandidates": ["AI"],
                "facts": [{"category": "stage_signal", "text": "The manuscript reports experiments.", "evidenceIds": ["ev_stage"], "confidence": "high"}],
            },
        },
    ]
    # Force the compact synthesis packet to stop after the first chunk.
    _, synthesis_ids = _compact_packet(text_results, [], max_chars=180)
    extraction_ids = _extraction_evidence_ids(text_results, [])
    assert "ev_stage" not in synthesis_ids
    assert "ev_stage" in extraction_ids
