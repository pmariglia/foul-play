"""
Move evaluation module for analyzing Pokemon battle decisions.

Similar to Stockfish's evaluation system, this module provides:
- Move scoring (0-1 scale for optimality)
- Visit counts (confidence/exploration metric)
- Win rates (expected value from MCTS simulations)
"""

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class MoveEvaluation:
    """Evaluation data for a single move choice."""

    move: str
    optimality: float  # 0-1 scale, 1 = best move
    visit_percentage: float  # Percentage of MCTS visits
    win_rate: float  # Expected win rate from simulations (-1 to 1)
    raw_score: float  # Raw aggregated score before normalization

    def __repr__(self):
        return (
            f"MoveEvaluation(move={self.move}, "
            f"optimality={self.optimality:.3f}, "
            f"visit_pct={self.visit_percentage:.1%}, "
            f"win_rate={self.win_rate:.3f})"
        )


@dataclass
class BattleEvaluation:
    """Complete evaluation of all available moves in a position."""

    best_move: str
    evaluations: dict[str, MoveEvaluation]  # move -> evaluation
    num_scenarios: int  # Number of battle scenarios analyzed
    total_iterations: int  # Total MCTS iterations across scenarios

    def get_move_evaluation(self, move: str) -> Optional[MoveEvaluation]:
        """Get evaluation for a specific move."""
        return self.evaluations.get(move)

    def get_top_moves(self, n: int = 5) -> list[MoveEvaluation]:
        """Get top N moves by optimality."""
        return sorted(
            self.evaluations.values(),
            key=lambda e: e.optimality,
            reverse=True
        )[:n]

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "best_move": self.best_move,
            "num_scenarios": self.num_scenarios,
            "total_iterations": self.total_iterations,
            "evaluations": {
                move: {
                    "optimality": e.optimality,
                    "visit_percentage": e.visit_percentage,
                    "win_rate": e.win_rate,
                    "raw_score": e.raw_score,
                }
                for move, e in self.evaluations.items()
            }
        }

    def __repr__(self):
        top_3 = self.get_top_moves(3)
        moves_str = ", ".join(f"{e.move}({e.optimality:.2f})" for e in top_3)
        return (
            f"BattleEvaluation(best={self.best_move}, "
            f"scenarios={self.num_scenarios}, "
            f"iterations={self.total_iterations}, "
            f"top_moves=[{moves_str}])"
        )


def compute_battle_evaluation(mcts_results: list, selected_move: str) -> BattleEvaluation:
    """
    Compute complete evaluation from MCTS results.

    Args:
        mcts_results: List of (MctsResult, sample_chance, index) tuples
        selected_move: The move that was selected by the bot

    Returns:
        BattleEvaluation with all move scores
    """
    # Aggregate scores across all scenarios (same logic as select_move_from_mcts_results)
    final_policy = {}
    total_iterations = 0

    for mcts_result, sample_chance, index in mcts_results:
        total_iterations += mcts_result.total_visits

        # Weight each move by scenario probability and visit percentage
        for s1_option in mcts_result.side_one:
            visit_weight = s1_option.visits / mcts_result.total_visits
            weighted_score = sample_chance * visit_weight

            if s1_option.move_choice not in final_policy:
                final_policy[s1_option.move_choice] = {
                    "raw_score": 0.0,
                    "win_rate_sum": 0.0,
                    "win_rate_weight": 0.0,
                }

            final_policy[s1_option.move_choice]["raw_score"] += weighted_score

            # Track weighted average win rate
            if s1_option.visits > 0:
                win_rate = s1_option.total_score / s1_option.visits
                final_policy[s1_option.move_choice]["win_rate_sum"] += win_rate * weighted_score
                final_policy[s1_option.move_choice]["win_rate_weight"] += weighted_score

    # Normalize to 0-1 optimality scale
    max_score = max(p["raw_score"] for p in final_policy.values()) if final_policy else 1.0

    evaluations = {}
    for move, data in final_policy.items():
        raw_score = data["raw_score"]
        optimality = raw_score / max_score if max_score > 0 else 0.0

        # Compute weighted average win rate
        win_rate = 0.0
        if data["win_rate_weight"] > 0:
            win_rate = data["win_rate_sum"] / data["win_rate_weight"]

        evaluations[move] = MoveEvaluation(
            move=move,
            optimality=optimality,
            visit_percentage=raw_score,  # This is already a percentage
            win_rate=win_rate,
            raw_score=raw_score,
        )

    # Determine best move (should match selected_move in normal operation)
    best_move = selected_move
    if not evaluations:
        logger.warning("No evaluations computed!")
    elif selected_move not in evaluations:
        # Fallback: pick highest optimality
        best_move = max(evaluations.items(), key=lambda x: x[1].optimality)[0]
        logger.warning(f"Selected move {selected_move} not in evaluations, using {best_move}")

    return BattleEvaluation(
        best_move=best_move,
        evaluations=evaluations,
        num_scenarios=len(mcts_results),
        total_iterations=total_iterations,
    )


def log_evaluation_summary(evaluation: BattleEvaluation, verbose: bool = True):
    """Log a human-readable summary of move evaluations."""
    logger.info(f"Evaluation: {evaluation.num_scenarios} scenarios, {evaluation.total_iterations} total iterations")
    logger.info(f"Best move: {evaluation.best_move}")

    if verbose:
        logger.info("Move rankings:")
        for i, move_eval in enumerate(evaluation.get_top_moves(10), 1):
            logger.info(
                f"  {i}. {move_eval.move}: "
                f"optimality={move_eval.optimality:.3f} "
                f"visits={move_eval.visit_percentage:.1%} "
                f"win_rate={move_eval.win_rate:+.3f}"
            )


def compare_move_to_best(evaluation: BattleEvaluation, move: str) -> Optional[float]:
    """
    Compare a specific move to the best move.

    Returns:
        Centipawn-like loss (0 = best move, higher = worse)
        None if move not available
    """
    move_eval = evaluation.get_move_evaluation(move)
    if move_eval is None:
        return None

    best_eval = evaluation.evaluations[evaluation.best_move]

    # Return difference in win rate (scaled to 0-100 range like centipawns)
    loss = (best_eval.win_rate - move_eval.win_rate) * 50  # Scale to roughly 0-100
    return max(0.0, loss)
