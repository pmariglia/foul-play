import unittest
import json
from collections import defaultdict

import constants
from fp.helpers import calculate_stats

from fp.battle import Battle
from fp.battle import Pokemon
from fp.battle import Move
from fp.battle import LastUsedMove
from fp.battle import DamageDealt
from fp.battle import boost_multiplier_lookup

from fp.battle_modifier import (
    request,
    fieldstart,
    fieldend,
    illusion_end,
    drag,
    switch,
    clearboost,
)
from fp.battle_modifier import terastallize
from fp.battle_modifier import activate
from fp.battle_modifier import prepare
from fp.battle_modifier import switch_or_drag
from fp.battle_modifier import clearallboost
from fp.battle_modifier import heal_or_damage
from fp.battle_modifier import swapsideconditions
from fp.battle_modifier import move
from fp.battle_modifier import cant
from fp.battle_modifier import boost
from fp.battle_modifier import setboost
from fp.battle_modifier import unboost
from fp.battle_modifier import status
from fp.battle_modifier import weather
from fp.battle_modifier import curestatus
from fp.battle_modifier import start_volatile_status
from fp.battle_modifier import end_volatile_status
from fp.battle_modifier import immune
from fp.battle_modifier import set_opponent_ability_from_ability_tag
from fp.battle_modifier import form_change
from fp.battle_modifier import zpower
from fp.battle_modifier import clearnegativeboost
from fp.battle_modifier import check_speed_ranges
from fp.battle_modifier import check_choicescarf
from fp.battle_modifier import check_heavydutyboots
from fp.battle_modifier import get_damage_dealt
from fp.battle_modifier import singleturn
from fp.battle_modifier import transform
from fp.battle_modifier import update_battle
from fp.battle_modifier import upkeep
from fp.battle_modifier import inactive


# so we can instantiate a Battle object for testing
Battle.__abstractmethods__ = set()


class TestRequestMessage(unittest.TestCase):
    def setUp(self):
        self.battle = Battle(None)
        self.battle.user.active = Pokemon("pikachu", 100)
        self.request_json = {
            "active": [
                {
                    "moves": [
                        {
                            "move": "Storm Throw",
                            "id": "stormthrow",
                            "pp": 16,
                            "maxpp": 16,
                            "target": "normal",
                            "disabled": False,
                        },
                        {
                            "move": "Ice Punch",
                            "id": "icepunch",
                            "pp": 24,
                            "maxpp": 24,
                            "target": "normal",
                            "disabled": False,
                        },
                        {
                            "move": "Bulk Up",
                            "id": "bulkup",
                            "pp": 32,
                            "maxpp": 32,
                            "target": "self",
                            "disabled": False,
                        },
                        {
                            "move": "Knock Off",
                            "id": "knockoff",
                            "pp": 32,
                            "maxpp": 32,
                            "target": "normal",
                            "disabled": False,
                        },
                    ]
                }
            ],
            "side": {
                "name": "NiceNameNerd",
                "id": "p1",
                "pokemon": [
                    {
                        "ident": "p1: Throh",
                        "details": "Throh, L83, M",
                        "condition": "335/335",
                        "active": True,
                        "stats": {
                            "atk": 214,
                            "def": 189,
                            "spa": 97,
                            "spd": 189,
                            "spe": 122,
                        },
                        "moves": ["stormthrow", "icepunch", "bulkup", "knockoff"],
                        "baseAbility": "moldbreaker",
                        "item": "leftovers",
                        "pokeball": "pokeball",
                        "ability": "moldbreaker",
                    },
                    {
                        "ident": "p1: Empoleon",
                        "details": "Empoleon, L77, F",
                        "condition": "256/256",
                        "active": False,
                        "stats": {
                            "atk": 137,
                            "def": 180,
                            "spa": 215,
                            "spd": 200,
                            "spe": 137,
                        },
                        "moves": ["icebeam", "grassknot", "scald", "flashcannon"],
                        "baseAbility": "torrent",
                        "item": "choicespecs",
                        "pokeball": "pokeball",
                        "ability": "torrent",
                    },
                    {
                        "ident": "p1: Emboar",
                        "details": "Emboar, L79, M",
                        "condition": "303/303",
                        "active": False,
                        "stats": {
                            "atk": 240,
                            "def": 148,
                            "spa": 204,
                            "spd": 148,
                            "spe": 148,
                        },
                        "moves": ["headsmash", "superpower", "flareblitz", "grassknot"],
                        "baseAbility": "reckless",
                        "item": "assaultvest",
                        "pokeball": "pokeball",
                        "ability": "reckless",
                    },
                    {
                        "ident": "p1: Zoroark",
                        "details": "Zoroark, L77, M",
                        "condition": "219/219",
                        "active": False,
                        "stats": {
                            "atk": 166,
                            "def": 137,
                            "spa": 229,
                            "spd": 137,
                            "spe": 206,
                        },
                        "moves": [
                            "sludgebomb",
                            "darkpulse",
                            "flamethrower",
                            "focusblast",
                        ],
                        "baseAbility": "illusion",
                        "item": "choicespecs",
                        "pokeball": "pokeball",
                        "ability": "illusion",
                    },
                    {
                        "ident": "p1: Reuniclus",
                        "details": "Reuniclus, L78, M",
                        "condition": "300/300",
                        "active": False,
                        "stats": {
                            "atk": 106,
                            "def": 162,
                            "spa": 240,
                            "spd": 178,
                            "spe": 92,
                        },
                        "moves": ["calmmind", "shadowball", "psyshock", "recover"],
                        "baseAbility": "magicguard",
                        "item": "lifeorb",
                        "pokeball": "pokeball",
                        "ability": "magicguard",
                    },
                    {
                        "ident": "p1: Moltres",
                        "details": "Moltres, L77",
                        "condition": "265/265",
                        "active": False,
                        "stats": {
                            "atk": 159,
                            "def": 183,
                            "spa": 237,
                            "spd": 175,
                            "spe": 183,
                        },
                        "moves": ["fireblast", "toxic", "hurricane", "roost"],
                        "baseAbility": "flamebody",
                        "item": "leftovers",
                        "pokeball": "pokeball",
                        "ability": "flamebody",
                    },
                ],
            },
            "rqid": 2,
        }

    def test_request_sets_force_switch_to_false(self):
        split_request_message = ["", "request", json.dumps(self.request_json)]
        request(self.battle, split_request_message)
        self.assertEqual(False, self.battle.force_switch)

    def test_force_switch_properly_sets_the_force_switch_flag(self):
        self.request_json.pop("active")
        self.request_json[constants.FORCE_SWITCH] = [True]
        split_request_message = ["", "request", json.dumps(self.request_json)]
        request(self.battle, split_request_message)
        self.assertEqual(True, self.battle.force_switch)

    def test_wait_properly_sets_wait_flag(self):
        self.request_json.pop("active")
        self.request_json[constants.WAIT] = [True]
        split_request_message = ["", "request", json.dumps(self.request_json)]
        request(self.battle, split_request_message)
        self.assertEqual(True, self.battle.wait)

    def test_wait_does_not_initialize_pokemon(self):
        self.request_json.pop("active")
        self.request_json[constants.WAIT] = [True]
        split_request_message = ["", "request", json.dumps(self.request_json)]
        request(self.battle, split_request_message)
        self.assertEqual(0, len(self.battle.user.reserve))


class TestSwitchOrDrag(unittest.TestCase):
    def setUp(self):
        self.battle = Battle(None)
        self.battle.user.name = "p1"
        self.battle.opponent.name = "p2"
        self.battle.user.active = Pokemon("pikachu", 100)

        self.opponent_active = Pokemon("caterpie", 100)
        self.battle.opponent.active = self.opponent_active
        self.battle.opponent.reserve = []

    def test_switch_properly_switches_zoroark_for_user_when_last_selected_move_was_zoroark(
        self,
    ):
        self.battle.request_json = {
            "active": [],
            "side": {
                "pokemon": [
                    {
                        "ident": "p1: Zoroark",
                        "details": "Zoroark, L100, M",
                        "active": True,
                    },
                    {
                        "ident": "p1: Weedle",
                        "details": "Weedle, L100, M",
                        "active": False,
                    },
                ]
            },
        }
        self.battle.reserve = [
            Pokemon("zoroark", 100),
            Pokemon("weedle", 100),
        ]
        self.battle.user.last_selected_move = LastUsedMove(
            "caterpie", "switch zoroark", 0
        )
        split_msg = ["", "switch", "p1a: Weedle", "Weedle, L100, M", "100/100"]
        switch(self.battle, split_msg)

        self.assertEqual("zoroark", self.battle.user.active.name)

    def test_being_dragged_into_zoroark_properly_sets_zoroark(self):
        self.battle.request_json = {
            "active": [],
            "side": {
                "pokemon": [
                    {
                        "ident": "p1: Zoroark",
                        "details": "Zoroark, L100, M",
                        "active": True,
                    },
                    {
                        "ident": "p1: Weedle",
                        "details": "Weedle, L100, M",
                        "active": False,
                    },
                ]
            },
        }
        self.battle.reserve = [
            Pokemon("zoroark", 100),
            Pokemon("weedle", 100),
        ]
        split_msg = ["", "drag", "p1a: Weedle", "Weedle, L100, M", "100/100"]
        drag(self.battle, split_msg)

        self.assertEqual("zoroark", self.battle.user.active.name)

    def test_being_dragged_into_not_zoroark_properly_sets_not_zoroark(self):
        self.battle.request_json = {
            "active": [],
            "side": {
                "pokemon": [
                    {
                        "ident": "p1: Zoroark",
                        "details": "Zoroark, L100, M",
                        "active": False,
                    },
                    {
                        "ident": "p1: Weedle",
                        "details": "Weedle, L100, M",
                        "active": True,
                    },
                ]
            },
        }
        self.battle.reserve = [
            Pokemon("zoroark", 100),
            Pokemon("weedle", 100),
        ]
        split_msg = ["", "drag", "p1a: Weedle", "Weedle, L100, M", "100/100"]
        drag(self.battle, split_msg)

        self.assertEqual("weedle", self.battle.user.active.name)

    def test_switch_properly_resets_types_when_pkmn_was_typechanged(self):
        self.battle.opponent.active.volatile_statuses.append(constants.TYPECHANGE)
        self.battle.opponent.active.types = ["fire"]
        active = self.battle.opponent.active
        split_msg = ["", "switch", "p2a: weedle", "Weedle, L100, M", "100/100"]
        switch_or_drag(self.battle, split_msg)

        self.assertEqual(["bug"], active.types)

    def test_increments_rest_turns_by_consequtive_sleeptalks(self):
        self.battle.generation = "gen3"
        active = self.battle.opponent.active
        active.gen_3_consecutive_sleep_talks = 1
        active.rest_turns = 1
        active.status = constants.SLEEP
        split_msg = ["", "switch", "p2a: weedle", "Weedle, L100, M", "100/100"]
        switch_or_drag(self.battle, split_msg)

        self.assertEqual(0, active.gen_3_consecutive_sleep_talks)
        self.assertEqual(2, active.rest_turns)

    def test_decrements_sleep_turns_by_consequtive_sleeptalks(self):
        self.battle.generation = "gen3"
        active = self.battle.opponent.active
        active.gen_3_consecutive_sleep_talks = 1
        active.sleep_turns = 1
        active.status = constants.SLEEP
        split_msg = ["", "switch", "p2a: weedle", "Weedle, L100, M", "100/100"]
        switch_or_drag(self.battle, split_msg)

        self.assertEqual(0, active.gen_3_consecutive_sleep_talks)
        self.assertEqual(0, active.rest_turns)

    def test_switch_properly_resets_rest_turns_to_2_in_gen5(self):
        self.battle.generation = "gen5"
        active = self.battle.opponent.active
        active.rest_turns = 1
        active.status = constants.SLEEP
        split_msg = ["", "switch", "p2a: weedle", "Weedle, L100, M", "100/100"]
        switch_or_drag(self.battle, split_msg)

        self.assertEqual(3, active.rest_turns)

    def test_switch_properly_resets_sleep_turns_to_0_in_gen5(self):
        self.battle.opponent.active.volatile_statuses.append(constants.TYPECHANGE)
        self.battle.generation = "gen5"
        active = self.battle.opponent.active
        active.sleep_turns = 1
        active.status = constants.SLEEP
        split_msg = ["", "switch", "p2a: weedle", "Weedle, L100, M", "100/100"]
        switch_or_drag(self.battle, split_msg)

        self.assertEqual(0, active.sleep_turns)

    def test_switch_does_not_reset_sleep_turns_to_0_in_gen4(self):
        self.battle.opponent.active.volatile_statuses.append(constants.TYPECHANGE)
        self.battle.generation = "gen4"
        active = self.battle.opponent.active
        active.sleep_turns = 1
        active.status = constants.SLEEP
        split_msg = ["", "switch", "p2a: weedle", "Weedle, L100, M", "100/100"]
        switch_or_drag(self.battle, split_msg)

        self.assertEqual(1, active.sleep_turns)

    def test_switch_opponents_pokemon_successfully_creates_new_pokemon_for_active(self):
        new_pkmn = Pokemon("weedle", 100)
        split_msg = ["", "switch", "p2a: weedle", "Weedle, L100, M", "100/100"]
        switch_or_drag(self.battle, split_msg)

        self.assertEqual(new_pkmn, self.battle.opponent.active)

    def test_bot_switching_properly_heals_pokemon_if_it_had_regenerator(self):
        current_active = self.battle.user.active
        self.battle.user.active.ability = "regenerator"
        self.battle.user.active.hp = 1
        self.battle.user.active.max_hp = 300
        split_msg = ["", "switch", "p1a: weedle", "Weedle, L100, M", "100/100"]
        switch_or_drag(self.battle, split_msg)

        self.assertEqual(101, current_active.hp)  # 100 hp from regenerator heal

    def test_bot_switching_with_regenerator_does_not_overheal(self):
        current_active = self.battle.user.active
        self.battle.user.active.ability = "regenerator"
        self.battle.user.active.hp = 250
        self.battle.user.active.max_hp = 300
        split_msg = ["", "switch", "p1a: weedle", "Weedle, L100, M", "100/100"]
        switch_or_drag(self.battle, split_msg)

        self.assertEqual(300, current_active.hp)  # 50 hp from regenerator heal

    def test_fainted_pokemon_switching_does_not_heal(self):
        current_active = self.battle.user.active
        self.battle.user.active.ability = "regenerator"
        self.battle.user.active.hp = 0
        self.battle.user.active.fainted = True
        self.battle.user.active.max_hp = 300
        split_msg = ["", "switch", "p1a: weedle", "Weedle, L100, M", "100/100"]
        switch_or_drag(self.battle, split_msg)

        self.assertEqual(
            0, current_active.hp
        )  # no regenerator heal when you are fainted

    def test_nickname_attribute_is_set_when_switching(self):
        # |switch|p2a: Sus|Amoonguss, F|100/100
        split_msg = ["", "switch", "p2a: Sus", "Amoonguss, F", "100/100"]
        switch_or_drag(self.battle, split_msg)

        self.assertEqual(self.battle.opponent.active.name, "amoonguss")
        self.assertEqual(self.battle.opponent.active.nickname, "Sus")

    def test_switch_resets_toxic_count_for_opponent(self):
        self.battle.opponent.side_conditions[constants.TOXIC_COUNT] = 1
        split_msg = ["", "switch", "p2a: weedle", "Weedle, L100, M", "100/100"]
        switch_or_drag(self.battle, split_msg)

        self.assertEqual(0, self.battle.opponent.side_conditions[constants.TOXIC_COUNT])

    def test_switch_resets_toxic_count_for_opponent_when_there_is_no_toxic_count(self):
        split_msg = ["", "switch", "p2a: weedle", "Weedle, L100, M", "100/100"]
        switch_or_drag(self.battle, split_msg)

        self.assertEqual(0, self.battle.opponent.side_conditions[constants.TOXIC_COUNT])

    def test_switch_resets_toxic_count_for_user(self):
        self.battle.user.side_conditions[constants.TOXIC_COUNT] = 1
        split_msg = ["", "switch", "p1a: weedle", "Weedle, L100, M", "100/100"]
        switch_or_drag(self.battle, split_msg)

        self.assertEqual(0, self.battle.user.side_conditions[constants.TOXIC_COUNT])

    def test_switch_opponents_pokemon_successfully_places_previous_active_pokemon_in_reserve(
        self,
    ):
        split_msg = ["", "switch", "p2a: weedle", "Weedle, L100, M", "100/100"]
        switch_or_drag(self.battle, split_msg)

        self.assertIn(self.opponent_active, self.battle.opponent.reserve)

    def test_switch_opponents_pokemon_creates_reserve_of_length_1_when_reserve_was_previously_empty(
        self,
    ):
        split_msg = ["", "switch", "p2a: weedle", "Weedle, L100, M", "100/100"]
        switch_or_drag(self.battle, split_msg)

        self.assertEqual(1, len(self.battle.opponent.reserve))

    def test_switch_into_already_seen_pokemon_does_not_create_a_new_pokemon(self):
        already_seen_pokemon = Pokemon("weedle", 100)
        self.battle.opponent.reserve.append(already_seen_pokemon)
        split_msg = ["", "switch", "p2a: weedle", "Weedle, L100, M", "100/100"]
        switch_or_drag(self.battle, split_msg)

        self.assertEqual(1, len(self.battle.opponent.reserve))

    def test_user_switching_causes_pokemon_to_switch(self):
        already_seen_pokemon = Pokemon("weedle", 100)
        self.battle.user.reserve.append(already_seen_pokemon)
        split_msg = ["", "switch", "p1a: weedle", "Weedle, L100, M", "100/100"]
        switch_or_drag(self.battle, split_msg)

        self.assertEqual(Pokemon("weedle", 100), self.battle.user.active)

    def test_user_switching_causes_active_pokemon_to_be_placed_in_reserve(self):
        already_seen_pokemon = Pokemon("weedle", 100)
        self.battle.user.reserve.append(already_seen_pokemon)
        split_msg = ["", "switch", "p1a: weedle", "Weedle, L100, M", "100/100"]
        switch_or_drag(self.battle, split_msg)

        self.assertEqual(Pokemon("pikachu", 100), self.battle.user.reserve[0])

    def test_user_switching_removes_volatile_statuses(self):
        user_active = self.battle.user.active
        already_seen_pokemon = Pokemon("weedle", 100)
        self.battle.user.reserve.append(already_seen_pokemon)
        user_active.volatile_statuses = ["flashfire"]
        split_msg = ["", "switch", "p1a: weedle", "Weedle, L100, M", "100/100"]
        switch_or_drag(self.battle, split_msg)

        self.assertEqual([], user_active.volatile_statuses)

    def test_already_seen_pokemon_is_the_same_object_as_the_one_in_the_reserve(self):
        already_seen_pokemon = Pokemon("weedle", 100)
        self.battle.opponent.reserve.append(already_seen_pokemon)
        split_msg = ["", "switch", "p2a: weedle", "Weedle, L100, M", "100/100"]
        switch_or_drag(self.battle, split_msg)

        self.assertIs(already_seen_pokemon, self.battle.opponent.active)

    def test_silvally_steel_replaces_silvally(self):
        already_seen_pokemon = Pokemon("silvally", 100)
        self.battle.opponent.reserve.append(already_seen_pokemon)
        split_msg = [
            "",
            "switch",
            "p2a: silvally",
            "Silvally-Steel, L100, M",
            "100/100",
        ]
        switch_or_drag(self.battle, split_msg)

        expected_pokemon = Pokemon("silvallysteel", 100)

        self.assertEqual(expected_pokemon, self.battle.opponent.active)

    def test_silvally_steel_with_nickname_replaces_silvally(self):
        already_seen_pokemon = Pokemon("silvally", 100)
        self.battle.opponent.reserve.append(already_seen_pokemon)
        split_msg = [
            "",
            "switch",
            "p2a: notsilvally",
            "Silvally-Steel, L100, M",
            "100/100",
        ]
        switch_or_drag(self.battle, split_msg)

        expected_pokemon = Pokemon("silvallysteel", 100)

        self.assertEqual(expected_pokemon, self.battle.opponent.active)

    def test_silvally_replaces_reserve_silvally_with_different_name(self):
        already_seen_pokemon = Pokemon("silvally", 100)
        already_seen_pokemon.unknown_forme = True
        self.battle.opponent.reserve.append(already_seen_pokemon)
        split_msg = [
            "",
            "switch",
            "p2a: notsilvally",
            "Silvally-Steel, L100, M",
            "100/100",
        ]
        switch_or_drag(self.battle, split_msg)

        expected_pokemon = Pokemon("silvallysteel", 100)

        self.assertEqual(expected_pokemon, self.battle.opponent.active)
        self.assertNotIn(already_seen_pokemon, self.battle.opponent.reserve)

    def test_silvally_switching_in_preserves_previous_hp(self):
        already_seen_pokemon = Pokemon("silvallysteel", 100)
        already_seen_pokemon.hp = already_seen_pokemon.max_hp / 2
        self.battle.opponent.reserve.append(already_seen_pokemon)
        split_msg = [
            "",
            "switch",
            "p2a: notsilvally",
            "Silvally-Steel, L100, M",
            "50/100",
        ]
        switch_or_drag(self.battle, split_msg)

        self.assertEqual(
            self.battle.opponent.active.max_hp / 2, self.battle.opponent.active.hp
        )

    def test_arceus_ghost_switching_in(self):
        already_seen_pokemon = Pokemon("arceus", 100)
        self.battle.opponent.reserve.append(already_seen_pokemon)
        split_msg = ["", "switch", "p2a: Arceus", "Arceus-Ghost", "100/100"]
        switch_or_drag(self.battle, split_msg)

        expected_pokemon = Pokemon("arceus-ghost", 100)

        self.assertEqual(expected_pokemon, self.battle.opponent.active)

    def test_existing_boosts_on_opponents_active_pokemon_are_cleared_when_switching(
        self,
    ):
        self.opponent_active.boosts[constants.ATTACK] = 1
        self.opponent_active.boosts[constants.SPEED] = 1
        split_msg = ["", "switch", "p2a: weedle", "Weedle, L100, M", "100/100"]
        switch_or_drag(self.battle, split_msg)

        self.assertEqual({}, self.opponent_active.boosts)

    def test_existing_boosts_on_bots_active_pokemon_are_cleared_when_switching(self):
        pkmn = self.battle.user.active
        pkmn.boosts[constants.ATTACK] = 1
        pkmn.boosts[constants.SPEED] = 1
        split_msg = ["", "switch", "p1a: pidgey", "Pidgey, L100, M", "100/100"]
        switch_or_drag(self.battle, split_msg)

        self.assertEqual({}, pkmn.boosts)

    def test_switching_into_the_same_pokemon_does_not_put_that_pokemon_in_the_reserves(
        self,
    ):
        # this is specifically for Zororak
        split_msg = ["", "switch", "p2a: caterpie", "Caterpie, L100, M", "100/100"]
        switch_or_drag(self.battle, split_msg)

        self.assertFalse(self.battle.opponent.reserve)

    def test_switching_sets_last_move_to_none(self):
        split_msg = ["", "switch", "p2a: weedle", "Weedle, L100, M", "100/100"]
        switch_or_drag(self.battle, split_msg)

        expected_last_move = LastUsedMove(None, "switch weedle", 0)

        self.assertEqual(expected_last_move, self.battle.opponent.last_used_move)

    def test_ditto_switching_sets_ability_to_none(self):
        ditto = Pokemon("ditto", 100)
        ditto.ability = "some_ability"
        ditto.volatile_statuses.append(constants.TRANSFORM)
        self.battle.opponent.active = ditto
        split_msg = ["", "switch", "p2a: weedle", "Weedle, L100, M", "100/100"]
        switch_or_drag(self.battle, split_msg)

        if self.battle.opponent.reserve[0] != ditto:
            self.fail("Ditto was not moved to reserves")

        self.assertIsNone(ditto.ability)

    def test_ditto_switching_sets_moves_to_empty_list(self):
        ditto = Pokemon("ditto", 100)
        ditto.moves = [Move("tackle"), Move("stringshot")]
        ditto.volatile_statuses.append(constants.TRANSFORM)
        self.battle.opponent.active = ditto

        split_msg = ["", "switch", "p2a: weedle", "Weedle, L100, M", "100/100"]
        switch_or_drag(self.battle, split_msg)

        if self.battle.opponent.reserve[0] != ditto:
            self.fail("Ditto was not moved to reserves")

        self.assertEqual([], ditto.moves)

    def test_ditto_switching_resets_stats(self):
        ditto = Pokemon("ditto", 100)
        ditto.stats = {
            constants.ATTACK: 1,
            constants.DEFENSE: 2,
            constants.SPECIAL_ATTACK: 3,
            constants.SPECIAL_DEFENSE: 4,
            constants.SPEED: 5,
        }
        ditto.volatile_statuses.append(constants.TRANSFORM)
        self.battle.opponent.active = ditto

        split_msg = ["", "switch", "p2a: weedle", "Weedle, L100, M", "100/100"]
        switch_or_drag(self.battle, split_msg)

        if self.battle.opponent.reserve[0] != ditto:
            self.fail("Ditto was not moved to reserves")

        expected_stats = calculate_stats(ditto.base_stats, ditto.level)

        self.assertEqual(expected_stats, ditto.stats)

    def test_ditto_switching_resets_boosts(self):
        ditto = Pokemon("ditto", 100)
        ditto.boosts = {
            constants.ATTACK: 1,
            constants.DEFENSE: 2,
            constants.SPECIAL_ATTACK: 3,
            constants.SPECIAL_DEFENSE: 4,
            constants.SPEED: 5,
        }
        ditto.volatile_statuses.append(constants.TRANSFORM)
        self.battle.opponent.active = ditto

        split_msg = ["", "switch", "p2a: weedle", "Weedle, L100, M", "100/100"]
        switch_or_drag(self.battle, split_msg)

        if self.battle.opponent.reserve[0] != ditto:
            self.fail("Ditto was not moved to reserves")

        self.assertEqual({}, ditto.boosts)

    def test_ditto_switching_resets_types(self):
        ditto = Pokemon("ditto", 100)
        ditto.types = ["fairy", "flying"]
        ditto.volatile_statuses.append(constants.TRANSFORM)
        self.battle.opponent.active = ditto

        split_msg = ["", "switch", "p2a: weedle", "Weedle, L100, M", "100/100"]
        switch_or_drag(self.battle, split_msg)

        if self.battle.opponent.reserve[0] != ditto:
            self.fail("Ditto was not moved to reserves")

        self.assertEqual(["normal"], ditto.types)


class TestHealOrDamage(unittest.TestCase):
    def setUp(self):
        self.battle = Battle(None)
        self.battle.user.name = "p1"
        self.battle.opponent.name = "p2"

        self.user_active = Pokemon("caterpie", 100)
        self.opponent_active = Pokemon("caterpie", 100)

        # manually set hp to 200 for testing purposes
        self.opponent_active.max_hp = 200
        self.opponent_active.hp = 200

        self.battle.opponent.active = self.opponent_active
        self.battle.user.active = self.user_active

    def test_sets_ability_when_the_information_is_present(self):
        split_msg = [
            "",
            "-heal",
            "p2a: Quagsire",
            "68/100",
            "[from] ability: Water Absorb",
            "[of] p1a: Genesect",
        ]
        heal_or_damage(self.battle, split_msg)
        self.assertEqual("waterabsorb", self.battle.opponent.active.ability)

    def test_sets_ability_when_the_bot_is_damaged_from_opponents_ability(self):
        split_msg = [
            "",
            "-damage",
            "p1a: Lamdorus",
            "167/319",
            "[from] ability: Iron Barbs",
            "[of] p2a: Ferrothorn",
        ]
        heal_or_damage(self.battle, split_msg)
        self.assertEqual("ironbarbs", self.battle.opponent.active.ability)

    def test_sets_ability_when_the_opponent_is_damaged_from_bots_ability(self):
        split_msg = [
            "",
            "-damage",
            "p2a: Lamdorus",
            "167/319",
            "[from] ability: Iron Barbs",
            "[of] p1a: Ferrothorn",
        ]
        heal_or_damage(self.battle, split_msg)
        self.assertEqual("ironbarbs", self.battle.user.active.ability)

    def test_sets_item_when_it_causes_the_bot_damage(self):
        split_msg = [
            "",
            "-damage",
            "p1a: Kartana",
            "167/319",
            "[from] item: Rocky Helmet",
            "[of] p2a: Ferrothorn",
        ]
        heal_or_damage(self.battle, split_msg)
        self.assertEqual("rockyhelmet", self.battle.opponent.active.item)

    def test_sets_item_when_it_causes_the_opponent_damage(self):
        split_msg = [
            "",
            "-damage",
            "p2a: Kartana",
            "167/319",
            "[from] item: Rocky Helmet",
            "[of] p1a: Ferrothorn",
        ]
        heal_or_damage(self.battle, split_msg)
        self.assertEqual("rockyhelmet", self.battle.user.active.item)

    def test_does_not_set_item_when_item_is_none(self):
        # |-heal|p2a: Drifblim|37/100|[from] item: Sitrus Berry
        split_msg = [
            "",
            "-heal",
            "p2a: Drifblim",
            "37/100",
            "[from] item: Sitrus Berry",
        ]
        self.battle.opponent.active.item = None
        heal_or_damage(self.battle, split_msg)
        self.assertEqual(None, self.battle.opponent.active.item)

    def test_damage_sets_opponents_active_pokemon_to_correct_hp(self):
        split_msg = ["", "-damage", "p2a: Caterpie", "80/100"]
        heal_or_damage(self.battle, split_msg)
        self.assertEqual(160, self.battle.opponent.active.hp)

    def test_damage_sets_bots_active_pokemon_to_correct_hp(self):
        split_msg = ["", "-damage", "p1a: Caterpie", "150/250"]
        heal_or_damage(self.battle, split_msg)
        self.assertEqual(150, self.battle.user.active.hp)

    def test_damage_sets_bots_active_pokemon_to_correct_maxhp(self):
        split_msg = ["", "-damage", "p1a: Caterpie", "150/250"]
        heal_or_damage(self.battle, split_msg)
        self.assertEqual(250, self.battle.user.active.max_hp)

    def test_damage_sets_bots_active_pokemon_to_zero_hp(self):
        split_msg = ["", "-damage", "p1a: Caterpie", "0 fnt"]
        heal_or_damage(self.battle, split_msg)
        self.assertEqual(0, self.battle.user.active.hp)

    def test_fainted_message_properly_faints_opponents_pokemon(self):
        split_msg = ["", "-damage", "p2a: Caterpie", "0 fnt"]
        heal_or_damage(self.battle, split_msg)
        self.assertEqual(0, self.battle.opponent.active.hp)

    def test_damage_caused_by_an_item_properly_sets_opponents_item(self):
        split_msg = ["", "-damage", "p2a: Caterpie", "100/100", "[from] item: Life Orb"]
        heal_or_damage(self.battle, split_msg)
        self.assertEqual("lifeorb", self.battle.opponent.active.item)

    def test_damage_caused_by_toxic_increases_side_condition_toxic_counter_for_opponent(
        self,
    ):
        split_msg = ["", "-damage", "p2a: Caterpie", "94/100 tox", "[from] psn"]
        heal_or_damage(self.battle, split_msg)
        self.assertEqual(1, self.battle.opponent.side_conditions[constants.TOXIC_COUNT])

    def test_damage_caused_by_toxic_increases_side_condition_toxic_counter_for_user(
        self,
    ):
        split_msg = ["", "-damage", "p1a: Caterpie", "94/100 tox", "[from] psn"]
        heal_or_damage(self.battle, split_msg)
        self.assertEqual(1, self.battle.user.side_conditions[constants.TOXIC_COUNT])

    def test_toxic_count_increases_to_2(self):
        self.battle.opponent.side_conditions[constants.TOXIC_COUNT] = 1
        split_msg = ["", "-damage", "p2a: Caterpie", "94/100 tox", "[from] psn"]
        heal_or_damage(self.battle, split_msg)
        self.assertEqual(2, self.battle.opponent.side_conditions[constants.TOXIC_COUNT])

    def test_damage_caused_by_non_toxic_damage_does_not_increase_toxic_count(self):
        split_msg = [
            "",
            "-damage",
            "p2a: Caterpie",
            "50/100 tox",
            "[from] item: Life Orb",
        ]
        heal_or_damage(self.battle, split_msg)
        self.assertEqual(0, self.battle.opponent.side_conditions[constants.TOXIC_COUNT])

    def test_healing_from_ability_sets_ability_to_opponent(self):
        split_msg = [
            "",
            "-heal",
            "p2a: Caterpie",
            "50/100",
            "[from] ability: Volt Absorb",
            "[of] p1a: Caterpie",
        ]
        heal_or_damage(self.battle, split_msg)
        self.assertEqual("voltabsorb", self.battle.opponent.active.ability)

    def test_healing_from_ability_does_not_set_bots_ability(self):
        self.battle.user.active.ability = None
        split_msg = [
            "",
            "-heal",
            "p2a: Caterpie",
            "50/100",
            "[from] ability: Volt Absorb",
            "[of] p1a: Caterpie",
        ]
        heal_or_damage(self.battle, split_msg)
        self.assertIsNone(self.battle.user.active.ability)

    def test_healing_from_revivalblessing_for_opponent_pkmn(self):
        amoongus_reserve = Pokemon("amoonguss", 100)
        amoongus_reserve.nickname = "Sus"
        amoongus_reserve.hp = 0
        amoongus_reserve.fainted = True
        self.battle.opponent.reserve = [amoongus_reserve]

        # |-heal|p1: Amoonguss|50/100|[from] move: Revival Blessing
        split_msg = ["", "-heal", "p2a: Sus", "50/100", "[from] move: Revival Blessing"]
        heal_or_damage(self.battle, split_msg)
        self.assertEqual(amoongus_reserve.hp, int(amoongus_reserve.max_hp / 2))

    def test_healing_from_revivalblessing_for_bot_pkmn(self):
        amoongus_reserve = Pokemon("amoonguss", 100)
        amoongus_reserve.nickname = "Sus"
        amoongus_reserve.hp = 0
        amoongus_reserve.fainted = True
        self.battle.user.reserve = [amoongus_reserve]

        split_msg = [
            "",
            "-heal",
            "p1a: Sus",
            "150/301",
            "[from] move: Revival Blessing",
        ]
        heal_or_damage(self.battle, split_msg)
        self.assertEqual(amoongus_reserve.hp, int(amoongus_reserve.max_hp / 2))


class TestActivate(unittest.TestCase):
    def setUp(self):
        self.battle = Battle(None)
        self.battle.user.name = "p1"
        self.battle.opponent.name = "p2"

        self.user_active = Pokemon("caterpie", 100)
        self.opponent_active = Pokemon("caterpie", 100)

        # manually set hp to 200 for testing purposes
        self.opponent_active.max_hp = 200
        self.opponent_active.hp = 200

        self.battle.opponent.active = self.opponent_active
        self.battle.user.active = self.user_active

    def test_sets_item_when_poltergeist_activates(self):
        split_msg = [
            "",
            "-activate",
            "p2a: Mandibuzz",
            "Move: Poltergeist",
            "Leftovers",
        ]
        activate(self.battle, split_msg)
        self.assertEqual("leftovers", self.battle.opponent.active.item)

    def test_sets_item_when_poltergeist_activates_and_move_is_lowercase(self):
        split_msg = [
            "",
            "-activate",
            "p2a: Mandibuzz",
            "move: Poltergeist",
            "Leftovers",
        ]
        activate(self.battle, split_msg)
        self.assertEqual("leftovers", self.battle.opponent.active.item)

    def test_sets_item_from_activate(self):
        split_msg = [
            "",
            "-activate",
            "p2a: Mandibuzz",
            "item: Safety Goggles",
            "Stun Spore",
        ]
        activate(self.battle, split_msg)
        self.assertEqual("safetygoggles", self.battle.opponent.active.item)

    def test_sets_ability_from_activate(self):
        split_msg = ["", "-activate", "p2a: Ferrothorn", "ability: Iron Barbs"]
        activate(self.battle, split_msg)
        self.assertEqual("ironbarbs", self.battle.opponent.active.ability)

    def test_sets_substitute_hit_from_activate(self):
        split_msg = ["", "-activate", "p2a: Heatran", "Substitute", "[damage]"]
        activate(self.battle, split_msg)
        self.assertTrue(self.battle.opponent.active.substitute_hit)


class TestPrepare(unittest.TestCase):
    def setUp(self):
        self.battle = Battle(None)
        self.battle.user.name = "p1"
        self.battle.opponent.name = "p2"

        self.user_active = Pokemon("caterpie", 100)
        self.opponent_active = Pokemon("caterpie", 100)

        # manually set hp to 200 for testing purposes
        self.opponent_active.max_hp = 200
        self.opponent_active.hp = 200

        self.battle.opponent.active = self.opponent_active
        self.battle.user.active = self.user_active

    def test_prepare_sets_volatile_status_on_pokemon(self):
        # |-prepare|p1a: Dragapult|Phantom Force
        split_msg = ["", "-prepare", "p2a: Caterpie", "Phantom Force"]
        prepare(self.battle, split_msg)
        self.assertIn("phantomforce", self.battle.opponent.active.volatile_statuses)


class TestClearAllBoosts(unittest.TestCase):
    def setUp(self):
        self.battle = Battle(None)
        self.battle.user.name = "p1"
        self.battle.opponent.name = "p2"

        self.user_active = Pokemon("caterpie", 100)
        self.opponent_active = Pokemon("caterpie", 100)

        # manually set hp to 200 for testing purposes
        self.opponent_active.max_hp = 200
        self.opponent_active.hp = 200

        self.battle.opponent.active = self.opponent_active
        self.battle.user.active = self.user_active

    def test_clears_bots_boosts(self):
        split_msg = ["", "-clearallboost"]
        self.battle.user.active.boosts = {constants.ATTACK: 1, constants.DEFENSE: 1}
        clearallboost(self.battle, split_msg)
        self.assertEqual(0, self.battle.user.active.boosts[constants.ATTACK])
        self.assertEqual(0, self.battle.user.active.boosts[constants.DEFENSE])

    def test_clears_opponents_boosts(self):
        split_msg = ["", "-clearallboost"]
        self.battle.opponent.active.boosts = {constants.ATTACK: 1, constants.DEFENSE: 1}
        clearallboost(self.battle, split_msg)
        self.assertEqual(0, self.battle.opponent.active.boosts[constants.ATTACK])
        self.assertEqual(0, self.battle.opponent.active.boosts[constants.DEFENSE])

    def test_clears_opponents_and_botsboosts(self):
        split_msg = ["", "-clearallboost"]
        self.battle.user.active.boosts = {constants.ATTACK: 1, constants.DEFENSE: 1}
        self.battle.opponent.active.boosts = {constants.ATTACK: 1, constants.DEFENSE: 1}
        clearallboost(self.battle, split_msg)
        self.assertEqual(0, self.battle.user.active.boosts[constants.ATTACK])
        self.assertEqual(0, self.battle.user.active.boosts[constants.DEFENSE])
        self.assertEqual(0, self.battle.opponent.active.boosts[constants.ATTACK])
        self.assertEqual(0, self.battle.opponent.active.boosts[constants.DEFENSE])


class TestMove(unittest.TestCase):
    def setUp(self):
        self.battle = Battle(None)
        self.battle.user.name = "p1"
        self.battle.opponent.name = "p2"

        self.opponent_active = Pokemon("caterpie", 100)
        self.battle.opponent.active = self.opponent_active

        self.battle.user.active = Pokemon("clefable", 100)

    def test_adds_move_to_opponent(self):
        split_msg = ["", "move", "p2a: Caterpie", "String Shot"]

        move(self.battle, split_msg)
        m = Move("String Shot")

        self.assertIn(m, self.battle.opponent.active.moves)

    def test_adds_truant_when_truant_pkmn(self):
        self.battle.opponent.active.ability = "truant"
        split_msg = ["", "move", "p2a: Slaking", "Earthquake"]
        move(self.battle, split_msg)
        self.assertIn("truant", self.battle.opponent.active.volatile_statuses)

    def test_adds_truant_when_slaking_pkmn(self):
        self.battle.opponent.active.name = "slaking"
        split_msg = ["", "move", "p2a: Slaking", "Earthquake"]
        move(self.battle, split_msg)
        self.assertIn("truant", self.battle.opponent.active.volatile_statuses)

    def test_does_not_set_move_for_magicbounch(self):
        split_msg = ["", "move", "p2a: Caterpie", "String Shot", "[from]Magic Bounce"]

        move(self.battle, split_msg)
        m = Move("String Shot")

        self.assertNotIn(m, self.battle.opponent.active.moves)

    def test_new_move_has_one_pp_less_than_max(self):
        split_msg = ["", "move", "p2a: Caterpie", "String Shot"]

        move(self.battle, split_msg)
        m = self.battle.opponent.active.get_move("String Shot")
        expected_pp = m.max_pp - 1

        self.assertEqual(expected_pp, m.current_pp)

    def test_new_move_has_two_pp_less_than_max_if_against_pressure(self):
        split_msg = ["", "move", "p2a: Caterpie", "String Shot"]
        self.battle.user.active.ability = "pressure"

        move(self.battle, split_msg)
        m = self.battle.opponent.active.get_move("String Shot")
        expected_pp = m.max_pp - 2

        self.assertEqual(expected_pp, m.current_pp)

    def test_unknown_move_does_not_try_to_decrement(self):
        split_msg = ["", "move", "p2a: Caterpie", "some-random-unknown-move"]

        move(self.battle, split_msg)

    def test_add_revealed_move_does_not_add_move_twice(self):
        split_msg = ["", "move", "p2a: Caterpie", "String Shot"]

        self.battle.opponent.active.moves.append(Move("String Shot"))
        move(self.battle, split_msg)

        self.assertEqual(1, len(self.battle.opponent.active.moves))

    def test_increments_gen3_consecutive_sleeptalk_turns_when_using_sleeptalk(self):
        split_msg = ["", "move", "p2a: Caterpie", "Earthquake", "[from]Sleep Talk"]
        self.battle.opponent.active.status = constants.SLEEP
        self.battle.generation = "gen3"

        move(self.battle, split_msg)

        self.assertEqual(1, self.battle.opponent.active.gen_3_consecutive_sleep_talks)

    def test_does_not_reset_consecutive_sleeptalk_turns_in_gen3_when_move_is_sleeptalk(
        self,
    ):
        split_msg = ["", "move", "p2a: Caterpie", "Sleep Talk"]
        self.battle.opponent.active.status = constants.SLEEP
        self.battle.opponent.active.gen_3_consecutive_sleep_talks = 1
        self.battle.generation = "gen3"

        move(self.battle, split_msg)

        self.assertEqual(1, self.battle.opponent.active.gen_3_consecutive_sleep_talks)

    def test_resets_consecutive_sleeptalk_turns_in_gen3_when_move_is_non_sleeptalk(
        self,
    ):
        split_msg = ["", "move", "p2a: Caterpie", "Earthquake"]
        self.battle.opponent.active.status = constants.SLEEP
        self.battle.opponent.active.gen_3_consecutive_sleep_talks = 1
        self.battle.generation = "gen3"

        move(self.battle, split_msg)

        self.assertEqual(0, self.battle.opponent.active.gen_3_consecutive_sleep_talks)

    def test_does_not_decrement_pp_if_move_is_called_by_sleeptalk(self):
        split_msg = ["", "move", "p2a: Caterpie", "String Shot", "[from]Sleep Talk"]
        m = Move("String Shot")
        m.current_pp = 5
        self.battle.opponent.active.moves.append(m)
        move(self.battle, split_msg)

        self.assertEqual(5, m.current_pp)

    def test_sets_move_if_doesnt_exist_from_sleeptalk(self):
        split_msg = ["", "move", "p2a: Caterpie", "String Shot", "[from]Sleep Talk"]
        move(self.battle, split_msg)

        self.assertIn(Move("stringshot"), self.battle.opponent.active.moves)
        self.assertEqual(
            self.battle.opponent.active.moves[0].current_pp,
            self.battle.opponent.active.moves[0].max_pp,
        )

    def test_sets_move_if_doesnt_exist_from_move_sleeptalk(self):
        split_msg = [
            "",
            "move",
            "p2a: Caterpie",
            "String Shot",
            "[from]move: Sleep Talk",
        ]
        move(self.battle, split_msg)

        self.assertIn(Move("stringshot"), self.battle.opponent.active.moves)
        self.assertEqual(
            self.battle.opponent.active.moves[0].current_pp,
            self.battle.opponent.active.moves[0].max_pp,
        )

    def test_does_not_decrement_pp_if_move_is_called_by_move_sleeptalk(self):
        split_msg = [
            "",
            "move",
            "p2a: Caterpie",
            "String Shot",
            "[from]move: Sleep Talk",
        ]
        m = Move("String Shot")
        m.current_pp = 5
        self.battle.opponent.active.moves.append(m)
        move(self.battle, split_msg)

        self.assertEqual(5, m.current_pp)

    def test_decrements_seen_move_pp_if_seen_again(self):
        split_msg = ["", "move", "p2a: Caterpie", "String Shot"]
        m = Move("String Shot")
        m.current_pp = 5
        self.battle.opponent.active.moves.append(m)
        move(self.battle, split_msg)

        self.assertEqual(4, m.current_pp)

    def test_decrements_seen_move_pp_by_two_if_opponent_has_pressure(self):
        split_msg = ["", "move", "p2a: Caterpie", "String Shot"]
        m = Move("String Shot")
        m.current_pp = 5
        self.battle.user.active.ability = "pressure"
        self.battle.opponent.active.moves.append(m)
        move(self.battle, split_msg)

        self.assertEqual(3, m.current_pp)

    def test_properly_sets_last_used_move(self):
        split_msg = ["", "move", "p2a: Caterpie", "String Shot"]

        move(self.battle, split_msg)

        expected_last_used_move = LastUsedMove(
            pokemon_name="caterpie", move="stringshot", turn=0
        )

        self.assertEqual(expected_last_used_move, self.battle.opponent.last_used_move)

    def test_using_status_move_makes_assaultvest_impossible(self):
        split_msg = ["", "move", "p2a: Caterpie", "String Shot"]
        self.battle.opponent.last_used_move = LastUsedMove("caterpie", "tackle", 0)

        move(self.battle, split_msg)

        self.assertIn(
            constants.ASSAULT_VEST, self.battle.opponent.active.impossible_items
        )

    def test_using_nonstatus_move_does_not_make_assultvest_impossible(self):
        split_msg = ["", "move", "p2a: Caterpie", "Tackle"]
        self.battle.opponent.last_used_move = LastUsedMove("caterpie", "tackle", 0)

        move(self.battle, split_msg)

        self.assertNotIn(
            constants.ASSAULT_VEST, self.battle.opponent.active.impossible_items
        )

    def test_removes_volatilestatus_if_pkmn_has_it_when_using_move(self):
        self.battle.opponent.active.volatile_statuses = ["phantomforce"]
        split_msg = ["", "move", "p2a: Caterpie", "Phantom Force", "[from]lockedmove"]

        move(self.battle, split_msg)

        self.assertEqual([], self.battle.opponent.active.volatile_statuses)

    def test_sets_can_have_choice_item_to_false_if_two_different_moves_are_used_when_the_pkmn_has_an_unknown_item(
        self,
    ):
        self.battle.opponent.active.can_have_choice_item = True
        split_msg = ["", "move", "p2a: Caterpie", "String Shot"]
        self.battle.opponent.last_used_move = LastUsedMove("caterpie", "tackle", 0)

        move(self.battle, split_msg)

        self.assertFalse(self.battle.opponent.active.can_have_choice_item)

    def test_using_a_boosting_status_move_sets_can_have_choice_item_to_false(self):
        self.battle.opponent.active.can_have_choice_item = True
        split_msg = ["", "move", "p2a: Caterpie", "Dragon Dance"]

        move(self.battle, split_msg)

        self.assertFalse(self.battle.opponent.active.can_have_choice_item)

    def test_using_a_boosting_physical_move_does_not_set_can_have_choice_item_to_false(
        self,
    ):
        self.battle.opponent.active.can_have_choice_item = True
        split_msg = ["", "move", "p2a: Caterpie", "Scale Shot"]

        move(self.battle, split_msg)

        self.assertTrue(self.battle.opponent.active.can_have_choice_item)

    def test_using_a_boosting_special_move_does_not_set_can_have_choice_item_to_false(
        self,
    ):
        self.battle.opponent.active.can_have_choice_item = True
        split_msg = ["", "move", "p2a: Caterpie", "Scale Shot"]

        move(self.battle, split_msg)

        self.assertTrue(self.battle.opponent.active.can_have_choice_item)

    def test_sets_item_to_unknown_if_the_pokemon_choice_item_was_inferred_but_two_different_moves_are_used(
        self,
    ):
        self.battle.opponent.active.can_have_choice_item = True
        self.battle.opponent.active.item = "choiceband"
        self.battle.opponent.active.item_inferred = True
        split_msg = ["", "move", "p2a: Caterpie", "String Shot"]
        self.battle.opponent.last_used_move = LastUsedMove("caterpie", "tackle", 0)

        move(self.battle, split_msg)

        self.assertEqual(constants.UNKNOWN_ITEM, self.battle.opponent.active.item)

    def test_does_not_set_item_to_unknow_if_choice_item_was_not_inferred_and_two_different_moves_were_used(
        self,
    ):
        self.battle.opponent.active.can_have_choice_item = True
        self.battle.opponent.active.item = "choiceband"
        self.battle.opponent.active.item_inferred = False
        split_msg = ["", "move", "p2a: Caterpie", "String Shot"]
        self.battle.opponent.last_used_move = LastUsedMove("caterpie", "tackle", 0)

        move(self.battle, split_msg)

        self.assertEqual(constants.CHOICE_BAND, self.battle.opponent.active.item)

    def test_does_not_set_item_to_unknown_if_the_known_item_is_not_a_choice_item_and_two_different_moves_are_used(
        self,
    ):
        self.battle.opponent.active.can_have_choice_item = True
        self.battle.opponent.active.item = "leftovers"
        split_msg = ["", "move", "p2a: Caterpie", "String Shot"]
        self.battle.opponent.last_used_move = LastUsedMove("caterpie", "tackle", 0)

        move(self.battle, split_msg)

        self.assertEqual("leftovers", self.battle.opponent.active.item)

    def test_does_not_set_can_have_choice_item_to_false_if_the_same_move_is_used_when_the_pkmn_has_an_unknown_item(
        self,
    ):
        self.battle.opponent.active.can_have_choice_item = True
        split_msg = ["", "move", "p2a: Caterpie", "Tackle"]
        self.battle.opponent.last_used_move = LastUsedMove("caterpie", "tackle", 0)

        move(self.battle, split_msg)

        self.assertTrue(self.battle.opponent.active.can_have_choice_item)

    def test_sets_can_have_choice_item_to_false_even_if_item_is_known(self):
        # if the item is known - this flag doesn't matter anyways
        self.battle.opponent.active.can_have_choice_item = True
        self.battle.opponent.active.item = "leftovers"
        split_msg = ["", "move", "p2a: Caterpie", "String Shot"]
        self.battle.opponent.last_used_move = LastUsedMove("caterpie", "tackle", 0)

        move(self.battle, split_msg)

        self.assertFalse(self.battle.opponent.active.can_have_choice_item)

    def test_sets_life_orb_as_impossible_if_damaging_move_is_used(self):
        # if a damaging move is used, we no longer want to guess lifeorb as an item
        split_msg = ["", "move", "p2a: Caterpie", "Tackle"]

        move(self.battle, split_msg)

        self.assertIn(constants.LIFE_ORB, self.battle.opponent.active.impossible_items)

    def test_does_not_set_can_life_orb_to_impossible_if_pokemon_could_have_sheerforce(
        self,
    ):
        # mawile could have sheerforce
        # we shouldn't set the lifeorb flag to False because sheerforce doesn't reveal lifeorb when a damaging move is used
        self.battle.opponent.active.name = "mawile"
        split_msg = ["", "move", "p2a: Mawile", "Tackle"]

        move(self.battle, split_msg)

        self.assertNotIn(
            constants.LIFE_ORB, self.battle.opponent.active.impossible_items
        )

    def test_does_not_set_life_orb_to_impossible_if_pokemon_could_have_magic_guard(
        self,
    ):
        # clefable could have magic guard
        # we shouldn't set the lifeorb flag to False because magic guard doesn't reveal lifeorb when a damaging move is used
        self.battle.opponent.active.name = "clefable"
        split_msg = ["", "move", "p2a: Clefable", "Tackle"]

        move(self.battle, split_msg)

        self.assertNotIn(
            constants.LIFE_ORB, self.battle.opponent.active.impossible_items
        )

    def test_adds_normal_gem_to_impossible_items(self):
        split_msg = ["", "move", "p2a: Clefable", "Tackle"]

        move(self.battle, split_msg)
        self.assertIn("normalgem", self.battle.opponent.active.impossible_items)

    def test_adds_flying_gem_to_impossible_items(self):
        split_msg = ["", "move", "p2a: Clefable", "Acrobatics"]

        move(self.battle, split_msg)
        self.assertIn("flyinggem", self.battle.opponent.active.impossible_items)

    def test_does_not_add_gem_if_non_damaging_move(self):
        split_msg = ["", "move", "p2a: Clefable", "Protect"]

        move(self.battle, split_msg)
        self.assertNotIn("normalgem", self.battle.opponent.active.impossible_items)

    def test_wish_sets_battler_wish(self):
        split_msg = ["", "move", "p1a: Clefable", "Wish", "p1a: Clefable"]

        move(self.battle, split_msg)

        expected_wish = (2, self.battle.user.active.max_hp / 2)

        self.assertEqual(expected_wish, self.battle.user.wish)

    def test_failed_wish_does_not_set_wish(self):
        self.battle.user.wish = (1, 100)
        split_msg = ["", "move", "p1a: Clefable", "Wish", "[still]"]

        move(self.battle, split_msg)

        expected_wish = (1, 100)

        self.assertEqual(expected_wish, self.battle.user.wish)


class TestTrickRoom(unittest.TestCase):
    def setUp(self):
        self.battle = Battle(None)
        self.battle.user.name = "p1"
        self.battle.opponent.name = "p2"

        self.opponent_active = Pokemon("caterpie", 100)
        self.battle.opponent.active = self.opponent_active

    def test_starts_trickroom_properly(self):
        split_msg = [
            "",
            "-fieldstart",
            "move: Trick Room",
            "p1a: Bronzong",
        ]

        fieldstart(self.battle, split_msg)

        self.assertEqual(True, self.battle.trick_room)
        self.assertEqual(5, self.battle.trick_room_turns_remaining)

    def test_removes_trickroom_properly(self):
        split_msg = [
            "",
            "-fieldend",
            "move: Trick Room",
        ]

        fieldend(self.battle, split_msg)

        self.assertEqual(False, self.battle.trick_room)
        self.assertEqual(0, self.battle.trick_room_turns_remaining)


class TestWeather(unittest.TestCase):
    def setUp(self):
        self.battle = Battle(None)
        self.battle.user.name = "p1"
        self.battle.opponent.name = "p2"

        self.opponent_active = Pokemon("caterpie", 100)
        self.battle.opponent.active = self.opponent_active
        self.user_active = Pokemon("caterpie", 100)
        self.battle.user.active = self.user_active

    def test_starts_weather_properly(self):
        split_msg = [
            "",
            "-weather",
            "RainDance",
            "[from] ability: Drizzle",
            "[of] p2a: Pelipper",
        ]

        weather(self.battle, split_msg)

        self.assertEqual("raindance", self.battle.weather)

    def test_sets_weather_turns_remaining_from_ability_gen4(self):
        self.battle.generation = "gen4"
        split_msg = [
            "",
            "-weather",
            "RainDance",
            "[from] ability: Drizzle",
            "[of] p2a: Pelipper",
        ]

        weather(self.battle, split_msg)

        self.assertEqual("raindance", self.battle.weather)
        self.assertEqual(-1, self.battle.weather_turns_remaining)

    def test_sets_weather_turns_remaining_from_ability_gen6(self):
        self.battle.generation = "gen6"
        split_msg = [
            "",
            "-weather",
            "RainDance",
            "[from] ability: Drizzle",
            "[of] p2a: Pelipper",
        ]

        weather(self.battle, split_msg)

        self.assertEqual("raindance", self.battle.weather)
        self.assertEqual(5, self.battle.weather_turns_remaining)

    def test_sets_rain_to_8_turns_from_ability_gen6_with_extension_item(self):
        self.battle.generation = "gen6"
        self.battle.opponent.active.item = "damprock"
        split_msg = [
            "",
            "-weather",
            "RainDance",
            "[from] ability: Drizzle",
            "[of] p2a: Pelipper",
        ]

        weather(self.battle, split_msg)

        self.assertEqual("raindance", self.battle.weather)
        self.assertEqual(8, self.battle.weather_turns_remaining)

    def test_sets_sun_to_8_turns_from_ability_gen6_with_extension_item(self):
        self.battle.generation = "gen6"
        self.battle.opponent.active.item = "heatrock"
        split_msg = [
            "",
            "-weather",
            "SunnyDay",
            "[from] ability: Drought",
            "[of] p2a: Pelipper",
        ]

        weather(self.battle, split_msg)

        self.assertEqual("sunnyday", self.battle.weather)
        self.assertEqual(8, self.battle.weather_turns_remaining)

    def test_sets_sand_to_8_turns_from_ability_gen6_with_extension_item(self):
        self.battle.generation = "gen6"
        self.battle.opponent.active.item = "smoothrock"
        split_msg = [
            "",
            "-weather",
            "SandStorm",
            "[from] ability: Sand Stream",
            "[of] p2a: Pelipper",
        ]

        weather(self.battle, split_msg)

        self.assertEqual("sandstorm", self.battle.weather)
        self.assertEqual(8, self.battle.weather_turns_remaining)

    def test_sets_hail_to_8_turns_from_ability_gen6_with_extension_item(self):
        self.battle.generation = "gen6"
        self.battle.opponent.active.item = "icyrock"
        split_msg = [
            "",
            "-weather",
            "Hail",
            "[from] ability: Snow Warning",
            "[of] p2a: Pelipper",
        ]

        weather(self.battle, split_msg)

        self.assertEqual("hail", self.battle.weather)
        self.assertEqual(8, self.battle.weather_turns_remaining)

    def test_sets_weather_turns_remaining_from_move_gen4(self):
        self.battle.generation = "gen4"
        split_msg = [
            "",
            "-weather",
            "RainDance",
        ]

        weather(self.battle, split_msg)

        self.assertEqual("raindance", self.battle.weather)
        self.assertEqual(5, self.battle.weather_turns_remaining)

    def test_decrements_weather(self):
        self.battle.generation = "gen4"
        self.battle.weather = constants.RAIN
        self.battle.weather_turns_remaining = 5
        split_msg = [
            "",
            "-weather",
            "RainDance",
            "[upkeep]",
        ]

        weather(self.battle, split_msg)

        self.assertEqual("raindance", self.battle.weather)
        self.assertEqual(4, self.battle.weather_turns_remaining)

    def test_does_not_decrement_weather_if_set_to_negative_1(self):
        self.battle.generation = "gen4"
        self.battle.weather = constants.RAIN
        self.battle.weather_turns_remaining = -1
        split_msg = [
            "",
            "-weather",
            "RainDance",
            "[upkeep]",
        ]

        weather(self.battle, split_msg)

        self.assertEqual("raindance", self.battle.weather)
        self.assertEqual(-1, self.battle.weather_turns_remaining)

    def test_sets_weather_to_3_when_expecting_0(self):
        self.battle.generation = "gen4"
        self.battle.weather = constants.RAIN
        self.battle.weather_turns_remaining = 1
        split_msg = [
            "",
            "-weather",
            "RainDance",
            "[upkeep]",
        ]

        weather(self.battle, split_msg)

        self.assertEqual("raindance", self.battle.weather)
        self.assertEqual(3, self.battle.weather_turns_remaining)

    def test_sets_weather_ability_on_opponent_when_it_is_present(self):
        split_msg = [
            "",
            "-weather",
            "RainDance",
            "[from] ability: Drizzle",
            "[of] p2a: Pelipper",
        ]

        weather(self.battle, split_msg)

        self.assertEqual("drizzle", self.battle.opponent.active.ability)

    def test_sets_weather_ability_on_user_when_it_is_present(self):
        split_msg = [
            "",
            "-weather",
            "RainDance",
            "[from] ability: Drizzle",
            "[of] p1a: Pelipper",
        ]

        weather(self.battle, split_msg)

        self.assertEqual("drizzle", self.battle.user.active.ability)


# |-setboost|p2a: Linoone|atk|6|[from] move: Belly Drum
class TestSetBoost(unittest.TestCase):
    def setUp(self):
        self.battle = Battle(None)
        self.battle.user.name = "p1"
        self.battle.opponent.name = "p2"

        self.user_active = Pokemon("weedle", 100)
        self.battle.user.active = self.user_active

        self.opponent_active = Pokemon("caterpie", 100)
        self.battle.opponent.active = self.opponent_active

    def test_set_boost_to_6_from_bellydrum(self):
        split_msg = [
            "",
            "-setboost",
            "p2a: Linoone",
            "atk",
            "6",
            "[from] move: Belly Drum",
        ]
        setboost(self.battle, split_msg)

        expected_boosts = {constants.ATTACK: 6}

        self.assertEqual(expected_boosts, self.battle.opponent.active.boosts)

    def test_set_boost_to_6_even_when_at_negative_from_bellydrum(self):
        self.battle.opponent.active.boosts[constants.ATTACK] = -3
        split_msg = [
            "",
            "-setboost",
            "p2a: Linoone",
            "atk",
            "6",
            "[from] move: Belly Drum",
        ]
        setboost(self.battle, split_msg)

        expected_boosts = {constants.ATTACK: 6}

        self.assertEqual(expected_boosts, self.battle.opponent.active.boosts)


class TestBoostAndUnboost(unittest.TestCase):
    def setUp(self):
        self.battle = Battle(None)
        self.battle.user.name = "p1"
        self.battle.opponent.name = "p2"

        self.user_active = Pokemon("weedle", 100)
        self.battle.user.active = self.user_active

        self.opponent_active = Pokemon("caterpie", 100)
        self.battle.opponent.active = self.opponent_active

    def test_opponent_boost_properly_updates_opponent_pokemons_boosts(self):
        split_msg = ["", "boost", "p2a: Weedle", "atk", "1"]
        boost(self.battle, split_msg)

        expected_boosts = {constants.ATTACK: 1}

        self.assertEqual(expected_boosts, self.battle.opponent.active.boosts)

    def test_unboost_works_properly_on_opponent(self):
        split_msg = ["", "boost", "p2a: Weedle", "atk", "1"]
        unboost(self.battle, split_msg)

        expected_boosts = {constants.ATTACK: -1}

        self.assertEqual(expected_boosts, self.battle.opponent.active.boosts)

    def test_unboost_does_not_lower_below_negative_6(self):
        self.battle.opponent.active.boosts[constants.ATTACK] = -6
        split_msg = ["", "unboost", "p2a: Weedle", "atk", "2"]
        unboost(self.battle, split_msg)

        expected_boosts = {constants.ATTACK: -6}

        self.assertEqual(expected_boosts, dict(self.battle.opponent.active.boosts))

    def test_unboost_lowers_one_when_it_hits_the_limit(self):
        self.battle.opponent.active.boosts[constants.ATTACK] = -5
        split_msg = ["", "unboost", "p2a: Weedle", "atk", "2"]
        unboost(self.battle, split_msg)

        expected_boosts = {constants.ATTACK: -6}

        self.assertEqual(expected_boosts, dict(self.battle.opponent.active.boosts))

    def test_boost_does_not_lower_below_negative_6(self):
        self.battle.opponent.active.boosts[constants.ATTACK] = 6
        split_msg = ["", "boost", "p2a: Weedle", "atk", "2"]
        boost(self.battle, split_msg)

        expected_boosts = {constants.ATTACK: 6}

        self.assertEqual(expected_boosts, dict(self.battle.opponent.active.boosts))

    def test_boost_lowers_one_when_it_hits_the_limit(self):
        self.battle.opponent.active.boosts[constants.ATTACK] = 5
        split_msg = ["", "boost", "p2a: Weedle", "atk", "2"]
        boost(self.battle, split_msg)

        expected_boosts = {constants.ATTACK: 6}

        self.assertEqual(expected_boosts, dict(self.battle.opponent.active.boosts))

    def test_unboost_works_properly_on_user(self):
        split_msg = ["", "boost", "p1a: Caterpie", "atk", "1"]
        unboost(self.battle, split_msg)

        expected_boosts = {constants.ATTACK: -1}

        self.assertEqual(expected_boosts, self.battle.user.active.boosts)

    def test_user_boosts_updates_properly(self):
        split_msg = ["", "boost", "p1a: Caterpie", "atk", "1"]
        boost(self.battle, split_msg)

        expected_boosts = {constants.ATTACK: 1}

        self.assertEqual(expected_boosts, self.battle.user.active.boosts)

    def test_multiple_boost_properly_updates(self):
        split_msg = ["", "boost", "p2a: Weedle", "atk", "1"]
        boost(self.battle, split_msg)
        boost(self.battle, split_msg)

        expected_boosts = {constants.ATTACK: 2}

        self.assertEqual(expected_boosts, self.battle.opponent.active.boosts)


class TestStatus(unittest.TestCase):
    def setUp(self):
        self.battle = Battle(None)
        self.battle.user.name = "p1"
        self.battle.opponent.name = "p2"

        self.battle.opponent.active = Pokemon("caterpie", 100)
        self.battle.user.active = Pokemon("caterpie", 100)

    def test_opponents_active_pokemon_has_status_properly_set(self):
        split_msg = ["", "-status", "p2a: Caterpie", "brn"]
        status(self.battle, split_msg)

        self.assertEqual(self.battle.opponent.active.status, constants.BURN)

    def test_getting_status_causes_lumberry_to_be_an_impossible_item(self):
        split_msg = ["", "-status", "p2a: Caterpie", "brn"]
        status(self.battle, split_msg)

        self.assertIn("lumberry", self.battle.opponent.active.impossible_items)

    def test_rest_turns_set_to_3_on_rest(self):
        split_msg = ["", "-status", "p2a: Caterpie", "slp", "[from] move: Rest"]
        status(self.battle, split_msg)

        self.assertEqual(self.battle.opponent.active.status, constants.SLEEP)
        self.assertEqual(self.battle.opponent.active.rest_turns, 3)

    def test_rest_turns_at_0_and_sleep_turns_at_0_from_nonrest_sleep(self):
        split_msg = ["", "-status", "p2a: Caterpie", "slp", "[from] move: Sleep powder"]
        status(self.battle, split_msg)

        self.assertEqual(self.battle.opponent.active.status, constants.SLEEP)
        self.assertEqual(self.battle.opponent.active.rest_turns, 0)
        self.assertEqual(self.battle.opponent.active.sleep_turns, 0)

    def test_bots_active_pokemon_has_status_properly_set(self):
        split_msg = ["", "-status", "p1a: Caterpie", "brn"]
        status(self.battle, split_msg)

        self.assertEqual(self.battle.user.active.status, constants.BURN)

    def test_status_from_item_properly_sets_that_item(self):
        split_msg = ["", "-status", "p2a: Caterpie", "brn", "[from] item: Flame Orb"]
        status(self.battle, split_msg)

        self.assertEqual(self.battle.opponent.active.item, "flameorb")


class TestCureStatus(unittest.TestCase):
    def setUp(self):
        self.battle = Battle(None)
        self.battle.user.name = "p1"
        self.battle.opponent.name = "p2"

        self.opponent_active = Pokemon("caterpie", 100)
        self.battle.opponent.active = self.opponent_active

        self.opponent_reserve = Pokemon("pikachu", 100)
        self.battle.opponent.reserve = [self.opponent_active, self.opponent_reserve]

        self.battle.user.active = Pokemon("weedle", 100)

    def test_curestatus_works_on_active_pokemon(self):
        self.opponent_active.status = constants.BURN
        split_msg = ["", "-curestatus", "p2: Caterpie", "brn", "[msg]"]
        curestatus(self.battle, split_msg)

        self.assertEqual(None, self.opponent_active.status)

    def test_curestatus_works_on_active_pokemon_for_bot(self):
        self.battle.user.active.status = constants.BURN
        split_msg = ["", "-curestatus", "p1: Weedle", "brn", "[msg]"]
        curestatus(self.battle, split_msg)

        self.assertEqual(None, self.battle.user.active.status)

    def test_curestatus_works_on_reserve_pokemon(self):
        self.opponent_reserve.status = constants.BURN
        split_msg = ["", "-curestatus", "p2: Pikachu", "brn", "[msg]"]
        curestatus(self.battle, split_msg)

        self.assertEqual(None, self.opponent_reserve.status)

    def test_curestatus_sets_sleep_and_rest_turns_to_0(self):
        self.opponent_reserve.status = constants.SLEEP
        self.opponent_reserve.sleep_turns = 1
        self.opponent_reserve.rest_turns = 1
        split_msg = ["", "-curestatus", "p2: Pikachu", "slp", "[msg]"]
        curestatus(self.battle, split_msg)

        self.assertEqual(0, self.opponent_reserve.sleep_turns)
        self.assertEqual(0, self.opponent_reserve.rest_turns)


class TestStartFutureSight(unittest.TestCase):
    def setUp(self):
        self.battle = Battle(None)
        self.battle.user.name = "p1"
        self.battle.opponent.name = "p2"

        self.opponent_active = Pokemon("caterpie", 100)
        self.battle.opponent.active = self.opponent_active

        self.user_active = Pokemon("weedle", 100)
        self.battle.user.active = self.user_active

    def test_sets_futuresight_on_side_that_used_the_move(self):
        split_msg = ["", "-start", "p2a: Caterpie", "Future Sight"]
        start_volatile_status(self.battle, split_msg)

        self.assertEqual(self.battle.opponent.future_sight, (3, "caterpie"))

    def test_does_not_set_futuresight_as_a_volatilestatus(self):
        split_msg = ["", "-start", "p2a: Caterpie", "Future Sight"]
        self.battle.opponent.active.volatile_statuses = []
        start_volatile_status(self.battle, split_msg)

        self.assertEqual([], self.battle.opponent.active.volatile_statuses)


class TestStartVolatileStatus(unittest.TestCase):
    def setUp(self):
        self.battle = Battle(None)
        self.battle.user.name = "p1"
        self.battle.opponent.name = "p2"

        self.opponent_active = Pokemon("caterpie", 100)
        self.battle.opponent.active = self.opponent_active

        self.user_active = Pokemon("weedle", 100)
        self.battle.user.active = self.user_active

    def test_volatile_status_is_set_on_opponent_pokemon(self):
        split_msg = ["", "-start", "p2a: Caterpie", "Encore"]
        start_volatile_status(self.battle, split_msg)

        expected_volatile_statuese = ["encore"]

        self.assertEqual(
            expected_volatile_statuese, self.battle.opponent.active.volatile_statuses
        )

    def test_substitute_gets_substitute_hit_flag_set_to_false(self):
        self.battle.user.active.max_hp = 100
        self.battle.user.active.hp = 100

        self.battle.opponent.active.hp = 100
        self.battle.user.active.hp = 100

        messages = [
            "|move|p2a: Pikachu|Substitute|p2a: Pikachu",
            "|-start|p2a: Pikachu|Substitute",
            "|-damage|p2a: Pikachu|75/100",  # damage from sub should not be caught
        ]

        split_msg = messages[1].split("|")

        start_volatile_status(self.battle, split_msg)
        self.assertFalse(self.battle.opponent.active.substitute_hit)

    def test_flashfire_sets_ability_on_opponent(self):
        split_msg = ["", "-start", "p2a: Caterpie", "ability: Flash Fire"]
        start_volatile_status(self.battle, split_msg)

        self.assertEqual("flashfire", self.battle.opponent.active.ability)

    def test_flashfire_sets_ability_on_bot(self):
        split_msg = ["", "-start", "p1a: Caterpie", "ability: Flash Fire"]
        start_volatile_status(self.battle, split_msg)

        self.assertEqual("flashfire", self.battle.user.active.ability)

    def test_volatile_status_is_set_on_user_pokemon(self):
        split_msg = ["", "-start", "p1a: Weedle", "Encore"]
        start_volatile_status(self.battle, split_msg)

        expected_volatile_statuese = ["encore"]

        self.assertEqual(
            expected_volatile_statuese, self.battle.user.active.volatile_statuses
        )

    def test_adds_volatile_status_from_move_string(self):
        split_msg = ["", "-start", "p1a: Weedle", "move: Taunt"]
        start_volatile_status(self.battle, split_msg)

        expected_volatile_statuese = ["taunt"]

        self.assertEqual(
            expected_volatile_statuese, self.battle.user.active.volatile_statuses
        )

    def test_does_not_add_the_same_volatile_status_twice(self):
        self.battle.opponent.active.volatile_statuses = ["encore"]
        split_msg = ["", "-start", "p2a: Caterpie", "Encore"]
        start_volatile_status(self.battle, split_msg)

        expected_volatile_statuese = ["encore"]

        self.assertEqual(
            expected_volatile_statuese, self.battle.opponent.active.volatile_statuses
        )

    def test_doubles_hp_when_dynamax_starts_for_opponent(self):
        split_msg = ["", "-start", "p2a: Caterpie", "Dynamax"]
        hp, maxhp = self.battle.opponent.active.hp, self.battle.opponent.active.max_hp
        start_volatile_status(self.battle, split_msg)

        self.assertEqual(hp * 2, self.battle.opponent.active.hp)
        self.assertEqual(maxhp * 2, self.battle.opponent.active.max_hp)

    def test_doubles_hp_when_dynamax_starts_for_bot(self):
        split_msg = ["", "-start", "p1a: Caterpie", "Dynamax"]
        hp, maxhp = self.battle.user.active.hp, self.battle.user.active.max_hp
        start_volatile_status(self.battle, split_msg)

        self.assertEqual(hp * 2, self.battle.user.active.hp)
        self.assertEqual(maxhp * 2, self.battle.user.active.max_hp)

    def test_terastallize(self):
        split_msg = ["", "-terastallize", "p2a: Caterpie", "Fire"]
        terastallize(self.battle, split_msg)

        self.assertTrue(self.battle.opponent.active.terastallized)

    def test_terastallize_sets_tera_type(self):
        split_msg = ["", "-terastallize", "p2a: Caterpie", "Fire"]
        terastallize(self.battle, split_msg)

        self.assertEqual("fire", self.battle.opponent.active.tera_type)

    def test_sets_ability(self):
        # |-start|p1a: Cinderace|typechange|Fighting|[from] ability: Libero
        split_msg = [
            "",
            "-start",
            "p2a: Cinderace",
            "typechange",
            "Fighting",
            "[from] ability: Libero",
        ]
        start_volatile_status(self.battle, split_msg)

        self.assertEqual("libero", self.battle.opponent.active.ability)

    def test_typechange_starts_volatilestatus(self):
        # |-start|p1a: Cinderace|typechange|Fighting|[from] ability: Libero
        split_msg = [
            "",
            "-start",
            "p2a: Cinderace",
            "typechange",
            "Fighting",
            "[from] ability: Libero",
        ]
        start_volatile_status(self.battle, split_msg)

        self.assertIn(
            constants.TYPECHANGE, self.battle.opponent.active.volatile_statuses
        )

    def test_getting_confused_makes_lumberry_impossible(self):
        split_msg = [
            "",
            "-start",
            "p2a: Cinderace",
            "Confusion",
        ]
        start_volatile_status(self.battle, split_msg)

        self.assertIn("lumberry", self.battle.opponent.active.impossible_items)

    def test_getting_confused_from_fatigue_removes_lockedmove(self):
        self.battle.opponent.active.volatile_statuses.append("lockedmove")
        split_msg = ["", "-start", "p2a: Cinderace", "Confusion", "[fatigue]"]
        start_volatile_status(self.battle, split_msg)

        self.assertNotIn(
            constants.LOCKED_MOVE, self.battle.opponent.active.volatile_statuses
        )

    def test_typechange_changes_the_type_of_the_user(self):
        # |-start|p1a: Cinderace|typechange|Fighting|[from] ability: Libero
        split_msg = [
            "",
            "-start",
            "p2a: Cinderace",
            "typechange",
            "Fighting",
            "[from] ability: Libero",
        ]
        start_volatile_status(self.battle, split_msg)

        self.assertEqual(["fighting"], self.battle.opponent.active.types)

    def test_typechange_works_with_reflect_type(self):
        # |-start|p1a: Starmie|typechange|[from] move: Reflect Type|[of] p2a: Dragapult
        split_msg = [
            "",
            "-start",
            "p2a: Starmie",
            "typechange",
            "[from] move: Reflect Type",
            "[of] p1a: Dragapult",
        ]
        start_volatile_status(self.battle, split_msg)

        self.assertEqual(["dragon", "ghost"], self.battle.opponent.active.types)

    def test_typechange_from_multiple_types(self):
        # |-start|p2a: Moltres|typechange|???/Flying|[from] move: Burn Up
        split_msg = [
            "",
            "-start",
            "p2a: Moltres",
            "typechange",
            "???/Flying",
            "[from] move: Burn Up",
        ]
        start_volatile_status(self.battle, split_msg)

        self.assertEqual(["???", "flying"], self.battle.opponent.active.types)


class TestEndVolatileStatus(unittest.TestCase):
    def setUp(self):
        self.battle = Battle(None)
        self.battle.user.name = "p1"
        self.battle.opponent.name = "p2"

        self.opponent_active = Pokemon("caterpie", 100)
        self.battle.opponent.active = self.opponent_active

        self.user_active = Pokemon("weedle", 100)
        self.battle.user.active = self.user_active

    def test_removes_volatile_status_from_opponent(self):
        self.battle.opponent.active.volatile_statuses = ["encore"]
        split_msg = ["", "-end", "p2a: Caterpie", "Encore"]
        end_volatile_status(self.battle, split_msg)

        expected_volatile_statuses = []

        self.assertEqual(
            expected_volatile_statuses, self.battle.opponent.active.volatile_statuses
        )

    def test_removes_volatile_status_from_user(self):
        self.battle.user.active.volatile_statuses = ["encore"]
        split_msg = ["", "-end", "p1a: Weedle", "Encore"]
        end_volatile_status(self.battle, split_msg)

        expected_volatile_statuses = []

        self.assertEqual(
            expected_volatile_statuses, self.battle.user.active.volatile_statuses
        )

    def test_halves_opponent_hp_when_dynamax_ends(self):
        self.battle.opponent.active.volatile_statuses = ["dynamax"]
        hp, maxhp = self.battle.opponent.active.hp, self.battle.opponent.active.max_hp
        split_msg = ["", "-end", "p2a: Weedle", "Dynamax"]
        end_volatile_status(self.battle, split_msg)

        self.assertEqual(hp / 2, self.battle.opponent.active.hp)
        self.assertEqual(maxhp / 2, self.battle.opponent.active.max_hp)

    def test_halves_bots_hp_when_dynamax_ends(self):
        self.battle.user.active.volatile_statuses = ["dynamax"]
        hp, maxhp = self.battle.user.active.hp, self.battle.user.active.max_hp
        split_msg = ["", "-end", "p1a: Weedle", "Dynamax"]
        end_volatile_status(self.battle, split_msg)

        self.assertEqual(hp / 2, self.battle.user.active.hp)
        self.assertEqual(maxhp / 2, self.battle.user.active.max_hp)

    def test_ending_substitute_sets_substitute_hit_to_false(self):
        self.battle.opponent.active.substitute_hit = True

        split_msg = ["", "-end", "p2a: Weedle", "Substitute"]
        end_volatile_status(self.battle, split_msg)
        self.assertFalse(self.battle.opponent.active.substitute_hit)


class TestUpdateAbility(unittest.TestCase):
    def setUp(self):
        self.battle = Battle(None)
        self.battle.user.name = "p1"
        self.battle.opponent.name = "p2"

        self.opponent_active = Pokemon("caterpie", 100)
        self.battle.opponent.active = self.opponent_active
        self.battle.opponent.active.ability = None

        self.user_active = Pokemon("weedle", 100)
        self.battle.user.active = self.user_active

    def test_update_ability_from_ability_string_properly_updates_ability(self):
        split_msg = ["", "-ability", "p2a: Caterpie", "Lightning Rod", "boost"]
        set_opponent_ability_from_ability_tag(self.battle, split_msg)

        expected_ability = "lightningrod"

        self.assertEqual(expected_ability, self.battle.opponent.active.ability)

    def test_update_ability_from_ability_string_properly_updates_ability_for_bot(self):
        split_msg = ["", "-ability", "p1a: Caterpie", "Lightning Rod", "boost"]
        set_opponent_ability_from_ability_tag(self.battle, split_msg)

        expected_ability = "lightningrod"

        self.assertEqual(expected_ability, self.battle.user.active.ability)


class TestSwapSideConditions(unittest.TestCase):
    def setUp(self):
        self.battle = Battle(None)
        self.battle.user.name = "p1"
        self.battle.opponent.name = "p2"

        self.opponent_active = Pokemon("caterpie", 100)
        self.battle.opponent.active = self.opponent_active
        self.battle.opponent.active.ability = None

        self.user_active = Pokemon("weedle", 100)
        self.battle.user.active = self.user_active

    def get_expected_empty_dict(self):
        # The defaultdict's start empty, but swapping them adds the values of 0 to them
        return {k: 0 for k in constants.COURT_CHANGE_SWAPS}

    def test_does_nothing_when_no_side_conditions_are_present(self):
        split_msg = ["", "-swapsideconditions"]
        swapsideconditions(self.battle, split_msg)

        expected_dict = self.get_expected_empty_dict()

        self.assertEqual(expected_dict, self.battle.user.side_conditions)
        self.assertEqual(expected_dict, self.battle.opponent.side_conditions)

    def test_swaps_one_layer_of_spikes(self):
        split_msg = ["", "-swapsideconditions"]

        self.battle.user.side_conditions[constants.SPIKES] = 1

        swapsideconditions(self.battle, split_msg)

        expected_user_side_conditions = self.get_expected_empty_dict()

        expected_opponent_side_conditions = self.get_expected_empty_dict()
        expected_opponent_side_conditions[constants.SPIKES] = 1

        self.assertEqual(
            expected_user_side_conditions, self.battle.user.side_conditions
        )
        self.assertEqual(
            expected_opponent_side_conditions, self.battle.opponent.side_conditions
        )

    def test_swaps_one_layer_of_spikes_with_two_layers_of_spikes(self):
        split_msg = ["", "-swapsideconditions"]

        self.battle.user.side_conditions[constants.SPIKES] = 2
        self.battle.opponent.side_conditions[constants.SPIKES] = 1

        swapsideconditions(self.battle, split_msg)

        expected_user_side_conditions = self.get_expected_empty_dict()
        expected_user_side_conditions[constants.SPIKES] = 1

        expected_opponent_side_conditions = self.get_expected_empty_dict()
        expected_opponent_side_conditions[constants.SPIKES] = 2

        self.assertEqual(
            expected_user_side_conditions, self.battle.user.side_conditions
        )
        self.assertEqual(
            expected_opponent_side_conditions, self.battle.opponent.side_conditions
        )

    def test_swaps_multiple_side_conditions_on_either_side(self):
        split_msg = ["", "-swapsideconditions"]

        self.battle.user.side_conditions[constants.SPIKES] = 2
        self.battle.user.side_conditions[constants.REFLECT] = 3
        self.battle.user.side_conditions[constants.TAILWIND] = 2

        self.battle.opponent.side_conditions[constants.SPIKES] = 1
        self.battle.opponent.side_conditions[constants.LIGHT_SCREEN] = 2

        swapsideconditions(self.battle, split_msg)

        expected_user_side_conditions = self.get_expected_empty_dict()
        expected_user_side_conditions[constants.SPIKES] = 1
        expected_user_side_conditions[constants.LIGHT_SCREEN] = 2

        expected_opponent_side_conditions = self.get_expected_empty_dict()
        expected_opponent_side_conditions[constants.SPIKES] = 2
        expected_opponent_side_conditions[constants.REFLECT] = 3
        expected_opponent_side_conditions[constants.TAILWIND] = 2

        self.assertEqual(
            expected_user_side_conditions, self.battle.user.side_conditions
        )
        self.assertEqual(
            expected_opponent_side_conditions, self.battle.opponent.side_conditions
        )


class TestIllusionEnd(unittest.TestCase):
    def setUp(self):
        self.battle = Battle(None)
        self.battle.user.name = "p1"
        self.battle.opponent.name = "p2"

        self.opponent_active = Pokemon("caterpie", 100)
        self.battle.opponent.active = self.opponent_active
        self.battle.opponent.active.ability = None

        self.user_active = Pokemon("weedle", 100)
        self.battle.user.active = self.user_active

    def test_zoroark_is_switched_in_pkmn(self):
        self.battle.opponent.active = Pokemon("meloetta", 100)
        self.battle.opponent.reserve = []
        split_msg = ["", "replace", "p2a: Zoroark", "Zoroark, L82, M"]
        illusion_end(self.battle, split_msg)

        self.assertEqual("zoroark", self.battle.opponent.active.name)

    def test_zoroark_disguising_as_pokemon_results_in_that_pkmn_in_reserve(
        self,
    ):
        """
        Weirdly worded test, but basically:

        If Zoroark was disguised as a previously unseen pkmn, that pkmn should be in the reserve
        Normally theres some fuckery around levels but PokemonShowdown has Illusion Level Mod
        """
        self.battle.opponent.active = Pokemon("meloetta", 100)
        self.battle.opponent.reserve = []
        split_msg = ["", "replace", "p2a: Zoroark", "Zoroark, L82, M"]
        illusion_end(self.battle, split_msg)

        self.assertEqual([Pokemon("meloetta", 100)], self.battle.opponent.reserve)

    def test_moves_used_while_disguised_are_associated_with_zoroark(
        self,
    ):
        """
        zoroark (disguised as meloetta) used focusblast and flamethrower since it switched in
        meloetta previously had hypervoice revealed
        zoroark previously had flamethrower and nastysplot revealed

        illusion ending in this scenario should apply focusblast to zoroark since that is the
        un-revealed zoroark move. meloetta should have focusblast and flamethrower removed
        """
        meloetta = Pokemon("meloetta", 100)
        meloetta.moves = [
            Move("focusblast"),
            Move("flamethrower"),
            Move("hypervoice"),
        ]
        meloetta.moves_used_since_switch_in = ["focusblast", "flamethrower"]
        zoroark = Pokemon("zoroark", 82)
        zoroark.moves = [
            Move("flamethrower"),
            Move("nastyplot"),
        ]
        self.battle.opponent.active = meloetta
        self.battle.opponent.reserve = [zoroark]
        split_msg = ["", "replace", "p2a: Zoroark", "Zoroark, L82, M"]
        illusion_end(self.battle, split_msg)

        self.assertEqual(Pokemon("zoroark", 82), self.battle.opponent.active)
        self.assertEqual([Pokemon("meloetta", 100)], self.battle.opponent.reserve)
        self.assertEqual([Move("hypervoice")], meloetta.moves)
        self.assertEqual(
            [Move("flamethrower"), Move("nastyplot"), Move("focusblast")], zoroark.moves
        )

    def test_moves_used_while_disguised_are_associated_with_previously_nonexistent_zoroark(
        self,
    ):
        meloetta = Pokemon("meloetta", 100)
        meloetta.moves = [
            Move("focusblast"),
            Move("flamethrower"),
            Move("hypervoice"),
        ]
        meloetta.moves_used_since_switch_in = ["focusblast", "flamethrower"]
        self.battle.opponent.active = meloetta
        self.battle.opponent.reserve = []
        split_msg = ["", "replace", "p2a: Zoroark", "Zoroark, L82, M"]
        illusion_end(self.battle, split_msg)

        self.assertEqual(Pokemon("zoroark", 82), self.battle.opponent.active)
        self.assertEqual([Pokemon("meloetta", 100)], self.battle.opponent.reserve)
        self.assertEqual([Move("hypervoice")], meloetta.moves)
        self.assertEqual(
            [Move("focusblast"), Move("flamethrower")],
            self.battle.opponent.active.moves,
        )

    def test_removes_zoroark_from_reserve_if_it_is_in_there(self):
        zoroark = Pokemon("zoroark", 82)
        self.battle.opponent.active = Pokemon("meloetta", 100)
        self.battle.opponent.reserve = [zoroark]
        split_msg = ["", "replace", "p2a: Zoroark", "Zoroark, L82, M"]
        illusion_end(self.battle, split_msg)

        self.assertNotIn(zoroark, self.battle.opponent.reserve)

    def test_does_not_set_base_name_for_illusion_ending(self):
        self.battle.opponent.active = Pokemon("meloetta", 100)
        split_msg = ["", "replace", "p2a: Zoroark", "Zoroark, L84, F"]
        illusion_end(self.battle, split_msg)

        self.assertEqual("zoroark", self.battle.opponent.active.base_name)

    def test_pulls_zoroark_out_of_reserves_if_it_is_in_there(self):
        self.battle.opponent.active = Pokemon("meloetta", 100)
        zoroark = Pokemon("zoroark", 100)
        zoroark.moves = [
            Move("flamethrower"),
            Move("nastyplot"),
            Move("focusblast"),
            Move("darkpulse"),
        ]
        self.battle.opponent.reserve = [zoroark]
        split_msg = ["", "replace", "p2a: Zoroark", "Zoroark, F"]
        illusion_end(self.battle, split_msg)

        self.assertEqual("zoroark", self.battle.opponent.active.base_name)
        self.assertEqual(4, len(self.battle.opponent.active.moves))

    def test_does_nothing_if_zoroark_was_already_active_pkmn(self):
        """
        Logically this seems impossible but the client has places where it tries to infer a
        zoroark based events that happen before the zoroark is revealed. If that was done
        the zoroark would've been set as the active pkmn and the illusion ending event should
        do nothing
        """
        self.battle.opponent.active = Pokemon("zoroark", 100)
        self.battle.opponent.active.zoroark_disguised_as = "meloetta"
        self.battle.opponent.active.moves = [
            Move("flamethrower"),
            Move("nastyplot"),
            Move("focusblast"),
            Move("darkpulse"),
        ]
        self.battle.opponent.reserve = [Pokemon("meloetta", 100)]
        split_msg = ["", "replace", "p2a: Zoroark", "Zoroark, L84, F"]
        illusion_end(self.battle, split_msg)

        self.assertEqual("zoroark", self.battle.opponent.active.base_name)
        self.assertEqual("meloetta", self.battle.opponent.active.zoroark_disguised_as)
        self.assertEqual("meloetta", self.battle.opponent.reserve[0].name)
        self.assertEqual(4, len(self.battle.opponent.active.moves))


class TestFormChange(unittest.TestCase):
    def setUp(self):
        self.battle = Battle(None)
        self.battle.user.name = "p1"
        self.battle.opponent.name = "p2"

        self.opponent_active = Pokemon("caterpie", 100)
        self.battle.opponent.active = self.opponent_active
        self.battle.opponent.active.ability = None

        self.user_active = Pokemon("weedle", 100)
        self.battle.user.active = self.user_active

    def test_changes_with_formechange_message(self):
        self.battle.opponent.active = Pokemon("meloetta", 100)
        split_msg = [
            "",
            "-formechange",
            "p2a: Meloetta",
            "Meloetta - Pirouette",
            "[msg]",
        ]
        form_change(self.battle, split_msg)

        self.assertEqual("meloettapirouette", self.battle.opponent.active.name)

    def test_preserves_boosts(self):
        self.battle.opponent.active = Pokemon("meloetta", 100)
        self.battle.opponent.active.boosts = {constants.ATTACK: 2}
        split_msg = [
            "",
            "-formechange",
            "p2a: Meloetta",
            "Meloetta - Pirouette",
            "[msg]",
        ]
        form_change(self.battle, split_msg)

        self.assertEqual(2, self.battle.opponent.active.boosts[constants.ATTACK])

    def test_preserves_status(self):
        self.battle.opponent.active = Pokemon("meloetta", 100)
        self.battle.opponent.active.status = constants.BURN
        split_msg = [
            "",
            "-formechange",
            "p2a: Meloetta",
            "Meloetta - Pirouette",
            "[msg]",
        ]
        form_change(self.battle, split_msg)

        self.assertEqual(constants.BURN, self.battle.opponent.active.status)

    def test_preserves_item(self):
        self.battle.opponent.active = Pokemon("aegislash", 100)
        self.battle.opponent.active.item = "airballoon"
        split_msg = [
            "",
            "-formechange",
            "p2a: Aegislash",
            "Aegislash-Blade",
            "[from] ability: Stance Change",
        ]
        form_change(self.battle, split_msg)

        self.assertEqual("airballoon", self.battle.opponent.active.item)

    def test_preserves_base_name_when_form_changes(self):
        self.battle.opponent.active = Pokemon("meloetta", 100)
        split_msg = [
            "",
            "-formechange",
            "p2a: Meloetta",
            "Meloetta - Pirouette",
            "[msg]",
        ]
        form_change(self.battle, split_msg)

        self.assertEqual("meloetta", self.battle.opponent.active.base_name)

    def test_multiple_forme_changes_does_not_ruin_base_name(self):
        self.battle.user.active = Pokemon("pikachu", 100)
        self.battle.opponent.active = Pokemon("pikachu", 100)
        self.battle.opponent.reserve = []
        self.battle.opponent.reserve.append(Pokemon("wishiwashi", 100))

        m1 = ["", "switch", "p2a: Wishiwashi", "Wishiwashi, L100, M", "100/100"]
        m2 = [
            "",
            "-formechange",
            "p2a: Wishiwashi",
            "Wishiwashi-School",
            "",
            "[from] ability: Schooling",
        ]
        m3 = ["", "switch", "p2a: Pikachu", "Pikachu, L100, M", "100/100"]
        m4 = ["", "switch", "p2a: Wishiwashi", "Wishiwashi, L100, M", "100/100"]
        m5 = [
            "",
            "-formechange",
            "p2a: Wishiwashi",
            "Wishiwashi-School",
            "",
            "[from] ability: Schooling",
        ]
        m6 = ["", "switch", "p2a: Pikachu", "Pikachu, L100, M", "100/100"]
        m7 = ["", "switch", "p2a: Wishiwashi", "Wishiwashi, L100, M", "100/100"]
        m8 = [
            "",
            "-formechange",
            "p2a: Wishiwashi",
            "Wishiwashi-School",
            "",
            "[from] ability: Schooling",
        ]

        switch_or_drag(self.battle, m1)
        form_change(self.battle, m2)
        switch_or_drag(self.battle, m3)
        switch_or_drag(self.battle, m4)
        form_change(self.battle, m5)
        switch_or_drag(self.battle, m6)
        switch_or_drag(self.battle, m7)
        form_change(self.battle, m8)

        pkmn = Pokemon("wishiwashischool", 100)
        self.assertNotIn(pkmn, self.battle.opponent.reserve)


class TestClearNegativeBoost(unittest.TestCase):
    def setUp(self):
        self.battle = Battle(None)
        self.battle.user.name = "p1"
        self.battle.opponent.name = "p2"

        self.user_active = Pokemon("weedle", 100)
        self.battle.user.active = self.user_active

        self.opponent_active = Pokemon("caterpie", 100)
        self.battle.opponent.active = self.opponent_active

    def test_clears_negative_boosts(self):
        self.battle.opponent.active.boosts = {constants.ATTACK: -1}
        split_msg = ["-clearnegativeboost", "p2a: caterpie", "[silent]"]
        clearnegativeboost(self.battle, split_msg)

        self.assertEqual(0, self.battle.opponent.active.boosts[constants.ATTACK])

    def test_clears_multiple_negative_boosts(self):
        self.battle.opponent.active.boosts = {constants.ATTACK: -1, constants.SPEED: -1}
        split_msg = ["-clearnegativeboost", "p2a: caterpie", "[silent]"]
        clearnegativeboost(self.battle, split_msg)

        self.assertEqual(0, self.battle.opponent.active.boosts[constants.ATTACK])
        self.assertEqual(0, self.battle.opponent.active.boosts[constants.SPEED])

    def test_does_not_clear_positive_boost(self):
        self.battle.opponent.active.boosts = {constants.ATTACK: 1}
        split_msg = ["-clearnegativeboost", "p2a: caterpie", "[silent]"]
        clearnegativeboost(self.battle, split_msg)

        self.assertEqual(1, self.battle.opponent.active.boosts[constants.ATTACK])

    def test_clears_only_negative_boosts(self):
        self.battle.opponent.active.boosts = {
            constants.ATTACK: 1,
            constants.SPECIAL_ATTACK: 1,
            constants.SPEED: 1,
            constants.DEFENSE: -1,
            constants.SPECIAL_DEFENSE: -1,
        }
        split_msg = ["-clearnegativeboost", "p2a: caterpie", "[silent]"]
        clearnegativeboost(self.battle, split_msg)

        expected_boosts = {
            constants.ATTACK: 1,
            constants.SPECIAL_ATTACK: 1,
            constants.SPEED: 1,
            constants.DEFENSE: 0,
            constants.SPECIAL_DEFENSE: 0,
        }

        self.assertEqual(expected_boosts, self.battle.opponent.active.boosts)


class TestClearBoost(unittest.TestCase):
    def setUp(self):
        self.battle = Battle(None)
        self.battle.user.name = "p1"
        self.battle.opponent.name = "p2"

        self.user_active = Pokemon("weedle", 100)
        self.battle.user.active = self.user_active

        self.opponent_active = Pokemon("caterpie", 100)
        self.battle.opponent.active = self.opponent_active

    def test_clears_boost(self):
        self.battle.opponent.active.boosts = {constants.ATTACK: 2}
        split_msg = ["-clearboost", "p2a: caterpie", "[silent]"]
        clearboost(self.battle, split_msg)

        self.assertEqual(0, self.battle.opponent.active.boosts[constants.ATTACK])

    def test_clears_multiple_boosts(self):
        self.battle.opponent.active.boosts = {
            constants.ATTACK: 2,
            constants.SPEED: 1,
            constants.SPECIAL_ATTACK: -3,
        }
        split_msg = ["-clearboost", "p2a: caterpie", "[silent]"]
        clearboost(self.battle, split_msg)

        self.assertEqual(0, self.battle.opponent.active.boosts[constants.ATTACK])
        self.assertEqual(
            0, self.battle.opponent.active.boosts[constants.SPECIAL_ATTACK]
        )
        self.assertEqual(0, self.battle.opponent.active.boosts[constants.SPEED])


class TestZPower(unittest.TestCase):
    def setUp(self):
        self.battle = Battle(None)
        self.battle.user.name = "p1"
        self.battle.opponent.name = "p2"

        self.opponent_active = Pokemon("caterpie", 100)
        self.battle.opponent.active = self.opponent_active
        self.battle.opponent.active.ability = None

        self.user_active = Pokemon("weedle", 100)
        self.battle.user.active = self.user_active

        self.username = "CoolUsername"

        self.battle.username = self.username

    def test_sets_item_to_none(self):
        split_msg = ["", "-zpower", "p2a: Pkmn"]
        self.battle.opponent.active.item = "some_item"
        zpower(self.battle, split_msg)

        self.assertEqual(None, self.battle.opponent.active.item)

    def test_does_not_set_item_when_the_bot_moves(self):
        split_msg = ["", "-zpower", "p1a: Pkmn"]
        self.battle.opponent.active.item = "some_item"
        zpower(self.battle, split_msg)

        self.assertEqual("some_item", self.battle.opponent.active.item)


class TestSingleTurn(unittest.TestCase):
    def setUp(self):
        self.battle = Battle(None)
        self.battle.user.name = "p1"
        self.battle.opponent.name = "p2"

        self.opponent_active = Pokemon("caterpie", 100)
        self.battle.opponent.active = self.opponent_active
        self.battle.opponent.active.ability = None

        self.user_active = Pokemon("weedle", 100)
        self.battle.user.active = self.user_active

        self.username = "CoolUsername"

        self.battle.username = self.username

    def test_sets_protect_side_condition_for_opponent_when_used(self):
        split_msg = ["", "-singleturn", "p2a: Caterpie", "Protect"]
        singleturn(self.battle, split_msg)

        self.assertEqual(2, self.battle.opponent.side_conditions[constants.PROTECT])

    def test_does_not_set_for_non_protect_move(self):
        split_msg = ["", "-singleturn", "p2a: Caterpie", "Roost"]
        singleturn(self.battle, split_msg)

        self.assertEqual(0, self.battle.opponent.side_conditions[constants.PROTECT])

    def test_sets_protect_side_condition_for_bot_when_used(self):
        split_msg = ["", "-singleturn", "p1a: Weedle", "Protect"]
        singleturn(self.battle, split_msg)

        self.assertEqual(2, self.battle.user.side_conditions[constants.PROTECT])

    def test_sets_protect_side_condition_when_prefixed_by_move(self):
        split_msg = ["", "-singleturn", "p2a: Caterpie", "move: Protect"]
        singleturn(self.battle, split_msg)

        self.assertEqual(2, self.battle.opponent.side_conditions[constants.PROTECT])


class TestTransform(unittest.TestCase):
    def setUp(self):
        self.battle = Battle(None)
        self.battle.user.name = "p1"
        self.battle.opponent.name = "p2"

        self.opponent_active = Pokemon("Ditto", 100)
        self.battle.opponent.active = self.opponent_active

        self.user_active = Pokemon("weedle", 100)
        self.battle.user.active = self.user_active

        self.username = "CoolUsername"

        self.battle.username = self.username

        self.user_active_stats = {
            "atk": 103,
            "def": 214,
            "spa": 118,
            "spd": 132,
            "spe": 132,
        }
        self.user_active_ability = "levitate"
        self.user_active_moves = [
            "dracometeor",
            "darkpulse",
            "flashcannon",
            "fireblast",
        ]
        self.request_json = {
            "active": [
                {
                    "moves": [
                        {
                            "move": "Draco Meteor",
                            "id": "dracometeor",
                            "pp": 5,
                            "maxpp": 5,
                            "target": "normal",
                            "disabled": False,
                        },
                        {
                            "move": "Dark Pulse",
                            "id": "darkpulse",
                            "pp": 5,
                            "maxpp": 5,
                            "target": "any",
                            "disabled": False,
                        },
                        {
                            "move": "Flash Cannon",
                            "id": "flashcannon",
                            "pp": 5,
                            "maxpp": 5,
                            "target": "normal",
                            "disabled": False,
                        },
                        {
                            "move": "Fire Blast",
                            "id": "fireblast",
                            "pp": 5,
                            "maxpp": 5,
                            "target": "normal",
                            "disabled": False,
                        },
                    ],
                    "canDynamax": True,
                    "maxMoves": {
                        "maxMoves": [
                            {"move": "maxwyrmwind", "target": "adjacentFoe"},
                            {"move": "maxdarkness", "target": "adjacentFoe"},
                            {"move": "maxsteelspike", "target": "adjacentFoe"},
                            {"move": "maxflare", "target": "adjacentFoe"},
                        ]
                    },
                }
            ],
            "side": {
                "name": "BigBluePikachu",
                "id": "p2",
                "pokemon": [
                    {
                        "ident": "p1: Weedle",
                        "details": "Weedle",
                        "condition": "299/299",
                        "active": True,
                        "stats": self.user_active_stats,
                        "moves": self.user_active_moves,
                        "baseAbility": self.user_active_ability,
                        "item": "choicescarf",
                        "pokeball": "pokeball",
                        "ability": self.user_active_ability,
                    },
                    {
                        "ident": "p1: Charmander",
                        "details": "Charmander",
                        "condition": "299/299",
                        "active": False,
                        "stats": {"atk": 1, "def": 2, "spa": 3, "spd": 4, "spe": 5},
                        "moves": ["flamethrower", "firespin", "scratch", "growl"],
                        "baseAbility": "blaze",
                        "item": "sitrusberry",
                        "pokeball": "pokeball",
                        "ability": "blaze",
                    },
                ],
            },
        }

        self.battle.request_json = self.request_json

    def test_transform_sets_ability_to_opposing_pokemons_ability(self):
        self.battle.user.active.ability = self.user_active_ability
        self.battle.opponent.active.ability = None
        split_msg = [
            "",
            "-transform",
            "p2a: Ditto",
            "p1a: Weedle",
            "[from] ability: Imposter",
        ]

        if self.battle.user.active.ability == self.battle.opponent.active.ability:
            self.fail("Abilities were equal before transform")

        transform(self.battle, split_msg)

        self.assertEqual(self.user_active_ability, self.battle.opponent.active.ability)

    def test_transform_sets_moves_to_opposing_pokemons_moves(self):
        self.battle.user.active.moves = [
            Move("dracometeor"),
            Move("darkpulse"),
            Move("flashcannon"),
            Move("fireblast"),
        ]
        split_msg = [
            "",
            "-transform",
            "p2a: Ditto",
            "p1a: Weedle",
            "[from] ability: Imposter",
        ]

        if self.battle.user.active.moves == self.battle.opponent.active.moves:
            self.fail("Moves were equal before transform")

        transform(self.battle, split_msg)

        self.assertEqual(
            self.battle.user.active.moves, self.battle.opponent.active.moves
        )

    def test_transform_sets_types_to_opposing_pokemons_types(self):
        self.battle.user.active.types = ["flying", "dragon"]
        self.battle.opponent.active.types = ["normal"]
        split_msg = [
            "",
            "-transform",
            "p2a: Ditto",
            "p1a: Weedle",
            "[from] ability: Imposter",
        ]

        transform(self.battle, split_msg)

        self.assertEqual(
            self.battle.user.active.types, self.battle.opponent.active.types
        )

    def test_transform_sets_boosts_to_opposing_pokemons_boosts(self):
        self.battle.user.active.boosts = defaultdict(
            lambda: 0,
            {
                constants.ATTACK: 1,
                constants.DEFENSE: 2,
                constants.SPECIAL_ATTACK: 3,
                constants.SPECIAL_DEFENSE: 4,
                constants.SPEED: 5,
            },
        )
        self.battle.opponent.active.boosts = {}

        split_msg = [
            "",
            "-transform",
            "p2a: Ditto",
            "p1a: Weedle",
            "[from] ability: Imposter",
        ]

        transform(self.battle, split_msg)

        self.assertEqual(
            self.battle.user.active.boosts, self.battle.opponent.active.boosts
        )

    def test_transform_sets_transform_volatile_status(self):
        self.battle.user.active.volatile_statuses = []
        split_msg = [
            "",
            "-transform",
            "p2a: Ditto",
            "p1a: Weedle",
            "[from] ability: Imposter",
        ]

        transform(self.battle, split_msg)

        self.assertIn(
            constants.TRANSFORM, self.battle.opponent.active.volatile_statuses
        )


class TestCant(unittest.TestCase):
    def setUp(self):
        self.battle = Battle(None)
        self.battle.user.name = "p1"
        self.battle.opponent.name = "p2"

        self.opponent_active = Pokemon("caterpie", 100)
        self.battle.opponent.active = self.opponent_active

        self.user_active = Pokemon("weedle", 100)
        self.battle.user.active = self.user_active

    def test_increments_sleep_turns_when_cant_from_sleep(self):
        self.battle.user.active.sleep_turns = 0
        self.battle.user.active.status = constants.SLEEP
        cant(self.battle, ["", "-cant", "p1a: Weedle", "slp"])
        self.assertEqual(1, self.battle.user.active.sleep_turns)

    def test_removes_truant_when_cant_from_truant(self):
        self.battle.user.active.sleep_turns = 0
        self.battle.user.active.volatile_statuses.append("truant")
        cant(self.battle, ["", "-cant", "p1a: Slaking", "ability: Truant"])
        self.assertNotIn("truant", self.battle.user.active.volatile_statuses)

    def test_removes_mustrecharge_when_cant_from_recharge(self):
        self.battle.user.active.sleep_turns = 0
        self.battle.user.active.volatile_statuses.append("mustrecharge")
        cant(self.battle, ["", "-cant", "p1a: Slaking", "recharge"])
        self.assertNotIn("mustrecharge", self.battle.user.active.volatile_statuses)

    def test_only_decrements_rest_turns_when_cant_from_sleep_with_a_rest_turn(self):
        self.battle.user.active.sleep_turns = 0
        self.battle.user.active.rest_turns = 3
        self.battle.user.active.status = constants.SLEEP
        cant(self.battle, ["", "-cant", "p1a: Weedle", "slp"])
        self.assertEqual(0, self.battle.user.active.sleep_turns)
        self.assertEqual(2, self.battle.user.active.rest_turns)


class TestUpkeep(unittest.TestCase):
    def setUp(self):
        self.battle = Battle(None)
        self.battle.user.name = "p1"
        self.battle.opponent.name = "p2"

        self.opponent_active = Pokemon("caterpie", 100)
        self.battle.opponent.active = self.opponent_active

        self.user_active = Pokemon("weedle", 100)
        self.battle.user.active = self.user_active

    def test_resets_sleep_turns_to_zero_after_not_using_sleeptalk(self):
        self.battle.generation = "gen3"
        self.battle.user.active.status = constants.SLEEP
        self.battle.user.active.gen_3_consecutive_sleep_talks = 1

        cant(self.battle, ["", "-cant", "p1a: Weedle", "slp"])
        upkeep(self.battle, "")

        self.assertEqual(0, self.battle.user.active.gen_3_consecutive_sleep_talks)

    def test_does_not_reset_sleep_turns_when_sleeptalk_used(self):
        self.battle.generation = "gen3"
        self.battle.user.active.status = constants.SLEEP
        self.battle.user.active.gen_3_consecutive_sleep_talks = 1

        cant(self.battle, ["", "-cant", "p1a: Weedle", "slp"])
        move(self.battle, ["", "move", "p1a: Weedle", "Sleeptalk"])
        move(self.battle, ["", "move", "p1a: Weedle", "Tackle", "[from]Sleep Talk"])
        upkeep(self.battle, "")

        self.assertEqual(2, self.battle.user.active.gen_3_consecutive_sleep_talks)
        self.assertEqual("sleeptalk", self.battle.user.last_used_move.move)

    def test_swaps_out_yawn_for_yawnSleepThisTurn(self):
        self.battle.user.active.volatile_statuses.append(constants.YAWN_SLEEP_THIS_TURN)
        upkeep(self.battle, "")
        self.assertNotIn(
            constants.YAWN_SLEEP_THIS_TURN, self.battle.user.active.volatile_statuses
        )

    def test_decrements_trickroom_in_upkeep(self):
        self.battle.trick_room = True
        self.battle.trick_room_turns_remaining = 5
        upkeep(self.battle, "")
        self.assertEqual(4, self.battle.trick_room_turns_remaining)

    def test_swaps_out_yawn_for_yawnSleepThisTurn_opponent(self):
        self.battle.opponent.active.volatile_statuses.append(
            constants.YAWN_SLEEP_THIS_TURN
        )
        upkeep(self.battle, "")
        self.assertNotIn(
            constants.YAWN_SLEEP_THIS_TURN,
            self.battle.opponent.active.volatile_statuses,
        )

    def test_removes_yawnSleepNextTurn(self):
        self.battle.user.active.volatile_statuses.append(constants.YAWN)
        upkeep(self.battle, "")
        self.assertIn(
            constants.YAWN_SLEEP_THIS_TURN, self.battle.user.active.volatile_statuses
        )
        self.assertNotIn(constants.YAWN, self.battle.user.active.volatile_statuses)

    def test_reduces_protect_for_bot(self):
        self.battle.user.side_conditions[constants.PROTECT] = 1

        upkeep(self.battle, "")

        self.assertEqual(self.battle.user.side_conditions[constants.PROTECT], 0)

    def test_does_not_reduce_protect_when_it_is_0(self):
        self.battle.user.side_conditions[constants.PROTECT] = 0

        upkeep(self.battle, "")

        self.assertEqual(self.battle.user.side_conditions[constants.PROTECT], 0)

    def test_reduces_wish_if_it_is_larger_than_0_for_the_opponent(self):
        self.battle.opponent.wish = (2, 100)

        upkeep(self.battle, "")

        self.assertEqual(self.battle.opponent.wish, (1, 100))

    def test_reduces_wish_if_it_is_larger_than_0_for_the_bot(self):
        self.battle.user.wish = (2, 100)

        upkeep(self.battle, "")

        self.assertEqual(self.battle.user.wish, (1, 100))

    def test_does_not_reduce_wish_if_it_is_0(self):
        self.battle.user.wish = (0, 100)

        upkeep(self.battle, "")

        self.assertEqual(self.battle.user.wish, (0, 100))

    def test_reduces_future_sight_if_it_is_larger_than_0_for_the_bot(self):
        self.battle.user.future_sight = (2, "pokemon_name")

        upkeep(self.battle, "")

        self.assertEqual(self.battle.user.future_sight, (1, "pokemon_name"))

    def test_does_not_reduce_future_sight_if_it_is_0(self):
        self.battle.user.future_sight = (0, "pokemon_name")

        upkeep(self.battle, "")

        self.assertEqual(self.battle.user.future_sight, (0, "pokemon_name"))

    def test_adds_leftovers_blacksludge_to_impossible_items_at_end_of_turn(self):
        self.battle.opponent.active.hp = 50
        upkeep(self.battle, "")
        self.assertIn(constants.LEFTOVERS, self.battle.opponent.active.impossible_items)
        self.assertIn(
            constants.BLACK_SLUDGE, self.battle.opponent.active.impossible_items
        )

    def test_adds_flameorb_toxicorb_if_status_is_none_at_end_of_turn(self):
        self.battle.opponent.active.status = None
        upkeep(self.battle, "")
        self.assertIn("flameorb", self.battle.opponent.active.impossible_items)
        self.assertIn("toxicorb", self.battle.opponent.active.impossible_items)

    def test_does_not_add_flameorb_toxicorb_if_status_exists_at_end_of_turn(self):
        self.battle.opponent.active.status = constants.FROZEN
        upkeep(self.battle, "")
        self.assertNotIn("flameorb", self.battle.opponent.active.impossible_items)
        self.assertNotIn("toxicorb", self.battle.opponent.active.impossible_items)


class TestCheckSpeedRanges(unittest.TestCase):
    def setUp(self):
        self.battle = Battle(None)
        self.battle.user.name = "p1"
        self.battle.opponent.name = "p2"

        self.opponent_active = Pokemon("caterpie", 100)
        self.battle.opponent.active = self.opponent_active
        self.battle.opponent.active.ability = None

        self.user_active = Pokemon("caterpie", 100)
        self.battle.user.active = self.user_active

        self.username = "CoolUsername"

        self.battle.username = self.username

        self.battle.request_json = {
            constants.ACTIVE: [{constants.MOVES: []}],
            constants.SIDE: {
                constants.ID: None,
                constants.NAME: None,
                constants.POKEMON: [],
                constants.RQID: None,
            },
        }

    def test_sets_minspeed_when_opponent_goes_first(self):
        # opponent should have min speed equal to the bot's speed
        self.battle.user.active.stats[constants.SPEED] = 150

        messages = [
            "|move|p2a: Caterpie|Stealth Rock|",
            "|move|p1a: Caterpie|Stealth Rock|",
        ]

        check_speed_ranges(self.battle, messages)

        self.assertEqual(
            self.battle.user.active.stats[constants.SPEED],
            self.battle.opponent.active.speed_range.min,
        )

    def test_sets_maxspeed_when_opponent_goes_first_in_trickroom(self):
        # opponent should have min speed equal to the bot's speed
        self.battle.user.active.stats[constants.SPEED] = 150
        self.battle.trick_room = True

        messages = [
            "|move|p2a: Caterpie|Stealth Rock|",
            "|move|p1a: Caterpie|Stealth Rock|",
        ]

        check_speed_ranges(self.battle, messages)

        self.assertEqual(
            self.battle.user.active.stats[constants.SPEED],
            self.battle.opponent.active.speed_range.max,
        )

    def test_nothing_happens_with_priority_move_in_trickroom(self):
        # opponent should have min speed equal to the bot's speed
        self.battle.user.active.stats[constants.SPEED] = 150
        self.battle.trick_room = True

        messages = [
            "|move|p2a: Caterpie|Aqua Jet|",
            "|move|p1a: Caterpie|Stealth Rock|",
        ]

        check_speed_ranges(self.battle, messages)

        self.assertEqual(float("inf"), self.battle.opponent.active.speed_range.max)
        self.assertEqual(0, self.battle.opponent.active.speed_range.min)

    def test_accounts_for_paralysis_when_calculating_speed_range(self):
        # opponent should have min speed equal to the bot's speed
        self.battle.user.active.stats[constants.SPEED] = 150
        self.battle.opponent.active.status = constants.PARALYZED

        messages = [
            "|move|p2a: Caterpie|Stealth Rock|",
            "|move|p1a: Caterpie|Stealth Rock|",
        ]

        check_speed_ranges(self.battle, messages)

        # bot_speed * 2 should be the minspeed it has b/c it went first with paralysis
        expected_min_speed = int(self.battle.user.active.stats[constants.SPEED] * 2)

        self.assertEqual(
            expected_min_speed, self.battle.opponent.active.speed_range.min
        )

    def test_accounts_for_paralysis_on_bots_side_when_calculating_speed_range(self):
        # opponent should have min speed equal to the bot's speed
        self.battle.user.active.stats[constants.SPEED] = 150
        self.battle.user.active.status = constants.PARALYZED

        messages = [
            "|move|p2a: Caterpie|Stealth Rock|",
            "|move|p1a: Caterpie|Stealth Rock|",
        ]

        check_speed_ranges(self.battle, messages)

        # bot_speed / 2 should be the minspeed it has b/c it went first with paralysis
        expected_min_speed = int(self.battle.user.active.stats[constants.SPEED] / 2)

        self.assertEqual(
            expected_min_speed, self.battle.opponent.active.speed_range.min
        )

    def test_accounts_for_tailwind_on_opponent_side_when_calculating_speed_ranges(self):
        # opponent should have min speed equal to the bot's speed
        self.battle.user.active.stats[constants.SPEED] = 300
        self.battle.opponent.side_conditions[constants.TAILWIND] = 1

        messages = [
            "|move|p2a: Caterpie|Stealth Rock|",
            "|move|p1a: Caterpie|Stealth Rock|",
        ]

        check_speed_ranges(self.battle, messages)

        # bot_speed / 2 should be the minspeed it has b/c it went first with tailwind up
        expected_min_speed = int(self.battle.user.active.stats[constants.SPEED] / 2)

        self.assertEqual(
            expected_min_speed, self.battle.opponent.active.speed_range.min
        )

    def test_accounts_for_tailwind_on_bot_side_when_calculating_speed_ranges(self):
        # opponent should have min speed equal to the bot's speed
        self.battle.user.active.stats[constants.SPEED] = 300
        self.battle.user.side_conditions[constants.TAILWIND] = 1

        messages = [
            "|move|p2a: Caterpie|Stealth Rock|",
            "|move|p1a: Caterpie|Stealth Rock|",
        ]

        check_speed_ranges(self.battle, messages)

        # bot_speed * 2 should be the minspeed it has b/c it went first with tailwind up
        expected_min_speed = int(self.battle.user.active.stats[constants.SPEED] * 2)

        self.assertEqual(
            expected_min_speed, self.battle.opponent.active.speed_range.min
        )

    def test_accounts_for_tailwind_on_both_side_when_calculating_speed_ranges(self):
        # opponent should have min speed equal to the bot's speed
        self.battle.user.active.stats[constants.SPEED] = 300
        self.battle.user.side_conditions[constants.TAILWIND] = 1
        self.battle.opponent.side_conditions[constants.TAILWIND] = 1

        messages = [
            "|move|p2a: Caterpie|Stealth Rock|",
            "|move|p1a: Caterpie|Stealth Rock|",
        ]

        check_speed_ranges(self.battle, messages)

        # bot_speed / 2 should be the minspeed it has b/c it went first with tailwind up
        expected_min_speed = int(self.battle.user.active.stats[constants.SPEED] / 2)

        # bot_speed * 2 should be the minspeed it has b/c it went first with tailwind up
        expected_min_speed = int(expected_min_speed * 2)

        self.assertEqual(
            expected_min_speed, self.battle.opponent.active.speed_range.min
        )

    def test_does_not_set_minspeed_when_opponent_could_have_unburden_activated(self):
        # opponent should have min speed equal to the bot's speed
        self.battle.user.active.stats[constants.SPEED] = 150
        self.battle.opponent.active.item = None
        self.battle.opponent.active.name = "hawlucha"  # can possibly have unburden

        messages = [
            "|move|p2a: Caterpie|Stealth Rock|",
            "|move|p1a: Caterpie|Stealth Rock|",
        ]

        check_speed_ranges(self.battle, messages)

        self.assertEqual(0, self.battle.opponent.active.speed_range.min)

    def test_sets_maxspeed_when_bot_goes_first(self):
        # opponent should have max speed equal to the bot's speed
        self.battle.user.active.stats[constants.SPEED] = 150

        messages = [
            "|move|p1a: Caterpie|Stealth Rock|",
            "|move|p2a: Caterpie|Stealth Rock|",
        ]

        check_speed_ranges(self.battle, messages)

        self.assertEqual(
            self.battle.user.active.stats[constants.SPEED],
            self.battle.opponent.active.speed_range.max,
        )

    def test_minspeed_is_not_set_when_rain_is_up_and_opponent_can_have_swiftswim(self):
        # opponent should have max speed equal to the bot's speed
        self.battle.user.active.stats[constants.SPEED] = 150
        self.battle.weather = constants.RAIN
        self.battle.opponent.active.name = "seismitoad"

        messages = [
            "|move|p2a: Caterpie|Stealth Rock|",
            "|move|p1a: Caterpie|Stealth Rock|",
        ]

        check_speed_ranges(self.battle, messages)

        self.assertEqual(0, self.battle.opponent.active.speed_range.min)

    def test_minspeed_is_set_when_only_rain_is_up(self):
        # opponent should have max speed equal to the bot's speed
        self.battle.user.active.stats[constants.SPEED] = 150
        self.battle.weather = constants.RAIN

        messages = [
            "|move|p2a: Caterpie|Stealth Rock|",
            "|move|p1a: Caterpie|Stealth Rock|",
        ]

        check_speed_ranges(self.battle, messages)

        self.assertEqual(
            self.battle.user.active.stats[constants.SPEED],
            self.battle.opponent.active.speed_range.min,
        )

    def test_minspeed_is_set_when_rain_is_not_up_but_opponent_could_have_swiftswim(
        self,
    ):
        # opponent should have max speed equal to the bot's speed
        self.battle.user.active.stats[constants.SPEED] = 150
        self.battle.opponent.active.name = "seismitoad"

        messages = [
            "|move|p2a: Caterpie|Stealth Rock|",
            "|move|p1a: Caterpie|Stealth Rock|",
        ]

        check_speed_ranges(self.battle, messages)

        self.assertEqual(
            self.battle.user.active.stats[constants.SPEED],
            self.battle.opponent.active.speed_range.min,
        )

    def test_minspeed_is_not_set_when_opponent_has_choicescarf(self):
        # opponent should have max speed equal to the bot's speed
        self.battle.user.active.stats[constants.SPEED] = 150
        self.battle.opponent.active.item = "choicescarf"

        messages = [
            "|move|p2a: Caterpie|Stealth Rock|",
            "|move|p1a: Caterpie|Stealth Rock|",
        ]

        check_speed_ranges(self.battle, messages)

        self.assertEqual(0, self.battle.opponent.active.speed_range.min)

    def test_minspeed_is_correctly_set_when_bot_has_choicescarf(self):
        # opponent should have max speed equal to the bot's speed
        self.battle.user.active.stats[constants.SPEED] = 150
        self.battle.user.active.item = "choicescarf"

        messages = [
            "|move|p1a: Caterpie|Stealth Rock|",
            "|move|p2a: Caterpie|Stealth Rock|",
        ]

        check_speed_ranges(self.battle, messages)

        self.assertEqual(
            self.battle.user.active.stats[constants.SPEED] * 1.5,
            self.battle.opponent.active.speed_range.max,
        )

    def test_minspeed_is_correctly_set_when_bot_has_choicescarf_and_opponent_is_boosted(
        self,
    ):
        # opponent should have max speed equal to the bot's speed
        self.battle.user.active.stats[constants.SPEED] = 317
        self.battle.opponent.active.stats[constants.SPEED] = 383
        self.battle.user.active.item = "choicescarf"
        self.battle.opponent.active.boosts[constants.SPEED] = 1

        messages = [
            "|move|p2a: Caterpie|Stealth Rock|",
            "|move|p1a: Caterpie|Stealth Rock|",
        ]

        check_speed_ranges(self.battle, messages)

        # this is meant to show the rounding inherent with way pokemon floors values
        # floor(317 / 1.5) = 211
        # floor(211*1.5) = 316
        expected_speed = int(self.battle.user.active.stats[constants.SPEED] / 1.5)
        expected_speed = int(expected_speed * 1.5)

        self.assertEqual(expected_speed, self.battle.opponent.active.speed_range.min)

    def test_minspeed_interaction_with_boosted_speed(self):
        # opponent should have max speed equal to the bot's speed
        self.battle.user.active.stats[constants.SPEED] = 150
        self.battle.opponent.active.boosts[constants.SPEED] = 1

        messages = [
            "|move|p2a: Caterpie|Stealth Rock|",
            "|move|p1a: Caterpie|Stealth Rock|",
        ]

        check_speed_ranges(self.battle, messages)

        # the minspeed should take into account the fact that the opponent has a boost
        # therefore, the minimum (unboosted) speed must be divided by the boost multiplier
        expected_min_speed = int(
            150
            / boost_multiplier_lookup[
                self.battle.opponent.active.boosts[constants.SPEED]
            ]
        )

        self.assertEqual(
            expected_min_speed, self.battle.opponent.active.speed_range.min
        )

    def test_minspeed_interaction_with_bots_boosted_speed(self):
        # opponent should have max speed equal to the bot's speed
        self.battle.user.active.stats[constants.SPEED] = 150
        self.battle.user.active.boosts[constants.SPEED] = 1

        messages = [
            "|move|p2a: Caterpie|Stealth Rock|",
            "|move|p1a: Caterpie|Stealth Rock|",
        ]

        check_speed_ranges(self.battle, messages)

        # the minspeed should take into account the fact that the opponent has a boost
        # therefore, the minimum (unboosted) speed must be divided by the boost multiplier
        expected_min_speed = int(
            150
            * boost_multiplier_lookup[self.battle.user.active.boosts[constants.SPEED]]
            / boost_multiplier_lookup[
                self.battle.opponent.active.boosts[constants.SPEED]
            ]
        )

        self.assertEqual(
            expected_min_speed, self.battle.opponent.active.speed_range.min
        )

    def test_minspeed_interaction_with_bot_and_opponents_boosted_speed(self):
        # opponent should have max speed equal to the bot's speed
        self.battle.user.active.stats[constants.SPEED] = 150
        self.battle.user.active.boosts[constants.SPEED] = 1
        self.battle.opponent.active.boosts[constants.SPEED] = 3

        messages = [
            "|move|p2a: Caterpie|Stealth Rock|",
            "|move|p1a: Caterpie|Stealth Rock|",
        ]

        check_speed_ranges(self.battle, messages)

        # the minspeed should take into account the fact that the opponent has a boost
        # therefore, the minimum (unboosted) speed must be divided by the boost multiplier
        expected_min_speed = int(
            150
            * boost_multiplier_lookup[self.battle.user.active.boosts[constants.SPEED]]
            / boost_multiplier_lookup[
                self.battle.opponent.active.boosts[constants.SPEED]
            ]
        )

        self.assertEqual(
            expected_min_speed, self.battle.opponent.active.speed_range.min
        )

    def test_opponents_unknown_move_is_used_as_a_zero_priority_move(self):
        # opponent should have max speed equal to the bot's speed
        self.battle.user.active.stats[constants.SPEED] = 150

        messages = [
            "|move|p2a: Caterpie|unknown-move|",
            "|move|p1a: Caterpie|unknown-move|",
        ]

        check_speed_ranges(self.battle, messages)

        self.assertEqual(150, self.battle.opponent.active.speed_range.min)

    def test_bots_unknown_move_is_used_as_a_zero_priority_move(self):
        # opponent should have max speed equal to the bot's speed
        self.battle.user.active.stats[constants.SPEED] = 150

        messages = [
            "|move|p1a: Caterpie|unknown-move|",
            "|move|p2a: Caterpie|unknown-move|",
        ]

        check_speed_ranges(self.battle, messages)

        self.assertEqual(150, self.battle.opponent.active.speed_range.max)

    def test_opponent_has_unknown_choicescarf_causing_it_to_be_faster(self):
        # Situation:
        #   The opponent's pokemon has a choice scarf but the bot doesn't know that - it only sees it's item as unknown
        #   The choicescarf causes the opponent to go first, when it wouldn't have gone first normally
        #   If the opponent didn't have a choicescarf it COULD still be naturally faster than the bot's pokemon
        #   This means the check_choicescarf function won't assign a choicescarf
        # Expected Result:
        #   min_speed should be set to the bot's speed. The set inferral DOES take into account items when validating
        #   the final speed

        # opponent should have max speed equal to the bot's speed
        self.battle.user.active.stats[constants.SPEED] = 150

        messages = [
            "|move|p2a: Caterpie|Stealth Rock|",
            "|move|p1a: Caterpie|Stealth Rock|",
        ]

        check_speed_ranges(self.battle, messages)
        expected_min_speed = 150
        self.assertEqual(
            expected_min_speed, self.battle.opponent.active.speed_range.min
        )

    def test_opponent_using_grassyglide_in_grassy_terrain_does_not_cause_minspeed_to_be_set(
        self,
    ):
        self.battle.user.active.stats[constants.SPEED] = 150
        self.battle.field = constants.GRASSY_TERRAIN

        messages = [
            "|move|p2a: Caterpie|Grassy Glide|",
            "|move|p1a: Caterpie|Stealth Rock|",
        ]

        check_speed_ranges(self.battle, messages)
        self.assertEqual(0, self.battle.opponent.active.speed_range.min)

    def test_bot_using_grassyglide_in_grassy_terrain_does_not_cause_maxspeed_to_be_set(
        self,
    ):
        self.battle.user.active.stats[constants.SPEED] = 150
        self.battle.field = constants.GRASSY_TERRAIN

        messages = [
            "|move|p1a: Caterpie|Grassy Glide|",
            "|move|p2a: Caterpie|Stealth Rock|",
        ]

        check_speed_ranges(self.battle, messages)
        self.assertEqual(float("inf"), self.battle.opponent.active.speed_range.max)

    def test_move_from_magicbounce_after_switching_does_not_set_speed_range(self):
        user_reserve_weedle = Pokemon("Weedle", 100)
        self.battle.user.reserve = [user_reserve_weedle]

        messages = [
            "|switch|p1a: Caterpie|Caterpie, F|255/255",
            "|move|p2a: Caterpie|Stealth Rock|",
            "|move|p1a: Caterpie|Stealth Rock|p2a: Caterpie|[from]ability: Magic Bounce",
        ]

        check_speed_ranges(self.battle, messages)

        # speed ranges should be unchanged because this was a switch-in
        self.assertEqual(float("inf"), self.battle.opponent.active.speed_range.max)
        self.assertEqual(0, self.battle.opponent.active.speed_range.min)


class TestGuessChoiceScarf(unittest.TestCase):
    def setUp(self):
        self.battle = Battle(None)
        self.battle.user.name = "p1"
        self.battle.opponent.name = "p2"

        self.opponent_active = Pokemon("caterpie", 100)
        self.battle.opponent.active = self.opponent_active
        self.battle.opponent.active.ability = None

        self.user_active = Pokemon("caterpie", 100)
        self.battle.user.active = self.user_active

        self.username = "CoolUsername"

        self.battle.username = self.username

        self.battle.request_json = {
            constants.ACTIVE: [{constants.MOVES: []}],
            constants.SIDE: {
                constants.ID: None,
                constants.NAME: None,
                constants.POKEMON: [],
                constants.RQID: None,
            },
        }

    def test_guesses_choicescarf_when_opponent_should_always_be_slower(self):
        self.battle.user.active.stats[constants.SPEED] = (
            210  # opponent's speed should not be greater than 207 (max speed caterpie)
        )

        messages = [
            "|move|p2a: Caterpie|Stealth Rock|",
            "|move|p1a: Caterpie|Stealth Rock|",
        ]

        check_choicescarf(self.battle, messages)

        self.assertEqual("choicescarf", self.battle.opponent.active.item)

    def test_guesses_choicescarf_when_enemy_knocks_out_user(self):
        self.battle.user.active.stats[constants.SPEED] = (
            210  # opponent's speed should not be greater than 207 (max speed caterpie)
        )
        self.battle.user.last_selected_move = LastUsedMove("caterpie", "tackle", 0)
        messages = [
            "|move|p2a: Caterpie|Tackle| p1a: Caterpie",
            "|-damage|p1a: Caterpie|0 fnt",
            "|faint|p1a: Forretress",
        ]

        check_choicescarf(self.battle, messages)

        self.assertEqual("choicescarf", self.battle.opponent.active.item)

    def test_does_not_guess_choicescarf_when_user_hits_self_in_confusion(self):
        self.battle.user.active.stats[constants.SPEED] = (
            210  # opponent's speed should not be greater than 207 (max speed caterpie)
        )
        self.battle.user.last_selected_move = LastUsedMove("caterpie", "tackle", 0)
        messages = [
            "|-activate|p1a: Caterpie|confusion",
            "|move|p2a: Caterpie|Tackle| p1a: Caterpie",
            "|-damage|p1a: Caterpie|0 fnt",
            "|faint|p1a: Forretress",
        ]

        check_choicescarf(self.battle, messages)

        self.assertEqual(constants.UNKNOWN_ITEM, self.battle.opponent.active.item)

    def test_does_not_guess_choicescarf_when_opponent_knocks_out_user_with_priority_move(
        self,
    ):
        self.battle.user.active.stats[constants.SPEED] = (
            210  # opponent's speed should not be greater than 207 (max speed caterpie)
        )
        self.battle.user.last_selected_move = LastUsedMove("caterpie", "tackle", 0)
        messages = [
            "|move|p2a: Caterpie|Quick Attack| p1a: Caterpie",
            "|-damage|p1a: Caterpie|0 fnt",
            "|faint|p1a: Caterpie",
        ]

        check_choicescarf(self.battle, messages)

        self.assertEqual(constants.UNKNOWN_ITEM, self.battle.opponent.active.item)

    def test_does_not_guess_choicescarf_when_user_recharged(
        self,
    ):
        self.battle.user.active.stats[constants.SPEED] = (
            210  # opponent's speed should not be greater than 207 (max speed caterpie)
        )
        messages = [
            "|cant|p1a: Caterpie|recharge",
            "|move|p2a: Caterpie|Tackle| p1a: Caterpie",
            "|-damage|p1a: Caterpie|0 fnt",
            "|faint|p1a: Caterpie",
        ]

        check_choicescarf(self.battle, messages)

        self.assertEqual(constants.UNKNOWN_ITEM, self.battle.opponent.active.item)

    def test_does_not_guess_choicescarf_when_opponent_could_have_prankster(self):
        self.battle.opponent.active.name = "grimmsnarl"  # grimmsnarl could have prankster - it's non-damaging moves get +1 priority
        self.battle.user.active.stats[constants.SPEED] = (
            245  # opponent's speed should not be greater than 240 (max speed grimmsnarl)
        )

        messages = [
            "|move|p2a: Grimmsnarl|Stealth Rock|",
            "|move|p1a: Caterpie|Stealth Rock|",
        ]

        check_choicescarf(self.battle, messages)

        self.assertEqual(constants.UNKNOWN_ITEM, self.battle.opponent.active.item)

    def test_does_not_guess_choicescarf_when_opponent_is_speed_boosted(self):
        self.battle.user.active.stats[constants.SPEED] = (
            210  # opponent's speed should not be greater than 207 (max speed caterpie)
        )
        self.battle.opponent.active.boosts[constants.SPEED] = 1

        messages = [
            "|move|p2a: Caterpie|Stealth Rock|",
            "|move|p1a: Caterpie|Stealth Rock|",
        ]

        check_choicescarf(self.battle, messages)

        self.assertEqual(constants.UNKNOWN_ITEM, self.battle.opponent.active.item)

    def test_does_not_guess_choicescarf_when_opponent_uses_grassyglide_in_grassy_terrain(
        self,
    ):
        self.battle.user.active.stats[constants.SPEED] = (
            210  # opponent's speed should not be greater than 207 (max speed caterpie)
        )
        self.battle.field = constants.GRASSY_TERRAIN

        messages = [
            "|move|p2a: Caterpie|Grassy Glide|",
            "|move|p1a: Caterpie|Stealth Rock|",
        ]

        check_choicescarf(self.battle, messages)

        self.assertEqual(constants.UNKNOWN_ITEM, self.battle.opponent.active.item)

    def test_does_not_guess_choicescarf_when_bot_is_speed_unboosted(self):
        self.battle.user.active.stats[constants.SPEED] = (
            210  # opponent's speed should not be greater than 207 (max speed caterpie)
        )
        self.battle.user.active.boosts[constants.SPEED] = -1

        messages = [
            "|move|p2a: Caterpie|Stealth Rock|",
            "|move|p1a: Caterpie|Stealth Rock|",
        ]

        check_choicescarf(self.battle, messages)

        self.assertEqual(constants.UNKNOWN_ITEM, self.battle.opponent.active.item)

    def test_does_not_guess_scarf_in_trickroom(self):
        self.battle.trick_room = True
        self.battle.user.active.stats[constants.SPEED] = (
            210  # opponent's speed should not be greater than 207 (max speed caterpie)
        )

        messages = [
            "|move|p2a: Caterpie|Stealth Rock|",
            "|move|p1a: Caterpie|Stealth Rock|",
        ]

        check_choicescarf(self.battle, messages)

        self.assertEqual(constants.UNKNOWN_ITEM, self.battle.opponent.active.item)

    def test_does_not_guess_scarf_under_trickroom_when_opponent_could_be_slower(self):
        self.battle.trick_room = True
        self.battle.user.active.stats[constants.SPEED] = (
            205  # opponent caterpie speed is 113 - 207
        )

        messages = [
            "|move|p2a: Caterpie|Stealth Rock|",
            "|move|p1a: Caterpie|Stealth Rock|",
        ]

        check_choicescarf(self.battle, messages)

        self.assertEqual(constants.UNKNOWN_ITEM, self.battle.opponent.active.item)

    def test_guesses_scarf_in_trickroom_when_opponent_cannot_be_slower(self):
        self.battle.trick_room = True
        self.battle.user.active.stats[constants.SPEED] = (
            110  # opponent caterpie speed is 113 - 207
        )

        messages = [
            "|move|p2a: Caterpie|Stealth Rock|",
            "|move|p1a: Caterpie|Stealth Rock|",
        ]

        check_choicescarf(self.battle, messages)

        self.assertEqual("choicescarf", self.battle.opponent.active.item)

    def test_unknown_moves_defaults_to_0_priority(self):
        self.battle.user.active.stats[constants.SPEED] = (
            210  # opponent's speed should not be greater than 207 (max speed caterpie)
        )

        messages = [
            "|move|p2a: Caterpie|unknown-move|",
            "|move|p1a: Caterpie|unknown-move|",
        ]

        check_choicescarf(self.battle, messages)

        self.assertEqual("choicescarf", self.battle.opponent.active.item)

    def test_priority_move_with_unknown_move_does_not_cause_guess(self):
        self.battle.user.active.stats[constants.SPEED] = (
            210  # opponent's speed should not be greater than 207 (max speed caterpie)
        )

        messages = [
            "|move|p2a: Caterpie|Quick Attack|",
            "|move|p1a: Caterpie|unknown-move|",
        ]

        check_choicescarf(self.battle, messages)

        self.assertEqual(constants.UNKNOWN_ITEM, self.battle.opponent.active.item)

    def test_does_not_guess_item_when_bot_moves_first(self):
        self.battle.user.active.stats[constants.SPEED] = (
            210  # opponent's speed should not be greater than 207 (max speed caterpie)
        )

        messages = [
            "|move|p1a: Caterpie|Stealth Rock|",
            "|move|p2a: Caterpie|Stealth Rock|",
        ]

        check_choicescarf(self.battle, messages)

        self.assertEqual(constants.UNKNOWN_ITEM, self.battle.opponent.active.item)

    def test_does_not_guess_item_when_moves_are_different_priority(self):
        self.battle.user.active.stats[constants.SPEED] = (
            210  # opponent's speed should not be greater than 207 (max speed caterpie)
        )

        messages = [
            "|move|p2a: Caterpie|Quick Attack|",
            "|move|p1a: Caterpie|Stealth Rock|",
        ]

        check_choicescarf(self.battle, messages)

        self.assertEqual(constants.UNKNOWN_ITEM, self.battle.opponent.active.item)

    def test_does_not_guess_item_when_opponent_can_be_faster(self):
        self.battle.user.active.stats[constants.SPEED] = (
            200  # opponent's speed can be 207 (max speed caterpie)
        )

        messages = [
            "|move|p2a: Caterpie|Stealth Rock|",
            "|move|p1a: Caterpie|Stealth Rock|",
        ]

        check_choicescarf(self.battle, messages)

        self.assertEqual(constants.UNKNOWN_ITEM, self.battle.opponent.active.item)

    def test_swiftswim_causing_opponent_to_be_faster_results_in_not_guessing_choicescarf(
        self,
    ):
        self.battle.opponent.active.ability = "swiftswim"
        self.battle.weather = constants.RAIN
        self.battle.user.active.stats[constants.SPEED] = (
            300  # opponent's speed can be 414 (max speed caterpie plus swiftswim)
        )

        messages = [
            "|move|p2a: Caterpie|Stealth Rock|",
            "|move|p1a: Caterpie|Stealth Rock|",
        ]

        check_choicescarf(self.battle, messages)

        self.assertEqual(constants.UNKNOWN_ITEM, self.battle.opponent.active.item)

    def test_pokemon_possibly_having_swiftswim_in_rain_does_not_result_in_a_choicescarf_guess(
        self,
    ):
        self.battle.opponent.active.name = "seismitoad"  # can have swiftswim
        self.battle.weather = constants.RAIN
        self.battle.user.active.stats[constants.SPEED] = (
            210  # opponent's speed can be 414 (max speed caterpie plus swiftswim)
        )

        messages = [
            "|move|p2a: Caterpie|Stealth Rock|",
            "|move|p1a: Caterpie|Stealth Rock|",
        ]

        check_choicescarf(self.battle, messages)

        self.assertEqual(constants.UNKNOWN_ITEM, self.battle.opponent.active.item)

    def test_seismitoad_choicescarf_is_guessed_when_ability_has_been_revealed(self):
        self.battle.opponent.active.name = (
            "seismitoad"  # set ID so lookup says it has swiftswim
        )
        self.battle.opponent.active.ability = "waterabsorb"  # but ability has been revealed so if it is faster a choice item should be inferred
        self.battle.weather = constants.RAIN
        self.battle.user.active.stats[constants.SPEED] = (
            300  # opponent's speed can be 414 (max speed caterpie plus swiftswim). Yes it is still a caterpie
        )

        messages = [
            "|move|p2a: Caterpie|Stealth Rock|",
            "|move|p1a: Caterpie|Stealth Rock|",
        ]

        check_choicescarf(self.battle, messages)

        self.assertEqual("choicescarf", self.battle.opponent.active.item)

    def test_possible_surgesurfer_does_not_result_in_scarf_inferral(self):
        self.battle.opponent.active.name = (
            "raichualola"  # set ID so lookup says it has surgesurfer
        )
        self.battle.field = constants.ELECTRIC_TERRAIN
        self.battle.user.active.stats[constants.SPEED] = (
            300  # opponent's speed can be 414 (max speed caterpie plus swiftswim). Yes it is still a caterpie
        )

        messages = [
            "|move|p2a: Caterpie|Stealth Rock|",
            "|move|p1a: Caterpie|Stealth Rock|",
        ]

        check_choicescarf(self.battle, messages)

        self.assertEqual(constants.UNKNOWN_ITEM, self.battle.opponent.active.item)

    def test_surgesurfer_pokemon_choice_item_is_guessed_if_ability_is_revealed_to_be_otherwise(
        self,
    ):
        self.battle.opponent.active.name = (
            "raichualola"  # set ID so lookup says it has surgesurfer
        )
        self.battle.opponent.active.ability = "some_weird_ability"
        self.battle.field = constants.ELECTRIC_TERRAIN
        self.battle.user.active.stats[constants.SPEED] = (
            300  # opponent's speed can be 414 (max speed caterpie plus swiftswim). Yes it is still a caterpie
        )

        messages = [
            "|move|p2a: Caterpie|Stealth Rock|",
            "|move|p1a: Caterpie|Stealth Rock|",
        ]

        check_choicescarf(self.battle, messages)

        self.assertEqual("choicescarf", self.battle.opponent.active.item)

    def test_pokemon_with_possible_quickfeet_does_not_have_choice_scarf_inferred(self):
        self.battle.opponent.active.name = (
            "ursaring"  # set ID so lookup says it has quickfeet
        )
        self.battle.opponent.active.status = constants.PARALYZED
        self.battle.user.active.stats[constants.SPEED] = 210

        messages = [
            "|move|p2a: Caterpie|Stealth Rock|",
            "|move|p1a: Caterpie|Stealth Rock|",
        ]

        check_choicescarf(self.battle, messages)

        self.assertEqual(constants.UNKNOWN_ITEM, self.battle.opponent.active.item)

    def test_pokemon_with_possible_quickfeet_does_have_choice_scarf_inferred_if_ability_revealed_to_something_else(
        self,
    ):
        self.battle.opponent.active.name = (
            "ursaring"  # set ID so lookup says it has quickfeet
        )
        self.battle.opponent.active.ability = (
            "some_other_ability"  # ability cant be quickfeet
        )
        self.battle.opponent.active.status = constants.PARALYZED
        self.battle.user.active.stats[constants.SPEED] = 210

        messages = [
            "|move|p2a: Caterpie|Stealth Rock|",
            "|move|p1a: Caterpie|Stealth Rock|",
        ]

        check_choicescarf(self.battle, messages)

        self.assertEqual("choicescarf", self.battle.opponent.active.item)

    def test_does_not_guess_choicescarf_when_item_is_none(self):
        self.battle.opponent.active.item = None
        self.battle.user.active.stats[constants.SPEED] = (
            210  # opponent's speed should not be greater than 207 (max speed caterpie)
        )

        messages = [
            "|move|p2a: Caterpie|Stealth Rock|",
            "|move|p1a: Caterpie|Stealth Rock|",
        ]

        check_choicescarf(self.battle, messages)

        self.assertEqual(None, self.battle.opponent.active.item)

    def test_does_not_guess_choicescarf_when_item_is_known(self):
        self.battle.opponent.active.item = "leftovers"
        self.battle.user.active.stats[constants.SPEED] = (
            210  # opponent's speed should not be greater than 207 (max speed caterpie)
        )

        messages = [
            "|move|p2a: Caterpie|Stealth Rock|",
            "|move|p1a: Caterpie|Stealth Rock|",
        ]

        check_choicescarf(self.battle, messages)

        self.assertEqual("leftovers", self.battle.opponent.active.item)

    def test_uses_randombattle_spread_when_guessing_for_randombattle(self):
        self.battle.battle_type = constants.RANDOM_BATTLE

        # opponent's speed should be 193 WITHOUT a choicescarf
        # HOWEVER, max-speed should still outspeed this value
        self.battle.user.active.stats[constants.SPEED] = 195

        self.opponent_active = Pokemon(
            "floetteeternal", 80
        )  # randombattle level for Floette-E
        self.battle.opponent.active = self.opponent_active

        messages = [
            "|move|p2a: Floette-Eternal|Stealth Rock|",
            "|move|p1a: Caterpie|Stealth Rock|",
        ]

        check_choicescarf(self.battle, messages)

        self.assertEqual("choicescarf", self.battle.opponent.active.item)

    def test_choicescarf_is_not_checked_when_switching_happens(self):
        self.battle.user.active.stats[constants.SPEED] = 210
        user_reserve_weedle = Pokemon("Weedle", 100)
        user_reserve_weedle.stats[constants.SPEED] = 75
        self.battle.user.reserve = [user_reserve_weedle]

        messages = [
            "|switch|p1a: Caterpie|Caterpie, F|255/255",
            "|move|p2a: Caterpie|Stealth Rock|",
            "|move|p1a: Caterpie|Stealth Rock|p2a: Caterpie|[from]ability: Magic Bounce",
        ]

        check_choicescarf(self.battle, messages)

        self.assertEqual(constants.UNKNOWN_ITEM, self.battle.opponent.active.item)


class TestCheckHeavyDutyBoots(unittest.TestCase):
    def setUp(self):
        self.battle = Battle(None)
        self.battle.user.name = "p1"
        self.battle.opponent.name = "p2"

        self.opponent_active = Pokemon("caterpie", 100)
        self.battle.opponent.active = self.opponent_active
        self.battle.opponent.active.ability = None
        self.opponent_reserve_pkmn = Pokemon("weedle", 100)
        self.battle.opponent.reserve.append(self.opponent_reserve_pkmn)
        self.battle.opponent.active.item = constants.UNKNOWN_ITEM

        self.user_active = Pokemon("caterpie", 100)
        self.battle.user.active = self.user_active

        self.user_reserve_pkmn = Pokemon("weedle", 100)
        self.battle.user.reserve.append(self.user_reserve_pkmn)
        self.battle.user.active.item = constants.UNKNOWN_ITEM

        self.username = "CoolUsername"

        self.battle.username = self.username
        self.battle.generation = "gen9"

        self.battle.request_json = {
            constants.ACTIVE: [{constants.MOVES: []}],
            constants.SIDE: {
                constants.ID: None,
                constants.NAME: None,
                constants.POKEMON: [],
                constants.RQID: None,
            },
        }

    def test_basic_case_of_switching_in_and_not_taking_damage_sets_heavydutyboots(self):
        self.battle.opponent.side_conditions[constants.STEALTH_ROCK] = 1
        messages = [
            "|switch|p2a: Weedle|Weedle, M|100/100",
            "|move|p1a: Caterpie|Tackle",
            "|-damage|p2a: Weedle|90/100",
        ]

        update_battle(self.battle, "\n".join(messages))

        self.assertEqual("heavydutyboots", self.battle.opponent.active.item)

    def test_parser_deals_with_empty_line(self):
        self.battle.opponent.side_conditions[constants.STEALTH_ROCK] = 1
        messages = [
            "|switch|p2a: Weedle|Weedle, M|100/100",
            "|move|p1a: Caterpie|Tackle",
            "|-damage|p2a: Weedle|90/100",
            "",
        ]

        update_battle(self.battle, "\n".join(messages))

        self.assertEqual("heavydutyboots", self.battle.opponent.active.item)

    def test_parser_deals_with_empty_line_with_toxicspikes(self):
        self.battle.opponent.side_conditions[constants.TOXIC_SPIKES] = 1
        messages = [
            "|switch|p2a: Pikachu|Pikachu, M|100/100",
            "",
            "|move|p1a: Caterpie|Tackle",
            "|-damage|p2a: Pikachu|90/100",
            "",
        ]

        update_battle(self.battle, "\n".join(messages))

        self.assertEqual("heavydutyboots", self.battle.opponent.active.item)

    def test_having_an_item_bypasses_this_check(self):
        self.battle.opponent.side_conditions[constants.STEALTH_ROCK] = 1
        self.battle.opponent.active.item = None
        messages = [
            "|switch|p2a: Weedle|Weedle, M|100/100",
            "|move|p1a: Caterpie|Tackle",
            "|-damage|p2a: Weedle|90/100",
        ]

        check_heavydutyboots(self.battle, messages)

        self.assertEqual(None, self.battle.opponent.active.item)

    def test_double_switch_where_other_side_takes_damage_does_not_set_hdb_for_the_first_side(
        self,
    ):
        self.battle.opponent.side_conditions[constants.STEALTH_ROCK] = 1
        messages = [
            "|switch|p2a: Weedle|Weedle, M|100/100",
            "|switch|p1a: Weedle|Weedle, M|100/100",
            "|-damage|p1a: Weedle|88/100|[from] Stealth Rock",
        ]

        update_battle(self.battle, "\n".join(messages))

        self.assertEqual("heavydutyboots", self.battle.opponent.active.item)

    def test_basic_case_of_switching_in_and_taking_damage_does_not_set_heavydutyboots(
        self,
    ):
        self.battle.opponent.side_conditions[constants.STEALTH_ROCK] = 1
        messages = [
            "|switch|p2a: Weedle|Weedle, M|100/100",
            "|-damage|p2a: Weedle|88/100|[from] Stealth Rock"
            "|move|p1a: Caterpie|Tackle",
            "|-damage|p2a: Weedle|78/100",
        ]

        update_battle(self.battle, "\n".join(messages))

        self.assertEqual(constants.UNKNOWN_ITEM, self.battle.opponent.active.item)

    def test_basic_case_of_switching_in_and_taking_damage_sets_heavydutyboots_to_impossible(
        self,
    ):
        self.battle.opponent.side_conditions[constants.STEALTH_ROCK] = 1
        messages = [
            "|switch|p2a: Weedle|Weedle, M|100/100",
            "|-damage|p2a: Weedle|88/100|[from] Stealth Rock"
            "|move|p1a: Caterpie|Tackle",
            "|-damage|p2a: Weedle|78/100",
        ]

        update_battle(self.battle, "\n".join(messages))

        self.assertIn(
            constants.HEAVY_DUTY_BOOTS, self.battle.opponent.active.impossible_items
        )

    def test_not_taking_damage_from_spikes_sets_heavydutyboots(self):
        self.battle.opponent.side_conditions[constants.SPIKES] = 1
        messages = [
            "|switch|p2a: Weedle|Weedle, M|100/100",
            "|move|p1a: Caterpie|Tackle",
            "|-damage|p2a: Weedle|78/100",
        ]

        update_battle(self.battle, "\n".join(messages))

        self.assertEqual("heavydutyboots", self.battle.opponent.active.item)

    def test_taking_damage_from_spikes_does_not_set_heavydutyboots(self):
        self.battle.opponent.side_conditions[constants.SPIKES] = 1
        messages = [
            "|switch|p2a: Weedle|Weedle, M|100/100",
            "|-damage|p2a: Weedle|88/100|[from] Spikes" "|move|p1a: Caterpie|Tackle",
            "|-damage|p2a: Weedle|78/100",
        ]

        update_battle(self.battle, "\n".join(messages))

        self.assertEqual(constants.UNKNOWN_ITEM, self.battle.opponent.active.item)

    def test_taking_damage_from_spikes_sets_heavydutyboots_to_impossible(self):
        self.battle.opponent.side_conditions[constants.SPIKES] = 1
        messages = [
            "|switch|p2a: Weedle|Weedle, M|100/100",
            "|-damage|p2a: Weedle|88/100|[from] Spikes" "|move|p1a: Caterpie|Tackle",
            "|-damage|p2a: Weedle|78/100",
        ]

        update_battle(self.battle, "\n".join(messages))

        self.assertIn(
            constants.HEAVY_DUTY_BOOTS, self.battle.opponent.active.impossible_items
        )

    def test_not_getting_poisoned_by_toxicspikes_sets_heavydutyboots(self):
        self.battle.opponent.side_conditions[constants.TOXIC_SPIKES] = 1
        self.battle.opponent.active = Pokemon("pikachu", 100)
        messages = [
            "|switch|p2a: Pikachu|Pikachu, M|100/100",
            "|move|p1a: Caterpie|Tackle",
            "|-damage|p2a: Pikachu|78/100",
        ]

        update_battle(self.battle, "\n".join(messages))

        self.assertEqual("heavydutyboots", self.battle.opponent.active.item)

    def test_not_getting_poisoned_by_toxicspikes_does_not_set_heavydutyboots_if_already_poisoned(
        self,
    ):
        self.battle.opponent.side_conditions[constants.TOXIC_SPIKES] = 1
        pikachu = Pokemon("pikachu", 100)
        pikachu.status = constants.POISON
        self.battle.opponent.reserve.append(pikachu)
        messages = [
            "|switch|p2a: Pikachu|Pikachu, M|100/100",
            "|move|p1a: Caterpie|Tackle",
            "|-damage|p2a: Pikachu|78/100",
        ]

        update_battle(self.battle, "\n".join(messages))

        self.assertEqual(constants.UNKNOWN_ITEM, self.battle.opponent.active.item)

    def test_does_not_infer_headydutyboots_if_levitate_is_possible_with_tspikes(self):
        self.battle.opponent.side_conditions[constants.TOXIC_SPIKES] = 1
        self.battle.opponent.active = Pokemon("azelf", 100)
        messages = [
            "|switch|p2a: Azelf|Azelf, M|100/100",
            "|move|p1a: Caterpie|Tackle",
            "|-damage|p2a: Azelf|78/100",
        ]

        update_battle(self.battle, "\n".join(messages))

        self.assertEqual(constants.UNKNOWN_ITEM, self.battle.opponent.active.item)

    def test_does_not_infer_headydutyboots_if_levitate_is_possible_with_spikes(self):
        self.battle.opponent.side_conditions[constants.SPIKES] = 1
        self.battle.opponent.active = Pokemon("azelf", 100)
        messages = [
            "|switch|p2a: Azelf|Azelf, M|100/100",
            "|move|p1a: Caterpie|Tackle",
            "|-damage|p2a: Azelf|78/100",
        ]

        update_battle(self.battle, "\n".join(messages))

        self.assertEqual(constants.UNKNOWN_ITEM, self.battle.opponent.active.item)

    def test_getting_poisoned_by_two_layers_of_toxicspikes_does_not_set_heavydutyboots(
        self,
    ):
        self.battle.opponent.side_conditions[constants.TOXIC_SPIKES] = 1
        self.battle.opponent.active = Pokemon("pikachu", 100)
        messages = [
            "|switch|p2a: Pikachu|Pikachu, M|100/100",
            "|-status|p2a: Pikachu|tox",
            "|move|p1a: Caterpie|Tackle",
            "|-damage|p2a: Pikachu|78/100",
        ]

        update_battle(self.battle, "\n".join(messages))

        self.assertEqual(constants.UNKNOWN_ITEM, self.battle.opponent.active.item)

    def test_getting_toxiced_by_toxic_afterwards_still_sets_heavydutyboots(self):
        self.battle.opponent.side_conditions[constants.TOXIC_SPIKES] = 1
        self.battle.opponent.active = Pokemon("pikachu", 100)
        messages = [
            "|switch|p2a: Pikachu|Pikachu, M|100/100",
            "|move|p1a: Caterpie|Toxic",
            "|-status|p2a: Pikachu|tox",
        ]

        update_battle(self.battle, "\n".join(messages))

        self.assertEqual("heavydutyboots", self.battle.opponent.active.item)

    def test_toxicorb_poisoning_at_the_end_of_the_turn_does_not_infer_heavydutyboots(
        self,
    ):
        self.battle.opponent.side_conditions[constants.TOXIC_SPIKES] = 1
        messages = [
            "|switch|p1a: Pikachu|Pikachu, M|100/100",
            "|switch|p2a: Pikachu|Pikachu, M|100/100",
            "|",
            "|-status|p2a: Pikachu|tox|[from] item: Toxic Orb",
        ]

        update_battle(self.battle, "\n".join(messages))

        self.assertEqual("toxicorb", self.battle.opponent.active.item)

    def test_having_airballoon_does_notcause_a_heavydutyboost_inferral(self):
        self.battle.opponent.side_conditions[constants.TOXIC_SPIKES] = 1

        messages = [
            "|switch|p2a: Pikachu|Pikachu, M|100/100",
            "|-item|p2a: Pikachu|Air Balloon",
        ]

        update_battle(self.battle, "\n".join(messages))

        self.assertEqual("airballoon", self.battle.opponent.active.item)

    def test_flying_type_does_not_trigger_heavydutyboots_check_on_toxicspikes(self):
        self.battle.opponent.side_conditions[constants.TOXIC_SPIKES] = 1

        messages = [
            "|switch|p2a: Pidgey|Pidgey, M|100/100",
        ]

        update_battle(self.battle, "\n".join(messages))

        self.assertEqual(constants.UNKNOWN_ITEM, self.battle.opponent.active.item)

    def test_getting_poisoned_by_toxicspikes_does_not_set_heavydutyboots(self):
        self.battle.opponent.side_conditions[constants.TOXIC_SPIKES] = 1
        self.battle.opponent.active = Pokemon("pikachu", 100)
        messages = [
            "|switch|p2a: Pikachu|Pikachu, M|100/100",
            "|-status|p2a: Pikachu|psn",
            "|move|p1a: Caterpie|Tackle",
            "|-damage|p2a: Pikachu|78/100",
        ]

        update_battle(self.battle, "\n".join(messages))

        self.assertEqual(constants.UNKNOWN_ITEM, self.battle.opponent.active.item)

    def test_nothing_is_set_when_there_are_no_hazards_on_the_field(self):
        messages = [
            "|switch|p2a: Weedle|Weedle, M|100/100",
            "|move|p1a: Caterpie|Tackle",
            "|-damage|p2a: Weedle|78/100",
        ]

        update_battle(self.battle, "\n".join(messages))

        self.assertEqual(constants.UNKNOWN_ITEM, self.battle.opponent.active.item)

    def test_pokemon_that_could_have_magicguard_does_not_set_heavydutyboots_when_no_damage_is_taken(
        self,
    ):
        # clefable could have magicguard so HDB should not be set even though no damage was taken on switch
        self.battle.opponent.active = Pokemon("Clefable", 100)
        messages = [
            "|switch|p2a: Clefable|Clefable, M|100/100",
            "|move|p1a: Caterpie|Tackle",
            "|-damage|p2a: Clefable|78/100",
        ]

        update_battle(self.battle, "\n".join(messages))

        self.assertEqual(constants.UNKNOWN_ITEM, self.battle.opponent.active.item)

    def test_being_caught_in_stickyweb_does_not_set_set_heavydutyboots(self):
        self.battle.opponent.side_conditions[constants.STICKY_WEB] = 1
        messages = [
            "|switch|p2a: Weedle|Weedle, M|100/100",
            "|-activate|p2a: Weedle|move: Sticky Web",
            "|move|p1a: Caterpie|Tackle",
            "|-damage|p2a: Weedle|78/100",
        ]

        update_battle(self.battle, "\n".join(messages))

        self.assertEqual(constants.UNKNOWN_ITEM, self.battle.opponent.active.item)

    def test_being_caught_in_stickyweb_sets_heavydutyboots_to_impossible(self):
        self.battle.opponent.side_conditions[constants.STICKY_WEB] = 1
        messages = [
            "|switch|p2a: Weedle|Weedle, M|100/100",
            "|-activate|p2a: Weedle|move: Sticky Web",
            "|move|p1a: Caterpie|Tackle",
            "|-damage|p2a: Weedle|78/100",
        ]

        update_battle(self.battle, "\n".join(messages))

        self.assertIn(
            constants.HEAVY_DUTY_BOOTS, self.battle.opponent.active.impossible_items
        )

    def test_not_being_caught_in_stickyweb_sets_item_to_heavydutyboots(self):
        self.battle.opponent.side_conditions[constants.STICKY_WEB] = 1
        messages = [
            "|switch|p2a: Weedle|Weedle, M|100/100",
            "|move|p1a: Caterpie|Tackle",
            "|-damage|p2a: Weedle|78/100",
        ]

        update_battle(self.battle, "\n".join(messages))

        self.assertEqual("heavydutyboots", self.battle.opponent.active.item)

    def test_not_taking_spikes_with_possible_magicguard_does_not_set_heavydutyboots(
        self,
    ):
        self.battle.opponent.side_conditions[constants.SPIKES] = 1
        self.battle.opponent.reserve.append(Pokemon("Clefable", 100))
        messages = [
            "|switch|p2a: Clefable|Clefable, M|100/100",
            "|move|p1a: Caterpie|Tackle",
            "|-damage|p2a: Clefable|78/100",
        ]

        update_battle(self.battle, "\n".join(messages))

        self.assertNotEqual("heavydutyboots", self.battle.opponent.active.item)
        self.assertNotIn("heavydutyboots", self.battle.opponent.active.impossible_items)


class TestImmune(unittest.TestCase):
    def setUp(self):
        self.battle = Battle(None)
        self.battle.user.name = "p1"
        self.battle.opponent.name = "p2"

        self.opponent_active = Pokemon("caterpie", 100)
        self.battle.opponent.active = self.opponent_active
        self.battle.opponent.active.ability = None

        self.user_active = Pokemon("weedle", 100)
        self.battle.user.active = self.user_active

        self.username = "CoolUsername"

        self.battle.username = self.username

    def test_sets_ability_for_opponent(self):
        split_msg = ["", "-immune", "p2a: Caterpie", "[from] ability: Volt Absorb"]
        immune(self.battle, split_msg)

        expected_ability = "voltabsorb"

        self.assertEqual(expected_ability, self.battle.opponent.active.ability)

    def test_sets_ability_for_bot(self):
        split_msg = ["", "-immune", "p1a: Caterpie", "[from] ability: Volt Absorb"]
        immune(self.battle, split_msg)

        expected_ability = "voltabsorb"

        self.assertEqual(expected_ability, self.battle.user.active.ability)

    def test_immune_when_shouldnt_be_sets_potential_zoroark(self):
        """
        Zoroark disguised as Furret
        |
        |t:|1731185949
        |switch|p2a: Furret|Furret, L94, F|238/238
        |move|p1a: Chimecho|Psychic Noise|p2a: Furret
        |-immune|p2a: Furret
        |
        |-heal|p1a: Chimecho|73/100 brn|[from] item: Leftovers
        |-damage|p1a: Chimecho|67/100 brn|[from] brn
        |upkeep
        |turn|22
        """
        pass


class TestInactive(unittest.TestCase):
    def setUp(self):
        self.battle = Battle(None)
        self.battle.user.name = "p1"
        self.battle.opponent.name = "p2"

        self.opponent_active = Pokemon("caterpie", 100)
        self.battle.opponent.active = self.opponent_active
        self.battle.opponent.active.ability = None

        self.user_active = Pokemon("weedle", 100)
        self.battle.user.active = self.user_active

        self.username = "CoolUsername"

        self.battle.username = self.username

    def test_sets_time_to_15_seconds(self):
        split_msg = ["", "inactive", "Time left: 135 sec this turn", "135 sec total"]
        inactive(self.battle, split_msg)

        self.assertEqual(135, self.battle.time_remaining)

    def test_sets_to_60_seconds(self):
        split_msg = ["", "inactive", "Time left: 60 sec this turn", "60 sec total"]
        inactive(self.battle, split_msg)

        self.assertEqual(60, self.battle.time_remaining)

    def test_capture_group_failing(self):
        self.battle.time_remaining = 1
        split_msg = ["", "inactive", "some random message"]
        inactive(self.battle, split_msg)

        self.assertEqual(1, self.battle.time_remaining)

    def test_capture_group_failing_but_message_starts_with_username(self):
        self.battle.time_remaining = 1
        split_msg = ["", "inactive", "Time left: some random message"]
        inactive(self.battle, split_msg)

        self.assertEqual(1, self.battle.time_remaining)

    def test_different_inactive_message_does_not_change_time(self):
        self.battle.time_remaining = 1
        split_msg = ["", "inactive", "Some Other Person has 10 seconds left"]
        inactive(self.battle, split_msg)

        self.assertEqual(1, self.battle.time_remaining)


class TestInactiveOff(unittest.TestCase):
    def setUp(self):
        self.battle = Battle(None)
        self.battle.user.name = "p1"
        self.battle.opponent.name = "p2"

        self.opponent_active = Pokemon("caterpie", 100)
        self.battle.opponent.active = self.opponent_active
        self.battle.opponent.active.ability = None

        self.user_active = Pokemon("caterpie", 100)
        self.battle.user.active = self.user_active
        self.battle.user.active.previous_hp = self.battle.user.active.hp

        self.username = "CoolUsername"

        self.battle.username = self.username

        self.battle.user.last_used_move = LastUsedMove("caterpie", "tackle", 0)

        self.battle.request_json = {
            constants.ACTIVE: [{constants.MOVES: []}],
            constants.SIDE: {
                constants.ID: None,
                constants.NAME: None,
                constants.POKEMON: [],
                constants.RQID: None,
            },
        }

    def test_turns_timer_off(self):
        self.battle.time_remaining = 60
        msg = (
            "|move|p2a: Caterpie|Tackle|\n"
            "|-damage|p1a: Caterpie|186/252\n"
            "|move|p1a: Caterpie|Tackle|\n"
            "|-damage|p2a: Caterpie|85/100\n"
            "|upkeep\n"
            "|inactiveoff|Battle timer is now OFF.\n"  # this line is being tested
            "|turn|4"
        )
        update_battle(self.battle, msg)
        self.assertIsNone(self.battle.time_remaining)


class TestGetDamageDealt(unittest.TestCase):
    def setUp(self):
        self.battle = Battle(None)

        self.battle.user.name = "p1"
        self.battle.user.active = Pokemon("Caterpie", 100)

        self.battle.opponent.name = "p2"
        self.battle.opponent.active = Pokemon("Pikachu", 100)

    def test_assigns_damage_dealt_from_opponent_to_bot(self):
        self.battle.user.active.max_hp = 250
        self.battle.user.active.hp = 250

        messages = [
            "|move|p2a: Pikachu|Tackle|p1a: Caterpie",
            "|-damage|p1a: Caterpie|200/250",  # 50 / 250 = 0.20 of total health
            "|",
            "|move|p1a: Caterpie|Tackle|p2a: Pikachu",
            "|-damage|p2a: Pikachu|90/100",
        ]

        split_msg = messages[0].split("|")

        damage_dealt = get_damage_dealt(self.battle, split_msg, messages[1:])

        expected_damage_amount_dealt = DamageDealt(
            attacker="pikachu",
            defender="caterpie",
            move="tackle",
            percent_damage=0.20,
            crit=False,
        )
        self.assertEqual(expected_damage_amount_dealt, damage_dealt)

    def test_assigns_damage_when_bots_pokemon_has_no_last_used_move(self):
        self.battle.user.active.max_hp = 250
        self.battle.user.active.hp = 250

        messages = [
            "|move|p2a: Pikachu|Tackle|p1a: Caterpie",
            "|-damage|p1a: Caterpie|200/250",  # 50 / 250 = 0.20 of total health
            "|",
            "|move|p1a: Caterpie|Tackle|p2a: Pikachu",
            "|-damage|p2a: Pikachu|90/100",
        ]

        split_msg = messages[0].split("|")

        damage_dealt = get_damage_dealt(self.battle, split_msg, messages[1:])

        expected_damage_amount_dealt = DamageDealt(
            attacker="pikachu",
            defender="caterpie",
            move="tackle",
            percent_damage=0.20,
            crit=False,
        )
        self.assertEqual(expected_damage_amount_dealt, damage_dealt)

    def test_supereffective_damage_is_captured(self):
        self.battle.user.active.max_hp = 250
        self.battle.user.active.hp = 250

        messages = [
            "|move|p2a: Pikachu|Tackle|p1a: Caterpie",
            "|supereffective|p1a: Caterpie",
            "|-damage|p1a: Caterpie|100/250",  # 150 / 250 = 0.60 of total health
            "|",
            "|move|p1a: Caterpie|Tackle|p2a: Pikachu",
            "|-damage|p2a: Pikachu|90/100",
        ]

        split_msg = messages[0].split("|")

        damage_dealt = get_damage_dealt(self.battle, split_msg, messages[1:])

        expected_damage_amount_dealt = DamageDealt(
            attacker="pikachu",
            defender="caterpie",
            move="tackle",
            percent_damage=0.60,
            crit=False,
        )
        self.assertEqual(expected_damage_amount_dealt, damage_dealt)

    def test_crit_sets_crit_flag(self):
        self.battle.user.active.max_hp = 250
        self.battle.user.active.hp = 250

        messages = [
            "|move|p2a: Pikachu|Tackle|p1a: Caterpie",
            "|-crit|p1a: Caterpie",  # should set crit to True
            "|-damage|p1a: Caterpie|100/250",  # 150 / 250 = 0.60 of total health
            "|",
            "|move|p1a: Caterpie|Tackle|p2a: Pikachu",
            "|-damage|p2a: Pikachu|90/100",
        ]

        split_msg = messages[0].split("|")

        damage_dealt = get_damage_dealt(self.battle, split_msg, messages[1:])

        expected_damage_amount_dealt = DamageDealt(
            attacker="pikachu",
            defender="caterpie",
            move="tackle",
            percent_damage=0.60,
            crit=True,
        )
        self.assertEqual(expected_damage_amount_dealt, damage_dealt)

    def test_stop_after_the_end_of_this_move(self):
        self.battle.user.active.max_hp = 250
        self.battle.user.active.hp = 250

        messages = [
            "|move|p2a: Pikachu|Tackle|p1a: Caterpie",
            "|-damage|p1a: Caterpie|200/250",  # 50 / 250 = 0.20 of total health
            "|",
            "|move|p1a: Caterpie|Tackle|p2a: Pikachu",
            "|-damage|p2a: Pikachu|90/100",
        ]

        split_msg = messages[0].split("|")

        damage_dealt = get_damage_dealt(self.battle, split_msg, messages[1:])

        expected_damage_amount_dealt = DamageDealt(
            attacker="pikachu",
            defender="caterpie",
            move="tackle",
            percent_damage=0.20,
            crit=False,
        )
        self.assertEqual(expected_damage_amount_dealt, damage_dealt)

    def test_does_not_assign_anything_when_move_does_no_damage(self):
        self.battle.user.active.max_hp = 250
        self.battle.user.active.hp = 250

        messages = [
            "|move|p2a: Pikachu|Recover|p2a: Pikachu",
            "|-heal|p2a: Pikachu|200/250",
        ]

        split_msg = messages[0].split("|")

        damage_dealt = get_damage_dealt(self.battle, split_msg, messages[1:])
        self.assertIsNone(damage_dealt)

    def test_does_not_catch_second_moves_damage_after_a_heal(self):
        self.battle.user.active.max_hp = 250
        self.battle.user.active.hp = 250

        messages = [
            "|move|p2a: Pikachu|Recover|p2a: Pikachu",
            "|-heal|p2a: Pikachu|200/250",
            "|move|p1a: Caterpie|Tackle|p2a: Pikachu",
            "|-damage|p2a: Pikachu|90/100",
        ]

        split_msg = messages[0].split("|")

        damage_dealt = get_damage_dealt(self.battle, split_msg, messages[1:])
        self.assertIsNone(damage_dealt)

    def test_does_not_set_damage_when_status_move_occurs(self):
        self.battle.user.active.max_hp = 250
        self.battle.user.active.hp = 250

        messages = [
            "|move|p2a: Pikachu|Thunder Wave|p1a: Caterpie",
            "|-status|p1a: Caterpie|par",
        ]

        split_msg = messages[0].split("|")

        damage_dealt = get_damage_dealt(self.battle, split_msg, messages[1:])
        self.assertIsNone(damage_dealt)

    def test_assigns_damage_from_move_that_causes_status_as_secondary(self):
        self.battle.user.active.max_hp = 250
        self.battle.user.active.hp = 250

        messages = [
            "|move|p2a: Pikachu|Thunderbolt|p1a: Caterpie",
            "|-damage|p1a: Caterpie|200/250",  # 50 / 250 = 0.20 of total health
            "|-status|p1a: Caterpie|par",
        ]

        split_msg = messages[0].split("|")

        damage_dealt = get_damage_dealt(self.battle, split_msg, messages[1:])

        expected_damage_amount_dealt = DamageDealt(
            attacker="pikachu",
            defender="caterpie",
            move="thunderbolt",
            percent_damage=0.20,
            crit=False,
        )
        self.assertEqual(expected_damage_amount_dealt, damage_dealt)

    def test_assigns_damage_to_bot_on_faint(self):
        self.battle.user.active.max_hp = 250
        self.battle.user.active.hp = 250

        self.battle.user.active.hp = 1

        messages = [
            "|move|p2a: Pikachu|Tackle|p1a: Caterpie",
            "|-damage|p1a: Caterpie|0 fnt",  # 1 / 250 of health was done
            "|faint|p1a: Caterpie",
        ]

        split_msg = messages[0].split("|")

        damage_dealt = get_damage_dealt(self.battle, split_msg, messages[1:])

        expected_damage_amount_dealt = DamageDealt(
            attacker="pikachu",
            defender="caterpie",
            move="tackle",
            percent_damage=1 / 250,
            crit=False,
        )
        self.assertEqual(expected_damage_amount_dealt, damage_dealt)

    def test_assigns_damage_to_opponent_on_faint(self):
        self.battle.opponent.active.max_hp = 250
        self.battle.opponent.active.hp = 2.5

        messages = [
            "|move|p1a: Caterpie|Tackle|p2a: Pikachu",
            "|-damage|p2a: Pikachu|0 fnt",
            "|faint|p2a: Pikachu",
        ]

        split_msg = messages[0].split("|")

        damage_dealt = get_damage_dealt(self.battle, split_msg, messages[1:])

        expected_damage_amount_dealt = DamageDealt(
            attacker="caterpie",
            defender="pikachu",
            move="tackle",
            percent_damage=0.01,
            crit=False,
        )
        self.assertEqual(expected_damage_amount_dealt, damage_dealt)

    def test_assigns_damage_to_opponent_on_faint_from_1_hp(self):
        self.battle.opponent.active.max_hp = 250
        self.battle.opponent.active.hp = 250

        self.battle.opponent.active.hp = 1

        messages = [
            "|move|p1a: Caterpie|Tackle|p2a: Pikachu",
            "|-damage|p2a: Pikachu|0 fnt",  # 1 / 250 of health was done
            "|faint|p1a: Pikachu",
        ]

        split_msg = messages[0].split("|")

        damage_dealt = get_damage_dealt(self.battle, split_msg, messages[1:])

        expected_damage_amount_dealt = DamageDealt(
            attacker="caterpie",
            defender="pikachu",
            move="tackle",
            percent_damage=1 / 250,
            crit=False,
        )
        self.assertEqual(expected_damage_amount_dealt, damage_dealt)

    def test_assigns_nothing_on_substitute(self):
        self.battle.user.active.max_hp = 100
        self.battle.user.active.hp = 100

        self.battle.opponent.active.hp = 100
        self.battle.user.active.hp = 100

        messages = [
            "|move|p2a: Pikachu|Substitute|p2a: Pikachu",
            "|-start|p2a: Pikachu|Substitute",
            "|-damage|p2a: Pikachu|75/100",  # damage from sub should not be caught
        ]

        split_msg = messages[0].split("|")

        damage_dealt = get_damage_dealt(self.battle, split_msg, messages[1:])
        self.assertIsNone(damage_dealt)

    def test_lifeorb_does_not_assign_damage(self):
        self.battle.user.active.max_hp = 250
        self.battle.user.active.hp = 250

        messages = [
            "|move|p2a: Pikachu|Tackle|p1a: Caterpie",
            "|-damage|p1a: Caterpie|200/250",  # 0.2 of total health
            "|-damage|p2a: Pikachu|90/100|[from] item: Life Orb",
        ]

        split_msg = messages[0].split("|")

        damage_dealt = get_damage_dealt(self.battle, split_msg, messages[1:])

        expected_damage_dealt = DamageDealt(
            attacker="pikachu",
            defender="caterpie",
            move="tackle",
            percent_damage=0.20,
            crit=False,
        )
        self.assertEqual(damage_dealt, expected_damage_dealt)

    def test_doing_damage_to_opponent_gets_correct_percentage(self):
        # start at 100% health
        self.battle.opponent.active.max_hp = 250
        self.battle.opponent.active.hp = 250

        messages = [
            "|move|p1a: Caterpie|Tackle|p2a: Pikachu",
            "|-damage|p2a: Pikachu|85/100",  # 0.15 of total health
        ]

        split_msg = messages[0].split("|")

        damage_dealt = get_damage_dealt(self.battle, split_msg, messages[1:])

        expected_damage_dealt = DamageDealt(
            attacker="caterpie",
            defender="pikachu",
            move="tackle",
            percent_damage=0.15,
            crit=False,
        )
        self.assertEqual(expected_damage_dealt, damage_dealt)

    def test_entire_message_finishing(self):
        # start at 100% health
        self.battle.opponent.active.max_hp = 250
        self.battle.opponent.active.hp = 250

        messages = [
            "|move|p1a: Caterpie|Parting Shot|p2a: Pikachu",
            "|-unboost|p2a: Pikachu|atk|1",
            "|-unboost|p2a: Pikachu|spa|1",
            "",
        ]

        split_msg = messages[0].split("|")

        damage_dealt = get_damage_dealt(self.battle, split_msg, messages[1:])

        self.assertIsNone(damage_dealt)


class TestNoInit(unittest.TestCase):
    def setUp(self):
        self.battle = Battle(None)

        self.battle.user.name = "p1"
        self.battle.user.active = Pokemon("Caterpie", 100)

        self.battle.opponent.name = "p2"
        self.battle.opponent.active = Pokemon("Pikachu", 100)

    def test_renames_battle_when_rename_message_occurs(self):
        self.battle.battle_tag = "original_tag"
        new_battle_tag = "new_battle_tag"

        msg = "|noinit|rename|{}".format(new_battle_tag)

        update_battle(self.battle, msg)

        self.assertEqual(self.battle.battle_tag, new_battle_tag)
