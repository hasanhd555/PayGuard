# Part A: setup, dataset and implementation

A small, offline feasibility study comparing logistic regression with random
forest on ULB credit-card transactions. The default action is **request human
review**, not automatically decline a payment.

For the decision rationale and interpretation of the model comparison, read the
[main README](../README.md#part-a-fraud-detection). This document contains the
reproduction instructions, dataset audit and implementation walkthrough.

## Independent setup

Run these PowerShell commands from the Git repository directory (the inner
`PayGuard` directory), using Python 3.11. Each prototype has its own environment,
requirements, tests, data and outputs. Part A does not import complaint triage,
read `.env`, use credentials or make model API calls.

```powershell
python -m venv Fraud_Detection_Prototype/.venv
& ./Fraud_Detection_Prototype/.venv/Scripts/python.exe -m pip install -r Fraud_Detection_Prototype/requirements.txt

# Download once; refuses to overwrite an existing dataset.
& ./Fraud_Detection_Prototype/.venv/Scripts/python.exe -m Fraud_Detection_Prototype.data

# Train on earlier data; freeze choices using validation only.
& ./Fraud_Detection_Prototype/.venv/Scripts/python.exe -m Fraud_Detection_Prototype.train --output-dir Fraud_Detection_Prototype/runs/experiment-1

# Evaluate both frozen pipelines on the final chronological period.
& ./Fraud_Detection_Prototype/.venv/Scripts/python.exe -m Fraud_Detection_Prototype.evaluate --run-dir Fraud_Detection_Prototype/runs/experiment-1 --output-dir Fraud_Detection_Prototype/runs/experiment-1/test

# Offline checks with no API credentials or downloads.
& ./Fraud_Detection_Prototype/.venv/Scripts/python.exe -m pytest -c Fraud_Detection_Prototype/pytest.ini Fraud_Detection_Prototype/tests
```

On Linux/macOS, use `Fraud_Detection_Prototype/.venv/bin/python` instead. Reuse the
downloaded data but choose new run/output names for another experiment. To use
an existing dataset, pass `--data path/to/creditcard.csv` to both training and
evaluation; training never downloads automatically. Evaluation requires the same
file fingerprint. The download command also accepts `--output`.

Dependencies are pinned in this part's requirements file. Artifacts record actual
versions and prediction/evaluation reject mismatched direct dependency versions.
Do not use the old shared root `.venv` for the independent setup. Root
`requirements.txt` remains a compatibility entry point for Part B only.

## Dataset and audit

Original: [ULB/Worldline Credit Card Fraud Detection](https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud).
The downloader uses the public CSV mirror linked by the
[TensorFlow tutorial](https://www.tensorflow.org/tutorials/structured_data/imbalanced_data):
`https://storage.googleapis.com/download.tensorflow.org/data/creditcard.csv`.
No Kaggle account or TensorFlow installation is required.

The documented source contains 284,807 transactions, including 492 frauds,
across two days in September 2013. `V1`–`V28` are anonymized PCA components;
`Time` is seconds since the first transaction, `Amount` is transaction size,
and `Class` is the fraud label. Downloaded data is excluded from Git. A source
sidecar records the URL and SHA-256; each training manifest records its own hash.

The audit checks schema, numeric types, missing/nonfinite values, binary labels,
nonnegative time/amount, and exact duplicates. Invalid inputs fail explicitly:
there is no silent dropping or imputation. Exact full-row duplicates are removed,
keeping their first occurrence. This is an assumption: without transaction IDs,
we cannot establish that every exact repeat is an ingestion error. Repeated
model features at different timestamps remain; their overlap across partitions
is reported. Such overlap is a warning to investigate, not proof of leakage.

The training audit plot displays `log1p(Amount)` only to make its distribution
readable. The actual models use raw Amount. Amount extremes are not discarded:
unusual observations may contain the fraud signal.

## Pipeline walkthrough

1. **Audit and split.** Stable-sort by Time, then split approximately 60/20/20 by
   row count. Equal timestamps stay together. The validation period begins at
   the 60% row's timestamp; test begins at the 80% row's timestamp. All partitions
   must contain both classes. Boundaries and counts are saved. Test outcomes
   never influence model or threshold selection.
2. **Select inputs.** Both models receive `V1`–`V28` and Amount in a fixed order.
   Class is the target. Time establishes chronology but is excluded as a
   predictor: time since this particular dataset began is not a durable signal
   for future deployment. No extra PCA, categorical encoding or feature
   selection is needed for this initial feature set.
3. **Handle imbalance.** Retain every deduplicated training row and use balanced
   class weights derived from training labels. No undersampling, oversampling
   or SMOTE is applied. Weighting changes the fitting objective, not row counts.
4. **Fit logistic regression.** Fit StandardScaler on training inputs only, then
   fit an L2-regularized logistic model. Scaling aids optimization and prevents
   feature units from dominating regularization. It does not remove skew.
5. **Fit random forest.** Use the same features without scaling. Trees can learn
   nonlinear relationships and interactions. Their internal bootstrap samples
   are not explicit class balancing; class weights handle imbalance separately.
6. **Choose on validation.** Score validation data, derive thresholds and select
   a model using the fixed cost policy below. Save both fitted pipelines and
   the frozen decisions. Do not refit on train plus validation.
7. **Evaluate separately.** The evaluation command scores the final period with
   both saved models and their frozen thresholds. It cannot change selection.

The core fitting logic is deliberately ordinary scikit-learn:

```python
logistic = Pipeline([
    ("scale", StandardScaler()),
    ("model", LogisticRegression(
        penalty="l2", C=1.0, solver="lbfgs",
        class_weight="balanced", max_iter=1000, random_state=42,
    )),
])
logistic.fit(X_train, y_train)  # Learns scaler and coefficients from train only.

forest = Pipeline([
    ("model", RandomForestClassifier(
        n_estimators=120, max_depth=16, min_samples_leaf=2,
        class_weight="balanced", bootstrap=True,
        random_state=42, n_jobs=2,
    )),
])
forest.fit(X_train, y_train)

validation_scores = logistic.predict_proba(X_validation)[:, 1]
# predict_proba reuses the training scaler; it never fits a new scaler.
```

These are fixed initial configurations, not tuned winners. Logistic convergence
warnings stop training. Random forest uses one worker after fitting to avoid
thread-dispatch overhead during single-row inference. A more complex model is
not guaranteed to win.

## Metrics and operating policy

**Average precision (AP)** measures ranking quality under severe imbalance.
It summarizes precision over recall increments, rather than trapezoidal PR area;
we name it precisely. A constant-score comparator has AP equal to that period's
prevalence. ROC AUC is secondary context; accuracy can hide complete failure to
detect fraud. We also report TP/FP/FN/TN, precision, recall, false-positive rate,
alert count/rate, and modeled cost per 1,000 transactions.

Default costs are **FP = 5 and FN = 100 hypothetical units**, so policy cost is
`5 * FP + 100 * FN`. An FP represents unnecessary review/customer friction;
an FN represents expected unrecovered loss and handling. These are not measured
PayGuard economics, and the transaction amount is not assumed to equal net loss.
The simplified objective omits review costs on true positives and recovery
effectiveness. Confirm these with PayGuard before setting a production policy.

For each model, scan all distinct validation scores, keeping tied scores
together, plus a no-alert option. Minimize cost; prefer fewer alerts on a tie.
Choose the model with the lower validation cost; prefer logistic regression if
model costs tie. A no-alert threshold can be slightly above 1 when required.
This is an explicitly encoded decision rule, not a probability claim.

Validation sensitivity repeats selection at FN/FP ratios 10, 20 and 50 (plus a
custom ratio if supplied). It never changes the default frozen policy or tunes
against test results. Custom costs are accepted by `train --fp-cost 5 --fn-cost 100`
and must be finite and positive. No review-capacity limit is
assumed; alert volume is reported for business discussion. Never choose a
different model just because its test result looks better.

## Outputs and new-transaction scoring

Training writes `manifest.json`, both `.joblib` pipelines, validation scores and
comparison CSVs, training summary statistics, training audit and validation PR
plots. The manifest includes versions, seed, dataset hash, split boundaries,
fixed model configurations, timing, selection and cost sensitivity.

Evaluation writes JSON metrics, a comparison CSV, test PR plot, and `RESULTS.md`
with the validation and training plots copied alongside it. The curated
[measured results](results/RESULTS.md) preserve a complete experiment's tables
and figures. Models and raw run directories remain excluded from Git.

The recorded run removed 1,081 exact duplicates, including 19 fraud rows, leaving
283,726 rows and 473 frauds. The chronological partitions contain 342, 57 and 74
frauds respectively. Validation selected random forest at score **0.324504778**:
cost 1,410 versus logistic regression's 1,425, a small advantage. Logistic
regression actually had slightly higher validation AP (0.7727 versus 0.7692).
Thus the cost objective, rather than ranking AP, determined the selection.

On test, random forest caught 56/74 frauds with 8 false alarms (AP 0.8062), versus
55/74 with 21 false alarms for logistic regression (AP 0.7466). Random forest
required 108.53 seconds to fit versus 1.39 seconds for logistic regression in
this run. Its model-only warm inference p95 was 32.10 ms on the recorded machine.
The forest is a provisional operating choice, not a robustly established winner:
validation contains only 57 frauds, the assumed costs are uncertain, and its
validation advantage is only 15 hypothetical units.

At FN/FP ratio 50, the validation-selected forest threshold fell to 0.06645:
recall increased from 75.44% to 82.46%, but alerts rose from 45 to 153 and
precision fell from 95.56% to 30.72%. This illustrates why the review action and
business costs matter. That alternative was not adopted or tuned on test.

```powershell
& ./Fraud_Detection_Prototype/.venv/Scripts/python.exe -m Fraud_Detection_Prototype.predict --run-dir Fraud_Detection_Prototype/runs/experiment-1 --input path/to/new_transactions.csv --output Fraud_Detection_Prototype/runs/new_predictions.csv
```

Prediction requires the 29 input features, permits extra metadata, reorders
columns using the saved feature list and ignores labels/Time. Its output is
`row_index,fraud_score,requires_review`, with zero-based input row positions.
Review uses `fraud_score >= saved_threshold`. It never fits or selects anything.
Load only artifacts you created or trust: joblib is pickle-based.

## Real-time feasibility and limits

At payment time, every feature must already exist and be inexpensive to retrieve.
A recent-transaction count must include only events preceding that payment;
future chargebacks or later investigation outcomes cannot be predictors.
Training must use the same feature availability rules as live scoring, including
the delay before fraud labels become available. This dataset cannot simulate
those delays or reconstruct the original PCA inputs, so chronological evaluation
is necessary but does not establish a deployable feature pipeline.

Fit offline, load the pipeline into memory, and reuse preprocessing for each
request. Measure full service latency including feature retrieval, networking
and peak load before choosing a production latency budget. The prototype reports
five warm-up calls followed by 100 single-row calls, p50/p95, including DataFrame
selection and preprocessing but excluding I/O and networking. It supplies a CSV
scorer, not an inference server.

Two historical days cannot demonstrate future robustness, seasonal coverage or
transfer to PayGuard. There are few fraud cases, potentially correlated within
episodes. Counts support interpretation; no independent-sample confidence claim
is made. Card/merchant identifiers are absent, preventing entity-level holdouts
and velocity features. The PCA fitting procedure is unavailable; we cannot
verify that its upstream preprocessing obeyed our split. Class weighting can
distort probability calibration: scores should not be called established fraud
probabilities.

Deliberate cuts: calibration, tuning searches, resampling experiments, additional
models, a service/UI, confidence intervals, and Part C. A production follow-up
would establish local costs and review capacity, validate with longer
representative data, account for delayed labels, and monitor feature drift,
alert volume, precision/recall once labels mature, and end-to-end latency.
