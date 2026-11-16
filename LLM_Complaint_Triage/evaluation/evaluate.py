"""Run models once, then score explicitly with Pydantic Evals and local reports."""

import argparse
import asyncio
import json
import sys
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from pydantic_evals import Case, Dataset

from ..pipeline.contracts import EvaluationCase, GroundingVerdict, StageMetrics, TriageResult
from ..pipeline.files import DEFAULT_SAMPLE, ROOT, checked_complaint, fingerprint, load_inputs, read_jsonl, write_json
from ..pipeline.model_client import ConfigurationError, Settings, StageFailure, live_client, load_prices
from ..pipeline.triage import judge_grounding, triage
from .metrics import TriageChecks, summarize


def load_cases(suite, labels):
    if suite == "slice":
        return [EvaluationCase(complaint_id=i, inputs=checked_complaint(v)) for i, v in load_inputs(DEFAULT_SAMPLE)]
    path = labels if suite == "labeled" else ROOT / "evaluation/safety.jsonl"
    cases = [EvaluationCase.model_validate(row) for row in read_jsonl(path)]
    seen = set()
    for case in cases:
        if case.complaint_id in seen:
            raise ValueError(f"Duplicate case ID: {case.complaint_id}")
        seen.add(case.complaint_id)
        if case.label_source == "pending_human" and any(v is not None for v in case.expected.model_dump().values()):
            raise ValueError(f"{case.complaint_id}: complete review and set label_source=human before scoring labels")
    return cases


def load_predictions(path):
    predictions = {}
    for row in read_jsonl(path):
        result = TriageResult.model_validate(row.get("result", row))
        identifier = result.complaint_id
        if identifier in predictions:
            raise ValueError(f"Duplicate prediction ID: {identifier}")
        bundle = {"result": result.model_dump(), "grounding": None, "judge_metrics": None,
                  "judge_status": "not_requested", "judge_error": None}
        if "result" in row:
            if row.get("grounding"):
                bundle["grounding"] = GroundingVerdict.model_validate(row["grounding"]).model_dump()
            if row.get("judge_metrics"):
                bundle["judge_metrics"] = StageMetrics.model_validate(row["judge_metrics"]).model_dump()
            bundle["judge_status"] = row.get("judge_status", "not_requested")
            bundle["judge_error"] = row.get("judge_error")
        predictions[identifier] = bundle
    return predictions


def match_prediction(case, predictions):
    if case.complaint_id not in predictions:
        raise ValueError(f"Missing prediction for {case.complaint_id}")
    output = predictions[case.complaint_id]
    if output["result"]["input_sha256"] != fingerprint(case.inputs.model_dump()):
        raise ValueError(f"Input changed for prediction {case.complaint_id}")
    return output


async def score_with_pydantic(cases, outputs):
    dataset = Dataset(name="payguard-triage", cases=[Case(name=c.complaint_id, inputs=c) for c in cases],
                      evaluators=[TriageChecks()])

    def lookup(case):
        return match_prediction(case, outputs)

    return await dataset.evaluate(lookup, max_concurrency=1, progress=False)


@asynccontextmanager
async def optional_client(saved, prices, model=None, provider=None):
    if saved:
        yield None  # Scoring saved predictions is entirely offline.
    else:
        settings = Settings.from_env(provider=provider)
        if model:
            settings = replace(settings, triage_model=model, judge_model=model)
        async with live_client(settings=settings, prices=prices) as client:
            yield client


async def run(args):
    suites = ["labeled", "safety", "slice"] if args.suite == "all" else [args.suite]
    groups = {suite: load_cases(suite, args.labels) for suite in suites}
    if args.limit is not None:
        groups = {suite: cases[:args.limit] for suite, cases in groups.items()}
    saved = load_predictions(args.predictions) if args.predictions else None
    if saved is not None:
        for cases in groups.values():
            for case in cases:
                match_prediction(case, saved)  # Fail before writing reports if inputs mismatch.
    if args.output_dir.exists():
        raise ValueError("Output directory already exists; choose a new directory")
    prices = load_prices(args.prices)
    all_outputs = dict(saved or {})
    summaries = {}
    async with optional_client(args.predictions is not None, prices, getattr(args, "model", None),
                               getattr(args, "provider", None)) as client:
        args.output_dir.mkdir(parents=True)
        # A single append-only file contains each complaint once, even across suites.
        with (args.output_dir / "predictions.jsonl").open("x", encoding="utf-8") as handle:
            written = set()
            for suite, cases in groups.items():
                for case in cases:
                    if case.complaint_id not in all_outputs:
                        result = await triage(case.inputs, client, case.complaint_id)
                        output = {"result": result.model_dump(), "grounding": None, "judge_metrics": None,
                                  "judge_status": "not_requested", "judge_error": None}
                        if not args.no_judge and result.status == "success":
                            try:
                                verdict, metrics = await judge_grounding(case.inputs, result.triage, client)
                                output.update(grounding=verdict.model_dump(), judge_metrics=metrics.model_dump(),
                                              judge_status="success")
                            except StageFailure as exc:
                                output.update(judge_status="failed", judge_metrics=exc.metrics.model_dump(),
                                              judge_error=exc.metrics.error)
                        elif result.status != "success":
                            output["judge_status"] = "not_applicable_fallback"
                        all_outputs[case.complaint_id] = output
                    output = match_prediction(case, all_outputs)
                    if case.complaint_id not in written:
                        write_json(handle, output)
                        written.add(case.complaint_id)
                    print(f"{suite}: {case.complaint_id}: {output['result']['status']}; "
                          f"judge={output['judge_status']}", flush=True)
                if not cases:
                    raise ValueError(f"Empty suite: {suite}")
                report = await score_with_pydantic(cases, all_outputs)
                if report.failures or report.report_evaluator_failures or any(c.evaluator_failures for c in report.cases):
                    raise RuntimeError("Pydantic Evals reported scoring failures")
                with (args.output_dir / f"{suite}_scores.jsonl").open("x", encoding="utf-8") as scores:
                    for case_report in report.cases:
                        write_json(scores, {"complaint_id": case_report.name,
                                            "checks": {k: v.value for k, v in case_report.assertions.items()}})
                summaries[suite] = summarize(cases, all_outputs)
                print(f"{suite}: {len(cases)} cases; {summaries[suite]['accuracy']}")
    summary = {"created_at": datetime.now(timezone.utc).isoformat(), "suites": summaries,
               "prices": prices, "saved_predictions": bool(args.predictions),
               "notes": ["Suites overlap; do not add their costs or pool their quality scores.",
                         "Null scores mean no eligible labels/verdicts; null cost means unavailable pricing/usage.",
                         "Grounding is model-judged, not human-verified. Failures and fallbacks are reported separately."]}
    (args.output_dir / "report.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"Reports saved to {args.output_dir}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=["labeled", "safety", "slice", "all"], default="labeled")
    parser.add_argument("--labels", type=Path, default=ROOT / "evaluation/labels.jsonl")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "runs/evaluation")
    parser.add_argument("--predictions", type=Path, help="Score saved outputs offline; never re-call models")
    parser.add_argument("--limit", type=int, help="Apply independently to each selected suite")
    parser.add_argument("--no-judge", action="store_true", help="Skip grounding calls in live evaluations")
    parser.add_argument("--provider", choices=["google", "groq"], help="Provider for triage and judging; screening always uses Gemini Decisions")
    parser.add_argument("--model", help="Explicitly override the text model for triage and judging")
    parser.add_argument("--prices", type=Path, default=ROOT / "prices.json")
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")
    try:
        asyncio.run(run(args))
    except (ConfigurationError, ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
