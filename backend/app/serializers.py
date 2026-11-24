from __future__ import annotations

from .models import Material, Project


def project_to_dict(project: Project) -> dict:
    return {
        "id": project.id,
        "name": project.name,
        "brief": project.brief,
        "status": project.status,
        "archived": project.archived,
        "profile": project.profile_json,
        "preferences": project.preferences_json or {},
        "recommendationRun": project.recommendation_run_json,
        "comparisonVenueIds": project.comparison_venue_ids_json or [],
        "selectedVenueId": project.selected_venue_id,
        "materialIds": [material.id for material in project.materials],
        "createdAt": project.created_at,
        "updatedAt": project.updated_at,
    }


def material_to_dict(material: Material, api_prefix: str) -> dict:
    return {
        "id": material.id,
        "projectId": material.project_id,
        "name": material.name,
        "mimeType": material.mime_type,
        "extension": material.extension,
        "size": material.size,
        "kind": material.kind,
        "sha256": material.sha256,
        "analysis": material.analysis_json or {},
        "createdAt": material.created_at,
        "updatedAt": material.updated_at,
        "downloadUrl": f"{api_prefix}/materials/{material.id}/download",
        "textAvailable": bool(material.text_storage_path),
    }
