"""
The `|request|` JSON sent to the bot, as defined by `ChoiceRequest` in PS's sim/side.ts
(plus the `rqid` that server/room-battle.ts adds)

Only the fields the bot reads are modelled. Fields PS always sends are required and
raise a KeyError when missing; fields PS marks optional default to None/False.
Keys that are not modelled are ignored.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from fp.battle.protocol_types import Condition, Details, PokemonIdent, SideId


@dataclass(frozen=True, slots=True)
class RequestMove:
    """`MoveRequestData`"""

    move: str
    id: str
    # locked moves (e.g. struggle, outrage, gen1 "fight") have no pp
    pp: int | None = None
    disabled: str | bool = False

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> "RequestMove":
        return cls(
            move=data["move"],
            id=data["id"],
            pp=data.get("pp"),
            disabled=data.get("disabled", False),
        )


@dataclass(frozen=True, slots=True)
class RequestActive:
    """`PokemonMoveRequestData`"""

    moves: tuple[RequestMove, ...]
    trapped: bool = False
    maybe_trapped: bool = False
    can_mega_evo: bool = False
    can_ultra_burst: bool = False
    can_dynamax: bool = False
    can_terastallize: str | None = None
    # one entry per move, None for a move that cannot be used as a z-move
    can_z_move: tuple[Any, ...] | None = None

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> "RequestActive":
        can_z_move = data.get("canZMove")
        return cls(
            moves=tuple(RequestMove.from_json(m) for m in data["moves"]),
            trapped=data.get("trapped", False),
            maybe_trapped=data.get("maybeTrapped", False),
            can_mega_evo=data.get("canMegaEvo", False),
            can_ultra_burst=data.get("canUltraBurst", False),
            can_dynamax=data.get("canDynamax", False),
            can_terastallize=data.get("canTerastallize"),
            can_z_move=tuple(can_z_move) if can_z_move is not None else None,
        )


@dataclass(frozen=True, slots=True)
class RequestPokemon:
    """`PokemonSwitchRequestData`"""

    ident: PokemonIdent
    details: Details
    condition: Condition
    active: bool
    stats: Mapping[str, int]
    moves: tuple[str, ...]
    base_ability: str
    item: str
    # the current ability is only sent in gen7+
    ability: str | None = None
    reviving: bool = False
    tera_type: str | None = None

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> "RequestPokemon":
        return cls(
            ident=PokemonIdent.parse(data["ident"]),
            details=Details.parse(data["details"]),
            condition=Condition.parse(data["condition"]),
            active=data["active"],
            stats=dict(data["stats"]),
            moves=tuple(data["moves"]),
            base_ability=data["baseAbility"],
            item=data["item"],
            ability=data.get("ability"),
            reviving=data.get("reviving", False),
            tera_type=data.get("teraType"),
        )


@dataclass(frozen=True, slots=True)
class RequestSide:
    """`SideRequestData`"""

    id: SideId
    pokemon: tuple[RequestPokemon, ...]

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> "RequestSide":
        return cls(
            id=SideId(data["id"]),
            pokemon=tuple(RequestPokemon.from_json(p) for p in data["pokemon"]),
        )


@dataclass(frozen=True, slots=True)
class Request:
    """
    `ChoiceRequest`: exactly one of `active` (move request), `force_switch`,
    `team_preview` or `wait` describes what is being asked for
    """

    rqid: int
    side: RequestSide
    # None for an empty slot (doubles only)
    active: tuple[RequestActive | None, ...] | None = None
    force_switch: tuple[bool, ...] | None = None
    team_preview: bool = False
    wait: bool = False

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> "Request":
        active = data.get("active")
        force_switch = data.get("forceSwitch")
        return cls(
            rqid=data["rqid"],
            side=RequestSide.from_json(data["side"]),
            active=(
                tuple(RequestActive.from_json(a) if a else None for a in active)
                if active is not None
                else None
            ),
            force_switch=tuple(force_switch) if force_switch is not None else None,
            team_preview=data.get("teamPreview", False),
            wait=data.get("wait", False),
        )

    @classmethod
    def parse(cls, request_json: str) -> "Request":
        return cls.from_json(json.loads(request_json))

    @property
    def active_pokemon_request(self) -> RequestActive | None:
        """The move request for the bot's (single) active pokemon"""
        if not self.active:
            return None
        return self.active[0]
