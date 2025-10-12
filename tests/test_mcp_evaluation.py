"""Tests for MCP move evaluation integration."""

import unittest
from unittest.mock import patch, AsyncMock, MagicMock

from fp.battle import Battle, Pokemon, Move
from fp.evaluate import BattleEvaluation, MoveEvaluation


class TestMCPEvaluationIntegration(unittest.IsolatedAsyncioTestCase):
    """Test evaluation integration in MCP make_move tool."""

    def setUp(self):
        from fp_mcp import server
        server.sessions.clear()

    def tearDown(self):
        from fp_mcp import server
        server.sessions.clear()

    async def test_make_move_returns_optimality_optimal_move(self):
        """Test that make_move returns optimality score for optimal move."""
        from fp_mcp import server
        from fp_mcp.battle_session import BattleSession, BattleStatus

        # Create battle with moves
        battle = Battle("test-battle")
        battle.generation = "gen9"
        battle.user.active = Pokemon("pikachu", 50)
        move = Move("thunderbolt")
        move.current_pp = 15
        move.max_pp = 24
        battle.user.active.moves = [move]
        battle.opponent.active = Pokemon("gyarados", 50)

        # Create session
        mock_ws = MagicMock()
        session = BattleSession("test-eval", mock_ws, "gen9randombattle", None)
        session.awaiting_decision = True
        session.battle = battle
        session.status = BattleStatus.ACTIVE
        session.submit_decision = AsyncMock()
        server.sessions["test-eval"] = session

        # Mock evaluation
        mock_eval = BattleEvaluation(
            best_move="thunderbolt",
            evaluations={
                "thunderbolt": MoveEvaluation("thunderbolt", 1.0, 0.8, 0.5, 0.8),
            },
            num_scenarios=2,
            total_iterations=1000,
        )

        with patch('fp_mcp.server.run_evaluation') as mock_run_eval:
            mock_run_eval.return_value = mock_eval
            with patch('fp_mcp.server.validate_action') as mock_validate:
                mock_validate.return_value = (True, None)

                # Call make_move
                make_move_fn = server.make_move.fn if hasattr(server.make_move, 'fn') else server.make_move
                result = await make_move_fn("test-eval", "thunderbolt")

                # Verify response includes evaluation
                self.assertEqual(result["status"], "sent")
                self.assertIn("evaluation", result)
                self.assertIsNotNone(result["evaluation"])

                # Check evaluation fields
                eval_data = result["evaluation"]
                self.assertEqual(eval_data["optimality"], 1.0)
                self.assertEqual(eval_data["best_move"], "thunderbolt")
                self.assertTrue(eval_data["is_optimal"])
                self.assertEqual(eval_data["scenarios_analyzed"], 2)

    async def test_make_move_returns_optimality_suboptimal_move(self):
        """Test that make_move returns correct optimality for suboptimal move."""
        from fp_mcp import server
        from fp_mcp.battle_session import BattleSession, BattleStatus

        # Create battle
        battle = Battle("test-battle")
        battle.generation = "gen9"
        battle.user.active = Pokemon("pikachu", 50)
        move1 = Move("thunderbolt")
        move1.current_pp = 15
        move2 = Move("quickattack")
        move2.current_pp = 20
        battle.user.active.moves = [move1, move2]
        battle.opponent.active = Pokemon("gyarados", 50)

        # Create session
        mock_ws = MagicMock()
        session = BattleSession("test-suboptimal", mock_ws, "gen9randombattle", None)
        session.awaiting_decision = True
        session.battle = battle
        session.status = BattleStatus.ACTIVE
        session.submit_decision = AsyncMock()
        server.sessions["test-suboptimal"] = session

        # Mock evaluation - quickattack is suboptimal
        mock_eval = BattleEvaluation(
            best_move="thunderbolt",
            evaluations={
                "thunderbolt": MoveEvaluation("thunderbolt", 1.0, 0.9, 0.6, 0.9),
                "quickattack": MoveEvaluation("quickattack", 0.3, 0.1, -0.2, 0.1),
            },
            num_scenarios=3,
            total_iterations=1500,
        )

        with patch('fp_mcp.server.run_evaluation') as mock_run_eval:
            mock_run_eval.return_value = mock_eval
            with patch('fp_mcp.server.validate_action') as mock_validate:
                mock_validate.return_value = (True, None)

                # Call with suboptimal move
                make_move_fn = server.make_move.fn if hasattr(server.make_move, 'fn') else server.make_move
                result = await make_move_fn("test-suboptimal", "quickattack")

                # Verify low optimality
                self.assertEqual(result["status"], "sent")
                eval_data = result["evaluation"]
                self.assertEqual(eval_data["optimality"], 0.3)
                self.assertEqual(eval_data["best_move"], "thunderbolt")
                self.assertFalse(eval_data["is_optimal"])

    async def test_make_move_evaluation_disabled(self):
        """Test that evaluation can be disabled."""
        from fp_mcp import server
        from fp_mcp.battle_session import BattleSession, BattleStatus

        # Temporarily disable evaluation
        original_value = server.ENABLE_EVALUATION
        server.ENABLE_EVALUATION = False

        try:
            # Create battle
            battle = Battle("test-battle")
            battle.generation = "gen9"
            battle.user.active = Pokemon("pikachu", 50)
            move = Move("thunderbolt")
            move.current_pp = 15
            battle.user.active.moves = [move]
            battle.opponent.active = Pokemon("gyarados", 50)

            # Create session
            mock_ws = MagicMock()
            session = BattleSession("test-disabled", mock_ws, "gen9randombattle", None)
            session.awaiting_decision = True
            session.battle = battle
            session.status = BattleStatus.ACTIVE
            session.submit_decision = AsyncMock()
            server.sessions["test-disabled"] = session

            with patch('fp_mcp.server.validate_action') as mock_validate:
                mock_validate.return_value = (True, None)

                # Call make_move
                make_move_fn = server.make_move.fn if hasattr(server.make_move, 'fn') else server.make_move
                result = await make_move_fn("test-disabled", "thunderbolt")

                # Verify no evaluation
                self.assertEqual(result["status"], "sent")
                self.assertIsNone(result["evaluation"])

        finally:
            server.ENABLE_EVALUATION = original_value

    async def test_make_move_evaluation_fails_gracefully(self):
        """Test that move still sent if evaluation fails."""
        from fp_mcp import server
        from fp_mcp.battle_session import BattleSession, BattleStatus

        # Create battle
        battle = Battle("test-battle")
        battle.generation = "gen9"
        battle.user.active = Pokemon("pikachu", 50)
        move = Move("thunderbolt")
        move.current_pp = 15
        battle.user.active.moves = [move]
        battle.opponent.active = Pokemon("gyarados", 50)

        # Create session
        mock_ws = MagicMock()
        session = BattleSession("test-fail", mock_ws, "gen9randombattle", None)
        session.awaiting_decision = True
        session.battle = battle
        session.status = BattleStatus.ACTIVE
        session.submit_decision = AsyncMock()
        server.sessions["test-fail"] = session

        with patch('fp_mcp.server.run_evaluation') as mock_run_eval:
            # Make evaluation return None (failure)
            mock_run_eval.return_value = None
            with patch('fp_mcp.server.validate_action') as mock_validate:
                mock_validate.return_value = (True, None)

                # Call make_move
                make_move_fn = server.make_move.fn if hasattr(server.make_move, 'fn') else server.make_move
                result = await make_move_fn("test-fail", "thunderbolt")

                # Verify move still sent, evaluation is None
                self.assertEqual(result["status"], "sent")
                self.assertIsNone(result["evaluation"])
                session.submit_decision.assert_called_once()

    async def test_make_move_invalid_still_no_evaluation(self):
        """Test that invalid moves don't trigger evaluation."""
        from fp_mcp import server
        from fp_mcp.battle_session import BattleSession, BattleStatus

        # Create battle
        battle = Battle("test-battle")
        battle.generation = "gen9"
        battle.user.active = Pokemon("pikachu", 50)
        move = Move("thunderbolt")
        move.current_pp = 15
        battle.user.active.moves = [move]
        battle.opponent.active = Pokemon("gyarados", 50)

        # Create session
        mock_ws = MagicMock()
        session = BattleSession("test-invalid", mock_ws, "gen9randombattle", None)
        session.awaiting_decision = True
        session.battle = battle
        session.status = BattleStatus.ACTIVE
        session.submit_decision = AsyncMock()
        server.sessions["test-invalid"] = session

        with patch('fp_mcp.server.run_evaluation') as mock_run_eval:
            with patch('fp_mcp.server.validate_action') as mock_validate:
                # Make validation fail
                mock_validate.return_value = (False, "Move not available")

                # Call make_move with invalid move
                make_move_fn = server.make_move.fn if hasattr(server.make_move, 'fn') else server.make_move
                result = await make_move_fn("test-invalid", "fly")

                # Verify evaluation was not called
                mock_run_eval.assert_not_called()
                self.assertEqual(result["status"], "invalid")

    async def test_make_move_move_not_in_evaluation(self):
        """Test handling when chosen move not in MCTS evaluation."""
        from fp_mcp import server
        from fp_mcp.battle_session import BattleSession, BattleStatus

        # Create battle
        battle = Battle("test-battle")
        battle.generation = "gen9"
        battle.user.active = Pokemon("pikachu", 50)
        move = Move("thunderbolt")
        move.current_pp = 15
        battle.user.active.moves = [move]
        battle.opponent.active = Pokemon("gyarados", 50)

        # Create session
        mock_ws = MagicMock()
        session = BattleSession("test-missing", mock_ws, "gen9randombattle", None)
        session.awaiting_decision = True
        session.battle = battle
        session.status = BattleStatus.ACTIVE
        session.submit_decision = AsyncMock()
        server.sessions["test-missing"] = session

        # Mock evaluation without thunderbolt
        mock_eval = BattleEvaluation(
            best_move="voltswitch",
            evaluations={
                "voltswitch": MoveEvaluation("voltswitch", 1.0, 0.9, 0.5, 0.9),
            },
            num_scenarios=2,
            total_iterations=1000,
        )

        with patch('fp_mcp.server.run_evaluation') as mock_run_eval:
            mock_run_eval.return_value = mock_eval
            with patch('fp_mcp.server.validate_action') as mock_validate:
                mock_validate.return_value = (True, None)

                # Call make_move with move not in evaluation
                make_move_fn = server.make_move.fn if hasattr(server.make_move, 'fn') else server.make_move
                result = await make_move_fn("test-missing", "thunderbolt")

                # Verify optimality is 0.0 for missing move
                self.assertEqual(result["status"], "sent")
                eval_data = result["evaluation"]
                self.assertEqual(eval_data["optimality"], 0.0)
                self.assertEqual(eval_data["best_move"], "voltswitch")
                self.assertFalse(eval_data["is_optimal"])


class TestRunEvaluationFunction(unittest.IsolatedAsyncioTestCase):
    """Test the run_evaluation helper function."""

    async def test_run_evaluation_success(self):
        """Test successful evaluation."""
        from fp_mcp.server import run_evaluation

        # Create simple battle
        battle = Battle("test")
        battle.generation = "gen9"
        battle.user.active = Pokemon("pikachu", 50)
        move = Move("thunderbolt")
        move.current_pp = 15
        battle.user.active.moves = [move]
        battle.opponent.active = Pokemon("gyarados", 50)

        # Mock find_best_move
        mock_eval = BattleEvaluation(
            best_move="thunderbolt",
            evaluations={
                "thunderbolt": MoveEvaluation("thunderbolt", 1.0, 0.9, 0.5, 0.9),
            },
            num_scenarios=1,
            total_iterations=100,
        )

        with patch('fp_mcp.server.find_best_move') as mock_find:
            mock_find.return_value = ("thunderbolt", mock_eval)

            result = await run_evaluation(battle, "thunderbolt")

            # Verify result
            self.assertIsNotNone(result)
            self.assertEqual(result.best_move, "thunderbolt")
            self.assertEqual(result.num_scenarios, 1)

    async def test_run_evaluation_handles_exceptions(self):
        """Test that run_evaluation handles exceptions gracefully."""
        from fp_mcp.server import run_evaluation

        battle = Battle("test")
        battle.generation = "gen9"
        battle.user.active = Pokemon("pikachu", 50)
        battle.opponent.active = Pokemon("gyarados", 50)

        # Mock find_best_move to raise exception
        with patch('fp_mcp.server.find_best_move') as mock_find:
            mock_find.side_effect = Exception("MCTS failed")

            result = await run_evaluation(battle, "thunderbolt")

            # Should return None, not raise
            self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
