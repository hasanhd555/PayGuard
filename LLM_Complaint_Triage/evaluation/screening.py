"""Evaluate the actual Decisions endpoint independently of generative quotas."""

import argparse
import asyncio
import json
import sys
from dataclasses import replace
from pathlib import Path

from ..pipeline.contracts import ScreenDecision
from ..pipeline.files import ROOT, write_json
from ..pipeline.model_client import ConfigurationError, Settings, StageFailure, live_client, load_prices
from ..pipeline.triage import prompt_for
from .evaluate import load_cases
from .metrics import ratio


async def run(args):
    cases = load_cases("safety", None)
    if args.limit:
        cases = cases[:args.limit]
    if args.output_dir.exists():
        raise ValueError("Output directory exists; choose a new path")
    # Only Decisions is called. Do not require Groq credentials to screen inputs.
    settings = replace(Settings.from_env(), generation_provider="google")
    rows = []
    async with live_client(settings=settings, prices=load_prices(ROOT / "prices.json")) as client:
        args.output_dir.mkdir(parents=True)
        with (args.output_dir / "predictions.jsonl").open("x", encoding="utf-8") as handle:
            for case in cases:
                try:
                    decision, metrics = await client.structured(
                        "screen", prompt_for("screen"), case.inputs.model_dump(), ScreenDecision)
                    row = {"complaint_id": case.complaint_id, "expected_block": case.expected_block,
                           "decision": decision.model_dump(), "metrics": metrics.model_dump(), "status": "success"}
                except StageFailure as exc:
                    row = {"complaint_id": case.complaint_id, "expected_block": case.expected_block,
                           "decision": None, "metrics": exc.metrics.model_dump(), "status": "failed"}
                rows.append(row)
                write_json(handle, row)
                print(f"{case.complaint_id}: {row['decision']['decision'] if row['decision'] else 'failed'}", flush=True)
    attacks = [r for r in rows if r["expected_block"]]
    benign = [r for r in rows if r["expected_block"] is False]
    decided = [r for r in rows if r["decision"]]
    summary = {
        "model": settings.screen_model, "endpoint": "Google Decisions API /v1beta/decisions",
        "cases": len(rows), "decided": len(decided), "failures": len(rows) - len(decided),
        "correct": sum((r["decision"]["decision"] == "block") == r["expected_block"] for r in decided),
        "attacks": len(attacks), "attacks_decided": sum(r["decision"] is not None for r in attacks),
        "attacks_blocked": sum(r["decision"] is not None and r["decision"]["decision"] == "block" for r in attacks),
        "benign": len(benign), "benign_decided": sum(r["decision"] is not None for r in benign),
        "benign_blocked": sum(r["decision"] is not None and r["decision"]["decision"] == "block" for r in benign),
        "input_tokens": sum(r["metrics"]["input_tokens"] for r in rows),
        "output_tokens": sum(r["metrics"]["output_tokens"] for r in rows),
        "mean_latency_seconds": ratio(sum(r["metrics"]["latency_seconds"] for r in rows), len(rows)),
        "estimated_cost_usd": (sum(r["metrics"]["estimated_cost_usd"] for r in rows)
                               if all(r["metrics"]["estimated_cost_usd"] is not None for r in rows) else None),
    }
    (args.output_dir / "report.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "runs/decisions-screening")
    parser.add_argument("--limit", type=int)
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
