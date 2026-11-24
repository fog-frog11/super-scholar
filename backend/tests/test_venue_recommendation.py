from __future__ import annotations

from app.services.openalex import SemanticSearchResult, SemanticWork, SourceProfile, SourceTopic
from app.services.venue_intelligence import _find_reference_section, reference_count
from app.services.venue_recommendation import build_semantic_query, merge_openalex_sources, rank_venues


def work(
    rank: int,
    source: str,
    title: str,
    *,
    source_id: str | None = None,
    topics: tuple[str, ...] = ("Object Detection", "Computer Vision"),
    topic_ids: tuple[str, ...] = ("T-CV", "T-DET"),
    topic_scores: tuple[float, ...] = (0.91, 0.72),
) -> SemanticWork:
    return SemanticWork(
        id=f"W{rank}",
        title=title,
        year=2026,
        relevance_score=1.0 / rank,
        source_id=source_id or f"S{rank}",
        source_name=source,
        source_type="conference",
        topics=topics,
        keywords=("DETR", "Real-time object detection"),
        topic_ids=topic_ids,
        topic_scores=topic_scores,
    )


def conference(title: str, description: str, ccf: str = "A", core: str = "A*") -> dict:
    return {
        "type": "conference",
        "id": f"conference:{title.lower()}:2099",
        "title": title,
        "description": description,
        "sub": "AI",
        "ccf": ccf,
        "core": core,
        "dblp": title.lower(),
        "year": 2099,
        "editionId": f"{title.lower()}99",
        "link": "https://example.test",
        "deadline": "2099-11-15 23:59:59",
        "abstractDeadline": None,
        "timezone": "UTC-12",
        "date": "2099",
        "place": "TBD",
        "source": "CCFDDL",
    }


def profile() -> dict:
    return {
        "summary": "We propose RT-DETR, a real-time end-to-end object detector that removes NMS and improves the speed-accuracy trade-off against YOLO on COCO.",
        "researchProblem": {"text": "Can DETR become a real-time object detector while outperforming YOLO in speed and accuracy?"},
        "coreIdea": {"text": "An efficient hybrid encoder and uncertainty-minimal query selection make DETR practical for real-time object detection."},
        "primaryArea": "AI",
        "secondaryAreas": ["CG"],
        "topics": ["real-time object detection", "computer vision", "DETR", "YOLO"],
        "methods": ["Transformer", "hybrid encoder", "query selection"],
        "datasets": ["COCO", "Objects365"],
        "models": ["RT-DETR", "YOLOv8"],
        "metrics": ["AP", "FPS"],
    }


def brdg_profile() -> dict:
    return {
        "summary": "BRDG is a differentiable superpixel-based semantic segmentation framework for high-precision surgical scene understanding, with boundary-responsive gating and efficient real-time refinement.",
        "researchProblem": {"text": "Pixel-wise surgical image segmentation is accurate but computationally expensive, while superpixel methods lose boundary precision."},
        "coreIdea": {"text": "A boundary-responsive differentiable gate routes ambiguous superpixel boundaries to a refinement path and preserves efficient coarse prediction in stable regions."},
        "primaryArea": "AI",
        "secondaryAreas": ["CG"],
        "topics": ["semantic segmentation", "medical image analysis", "surgical scene segmentation", "differentiable superpixels", "boundary refinement"],
        "methods": ["ResNet-UNet", "differentiable gating", "contrastive learning", "superpixel adjacency graph", "three cooperative agents"],
        "datasets": ["EndoVis18", "EndoVis17", "CholecSeg8K", "Cityscapes", "BSDS500"],
        "models": ["BRDG", "SegFormer", "U-Net"],
        "metrics": ["mIoU", "Boundary F1", "FPS", "GFLOPs"],
    }


def preferences() -> dict:
    return {
        "targetType": "conference",
        "ccfRanks": {"enabled": True, "mode": "preferred", "value": ["A", "B", "C"]},
        "coreRanks": {"enabled": True, "mode": "preferred", "value": ["A*", "A", "B"]},
        "deadlineMonths": {"enabled": False, "mode": "preferred", "value": 3},
        "locations": {"enabled": False, "mode": "preferred", "value": []},
        "topN": 12,
    }


def test_rtdetr_semantic_source_evidence_beats_same_ccf_area_venues() -> None:
    venues = [
        conference("CVPR", "IEEE/CVF Conference on Computer Vision and Pattern Recognition"),
        conference("AAMAS", "International Conference on Autonomous Agents and Multiagent Systems", "B", "A"),
        conference("ALT", "International Conference on Algorithmic Learning Theory", "C", "A"),
        conference("COLING", "International Conference on Computational Linguistics", "B", "A"),
        conference("FG", "IEEE International Conference on Automatic Face and Gesture Recognition", "C", "A"),
    ]
    semantic = SemanticSearchResult(
        query="rt-detr",
        source_url="https://api.openalex.org/works",
        works=[
            work(1, "Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition", "Real-time Detection Transformers"),
            work(2, "IEEE/CVF Conference on Computer Vision and Pattern Recognition", "End-to-end Object Detection"),
            work(3, "Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition", "Efficient DETR for Object Detection"),
            work(5, "IEEE/CVF Conference on Computer Vision and Pattern Recognition", "Transformer Object Detectors"),
        ],
    )
    ranked = rank_venues(profile(), preferences(), venues, semantic)
    by_name = {r["venue"]["title"]: r for r in ranked}

    assert by_name["CVPR"]["semanticMatch"] >= 80
    assert by_name["CVPR"]["researchMatch"] >= 70
    assert by_name["CVPR"]["semanticEvidenceCount"] >= 3
    for unrelated in ("AAMAS", "ALT", "COLING", "FG"):
        assert by_name[unrelated]["semanticMatch"] == 0
        assert by_name[unrelated]["researchMatch"] < 35
    assert ranked[0]["venue"]["title"] == "CVPR"


def test_openalex_failure_uses_scope_not_same_area_flat_score() -> None:
    venues = [
        conference("CVPR", "IEEE/CVF Conference on Computer Vision and Pattern Recognition"),
        conference("AAMAS", "International Conference on Autonomous Agents and Multiagent Systems"),
        conference("COLING", "International Conference on Computational Linguistics"),
    ]
    semantic = SemanticSearchResult(query="rt-detr", works=[], source_url="https://api.openalex.org/works", error="offline")
    ranked = rank_venues(profile(), preferences(), venues, semantic)
    by_name = {r["venue"]["title"]: r for r in ranked}
    assert by_name["CVPR"]["researchMatch"] > by_name["AAMAS"]["researchMatch"] + 25
    assert by_name["CVPR"]["researchMatch"] > by_name["COLING"]["researchMatch"] + 25
    assert by_name["AAMAS"]["researchMatch"] != 72
    assert by_name["COLING"]["researchMatch"] != 72


def test_brdg_scope_and_bibliography_prioritize_vision_and_medical_venues_without_direct_source_hits() -> None:
    venues = [
        conference("CVPR", "IEEE/CVF Conference on Computer Vision and Pattern Recognition"),
        conference("MICCAI", "Medical Image Computing and Computer Assisted Intervention", "N", "N"),
        conference("ECCV", "European Conference on Computer Vision", "B", "A"),
        conference("ICLR", "International Conference on Learning Representations", "A", "A*"),
        conference("AAMAS", "International Conference on Autonomous Agents and Multiagent Systems", "B", "A"),
        conference("COLING", "International Conference on Computational Linguistics", "B", "A"),
        conference("ICRA", "IEEE International Conference on Robotics and Automation", "B", "A*"),
    ]
    # The semantic neighborhood is available but deliberately has no direct venue match.
    semantic = SemanticSearchResult(
        query="surgical segmentation",
        source_url="https://api.openalex.org/works",
        works=[
            work(1, "Some Other Vision Proceedings", "Boundary-aware surgical image segmentation", source_id="SX1", topics=("Medical Image Segmentation", "Computer Vision"), topic_ids=("T-MED", "T-CV"), topic_scores=(0.95, 0.88)),
            work(2, "Another Vision Venue", "Differentiable superpixels for segmentation", source_id="SX2", topics=("Semantic Segmentation", "Computer Vision"), topic_ids=("T-SEG", "T-CV"), topic_scores=(0.93, 0.84)),
        ],
    )
    references = """
    References
    [1] Superpixel Sampling Networks. In CVPR, 2018.
    [2] Learning superpixels in space and time. In CVPR, 2022.
    [3] Boundary detection. In CVPR, 2019.
    [4] U-Net. In MICCAI, 2015.
    [5] Medical Transformer. In MICCAI, 2021.
    [6] SegFix. In ECCV, 2020.
    [7] Gated-SCNN. In ICCV, 2019.
    [8] Adam. In ICLR, 2015.
    """
    ranked = rank_venues(brdg_profile(), preferences(), venues, semantic, reference_text=references)
    by_name = {r["venue"]["title"]: r for r in ranked}

    assert by_name["CVPR"]["scopeMatch"] >= 60
    assert by_name["MICCAI"]["scopeMatch"] >= 70
    assert by_name["CVPR"]["referenceCount"] >= 3
    assert by_name["MICCAI"]["referenceCount"] >= 2
    for unrelated in ("AAMAS", "COLING", "ICRA"):
        assert by_name["CVPR"]["researchMatch"] > by_name[unrelated]["researchMatch"] + 20
        assert by_name["MICCAI"]["researchMatch"] > by_name[unrelated]["researchMatch"] + 20
    # "three cooperative agents" in the method description must NOT imply multi-agent systems.
    assert by_name["AAMAS"]["scopeMatch"] < 25


def test_source_topic_fit_and_dynamic_source_candidate() -> None:
    cvpr = conference("CVPR", "IEEE/CVF Conference on Computer Vision and Pattern Recognition")
    source = SourceProfile(
        id="S-CVPR",
        display_name="Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition",
        source_type="conference",
        alternate_titles=("CVPR",),
        abbreviated_title="CVPR",
        topics=(
            SourceTopic("T-CV", "Computer Vision", 1000),
            SourceTopic("T-DET", "Object Detection", 700),
        ),
    )
    semantic = SemanticSearchResult(
        query="object detection",
        source_url="x",
        works=[work(1, source.display_name, "Detector", source_id="S-CVPR")],
    )
    merged, profiles, dynamic_count = merge_openalex_sources([cvpr], semantic, {source.id: source}, profile(), "conference")
    assert dynamic_count == 0
    assert merged[0]["openalexSourceId"] == "S-CVPR"
    ranked = rank_venues(profile(), preferences(), merged, semantic, profiles)
    assert ranked[0]["topicMatch"] is not None
    assert ranked[0]["topicMatch"] > 0

    miccai = SourceProfile(
        id="S-MICCAI",
        display_name="Medical Image Computing and Computer Assisted Intervention – MICCAI",
        source_type="conference",
        abbreviated_title="MICCAI",
        topics=(SourceTopic("T-MED", "Medical Image Segmentation", 900),),
    )
    semantic2 = SemanticSearchResult(query="medical segmentation", source_url="x", works=[])
    merged2, _, dynamic_count2 = merge_openalex_sources([], semantic2, {miccai.id: miccai}, brdg_profile(), "conference")
    assert dynamic_count2 == 1
    assert merged2[0]["title"] == "MICCAI"
    assert merged2[0]["ccf"] == "U"


def test_reference_section_excludes_front_matter_publication_watermark() -> None:
    text = "This CVPR paper is the Open Access accepted version.\nIntroduction...\nReferences\n[1] A paper in MICCAI.\n[2] A paper in ECCV."
    section = _find_reference_section(text)
    assert "This CVPR paper" not in section
    assert section.startswith("References")
    assert reference_count(section, conference("CVPR", "IEEE/CVF Conference on Computer Vision and Pattern Recognition")) == 0
    assert reference_count(section, conference("MICCAI", "Medical Image Computing and Computer Assisted Intervention")) == 1


def test_one_direct_hit_does_not_overrule_strong_scope_and_reference_evidence() -> None:
    venues = [
        conference("CVPR", "IEEE/CVF Conference on Computer Vision and Pattern Recognition"),
        conference("ICLR", "International Conference on Learning Representations"),
    ]
    semantic = SemanticSearchResult(
        query="surgical segmentation", source_url="x",
        works=[work(1, "International Conference on Learning Representations", "A generic representation-learning paper", source_id="S-ICLR")],
    )
    references = "References\n[1] In CVPR.\n[2] In CVPR.\n[3] In CVPR.\n[4] In ECCV."
    ranked = rank_venues(brdg_profile(), preferences(), venues, semantic, reference_text=references)
    by_name = {r["venue"]["title"]: r for r in ranked}
    assert by_name["ICLR"]["semanticMatch"] <= 45
    assert by_name["CVPR"]["researchMatch"] > by_name["ICLR"]["researchMatch"]


def test_semantic_query_prioritizes_problem_and_is_bounded() -> None:
    p = profile()
    p["summary"] = p["summary"] * 100
    query = build_semantic_query(p)
    assert query.startswith("Can DETR become a real-time object detector")
    assert len(query) <= 1950
