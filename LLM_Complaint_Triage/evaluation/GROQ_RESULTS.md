# Gemini Decisions + Groq GPT-OSS 120B evaluation

Runs completed on 2026-11-15 with native `gemini-decision-1` screening and
`openai/gpt-oss-120b` for triage and judging. Prompts and reference labels were
unchanged during the runs. Model outputs were not edited.

| Metric | Synthetic safety suite | Reviewed CFPB sample |
| --- | ---: | ---: |
| Cases | 22: 12 benign, 10 attacks | 20 |
| Valid triage records | 12/12 allowed complaints | 20/20 |
| Category accuracy | 12/12 (100%) | 20/20 (100%) |
| Urgency accuracy | 11/12 (91.7%) | 16/20 (80%) |
| Human-review accuracy | 22/22 (100%) | 20/20 (100%) |
| Joint category/urgency/review accuracy | 11/12 (91.7%) | 16/20 (80%) |
| Model-judged ungrounded output | 1/12 (8.3%) | 7/19 (36.8%) |
| Judge failures | 0 | 1 |

All ten injection attempts were blocked before triage. No benign safety case
was blocked. All screening and triage calls ultimately succeeded; blocked
attacks use the human-review fallback and are excluded from category/urgency
denominators. The JSON `fallback_rate` includes intentional attack blocks and
must not be read as a service-failure rate.

## Interpretation and error review

The real sample contains 19 `OTHER_OR_UNCLEAR` cases and one `FEES_AND_BILLING`
case. Always predicting the majority category would score **95%**. Thus 100%
accuracy does not establish broad payments routing quality; five categories
have no real-sample support. The synthetic suite covers all seven categories,
but has only one to three benign cases per category.

An always-medium urgency baseline scores **18/20 (90%)**, exceeding the model's
80%. Urgency is the clearest classification weakness:

| Complaint ID | Expected | Predicted |
| --- | --- | --- |
| 16621847 | low | medium |
| 15664282 | medium | low |
| 16811317 | medium | low |
| 16004084 | medium | low |

The synthetic mismatch is `safety-credit-deletion`: expected medium, predicted
low. All five mismatched cases still required human review. No real complaint
is labeled high urgency; that behavior is tested by two synthetic cases only.

All seven real-sample grounding flags concern confidence notes. One also flags
the summary for `16252002`: it describes Bridgecrest as collecting for a loan
servicer, while the narrative says it collects for an SPV. This changes the
stated relationship and warrants manual review.

The confidence-note flags need adjudication. For example, `15836815` was flagged
for applying the out-of-scope policy even though the judge prompt explicitly
permits that policy. Other flags dispute statements that supporting records are
missing. The 36.8% model-judged flag rate is **not** a human-verified hallucination
rate. Audit passes too: summary paraphrases may introduce causal connections
the judge overlooks.

Judge call `16531065` failed validation after two correction retries. It is
excluded from the 19-verdict grounding denominator; its triage record remains
available. No prompt changes or selective reruns were made to improve scores.

## Latency, retries, and cost

| Measurement | Safety suite | Reviewed sample |
| --- | ---: | ---: |
| Screening mean | 0.63 s | 0.79 s |
| Pipeline mean, excluding judge | 7.84 s | 17.28 s |
| Pipeline p95, excluding judge | 19.87 s | 27.08 s |
| Judge mean, including retries | 7.16 s | 13.88 s |
| Transport retries, triage + judge | 31 | 50 |
| Judge correction retries | 1 | 11 |

Safety latency includes ten fast attack blocks. Groq token throttling caused
backoff, so these are free-tier operational timings rather than model-compute
latency or production benchmarks. Triage needed no output correction retries.

Some retry attempts lack reported usage; aggregate costs and monthly estimates
therefore remain null in the JSON reports. Applying recorded paid prices to the
reviewed sample's **reported response tokens only** gives about **$0.0126** for
screening plus triage and **$0.0248** for judging. These are partial-usage
estimates, not actual invoices or complete cost benchmarks.

## Artifacts and reproduction

The submission includes [reviewable artifacts](results/README.md) for the labeled
and safety evaluations: original JSON reports, saved predictions/judge verdicts,
per-case checks and run provenance. They can be rescored offline without API
keys. These curated copies are outside the ignored run directories; outputs
have not been edited and incomplete costs remain null.

Each local, ignored directory contains `report.json`, `predictions.jsonl`, and
per-case `*_scores.jsonl`:

- `runs/groq-120b-smoke-20261115/`
- `runs/groq-120b-safety-20261115/`
- `runs/groq-120b-labeled-20261115/`

The live evaluations used Groq GPT-OSS 120B for triage and judging. To generate
new live outputs using your own credentials, choose fresh output directories:

```powershell
python -m LLM_Complaint_Triage.evaluation.evaluate --suite safety --provider groq --model openai/gpt-oss-120b --output-dir LLM_Complaint_Triage/runs/safety-repeat
python -m LLM_Complaint_Triage.evaluation.evaluate --suite labeled --provider groq --model openai/gpt-oss-120b --output-dir LLM_Complaint_Triage/runs/labeled-repeat
```

Use `--predictions` to rescore saved outputs offline. If these results guide
model or rubric changes, evaluate the new version on a fresh holdout.
