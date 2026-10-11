"""Revival Blessing: the revive pick must be a FAINTED ally, and must not crash speed inference.

`revival_blessing_request.json` is the exact request Pokemon Showdown sends for the revive prompt
(gen9 Champions; Pawmot used Revival Blessing; Gyarados is alive, Banette fainted). Against Showdown,
"switch 2" (Gyarados) is rejected - "You have to pass to a fainted Pokemon" - and "switch 3" (Banette)
is accepted and revives Banette.

Before the fix, the bot searched an ordinary switch among LIVING allies, so it picked Gyarados: the
choice was rejected, the turn timer ran down (~55 s) and Showdown revived its own default; then speed
inference looked the switch up as a move (KeyError: 'switchbanette') and the bot crashed mid-battle.
"""

import json
import os

import pytest

from fp import constants
from fp.battle.inference import check_speed_ranges
from fp.battle.state import Battle, Battler, LastUsedMove, Pokemon
from fp.battle.protocol import heal_or_damage
from fp.modes.base import format_decision

from fp.search.main import revival_blessing_choice

REQUEST = json.load(
    open(os.path.join(os.path.dirname(__file__), "revival_blessing_request.json"))
)


@pytest.fixture
def battle():
    b = Battle("battle-test-revival")
    b.generation = "gen9"
    b.user = Battler()
    b.user.name = "p1"
    b.user.active = Pokemon("pawmot", 50)
    b.user.reserve = [Pokemon("gyarados", 50), Pokemon("banette", 50)]
    b.user.update_from_request_json(REQUEST)
    b.opponent.name = "p2"
    b.opponent.active = Pokemon("snorlax", 50)
    b.rqid = 1
    return b


def test_request_marks_the_active_as_reviving(battle):
    assert battle.user.active.reviving is True
    assert {p.name: p.hp for p in battle.user.reserve} == {
        "gyarados": 170,
        "banette": 0,
    }


def test_revive_pick_is_the_fainted_ally_not_the_living_one(battle):
    assert revival_blessing_choice(battle) == "switch banette"


def test_revive_pick_is_sent_as_the_fainted_allys_slot(battle):
    # Banette is 3rd in the request; Showdown accepts "switch 3" and revives Banette
    assert format_decision(battle, revival_blessing_choice(battle))[0] == "/switch 3"


def test_no_revive_pick_on_an_ordinary_request(battle):
    battle.user.active.reviving = False
    assert revival_blessing_choice(battle) is None


def test_revive_pick_with_two_fainted_takes_the_first_in_team_order(battle):
    for p in battle.user.reserve:
        p.hp = 0
    assert (
        revival_blessing_choice(battle) == "switch gyarados"
    )  # Showdown's own default for this prompt


def test_speed_inference_survives_a_switch_selection():
    """The crash itself: after the revive pick, the next message chunk holds only the opponent's move."""
    b = Battle("battle-test-speed")
    b.generation = "gen9"
    b.user.name, b.opponent.name = "p1", "p2"
    b.user.active = Pokemon("pawmot", 50)
    b.opponent.active = Pokemon("bellibolt", 50)
    b.user.active.stats[constants.SPEED] = 150
    b.opponent.active.stats[constants.SPEED] = 100
    b.user.last_selected_move = LastUsedMove("pawmot", "switch banette", 5)
    messages = [
        "|move|p2a: Bellibolt|Parabolic Charge|p1a: Pawmot",
        "|-damage|p1a: Pawmot|21/147 tox",
        "|upkeep",
        "|turn|6",
    ]
    check_speed_ranges(b, messages)  # raised KeyError: 'switchbanette' before the fix
    assert (
        b.opponent.active.speed_range.min == 0
    )  # nothing inferred from a turn with no bot move


def test_revived_ally_gets_its_hp_back(battle):
    heal_or_damage(
        battle, "|-heal|p1: Banette|83/167|[from] move: Revival Blessing".split("|")
    )
    banette = next(p for p in battle.user.reserve if p.name == "banette")
    assert (banette.hp, banette.max_hp) == (83, 167)
