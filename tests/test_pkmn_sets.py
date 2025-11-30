import unittest

from data.pkmn_sets import (
    TeamDatasets,
    SmogonSets,
    PredictedPokemonSet,
    PokemonSet,
    PokemonMoveset,
)
from fp.battle import Pokemon, Move


class TestTeamDatasets(unittest.TestCase):
    def setUp(self):
        TeamDatasets.__init__()

    def test_team_datasets_initialize_gen5(self):
        TeamDatasets.initialize(
            "gen5ou",
            {"azelf", "heatran", "rotomwash", "scizor", "tyranitar", "volcarona"},
        )
        self.assertEqual("gen5ou", TeamDatasets.pkmn_mode)
        self.assertEqual(6, len(TeamDatasets.pkmn_sets))

    def test_team_datasets_add_new_pokemon(self):
        TeamDatasets.initialize("gen5ou", {"dragonite"})
        self.assertNotIn("azelf", TeamDatasets.pkmn_sets)
        TeamDatasets.add_new_pokemon("azelf")
        self.assertIn("azelf", TeamDatasets.pkmn_sets)

    def test_pokemon_not_in_team_datasets_does_not_error(self):
        TeamDatasets.initialize("gen5ou", {"dragonite"})
        self.assertNotIn("azelf", TeamDatasets.pkmn_sets)
        TeamDatasets.add_new_pokemon("not_in_team_datasets")
        self.assertNotIn("not_in_team_datasets", TeamDatasets.pkmn_sets)

    def test_smogon_datasets_add_new_pokemon_with_cosmetic_forme(self):
        TeamDatasets.initialize("gen5ou", {"dragonite"})
        self.assertNotIn("gastrodon", TeamDatasets.pkmn_sets)
        self.assertNotIn("gastrodoneast", TeamDatasets.pkmn_sets)
        TeamDatasets.add_new_pokemon("gastrodoneast")
        self.assertIn("gastrodoneast", TeamDatasets.pkmn_sets)
        self.assertNotIn("gastrodon", TeamDatasets.pkmn_sets)

    def test_removing_initial_set_does_not_change_existing_pokemon_sets(self):
        TeamDatasets.initialize("gen5ou", {"dragonite"})
        initial_len = len(TeamDatasets.pkmn_sets["dragonite"])
        TeamDatasets.pkmn_sets["dragonite"].pop(-1)
        len_after_pop = len(TeamDatasets.pkmn_sets["dragonite"])
        self.assertNotEqual(initial_len, len_after_pop)
        TeamDatasets.add_new_pokemon("azelf")
        self.assertEqual(len_after_pop, len(TeamDatasets.pkmn_sets["dragonite"]))


class TestSmogonDatasets(unittest.TestCase):
    def setUp(self):
        SmogonSets.__init__()

    def test_smogon_datasets_initialize_gen5(self):
        SmogonSets.initialize(
            "gen5ou",
            {"azelf", "heatran", "scizor", "tyranitar", "volcarona"},
        )
        self.assertEqual("gen5ou", SmogonSets.pkmn_mode)
        self.assertEqual(5, len(SmogonSets.pkmn_sets))

    def test_smogon_datasets_initialize_gen4(self):
        SmogonSets.initialize(
            "gen4ou",
            {"azelf", "heatran", "scizor", "tyranitar", "dragonite"},
        )
        self.assertEqual("gen4ou", SmogonSets.pkmn_mode)
        self.assertEqual(5, len(SmogonSets.pkmn_sets))

    def test_smogon_datasets_add_new_pokemon(self):
        SmogonSets.initialize("gen4ou", {"dragonite"})
        self.assertNotIn("azelf", SmogonSets.pkmn_sets)
        SmogonSets.add_new_pokemon("azelf")
        self.assertIn("azelf", SmogonSets.pkmn_sets)

    def test_smogon_datasets_add_new_pokemon_with_cosmetic_forme(self):
        SmogonSets.initialize("gen4ou", {"dragonite"})
        self.assertNotIn("gastrodon", SmogonSets.pkmn_sets)
        self.assertNotIn("gastrodoneast", SmogonSets.pkmn_sets)
        SmogonSets.add_new_pokemon("gastrodoneast")
        self.assertNotIn("gastrodoneast", SmogonSets.pkmn_sets)
        self.assertIn("gastrodon", SmogonSets.pkmn_sets)

    def test_removing_initial_set_does_not_change_existing_pokemon_sets(self):
        SmogonSets.initialize("gen4ou", {"dragonite"})
        initial_len = len(SmogonSets.pkmn_sets["dragonite"])
        SmogonSets.pkmn_sets["dragonite"].pop(-1)
        len_after_pop = len(SmogonSets.pkmn_sets["dragonite"])
        self.assertNotEqual(initial_len, len_after_pop)
        SmogonSets.add_new_pokemon("azelf")
        self.assertEqual(len_after_pop, len(SmogonSets.pkmn_sets["dragonite"]))


class TestPredictSet(unittest.TestCase):
    def setUp(self):
        TeamDatasets.__init__()

    def test_omits_impossible_ability_when_predicting_set(self):
        TeamDatasets.initialize(
            "gen9battlefactory", {"krookodile"}, battle_factory_tier_name="ru"
        )

        pkmn = Pokemon("krookodile", 100)
        pkmn.ability = None

        all_sets = TeamDatasets.get_all_remaining_sets(pkmn)
        any_set_has_intimidate = any(
            set_.pkmn_set.ability == "intimidate" for set_ in all_sets
        )
        self.assertTrue(
            any_set_has_intimidate
        )  # Intimidate is possible before adding it to impossible_abilities

        pkmn.impossible_abilities.add("intimidate")

        all_sets = TeamDatasets.get_all_remaining_sets(pkmn)
        any_set_has_intimidate = any(
            set_.pkmn_set.ability == "intimidate" for set_ in all_sets
        )
        self.assertFalse(any_set_has_intimidate)

    def test_allows_impossible_ability_when_predicting_set_if_ability_is_explicitly_set(
        self,
    ):
        TeamDatasets.initialize(
            "gen9battlefactory", {"krookodile"}, battle_factory_tier_name="ru"
        )

        pkmn = Pokemon("krookodile", 100)
        pkmn.ability = None

        all_sets = TeamDatasets.get_all_remaining_sets(pkmn)
        any_set_has_intimidate = any(
            set_.pkmn_set.ability == "intimidate" for set_ in all_sets
        )
        self.assertTrue(
            any_set_has_intimidate
        )  # Intimidate is possible before adding it to impossible_abilities

        # this doesn't matter because the pkmn's ability is intimidate
        pkmn.impossible_abilities.add("intimidate")
        pkmn.ability = "intimidate"

        all_sets = TeamDatasets.get_all_remaining_sets(pkmn)
        any_set_has_intimidate = any(
            set_.pkmn_set.ability == "intimidate" for set_ in all_sets
        )
        self.assertTrue(
            any_set_has_intimidate
        )  # this is True because intimidate is the ability

    def test_uses_removed_item_when_predicting_set(self):
        TeamDatasets.initialize(
            "gen9battlefactory", {"gholdengo"}, battle_factory_tier_name="ou"
        )

        pkmn = Pokemon("gholdengo", 100)

        all_sets = TeamDatasets.get_all_remaining_sets(pkmn)
        all_sets_have_airballoon = all(
            set_.pkmn_set.item == "airballoon" for set_ in all_sets
        )
        self.assertFalse(all_sets_have_airballoon)

        pkmn.item = None
        pkmn.removed_item = "airballoon"

        sets_after_removed_item = TeamDatasets.get_all_remaining_sets(pkmn)

        all_sets_have_airballoon = all(
            set_.pkmn_set.item == "airballoon" for set_ in sets_after_removed_item
        )
        self.assertTrue(all_sets_have_airballoon)

    def test_predicts_set_when_there_is_no_removed_item(
        self,
    ):
        TeamDatasets.initialize(
            "gen9battlefactory", {"gholdengo"}, battle_factory_tier_name="ou"
        )

        pkmn = Pokemon("gholdengo", 100)
        pkmn.item = None

        sets_after_removed_item = TeamDatasets.get_all_remaining_sets(pkmn)
        self.assertNotEqual(0, len(sets_after_removed_item))

    def test_removed_item_is_used_when_another_item_was_tricked(
        self,
    ):
        TeamDatasets.initialize("gen5ou", {"starmie"})
        TeamDatasets.raw_pkmn_sets = {
            "starmie": {
                "|analytic|choicespecs|timid|0,0,0,252,4,252|trick|rapidspin|thunder|surf",
            }
        }
        TeamDatasets.pkmn_sets = {
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

        sets_after_removed_item = TeamDatasets.get_all_remaining_sets(pkmn)
        self.assertNotEqual(0, len(sets_after_removed_item))
