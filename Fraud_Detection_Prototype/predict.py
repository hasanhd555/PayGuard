"""Score new transactions using a saved model and its frozen review threshold."""

import argparse
from pathlib import Path

import joblib
import pandas as pd

from .common import check_versions, read_json
from .data import validate_features


def score(frame: pd.DataFrame, pipeline, features: list[str], threshold: float) -> pd.DataFrame:
    validate_features(frame, features)
    scores = pipeline.predict_proba(frame[features])[:, 1]
    return pd.DataFrame({"row_index": range(len(frame)), "fraud_score": scores,
                         "requires_review": scores >= threshold})


def run(run_dir: Path, input_path: Path, output: Path) -> pd.DataFrame:
    if output.exists():
        raise FileExistsError(f"Prediction output must be new: {output}")
    manifest = read_json(run_dir / "manifest.json")
    check_versions(manifest["versions"])
    selected = manifest["selected_model"]
    # Load only run artifacts you created or otherwise trust: joblib uses pickle.
    pipeline = joblib.load(run_dir / manifest["models"][selected]["artifact"])
    predictions = score(pd.read_csv(input_path), pipeline, manifest["features"],
                        manifest["validation"][selected]["threshold"])
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="") as handle:
        predictions.to_csv(handle, index=False)
    print(f"Scored {len(predictions):,} rows; {predictions.requires_review.sum():,} require review")
    return predictions


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.run_dir, args.input, args.output)


if __name__ == "__main__":
    main()
