from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_research_capabilities_are_truthful_without_key(monkeypatch):
    from app.routers import research
    monkeypatch.setattr(research, "openai_sdk_available", lambda: True)
    # Test environment intentionally has no API key.
    with TestClient(app) as client:
        data = client.get("/api/v1/research/capabilities").json()
    assert data["aiConfigured"] is False
    assert isinstance(data["ocrAvailable"], bool)


def test_ai_start_requires_configuration():
    with TestClient(app) as client:
        client.put("/api/v1/projects/project_research_test/snapshot", json={"id":"project_research_test","name":"Research test","brief":"test","status":"draft","archived":False,"preferences":{},"comparisonVenueIds":[]})
        response = client.post("/api/v1/projects/project_research_test/research-analysis", json={"consent_external_processing": True})
    assert response.status_code == 409
