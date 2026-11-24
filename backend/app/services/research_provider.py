from __future__ import annotations

import base64
import io
import json
import time
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

from PIL import Image, ImageDraw

try:
    from openai import APIConnectionError, APIStatusError, OpenAI
except ImportError:  # pragma: no cover
    APIConnectionError = APIStatusError = Exception  # type: ignore[assignment]
    OpenAI = None  # type: ignore[assignment]

from .integration_settings import RuntimeIntegration


class ProviderCallError(RuntimeError):
    def __init__(
        self,
        phase: str,
        *,
        status_code: int | None = None,
        message: str = "",
        response_body: str | None = None,
        request_id: str | None = None,
        response_headers: dict[str, str] | None = None,
    ):
        self.phase = phase
        self.status_code = status_code
        self.provider_message = message
        self.response_body = response_body
        self.request_id = request_id
        self.response_headers = response_headers or {}
        pieces = [f"AI provider failed during {phase}"]
        if status_code is not None:
            pieces.append(f"HTTP {status_code}")
        if message:
            pieces.append(message.strip())
        if response_body and response_body.strip() and response_body.strip() not in message:
            pieces.append(response_body.strip()[:600])
        if request_id:
            pieces.append(f"request_id={request_id}")
        super().__init__(": ".join(pieces))


def sdk_available() -> bool:
    return OpenAI is not None


def make_client(runtime: RuntimeIntegration):
    if OpenAI is None:
        raise RuntimeError("The OpenAI-compatible Python SDK is not installed")
    if not runtime.api_key.strip():
        raise RuntimeError("API key is not configured")
    if not runtime.base_url.strip():
        raise RuntimeError("Base URL is not configured")
    # IMPORTANT: Super Scholar owns its request budget. The OpenAI Python SDK retries
    # >=500 responses twice by default, which can multiply both cost and latency when a
    # custom gateway returns a non-standard 5xx such as 554. Disable SDK retries so one
    # planned provider call always means one real HTTP request.
    return OpenAI(
        api_key=runtime.api_key,
        base_url=runtime.base_url.rstrip("/"),
        max_retries=0,
        timeout=float(runtime.request_timeout_seconds),
    )


SAFE_RESPONSE_HEADERS = {
    "x-request-id", "request-id", "cf-ray", "server", "content-type",
    "retry-after", "x-ratelimit-limit-requests", "x-ratelimit-remaining-requests",
    "x-ratelimit-reset-requests", "x-upstream-status", "x-error-code", "x-error-type",
}


def _response_text(exc: Exception) -> tuple[int | None, str | None, str | None, dict[str, str]]:
    status_code = getattr(exc, "status_code", None)
    request_id = getattr(exc, "request_id", None)
    response = getattr(exc, "response", None)
    body: str | None = None
    headers: dict[str, str] = {}
    if response is not None:
        try:
            body = response.text
        except Exception:
            body = None
        try:
            for key, value in response.headers.items():
                low = str(key).lower()
                if low in SAFE_RESPONSE_HEADERS or low.startswith("x-request-") or low.startswith("x-error-"):
                    headers[str(key)] = str(value)[:400]
        except Exception:
            headers = {}
    return status_code, body, request_id, headers


def raise_provider_error(exc: Exception, phase: str) -> None:
    if isinstance(exc, ProviderCallError):
        raise exc
    status_code, body, request_id, headers = _response_text(exc)
    message = str(exc)
    raise ProviderCallError(
        phase,
        status_code=status_code,
        message=message,
        response_body=body,
        request_id=request_id,
        response_headers=headers,
    ) from exc


def _schema_instructions(instructions: str, schema: dict[str, Any], compact_contract: str | None = None) -> str:
    if compact_contract:
        return instructions + "\n\nReturn JSON only. Follow this compact JSON contract exactly:\n" + compact_contract.strip()
    return instructions + "\n\nReturn JSON only. The JSON must conform to this schema:\n" + json.dumps(schema, ensure_ascii=False, separators=(",", ":"))


def _response_object_text(response: Any) -> str:
    text = getattr(response, "output_text", None)
    if isinstance(text, str) and text.strip():
        return text.strip()
    pieces: list[str] = []
    for item in getattr(response, "output", None) or []:
        for content_item in getattr(item, "content", None) or []:
            value = getattr(content_item, "text", None)
            if isinstance(value, str) and value:
                pieces.append(value)
    return "".join(pieces).strip()


def _responses_stream_text(client: Any, *, phase: str, kwargs: dict[str, Any]) -> tuple[str, int | None, int]:
    started = time.monotonic()
    first_event_ms: int | None = None
    event_count = 0
    terminal: str | None = None
    completed_response: Any = None
    parts: list[str] = []
    try:
        stream = client.responses.create(**kwargs, stream=True)
        for event in stream:
            event_count += 1
            if first_event_ms is None:
                first_event_ms = round((time.monotonic() - started) * 1000)
            typ = str(getattr(event, "type", "") or "")
            if typ == "response.output_text.delta":
                delta = getattr(event, "delta", None)
                if isinstance(delta, str):
                    parts.append(delta)
            elif typ == "response.completed":
                terminal = "completed"
                completed_response = getattr(event, "response", None)
            elif typ in {"response.failed", "response.incomplete", "response.cancelled"}:
                terminal = typ
                response_obj = getattr(event, "response", None)
                detail = getattr(response_obj, "error", None) or getattr(event, "error", None) or typ
                raise ProviderCallError(phase, message=f"stream ended with terminal event {typ}: {detail}")
    except ProviderCallError:
        raise
    except Exception as exc:
        raise_provider_error(exc, phase)
    if terminal != "completed":
        raise ProviderCallError(
            phase,
            message=(
                "stream closed before response.completed"
                + (f" after {event_count} SSE event(s)" if event_count else " before the first SSE event")
            ),
        )
    text = "".join(parts).strip() or _response_object_text(completed_response)
    if not text:
        raise ProviderCallError(phase, message="provider completed the SSE stream but returned no text output")
    return text, first_event_ms, event_count


def _chat_stream_text(client: Any, *, phase: str, kwargs: dict[str, Any]) -> tuple[str, int | None, int]:
    started = time.monotonic()
    first_event_ms: int | None = None
    event_count = 0
    finished = False
    finish_reasons: list[str] = []
    parts: list[str] = []
    try:
        stream = client.chat.completions.create(**kwargs, stream=True)
        for chunk in stream:
            event_count += 1
            if first_event_ms is None:
                first_event_ms = round((time.monotonic() - started) * 1000)
            for choice in getattr(chunk, "choices", None) or []:
                delta = getattr(getattr(choice, "delta", None), "content", None)
                if isinstance(delta, str):
                    parts.append(delta)
                finish_reason = getattr(choice, "finish_reason", None)
                if finish_reason is not None:
                    finished = True
                    finish_reasons.append(str(finish_reason))
    except ProviderCallError:
        raise
    except Exception as exc:
        raise_provider_error(exc, phase)
    if not finished:
        raise ProviderCallError(
            phase,
            message=(
                "chat stream closed before a finish_reason was received"
                + (f" after {event_count} chunk(s)" if event_count else " before the first streamed chunk")
            ),
        )
    terminal_reason = finish_reasons[-1] if finish_reasons else None
    if terminal_reason in {"length", "content_filter", "insufficient_system_resource"}:
        raise ProviderCallError(
            phase,
            message=f"chat stream ended with finish_reason={terminal_reason}; output cannot be trusted as complete JSON",
        )
    text = "".join(parts).strip()
    if not text:
        raise ProviderCallError(phase, message="provider completed the chat stream but returned no text output")
    return text, first_event_ms, event_count


def _responses_json(runtime: RuntimeIntegration, client: Any, *, instructions: str, content: list[dict[str, Any]], schema: dict[str, Any], name: str, phase: str, compact_contract: str | None = None) -> str:
    kwargs: dict[str, Any] = {
        "model": runtime.model,
        "store": False,
        "max_output_tokens": runtime.max_output_tokens,
        "input": [{"role": "user", "content": content}],
    }
    if runtime.reasoning_enabled:
        kwargs["reasoning"] = {"effort": runtime.reasoning_effort}
    else:
        # Do not merely omit reasoning for GPT-5.x / Responses-compatible gateways:
        # omission may use the model default (often medium), which increases time-to-first-event.
        # `none` is documented by OpenAI GPT-5.6 and DeepSeek Responses and is the intended
        # extraction-stage behavior. If a custom gateway does not implement this field, the
        # connection research-probe will surface that incompatibility before a real project run.
        kwargs["reasoning"] = {"effort": "none"}
    if runtime.output_mode == "json_schema":
        # If the user selected JSON Schema / Structured Outputs, request actual strict
        # adherence rather than silently weakening custom OpenAI-compatible gateways to
        # non-strict schema mode. Incompatible gateways are surfaced by the connection
        # probe and can use JSON Object compatibility mode instead.
        fmt: dict[str, Any] = {"type": "json_schema", "name": name, "schema": schema, "strict": True}
        kwargs["instructions"] = instructions
        kwargs["text"] = {"format": fmt}
    else:
        kwargs["instructions"] = _schema_instructions(instructions, schema, compact_contract)
        kwargs["text"] = {"format": {"type": "json_object"}}
    if runtime.streaming_enabled:
        text, _, _ = _responses_stream_text(client, phase=phase, kwargs=kwargs)
        return text
    try:
        response = client.responses.create(**kwargs)
    except Exception as exc:
        raise_provider_error(exc, phase)
    text = _response_object_text(response)
    if not text:
        raise ProviderCallError(phase, message="provider returned no text output")
    return text


def _chat_content(content: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in content:
        typ = item.get("type")
        if typ == "input_text":
            result.append({"type": "text", "text": item.get("text", "")})
        elif typ == "input_image":
            result.append({"type": "image_url", "image_url": {"url": item.get("image_url", ""), "detail": item.get("detail", "high")}})
    return result


def _chat_json(runtime: RuntimeIntegration, client: Any, *, instructions: str, content: list[dict[str, Any]], schema: dict[str, Any], name: str, phase: str, compact_contract: str | None = None) -> str:
    system = _schema_instructions(instructions, schema, compact_contract)
    # DeepSeek's official Chat Completions schema requires user-message content to be
    # a text string. OpenAI's Chat API also accepts content-part arrays, which are only
    # needed here for vision-capable compatible providers. Sending an OpenAI-style text
    # part array to DeepSeek can be rejected before inference, so keep its text adapter
    # deliberately provider-specific instead of treating every compatible API identically.
    if runtime.provider == "deepseek":
        user_content: Any = "\n\n".join(
            str(item.get("text", "")) for item in content if item.get("type") == "input_text" and str(item.get("text", "")).strip()
        )
        if any(item.get("type") == "input_image" for item in content):
            raise ProviderCallError(phase, message="DeepSeek text adapter does not accept image content; enable local OCR or use a vision-capable provider")
    else:
        user_content = _chat_content(content)
    response_format: dict[str, Any]
    if runtime.output_mode == "json_schema":
        response_format = {
            "type": "json_schema",
            "json_schema": {"name": name, "schema": schema, "strict": True},
        }
    else:
        response_format = {"type": "json_object"}

    kwargs: dict[str, Any] = {
        "model": runtime.model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
        "response_format": response_format,
        "max_tokens": runtime.max_output_tokens,
    }
    if runtime.reasoning_enabled:
        effort = runtime.reasoning_effort
        if runtime.provider == "deepseek":
            # DeepSeek Chat Completions documents low/high/max; map generic UI values.
            effort = "low" if effort == "low" else ("max" if effort == "max" else "high")
            kwargs["extra_body"] = {"thinking": {"type": "enabled"}}
        kwargs["reasoning_effort"] = effort
    elif runtime.provider == "deepseek":
        kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
    if runtime.streaming_enabled:
        text, _, _ = _chat_stream_text(client, phase=phase, kwargs=kwargs)
        return text
    try:
        response = client.chat.completions.create(**kwargs)
    except Exception as exc:
        raise_provider_error(exc, phase)
    choices = getattr(response, "choices", None) or []
    text = choices[0].message.content if choices else None
    if not text:
        raise ProviderCallError(phase, message="provider returned no chat completion text")
    return text

def generate_structured_json(runtime: RuntimeIntegration, client: Any, *, instructions: str, content: list[dict[str, Any]], schema: dict[str, Any], name: str = "super_scholar_research_profile", phase: str = "structured research analysis", compact_contract: str | None = None) -> str:
    if runtime.protocol == "chat_completions":
        return _chat_json(runtime, client, instructions=instructions, content=content, schema=schema, name=name, phase=phase, compact_contract=compact_contract)
    return _responses_json(runtime, client, instructions=instructions, content=content, schema=schema, name=name, phase=phase, compact_contract=compact_contract)


def _basic_text_call(runtime: RuntimeIntegration, client: Any) -> str:
    if runtime.protocol == "chat_completions":
        try:
            response = client.chat.completions.create(
                model=runtime.model,
                messages=[{"role": "user", "content": "Reply with exactly: SUPER_SCHOLAR_OK"}],
                max_tokens=32,
            )
        except Exception as exc:
            raise_provider_error(exc, "basic text connectivity test")
        choices = getattr(response, "choices", None) or []
        return (choices[0].message.content or "").strip() if choices else ""
    try:
        response = client.responses.create(
            model=runtime.model,
            input="Reply with exactly: SUPER_SCHOLAR_OK",
            max_output_tokens=32,
            store=False,
        )
    except Exception as exc:
        raise_provider_error(exc, "basic text connectivity test")
    return (getattr(response, "output_text", None) or "").strip()


def _streaming_probe(runtime: RuntimeIntegration, client: Any) -> dict[str, Any]:
    if runtime.protocol == "chat_completions":
        kwargs = {
            "model": runtime.model,
            "messages": [{"role": "user", "content": "Reply with exactly: STREAM_OK"}],
            "max_tokens": 48,
        }
        text, first_event_ms, events = _chat_stream_text(client, phase="streaming compatibility test", kwargs=kwargs)
    else:
        kwargs = {
            "model": runtime.model,
            "input": "Reply with exactly: STREAM_OK",
            "max_output_tokens": 48,
            "store": False,
        }
        text, first_event_ms, events = _responses_stream_text(client, phase="streaming compatibility test", kwargs=kwargs)
    return {"text": text, "firstEventMs": first_event_ms, "events": events}


def _tiny_image_data_url() -> str:
    image = Image.new("RGB", (96, 64), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((18, 14, 78, 50), fill=(38, 99, 235))
    out = io.BytesIO(); image.save(out, format="PNG")
    return "data:image/png;base64," + base64.b64encode(out.getvalue()).decode("ascii")


def _vision_call(runtime: RuntimeIntegration, client: Any) -> str:
    image_url = _tiny_image_data_url()
    if runtime.protocol == "chat_completions":
        try:
            response = client.chat.completions.create(
                model=runtime.model,
                messages=[{"role": "user", "content": [
                    {"type": "text", "text": "This is a connectivity test. Name the dominant rectangle color in one English word."},
                    {"type": "image_url", "image_url": {"url": image_url, "detail": "low"}},
                ]}],
                max_tokens=48,
            )
        except Exception as exc:
            raise_provider_error(exc, "vision compatibility test")
        choices = getattr(response, "choices", None) or []
        return (choices[0].message.content or "").strip() if choices else ""
    try:
        response = client.responses.create(
            model=runtime.model,
            input=[{"role": "user", "content": [
                {"type": "input_text", "text": "This is a connectivity test. Name the dominant rectangle color in one English word."},
                {"type": "input_image", "image_url": image_url, "detail": "low"},
            ]}],
            max_output_tokens=48,
            store=False,
        )
    except Exception as exc:
        raise_provider_error(exc, "vision compatibility test")
    return (getattr(response, "output_text", None) or "").strip()



def _tiny_pdf_buffer() -> io.BytesIO:
    import fitz

    doc = fitz.open()
    try:
        page = doc.new_page(width=420, height=240)
        page.insert_text((54, 72), "SUPER_SCHOLAR_FILE_TEST", fontsize=16)
        page.insert_text((54, 106), "This PDF is generated only for a provider compatibility test.", fontsize=9)
        data = doc.tobytes()
    finally:
        doc.close()
    buffer = io.BytesIO(data)
    buffer.name = "super-scholar-provider-test.pdf"
    return buffer


def _file_call(runtime: RuntimeIntegration, client: Any) -> str:
    if runtime.protocol != "responses":
        raise ProviderCallError("Files API compatibility test", message="direct PDF testing requires the Responses API protocol")
    uploaded_id: str | None = None
    try:
        upload_kwargs: dict[str, Any] = {"file": _tiny_pdf_buffer(), "purpose": "user_data"}
        # OpenAI documents expires_after for /v1/files. Custom compatible gateways often
        # implement only the core upload fields, so we do not require that extension there.
        if runtime.provider == "openai":
            upload_kwargs["expires_after"] = {"anchor": "created_at", "seconds": 3600}
        try:
            uploaded = client.files.create(**upload_kwargs)
        except Exception as exc:
            raise_provider_error(exc, "Files API upload compatibility test")
        uploaded_id = getattr(uploaded, "id", None)
        if not uploaded_id:
            raise ProviderCallError("Files API upload compatibility test", message="provider returned no file id")
        try:
            response = client.responses.create(
                model=runtime.model,
                input=[{"role": "user", "content": [
                    {"type": "input_file", "file_id": uploaded_id},
                    {"type": "input_text", "text": "Read the attached test PDF and reply with exactly: FILE_OK"},
                ]}],
                max_output_tokens=64,
                store=False,
            )
        except Exception as exc:
            raise_provider_error(exc, "input_file compatibility test")
        return (getattr(response, "output_text", None) or "").strip()
    finally:
        if uploaded_id:
            try:
                client.files.delete(uploaded_id)
            except Exception:
                pass


_PROBE_CCF_CODES = {"DS", "NW", "SC", "SE", "DB", "CT", "CG", "AI", "HI", "MX"}
_PROBE_FACT_CATEGORIES = {
    "research_problem", "core_idea", "topic", "method", "dataset", "model", "metric",
    "contribution", "research_question", "claimed_novelty", "gap", "stage_signal", "visual_observation",
}
_PROBE_CONFIDENCE = {"high", "medium", "low"}


def _validate_research_probe_payload(value: Any) -> None:
    """Mirror the real text-chunk contract closely enough for the settings probe.

    The previous probe only checked that a JSON object contained ``summary``. That allowed
    a gateway/model to show a green ResearchProbe while returning categories or confidence
    values that the real Pydantic contract would reject minutes later on a paid project.
    """
    if not isinstance(value, dict):
        raise ValueError("research probe output must be one JSON object")
    summary = value.get("summary")
    if not isinstance(summary, dict) or not isinstance(summary.get("text"), str) or not summary.get("text", "").strip():
        raise ValueError("research probe summary.text must be a non-empty string")
    refs = summary.get("evidence_ids")
    if not isinstance(refs, list) or "probe_ev" not in refs:
        raise ValueError("research probe summary must cite probe_ev")

    areas = value.get("area_candidates", [])
    if not isinstance(areas, list) or any(not isinstance(x, str) or x not in _PROBE_CCF_CODES for x in areas):
        raise ValueError("research probe area_candidates contains an unsupported CCF code")

    facts = value.get("facts", [])
    if not isinstance(facts, list):
        raise ValueError("research probe facts must be an array")
    for idx, fact in enumerate(facts):
        if not isinstance(fact, dict):
            raise ValueError(f"research probe facts[{idx}] must be an object")
        if fact.get("category") not in _PROBE_FACT_CATEGORIES:
            raise ValueError(f"research probe facts[{idx}].category is unsupported: {fact.get('category')!r}")
        if fact.get("confidence") not in _PROBE_CONFIDENCE:
            raise ValueError(f"research probe facts[{idx}].confidence is unsupported: {fact.get('confidence')!r}")
        if not isinstance(fact.get("text"), str) or not fact.get("text", "").strip():
            raise ValueError(f"research probe facts[{idx}].text must be non-empty")
        evidence_ids = fact.get("evidence_ids")
        if not isinstance(evidence_ids, list) or "probe_ev" not in evidence_ids:
            raise ValueError(f"research probe facts[{idx}] must cite probe_ev")

def test_provider(runtime: RuntimeIntegration) -> dict[str, Any]:
    started = datetime.now(timezone.utc)
    result: dict[str, Any] = {
        "ok": False,
        "provider": runtime.provider,
        "baseUrl": runtime.base_url,
        "model": runtime.model,
        "protocol": runtime.protocol,
        "testedAt": started.isoformat(),
        "checks": {},
    }
    if not runtime.ai_configured:
        result["checks"]["text"] = {"ok": False, "required": True, "message": "API key, Base URL or model is missing"}
        return result
    client = make_client(runtime)
    try:
        text = _basic_text_call(runtime, client)
        result["checks"]["text"] = {"ok": bool(text), "required": True, "message": text[:180] or "empty response"}
    except Exception as exc:
        result["checks"]["text"] = {"ok": False, "required": True, "message": str(exc)}
        return result

    if runtime.streaming_enabled:
        try:
            streamed = _streaming_probe(runtime, client)
            result["checks"]["streaming"] = {
                "ok": bool(streamed.get("text")),
                "required": True,
                "message": f"SSE OK · first event {streamed.get('firstEventMs')} ms · {streamed.get('events')} event(s) · {str(streamed.get('text') or '')[:100]}",
            }
        except Exception as exc:
            result["checks"]["streaming"] = {"ok": False, "required": True, "message": str(exc)}
            return result
    else:
        result["checks"]["streaming"] = {"ok": None, "required": False, "message": "disabled; long-running requests may time out behind CDNs or reverse proxies"}

    # Structured-output test deliberately uses a tiny schema and the configured output mode.
    schema = {
        "type": "object",
        "properties": {"status": {"type": "string"}},
        "required": ["status"],
        "additionalProperties": False,
    }
    try:
        raw = generate_structured_json(
            runtime, client,
            instructions="Return JSON for the connectivity test.",
            content=[{"type": "input_text", "text": "Set status to ok."}],
            schema=schema,
            name="super_scholar_connection_test",
            phase="structured-output compatibility test",
        )
        parsed = json.loads(raw)
        result["checks"]["structured"] = {"ok": isinstance(parsed, dict), "required": True, "message": raw[:220]}
    except Exception as exc:
        result["checks"]["structured"] = {"ok": False, "required": True, "message": str(exc)}

    # Research-probe uses the same text-first shape as the real V3.6 pipeline, but with
    # a tiny synthetic CS paragraph and a compact output contract. This catches gateways
    # that pass a one-word JSON test but fail on realistic structured research extraction.
    probe_schema = {
        "type": "object",
        "properties": {
            "summary": {
                "type": "object",
                "properties": {"text": {"type": "string"}, "evidence_ids": {"type": "array", "items": {"type": "string"}}},
                "required": ["text", "evidence_ids"],
                "additionalProperties": False,
            },
            "area_candidates": {"type": "array", "items": {"type": "string", "enum": sorted(_PROBE_CCF_CODES)}},
            "facts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "category": {"type": "string", "enum": sorted(_PROBE_FACT_CATEGORIES)}, "text": {"type": "string"},
                        "evidence_ids": {"type": "array", "items": {"type": "string"}},
                        "confidence": {"type": "string", "enum": sorted(_PROBE_CONFIDENCE)},
                    },
                    "required": ["category", "text", "evidence_ids", "confidence"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["summary", "area_candidates", "facts"],
        "additionalProperties": False,
    }
    probe_contract = '{"summary":{"text":"...","evidence_ids":["probe_ev"]},"area_candidates":["AI"],"facts":[{"category":"method","text":"...","evidence_ids":["probe_ev"],"confidence":"high"}]}'
    probe_text = "[probe_ev] A semantic-segmentation system uses a transformer encoder and evaluates mean IoU on a benchmark dataset. The project studies efficient model adaptation and reports an ablation experiment."
    try:
        probe_runtime = replace(runtime, reasoning_enabled=False, max_output_tokens=min(runtime.max_output_tokens, 420))
        raw = generate_structured_json(
            probe_runtime, client,
            instructions="Return compact JSON research facts grounded only in probe_ev.",
            content=[{"type": "input_text", "text": probe_text}],
            schema=probe_schema,
            name="super_scholar_research_probe",
            phase="research-pipeline compatibility probe",
            compact_contract=probe_contract,
        )
        parsed = json.loads(raw)
        _validate_research_probe_payload(parsed)
        result["checks"]["researchProbe"] = {"ok": True, "required": True, "message": raw[:260]}
    except Exception as exc:
        result["checks"]["researchProbe"] = {"ok": False, "required": True, "message": str(exc)}

    if runtime.supports_vision:
        try:
            vision = _vision_call(runtime, client)
            result["checks"]["vision"] = {"ok": bool(vision), "required": True, "message": vision[:180] or "empty response"}
        except Exception as exc:
            result["checks"]["vision"] = {"ok": False, "required": True, "message": str(exc)}
    else:
        result["checks"]["vision"] = {"ok": None, "required": False, "message": "disabled for this provider configuration"}

    if runtime.supports_files:
        try:
            file_result = _file_call(runtime, client)
            result["checks"]["files"] = {"ok": bool(file_result), "required": bool(runtime.send_direct_pdf), "message": file_result[:180] or "empty response"}
        except Exception as exc:
            result["checks"]["files"] = {"ok": False, "required": bool(runtime.send_direct_pdf), "message": str(exc)}
    else:
        result["checks"]["files"] = {"ok": None, "required": False, "message": "disabled for this provider configuration"}

    required_checks = [item for item in result["checks"].values() if item.get("required")]
    result["ok"] = bool(required_checks and all(item.get("ok") is True for item in required_checks))
    optional_failures = [name for name, item in result["checks"].items() if not item.get("required") and item.get("ok") is False]
    result["optionalFailures"] = optional_failures
    result["fullyCompatible"] = not optional_failures and all(item.get("ok") is not False for item in result["checks"].values())
    return result
