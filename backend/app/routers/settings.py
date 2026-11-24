from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..db import get_db
from ..schemas import IntegrationSettingsOut, IntegrationSettingsUpdate, ScholarlyDataSettingsOut, ScholarlyDataSettingsUpdate
from ..services.integration_settings import (
    as_parser_settings,
    load_last_test,
    load_runtime,
    provider_defaults,
    provider_profiles_to_public,
    runtime_to_public,
    save_runtime,
    update_last_test,
)
from ..services.research_documents import ocr_available
from ..services.research_provider import sdk_available, test_provider
from ..services.scholarly_settings import (
    load_last_scholarly_test,
    load_scholarly_runtime,
    save_scholarly_runtime,
    scholarly_runtime_to_public,
    update_last_scholarly_test,
)
from ..services.scholarly_diagnostics import test_scholarly_sources

router = APIRouter(tags=["settings"])


@router.get("/settings/integrations", response_model=IntegrationSettingsOut)
def get_integrations(db: Session = Depends(get_db), base: Settings = Depends(get_settings)) -> dict:
    runtime = load_runtime(db, base)
    return runtime_to_public(runtime, last_test=load_last_test(db), provider_profiles=provider_profiles_to_public(db, base))


@router.get("/settings/integrations/presets")
def get_presets() -> dict:
    return {
        "openai": {
            **provider_defaults("openai"),
            "label": "OpenAI",
            "helpUrl": "https://platform.openai.com/api-keys",
            "helpText": "在 OpenAI API Platform 创建 API Key。API 使用量与 ChatGPT 订阅分开计费。",
        },
        "deepseek": {
            **provider_defaults("deepseek"),
            "label": "DeepSeek",
            "helpUrl": "https://platform.deepseek.com/",
            "docsUrl": "https://api-docs.deepseek.com/zh-cn/",
            "helpText": "在 DeepSeek 开放平台创建 API Key。Super Scholar 默认使用 Chat Completions + JSON Object 进行文本研究理解；视觉材料通过本地 OCR 转成文本。",
        },
        "custom": {
            **provider_defaults("custom"),
            "label": "自定义 OpenAI-compatible",
            "helpText": "填写服务商给出的 Base URL、模型名和 API Key。不同兼容网关对 Responses、JSON Schema、图片和 Files API 的支持可能不同，请保存后运行连接测试。",
        },
    }


@router.put("/settings/integrations", response_model=IntegrationSettingsOut)
def put_integrations(payload: IntegrationSettingsUpdate, db: Session = Depends(get_db), base: Settings = Depends(get_settings)) -> dict:
    if payload.provider == "deepseek" and payload.supports_vision:
        raise HTTPException(status_code=400, detail="DeepSeek is configured as a text-only provider in Super Scholar. Disable vision; image/scanned content should first pass through local OCR or use a vision-capable provider.")
    if payload.send_direct_pdf and not payload.supports_files:
        raise HTTPException(status_code=400, detail="Direct PDF upload requires Files API support")
    runtime = save_runtime(db, payload, base)
    return runtime_to_public(runtime, last_test=load_last_test(db), provider_profiles=provider_profiles_to_public(db, base))


@router.post("/settings/integrations/test-ai")
def test_ai(db: Session = Depends(get_db), base: Settings = Depends(get_settings)) -> dict:
    if not sdk_available():
        raise HTTPException(status_code=503, detail="OpenAI-compatible SDK is not installed")
    runtime = load_runtime(db, base)
    result = test_provider(runtime)
    update_last_test(db, result)
    return result


@router.post("/settings/integrations/test-ocr")
def test_ocr(db: Session = Depends(get_db), base: Settings = Depends(get_settings)) -> dict:
    runtime = load_runtime(db, base)
    parser_settings = as_parser_settings(base, runtime)
    available = ocr_available(parser_settings)
    result = {
        "ok": available,
        "autoDetect": not bool(runtime.tesseract_cmd.strip()),
        "configuredPath": runtime.tesseract_cmd or None,
        "languages": runtime.ocr_languages,
        "message": "Tesseract OCR is available" if available else "Tesseract OCR was not detected. Install Tesseract or provide the executable path.",
    }
    if available:
        try:
            import pytesseract
            result["version"] = str(pytesseract.get_tesseract_version())
            result["installedLanguages"] = pytesseract.get_languages(config="")
            wanted = [x for x in runtime.ocr_languages.split("+") if x]
            result["configuredLanguagesPresent"] = all(x in result["installedLanguages"] for x in wanted)
            if not result["configuredLanguagesPresent"]:
                result["ok"] = False
                result["message"] = "Tesseract is installed, but one or more configured OCR language packs are missing."
        except Exception as exc:
            result["ok"] = False
            result["message"] = f"Tesseract was detected but capability inspection failed: {exc}"
    return result


@router.get("/settings/scholarly", response_model=ScholarlyDataSettingsOut)
def get_scholarly_settings(db: Session = Depends(get_db), base: Settings = Depends(get_settings)) -> dict:
    runtime = load_scholarly_runtime(db, base)
    return scholarly_runtime_to_public(runtime, last_test=load_last_scholarly_test(db))


@router.put("/settings/scholarly", response_model=ScholarlyDataSettingsOut)
def put_scholarly_settings(payload: ScholarlyDataSettingsUpdate, db: Session = Depends(get_db), base: Settings = Depends(get_settings)) -> dict:
    if payload.crossref_email and "@" not in payload.crossref_email:
        raise HTTPException(status_code=400, detail="Crossref polite-pool contact email must be a valid email address or left blank")
    runtime = save_scholarly_runtime(db, payload, base)
    return scholarly_runtime_to_public(runtime, last_test=load_last_scholarly_test(db))


@router.post("/settings/scholarly/test")
async def test_scholarly(db: Session = Depends(get_db), base: Settings = Depends(get_settings)) -> dict:
    runtime = load_scholarly_runtime(db, base)
    result = await test_scholarly_sources(runtime)
    update_last_scholarly_test(db, result, base)
    return result
