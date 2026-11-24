from __future__ import annotations

from pathlib import Path
import shutil
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..db import get_db
from ..models import Project, ResearchAnalysisRun
from ..schemas import ResearchAnalysisCapabilities, ResearchAnalysisStart
from ..services.research_analysis import execute_analysis
from ..services.research_ai import openai_sdk_available
from ..services.integration_settings import as_parser_settings, load_runtime
from ..services.research_documents import ocr_available

router = APIRouter(tags=["research-understanding"])


def run_to_dict(run: ResearchAnalysisRun) -> dict:
    return {
        "id": run.id,
        "projectId": run.project_id,
        "mode": run.mode,
        "status": run.status,
        "progress": run.progress,
        "stage": run.stage,
        "message": run.message,
        "model": run.model,
        "result": run.result_json,
        "error": run.error,
        "createdAt": run.created_at,
        "updatedAt": run.updated_at,
    }


@router.get("/research/capabilities", response_model=ResearchAnalysisCapabilities)
def capabilities(db: Session = Depends(get_db), settings: Settings = Depends(get_settings)) -> ResearchAnalysisCapabilities:
    runtime = load_runtime(db, settings)
    parser_settings = as_parser_settings(settings, runtime)
    return ResearchAnalysisCapabilities(
        aiConfigured=runtime.ai_configured and openai_sdk_available(),
        provider=runtime.provider if runtime.ai_configured and openai_sdk_available() else None,
        model=runtime.model if runtime.ai_configured and openai_sdk_available() else None,
        ocrAvailable=ocr_available(parser_settings),
        ocrLanguages=runtime.ocr_languages,
        # Hierarchical research understanding never uploads a full raw PDF; bounded page/figure evidence is used instead.
        directPdfLimit=0,
        visualAssetLimit=max(0, runtime.max_visual_assets if runtime.supports_vision else 0),
        maxTextChars=max(10_000, runtime.max_text_chars),
        chunkTextChars=max(4_000, runtime.chunk_text_chars),
        maxProviderCalls=max(2, runtime.max_provider_calls),
        visualsPerChunk=max(0, runtime.visuals_per_chunk if runtime.supports_vision else 0),
    )


@router.post("/projects/{project_id}/research-analysis", status_code=status.HTTP_202_ACCEPTED)
def start_analysis(project_id: str, payload: ResearchAnalysisStart, background: BackgroundTasks, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)) -> dict:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    runtime = load_runtime(db, settings)
    if not runtime.ai_configured or not openai_sdk_available():
        raise HTTPException(status_code=409, detail="AI deep analysis is not configured. Open Settings → 模型与解析.")
    if not payload.consent_external_processing:
        raise HTTPException(status_code=400, detail="Explicit consent is required before external AI processing")
    active = db.scalars(select(ResearchAnalysisRun).where(ResearchAnalysisRun.project_id == project_id, ResearchAnalysisRun.status.in_(["queued", "running"]))).first()
    if active:
        return run_to_dict(active)
    run = ResearchAnalysisRun(
        id=f"analysis_{uuid.uuid4()}", project_id=project_id, mode="ai", status="queued",
        progress=0, stage="queued", message="已创建研究理解任务", model=runtime.model,
    )
    db.add(run); db.commit(); db.refresh(run)
    background.add_task(execute_analysis, run.id)
    return run_to_dict(run)


@router.get("/projects/{project_id}/research-analysis/latest")
def latest_analysis(project_id: str, db: Session = Depends(get_db)) -> dict | None:
    if db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    run = db.scalars(select(ResearchAnalysisRun).where(ResearchAnalysisRun.project_id == project_id).order_by(ResearchAnalysisRun.created_at.desc())).first()
    return run_to_dict(run) if run else None


@router.get("/research-analysis/{run_id}")
def get_analysis(run_id: str, db: Session = Depends(get_db)) -> dict:
    run = db.get(ResearchAnalysisRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Analysis run not found")
    return run_to_dict(run)


@router.delete("/research-analysis/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_analysis(run_id: str, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)) -> None:
    run = db.get(ResearchAnalysisRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Analysis run not found")
    if run.status in {"queued", "running"}:
        raise HTTPException(status_code=409, detail="Cannot delete an active analysis run")
    directory = settings.storage_dir / "projects" / run.project_id / "research_runs" / run.id
    db.delete(run); db.commit(); shutil.rmtree(directory, ignore_errors=True)


@router.get("/research-analysis/{run_id}/artifacts/{artifact_id}")
def get_artifact(run_id: str, artifact_id: str, db: Session = Depends(get_db)) -> FileResponse:
    run = db.get(ResearchAnalysisRun, run_id)
    if run is None or not run.result_json:
        raise HTTPException(status_code=404, detail="Analysis result not found")
    match = next((item for item in run.result_json.get("artifacts", []) if item.get("id") == artifact_id), None)
    if not match:
        raise HTTPException(status_code=404, detail="Artifact not found")
    path = Path(match.get("path", ""))
    if not path.is_file():
        raise HTTPException(status_code=410, detail="Artifact file is missing")
    return FileResponse(path, media_type=match.get("mime_type") or "application/octet-stream", filename=path.name)
