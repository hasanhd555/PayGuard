"""Explicit CSV/JSONL boundaries; only five complaint fields enter prompts."""

import csv
import hashlib
import json
from pathlib import Path

from .contracts import Complaint

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
DEFAULT_SAMPLE = ROOT / "data/complaints_sample_500.csv"
FIELD_NAMES = {
    "narrative": "Consumer complaint narrative", "product": "Product",
    "sub_product": "Sub-product", "issue": "Issue", "sub_issue": "Sub-issue",
}


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def read_jsonl(path):
    with Path(path).open(encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, 1):
            if line.strip():
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Invalid JSON at {path}:{line_number}") from exc


def load_inputs(path):
    """Read fully before spending tokens; reject missing/duplicate identifiers."""
    path = Path(path)
    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not {"Complaint ID", FIELD_NAMES["narrative"]}.issubset(reader.fieldnames or []):
                raise ValueError("CSV requires Complaint ID and Consumer complaint narrative")
            rows = []
            for row in reader:
                if None in row or any(v is None for v in row.values()):
                    raise ValueError("Malformed CSV row: inconsistent column count")
                rows.append((row["Complaint ID"], {k: row.get(v) for k, v in FIELD_NAMES.items()}))
    else:
        rows = []
        for row in read_jsonl(path):
            if not isinstance(row, dict):
                raise ValueError("JSONL rows must be objects")
            inputs = row.get("inputs", {k: row[k] for k in FIELD_NAMES if k in row})
            rows.append((row.get("complaint_id"), inputs))
    seen = set()
    for identifier, _ in rows:
        if not isinstance(identifier, str) or not identifier.strip() or identifier in seen:
            raise ValueError("Complaint IDs must be nonempty unique strings")
        seen.add(identifier)
    return rows


def write_json(handle, value):
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    handle.write(json.dumps(value, ensure_ascii=False) + "\n")
    handle.flush()


def checked_complaint(value):
    return value if isinstance(value, Complaint) else Complaint.model_validate(value)
