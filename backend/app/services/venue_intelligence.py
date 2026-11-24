from __future__ import annotations

import math
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

try:
    import fitz  # PyMuPDF
except Exception:  # pragma: no cover - dependency is present in production requirements
    fitz = None

from ..models import Project
from .openalex import SemanticWork, SourceProfile

SCOPE_LABELS: dict[str, str] = {
    "computer_vision": "Computer Vision",
    "medical_imaging": "Medical Imaging / Surgical Vision",
    "machine_learning": "Machine Learning",
    "efficient_ai": "Efficient / Real-time AI",
    "nlp": "Natural Language Processing",
    "robotics": "Robotics",
    "multiagent": "Multi-Agent Systems",
    "data_mining": "Data Mining",
    "information_retrieval": "Information Retrieval",
    "databases": "Databases",
    "security": "Security",
    "systems": "Computer Systems",
    "software_engineering": "Software Engineering",
    "networks": "Computer Networks",
    "theory": "Theory / Algorithms",
    "graphics": "Computer Graphics",
    "multimedia": "Multimedia",
    "hci": "Human-Computer Interaction",
    "speech": "Speech / Audio",
    "bioinformatics": "Bioinformatics / Computational Biology",
}

# Phrase-level ontology. Generic words such as "agent" are intentionally absent: a paper
# describing three internal "agents" must not be mistaken for AAMAS-style multi-agent work.
SCOPE_TERMS: dict[str, tuple[tuple[str, float], ...]] = {
    "computer_vision": (
        ("computer vision", 1.3), ("semantic segmentation", 1.6), ("image segmentation", 1.5),
        ("instance segmentation", 1.5), ("object detection", 1.5), ("superpixel", 1.5),
        ("dense prediction", 1.2), ("boundary detection", 1.2), ("image recognition", 1.1),
        ("visual recognition", 1.1), ("image analysis", 0.9), ("segmentation mask", 1.0),
    ),
    "medical_imaging": (
        ("medical imaging", 1.6), ("medical image", 1.6), ("surgical", 1.5), ("surgery", 1.3),
        ("endovis", 1.6), ("cholec", 1.5), ("laparoscopic", 1.5), ("instrument segmentation", 1.5),
        ("surgical scene", 1.6), ("biomedical image", 1.4), ("anatomical", 1.1),
    ),
    "machine_learning": (
        ("machine learning", 1.3), ("deep learning", 1.1), ("neural network", 1.0),
        ("transformer", 0.8), ("contrastive learning", 1.0), ("representation learning", 1.0),
        ("self-supervised", 0.9), ("reinforcement learning", 1.1),
    ),
    "efficient_ai": (
        ("real-time", 1.4), ("real time", 1.4), ("efficiency", 1.0), ("efficient", 0.9),
        ("latency", 1.0), ("fps", 1.1), ("gflops", 1.0), ("throughput", 0.8),
        ("resource-constrained", 1.0), ("lightweight", 1.0), ("edge device", 1.0),
    ),
    "nlp": (
        ("natural language processing", 1.7), ("computational linguistics", 1.7), ("language model", 1.5),
        ("machine translation", 1.4), ("text generation", 1.3), ("question answering", 1.2),
        ("information extraction", 1.0), ("large language model", 1.5), ("llm", 1.3),
    ),
    "robotics": (
        ("robotics", 1.6), ("robot manipulation", 1.5), ("motion planning", 1.4), ("slam", 1.5),
        ("robot navigation", 1.4), ("control policy", 1.0), ("autonomous robot", 1.3),
    ),
    "multiagent": (
        ("multi-agent", 1.8), ("multiagent", 1.8), ("multi agent", 1.8),
        ("autonomous agents", 1.7), ("agent-based system", 1.5), ("agent systems", 1.5),
        ("strategic agents", 1.4), ("mechanism design", 1.0),
    ),
    "data_mining": (("data mining", 1.7), ("knowledge discovery", 1.4), ("graph mining", 1.3), ("web mining", 1.2)),
    "information_retrieval": (("information retrieval", 1.7), ("search engine", 1.3), ("document retrieval", 1.4), ("ranking model", 1.0)),
    "databases": (("database", 1.5), ("query optimization", 1.5), ("transaction processing", 1.3), ("data management", 1.0)),
    "security": (("cybersecurity", 1.6), ("network security", 1.5), ("malware", 1.4), ("vulnerability", 1.4), ("cryptography", 1.5), ("privacy", 1.0)),
    "systems": (("operating system", 1.5), ("distributed system", 1.4), ("cloud computing", 1.2), ("computer architecture", 1.5), ("storage system", 1.3)),
    "software_engineering": (("software engineering", 1.7), ("program analysis", 1.3), ("software testing", 1.3), ("code generation", 1.1), ("program repair", 1.3)),
    "networks": (("computer network", 1.6), ("networking", 1.3), ("congestion control", 1.4), ("routing", 1.1), ("wireless network", 1.4)),
    "theory": (("algorithmic theory", 1.5), ("learning theory", 1.6), ("computational complexity", 1.6), ("approximation algorithm", 1.4), ("theorem", 0.7)),
    "graphics": (("computer graphics", 1.7), ("rendering", 1.4), ("neural rendering", 1.5), ("geometry processing", 1.3), ("3d reconstruction", 1.2)),
    "multimedia": (("multimedia", 1.6), ("video understanding", 1.3), ("multimodal", 1.1), ("cross-modal", 1.1)),
    "hci": (("human-computer interaction", 1.7), ("human computer interaction", 1.7), ("user study", 1.2), ("usability", 1.2), ("interaction design", 1.3)),
    "speech": (("speech recognition", 1.6), ("speech synthesis", 1.5), ("audio processing", 1.3), ("speaker recognition", 1.4)),
    "bioinformatics": (("bioinformatics", 1.7), ("computational biology", 1.6), ("protein", 1.0), ("genomic", 1.2), ("molecular", 0.8)),
}

# Venue-family priors are scope metadata, not paper-specific shortcuts. They are used only
# as one content signal and can be overridden/enriched by OpenAlex source topics.
VENUE_SCOPE_OVERRIDES: dict[str, dict[str, float]] = {
    # vision
    "CVPR": {"computer_vision": 1.0, "machine_learning": 0.35},
    "ICCV": {"computer_vision": 1.0, "machine_learning": 0.35},
    "ECCV": {"computer_vision": 1.0, "machine_learning": 0.35},
    "WACV": {"computer_vision": 1.0, "machine_learning": 0.25},
    "BMVC": {"computer_vision": 1.0}, "ACCV": {"computer_vision": 1.0},
    "IJCV": {"computer_vision": 1.0}, "TPAMI": {"computer_vision": 0.85, "machine_learning": 0.45},
    "T-PAMI": {"computer_vision": 0.85, "machine_learning": 0.45},
    # medical imaging / surgical vision
    "MICCAI": {"medical_imaging": 1.0, "computer_vision": 0.8, "machine_learning": 0.45},
    "MIDL": {"medical_imaging": 1.0, "computer_vision": 0.65, "machine_learning": 0.55},
    "IPMI": {"medical_imaging": 1.0, "computer_vision": 0.55},
    "TMI": {"medical_imaging": 1.0, "computer_vision": 0.55},
    "IEEE TRANSACTIONS ON MEDICAL IMAGING": {"medical_imaging": 1.0, "computer_vision": 0.55},
    "MEDIA": {"medical_imaging": 1.0, "computer_vision": 0.45},
    "MEDICAL IMAGE ANALYSIS": {"medical_imaging": 1.0, "computer_vision": 0.55, "machine_learning": 0.25},
    "JOURNAL OF BIOMEDICAL AND HEALTH INFORMATICS": {"medical_imaging": 0.85, "machine_learning": 0.35},
    "PATTERN RECOGNITION": {"computer_vision": 0.85, "machine_learning": 0.4},
    "IEEE TRANSACTIONS ON IMAGE PROCESSING": {"computer_vision": 0.9},
    "COMPUTER VISION AND IMAGE UNDERSTANDING": {"computer_vision": 1.0},
    "IEEE TRANSACTIONS ON CIRCUITS AND SYSTEMS FOR VIDEO TECHNOLOGY": {"computer_vision": 0.65, "multimedia": 0.6},
    "IEEE TRANSACTIONS ON MULTIMEDIA": {"multimedia": 0.9, "computer_vision": 0.45},
    # general ML/AI
    "ICLR": {"machine_learning": 1.0}, "ICML": {"machine_learning": 1.0},
    "NEURIPS": {"machine_learning": 1.0}, "AAAI": {"machine_learning": 0.65},
    "IJCAI": {"machine_learning": 0.65},
    # NLP
    "ACL": {"nlp": 1.0}, "EMNLP": {"nlp": 1.0}, "NAACL": {"nlp": 1.0},
    "COLING": {"nlp": 1.0},
    # robotics / agents
    "ICRA": {"robotics": 1.0, "computer_vision": 0.2}, "IROS": {"robotics": 1.0, "computer_vision": 0.2},
    "RSS": {"robotics": 1.0}, "CORL": {"robotics": 1.0, "machine_learning": 0.35},
    "AAMAS": {"multiagent": 1.0, "machine_learning": 0.15},
    # DB/IR/mining/security/systems/etc.
    "KDD": {"data_mining": 1.0, "machine_learning": 0.35}, "ICDM": {"data_mining": 1.0},
    "SIGIR": {"information_retrieval": 1.0, "nlp": 0.25},
    "SIGMOD": {"databases": 1.0}, "VLDB": {"databases": 1.0}, "ICDE": {"databases": 1.0},
    "CCS": {"security": 1.0}, "S&P": {"security": 1.0}, "NDSS": {"security": 1.0}, "USENIX SECURITY": {"security": 1.0},
    "SOSP": {"systems": 1.0}, "OSDI": {"systems": 1.0}, "ISCA": {"systems": 1.0}, "ASPLOS": {"systems": 1.0},
    "ICSE": {"software_engineering": 1.0}, "FSE": {"software_engineering": 1.0}, "ASE": {"software_engineering": 1.0},
    "SIGCOMM": {"networks": 1.0}, "INFOCOM": {"networks": 1.0},
    "STOC": {"theory": 1.0}, "FOCS": {"theory": 1.0}, "SODA": {"theory": 1.0}, "ALT": {"theory": 0.85, "machine_learning": 0.45},
    "SIGGRAPH": {"graphics": 1.0}, "SIGGRAPH ASIA": {"graphics": 1.0},
    "ACM MM": {"multimedia": 1.0, "computer_vision": 0.35},
    "CHI": {"hci": 1.0}, "UIST": {"hci": 1.0},
}

REFERENCE_HEADING_RE = re.compile(r"(?im)^\s*(?:\d+\.?\s*)?(references|bibliography)\s*$")


def _norm_text(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("text")
    return " ".join(str(value or "").split())


def profile_text(profile: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("researchProblem", "coreIdea", "summary"):
        text = _norm_text(profile.get(key))
        if text:
            parts.append(text)
    for key in ("topics", "methods", "datasets", "models", "metrics", "contributions"):
        parts.extend(_norm_text(x) for x in (profile.get(key) or []) if _norm_text(x))
    return " ".join(parts)


def scope_vector_from_text(text: str) -> dict[str, float]:
    hay = " ".join(text.lower().split())
    vector: dict[str, float] = {}
    for scope, terms in SCOPE_TERMS.items():
        raw = 0.0
        for phrase, weight in terms:
            occurrences = hay.count(phrase)
            if occurrences:
                raw += weight * min(2, occurrences)
        if raw > 0:
            # Saturate repeated wording so one verbose section cannot dominate.
            vector[scope] = min(1.0, raw / 2.6)
    return vector


def research_scope_vector(profile: dict[str, Any]) -> dict[str, float]:
    return scope_vector_from_text(profile_text(profile))


def _compact(value: str) -> str:
    return re.sub(r"[^A-Z0-9*+&-]+", "", value.upper())


def _venue_aliases(venue: dict[str, Any]) -> list[str]:
    raw: list[str] = []
    if venue.get("type") == "conference":
        raw.extend([str(venue.get("title") or ""), str(venue.get("description") or "")])
    else:
        raw.extend([str(venue.get("shortName") or ""), str(venue.get("name") or "")])
    raw.extend(str(x) for x in venue.get("openalexAliases") or [])
    raw.extend(str(x) for x in venue.get("dblpAliases") or [])
    raw.extend(str(x) for x in venue.get("crossrefAliases") or [])
    return list(dict.fromkeys(" ".join(x.split()).strip() for x in raw if x and x.strip()))


def venue_scope_vector(venue: dict[str, Any], source: SourceProfile | None = None) -> dict[str, float]:
    vector: dict[str, float] = {}
    aliases = _venue_aliases(venue)
    compact_aliases = {_compact(x) for x in aliases}
    for alias_key, override in VENUE_SCOPE_OVERRIDES.items():
        key = _compact(alias_key)
        if any(key and (key == x or (len(key) >= 4 and key in x)) for x in compact_aliases):
            for scope, value in override.items():
                vector[scope] = max(vector.get(scope, 0.0), value)

    source_topic_text = " ".join(t.name for t in source.topics) if source else ""
    inferred = scope_vector_from_text(" ".join(aliases) + " " + source_topic_text)
    for scope, value in inferred.items():
        # Topic/name inference supports the curated family prior rather than erasing it.
        vector[scope] = max(vector.get(scope, 0.0), value * 0.9)
    return vector


def cosine_score(left: dict[str, float], right: dict[str, float]) -> int | None:
    if not left or not right:
        return None
    keys = set(left) | set(right)
    dot = sum(left.get(k, 0.0) * right.get(k, 0.0) for k in keys)
    ln = math.sqrt(sum(v * v for v in left.values()))
    rn = math.sqrt(sum(v * v for v in right.values()))
    if ln <= 0 or rn <= 0:
        return None
    return max(0, min(100, round(100.0 * dot / (ln * rn))))


def matched_scope_labels(research: dict[str, float], venue: dict[str, float]) -> list[str]:
    shared = [(scope, research[scope] * venue[scope]) for scope in research.keys() & venue.keys()]
    shared.sort(key=lambda x: x[1], reverse=True)
    return [SCOPE_LABELS.get(scope, scope) for scope, value in shared if value > 0.04][:5]


def research_topic_vector(works: Iterable[SemanticWork]) -> tuple[dict[str, float], dict[str, str]]:
    vector: dict[str, float] = Counter()
    names: dict[str, str] = {}
    for rank, work in enumerate(works, start=1):
        rank_weight = 1.0 / math.log2(rank + 1.0)
        for index, topic_id in enumerate(work.topic_ids):
            if not topic_id:
                continue
            score = work.topic_scores[index] if index < len(work.topic_scores) else 0.0
            vector[topic_id] += rank_weight * max(0.15, score)
            if index < len(work.topics):
                names[topic_id] = work.topics[index]
    total = sum(vector.values())
    if total > 0:
        vector = {k: v / total for k, v in vector.items()}
    return dict(vector), names


def source_topic_vector(source: SourceProfile | None) -> tuple[dict[str, float], dict[str, str]]:
    if source is None or not source.topics:
        return {}, {}
    raw: dict[str, float] = {}
    names: dict[str, str] = {}
    for index, topic in enumerate(source.topics):
        if not topic.id:
            continue
        # OpenAlex source topic payloads can expose count/share/score depending on API
        # generation. Ranking position is a safe fallback when the numeric score is absent.
        weight = topic.score if topic.score > 0 else 1.0 / (index + 1.0)
        raw[topic.id] = max(raw.get(topic.id, 0.0), weight)
        names[topic.id] = topic.name
    norm = math.sqrt(sum(v * v for v in raw.values()))
    if norm > 0:
        raw = {k: v / norm for k, v in raw.items()}
    return raw, names


def topic_fit_score(research_topics: dict[str, float], source: SourceProfile | None) -> tuple[int | None, list[str]]:
    source_topics, source_names = source_topic_vector(source)
    if not research_topics or not source_topics:
        return None, []
    rnorm = math.sqrt(sum(v * v for v in research_topics.values()))
    snorm = math.sqrt(sum(v * v for v in source_topics.values()))
    if rnorm <= 0 or snorm <= 0:
        return None, []
    common = research_topics.keys() & source_topics.keys()
    dot = sum(research_topics[k] * source_topics[k] for k in common)
    score = max(0, min(100, round(100 * dot / (rnorm * snorm))))
    matched = sorted(common, key=lambda k: research_topics[k] * source_topics[k], reverse=True)
    return score, [source_names.get(k, k) for k in matched[:5]]


def _find_reference_section(text: str) -> str:
    matches = list(REFERENCE_HEADING_RE.finditer(text))
    if matches:
        return text[matches[-1].start():]
    # Conservative fallback: use only the tail, never the title/abstract where an accepted
    # paper watermark could leak its actual publication venue into the ranking signal.
    start = max(0, int(len(text) * 0.65))
    return text[start:]


def extract_reference_text(project: Project, *, max_chars: int = 160_000) -> str:
    candidates = sorted(project.materials, key=lambda m: (m.kind != "manuscript", m.created_at))
    chunks: list[str] = []
    for material in candidates:
        ext = str(material.extension or "").lower()
        if ext == ".pdf" and fitz is not None:
            try:
                with fitz.open(material.storage_path) as doc:
                    page_text = [page.get_text("text") or "" for page in doc]
                text = "\n".join(page_text)
                section = _find_reference_section(text)
                if section.strip():
                    chunks.append(section)
            except Exception:
                pass
        elif material.text_storage_path:
            try:
                text = Path(material.text_storage_path).read_text(encoding="utf-8", errors="ignore")
                section = _find_reference_section(text)
                if section.strip():
                    chunks.append(section)
            except Exception:
                pass
        if sum(len(x) for x in chunks) >= max_chars:
            break
    return "\n".join(chunks)[:max_chars]


RISKY_VENUE_ACRONYMS = {
    "FAST", "CASE", "DATE", "CHI", "SC", "IC", "AI", "ML", "CV", "DB", "SE",
}


def _acronym_candidate(alias: str) -> str | None:
    clean = alias.strip()
    if not (3 <= len(clean) <= 24):
        return None
    if re.fullmatch(r"[A-Z][A-Z0-9*+&/-]{2,23}", clean):
        if clean in {"AI", "ML", "NLP", "CV", "DB", "SE"}:
            return None
        return clean
    return None


def _reference_lines(reference_text: str) -> list[str]:
    # Bibliographies are naturally line-oriented. Preserve enough local context for
    # wrapped entries while avoiding a match that crosses unrelated references.
    raw = [" ".join(line.split()) for line in reference_text.splitlines()]
    lines: list[str] = []
    current = ""
    for line in raw:
        if not line:
            continue
        if re.match(r"^\s*(?:\[?\d+\]?|\d+\.)\s+", line) and current:
            lines.append(current)
            current = line
        else:
            current = f"{current} {line}".strip()
    if current:
        lines.append(current)
    return lines or [" ".join(reference_text.split())]


def _acronym_reference_match(entry: str, acronym: str) -> bool:
    """Require publication context for ambiguous acronym-like venue names.

    FAST/CASE/DATE/CHI are ordinary English words. Case-insensitive bare matching caused
    serious false positives in V3.9.x. A risky acronym now needs explicit bibliography
    context ("In FAST", "Proc. FAST", "FAST 2025", etc.). Non-risky all-caps acronyms
    remain case-sensitive unless such context is present.
    """
    escaped = re.escape(acronym)
    context_patterns = [
        rf"(?i)\b(?:in|at)\s+(?:the\s+)?{escaped}\b",
        rf"(?i)\b(?:proc\.?|proceedings(?:\s+of)?)\s*(?:the\s+)?(?:\d{{4}}\s+)?{escaped}\b",
        rf"(?i)\b{escaped}\s*['’]?\d{{2}}\b",
        rf"(?i)\b{escaped}\s*,?\s*(?:19|20)\d{{2}}\b",
        rf"(?i)\b(?:conference|symposium|workshop)\s+{escaped}\b",
    ]
    if any(re.search(pattern, entry) for pattern in context_patterns):
        return True
    if acronym in RISKY_VENUE_ACRONYMS:
        return False
    # Unambiguous scholarly acronyms (CVPR, MICCAI, NeurIPS, ACL...) must still be
    # written as the actual acronym, not a lower-case lexical coincidence.
    return re.search(rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])", entry) is not None


def reference_count(reference_text: str, venue: dict[str, Any]) -> int:
    if not reference_text.strip():
        return 0
    entries = _reference_lines(reference_text)
    matched_entries: set[int] = set()
    aliases = _venue_aliases(venue)
    for idx, entry in enumerate(entries):
        for alias in aliases:
            acronym = _acronym_candidate(alias)
            if acronym and _acronym_reference_match(entry, acronym):
                matched_entries.add(idx)
                break
            if len(alias) < 14:
                continue
            generic = {
                "the", "and", "for", "with", "from", "into", "international", "conference",
                "conferences", "journal", "proceedings", "symposium", "annual", "ieee", "acm",
                "cvf", "on", "of", "transactions", "association", "society",
            }
            words = [w for w in re.findall(r"[A-Za-z0-9]+", alias.lower()) if len(w) >= 3 and w not in generic]
            if len(words) < 2:
                continue
            # Require several distinctive ordered words. This tolerates publisher prefixes
            # and stopwords but does not let a generic field phrase identify a venue.
            core = words[-min(7, len(words)):]
            min_required = 2 if len(core) <= 3 else 3
            entry_lower = entry.lower()
            positions: list[int] = []
            cursor = 0
            for word in core:
                pos = entry_lower.find(word, cursor)
                if pos >= 0:
                    positions.append(pos)
                    cursor = pos + len(word)
            if len(positions) >= min_required:
                matched_entries.add(idx)
                break
    return len(matched_entries)

def reference_scores(reference_text: str, venues: Iterable[dict[str, Any]]) -> dict[str, tuple[int, int]]:
    counts = {str(v.get("id")): reference_count(reference_text, v) for v in venues}
    max_count = max(counts.values(), default=0)
    if max_count <= 0:
        return {key: (0, 0) for key in counts}
    denom = math.log1p(max_count)
    return {
        key: (count, round(100 * math.log1p(count) / denom) if count > 0 else 0)
        for key, count in counts.items()
    }


def infer_ccf_area(scope_vector: dict[str, float]) -> str:
    if not scope_vector:
        return "MX"
    top = max(scope_vector, key=scope_vector.get)
    if top in {"computer_vision", "medical_imaging", "machine_learning", "nlp", "robotics", "multiagent", "speech", "bioinformatics", "efficient_ai"}:
        return "AI"
    if top in {"graphics", "multimedia"}:
        return "CG"
    if top in {"data_mining", "information_retrieval", "databases"}:
        return "DB"
    if top == "security":
        return "SC"
    if top == "networks":
        return "NW"
    if top == "software_engineering":
        return "SE"
    if top == "theory":
        return "CT"
    if top == "hci":
        return "HI"
    if top == "systems":
        return "DS"
    return "MX"
