from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup, Tag

CCF_RELEASE = "CCF 第七版，2026-03-31 正式发布，2026-04-09 勘误更新"
CCF_OFFICIAL_INDEX = "https://www.ccf.org.cn/Academic_Evaluation/By_category/"
CCF_MIRROR = "https://raw.githubusercontent.com/haozhou-wong/ccf-recommended-list-2026-markdown/main/data/ccf-2026.json"
EXPECTED_JOURNAL_PLACEMENTS = 295
EXPECTED_UNIQUE_JOURNALS = 291

AREAS: list[tuple[str, str, str]] = [
    ("DS", "计算机体系结构/并行与分布计算/存储系统", "https://www.ccf.org.cn/Academic_Evaluation/ARCH_DCP_SS/"),
    ("NW", "计算机网络", "https://www.ccf.org.cn/Academic_Evaluation/CN/"),
    ("SC", "网络与信息安全", "https://www.ccf.org.cn/Academic_Evaluation/NIS/"),
    ("SE", "软件工程/系统软件/程序设计语言", "https://www.ccf.org.cn/Academic_Evaluation/TCSE_SS_PDL/"),
    ("DB", "数据库/数据挖掘/内容检索", "https://www.ccf.org.cn/Academic_Evaluation/DM_CS/"),
    ("CT", "计算机科学理论", "https://www.ccf.org.cn/Academic_Evaluation/TCS/"),
    ("CG", "计算机图形学与多媒体", "https://www.ccf.org.cn/Academic_Evaluation/CGAndMT/"),
    ("AI", "人工智能", "https://www.ccf.org.cn/Academic_Evaluation/AI/"),
    ("HI", "人机交互与普适计算", "https://www.ccf.org.cn/Academic_Evaluation/HCIAndPC/"),
    ("MX", "交叉/综合/新兴", "https://www.ccf.org.cn/Academic_Evaluation/Cross_Compre_Emerging/"),
]
NAME_TO_CODE = {name: code for code, name, _ in AREAS}


@dataclass(frozen=True)
class JournalFetchResult:
    items: list[dict[str, Any]]
    source_url: str
    source_label: str
    source_tier: str


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()



def _journal_id(short_name: str, full_name: str) -> str:
    # Identity must not change when a future CCF edition changes rank/category.
    base = full_name or short_name
    slug = re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-")[:180]
    return f"journal:{slug}"


def _canonicalize_journal_placements(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge the 295 official CCF placements into stable journal identities.

    The seventh-edition directory contains a small number of journals listed in more
    than one CCF domain. 295 is therefore the number of catalog placements, not the
    number of unique journal identities. Super Scholar preserves every placement in
    ``ccfEntries`` while exposing one stable venue object for recommendation.
    """
    rank_value = {"A": 3, "B": 2, "C": 1}
    by_id: dict[str, dict[str, Any]] = {}
    for raw in items:
        item = dict(raw)
        key = str(item.get("id") or "")
        if not key:
            continue
        entry = {
            "sub": item.get("sub"),
            "ccf": item.get("ccf"),
            "source": item.get("source"),
            "sourceVersion": item.get("sourceVersion"),
        }
        existing = by_id.get(key)
        if existing is None:
            item["ccfEntries"] = [entry]
            item["ccfVerified"] = True
            by_id[key] = item
            continue
        entries = list(existing.get("ccfEntries") or [])
        if not any(e.get("sub") == entry["sub"] and e.get("ccf") == entry["ccf"] for e in entries):
            entries.append(entry)
        existing["ccfEntries"] = entries
        if rank_value.get(str(item.get("ccf")), 0) > rank_value.get(str(existing.get("ccf")), 0):
            existing["ccf"] = item.get("ccf")
            existing["sub"] = item.get("sub")
        # Keep the richest stable metadata without changing identity.
        for field in ("shortName", "name", "publisher", "link"):
            if not existing.get(field) and item.get(field):
                existing[field] = item[field]
        by_id[key] = existing
    return list(by_id.values())

def _rank_from_text(text: str) -> str | None:
    text = _clean(text)
    for rank in ("A", "B", "C"):
        if text in {f"{rank}类", f"{rank} 类"}:
            return rank
    return None


def _closest_section(table: Tag) -> tuple[str | None, str | None]:
    rank: str | None = None
    for node in table.find_all_previous(["h1", "h2", "h3", "h4", "h5", "div", "p"], limit=80):
        text = _clean(node.get_text(" ", strip=True))
        if rank is None:
            rank = _rank_from_text(text)
        if "推荐国际学术会议" in text:
            return "conference", rank
        if "推荐国际学术刊物" in text or "推荐国际学术期刊" in text:
            return "journal", rank
    return None, rank


def _closest_context(table: Tag) -> tuple[bool, str | None]:
    section, rank = _closest_section(table)
    return section == "journal", rank


def parse_official_area(html: str, code: str, source_url: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "lxml")
    items: list[dict[str, Any]] = []
    for table in soup.find_all("table"):
        is_journal, rank = _closest_context(table)
        if not is_journal or rank not in {"A", "B", "C"}:
            continue
        for row in table.find_all("tr"):
            cells = [_clean(cell.get_text(" ", strip=True)) for cell in row.find_all(["td", "th"])]
            if len(cells) < 3 or any("刊物全称" in cell for cell in cells):
                continue
            # Official tables are: 序号 / 刊物名称 / 刊物全称 / 出版社 / 地址.
            short_name = cells[1] if len(cells) >= 2 else ""
            full_name = cells[2] if len(cells) >= 3 else ""
            publisher = cells[3] if len(cells) >= 4 else ""
            if not full_name or full_name in {"刊物全称", "会议全称"}:
                continue
            anchor = row.find("a", href=True)
            link = urljoin(source_url, anchor["href"]) if anchor else None
            journal_id = _journal_id(short_name, full_name)
            items.append({
                "type": "journal",
                "id": journal_id,
                "seriesId": journal_id,
                "shortName": short_name or full_name,
                "name": full_name,
                "publisher": publisher,
                "sub": code,
                "ccf": rank,
                "link": link,
                "source": source_url,
                "sourceVersion": CCF_RELEASE,
                "metrics": {},
            })
    return items


def parse_official_conference_area(html: str, code: str, source_url: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "lxml")
    items: list[dict[str, Any]] = []
    for table in soup.find_all("table"):
        section, rank = _closest_section(table)
        if section != "conference" or rank not in {"A", "B", "C"}:
            continue
        for row in table.find_all("tr"):
            cells = [_clean(cell.get_text(" ", strip=True)) for cell in row.find_all(["td", "th"])]
            if len(cells) < 3 or any("会议全称" in cell for cell in cells):
                continue
            short_name = cells[1] if len(cells) >= 2 else ""
            full_name = cells[2] if len(cells) >= 3 else ""
            if not full_name or full_name == "会议全称":
                continue
            anchor = row.find("a", href=True)
            link = urljoin(source_url, anchor["href"]) if anchor else None
            items.append({
                "shortName": short_name or full_name,
                "name": full_name,
                "sub": code,
                "ccf": rank,
                "link": link,
                "source": source_url,
                "sourceVersion": CCF_RELEASE,
            })
    return items


async def fetch_official_conferences(client: httpx.AsyncClient) -> list[dict[str, Any]]:
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; SuperScholar/3.7; +local research tool)",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
        "Accept": "text/html,application/xhtml+xml",
    }

    async def one(code: str, _name: str, url: str) -> list[dict[str, Any]]:
        response = await client.get(url, headers=headers, follow_redirects=True)
        response.raise_for_status()
        return parse_official_conference_area(response.text, code, url)

    results = await asyncio.gather(*(one(*area) for area in AREAS), return_exceptions=True)
    items: list[dict[str, Any]] = []
    failed: list[str] = []
    for area, result in zip(AREAS, results, strict=True):
        if isinstance(result, Exception):
            failed.append(f"{area[0]}: {result}")
        else:
            items.extend(result)
    covered = {item["sub"] for item in items}
    if failed or len(items) < 100 or len(covered) != 10:
        raise RuntimeError(
            f"Official CCF conference parse incomplete: conferences={len(items)}, areas={len(covered)}, failures={'; '.join(failed) or 'none'}"
        )
    return items


async def _fetch_official(client: httpx.AsyncClient) -> JournalFetchResult:
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; SuperScholar/2.0; +local research tool)",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
        "Accept": "text/html,application/xhtml+xml",
    }

    async def one(code: str, _name: str, url: str) -> list[dict[str, Any]]:
        response = await client.get(url, headers=headers, follow_redirects=True)
        response.raise_for_status()
        return parse_official_area(response.text, code, url)

    results = await asyncio.gather(*(one(*area) for area in AREAS), return_exceptions=True)
    items: list[dict[str, Any]] = []
    failed: list[str] = []
    for area, result in zip(AREAS, results, strict=True):
        if isinstance(result, Exception):
            failed.append(f"{area[0]}: {result}")
        else:
            items.extend(result)
    covered = {item["sub"] for item in items}
    canonical = _canonicalize_journal_placements(items)
    if (
        failed
        or len(items) != EXPECTED_JOURNAL_PLACEMENTS
        or len(canonical) != EXPECTED_UNIQUE_JOURNALS
        or len(covered) != 10
    ):
        raise RuntimeError(
            "Official CCF parse incomplete: "
            f"placements={len(items)}/{EXPECTED_JOURNAL_PLACEMENTS}, "
            f"unique={len(canonical)}/{EXPECTED_UNIQUE_JOURNALS}, "
            f"areas={len(covered)}/10, failures={'; '.join(failed) or 'none'}"
        )
    return JournalFetchResult(canonical, CCF_OFFICIAL_INDEX, CCF_RELEASE, "official")


def parse_mirror(payload: dict[str, Any]) -> list[dict[str, Any]]:
    metadata = payload.get("metadata") or {}
    if metadata.get("year") != 2026 or metadata.get("edition") != "第七版" or metadata.get("publisher") != "中国计算机学会":
        raise ValueError("Structured mirror metadata does not match CCF seventh edition")
    domains = payload.get("domains")
    if not isinstance(domains, list) or len(domains) != 10:
        raise ValueError("Structured mirror must contain all ten CCF domains")
    items: list[dict[str, Any]] = []
    for domain in domains:
        name = _clean(str(domain.get("name", "")))
        code = NAME_TO_CODE.get(name)
        if not code:
            raise ValueError(f"Unknown CCF domain in mirror: {name}")
        journals = domain.get("journals") or {}
        for rank in ("A", "B", "C"):
            for item in journals.get(rank, []) or []:
                short_name = _clean(str(item.get("abbr", "")))
                full_name = _clean(str(item.get("full_name", "")))
                if not full_name:
                    continue
                publisher = _clean(str(item.get("publisher", "")))
                link = item.get("url") or None
                journal_id = _journal_id(short_name, full_name)
                items.append({
                    "type": "journal",
                    "id": journal_id,
                    "seriesId": journal_id,
                    "shortName": short_name or full_name,
                    "name": full_name,
                    "publisher": publisher,
                    "sub": code,
                    "ccf": rank,
                    "link": link,
                    "source": CCF_MIRROR,
                    "sourceVersion": CCF_RELEASE,
                    "metrics": {},
                })
    canonical = _canonicalize_journal_placements(items)
    if len(items) != EXPECTED_JOURNAL_PLACEMENTS:
        raise ValueError(
            f"Expected {EXPECTED_JOURNAL_PLACEMENTS} CCF journal placements, got {len(items)}"
        )
    if len(canonical) != EXPECTED_UNIQUE_JOURNALS:
        raise ValueError(
            f"Expected {EXPECTED_UNIQUE_JOURNALS} unique CCF journal identities after placement merge, got {len(canonical)}"
        )
    # Anchors visible on the official directory pages and stable enough to detect schema/content drift.
    anchors = {
        ("AI", "A", "Artificial Intelligence"),
        ("SC", "A", "IEEE Transactions on Dependable and Secure Computing"),
        ("DB", "A", "ACM Transactions on Database Systems"),
        ("CT", "A", "IEEE Transactions on Information Theory"),
        ("MX", "A", "Journal of the ACM"),
    }
    actual = {(e["sub"], e["ccf"], x["name"]) for x in canonical for e in (x.get("ccfEntries") or [])}
    missing = anchors - actual
    if missing:
        raise ValueError(f"CCF mirror anchor validation failed: {sorted(missing)}")
    return canonical


async def _fetch_mirror(client: httpx.AsyncClient) -> JournalFetchResult:
    response = await client.get(CCF_MIRROR, headers={"User-Agent": "SuperScholar/2.0 venue-sync"}, follow_redirects=True)
    response.raise_for_status()
    payload = response.json()
    items = parse_mirror(payload)
    return JournalFetchResult(
        items,
        CCF_MIRROR,
        "CCF 第七版结构化镜像（由官方 PDF 转换，并通过数量、领域和锚点校验）",
        "verified_mirror",
    )


async def fetch_journals(client: httpx.AsyncClient) -> JournalFetchResult:
    official_error: Exception | None = None
    try:
        return await _fetch_official(client)
    except Exception as exc:  # The CCF website occasionally throttles automated requests.
        official_error = exc
    try:
        return await _fetch_mirror(client)
    except Exception as mirror_error:
        raise RuntimeError(f"CCF official source failed: {official_error}; structured mirror failed: {mirror_error}") from mirror_error
