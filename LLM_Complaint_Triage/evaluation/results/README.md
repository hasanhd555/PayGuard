# Reviewable Part B evaluation artifacts

These are byte-for-byte copies of the completed 2026-11-15 Gemini Decisions +
Groq GPT-OSS 120B runs, selected from the local ignored `runs/` directory.
Model outputs, judge verdicts and metrics have not been edited. The accompanying
[results discussion](../GROQ_RESULTS.md) explains the errors and limitations.
The [artifact manifest](artifact_manifest.json) records file hashes for checking
that the copied evidence has not changed.

| Suite | Evidence | Reference cases |
|---|---|---|
| 20 reviewed real complaints | [Metrics](labeled/report.json), [predictions and judge verdicts](labeled/predictions.jsonl), [per-case checks](labeled/labeled_scores.jsonl), [run provenance](labeled/run_manifest.json) | [Reviewed labels and inputs](../labels.jsonl) |
| 22 synthetic safety cases: 12 benign and 10 attacks | [Metrics](safety/report.json), [predictions and judge verdicts](safety/predictions.jsonl), [per-case checks](safety/safety_scores.jsonl), [run provenance](safety/run_manifest.json) | [Synthetic cases and expected decisions](../safety.jsonl) |

Predictions contain generated triage records, screening decisions, stage metrics
and available grounding judgments. Original inputs remain in the reference case
files and are matched by complaint ID and input fingerprint. The run provenance
records dependency versions and prompt hashes; the labeled run also records the
reference-label file hash. The remaining temporary runs stay excluded from Git.

## Reproduce the scores offline

After installing the isolated Part B environment, run from the repository root:

```powershell
& ./LLM_Complaint_Triage/.venv/Scripts/python.exe -m LLM_Complaint_Triage.evaluation.evaluate --suite labeled --predictions LLM_Complaint_Triage/evaluation/results/labeled/predictions.jsonl --output-dir LLM_Complaint_Triage/runs/review-labeled

& ./LLM_Complaint_Triage/.venv/Scripts/python.exe -m LLM_Complaint_Triage.evaluation.evaluate --suite safety --predictions LLM_Complaint_Triage/evaluation/results/safety/predictions.jsonl --output-dir LLM_Complaint_Triage/runs/review-safety
```

No credentials or API calls are needed. Choose new output directories when
repeating the commands. This recomputes local scores and reuses the recorded
judge verdicts; it does not regenerate outputs or obtain a fresh judge opinion.
Report timestamps and the saved-prediction marker will differ from the original
live reports, while suite metrics should match with the same labels and code.

## Interpretation

The reviewed suite achieves 100% category/review accuracy and 80% urgency/joint
accuracy. Its majority-category and always-review baselines are already 95%,
and always-medium urgency scores 90%. It is a small, heavily out-of-scope sample,
not broad evidence of payments-routing quality.

All ten authored attacks were blocked, and all twelve benign controls were
allowed. Blocked attacks use safe fallbacks and are excluded from generated
category/urgency denominators. Do not pool synthetic and reviewed-suite quality
scores or interpret every fallback as a provider failure.

Seven of 19 completed real-case grounding verdicts flagged potential issues;
one judge call failed. The flags still need human adjudication and are not
human-verified hallucination labels. Incomplete retry usage keeps total cost
fields null; do not replace unknown usage with zero or infer a complete bill
from the partial token estimates.
