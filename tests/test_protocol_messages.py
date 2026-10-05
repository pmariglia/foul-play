import pytest

from fp import constants
from fp.battle.protocol import apply_message
from fp.battle.protocol_messages import (
    Ability,
    Activate,
    Boost,
    Cant,
    Crit,
    Damage,
    FormeChange,
    Heal,
    Inactive,
    Item,
    Miss,
    Move,
    Resisted,
    SideStart,
    Start,
    SuperEffective,
    Switch,
    Turn,
    Unknown,
    Upkeep,
    parse_as,
    parse_line,
    parse_lines,
)
from fp.battle.protocol_types import (
    Effect,
    EffectKind,
    PokemonIdent,
    SideId,
)
from fp.battle.state import Battle, Pokemon
from fp.modes.standard_battle import StandardBattleMode


class TestParseLine:
    @pytest.mark.parametrize("line", ["", ">battle-gen9ou-1", "plain text"])
    def test_non_protocol_lines_are_none(self, line):
        assert parse_line(line) is None

    def test_unknown_message_type(self):
        msg = parse_line("|t:|1727800000")
        assert Unknown(type="t:", args=("1727800000",)) == msg

    def test_switch(self):
        msg = parse_line("|switch|p2a: Furret|Furret, L93, F|59/100")
        assert isinstance(msg, Switch)
        assert PokemonIdent(SideId.P2, "a", "Furret") == msg.pokemon
        assert "Furret" == msg.details.species
        assert 93 == msg.details.level
        assert 59 == msg.condition.hp
        assert not msg.is_drag

    def test_drag(self):
        msg = parse_line("|drag|p2a: Furret|Furret, L93, F|59/100")
        assert isinstance(msg, Switch)
        assert msg.is_drag

    def test_switch_from_baton_pass(self):
        msg = parse_line("|switch|p2a: Furret|Furret|100/100|[from] Baton Pass")
        assert msg.kwargs.is_from("batonpass")

    def test_move(self):
        msg = parse_line("|move|p1a: Dragonite|Wrap|p2a: Tauros|[miss]")
        assert isinstance(msg, Move)
        assert PokemonIdent(SideId.P1, "a", "Dragonite") == msg.user
        assert "Wrap" == msg.move
        assert "wrap" == msg.move_id
        assert PokemonIdent(SideId.P2, "a", "Tauros") == msg.target
        assert "miss" in msg.kwargs

    def test_move_with_still_has_no_target(self):
        msg = parse_line("|move|p1a: Clefable|Wish||[still]")
        assert msg.target is None
        assert "still" in msg.kwargs

    def test_heal_and_damage_are_different_types(self):
        assert isinstance(parse_line("|-heal|p1a: X|50/100"), Heal)
        assert isinstance(parse_line("|-damage|p1a: X|50/100"), Damage)

    def test_boost(self):
        msg = parse_line("|-boost|p1a: X|spe|2")
        assert Boost(PokemonIdent(SideId.P1, "a", "X"), "spe", 2) == msg

    def test_activate_args(self):
        msg = parse_line("|-activate|p2a: Gengar|move: Poltergeist|Leftovers")
        assert isinstance(msg, Activate)
        assert Effect(EffectKind.MOVE, "Poltergeist", "poltergeist") == msg.effect
        assert ("Leftovers",) == msg.args

    def test_start_and_singlemove(self):
        start = parse_line("|-start|p1a: X|typechange|Water|[from] ability: Protean")
        assert isinstance(start, Start)
        assert ("Water",) == start.args
        assert isinstance(parse_line("|-singlemove|p1a: X|Destiny Bond"), Start)

    def test_side_start(self):
        msg = parse_line("|-sidestart|p2: Username|move: Stealth Rock")
        assert (
            SideStart(SideId.P2, Effect(EffectKind.MOVE, "Stealth Rock", "stealthrock"))
            == msg
        )

    def test_item_without_holder(self):
        msg = parse_line("|-item||Life Orb|[from] ability: Frisk|[of] p2a: Furret")
        assert isinstance(msg, Item)
        assert msg.pokemon is None
        assert "Life Orb" == msg.item

    def test_ability_previous_ability(self):
        msg = parse_line(
            "|-ability|p2a: Porygon2|Levitate|Trace|[from] ability: Trace|[of] p1a: Claydol"
        )
        assert isinstance(msg, Ability)
        assert "Levitate" == msg.ability
        assert ("Trace",) == msg.args

    def test_forme_change_permanence(self):
        assert parse_line("|detailschange|p1a: X|Charizard-Mega-X, L80").permanent
        assert not parse_line("|-formechange|p1a: X|Wishiwashi-School").permanent
        assert isinstance(
            parse_line("|-formechange|p1a: X|Wishiwashi-School"), FormeChange
        )

    def test_cant_with_and_without_move(self):
        with_move = parse_line("|cant|p2a: Politoed|move: Taunt|Toxic")
        assert isinstance(with_move, Cant)
        assert "Toxic" == with_move.move
        assert parse_line("|cant|p2a: Politoed|slp").move is None

    def test_inactive_keeps_pipes_in_message(self):
        msg = parse_line("|inactive|Time left: 150 sec this turn | 290 sec total")
        assert Inactive("Time left: 150 sec this turn | 290 sec total") == msg

    def test_turn(self):
        assert Turn(7) == parse_line("|turn|7")

    def test_upkeep(self):
        assert Upkeep() == parse_line("|upkeep")

    def test_move_result_messages(self):
        target = PokemonIdent(SideId.P2, "a", "Y")
        assert Crit(target) == parse_line("|-crit|p2a: Y")
        assert SuperEffective(target) == parse_line("|-supereffective|p2a: Y")
        assert Resisted(target) == parse_line("|-resisted|p2a: Y")
        assert Miss(PokemonIdent(SideId.P1, "a", "X"), target) == parse_line(
            "|-miss|p1a: X|p2a: Y"
        )


class TestParseLines:
    def test_drops_non_protocol_lines(self):
        messages = parse_lines(
            [">battle-gen9ou-1", "", "|move|p1a: X|Tackle|p2a: Y", "|", "|upkeep"]
        )
        assert [Move, Unknown, Upkeep] == [type(m) for m in messages]


class TestParseAs:
    def test_returns_the_expected_type(self):
        msg = parse_as(Move, ["", "move", "p1a: X", "Tackle", "p2a: Y"])
        assert isinstance(msg, Move)

    def test_raises_on_a_different_type(self):
        with pytest.raises(TypeError):
            parse_as(Move, ["", "-damage", "p1a: X", "50/100"])

    def test_raises_on_a_non_protocol_line(self):
        with pytest.raises(TypeError):
            parse_as(Move, [">battle-gen9ou-1"])


class TestApplyMessage:
    @pytest.fixture(autouse=True)
    def _setup(self):
        self.battle = Battle(None)
        self.battle.generation = "gen9"
        self.battle.mode = StandardBattleMode()
        self.battle.user.name = "p1"
        self.battle.opponent.name = "p2"
        self.battle.user.active = Pokemon("weedle", 100)
        self.battle.opponent.active = Pokemon("caterpie", 100)

    def test_routes_damage(self):
        apply_message(self.battle, parse_line("|-damage|p2a: Caterpie|50/100"))
        opponent = self.battle.opponent.active
        assert 0.5 == opponent.hp / opponent.max_hp

    def test_routes_status(self):
        apply_message(self.battle, parse_line("|-status|p2a: Caterpie|par"))
        assert constants.Status.PARALYZED == self.battle.opponent.active.status

    def test_unknown_messages_are_ignored(self):
        apply_message(self.battle, parse_line("|t:|1727800000"))
