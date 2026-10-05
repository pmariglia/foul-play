import asyncio
import json

import pytest

from fp.battle.protocol import update_battle
from fp.battle.protocol_types import Details
from fp.battle.state import Battle, Pokemon
from fp.config import FoulPlayConfig
from fp.modes.base import (
    get_battle_tag_and_opponent,
    get_first_request,
    lines_after_battle_start,
    team_preview_pokemon,
)
from fp.modes.random_battle import RandomBattleMode
from fp.modes.standard_battle import StandardBattleMode


class FakeWebsocketClient:
    def __init__(self, messages):
        self.messages = list(messages)

    async def receive_message(self):
        return self.messages.pop(0)


def request_json(side_id="p1"):
    return {
        "rqid": 1,
        "active": [{"moves": [{"move": "Tackle", "id": "tackle", "pp": 56}]}],
        "side": {
            "name": "Bobby",
            "id": side_id,
            "pokemon": [
                {
                    "ident": "{}: Caterpie".format(side_id),
                    "details": "Caterpie, L100, M",
                    "condition": "100/100",
                    "active": True,
                    "stats": {"atk": 1, "def": 1, "spa": 1, "spd": 1, "spe": 1},
                    "moves": ["tackle"],
                    "baseAbility": "shielddust",
                    "ability": "shielddust",
                    "item": "",
                    "pokeball": "pokeball",
                }
            ],
        },
    }


@pytest.fixture(autouse=True)
def bot_username(monkeypatch):
    monkeypatch.setattr(FoulPlayConfig, "username", "Bobby", raising=False)
    monkeypatch.setattr(FoulPlayConfig, "log_to_file", False, raising=False)


class TestGetBattleTagAndOpponent:
    def test_reads_battle_tag_and_opponent_from_title(self):
        client = FakeWebsocketClient(
            [
                "|updatesearch|{}",
                ">battle-gen9randombattle-1\n|init|battle\n|title|Bobby vs. Bob\n|j|☆Bobby",
            ]
        )
        battle_tag, opponent_name = asyncio.run(get_battle_tag_and_opponent(client))

        assert "battle-gen9randombattle-1" == battle_tag
        assert "Bob" == opponent_name

    def test_username_matching_ignores_case_and_spaces(self):
        client = FakeWebsocketClient(
            [">battle-gen9randombattle-1\n|init|battle\n|title|Some Guy vs. bob by"]
        )
        _, opponent_name = asyncio.run(get_battle_tag_and_opponent(client))
        assert "Some Guy" == opponent_name


class TestStartBattleCommon:
    def start(self, messages):
        client = FakeWebsocketClient(
            [">battle-gen9randombattle-1\n|init|battle\n|title|Bobby vs. Bob"]
            + messages
        )
        battle, _ = asyncio.run(
            RandomBattleMode().start_battle_common(client, "gen9randombattle")
        )
        return battle

    def test_finds_bots_side(self):
        battle = self.start(
            [
                ">battle-gen9randombattle-1\n|player|p2|Bobby|1|",
                ">battle-gen9randombattle-1\n|player|p1|Bob|2|",
            ]
        )
        assert "p2" == battle.user.name
        assert "p1" == battle.opponent.name

    def test_opponent_name_contained_in_bot_name(self):
        # the opponent's name "Bob" is a substring of the bot's name "Bobby"
        battle = self.start([">battle-gen9randombattle-1\n|player|p1|Bobby|1|"])
        assert "p1" == battle.user.name
        assert "p2" == battle.opponent.name

    def test_player_lines_after_other_lines_in_the_same_chunk(self):
        battle = self.start(
            [
                ">battle-gen9randombattle-1\n|j|☆Bob\n|player|p1|Bob|2|\n|player|p2|Bobby|1|"
            ]
        )
        assert "p2" == battle.user.name


class TestGetFirstRequest:
    def test_skips_empty_requests(self):
        battle = Battle("battle-gen9randombattle-1")
        battle.generation = "gen9"
        battle.mode = RandomBattleMode()
        client = FakeWebsocketClient(
            [
                ">battle-gen9randombattle-1\n|request|",
                ">battle-gen9randombattle-1\n|request|{}".format(
                    json.dumps(request_json())
                ),
            ]
        )
        asyncio.run(get_first_request(client, battle))

        assert 1 == battle.rqid
        assert "caterpie" == battle.user.active.name
        assert "p1" == battle.user.name


class TestLinesAfterBattleStart:
    def test_none_before_the_battle_starts(self):
        assert lines_after_battle_start(">battle-x\n|player|p1|Bobby|1|", "p1") is None

    def test_omits_the_bots_switch_in(self):
        msg = "\n".join(
            [
                ">battle-x",
                "|gametype|singles",
                "|start",
                "|switch|p1a: Caterpie|Caterpie, M|100/100",
                "|switch|p2a: Weedle|Weedle, M|100/100",
                "|turn|1",
            ]
        )
        assert [
            "|switch|p2a: Weedle|Weedle, M|100/100",
            "|turn|1",
        ] == lines_after_battle_start(msg, "p1")


class TestTeamPreviewPokemon:
    def test_none_before_team_preview(self):
        assert team_preview_pokemon(">battle-x\n|player|p1|Bobby|1|", "p2") is None

    def test_returns_only_the_requested_sides_pokemon(self):
        msg = "\n".join(
            [
                ">battle-x",
                "|clearpoke",
                "|poke|p1|Pikachu, M|",
                "|poke|p2|Urshifu-*, M|",
                "|poke|p2|Arceus-*|",
                "|teampreview",
            ]
        )
        assert [
            Details.parse("Urshifu-*, M"),
            Details.parse("Arceus-*"),
        ] == team_preview_pokemon(msg, "p2")


class TestInitializeTeamPreview:
    def test_unknown_forme_with_gender(self):
        battle = Battle(None)
        battle.generation = "gen9"
        battle.mode = StandardBattleMode()
        battle.user.active = Pokemon("pikachu", 100)

        battle.initialize_team_preview([Details.parse("Urshifu-*, M")], "gen9uu")

        assert battle.opponent.reserve[0].unknown_forme


class TestUpdateBattleEmptyRequest:
    def test_empty_request_processes_updates_and_does_not_ask_for_a_decision(self):
        battle = Battle(None)
        battle.generation = "gen9"
        battle.mode = StandardBattleMode()
        battle.user.name = "p1"
        battle.opponent.name = "p2"
        battle.user.active = Pokemon("caterpie", 100)
        battle.opponent.active = Pokemon("pikachu", 100)

        assert False is update_battle(battle, "|faint|p2a: Pikachu\n|request|")
        assert 0 == battle.opponent.active.hp
