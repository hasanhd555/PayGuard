# Setup and datasets

This document covers installation, data acquisition and commands. The
[main README](README.md) explains the decisions and measured trade-offs.

## Independent environments

Use Python 3.11 and run commands from this Git repository directory (the inner
`PayGuard` directory). Each part has its own virtual environment, requirements,
tests, data and outputs. The commands below do not use the old shared root
`.venv`. On Linux/macOS, replace `.venv/Scripts/python.exe` with `.venv/bin/python`
and omit PowerShell's `&`.

## Part A: fraud detection

```powershell
python -m venv Fraud_Detection_Prototype/.venv
& ./Fraud_Detection_Prototype/.venv/Scripts/python.exe -m pip install -r Fraud_Detection_Prototype/requirements.txt

# Download once. No API keys, Kaggle account or LLM dependencies are required.
& ./Fraud_Detection_Prototype/.venv/Scripts/python.exe -m Fraud_Detection_Prototype.data

# Freeze model and threshold choices using validation only.
& ./Fraud_Detection_Prototype/.venv/Scripts/python.exe -m Fraud_Detection_Prototype.train --output-dir Fraud_Detection_Prototype/runs/experiment-1

# Evaluate the untouched final period using the saved choices.
& ./Fraud_Detection_Prototype/.venv/Scripts/python.exe -m Fraud_Detection_Prototype.evaluate --run-dir Fraud_Detection_Prototype/runs/experiment-1 --output-dir Fraud_Detection_Prototype/runs/experiment-1/test

& ./Fraud_Detection_Prototype/.venv/Scripts/python.exe -m pytest -c Fraud_Detection_Prototype/pytest.ini Fraud_Detection_Prototype/tests
```

The source is the ULB/Worldline credit-card dataset: 284,807 transactions with
492 fraud labels, covering two days in September 2013. The download uses the
public TensorFlow CSV mirror; both original source and mirror links are in the
[Part A setup and data guide](Fraud_Detection_Prototype/SETUP_AND_DATA.md#dataset-and-audit).
That guide documents columns, duplicate handling, input validation, source
fingerprints, saved artifacts and new-transaction scoring.

To use your own downloaded copy, pass `--data path/to/creditcard.csv` to both
training and evaluation. The file fingerprint must match. The download and run
commands refuse to overwrite existing inputs/results; use fresh output names
when repeating an experiment. Raw fraud data, models and run directories are
excluded from Git; the [curated results](Fraud_Detection_Prototype/results/RESULTS.md)
are included for review.

## Part B: complaint triage

```powershell
python -m venv LLM_Complaint_Triage/.venv
& ./LLM_Complaint_Triage/.venv/Scripts/python.exe -m pip install -r LLM_Complaint_Triage/requirements.txt

# First-time configuration only; keep an existing populated .env.
Copy-Item .env.example .env
# Set GOOGLE_API_KEY for screening and GROQ_API_KEY for Groq generation.
& ./LLM_Complaint_Triage/.venv/Scripts/python.exe -m LLM_Complaint_Triage.pipeline.batch --provider groq --limit 5

# Offline verification makes no API calls and requires no credentials.
& ./LLM_Complaint_Triage/.venv/Scripts/python.exe -m pytest -c LLM_Complaint_Triage/pytest.ini LLM_Complaint_Triage/tests
```

Part B uses a reproducible 500-record CFPB complaint slice. See the
[Part B guide](LLM_Complaint_Triage/README.md) for exact slice documentation,
provider configuration, batch/evaluation commands, schemas, retries and costs;
the [data profile](LLM_Complaint_Triage/data/sample_profile.md) describes the
sample. The [labeling guide](LLM_Complaint_Triage/evaluation/LABELING.md) defines
the reviewed labels and rubric. Existing `.env` lookup and provider behavior
are unchanged; Part A does not read those credentials.

The [curated Part B evaluation artifacts](LLM_Complaint_Triage/evaluation/results/README.md)
include both live evaluation suites and commands to rescore them offline without
credentials. The full upstream complaint export is excluded from Git; the
included 500-record slice and reviewed/synthetic cases are sufficient to run
the prototypes and inspect their evaluation.

The root requirements file and default root pytest command remain compatibility
entry points for Part B only. Use the explicit per-part commands for independent
environments. Verified offline suites contain 25 fraud tests and 54 triage tests.
