import unittest

from fp.generations import (
    GENERATIONS,
    StatCalculation,
    generation_mechanics,
)


class TestGenerationMechanicsTable(unittest.TestCase):
    def test_no_team_preview_gens(self):
        for gen in ["gen1", "gen2", "gen3", "gen4"]:
            self.assertFalse(GENERATIONS[gen].has_team_preview, gen)
        for gen in ["gen5", "gen6", "gen7", "gen8", "gen9"]:
            self.assertTrue(GENERATIONS[gen].has_team_preview, gen)

    def test_heavy_duty_boots_exist_in_gen8_and_gen9_only(self):
        for gen, mechanics in GENERATIONS.items():
            expected = gen in ["gen8", "gen9", "gen9champions"]
            self.assertEqual(expected, mechanics.heavy_duty_boots_exists, gen)

    def test_choice_scarf_does_not_exist_before_gen4(self):
        for gen in ["gen1", "gen2", "gen3"]:
            self.assertFalse(GENERATIONS[gen].choice_scarf_exists, gen)
        for gen in ["gen4", "gen5", "gen6", "gen7", "gen8", "gen9"]:
            self.assertTrue(GENERATIONS[gen].choice_scarf_exists, gen)

    def test_paralysis_speed_divisor(self):
        for gen, mechanics in GENERATIONS.items():
            expected = (
                4 if gen in ["gen1", "gen2", "gen3", "gen4", "gen5", "gen6"] else 2
            )
            self.assertEqual(expected, mechanics.paralysis_speed_divisor, gen)

    def test_taunt_duration_increments_end_of_turn_in_gen3_and_gen4(self):
        for gen, mechanics in GENERATIONS.items():
            expected = gen in ["gen3", "gen4"]
            self.assertEqual(
                expected, mechanics.taunt_duration_increments_end_of_turn, gen
            )

    def test_ability_weather_is_permanent_in_gen3_through_gen5(self):
        for gen, mechanics in GENERATIONS.items():
            expected = gen in ["gen3", "gen4", "gen5"]
            self.assertEqual(expected, mechanics.ability_weather_is_permanent, gen)

    def test_pressure_not_revealed_on_switch_in_gen3_only(self):
        for gen, mechanics in GENERATIONS.items():
            expected = gen != "gen3"
            self.assertEqual(expected, mechanics.pressure_revealed_on_switch_in, gen)

    def test_gen5_only_rest_turn_reset(self):
        for gen, mechanics in GENERATIONS.items():
            self.assertEqual(gen == "gen5", mechanics.rest_turns_reset_on_switch, gen)

    def test_gen3_only_sleep_talk_tracking(self):
        for gen, mechanics in GENERATIONS.items():
            self.assertEqual(
                gen == "gen3", mechanics.tracks_consecutive_sleep_talks, gen
            )

    def test_gen1_only_quirks(self):
        for gen, mechanics in GENERATIONS.items():
            self.assertEqual(gen == "gen1", mechanics.partial_trapping_mechanics, gen)
            self.assertEqual(gen == "gen1", mechanics.stat_modification_glitches, gen)

    def test_reverse_damage_checking_disabled_in_gen1_and_gen2(self):
        for gen, mechanics in GENERATIONS.items():
            expected = gen not in ["gen1", "gen2"]
            self.assertEqual(expected, mechanics.supports_reverse_damage_checking, gen)

    def test_gen_1_2_stat_calculation(self):
        self.assertIs(StatCalculation.GEN_1_2, GENERATIONS["gen1"].stat_calculation)
        self.assertIs(StatCalculation.GEN_1_2, GENERATIONS["gen2"].stat_calculation)
        self.assertIs(StatCalculation.MODERN, GENERATIONS["gen3"].stat_calculation)
        self.assertIs(StatCalculation.MODERN, GENERATIONS["gen9"].stat_calculation)

    def test_megas_exist(self):
        for gen, mechanics in GENERATIONS.items():
            expected = gen in ["gen6", "gen7", "gen9champions"]
            self.assertEqual(expected, mechanics.megas_exist, gen)

    def test_champions_row(self):
        champions = GENERATIONS["gen9champions"]
        self.assertEqual((11,) * 6, champions.randombattle_evs)
        self.assertEqual(32, champions.max_ev)
        self.assertFalse(champions.regenerator_heals_on_switch_out)
        self.assertIs(StatCalculation.CHAMPIONS, champions.stat_calculation)
        # 15pp move: (15/5 + 1) * 4 = 16
        self.assertEqual(16, champions.max_pp(15))
        # everything else inherits gen9
        self.assertTrue(champions.has_team_preview)
        self.assertTrue(champions.heavy_duty_boots_exists)

    def test_modern_max_pp(self):
        self.assertEqual(24, GENERATIONS["gen9"].max_pp(15))
        self.assertEqual(32, GENERATIONS["gen9"].max_pp(20))

    def test_unknown_generation_raises(self):
        with self.assertRaises(KeyError):
            generation_mechanics("gen0")
        with self.assertRaises(KeyError):
            generation_mechanics(None)
