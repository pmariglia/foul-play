import unittest

from data.pkmn_sets import spreads_are_alike
from fp.helpers import get_pokemon_info_from_condition
from fp.helpers import normalize_name


class TestSpreadsAreAlike(unittest.TestCase):
    def test_two_similar_spreads_are_alike(self):
        s1 = ("jolly", "0,0,0,252,4,252")
        s2 = ("jolly", "0,0,4,252,0,252")

        self.assertTrue(spreads_are_alike(s1, s2))

    def test_different_natures_are_not_alike(self):
        s1 = ("jolly", "0,0,0,252,4,252")
        s2 = ("modest", "0,0,4,252,0,252")

        self.assertFalse(spreads_are_alike(s1, s2))

    def test_custom_is_not_the_same_as_max_values(self):
        s1 = ("jolly", "16,0,0,252,0,240")
        s2 = ("modest", "0,0,4,252,0,252")

        self.assertFalse(spreads_are_alike(s1, s2))

    def test_very_similar_returns_true(self):
        s1 = ("modest", "16,0,0,252,0,240")
        s2 = ("modest", "28,0,4,252,0,252")

        self.assertTrue(spreads_are_alike(s1, s2))


class TestNormalizeName(unittest.TestCase):
    def test_removes_nonascii_characters(self):
        n = "Flabébé"
        expected_result = "flabebe"
        result = normalize_name(n)

        self.assertEqual(expected_result, result)


class TestGetPokemonInfoFromCondition(unittest.TestCase):
    def test_basic_case(self):
        condition_string = "100/100"
        expected_results = 100, 100, None

        self.assertEqual(
            expected_results, get_pokemon_info_from_condition(condition_string)
        )

    def test_burned_case(self):
        condition_string = "100/100 brn"
        expected_results = 100, 100, "brn"

        self.assertEqual(
            expected_results, get_pokemon_info_from_condition(condition_string)
        )

    def test_poisoned_case(self):
        condition_string = "121/403 psn"
        expected_results = 121, 403, "psn"

        self.assertEqual(
            expected_results, get_pokemon_info_from_condition(condition_string)
        )

    def test_fainted_case(self):
        condition_string = "0/100 fnt"

        self.assertEqual(0, get_pokemon_info_from_condition(condition_string)[0])

    def test_g_on_50(self):
        condition_string = "50/100g"
        self.assertEqual(
            (50, 100, None), get_pokemon_info_from_condition(condition_string)
        )

    def test_y_on_50(self):
        condition_string = "50/100y"
        self.assertEqual(
            (50, 100, None), get_pokemon_info_from_condition(condition_string)
        )

    def test_r_on_20(self):
        condition_string = "20/100r"
        self.assertEqual(
            (20, 100, None), get_pokemon_info_from_condition(condition_string)
        )

    def test_g_on_50_brn(self):
        condition_string = "50/100g brn"
        self.assertEqual(
            (50, 100, "brn"), get_pokemon_info_from_condition(condition_string)
        )

    def test_y_on_50_brn(self):
        condition_string = "50/100y brn"
        self.assertEqual(
            (50, 100, "brn"), get_pokemon_info_from_condition(condition_string)
        )

    def test_r_on_20_brn(self):
        condition_string = "20/100r brn"
        self.assertEqual(
            (20, 100, "brn"), get_pokemon_info_from_condition(condition_string)
        )
