"""Tests for MCP serialization functions."""

import unittest

from fp.battle import Battle, Battler, Pokemon, Move
from fp_mcp.serialization import (
    pokemon_to_dict,
    battler_to_dict,
    battle_to_llm_json,
    get_available_actions,
    validate_action,
    get_move_details,
)
import constants


class TestPokemonToDict(unittest.TestCase):
    """Test pokemon serialization."""

    def setUp(self):
        """Create test pokemon."""
        self.pokemon = Pokemon("pikachu", 100)
        self.pokemon.hp = 250
        self.pokemon.max_hp = 250
        self.pokemon.ability = "static"
        self.pokemon.item = "lightball"
        self.pokemon.status = None
        self.pokemon.types = ("electric",)
        self.pokemon.tera_type = "electric"
        self.pokemon.terastallized = False

        # Add moves
        move1 = Move("thunderbolt")
        move1.current_pp = 24
        move1.max_pp = 24
        move1.disabled = False
        self.pokemon.moves = [move1]

        # Stats and boosts
        self.pokemon.stats = {
            constants.ATTACK: 229,
            constants.DEFENSE: 196,
            constants.SPECIAL_ATTACK: 229,
            constants.SPECIAL_DEFENSE: 229,
            constants.SPEED: 306,
        }
        self.pokemon.boosts = {
            constants.ATTACK: 0,
            constants.DEFENSE: 0,
            constants.SPECIAL_ATTACK: 0,
            constants.SPECIAL_DEFENSE: 0,
            constants.SPEED: 0,
        }

    def test_basic_serialization(self):
        """Test basic pokemon serialization."""
        result = pokemon_to_dict(self.pokemon)

        self.assertEqual(result["name"], "pikachu")
        self.assertEqual(result["level"], 100)
        self.assertEqual(result["hp"], 250)
        self.assertEqual(result["max_hp"], 250)
        self.assertEqual(result["ability"], "static")
        self.assertEqual(result["item"], "lightball")
        self.assertIsNone(result["status"])
        self.assertTrue(result["is_alive"])
        self.assertFalse(result["fainted"])

    def test_moves_serialization(self):
        """Test moves are serialized correctly."""
        result = pokemon_to_dict(self.pokemon)

        self.assertEqual(len(result["moves"]), 1)
        move = result["moves"][0]
        self.assertEqual(move["name"], "thunderbolt")
        self.assertEqual(move["pp"], 24)
        self.assertEqual(move["max_pp"], 24)
        self.assertFalse(move["disabled"])
        self.assertIn("type", move)  # Should include move details
        self.assertIn("category", move)
        self.assertIn("power", move)

    def test_hide_unknowns(self):
        """Test hiding unknown opponent info."""
        self.pokemon.item = constants.UNKNOWN_ITEM
        self.pokemon.ability = None

        result = pokemon_to_dict(self.pokemon, hide_unknowns=True)

        self.assertEqual(result["item"], "unknown")
        self.assertEqual(result["ability"], "unknown")

    def test_fainted_pokemon(self):
        """Test fainted pokemon serialization."""
        self.pokemon.hp = 0
        self.pokemon.fainted = True  # Need to explicitly set fainted flag

        result = pokemon_to_dict(self.pokemon)

        self.assertEqual(result["hp"], 0)
        self.assertFalse(result["is_alive"])
        self.assertTrue(result["fainted"])


class TestBattleToLLMJson(unittest.TestCase):
    """Test complete battle serialization."""

    def setUp(self):
        """Create test battle."""
        self.battle = Battle("test-battle-123")
        self.battle.turn = 5
        self.battle.time_remaining = 120
        self.battle.generation = "gen9"
        self.battle.pokemon_format = "gen9randombattle"
        self.battle.force_switch = False
        self.battle.wait = False

        # User's active pokemon
        self.battle.user.active = Pokemon("pikachu", 100)
        self.battle.user.active.hp = 250
        self.battle.user.active.max_hp = 250
        self.battle.user.active.ability = "static"
        self.battle.user.active.item = "lightball"
        self.battle.user.active.can_terastallize = True

        move = Move("thunderbolt")
        move.current_pp = 24
        move.max_pp = 24
        move.disabled = False
        self.battle.user.active.moves = [move]

        # Opponent's active pokemon
        self.battle.opponent.active = Pokemon("landorustherian", 100)
        self.battle.opponent.active.hp = 270
        self.battle.opponent.active.max_hp = 312
        self.battle.opponent.active.ability = "intimidate"
        self.battle.opponent.active.item = constants.UNKNOWN_ITEM

        # Field conditions
        self.battle.weather = constants.RAIN
        self.battle.weather_turns_remaining = 3
        self.battle.field = None
        self.battle.trick_room = False

    def test_meta_information(self):
        """Test meta information is serialized."""
        result = battle_to_llm_json(self.battle)

        meta = result["meta"]
        self.assertEqual(meta["turn"], 5)
        self.assertEqual(meta["time_remaining"], 120)
        self.assertEqual(meta["generation"], "gen9")
        self.assertEqual(meta["format"], "gen9randombattle")
        self.assertFalse(meta["force_switch"])
        self.assertFalse(meta["wait"])

    def test_user_information(self):
        """Test user pokemon serialization."""
        result = battle_to_llm_json(self.battle)

        user = result["user"]
        self.assertIsNotNone(user["active"])
        self.assertEqual(user["active"]["name"], "pikachu")
        self.assertEqual(user["active"]["hp"], 250)
        self.assertEqual(user["active"]["ability"], "static")
        self.assertEqual(user["active"]["item"], "lightball")

    def test_opponent_information(self):
        """Test opponent pokemon serialization with hidden info."""
        result = battle_to_llm_json(self.battle)

        opponent = result["opponent"]
        self.assertIsNotNone(opponent["active"])
        self.assertEqual(opponent["active"]["name"], "landorustherian")
        self.assertEqual(opponent["active"]["hp"], 270)
        self.assertEqual(opponent["active"]["ability"], "intimidate")
        # Item should be hidden
        self.assertEqual(opponent["active"]["item"], "unknown")

    def test_field_conditions(self):
        """Test field conditions serialization."""
        result = battle_to_llm_json(self.battle)

        field = result["field"]
        self.assertEqual(field["weather"], constants.RAIN)
        self.assertEqual(field["weather_turns_remaining"], 3)
        self.assertIsNone(field["terrain"])
        self.assertFalse(field["trick_room"])

    def test_available_actions(self):
        """Test available actions are included."""
        result = battle_to_llm_json(self.battle)

        actions = result["available_actions"]
        self.assertIsInstance(actions, list)
        self.assertIn("thunderbolt", actions)
        # Should include tera variant
        self.assertIn("thunderbolt-tera", actions)

    def test_capabilities(self):
        """Test capability flags are included."""
        result = battle_to_llm_json(self.battle)

        caps = result["capabilities"]
        self.assertFalse(caps["can_mega"])
        self.assertTrue(caps["can_tera"])
        self.assertFalse(caps["can_dynamax"])
        self.assertFalse(caps["trapped"])


class TestGetAvailableActions(unittest.TestCase):
    """Test available actions computation."""

    def setUp(self):
        """Create test battle."""
        self.battle = Battle("test-battle")
        self.battle.user.active = Pokemon("pikachu", 100)
        self.battle.user.active.can_terastallize = True
        self.battle.user.active.can_mega_evo = False

        # Add moves
        move1 = Move("thunderbolt")
        move1.disabled = False
        move1.current_pp = 24

        move2 = Move("voltswitch")
        move2.disabled = False
        move2.current_pp = 32

        move3 = Move("irontail")
        move3.disabled = True  # Disabled move
        move3.current_pp = 0

        self.battle.user.active.moves = [move1, move2, move3]

        # Add reserve pokemon
        reserve = Pokemon("charizard", 100)
        reserve.hp = 297
        reserve.max_hp = 297
        self.battle.user.reserve = [reserve]

        self.battle.force_switch = False
        self.battle.user.trapped = False

    def test_regular_turn_actions(self):
        """Test available actions on regular turn."""
        actions = get_available_actions(self.battle)

        # Should have enabled moves
        self.assertIn("thunderbolt", actions)
        self.assertIn("voltswitch", actions)
        # Should NOT have disabled move
        self.assertNotIn("irontail", actions)

        # Should have tera variants
        self.assertIn("thunderbolt-tera", actions)
        self.assertIn("voltswitch-tera", actions)

        # Should have switch option
        self.assertIn("switch charizard", actions)

    def test_force_switch_actions(self):
        """Test available actions when forced to switch."""
        self.battle.force_switch = True

        actions = get_available_actions(self.battle)

        # Should ONLY have switch option
        self.assertEqual(actions, ["switch charizard"])
        self.assertNotIn("thunderbolt", actions)

    def test_trapped_no_switches(self):
        """Test no switches available when trapped."""
        self.battle.user.trapped = True

        actions = get_available_actions(self.battle)

        # Should have moves
        self.assertIn("thunderbolt", actions)
        self.assertIn("voltswitch", actions)
        # Should NOT have switches
        self.assertNotIn("switch charizard", actions)

    def test_fainted_reserve_not_available(self):
        """Test fainted reserve pokemon are not switch options."""
        self.battle.user.reserve[0].hp = 0

        actions = get_available_actions(self.battle)

        # Should not have switch to fainted pokemon
        self.assertNotIn("switch charizard", actions)
        # Should still have moves
        self.assertIn("thunderbolt", actions)

    def test_mega_evolution_variant(self):
        """Test mega evolution move variants."""
        self.battle.user.active.can_mega_evo = True

        actions = get_available_actions(self.battle)

        # Should have mega variants
        self.assertIn("thunderbolt-mega", actions)
        self.assertIn("voltswitch-mega", actions)


class TestValidateAction(unittest.TestCase):
    """Test action validation."""

    def setUp(self):
        """Create test battle."""
        self.battle = Battle("test-battle")
        self.battle.user.active = Pokemon("pikachu", 100)

        move = Move("thunderbolt")
        move.disabled = False
        move.current_pp = 24
        self.battle.user.active.moves = [move]

        reserve = Pokemon("charizard", 100)
        reserve.hp = 297
        self.battle.user.reserve = [reserve]

        self.battle.force_switch = False
        self.battle.user.trapped = False

    def test_valid_move(self):
        """Test validating a valid move."""
        is_valid, error = validate_action(self.battle, "thunderbolt")

        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_invalid_move(self):
        """Test validating an invalid move."""
        is_valid, error = validate_action(self.battle, "flamethrower")

        self.assertFalse(is_valid)
        self.assertIsNotNone(error)
        self.assertIn("not legal", error)
        self.assertIn("thunderbolt", error)  # Should suggest available moves

    def test_valid_switch(self):
        """Test validating a valid switch."""
        is_valid, error = validate_action(self.battle, "switch charizard")

        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_invalid_switch(self):
        """Test validating switch to non-existent pokemon."""
        is_valid, error = validate_action(self.battle, "switch blastoise")

        self.assertFalse(is_valid)
        self.assertIsNotNone(error)

    def test_force_switch_rejects_moves(self):
        """Test that moves are rejected when forced to switch."""
        self.battle.force_switch = True

        is_valid, error = validate_action(self.battle, "thunderbolt")

        self.assertFalse(is_valid)
        self.assertIsNotNone(error)


class TestGetMoveDetails(unittest.TestCase):
    """Test move details lookup."""

    def test_existing_move(self):
        """Test getting details for existing move."""
        details = get_move_details("thunderbolt")

        self.assertEqual(details["name"], "thunderbolt")
        self.assertEqual(details["type"], "electric")
        self.assertEqual(details["category"], "special")
        self.assertEqual(details["power"], 90)
        self.assertEqual(details["accuracy"], 100)

    def test_nonexistent_move(self):
        """Test getting details for non-existent move."""
        details = get_move_details("fakemove")

        self.assertEqual(details["name"], "fakemove")
        self.assertIn("error", details)


if __name__ == "__main__":
    unittest.main()
