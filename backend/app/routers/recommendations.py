from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..db import get_db
from ..models import Project
from ..services.venue_recommendation import recommend

router = APIRouter(tags=["recommendations"])


class RecommendationRequest(BaseModel):
    profile: dict[str, Any] = Field(default_factory=dict)
    preferences: dict[str, Any] = Field(default_factory=dict)


@router.post("/projects/{project_id}/recommendations")
async def create_recommendations(
    project_id: str,
    payload: RecommendationRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if not payload.profile:
        raise HTTPException(status_code=400, detail="Research profile is required")
    try:
        run = await recommend(db, settings, project, payload.profile, payload.preferences)
    except Exception as exc:
        raise HTTPException(status_code=503, detail={"code": "recommendation_failed", "message": str(exc)}) from exc

    # Persist the exact inputs used for the run so browser refreshes cannot silently pair
    # results with a different profile/preferences snapshot.
    project.profile_json = payload.profile
    project.preferences_json = payload.preferences
    project.recommendation_run_json = run
    project.status = "recommendations_ready"
    project.comparison_venue_ids_json = []
    project.selected_venue_id = None
    db.add(project)
    db.commit()
    return run
