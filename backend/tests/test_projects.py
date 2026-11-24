import os
from pathlib import Path

os.environ["SUPER_SCHOLAR_DATABASE_URL"] = "sqlite:///./data/test_super_scholar.db"
os.environ["SUPER_SCHOLAR_STORAGE_DIR"] = "./storage-test"

from fastapi.testclient import TestClient
from app.main import app


def test_project_crud():
    with TestClient(app) as client:
        created = client.post("/api/v1/projects", json={"name": "Test Research", "brief": "A research brief", "preferences": {}})
        assert created.status_code == 201, created.text
        project = created.json()
        project_id = project["id"]
        assert project["name"] == "Test Research"

        changed = client.patch(f"/api/v1/projects/{project_id}", json={"name": "Renamed Research", "archived": True})
        assert changed.status_code == 200, changed.text
        assert changed.json()["name"] == "Renamed Research"
        assert changed.json()["archived"] is True

        fetched = client.get(f"/api/v1/projects/{project_id}")
        assert fetched.status_code == 200
        assert fetched.json()["id"] == project_id

        deleted = client.delete(f"/api/v1/projects/{project_id}")
        assert deleted.status_code == 204
        assert client.get(f"/api/v1/projects/{project_id}").status_code == 404
