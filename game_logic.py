#!/usr/bin/env python3
"""
Full Court Fortune - Game Logic for Stake Engine Math SDK
This file defines the core game mechanics and will be used to generate
simulation results and lookup tables for the RGS.
"""

import random
import json
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import hashlib
import math

# Game States
class GameState(Enum):
    IDLE = "idle"
    SHOOTING = "shooting"
    BONUS = "bonus"
    ENDED = "ended"

# Shot Outcomes
class ShotOutcome(Enum):
    MISS = "miss"
    SCORE = "score"
    BONUS_TRIGGER = "bonus_trigger"
    JACKPOT = "jackpot"

@dataclass
class GameConfig:
    """Game configuration parameters"""
    # Betting
    bet_levels: List[float]
    min_bet: float = 0.1
    max_bet: float = 1000.0
    
    # Win rates
    base_win_rate: float = 0.25
    bonus_win_rate: float = 0.40
    
    # Multipliers
    regular_multiplier: float = 10.0
    bonus_multipliers: List[float] = None
    jackpot_multiplier: float = 5000.0
    
    # Bonus mechanics
    bonus_trigger_rate: float = 0.05
    bonus_free_shots: int = 5
    buy_bonus_multiplier: float = 100.0
    
    # Jackpot
    jackpot_rate: float = 0.001
    
    def __post_init__(self):
        if self.bonus_multipliers is None:
            self.bonus_multipliers = [15.0, 25.0]

@dataclass
class RoundResult:
    """Result of a single game round"""
    outcome: ShotOutcome
    multiplier: float
    winnings: float
    is_bonus: bool
    is_jackpot: bool
    free_spins_remaining: int
    message: str
    animation_type: str
    rtp_contribution: float

class BasketballSlotGame:
    """Core game logic for basketball slot game"""
    
    def __init__(self, config: GameConfig):
        self.config = config
        self.state = GameState.IDLE
        self.free_spins_remaining = 0
        
    def set_seeds(self, server_seed: str, client_seed: str = "", nonce: int = 0):
        """Set seeds for provably fair random generation"""
        self.server_seed = server_seed
        self.client_seed = client_seed
        self.nonce = nonce
        
    def generate_random(self) -> float:
        """Generate provably fair random number between 0 and 1"""
        if not hasattr(self, 'server_seed'):
            raise ValueError("Seeds not set")
            
        combined_seed = f"{self.server_seed}:{self.client_seed}:{self.nonce}"
        self.nonce += 1
        
        hash_input = combined_seed.encode('utf-8')
        hash_result = hashlib.sha256(hash_input).hexdigest()
        
        return int(hash_result[:8], 16) / (16 ** 8)
    
    def determine_outcome(self, bet_amount: float, power_level: int = 50) -> RoundResult:
        """Determine the outcome of a basketball shot"""
        random_value = self.generate_random()
        
        # Check for bonus trigger (only if not already in bonus)
        if (self.free_spins_remaining == 0 and 
            random_value < self.config.bonus_trigger_rate):
            return self._create_bonus_trigger_result(bet_amount)
        
        # Determine win/loss based on current state
        win_rate = (self.config.bonus_win_rate if self.free_spins_remaining > 0 
                   else self.config.base_win_rate)
        
        if random_value < win_rate:
            return self._create_win_result(bet_amount, random_value)
        else:
            return self._create_loss_result(bet_amount)
    
    def _create_bonus_trigger_result(self, bet_amount: float) -> RoundResult:
        """Create result for bonus trigger"""
        self.free_spins_remaining = self.config.bonus_free_shots
        
        return RoundResult(
            outcome=ShotOutcome.BONUS_TRIGGER,
            multiplier=self.config.regular_multiplier,
            winnings=bet_amount * self.config.regular_multiplier,
            is_bonus=True,
            is_jackpot=False,
            free_spins_remaining=self.free_spins_remaining,
            message="BONUS! 5 FREE SHOTS!",
            animation_type="score",
            rtp_contribution=self.config.regular_multiplier * self.config.bonus_trigger_rate
        )
    
    def _create_win_result(self, bet_amount: float, random_value: float) -> RoundResult:
        """Create result for a winning shot"""
        # Check for jackpot
        if random_value < self.config.jackpot_rate:
            multiplier = self.config.jackpot_multiplier
            outcome = ShotOutcome.JACKPOT
            message = "JACKPOT!"
            animation_type = "score"
            is_jackpot = True
        elif self.free_spins_remaining > 0:
            # Bonus round
            multiplier = random.choice(self.config.bonus_multipliers)
            outcome = ShotOutcome.SCORE
            message = random.choice(["SWISH!", "NICE SHOT!", "PERFECT!", "AMAZING!"])
            animation_type = "score"
            is_jackpot = False
        else:
            # Regular win
            multiplier = self.config.regular_multiplier
            outcome = ShotOutcome.SCORE
            message = random.choice(["SWISH!", "NICE SHOT!", "PERFECT!", "AMAZING!"])
            animation_type = "score"
            is_jackpot = False
        
        # Decrement free spins if in bonus mode
        if self.free_spins_remaining > 0:
            self.free_spins_remaining -= 1
        
        winnings = bet_amount * multiplier
        
        return RoundResult(
            outcome=outcome,
            multiplier=multiplier,
            winnings=winnings,
            is_bonus=False,
            is_jackpot=is_jackpot,
            free_spins_remaining=self.free_spins_remaining,
            message=message,
            animation_type=animation_type,
            rtp_contribution=multiplier * (self.config.bonus_win_rate if self.free_spins_remaining > 0 else self.config.base_win_rate)
        )
    
    def _create_loss_result(self, bet_amount: float) -> RoundResult:
        """Create result for a losing shot"""
        # Decrement free spins if in bonus mode
        if self.free_spins_remaining > 0:
            self.free_spins_remaining -= 1
        
        animation_type = random.choice(["bounce_backboard", "bounce_rim"])
        message = random.choice(["So close!", "Next time!", "You almost had it!", "Keep trying!", "Almost there!"])
        
        return RoundResult(
            outcome=ShotOutcome.MISS,
            multiplier=0.0,
            winnings=0.0,
            is_bonus=False,
            is_jackpot=False,
            free_spins_remaining=self.free_spins_remaining,
            message=message,
            animation_type=animation_type,
            rtp_contribution=0.0
        )
    
    def buy_bonus(self, bet_amount: float) -> RoundResult:
        """Buy bonus round"""
        if self.free_spins_remaining > 0:
            raise ValueError("Bonus already active")
        
        cost = bet_amount * self.config.buy_bonus_multiplier
        self.free_spins_remaining = self.config.bonus_free_shots
        
        return RoundResult(
            outcome=ShotOutcome.BONUS_TRIGGER,
            multiplier=0.0,
            winnings=0.0,
            is_bonus=True,
            is_jackpot=False,
            free_spins_remaining=self.free_spins_remaining,
            message="BONUS PURCHASED! 5 FREE SHOTS!",
            animation_type="score",
            rtp_contribution=0.0  # Cost is handled separately
        )

def simulate_game(config: GameConfig, rounds: int = 1000000) -> Dict[str, Any]:
    """Simulate the game for RTP calculation and analysis"""
    game = BasketballSlotGame(config)
    game.set_seeds("simulation_seed")
    
    total_bet = 0.0
    total_winnings = 0.0
    outcomes = {
        ShotOutcome.MISS: 0,
        ShotOutcome.SCORE: 0,
        ShotOutcome.BONUS_TRIGGER: 0,
        ShotOutcome.JACKPOT: 0
    }
    
    max_win = 0.0
    max_multiplier = 0.0
    
    for i in range(rounds):
        bet_amount = random.choice(config.bet_levels)
        total_bet += bet_amount
        
        result = game.determine_outcome(bet_amount)
        total_winnings += result.winnings
        outcomes[result.outcome] += 1
        
        if result.winnings > max_win:
            max_win = result.winnings
        if result.multiplier > max_multiplier:
            max_multiplier = result.multiplier
    
    rtp = total_winnings / total_bet if total_bet > 0 else 0.0
    
    return {
        "rounds": rounds,
        "total_bet": total_bet,
        "total_winnings": total_winnings,
        "rtp": rtp,
        "outcomes": {k.value: v for k, v in outcomes.items()},
        "max_win": max_win,
        "max_multiplier": max_multiplier,
        "outcome_percentages": {k.value: v/rounds for k, v in outcomes.items()}
    }

def generate_lookup_tables(config: GameConfig) -> Dict[str, Any]:
    """Generate lookup tables for the RGS"""
    tables = {
        "outcome_probabilities": {
            "miss": 1.0 - config.base_win_rate,
            "score": config.base_win_rate,
            "bonus_trigger": config.bonus_trigger_rate,
            "jackpot": config.jackpot_rate
        },
        "multipliers": {
            "regular": config.regular_multiplier,
            "bonus": config.bonus_multipliers,
            "jackpot": config.jackpot_multiplier
        },
        "bonus_config": {
            "free_shots": config.bonus_free_shots,
            "buy_cost_multiplier": config.buy_bonus_multiplier
        }
    }
    
    return tables

# Example usage for testing
if __name__ == "__main__":
    config = GameConfig(
        bet_levels=[0.1, 0.25, 0.5, 1, 2, 5, 10, 25, 50, 100, 250, 500, 1000]
    )
    
    # Run simulation
    simulation_results = simulate_game(config, 100000)
    print("Simulation Results:")
    print(json.dumps(simulation_results, indent=2))
    
    # Generate lookup tables
    lookup_tables = generate_lookup_tables(config)
    print("\nLookup Tables:")
    print(json.dumps(lookup_tables, indent=2))
