from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import os
from typing import Any, Literal

from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..models import AIProviderProfile, IntegrationSettings
from ..security import decrypt_secret, encrypt_secret, secret_hint

ProviderName = Literal["openai", "deepseek", "custom"]
ProtocolName = Literal["responses", "chat_completions"]
OutputMode = Literal["json_schema", "json_object"]
TransportProfile = Literal["auto", "standard", "edge_safe"]
PROVIDERS: tuple[ProviderName, ...] = ("openai", "deepseek", "custom")


@dataclass(frozen=True)
class RuntimeIntegration:
    provider: ProviderName
    base_url: str
    api_key: str
    model: str
    protocol: ProtocolName
    output_mode: OutputMode
    reasoning_effort: str
    reasoning_enabled: bool
    streaming_enabled: bool
    transport_profile: TransportProfile
    supports_vision: bool
    supports_files: bool
    send_direct_pdf: bool
    max_text_chars: int
    max_visual_assets: int
    max_pdf_files: int
    max_output_tokens: int
    chunk_text_chars: int
    chunk_output_tokens: int
    synthesis_max_chars: int
    max_provider_calls: int
    visuals_per_chunk: int
    request_timeout_seconds: int
    tesseract_cmd: str
    ocr_languages: str
    ocr_min_native_text_chars: int
    source: Literal["ui", "environment"]

    @property
    def ai_configured(self) -> bool:
        return bool(self.api_key.strip() and self.base_url.strip() and self.model.strip())


def provider_defaults(provider: str) -> dict[str, Any]:
    if provider == "deepseek":
        return {
            "provider": "deepseek",
            "base_url": "https://api.deepseek.com",
            "model": "deepseek-v4-pro",
            "protocol": "chat_completions",
            "output_mode": "json_object",
            "reasoning_effort": "high",
            "reasoning_enabled": True,
            "streaming_enabled": True,
            "transport_profile": "auto",
            "supports_vision": False,
            "supports_files": False,
            "send_direct_pdf": False,
        }
    if provider == "openai":
        return {
            "provider": "openai",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-5.6",
            "protocol": "responses",
            "output_mode": "json_schema",
            "reasoning_effort": "medium",
            "reasoning_enabled": True,
            "streaming_enabled": True,
            "transport_profile": "auto",
            "supports_vision": True,
            "supports_files": True,
            "send_direct_pdf": False,
        }
    return {
        "provider": "custom",
        "base_url": "",
        "model": "",
        "protocol": "responses",
        "output_mode": "json_object",
        "reasoning_effort": "medium",
        "reasoning_enabled": True,
        "streaming_enabled": True,
        "transport_profile": "auto",
        "supports_vision": False,
        "supports_files": False,
        "send_direct_pdf": False,
    }


def _environment_runtime(settings: Settings | None = None) -> RuntimeIntegration:
    settings = settings or get_settings()
    base_url = os.getenv("OPENAI_BASE_URL", "").strip() or getattr(settings, "openai_base_url", "").strip() or "https://api.openai.com/v1"
    provider: ProviderName = "openai" if "api.openai.com" in base_url else "custom"
    return RuntimeIntegration(
        provider=provider,
        base_url=base_url.rstrip("/"),
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        protocol="responses",
        output_mode="json_schema" if provider == "openai" else "json_object",
        reasoning_effort=settings.openai_reasoning_effort,
        reasoning_enabled=True,
        streaming_enabled=settings.ai_streaming_enabled,
        transport_profile=(settings.ai_transport_profile if settings.ai_transport_profile in {"auto", "standard", "edge_safe"} else "auto"),
        supports_vision=True if provider == "openai" else False,
        supports_files=True if provider == "openai" else False,
        send_direct_pdf=False,
        max_text_chars=settings.ai_max_text_chars,
        max_visual_assets=settings.ai_max_visual_assets,
        max_pdf_files=settings.ai_max_pdf_files,
        max_output_tokens=settings.ai_max_output_tokens,
        chunk_text_chars=settings.ai_chunk_text_chars,
        chunk_output_tokens=settings.ai_chunk_output_tokens,
        synthesis_max_chars=settings.ai_synthesis_max_chars,
        max_provider_calls=settings.ai_max_provider_calls,
        visuals_per_chunk=settings.ai_visuals_per_chunk,
        request_timeout_seconds=settings.ai_request_timeout_seconds,
        tesseract_cmd=settings.tesseract_cmd,
        ocr_languages=settings.ocr_languages,
        ocr_min_native_text_chars=settings.ocr_min_native_text_chars,
        source="environment",
    )


def _profile_values_from_row(row: AIProviderProfile) -> dict[str, Any]:
    return {
        "provider": row.provider,
        "base_url": row.base_url.rstrip("/"),
        "api_key": decrypt_secret(row.api_key_encrypted),
        "model": row.model,
        "protocol": row.protocol if row.protocol in {"responses", "chat_completions"} else "responses",
        "output_mode": row.output_mode if row.output_mode in {"json_schema", "json_object"} else "json_object",
        "reasoning_effort": row.reasoning_effort,
        "reasoning_enabled": bool(row.reasoning_enabled),
        "streaming_enabled": bool(row.streaming_enabled),
        "transport_profile": row.transport_profile if row.transport_profile in {"auto", "standard", "edge_safe"} else "auto",
        "supports_vision": bool(row.supports_vision),
        "supports_files": bool(row.supports_files),
        "send_direct_pdf": bool(row.send_direct_pdf),
    }


def _legacy_profile_values(row: IntegrationSettings) -> dict[str, Any]:
    provider = row.ai_provider if row.ai_provider in PROVIDERS else "custom"
    return {
        "provider": provider,
        "base_url": row.ai_base_url.rstrip("/"),
        "api_key": decrypt_secret(row.ai_api_key_encrypted),
        "model": row.ai_model,
        "protocol": row.ai_protocol if row.ai_protocol in {"responses", "chat_completions"} else "responses",
        "output_mode": row.ai_output_mode if row.ai_output_mode in {"json_schema", "json_object"} else "json_object",
        "reasoning_effort": row.ai_reasoning_effort,
        "reasoning_enabled": bool(row.ai_reasoning_enabled),
        "streaming_enabled": bool(row.ai_streaming_enabled),
        "transport_profile": row.ai_transport_profile if row.ai_transport_profile in {"auto", "standard", "edge_safe"} else "auto",
        "supports_vision": bool(row.ai_supports_vision),
        "supports_files": bool(row.ai_supports_files),
        "send_direct_pdf": bool(row.ai_send_direct_pdf),
    }


def _global_values(row: IntegrationSettings | None, settings: Settings) -> dict[str, Any]:
    if row is None:
        env = _environment_runtime(settings)
        return {
            "max_text_chars": env.max_text_chars,
            "max_visual_assets": env.max_visual_assets,
            "max_pdf_files": env.max_pdf_files,
            "max_output_tokens": env.max_output_tokens,
            "chunk_text_chars": env.chunk_text_chars,
            "chunk_output_tokens": env.chunk_output_tokens,
            "synthesis_max_chars": env.synthesis_max_chars,
            "max_provider_calls": env.max_provider_calls,
            "visuals_per_chunk": env.visuals_per_chunk,
            "request_timeout_seconds": env.request_timeout_seconds,
            "tesseract_cmd": env.tesseract_cmd,
            "ocr_languages": env.ocr_languages,
            "ocr_min_native_text_chars": env.ocr_min_native_text_chars,
        }
    return {
        "max_text_chars": max(10_000, int(row.ai_max_text_chars)),
        "max_visual_assets": max(0, int(row.ai_max_visual_assets)),
        "max_pdf_files": max(0, int(row.ai_max_pdf_files)),
        "max_output_tokens": max(1_000, int(row.ai_max_output_tokens)),
        "chunk_text_chars": max(1_200, int(row.ai_chunk_text_chars)),
        "chunk_output_tokens": max(800, int(row.ai_chunk_output_tokens)),
        "synthesis_max_chars": max(8_000, int(row.ai_synthesis_max_chars)),
        "max_provider_calls": max(2, int(row.ai_max_provider_calls)),
        "visuals_per_chunk": max(0, int(row.ai_visuals_per_chunk)),
        "request_timeout_seconds": max(30, int(row.ai_request_timeout_seconds)),
        "tesseract_cmd": row.tesseract_cmd,
        "ocr_languages": row.ocr_languages,
        "ocr_min_native_text_chars": max(0, int(row.ocr_min_native_text_chars)),
    }


def _provider_values(db: Session, provider: ProviderName, settings: Settings, legacy: IntegrationSettings | None) -> tuple[dict[str, Any], Literal["ui", "environment", "default"]]:
    profile = db.get(AIProviderProfile, provider)
    if profile is not None:
        return _profile_values_from_row(profile), "ui"
    if legacy is not None and legacy.ai_provider == provider:
        return _legacy_profile_values(legacy), "ui"
    env = _environment_runtime(settings)
    if legacy is None and env.provider == provider:
        return {
            "provider": env.provider,
            "base_url": env.base_url,
            "api_key": env.api_key,
            "model": env.model,
            "protocol": env.protocol,
            "output_mode": env.output_mode,
            "reasoning_effort": env.reasoning_effort,
            "reasoning_enabled": env.reasoning_enabled,
            "streaming_enabled": env.streaming_enabled,
            "transport_profile": env.transport_profile,
            "supports_vision": env.supports_vision,
            "supports_files": env.supports_files,
            "send_direct_pdf": env.send_direct_pdf,
        }, "environment"
    defaults = provider_defaults(provider)
    return {**defaults, "api_key": ""}, "default"


def load_runtime(db: Session, settings: Settings | None = None) -> RuntimeIntegration:
    settings = settings or get_settings()
    row = db.get(IntegrationSettings, 1)
    if row is None:
        env = _environment_runtime(settings)
        profile_row = db.get(AIProviderProfile, env.provider)
        if profile_row is None:
            return env
        active: ProviderName = env.provider
    else:
        active = row.ai_provider if row.ai_provider in PROVIDERS else "custom"  # type: ignore[assignment]
    profile, source = _provider_values(db, active, settings, row)
    global_values = _global_values(row, settings)
    return RuntimeIntegration(
        provider=active,
        base_url=str(profile["base_url"]).rstrip("/"),
        api_key=str(profile.get("api_key") or ""),
        model=str(profile["model"]),
        protocol=profile["protocol"],  # type: ignore[arg-type]
        output_mode=profile["output_mode"],  # type: ignore[arg-type]
        reasoning_effort=str(profile["reasoning_effort"]),
        reasoning_enabled=bool(profile["reasoning_enabled"]),
        streaming_enabled=bool(profile["streaming_enabled"]),
        transport_profile=profile["transport_profile"],  # type: ignore[arg-type]
        supports_vision=bool(profile["supports_vision"]),
        supports_files=bool(profile["supports_files"]),
        send_direct_pdf=bool(profile["send_direct_pdf"]),
        source=source,
        **global_values,
    )


def _provider_profile_to_public(values: dict[str, Any], source: str, *, last_test: dict[str, Any] | None = None) -> dict[str, Any]:
    key = str(values.get("api_key") or "")
    return {
        "provider": values["provider"],
        "baseUrl": values["base_url"],
        "model": values["model"],
        "protocol": values["protocol"],
        "outputMode": values["output_mode"],
        "reasoningEffort": values["reasoning_effort"],
        "reasoningEnabled": bool(values["reasoning_enabled"]),
        "streamingEnabled": bool(values["streaming_enabled"]),
        "transportProfile": values["transport_profile"],
        "apiKeyConfigured": bool(key),
        "apiKeyHint": secret_hint(key),
        "supportsVision": bool(values["supports_vision"]),
        "supportsFiles": bool(values["supports_files"]),
        "sendDirectPdf": bool(values["send_direct_pdf"]),
        "source": source,
        "lastAiTest": last_test,
    }


def provider_profiles_to_public(db: Session, settings: Settings | None = None) -> dict[str, dict[str, Any]]:
    settings = settings or get_settings()
    legacy = db.get(IntegrationSettings, 1)
    output: dict[str, dict[str, Any]] = {}
    for provider in PROVIDERS:
        values, source = _provider_values(db, provider, settings, legacy)
        profile_row = db.get(AIProviderProfile, provider)
        last_test = dict(profile_row.last_test_json) if profile_row and profile_row.last_test_json else None
        if last_test is None and legacy is not None and legacy.ai_provider == provider and legacy.last_ai_test_json:
            last_test = dict(legacy.last_ai_test_json)
        output[provider] = _provider_profile_to_public(values, source, last_test=last_test)
    return output


def runtime_to_public(runtime: RuntimeIntegration, *, last_test: dict[str, Any] | None = None, provider_profiles: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "provider": runtime.provider,
        "baseUrl": runtime.base_url,
        "model": runtime.model,
        "protocol": runtime.protocol,
        "outputMode": runtime.output_mode,
        "reasoningEffort": runtime.reasoning_effort,
        "reasoningEnabled": runtime.reasoning_enabled,
        "streamingEnabled": runtime.streaming_enabled,
        "transportProfile": runtime.transport_profile,
        "apiKeyConfigured": bool(runtime.api_key),
        "apiKeyHint": secret_hint(runtime.api_key),
        "supportsVision": runtime.supports_vision,
        "supportsFiles": runtime.supports_files,
        "sendDirectPdf": runtime.send_direct_pdf,
        "maxTextChars": runtime.max_text_chars,
        "maxVisualAssets": runtime.max_visual_assets,
        "maxPdfFiles": runtime.max_pdf_files,
        "maxOutputTokens": runtime.max_output_tokens,
        "chunkTextChars": runtime.chunk_text_chars,
        "chunkOutputTokens": runtime.chunk_output_tokens,
        "synthesisMaxChars": runtime.synthesis_max_chars,
        "maxProviderCalls": runtime.max_provider_calls,
        "visualsPerChunk": runtime.visuals_per_chunk,
        "requestTimeoutSeconds": runtime.request_timeout_seconds,
        "tesseractCmd": runtime.tesseract_cmd,
        "ocrLanguages": runtime.ocr_languages,
        "ocrMinNativeTextChars": runtime.ocr_min_native_text_chars,
        "source": runtime.source,
        "lastAiTest": last_test,
        "providerProfiles": provider_profiles or {},
    }


def save_runtime(db: Session, payload: Any, settings: Settings | None = None) -> RuntimeIntegration:
    settings = settings or get_settings()
    row = db.get(IntegrationSettings, 1)
    current = load_runtime(db, settings) if row is not None else _environment_runtime(settings)
    if row is None:
        row = IntegrationSettings(id=1)
        db.add(row)

    provider: ProviderName = payload.provider
    defaults = provider_defaults(provider)
    profile = db.get(AIProviderProfile, provider)
    if profile is None:
        profile = AIProviderProfile(provider=provider)
        db.add(profile)
        old_key = current.api_key if current.provider == provider else ""
    else:
        old_key = decrypt_secret(profile.api_key_encrypted)

    base_url = (payload.base_url or defaults["base_url"]).strip().rstrip("/")
    model = (payload.model or defaults["model"]).strip()
    profile.base_url = base_url
    profile.model = model
    profile.protocol = payload.protocol
    profile.output_mode = payload.output_mode
    profile.reasoning_effort = payload.reasoning_effort
    profile.reasoning_enabled = bool(payload.reasoning_enabled)
    profile.streaming_enabled = bool(payload.streaming_enabled)
    profile.transport_profile = payload.transport_profile if payload.transport_profile in {"auto", "standard", "edge_safe"} else "auto"
    if payload.api_key is not None:
        key = payload.api_key.strip()
        profile.api_key_encrypted = encrypt_secret(key) if key else None
        effective_key = key
    else:
        effective_key = old_key
        if profile.api_key_encrypted is None and old_key:
            profile.api_key_encrypted = encrypt_secret(old_key)
    profile.supports_vision = False if provider == "deepseek" else bool(payload.supports_vision)
    profile.supports_files = False if provider == "deepseek" else bool(payload.supports_files)
    profile.send_direct_pdf = bool(payload.send_direct_pdf and payload.supports_files and provider != "deepseek")
    profile.updated_at = datetime.now(timezone.utc)

    # Active provider and global analysis/OCR limits remain singleton settings. The
    # legacy active-provider columns are mirrored for downgrade/backward compatibility,
    # while each provider's real settings/key live independently in ai_provider_profiles.
    row.ai_provider = provider
    row.ai_base_url = profile.base_url
    row.ai_model = profile.model
    row.ai_protocol = profile.protocol
    row.ai_output_mode = profile.output_mode
    row.ai_reasoning_effort = profile.reasoning_effort
    row.ai_reasoning_enabled = profile.reasoning_enabled
    row.ai_streaming_enabled = profile.streaming_enabled
    row.ai_transport_profile = profile.transport_profile
    row.ai_api_key_encrypted = encrypt_secret(effective_key) if effective_key else None
    row.ai_supports_vision = profile.supports_vision
    row.ai_supports_files = profile.supports_files
    row.ai_send_direct_pdf = profile.send_direct_pdf
    row.ai_max_text_chars = max(10_000, min(int(payload.max_text_chars), 1_000_000))
    row.ai_max_visual_assets = max(0, min(int(payload.max_visual_assets), 32))
    row.ai_max_pdf_files = max(0, min(int(payload.max_pdf_files), 8))
    row.ai_max_output_tokens = max(1_000, min(int(payload.max_output_tokens), 64_000))
    row.ai_chunk_text_chars = max(1_200, min(int(payload.chunk_text_chars), 50_000))
    row.ai_chunk_output_tokens = max(800, min(int(payload.chunk_output_tokens), 8_000))
    row.ai_synthesis_max_chars = max(8_000, min(int(payload.synthesis_max_chars), 100_000))
    row.ai_max_provider_calls = max(2, min(int(payload.max_provider_calls), 20))
    row.ai_visuals_per_chunk = max(0, min(int(payload.visuals_per_chunk), 4))
    row.ai_request_timeout_seconds = max(30, min(int(payload.request_timeout_seconds), 600))
    row.tesseract_cmd = payload.tesseract_cmd.strip()
    row.ocr_languages = payload.ocr_languages.strip() or "eng"
    row.ocr_min_native_text_chars = max(0, min(int(payload.ocr_min_native_text_chars), 5000))
    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return load_runtime(db, settings)


def update_last_test(db: Session, result: dict[str, Any]) -> None:
    row = db.get(IntegrationSettings, 1)
    if row is None:
        return
    row.last_ai_test_json = result
    provider = row.ai_provider if row.ai_provider in PROVIDERS else "custom"
    profile = db.get(AIProviderProfile, provider)
    if profile is not None:
        profile.last_test_json = result
        profile.updated_at = datetime.now(timezone.utc)
        db.add(profile)
    row.updated_at = datetime.now(timezone.utc)
    db.add(row)
    db.commit()


def load_last_test(db: Session) -> dict[str, Any] | None:
    row = db.get(IntegrationSettings, 1)
    if row is None:
        return None
    provider = row.ai_provider if row.ai_provider in PROVIDERS else "custom"
    profile = db.get(AIProviderProfile, provider)
    if profile is not None and profile.last_test_json:
        return dict(profile.last_test_json)
    return dict(row.last_ai_test_json) if row.last_ai_test_json else None


def as_parser_settings(base: Settings, runtime: RuntimeIntegration) -> Settings:
    return base.model_copy(update={
        "tesseract_cmd": runtime.tesseract_cmd,
        "ocr_languages": runtime.ocr_languages,
        "ocr_min_native_text_chars": runtime.ocr_min_native_text_chars,
        "openai_api_key": runtime.api_key,
        "openai_model": runtime.model,
        "openai_reasoning_effort": runtime.reasoning_effort,
        "ai_max_text_chars": runtime.max_text_chars,
        "ai_max_visual_assets": runtime.max_visual_assets,
        "ai_max_pdf_files": runtime.max_pdf_files,
        "ai_max_output_tokens": runtime.max_output_tokens,
    })
