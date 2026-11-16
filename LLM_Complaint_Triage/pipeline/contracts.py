"""Small, strict contracts at the model and file boundaries."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Category = Literal[
    "FRAUD_AND_SECURITY", "TRANSACTION_DISPUTES", "REFUNDS_AND_TRANSFERS",
    "ACCOUNT_ACCESS", "FEES_AND_BILLING", "SERVICE_AND_SUPPORT", "OTHER_OR_UNCLEAR",
]
Urgency = Literal["low", "medium", "high"]
Text = Annotated[str, Field(min_length=1)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)


class Complaint(StrictModel):
    narrative: Annotated[str, Field(min_length=1, max_length=50000)]
    product: str | None = None
    sub_product: str | None = None
    issue: str | None = None
    sub_issue: str | None = None

    @field_validator("product", "sub_product", "issue", "sub_issue")
    @classmethod
    def metadata_length(cls, value):
        if value is not None and len(value) > 2000:
            raise ValueError("metadata fields must be at most 2000 characters")
        return value or None


class TriageRecord(StrictModel):
    category: Category
    urgency: Urgency
    summary: Annotated[str, Field(min_length=1, max_length=1200)]
    requires_human: bool
    confidence_note: Annotated[str, Field(min_length=1, max_length=1200)]


class ScreenDecision(StrictModel):
    decision: Literal["allow", "block"]
    reason: Annotated[str, Field(min_length=1, max_length=800)]
    injection_probability: Annotated[float, Field(ge=0, le=1)] | None = None
    confidence: Annotated[float, Field(ge=0, le=1)] | None = None


class GroundingVerdict(StrictModel):
    summary_grounded: bool
    confidence_grounded: bool
    unsupported_claims: list[Text]
    evidence: list[Text]
    explanation: Text


class StageMetrics(StrictModel):
    stage: str
    model: str
    thinking_level: str
    prompt_sha256: str
    attempts: int = 0
    correction_retries: int = 0
    transport_retries: int = 0
    latency_seconds: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    thinking_tokens: int = 0
    cache_read_tokens: int = 0
    usage_complete: bool = True
    estimated_cost_usd: float | None = None
    price_date: str | None = None
    error: str | None = None


class TriageResult(StrictModel):
    complaint_id: str
    input_sha256: str
    status: Literal["success", "blocked", "screen_failed", "triage_failed", "invalid_input"]
    triage: TriageRecord
    screening: ScreenDecision | None = None
    policy_overrides: list[str] = Field(default_factory=list)
    stages: list[StageMetrics] = Field(default_factory=list)
    latency_seconds: float = 0.0
    error: str | None = None


class ExpectedLabels(StrictModel):
    category: Category | None = None
    urgency: Urgency | None = None
    requires_human: bool | None = None
    summary: str | None = None
    confidence_note: str | None = None


class EvaluationCase(StrictModel):
    complaint_id: str
    inputs: Complaint
    expected: ExpectedLabels = Field(default_factory=ExpectedLabels)
    expected_block: bool | None = None
    label_source: Literal["pending_human", "human", "synthetic"] = "pending_human"
    notes: str = ""
