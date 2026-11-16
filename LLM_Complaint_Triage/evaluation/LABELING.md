# Manual labeling and grounding audit

Edit `labels.jsonl` before viewing predictions. Each JSONL line contains the
original five input fields, complaint ID, an `expected` object with null values,
`label_source`, and optional `notes`. The manifest identifies the fixed sample.

1. Read the narrative and metadata. Treat allegations as reported facts, not
   verified misconduct. Never use company responses as evidence for the label.
2. Fill `expected.category`, `expected.urgency`, and `expected.requires_human`.
   Keep null for genuinely unadjudicated labels; do not invent ground truth.
3. Optionally write a reference summary and confidence note. These guide human
   review; they are not compared by string equality to generated prose.
4. Explain ambiguity in `notes`, resolve disagreements, and set `label_source`
   to `human` only after review. Never change IDs or input text to match a model.
5. Run evaluation. Keep labels fixed across prompt comparisons. Once labels
   influence prompt changes, reserve new complaints for final evaluation.

## Category rubric

| Category | Route and decision rule |
| --- | --- |
| FRAUD_AND_SECURITY | Fraud & Risk: alleged unauthorized activity, takeover or identity theft involving payments, cards, wallets or bank accounts. Takes precedence over ordinary disputes. |
| TRANSACTION_DISPUTES | Payments & Disputes: duplicate/incorrect charges or disputed purchases without fraud indicators. |
| REFUNDS_AND_TRANSFERS | Payment Operations: missing/pending transfers, approved refunds, reversals or settlement. A fee refund request belongs to billing. |
| ACCOUNT_ACCESS | Account Support: login, verification, restrictions, or closure issues. |
| FEES_AND_BILLING | Billing & Finance: fees, interest, subscriptions and pricing disputes. |
| SERVICE_AND_SUPPORT | Customer Experience: support and communication issues when there is no more specific payment/account problem. |
| OTHER_OR_UNCLEAR | General Triage: standalone credit reporting, collections, mortgages, loans, unsupported products, or materially ambiguous inputs. |

Scope is determined by the underlying problem; do not route a standalone credit
report allegation to payments fraud merely because it mentions identity theft.
Narrative-only payments cases are supported when the product is clear from the
text. For multiple issues choose the primary underlying problem; flag material
ambiguity for human review rather than force a confident route.

## Urgency and escalation

| Urgency | Evidence needed |
| --- | --- |
| high | Ongoing unauthorized activity, immediate threats, imminent serious harm, or essential funds blocked with an immediate stated consequence. |
| medium | Unresolved loss, delayed transfers, restrictions, repeated disputes or a time-sensitive issue without evidence of immediate serious harm. |
| low | Routine explanation, minor fee or ordinary service question with no escalation signals. |

`requires_human=true` for fraud allegations, explicit legal threats, high urgency,
unsupported products, and material ambiguity. A legal citation alone is not a
threat. An ordinary request to escalate to customer support is not an injection.
False means suitable for routine routing; no case is automatically closed.

## Grounding audit

Review the saved generated summary, confidence note, judge flags, unsupported
claims and excerpts against the original input. Check amounts, dates, actors,
actions, and whether an allegation was incorrectly presented as verified. Check
that unknown facts are described as unknown rather than fabricated. Avoid
penalizing valid paraphrases or a justified out-of-scope explanation.

Record human disagreements with the judge separately from reference triage
labels, citing the offending claim and input evidence. Audit some judge passes
as well as failures; model agreement is not independent human verification.
Report the audited sample size and denominator when presenting a human grounding
rate. The CLI's grounding rate is explicitly **model-judged**.

Synthetic injection cases test instruction override, not ordinary consumer
commands such as "refund this fee". A blocked attack must not reach triage.
Measure benign false blocks too: screening everything would otherwise appear
perfect on attack detection. No sensitivity or false-positive claim is valid
until live outputs have been produced and evaluated.
