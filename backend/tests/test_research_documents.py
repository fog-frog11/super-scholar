from __future__ import annotations

import json
import zipfile
from pathlib import Path

from PIL import Image

from app.models import Material
from app.services.research_documents import parse_image, parse_source_zip, parse_text, redact_secrets
from app.config import get_settings


def material(path: Path, *, mid: str = "material_test", kind: str = "source") -> Material:
    return Material(id=mid, project_id="project_test", name=path.name, mime_type="application/octet-stream", extension=path.suffix.lstrip("."), size=path.stat().st_size, kind=kind, sha256="0"*64, storage_path=str(path), analysis_json={})


def test_secret_redaction():
    text = 'api_key="abcdef123456789"\npassword = hunter22\nAuthorization: Bearer xyzxyzxyzxyzxyz'
    redacted = redact_secrets(text)
    assert "abcdef123456789" not in redacted
    assert "hunter22" not in redacted
    assert "xyzxyzxyzxyzxyz" not in redacted


def test_source_zip_filters_noise_and_normalizes_notebook(tmp_path: Path):
    archive = tmp_path / "code.zip"
    notebook = {"cells": [{"cell_type": "markdown", "source": ["# Method"]}, {"cell_type": "code", "source": ["print('ok')"]}], "metadata": {"secret": "do-not-include"}}
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("README.md", "Research repository")
        zf.writestr("src/train.py", "TOKEN='abcdefghijklmnopqrstuvwxyz123456'\nprint('train')")
        zf.writestr("notebooks/demo.ipynb", json.dumps(notebook))
        zf.writestr(".ipynb_checkpoints/noise.py", "checkpoint noise")
        zf.writestr("checkpoints/model.ckpt", b"binary")
    evidence, _, meta = parse_source_zip(material(archive), archive)
    joined = "\n".join(item.text for item in evidence)
    labels = "\n".join(item.label for item in evidence)
    assert "checkpoint noise" not in joined
    assert "do-not-include" not in joined
    assert "# Method" in joined and "print('ok')" in joined
    assert "abcdefghijklmnopqrstuvwxyz123456" not in joined
    assert ".ipynb_checkpoints" not in labels
    assert meta["readableSourceFiles"] == 3


def test_text_source_parser_redacts_secret(tmp_path: Path):
    source = tmp_path / "config.py"
    source.write_text("api_key='supersecretvalue123'\nprint('x')", encoding="utf-8")
    evidence, _, meta = parse_text(material(source), source)
    assert "supersecretvalue123" not in evidence[0].text
    assert meta["chars"] > 0


def test_image_parser_persists_visual_asset_without_fake_ocr(tmp_path: Path, monkeypatch):
    image_path = tmp_path / "figure.png"
    Image.new("RGB", (320, 180), "white").save(image_path)
    from app.services import research_documents as module
    monkeypatch.setattr(module, "ocr_available", lambda _settings: False)
    evidence, artifacts, meta = parse_image(material(image_path, kind="image"), image_path, tmp_path / "artifacts", get_settings())
    assert evidence == []
    assert len(artifacts) == 1
    assert artifacts[0].width == 320 and artifacts[0].height == 180
    assert meta["ocrAvailable"] is False


def test_image_only_pdf_produces_visual_evidence_without_ocr(tmp_path: Path, monkeypatch):
    import io
    import pymupdf
    from app.services import research_documents as module

    image_bytes = io.BytesIO()
    Image.new("RGB", (640, 360), "navy").save(image_bytes, format="PNG")
    pdf_path = tmp_path / "image-only.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=640, height=360)
    page.insert_image(page.rect, stream=image_bytes.getvalue())
    doc.save(pdf_path)
    doc.close()

    monkeypatch.setattr(module, "ocr_available", lambda _settings: False)
    evidence, artifacts, meta = module.parse_pdf(material(pdf_path, kind="manuscript"), pdf_path, tmp_path / "pdf-artifacts", get_settings())
    assert evidence == []
    assert artifacts, "image-only PDFs must still produce visual artifacts"
    assert meta["nativeTextChars"] == 0
    assert meta["ocrAvailable"] is False
