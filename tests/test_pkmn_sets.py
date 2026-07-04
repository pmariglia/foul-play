import unittest

from fp.data.sets import (
    BattleFactoryTeamDatasets,
    TeamDatasets,
    SmogonSets,
    PredictedPokemonSet,
    PokemonSet,
    PokemonMoveset,
)
from fp.battle.state import Pokemon, Move
from fp.format_spec import FormatSpec


class TestTeamDatasets(unittest.TestCase):
    def setUp(self):
        self.team_datasets = TeamDatasets()

    def test_team_datasets_initialize_gen5(self):
        self.team_datasets.initialize(
            FormatSpec.from_format_string("gen5ou"),
            {"azelf", "heatran", "rotomwash", "scizor", "tyranitar", "volcarona"},
        )
        self.assertEqual("gen5ou", self.team_datasets.pkmn_mode)
        self.assertEqual(6, len(self.team_datasets.pkmn_sets))

    def test_team_datasets_add_new_pokemon(self):
        self.team_datasets.initialize(
            FormatSpec.from_format_string("gen5ou"), {"dragonite"}
        )
        self.assertNotIn("azelf", self.team_datasets.pkmn_sets)
        self.team_datasets.add_new_pokemon("azelf")
        self.assertIn("azelf", self.team_datasets.pkmn_sets)

    def test_pokemon_not_in_team_datasets_does_not_error(self):
        self.team_datasets.initialize(
            FormatSpec.from_format_string("gen5ou"), {"dragonite"}
        )
        self.assertNotIn("azelf", self.team_datasets.pkmn_sets)
        self.team_datasets.add_new_pokemon("not_in_team_datasets")
        self.assertNotIn("not_in_team_datasets", self.team_datasets.pkmn_sets)

    def test_smogon_datasets_add_new_pokemon_with_cosmetic_forme(self):
        self.team_datasets.initialize(
            FormatSpec.from_format_string("gen5ou"), {"dragonite"}
        )
        self.assertNotIn("gastrodon", self.team_datasets.pkmn_sets)
        self.assertNotIn("gastrodoneast", self.team_datasets.pkmn_sets)
        self.team_datasets.add_new_pokemon("gastrodoneast")
        self.assertIn("gastrodoneast", self.team_datasets.pkmn_sets)
        self.assertNotIn("gastrodon", self.team_datasets.pkmn_sets)

    def test_removing_initial_set_does_not_change_existing_pokemon_sets(self):
        self.team_datasets.initialize(
            FormatSpec.from_format_string("gen5ou"), {"dragonite"}
        )
        initial_len = len(self.team_datasets.pkmn_sets["dragonite"])
        self.team_datasets.pkmn_sets["dragonite"].pop(-1)
        len_after_pop = len(self.team_datasets.pkmn_sets["dragonite"])
        self.assertNotEqual(initial_len, len_after_pop)
        self.team_datasets.add_new_pokemon("azelf")
        self.assertEqual(len_after_pop, len(self.team_datasets.pkmn_sets["dragonite"]))


class TestSmogonDatasets(unittest.TestCase):
    def setUp(self):
        self.smogon_sets = SmogonSets()

    def test_smogon_datasets_initialize_gen5(self):
        self.smogon_sets.initialize(
            FormatSpec.from_format_string("gen5ou"),
            {"azelf", "heatran", "scizor", "tyranitar", "volcarona"},
        )
        self.assertEqual("gen5ou", self.smogon_sets.pkmn_mode)
        self.assertEqual(5, len(self.smogon_sets.pkmn_sets))

    def test_smogon_datasets_initialize_gen4(self):
        self.smogon_sets.initialize(
            FormatSpec.from_format_string("gen4ou"),
            {"azelf", "heatran", "scizor", "tyranitar", "dragonite"},
        )
        self.assertEqual("gen4ou", self.smogon_sets.pkmn_mode)
        self.assertEqual(5, len(self.smogon_sets.pkmn_sets))

    def test_smogon_datasets_add_new_pokemon(self):
        self.smogon_sets.initialize(
            FormatSpec.from_format_string("gen4ou"), {"dragonite"}
        )
        self.assertNotIn("azelf", self.smogon_sets.pkmn_sets)
        self.smogon_sets.add_new_pokemon("azelf")
        self.assertIn("azelf", self.smogon_sets.pkmn_sets)

    def test_smogon_datasets_add_new_pokemon_with_cosmetic_forme(self):
        self.smogon_sets.initialize(
            FormatSpec.from_format_string("gen4ou"), {"dragonite"}
        )
        self.assertNotIn("gastrodon", self.smogon_sets.pkmn_sets)
        self.assertNotIn("gastrodoneast", self.smogon_sets.pkmn_sets)
        self.smogon_sets.add_new_pokemon("gastrodoneast")
        self.assertNotIn("gastrodoneast", self.smogon_sets.pkmn_sets)
        self.assertIn("gastrodon", self.smogon_sets.pkmn_sets)

    def test_removing_initial_set_does_not_change_existing_pokemon_sets(self):
        self.smogon_sets.initialize(
            FormatSpec.from_format_string("gen4ou"), {"dragonite"}
        )
        initial_len = len(self.smogon_sets.pkmn_sets["dragonite"])
        self.smogon_sets.pkmn_sets["dragonite"].pop(-1)
        len_after_pop = len(self.smogon_sets.pkmn_sets["dragonite"])
        self.assertNotEqual(initial_len, len_after_pop)
        self.smogon_sets.add_new_pokemon("azelf")
        self.assertEqual(len_after_pop, len(self.smogon_sets.pkmn_sets["dragonite"]))


class TestPredictSet(unittest.TestCase):
    def test_omits_impossible_ability_when_predicting_set(self):
        self.battle_factory_datasets = BattleFactoryTeamDatasets("ru")
        self.battle_factory_datasets.initialize(
            FormatSpec.from_format_string("gen9battlefactory"),
            {"krookodile"},
        )

        pkmn = Pokemon("krookodile", 100)
        pkmn.ability = None

        all_sets = self.battle_factory_datasets.get_all_remaining_sets(pkmn)
        any_set_has_intimidate = any(
            set_.pkmn_set.ability == "intimidate" for set_ in all_sets
        )
        self.assertTrue(
            any_set_has_intimidate
        )  # Intimidate is possible before adding it to impossible_abilities

        pkmn.impossible_abilities.add("intimidate")

        all_sets = self.battle_factory_datasets.get_all_remaining_sets(pkmn)
        any_set_has_intimidate = any(
            set_.pkmn_set.ability == "intimidate" for set_ in all_sets
        )
        self.assertFalse(any_set_has_intimidate)

    def test_allows_impossible_ability_when_predicting_set_if_ability_is_explicitly_set(
        self,
    ):
        self.battle_factory_datasets = BattleFactoryTeamDatasets("ru")
        self.battle_factory_datasets.initialize(
            FormatSpec.from_format_string("gen9battlefactory"),
            {"krookodile"},
        )

        pkmn = Pokemon("krookodile", 100)
        pkmn.ability = None

        all_sets = self.battle_factory_datasets.get_all_remaining_sets(pkmn)
        any_set_has_intimidate = any(
            set_.pkmn_set.ability == "intimidate" for set_ in all_sets
        )
        self.assertTrue(
            any_set_has_intimidate
        )  # Intimidate is possible before adding it to impossible_abilities

        # this doesn't matter because the pkmn's ability is intimidate
        pkmn.impossible_abilities.add("intimidate")
        pkmn.ability = "intimidate"

        all_sets = self.battle_factory_datasets.get_all_remaining_sets(pkmn)
        any_set_has_intimidate = any(
            set_.pkmn_set.ability == "intimidate" for set_ in all_sets
        )
        self.assertTrue(
            any_set_has_intimidate
        )  # this is True because intimidate is the ability

    def test_uses_removed_item_when_predicting_set(self):
        self.battle_factory_datasets = BattleFactoryTeamDatasets("ou")
        self.battle_factory_datasets.initialize(
            FormatSpec.from_format_string("gen9battlefactory"),
            {"gholdengo"},
        )

        pkmn = Pokemon("gholdengo", 100)

        all_sets = self.battle_factory_datasets.get_all_remaining_sets(pkmn)
        all_sets_have_airballoon = all(
            set_.pkmn_set.item == "airballoon" for set_ in all_sets
        )
        self.assertFalse(all_sets_have_airballoon)

        pkmn.item = None
        pkmn.removed_item = "airballoon"

        sets_after_removed_item = self.battle_factory_datasets.get_all_remaining_sets(
            pkmn
        )

        all_sets_have_airballoon = all(
            set_.pkmn_set.item == "airballoon" for set_ in sets_after_removed_item
        )
        self.assertTrue(all_sets_have_airballoon)

    def test_predicts_set_when_there_is_no_removed_item(
        self,
    ):
        self.battle_factory_datasets = BattleFactoryTeamDatasets("ou")
        self.battle_factory_datasets.initialize(
            FormatSpec.from_format_string("gen9battlefactory"),
            {"gholdengo"},
        )

        pkmn = Pokemon("gholdengo", 100)
        pkmn.item = None

        sets_after_removed_item = self.battle_factory_datasets.get_all_remaining_sets(
            pkmn
        )
        self.assertNotEqual(0, len(sets_after_removed_item))

    def test_removed_item_is_used_when_another_item_was_tricked(
        self,
    ):
        team_datasets = TeamDatasets()
        team_datasets.initialize(FormatSpec.from_format_string("gen5ou"), {"starmie"})
        team_datasets.raw_pkmn_sets = {
            "starmie": {
                "|analytic|choicespecs|timid|0,0,0,252,4,252|trick|rapidspin|thunder|surf",
            }
        }
        team_datasets.pkmn_sets = {
            "starmie": [
                PredictedPokemonSet(
                    pkmn_set=PokemonSet(
                        nature="timid",
                        item="choicespecs",
                        ability="analytic",
                        evs=[0, 0, 0, 252, 4, 252],
                        count=1,
                    ),
                    pkmn_moveset=PokemonMoveset(
                        moves=["trick", "rapidspin", "thunder", "surf"],
                    ),
                )
            ]
        }

        pkmn = Pokemon("starmie", 100)
        pkmn.moves = [
            Move("trick"),
            Move("rapidspin"),
            Move("thunder"),
        ]
        pkmn.item = "leftovers"
        pkmn.removed_item = "choicespecs"

        sets_after_removed_item = team_datasets.get_all_remaining_sets(pkmn)
        self.assertNotEqual(0, len(sets_after_removed_item))
