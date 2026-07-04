from fp.constants import BattleType
from fp.format_spec import FormatSpec


class TestFormatSpecParsing:
    def test_gen9randombattle(self):
        spec = FormatSpec.from_format_string("gen9randombattle")
        assert 9 == spec.gen_number
        assert "gen9" == spec.gen_string
        assert "gen9" == spec.generation
        assert BattleType.RANDOM_BATTLE == spec.battle_type
        assert not spec.blitz
        assert not spec.champions
        assert not spec.national_dex

    def test_blitz_suffix(self):
        spec = FormatSpec.from_format_string("gen9randombattleblitz")
        assert spec.blitz
        assert "gen9randombattle" == spec.base_name
        assert BattleType.RANDOM_BATTLE == spec.battle_type

    def test_base_name_without_blitz_is_full_name(self):
        spec = FormatSpec.from_format_string("gen9ou")
        assert "gen9ou" == spec.base_name

    def test_standard_battle(self):
        spec = FormatSpec.from_format_string("gen5ou")
        assert 5 == spec.gen_number
        assert BattleType.STANDARD_BATTLE == spec.battle_type

    def test_battle_factory(self):
        spec = FormatSpec.from_format_string("gen9battlefactory")
        assert BattleType.BATTLE_FACTORY == spec.battle_type

    def test_random_takes_precedence_over_battlefactory(self):
        spec = FormatSpec.from_format_string("gen9randombattle")
        assert BattleType.RANDOM_BATTLE == spec.battle_type

    def test_champions_randombattle_is_champions_generation(self):
        spec = FormatSpec.from_format_string("gen9championsrandombattle")
        assert spec.champions
        assert "gen9champions" == spec.generation
        assert "gen9" == spec.gen_string
        assert BattleType.RANDOM_BATTLE == spec.battle_type

    def test_national_dex(self):
        spec = FormatSpec.from_format_string("gen9nationaldex")
        assert spec.national_dex
        assert BattleType.STANDARD_BATTLE == spec.battle_type

    def test_old_generation(self):
        spec = FormatSpec.from_format_string("gen1randombattle")
        assert 1 == spec.gen_number
        assert "gen1" == spec.generation

    def test_empty_string_parses(self):
        spec = FormatSpec.from_format_string("")
        assert 0 == spec.gen_number
        assert BattleType.STANDARD_BATTLE == spec.battle_type
        assert not spec.champions

    def test_parsing_is_cached_and_equal(self):
        a = FormatSpec.from_format_string("gen9randombattle")
        b = FormatSpec.from_format_string("gen9randombattle")
        assert a is b
