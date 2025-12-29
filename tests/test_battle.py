import unittest

from fp.battle import LastUsedMove
from fp.battle import Battler
from fp.battle import Pokemon
from fp.battle import Move


class TestPokemon(unittest.TestCase):
    def test_alternate_pokemon_name_initializes(self):
        name = "florgeswhite"
        Pokemon(name, 100)

    def test_get_mega_formes_one_mega(self):
        self.assertEqual(
            Pokemon("venusaur", 100).get_mega_pkmn_info(),
            [("venusaurmega", "venusaurite")],
        )

    def test_get_mega_formes_two_mega(self):
        self.assertEqual(
            Pokemon("charizard", 100).get_mega_pkmn_info(),
            [("charizardmegax", "charizarditex"), ("charizardmegay", "charizarditey")],
        )

    def test_get_mega_formes_none(self):
        self.assertEqual(Pokemon("umbreon", 100).get_mega_pkmn_info(), [])

    def test_does_not_get_legends_za_mega_forme(self):
        self.assertEqual(Pokemon("emboar", 100).get_mega_pkmn_info(), [])


class TestBattlerActiveLockedIntoMove(unittest.TestCase):
    def setUp(self):
        self.battler = Battler()
        self.battler.active = Pokemon("pikachu", 100)
        self.battler.active.moves = [
            Move("thunderbolt"),
            Move("volttackle"),
            Move("agility"),
            Move("doubleteam"),
        ]

    def test_choice_item_with_previous_move_used_by_this_pokemon_returns_true(self):
        self.battler.active.item = "choicescarf"
        self.battler.last_used_move = LastUsedMove(
            pokemon_name="pikachu", move="volttackle", turn=0
        )

        self.battler.lock_moves()

        self.assertFalse(self.battler.active.get_move("volttackle").disabled)

        self.assertTrue(self.battler.active.get_move("thunderbolt").disabled)
        self.assertTrue(self.battler.active.get_move("agility").disabled)
        self.assertTrue(self.battler.active.get_move("doubleteam").disabled)

    def test_firstimpression_gets_locked_when_last_used_move_was_by_the_active_pokemon(
        self,
    ):
        self.battler.active.moves.append(Move("firstimpression"))
        self.battler.last_used_move = LastUsedMove(
            pokemon_name="pikachu",  # the current active pokemon
            move="volttackle",
            turn=0,
        )

        self.battler.lock_moves()

        self.assertTrue(self.battler.active.get_move("firstimpression").disabled)

    def test_taunt_locks_status_move(self):
        self.battler.active.moves.append(Move("calmmind"))
        self.battler.active.volatile_statuses.append("taunt")

        self.battler.lock_moves()

        self.assertTrue(self.battler.active.get_move("calmmind").disabled)

    def test_taunt_does_not_lock_physical_move(self):
        self.battler.active.moves.append(Move("tackle"))
        self.battler.active.volatile_statuses.append("taunt")

        self.battler.lock_moves()

        self.assertFalse(self.battler.active.get_move("tackle").disabled)

    def test_taunt_does_not_lock_special_move(self):
        self.battler.active.moves.append(Move("watergun"))
        self.battler.active.volatile_statuses.append("taunt")

        self.battler.lock_moves()

        self.assertFalse(self.battler.active.get_move("watergun").disabled)

    def test_taunt_with_multiple_moves(self):
        self.battler.active.moves.append(Move("watergun"))
        self.battler.active.moves.append(Move("tackle"))
        self.battler.active.moves.append(Move("calmmind"))
        self.battler.active.volatile_statuses.append("taunt")

        self.battler.lock_moves()

        self.assertFalse(self.battler.active.get_move("watergun").disabled)
        self.assertFalse(self.battler.active.get_move("tackle").disabled)
        self.assertTrue(self.battler.active.get_move("calmmind").disabled)

    def test_calmmind_gets_locked_when_user_has_assaultvest(self):
        self.battler.active.moves.append(Move("calmmind"))
        self.battler.active.item = "assaultvest"

        self.battler.lock_moves()

        self.assertTrue(self.battler.active.get_move("calmmind").disabled)

    def test_tackle_is_not_disabled_when_user_has_assaultvest(self):
        self.battler.active.moves.append(Move("tackle"))
        self.battler.active.item = "assaultvest"

        self.battler.lock_moves()

        self.assertFalse(self.battler.active.get_move("tackle").disabled)

    def test_fakeout_gets_locked_when_last_used_move_was_by_the_active_pokemon(self):
        self.battler.active.moves.append(Move("fakeout"))
        self.battler.last_used_move = LastUsedMove(
            pokemon_name="pikachu",  # the current active pokemon
            move="volttackle",
            turn=0,
        )

        self.battler.lock_moves()

        self.assertTrue(self.battler.active.get_move("fakeout").disabled)

    def test_firstimpression_is_not_disabled_when_the_last_used_move_was_a_switch(self):
        self.battler.active.moves.append(Move("firstimpression"))
        self.battler.last_used_move = LastUsedMove(
            pokemon_name="caterpie", move="switch", turn=0
        )

        self.battler.lock_moves()

        self.assertFalse(self.battler.active.get_move("firstimpression").disabled)

    def test_fakeout_is_not_disabled_when_the_last_used_move_was_a_switch(self):
        self.battler.active.moves.append(Move("fakeout"))
        self.battler.last_used_move = LastUsedMove(
            pokemon_name="caterpie", move="switch", turn=0
        )

        self.battler.lock_moves()

        self.assertFalse(self.battler.active.get_move("fakeout").disabled)

    def test_choice_item_with_previous_move_being_a_switch_returns_false(self):
        self.battler.active.item = "choicescarf"
        self.battler.last_used_move = LastUsedMove(
            pokemon_name="caterpie", move="switch", turn=0
        )
        self.battler.lock_moves()

        self.assertFalse(self.battler.active.get_move("volttackle").disabled)
        self.assertFalse(self.battler.active.get_move("thunderbolt").disabled)
        self.assertFalse(self.battler.active.get_move("agility").disabled)
        self.assertFalse(self.battler.active.get_move("doubleteam").disabled)

    def test_non_choice_item_possession_returns_false(self):
        self.battler.active.item = ""
        self.battler.last_used_move = LastUsedMove(
            pokemon_name="pikachu", move="tackle", turn=0
        )
        self.battler.lock_moves()

        self.assertFalse(self.battler.active.get_move("volttackle").disabled)
        self.assertFalse(self.battler.active.get_move("thunderbolt").disabled)
        self.assertFalse(self.battler.active.get_move("agility").disabled)
        self.assertFalse(self.battler.active.get_move("doubleteam").disabled)
