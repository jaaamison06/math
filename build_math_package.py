#!/usr/bin/env python3
"""
Build script to generate Stake Math SDK package files for Full Court Fortune.
Produces:
- math/_index.json
- math/full_court_base.jsonl.zst
- math/lookup_base.csv

Conforms to https://stakeengine.github.io/math-sdk/rgs_docs/data_format/
Key fields per round: id, events, payoutMultiplier (integer)

This version generates EXACTLY 5000 outcomes with:
- 1-in-1,000,000 chance of 5000x (jackpot)
- Equal probability distribution across the remaining 4,999 outcomes
- Majority of spins are losses (0x outcomes > 50% probability)
- Target RTP of 94% (exactly 0.94 expected multiplier)
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


def build_5000_outcomes(target_rtp: float = 0.94) -> List[Outcome]:
    """Construct exactly 5000 outcomes meeting the constraints:
    - Jackpot: 1 ppm at 5000x (exact 1-in-1,000,000)
    - Remaining 4,999 outcomes share 999,999 ppm as equally as possible
    - Majority losses via 0x outcomes
    - Overall RTP equals target_rtp exactly

    Strategy:
    - Set K0 = 3000 zero-multiplier outcomes (losses) among the 4,999
      -> Loss probability = 3000 * 200 ppm = 600,000 ppm (> 50%)
    - The remaining K1 = 1,999 outcomes are wins at 2x or 3x
    - Distribute the 999,999 ppm: each of the 4,999 outcomes gets 200 ppm, and 199 get +1 ppm to account for remainder
      We assign all +1 ppm extras to win outcomes for finer EV control
    - Solve integers so that the exact EV from non-jackpot outcomes is 0.935 (935,000 ppm-mult total)
      Let W_total_ppm = 399,999 (all winning outcomes' ppm sum)
      We choose counts (x at 3x with 201 ppm, y at 3x with 200 ppm) so that 201*x + 200*y = 135,002,
      which yields x=2, y=673. The rest of winners are 2x.
    """

    total_outcomes = 5000
    others = total_outcomes - 1  # excluding jackpot

    jackpot_ppm = 1
    jackpot_multiplier = 5000

    # Equal distribution across remaining outcomes: 999,999 ppm across 4,999 ids
    base_ppm = 200  # floor(999,999 / 4,999)
    remainder = 999_999 - others * base_ppm  # 199

    # Set majority losses: pick K0 zeros
    K0 = 3000
    K1 = others - K0  # 1,999 winners

    # Allocate +1 ppm extras to winners to maximize EV control
    extra_ppm_for_winners = min(remainder, K1)  # 199
    extra_ppm_for_zeros = remainder - extra_ppm_for_winners  # 0

    # Winning ppm sum
    winners_ppm_sum = K1 * base_ppm + extra_ppm_for_winners  # 399,999

    # Target EV contributions in ppm-mult units
    target_total_ev = int(round(target_rtp * 1_000_000))  # 940,000
    jackpot_ev = jackpot_ppm * jackpot_multiplier  # 5,000
    others_target_ev = target_total_ev - jackpot_ev  # 935,000

    # We will use only 2x and 3x for winners. Let S3 be total ppm at 3x.
    # Then EV_others = 2 * winners_ppm_sum + S3 must equal others_target_ev.
    # Solve S3 exactly.
    S3 = others_target_ev - 2 * winners_ppm_sum  # 135,002 ppm must be at 3x
    if S3 < 0 or S3 > winners_ppm_sum:
        raise ValueError("Invalid configuration for winners' ppm split")

    # Count outcomes with 201 ppm (only winners get these extras): x=2 of them are 3x; rest 2x
    winners_201_count = extra_ppm_for_winners  # 199
    # Solve 201*x + 200*y = S3 with constraints x <= winners_201_count, y <= (K1 - winners_201_count)
    # From congruence, x ≡ S3 (mod 200). Pick minimal feasible x.
    x_3x_201 = S3 % 200
    # Clamp x to available 201-ppm winners by adding/subtracting 200 if needed
    while x_3x_201 > winners_201_count:
        x_3x_201 -= 200
    # Ensure non-negative
    while x_3x_201 < 0:
        x_3x_201 += 200
    # Compute y from remaining ppm
    remaining_ppm_for_3x = S3 - 201 * x_3x_201
    if remaining_ppm_for_3x % 200 != 0:
        raise ValueError("No integer solution for 3x allocation")
    y_3x_200 = remaining_ppm_for_3x // 200
    if y_3x_200 < 0 or y_3x_200 > (K1 - winners_201_count):
        raise ValueError("3x 200ppm allocation exceeds available winners")

    # Build outcomes deterministically:
    outcomes: List[Outcome] = []

    # First, 4,999 non-jackpot outcomes
    current_id = 1
    zeros_to_make = K0
    winners_to_make = K1
    winners_201_left = winners_201_count
    x_left = x_3x_201
    y_left = y_3x_200

    # We will create in order: zeros (all 200 ppm), then winners with 201 ppm, then winners with 200 ppm
    # 1) Zeros
    for _ in range(zeros_to_make):
        outcomes.append(Outcome(id=current_id, probability_ppm=base_ppm, payout_multiplier=0))
        current_id += 1

    # 2) Winners with 201 ppm (first x_left are 3x, rest 2x)
    for i in range(winners_201_left):
        mult = 3 if i < x_left else 2
        outcomes.append(Outcome(id=current_id, probability_ppm=base_ppm + 1, payout_multiplier=mult))
        current_id += 1

    # 3) Winners with 200 ppm (first y_left are 3x, rest 2x)
    for j in range(winners_to_make - winners_201_left):
        mult = 3 if j < y_left else 2
        outcomes.append(Outcome(id=current_id, probability_ppm=base_ppm, payout_multiplier=mult))
        current_id += 1

    # Sanity checks for 4,999 generated outcomes
    assert len(outcomes) == others, f"Expected {others} non-jackpot outcomes, got {len(outcomes)}"
    assert sum(o.probability_ppm for o in outcomes) == 999_999, "Non-jackpot ppm must sum to 999,999"

    # Append jackpot as the 5,000th outcome
    outcomes.append(Outcome(id=current_id, probability_ppm=jackpot_ppm, payout_multiplier=jackpot_multiplier))

    # Final checks
    total_ppm = sum(o.probability_ppm for o in outcomes)
    assert total_ppm == 1_000_000, f"Total ppm must be 1,000,000, got {total_ppm}"
    total_ev = sum(o.probability_ppm * o.payout_multiplier for o in outcomes)
    assert total_ev == target_total_ev, f"EV ppm*mult must be {target_total_ev}, got {total_ev}"

    # Majority losses
    loss_ppm = sum(o.probability_ppm for o in outcomes if o.payout_multiplier == 0)
    assert loss_ppm > 500_000, "Loss probability must be a majority (> 50%)"

    return outcomes


def build_bonus_mode() -> List[Outcome]:
    # Retained for reference; not used in this 5000-outcome build
    raw = {
        0: 0.60,
        15: 0.28,
        25: 0.119,
        5000: 0.001,
    }
    return normalize_probabilities(raw)


def main() -> None:
    root = os.path.abspath(os.path.dirname(__file__))
    math_dir = os.path.join(root, "math")
    ensure_dir(math_dir)

    # Build the 5000-outcome table and emit files for base mode only
    base = build_5000_outcomes(target_rtp=0.94)

    write_csv(os.path.join(math_dir, "lookup_base.csv"), base)
    write_jsonl_zst(os.path.join(math_dir, "full_court_base.jsonl.zst"), base)

    # Always (re)write a minimal index describing the base mode
    index_path = os.path.join(math_dir, "_index.json")
    with open(index_path, "w") as f:
        json.dump({
            "modes": [
                {"name": "base", "cost": 1.0, "events": "full_court_base.jsonl.zst", "weights": "lookup_base.csv"}
            ]
        }, f, indent=2)

    print("Math package generated in ./math per data_format docs")

if __name__ == "__main__":
    main()
