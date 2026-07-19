import pytest

from fp import constants
from fp.battle.state import Battle, Battler, LastUsedMove, Pokemon
from fp.config import FoulPlayConfig
from fp.format_spec import FormatSpec
from fp.modes.random_battle import RandomBattleMode
from fp.modes.standard_battle import StandardBattleMode
from fp.search.main import find_best_move
from fp.search.poke_engine_helpers import (
    battle_to_poke_engine_state,
    get_terrain_string,
    get_weather_string,
    pokemon_to_poke_engine_pkmn,
    replace_hidden_power_last_used_move,
    replace_return_last_used_move,
    status_to_string,
)

from poke_engine import State as PokeEngineState


def real_pkmn(name, level, ability, item, moves):
    pkmn = Pokemon(name, level)
    pkmn.ability = ability
    pkmn.item = item
    for mv in moves:
        pkmn.add_move(mv)
    return pkmn


def small_battle():
    battle = Battle(None)
    battle.generation = "gen9"
    battle.mode = StandardBattleMode()

    battle.user.active = real_pkmn(
        "pikachu", 100, "static", "lightball", ["thunderbolt", "surf"]
    )
    battle.user.reserve = [
        real_pkmn("garchomp", 100, "roughskin", "rockyhelmet", ["earthquake"])
    ]

    battle.opponent.active = real_pkmn(
        "heatran", 100, "flashfire", "leftovers", ["magmastorm"]
    )
    battle.opponent.reserve = [
        real_pkmn("tyranitar", 100, "sandstream", "chopleberry", ["stoneedge"])
    ]

    battle.weather = constants.Weather.SAND
    battle.weather_turns_remaining = 3
    battle.field = constants.Terrain.ELECTRIC
    battle.field_turns_remaining = 2
    battle.trick_room = True
    battle.trick_room_turns_remaining = 4
    return battle


class TestBattleToPokeEngineState:
    def test_small_battle_maps_onto_poke_engine_state(self):
        state = battle_to_poke_engine_state(small_battle())

        assert "sand" == state.weather
        assert 3 == state.weather_turns_remaining
        assert "electricterrain" == state.terrain
        assert 2 == state.terrain_turns_remaining
        assert state.trick_room
        assert 4 == state.trick_room_turns_remaining
        assert not state.team_preview

        # sides are padded to 6 pokemon with fainted dummies
        assert ["pikachu", "garchomp"] == [p.id for p in state.side_one.pokemon[:2]]
        assert ["heatran", "tyranitar"] == [p.id for p in state.side_two.pokemon[:2]]
        assert 6 == len(state.side_one.pokemon)
        assert 6 == len(state.side_two.pokemon)
        assert all(0 == p.hp for p in state.side_one.pokemon[2:])

        # moves are padded to 4 with disabled "none" moves
        assert ["thunderbolt", "surf", "none", "none"] == [
            m.id for m in state.side_one.pokemon[0].moves
        ]

    def test_team_preview_flag_is_serialized(self):
        battle = small_battle()
        battle.team_preview = True
        assert battle_to_poke_engine_state(battle).team_preview

    def test_state_round_trips_through_string_serialization(self):
        state = battle_to_poke_engine_state(small_battle())
        state_string = state.to_string()
        round_tripped = PokeEngineState.from_string(state_string)
        assert state_string == round_tripped.to_string()

    def test_swap_flips_the_sides(self):
        state = battle_to_poke_engine_state(small_battle(), swap=True)
        assert "heatran" == state.side_one.pokemon[0].id
        assert "pikachu" == state.side_two.pokemon[0].id


class TestStringMappings:
    def test_weather_strings(self):
        assert "rain" == get_weather_string(constants.Weather.RAIN)
        assert "sun" == get_weather_string(constants.Weather.SUN)
        assert "sand" == get_weather_string(constants.Weather.SAND)
        assert "hail" == get_weather_string(constants.Weather.HAIL)
        assert "snow" == get_weather_string(constants.Weather.SNOW)
        assert "harshsun" == get_weather_string(constants.Weather.DESOLATE_LAND)
        assert "heavyrain" == get_weather_string(constants.Weather.HEAVY_RAIN)
        assert "none" == get_weather_string(None)
        assert "none" == get_weather_string("none")
        with pytest.raises(ValueError):
            get_weather_string("acidrain")

    def test_terrain_strings(self):
        assert "electricterrain" == get_terrain_string(constants.Terrain.ELECTRIC)
        assert "grassyterrain" == get_terrain_string(constants.Terrain.GRASSY)
        assert "mistyterrain" == get_terrain_string(constants.Terrain.MISTY)
        assert "psychicterrain" == get_terrain_string(constants.Terrain.PSYCHIC)
        assert "none" == get_terrain_string(None)
        assert "none" == get_terrain_string("none")
        with pytest.raises(ValueError):
            get_terrain_string("wonderroom")

    def test_status_strings(self):
        assert "Sleep" == status_to_string(constants.Status.SLEEP)
        assert "Burn" == status_to_string(constants.Status.BURN)
        assert "Freeze" == status_to_string(constants.Status.FROZEN)
        assert "Paralyze" == status_to_string(constants.Status.PARALYZED)
        assert "Poison" == status_to_string(constants.Status.POISON)
        assert "Toxic" == status_to_string(constants.Status.TOXIC)
        assert "None" == status_to_string(None)
        with pytest.raises(ValueError):
            status_to_string("frostbite")


class TestReplaceLastUsedMove:
    @pytest.fixture(autouse=True)
    def _setup(self):
        self.battler = Battler()
        self.battler.active = Pokemon("pikachu", 100)

    def test_hidden_power_is_replaced_with_the_full_move_name(self):
        self.battler.active.add_move("hiddenpowerice60")
        self.battler.last_used_move = LastUsedMove("pikachu", "hiddenpower", 3)
        replace_hidden_power_last_used_move(self.battler)
        assert LastUsedMove("pikachu", "hiddenpowerice60", 3) == (
            self.battler.last_used_move
        )

    def test_hidden_power_falls_back_to_a_switch_when_no_move_matches(self):
        self.battler.active.add_move("thunderbolt")
        self.battler.last_used_move = LastUsedMove("pikachu", "hiddenpower", 3)
        replace_hidden_power_last_used_move(self.battler)
        assert LastUsedMove("pikachu", "switch pikachu", 3) == (
            self.battler.last_used_move
        )

    def test_return_is_replaced_with_the_full_move_name(self):
        self.battler.active.add_move("return102")
        self.battler.last_used_move = LastUsedMove("pikachu", "return", 5)
        replace_return_last_used_move(self.battler)
        assert LastUsedMove("pikachu", "return102", 5) == self.battler.last_used_move

    def test_return_falls_back_to_a_switch_when_no_move_matches(self):
        self.battler.active.add_move("thunderbolt")
        self.battler.last_used_move = LastUsedMove("pikachu", "return", 5)
        replace_return_last_used_move(self.battler)
        assert LastUsedMove("pikachu", "switch pikachu", 5) == (
            self.battler.last_used_move
        )


class TestPokemonToPokeEnginePkmn:
    def test_moves_are_padded_to_four(self):
        pkmn = real_pkmn("pikachu", 100, "static", "lightball", ["thunderbolt", "surf"])
        engine_pkmn = pokemon_to_poke_engine_pkmn(pkmn)
        assert ["thunderbolt", "surf", "none", "none"] == [
            m.id for m in engine_pkmn.moves
        ]
        assert engine_pkmn.moves[2].disabled
        assert 0 == engine_pkmn.moves[2].pp

    def test_more_than_four_moves_are_truncated(self):
        pkmn = real_pkmn(
            "pikachu",
            100,
            "static",
            "lightball",
            ["thunderbolt", "surf", "irontail", "voltswitch", "fakeout"],
        )
        engine_pkmn = pokemon_to_poke_engine_pkmn(pkmn)
        assert ["thunderbolt", "surf", "irontail", "voltswitch"] == [
            m.id for m in engine_pkmn.moves
        ]
        # the source pokemon is mutated by the truncation
        assert 4 == len(pkmn.moves)

    def test_single_typed_pkmn_gets_typeless_second_type(self):
        pkmn = real_pkmn("pikachu", 100, "static", "lightball", ["thunderbolt"])
        engine_pkmn = pokemon_to_poke_engine_pkmn(pkmn)
        assert ("electric", "typeless") == engine_pkmn.types
        assert ("electric", "typeless") == engine_pkmn.base_types

    def test_knocked_off_item_becomes_none_string(self):
        pkmn = real_pkmn("pikachu", 100, "static", "lightball", ["thunderbolt"])
        pkmn.knocked_off = True
        engine_pkmn = pokemon_to_poke_engine_pkmn(pkmn)
        assert "None" == engine_pkmn.item
        # the source pokemon's item is overwritten too
        assert "None" == pkmn.item

    def test_missing_item_becomes_none_string(self):
        pkmn = real_pkmn("pikachu", 100, "static", None, ["thunderbolt"])
        assert "None" == pokemon_to_poke_engine_pkmn(pkmn).item


class TestFindBestMoveSmoke:
    @pytest.fixture(autouse=True)
    def _setup(self):
        FoulPlayConfig.pokemon_format = "gen9randombattle"
        FoulPlayConfig.search_time_ms = 20
        FoulPlayConfig.parallelism = 1
        FoulPlayConfig.search_threads = 1
        yield
        del FoulPlayConfig.search_time_ms
        del FoulPlayConfig.parallelism
        del FoulPlayConfig.search_threads

    def test_find_best_move_returns_a_legal_option_for_a_randombattle(self):
        battle = Battle(None)
        battle.pokemon_format = "gen9randombattle"
        battle.generation = battle.format_spec.generation
        battle.battle_type = battle.format_spec.battle_type
        battle.mode = RandomBattleMode()
        battle.mode.datasets.initialize(
            FormatSpec.from_format_string("gen9randombattle")
        )

        battle.user.active = real_pkmn(
            "garchomp",
            74,
            "roughskin",
            "rockyhelmet",
            ["earthquake", "outrage", "spikes", "stealthrock"],
        )
        battle.user.reserve = [
            real_pkmn(
                "heatran",
                79,
                "flashfire",
                "leftovers",
                ["magmastorm", "earthpower", "stealthrock", "taunt"],
            )
        ]

        # reveal a full opposing team so prepare_battles samples sets for these
        # pokemon instead of generating unrevealed ones
        battle.opponent.active = Pokemon("pikachu", 88)
        battle.opponent.reserve = [
            Pokemon("tyranitar", 82),
            Pokemon("dragonite", 79),
            Pokemon("volcarona", 78),
            Pokemon("scizor", 82),
            Pokemon("rotomwash", 84),
        ]

        choice = find_best_move(battle)

        legal_options = {
            "earthquake",
            "outrage",
            "spikes",
            "stealthrock",
            "switch heatran",
        }
        assert choice.removesuffix("-tera") in legal_options
