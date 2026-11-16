"""Standalone plots and concise tables for the feasibility study."""

from pathlib import Path
import os

from .common import ROOT

# Keep Matplotlib's writable cache local to this prototype as well.
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".cache" / "matplotlib"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import PrecisionRecallDisplay


def plot_precision_recall(y, predictions: dict, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(7, 5))
    for name, scores in predictions.items():
        PrecisionRecallDisplay.from_predictions(y, scores, name=name, ax=ax)
    ax.axhline(float(np.mean(y)), linestyle="--", color="gray", label="Prevalence")
    ax.set_title("Fraud detection: precision–recall")
    ax.legend(loc="lower left")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_training_data(train: pd.DataFrame, path: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for label, name in [(0, "Legitimate"), (1, "Fraud")]:
        values = train.loc[train.Class == label, "Amount"]
        axes[0].hist(np.log1p(values), bins=40, density=True, histtype="step", label=name)
    axes[0].set(xlabel="log(1 + Amount), visualization only", ylabel="Density")
    axes[0].legend()
    hourly = train.groupby((train.Time // 3600).astype(int)).Class.agg(["count", "sum"])
    axes[1].plot(hourly.index, hourly["sum"] / hourly["count"])
    axes[1].set(xlabel="Elapsed hour", ylabel="Fraud prevalence", title="Training period only")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def comparison_table(validation: dict, test=None) -> pd.DataFrame:
    rows = []
    for name, metrics in validation.items():
        row = {"model": name}
        row.update({f"validation_{key}": value for key, value in metrics.items()})
        if test is not None:
            row.update({f"test_{key}": value for key, value in test[name].items()})
        rows.append(row)
    return pd.DataFrame(rows)


def render_results(manifest: dict, test: dict, latency: dict) -> str:
    lines = ["# Part A: measured results", "", "Generated from frozen validation decisions; no test-based tuning.",
             "", f"Dataset SHA-256: `{manifest['data']['sha256']}`.",
             f"Source rows: {manifest['data']['source_rows']:,}; exact duplicates removed: "
             f"{manifest['data']['exact_duplicates_removed']:,}.", "",
             "| Partition | Rows | Fraud | Prevalence | Time range (seconds) | Earlier feature repeats |",
             "|---|---:|---:|---:|---|---:|"]
    for name, row in manifest["splits"].items():
        lines.append(f"| {name} | {row['rows']:,} | {row['frauds']} | {row['prevalence']:.4%} | "
                     f"{row['time_min']:g}–{row['time_max']:g} | {row['feature_rows_seen_in_earlier_split']} |")
    lines += ["", "| Model | Validation AP | Validation cost | Test AP | ROC AUC | Threshold | Precision | Recall | FP | FN | Alerts | Cost / 1,000 |",
              "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for name, val in manifest["validation"].items():
        row = test[name]
        lines.append(f"| {name} | {val['average_precision']:.4f} | {val['modeled_cost']:.0f} | "
                     f"{row['average_precision']:.4f} | {row['roc_auc']:.4f} | {row['threshold']:.6g} | "
                     f"{row['precision']:.2%} | {row['recall']:.2%} | {row['fp']} | {row['fn']} | "
                     f"{row['alerts']} | {row['cost_per_1000']:.2f} |")
    selected = manifest["selected_model"]
    policy = manifest["policy"]
    lines += ["", f"Selected on validation: **{selected}**, threshold "
              f"**{manifest['validation'][selected]['threshold']:.9g}**.",
              f"FP cost = {policy['fp_cost']:g}; FN cost = {policy['fn_cost']:g} hypothetical units.",
              "Flags request human review. These costs are assumptions, not PayGuard measurements.",
              "", "## Validation sensitivity", "",
              "Each row reselects the model and threshold on validation only. The default policy stays frozen.", "",
              "| FN/FP cost ratio | Selected model | Threshold | Precision | Recall | Alerts |",
              "|---|---|---:|---:|---:|---:|"]
    for row in manifest["sensitivity"]:
        lines.append(f"| {row['ratio']:g} | {row['selected_model']} | {row['threshold']:.6g} | "
                     f"{row['precision']:.2%} | {row['recall']:.2%} | {row['alerts']} |")
    lines += ["", "## Runtime", "",
              f"Selected pipeline, warm single-row inference: p50 {latency['p50_ms']:.2f} ms; "
              f"p95 {latency['p95_ms']:.2f} ms, {latency['repeats']} calls, one inference worker.",
              "Includes DataFrame feature selection and fitted preprocessing; excludes CSV reading, "
              "feature retrieval and network latency. This is not a service latency guarantee.", "",
              "Training times: " + "; ".join(f"{name}: {row['fit_seconds']:.2f} s"
                  for name, row in manifest["models"].items()) + ".", "",
              "## Interpretation limits", "",
              "Test estimates use only the fraud counts shown above, from a short historical period. "
              "No confidence interval or independence across fraud episodes is established. "
              "Feature repeats may represent genuine events; without entity IDs we cannot isolate cards or episodes. "
              "Higher scores are not established fraud probabilities. "
              "See the Part A README for methodology, costs and real-time constraints.", "",
              "![Validation precision–recall](validation_pr.png)", "",
              "![Test precision–recall](test_pr.png)", "",
              "![Training data audit](training_audit.png)", ""]
    return "\n".join(lines)
