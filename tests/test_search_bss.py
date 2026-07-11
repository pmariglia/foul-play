import random

import pytest

from fp.battle.state import Battle, Battler, Pokemon
from fp.data.sets import PokemonMoveset, PokemonSet, PredictedPokemonSet
from fp.modes.bss import BSSMode
from fp.search.bss import (
    prepare_post_team_preview_bss_battles,
    sample_pkmn_to_remove,
)
from fp.search.bss import calculate_opponent_team_preview_preferences


def make_predicted_set(moves, ability="levitate", item="leftovers"):
    return PredictedPokemonSet(
        pkmn_set=PokemonSet(
            ability=ability,
            item=item,
            nature="serious",
            evs=(0, 0, 0, 0, 0, 0),
            count=1,
            tera_type=None,
        ),
        pkmn_moveset=PokemonMoveset(moves=tuple(moves)),
    )


def make_bss_battle():
    battle = Battle(None)
    battle.generation = "gen9"
    battle.pokemon_format = "gen9bssregi"
    battle.mode = BSSMode()
    return battle


class TestSamplePkmnToRemove:
    def test_only_samples_unrevealed_pokemon(self):
        battler = Battler()
        battler.active = Pokemon("greattusk", 100)
        revealed = Pokemon("kingambit", 100)
        revealed.revealed = True
        unrevealed = Pokemon("dragapult", 100)
        battler.reserve = [revealed, unrevealed]

        affinities = {"kingambit": 1.0, "dragapult": 1.0}
        for _ in range(20):
            assert sample_pkmn_to_remove(battler, affinities) is unrevealed


class TestPreparePostTeamPreviewBssBattles:
    @pytest.fixture(autouse=True)
    def _setup(self):
        self.battle = make_bss_battle()
        names = [
            "greattusk",
            "kingambit",
            "dragapult",
            "gholdengo",
            "ironvaliant",
            "landorustherian",
        ]
        self.battle.opponent.active = Pokemon(names[0], 100)
        self.battle.opponent.reserve = [Pokemon(n, 100) for n in names[1:]]
        self.battle.opponent_team_preview_affinities = {n: 1.0 for n in names}
        self.battle.mode.team_datasets.pkmn_sets = {
            n: [make_predicted_set(["protect", "substitute", "rest", "sleeptalk"])]
            for n in names
        }

    def test_reduces_opponent_to_three_pokemon(self):
        random.seed(0)
        battles = prepare_post_team_preview_bss_battles(self.battle, 4)

        assert 4 == len(battles)
        for sampled_battle, _chance in battles:
            assert 2 == len(sampled_battle.opponent.reserve)


class TestCalculateOpponentTeamPreviewPreferences:
    def test_empty_results_returns_empty_dict(self):
        assert {} == calculate_opponent_team_preview_preferences([])

    def test_accumulates_visits_over_iterations(self):
        class FakeSideResult:
            def __init__(self, move_choice, visits):
                self.move_choice = move_choice
                self.visits = visits

        results = [
            (
                100,
                [
                    FakeSideResult("pikachu,charizard,snorlax", 50),
                    FakeSideResult("pikachu,gengar,alakazam", 30),
                ],
            )
        ]

        prefs = calculate_opponent_team_preview_preferences(results)

        assert prefs["pikachu"] == pytest.approx(0.8)
        assert prefs["charizard"] == pytest.approx(0.5)
        assert prefs["gengar"] == pytest.approx(0.3)
