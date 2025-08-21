#!/usr/bin/env python3
"""
Full Court Fortune - Basketball Slot Game Backend
Using Stake Engine Math SDK for provably fair gaming
"""

import random
import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import hashlib
import hmac
import time

# Game Configuration
@dataclass
class GameConfig:
    """Basketball slot game configuration"""
    # Betting levels (in dollars)
    bet_levels: List[float] = None
    
    # Win probabilities and multipliers
    base_win_rate: float = 0.25  # 25% base win rate
    bonus_win_rate: float = 0.40  # 40% win rate during bonus
    
    # Multipliers
    regular_multiplier: float = 10.0  # 10x for regular wins
    bonus_multipliers: List[float] = None  # [15x, 25x] for bonus wins
    jackpot_multiplier: float = 5000.0  # 5000x jackpot
    
    # Bonus mechanics
    bonus_trigger_rate: float = 0.05  # 5% chance to trigger bonus
    bonus_free_shots: int = 5  # Number of free shots in bonus
    buy_bonus_multiplier: float = 100.0  # Cost to buy bonus (100x bet)
    
    # Jackpot mechanics
    jackpot_rate: float = 0.001  # 0.1% chance for jackpot
    
    def __post_init__(self):
        if self.bet_levels is None:
            self.bet_levels = [0.1, 0.25, 0.5, 1, 2, 5, 10, 25, 50, 100, 250, 500, 1000]
        if self.bonus_multipliers is None:
            self.bonus_multipliers = [15.0, 25.0]

class GameState(Enum):
    """Game state enumeration"""
    IDLE = "idle"
    SHOOTING = "shooting"
    BONUS = "bonus"
    ENDED = "ended"

@dataclass
class ShotResult:
    """Result of a basketball shot"""
    is_win: bool
    multiplier: float
    is_bonus: bool
    is_jackpot: bool
    winnings: float
    free_spins_remaining: int
    message: str
    animation_type: str  # "score", "bounce_backboard", "bounce_rim"

class BasketballSlotGame:
    """Main basketball slot game class using Stake Engine principles"""
    
    def __init__(self, config: GameConfig = None):
        self.config = config or GameConfig()
        self.game_state = GameState.IDLE
        self.free_spins_remaining = 0
        self.total_winnings = 0.0
        self.games_played = 0
        
        # Provably fair seed management
        self.server_seed = None
        self.client_seed = None
        self.nonce = 0
        
    def set_seeds(self, server_seed: str, client_seed: str = None):
        """Set seeds for provably fair gaming"""
        self.server_seed = server_seed
        self.client_seed = client_seed or ""
        self.nonce = 0
        
    def generate_random(self) -> float:
        """Generate provably fair random number between 0 and 1"""
        if not self.server_seed:
            raise ValueError("Server seed not set")
            
        # Create combined seed
        combined_seed = f"{self.server_seed}:{self.client_seed}:{self.nonce}"
        self.nonce += 1
        
        # Generate hash
        hash_input = combined_seed.encode('utf-8')
        hash_result = hashlib.sha256(hash_input).hexdigest()
        
        # Convert to float between 0 and 1
        return int(hash_result[:8], 16) / (16 ** 8)
    
    def determine_shot_outcome(self, bet_amount: float, power_level: int = 50) -> ShotResult:
        """Determine the outcome of a basketball shot"""
        random_value = self.generate_random()
        
        # Determine if this is a bonus trigger
        is_bonus_trigger = (random_value < self.config.bonus_trigger_rate and 
                           self.free_spins_remaining == 0)
        
        if is_bonus_trigger:
            return self._create_bonus_trigger_result(bet_amount)
        
        # Determine win/loss
        win_rate = self.config.bonus_win_rate if self.free_spins_remaining > 0 else self.config.base_win_rate
        is_win = random_value < win_rate
        
        if is_win:
            return self._create_win_result(bet_amount, random_value)
        else:
            return self._create_loss_result(bet_amount)
    
    def _create_bonus_trigger_result(self, bet_amount: float) -> ShotResult:
        """Create result for bonus trigger"""
        self.free_spins_remaining = self.config.bonus_free_shots
        
        return ShotResult(
            is_win=True,
            multiplier=self.config.regular_multiplier,
            is_bonus=True,
            is_jackpot=False,
            winnings=bet_amount * self.config.regular_multiplier,
            free_spins_remaining=self.free_spins_remaining,
            message="BONUS! 5 FREE SHOTS!",
            animation_type="score"
        )
    
    def _create_win_result(self, bet_amount: float, random_value: float) -> ShotResult:
        """Create result for a winning shot"""
        # Check for jackpot
        is_jackpot = random_value < self.config.jackpot_rate
        
        if is_jackpot:
            multiplier = self.config.jackpot_multiplier
            message = "JACKPOT!"
            animation_type = "score"
        elif self.free_spins_remaining > 0:
            # Bonus round - choose between bonus multipliers
            multiplier = random.choice(self.config.bonus_multipliers)
            message = random.choice(["SWISH!", "NICE SHOT!", "PERFECT!", "AMAZING!"])
            animation_type = "score"
        else:
            # Regular win
            multiplier = self.config.regular_multiplier
            message = random.choice(["SWISH!", "NICE SHOT!", "PERFECT!", "AMAZING!"])
            animation_type = "score"
        
        # Decrement free spins if in bonus mode
        if self.free_spins_remaining > 0:
            self.free_spins_remaining -= 1
        
        winnings = bet_amount * multiplier
        
        return ShotResult(
            is_win=True,
            multiplier=multiplier,
            is_bonus=False,
            is_jackpot=is_jackpot,
            winnings=winnings,
            free_spins_remaining=self.free_spins_remaining,
            message=message,
            animation_type=animation_type
        )
    
    def _create_loss_result(self, bet_amount: float) -> ShotResult:
        """Create result for a losing shot"""
        # Decrement free spins if in bonus mode
        if self.free_spins_remaining > 0:
            self.free_spins_remaining -= 1
        
        # Choose bounce animation type
        animation_type = random.choice(["bounce_backboard", "bounce_rim"])
        message = random.choice(["So close!", "Next time!", "You almost had it!", "Keep trying!", "Almost there!"])
        
        return ShotResult(
            is_win=False,
            multiplier=0.0,
            is_bonus=False,
            is_jackpot=False,
            winnings=0.0,
            free_spins_remaining=self.free_spins_remaining,
            message=message,
            animation_type=animation_type
        )
    
    def buy_bonus(self, bet_amount: float) -> ShotResult:
        """Buy bonus round"""
        if self.free_spins_remaining > 0:
            raise ValueError("Bonus already active")
        
        cost = bet_amount * self.config.buy_bonus_multiplier
        self.free_spins_remaining = self.config.bonus_free_shots
        
        return ShotResult(
            is_win=True,
            multiplier=0.0,  # No immediate win, just bonus activation
            is_bonus=True,
            is_jackpot=False,
            winnings=0.0,
            free_spins_remaining=self.free_spins_remaining,
            message="BONUS PURCHASED! 5 FREE SHOTS!",
            animation_type="score"
        )
    
    def get_game_stats(self) -> Dict:
        """Get current game statistics"""
        return {
            "total_winnings": self.total_winnings,
            "games_played": self.games_played,
            "free_spins_remaining": self.free_spins_remaining,
            "game_state": self.game_state.value,
            "server_seed": self.server_seed,
            "nonce": self.nonce
        }
    
    def reset_game(self):
        """Reset game state"""
        self.free_spins_remaining = 0
        self.game_state = GameState.IDLE
        self.nonce = 0

# Example usage and testing
if __name__ == "__main__":
    # Initialize game
    config = GameConfig()
    game = BasketballSlotGame(config)
    
    # Set seeds for provably fair gaming
    game.set_seeds("server_seed_example_123", "client_seed_example_456")
    
    # Simulate some shots
    bet_amount = 1.0
    print("Simulating basketball shots...")
    
    for i in range(10):
        result = game.determine_shot_outcome(bet_amount)
        print(f"Shot {i+1}: {result.message} - Win: {result.is_win}, "
              f"Multiplier: {result.multiplier}x, Winnings: ${result.winnings:.2f}")
        
        if result.free_spins_remaining > 0:
            print(f"  Bonus active! {result.free_spins_remaining} free shots remaining")
    
    print(f"\nGame Stats: {game.get_game_stats()}")
