import pytest

from copy import deepcopy

from fp.config import FoulPlayConfig
from fp.constants import BattleType
from fp.battle.state import Battle, Pokemon
from fp.modes import BATTLE_MODES, battle_mode
from fp.modes.base import BattleMode, format_decision
from fp.modes.battle_factory import (
    BattleFactoryMode,
    extract_battle_factory_tier_from_msg,
)
from fp.modes.bss import BSSMode
from fp.modes.random_battle import RandomBattleMode
from fp.modes.standard_battle import StandardBattleMode
from fp.run_battle import battle_is_finished


class TestFormatDecision:
    @pytest.fixture(autouse=True)
    def _setup(self):
        self.battle = Battle(None)
        self.battle.generation = "gen9"
        self.battle.mode = StandardBattleMode()
        self.battle.rqid = 7
        self.battle.user.active = Pokemon("pikachu", 100)
        self.battle.user.active.add_move("thunderbolt")
        reserve_pkmn = Pokemon("weedle", 100)
        reserve_pkmn.index = 3
        self.battle.user.reserve = [reserve_pkmn]

    def test_switch_decision_uses_reserve_pkmn_index(self):
        assert ["/switch 3", "7"] == format_decision(self.battle, "switch weedle")

    def test_switch_to_pkmn_not_in_reserve_raises(self):
        with pytest.raises(ValueError):
            format_decision(self.battle, "switch caterpie")

    def test_move_decision(self):
        assert ["/choose move thunderbolt", "7"] == format_decision(
            self.battle, "thunderbolt"
        )

    def test_rqid_is_stringified(self):
        self.battle.rqid = 42
        assert "42" == format_decision(self.battle, "thunderbolt")[1]

    def test_mega_suffix_appends_mega_when_pkmn_can_mega_evo(self):
        self.battle.user.active.can_mega_evo = True
        assert ["/choose move thunderbolt mega", "7"] == format_decision(
            self.battle, "thunderbolt-mega"
        )

    def test_mega_suffix_is_silently_dropped_when_pkmn_cannot_mega_evo(self):
        self.battle.user.active.can_mega_evo = False
        assert ["/choose move thunderbolt", "7"] == format_decision(
            self.battle, "thunderbolt-mega"
        )

    def test_ultra_burst_is_appended_even_when_not_asked_for(self):
        # any plain move decision picks up the ultra burst suffix
        self.battle.user.active.can_ultra_burst = True
        assert ["/choose move thunderbolt ultra", "7"] == format_decision(
            self.battle, "thunderbolt"
        )

    def test_dynamax_is_appended_only_when_all_reserves_are_fainted(self):
        self.battle.user.active.can_dynamax = True
        self.battle.user.reserve[0].hp = 0
        assert ["/choose move thunderbolt dynamax", "7"] == format_decision(
            self.battle, "thunderbolt"
        )

    def test_dynamax_is_not_appended_when_a_reserve_is_healthy(self):
        self.battle.user.active.can_dynamax = True
        assert ["/choose move thunderbolt", "7"] == format_decision(
            self.battle, "thunderbolt"
        )

    def test_tera_suffix_appends_terastallize(self):
        assert ["/choose move thunderbolt terastallize", "7"] == format_decision(
            self.battle, "thunderbolt-tera"
        )

    def test_zmove_is_appended_when_the_move_can_z(self):
        self.battle.user.active.get_move("thunderbolt").can_z = True
        assert ["/choose move thunderbolt zmove", "7"] == format_decision(
            self.battle, "thunderbolt"
        )

    def test_dynamax_comes_before_terastallize_when_both_apply(self):
        self.battle.user.active.can_dynamax = True
        self.battle.user.reserve[0].hp = 0
        assert [
            "/choose move thunderbolt dynamax terastallize",
            "7",
        ] == format_decision(self.battle, "thunderbolt-tera")


class TestBattleIsFinished:
    def test_win_message_for_the_right_battle_tag(self):
        msg = ">battle-gen9ou-123\n|win|SomePlayer\n"
        assert battle_is_finished("battle-gen9ou-123", msg)

    def test_win_message_for_a_different_battle_tag(self):
        msg = ">battle-gen9ou-999\n|win|SomePlayer\n"
        assert not battle_is_finished("battle-gen9ou-123", msg)

    def test_tie_message(self):
        msg = ">battle-gen9ou-123\n|tie\n"
        assert battle_is_finished("battle-gen9ou-123", msg)

    def test_chat_message_containing_win_string_is_excluded(self):
        msg = ">battle-gen9ou-123\n|c|☆SomePlayer|i always |win| this matchup\n"
        assert not battle_is_finished("battle-gen9ou-123", msg)

    def test_regular_battle_message_is_not_finished(self):
        msg = ">battle-gen9ou-123\n|move|p2a: Pikachu|Thunderbolt|p1a: Weedle\n"
        assert not battle_is_finished("battle-gen9ou-123", msg)


class TestExtractBattleFactoryTierFromMsg:
    def test_extracts_tier_from_html_message(self):
        msg = '|raw|<div class="infobox"><b>Battle Factory Tier: RU</b></div>'
        assert "ru" == extract_battle_factory_tier_from_msg(msg)

    def test_tier_name_is_normalized(self):
        msg = "<b>Battle Factory Tier: National Dex OU</b>"
        assert "nationaldexou" == extract_battle_factory_tier_from_msg(msg)

    def test_message_without_tier_marker_returns_empty_string(self):
        # find() returning -1 makes the slice start at len("Battle Factory Tier: ")
        # rather than raising; for a short message this produces an empty string
        assert "" == extract_battle_factory_tier_from_msg("no tier marker here")


class TestRandomBattleSearchParams:
    @pytest.fixture(autouse=True)
    def _setup(self):
        FoulPlayConfig.parallelism = 2
        FoulPlayConfig.search_time_ms = 100
        self.battle = Battle(None)
        self.battle.generation = "gen9"
        self.battle.mode = RandomBattleMode()
        self.battle.opponent.active = Pokemon("pikachu", 100)
        yield
        del FoulPlayConfig.parallelism
        del FoulPlayConfig.search_time_ms

    def test_early_battle_with_no_revealed_moves_searches_more_battles_shallowly(self):
        assert (8, 50) == self.battle.mode.search_params(self.battle)

    def test_early_battle_in_time_pressure_halves_the_multiplier(self):
        self.battle.time_remaining = 60
        assert (4, 50) == self.battle.mode.search_params(self.battle)

    def test_revealed_moves_searches_fewer_battles_at_full_time(self):
        self.battle.opponent.active.add_move("thunderbolt")
        assert (4, 100) == self.battle.mode.search_params(self.battle)

    def test_many_revealed_pkmn_searches_fewer_battles_at_full_time(self):
        self.battle.opponent.reserve = [
            Pokemon("weedle", 100),
            Pokemon("caterpie", 100),
            Pokemon("metapod", 100),
        ]
        assert (4, 100) == self.battle.mode.search_params(self.battle)

    def test_late_battle_in_time_pressure(self):
        self.battle.opponent.active.add_move("thunderbolt")
        self.battle.time_remaining = 60
        assert (2, 100) == self.battle.mode.search_params(self.battle)


class TestStandardBattleSearchParams:
    @pytest.fixture(autouse=True)
    def _setup(self):
        FoulPlayConfig.parallelism = 2
        FoulPlayConfig.search_time_ms = 100
        self.battle = Battle(None)
        self.battle.generation = "gen9"
        self.battle.mode = StandardBattleMode()
        self.battle.opponent.active = Pokemon("pikachu", 100)
        yield
        del FoulPlayConfig.parallelism
        del FoulPlayConfig.search_time_ms

    def test_no_revealed_moves_doubles_the_number_of_battles(self):
        assert (4, 100) == self.battle.mode.search_params(self.battle)

    def test_team_preview_doubles_the_number_of_battles(self):
        self.battle.team_preview = True
        for mv in ["thunderbolt", "surf", "voltswitch", "irontail"]:
            self.battle.opponent.active.add_move(mv)
        assert (4, 100) == self.battle.mode.search_params(self.battle)

    def test_fewer_than_three_revealed_moves_doubles_the_number_of_battles(self):
        self.battle.opponent.active.add_move("thunderbolt")
        self.battle.opponent.active.add_move("surf")
        assert (4, 100) == self.battle.mode.search_params(self.battle)

    def test_time_pressure_removes_the_multiplier(self):
        self.battle.time_remaining = 60
        assert (2, 100) == self.battle.mode.search_params(self.battle)

    def test_three_revealed_moves_searches_parallelism_battles_at_full_time(self):
        for mv in ["thunderbolt", "surf", "voltswitch"]:
            self.battle.opponent.active.add_move(mv)
        assert (2, 100) == self.battle.mode.search_params(self.battle)


class TestModeRegistry:
    def test_battle_mode_returns_the_right_mode_for_each_battle_type(self):
        assert isinstance(battle_mode(BattleType.RANDOM_BATTLE), RandomBattleMode)
        assert isinstance(battle_mode(BattleType.STANDARD_BATTLE), StandardBattleMode)
        assert isinstance(battle_mode(BattleType.BATTLE_FACTORY), BattleFactoryMode)
        assert isinstance(battle_mode(BattleType.BSS), BSSMode)

    def test_battle_modes_are_module_level_singletons(self):
        assert battle_mode(BattleType.RANDOM_BATTLE) is battle_mode(
            BattleType.RANDOM_BATTLE
        )

    def test_registry_has_exactly_four_entries(self):
        assert 4 == len(BATTLE_MODES)

    def test_battle_factory_mode_is_a_standard_battle_mode(self):
        assert issubclass(BattleFactoryMode, StandardBattleMode)
        assert isinstance(BattleFactoryMode(), StandardBattleMode)

    def test_deepcopying_a_battle_shares_the_mode(self):
        battle = Battle(None)
        battle.generation = "gen9"
        battle.mode = StandardBattleMode()
        assert deepcopy(battle).mode is battle.mode

    def test_battle_factory_prepares_battles_like_a_random_battle(self, monkeypatch):
        calls = []
        monkeypatch.setattr(
            "fp.modes.battle_factory.prepare_random_battles",
            lambda battle, num_battles: calls.append((battle, num_battles)),
        )
        battle = Battle(None)
        mode = BattleFactoryMode()
        mode.prepare_battles(battle, 4)
        assert [(battle, 4)] == calls

    def test_base_mode_get_all_remaining_sets_raises(self):
        with pytest.raises(ValueError):
            BattleMode().get_all_remaining_sets(Pokemon("pikachu", 100))
