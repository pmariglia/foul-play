from fp.data.sets import spreads_are_alike
from fp.battle.helpers import normalize_name


class TestSpreadsAreAlike:
    def test_two_similar_spreads_are_alike(self):
        s1 = ("jolly", "0,0,0,252,4,252")
        s2 = ("jolly", "0,0,4,252,0,252")

        assert spreads_are_alike(s1, s2)

    def test_different_natures_are_not_alike(self):
        s1 = ("jolly", "0,0,0,252,4,252")
        s2 = ("modest", "0,0,4,252,0,252")

        assert not spreads_are_alike(s1, s2)

    def test_custom_is_not_the_same_as_max_values(self):
        s1 = ("jolly", "16,0,0,252,0,240")
        s2 = ("modest", "0,0,4,252,0,252")

        assert not spreads_are_alike(s1, s2)

    def test_very_similar_returns_true(self):
        s1 = ("modest", "16,0,0,252,0,240")
        s2 = ("modest", "28,0,4,252,0,252")

        assert spreads_are_alike(s1, s2)


class TestNormalizeName:
    def test_removes_nonascii_characters(self):
        n = "Flabébé"
        expected_result = "flabebe"
        result = normalize_name(n)

        assert expected_result == result
