#!/usr/bin/env python3
"""
RTP Simulation Script for Full Court Fortune
Tests the accuracy of the generated 5000-outcome tables with 1 million spins
"""

import csv
import random
import json
from typing import List, Dict, Tuple
from dataclasses import dataclass

@dataclass
class Outcome:
    id: int
    probability_ppm: int
    payout_multiplier: int

def load_lookup_table(csv_path: str) -> List[Outcome]:
    """Load outcomes from CSV lookup table"""
    outcomes = []
    with open(csv_path, 'r') as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) >= 3:
                outcomes.append(Outcome(
                    id=int(row[0]),
                    probability_ppm=int(row[1]),
                    payout_multiplier=int(row[2])
                ))
    return outcomes

def simulate_spins(outcomes: List[Outcome], num_spins: int = 1_000_000) -> Dict:
    """Simulate spins using the lookup table"""
    # Create weighted random selection
    total_ppm = sum(o.probability_ppm for o in outcomes)
    
    # Build cumulative distribution for efficient random selection
    cumulative_ppm = 0
    cumulative_dist = []
    for outcome in outcomes:
        cumulative_ppm += outcome.probability_ppm
        cumulative_dist.append((cumulative_ppm, outcome))
    
    # Simulation results
    total_bet = 0.0
    total_winnings = 0.0
    outcome_counts = {}
    max_win = 0.0
    max_multiplier = 0.0
    
    # Track jackpot hits
    jackpot_hits = 0
    
    print(f"Simulating {num_spins:,} spins...")
    
    for spin in range(num_spins):
        # Generate random number
        random_value = random.random() * total_ppm
        
        # Find selected outcome using binary search
        left, right = 0, len(cumulative_dist) - 1
        selected_outcome = None
        
        while left <= right:
            mid = (left + right) // 2
            if random_value <= cumulative_dist[mid][0]:
                selected_outcome = cumulative_dist[mid][1]
                right = mid - 1
            else:
                left = mid + 1
        
        if selected_outcome is None:
            selected_outcome = cumulative_dist[-1][1]  # Fallback
        
        # Simulate bet amount (using $1 for simplicity)
        bet_amount = 1.0
        total_bet += bet_amount
        
        # Calculate winnings
        winnings = bet_amount * selected_outcome.payout_multiplier
        total_winnings += winnings
        
        # Track statistics
        outcome_id = selected_outcome.id
        outcome_counts[outcome_id] = outcome_counts.get(outcome_id, 0) + 1
        
        if winnings > max_win:
            max_win = winnings
        if selected_outcome.payout_multiplier > max_multiplier:
            max_multiplier = selected_outcome.payout_multiplier
            
        # Track jackpot hits
        if selected_outcome.payout_multiplier == 5000:
            jackpot_hits += 1
            
        # Progress indicator
        if spin % 100_000 == 0 and spin > 0:
            current_rtp = (total_winnings / total_bet) * 100
            print(f"  {spin:,} spins completed - Current RTP: {current_rtp:.4f}%")
    
    # Calculate final RTP (as decimal, not percentage)
    rtp = (total_winnings / total_bet) if total_bet > 0 else 0.0
    
    return {
        "total_spins": num_spins,
        "total_bet": total_bet,
        "total_winnings": total_winnings,
        "rtp_decimal": rtp,
        "max_win": max_win,
        "max_multiplier": max_multiplier,
        "jackpot_hits": jackpot_hits,
        "jackpot_rate": jackpot_hits / num_spins,
        "expected_jackpot_rate": 1 / 1_000_000,
        "outcome_counts": outcome_counts
    }

def analyze_outcomes(outcomes: List[Outcome]) -> Dict:
    """Analyze the theoretical properties of the outcome table"""
    total_ppm = sum(o.probability_ppm for o in outcomes)
    theoretical_rtp = sum(o.probability_ppm * o.payout_multiplier for o in outcomes) / total_ppm
    
    # Count outcomes by multiplier
    multiplier_counts = {}
    for outcome in outcomes:
        mult = outcome.payout_multiplier
        multiplier_counts[mult] = multiplier_counts.get(mult, 0) + 1
    
    # Find jackpot
    jackpot_outcome = None
    for outcome in outcomes:
        if outcome.payout_multiplier == 5000:
            jackpot_outcome = outcome
            break
    
    return {
        "total_outcomes": len(outcomes),
        "total_ppm": total_ppm,
        "theoretical_rtp": theoretical_rtp,
        "theoretical_rtp_percentage": theoretical_rtp * 100,
        "multiplier_counts": multiplier_counts,
        "jackpot_ppm": jackpot_outcome.probability_ppm if jackpot_outcome else 0,
        "jackpot_probability": jackpot_outcome.probability_ppm / total_ppm if jackpot_outcome else 0
    }

def main():
    print("=== Full Court Fortune RTP Simulation ===\n")
    
    # Test both base and bonus modes
    modes = ["base", "bonus"]
    
    for mode in modes:
        print(f"\n--- {mode.upper()} MODE ---")
        
        # Load lookup table
        csv_path = f"math/lookup_{mode}.csv"
        outcomes = load_lookup_table(csv_path)
        print(f"Loaded {len(outcomes)} outcomes from {csv_path}")
        
        # Analyze theoretical properties
        analysis = analyze_outcomes(outcomes)
        print(f"\nTheoretical Analysis:")
        print(f"  Total outcomes: {analysis['total_outcomes']}")
        print(f"  Total ppm: {analysis['total_ppm']:,}")
        print(f"  Theoretical RTP: {analysis['theoretical_rtp_percentage']:.4f}%")
        print(f"  Jackpot probability: {analysis['jackpot_probability']:.8f} (1 in {1/analysis['jackpot_probability']:,.0f})")
        
        # Simulate 1 million spins
        simulation_results = simulate_spins(outcomes, 1_000_000)
        
        print(f"\nSimulation Results (1M spins):")
        print(f"  Total bet: ${simulation_results['total_bet']:,.2f}")
        print(f"  Total winnings: ${simulation_results['total_winnings']:,.2f}")
        print(f"  Actual RTP: {simulation_results['rtp_decimal'] * 100:.4f}%")
        print(f"  RTP Difference: {(simulation_results['rtp_decimal'] - analysis['theoretical_rtp']) * 100:.4f}%")
        print(f"  Max win: ${simulation_results['max_win']:,.2f}")
        print(f"  Max multiplier: {simulation_results['max_multiplier']}x")
        print(f"  Jackpot hits: {simulation_results['jackpot_hits']}")
        print(f"  Actual jackpot rate: {simulation_results['jackpot_rate']:.8f}")
        print(f"  Expected jackpot rate: {simulation_results['expected_jackpot_rate']:.8f}")
        
        # Verify RTP accuracy
        rtp_diff = abs((simulation_results['rtp_decimal'] - analysis['theoretical_rtp']) * 100)
        if rtp_diff < 0.1:
            print(f"  ✅ RTP accuracy: EXCELLENT (difference: {rtp_diff:.4f}%)")
        elif rtp_diff < 0.5:
            print(f"  ✅ RTP accuracy: GOOD (difference: {rtp_diff:.4f}%)")
        else:
            print(f"  ⚠️  RTP accuracy: NEEDS ATTENTION (difference: {rtp_diff:.4f}%)")
    
    print(f"\n=== Simulation Complete ===")
    print(f"Math package zip file: math_package.zip")

if __name__ == "__main__":
    main()