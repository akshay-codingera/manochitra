import pytest

from app.core.concepts import CONCEPT_BY_ID
from app.services.gemini_client import ModelResponse
from app.services.generation_pipeline import GenerationPipeline
from conftest import make_valid_svg


class FakeGeminiClient:
    model = "gemini-3.5-flash-lite"
    api_key = "not-used-in-tests"

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    async def generate_svg(self, prompt):
        self.calls += 1
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


@pytest.mark.asyncio
async def test_pipeline_uses_one_validation_repair_then_passes():
    concept = CONCEPT_BY_ID["pythagoras"]
    invalid = '<svg xmlns="http://www.w3.org/2000/svg"><title>Missing viewBox</title></svg>'
    valid = make_valid_svg(concept)
    client = FakeGeminiClient([
        ModelResponse(invalid, 100, 20, "gemini-3.5-flash-lite"),
        ModelResponse(valid, 120, 30, "gemini-3.5-flash-lite"),
    ])
    result = await GenerationPipeline(client=client).generate("pythagoras")

    assert client.calls == 2
    assert result["status"] == "PASS"
    assert result["retries"]["validation_retries"] == 1
    assert result["retries"]["total_retries"] == 1
    assert result["usage"] == {
        "input_tokens": 220,
        "output_tokens": 50,
        "thinking_tokens": 0,
        "metadata_available": True,
    }
    assert len(result["attempt_history"]) == 2
    assert result['trace_id']
    assert {'prompt_build_ms', 'model_request_with_retries_ms', 'validation_ms', 'svg_validation_ms', 'concept_structure_ms'}.issubset(result['timings_ms'])
    assert set(result['checks']) == {'valid_svg', 'within_viewbox', 'title_and_labels', 'has_animation', 'scientific_terms', 'concept_structure'}


@pytest.mark.asyncio
async def test_pipeline_does_not_repair_a_valid_first_response():
    concept = CONCEPT_BY_ID["pythagoras"]
    client = FakeGeminiClient([ModelResponse(make_valid_svg(concept), 100, 20, "gemini-3.5-flash-lite")])
    result = await GenerationPipeline(client=client).generate("pythagoras")

    assert client.calls == 1
    assert result["status"] == "PASS"
    assert result["retries"]["validation_retries"] == 0


@pytest.mark.asyncio
async def test_pipeline_rejects_unknown_concept():
    pipeline = GenerationPipeline(client=FakeGeminiClient([]))
    with pytest.raises(ValueError):
        await pipeline.generate("not-a-real-concept")


@pytest.mark.asyncio
async def test_pipeline_records_unrecoverable_initial_api_error(monkeypatch):
    from app.services.gemini_client import GeminiAPIError

    class UnusedClient:
        model = 'gemini-3.5-flash-lite'
        api_key = 'configured'

    async def fail_with_retries(_operation):
        error = GeminiAPIError(503, 'temporarily unavailable')
        error.retry_count = 3
        raise error

    monkeypatch.setattr('app.services.generation_pipeline.call_with_transient_retries', fail_with_retries)
    result = await GenerationPipeline(client=UnusedClient()).generate('circle')
    assert result['status'] == 'ERROR'
    assert result['retries']['api_retries'] == 3
    assert result['checks']['valid_svg']['passed'] is False
    assert result['usage']['metadata_available'] is False
    assert result['cost']['estimated_cost_usd'] is None
    assert '503' in result['last_error']


@pytest.mark.asyncio
async def test_pipeline_keeps_fail_when_single_repair_still_fails(pythagoras_concept):
    invalid = '<svg xmlns="http://www.w3.org/2000/svg"><title>Missing bounds</title></svg>'
    client = FakeGeminiClient([
        ModelResponse(invalid, 10, 5, 'gemini-3.5-flash-lite'),
        ModelResponse(invalid, 12, 6, 'gemini-3.5-flash-lite'),
    ])
    result = await GenerationPipeline(client=client).generate('pythagoras')
    assert client.calls == 2
    assert result['status'] == 'FAIL'
    assert result['retries']['validation_retries'] == 1
    assert len(result['attempt_history']) == 2
    assert 'single permitted repair' in result['last_error']
