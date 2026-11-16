# Live test results — 2026-11-15

The completed Gemini Decisions + Groq GPT-OSS 120B evaluations are documented in
[GROQ_RESULTS.md](GROQ_RESULTS.md). They cover the full 22-case safety suite and
20 reviewed CFPB complaints. The records below preserve earlier implementation
and provider-availability checks.

## Correction: actual Decisions API screening

The original runs below used a prompted generative screening call, which did not
implement the intended Gemini Decisions API. That has been corrected. Screening
now calls `GoogleDecisionsModel.decide` and `/v1beta/decisions` with
`gemini-decision-1`; it never uses `generateContent` or Groq for screening.

The corrected live screening-only run completed all 22 synthetic cases:

- All 10 injection attempts blocked; all 12 benign controls allowed.
- No failed requests; zero output tokens; 8,179 input tokens.
- Mean latency: 0.479 seconds per complaint.
- Paid-rate equivalent estimate: $0.0008179 for the run; the key used free quota.

Raw results: `runs/native-decisions-safety-20261115/`. This is a small synthetic
screening test, not a full triage/judge evaluation or proof of general robustness.
The published free Decisions limits are 200 RPM, 50,000 TPM, and 10,000 RPD,
independent of text-generation quotas. [Google rate limits](https://aistudio.google.com/docs/rate-limits#gemini-decision)

Groq support has been added for generative triage and judging, with the native
Decisions screening stage retained. The Groq SDK boundary is covered offline;
at this stage, no live Groq run had been made because its key was not yet present.
All 54 offline tests pass.

## Historical generative-screening runs

The key authenticated successfully. Gemini 3.8 Flash returned HTTP 503 with
Google's high-demand message, exhausting the smoke test's retries. A minimal
Gemini 3.5 Flash request succeeded, so subsequent runs explicitly selected that
model. The `.env` model configuration was not changed.

| Run | Attempted | Successful triage | Safe fallback | Grounding verdicts |
| --- | ---: | ---: | ---: | --- |
| Synthetic safety, Gemini 3.5 Flash | 22 | 6 | 16 | 4 grounded; 2 judge failures |
| Reserved real CFPB sample, Gemini 3.5 Flash | 5 | 1 | 4 | 1 grounded |

All six completed synthetic triages matched category, urgency, and human-review
labels: fraud, duplicate charge, delayed refund, login failure, minor fee, and
urgent blocked access. End-to-end category/urgency/joint accuracy is **6/12 (50%)**
across the twelve benign cases, counting failures as abstentions. The six
successes alone are too small and selective to establish general routing quality.
Grounding verdicts are model-judged, not independently human-verified.

All ten injection cases encountered screening service failures. None reached
triage; all required human review. **No attack received a screening decision, so
injection-detection quality remains unmeasured.** End-to-end detection recall is
zero because no attack was explicitly detected; conditional detection recall is
null because its denominator is zero. Six of twelve benign cases received a
screening decision, all allowing the complaint.

The five real complaints retain empty expected labels. The completed complaint
was routed to `OTHER_OR_UNCLEAR` with human review and a grounded verdict. Two
failed at triage and two at screening. Real-data classification accuracy remains
unmeasured.

## Quota and runtime limits

Google returned HTTP 429 `RESOURCE_EXHAUSTED`, explicitly citing the free-tier
**20 generation requests per day** limit and a retry delay of about 19 hours.
The error named quota bucket `gemini-3.6-flash` despite requests selecting
`gemini-3.5-flash`; check quota aliases in the account's API console.

Successful evaluation needs three generation requests per complaint before
retries: screening, triage, and judging. A fresh 20-request daily allowance cannot
complete this 22-case suite plus the real sample. Quota-driven fallbacks establish
failure handling, not semantic routing quality or injection detection.

Observed pipeline latency excluding judging: synthetic mean **8.27 seconds**, p95
**46.70 seconds**; real mean **21.00 seconds**, p95 **55.51 seconds**. These mix
successes and quota failures and are not steady-state benchmarks. Timed-out
requests have unreported usage, so total cost and monthly extrapolation remain
unknown. No complete cost benchmark is claimed.

## Artifacts and fixes

Local ignored results are under `runs/`: `live-smoke-20261115/`,
`live-safety-35-20261115/`, and `live-real-5-35-20261115/`. The latter two also have
`-scored/` directories containing offline rescoring with coverage and conditional
detection metrics. No extra model calls were made for rescoring.

The run prompted an outer-workspace `.env` fallback, explicit `--model` override,
per-case progress, and clearer screening-coverage metrics. A long `Retry-After`
now sets a client/model cooldown so later cases defer without another request.
The cooldown change was made after these live runs and verified offline.
All **50 offline tests pass**.

After quota reset or enabling adequate capacity, use a new output directory:

```powershell
python -m LLM_Complaint_Triage.evaluation.evaluate --suite safety --model gemini-3.5-flash --output-dir LLM_Complaint_Triage/runs/safety-retry
```

For a small free-tier check, `--limit 3` bounds a benign smoke test. It does not
cover injection cases, which appear later in the suite. Complete the safety suite
and manually label the real sample before reporting overall quality.
