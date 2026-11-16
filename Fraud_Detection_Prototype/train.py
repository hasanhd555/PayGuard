"""Fit fixed models and freeze validation decisions before any test scoring."""

import argparse
from datetime import datetime, timezone
from pathlib import Path
import platform
from time import perf_counter
import warnings

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .common import DATA_PATH, FEATURES, SEED, read_json, versions, write_json
from .data import chronological_split, load_data, split_audit
from .metrics import choose_threshold, evaluate, select_model, validate_costs
from .reporting import comparison_table, plot_precision_recall, plot_training_data


def build_models() -> dict:
    return {
        "logistic_regression": Pipeline([
            ("scale", StandardScaler()),
            ("model", LogisticRegression(penalty="l2", C=1., solver="lbfgs",
                                         class_weight="balanced", max_iter=1000, random_state=SEED)),
        ]),
        "random_forest": Pipeline([
            ("model", RandomForestClassifier(n_estimators=120, max_depth=16, min_samples_leaf=2,
                                             class_weight="balanced", bootstrap=True,
                                             random_state=SEED, n_jobs=2)),
        ]),
    }


def sensitivity(y, predictions: dict, fp_cost: float, fn_cost: float) -> list[dict]:
    rows = []
    for ratio in sorted({10., 20., 50., fn_cost / fp_cost}):
        metrics = {}
        for name, scores in predictions.items():
            threshold = choose_threshold(y, scores, fp_cost, fp_cost * ratio)["threshold"]
            metrics[name] = evaluate(y, scores, threshold, fp_cost, fp_cost * ratio)
        selected = select_model(metrics)
        rows.append({"ratio": ratio, "selected_model": selected, **metrics[selected]})
    return rows


def run(data_path: Path, output: Path, fp_cost=5., fn_cost=100.) -> dict:
    validate_costs(fp_cost, fn_cost)
    if output.exists():
        raise FileExistsError(f"Run directory must be new: {output}")
    frame, audit = load_data(data_path)
    splits, boundaries = chronological_split(frame)
    train, validation = splits["train"], splits["validation"]
    manifest = {"created_utc": datetime.now(timezone.utc).isoformat(),
                "python": platform.python_version(), "platform": platform.platform(),
                "versions": versions(), "seed": SEED, "data": audit, "features": FEATURES,
                "boundaries": boundaries, "splits": split_audit(splits),
                "policy": {"fp_cost": fp_cost, "fn_cost": fn_cost, "action": "human_review"},
                "models": {}, "validation": {}}
    source = data_path.with_suffix(".source.json")
    if source.exists():
        provenance = read_json(source)
        if provenance.get("sha256") == audit["sha256"]:
            manifest["data"]["source_url"] = provenance.get("source_url")
    models, predictions = build_models(), {}
    for name, pipeline in models.items():
        print(f"Fitting {name}: {len(train):,} earlier transactions...", flush=True)
        start = perf_counter()
        with warnings.catch_warnings():
            warnings.simplefilter("error", ConvergenceWarning)
            pipeline.fit(train[FEATURES], train.Class)
        fit_seconds = perf_counter() - start
        if name == "random_forest":
            pipeline.set_params(model__n_jobs=1)
        scores = pipeline.predict_proba(validation[FEATURES])[:, 1]
        predictions[name] = scores
        threshold = choose_threshold(validation.Class, scores, fp_cost, fn_cost)["threshold"]
        manifest["validation"][name] = evaluate(validation.Class, scores, threshold, fp_cost, fn_cost)
        manifest["models"][name] = {"artifact": f"{name}.joblib", "fit_seconds": fit_seconds,
                                    "configuration": str(pipeline)}
    # Selection only sees the validation dictionaries. Test features are never scored here.
    manifest["selected_model"] = select_model(manifest["validation"])
    manifest["sensitivity"] = sensitivity(validation.Class, predictions, fp_cost, fn_cost)
    manifest["validation"]["always_legitimate"] = evaluate(
        validation.Class, np.zeros(len(validation)), 1., fp_cost, fn_cost)
    output.mkdir(parents=True, exist_ok=False)
    for name, pipeline in models.items():
        joblib.dump(pipeline, output / manifest["models"][name]["artifact"])
    write_json(output / "manifest.json", manifest)
    pd.DataFrame({"label": validation.Class.to_numpy(), **predictions}).to_csv(
        output / "validation_scores.csv", index=False)
    comparison_table(manifest["validation"]).to_csv(output / "validation.csv", index=False)
    plot_precision_recall(validation.Class, predictions, output / "validation_pr.png")
    plot_training_data(train, output / "training_audit.png")
    write_json(output / "training_summary.json", train[FEATURES].describe().to_dict())
    selected = manifest["selected_model"]
    print(f"Frozen selection: {selected}; threshold {manifest['validation'][selected]['threshold']:.9g}", flush=True)
    print(f"Run: {output}", flush=True)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DATA_PATH)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--fp-cost", type=float, default=5.)
    parser.add_argument("--fn-cost", type=float, default=100.)
    args = parser.parse_args()
    run(args.data, args.output_dir, args.fp_cost, args.fn_cost)


if __name__ == "__main__":
    main()
