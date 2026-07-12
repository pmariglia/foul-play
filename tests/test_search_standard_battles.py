import logging
import random

import pytest

from fp import constants
from fp.battle.state import Battle, LastUsedMove, Pokemon
from fp.data.sets import (
    MOVES_STRING,
    PokemonMoveset,
    PokemonSet,
    PredictedPokemonSet,
    RAW_COUNT,
    TEAMMATES,
)
from fp.modes.standard_battle import StandardBattleMode
from fp.search.standard_battles import (
    _sample_pokemon,
    adjust_probabilities_for_sampling,
    choice_item,
    get_filtered_sets,
    physical_boosting_move,
    pokemon_guaranteed_move,
    populate_standardbattle_unrevealed_pkmn,
    predict_team_likelihood,
    prepare_battles,
    sample_pokemon_moveset_with_known_pkmn_set,
    set_most_likely_hidden_power,
    smogon_set_makes_sense,
    special_boosting_move,
)


def make_pkmn_set(
    ability="levitate",
    item="leftovers",
    nature="serious",
    evs=(0, 0, 0, 0, 0, 0),
    count=1,
    tera_type=None,
):
    return PokemonSet(
        ability=ability,
        item=item,
        nature=nature,
        evs=evs,
        count=count,
        tera_type=tera_type,
    )


def make_predicted_set(moves, **kwargs):
    return PredictedPokemonSet(
        pkmn_set=make_pkmn_set(**kwargs),
        pkmn_moveset=PokemonMoveset(moves=tuple(moves)),
    )


def make_standard_battle():
    battle = Battle(None)
    battle.generation = "gen9"
    battle.pokemon_format = "gen9ou"
    battle.mode = StandardBattleMode()
    return battle


class TestPhysicalBoostingMove:
    def test_allows_swordsdance_with_mostly_physical_moves(self):
        # recover is the single allowed non-physical move besides the boosting move
        pkmn_set = make_predicted_set(
            ["swordsdance", "earthquake", "stoneedge", "recover"]
        )
        assert physical_boosting_move("swordsdance", pkmn_set)

    def test_rejects_swordsdance_with_more_than_one_other_non_physical_move(self):
        pkmn_set = make_predicted_set(
            ["swordsdance", "protect", "recover", "earthquake"]
        )
        assert not physical_boosting_move("swordsdance", pkmn_set)

    def test_rejects_boosting_move_with_choice_item(self):
        pkmn_set = make_predicted_set(
            ["swordsdance", "earthquake", "stoneedge", "outrage"],
            item="choiceband",
        )
        assert not physical_boosting_move("swordsdance", pkmn_set)


class TestSpecialBoostingMove:
    def test_allows_nastyplot_with_mostly_special_moves(self):
        pkmn_set = make_predicted_set(
            ["nastyplot", "shadowball", "thunderbolt", "recover"]
        )
        assert special_boosting_move("nastyplot", pkmn_set)

    def test_rejects_nastyplot_with_more_than_one_other_non_special_move(self):
        pkmn_set = make_predicted_set(["nastyplot", "protect", "recover", "surf"])
        assert not special_boosting_move("nastyplot", pkmn_set)

    def test_rejects_nastyplot_with_choice_item(self):
        pkmn_set = make_predicted_set(
            ["nastyplot", "shadowball", "thunderbolt", "surf"],
            item="choicespecs",
        )
        assert not special_boosting_move("nastyplot", pkmn_set)


class TestChoiceItem:
    def test_choiceband_allows_at_most_one_illogical_move(self):
        all_physical = make_predicted_set(
            ["earthquake", "stoneedge", "outrage", "dragonclaw"], item="choiceband"
        )
        assert choice_item(all_physical)

        one_status = make_predicted_set(
            ["earthquake", "stoneedge", "outrage", "toxic"], item="choiceband"
        )
        assert choice_item(one_status)

        two_status = make_predicted_set(
            ["earthquake", "stoneedge", "toxic", "protect"], item="choiceband"
        )
        assert not choice_item(two_status)

    def test_choicespecs_counts_physical_moves_as_illogical(self):
        pkmn_set = make_predicted_set(
            ["shadowball", "thunderbolt", "earthquake", "stoneedge"],
            item="choicespecs",
        )
        assert not choice_item(pkmn_set)

    def test_choicescarf_allows_both_attacking_categories(self):
        pkmn_set = make_predicted_set(
            ["shadowball", "earthquake", "thunderbolt", "stoneedge"],
            item="choicescarf",
        )
        assert choice_item(pkmn_set)

    def test_pivot_and_trick_moves_are_never_illogical(self):
        # uturn is physical and trick is status but both are whitelisted on specs
        pkmn_set = make_predicted_set(
            ["trick", "uturn", "shadowball", "thunderbolt"], item="choicespecs"
        )
        assert choice_item(pkmn_set)

    def test_non_choice_item_raises_valueerror(self):
        pkmn_set = make_predicted_set(["tackle"], item="leftovers")
        with pytest.raises(ValueError):
            choice_item(pkmn_set)


class TestSmogonSetMakesSense:
    def test_toxicorb_requires_a_synergistic_ability(self):
        bad = make_predicted_set(["earthquake"], item="toxicorb", ability="intimidate")
        assert not smogon_set_makes_sense(bad)

        good = make_predicted_set(["earthquake"], item="toxicorb", ability="poisonheal")
        assert smogon_set_makes_sense(good)

    def test_poisonheal_requires_toxicorb(self):
        pkmn_set = make_predicted_set(
            ["earthquake"], item="leftovers", ability="poisonheal"
        )
        assert not smogon_set_makes_sense(pkmn_set)

    def test_flameorb_requires_a_synergistic_ability(self):
        bad = make_predicted_set(["facade"], item="flameorb", ability="intimidate")
        assert not smogon_set_makes_sense(bad)

        good = make_predicted_set(["facade"], item="flameorb", ability="guts")
        assert smogon_set_makes_sense(good)

    def test_assaultvest_rejects_status_moves_unless_klutz(self):
        bad = make_predicted_set(
            ["earthquake", "toxic"], item="assaultvest", ability="intimidate"
        )
        assert not smogon_set_makes_sense(bad)

        klutz = make_predicted_set(
            ["earthquake", "toxic"], item="assaultvest", ability="klutz"
        )
        assert smogon_set_makes_sense(klutz)

    def test_protect_with_choice_item_is_rejected(self):
        pkmn_set = make_predicted_set(
            ["protect", "earthquake", "stoneedge", "outrage"], item="choiceband"
        )
        assert not smogon_set_makes_sense(pkmn_set)

    def test_bulkup_rejects_choice_item_spa_evs_and_spa_boosting_nature(self):
        choice = make_predicted_set(
            ["bulkup", "earthquake", "stoneedge", "outrage"], item="choiceband"
        )
        assert not smogon_set_makes_sense(choice)

        spa_evs = make_predicted_set(
            ["bulkup", "earthquake"], evs=(252, 0, 0, 4, 0, 252)
        )
        assert not smogon_set_makes_sense(spa_evs)

        spa_nature = make_predicted_set(["bulkup", "earthquake"], nature="modest")
        assert not smogon_set_makes_sense(spa_nature)

        good = make_predicted_set(
            ["bulkup", "earthquake"], nature="adamant", evs=(252, 252, 0, 0, 4, 0)
        )
        assert smogon_set_makes_sense(good)

    def test_calmmind_rejects_choice_item_atk_evs_and_atk_boosting_nature(self):
        choice = make_predicted_set(
            ["calmmind", "shadowball", "thunderbolt", "surf"], item="choicespecs"
        )
        assert not smogon_set_makes_sense(choice)

        atk_evs = make_predicted_set(
            ["calmmind", "shadowball"], evs=(252, 4, 0, 0, 0, 252)
        )
        assert not smogon_set_makes_sense(atk_evs)

        atk_nature = make_predicted_set(["calmmind", "shadowball"], nature="adamant")
        assert not smogon_set_makes_sense(atk_nature)

        good = make_predicted_set(
            ["calmmind", "shadowball"], nature="modest", evs=(252, 0, 0, 252, 4, 0)
        )
        assert smogon_set_makes_sense(good)

    def test_trick_requires_a_trickable_item(self):
        bad = make_predicted_set(
            ["trick", "shadowball", "thunderbolt", "surf"], item="leftovers"
        )
        assert not smogon_set_makes_sense(bad)

        good = make_predicted_set(
            ["trick", "shadowball", "thunderbolt", "surf"], item="choicescarf"
        )
        assert smogon_set_makes_sense(good)


class TestAdjustProbabilitiesForSampling:
    def test_exact_math_for_rate_list(self):
        adjusted = adjust_probabilities_for_sampling(
            [("earthquake", 0.75), ("stoneedge", 0.0)], num_moves=4
        )
        assert adjusted[0][0] == "earthquake"
        assert adjusted[0][1] == pytest.approx(1 - 0.25 ** (1 / 4))
        assert adjusted[1] == ("stoneedge", 0.0)

    def test_default_num_moves_is_four_and_rate_one_stays_one(self):
        adjusted = adjust_probabilities_for_sampling([("tackle", 0.19)], num_moves=2)
        assert adjusted[0][1] == pytest.approx(0.1)

        adjusted = adjust_probabilities_for_sampling([("tackle", 1.0)])
        assert adjusted[0][1] == pytest.approx(1.0)


class TestPredictTeamLikelihood:
    @pytest.fixture(autouse=True)
    def _setup(self):
        self.all_pkmn_counts = {
            "pikachu": {
                RAW_COUNT: 100,
                TEAMMATES: {"charizard": 80, "blastoise": 20},
            },
            "charizard": {RAW_COUNT: 200, TEAMMATES: {"pikachu": 80}},
            "blastoise": {RAW_COUNT: 50, TEAMMATES: {}},
        }

    def test_single_revealed_pokemon_gives_sorted_teammate_rates(self):
        likelihoods = predict_team_likelihood(["pikachu"], self.all_pkmn_counts)
        assert list(likelihoods.keys()) == ["charizard", "blastoise"]
        assert likelihoods["charizard"] == pytest.approx(0.8)
        assert likelihoods["blastoise"] == pytest.approx(0.2)

    def test_revealed_pokemon_are_excluded_and_missing_co_counts_are_zero(self):
        likelihoods = predict_team_likelihood(
            ["pikachu", "charizard"], self.all_pkmn_counts
        )
        # blastoise never appears as a teammate of charizard so that term is 0
        assert list(likelihoods.keys()) == ["blastoise"]
        assert likelihoods["blastoise"] == pytest.approx((20 / 100 + 0 / 200) / 2)

    def test_no_revealed_pokemon_raises_zerodivisionerror(self):
        # pins current behavior: an empty revealed list divides by zero
        with pytest.raises(ZeroDivisionError):
            predict_team_likelihood([], self.all_pkmn_counts)


class TestGetFilteredSets:
    def test_filters_sets_that_fail_smogon_set_makes_sense_with_known_moves(self):
        pkmn = Pokemon("gengar", 100)
        pkmn.add_move("protect")

        choice_set = make_pkmn_set(item="choicespecs")
        leftovers_set = make_pkmn_set(item="leftovers")

        filtered = get_filtered_sets(pkmn, [choice_set, leftovers_set])
        assert filtered == [leftovers_set]

    def test_all_sets_kept_when_no_moves_are_revealed(self):
        pkmn = Pokemon("gengar", 100)
        remaining = [make_pkmn_set(item="choicespecs"), make_pkmn_set()]
        assert get_filtered_sets(pkmn, remaining) == remaining


class TestSamplePokemonMovesetWithKnownPkmnSet:
    @pytest.fixture(autouse=True)
    def _setup(self):
        self.mode = StandardBattleMode()

    def test_four_known_moves_short_circuits(self):
        pkmn = Pokemon("azelf", 100)
        for mv in ["psychic", "stealthrock", "explosion", "flamethrower"]:
            pkmn.add_move(mv)

        moves = sample_pokemon_moveset_with_known_pkmn_set(
            pkmn, make_pkmn_set(), self.mode
        )
        assert moves == ["psychic", "stealthrock", "explosion", "flamethrower"]

    def test_team_dataset_moveset_completes_known_moves(self):
        self.mode.team_datasets.raw_pkmn_moves = {
            "azelf": [
                PokemonMoveset(
                    moves=("knockoff", "psychic", "stealthrock", "explosion"), count=5
                )
            ]
        }
        pkmn = Pokemon("azelf", 100)
        pkmn.add_move("knockoff")

        random.seed(0)
        moves = sample_pokemon_moveset_with_known_pkmn_set(
            pkmn, make_pkmn_set(), self.mode
        )
        assert moves == ["knockoff", "psychic", "stealthrock", "explosion"]

    def test_movesets_with_more_moves_are_weighted_higher(self):
        # a 4-move moveset is weighted count*3 while a 2-move moveset is weighted count
        self.mode.team_datasets.raw_pkmn_moves = {
            "azelf": [
                PokemonMoveset(moves=("psychic", "grassknot"), count=1),
                PokemonMoveset(
                    moves=("psychic", "stealthrock", "explosion", "flamethrower"),
                    count=1,
                ),
            ]
        }

        random.seed(0)
        four_move_count = 0
        two_move_count = 0
        for _ in range(200):
            pkmn = Pokemon("azelf", 100)
            pkmn.add_move("psychic")
            moves = sample_pokemon_moveset_with_known_pkmn_set(
                pkmn, make_pkmn_set(), self.mode
            )
            if "explosion" in moves:
                four_move_count += 1
            else:
                assert moves == ["psychic", "grassknot"]
                two_move_count += 1

        assert two_move_count > 0
        assert four_move_count > two_move_count

    def test_smogon_move_that_invalidates_set_is_discarded(self):
        # protect can never coexist with a choice item so it gets popped after sampling
        self.mode.smogon_sets.raw_pkmn_sets = {
            "garchomp": {
                MOVES_STRING: [
                    ("protect", 1.0),
                    ("earthquake", 1.0),
                    ("stoneedge", 1.0),
                    ("outrage", 1.0),
                    ("dragonclaw", 1.0),
                ]
            }
        }
        pkmn = Pokemon("garchomp", 100)
        pkmn_set = make_pkmn_set(
            item="choiceband", nature="adamant", evs=(0, 252, 0, 0, 4, 252)
        )

        random.seed(0)
        moves = sample_pokemon_moveset_with_known_pkmn_set(pkmn, pkmn_set, self.mode)
        assert moves == ["earthquake", "stoneedge", "outrage", "dragonclaw"]


class TestSetMostLikelyHiddenPower:
    @pytest.fixture(autouse=True)
    def _setup(self):
        self.mode = StandardBattleMode()
        self.mode.smogon_sets.raw_pkmn_sets = {
            "gengar": {
                MOVES_STRING: [
                    ("shadowball", 0.9),
                    ("hiddenpowerice60", 0.5),
                    ("hiddenpowerfire60", 0.4),
                ]
            }
        }

    def test_hiddenpower_replaced_by_most_used_possibility(self):
        pkmn = Pokemon("gengar", 100)
        pkmn.add_move("hiddenpower")

        set_most_likely_hidden_power(pkmn, self.mode)
        assert [m.name for m in pkmn.moves] == ["hiddenpowerice60"]

    def test_hiddenpower_possibilities_restrict_the_choice(self):
        pkmn = Pokemon("gengar", 100)
        pkmn.add_move("hiddenpower")
        pkmn.hidden_power_possibilities = {"fire"}

        set_most_likely_hidden_power(pkmn, self.mode)
        assert [m.name for m in pkmn.moves] == ["hiddenpowerfire60"]

    def test_no_op_when_hiddenpower_not_known(self):
        pkmn = Pokemon("gengar", 100)
        pkmn.add_move("shadowball")

        set_most_likely_hidden_power(pkmn, self.mode)
        assert [m.name for m in pkmn.moves] == ["shadowball"]


class TestPokemonGuaranteedMove:
    def test_required_move_from_pokedex_is_added(self):
        pkmn = Pokemon("keldeoresolute", 100)
        pkmn.add_move("surf")

        pokemon_guaranteed_move(pkmn)
        assert [m.name for m in pkmn.moves] == ["surf", "secretsword"]

    def test_required_move_not_duplicated_and_not_added_with_four_moves(self):
        pkmn = Pokemon("keldeoresolute", 100)
        pkmn.add_move("secretsword")
        pokemon_guaranteed_move(pkmn)
        assert [m.name for m in pkmn.moves] == ["secretsword"]

        pkmn = Pokemon("keldeoresolute", 100)
        for mv in ["surf", "hydropump", "calmmind", "substitute"]:
            pkmn.add_move(mv)
        pokemon_guaranteed_move(pkmn)
        assert len(pkmn.moves) == 4
        assert pkmn.get_move("secretsword") is None


class TestSamplePokemonCascade:
    @pytest.fixture(autouse=True)
    def _setup(self):
        self.mode = StandardBattleMode()

    def test_full_team_set_populates_pokemon(self):
        self.mode.team_datasets.pkmn_sets = {
            "gengar": [
                make_predicted_set(
                    ["shadowball", "sludgebomb", "substitute", "protect"],
                    ability="cursedbody",
                    item="lifeorb",
                    nature="timid",
                    evs=(0, 0, 0, 252, 4, 252),
                    tera_type="ghost",
                )
            ]
        }
        pkmn = Pokemon("gengar", 100)

        random.seed(0)
        _sample_pokemon(pkmn, self.mode)

        assert [m.name for m in pkmn.moves] == [
            "shadowball",
            "sludgebomb",
            "substitute",
            "protect",
        ]
        assert pkmn.ability == "cursedbody"
        assert pkmn.item == "lifeorb"
        assert pkmn.nature == "timid"
        assert pkmn.evs == [0, 0, 0, 252, 4, 252]
        assert pkmn.tera_type == "ghost"

    def test_invalidated_team_moveset_falls_back_to_partial_path(self):
        # the stored moveset does not contain the revealed move so
        # get_all_remaining_sets finds nothing and only the traits are reused
        self.mode.team_datasets.pkmn_sets = {
            "azelf": [
                make_predicted_set(
                    ["psychic", "flamethrower", "stealthrock", "explosion"],
                    ability="levitate",
                    item="focussash",
                    nature="jolly",
                    evs=(0, 252, 0, 0, 4, 252),
                )
            ]
        }
        self.mode.team_datasets.raw_pkmn_moves = {
            "azelf": [
                PokemonMoveset(
                    moves=("knockoff", "psychic", "stealthrock", "explosion"), count=5
                )
            ]
        }
        pkmn = Pokemon("azelf", 100)
        pkmn.add_move("knockoff")

        random.seed(0)
        _sample_pokemon(pkmn, self.mode)

        assert [m.name for m in pkmn.moves] == [
            "knockoff",
            "psychic",
            "stealthrock",
            "explosion",
        ]
        assert pkmn.item == "focussash"
        assert pkmn.ability == "levitate"

    def test_empty_team_datasets_falls_back_to_smogon_path(self):
        self.mode.smogon_sets.pkmn_sets = {
            "heatran": [
                make_pkmn_set(
                    ability="flashfire",
                    item="leftovers",
                    nature="calm",
                    evs=(252, 0, 0, 0, 208, 48),
                    count=10,
                    tera_type="grass",
                )
            ]
        }
        self.mode.smogon_sets.raw_pkmn_sets = {
            "heatran": {
                MOVES_STRING: [
                    ("magmastorm", 1.0),
                    ("earthpower", 1.0),
                    ("taunt", 1.0),
                    ("stealthrock", 1.0),
                    ("protect", 1.0),
                ]
            }
        }
        pkmn = Pokemon("heatran", 100)

        random.seed(0)
        _sample_pokemon(pkmn, self.mode)

        assert [m.name for m in pkmn.moves] == [
            "magmastorm",
            "earthpower",
            "taunt",
            "stealthrock",
        ]
        assert pkmn.ability == "flashfire"
        assert pkmn.item == "leftovers"
        assert pkmn.nature == "calm"
        assert pkmn.tera_type == "grass"

    def test_nothing_available_leaves_pokemon_unsampled(self, caplog):
        pkmn = Pokemon("snorlax", 100)

        with caplog.at_level(logging.WARNING):
            _sample_pokemon(pkmn, self.mode)

        assert "Could not sample snorlax" in caplog.text
        assert pkmn.moves == []
        assert pkmn.item == constants.UNKNOWN_ITEM
        assert pkmn.ability is None


class TestPopulateStandardBattleUnrevealedPkmn:
    @pytest.fixture(autouse=True)
    def _setup(self):
        self.battle = make_standard_battle()
        self.battle.opponent.active = Pokemon("pikachu", 100)

        self.candidates = [
            "charizard",
            "blastoise",
            "venusaur",
            "snorlax",
            "gengar",
            "dragonite",
        ]
        all_names = ["pikachu"] + self.candidates
        all_pkmn_counts = {}
        for name in all_names:
            all_pkmn_counts[name] = {
                RAW_COUNT: 100,
                TEAMMATES: {n: 50 for n in all_names if n != name},
            }
        self.battle.mode.smogon_sets.all_pkmn_counts = all_pkmn_counts
        self.battle.mode.smogon_sets.pkmn_sets = {
            name: [make_pkmn_set(ability="pressure", item="leftovers")]
            for name in self.candidates
        }
        self.battle.mode.smogon_sets.raw_pkmn_sets = {
            name: {
                MOVES_STRING: [
                    ("tackle", 1.0),
                    ("protect", 1.0),
                    ("toxic", 1.0),
                    ("substitute", 1.0),
                ]
            }
            for name in self.candidates
        }

    def test_fills_opponent_side_to_six_unique_pokemon(self):
        random.seed(0)
        populate_standardbattle_unrevealed_pkmn(self.battle)

        reserve_names = [p.name for p in self.battle.opponent.reserve]
        assert len(reserve_names) == 5
        assert len(set(reserve_names)) == 5
        assert "pikachu" not in reserve_names
        assert set(reserve_names).issubset(set(self.candidates))
        for pkmn in self.battle.opponent.reserve:
            assert pkmn.item == "leftovers"
            assert len(pkmn.moves) == 4

    def test_early_return_when_six_pokemon_are_revealed(self):
        self.battle.opponent.reserve = [Pokemon(n, 100) for n in self.candidates[:5]]
        # empty the counts to prove that sampling never happens
        self.battle.mode.smogon_sets.all_pkmn_counts = {}

        populate_standardbattle_unrevealed_pkmn(self.battle)
        assert len(self.battle.opponent.reserve) == 5


class TestPrepareBattles:
    @pytest.fixture(autouse=True)
    def _setup(self):
        self.battle = make_standard_battle()
        self.battle.opponent.active = Pokemon("gengar", 100)
        self.battle.opponent.reserve = [Pokemon("azelf", 100)]
        self.battle.mode.team_datasets.pkmn_sets = {
            "gengar": [
                make_predicted_set(
                    ["shadowball", "sludgebomb", "focusblast", "trick"],
                    ability="cursedbody",
                    item="choicescarf",
                    nature="timid",
                    evs=(0, 0, 0, 252, 4, 252),
                )
            ],
            "azelf": [
                make_predicted_set(
                    ["psychic", "stealthrock", "explosion", "knockoff"],
                    ability="levitate",
                    item="focussash",
                    nature="jolly",
                    evs=(0, 252, 0, 0, 4, 252),
                )
            ],
        }

    def test_returns_num_battles_pairs_with_equal_likelihood(self):
        random.seed(0)
        sampled = prepare_battles(self.battle, 3)

        assert len(sampled) == 3
        for battle_copy, likelihood in sampled:
            assert battle_copy is not self.battle
            assert likelihood == pytest.approx(1 / 3)

    def test_opponent_pokemon_receive_sets_and_original_is_untouched(self):
        random.seed(0)
        sampled = prepare_battles(self.battle, 2)

        for battle_copy, _ in sampled:
            active = battle_copy.opponent.active
            assert active.item == "choicescarf"
            assert active.ability == "cursedbody"
            assert len(active.moves) == 4

            reserve_pkmn = battle_copy.opponent.reserve[0]
            assert reserve_pkmn.item == "focussash"
            assert len(reserve_pkmn.moves) == 4

            # gen9 has team preview so unrevealed pokemon are not filled in here
            assert len(battle_copy.opponent.reserve) == 1

        assert self.battle.opponent.active.item == constants.UNKNOWN_ITEM
        assert self.battle.opponent.active.moves == []

    def test_choice_locked_moves_are_disabled_after_sampling(self):
        self.battle.opponent.last_used_move = LastUsedMove("gengar", "shadowball", 0)

        random.seed(0)
        sampled = prepare_battles(self.battle, 2)

        for battle_copy, _ in sampled:
            for mv in battle_copy.opponent.active.moves:
                if mv.name == "shadowball":
                    assert not mv.disabled
                else:
                    assert mv.disabled

    def test_fainted_reserve_pokemon_are_not_sampled(self):
        self.battle.opponent.reserve[0].hp = 0

        random.seed(0)
        sampled = prepare_battles(self.battle, 1)

        battle_copy, _ = sampled[0]
        fainted = battle_copy.opponent.reserve[0]
        assert fainted.item == constants.UNKNOWN_ITEM
        assert fainted.moves == []
