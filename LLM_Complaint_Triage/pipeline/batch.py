"""Process a CFPB CSV or normalized JSONL, preserving one result per input row."""

import argparse
import asyncio
import sys
from collections import Counter
from pathlib import Path

from .files import DEFAULT_SAMPLE, ROOT, load_inputs, write_json
from .model_client import ConfigurationError, Settings, live_client, load_prices
from .triage import triage


async def run_batch(rows, client, handle):
    counts = Counter()
    for identifier, complaint in rows:
        result = await triage(complaint, client, identifier)
        write_json(handle, result)
        counts[result.status] += 1
    return counts


async def run(args):
    rows = load_inputs(args.input)
    if args.limit is not None:
        rows = rows[:args.limit]
    if args.output.exists():
        raise ValueError("Output already exists; choose a new output path")
    prices = load_prices(args.prices)
    async with live_client(settings=Settings.from_env(provider=args.provider), prices=prices) as client:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as handle:
            counts = await run_batch(rows, client, handle)
    print(f"Processed {sum(counts.values())} complaints: {dict(counts)}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_SAMPLE)
    parser.add_argument("--output", type=Path, default=ROOT / "runs/predictions.jsonl")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--provider", choices=["google", "groq"], help="Triage provider; screening always uses Gemini Decisions")
    parser.add_argument("--prices", type=Path, default=ROOT / "prices.json",
                        help="Dated per-model price JSON; missing or expired prices remain unknown")
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")
    try:
        asyncio.run(run(args))
    except (ConfigurationError, ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
