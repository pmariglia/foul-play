"""Tests for the move evaluation system."""

import unittest
from unittest.mock import MagicMock
from dataclasses import dataclass

from fp.evaluate import (
    MoveEvaluation,
    BattleEvaluation,
    compute_battle_evaluation,
    compare_move_to_best,
)


# Mock MctsResult structure based on actual usage in main.py
@dataclass
class MockMoveChoice:
    """Mock for individual move option in MCTS result."""
    move_choice: str
    visits: int
    total_score: float


@dataclass
class MockMctsResult:
    """Mock for MctsResult from poke-engine."""
    side_one: list
    total_visits: int


class TestMoveEvaluation(unittest.TestCase):
    """Test MoveEvaluation dataclass."""

    def test_move_evaluation_creation(self):
        """Test creating a MoveEvaluation."""
        eval = MoveEvaluation(
            move="thunderbolt",
            optimality=0.95,
            visit_percentage=0.45,
            win_rate=0.234,
            raw_score=0.45,
        )
        self.assertEqual(eval.move, "thunderbolt")
        self.assertAlmostEqual(eval.optimality, 0.95)
        self.assertAlmostEqual(eval.visit_percentage, 0.45)
        self.assertAlmostEqual(eval.win_rate, 0.234)

    def test_move_evaluation_repr(self):
        """Test string representation."""
        eval = MoveEvaluation(
            move="surf",
            optimality=1.0,
            visit_percentage=0.6,
            win_rate=0.5,
            raw_score=0.6,
        )
        repr_str = repr(eval)
        self.assertIn("surf", repr_str)
        self.assertIn("1.000", repr_str)


class TestBattleEvaluation(unittest.TestCase):
    """Test BattleEvaluation dataclass."""

    def setUp(self):
        """Create sample evaluations."""
        self.eval1 = MoveEvaluation("thunderbolt", 1.0, 0.6, 0.5, 0.6)
        self.eval2 = MoveEvaluation("icebeam", 0.85, 0.3, 0.45, 0.3)
        self.eval3 = MoveEvaluation("surf", 0.7, 0.1, 0.4, 0.1)

        self.battle_eval = BattleEvaluation(
            best_move="thunderbolt",
            evaluations={
                "thunderbolt": self.eval1,
                "icebeam": self.eval2,
                "surf": self.eval3,
            },
            num_scenarios=4,
            total_iterations=2000,
        )

    def test_get_move_evaluation(self):
        """Test retrieving a specific move evaluation."""
        eval = self.battle_eval.get_move_evaluation("icebeam")
        self.assertIsNotNone(eval)
        self.assertEqual(eval.move, "icebeam")
        self.assertAlmostEqual(eval.optimality, 0.85)

    def test_get_move_evaluation_missing(self):
        """Test retrieving non-existent move."""
        eval = self.battle_eval.get_move_evaluation("flamethrower")
        self.assertIsNone(eval)

    def test_get_top_moves(self):
        """Test getting top N moves."""
        top_moves = self.battle_eval.get_top_moves(2)
        self.assertEqual(len(top_moves), 2)
        self.assertEqual(top_moves[0].move, "thunderbolt")
        self.assertEqual(top_moves[1].move, "icebeam")

    def test_get_top_moves_all(self):
        """Test getting more moves than available."""
        top_moves = self.battle_eval.get_top_moves(10)
        self.assertEqual(len(top_moves), 3)

    def test_to_dict(self):
        """Test JSON serialization."""
        result = self.battle_eval.to_dict()
        self.assertIsInstance(result, dict)
        self.assertEqual(result["best_move"], "thunderbolt")
        self.assertEqual(result["num_scenarios"], 4)
        self.assertEqual(result["total_iterations"], 2000)
        self.assertIn("thunderbolt", result["evaluations"])
        self.assertAlmostEqual(result["evaluations"]["thunderbolt"]["optimality"], 1.0)


class TestComputeBattleEvaluation(unittest.TestCase):
    """Test compute_battle_evaluation function."""

    def test_single_scenario(self):
        """Test evaluation with a single scenario."""
        # Create mock MCTS result
        move1 = MockMoveChoice("thunderbolt", visits=600, total_score=300.0)
        move2 = MockMoveChoice("icebeam", visits=300, total_score=120.0)
        move3 = MockMoveChoice("surf", visits=100, total_score=40.0)

        mcts_result = MockMctsResult(
            side_one=[move1, move2, move3],
            total_visits=1000,
        )

        mcts_results = [(mcts_result, 1.0, 0)]  # (result, sample_chance, index)

        evaluation = compute_battle_evaluation(mcts_results, "thunderbolt")

        # Check basic properties
        self.assertEqual(evaluation.best_move, "thunderbolt")
        self.assertEqual(evaluation.num_scenarios, 1)
        self.assertEqual(evaluation.total_iterations, 1000)

        # Check that all moves are present
        self.assertEqual(len(evaluation.evaluations), 3)
        self.assertIn("thunderbolt", evaluation.evaluations)
        self.assertIn("icebeam", evaluation.evaluations)
        self.assertIn("surf", evaluation.evaluations)

        # Check that best move has optimality 1.0
        self.assertAlmostEqual(evaluation.evaluations["thunderbolt"].optimality, 1.0)

        # Check that other moves have lower optimality
        self.assertLess(evaluation.evaluations["icebeam"].optimality, 1.0)
        self.assertLess(evaluation.evaluations["surf"].optimality, 1.0)

        # Check win rates
        self.assertAlmostEqual(
            evaluation.evaluations["thunderbolt"].win_rate, 300.0 / 600
        )
        self.assertAlmostEqual(evaluation.evaluations["icebeam"].win_rate, 120.0 / 300)

    def test_multiple_scenarios(self):
        """Test evaluation with multiple scenarios (typical case)."""
        # Scenario 1: Thunderbolt looks best
        move1a = MockMoveChoice("thunderbolt", visits=500, total_score=250.0)
        move2a = MockMoveChoice("icebeam", visits=300, total_score=120.0)
        mcts_result1 = MockMctsResult(side_one=[move1a, move2a], total_visits=800)

        # Scenario 2: Ice Beam looks best
        move1b = MockMoveChoice("thunderbolt", visits=200, total_score=80.0)
        move2b = MockMoveChoice("icebeam", visits=600, total_score=300.0)
        mcts_result2 = MockMctsResult(side_one=[move1b, move2b], total_visits=800)

        mcts_results = [
            (mcts_result1, 0.6, 0),  # 60% chance scenario 1
            (mcts_result2, 0.4, 1),  # 40% chance scenario 2
        ]

        evaluation = compute_battle_evaluation(mcts_results, "thunderbolt")

        self.assertEqual(evaluation.num_scenarios, 2)
        self.assertEqual(evaluation.total_iterations, 1600)

        # Both moves should be present
        self.assertIn("thunderbolt", evaluation.evaluations)
        self.assertIn("icebeam", evaluation.evaluations)

        # Thunderbolt should be best (weighted by scenario probability)
        # Scenario 1: thunderbolt = 0.6 * 500/800 = 0.375
        # Scenario 2: thunderbolt = 0.4 * 200/800 = 0.1
        # Total: 0.475
        thunderbolt_score = evaluation.evaluations["thunderbolt"].raw_score
        self.assertAlmostEqual(thunderbolt_score, 0.475, places=3)

        # Ice beam score
        # Scenario 1: 0.6 * 300/800 = 0.225
        # Scenario 2: 0.4 * 600/800 = 0.3
        # Total: 0.525
        icebeam_score = evaluation.evaluations["icebeam"].raw_score
        self.assertAlmostEqual(icebeam_score, 0.525, places=3)

        # Ice beam should actually be slightly better in this case
        self.assertGreater(
            evaluation.evaluations["icebeam"].optimality,
            evaluation.evaluations["thunderbolt"].optimality,
        )

    def test_switch_moves(self):
        """Test that switch moves are evaluated correctly."""
        move1 = MockMoveChoice("switch charizard", visits=400, total_score=200.0)
        move2 = MockMoveChoice("thunderbolt", visits=600, total_score=240.0)

        mcts_result = MockMctsResult(side_one=[move1, move2], total_visits=1000)
        mcts_results = [(mcts_result, 1.0, 0)]

        evaluation = compute_battle_evaluation(mcts_results, "thunderbolt")

        self.assertIn("switch charizard", evaluation.evaluations)
        self.assertIn("thunderbolt", evaluation.evaluations)


class TestCompareMoveToEst(unittest.TestCase):
    """Test compare_move_to_best function."""

    def setUp(self):
        """Create sample battle evaluation."""
        self.eval1 = MoveEvaluation("thunderbolt", 1.0, 0.6, 0.5, 0.6)
        self.eval2 = MoveEvaluation("icebeam", 0.85, 0.3, 0.3, 0.3)
        self.eval3 = MoveEvaluation("tackle", 0.5, 0.1, -0.2, 0.1)

        self.battle_eval = BattleEvaluation(
            best_move="thunderbolt",
            evaluations={
                "thunderbolt": self.eval1,
                "icebeam": self.eval2,
                "tackle": self.eval3,
            },
            num_scenarios=2,
            total_iterations=1000,
        )

    def test_best_move_has_zero_loss(self):
        """Test that best move has 0 centipawn loss."""
        loss = compare_move_to_best(self.battle_eval, "thunderbolt")
        self.assertAlmostEqual(loss, 0.0)

    def test_good_move_has_small_loss(self):
        """Test that a good move has small loss."""
        loss = compare_move_to_best(self.battle_eval, "icebeam")
        self.assertGreater(loss, 0.0)
        self.assertLess(loss, 20.0)  # Should be relatively small

    def test_bad_move_has_large_loss(self):
        """Test that a bad move has larger loss."""
        loss = compare_move_to_best(self.battle_eval, "tackle")
        self.assertGreater(loss, 20.0)  # Should be substantial

    def test_nonexistent_move_returns_none(self):
        """Test that comparing non-existent move returns None."""
        loss = compare_move_to_best(self.battle_eval, "flamethrower")
        self.assertIsNone(loss)


if __name__ == "__main__":
    unittest.main()
