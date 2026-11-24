from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import uuid

from sqlalchemy import select

from ..config import get_settings
from ..db import SessionLocal
from ..models import Material, Project, ResearchAnalysisRun
from .research_ai import ResearchPipelineError, analyze_with_provider
from .integration_settings import as_parser_settings, load_runtime
from .research_documents import EvidenceItem, VisualArtifact, parse_material, serialize_artifacts, serialize_evidence


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _update(run_id: str, *, status: str | None = None, progress: int | None = None, stage: str | None = None, message: str | None = None, result: dict[str, Any] | None = None, error: str | None = None, model: str | None = None) -> None:
    with SessionLocal() as db:
        run = db.get(ResearchAnalysisRun, run_id)
        if run is None:
            return
        if status is not None: run.status = status
        if progress is not None: run.progress = max(0, min(100, progress))
        if stage is not None: run.stage = stage
        if message is not None: run.message = message
        if result is not None: run.result_json = result
        if error is not None: run.error = error
        if model is not None: run.model = model
        run.updated_at = _now()
        db.add(run); db.commit()


def execute_analysis(run_id: str) -> None:
    settings = get_settings()
    try:
        _update(run_id, status="running", progress=6, stage="loading", message="正在读取项目与材料")
        with SessionLocal() as db:
            run = db.get(ResearchAnalysisRun, run_id)
            if run is None:
                return
            project = db.get(Project, run.project_id)
            if project is None:
                raise RuntimeError("Project not found")
            materials = list(db.scalars(select(Material).where(Material.project_id == project.id).order_by(Material.created_at.asc())).all())
            # Detach the objects before the session is closed.
            project_snapshot = Project(id=project.id, name=project.name, brief=project.brief)
            material_snapshots = [
                Material(
                    id=m.id, project_id=m.project_id, name=m.name, mime_type=m.mime_type,
                    extension=m.extension, size=m.size, kind=m.kind, sha256=m.sha256,
                    storage_path=m.storage_path, text_storage_path=m.text_storage_path,
                    analysis_json=dict(m.analysis_json or {}), created_at=m.created_at, updated_at=m.updated_at,
                ) for m in materials
            ]
            runtime = load_runtime(db, settings)
            parser_settings = as_parser_settings(settings, runtime)

        if not material_snapshots and not project_snapshot.brief.strip():
            raise RuntimeError("No research material or project brief is available")

        _update(run_id, progress=14, stage="parsing", message="正在解析论文、代码、表格与图像")
        artifact_dir = settings.storage_dir / "projects" / project_snapshot.id / "research_runs" / run_id / "artifacts"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        evidence: list[EvidenceItem] = []
        artifacts: list[VisualArtifact] = []
        parser_meta: dict[str, Any] = {}
        if project_snapshot.brief.strip():
            evidence.append(EvidenceItem(
                id=f"ev_project_{project_snapshot.id}_brief", material_id="project", kind="project_brief",
                label="User project brief", text=project_snapshot.brief.strip()[:50_000], metadata={}
            ))
        total = max(1, len(material_snapshots))
        for idx, material in enumerate(material_snapshots):
            ev, arts, meta = parse_material(material, artifact_dir, parser_settings)
            evidence.extend(ev); artifacts.extend(arts); parser_meta[material.id] = meta
            # Real parser-completion progress; no timer-based fake growth.
            _update(run_id, progress=14 + round(((idx + 1) / total) * 38), stage="parsing", message=f"已解析 {idx+1}/{total} 份材料：{material.name}")

        if not evidence and not artifacts:
            raise RuntimeError("No usable text, table, OCR, code, or visual evidence could be extracted from the project")
        if not evidence and artifacts and not runtime.supports_vision:
            raise RuntimeError("The project contains visual evidence but the current AI provider is configured as text-only and OCR produced no text. Enable OCR or choose a vision-capable provider in Settings → 模型与解析.")
        _update(run_id, progress=56, stage="evidence", message=f"已形成 {len(evidence)} 条证据与 {len(artifacts)} 个视觉资产")

        if not runtime.ai_configured:
            raise RuntimeError("AI deep analysis is not configured. Open Settings → 模型与解析 to configure a provider, or use the local baseline.")

        _update(run_id, progress=64, stage="reasoning", message=f"正在通过 {runtime.provider} / {runtime.model} 进行跨材料研究理解", model=runtime.model)
        generated_at = _now().isoformat()
        def _attempt_progress(attempt_index: int, attempt_total: int, attempt_name: str) -> None:
            # Every callback corresponds to exactly one real provider request; SDK retries are disabled.
            if attempt_name.startswith("text:"):
                label = f"正在逐块读取研究文本 · {attempt_name.split(':', 1)[1]}"
            elif attempt_name.startswith("visual:"):
                label = f"正在逐张理解研究图像 · {attempt_name.split(':', 1)[1]}"
            elif attempt_name == "synthesis":
                label = "正在用压缩后的研究事实生成最终画像"
            else:
                label = "正在执行研究理解请求"
            span = max(1, attempt_total)
            progress = min(89, 64 + round((max(0, attempt_index - 1) / span) * 23))
            _update(run_id, progress=progress, stage="reasoning", message=f"{label} · Provider 请求 {attempt_index}/{attempt_total}")

        ai_result = analyze_with_provider(
            project_snapshot, material_snapshots, evidence, artifacts, parser_meta,
            parser_settings, runtime, generated_at, on_attempt=_attempt_progress,
        )
        _update(run_id, progress=91, stage="grounding", message="正在校验证据引用并过滤未落地的结论")

        result = {
            **ai_result,
            "evidence": serialize_evidence(evidence),
            "artifacts": [
                {**item, "url": f"{settings.api_prefix}/research-analysis/{run_id}/artifacts/{item['id']}"}
                for item in serialize_artifacts(artifacts)
            ],
            "parserMetadata": parser_meta,
        }
        with SessionLocal() as db:
            project = db.get(Project, project_snapshot.id)
            run = db.get(ResearchAnalysisRun, run_id)
            if project is None or run is None:
                raise RuntimeError("Analysis state disappeared before persistence")
            project.profile_json = ai_result["profile"]
            project.status = "profile_ready"
            project.recommendation_run_json = None
            project.comparison_venue_ids_json = []
            project.selected_venue_id = None
            project.updated_at = _now()
            run.result_json = result
            run.status = "ready"; run.progress = 100; run.stage = "ready"; run.message = "AI 深度研究画像已完成"; run.error = None; run.model = runtime.model; run.updated_at = _now()
            db.add(project); db.add(run); db.commit()
    except ResearchPipelineError as exc:
        _update(
            run_id, status="error", stage="error", message="研究理解失败",
            error=str(exc), result={"diagnostics": exc.diagnostics},
        )
    except Exception as exc:
        _update(run_id, status="error", stage="error", message="研究理解失败", error=str(exc))
