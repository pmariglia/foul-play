import pytest

from fp.battle.protocol import switch_or_drag
from fp.battle.state import Battle, Move, Pokemon
from fp.config import FoulPlayConfig
from fp.constants import BattleType
from fp.battle.helpers import calculate_stats, maximum_ev, random_battles_evs
from fp.data.sets import RandomBattleTeamDatasets
from fp.format_spec import FormatSpec
from fp.generations import GENERATIONS
from fp.modes.random_battle import RandomBattleMode

CHAMPIONS_FORMAT = "gen9championsrandombattle"


def champions_battle():
    battle = Battle(None)
    battle.pokemon_format = CHAMPIONS_FORMAT
    battle.generation = battle.format_spec.generation
    battle.battle_type = battle.format_spec.battle_type
    battle.mode = RandomBattleMode()
    battle.user.name = "p1"
    battle.opponent.name = "p2"
    return battle


def gen9_randombattle_battle():
    battle = Battle(None)
    battle.pokemon_format = "gen9randombattle"
    battle.generation = battle.format_spec.generation
    battle.battle_type = battle.format_spec.battle_type
    battle.mode = RandomBattleMode()
    battle.user.name = "p1"
    battle.opponent.name = "p2"
    return battle


class TestChampionsIsAGeneration:
    def test_format_parses_as_randombattle_with_champions_generation(self):
        spec = FormatSpec.from_format_string(CHAMPIONS_FORMAT)
        assert BattleType.RANDOM_BATTLE == spec.battle_type
        assert "gen9champions" == spec.generation
        assert 9 == spec.gen_number

    def test_champions_battle_resolves_champions_mechanics(self):
        battle = champions_battle()
        assert GENERATIONS["gen9champions"] is battle.gen

    def test_champions_battle_uses_the_same_mode_as_randombattles(self):
        # champions is a generation, not a battle type: the mode is plain randombattle
        battle = champions_battle()
        assert isinstance(battle.mode, RandomBattleMode)


class TestChampionsMechanics:
    @pytest.fixture(autouse=True)
    def _setup(self):
        FoulPlayConfig.pokemon_format = CHAMPIONS_FORMAT

    def test_max_pp_formula(self):
        # tackle has 35pp: champions gives (35/5 + 1) * 4 = 32 rather than 35 * 1.6 = 56
        assert 32 == Move("tackle").max_pp

    def test_randombattle_evs(self):
        assert (11,) * 6 == random_battles_evs()

    def test_maximum_ev(self):
        assert 32 == maximum_ev()

    def test_stat_calculation_converts_stat_points_to_evs(self):
        base_stats = {
            "hp": 100,
            "attack": 100,
            "defense": 100,
            "special-attack": 100,
            "special-defense": 100,
            "speed": 100,
        }
        champions_stats = calculate_stats(base_stats, 100, evs=(11,) * 6)

        # 11 champions stat points are worth 8 * 11 - 4 = 84 EVs
        FoulPlayConfig.pokemon_format = "gen9randombattle"
        assert calculate_stats(base_stats, 100, evs=(84,) * 6) == champions_stats

    def test_randombattle_sets_get_champions_evs(self):
        datasets = RandomBattleTeamDatasets()
        datasets.pkmn_mode = CHAMPIONS_FORMAT
        datasets.raw_pkmn_sets = {
            "pikachu": {"81,lightball,static,volttackle,surf,irontail,fakeout": 1}
        }
        datasets._initialize_pkmn_sets()
        assert (11,) * 6 == datasets.pkmn_sets["pikachu"][0].pkmn_set.evs


class TestChampionsRegenerator:
    def _switch_out_regenerator_pkmn(self, battle):
        outgoing = Pokemon("slowbro", 100)
        outgoing.ability = "regenerator"
        outgoing.hp = 30
        outgoing.max_hp = 100
        battle.opponent.active = outgoing
        battle.opponent.reserve = [Pokemon("weedle", 100)]
        battle.user.active = Pokemon("pikachu", 100)

        split_msg = ["", "switch", "p2a: weedle", "Weedle, L100, M", "100/100"]
        switch_or_drag(battle, split_msg)
        return outgoing

    def test_regenerator_does_not_heal_in_champions(self):
        FoulPlayConfig.pokemon_format = CHAMPIONS_FORMAT
        outgoing = self._switch_out_regenerator_pkmn(champions_battle())
        assert 30 == outgoing.hp

    def test_regenerator_heals_in_gen9_randombattle(self):
        FoulPlayConfig.pokemon_format = "gen9randombattle"
        outgoing = self._switch_out_regenerator_pkmn(gen9_randombattle_battle())
        assert 30 + int(100 / 3) == outgoing.hp


class TestChampionsSpeedCheckSpread:
    def test_speed_check_assumes_champions_evs(self):
        FoulPlayConfig.pokemon_format = CHAMPIONS_FORMAT
        battle = champions_battle()
        battle.opponent.active = Pokemon("pikachu", 100)
        battle_copy = champions_battle()
        battle_copy.opponent.active = Pokemon("pikachu", 100)

        battle.mode.assume_spread_for_speed_check(battle, battle_copy)
        assert [11] * 6 == battle_copy.opponent.active.evs


class TestChampionsDoesNotLeakIntoOtherGens:
    def test_gen9_randombattle_is_unaffected(self):
        assert (85,) * 6 == random_battles_evs()
        assert 252 == maximum_ev()
        assert 56 == Move("tackle").max_pp
        battle = gen9_randombattle_battle()
        assert GENERATIONS["gen9"] is battle.gen
        assert battle.gen.regenerator_heals_on_switch_out
