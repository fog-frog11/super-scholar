from __future__ import annotations

from pathlib import Path

from app.config import Settings
from app.models import Material
from app.services.research_documents import parse_pdf


def _material(pdf_path: Path) -> Material:
    return Material(
        id="material_visual",
        project_id="project_visual",
        name="sample.pdf",
        mime_type="application/pdf",
        extension=".pdf",
        size=pdf_path.stat().st_size,
        kind="manuscript",
        sha256="0" * 64,
        storage_path=str(pdf_path),
        analysis_json={},
    )


def test_pdf_figure_crop_precedes_page_render_and_embedded_fragments(tmp_path: Path) -> None:
    import pymupdf

    pdf_path = tmp_path / "sample.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    # Logical Figure content above its caption, with both vector and raster components.
    page.draw_rect(pymupdf.Rect(72, 80, 310, 250), color=(0, 0, 0), width=1)
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 180, 100), 0)
    pix.clear_with(220)
    page.insert_image(pymupdf.Rect(95, 105, 275, 205), pixmap=pix)
    page.insert_text((72, 272), "Figure 1. Composite research diagram")
    doc.save(pdf_path)
    doc.close()

    _, artifacts, meta = parse_pdf(_material(pdf_path), pdf_path, tmp_path / "artifacts", Settings(ocr_min_native_text_chars=0))
    assert artifacts
    assert artifacts[0].kind == "figure_crop"
    assert artifacts[0].region_label == "Figure 1"
    assert artifacts[0].caption and artifacts[0].caption.startswith("Figure 1")
    assert meta["figureCrops"] >= 1
    assert meta["pageRenders"] >= 1
    assert [a.kind for a in artifacts].index("figure_crop") < [a.kind for a in artifacts].index("page_render")


def test_pdf_table_crop_is_created_from_detected_table(tmp_path: Path) -> None:
    import pymupdf

    pdf_path = tmp_path / "table.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    x0, y0, cell_w, cell_h = 72, 100, 90, 28
    for row in range(4):
        page.draw_line((x0, y0 + row * cell_h), (x0 + 2 * cell_w, y0 + row * cell_h))
    for col in range(3):
        page.draw_line((x0 + col * cell_w, y0), (x0 + col * cell_w, y0 + 3 * cell_h))
    page.insert_text((82, 120), "Model")
    page.insert_text((172, 120), "mIoU")
    page.insert_text((82, 148), "A")
    page.insert_text((172, 148), "72.3")
    # IEEE-style papers commonly number tables with Roman numerals.
    page.insert_text((72, 208), "TABLE IV. Main segmentation results")
    doc.save(pdf_path)
    doc.close()

    _, artifacts, meta = parse_pdf(_material(pdf_path), pdf_path, tmp_path / "artifacts", Settings(ocr_min_native_text_chars=0))
    assert meta["tables"] >= 1
    assert meta["tableCrops"] >= 1
    table_artifacts = [a for a in artifacts if a.kind == "table_crop"]
    assert table_artifacts
    assert table_artifacts[0].page == 1
    assert table_artifacts[0].region_label == "Table IV"
