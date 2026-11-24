from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from typing import Any
import re

import httpx
import yaml

SOURCES = [
    "https://ccfddl.com/conference/allconf.yml",
    "https://ccfddl.github.io/conference/allconf.yml",
    "https://raw.githubusercontent.com/ccfddl/ccfddl.github.io/master/conference/allconf.yml",
    "https://raw.githubusercontent.com/ccfddl/ccfddl.github.io/main/conference/allconf.yml",
]


@dataclass(frozen=True)
class ConferenceFetchResult:
    items: list[dict[str, Any]]
    source_url: str
    source_label: str
    source_tier: str = "aggregator"


def _deadline_in_utc(value: str, zone: str) -> datetime | None:
    if not value or value == "TBD":
        return None
    try:
        local = datetime.strptime(value.replace("T", " "), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
    z = zone.strip() or "UTC"
    if z.lower() == "aoe":
        tz = timezone(timedelta(hours=-12))
    elif z.upper() == "PT":
        try:
            tz = ZoneInfo("America/Los_Angeles")
        except ZoneInfoNotFoundError:
            # On Windows, the standard library may not have an IANA timezone
            # database unless the `tzdata` package is installed.  The project
            # declares tzdata as a runtime dependency, but a missing database
            # must never make the entire CCFDDL catalog unusable.
            return None
    elif z.upper().startswith("UTC"):
        suffix = z[3:]
        if not suffix:
            tz = timezone.utc
        else:
            sign = 1 if suffix.startswith("+") else -1
            raw_offset = suffix[1:]
            if ":" in raw_offset:
                hh, mm = raw_offset.split(":", 1)
            else:
                hh, mm = raw_offset, "0"
            try:
                tz = timezone(sign * timedelta(hours=int(hh), minutes=int(mm)))
            except (TypeError, ValueError):
                return None
    elif "/" in z:
        # Some CCFDDL editions use an explicit IANA timezone such as
        # America/Los_Angeles instead of the schema shorthand PT.  Supporting
        # it preserves daylight-saving rules and avoids treating local time as
        # a fixed offset.
        try:
            tz = ZoneInfo(z)
        except ZoneInfoNotFoundError:
            return None
    else:
        # Unknown zones are intentionally not guessed as UTC.
        return None
    return local.replace(tzinfo=tz).astimezone(timezone.utc)


def parse_catalog(raw: Any, source_url: str, current_year: int | None = None) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        raise ValueError("CCFDDL allconf.yml root must be a list")
    year_now = current_year or datetime.now(timezone.utc).year
    items: list[dict[str, Any]] = []
    for conference in raw:
        if not isinstance(conference, dict):
            continue
        confs = conference.get("confs") or []
        rank = conference.get("rank") or {}
        for edition in confs:
            if not isinstance(edition, dict):
                continue
            year = edition.get("year")
            if not isinstance(year, int) or year < year_now - 1:
                continue
            timeline = edition.get("timeline") or []
            preferred: dict[str, Any] | None = None
            now = datetime.now(timezone.utc)
            dated: list[tuple[datetime, dict[str, Any]]] = []
            for entry in timeline:
                if not isinstance(entry, dict):
                    continue
                parsed = _deadline_in_utc(str(entry.get("deadline") or ""), str(edition.get("timezone") or "UTC"))
                if parsed is not None:
                    dated.append((parsed, entry))
            future = sorted((pair for pair in dated if pair[0] >= now), key=lambda pair: pair[0])
            past = sorted((pair for pair in dated if pair[0] < now), key=lambda pair: pair[0], reverse=True)
            preferred = (future[0][1] if future else past[0][1] if past else None)
            if preferred is None and timeline and isinstance(timeline[0], dict):
                preferred = timeline[0]
            edition_id = str(edition.get("id") or f"{conference.get('title','conf').lower()}-{year}")
            series_title = str(conference.get("title") or "")
            series_slug = re.sub(r"[^a-z0-9]+", "-", series_title.lower()).strip("-")
            items.append({
                "type": "conference",
                "id": f"conference:{edition_id}",
                "seriesId": f"conference-series:{series_slug}",
                "title": series_title,
                "description": str(conference.get("description") or ""),
                "sub": str(conference.get("sub") or "MX"),
                "ccf": str(rank.get("ccf") or "N"),
                "core": str(rank.get("core") or "N"),
                "dblp": str(conference.get("dblp") or ""),
                "year": year,
                "editionId": edition_id,
                "link": str(edition.get("link") or ""),
                "deadline": preferred.get("deadline") if preferred else None,
                "abstractDeadline": preferred.get("abstract_deadline") if preferred else None,
                "timeline": [
                    {
                        "deadline": entry.get("deadline"),
                        "abstractDeadline": entry.get("abstract_deadline"),
                        "comment": entry.get("comment"),
                    }
                    for entry in timeline if isinstance(entry, dict)
                ],
                "timezone": str(edition.get("timezone") or ""),
                "date": str(edition.get("date") or ""),
                "place": str(edition.get("place") or ""),
                "source": source_url,
                "ccfSource": "CCFDDL",
            })
    if len(items) < 50:
        raise ValueError(f"CCFDDL catalog unexpectedly small: {len(items)} editions")
    return items


def _name_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _overlay_official_ccf(items: list[dict[str, Any]], official: list[dict[str, Any]]) -> int:
    by_name: dict[str, dict[str, Any]] = {}
    for row in official:
        for value in (str(row.get("shortName") or ""), str(row.get("name") or "")):
            key = _name_key(value)
            if key:
                by_name[key] = row
    matched = 0
    for item in items:
        row = None
        for value in (str(item.get("title") or ""), str(item.get("description") or "")):
            key = _name_key(value)
            if key and key in by_name:
                row = by_name[key]
                break
        if row is None:
            continue
        item["ccf"] = str(row.get("ccf") or item.get("ccf") or "N")
        item["sub"] = str(row.get("sub") or item.get("sub") or "MX")
        item["ccfSource"] = "CCF official seventh edition"
        item["ccfSourceVersion"] = str(row.get("sourceVersion") or "")
        item["ccfOfficialLink"] = row.get("link")
        matched += 1
    return matched


async def fetch_conferences(client: httpx.AsyncClient) -> ConferenceFetchResult:
    errors: list[str] = []
    for source in SOURCES:
        try:
            response = await client.get(source, headers={"User-Agent": "SuperScholar/3.7 venue-sync"}, follow_redirects=True)
            response.raise_for_status()
            raw = yaml.safe_load(response.text)
            items = parse_catalog(raw, source)
            label = "CCFDDL conference edition/deadline dataset"
            try:
                # CCFDDL remains the edition/deadline/location source.  Rank/category are
                # overlaid from the official CCF seventh-edition directory when available.
                from .ccf import fetch_official_conferences
                official = await fetch_official_conferences(client)
                matched = _overlay_official_ccf(items, official)
                label += f" · official CCF rank overlay ({matched} editions matched)"
            except Exception as official_exc:
                label += f" · CCF rank fallback from CCFDDL ({official_exc})"
            return ConferenceFetchResult(items, source, label)
        except Exception as exc:
            errors.append(f"{source}: {exc}")
    raise RuntimeError(" | ".join(errors))
