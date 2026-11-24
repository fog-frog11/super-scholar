import json
from types import SimpleNamespace

import pytest

from app.config import Settings
from app.models import Project
from app.services.integration_settings import RuntimeIntegration
from app.services.research_ai import ResearchPipelineError, analyze_with_provider
from app.services.research_documents import EvidenceItem
from app.services.research_provider import ProviderCallError


def _runtime(**overrides):
    data = dict(
        provider="custom",
        base_url="https://example.invalid/v1",
        api_key="test-key",
        model="compatible-model",
        protocol="responses",
        output_mode="json_object",
        reasoning_effort="high",
        reasoning_enabled=True,
        streaming_enabled=True,
        transport_profile="auto",
        supports_vision=False,
        supports_files=False,
        send_direct_pdf=False,
        max_text_chars=220_000,
        max_visual_assets=8,
        max_pdf_files=0,
        max_output_tokens=12_000,
        chunk_text_chars=8_000,
        chunk_output_tokens=1_800,
        synthesis_max_chars=32_000,
        max_provider_calls=5,
        visuals_per_chunk=0,
        request_timeout_seconds=180,
        tesseract_cmd="",
        ocr_languages="eng",
        ocr_min_native_text_chars=80,
        source="ui",
    )
    data.update(overrides)
    return RuntimeIntegration(**data)


def _chunk_payload(evidence_id="ev1") -> str:
    return json.dumps({
        "summary": {"text": "Supported by uploaded evidence.", "evidence_ids": [evidence_id]},
        "area_candidates": ["AI"],
        "facts": [
            {"category": "research_problem", "text": "Supported problem.", "evidence_ids": [evidence_id], "confidence": "high"},
            {"category": "core_idea", "text": "Supported core idea.", "evidence_ids": [evidence_id], "confidence": "high"},
            {"category": "topic", "text": "Computer Vision", "evidence_ids": [evidence_id], "confidence": "high"},
            {"category": "method", "text": "Transformer", "evidence_ids": [evidence_id], "confidence": "high"},
            {"category": "contribution", "text": "A supported contribution.", "evidence_ids": [evidence_id], "confidence": "high"},
            {"category": "stage_signal", "text": "Experiments are present.", "evidence_ids": [evidence_id], "confidence": "medium"},
        ],
    })


def _final_payload(evidence_id="ev1") -> str:
    grounded = {"text": "Supported by uploaded evidence.", "evidence_ids": [evidence_id]}
    item = {"text": "A supported contribution.", "evidence_ids": [evidence_id], "confidence": "high"}
    return json.dumps({
        "summary": grounded,
        "research_problem": grounded,
        "core_idea": grounded,
        "primary_area": "AI",
        "secondary_areas": [],
        "area_rationale": grounded,
        "topics": ["Computer Vision"],
        "methods": ["Transformer"],
        "datasets": [],
        "models": [],
        "metrics": [],
        "contributions": [item],
        "research_questions": [item],
        "claimed_novelty": [item],
        "gaps": [],
        "visual_observations": [],
        "stage": "early",
        "stage_rationale": grounded,
    })


def test_research_understanding_stops_after_first_provider_554(monkeypatch):
    monkeypatch.setattr("app.services.research_ai.make_client", lambda runtime: object())
    monkeypatch.setattr("app.services.research_ai.sdk_available", lambda: True)
    calls = []

    def fail_once(*args, **kwargs):
        calls.append(kwargs.get("phase"))
        raise ProviderCallError("text research chunk 1/4", status_code=554, message="gateway rejected request")

    monkeypatch.setattr("app.services.research_ai.generate_structured_json", fail_once)
    evidence = [EvidenceItem("ev1", "m1", "document_text", "paper text", "semantic segmentation evidence " * 5000, {})]

    with pytest.raises(ResearchPipelineError) as exc_info:
        analyze_with_provider(
            Project(id="p1", name="Test research", brief=""), [], evidence, [], {}, Settings(),
            _runtime(), "2026-08-28T00:00:00+00:00",
        )

    assert len(calls) == 1
    diagnostics = exc_info.value.diagnostics
    assert diagnostics["callTrace"][0]["statusCode"] == 554
    assert diagnostics["pipeline"]["sdkRetries"] == 0
    assert "stopped immediately" in str(exc_info.value)


def test_research_understanding_uses_small_chunks_then_one_synthesis(monkeypatch):
    monkeypatch.setattr("app.services.research_ai.make_client", lambda runtime: object())
    monkeypatch.setattr("app.services.research_ai.sdk_available", lambda: True)
    calls = []

    def respond(*args, **kwargs):
        phase = kwargs.get("phase", "")
        calls.append((phase, kwargs["content"][0]["text"], kwargs["runtime"] if "runtime" in kwargs else None))
        if phase == "final research synthesis":
            return _final_payload()
        return _chunk_payload()

    # The real function receives runtime/client positionally, so accept positional args cleanly.
    def respond2(runtime, client, **kwargs):
        phase = kwargs.get("phase", "")
        calls.append((phase, len(kwargs["content"][0]["text"]), runtime.reasoning_enabled, runtime.max_output_tokens))
        return _final_payload() if phase == "final research synthesis" else _chunk_payload()

    monkeypatch.setattr("app.services.research_ai.generate_structured_json", respond2)
    evidence = [EvidenceItem("ev1", "m1", "document_text", "paper text", "A" * 23_000, {"page": 1})]
    progress = []
    result = analyze_with_provider(
        Project(id="p1", name="Test research", brief=""), [], evidence, [], {}, Settings(),
        _runtime(chunk_text_chars=8_000, max_provider_calls=5), "2026-08-28T00:00:00+00:00",
        on_attempt=lambda i, total, name: progress.append((i, total, name)),
    )

    assert len(calls) == 5  # four bounded chunks + one synthesis, exactly the configured hard budget
    assert all(reasoning is False for _, _, reasoning, _ in calls[:-1])
    assert calls[-1][2] is False  # custom Auto resolves to Edge-safe; final reasoning is disabled for TTFE safety
    assert result["providerCallsUsed"] == 5
    assert result["requestPlan"]["sdkRetries"] == 0
    assert result["requestPlan"]["plannedChunkCalls"] == 4
    # Character sampling is intentionally bounded by the provider-call budget, but it
    # must not be presented as document/page coverage.  This one-page source is fully
    # represented even though only part of its raw character stream is transmitted.
    assert result["requestPlan"]["pageCoverageRatio"] == 1.0
    assert result["requestPlan"]["evidenceCoverageRatio"] == 1.0
    assert result["requestPlan"]["characterSamplingRatio"] < 1.0
    assert progress[-1][2] == "synthesis"


class _Event:
    def __init__(self, typ, *, delta=None, response=None):
        self.type = typ
        self.delta = delta
        self.response = response


class _ProviderTestResponses:
    def create(self, **kwargs):
        if kwargs.get("stream"):
            input_value = kwargs.get("input")
            if isinstance(input_value, str):
                text = "STREAM_OK"
            else:
                content = (input_value or [{}])[0].get("content", [])
                if any(item.get("type") == "input_image" for item in content if isinstance(item, dict)):
                    text = "blue"
                else:
                    joined = " ".join(str(item.get("text", "")) for item in content if isinstance(item, dict))
                    if "probe_ev" in joined:
                        text = '{"summary":{"text":"probe summary","evidence_ids":["probe_ev"]},"area_candidates":["AI"],"facts":[]}'
                    else:
                        text = '{"status":"ok"}'
            response = SimpleNamespace(output_text=text, output=[])
            return iter([
                _Event("response.created"),
                _Event("response.output_text.delta", delta=text),
                _Event("response.completed", response=response),
            ])
        if isinstance(kwargs.get("input"), str):
            return SimpleNamespace(output_text="SUPER_SCHOLAR_OK")
        content = (kwargs.get("input") or [{}])[0].get("content", [])
        if any(item.get("type") == "input_image" for item in content if isinstance(item, dict)):
            return SimpleNamespace(output_text="blue")
        joined = " ".join(str(item.get("text", "")) for item in content if isinstance(item, dict))
        if "probe_ev" in joined:
            return SimpleNamespace(output_text='{"summary":{"text":"probe summary","evidence_ids":["probe_ev"]},"area_candidates":["AI"],"facts":[]}')
        return SimpleNamespace(output_text='{"status":"ok"}')


class _ProviderTestFiles:
    def create(self, **kwargs):
        raise ProviderCallError("Files API upload compatibility test", status_code=404, message="files endpoint unavailable")

    def delete(self, file_id):
        return None


class _ProviderTestClient:
    def __init__(self):
        self.responses = _ProviderTestResponses()
        self.files = _ProviderTestFiles()


def test_files_failure_is_optional_when_direct_pdf_is_disabled(monkeypatch):
    from app.services.research_provider import test_provider

    monkeypatch.setattr("app.services.research_provider.make_client", lambda runtime: _ProviderTestClient())
    runtime = _runtime(
        supports_vision=True, supports_files=True, send_direct_pdf=False,
        max_text_chars=50_000, max_visual_assets=2, max_output_tokens=4_000,
    )
    result = test_provider(runtime)
    assert result["checks"]["files"]["ok"] is False
    assert result["checks"]["files"]["required"] is False
    assert result["ok"] is True
    assert result["optionalFailures"] == ["files"]


def test_research_probe_rejects_enum_values_that_real_pipeline_would_reject(monkeypatch):
    from app.services.research_provider import test_provider

    class Responses(_ProviderTestResponses):
        def create(self, **kwargs):
            if kwargs.get("stream"):
                input_value = kwargs.get("input")
                if isinstance(input_value, str):
                    text = "STREAM_OK"
                else:
                    content = (input_value or [{}])[0].get("content", [])
                    joined = " ".join(str(item.get("text", "")) for item in content if isinstance(item, dict))
                    if "probe_ev" in joined:
                        text = json.dumps({
                            "summary": {"text": "probe", "evidence_ids": ["probe_ev"]},
                            "area_candidates": ["AI"],
                            "facts": [{"category": "result", "text": "bad enum", "evidence_ids": ["probe_ev"], "confidence": "high"}],
                        })
                    else:
                        text = '{"status":"ok"}'
                response = SimpleNamespace(output_text=text, output=[])
                return iter([
                    _Event("response.created"),
                    _Event("response.output_text.delta", delta=text),
                    _Event("response.completed", response=response),
                ])
            return super().create(**kwargs)

    client = _ProviderTestClient()
    client.responses = Responses()
    monkeypatch.setattr("app.services.research_provider.make_client", lambda runtime: client)
    runtime = _runtime(supports_vision=False, supports_files=False)
    result = test_provider(runtime)
    assert result["checks"]["researchProbe"]["ok"] is False
    assert "category is unsupported" in result["checks"]["researchProbe"]["message"]
    assert result["ok"] is False

def test_openai_sdk_retries_are_disabled(monkeypatch):
    import app.services.research_provider as provider_module

    captured = {}

    class FakeOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(provider_module, "OpenAI", FakeOpenAI)
    provider_module.make_client(_runtime(request_timeout_seconds=123))
    assert captured["max_retries"] == 0
    assert captured["timeout"] == 123.0


def test_responses_structured_output_uses_sse_when_enabled(monkeypatch):
    from app.services.research_provider import generate_structured_json

    class Responses:
        def __init__(self):
            self.kwargs = None
        def create(self, **kwargs):
            self.kwargs = kwargs
            response = SimpleNamespace(output_text='{"status":"ok"}', output=[])
            return iter([
                _Event("response.created"),
                _Event("response.output_text.delta", delta='{"status":"ok"}'),
                _Event("response.completed", response=response),
            ])
    responses = Responses()
    client = SimpleNamespace(responses=responses)
    raw = generate_structured_json(
        _runtime(streaming_enabled=True), client,
        instructions="Return JSON", content=[{"type":"input_text","text":"test"}],
        schema={"type":"object","properties":{"status":{"type":"string"}},"required":["status"]},
        phase="test stream",
    )
    assert json.loads(raw)["status"] == "ok"
    assert responses.kwargs["stream"] is True


def test_responses_json_schema_requests_strict_adherence_for_custom_gateway():
    from app.services.research_provider import generate_structured_json

    class Responses:
        def __init__(self):
            self.kwargs = None
        def create(self, **kwargs):
            self.kwargs = kwargs
            return SimpleNamespace(output_text='{"status":"ok"}', output=[])

    responses = Responses()
    client = SimpleNamespace(responses=responses)
    raw = generate_structured_json(
        _runtime(streaming_enabled=False, output_mode="json_schema"), client,
        instructions="Return JSON", content=[{"type":"input_text","text":"test"}],
        schema={"type":"object","properties":{"status":{"type":"string"}},"required":["status"],"additionalProperties":False},
        name="strict_test", phase="strict response schema test",
    )
    assert json.loads(raw)["status"] == "ok"
    assert responses.kwargs["text"]["format"]["type"] == "json_schema"
    assert responses.kwargs["text"]["format"]["strict"] is True


def test_stream_must_reach_terminal_event():
    from app.services.research_provider import generate_structured_json

    class Responses:
        def create(self, **kwargs):
            return iter([_Event("response.created"), _Event("response.output_text.delta", delta='{"status":"ok"}')])
    client = SimpleNamespace(responses=Responses())
    with pytest.raises(ProviderCallError, match="response.completed"):
        generate_structured_json(
            _runtime(streaming_enabled=True), client,
            instructions="Return JSON", content=[{"type":"input_text","text":"test"}],
            schema={"type":"object","properties":{"status":{"type":"string"}},"required":["status"]},
            phase="test stream",
        )


def test_text_stage_never_mixes_images_and_visuals_are_one_request_each(monkeypatch, tmp_path):
    from PIL import Image
    from app.services.research_documents import VisualArtifact

    monkeypatch.setattr("app.services.research_ai.make_client", lambda runtime: object())
    monkeypatch.setattr("app.services.research_ai.sdk_available", lambda: True)
    image_path = tmp_path / "figure.png"
    Image.new("RGB", (120, 80), "blue").save(image_path)
    artifact = VisualArtifact("art1", "m1", "figure", "Figure 1", "image/png", str(image_path), 120, 80, 1, "test")
    calls = []

    def respond(runtime, client, **kwargs):
        phase = kwargs.get("phase", "")
        types = [x.get("type") for x in kwargs["content"]]
        calls.append((phase, types))
        if phase.startswith("visual research asset"):
            return json.dumps({"facts": [{"category": "visual_observation", "text": "A blue diagram is visible.", "evidence_ids": ["art1"], "confidence": "high"}]})
        if phase == "final research synthesis":
            return _final_payload()
        return _chunk_payload()

    monkeypatch.setattr("app.services.research_ai.generate_structured_json", respond)
    result = analyze_with_provider(
        Project(id="p1", name="Test research", brief=""), [],
        [EvidenceItem("ev1", "m1", "document_text", "paper", "semantic segmentation " * 900, {"page": 1})],
        [artifact], {}, Settings(),
        _runtime(supports_vision=True, max_visual_assets=1, max_provider_calls=5),
        "2026-08-28T00:00:00+00:00",
    )
    text_calls = [types for phase, types in calls if phase.startswith("text research chunk")]
    visual_calls = [types for phase, types in calls if phase.startswith("visual research asset")]
    assert text_calls and all("input_image" not in types for types in text_calls)
    assert visual_calls == [["input_text", "input_image"]]
    assert result["visualAssetCount"] == 1
    assert result["requestPlan"]["visualsAreSeparateCalls"] is True


def test_final_synthesis_failure_preserves_paid_chunk_results(monkeypatch):
    monkeypatch.setattr("app.services.research_ai.make_client", lambda runtime: object())
    monkeypatch.setattr("app.services.research_ai.sdk_available", lambda: True)
    calls = []

    def respond(runtime, client, **kwargs):
        phase = kwargs.get("phase", "")
        calls.append(phase)
        if phase == "final research synthesis":
            raise ProviderCallError(phase, status_code=554, message="edge timeout")
        return _chunk_payload()

    monkeypatch.setattr("app.services.research_ai.generate_structured_json", respond)
    result = analyze_with_provider(
        Project(id="p1", name="Test research", brief=""), [],
        [EvidenceItem("ev1", "m1", "document_text", "paper", "method experiment result " * 700, {"page": 1})],
        [], {}, Settings(), _runtime(max_provider_calls=4), "2026-08-28T00:00:00+00:00",
    )
    assert result["synthesisFallback"] is True
    assert result["profile"]["sourceMode"] == "ai_extracted_partial"
    assert result["providerCallsUsed"] == len(calls)
    assert result["analysisWarnings"]


def test_invalid_provider_json_is_salvaged_without_retry(monkeypatch):
    monkeypatch.setattr("app.services.research_ai.make_client", lambda runtime: object())
    monkeypatch.setattr("app.services.research_ai.sdk_available", lambda: True)
    calls = []

    def respond(runtime, client, **kwargs):
        phase = kwargs.get("phase", "")
        calls.append(phase)
        if phase == "final research synthesis":
            return _final_payload()
        return "not-json-at-all"

    monkeypatch.setattr("app.services.research_ai.generate_structured_json", respond)
    result = analyze_with_provider(
        Project(id="p1", name="Test research", brief=""), [],
        [EvidenceItem("ev1", "m1", "document_text", "paper", "short research evidence " * 200, {})],
        [], {}, Settings(), _runtime(max_provider_calls=3), "2026-08-28T00:00:00+00:00",
    )
    trace = result["callTrace"][0]
    assert trace["phase"].startswith("text research chunk")
    assert trace["status"] == "warning"
    assert trace["errorKind"] == "local_output_validation"
    assert trace["rawOutputChars"] == len("not-json-at-all")
    assert trace["responseTail"] == "not-json-at-all"
    assert result["profile"]
    assert result["analysisWarnings"]
    assert len(calls) == result["providerCallsUsed"]


def test_text_chunk_salvages_valid_facts_and_drops_bad_enum_values():
    from app.services.research_ai import _parse_text_chunk

    raw = json.dumps({
        "summary": {"text": "Grounded summary", "evidence_ids": ["ev1"]},
        "area_candidates": ["AI", "HEALTH", "DS"],
        "facts": [
            {"category": "method", "text": "Transformer adaptation", "evidence_ids": ["ev1"], "confidence": "high"},
            {"category": "result", "text": "Unsupported category", "evidence_ids": ["ev1"], "confidence": "high"},
            {"category": "metric", "text": "mIoU", "evidence_ids": ["ev1"], "confidence": "very_high"},
            {"category": "dataset", "text": "Cityscapes", "evidence_ids": ["other"], "confidence": "medium"},
        ],
    })
    parsed, warnings = _parse_text_chunk(raw, {"ev1"}, "ev1", "fallback evidence")
    assert parsed["areaCandidates"] == ["AI", "DS"]
    assert parsed["facts"] == [{
        "category": "method", "text": "Transformer adaptation", "evidenceIds": ["ev1"], "confidence": "high",
    }]
    assert any("HEALTH" in warning for warning in warnings)
    assert any("facts[1]" in warning for warning in warnings)
    assert any("facts[2]" in warning for warning in warnings)
    assert any("facts[3]" in warning for warning in warnings)


def test_responses_extraction_explicitly_disables_reasoning_when_runtime_disabled():
    from app.services.research_provider import generate_structured_json

    class Responses:
        def __init__(self):
            self.kwargs = None
        def create(self, **kwargs):
            self.kwargs = kwargs
            response = SimpleNamespace(output_text='{"status":"ok"}', output=[])
            return iter([
                _Event("response.created"),
                _Event("response.output_text.delta", delta='{"status":"ok"}'),
                _Event("response.completed", response=response),
            ])

    responses = Responses()
    client = SimpleNamespace(responses=responses)
    raw = generate_structured_json(
        _runtime(streaming_enabled=True, reasoning_enabled=False), client,
        instructions="Return JSON", content=[{"type":"input_text","text":"test"}],
        schema={"type":"object","properties":{"status":{"type":"string"}},"required":["status"]},
        phase="test no reasoning",
    )
    assert json.loads(raw)["status"] == "ok"
    assert responses.kwargs["reasoning"] == {"effort": "none"}


def test_deepseek_chat_stream_collects_content_and_finishes():
    from app.services.research_provider import generate_structured_json

    class Choice:
        def __init__(self, content=None, finish_reason=None, reasoning_content=None):
            self.delta = SimpleNamespace(content=content, reasoning_content=reasoning_content)
            self.finish_reason = finish_reason

    class ChatCompletions:
        def __init__(self):
            self.kwargs = None
        def create(self, **kwargs):
            self.kwargs = kwargs
            return iter([
                SimpleNamespace(choices=[Choice(reasoning_content="thinking...")]),
                SimpleNamespace(choices=[Choice(content='{"status":')]),
                SimpleNamespace(choices=[Choice(content='"ok"}')]),
                SimpleNamespace(choices=[Choice(finish_reason="stop")]),
            ])

    chat = SimpleNamespace(completions=ChatCompletions())
    client = SimpleNamespace(chat=chat)
    runtime = _runtime(
        provider="deepseek", protocol="chat_completions", output_mode="json_object",
        model="deepseek-v4-pro", reasoning_enabled=False, streaming_enabled=True,
    )
    raw = generate_structured_json(
        runtime, client,
        instructions="Return JSON", content=[{"type":"input_text","text":"test"}],
        schema={"type":"object","properties":{"status":{"type":"string"}},"required":["status"]},
        phase="deepseek chat stream",
    )
    assert json.loads(raw)["status"] == "ok"
    kwargs = chat.completions.kwargs
    assert kwargs["stream"] is True
    assert kwargs["response_format"] == {"type": "json_object"}
    assert kwargs["extra_body"] == {"thinking": {"type": "disabled"}}


def test_chat_stream_length_is_not_accepted_as_complete_json():
    from app.services.research_provider import generate_structured_json

    class Choice:
        def __init__(self, content=None, finish_reason=None):
            self.delta = SimpleNamespace(content=content)
            self.finish_reason = finish_reason

    class ChatCompletions:
        def create(self, **kwargs):
            return iter([
                SimpleNamespace(choices=[Choice(content='{"status":"')]),
                SimpleNamespace(choices=[Choice(finish_reason="length")]),
            ])

    client = SimpleNamespace(chat=SimpleNamespace(completions=ChatCompletions()))
    runtime = _runtime(provider="deepseek", protocol="chat_completions", output_mode="json_object", reasoning_enabled=False)
    with pytest.raises(ProviderCallError, match="finish_reason=length"):
        generate_structured_json(
            runtime, client,
            instructions="Return JSON", content=[{"type":"input_text","text":"test"}],
            schema={"type":"object","properties":{"status":{"type":"string"}},"required":["status"]},
            phase="deepseek truncated stream",
        )


def test_deepseek_chat_json_sends_plain_string_user_content():
    from app.services.research_provider import generate_structured_json

    captured = {}

    class Choice:
        finish_reason = "stop"
        class message:
            content = '{"status":"ok"}'

    class ChatCompletions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return type("Response", (), {"choices": [Choice()]})()

    class Client:
        chat = type("Chat", (), {"completions": ChatCompletions()})()

    runtime = _runtime(
        provider="deepseek",
        protocol="chat_completions",
        output_mode="json_object",
        model="deepseek-v4-pro",
        reasoning_enabled=False,
        streaming_enabled=False,
    )
    raw = generate_structured_json(
        runtime,
        Client(),
        instructions="Return JSON.",
        content=[{"type": "input_text", "text": "[ev_1] first"}, {"type": "input_text", "text": "[ev_2] second"}],
        schema={"type": "object", "properties": {"status": {"type": "string"}}},
        compact_contract='{"status":"ok"}',
        phase="deepseek plain text adapter test",
    )
    assert raw == '{"status":"ok"}'
    user_message = captured["messages"][1]
    assert isinstance(user_message["content"], str)
    assert "[ev_1] first" in user_message["content"]
    assert "[ev_2] second" in user_message["content"]
    assert captured["extra_body"] == {"thinking": {"type": "disabled"}}
