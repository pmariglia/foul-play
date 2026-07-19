import logging
import random

import pytest

from fp import constants
from fp.config import FoulPlayConfig
from fp.format_spec import FormatSpec
from fp.modes.random_battle import RandomBattleMode
from fp.data.sets import (
    PredictedPokemonSet,
    PokemonSet,
    PokemonMoveset,
)

from fp.battle.state import Battle
from fp.battle.state import Pokemon
from fp.battle.state import Move

from fp.search.helpers import populate_pkmn_from_set
from fp.search.random_battles import (
    get_all_remaining_sets_for_revealed_pkmn,
    prepare_random_battles,
    sample_randombattle_pokemon,
    populate_randombattle_unrevealed_pkmn,
    _more_than_1_species,
    _more_than_3_pokemon_weak_to_a_given_typing,
    _more_than_2_pokemon_of_any_type,
    _more_than_1_pokemon_with_4x_weakness,
)


def make_set(
    moves,
    level=100,
    ability="static",
    item="leftovers",
    tera_type=None,
    count=1,
):
    return PredictedPokemonSet(
        pkmn_set=PokemonSet(
            ability=ability,
            item=item,
            nature="serious",
            evs=(85,) * 6,
            count=count,
            level=level,
            tera_type=tera_type,
        ),
        pkmn_moveset=PokemonMoveset(moves=moves),
    )


class TestTeamLegalityConstraints:
    def test_more_than_1_species_true_for_duplicate_pokemon(self):
        team = [Pokemon("pikachu", 100), Pokemon("pikachu", 100)]
        assert _more_than_1_species(team) is True

    def test_more_than_1_species_true_for_cosmetic_forme_of_same_species(self):
        # basculinbluestriped has baseSpecies basculin so they count as one species
        team = [Pokemon("basculin", 100), Pokemon("basculinbluestriped", 100)]
        assert _more_than_1_species(team) is True

    def test_more_than_1_species_false_for_distinct_species(self):
        team = [Pokemon("pikachu", 100), Pokemon("charizard", 100)]
        assert _more_than_1_species(team) is False

    def test_more_than_3_pokemon_weak_to_a_given_typing_true_with_4_fire_weak(self):
        team = [
            Pokemon("abomasnow", 100),
            Pokemon("ferrothorn", 100),
            Pokemon("scizor", 100),
            Pokemon("kartana", 100),
        ]
        assert _more_than_3_pokemon_weak_to_a_given_typing(team) is True

    def test_more_than_3_pokemon_weak_to_a_given_typing_false_with_3_fire_weak(self):
        team = [
            Pokemon("abomasnow", 100),
            Pokemon("ferrothorn", 100),
            Pokemon("scizor", 100),
        ]
        assert _more_than_3_pokemon_weak_to_a_given_typing(team) is False

    def test_more_than_2_pokemon_of_any_type_true_with_3_water_types(self):
        team = [
            Pokemon("squirtle", 100),
            Pokemon("totodile", 100),
            Pokemon("vaporeon", 100),
        ]
        assert _more_than_2_pokemon_of_any_type(team) is True

    def test_more_than_2_pokemon_of_any_type_false_with_2_water_types(self):
        team = [
            Pokemon("squirtle", 100),
            Pokemon("totodile", 100),
            Pokemon("growlithe", 100),
        ]
        assert _more_than_2_pokemon_of_any_type(team) is False

    def test_more_than_1_pokemon_with_4x_weakness_true_when_shared(self):
        # abomasnow and ferrothorn are both 4x weak to fire
        team = [Pokemon("abomasnow", 100), Pokemon("ferrothorn", 100)]
        assert _more_than_1_pokemon_with_4x_weakness(team) is True

    def test_more_than_1_pokemon_with_4x_weakness_false_when_not_shared(self):
        team = [Pokemon("abomasnow", 100), Pokemon("squirtle", 100)]
        assert _more_than_1_pokemon_with_4x_weakness(team) is False


class TestGetAllRemainingSetsForRevealedPkmn:
    @pytest.fixture(autouse=True)
    def _setup(self):
        FoulPlayConfig.pokemon_format = "gen9randombattle"
        self.battle = Battle(None)
        self.battle.generation = "gen9"
        self.battle.mode = RandomBattleMode()

        self.pikachu_set_1 = make_set(
            ["thunderbolt", "surf", "voltswitch", "irontail"], level=88
        )
        self.pikachu_set_2 = make_set(
            ["thunderbolt", "knockoff", "voltswitch", "fakeout"],
            level=88,
            item="lightball",
        )
        self.growlithe_set = make_set(
            ["flareblitz", "willowisp", "morningsun", "protect"],
            level=90,
            ability="intimidate",
        )
        self.battle.mode.datasets.pkmn_sets = {
            "pikachu": [self.pikachu_set_1, self.pikachu_set_2],
            "growlithe": [self.growlithe_set],
        }

    def test_returns_all_sets_keyed_by_name_for_active_and_reserves(self):
        self.battle.opponent.active = Pokemon("pikachu", 88)
        self.battle.opponent.reserve = [Pokemon("growlithe", 90)]

        random.seed(0)
        ret = get_all_remaining_sets_for_revealed_pkmn(self.battle)

        assert {"pikachu", "growlithe"} == set(ret.keys())
        # shuffled, so compare without order
        assert 2 == len(ret["pikachu"])
        assert self.pikachu_set_1 in ret["pikachu"]
        assert self.pikachu_set_2 in ret["pikachu"]
        assert [self.growlithe_set] == ret["growlithe"]

    def test_revealed_move_filters_out_sets_without_that_move(self):
        self.battle.opponent.active = Pokemon("pikachu", 88)
        self.battle.opponent.active.add_move("surf")

        random.seed(0)
        ret = get_all_remaining_sets_for_revealed_pkmn(self.battle)

        assert [self.pikachu_set_1] == ret["pikachu"]


class TestSampleRandombattlePokemon:
    @pytest.fixture(autouse=True)
    def _setup(self):
        FoulPlayConfig.pokemon_format = "gen9randombattle"
        self.battle = Battle(None)
        self.battle.generation = "gen9"
        self.battle.mode = RandomBattleMode()
        self.datasets = self.battle.mode.datasets

    def test_returns_pokemon_with_set_applied(self):
        self.datasets.pkmn_sets = {
            "growlithe": [
                make_set(
                    ["flareblitz", "willowisp", "morningsun", "protect"],
                    level=90,
                    ability="intimidate",
                    item="eviolite",
                )
            ],
        }

        random.seed(0)
        pkmn = sample_randombattle_pokemon([Pokemon("squirtle", 80)], self.datasets)

        assert "growlithe" == pkmn.name
        assert 90 == pkmn.level
        assert "intimidate" == pkmn.ability
        assert "eviolite" == pkmn.item
        assert [
            Move("flareblitz"),
            Move("willowisp"),
            Move("morningsun"),
            Move("protect"),
        ] == pkmn.moves

    def test_does_not_sample_pokemon_already_on_the_team(self):
        self.datasets.pkmn_sets = {
            "pikachu": [
                make_set(["thunderbolt", "surf", "voltswitch", "irontail"], level=88)
            ],
            "growlithe": [
                make_set(["flareblitz", "willowisp", "morningsun", "protect"], level=90)
            ],
        }
        existing = [Pokemon("pikachu", 88)]

        random.seed(0)
        pkmn = sample_randombattle_pokemon(existing, self.datasets)

        assert "growlithe" == pkmn.name

    def test_rejects_candidate_that_would_give_3_pokemon_of_the_same_type(self):
        # vaporeon would be a third water type so growlithe must be chosen
        self.datasets.pkmn_sets = {
            "vaporeon": [
                make_set(
                    ["scald", "protect", "wish", "haze"],
                    level=85,
                    ability="waterabsorb",
                )
            ],
            "growlithe": [
                make_set(
                    ["flareblitz", "willowisp", "morningsun", "protect"],
                    level=90,
                    ability="intimidate",
                )
            ],
        }
        existing = [Pokemon("squirtle", 80), Pokemon("totodile", 80)]

        random.seed(1)
        pkmn = sample_randombattle_pokemon(existing, self.datasets)

        assert "growlithe" == pkmn.name


class TestPopulateRandombattleUnrevealedPkmn:
    @pytest.fixture(autouse=True)
    def _setup(self):
        FoulPlayConfig.pokemon_format = "gen9randombattle"
        self.battle = Battle(None)
        self.battle.generation = "gen9"
        self.battle.mode = RandomBattleMode()

    def test_fills_opponent_side_to_6_pokemon(self):
        self.battle.mode.datasets.pkmn_sets = {
            "vaporeon": [make_set(["scald", "protect", "wish", "haze"], level=85)],
            "garchomp": [
                make_set(
                    ["earthquake", "outrage", "swordsdance", "stoneedge"], level=78
                )
            ],
            "metagross": [
                make_set(
                    ["meteormash", "earthquake", "agility", "psychicfangs"], level=82
                )
            ],
            "sylveon": [
                make_set(["hypervoice", "calmmind", "wish", "protect"], level=86)
            ],
            "snorlax": [
                make_set(["bodyslam", "curse", "rest", "earthquake"], level=85)
            ],
        }
        self.battle.opponent.active = Pokemon("pikachu", 88)
        self.battle.opponent.reserve = [Pokemon("growlithe", 90)]

        random.seed(3)
        populate_randombattle_unrevealed_pkmn(self.battle)

        assert 5 == len(self.battle.opponent.reserve)
        names = [self.battle.opponent.active.name] + [
            p.name for p in self.battle.opponent.reserve
        ]
        assert 6 == len(set(names))
        # sampled pokemon come fully populated, the revealed growlithe is untouched
        assert [] == self.battle.opponent.reserve[0].moves
        for pkmn in self.battle.opponent.reserve[1:]:
            assert 4 == len(pkmn.moves)

    def test_early_return_when_6_pokemon_already_revealed(self):
        # datasets are uninitialized: sampling would blow up on the empty
        # pkmn_sets dict, so returning cleanly proves they were not touched
        self.battle.opponent.active = Pokemon("pikachu", 88)
        self.battle.opponent.reserve = [
            Pokemon("growlithe", 90),
            Pokemon("squirtle", 80),
            Pokemon("garchomp", 78),
            Pokemon("snorlax", 85),
            Pokemon("sylveon", 86),
        ]

        populate_randombattle_unrevealed_pkmn(self.battle)

        assert 5 == len(self.battle.opponent.reserve)
        assert "uninitialized" == self.battle.mode.datasets.pkmn_mode


class TestPrepareRandomBattles:
    @pytest.fixture(autouse=True)
    def _setup(self):
        FoulPlayConfig.pokemon_format = "gen9randombattle"
        self.battle = Battle(None)
        self.battle.generation = "gen9"
        self.battle.mode = RandomBattleMode()
        self.battle.mode.datasets.initialize(
            FormatSpec.from_format_string("gen9randombattle")
        )

    def _pkmn_from_cache(self, name):
        # levels in randombattles are fixed per-pokemon: take it from the data
        level = self.battle.mode.datasets.pkmn_sets[name][0].pkmn_set.level
        return Pokemon(name, level)

    def test_returns_num_battles_copies_with_opponent_filled_out(self):
        self.battle.opponent.active = self._pkmn_from_cache("gyarados")
        self.battle.opponent.active.add_move("waterfall")

        random.seed(4)
        sampled = prepare_random_battles(self.battle, 2)

        assert 2 == len(sampled)
        for battle_copy, likelihood in sampled:
            assert battle_copy is not self.battle
            assert 1 / 2 == likelihood

            active = battle_copy.opponent.active
            assert "gyarados" == active.name
            assert 4 == len(active.moves)
            # the revealed move must be part of the chosen set
            assert Move("waterfall") in active.moves
            assert active.ability is not None
            assert constants.UNKNOWN_ITEM != active.item

            assert 5 == len(battle_copy.opponent.reserve)
            for pkmn in battle_copy.opponent.reserve:
                assert 4 == len(pkmn.moves)

        # the original battle is untouched
        assert [] == self.battle.opponent.reserve
        assert [Move("waterfall")] == self.battle.opponent.active.moves

    def test_revealed_reserve_is_populated_but_fainted_reserve_is_not(self):
        self.battle.opponent.active = self._pkmn_from_cache("gyarados")
        alomomola = self._pkmn_from_cache("alomomola")
        fainted = self._pkmn_from_cache("skarmory")
        fainted.hp = 0
        fainted.fainted = True
        self.battle.opponent.reserve = [alomomola, fainted]

        random.seed(5)
        sampled = prepare_random_battles(self.battle, 2)

        for battle_copy, _ in sampled:
            reserve_by_name = {p.name: p for p in battle_copy.opponent.reserve}
            # fainted pokemon still counts towards the 6 revealed pokemon
            assert 5 == len(battle_copy.opponent.reserve)
            assert 4 == len(reserve_by_name["alomomola"].moves)
            # fainted pokemon are skipped when populating sets
            assert [] == reserve_by_name["skarmory"].moves


class TestPopulatePkmnFromSet:
    @pytest.fixture(autouse=True)
    def _setup(self):
        FoulPlayConfig.pokemon_format = "gen9randombattle"
        self.pkmn = Pokemon("pikachu", 88)
        self.set = make_set(
            ["thunderbolt", "surf", "voltswitch", "irontail"],
            level=88,
            ability="static",
            item="lightball",
            tera_type="electric",
        )

    def test_applies_ability_item_moves_spread_and_tera(self):
        populate_pkmn_from_set(self.pkmn, self.set)

        assert "static" == self.pkmn.ability
        assert "lightball" == self.pkmn.item
        assert [
            Move("thunderbolt"),
            Move("surf"),
            Move("voltswitch"),
            Move("irontail"),
        ] == self.pkmn.moves
        assert "serious" == self.pkmn.nature
        assert [85] * 6 == self.pkmn.evs
        assert "electric" == self.pkmn.tera_type

    def test_known_ability_and_item_are_preserved(self):
        self.pkmn.ability = "lightningrod"
        self.pkmn.item = "focussash"

        populate_pkmn_from_set(self.pkmn, self.set)

        assert "lightningrod" == self.pkmn.ability
        assert "focussash" == self.pkmn.item

    def test_known_move_pp_is_copied_onto_the_new_move(self):
        known_move = self.pkmn.add_move("thunderbolt")
        known_move.current_pp = 3

        populate_pkmn_from_set(self.pkmn, self.set)

        assert 3 == self.pkmn.get_move("thunderbolt").current_pp
        assert (
            self.pkmn.get_move("surf").max_pp == self.pkmn.get_move("surf").current_pp
        )

    def test_existing_tera_type_is_not_overwritten(self):
        self.pkmn.tera_type = "flying"

        populate_pkmn_from_set(self.pkmn, self.set)

        assert "flying" == self.pkmn.tera_type

    def test_source_is_included_in_the_logged_set(self, caplog):
        caplog.set_level(logging.INFO, logger="fp.search.helpers")

        populate_pkmn_from_set(self.pkmn, self.set, source="team_datasets")

        assert "source=team_datasets" in caplog.text
