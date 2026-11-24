from __future__ import annotations

from datetime import datetime, timezone

from app.services.ccfddl import _deadline_in_utc


def test_aoe_deadline_is_utc_minus_12():
    value = _deadline_in_utc("2026-10-12 23:59:59", "AoE")
    assert value == datetime(2026, 10, 13, 11, 59, 59, tzinfo=timezone.utc)


def test_explicit_utc_offset():
    value = _deadline_in_utc("2026-10-09 11:59:00", "UTC+8")
    assert value == datetime(2026, 10, 9, 3, 59, 0, tzinfo=timezone.utc)


def test_pt_uses_iana_timezone_and_dst():
    # August in America/Los_Angeles is PDT (UTC-7), not a hard-coded UTC-8.
    value = _deadline_in_utc("2026-08-25 12:00:00", "PT")
    assert value == datetime(2026, 8, 25, 19, 0, 0, tzinfo=timezone.utc)


def test_explicit_iana_timezone_is_supported():
    value = _deadline_in_utc("2026-08-25 12:00:00", "America/Los_Angeles")
    assert value == datetime(2026, 8, 25, 19, 0, 0, tzinfo=timezone.utc)


def test_unknown_timezone_is_not_guessed():
    assert _deadline_in_utc("2026-09-01 12:00:00", "Not/A_Real_Zone") is None

from app.services.ccfddl import _overlay_official_ccf, parse_catalog


def test_ccfddl_keeps_full_timeline_and_overlays_official_rank():
    raw = [{
        "title": "CVPR",
        "description": "IEEE/CVF Conference on Computer Vision and Pattern Recognition",
        "sub": "AI",
        "rank": {"ccf": "B", "core": "A*"},
        "dblp": "cvpr",
        "confs": [{
            "year": 2099,
            "id": "cvpr99",
            "link": "https://example.test/cvpr",
            "timeline": [
                {"deadline": "2098-11-01 23:59:59", "comment": "round 1"},
                {"deadline": "2098-11-15 23:59:59", "comment": "round 2"},
            ],
            "timezone": "AoE",
            "date": "June 2099",
            "place": "TBD",
        }],
    }]
    # parse_catalog has a safety lower bound for production feeds, so replicate a valid-size feed.
    items = parse_catalog(raw * 50, "test", current_year=2098)
    assert items[0]["seriesId"] == "conference-series:cvpr"
    assert len(items[0]["timeline"]) == 2
    official = [{"shortName": "CVPR", "name": "IEEE/CVF Conference on Computer Vision and Pattern Recognition", "sub": "AI", "ccf": "A", "sourceVersion": "CCF7", "link": "https://ccf.test"}]
    matched = _overlay_official_ccf(items, official)
    assert matched == len(items)
    assert items[0]["ccf"] == "A"
    assert items[0]["ccfSource"].startswith("CCF official")
