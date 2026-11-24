from __future__ import annotations

import hashlib

from fastapi.testclient import TestClient

from app.main import app


def test_material_upload_analysis_and_download():
    content = b"Super Scholar material bytes\n"
    expected = hashlib.sha256(content).hexdigest()
    with TestClient(app) as client:
        project = client.post("/api/v1/projects", json={"name": "Material test"}).json()
        project_id = project["id"]
        uploaded = client.post(
            f"/api/v1/projects/{project_id}/materials",
            files={"file": ("notes.txt", content, "text/plain")},
            data={"kind": "manuscript"},
        )
        assert uploaded.status_code == 201, uploaded.text
        material = uploaded.json()
        assert material["sha256"] == expected
        assert material["size"] == len(content)

        analysis = {
            "status": "ready",
            "progress": 100,
            "stage": "ready",
            "message": "解析完成",
        }
        updated = client.put(
            f"/api/v1/materials/{material['id']}/analysis",
            json={"analysis": analysis, "extracted_text": content.decode()},
        )
        assert updated.status_code == 200
        assert updated.json()["textAvailable"] is True
        assert client.get(f"/api/v1/materials/{material['id']}/text").text == content.decode()
        assert client.get(f"/api/v1/materials/{material['id']}/download").content == content
        preview = client.get(f"/api/v1/materials/{material['id']}/preview")
        assert preview.status_code == 200
        assert preview.content == content
        assert preview.headers.get("content-disposition") == "inline"

        removed = client.delete(f"/api/v1/materials/{material['id']}")
        assert removed.status_code == 204
        client.delete(f"/api/v1/projects/{project_id}")


def test_pdf_page_preview_route_renders_inline_page_png():
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Evidence page 1")
    pdf_bytes = doc.tobytes()
    doc.close()

    with TestClient(app) as client:
        project = client.post("/api/v1/projects", json={"name": "PDF preview test"}).json()
        uploaded = client.post(
            f"/api/v1/projects/{project['id']}/materials",
            files={"file": ("paper.pdf", pdf_bytes, "application/pdf")},
            data={"kind": "manuscript"},
        )
        assert uploaded.status_code == 201, uploaded.text
        material = uploaded.json()
        preview = client.get(f"/api/v1/materials/{material['id']}/pages/1/preview.png")
        assert preview.status_code == 200
        assert preview.headers["content-type"].startswith("image/png")
        assert preview.content.startswith(b"\x89PNG")
        client.delete(f"/api/v1/materials/{material['id']}")
        client.delete(f"/api/v1/projects/{project['id']}")
