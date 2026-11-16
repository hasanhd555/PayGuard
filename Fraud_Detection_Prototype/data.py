"""Explicit download, schema checks, duplicate audit and chronological partitions."""

import argparse
import hashlib
from pathlib import Path
import shutil
import urllib.request

import numpy as np
import pandas as pd
from pandas.api.types import is_numeric_dtype

from .common import DATA_PATH, FEATURES, write_json

COLUMNS = ["Time", *FEATURES, "Class"]
SOURCE_URL = "https://storage.googleapis.com/download.tensorflow.org/data/creditcard.csv"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_features(frame: pd.DataFrame, columns=FEATURES) -> None:
    if frame.empty:
        raise ValueError("Supply at least one transaction")
    missing = set(columns) - set(frame.columns)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")
    if not all(is_numeric_dtype(frame[col]) for col in columns):
        raise ValueError("Required columns must be numeric")
    if not np.isfinite(frame[list(columns)].to_numpy(dtype=float)).all():
        raise ValueError("Required columns must contain only finite values; no missing values allowed")
    if (frame.Amount < 0).any():
        raise ValueError("Amount must be nonnegative")


def load_data(path: Path) -> tuple[pd.DataFrame, dict]:
    frame = pd.read_csv(path)
    if set(frame.columns) != set(COLUMNS) or len(frame.columns) != len(COLUMNS):
        raise ValueError(f"Expected exactly these columns: {COLUMNS}")
    validate_features(frame, COLUMNS)
    if not frame.Class.isin([0, 1]).all() or frame.Class.nunique() != 2:
        raise ValueError("Class must contain both binary labels 0 and 1")
    if (frame.Time < 0).any():
        raise ValueError("Time must be nonnegative")
    audit = {"sha256": sha256(path), "source_rows": len(frame),
             "source_frauds": int(frame.Class.sum()),
             "dtypes": {key: str(value) for key, value in frame.dtypes.items()},
             "missing_values": {key: int(value) for key, value in frame.isna().sum().items()}}
    # No transaction IDs exist. Removing exact full-row repeats is an explicit
    # prototype assumption, not proof that every repeat is an ingestion error.
    cleaned = frame.drop_duplicates(subset=COLUMNS).sort_values("Time", kind="stable")
    cleaned = cleaned.reset_index(drop=True)
    cleaned["Class"] = cleaned.Class.astype(int)
    audit["exact_duplicates_removed"] = len(frame) - len(cleaned)
    audit["rows_after_deduplication"] = len(cleaned)
    return cleaned, audit


def chronological_split(frame: pd.DataFrame, boundaries=None) -> tuple[dict, dict]:
    frame = frame.sort_values("Time", kind="stable").reset_index(drop=True)
    if len(frame) < 10:
        raise ValueError("At least ten transactions required")
    if boundaries is None:
        boundaries = {"validation_start": float(frame.Time.iloc[int(len(frame) * .6)]),
                      "test_start": float(frame.Time.iloc[int(len(frame) * .8)])}
    first, second = boundaries["validation_start"], boundaries["test_start"]
    splits = {"train": frame[frame.Time < first].copy(),
              "validation": frame[(frame.Time >= first) & (frame.Time < second)].copy(),
              "test": frame[frame.Time >= second].copy()}
    for name, part in splits.items():
        if part.empty or part.Class.nunique() != 2:
            raise ValueError(f"{name} partition needs both classes; no random-split fallback")
    return splits, boundaries


def split_audit(splits: dict) -> dict:
    result, seen = {}, set()
    for name, part in splits.items():
        hashes = pd.util.hash_pandas_object(part[FEATURES], index=False)
        result[name] = {"rows": len(part), "frauds": int(part.Class.sum()),
                        "prevalence": float(part.Class.mean()),
                        "time_min": float(part.Time.min()), "time_max": float(part.Time.max()),
                        "feature_rows_seen_in_earlier_split": int(hashes.isin(seen).sum())}
        seen.update(hashes.tolist())
    return result


def download(output: Path) -> dict:
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite dataset: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".download")
    # Exclusive creation also prevents concurrent downloads sharing a partial file.
    target = temporary.open("xb")
    try:
        with target:
            with urllib.request.urlopen(SOURCE_URL, timeout=120) as response:
                shutil.copyfileobj(response, target)
        _, audit = load_data(temporary)
        temporary.replace(output)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    write_json(output.with_suffix(".source.json"), {"source_url": SOURCE_URL, **audit})
    return audit


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DATA_PATH)
    args = parser.parse_args()
    print(f"Downloading {SOURCE_URL}", flush=True)
    audit = download(args.output)
    print(f"Saved {args.output}; {audit['source_rows']:,} rows; SHA-256 {audit['sha256']}")


if __name__ == "__main__":
    main()
