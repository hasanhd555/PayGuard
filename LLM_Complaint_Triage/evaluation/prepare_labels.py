"""Reserve 20 distinct narratives for human labeling without using predictions."""

import argparse
import hashlib
import json
import random
from pathlib import Path

from ..pipeline.contracts import EvaluationCase
from ..pipeline.files import DEFAULT_SAMPLE, ROOT, checked_complaint, load_inputs, write_json


def select_cases(source=DEFAULT_SAMPLE, size=20, seed=42):
    unique = {}
    for identifier, values in load_inputs(source):
        complaint = checked_complaint(values)
        unique.setdefault(complaint.narrative.strip(), (identifier, complaint))
    if not 1 <= size <= len(unique):
        raise ValueError("Requested sample exceeds distinct narratives or is nonpositive")
    selected = random.Random(seed).sample(list(unique.values()), size)
    return [EvaluationCase(complaint_id=i, inputs=c) for i, c in selected]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_SAMPLE)
    parser.add_argument("--output", type=Path, default=ROOT / "evaluation/labels.jsonl")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--size", type=int, default=20)
    args = parser.parse_args()
    cases = select_cases(args.input, args.size, args.seed)
    manifest = args.output.with_suffix(".manifest.json")
    if args.output.exists() or manifest.exists():
        parser.error("Label output or manifest already exists; choose a new path to preserve annotations")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        for case in cases:
            write_json(handle, case)
    manifest.write_text(json.dumps({
        "source_filename": args.input.name,
        "source_sha256": hashlib.sha256(args.input.read_bytes()).hexdigest(),
        "seed": args.seed, "size": args.size,
        "method": "Uniform sample of distinct trimmed narratives; first source row per text",
        "complaint_ids": [c.complaint_id for c in cases],
        "narrative_sha256": [hashlib.sha256(c.inputs.narrative.encode()).hexdigest() for c in cases],
    }, indent=2) + "\n", encoding="utf-8")
    print(f"Prepared {len(cases)} cases with empty labels: {args.output}")


if __name__ == "__main__":
    main()
