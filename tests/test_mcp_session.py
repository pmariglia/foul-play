"""Tests for MCP battle session management."""

import asyncio
import unittest
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock

from fp_mcp.battle_session import BattleSession, BattleStatus
from fp.battle import Battle


class TestBattleSession(unittest.TestCase):
    """Test BattleSession class."""

    def setUp(self):
        """Create test session."""
        self.mock_websocket = MagicMock()
        self.mock_websocket.send_message = AsyncMock()

        self.session = BattleSession(
            battle_id="test-battle-123",
            websocket_client=self.mock_websocket,
            pokemon_format="gen9randombattle",
            team_dict=None,
        )

    def test_initialization(self):
        """Test session initialization."""
        self.assertEqual(self.session.battle_id, "test-battle-123")
        self.assertEqual(self.session.pokemon_format, "gen9randombattle")
        self.assertEqual(self.session.status, BattleStatus.INITIALIZING)
        self.assertFalse(self.session.awaiting_decision)
        self.assertIsNone(self.session.battle)
        self.assertIsNone(self.session.winner)

    def test_update_state(self):
        """Test updating battle state."""
        battle = Battle("test-battle")
        battle.turn = 5

        self.session.update_state(battle)

        self.assertEqual(self.session.battle, battle)
        self.assertEqual(self.session.turn_count, 5)
        self.assertIsNotNone(self.session.last_state_update)

    def test_status_transition(self):
        """Test status transitions."""
        self.session.status = BattleStatus.SEARCHING

        battle = Battle("test-battle")
        self.session.update_state(battle)

        # Should transition to FOUND
        self.assertEqual(self.session.status, BattleStatus.FOUND)

    def test_mark_finished(self):
        """Test marking battle as finished."""
        self.session.mark_finished(winner="TestPlayer")

        self.assertEqual(self.session.status, BattleStatus.FINISHED)
        self.assertEqual(self.session.winner, "TestPlayer")
        self.assertFalse(self.session.awaiting_decision)

    def test_mark_error(self):
        """Test marking battle with error."""
        self.session.mark_error("Connection lost")

        self.assertEqual(self.session.status, BattleStatus.ERROR)
        self.assertEqual(self.session.error_message, "Connection lost")
        self.assertFalse(self.session.awaiting_decision)

    def test_forfeit(self):
        """Test forfeiting battle."""
        self.session.forfeit()

        self.assertEqual(self.session.status, BattleStatus.FORFEITED)
        self.assertFalse(self.session.awaiting_decision)

    def test_to_dict(self):
        """Test serialization to dict."""
        battle = Battle("test-battle")
        battle.turn = 3
        self.session.update_state(battle)
        self.session.mark_finished(winner="Player1")

        result = self.session.to_dict()

        self.assertEqual(result["battle_id"], "test-battle-123")
        self.assertEqual(result["status"], "finished")
        self.assertEqual(result["turn"], 3)
        self.assertEqual(result["winner"], "Player1")
        self.assertEqual(result["format"], "gen9randombattle")
        self.assertIn("last_update", result)

    def test_repr(self):
        """Test string representation."""
        self.session.turn_count = 5

        repr_str = repr(self.session)

        self.assertIn("test-battle-123", repr_str)
        self.assertIn("initializing", repr_str)
        self.assertIn("5", repr_str)


class TestBattleSessionAsync(unittest.IsolatedAsyncioTestCase):
    """Test async methods of BattleSession."""

    async def asyncSetUp(self):
        """Create test session."""
        self.mock_websocket = MagicMock()
        self.session = BattleSession(
            battle_id="test-battle-async",
            websocket_client=self.mock_websocket,
            pokemon_format="gen9randombattle",
            team_dict=None,
        )
        self.session.battle = Battle("test-battle")

    async def test_submit_decision(self):
        """Test submitting a decision."""
        self.session.awaiting_decision = True

        # Submit decision in background
        submit_task = asyncio.create_task(
            self.session.submit_decision("thunderbolt")
        )

        # Give it a moment to queue
        await asyncio.sleep(0.01)

        # Should be in queue
        self.assertFalse(self.session.decision_queue.empty())

        # Get decision
        decision = await self.session.decision_queue.get()
        self.assertEqual(decision, "thunderbolt")

        await submit_task

    async def test_submit_decision_not_awaiting(self):
        """Test submitting when not awaiting raises error."""
        self.session.awaiting_decision = False

        with self.assertRaises(ValueError):
            await self.session.submit_decision("thunderbolt")

    async def test_wait_for_decision_success(self):
        """Test waiting for decision successfully."""
        # Queue a decision
        await self.session.decision_queue.put("voltswitch")

        # Wait for it
        decision = await self.session.wait_for_decision(timeout=1.0)

        self.assertEqual(decision, "voltswitch")

    async def test_wait_for_decision_timeout(self):
        """Test waiting for decision times out."""
        with self.assertRaises(asyncio.TimeoutError):
            await self.session.wait_for_decision(timeout=0.1)

    async def test_wait_for_decision_sets_flags(self):
        """Test wait_for_decision sets awaiting_decision flag."""
        # Start waiting in background
        wait_task = asyncio.create_task(
            self.session.wait_for_decision(timeout=1.0)
        )

        # Give it a moment to start
        await asyncio.sleep(0.01)

        # Should be awaiting
        self.assertTrue(self.session.awaiting_decision)
        self.assertEqual(self.session.status, BattleStatus.WAITING_MOVE)

        # Submit decision
        await self.session.submit_decision("thunderbolt")

        # Wait for completion
        decision = await wait_task

        # Should no longer be awaiting
        self.assertFalse(self.session.awaiting_decision)
        self.assertEqual(decision, "thunderbolt")


if __name__ == "__main__":
    unittest.main()
