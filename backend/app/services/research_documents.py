from __future__ import annotations

import csv
import io
import json
import mimetypes
import re
import shutil
import zipfile
from collections import Counter
from dataclasses import dataclass, asdict
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

import pymupdf
from docx import Document
from openpyxl import load_workbook
from PIL import Image
import pytesseract
try:
    import xlrd
except ImportError:  # optional at runtime unless legacy .xls is parsed
    xlrd = None

from ..config import Settings
from ..models import Material

TEXT_EXTENSIONS = {
    ".txt", ".md", ".tex", ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".c", ".cc", ".cpp",
    ".h", ".hpp", ".rs", ".go", ".json", ".yaml", ".yml", ".toml", ".sh", ".ps1", ".ini", ".cfg",
}
SOURCE_EXTENSIONS = TEXT_EXTENSIONS | {".ipynb"}
NOISE_PARTS = {
    ".git", ".svn", ".hg", "node_modules", "dist", "build", "target", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", ".ipynb_checkpoints", "wandb", "runs", "logs", "checkpoints", "checkpoint",
    ".idea", ".vscode", "venv", ".venv", "env", "site-packages",
}
NOISE_SUFFIXES = {".pyc", ".pyo", ".so", ".dll", ".dylib", ".exe", ".bin", ".pt", ".pth", ".ckpt", ".onnx", ".safetensors", ".npz", ".npy"}
SECRET_PATTERNS = [
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----", re.I), "[REDACTED_PRIVATE_KEY]"),
    (re.compile(r"(?i)\b(sk-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"), "[REDACTED_TOKEN]"),
    (re.compile(r"(?im)^(\s*(?:api[_-]?key|token|secret|password|passwd|access[_-]?key)\s*[:=]\s*)['\"]?[^\s'\"#]{6,}['\"]?"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)[A-Za-z0-9._~+/-]{10,}"), r"\1[REDACTED]"),
]


@dataclass
class EvidenceItem:
    id: str
    material_id: str
    kind: str
    label: str
    text: str
    metadata: dict[str, Any]


@dataclass
class VisualArtifact:
    id: str
    material_id: str
    kind: str
    label: str
    mime_type: str
    path: str
    width: int | None = None
    height: int | None = None
    page: int | None = None
    source: str | None = None
    caption: str | None = None
    bbox: list[float] | None = None
    region_label: str | None = None


def _bounded(text: str, limit: int = 18_000) -> str:
    text = text.replace("\x00", "").strip()
    return text[:limit]


def redact_secrets(text: str) -> str:
    redacted = text
    for pattern, replacement in SECRET_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


def _ocr_ready(settings: Settings) -> bool:
    if settings.tesseract_cmd.strip():
        candidate = Path(settings.tesseract_cmd.strip())
        if not candidate.is_file():
            return False
        pytesseract.pytesseract.tesseract_cmd = str(candidate)
    return shutil.which(pytesseract.pytesseract.tesseract_cmd) is not None or bool(settings.tesseract_cmd.strip())


def ocr_available(settings: Settings) -> bool:
    try:
        return _ocr_ready(settings) and bool(pytesseract.get_tesseract_version())
    except Exception:
        return False


def _save_visual(
    data: bytes,
    destination: Path,
    *,
    material_id: str,
    artifact_id: str,
    kind: str,
    label: str,
    page: int | None = None,
    source: str | None = None,
    forced_mime: str | None = None,
    caption: str | None = None,
    bbox: list[float] | None = None,
    region_label: str | None = None,
) -> VisualArtifact | None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        image = Image.open(io.BytesIO(data))
        width, height = image.size
        fmt = (image.format or "PNG").lower()
        ext = ".jpg" if fmt in {"jpeg", "jpg"} else f".{fmt}"
        if ext not in {".png", ".jpg", ".webp", ".gif", ".bmp", ".tif", ".tiff"}:
            ext = ".png"
        out = destination.with_suffix(ext)
        image.convert("RGB").save(out, format="JPEG" if ext == ".jpg" else "PNG" if ext == ".png" else image.format)
        mime = forced_mime or mimetypes.guess_type(out.name)[0] or "image/png"
        return VisualArtifact(
            artifact_id,
            material_id,
            kind,
            label,
            mime,
            str(out),
            width,
            height,
            page,
            source,
            caption,
            bbox,
            region_label,
        )
    except Exception:
        return None


CAPTION_RE = re.compile(
    # IEEE / ACM papers use both Arabic and Roman table numbering (``Table 2`` and
    # ``TABLE IV``).  Accept both while still requiring caption punctuation so body
    # prose such as "see Table 2 for ..." is not mistaken for a crop anchor.
    r"^\s*(?P<kind>fig(?:ure)?\.?|table)\s*(?P<number>(?:[A-Za-z]?\d+[A-Za-z]?|[IVXLCDM]+))\s*[\.:]\s*(?P<rest>.*)$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class _CaptionCandidate:
    kind: str
    number: str
    text: str
    bbox: pymupdf.Rect


def _caption_candidates(page: pymupdf.Page) -> list[_CaptionCandidate]:
    """Find figure / table caption lines with page coordinates.

    We deliberately use text-line geometry instead of embedded-image extraction: in
    research PDFs, one logical figure is commonly assembled from vector paths, labels,
    legends and multiple raster snippets. The caption is a much more stable anchor for
    reconstructing the human-visible figure region.
    """
    found: list[_CaptionCandidate] = []
    try:
        payload = page.get_text("dict", sort=True)
    except Exception:
        return found
    for block in payload.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            text = "".join(str(span.get("text", "")) for span in spans).strip()
            if not text:
                continue
            match = CAPTION_RE.match(text)
            if not match:
                continue
            raw_kind = match.group("kind").lower()
            kind = "table" if raw_kind.startswith("table") else "figure"
            bbox = pymupdf.Rect(line.get("bbox") or block.get("bbox"))
            if bbox.is_empty or bbox.is_infinite:
                continue
            normalized = re.sub(r"\s+", " ", text).strip()
            found.append(_CaptionCandidate(kind, match.group("number"), normalized, bbox))
    return found


def _horizontal_overlap(a: pymupdf.Rect, b: pymupdf.Rect) -> float:
    overlap = max(0.0, min(a.x1, b.x1) - max(a.x0, b.x0))
    base = max(1.0, min(a.width, b.width))
    return overlap / base


def _column_window(page_rect: pymupdf.Rect, caption_rect: pymupdf.Rect) -> pymupdf.Rect:
    """Approximate the caption's column, while preserving full-width figures."""
    margin = max(10.0, page_rect.width * 0.035)
    if caption_rect.width >= page_rect.width * 0.55:
        return pymupdf.Rect(page_rect.x0 + margin, page_rect.y0, page_rect.x1 - margin, page_rect.y1)
    mid = (page_rect.x0 + page_rect.x1) / 2
    gutter = page_rect.width * 0.025
    if caption_rect.x0 + caption_rect.x1 < page_rect.x0 + page_rect.x1:
        return pymupdf.Rect(page_rect.x0 + margin, page_rect.y0, mid - gutter, page_rect.y1)
    return pymupdf.Rect(mid + gutter, page_rect.y0, page_rect.x1 - margin, page_rect.y1)


def _clip_to_page(rect: pymupdf.Rect, page_rect: pymupdf.Rect, pad: float = 0.0) -> pymupdf.Rect:
    expanded = pymupdf.Rect(rect.x0 - pad, rect.y0 - pad, rect.x1 + pad, rect.y1 + pad)
    clipped = expanded & page_rect
    return clipped if not clipped.is_empty else rect & page_rect


def _visual_rectangles(page: pymupdf.Page) -> list[pymupdf.Rect]:
    rects: list[pymupdf.Rect] = []
    try:
        for drawing in page.get_drawings():
            rect = pymupdf.Rect(drawing.get("rect"))
            if rect.is_empty or rect.is_infinite:
                continue
            if rect.width < 4 or rect.height < 4 or rect.get_area() < 60:
                continue
            rects.append(rect)
    except Exception:
        pass
    try:
        for block in page.get_text("dict").get("blocks", []):
            if block.get("type") != 1:
                continue
            rect = pymupdf.Rect(block.get("bbox"))
            if rect.is_empty or rect.is_infinite or rect.width < 20 or rect.height < 20:
                continue
            rects.append(rect)
    except Exception:
        pass
    return rects


def _figure_region(page: pymupdf.Page, caption: _CaptionCandidate, table_rects: list[pymupdf.Rect]) -> pymupdf.Rect | None:
    """Build a caption-anchored crop for one logical figure.

    Prefer the union of nearby vector / raster geometry above the caption. If a PDF
    stores a plot unusually (e.g. almost entirely as text), fall back to a bounded
    caption-anchored column crop rather than showing the entire page.
    """
    page_rect = page.rect
    column = _column_window(page_rect, caption.bbox)
    max_lookback = min(page_rect.height * 0.46, 340.0)
    search = pymupdf.Rect(column.x0, max(page_rect.y0, caption.bbox.y0 - max_lookback), column.x1, caption.bbox.y0 - 2)
    candidates: list[pymupdf.Rect] = []
    for rect in _visual_rectangles(page):
        if rect.y0 >= caption.bbox.y0 or rect.y1 < search.y0:
            continue
        if _horizontal_overlap(rect, search) < 0.08 and not search.contains(rect.tl):
            continue
        # Do not accidentally turn a nearby detected table into a Figure crop.
        if any((rect & table_rect).get_area() >= rect.get_area() * 0.75 for table_rect in table_rects):
            continue
        candidates.append(rect & search)

    if candidates:
        # Start with geometry closest to the caption and grow upward while pieces remain
        # reasonably connected. This captures multi-part diagrams without swallowing a
        # whole preceding column of prose.
        candidates.sort(key=lambda r: (caption.bbox.y0 - r.y1, -r.get_area()))
        cluster = pymupdf.Rect(candidates[0])
        for rect in candidates[1:]:
            vertical_gap = max(0.0, cluster.y0 - rect.y1, rect.y0 - cluster.y1)
            horizontal_related = _horizontal_overlap(cluster, rect) >= 0.08 or abs(rect.x0 - cluster.x0) < column.width * 0.35
            if vertical_gap <= 42 and horizontal_related:
                cluster |= rect
        region = _clip_to_page(cluster, page_rect, pad=10)
        # Figure labels and axis text can sit slightly outside vector geometry. Widen to
        # the caption's column when the geometry already spans most of it.
        if region.width >= column.width * 0.62:
            region.x0 = column.x0
            region.x1 = column.x1
        region.y1 = min(region.y1, caption.bbox.y0 - 1)
        if region.width >= 80 and region.height >= 45:
            return region

    fallback_height = min(page_rect.height * 0.28, 220.0)
    fallback = pymupdf.Rect(column.x0, max(page_rect.y0, caption.bbox.y0 - fallback_height), column.x1, caption.bbox.y0 - 2)
    return fallback if fallback.width >= 80 and fallback.height >= 45 else None


def _nearest_caption(captions: list[_CaptionCandidate], kind: str, rect: pymupdf.Rect) -> _CaptionCandidate | None:
    options = [c for c in captions if c.kind == kind]
    if not options:
        return None
    return min(options, key=lambda c: min(abs(c.bbox.y0 - rect.y1), abs(c.bbox.y1 - rect.y0)))


def _render_region_artifact(
    page: pymupdf.Page,
    *,
    clip: pymupdf.Rect,
    artifact_dir: Path,
    material: Material,
    artifact_id: str,
    kind: str,
    label: str,
    page_number: int,
    caption: str | None,
    region_label: str,
) -> VisualArtifact | None:
    try:
        clip = _clip_to_page(clip, page.rect)
        if clip.width < 40 or clip.height < 30:
            return None
        pix = page.get_pixmap(matrix=pymupdf.Matrix(2.0, 2.0), clip=clip, alpha=False)
        return _save_visual(
            pix.tobytes("png"),
            artifact_dir / artifact_id,
            material_id=material.id,
            artifact_id=artifact_id,
            kind=kind,
            label=label,
            page=page_number,
            source="pdf_caption_region",
            forced_mime="image/png",
            caption=caption,
            bbox=[round(float(v), 2) for v in (clip.x0, clip.y0, clip.x1, clip.y1)],
            region_label=region_label,
        )
    except Exception:
        return None


def _evidence_id(material_id: str, suffix: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", suffix).strip("_")[:60]
    return f"ev_{material_id}_{safe}"


def _artifact_id(material_id: str, suffix: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", suffix).strip("_")[:60]
    return f"art_{material_id}_{safe}"


def parse_pdf(material: Material, path: Path, artifact_dir: Path, settings: Settings) -> tuple[list[EvidenceItem], list[VisualArtifact], dict[str, Any]]:
    evidence: list[EvidenceItem] = []
    artifacts: list[VisualArtifact] = []
    embedded_artifacts: list[VisualArtifact] = []
    region_artifacts: list[VisualArtifact] = []
    doc = pymupdf.open(path)
    native_chars = 0
    ocr_pages = 0
    table_count = 0
    image_count = 0
    figure_crop_count = 0
    table_crop_count = 0
    render_pages: set[int] = set()
    can_ocr = ocr_available(settings)

    for page_index, page in enumerate(doc):
        captions = _caption_candidates(page)
        detected_table_rects: list[pymupdf.Rect] = []
        captioned_table_rects: dict[str, tuple[_CaptionCandidate, list[pymupdf.Rect]]] = {}
        native = page.get_text("text", sort=True).strip()
        native_chars += len(native)
        page_text = native
        used_ocr = False
        if len(native) < settings.ocr_min_native_text_chars and can_ocr:
            try:
                pix = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
                image = Image.open(io.BytesIO(pix.tobytes("png")))
                ocr_text = pytesseract.image_to_string(image, lang=settings.ocr_languages).strip()
                if len(ocr_text) > len(native):
                    page_text = ocr_text
                    used_ocr = True
                    ocr_pages += 1
                    render_pages.add(page_index)
            except Exception:
                pass
        if page_text:
            evidence.append(EvidenceItem(
                _evidence_id(material.id, f"pdf_page_{page_index+1}"), material.id, "ocr_text" if used_ocr else "document_text",
                f"{material.name} · page {page_index+1}", _bounded(page_text), {"page": page_index + 1, "ocr": used_ocr}
            ))

        try:
            tabs = page.find_tables()
            for t_idx, table in enumerate(tabs.tables[:8]):
                rows = table.extract()
                if not rows:
                    continue
                table_rect = pymupdf.Rect(table.bbox)
                detected_table_rects.append(table_rect)
                table_count += 1
                render_pages.add(page_index)
                lines = [" | ".join("" if cell is None else str(cell) for cell in row) for row in rows[:80]]
                evidence.append(EvidenceItem(
                    _evidence_id(material.id, f"pdf_table_{page_index+1}_{t_idx+1}"), material.id, "table",
                    f"{material.name} · table p{page_index+1}.{t_idx+1}", _bounded("\n".join(lines), 14_000), {"page": page_index + 1, "rows": len(rows)}
                ))
                caption = _nearest_caption(captions, "table", table_rect)
                if caption is None or min(abs(caption.bbox.y0 - table_rect.y1), abs(caption.bbox.y1 - table_rect.y0)) > 120:
                    continue
                key = caption.number.lower()
                if key not in captioned_table_rects:
                    captioned_table_rects[key] = (caption, [])
                captioned_table_rects[key][1].append(table_rect)
        except Exception:
            pass

        # Some PDFs split one visible table into several adjacent detected rectangles.
        # Merge every fragment associated with the same caption and render it once.
        for _, (caption, rects) in captioned_table_rects.items():
            if not rects:
                continue
            merged = pymupdf.Rect(rects[0])
            for rect in rects[1:]:
                merged |= rect
            number = caption.number
            artifact_id = _artifact_id(material.id, f"pdf_table_crop_{page_index+1}_{number}")
            art = _render_region_artifact(
                page,
                clip=_clip_to_page(merged, page.rect, pad=8),
                artifact_dir=artifact_dir,
                material=material,
                artifact_id=artifact_id,
                kind="table_crop",
                label=f"{material.name} · Table {number} · p{page_index+1}",
                page_number=page_index + 1,
                caption=caption.text,
                region_label=f"Table {number}",
            )
            if art:
                region_artifacts.append(art)
                table_crop_count += 1

        try:
            blocks = page.get_text("dict").get("blocks", [])
            for i_idx, block in enumerate([b for b in blocks if b.get("type") == 1][:10]):
                data = block.get("image")
                if not data or len(data) < 2048:
                    continue
                art = _save_visual(
                    data,
                    artifact_dir / _artifact_id(material.id, f"pdf_image_{page_index+1}_{i_idx+1}"),
                    material_id=material.id,
                    artifact_id=_artifact_id(material.id, f"pdf_image_{page_index+1}_{i_idx+1}"),
                    kind="pdf_image",
                    label=f"{material.name} · image p{page_index+1}.{i_idx+1}",
                    page=page_index + 1,
                    source="embedded_pdf_image",
                )
                if art and (art.width or 0) >= 180 and (art.height or 0) >= 120:
                    embedded_artifacts.append(art)
                    image_count += 1
                    render_pages.add(page_index)
        except Exception:
            pass

        # Reconstruct logical Figure regions from caption anchors + nearby vector/raster
        # geometry. This produces human-readable evidence cards instead of either tiny PDF
        # internals or a full-page screenshot.
        for c_idx, caption in enumerate([c for c in captions if c.kind == "figure"][:10]):
            region = _figure_region(page, caption, detected_table_rects)
            if region is None:
                continue
            artifact_id = _artifact_id(material.id, f"pdf_figure_crop_{page_index+1}_{caption.number}_{c_idx+1}")
            art = _render_region_artifact(
                page,
                clip=region,
                artifact_dir=artifact_dir,
                material=material,
                artifact_id=artifact_id,
                kind="figure_crop",
                label=f"{material.name} · Figure {caption.number} · p{page_index+1}",
                page_number=page_index + 1,
                caption=caption.text,
                region_label=f"Figure {caption.number}",
            )
            if art:
                region_artifacts.append(art)
                figure_crop_count += 1
                render_pages.add(page_index)

    # Page renders are fallback / navigation assets. They are intentionally secondary to
    # caption-level Figure/Table crops in both the UI and Vision selection.
    if not render_pages and len(doc):
        render_pages.update({0, min(len(doc) - 1, 1)})
    for page_index in sorted(render_pages)[:8]:
        try:
            page = doc[page_index]
            pix = page.get_pixmap(matrix=pymupdf.Matrix(1.6, 1.6), alpha=False)
            data = pix.tobytes("png")
            art = _save_visual(
                data,
                artifact_dir / _artifact_id(material.id, f"pdf_render_{page_index+1}"),
                material_id=material.id,
                artifact_id=_artifact_id(material.id, f"pdf_render_{page_index+1}"),
                kind="page_render",
                label=f"{material.name} · rendered page {page_index+1}",
                page=page_index + 1,
                source="pdf_page_render",
                forced_mime="image/png",
            )
            if art:
                artifacts.append(art)
        except Exception:
            pass

    region_artifacts = sorted(
        region_artifacts,
        key=lambda a: (a.page or 10**9, 0 if a.kind == "figure_crop" else 1, a.region_label or "", a.id),
    )

    # Figure / Table crops are primary. Full pages remain useful for fallback navigation,
    # and raw image blocks remain trace-only artifacts because they are frequently just one
    # piece of a composite academic Figure.
    artifacts = region_artifacts + artifacts + embedded_artifacts
    pages = len(doc)
    doc.close()
    return evidence, artifacts, {
        "parser": "pymupdf",
        "pages": pages,
        "nativeTextChars": native_chars,
        "ocrAvailable": can_ocr,
        "ocrPages": ocr_pages,
        "tables": table_count,
        "embeddedImages": image_count,
        "figureCrops": figure_crop_count,
        "tableCrops": table_crop_count,
        "pageRenders": sum(1 for artifact in artifacts if artifact.kind == "page_render"),
    }


def parse_docx(material: Material, path: Path, artifact_dir: Path) -> tuple[list[EvidenceItem], list[VisualArtifact], dict[str, Any]]:
    evidence: list[EvidenceItem] = []
    artifacts: list[VisualArtifact] = []
    doc = Document(path)
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    if paragraphs:
        chunks: list[str] = []
        buf = ""
        for paragraph in paragraphs:
            if len(buf) + len(paragraph) > 14_000 and buf:
                chunks.append(buf)
                buf = ""
            buf += paragraph + "\n\n"
        if buf:
            chunks.append(buf)
        for idx, chunk in enumerate(chunks):
            evidence.append(EvidenceItem(_evidence_id(material.id, f"docx_text_{idx+1}"), material.id, "document_text", f"{material.name} · text {idx+1}", _bounded(chunk), {"chunk": idx + 1}))
    for idx, table in enumerate(doc.tables[:20]):
        rows = [[cell.text.strip() for cell in row.cells] for row in table.rows]
        evidence.append(EvidenceItem(_evidence_id(material.id, f"docx_table_{idx+1}"), material.id, "table", f"{material.name} · table {idx+1}", _bounded("\n".join(" | ".join(row) for row in rows[:100]), 14_000), {"rows": len(rows)}))

    try:
        with zipfile.ZipFile(path) as zf:
            media = [n for n in zf.namelist() if n.startswith("word/media/") and not n.endswith("/")]
            for idx, member in enumerate(media[:20]):
                data = zf.read(member)
                art = _save_visual(data, artifact_dir / _artifact_id(material.id, f"docx_image_{idx+1}"), material_id=material.id, artifact_id=_artifact_id(material.id, f"docx_image_{idx+1}"), kind="docx_image", label=f"{material.name} · embedded image {idx+1}", source=member)
                if art:
                    artifacts.append(art)
    except Exception:
        pass
    return evidence, artifacts, {"parser": "python-docx", "paragraphs": len(paragraphs), "tables": len(doc.tables), "embeddedImages": len(artifacts)}


def _safe_archive_member(name: str) -> bool:
    p = PurePosixPath(name)
    if p.is_absolute() or ".." in p.parts:
        return False
    lowered = {part.lower() for part in p.parts}
    if lowered & NOISE_PARTS:
        return False
    if p.suffix.lower() in NOISE_SUFFIXES:
        return False
    return True


def _notebook_text(raw: str) -> str:
    try:
        obj = json.loads(raw)
        pieces: list[str] = []
        for idx, cell in enumerate(obj.get("cells", [])):
            ctype = cell.get("cell_type", "")
            if ctype not in {"markdown", "code"}:
                continue
            source = cell.get("source", [])
            text = "".join(source) if isinstance(source, list) else str(source)
            if text.strip():
                pieces.append(f"# cell {idx+1} [{ctype}]\n{text.strip()}")
        return "\n\n".join(pieces)
    except Exception:
        return ""


def parse_source_zip(material: Material, path: Path) -> tuple[list[EvidenceItem], list[VisualArtifact], dict[str, Any]]:
    evidence: list[EvidenceItem] = []
    with zipfile.ZipFile(path) as zf:
        members = [n for n in zf.namelist() if not n.endswith("/") and _safe_archive_member(n)]
        candidates = [n for n in members if PurePosixPath(n).suffix.lower() in SOURCE_EXTENSIONS]
        ext_counts = Counter(PurePosixPath(n).suffix.lower() or "(none)" for n in candidates)
        top_paths = Counter(PurePosixPath(n).parts[0] if PurePosixPath(n).parts else "root" for n in candidates)
        summary = [f"Repository file count: {len(members)}", f"Readable source files: {len(candidates)}", "Extensions: " + ", ".join(f"{k}:{v}" for k, v in ext_counts.most_common(20)), "Top-level paths: " + ", ".join(f"{k}:{v}" for k, v in top_paths.most_common(20))]
        evidence.append(EvidenceItem(_evidence_id(material.id, "repo_summary"), material.id, "repository_summary", f"{material.name} · repository summary", "\n".join(summary), {"files": len(members), "readableSourceFiles": len(candidates)}))

        # Prioritize README, docs, configs, train/eval/main/model code, then bounded remainder.
        def priority(name: str) -> tuple[int, int, str]:
            low = name.lower()
            p = 0
            if "readme" in low or "/docs/" in f"/{low}/": p -= 50
            if any(token in low for token in ["train", "eval", "main", "model", "method", "algorithm", "config", "experiment"]): p -= 25
            return (p, low.count("/"), low)

        total_chars = 0
        for idx, member in enumerate(sorted(candidates, key=priority)[:120]):
            try:
                data = zf.read(member)
                if len(data) > 512_000:
                    data = data[:512_000]
                raw = data.decode("utf-8", errors="replace")
                text = _notebook_text(raw) if member.lower().endswith(".ipynb") else raw
                text = redact_secrets(text)
                text = _bounded(text, 18_000)
                if not text.strip():
                    continue
                if total_chars >= 280_000:
                    break
                remaining = 280_000 - total_chars
                text = text[:remaining]
                total_chars += len(text)
                evidence.append(EvidenceItem(_evidence_id(material.id, f"source_{idx+1}"), material.id, "source_code", f"{material.name} · {member}", text, {"path": member, "extension": PurePosixPath(member).suffix.lower()}))
            except Exception:
                continue
        return evidence, [], {"parser": "zip", "files": len(members), "readableSourceFiles": len(candidates), "evidenceChars": total_chars, "extensions": dict(ext_counts)}


def parse_spreadsheet(material: Material, path: Path) -> tuple[list[EvidenceItem], list[VisualArtifact], dict[str, Any]]:
    evidence: list[EvidenceItem] = []
    suffix = path.suffix.lower()
    sheet_count = 0
    row_count = 0
    if suffix == ".xlsx":
        wb = load_workbook(path, read_only=True, data_only=True)
        for s_idx, ws in enumerate(wb.worksheets[:20]):
            rows: list[list[str]] = []
            for row in ws.iter_rows(values_only=True):
                vals = ["" if v is None else str(v) for v in row[:40]]
                if any(v.strip() for v in vals):
                    rows.append(vals)
                if len(rows) >= 150:
                    break
            if rows:
                sheet_count += 1
                row_count += len(rows)
                text = "\n".join(" | ".join(r) for r in rows)
                evidence.append(EvidenceItem(_evidence_id(material.id, f"sheet_{s_idx+1}"), material.id, "table", f"{material.name} · {ws.title}", _bounded(text, 16_000), {"sheet": ws.title, "rows": len(rows)}))
        wb.close()
    elif suffix == ".xls":
        if xlrd is None:
            return [], [], {"parser": "spreadsheet", "error": "xlrd is required to parse legacy .xls files"}
        wb = xlrd.open_workbook(path)
        for s_idx in range(min(wb.nsheets, 20)):
            ws = wb.sheet_by_index(s_idx)
            rows = [[str(ws.cell_value(r, c)) for c in range(min(ws.ncols, 40))] for r in range(min(ws.nrows, 150))]
            if rows:
                sheet_count += 1; row_count += len(rows)
                evidence.append(EvidenceItem(_evidence_id(material.id, f"sheet_{s_idx+1}"), material.id, "table", f"{material.name} · {ws.name}", _bounded("\n".join(" | ".join(r) for r in rows), 16_000), {"sheet": ws.name, "rows": len(rows)}))
    else:
        delimiter = "\t" if suffix == ".tsv" else ","
        with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as f:
            rows = []
            for idx, row in enumerate(csv.reader(f, delimiter=delimiter)):
                rows.append(row[:40])
                if idx >= 149: break
        sheet_count = 1 if rows else 0; row_count = len(rows)
        if rows:
            evidence.append(EvidenceItem(_evidence_id(material.id, "table_1"), material.id, "table", material.name, _bounded("\n".join(" | ".join(r) for r in rows), 16_000), {"rows": len(rows)}))
    return evidence, [], {"parser": "spreadsheet", "sheets": sheet_count, "rows": row_count}


def parse_image(material: Material, path: Path, artifact_dir: Path, settings: Settings) -> tuple[list[EvidenceItem], list[VisualArtifact], dict[str, Any]]:
    evidence: list[EvidenceItem] = []
    data = path.read_bytes()
    art = _save_visual(data, artifact_dir / _artifact_id(material.id, "uploaded_image"), material_id=material.id, artifact_id=_artifact_id(material.id, "uploaded_image"), kind="uploaded_image", label=material.name, source="uploaded_image", forced_mime=material.mime_type)
    artifacts = [art] if art else []
    can_ocr = ocr_available(settings)
    ocr_chars = 0
    if can_ocr:
        try:
            image = Image.open(path)
            text = pytesseract.image_to_string(image, lang=settings.ocr_languages).strip()
            ocr_chars = len(text)
            if text:
                evidence.append(EvidenceItem(_evidence_id(material.id, "image_ocr"), material.id, "ocr_text", f"{material.name} · OCR", _bounded(text, 12_000), {"ocr": True}))
        except Exception:
            pass
    return evidence, artifacts, {"parser": "image", "ocrAvailable": can_ocr, "ocrChars": ocr_chars, "width": art.width if art else None, "height": art.height if art else None}


def parse_text(material: Material, path: Path) -> tuple[list[EvidenceItem], list[VisualArtifact], dict[str, Any]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    if material.kind == "source" or path.suffix.lower() in SOURCE_EXTENSIONS:
        text = redact_secrets(text)
    chunks = []
    for idx in range(0, min(len(text), 180_000), 16_000):
        chunk = text[idx: idx + 16_000].strip()
        if chunk:
            chunks.append(EvidenceItem(_evidence_id(material.id, f"text_{idx//16000+1}"), material.id, "source_code" if material.kind == "source" else "document_text", f"{material.name} · chunk {idx//16000+1}", chunk, {"offset": idx}))
    return chunks, [], {"parser": "text", "chars": len(text)}


def parse_material(material: Material, artifact_dir: Path, settings: Settings) -> tuple[list[EvidenceItem], list[VisualArtifact], dict[str, Any]]:
    path = Path(material.storage_path)
    if not path.is_file():
        return [], [], {"parser": "missing", "error": "stored file is missing"}
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return parse_pdf(material, path, artifact_dir, settings)
    if suffix == ".docx":
        return parse_docx(material, path, artifact_dir)
    if suffix == ".zip":
        return parse_source_zip(material, path)
    if suffix in {".xlsx", ".xls", ".csv", ".tsv"}:
        return parse_spreadsheet(material, path)
    if suffix in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
        return parse_image(material, path, artifact_dir, settings)
    return parse_text(material, path)


def serialize_evidence(items: Iterable[EvidenceItem]) -> list[dict[str, Any]]:
    return [asdict(item) for item in items]


def serialize_artifacts(items: Iterable[VisualArtifact]) -> list[dict[str, Any]]:
    return [asdict(item) for item in items]
