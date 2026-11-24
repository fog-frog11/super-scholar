from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import shutil
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..config import Settings, get_settings
from ..db import get_db
from ..models import Project
from ..schemas import ProjectCreate, ProjectSnapshot, ProjectUpdate
from ..serializers import project_to_dict

router = APIRouter(prefix="/projects", tags=["projects"])


def _query():
    return select(Project).options(selectinload(Project.materials))


@router.get("")
def list_projects(include_archived: bool = False, db: Session = Depends(get_db)) -> list[dict]:
    stmt = _query().order_by(Project.updated_at.desc())
    if not include_archived:
        stmt = stmt.where(Project.archived.is_(False))
    return [project_to_dict(project) for project in db.scalars(stmt).all()]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)) -> dict:
    project_id = payload.id or f"project_{uuid.uuid4()}"
    if db.get(Project, project_id):
        raise HTTPException(status_code=409, detail="Project ID already exists")
    now = datetime.now(timezone.utc)
    project = Project(
        id=project_id,
        name=payload.name.strip(),
        brief=payload.brief.strip(),
        preferences_json=payload.preferences,
        created_at=now,
        updated_at=now,
    )
    db.add(project)
    db.commit()
    project = db.scalar(_query().where(Project.id == project_id))
    assert project is not None
    return project_to_dict(project)


@router.put("/{project_id}/snapshot")
def upsert_snapshot(project_id: str, payload: ProjectSnapshot, db: Session = Depends(get_db)) -> dict:
    if payload.id != project_id:
        raise HTTPException(status_code=400, detail="Path project ID and snapshot ID differ")
    project = db.get(Project, project_id)
    if project is not None and payload.updatedAt is not None:
        current_updated = project.updated_at
        if current_updated.tzinfo is None:
            current_updated = current_updated.replace(tzinfo=timezone.utc)
        incoming_updated = payload.updatedAt
        if incoming_updated.tzinfo is None:
            incoming_updated = incoming_updated.replace(tzinfo=timezone.utc)
        if incoming_updated < current_updated:
            current = db.scalar(_query().where(Project.id == project_id))
            assert current is not None
            return project_to_dict(current)
    if project is None:
        project = Project(id=project_id, name=payload.name.strip())
    project.name = payload.name.strip()
    project.brief = payload.brief.strip()
    project.status = payload.status
    project.archived = payload.archived
    project.profile_json = payload.profile
    project.preferences_json = payload.preferences
    project.recommendation_run_json = payload.recommendationRun
    project.comparison_venue_ids_json = payload.comparisonVenueIds
    project.selected_venue_id = payload.selectedVenueId
    if payload.createdAt:
        project.created_at = payload.createdAt
    project.updated_at = payload.updatedAt or datetime.now(timezone.utc)
    db.add(project)
    db.commit()
    project = db.scalar(_query().where(Project.id == project_id))
    assert project is not None
    return project_to_dict(project)


@router.get("/{project_id}")
def get_project(project_id: str, db: Session = Depends(get_db)) -> dict:
    project = db.scalar(_query().where(Project.id == project_id))
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project_to_dict(project)


@router.patch("/{project_id}")
def update_project(project_id: str, payload: ProjectUpdate, db: Session = Depends(get_db)) -> dict:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    fields = payload.model_fields_set
    if "name" in fields and payload.name is not None:
        project.name = payload.name.strip()
    if "brief" in fields and payload.brief is not None:
        project.brief = payload.brief.strip()
    if "status" in fields and payload.status is not None:
        project.status = payload.status
    if "archived" in fields and payload.archived is not None:
        project.archived = payload.archived
    if payload.clear_profile:
        project.profile_json = None
    elif "profile" in fields:
        project.profile_json = payload.profile
    if "preferences" in fields and payload.preferences is not None:
        project.preferences_json = payload.preferences
    if payload.clear_recommendation_run:
        project.recommendation_run_json = None
    elif "recommendation_run" in fields:
        project.recommendation_run_json = payload.recommendation_run
    if "comparison_venue_ids" in fields and payload.comparison_venue_ids is not None:
        project.comparison_venue_ids_json = payload.comparison_venue_ids[:5]
    if payload.clear_selected_venue:
        project.selected_venue_id = None
    elif "selected_venue_id" in fields:
        project.selected_venue_id = payload.selected_venue_id
    project.updated_at = datetime.now(timezone.utc)
    db.add(project)
    db.commit()
    project = db.scalar(_query().where(Project.id == project_id))
    assert project is not None
    return project_to_dict(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: str, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)) -> None:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    db.delete(project)
    db.commit()
    shutil.rmtree(settings.storage_dir / "projects" / project_id, ignore_errors=True)
