"""Integration tests for the evaluation system with actual battle objects."""

import unittest
from unittest.mock import patch, MagicMock

from fp.battle import Battle, Battler, Pokemon
from fp.search.main import find_best_move
from fp.evaluate import BattleEvaluation
from constants import BattleType
from config import FoulPlayConfig


class TestEvaluationIntegration(unittest.TestCase):
    """Integration tests for evaluation with real battle objects."""

    def setUp(self):
        """Set up a simple battle scenario."""
        # Configure FoulPlayConfig with minimal settings
        FoulPlayConfig.parallelism = 1
        FoulPlayConfig.search_time_ms = 10  # Very short for testing
        FoulPlayConfig.log_level = "INFO"

        # Create a simple battle
        self.battle = Battle("test-battle")
        self.battle.battle_type = BattleType.RANDOM_BATTLE
        self.battle.generation = "gen9"
        self.battle.pokemon_format = "gen9randombattle"

        # User side
        self.battle.user.active = Pokemon("pikachu", 50)
        self.battle.user.active.hp = 100
        self.battle.user.active.max_hp = 100
        self.battle.user.active.ability = "static"
        self.battle.user.active.item = "lightball"
        self.battle.user.active.add_move("thunderbolt")
        self.battle.user.active.add_move("quickattack")
        self.battle.user.active.add_move("irontail")
        self.battle.user.active.add_move("thunderwave")

        reserve1 = Pokemon("charizard", 50)
        reserve1.hp = 150
        reserve1.max_hp = 150
        reserve1.ability = "blaze"
        reserve1.add_move("flamethrower")
        self.battle.user.reserve.append(reserve1)

        # Opponent side
        self.battle.opponent.active = Pokemon("gyarados", 50)
        self.battle.opponent.active.hp = 150
        self.battle.opponent.active.max_hp = 150
        self.battle.opponent.active.ability = "intimidate"
        self.battle.opponent.active.add_move("waterfall")
        self.battle.opponent.active.add_move("icefang")

    @patch("fp.search.main.ProcessPoolExecutor")
    @patch("fp.search.main.prepare_random_battles")
    def test_find_best_move_with_evaluation(
        self, mock_prepare_battles, mock_executor_class
    ):
        """Test that find_best_move can return evaluation data."""
        from dataclasses import dataclass

        @dataclass
        class MockMoveChoice:
            move_choice: str
            visits: int
            total_score: float

        @dataclass
        class MockMctsResult:
            side_one: list
            total_visits: int

        # Mock the battle preparation
        mock_prepare_battles.return_value = [(self.battle, 1.0)]

        # Create realistic move choices
        mock_result = MockMctsResult(
            side_one=[
                MockMoveChoice("thunderbolt", 500, 250.0),
                MockMoveChoice("thunderwave", 300, 120.0),
                MockMoveChoice("quickattack", 150, 60.0),
                MockMoveChoice("switch charizard", 50, 20.0),
            ],
            total_visits=1000,
        )

        # Mock the executor
        mock_future = MagicMock()
        mock_future.result.return_value = mock_result

        mock_executor = MagicMock()
        mock_executor.__enter__.return_value = mock_executor
        mock_executor.submit.return_value = mock_future
        mock_executor_class.return_value = mock_executor

        # Test without evaluation (normal operation)
        best_move = find_best_move(self.battle, return_evaluation=False)
        self.assertIsInstance(best_move, str)
        self.assertIn(
            best_move,
            ["thunderbolt", "thunderwave", "quickattack", "switch charizard"],
        )

        # Test with evaluation
        best_move, evaluation = find_best_move(self.battle, return_evaluation=True)

        # Verify we get a BattleEvaluation object
        self.assertIsInstance(evaluation, BattleEvaluation)

        # Verify basic properties
        self.assertEqual(evaluation.num_scenarios, 1)
        self.assertEqual(evaluation.total_iterations, 1000)

        # Verify evaluations are present
        self.assertGreater(len(evaluation.evaluations), 0)
        self.assertIn("thunderbolt", evaluation.evaluations)

        # Verify best move has highest optimality
        best_eval = evaluation.evaluations[evaluation.best_move]
        self.assertAlmostEqual(best_eval.optimality, 1.0, places=1)

        # Verify other moves have lower optimality
        for move, move_eval in evaluation.evaluations.items():
            if move != evaluation.best_move:
                self.assertLess(move_eval.optimality, best_eval.optimality)

    @patch("fp.search.main.ProcessPoolExecutor")
    @patch("fp.search.main.prepare_random_battles")
    def test_evaluation_with_multiple_scenarios(
        self, mock_prepare_battles, mock_executor_class
    ):
        """Test evaluation with multiple battle scenarios."""
        from dataclasses import dataclass

        @dataclass
        class MockMoveChoice:
            move_choice: str
            visits: int
            total_score: float

        @dataclass
        class MockMctsResult:
            side_one: list
            total_visits: int

        # Mock two different battle scenarios
        mock_prepare_battles.return_value = [
            (self.battle, 0.7),  # 70% likely scenario
            (self.battle, 0.3),  # 30% likely scenario
        ]

        # Scenario 1: Thunderbolt is best
        result1 = MockMctsResult(
            side_one=[
                MockMoveChoice("thunderbolt", 600, 300.0),
                MockMoveChoice("thunderwave", 400, 160.0),
            ],
            total_visits=1000,
        )

        # Scenario 2: Thunder Wave is best
        result2 = MockMctsResult(
            side_one=[
                MockMoveChoice("thunderbolt", 300, 120.0),
                MockMoveChoice("thunderwave", 700, 350.0),
            ],
            total_visits=1000,
        )

        # Mock futures for both results
        mock_future1 = MagicMock()
        mock_future1.result.return_value = result1
        mock_future2 = MagicMock()
        mock_future2.result.return_value = result2

        # Mock the executor
        mock_executor = MagicMock()
        mock_executor.__enter__.return_value = mock_executor
        mock_executor.submit.side_effect = [mock_future1, mock_future2]
        mock_executor_class.return_value = mock_executor

        best_move, evaluation = find_best_move(self.battle, return_evaluation=True)

        # Should have 2 scenarios
        self.assertEqual(evaluation.num_scenarios, 2)
        self.assertEqual(evaluation.total_iterations, 2000)

        # Both moves should be in evaluation
        self.assertIn("thunderbolt", evaluation.evaluations)
        self.assertIn("thunderwave", evaluation.evaluations)

        # Verify optimality is calculated from weighted scenarios
        # Thunderbolt: 0.7 * (600/1000) + 0.3 * (300/1000) = 0.42 + 0.09 = 0.51
        # Thunder Wave: 0.7 * (400/1000) + 0.3 * (700/1000) = 0.28 + 0.21 = 0.49
        # So thunderbolt should be slightly better
        thunderbolt_score = evaluation.evaluations["thunderbolt"].raw_score
        thunderwave_score = evaluation.evaluations["thunderwave"].raw_score

        self.assertAlmostEqual(thunderbolt_score, 0.51, places=2)
        self.assertAlmostEqual(thunderwave_score, 0.49, places=2)

    @patch("fp.search.main.ProcessPoolExecutor")
    @patch("fp.search.main.prepare_random_battles")
    def test_evaluation_export_to_json(self, mock_prepare_battles, mock_executor_class):
        """Test that evaluation can be exported to JSON."""
        import json
        from dataclasses import dataclass

        @dataclass
        class MockMoveChoice:
            move_choice: str
            visits: int
            total_score: float

        @dataclass
        class MockMctsResult:
            side_one: list
            total_visits: int

        mock_prepare_battles.return_value = [(self.battle, 1.0)]

        mock_result = MockMctsResult(
            side_one=[
                MockMoveChoice("thunderbolt", 700, 350.0),
                MockMoveChoice("quickattack", 300, 120.0),
            ],
            total_visits=1000,
        )

        # Mock the executor
        mock_future = MagicMock()
        mock_future.result.return_value = mock_result

        mock_executor = MagicMock()
        mock_executor.__enter__.return_value = mock_executor
        mock_executor.submit.return_value = mock_future
        mock_executor_class.return_value = mock_executor

        best_move, evaluation = find_best_move(self.battle, return_evaluation=True)

        # Export to dict and verify it's JSON-serializable
        eval_dict = evaluation.to_dict()
        json_str = json.dumps(eval_dict)

        # Parse it back and verify structure
        parsed = json.loads(json_str)
        self.assertEqual(parsed["num_scenarios"], 1)
        self.assertIn("thunderbolt", parsed["evaluations"])
        self.assertIn("optimality", parsed["evaluations"]["thunderbolt"])


if __name__ == "__main__":
    unittest.main()
