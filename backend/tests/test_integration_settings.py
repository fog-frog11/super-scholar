from __future__ import annotations

from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import AIProviderProfile, IntegrationSettings
from app.security import decrypt_secret


def cleanup():
    with SessionLocal() as db:
        for provider in ("openai", "deepseek", "custom"):
            profile = db.get(AIProviderProfile, provider)
            if profile:
                db.delete(profile)
        row = db.get(IntegrationSettings, 1)
        if row:
            db.delete(row)
        db.commit()


def test_ui_integration_settings_encrypt_and_mask_api_key():
    with TestClient(app) as client:
        cleanup()
        try:
            response = client.put("/api/v1/settings/integrations", json={
                "provider": "custom",
                "base_url": "https://gateway.example/v1",
                "model": "example-model",
                "protocol": "responses",
                "output_mode": "json_object",
                "reasoning_effort": "high",
                "reasoning_enabled": True,
                "streaming_enabled": True,
                "transport_profile": "edge_safe",
                "api_key": "sk-test-secret-1234567890",
                "supports_vision": False,
                "supports_files": False,
                "send_direct_pdf": False,
                "max_text_chars": 220000,
                "max_visual_assets": 8,
                "max_pdf_files": 0,
                "max_output_tokens": 12000,
                "tesseract_cmd": "",
                "ocr_languages": "eng",
                "ocr_min_native_text_chars": 80,
            })
            assert response.status_code == 200, response.text
            data = response.json()
            assert data["apiKeyConfigured"] is True
            assert data["apiKeyHint"].startswith("sk-")
            assert "test-secret" not in response.text

            fetched = client.get("/api/v1/settings/integrations").json()
            assert fetched["baseUrl"] == "https://gateway.example/v1"
            assert fetched["provider"] == "custom"
            assert fetched["transportProfile"] == "edge_safe"
            assert "test-secret" not in str(fetched)

            with SessionLocal() as db:
                row = db.get(IntegrationSettings, 1)
                assert row is not None
                assert row.ai_api_key_encrypted != "sk-test-secret-1234567890"
                assert decrypt_secret(row.ai_api_key_encrypted) == "sk-test-secret-1234567890"
        finally:
            cleanup()


def test_deepseek_preset_prefers_chat_text_pipeline():
    from app.services.integration_settings import provider_defaults
    preset = provider_defaults("deepseek")
    assert preset["protocol"] == "chat_completions"
    assert preset["output_mode"] == "json_object"
    assert preset["supports_vision"] is False
    assert preset["supports_files"] is False


def _payload(provider: str, *, base_url: str, model: str, api_key: str | None = None) -> dict:
    return {
        "provider": provider,
        "base_url": base_url,
        "model": model,
        "protocol": "responses" if provider != "deepseek" else "chat_completions",
        "output_mode": "json_object",
        "reasoning_effort": "medium",
        "reasoning_enabled": True,
        "streaming_enabled": True,
        "transport_profile": "edge_safe" if provider == "custom" else "auto",
        "api_key": api_key,
        "supports_vision": provider == "openai",
        "supports_files": provider == "openai",
        "send_direct_pdf": False,
        "max_text_chars": 220000,
        "max_visual_assets": 8,
        "max_pdf_files": 0,
        "max_output_tokens": 12000,
        "tesseract_cmd": "",
        "ocr_languages": "eng",
        "ocr_min_native_text_chars": 80,
    }


def test_provider_profiles_persist_independently_when_switching() -> None:
    with TestClient(app) as client:
        cleanup()
        try:
            custom = client.put("/api/v1/settings/integrations", json=_payload(
                "custom", base_url="https://gateway.example/v1", model="custom-model", api_key="custom-secret-key"
            ))
            assert custom.status_code == 200, custom.text
            openai = client.put("/api/v1/settings/integrations", json=_payload(
                "openai", base_url="https://api.openai.com/v1", model="gpt-test", api_key="openai-secret-key"
            ))
            assert openai.status_code == 200, openai.text

            fetched = client.get("/api/v1/settings/integrations")
            assert fetched.status_code == 200, fetched.text
            body = fetched.json()
            assert body["provider"] == "openai"
            assert body["providerProfiles"]["custom"]["baseUrl"] == "https://gateway.example/v1"
            assert body["providerProfiles"]["custom"]["model"] == "custom-model"
            assert body["providerProfiles"]["custom"]["apiKeyConfigured"] is True
            assert body["providerProfiles"]["openai"]["model"] == "gpt-test"
            assert body["providerProfiles"]["openai"]["apiKeyConfigured"] is True
            assert "custom-secret-key" not in fetched.text
            assert "openai-secret-key" not in fetched.text

            # Switch back to Custom without re-sending its API key. The independently
            # encrypted Custom key and model/base URL must survive the OpenAI save.
            switched = client.put("/api/v1/settings/integrations", json=_payload(
                "custom", base_url="https://gateway.example/v1", model="custom-model", api_key=None
            ))
            assert switched.status_code == 200, switched.text
            switched_body = switched.json()
            assert switched_body["provider"] == "custom"
            assert switched_body["baseUrl"] == "https://gateway.example/v1"
            assert switched_body["model"] == "custom-model"
            assert switched_body["apiKeyConfigured"] is True

            with SessionLocal() as db:
                custom_row = db.get(AIProviderProfile, "custom")
                openai_row = db.get(AIProviderProfile, "openai")
                assert custom_row is not None and openai_row is not None
                assert decrypt_secret(custom_row.api_key_encrypted) == "custom-secret-key"
                assert decrypt_secret(openai_row.api_key_encrypted) == "openai-secret-key"
        finally:
            cleanup()
