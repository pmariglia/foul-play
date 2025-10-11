#!/usr/bin/env python3
"""
Example script demonstrating how to use Foul Play's move evaluation API.

This is similar to Stockfish's analysis mode - you can evaluate specific positions
and get optimality scores for all available moves.
"""

import sys
from copy import deepcopy

# Example: Programmatically evaluating a battle position
def evaluate_battle_position(battle):
    """
    Evaluate a battle position and return all move scores.

    Args:
        battle: A Battle object representing the current game state

    Returns:
        BattleEvaluation with move scores
    """
    from fp.search.main import find_best_move

    # Get evaluation (returns tuple: (best_move, evaluation))
    best_move, evaluation = find_best_move(battle, return_evaluation=True)

    print(f"\n{'='*60}")
    print(f"POSITION EVALUATION")
    print(f"{'='*60}")
    print(f"Best move: {best_move}")
    print(f"Scenarios analyzed: {evaluation.num_scenarios}")
    print(f"Total MCTS iterations: {evaluation.total_iterations}")
    print(f"\nMove Rankings:")
    print(f"{'-'*60}")

    for i, move_eval in enumerate(evaluation.get_top_moves(10), 1):
        # Optimality: 0-1 scale (1 = best)
        # Visit percentage: How much MCTS explored this move
        # Win rate: Expected outcome (-1 to 1)
        print(
            f"{i:2}. {move_eval.move:20} | "
            f"Optimality: {move_eval.optimality:.3f} | "
            f"Visits: {move_eval.visit_percentage:5.1%} | "
            f"Win Rate: {move_eval.win_rate:+.3f}"
        )

    return evaluation


def evaluate_specific_move(battle, move_name):
    """
    Evaluate how optimal a specific move is compared to the best move.

    This is useful for post-game analysis:
    "I played Thunderbolt on turn 5. Was that optimal?"

    Args:
        battle: Battle state
        move_name: The move to evaluate (e.g., "thunderbolt", "switch charizard")

    Returns:
        float: Optimality score 0-1, or None if move not available
    """
    from fp.search.main import find_best_move
    from fp.evaluate import compare_move_to_best

    best_move, evaluation = find_best_move(battle, return_evaluation=True)

    move_eval = evaluation.get_move_evaluation(move_name)
    if move_eval is None:
        print(f"Move '{move_name}' was not available in this position")
        return None

    loss = compare_move_to_best(evaluation, move_name)

    print(f"\n{'='*60}")
    print(f"MOVE ANALYSIS: {move_name}")
    print(f"{'='*60}")
    print(f"Best move was:     {best_move}")
    print(f"Your move:         {move_name}")
    print(f"Optimality:        {move_eval.optimality:.3f} / 1.000")
    print(f"Win rate:          {move_eval.win_rate:+.3f}")
    print(f"Loss vs best:      {loss:.1f} centipawn-equivalents")

    if move_eval.optimality >= 0.95:
        print("Assessment:        Excellent move!")
    elif move_eval.optimality >= 0.80:
        print("Assessment:        Good move")
    elif move_eval.optimality >= 0.60:
        print("Assessment:        Acceptable move")
    elif move_eval.optimality >= 0.40:
        print("Assessment:        Dubious move")
    else:
        print("Assessment:        Mistake")

    return move_eval.optimality


def export_evaluation_json(evaluation, filename="evaluation.json"):
    """Export evaluation data to JSON for external analysis."""
    import json

    with open(filename, "w") as f:
        json.dump(evaluation.to_dict(), f, indent=2)

    print(f"Evaluation exported to {filename}")


# Example usage in battle loop
def example_usage():
    """
    Example showing how to integrate evaluation into your code.
    """
    print("""
    # During a battle, you can evaluate positions like this:

    from fp.search.main import find_best_move

    # Option 1: Just get the best move (normal operation)
    best_move = find_best_move(battle)

    # Option 2: Get best move + full evaluation
    best_move, evaluation = find_best_move(battle, return_evaluation=True)

    # Check optimality of a specific move
    move_eval = evaluation.get_move_evaluation("thunderbolt")
    print(f"Thunderbolt optimality: {move_eval.optimality:.1%}")

    # Get top 5 moves
    for move_eval in evaluation.get_top_moves(5):
        print(f"{move_eval.move}: {move_eval.optimality:.3f}")

    # Export for later analysis
    import json
    with open("turn5_analysis.json", "w") as f:
        json.dump(evaluation.to_dict(), f, indent=2)
    """)


if __name__ == "__main__":
    print(__doc__)
    print("\nThis script provides helper functions for move evaluation.")
    print("Import these functions in your own code to analyze positions.")
    print("\nExample usage:")
    example_usage()
    print("\n" + "="*60)
    print("To enable evaluation during live games, run:")
    print("  python run.py --enable-evaluation [other args]")
    print("="*60)
