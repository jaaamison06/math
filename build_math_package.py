#!/usr/bin/env python3
"""
Build script to generate Stake Math SDK package files for Full Court Fortune.
Produces:
- math/_index.json
- math/full_court_base.jsonl.zst
- math/full_court_bonus.jsonl.zst
- math/lookup_base.csv
- math/lookup_bonus.csv

Conforms to https://stakeengine.github.io/math-sdk/rgs_docs/data_format/
Key fields per round: id, events, payoutMultiplier (integer, in multiplier x100?)
"""

import csv
import os
import random
import json
from dataclasses import dataclass
from typing import List, Dict
import zstandard as zstd

# Simple model: discrete outcomes with integer payoutMultiplier
# Note: payoutMultiplier must be uint64 per CSV; we will emit ints.

@dataclass
class Outcome:
    id: int
    probability_ppm: int  # probability scaled to parts-per-million for integer math
    payout_multiplier: int  # integer multiplier (e.g., 0, 10, 15, 25, 5000)


def ensure_dir(path: str) -> None:
    if not os.path.isdir(path):
        os.makedirs(path, exist_ok=True)


def write_csv(path: str, outcomes: List[Outcome]) -> None:
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        # CSV format: simulation number, round probability, payout multiplier
        for oc in outcomes:
            writer.writerow([oc.id, oc.probability_ppm, oc.payout_multiplier])


def write_jsonl_zst(path: str, outcomes: List[Outcome]) -> None:
    compressor = zstd.ZstdCompressor(level=10)
    with open(path, "wb") as f:
        with compressor.stream_writer(f) as out:
            for oc in outcomes:
                round_doc = {
                    "id": oc.id,
                    "events": [{}],  # minimal required list
                    "payoutMultiplier": int(oc.payout_multiplier),
                }
                line = json.dumps(round_doc, separators=(",", ":")) + "\n"
                out.write(line.encode("utf-8"))


def normalize_probabilities(raw: Dict[int, float]) -> List[Outcome]:
    # raw: multiplier -> probability (float)
    total = sum(raw.values())
    outcomes: List[Outcome] = []
    for idx, (mult, p) in enumerate(sorted(raw.items()), start=1):
        ppm = int(round((p / total) * 1_000_000))
        outcomes.append(Outcome(id=idx, probability_ppm=max(ppm, 0), payout_multiplier=int(mult)))
    # Fix rounding to ensure sum ppm == 1_000_000
    diff = 1_000_000 - sum(o.probability_ppm for o in outcomes)
    if diff != 0 and outcomes:
        outcomes[-1].probability_ppm += diff
    return outcomes


def build_base_mode() -> List[Outcome]:
    # Example distribution matching earlier UI copy: base 25% win @10x; 5% bonus triggers are handled as separate mode.
    # Here base table represents payout multipliers for base play only. Use mostly 0 and some 10.
    raw = {
        0: 0.75,
        10: 0.25,
    }
    return normalize_probabilities(raw)


def build_bonus_mode() -> List[Outcome]:
    # Bonus mode: higher win rate, with 15x/25x and rare 5000x jackpot.
    raw = {
        0: 0.60,
        15: 0.28,
        25: 0.119,  # leaves 0.001 for jackpot
        5000: 0.001,
    }
    return normalize_probabilities(raw)


def main() -> None:
    root = os.path.abspath(os.path.dirname(__file__))
    math_dir = os.path.join(root, "math")
    ensure_dir(math_dir)

    base = build_base_mode()
    bonus = build_bonus_mode()

    write_csv(os.path.join(math_dir, "lookup_base.csv"), base)
    write_csv(os.path.join(math_dir, "lookup_bonus.csv"), bonus)

    write_jsonl_zst(os.path.join(math_dir, "full_court_base.jsonl.zst"), base)
    write_jsonl_zst(os.path.join(math_dir, "full_court_bonus.jsonl.zst"), bonus)

    # _index.json is authored separately; ensure it exists
    index_path = os.path.join(math_dir, "_index.json")
    if not os.path.isfile(index_path):
        with open(index_path, "w") as f:
            json.dump({
                "modes": [
                    {"name": "base", "cost": 1.0, "events": "full_court_base.jsonl.zst", "weights": "lookup_base.csv"},
                    {"name": "bonus", "cost": 100.0, "events": "full_court_bonus.jsonl.zst", "weights": "lookup_bonus.csv"},
                ]
            }, f, indent=2)

    print("Math package generated in ./math per data_format docs")

if __name__ == "__main__":
    main()
