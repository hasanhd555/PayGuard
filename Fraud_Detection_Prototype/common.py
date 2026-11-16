"""Small local helpers; this package has no dependency on Part B."""

import importlib.metadata
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FEATURES = [f"V{i}" for i in range(1, 29)] + ["Amount"]
DATA_PATH = ROOT / "data" / "creditcard.csv"
SEED = 42


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def versions() -> dict:
    return {name: importlib.metadata.version(name)
            for name in ("numpy", "pandas", "scikit-learn", "joblib", "matplotlib")}


def check_versions(expected: dict) -> None:
    actual = versions()
    if actual != expected:
        raise ValueError(f"Artifact dependency versions differ: expected {expected}; got {actual}")
