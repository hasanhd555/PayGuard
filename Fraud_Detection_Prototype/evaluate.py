"""Evaluate frozen models on their untouched chronological test partition."""

import argparse
from pathlib import Path
import platform
import shutil
from time import perf_counter

import joblib
import numpy as np
import pandas as pd

from .common import DATA_PATH, check_versions, read_json, write_json
from .data import chronological_split, load_data, sha256
from .metrics import evaluate
from .reporting import comparison_table, plot_precision_recall, render_results


def benchmark(pipeline, frame: pd.DataFrame, features: list[str]) -> dict:
    for _ in range(5):
        pipeline.predict_proba(frame.iloc[:1][features])
    timings = []
    for _ in range(100):
        start = perf_counter()
        pipeline.predict_proba(frame.iloc[:1][features])
        timings.append((perf_counter() - start) * 1000)
    return {"p50_ms": float(np.percentile(timings, 50)),
            "p95_ms": float(np.percentile(timings, 95)), "repeats": 100,
            "platform": platform.platform(), "inference_workers": 1,
            "scope": "warm DataFrame selection, preprocessing and predict_proba; no I/O or network"}


def run(run_dir: Path, data_path: Path, output: Path) -> dict:
    if output.exists():
        raise FileExistsError(f"Evaluation directory must be new: {output}")
    manifest = read_json(run_dir / "manifest.json")
    check_versions(manifest["versions"])
    if sha256(data_path) != manifest["data"]["sha256"]:
        raise ValueError("Dataset fingerprint differs from the frozen training run")
    frame, _ = load_data(data_path)
    splits, _ = chronological_split(frame, manifest["boundaries"])
    test = splits["test"]
    features, policy = manifest["features"], manifest["policy"]
    predictions, metrics, models = {}, {}, {}
    for name, config in manifest["models"].items():
        # joblib is pickle-based; only evaluate locally created/trusted run artifacts.
        pipeline = joblib.load(run_dir / config["artifact"])
        models[name] = pipeline
        scores = pipeline.predict_proba(test[features])[:, 1]
        predictions[name] = scores
        cutoff = manifest["validation"][name]["threshold"]
        metrics[name] = evaluate(test.Class, scores, cutoff, policy["fp_cost"], policy["fn_cost"])
    metrics["always_legitimate"] = evaluate(
        test.Class, np.zeros(len(test)), 1., policy["fp_cost"], policy["fn_cost"])
    selected = manifest["selected_model"]
    latency = benchmark(models[selected], test, features)
    report = {"training_manifest_sha256": sha256(run_dir / "manifest.json"),
              "selected_model": selected, "test": metrics, "latency": latency}
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "report.json", report)
    comparison_table(manifest["validation"], metrics).to_csv(output / "comparison.csv", index=False)
    plot_precision_recall(test.Class, predictions, output / "test_pr.png")
    for filename in ("validation_pr.png", "training_audit.png"):
        shutil.copyfile(run_dir / filename, output / filename)
    (output / "RESULTS.md").write_text(render_results(manifest, metrics, latency), encoding="utf-8")
    print(f"Test report: {output}; frozen selection remains {selected}", flush=True)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--data", type=Path, default=DATA_PATH)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    run(args.run_dir, args.data, args.output_dir)


if __name__ == "__main__":
    main()
