from __future__ import annotations

import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated
import uuid

import pymupdf

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, PlainTextResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..db import get_db
from ..models import Material, Project
from ..schemas import MaterialAnalysisUpdate
from ..serializers import material_to_dict
from ..services.storage import normalize_filename, persist_upload, safe_extension

router = APIRouter(tags=["materials"])


@router.get("/projects/{project_id}/materials")
def list_materials(project_id: str, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)) -> list[dict]:
    if db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    materials = db.scalars(select(Material).where(Material.project_id == project_id).order_by(Material.created_at.asc())).all()
    return [material_to_dict(item, settings.api_prefix) for item in materials]


@router.post("/projects/{project_id}/materials", status_code=status.HTTP_201_CREATED)
async def upload_material(
    project_id: str,
    file: Annotated[UploadFile, File()],
    material_id: Annotated[str | None, Form()] = None,
    kind: Annotated[str, Form()] = "other",
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    if db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    filename = file.filename or "material"
    ext = safe_extension(filename)
    if kind not in {"manuscript", "source", "data", "image", "other"}:
        raise HTTPException(status_code=400, detail="Invalid material kind")
    mid = material_id or f"material_{uuid.uuid4()}"
    if not re.fullmatch(r"[A-Za-z0-9_-]{3,96}", mid):
        raise HTTPException(status_code=400, detail="Invalid material ID")
    existing = db.get(Material, mid)
    if existing and existing.project_id != project_id:
        raise HTTPException(status_code=409, detail="Material ID belongs to another project")

    safe_name = normalize_filename(filename)
    destination = settings.storage_dir / "projects" / project_id / "materials" / mid / safe_name
    size, digest = await persist_upload(file, destination, settings.max_upload_mb * 1024 * 1024)
    now = datetime.now(timezone.utc)
    material = existing or Material(id=mid, project_id=project_id, created_at=now)
    if existing:
        old_path = Path(existing.storage_path)
        if old_path != destination:
            old_path.unlink(missing_ok=True)
        if existing.text_storage_path:
            Path(existing.text_storage_path).unlink(missing_ok=True)
        material.text_storage_path = None
    material.name = filename
    material.mime_type = file.content_type or "application/octet-stream"
    material.extension = ext.lstrip(".")
    material.size = size
    material.kind = kind
    material.sha256 = digest
    material.storage_path = str(destination)
    material.analysis_json = {"status": "queued", "progress": 0, "stage": "queued", "message": "等待解析"}
    material.updated_at = now
    db.add(material)
    db.commit()
    db.refresh(material)
    return material_to_dict(material, settings.api_prefix)


@router.put("/materials/{material_id}/analysis")
def update_analysis(
    material_id: str,
    payload: MaterialAnalysisUpdate,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    material = db.get(Material, material_id)
    if material is None:
        raise HTTPException(status_code=404, detail="Material not found")
    material.analysis_json = payload.analysis
    if payload.extracted_text is not None:
        text_path = settings.storage_dir / "projects" / material.project_id / "materials" / material.id / "extracted.txt"
        text_path.parent.mkdir(parents=True, exist_ok=True)
        text_path.write_text(payload.extracted_text, encoding="utf-8")
        material.text_storage_path = str(text_path)
    material.updated_at = datetime.now(timezone.utc)
    db.add(material)
    db.commit()
    db.refresh(material)
    return material_to_dict(material, settings.api_prefix)


@router.get("/materials/{material_id}/download")
def download_material(material_id: str, db: Session = Depends(get_db)) -> FileResponse:
    material = db.get(Material, material_id)
    if material is None:
        raise HTTPException(status_code=404, detail="Material not found")
    path = Path(material.storage_path)
    if not path.is_file():
        raise HTTPException(status_code=410, detail="Stored file is missing")
    return FileResponse(path, media_type=material.mime_type, filename=material.name)


@router.get("/materials/{material_id}/preview")
def preview_material(material_id: str, db: Session = Depends(get_db)) -> FileResponse:
    """Inline browser preview used by evidence chips.

    Keeping this separate from /download avoids changing existing download semantics while
    allowing PDF evidence links to open directly at #page=N in the browser / modal viewer.
    """
    material = db.get(Material, material_id)
    if material is None:
        raise HTTPException(status_code=404, detail="Material not found")
    path = Path(material.storage_path)
    if not path.is_file():
        raise HTTPException(status_code=410, detail="Stored file is missing")
    return FileResponse(
        path,
        media_type=material.mime_type,
        headers={"Content-Disposition": "inline"},
    )


@router.get("/materials/{material_id}/pages/{page_number}/preview.png")
def preview_material_page(material_id: str, page_number: int, db: Session = Depends(get_db)) -> Response:
    """Render one PDF page on demand for the interactive evidence viewer."""
    material = db.get(Material, material_id)
    if material is None:
        raise HTTPException(status_code=404, detail="Material not found")
    path = Path(material.storage_path)
    if not path.is_file():
        raise HTTPException(status_code=410, detail="Stored file is missing")
    if path.suffix.lower() != ".pdf" and material.mime_type != "application/pdf":
        raise HTTPException(status_code=415, detail="Page preview is only available for PDF materials")
    try:
        doc = pymupdf.open(path)
        if page_number < 1 or page_number > len(doc):
            doc.close()
            raise HTTPException(status_code=404, detail="PDF page not found")
        page = doc[page_number - 1]
        pix = page.get_pixmap(matrix=pymupdf.Matrix(1.45, 1.45), alpha=False)
        data = pix.tobytes("png")
        doc.close()
        return Response(data, media_type="image/png", headers={"Cache-Control": "private, max-age=300"})
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not render PDF page: {exc}") from exc


@router.get("/materials/{material_id}/text")
def material_text(material_id: str, db: Session = Depends(get_db)) -> PlainTextResponse:
    material = db.get(Material, material_id)
    if material is None:
        raise HTTPException(status_code=404, detail="Material not found")
    if not material.text_storage_path:
        raise HTTPException(status_code=404, detail="No extracted text stored for this material")
    path = Path(material.text_storage_path)
    if not path.is_file():
        raise HTTPException(status_code=410, detail="Extracted text file is missing")
    return PlainTextResponse(path.read_text(encoding="utf-8"))


@router.delete("/materials/{material_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_material(material_id: str, db: Session = Depends(get_db)) -> None:
    material = db.get(Material, material_id)
    if material is None:
        raise HTTPException(status_code=404, detail="Material not found")
    directory = Path(material.storage_path).parent
    db.delete(material)
    db.commit()
    shutil.rmtree(directory, ignore_errors=True)
