"""Reproducibly sample narrative-bearing CFPB complaints and audit their mix.

Uses only the Python standard library. Run from any working directory.
"""

import argparse
import csv
import hashlib
import json
import math
import random
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "data/CCDB_Export_13_September_2025_through_October_2025.csv"
NARRATIVE = "Consumer complaint narrative"
DIMENSIONS = (
    "Product", "Sub-product", "Issue", "Company", "State", "Submitted via",
    "Tags", "Company response to consumer", "Received month", "Narrative length",
)


def digest(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def new_profile():
    return {
        "rows": 0,
        "with_narrative": 0,
        "date_min": None,
        "date_max": None,
        "dimensions": {name: Counter() for name in DIMENSIONS},
    }


def observe(profile, row):
    profile["rows"] += 1
    narrative = row[NARRATIVE].strip()
    profile["with_narrative"] += bool(narrative)
    date = row["Date received"].strip()
    if date:
        # This export uses ISO YYYY-MM-DD dates, so lexical order is date order.
        profile["date_min"] = min(profile["date_min"] or date, date)
        profile["date_max"] = max(profile["date_max"] or date, date)
    length = len(narrative)
    bucket = (
        "0 (blank)" if not length else "1-249" if length < 250 else
        "250-999" if length < 1000 else "1000-2999" if length < 3000 else "3000+"
    )
    for name in DIMENSIONS:
        value = date[:7] if name == "Received month" else (
            bucket if name == "Narrative length" else row[name].strip()
        )
        profile["dimensions"][name][value or "(missing)"] += 1


def comparison(reference, sample, name):
    ref_counts = reference["dimensions"][name]
    sample_counts = sample["dimensions"][name]
    values = sorted(set(ref_counts) | set(sample_counts))
    entries = []
    for value in values:
        p = ref_counts[value] / reference["rows"]
        q = sample_counts[value] / sample["rows"]
        entries.append({
            "value": value,
            "reference_count": ref_counts[value],
            "sample_count": sample_counts[value],
            "reference_pct": round(100 * p, 4),
            "sample_pct": round(100 * q, 4),
            "difference_pp": round(100 * (q - p), 4),
        })
    entries.sort(key=lambda entry: (-abs(entry["difference_pp"]), entry["value"]))
    return {
        "reference_unique": len(ref_counts),
        "sample_unique": len(sample_counts),
        "total_variation_distance": round(sum(
            abs(ref_counts[v] / reference["rows"] - sample_counts[v] / sample["rows"])
            for v in values
        ) / 2, 6),
        "missing_reference_values": sorted(set(ref_counts) - set(sample_counts)),
        "values": entries,
    }


def cell(value):
    return str(value).replace("|", "\\|").replace("\n", " ")


def table(profiles, name, limit):
    # Show the largest values across all three populations, including sample leaders.
    values = set()
    for profile in profiles.values():
        values.update(v for v, _ in profile["dimensions"][name].most_common(limit))
    values = sorted(values, key=lambda v: (
        -profiles["eligible"]["dimensions"][name][v], v
    ))
    lines = [
        "| Value | Full export n (%) | Eligible n (%) | Sample n (%) | Sample - eligible (pp) |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for value in values:
        counts = [p["dimensions"][name][value] for p in profiles.values()]
        shares = [100 * n / p["rows"] for n, p in zip(counts, profiles.values())]
        cells = [f"{n:,} ({pct:.2f}%)" for n, pct in zip(counts, shares)]
        lines.append(f"| {cell(value)} | " + " | ".join(cells) +
                     f" | {shares[2] - shares[1]:+.2f} |")
    return lines


def markdown(report):
    profiles = report["profiles"]
    full, eligible, sample = profiles.values()
    method = report["sampling"]
    lines = [
        "# Complaint slice audit", "",
        f"Source: `{report['source']['filename']}`. Source SHA-256: `{report['source']['sha256']}`.",
        f"Sample SHA-256: `{report['sample']['sha256']}`.", "",
        f"Uniform reservoir sample without replacement; seed **{method['seed']}**; "
        f"**{sample['rows']:,} records**. Eligibility: narrative is nonempty after stripping "
        "whitespace. No category, company, date, length, or outcome filter; no balancing, "
        "deduplication, or rerolling. All original columns and cell values are preserved; "
        "selected rows are written in source order.", "",
        f"Full export: **{full['rows']:,}** rows. Narrative-eligible: **{eligible['rows']:,}** "
        f"(**{100 * eligible['rows'] / full['rows']:.2f}%**); excluded blank narratives: "
        f"**{full['rows'] - eligible['rows']:,}**.", "",
        f"Observed received dates: full export **{full['date_min']} to {full['date_max']}**; "
        f"eligible **{eligible['date_min']} to {eligible['date_max']}**; "
        f"sample **{sample['date_min']} to {sample['date_max']}**. "
        "These are received dates, which need not match the archive filename's period.", "",
        "## Findings", "",
    ]
    for name in ("Product", "Company"):
        counts = sample["dimensions"][name]
        leader, count = counts.most_common(1)[0]
        top_three = sum(n for _, n in counts.most_common(3))
        audit = report["eligible_vs_sample"][name]
        lines.append(
            f"- {name}: sample covers **{len(counts)} of {audit['reference_unique']}** "
            f"eligible values. Largest: **{leader}**, {count}/{sample['rows']} "
            f"(**{100 * count / sample['rows']:.2f}%**); top three share "
            f"**{100 * top_three / sample['rows']:.2f}%**. "
            f"Total variation distance from eligible data: "
            f"**{audit['total_variation_distance']:.4f}**."
        )
        missing = audit["missing_reference_values"]
        if missing and name == "Product":
            lines.append("- Products absent from this sample: " + "; ".join(missing) + ".")
        differences = [v for v in audit["values"] if abs(v["difference_pp"]) >= 5]
        if differences:
            lines.append(f"- {name} sampling differences of at least 5 percentage points: " +
                         "; ".join(f"{v['value']} ({v['difference_pp']:+.2f} pp)"
                                   for v in differences) + ".")
        else:
            lines.append(f"- No individual {name.lower()} differs from its eligible share "
                         "by 5 percentage points or more.")
    quality = report["quality"]
    lines.extend([
        f"- Duplicate Complaint IDs: eligible **{quality['eligible_duplicate_ids']}**, "
        f"sample **{quality['sample_duplicate_ids']}**. Repeated exact narrative texts "
        f"after whitespace trimming (extra rows beyond first occurrence): eligible "
        f"**{quality['eligible_repeated_narratives']}**, sample "
        f"**{quality['sample_repeated_narratives']}** "
        f"(**{100 * quality['sample_repeated_narratives'] / sample['rows']:.2f}%** "
        "of sample rows). No duplicates were removed.", "",
        "Repeated narratives reduce text diversity and can cause leakage if later "
        "evaluation splits place the same text in different sets. This audit counts exact "
        "matches after trimming only; it does not detect near-duplicates.", "",
        "A random slice can faithfully inherit substantial source concentration. Compare "
        "full-export versus eligible shares below to see selection associated with narrative "
        "availability, and eligible versus sample shares to see sampling variation. "
        "The 5-point flag is descriptive, not a significance test or a pass/fail criterion. "
        "At n=500 the worst-case approximate 95% margin for a single random-sample share "
        f"is +/-{100 * 1.96 * math.sqrt(0.25 / sample['rows']):.2f} percentage points "
        "(before finite-population correction). Many rare values will be absent, especially "
        "companies; this does not establish coverage of all routing or sensitive-case types.", "",
        "This audit assesses observed mix within this export, not representativeness of all "
        "CFPB complaints or PayGuard customers. Narrative availability and the archive window "
        "limit that inference. Product and Issue are existing metadata, not validated triage "
        "labels. No LLM triage or manual correctness evaluation was performed.", "",
    ])
    for name, limit in (("Product", 100), ("Company", 10), ("Issue", 10),
                        ("Received month", 100), ("State", 10),
                        ("Submitted via", 100), ("Narrative length", 100)):
        lines.extend([f"## {name}", ""] + table(profiles, name, limit) + [""])
    lines.extend([
        "Company, Issue, and State tables show the union of the top ten values in each "
        "population. The JSON report includes complete counts and comparisons for every "
        "dimension, including Sub-product, Tags, and Company response to consumer.", "",
    ])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=ROOT / "data/complaints_sample_500.csv")
    parser.add_argument("--report-prefix", type=Path, default=ROOT / "data/sample_profile")
    parser.add_argument("--size", type=int, default=500)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    if args.size < 1:
        parser.error("--size must be positive")
    targets = [args.output, args.report_prefix.with_suffix(".json"),
               args.report_prefix.with_suffix(".md")]
    paths = [args.input.resolve()] + [path.resolve() for path in targets]
    if len(set(paths)) != len(paths):
        parser.error("input, output, and report paths must all be different")

    # Allow long narratives without depending on platform-specific C integer limits.
    csv.field_size_limit(2**31 - 1)
    rng = random.Random(args.seed)
    profiles = {name: new_profile() for name in ("full_export", "eligible", "sample")}
    full, eligible, sample = profiles.values()
    reservoir = []
    eligible_ids = set()
    narrative_hashes = set()
    duplicate_ids = repeated_narratives = 0
    source_sha256 = digest(args.input)
    with args.input.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames
        required = {NARRATIVE, "Complaint ID", "Date received"} | set(DIMENSIONS[:-2])
        if fields is None or not required.issubset(fields):
            parser.error(f"missing required CSV columns: {sorted(required - set(fields or []))}")
        for index, row in enumerate(reader):
            if None in row or any(value is None for value in row.values()):
                parser.error(f"malformed CSV record {index + 1}: column count mismatch")
            observe(full, row)
            text = row[NARRATIVE].strip()
            if not text:
                continue
            if not row["Complaint ID"].strip():
                parser.error(f"eligible record {index + 1} has no Complaint ID")
            observe(eligible, row)
            identifier = row["Complaint ID"]
            duplicate_ids += identifier in eligible_ids
            eligible_ids.add(identifier)
            narrative_hash = hashlib.sha256(text.encode("utf-8")).digest()
            repeated_narratives += narrative_hash in narrative_hashes
            narrative_hashes.add(narrative_hash)
            # Algorithm R: each eligible row has the same size / eligible_rows chance.
            if len(reservoir) < args.size:
                reservoir.append((index, row))
            else:
                slot = rng.randrange(eligible["rows"])
                if slot < args.size:
                    reservoir[slot] = (index, row)
    if eligible["rows"] < args.size:
        parser.error(f"requested {args.size} rows but only {eligible['rows']} have narratives")
    selected = [row for _, row in sorted(reservoir)]
    for row in selected:
        observe(sample, row)
    for path in targets:
        path.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(selected)
    report = {
        "source": {"filename": args.input.name, "sha256": source_sha256},
        "sample": {"filename": args.output.name, "sha256": digest(args.output)},
        "sampling": {
            "algorithm": "Algorithm R reservoir sampling without replacement",
            "seed": args.seed, "size": args.size,
            "eligibility": "Consumer complaint narrative.strip() is nonempty",
            "ordering": "CSV source record order; selected records emitted in source order",
            "python_version": sys.version.split()[0],
        },
        "quality": {
            "eligible_duplicate_ids": duplicate_ids,
            "sample_duplicate_ids": len(selected) - len({r["Complaint ID"] for r in selected}),
            "eligible_repeated_narratives": repeated_narratives,
            "sample_repeated_narratives": len(selected) - len({r[NARRATIVE].strip() for r in selected}),
        },
        "profiles": profiles,
        "eligible_vs_sample": {name: comparison(eligible, sample, name) for name in DIMENSIONS},
        "full_export_vs_eligible": {name: comparison(full, eligible, name) for name in DIMENSIONS},
    }
    targets[1].write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
                          encoding="utf-8")
    targets[2].write_text(markdown(report), encoding="utf-8")
    print(f"Wrote {sample['rows']} complaints from {eligible['rows']:,} eligible / {full['rows']:,} total.")
    for path in targets:
        print(path)


if __name__ == "__main__":
    main()
