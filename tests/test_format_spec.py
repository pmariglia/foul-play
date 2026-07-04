import unittest

from fp.constants import BattleType
from fp.format_spec import FormatSpec


class TestFormatSpecParsing(unittest.TestCase):
    def test_gen9randombattle(self):
        spec = FormatSpec.from_format_string("gen9randombattle")
        self.assertEqual(9, spec.gen_number)
        self.assertEqual("gen9", spec.gen_string)
        self.assertEqual("gen9", spec.generation)
        self.assertEqual(BattleType.RANDOM_BATTLE, spec.battle_type)
        self.assertFalse(spec.blitz)
        self.assertFalse(spec.champions)
        self.assertFalse(spec.national_dex)

    def test_blitz_suffix(self):
        spec = FormatSpec.from_format_string("gen9randombattleblitz")
        self.assertTrue(spec.blitz)
        self.assertEqual("gen9randombattle", spec.base_name)
        self.assertEqual(BattleType.RANDOM_BATTLE, spec.battle_type)

    def test_base_name_without_blitz_is_full_name(self):
        spec = FormatSpec.from_format_string("gen9ou")
        self.assertEqual("gen9ou", spec.base_name)

    def test_standard_battle(self):
        spec = FormatSpec.from_format_string("gen5ou")
        self.assertEqual(5, spec.gen_number)
        self.assertEqual(BattleType.STANDARD_BATTLE, spec.battle_type)

    def test_battle_factory(self):
        spec = FormatSpec.from_format_string("gen9battlefactory")
        self.assertEqual(BattleType.BATTLE_FACTORY, spec.battle_type)

    def test_random_takes_precedence_over_battlefactory(self):
        spec = FormatSpec.from_format_string("gen9randombattle")
        self.assertEqual(BattleType.RANDOM_BATTLE, spec.battle_type)

    def test_champions_randombattle_is_champions_generation(self):
        spec = FormatSpec.from_format_string("gen9championsrandombattle")
        self.assertTrue(spec.champions)
        self.assertEqual("gen9champions", spec.generation)
        self.assertEqual("gen9", spec.gen_string)
        self.assertEqual(BattleType.RANDOM_BATTLE, spec.battle_type)

    def test_national_dex(self):
        spec = FormatSpec.from_format_string("gen9nationaldex")
        self.assertTrue(spec.national_dex)
        self.assertEqual(BattleType.STANDARD_BATTLE, spec.battle_type)

    def test_old_generation(self):
        spec = FormatSpec.from_format_string("gen1randombattle")
        self.assertEqual(1, spec.gen_number)
        self.assertEqual("gen1", spec.generation)

    def test_empty_string_parses(self):
        spec = FormatSpec.from_format_string("")
        self.assertEqual(0, spec.gen_number)
        self.assertEqual(BattleType.STANDARD_BATTLE, spec.battle_type)
        self.assertFalse(spec.champions)

    def test_parsing_is_cached_and_equal(self):
        a = FormatSpec.from_format_string("gen9randombattle")
        b = FormatSpec.from_format_string("gen9randombattle")
        self.assertIs(a, b)
