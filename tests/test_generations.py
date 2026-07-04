import pytest

from fp.generations import (
    GENERATIONS,
    StatCalculation,
    generation_mechanics,
)


class TestGenerationMechanicsTable:
    def test_no_team_preview_gens(self):
        for gen in ["gen1", "gen2", "gen3", "gen4"]:
            assert not GENERATIONS[gen].has_team_preview, gen
        for gen in ["gen5", "gen6", "gen7", "gen8", "gen9"]:
            assert GENERATIONS[gen].has_team_preview, gen

    def test_heavy_duty_boots_exist_in_gen8_and_gen9_only(self):
        for gen, mechanics in GENERATIONS.items():
            expected = gen in ["gen8", "gen9", "gen9champions"]
            assert expected == mechanics.heavy_duty_boots_exists, gen

    def test_choice_scarf_does_not_exist_before_gen4(self):
        for gen in ["gen1", "gen2", "gen3"]:
            assert not GENERATIONS[gen].choice_scarf_exists, gen
        for gen in ["gen4", "gen5", "gen6", "gen7", "gen8", "gen9"]:
            assert GENERATIONS[gen].choice_scarf_exists, gen

    def test_paralysis_speed_divisor(self):
        for gen, mechanics in GENERATIONS.items():
            expected = (
                4 if gen in ["gen1", "gen2", "gen3", "gen4", "gen5", "gen6"] else 2
            )
            assert expected == mechanics.paralysis_speed_divisor, gen

    def test_taunt_duration_increments_end_of_turn_in_gen3_and_gen4(self):
        for gen, mechanics in GENERATIONS.items():
            expected = gen in ["gen3", "gen4"]
            assert expected == mechanics.taunt_duration_increments_end_of_turn, gen

    def test_ability_weather_is_permanent_in_gen3_through_gen5(self):
        for gen, mechanics in GENERATIONS.items():
            expected = gen in ["gen3", "gen4", "gen5"]
            assert expected == mechanics.ability_weather_is_permanent, gen

    def test_pressure_not_revealed_on_switch_in_gen3_only(self):
        for gen, mechanics in GENERATIONS.items():
            expected = gen != "gen3"
            assert expected == mechanics.pressure_revealed_on_switch_in, gen

    def test_gen5_only_rest_turn_reset(self):
        for gen, mechanics in GENERATIONS.items():
            assert (gen == "gen5") == mechanics.rest_turns_reset_on_switch, gen

    def test_gen3_only_sleep_talk_tracking(self):
        for gen, mechanics in GENERATIONS.items():
            assert (gen == "gen3") == mechanics.tracks_consecutive_sleep_talks, gen

    def test_gen1_only_quirks(self):
        for gen, mechanics in GENERATIONS.items():
            assert (gen == "gen1") == mechanics.partial_trapping_mechanics, gen
            assert (gen == "gen1") == mechanics.stat_modification_glitches, gen

    def test_reverse_damage_checking_disabled_in_gen1_and_gen2(self):
        for gen, mechanics in GENERATIONS.items():
            expected = gen not in ["gen1", "gen2"]
            assert expected == mechanics.supports_reverse_damage_checking, gen

    def test_gen_1_2_stat_calculation(self):
        assert StatCalculation.GEN_1_2 is GENERATIONS["gen1"].stat_calculation
        assert StatCalculation.GEN_1_2 is GENERATIONS["gen2"].stat_calculation
        assert StatCalculation.MODERN is GENERATIONS["gen3"].stat_calculation
        assert StatCalculation.MODERN is GENERATIONS["gen9"].stat_calculation

    def test_megas_exist(self):
        for gen, mechanics in GENERATIONS.items():
            expected = gen in ["gen6", "gen7", "gen9champions"]
            assert expected == mechanics.megas_exist, gen

    def test_champions_row(self):
        champions = GENERATIONS["gen9champions"]
        assert (11,) * 6 == champions.randombattle_evs
        assert 32 == champions.max_ev
        assert not champions.regenerator_heals_on_switch_out
        assert StatCalculation.CHAMPIONS is champions.stat_calculation
        # 15pp move: (15/5 + 1) * 4 = 16
        assert 16 == champions.max_pp(15)
        # everything else inherits gen9
        assert champions.has_team_preview
        assert champions.heavy_duty_boots_exists

    def test_modern_max_pp(self):
        assert 24 == GENERATIONS["gen9"].max_pp(15)
        assert 32 == GENERATIONS["gen9"].max_pp(20)

    def test_unknown_generation_raises(self):
        with pytest.raises(KeyError):
            generation_mechanics("gen0")
        with pytest.raises(KeyError):
            generation_mechanics(None)
