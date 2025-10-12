"""Tests for MCP tool integration."""

import asyncio
import unittest
from unittest.mock import MagicMock, AsyncMock, patch

from fp.battle import Battle, Pokemon, Move
from fp_mcp.battle_session import BattleSession, BattleStatus


# Helper functions for test fixtures

def create_mock_websocket_client():
    """Create a standard mock websocket client."""
    mock_ws = MagicMock()
    mock_ws.send_message = AsyncMock()
    mock_ws.receive_message = AsyncMock()
    mock_ws.login = AsyncMock()
    mock_ws.search_for_match = AsyncMock()
    mock_ws.challenge_user = AsyncMock()
    mock_ws.leave_battle = AsyncMock()
    return mock_ws


def create_battle_with_active_pokemon():
    """Create a battle object with active pokemon for testing."""
    battle = Battle("test-battle")
    battle.generation = "gen9"
    battle.pokemon_format = "gen9randombattle"
    battle.user.active = Pokemon("pikachu", 100)
    battle.opponent.active = Pokemon("charizard", 100)

    # Add moves
    move = Move("thunderbolt")
    move.current_pp = 15
    move.max_pp = 24
    battle.user.active.moves = [move]

    # Add reserve
    reserve = Pokemon("blastoise", 100)
    reserve.hp = 100
    reserve.max_hp = 100
    battle.user.reserve = [reserve]

    return battle


def create_session_with_battle(battle_id="test-battle"):
    """Create a session with an active battle."""
    from fp_mcp import server
    mock_ws = create_mock_websocket_client()

    session = BattleSession(
        battle_id=battle_id,
        websocket_client=mock_ws,
        pokemon_format="gen9randombattle",
        team_dict=None
    )

    battle = create_battle_with_active_pokemon()
    battle.battle_tag = battle_id
    session.battle = battle
    session.status = BattleStatus.ACTIVE

    server.sessions[battle_id] = session
    return session


# Test classes

class TestInitiateBattle(unittest.IsolatedAsyncioTestCase):
    """Test initiate_battle tool."""

    def setUp(self):
        from fp_mcp import server
        server.sessions.clear()
        server.battle_counter = 0

    def tearDown(self):
        from fp_mcp import server
        server.sessions.clear()

    @patch("fp_mcp.server.asyncio.create_task")
    @patch("fp_mcp.server.PSWebsocketClient.create")
    async def test_initiate_battle_success(self, mock_create, mock_create_task):
        """Test successful battle initiation."""
        from fp_mcp import server

        # Mock websocket
        mock_ws = create_mock_websocket_client()
        mock_create.return_value = mock_ws

        # Mock battle loop task
        mock_task = AsyncMock()
        mock_create_task.return_value = mock_task

        # Call tool
        initiate_fn = server.initiate_battle.fn if hasattr(server.initiate_battle, 'fn') else server.initiate_battle
        result = await initiate_fn("gen9randombattle")

        # Verify response
        self.assertIn("battle_id", result)
        self.assertEqual(result["status"], "searching")
        self.assertEqual(result["format"], "gen9randombattle")
        self.assertIn("message", result)

        # Verify session created
        battle_id = result["battle_id"]
        self.assertIn(battle_id, server.sessions)

        # Verify websocket setup
        mock_create.assert_called_once()
        mock_ws.login.assert_called_once()

    @patch("fp_mcp.server.asyncio.create_task")
    @patch("fp_mcp.server.PSWebsocketClient.create")
    async def test_initiate_battle_websocket_creation_fails(self, mock_create, mock_create_task):
        """Test battle initiation when websocket creation fails."""
        from fp_mcp import server

        # Mock websocket creation to raise exception
        mock_create.side_effect = Exception("Connection failed")

        # Call tool
        initiate_fn = server.initiate_battle.fn if hasattr(server.initiate_battle, 'fn') else server.initiate_battle
        result = await initiate_fn("gen9randombattle")

        # Verify error response
        self.assertIn("error", result)
        self.assertEqual(result["status"], "error")
        self.assertIn("Connection failed", result["error"])

        # Verify no session created
        self.assertEqual(len(server.sessions), 0)

    @patch("fp_mcp.server.asyncio.create_task")
    @patch("fp_mcp.server.PSWebsocketClient.create")
    async def test_initiate_battle_generates_unique_ids(self, mock_create, mock_create_task):
        """Test that multiple battles get unique IDs."""
        from fp_mcp import server

        # Mock websocket
        mock_ws = create_mock_websocket_client()
        mock_create.return_value = mock_ws
        mock_create_task.return_value = AsyncMock()

        # Create two battles
        initiate_fn = server.initiate_battle.fn if hasattr(server.initiate_battle, 'fn') else server.initiate_battle
        result1 = await initiate_fn("gen9randombattle")
        result2 = await initiate_fn("gen9randombattle")

        # Verify different IDs
        self.assertNotEqual(result1["battle_id"], result2["battle_id"])
        self.assertEqual(len(server.sessions), 2)


class TestChallengeUser(unittest.IsolatedAsyncioTestCase):
    """Test challenge_user tool."""

    def setUp(self):
        from fp_mcp import server
        server.sessions.clear()
        server.battle_counter = 0

    def tearDown(self):
        from fp_mcp import server
        server.sessions.clear()

    @patch("fp_mcp.server.asyncio.create_task")
    @patch("fp_mcp.server.PSWebsocketClient.create")
    async def test_challenge_user_success(self, mock_create, mock_create_task):
        """Test successful user challenge."""
        from fp_mcp import server

        # Mock websocket
        mock_ws = create_mock_websocket_client()
        mock_create.return_value = mock_ws
        mock_create_task.return_value = AsyncMock()

        # Call tool
        challenge_fn = server.challenge_user.fn if hasattr(server.challenge_user, 'fn') else server.challenge_user
        result = await challenge_fn("TestOpponent", "gen9ou")

        # Verify response
        self.assertIn("battle_id", result)
        self.assertEqual(result["status"], "challenging")
        self.assertEqual(result["format"], "gen9ou")
        self.assertEqual(result["opponent"], "TestOpponent")
        self.assertIn("TestOpponent", result["message"])

    @patch("fp_mcp.server.asyncio.create_task")
    @patch("fp_mcp.server.PSWebsocketClient.create")
    async def test_challenge_user_websocket_fails(self, mock_create, mock_create_task):
        """Test challenge when websocket creation fails."""
        from fp_mcp import server

        # Mock failure
        mock_create.side_effect = Exception("Connection failed")

        # Call tool
        challenge_fn = server.challenge_user.fn if hasattr(server.challenge_user, 'fn') else server.challenge_user
        result = await challenge_fn("TestOpponent")

        # Verify error
        self.assertIn("error", result)
        self.assertEqual(result["status"], "error")


class TestGetAvailableActionsTools(unittest.IsolatedAsyncioTestCase):
    """Test get_available_actions tool."""

    def setUp(self):
        from fp_mcp import server
        server.sessions.clear()

    def tearDown(self):
        from fp_mcp import server
        server.sessions.clear()

    async def test_get_available_actions_success(self):
        """Test getting available actions successfully."""
        from fp_mcp import server

        # Create session with battle
        session = create_session_with_battle("test-actions")

        # Call tool
        actions_fn = server.get_available_actions.fn if hasattr(server.get_available_actions, 'fn') else server.get_available_actions
        result = await actions_fn("test-actions")

        # Verify response
        self.assertIn("actions", result)
        self.assertIn("constraints", result)
        self.assertIsInstance(result["actions"], list)

    async def test_get_available_actions_battle_not_found(self):
        """Test error when battle not found."""
        from fp_mcp import server

        # Call with nonexistent ID
        actions_fn = server.get_available_actions.fn if hasattr(server.get_available_actions, 'fn') else server.get_available_actions
        result = await actions_fn("nonexistent")

        # Verify error
        self.assertIn("error", result)
        self.assertIn("not found", result["error"])

    async def test_get_available_actions_battle_not_started(self):
        """Test error when battle hasn't started."""
        from fp_mcp import server

        # Create session without battle
        mock_ws = create_mock_websocket_client()
        session = BattleSession("test-no-battle", mock_ws, "gen9randombattle", None)
        session.battle = None
        session.status = BattleStatus.SEARCHING
        server.sessions["test-no-battle"] = session

        # Call tool
        actions_fn = server.get_available_actions.fn if hasattr(server.get_available_actions, 'fn') else server.get_available_actions
        result = await actions_fn("test-no-battle")

        # Verify error
        self.assertIn("error", result)
        self.assertIn("not started", result["error"].lower())


class TestMakeMoveTools(unittest.IsolatedAsyncioTestCase):
    """Test make_move tool."""

    def setUp(self):
        from fp_mcp import server
        server.sessions.clear()

    def tearDown(self):
        from fp_mcp import server
        server.sessions.clear()

    async def test_make_move_success(self):
        """Test successful move execution."""
        from fp_mcp import server

        # Create session with battle
        session = create_session_with_battle("test-move")
        session.awaiting_decision = True

        # Call tool
        make_move_fn = server.make_move.fn if hasattr(server.make_move, 'fn') else server.make_move
        result = await make_move_fn("test-move", "thunderbolt")

        # Verify response
        self.assertEqual(result["status"], "sent")
        self.assertEqual(result["action"], "thunderbolt")
        self.assertTrue(result["validation"]["valid"])

    async def test_make_move_battle_not_found(self):
        """Test error when battle not found."""
        from fp_mcp import server

        # Call with nonexistent ID
        make_move_fn = server.make_move.fn if hasattr(server.make_move, 'fn') else server.make_move
        result = await make_move_fn("nonexistent", "move")

        # Verify error
        self.assertIn("error", result)
        self.assertIn("not found", result["error"])

    async def test_make_move_not_awaiting_decision(self):
        """Test error when not awaiting decision."""
        from fp_mcp import server

        # Create session not awaiting decision
        session = create_session_with_battle("test-not-waiting")
        session.awaiting_decision = False

        # Call tool
        make_move_fn = server.make_move.fn if hasattr(server.make_move, 'fn') else server.make_move
        result = await make_move_fn("test-not-waiting", "move")

        # Verify error
        self.assertIn("error", result)
        self.assertIn("not waiting", result["error"].lower())

    async def test_make_move_invalid_action(self):
        """Test invalid action validation."""
        from fp_mcp import server

        # Create session
        session = create_session_with_battle("test-invalid")
        session.awaiting_decision = True

        # Call with invalid move
        make_move_fn = server.make_move.fn if hasattr(server.make_move, 'fn') else server.make_move
        result = await make_move_fn("test-invalid", "nonexistent-move")

        # Verify validation failure
        self.assertEqual(result["status"], "invalid")
        self.assertFalse(result["validation"]["valid"])
        self.assertIn("reason", result["validation"])


class TestForfeitBattleTools(unittest.IsolatedAsyncioTestCase):
    """Test forfeit_battle tool."""

    def setUp(self):
        from fp_mcp import server
        server.sessions.clear()

    def tearDown(self):
        from fp_mcp import server
        server.sessions.clear()

    async def test_forfeit_battle_success(self):
        """Test successful battle forfeit."""
        from fp_mcp import server

        # Create session with battle
        session = create_session_with_battle("test-forfeit")

        # Call tool
        forfeit_fn = server.forfeit_battle.fn if hasattr(server.forfeit_battle, 'fn') else server.forfeit_battle
        result = await forfeit_fn("test-forfeit")

        # Verify response
        self.assertEqual(result["status"], "forfeited")
        self.assertIn("message", result)

        # Verify session status updated
        self.assertEqual(session.status, BattleStatus.FORFEITED)

    async def test_forfeit_battle_not_found(self):
        """Test error when battle not found."""
        from fp_mcp import server

        # Call with nonexistent ID
        forfeit_fn = server.forfeit_battle.fn if hasattr(server.forfeit_battle, 'fn') else server.forfeit_battle
        result = await forfeit_fn("nonexistent")

        # Verify error
        self.assertIn("error", result)
        self.assertIn("not found", result["error"])

    async def test_forfeit_battle_before_start(self):
        """Test forfeit before battle starts."""
        from fp_mcp import server

        # Create session without battle
        mock_ws = create_mock_websocket_client()
        session = BattleSession("test-forfeit-early", mock_ws, "gen9randombattle", None)
        session.battle = None
        session.status = BattleStatus.SEARCHING
        server.sessions["test-forfeit-early"] = session

        # Call tool
        forfeit_fn = server.forfeit_battle.fn if hasattr(server.forfeit_battle, 'fn') else server.forfeit_battle
        result = await forfeit_fn("test-forfeit-early")

        # Verify success (forfeit works even without battle)
        self.assertEqual(result["status"], "forfeited")
        self.assertEqual(session.status, BattleStatus.FORFEITED)


class TestGetBattleStatePending(unittest.IsolatedAsyncioTestCase):
    """Test get_battle_state when battle is pending."""

    async def test_pending_battle_returns_message(self):
        """Test that pending battles return helpful message."""
        from fp_mcp import server

        # Create a session in SEARCHING state
        mock_ws = MagicMock()
        session = BattleSession(
            battle_id="test-pending",
            websocket_client=mock_ws,
            pokemon_format="gen9randombattle",
            team_dict=None
        )
        session.status = BattleStatus.SEARCHING
        session.battle = None  # No battle object yet

        server.sessions["test-pending"] = session

        # Call the underlying function (unwrapped)
        get_state_fn = server.get_battle_state.fn if hasattr(server.get_battle_state, 'fn') else server.get_battle_state.__wrapped__
        result = await get_state_fn("test-pending")

        # Should have helpful message
        self.assertEqual(result["battle_id"], "test-pending")
        self.assertEqual(result["status"], "searching")
        self.assertIn("message", result)
        self.assertIn("searching", result["message"].lower())
        self.assertNotIn("state", result)  # No state yet

    async def test_active_battle_returns_state(self):
        """Test that active battles return full state."""
        from fp_mcp import server

        # Create a session with active battle
        mock_ws = MagicMock()
        session = BattleSession(
            battle_id="test-active",
            websocket_client=mock_ws,
            pokemon_format="gen9randombattle",
            team_dict=None
        )

        # Create battle
        battle = Battle("test-battle")
        battle.turn = 5
        battle.generation = "gen9"
        battle.pokemon_format = "gen9randombattle"
        battle.user.active = Pokemon("pikachu", 100)
        battle.opponent.active = Pokemon("landorustherian", 100)

        session.battle = battle
        session.status = BattleStatus.ACTIVE

        server.sessions["test-active"] = session

        # Call the underlying function
        get_state_fn = server.get_battle_state.fn if hasattr(server.get_battle_state, 'fn') else server.get_battle_state.__wrapped__
        result = await get_state_fn("test-active")

        # Should have full state
        self.assertIn("state", result)
        self.assertIn("meta", result["state"])
        self.assertEqual(result["state"]["meta"]["turn"], 5)


class TestCompactReserveMode(unittest.TestCase):
    """Test compact reserve mode for token efficiency."""

    def test_compact_reserve_minimal_info(self):
        """Test that compact mode shows minimal reserve info."""
        from fp_mcp.serialization import battle_to_llm_json
        from fp.battle import Battle, Pokemon

        battle = Battle("test")
        battle.generation = "gen9"
        battle.pokemon_format = "gen9randombattle"
        battle.user.active = Pokemon("pikachu", 100)
        battle.opponent.active = Pokemon("landorustherian", 100)

        # Add reserve with full details
        reserve = Pokemon("charizard", 100)
        reserve.hp = 297
        reserve.max_hp = 297
        reserve.ability = "blaze"
        reserve.item = "leftovers"
        reserve.stats = {"attack": 293}
        battle.user.reserve = [reserve]

        # Compact mode (default)
        state = battle_to_llm_json(battle, compact_reserve=True)
        reserve_data = state["user"]["reserve"][0]

        # Should only have minimal fields
        self.assertIn("name", reserve_data)
        self.assertIn("hp", reserve_data)
        self.assertIn("status", reserve_data)
        self.assertIn("is_alive", reserve_data)

        # Should NOT have verbose fields
        self.assertNotIn("stats", reserve_data)
        self.assertNotIn("moves", reserve_data)
        self.assertNotIn("ability", reserve_data)
        self.assertNotIn("item", reserve_data)

    def test_full_reserve_complete_info(self):
        """Test that full mode shows complete reserve info."""
        from fp_mcp.serialization import battle_to_llm_json
        from fp.battle import Battle, Pokemon

        battle = Battle("test")
        battle.generation = "gen9"
        battle.pokemon_format = "gen9randombattle"
        battle.user.active = Pokemon("pikachu", 100)
        battle.opponent.active = Pokemon("landorustherian", 100)

        reserve = Pokemon("charizard", 100)
        reserve.hp = 297
        reserve.max_hp = 297
        reserve.ability = "blaze"
        reserve.item = "leftovers"
        reserve.stats = {"attack": 293}
        battle.user.reserve = [reserve]

        # Full mode
        state = battle_to_llm_json(battle, compact_reserve=False)
        reserve_data = state["user"]["reserve"][0]

        # Should have all fields
        self.assertIn("name", reserve_data)
        self.assertIn("hp", reserve_data)
        self.assertIn("stats", reserve_data)
        self.assertIn("ability", reserve_data)
        self.assertIn("item", reserve_data)


class TestGetPokemonDetails(unittest.IsolatedAsyncioTestCase):
    """Test get_pokemon_details tool."""

    async def test_get_user_pokemon_details(self):
        """Test getting details about user's pokemon."""
        from fp_mcp import server
        from fp.battle import Battle, Pokemon, Move

        # Setup battle
        mock_ws = MagicMock()
        session = BattleSession(
            battle_id="test-details",
            websocket_client=mock_ws,
            pokemon_format="gen9randombattle",
            team_dict=None
        )

        battle = Battle("test-battle")
        battle.generation = "gen9"
        battle.user.active = Pokemon("pikachu", 100)

        # Add reserve with moves
        reserve = Pokemon("charizard", 100)
        reserve.hp = 297
        reserve.max_hp = 297
        reserve.ability = "blaze"
        reserve.item = "leftovers"

        move = Move("flamethrower")
        move.current_pp = 24
        move.max_pp = 24
        reserve.moves = [move]

        battle.user.reserve = [reserve]
        battle.opponent.active = Pokemon("landorustherian", 100)

        session.battle = battle
        server.sessions["test-details"] = session

        # Call the underlying function
        get_details_fn = server.get_pokemon_details.fn if hasattr(server.get_pokemon_details, 'fn') else server.get_pokemon_details.__wrapped__
        result = await get_details_fn("test-details", "charizard", opponent=False)

        # Should have full details
        self.assertEqual(result["name"], "charizard")
        self.assertEqual(result["ability"], "blaze")
        self.assertEqual(result["item"], "leftovers")
        self.assertIn("moves", result)
        self.assertEqual(len(result["moves"]), 1)
        self.assertEqual(result["moves"][0]["name"], "flamethrower")

    async def test_get_nonexistent_pokemon(self):
        """Test getting details for pokemon that doesn't exist."""
        from fp_mcp import server
        from fp.battle import Battle, Pokemon

        mock_ws = MagicMock()
        session = BattleSession(
            battle_id="test-missing",
            websocket_client=mock_ws,
            pokemon_format="gen9randombattle",
            team_dict=None
        )

        battle = Battle("test-battle")
        battle.user.active = Pokemon("pikachu", 100)
        battle.opponent.active = Pokemon("landorustherian", 100)
        battle.user.reserve = [Pokemon("charizard", 100)]

        session.battle = battle
        server.sessions["test-missing"] = session

        # Call the underlying function
        get_details_fn = server.get_pokemon_details.fn if hasattr(server.get_pokemon_details, 'fn') else server.get_pokemon_details.__wrapped__
        result = await get_details_fn("test-missing", "blastoise", opponent=False)

        # Should return error
        self.assertIn("error", result)
        self.assertIn("not found", result["error"])
        self.assertIn("available_pokemon", result)
        self.assertIn("pikachu", result["available_pokemon"])
        self.assertIn("charizard", result["available_pokemon"])


if __name__ == "__main__":
    unittest.main()
