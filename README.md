# PayGuard: decisions and findings

PayGuard needs to reduce fraud losses and triage complaints without creating an
unmanageable review queue or mishandling sensitive cases. These prototypes test
those decisions: whether a more flexible fraud model earns its complexity, and
whether structured LLM triage is reliable enough to assist a support team.

**Fraud:** random forest is the provisional choice for human-review flagging at
a score of **0.324504778 or above**, selected using validation cost. Its advantage
over logistic regression was small. **Complaint triage:** the pipeline can
produce structured records, but the measured urgency and grounding weaknesses
do not support unattended use.

Installation, dataset descriptions, acquisition instructions and commands are in
[Setup and datasets](SETUP_AND_DATA.md).

The [production design memo](Production_Design_Memo.md) proposes an asynchronous,
in-country rollout of complaint triage, with human review, monitoring and phased
automation.
The [AWS architecture example](AWS_Architecture_Example.md) illustrates the
corresponding service choices and event, notification and reporting flows.

## Part A: fraud detection

The useful outcome for PayGuard is a review queue that identifies fraud without
overwhelming analysts or unnecessarily interrupting legitimate customers.
Training a classifier is only one part of that decision. The evaluation must
show whether its scores remain useful on later transactions, how much fraud is
missed, and how much review work is created. The prototype therefore separates
learning a score from choosing the action that score should trigger.

### Learning from the past and assessing later transactions

An approximately **60/20/20 chronological split** gives each partition a distinct
role. The earliest transactions fit the models and any learned preprocessing.
The next period selects the model and threshold. The final period assesses
those frozen choices. The proportions are by transaction count, not elapsed
duration; transactions sharing a timestamp stay in the same partition.

This follows the deployment question: can a model trained on earlier activity
identify fraud in later activity? A random stratified split would make class
proportions convenient, but could place later fraud patterns in training while
evaluating earlier, related transactions. That can make the experiment easier
than deployment. Chronological partitions also preserve differences in fraud
prevalence instead of forcing future periods to resemble the training sample.

The realized partitions contain **342 training, 57 validation and 74 test frauds**.
Their prevalence is approximately 0.201%, 0.100% and 0.130%, respectively.
Those differences are a reason to report each period's support and operating
results, rather than assume a stable fraud rate. The split is a practical
holdout design for a feasibility build, not evidence of performance across
multiple independent periods. No rolling-window validation was performed.

Leakage prevention applies to the whole pipeline. The logistic regression
scaler learns its means and standard deviations only from training data.
Class weights are also computed from training labels. Validation and test
transactions retain their observed class distribution; balancing those periods
would make precision, review volume and cost estimates unrepresentative.
Neither model is fitted again on training plus validation after its threshold
is chosen, because refitting could change the scores to which that threshold
applies. Once test results are seen, a later model or policy revision should
be assessed on a fresh holdout.

Both models use the same transaction inputs. Elapsed time determines order but
is excluded as a predictor: seconds since this recording began would be a
fragile shortcut for a later deployment. Additional PCA and feature selection
are deferred because the existing numerical inputs are manageable and more
learned transformations would add decisions without first establishing a
baseline. Extreme amounts are retained; automatically treating unusual values
as noise could remove the fraud signal.

The imbalance is addressed through balanced class weights while retaining
legitimate training examples. Undersampling could discard useful normal
patterns, and synthetic oversampling would add assumptions about plausible
fraud transactions. Class weighting is a simpler initial choice, although it
does not guarantee better detection and can affect probability calibration.
It is a training choice; the action threshold still needs separate selection.

A chronological split does not remove every threat to validity. Exact full-row
duplicates are removed to avoid giving repeated records extra influence on
fitting and reported counts. This is an assumption, since transaction IDs are
unavailable. Equal model features at different times remain: the audit finds
561 validation and 1,720 test rows whose feature vector appeared in an earlier
partition. These matches do not prove leakage, but they also prevent a claim
that every evaluation observation represents a new behavioral pattern.

Without card or merchant identifiers, related transactions and fraud episodes
cannot be isolated with an entity-level holdout. The supplied PCA transformation
cannot be audited for its own fitting boundary. Historical labels are available
for this experiment, but a live system would have to wait for investigations
or chargebacks to mature before training on them. These are unresolved limits
on the evidence, not issues that a high score can dismiss.

### Measuring detection and the work it creates

Fraud represents roughly **0.17% of the original data**. Predicting every
transaction as legitimate would therefore produce approximately **99.83%
accuracy while detecting no fraud at all**. In the final test period, the same
policy misses all 74 frauds. Accuracy would describe the majority class well
while saying almost nothing about the purpose of the system.

The primary measure of score-ranking quality is **average precision (AP)**.
It summarizes precision across increases in recall: as the system reaches
further down its ranked queue to find more fraud, how much legitimate traffic
does it bring along? AP weights precision by the recall gained at successive
score cutoffs. It is reported as average precision, rather than conflated with
trapezoidal area under a precision-recall curve.

The constant-score baseline has test AP of **0.0013**, equal to that period's
fraud prevalence, compared with **0.7466 for logistic regression and 0.8062 for
random forest**. Both models concentrate fraud near the top of their rankings.
An AP of 0.8062 does not mean 80.62% accuracy, precision or recall at the deployed
threshold. AP also depends on prevalence, so its change between chronological
periods should not be read as a pure change in model quality.

**Precision and recall describe the chosen action.** Precision is the fraction
of flagged transactions that are actually fraudulent; recall is the fraction
of all fraud transactions flagged. A high-precision queue can still miss
substantial fraud, while high recall can be achieved by flagging an impractical
amount of legitimate traffic. Alert count and false-positive count therefore
accompany these ratios. F1 is not the selection objective because its symmetric
precision-recall trade-off does not represent the assumed business costs.

ROC AUC is retained as secondary context. It measures how often fraud ranks
above a legitimate transaction, but a small false-positive rate can still
represent substantial work when legitimate transactions dominate. For example,
a hypothetical 0.1% false-positive rate on the test period's legitimate traffic
would mean roughly 57 false alarms. With 56 true alerts, precision would be
about 50%. This is an illustration of the denominator effect, not an additional
measured operating point.

The actual test results show why relying on one summary would be misleading:
logistic regression has higher ROC AUC (**0.9819 versus 0.9346**), while the
forest has higher AP and fewer false alarms at the frozen operating points.
The business decision needs the relevant portion of the precision-recall
trade-off, not simply the largest headline AUC.

AP diagnoses ranking quality; **modeled error cost selects the operating
policy**. That distinction is deliberate. A model with slightly better overall
ranking need not make the better decisions at the threshold PayGuard can use.

### What the additional model complexity buys

Logistic regression is a substantive baseline: it can learn a useful weighted
combination of the inputs, trains quickly, and uses regularization to limit
overfitting. Standardizing its inputs makes optimization and regularization
less sensitive to feature units. Its limitation is an additive decision
function in log-odds; interactions and nonlinear boundaries are not explicitly
constructed in this version. Anonymized inputs also limit business
interpretation, even when the model itself is simple.

Random forest tests whether nonlinear splits and feature interactions improve
the queue. Combining randomized trees can represent patterns the linear
baseline cannot, at a cost in model size, fitting work and explanatory
simplicity. Tree depth and leaf size are constrained to limit complexity.
Feature scaling is unnecessary for this model. Both models use fixed initial
configurations and the same data, features, validation period and cost
assumptions, making the comparison about model behavior rather than a larger
tuning budget.

Validation produced the following results at each model's own cost-minimizing
threshold:

| Model | Validation AP | Precision | Recall | False alarms | Missed fraud | Modeled cost |
|---|---:|---:|---:|---:|---:|---:|
| Logistic regression | 0.7727 | 63.77% | 77.19% | 25 | 13 | 1,425 |
| Random forest | 0.7692 | 95.56% | 75.44% | 2 | 14 | 1,410 |

Logistic regression has slightly higher AP and catches one additional fraud.
The forest generates 23 fewer false alarms. Under the declared costs, avoiding
those false alarms saves 115 units while missing the additional fraud costs
100, giving the forest a **15-unit net advantage**. This is the reason it was
selected; calling it simply more accurate would obscure the actual trade-off.

The margin is only about 1% of validation cost and rests on 57 fraud examples.
There is no established statistical significance or robust dominance. The
simpler model remains a credible choice if the costs, review action or
representative evaluation period change. Equal validation costs would select
logistic regression.

The final test comparison uses the thresholds fixed before test scoring:

| Model | Threshold | Test AP | Precision | Recall | Fraud flagged | False alarms | Missed fraud | Alerts |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Logistic regression | 0.999619042 | 0.7466 | 72.37% | 74.32% | 55 | 21 | 19 | 76 |
| Random forest | 0.324504778 | 0.8062 | 87.50% | 75.68% | 56 | 8 | 18 | 64 |

In this period, the forest flags one additional fraud, generates 13 fewer false
alarms and creates 12 fewer reviews. Its modeled cost is 1,840 versus 2,005 for
logistic regression and 7,400 for never flagging a transaction. These are
comparisons under an assumed loss function, not measured financial savings:
flagging a fraud does not establish that a reviewer can prevent or recover
the loss.

The fitting cost also differs: 108.53 seconds for the forest versus 1.39 seconds
for logistic regression on the recorded machine. Both are practical for this
offline experiment, but the result does not justify adding complexity
indefinitely. The forest is a provisional operating choice with a promising
test result, not a universally superior fraud model.

### From scores to a review policy

A **false positive** is a legitimate transaction incorrectly flagged as
potential fraud and sent for review. A **false negative** is a fraudulent
transaction that falls below the threshold and receives no fraud alert.
Lowering the threshold generally catches more fraud but creates more false
alarms; raising it reduces alerts but risks missing more fraud.

The proposed operating rule is to **request human review when the random-forest
score is at least 0.324504778**. This threshold was chosen using validation data
to minimize:

`modeled cost = 5 x false positives + 100 x false negatives`

Each model receives its own threshold. Comparing both at 0.5 would impose the
same numeric cutoff on different score scales without establishing equivalent
risk or review workload. The search considers all distinct validation scores,
keeps tied scores together, and includes a no-alert policy. If costs tie,
fewer alerts are preferred.

The costs encode a business assumption: **a missed fraud is twenty times as
costly as an unnecessary alert**. Five and 100 are hypothetical units, not
currency amounts or estimates supplied by PayGuard. A false positive uses
analyst time and may cause customer verification, payment delay, support
contacts or abandonment if review interrupts payment. Its cost depends on the
intervention; a background review and an automatic decline do not have the
same consequences.

A false negative can leave PayGuard exposed to unrecovered fraud, investigation
and dispute handling, and damage to customer trust. The loss depends on
transaction value, recovery prospects and when action is possible. Treating
every missed fraud as the same 100-unit loss is therefore a simplification.
The objective also omits the cost of reviewing true positives and does not
measure investigator effectiveness. It supports a transparent prototype
comparison, not a fully specified economic optimum.

Scores are used empirically to rank transactions. They are **not calibrated
fraud probabilities**: a forest score of 0.3245 does not establish 32.45% fraud
risk, and the logistic threshold near 1 does not establish near-certainty.
Class weighting and the different estimators affect score scales. The many
digits record the observed cutoff for reproducibility; they do not indicate
that the economically optimal policy is known to that precision.

At the selected test threshold, 64 reviews identify 56 frauds and 8 legitimate
transactions, while 18 frauds remain unflagged. This is useful queue
concentration but incomplete coverage: approximately one quarter of fraud is
still missed. Any deployment discussion must consider whether that residual
exposure is acceptable, rather than treating 87.5% precision as sufficient.

Cost sensitivity exposes the competing priorities. At an FN/FP ratio of 50,
validation selects a lower forest threshold of 0.06645. Fraud flagged increases
from 43 to 47, but false alarms increase from 2 to 106 and reviews rise from
45 to 153. Recall improves from 75.44% to 82.46%; precision drops from 95.56%
to 30.72%. The extra detection is bought with substantially more work. This
alternative remains a validation scenario, not a test-tuned recommendation.

Before choosing a production threshold, PayGuard would need to supply expected
net losses, recovery rates, the cost and effect of review, customer-friction
costs and review capacity. A capacity limit could rule out the cost-minimizing
threshold. If fraud prevalence or score distributions change, the queue's
precision and volume can change even with the same cutoff. The threshold
therefore requires monitoring and controlled reassessment on later labeled
data; it is not a permanent model property. Automatic declines would need
their own intervention policy and evaluation.

### Real-time inference

The dataset supplies precomputed PCA components. A fixed PCA transformation can
be applied quickly, but its original inputs and fitted transformation must be
available to reproduce these features during a live payment. Scoring the
supplied components alone does not establish an end-to-end feature pipeline.

Features must be available before the decision: transaction amount is available
immediately, and recent card activity may be available through maintained
history. A future chargeback or later investigation outcome is unavailable and
cannot be a predictor. Training must reproduce these availability rules, and
serving must reuse the fitted preprocessing and feature definitions.

The model must also fit the payment latency budget. Logistic regression is
cheaper to score; the forest's extra detection must justify its tree traversal
and operational complexity. The forest's measured warm single-row p95 was
32.10 ms, including preprocessing but excluding feature retrieval, networking
and concurrent load. Both models need end-to-end benchmarking before that
trade-off can be settled.

Training can remain offline, using sufficiently mature fraud labels because
investigations and chargebacks arrive later. Our chronological split does not
simulate that delay, so it may overstate what an operational training process
could learn at the same point in time.

### Further validation

Only 74 frauds support the final recall estimate: one fraud changes recall by
about 1.35 percentage points, and related fraud episodes may further reduce
the effective independence of the evidence. Two historical days cannot
represent changing attacker behavior, seasonality or PayGuard's customers.
The next useful step is a longer, representative chronological evaluation
with mature labels and realistic review outcomes. Repeated future windows
would test whether the small validation advantage and useful test queue
persist before more tuning or deployment is justified.

[Full measured results and sensitivity analysis](Fraud_Detection_Prototype/results/RESULTS.md).

## Part B: complaint triage

The objective is to produce a useful routing decision and a faithful short
account of a complaint, while retaining human control over sensitive or
uncertain cases. A well-formed response is necessary for downstream processing,
but does not establish that the route, urgency or summary is correct. The
prototype therefore treats **component reliability, decision quality and
factual grounding as separate questions**, with different checks for each.

### A bounded component with explicit failure behavior

A fixed sequence of screening, triage and local escalation rules is sufficient
for this task. Direct model requests keep those decisions visible without
adding an agent workflow or a conversational UI. In the recorded evaluation,
Gemini Decisions screened inputs and Groq GPT-OSS 120B generated triage records.
A separate evaluation call judged grounding; that judge is not a required
stage of ordinary batch triage.

The seven-category taxonomy represents routing destinations rather than every
possible complaint topic. A single primary route keeps ownership clear, while
`OTHER_OR_UNCLEAR` allows the system to abstain when the product is unsupported
or the underlying issue is ambiguous. Explicit precedence rules distinguish
unauthorized activity from an ordinary purchase dispute and route the underlying
payment problem before a secondary complaint about support. The uncertainty
note explains missing evidence; it is not a calibrated confidence score.

Generation requests a native structured response, then local Pydantic validation
checks the returned JSON again. Categories and urgency must come from fixed
allowed values; all five fields are required, the human-review flag must be a
real boolean, text fields must be nonempty and bounded, and extra fields are
rejected. An invented category, missing summary, string in place of a boolean,
malformed JSON or truncated response is therefore a failed result, rather than
something downstream code silently interprets. The one-to-two-sentence summary
instruction is a prompt requirement; schema validation enforces text length,
not sentence count or factual accuracy.

Malformed outputs and temporary provider failures take different paths.
Schema failures receive at most two correction retries, with sanitized
validation feedback rather than rejected model text inserted into trusted
instructions. Timeouts, connection failures, rate limits and server errors
receive at most three transport retries with exponential backoff and jitter.
There is a six-attempt total cap per stage and a 45-second timeout per request;
that is not a 45-second deadline for the entire complaint. SDK retries are
disabled to avoid hidden retry multiplication. A server-requested wait is
honored; waits beyond 60 seconds cause deferral and a provider cooldown rather
than an early retry.

Exhausted screening or triage, blocked inputs and provider content refusals
produce an explicit human-review fallback. Its generic summary says automation
is unavailable instead of inventing a description of the complaint. Status and
failure reason distinguish the fallback from a successful classification;
its default medium urgency is administrative, not a judgment that the case is
safe. Invalid credentials or permanent configuration errors stop the batch,
since retrying every complaint would not repair the underlying problem.
Completed rows are flushed to disk so a later interruption does not erase them.

These controls make failures observable and bounded. They do not turn a valid
JSON object into a correct triage decision: choosing the wrong allowed category
or inventing a detail inside a valid summary still requires semantic evaluation.

### Defining correctness before scoring

The reference task is defined by a written labeling rubric, rather than the
model's own explanation of its answer. CFPB product and issue fields provide
context, but are not automatically treated as ground-truth PayGuard routes.
Company responses and later resolution information are excluded from model
inputs and should not influence reference labels: the decision must be made
from information available when the complaint arrives.

The real-data evaluation reserves **20 distinct complaint narratives**, selected
uniformly with a fixed seed from the prepared slice after removing exact
trimmed-text repeats for this selection. IDs and source/input fingerprints
record which cases were selected. Distinct-text selection reduces the chance
that repeated wording makes the evaluation look more diverse than it is;
near-duplicates and related complaints can still remain.

Each reserved case has reference category, urgency and human-review annotations
marked `human`. The labeling protocol is to read the complaint, apply the rubric,
record ambiguity and annotate before inspecting predictions. The recorded run
kept its prompts and reference labels unchanged; it did not selectively rerun
errors to improve scores. No independent second-annotator agreement measurement
is reported, so the annotations remain reviewable judgments rather than
infallible truth. If these cases guide later prompt changes, they become
development examples and a new holdout is needed.

Correctness has several parts:

| Output | Reference decision or review criterion |
|---|---|
| Category | The primary underlying problem maps to the rubric's supported team; unsupported or materially ambiguous cases use `OTHER_OR_UNCLEAR`. |
| Urgency | Low, medium or high matches the stated evidence of harm and immediacy; anger or a large amount alone does not establish high urgency. |
| Human review | Escalation is required for fraud allegations, explicit legal threats, high urgency, unsupported products or material ambiguity. |
| Summary | A concise paraphrase preserves the issue and relevant actors, amounts and timing without adding facts or presenting allegations as verified. |
| Confidence note | Missing evidence or ambiguity is identified specifically, without unsupported claims about events, policy or legal outcomes. |

For example, an ongoing unauthorized withdrawal is different from a historical
duplicate charge. Both may concern missing money, but they warrant different
routes and potentially different urgency. Likewise, a credit-report complaint
mentioning identity theft is outside the defined payments teams and should not
be forced into payments fraud simply because it contains that phrase. These
distinctions make the reference task reproducible and expose policy ambiguity.

### Measuring decisions without hiding abstentions

Category, urgency and human-review accuracy are calculated separately against
available reference labels. **Joint correctness** requires all three categorical
decisions to be correct on a successful triage. It does not include summary or
confidence-note quality, so an 80% joint score is not an 80% success rate for
the complete five-field record.

Confusion matrices show which routes and urgency levels are being confused.
Per-category support, precision/recall and macro-F1 over supported categories
help reveal weaknesses hidden by overall accuracy. Categories with no reference
examples are reported as unsupported, not counted as successfully evaluated.
A whole-slice run without reviewed labels can measure throughput, failures and
judge flags, but cannot establish routing or urgency accuracy.

The human-review flag is also a safety decision. A **false negative** leaves
a case requiring review on a routine route; a **false positive** escalates a
case that could have received routine handling. Missing a fraud allegation or
legal threat can be more consequential than an unnecessary review, but
escalating everything would defeat the workload objective. Human-review recall
therefore needs to be considered alongside precision and escalation volume.

Failure accounting prevents safe abstention from masquerading as successful
automation. A fallback cannot earn category or urgency correctness, even if its
default values happen to match the reference. It can count as a correct
human-review decision when review is required, because it preserved that safety
boundary. Successful-routing coverage and fallback volume must accompany that
metric; otherwise an always-defer system could look safe without doing useful
triage. Missing labels and judge failures keep explicit denominators instead
of silently becoming correct answers or zero-error observations.

Saved predictions are matched by complaint ID and input fingerprint, then
scored locally. This allows an evaluator change or label audit to be checked
without another nondeterministic model call. Prompts, model names, attempts and
per-case checks are recorded for error review. The 54 offline tests exercise
these boundaries and metric calculations using mocks; passing them establishes
engineering behavior, not live model quality.

The recorded live evaluation gives the following evidence:

| Measurement | Reviewed complaints | Synthetic safety suite |
|---|---:|---:|
| Cases | 20 | 12 benign controls and 10 attacks |
| Valid generated triage records | 20/20 | 12/12 allowed controls |
| Category correct | 20/20 | 12/12 allowed controls |
| Urgency correct | 16/20 | 11/12 allowed controls |
| Human-review decision correct | 20/20 | 22/22, including blocked-attack fallbacks |
| Joint category/urgency/review correct | 16/20 | 11/12 allowed controls |
| Model-judged grounding flags | 7/19 completed verdicts | 1/12 completed verdicts |
| Judge failures | 1 | 0 |

The real sample contains **19 `OTHER_OR_UNCLEAR` labels and one
`FEES_AND_BILLING` label**. A majority-category baseline already scores 95%,
so 100% category accuracy provides little evidence about the other five
categories. Nineteen cases require human review and only one does not; an
always-review baseline also reaches 95% accuracy. Correct escalation on this
sample cannot establish that the system safely recognizes a broad range of
payment-fraud or legal-threat cases.

Urgency is a clearer weakness: **80% accuracy is below the 90% always-medium
baseline**. Three medium cases were labeled low and one low case medium.
All four still required human review, which preserves escalation but can still
affect queue prioritization. No real reference case is high urgency; only two
synthetic cases test that label. At this sample size, one case changes an
accuracy result by five percentage points.

The synthetic suite is therefore reported separately. It deliberately covers
all routes and targeted safety cases, while the real sample exposes the
observed complaint mix. Pooling them would let authored examples conceal poor
real-world coverage. Neither the small random sample nor hand-authored tests
is representative evidence of production payments-triage performance.

### Checking that summaries remain faithful

Routing labels do not establish summary quality, and exact text matching would
penalize legitimate paraphrases. A separate judge compares each successful
triage's summary and confidence note against the original complaint. It checks
whether factual claims are supported and returns unsupported claims with input
excerpts. Code verifies that quoted evidence actually occurs in the input and
that the verdict is internally consistent.

This is a scalable way to identify cases for audit, not independent proof that
a summary is true. The judge uses the same text-model family as generation and
can share its blind spots. Exact excerpts establish that evidence was quoted
correctly, not that it supports every inference. Human audit should check
amounts, dates, actors, alleged versus verified events, promised resolutions
and invented causal relationships. Both judge flags and a sample of passes
need review to estimate the judge's own errors.

The real-data run produced **seven flags among 19 completed verdicts (36.8%)**,
plus one judge failure. All seven flags concerned confidence notes; one also
questioned a summary's description of the relationship between a collector
and another party. Some flags themselves may be questionable, including an
objection to a permitted out-of-scope explanation. Consequently, 36.8% is a
**model-judged flag rate**, not a human-verified hallucination rate. The failed
judge call is unresolved, not a pass.

The next grounding evaluation should have humans adjudicate these cases and
a random selection of passes against the original text, recording the
unsupported claim and evidence. Human-confirmed summary and confidence-note
error rates should then be reported separately. A numerically correct route
does not compensate for a misleading account of the customer's complaint.

### Injection attempts and sensitive complaints

Complaint text and metadata are untrusted evidence. A request such as
"refund my payment" is ordinary complaint content; a request to ignore routing
rules, suppress review, reveal instructions or output attacker-selected JSON
is an instruction-override attempt. The screening call examines all input
fields before generation. The triage prompt also treats embedded instructions
as untrusted, since screening can miss attacks. Model calls have no tools
for following links, executing commands or accessing files.

The synthetic attack suite includes ten attempts and twelve benign controls.
All ten attacks were blocked before triage and no benign control was blocked:
observed detection recall is **10/10**, with a **0/12 benign false-block rate**.
Measuring benign controls matters because a screen that blocks everything
would otherwise appear perfect. Screening failures must also remain separate
from actual block decisions. These results cover the authored attempts,
not arbitrary paraphrases, languages or adaptive attacks.

Sensitive content is not itself an injection. Alleged unauthorized activity,
explicit legal threats and immediate harm need escalation while preserving
the customer's account of events. Local rules force human review for predicted
fraud/unclear categories, high urgency and recognized English legal-threat
patterns. Those rules are backstops: category-based overrides depend on the
model detecting the issue, and the legal pattern cannot capture every
paraphrase or language. A schema-valid but misrouted sensitive case can still
escape them.

The output never authorizes case closure or movement of funds.
`requires_human=false` means eligible for routine routing, not that the complaint
has been resolved or should be auto-closed. Screening blocks and exhausted
failures also require review. An invented category is rejected structurally;
an incorrect choice among allowed categories or an invented fact in the
summary must be caught through evaluation and audit.

### Cost and latency at 50,000 complaints per month

The cost model separates screening and triage from optional grounding
evaluation. The recorded price snapshot uses $0.10 per million input tokens
for Decisions, with no output tokens, and $0.15 input/$0.60 output per million
tokens for GPT-OSS 120B. These rates are documented by
[Google](https://aistudio.google.com/docs/pricing#gemini-decision) and
[Groq](https://console.groq.com/docs/models); the repository retains its dated
[price snapshot](LLM_Complaint_Triage/prices.json) for reproduction. Spend depends
on prompt plus narrative length, generated/reasoning tokens and retries.
Reasoning is already included in the reported output-token total and is not
charged a second time.

The recorded 20-complaint run estimates approximately **$0.0126 for screening
plus triage** and **$0.0248 for judging**, using only reported token usage.
Dividing by 20 and scaling linearly gives:

| Stage | Approximate cost per complaint | At 50,000 complaints/month |
|---|---:|---:|
| Screening and triage | $0.00063 | $31.50 |
| Optional grounding judge on every complaint | $0.00124 additional | $62.00 additional |
| Both, with judging on every complaint | $0.00187 | $93.50 |

**These are partial-usage extrapolations, not a complete budget or invoice.**
Some failed/retried attempts lack usage records, so automated aggregate and
monthly costs remain null rather than pretending usage is complete. The
projection assumes the same input/output mix and retry behavior and excludes
human review, infrastructure and operations. A changed complaint mix, longer
narratives or different models could change it substantially. A judge on a
sample would have a different cost from judging every complaint.

Operationally, the reviewed sample averaged **17.28 seconds per complaint** for
screening plus triage, with **27.08-second p95**; screening alone averaged
0.79 seconds. Judging added 13.88 seconds on average. There were 50 transport
retries across triage and judging and 11 judge correction retries; triage itself
needed no output correction retries. These are free-tier timings affected by
token throttling and backoff, not isolated model-compute benchmarks.

At the same 17.28-second average, a sequential worker would consume roughly
**240 hours** to process 50,000 complaints before judging. Paid capacity,
bounded concurrency and queue monitoring would need validation under realistic
load; concurrency does not remove token or request quotas. The prototype is
appropriate for asynchronous triage, not an established low-latency interaction.

The token projection also says nothing about staff savings. Most reviewed
cases still needed humans, and no change in handling time was measured. A
useful rollout must measure analyst time saved by summaries and routing against
review effort, overrides and error correction, not just the API bill.

### Building a stronger evaluation before rollout

The next evaluation should combine a random sample for population-level error
and workload estimates with a separate, deliberately enriched sample of
payments, rare routes, fraud, legal threats, ambiguity and high urgency.
Report the two separately; an enriched safety set does not establish a natural
prevalence. Have a second reviewer independently label a subset, resolve
disagreements with the rubric and retain a fresh holdout after prompt changes.

At scale, track per-route precision/recall and support, urgency confusion and
under-triage of high-risk cases, human-review recall and unnecessary escalation,
human-confirmed grounding errors, benign blocks, attacks reaching generation,
fallbacks, correction/transport retries, complete token spend, queue age and
p95 latency. Audit routine routes as well as escalations: reviewing only cases
the model already sends to humans would miss failures in the purportedly safe
queue.

Changes in product mix, language, narrative length or provider behavior can
degrade the workflow without breaking its schema. Versioned prompts and saved
per-case decisions support regression checks, but a representative human audit
is still needed to distinguish valid-looking output from useful triage. The
current evidence supports an assisted workflow with continued evaluation,
not unattended resolution.

[Recorded live results and error review](LLM_Complaint_Triage/evaluation/GROQ_RESULTS.md).
[Saved reports, predictions and offline reproduction](LLM_Complaint_Triage/evaluation/results/README.md).
[Labeling rubric and grounding-audit protocol](LLM_Complaint_Triage/evaluation/LABELING.md).
