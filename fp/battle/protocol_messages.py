from collections.abc import Iterable
from dataclasses import dataclass, field

from fp.battle.helpers import normalize_name
from fp.data import z_move_json
from fp.battle.request import Request
from fp.battle.protocol_types import (
    Condition,
    Details,
    Effect,
    KwArgs,
    PokemonIdent,
    SideId,
    parse_side_id,
    positional_args,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class Message:
    kwargs: KwArgs = field(default_factory=KwArgs)
    raw: str = field(default="", compare=False, repr=False)


@dataclass(frozen=True, slots=True)
class Switch(Message):
    pokemon: PokemonIdent
    details: Details
    condition: Condition
    is_drag: bool


@dataclass(frozen=True, slots=True)
class Replace(Message):
    pokemon: PokemonIdent
    details: Details


@dataclass(frozen=True, slots=True)
class FormeChange(Message):
    """`detailschange` (permanent) and `-formechange` (temporary)"""

    pokemon: PokemonIdent
    details: Details
    permanent: bool


@dataclass(frozen=True, slots=True)
class Faint(Message):
    pokemon: PokemonIdent


@dataclass(frozen=True, slots=True)
class Fail(Message):
    pokemon: PokemonIdent
    action: str | None


@dataclass(frozen=True, slots=True)
class Damage(Message):
    pokemon: PokemonIdent
    condition: Condition


@dataclass(frozen=True, slots=True)
class Heal(Message):
    pokemon: PokemonIdent
    condition: Condition


@dataclass(frozen=True, slots=True)
class SetHp(Message):
    pokemon: PokemonIdent
    condition: Condition


@dataclass(frozen=True, slots=True)
class Move(Message):
    user: PokemonIdent
    move: str
    target: PokemonIdent | None

    @property
    def move_id(self) -> str:
        return normalize_name(self.move)

    @property
    def is_z_move(self) -> bool:
        return self.move.startswith("Z-") or self.move_id in z_move_json

    @property
    def base_move_id(self) -> str | None:
        """
        The move that was chosen, which is not the same as the move shown for a Z-Move.
        None when the protocol does not say which move a Z-Move came from

        |move|p1a: Charizard|Flamethrower|p2a: Venusaur                -> flamethrower
        |move|p1a: Charizard|Z-Hold Hands|null|[anim]Hold Hands        -> holdhands
        |move|p1a: Pikachu|Catastropika|p2a: Venusaur|[zeffect]        -> volttackle
        |move|p1a: Charizard|Inferno Overdrive|p2a: Venusaur|[zeffect] -> None
        """
        if self.move.startswith("Z-"):
            return normalize_name(self.kwargs.get("anim") or self.move[2:])
        if self.move_id in z_move_json:
            return z_move_json[self.move_id]["base"]
        return self.move_id


@dataclass(frozen=True, slots=True)
class Miss(Message):
    source: PokemonIdent
    target: PokemonIdent | None


@dataclass(frozen=True, slots=True)
class Crit(Message):
    pokemon: PokemonIdent


@dataclass(frozen=True, slots=True)
class SuperEffective(Message):
    pokemon: PokemonIdent


@dataclass(frozen=True, slots=True)
class Resisted(Message):
    pokemon: PokemonIdent


@dataclass(frozen=True, slots=True)
class Boost(Message):
    pokemon: PokemonIdent
    stat: str
    amount: int


@dataclass(frozen=True, slots=True)
class Unboost(Message):
    pokemon: PokemonIdent
    stat: str
    amount: int


@dataclass(frozen=True, slots=True)
class SetBoost(Message):
    pokemon: PokemonIdent
    stat: str
    amount: int


@dataclass(frozen=True, slots=True)
class Status(Message):
    pokemon: PokemonIdent
    status: str


@dataclass(frozen=True, slots=True)
class CureStatus(Message):
    pokemon: PokemonIdent
    status: str


@dataclass(frozen=True, slots=True)
class CureTeam(Message):
    pokemon: PokemonIdent


@dataclass(frozen=True, slots=True)
class Activate(Message):
    pokemon: PokemonIdent
    effect: Effect
    args: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Anim(Message):
    pokemon: PokemonIdent
    move: str
    target: PokemonIdent | None


@dataclass(frozen=True, slots=True)
class Prepare(Message):
    pokemon: PokemonIdent
    move: str


@dataclass(frozen=True, slots=True)
class Start(Message):
    """`-start` and `-singlemove`"""

    pokemon: PokemonIdent
    effect: Effect
    args: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class End(Message):
    pokemon: PokemonIdent
    effect: Effect


@dataclass(frozen=True, slots=True)
class Weather(Message):
    weather: Effect


@dataclass(frozen=True, slots=True)
class FieldStart(Message):
    effect: Effect


@dataclass(frozen=True, slots=True)
class FieldEnd(Message):
    effect: Effect


@dataclass(frozen=True, slots=True)
class SideStart(Message):
    side: SideId
    effect: Effect


@dataclass(frozen=True, slots=True)
class SideEnd(Message):
    side: SideId
    effect: Effect


@dataclass(frozen=True, slots=True)
class SwapSideConditions(Message):
    pass


@dataclass(frozen=True, slots=True)
class Item(Message):
    # gen4/5 frisk does not identify the pokemon holding the item:
    # |-item||Life Orb|[from] ability: Frisk|[of] p2a: Furret
    pokemon: PokemonIdent | None
    item: str


@dataclass(frozen=True, slots=True)
class EndItem(Message):
    pokemon: PokemonIdent
    item: str


@dataclass(frozen=True, slots=True)
class Immune(Message):
    pokemon: PokemonIdent


@dataclass(frozen=True, slots=True)
class Ability(Message):
    pokemon: PokemonIdent
    ability: str
    args: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Transform(Message):
    pokemon: PokemonIdent
    target: PokemonIdent


@dataclass(frozen=True, slots=True)
class Mega(Message):
    pokemon: PokemonIdent
    species: str
    mega_stone: str | None


@dataclass(frozen=True, slots=True)
class Terastallize(Message):
    pokemon: PokemonIdent
    tera_type: str


@dataclass(frozen=True, slots=True)
class ZPower(Message):
    pokemon: PokemonIdent


@dataclass(frozen=True, slots=True)
class ClearNegativeBoost(Message):
    pokemon: PokemonIdent


@dataclass(frozen=True, slots=True)
class ClearPositiveBoost(Message):
    """`target`'s positive boosts are cleared by `source` e.g. spectral thief"""

    target: PokemonIdent
    source: PokemonIdent
    effect: Effect


@dataclass(frozen=True, slots=True)
class ClearBoost(Message):
    pokemon: PokemonIdent


@dataclass(frozen=True, slots=True)
class ClearAllBoost(Message):
    pass


@dataclass(frozen=True, slots=True)
class SingleTurn(Message):
    pokemon: PokemonIdent
    effect: Effect


@dataclass(frozen=True, slots=True)
class MustRecharge(Message):
    pokemon: PokemonIdent


@dataclass(frozen=True, slots=True)
class CopyBoost(Message):
    pokemon: PokemonIdent
    target: PokemonIdent


@dataclass(frozen=True, slots=True)
class SwapBoost(Message):
    pokemon: PokemonIdent
    target: PokemonIdent
    # None means every boost is swapped
    stats: tuple[str, ...] | None


@dataclass(frozen=True, slots=True)
class EndAbility(Message):
    pokemon: PokemonIdent


@dataclass(frozen=True, slots=True)
class Cant(Message):
    pokemon: PokemonIdent
    reason: Effect
    move: str | None


@dataclass(frozen=True, slots=True)
class Upkeep(Message):
    pass


@dataclass(frozen=True, slots=True)
class Turn(Message):
    number: int


@dataclass(frozen=True, slots=True)
class Inactive(Message):
    message: str


@dataclass(frozen=True, slots=True)
class InactiveOff(Message):
    message: str


@dataclass(frozen=True, slots=True)
class NoInit(Message):
    reason: str
    args: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Player(Message):
    # |player|p1| is sent with no username when a player leaves
    side: SideId
    username: str | None


@dataclass(frozen=True, slots=True)
class Title(Message):
    title: str


@dataclass(frozen=True, slots=True)
class ClearPoke(Message):
    """Team preview is starting"""


@dataclass(frozen=True, slots=True)
class Poke(Message):
    """A pokemon revealed during team preview"""

    side: SideId
    details: Details


@dataclass(frozen=True, slots=True)
class BattleStart(Message):
    """`|start`: the battle is starting (not to be confused with `-start`)"""


@dataclass(frozen=True, slots=True)
class RequestMessage(Message):
    # an empty `|request|` is sent when there is nothing to choose
    request: Request | None


@dataclass(frozen=True, slots=True)
class Unknown(Message):
    type: str
    args: tuple[str, ...]


def _optional(args: list[str], index: int) -> str | None:
    if index < len(args) and args[index] != "":
        return args[index]
    return None


def _optional_ident(args: list[str], index: int) -> PokemonIdent | None:
    value = _optional(args, index)
    # PS writes a missing target as "null", e.g. a z-move with no target:
    # |move|p1a: Charizard|Z-Hold Hands|null|[anim]Hold Hands|[notarget]
    if value is None or value == "null":
        return None
    return PokemonIdent.parse(value)


def _parse_switch(args, kwargs, raw, msg_type):
    return Switch(
        PokemonIdent.parse(args[0]),
        Details.parse(args[1]),
        Condition.parse(args[2]),
        is_drag=msg_type == "drag",
        kwargs=kwargs,
        raw=raw,
    )


def _parse_forme_change(args, kwargs, raw, msg_type):
    return FormeChange(
        PokemonIdent.parse(args[0]),
        Details.parse(args[1]),
        permanent=msg_type == "detailschange",
        kwargs=kwargs,
        raw=raw,
    )


def _parse_pokemon_and_condition(message_class):
    def parse(args, kwargs, raw, _):
        return message_class(
            PokemonIdent.parse(args[0]),
            Condition.parse(args[1]),
            kwargs=kwargs,
            raw=raw,
        )

    return parse


def _parse_boost(message_class):
    def parse(args, kwargs, raw, _):
        return message_class(
            PokemonIdent.parse(args[0]),
            args[1].strip(),
            int(args[2]),
            kwargs=kwargs,
            raw=raw,
        )

    return parse


def _parse_pokemon_only(message_class):
    def parse(args, kwargs, raw, _):
        return message_class(PokemonIdent.parse(args[0]), kwargs=kwargs, raw=raw)

    return parse


def _parse_pokemon_and_string(message_class):
    def parse(args, kwargs, raw, _):
        return message_class(
            PokemonIdent.parse(args[0]), args[1].strip(), kwargs=kwargs, raw=raw
        )

    return parse


def _parse_pokemon_and_effect(message_class):
    def parse(args, kwargs, raw, _):
        return message_class(
            PokemonIdent.parse(args[0]), Effect.parse(args[1]), kwargs=kwargs, raw=raw
        )

    return parse


def _parse_pokemon_effect_and_args(message_class):
    def parse(args, kwargs, raw, _):
        return message_class(
            PokemonIdent.parse(args[0]),
            Effect.parse(args[1]),
            tuple(args[2:]),
            kwargs=kwargs,
            raw=raw,
        )

    return parse


def _parse_effect_only(message_class):
    def parse(args, kwargs, raw, _):
        return message_class(Effect.parse(args[0]), kwargs=kwargs, raw=raw)

    return parse


def _parse_side_and_effect(message_class):
    def parse(args, kwargs, raw, _):
        return message_class(
            parse_side_id(args[0]), Effect.parse(args[1]), kwargs=kwargs, raw=raw
        )

    return parse


def _parse_no_args(message_class):
    def parse(args, kwargs, raw, _):
        return message_class(kwargs=kwargs, raw=raw)

    return parse


def _parse_move(args, kwargs, raw, _):
    return Move(
        PokemonIdent.parse(args[0]),
        args[1].strip(),
        _optional_ident(args, 2),
        kwargs=kwargs,
        raw=raw,
    )


def _parse_anim(args, kwargs, raw, _):
    return Anim(
        PokemonIdent.parse(args[0]),
        args[1].strip(),
        _optional_ident(args, 2),
        kwargs=kwargs,
        raw=raw,
    )


def _parse_miss(args, kwargs, raw, _):
    return Miss(
        PokemonIdent.parse(args[0]), _optional_ident(args, 1), kwargs=kwargs, raw=raw
    )


def _parse_fail(args, kwargs, raw, _):
    return Fail(PokemonIdent.parse(args[0]), _optional(args, 1), kwargs=kwargs, raw=raw)


def _parse_item(args, kwargs, raw, _):
    return Item(_optional_ident(args, 0), args[1].strip(), kwargs=kwargs, raw=raw)


def _parse_ability(args, kwargs, raw, _):
    return Ability(
        PokemonIdent.parse(args[0]),
        args[1].strip(),
        tuple(args[2:]),
        kwargs=kwargs,
        raw=raw,
    )


def _parse_replace(args, kwargs, raw, _):
    return Replace(
        PokemonIdent.parse(args[0]), Details.parse(args[1]), kwargs=kwargs, raw=raw
    )


def _parse_transform(args, kwargs, raw, _):
    return Transform(
        PokemonIdent.parse(args[0]),
        PokemonIdent.parse(args[1]),
        kwargs=kwargs,
        raw=raw,
    )


def _parse_copy_boost(args, kwargs, raw, _):
    return CopyBoost(
        PokemonIdent.parse(args[0]),
        PokemonIdent.parse(args[1]),
        kwargs=kwargs,
        raw=raw,
    )


def _parse_swap_boost(args, kwargs, raw, _):
    # |-swapboost|p1a: Shuckle|p2a: Dragonite|def, spd|[from] move: Guard Swap
    # |-swapboost|p1a: Manaphy|p2a: Dragonite|[from] move: Heart Swap
    stats = _optional(args, 2)
    return SwapBoost(
        PokemonIdent.parse(args[0]),
        PokemonIdent.parse(args[1]),
        tuple(s.strip() for s in stats.split(",")) if stats else None,
        kwargs=kwargs,
        raw=raw,
    )


def _parse_mega(args, kwargs, raw, _):
    return Mega(
        PokemonIdent.parse(args[0]),
        args[1].strip(),
        _optional(args, 2),
        kwargs=kwargs,
        raw=raw,
    )


def _parse_cant(args, kwargs, raw, _):
    return Cant(
        PokemonIdent.parse(args[0]),
        Effect.parse(args[1]),
        _optional(args, 2),
        kwargs=kwargs,
        raw=raw,
    )


def _parse_clear_positive_boost(args, kwargs, raw, _):
    return ClearPositiveBoost(
        PokemonIdent.parse(args[0]),
        PokemonIdent.parse(args[1]),
        Effect.parse(args[2]),
        kwargs=kwargs,
        raw=raw,
    )


def _parse_player(args, kwargs, raw, _):
    return Player(parse_side_id(args[0]), _optional(args, 1), kwargs=kwargs, raw=raw)


def _parse_poke(args, kwargs, raw, _):
    return Poke(parse_side_id(args[0]), Details.parse(args[1]), kwargs=kwargs, raw=raw)


def _parse_turn(args, kwargs, raw, _):
    return Turn(int(args[0]), kwargs=kwargs, raw=raw)


def _parse_noinit(args, kwargs, raw, _):
    return NoInit(args[0], tuple(args[1:]), kwargs=kwargs, raw=raw)


PARSERS = {
    "switch": _parse_switch,
    "drag": _parse_switch,
    "replace": _parse_replace,
    "detailschange": _parse_forme_change,
    "-formechange": _parse_forme_change,
    "faint": _parse_pokemon_only(Faint),
    "-fail": _parse_fail,
    "-damage": _parse_pokemon_and_condition(Damage),
    "-heal": _parse_pokemon_and_condition(Heal),
    "-sethp": _parse_pokemon_and_condition(SetHp),
    "move": _parse_move,
    "-miss": _parse_miss,
    "-crit": _parse_pokemon_only(Crit),
    "-supereffective": _parse_pokemon_only(SuperEffective),
    "-resisted": _parse_pokemon_only(Resisted),
    "-boost": _parse_boost(Boost),
    "-unboost": _parse_boost(Unboost),
    "-setboost": _parse_boost(SetBoost),
    "-status": _parse_pokemon_and_string(Status),
    "-curestatus": _parse_pokemon_and_string(CureStatus),
    "-cureteam": _parse_pokemon_only(CureTeam),
    "-activate": _parse_pokemon_effect_and_args(Activate),
    "-anim": _parse_anim,
    "-prepare": _parse_pokemon_and_string(Prepare),
    "-start": _parse_pokemon_effect_and_args(Start),
    "-singlemove": _parse_pokemon_effect_and_args(Start),
    "-end": _parse_pokemon_and_effect(End),
    "-weather": _parse_effect_only(Weather),
    "-fieldstart": _parse_effect_only(FieldStart),
    "-fieldend": _parse_effect_only(FieldEnd),
    "-sidestart": _parse_side_and_effect(SideStart),
    "-sideend": _parse_side_and_effect(SideEnd),
    "-swapsideconditions": _parse_no_args(SwapSideConditions),
    "-item": _parse_item,
    "-enditem": _parse_pokemon_and_string(EndItem),
    "-immune": _parse_pokemon_only(Immune),
    "-ability": _parse_ability,
    "-transform": _parse_transform,
    "-mega": _parse_mega,
    "-terastallize": _parse_pokemon_and_string(Terastallize),
    "-zpower": _parse_pokemon_only(ZPower),
    "-clearnegativeboost": _parse_pokemon_only(ClearNegativeBoost),
    "-clearpositiveboost": _parse_clear_positive_boost,
    "-clearboost": _parse_pokemon_only(ClearBoost),
    "-clearallboost": _parse_no_args(ClearAllBoost),
    "-singleturn": _parse_pokemon_and_effect(SingleTurn),
    "-mustrecharge": _parse_pokemon_only(MustRecharge),
    "-endability": _parse_pokemon_only(EndAbility),
    "-copyboost": _parse_copy_boost,
    "-swapboost": _parse_swap_boost,
    "cant": _parse_cant,
    "upkeep": _parse_no_args(Upkeep),
    "turn": _parse_turn,
    "noinit": _parse_noinit,
    "player": _parse_player,
    "clearpoke": _parse_no_args(ClearPoke),
    "poke": _parse_poke,
    "start": _parse_no_args(BattleStart),
}


def parse_split(split_msg: list[str]) -> Message | None:
    """
    Parse a protocol line that has already been split on "|"

    Returns None for anything that is not a protocol message (e.g. the `>battle-...` room id line)
    """
    if len(split_msg) < 2:
        return None

    msg_type = split_msg[1].strip()
    raw = "|".join(split_msg)

    # free-text and JSON payloads may contain "|" themselves
    # |inactive|Time left: 150 sec this turn | 290 sec total
    payload = "|".join(split_msg[2:])
    if msg_type == "inactive":
        return Inactive(payload, raw=raw)
    if msg_type == "inactiveoff":
        return InactiveOff(payload, raw=raw)
    if msg_type == "title":
        return Title(payload, raw=raw)
    if msg_type == "request":
        request = Request.parse(payload) if payload.strip() else None
        return RequestMessage(request, raw=raw)

    kwargs = KwArgs.parse(split_msg)
    args = positional_args(split_msg)
    parser = PARSERS.get(msg_type)
    if parser is None:
        return Unknown(msg_type, tuple(args), kwargs=kwargs, raw=raw)
    return parser(args, kwargs, raw, msg_type)


def parse_line(line: str) -> Message | None:
    return parse_split(line.split("|"))


def parse_lines(lines: Iterable[str]) -> list[Message]:
    """Parse protocol lines, dropping anything that is not a protocol message"""
    return [msg for msg in (parse_line(line) for line in lines) if msg is not None]


def parse_as[T: Message](message_class: type[T], split_msg: list[str]) -> T:
    """Parse a protocol line that is expected to be a specific message type"""
    msg = parse_split(split_msg)
    if not isinstance(msg, message_class):
        raise TypeError("expected {}, got {!r}".format(message_class.__name__, msg))
    return msg
