import json

import pytest

from fp import constants
from fp.battle.protocol_types import PokemonIdent, SideId
from fp.battle.request import Request


def pokemon_json(**overrides):
    pkmn = {
        "ident": "p1: Pikachu",
        "details": "Pikachu, L84, M",
        "condition": "152/335",
        "active": True,
        "stats": {"atk": 159, "def": 125, "spa": 176, "spd": 159, "spe": 260},
        "moves": ["volttackle", "thunderbolt"],
        "baseAbility": "static",
        "item": "lightball",
        "pokeball": "pokeball",
    }
    pkmn.update(overrides)
    return pkmn


def request_json(**overrides):
    data = {
        "rqid": 3,
        "side": {"name": "Bot", "id": "p1", "pokemon": [pokemon_json()]},
    }
    data.update(overrides)
    return data


class TestRequest:
    def test_move_request(self):
        request = Request.from_json(
            request_json(
                active=[
                    {
                        "moves": [
                            {
                                "move": "Volt Tackle",
                                "id": "volttackle",
                                "pp": 24,
                                "maxpp": 24,
                                "target": "normal",
                                "disabled": False,
                            }
                        ],
                        "canTerastallize": "Electric",
                    }
                ],
                noCancel=True,
            )
        )
        active = request.active_pokemon_request
        assert 3 == request.rqid
        assert "volttackle" == active.moves[0].id
        assert 24 == active.moves[0].pp
        assert "Electric" == active.can_terastallize
        assert not active.trapped
        assert request.force_switch is None
        assert not request.wait

    def test_locked_move_has_no_pp(self):
        request = Request.from_json(
            request_json(
                active=[
                    {
                        "moves": [{"move": "Outrage", "id": "outrage"}],
                        "trapped": True,
                    }
                ]
            )
        )
        active = request.active_pokemon_request
        assert active.moves[0].pp is None
        assert active.trapped

    def test_struggle(self):
        request = Request.from_json(
            request_json(
                active=[
                    {
                        "moves": [
                            {
                                "move": "Struggle",
                                "id": "struggle",
                                "target": "randomNormal",
                                "disabled": False,
                            }
                        ]
                    }
                ]
            )
        )
        assert "struggle" == request.active_pokemon_request.moves[0].id

    def test_z_move_options(self):
        request = Request.from_json(
            request_json(
                active=[
                    {
                        "moves": [
                            {"move": "Thunderbolt", "id": "thunderbolt", "pp": 24},
                            {"move": "Protect", "id": "protect", "pp": 16},
                        ],
                        "canZMove": [
                            {"move": "Gigavolt Havoc", "target": "normal"},
                            None,
                        ],
                    }
                ]
            )
        )
        assert request.active_pokemon_request.can_z_move[1] is None

    def test_force_switch(self):
        request = Request.from_json(request_json(forceSwitch=[True]))
        assert (True,) == request.force_switch
        assert request.active_pokemon_request is None

    def test_wait(self):
        assert Request.from_json(request_json(wait=True)).wait

    def test_team_preview(self):
        request = Request.from_json(request_json(teamPreview=True, maxChosenTeamSize=6))
        assert request.team_preview

    def test_empty_active_slot(self):
        request = Request.from_json(
            request_json(active=[None, {"moves": [{"move": "Tackle", "id": "tackle"}]}])
        )
        assert request.active[0] is None
        assert request.active_pokemon_request is None

    def test_pokemon_fields_are_parsed(self):
        request = Request.from_json(
            request_json(
                side={
                    "name": "Bot",
                    "id": "p1",
                    "pokemon": [
                        pokemon_json(
                            condition="0 fnt",
                            ability="lightningrod",
                            teraType="Water",
                            reviving=True,
                        )
                    ],
                }
            )
        )
        pkmn = request.side.pokemon[0]
        assert SideId.P1 == request.side.id
        assert PokemonIdent(SideId.P1, None, "Pikachu") == pkmn.ident
        assert "Pikachu" == pkmn.details.species
        assert 84 == pkmn.details.level
        assert pkmn.condition.fainted
        assert "static" == pkmn.base_ability
        assert "lightningrod" == pkmn.ability
        assert "Water" == pkmn.tera_type
        assert pkmn.reviving

    def test_current_ability_is_optional(self):
        # only sent in gen7+
        assert Request.from_json(request_json()).side.pokemon[0].ability is None

    def test_status_in_condition(self):
        request = Request.from_json(
            request_json(
                side={
                    "name": "Bot",
                    "id": "p1",
                    "pokemon": [pokemon_json(condition="152/335 par")],
                }
            )
        )
        assert constants.Status.PARALYZED == request.side.pokemon[0].condition.status

    def test_unknown_keys_are_ignored(self):
        request = Request.from_json(request_json(somethingNew={"a": 1}, update=True))
        assert 3 == request.rqid

    def test_missing_required_key_raises(self):
        data = request_json()
        del data["side"]["pokemon"][0]["details"]
        with pytest.raises(KeyError):
            Request.from_json(data)

    def test_parse_from_json_string(self):
        assert 3 == Request.parse(json.dumps(request_json())).rqid
