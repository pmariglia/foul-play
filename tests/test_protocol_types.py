import pytest

from fp import constants
from fp.battle.protocol_types import (
    Condition,
    Details,
    Effect,
    EffectKind,
    KwArgs,
    PokemonIdent,
    SideId,
    parse_side_id,
    positional_args,
)


class TestPokemonIdent:
    def test_active_pokemon(self):
        ident = PokemonIdent.parse("p1a: Pikachu")
        assert SideId.P1 == ident.side
        assert "a" == ident.slot
        assert "Pikachu" == ident.nickname
        assert ident.is_active

    def test_inactive_pokemon(self):
        ident = PokemonIdent.parse("p2: Pikachu")
        assert SideId.P2 == ident.side
        assert ident.slot is None
        assert not ident.is_active

    def test_nickname_containing_colon(self):
        assert "Mr: Mime" == PokemonIdent.parse("p1a: Mr: Mime").nickname

    def test_nickname_containing_other_side_id(self):
        assert SideId.P1 == parse_side_id("p1a: p2")

    def test_side_without_pokemon(self):
        ident = PokemonIdent.parse("p2")
        assert SideId.P2 == ident.side
        assert "" == ident.nickname

    def test_invalid_ident_raises(self):
        with pytest.raises(ValueError):
            PokemonIdent.parse("[silent]")


class TestEffect:
    @pytest.mark.parametrize(
        "effect_string,kind,name,effect_id",
        [
            ("move: Light Screen", EffectKind.MOVE, "Light Screen", "lightscreen"),
            ("ability: Drizzle", EffectKind.ABILITY, "Drizzle", "drizzle"),
            ("item: Choice Scarf", EffectKind.ITEM, "Choice Scarf", "choicescarf"),
            ("pokemon: Zoroark", EffectKind.POKEMON, "Zoroark", "zoroark"),
            ("Reflect", EffectKind.CONDITION, "Reflect", "reflect"),
            ("[from] item: Leftovers", EffectKind.ITEM, "Leftovers", "leftovers"),
            ("[from] move: Sleep Talk", EffectKind.MOVE, "Sleep Talk", "sleeptalk"),
            ("[from] Baton Pass", EffectKind.CONDITION, "Baton Pass", "batonpass"),
        ],
    )
    def test_parse(self, effect_string, kind, name, effect_id):
        assert Effect(kind=kind, name=name, id=effect_id) == Effect.parse(effect_string)

    def test_prefixed_and_bare_effect_have_the_same_id(self):
        assert Effect.parse("move: Substitute").id == Effect.parse("Substitute").id


class TestDetails:
    def test_species_only(self):
        details = Details.parse("Pikachu")
        assert "Pikachu" == details.species
        assert 100 == details.level
        assert details.gender is None
        assert not details.shiny
        assert details.tera_type is None

    def test_all_fields(self):
        details = Details.parse("Pikachu, L84, F, shiny, tera:Fire")
        assert "Pikachu" == details.species
        assert 84 == details.level
        assert "F" == details.gender
        assert details.shiny
        assert "Fire" == details.tera_type

    def test_gender_without_level(self):
        details = Details.parse("Pikachu, M")
        assert 100 == details.level
        assert "M" == details.gender

    def test_unknown_forme(self):
        assert Details.parse("Arceus-*, L70").unknown_forme
        assert not Details.parse("Arceus-Fire, L70").unknown_forme


class TestCondition:
    def test_exact_hp(self):
        assert Condition(
            hp=317, max_hp=403, status=None, fainted=False
        ) == Condition.parse("317/403")

    def test_status(self):
        condition = Condition.parse("121/403 tox")
        assert constants.Status.TOXIC == condition.status

    def test_fainted(self):
        condition = Condition.parse("0 fnt")
        assert condition.fainted
        assert 0 == condition.hp
        assert 0 == condition.fraction

    def test_fainted_with_denominator(self):
        assert Condition.parse("0/100 fnt").fainted

    @pytest.mark.parametrize("condition_string", ["50/100g", "50/100y", "24/48y"])
    def test_color_suffix_and_denominator(self, condition_string):
        assert 0.5 == Condition.parse(condition_string).fraction

    def test_color_suffix_with_status(self):
        condition = Condition.parse("20/100r brn")
        assert 20 == condition.hp
        assert 100 == condition.max_hp
        assert constants.Status.BURN == condition.status


class TestKwArgs:
    def test_from_and_of(self):
        kwargs = KwArgs.parse(
            ["", "-weather", "RainDance", "[from] ability: Drizzle", "[of] p2a: p1"]
        )
        assert Effect(EffectKind.ABILITY, "Drizzle", "drizzle") == kwargs.from_
        assert PokemonIdent(SideId.P2, "a", "p1") == kwargs.of

    def test_flags(self):
        kwargs = KwArgs.parse(["", "move", "p1a: Clefable", "Wish", "", "[still]"])
        assert "still" in kwargs
        assert "miss" not in kwargs
        assert kwargs.from_ is None
        assert kwargs.of is None

    def test_is_from(self):
        kwargs = KwArgs.parse(
            ["", "move", "p1a: X", "Tackle", "p2a: Y", "[from] move: Sleep Talk"]
        )
        assert kwargs.is_from("sleeptalk")
        assert kwargs.is_from("sleeptalk", EffectKind.MOVE)
        assert not kwargs.is_from("sleeptalk", EffectKind.ABILITY)

    def test_from_is_not_affected_by_trailing_flags(self):
        kwargs = KwArgs.parse(
            ["", "move", "p1a: X", "Tackle", "p2a: Y", "[from] lockedmove", "[miss]"]
        )
        assert kwargs.is_from("lockedmove")
        assert "miss" in kwargs

    def test_valued_kwarg(self):
        kwargs = KwArgs.parse(
            [
                "",
                "-activate",
                "p2a: X",
                "ability: Mummy",
                "p1a: Y",
                "[ability] Rough Skin",
            ]
        )
        assert "Rough Skin" == kwargs.get("ability")
        assert kwargs.get("of") is None

    def test_kwarg_without_space(self):
        # |move|p1a: X|Z-Thunderbolt|p2a: Y|[anim]Thunderbolt
        kwargs = KwArgs.parse(
            ["", "move", "p1a: X", "Z-Thunderbolt", "p2a: Y", "[anim]Thunderbolt"]
        )
        assert "Thunderbolt" == kwargs.get("anim")

    def test_positional_args(self):
        split_msg = ["", "move", "p1a: X", "Wish", "", "[still]"]
        assert ["p1a: X", "Wish", ""] == positional_args(split_msg)
