import asyncio
import json
from argparse import Namespace
from contextlib import asynccontextmanager

import pytest

from LLM_Complaint_Triage.evaluation.evaluate import load_cases, load_predictions, match_prediction, run, score_with_pydantic
from LLM_Complaint_Triage.evaluation.metrics import case_scores, summarize
from LLM_Complaint_Triage.evaluation.prepare_labels import select_cases
from LLM_Complaint_Triage.pipeline.contracts import Complaint, EvaluationCase, ExpectedLabels, TriageRecord, TriageResult
from LLM_Complaint_Triage.pipeline.files import ROOT, fingerprint, load_inputs, read_jsonl


def output(case, category="FEES_AND_BILLING", urgency="low", human=False, status="success"):
    return {"result": TriageResult(
        complaint_id=case.complaint_id, input_sha256=fingerprint(case.inputs.model_dump()), status=status,
        triage=TriageRecord(category=category, urgency=urgency, requires_human=human,
                            summary="The consumer reports a fee.", confidence_note="Details are unknown."),
    ).model_dump(), "grounding": None, "judge_metrics": None}


def case(identifier, category="FEES_AND_BILLING", human=False, source="human"):
    return EvaluationCase(complaint_id=identifier, inputs=Complaint(narrative="A fee was charged."),
                          expected=ExpectedLabels(category=category, urgency="low", requires_human=human),
                          label_source=source)


def test_twenty_reserved_inputs_are_reproducible():
    selected = select_cases()
    committed = [EvaluationCase.model_validate(row) for row in read_jsonl(ROOT / "evaluation/labels.jsonl")]
    assert [(c.complaint_id, c.inputs) for c in selected] == [(c.complaint_id, c.inputs) for c in committed]
    assert len(selected) == len({c.inputs.narrative for c in selected}) == 20
    assert all(all(v is None for v in c.expected.model_dump().values()) for c in selected)
    examples = json.loads((ROOT / "prompts/few_shot.json").read_text(encoding="utf-8"))
    assert not {e["input"]["narrative"] for e in examples} & {c.inputs.narrative for c in selected}


def test_sampling_deduplicates_narratives(tmp_path):
    path = tmp_path / "rows.jsonl"
    rows = [{"complaint_id": str(i), "narrative": text} for i, text in enumerate(["A", " A ", "B", "C"])]
    path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    assert len(select_cases(path, size=3)) == 3
    with pytest.raises(ValueError):
        select_cases(path, size=4)


def test_manual_labels_must_be_marked_reviewed(tmp_path):
    path = tmp_path / "labels.jsonl"
    path.write_text(case("1", source="pending_human").model_dump_json(), encoding="utf-8")
    with pytest.raises(ValueError, match="label_source=human"):
        load_cases("labeled", path)


def test_known_metrics_and_pending_denominators():
    first = case("1")
    second = case("2", category="FRAUD_AND_SECURITY", human=True)
    pending = EvaluationCase(complaint_id="3", inputs=Complaint(narrative="Unknown."))
    outputs = {"1": output(first), "2": output(second, human=False), "3": output(pending)}
    report = summarize([first, second, pending], outputs)
    assert report["accuracy"]["category"] == {"correct": 1, "n": 2, "accuracy": .5}
    assert report["category_macro_f1_supported_classes"] == pytest.approx(1 / 3)
    assert report["human_review"]["recall"] == 0
    assert report["human_review"]["precision"] is None
    assert report["pending_human_labels"] == 1
    assert "category_correct" not in case_scores(pending, outputs["3"])


def test_all_pending_accuracy_is_null():
    pending = EvaluationCase(complaint_id="p", inputs=Complaint(narrative="Something happened."))
    report = summarize([pending], {"p": output(pending)})
    assert report["accuracy"]["category"]["accuracy"] is None
    assert report["accuracy"]["category"]["n"] == 0
    assert report["grounding"]["model_judged_ungrounded_rate"] is None


def test_fallback_cannot_earn_category_credit_but_counts_for_escalation():
    item = case("1", category="OTHER_OR_UNCLEAR", human=True)
    scores = case_scores(item, output(item, category="OTHER_OR_UNCLEAR", human=True, status="triage_failed"))
    assert not scores["category_correct"] and scores["requires_human_correct"]
    assert not scores["joint_correct"]


def test_prediction_matching_uses_ids_and_hashes(tmp_path):
    a, b = case("a"), case("b")
    path = tmp_path / "predictions.jsonl"
    path.write_text("\n".join(json.dumps(output(c)) for c in [b, a]), encoding="utf-8")
    saved = load_predictions(path)
    assert match_prediction(a, saved)["result"]["complaint_id"] == "a"
    a.inputs.narrative = "Changed input"
    with pytest.raises(ValueError, match="Input changed"):
        match_prediction(a, saved)
    with pytest.raises(ValueError, match="Missing"):
        match_prediction(case("missing"), saved)


def test_pydantic_evals_runs_custom_checks():
    item = case("1")
    report = asyncio.run(score_with_pydantic([item], {"1": output(item)}))
    assert len(report.cases) == 1 and not report.failures
    assert report.cases[0].assertions["category_correct"].value is True


def test_offline_evaluation_cli_path(tmp_path):
    item = case("1")
    labels = tmp_path / "labels.jsonl"
    predictions = tmp_path / "predictions.jsonl"
    labels.write_text(item.model_dump_json(), encoding="utf-8")
    predictions.write_text(json.dumps(output(item)), encoding="utf-8")
    args = Namespace(suite="labeled", labels=labels, predictions=predictions, limit=None,
                     output_dir=tmp_path / "report", prices=None, no_judge=False)
    asyncio.run(run(args))
    report = json.loads((args.output_dir / "report.json").read_text())
    assert report["suites"]["labeled"]["accuracy"]["joint"]["accuracy"] == 1
    assert report["saved_predictions"] is True


def test_evaluation_flow_with_fake_model_calls(tmp_path, client_factory, record, monkeypatch):
    from LLM_Complaint_Triage.evaluation import evaluate

    first, second = case("1"), case("2")
    second.expected = ExpectedLabels(requires_human=True)
    second.expected_block = True
    labels = tmp_path / "labels.jsonl"
    labels.write_text("\n".join(c.model_dump_json() for c in [first, second]), encoding="utf-8")
    client, calls, _ = client_factory([
        {"decision": "allow", "reason": "Complaint"}, record,
        {"summary_grounded": True, "confidence_grounded": True, "unsupported_claims": [],
         "evidence": ["A fee was charged."], "explanation": "Supported"},
        {"decision": "block", "reason": "Instructions"},
    ])

    @asynccontextmanager
    async def fake_live_client(**kwargs):
        assert kwargs["settings"].screen_model == "gemini-decision-1"
        assert kwargs["settings"].triage_model == "explicit-test-model"
        assert kwargs["settings"].judge_model == "explicit-test-model"
        yield client

    monkeypatch.setattr(evaluate, "live_client", fake_live_client)
    args = Namespace(suite="labeled", labels=labels, predictions=None, limit=None,
                     output_dir=tmp_path / "report", prices=None, no_judge=False, model="explicit-test-model")
    asyncio.run(run(args))
    summary = json.loads((args.output_dir / "report.json").read_text())["suites"]["labeled"]
    assert [call[0] for call in calls] == ["screen", "triage", "judge", "screen"]
    assert summary["grounding"]["judged"] == 1
    assert summary["injection"]["detection_recall"] == 1
    assert summary["injection"]["blocked_reached_triage"] == 0
    assert (args.output_dir / "labeled_scores.jsonl").exists()


def test_grounding_failures_do_not_count_as_passes():
    item = case("1")
    bundle = output(item) | {"judge_status": "failed", "judge_error": "invalid_structured_output"}
    summary = summarize([item], {"1": bundle})
    assert summary["grounding"]["judge_failures"] == 1
    assert summary["grounding"]["model_judged_ungrounded_rate"] is None


def test_screen_failure_is_not_a_measured_attack_detection():
    attack = case("attack", human=True)
    attack.expected_block = True
    result = summarize([attack], {"attack": output(attack, human=True, status="screen_failed")})
    assert result["injection"]["attacks_decided"] == 0
    assert result["injection"]["decision_coverage"] == 0
    assert result["injection"]["detection_recall_decided_cases"] is None


def test_duplicate_ids_and_outcome_fields(tmp_path):
    path = tmp_path / "data.csv"
    path.write_text('Complaint ID,Consumer complaint narrative,Company response to consumer\n1,Refund missing,Closed\n', encoding="utf-8")
    assert "Closed" not in str(load_inputs(path)[0][1])
    path.write_text('Complaint ID,Consumer complaint narrative\n1,A\n1,B\n', encoding="utf-8")
    with pytest.raises(ValueError, match="unique"):
        load_inputs(path)
