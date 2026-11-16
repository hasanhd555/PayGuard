"""Screen -> triage -> enforce escalation. No agent or graph orchestration."""

import re
import time

from pydantic import ValidationError

from .contracts import GroundingVerdict, ScreenDecision, TriageRecord, TriageResult
from .files import ROOT, checked_complaint, fingerprint
from .model_client import StageFailure

PROMPTS = ROOT / "prompts"
# Conservative English backstop, not a complete legal-intent detector. The prompt
# handles paraphrases; tests and evaluation expose false positives/negatives.
LEGAL_THREAT = re.compile(
    r"\b(?:I|we)\s+(?:will|intend to|plan to|am going to|are going to)\s+"
    r"(?:sue|file (?:a |an )?(?:lawsuit|suit|legal action))\b|"
    r"\b(?:my|our)\s+(?:lawyer|attorney)\s+(?:will|is going to)\s+"
    r"(?:sue|file|take legal action)\b", re.IGNORECASE,
)


def prompt_for(stage):
    prompt = (PROMPTS / f"{stage}.txt").read_text(encoding="utf-8")
    if stage == "triage":
        examples = (PROMPTS / "few_shot.json").read_text(encoding="utf-8")
        prompt += "\nTrusted illustrative examples (not the current complaint):\n" + examples
    return prompt


def fallback(reason):
    return TriageRecord(
        category="OTHER_OR_UNCLEAR", urgency="medium", requires_human=True,
        summary="Automated triage is unavailable; the complaint requires human review.",
        confidence_note=reason,
    )


def enforce_policy(record, complaint):
    reasons = []
    if record.category in {"FRAUD_AND_SECURITY", "OTHER_OR_UNCLEAR"}:
        reasons.append("category_requires_review")
    if record.urgency == "high":
        reasons.append("high_urgency")
    if LEGAL_THREAT.search("\n".join(v for v in complaint.model_dump().values() if v)):
        reasons.append("explicit_legal_threat")
    if reasons and not record.requires_human:
        return record.model_copy(update={"requires_human": True}), reasons
    return record, []


async def triage(complaint, client, complaint_id="single"):
    started = time.perf_counter()
    raw = complaint.model_dump() if hasattr(complaint, "model_dump") else complaint
    result = TriageResult(
        complaint_id=complaint_id, input_sha256=fingerprint(raw), status="invalid_input",
        triage=fallback("Input failed validation; no model was called."),
    )
    try:
        try:
            complaint = checked_complaint(complaint)
        except ValidationError:
            result.error = "invalid_input"
            return result
        result.input_sha256 = fingerprint(complaint.model_dump())
        payload = complaint.model_dump()
        try:
            decision, metrics = await client.structured("screen", prompt_for("screen"), payload, ScreenDecision)
            result.stages.append(metrics)
            result.screening = decision
        except StageFailure as exc:
            result.stages.append(exc.metrics)
            result.status = "screen_failed"
            result.error = exc.metrics.error
            result.triage = fallback("Injection screening failed; the complaint has not been automatically classified.")
            return result
        if decision.decision == "block":
            result.status = "blocked"
            result.triage = fallback("Screening detected possible embedded instructions; a human must review the original complaint.")
            return result
        try:
            record, metrics = await client.structured("triage", prompt_for("triage"), payload, TriageRecord)
            result.stages.append(metrics)
        except StageFailure as exc:
            result.stages.append(exc.metrics)
            result.status = "triage_failed"
            result.error = exc.metrics.error
            result.triage = fallback("The triage model did not return a valid result; a human must classify the complaint.")
            return result
        result.triage, result.policy_overrides = enforce_policy(record, complaint)
        result.status = "success"
        return result
    finally:
        result.latency_seconds = round(time.perf_counter() - started, 6)


async def judge_grounding(complaint, record, client):
    complaint = checked_complaint(complaint)
    fields = [v for v in complaint.model_dump().values() if v]

    def validate(verdict):
        if any(not any(excerpt in field for field in fields) for excerpt in verdict.evidence):
            raise ValueError("Evidence excerpts must be exact substrings of the original input")
        grounded = verdict.summary_grounded and verdict.confidence_grounded
        if grounded == bool(verdict.unsupported_claims):
            raise ValueError("Grounding flags and unsupported_claims are inconsistent")
        if grounded and not verdict.evidence:
            raise ValueError("A grounded verdict needs at least one input evidence excerpt")

    return await client.structured(
        "judge", prompt_for("judge"),
        {"complaint": complaint.model_dump(), "candidate": record.model_dump()},
        GroundingVerdict, validate=validate,
    )
