import json

import pytest
from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.messages import ModelRequest, UserPromptPart
from pydantic_ai.models.decision import ChoiceAnswer, DecisionResponse
from pydantic_ai.exceptions import ContentFilterError, UnexpectedModelBehavior
from pydantic_ai.usage import RequestUsage

from LLM_Complaint_Triage.pipeline.model_client import ModelClient
from LLM_Complaint_Triage.pipeline.contracts import ScreenDecision


def response(value, **kwargs):
    return ModelResponse(parts=[TextPart(value if isinstance(value, str) else json.dumps(value))],
                         usage=RequestUsage(input_tokens=100, output_tokens=30, output_reasoning_tokens=10),
                         finish_reason="stop", **kwargs)


@pytest.fixture
def record():
    return {"category": "FEES_AND_BILLING", "urgency": "low", "requires_human": False,
            "summary": "The consumer questions a fee.", "confidence_note": "The fee disclosures are not provided."}


@pytest.fixture
def client_factory():
    def make(values, **kwargs):
        queue = iter(values)
        calls = []
        delays = []

        async def request(model, messages, **params):
            calls.append((model, messages, params))
            value = next(queue)
            if isinstance(value, Exception):
                raise value
            return value if isinstance(value, ModelResponse) else response(value)

        async def sleep(delay):
            delays.append(delay)

        class FakeDecisionsModel:
            async def decide(self, decision_request, settings):
                result = await request("screen", [ModelRequest(parts=[UserPromptPart(json.dumps(decision_request.state))])])
                if result.finish_reason == "content_filter":
                    raise ContentFilterError("Test refusal")
                try:
                    decision = ScreenDecision.model_validate_json(result.parts[0].content)
                except Exception as exc:
                    raise UnexpectedModelBehavior("Invalid test decision") from exc
                probability = .95 if decision.decision == "block" else .05
                return DecisionResponse(answers={"injection": ChoiceAnswer(
                    choice=decision.decision, confidence=.95,
                    probabilities={"block": probability, "allow": 1 - probability},
                )}, model_name="gemini-decision-1", usage=result.usage)

        models = {"screen": FakeDecisionsModel(), "triage": "triage", "judge": "judge"}
        client = ModelClient(models,
                             request=request, sleep=sleep, jitter=lambda: 0, **kwargs)
        return client, calls, delays
    return make
