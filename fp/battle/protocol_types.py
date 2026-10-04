import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from fp import constants
from fp.battle.helpers import normalize_name


IDENT_REGEX = re.compile(r"^(p[1-4])([a-z]?)(?:: ?(.*))?$", re.DOTALL)
KWARG_REGEX = re.compile(r"^\[([^\]]+)\]\s*(.*)$", re.DOTALL)


class SideId(StrEnum):
    P1 = "p1"
    P2 = "p2"
    P3 = "p3"
    P4 = "p4"


class EffectKind(StrEnum):
    MOVE = "move"
    ABILITY = "ability"
    ITEM = "item"
    POKEMON = "pokemon"
    CONDITION = "condition"


EFFECT_PREFIXES = {
    "move:": EffectKind.MOVE,
    "ability:": EffectKind.ABILITY,
    "item:": EffectKind.ITEM,
    "pokemon:": EffectKind.POKEMON,
}


@dataclass(frozen=True, slots=True)
class PokemonIdent:
    """
    A pokemon (or side) identifier as written by `Pokemon.toString()` / `Side.toString()`

    "p1a: Nickname" -> side=p1, slot="a", nickname="Nickname"
    "p2: Nickname"  -> side=p2, slot=None, nickname="Nickname"
    """

    side: SideId
    slot: str | None
    nickname: str

    @classmethod
    def parse(cls, ident: str) -> "PokemonIdent":
        # PS only splits on the first ": " so nicknames may themselves contain colons
        match = IDENT_REGEX.match(ident.strip())
        if match is None:
            raise ValueError("Invalid pokemon identifier: '{}'".format(ident))
        side, slot, nickname = match.groups()
        return cls(
            side=SideId(side),
            slot=slot or None,
            nickname=(nickname or "").strip(),
        )

    @property
    def is_active(self) -> bool:
        return self.slot is not None


def parse_side_id(ident: str) -> SideId:
    return PokemonIdent.parse(ident).side


@dataclass(frozen=True, slots=True)
class Effect:
    """
    An effect as written by its dex `fullname`

    "move: Light Screen" -> kind=MOVE, name="Light Screen", id="lightscreen"
    "ability: Drizzle"   -> kind=ABILITY, name="Drizzle", id="drizzle"
    "Reflect"            -> kind=CONDITION, name="Reflect", id="reflect"
    """

    kind: EffectKind
    name: str
    id: str

    @classmethod
    def parse(cls, effect: str) -> "Effect":
        effect = effect.strip()
        if effect.startswith("[from]"):
            effect = effect.removeprefix("[from]").strip()

        kind = EffectKind.CONDITION
        name = effect
        for prefix, prefix_kind in EFFECT_PREFIXES.items():
            if effect.lower().startswith(prefix):
                kind = prefix_kind
                name = effect[len(prefix) :].strip()
                break

        return cls(kind=kind, name=name, id=normalize_name(name))


@dataclass(frozen=True, slots=True)
class Details:
    """
    Pokemon details as written by `Pokemon.getUpdatedDetails()` / `getFullDetails()`

    "Arceus-*, L84, F, shiny, tera:Fire"
    """

    species: str
    level: int
    gender: str | None
    shiny: bool
    tera_type: str | None

    @classmethod
    def parse(cls, details: str) -> "Details":
        parts = [p.strip() for p in details.split(",")]
        species = parts[0]
        level = 100
        gender = None
        shiny = False
        tera_type = None
        for part in parts[1:]:
            if re.fullmatch(r"L\d+", part):
                level = int(part[1:])
            elif part in ("M", "F"):
                gender = part
            elif part == "shiny":
                shiny = True
            elif part.startswith("tera:"):
                tera_type = part.removeprefix("tera:")

        return cls(
            species=species,
            level=level,
            gender=gender,
            shiny=shiny,
            tera_type=tera_type,
        )

    @property
    def unknown_forme(self) -> bool:
        # team preview hides the forme of some pokemon e.g. "Arceus-*"
        return self.species.endswith("-*")


@dataclass(frozen=True, slots=True)
class Condition:
    """
    HP and status as written by `Pokemon.getHealth()`

    "317/403 par" -> exact HP (the bot's own pokemon)
    "55/100"      -> percentage
    "24/48y"      -> pixels with a color suffix
    "0 fnt"       -> fainted
    """

    hp: int
    max_hp: int
    status: constants.Status | None
    fainted: bool

    @classmethod
    def parse(cls, condition: str) -> "Condition":
        parts = condition.strip().split()
        if constants.FNT in parts:
            return cls(hp=0, max_hp=0, status=None, fainted=True)

        hp, max_hp = parts[0].split("/")
        status = None
        if len(parts) > 1 and parts[1] in constants.NON_VOLATILE_STATUSES:
            status = constants.Status(parts[1])

        return cls(
            hp=int(hp),
            max_hp=int(max_hp.rstrip("gyr")),
            status=status,
            fainted=False,
        )

    @property
    def fraction(self) -> float:
        if self.fainted:
            return 0.0
        return self.hp / self.max_hp


@dataclass(frozen=True)
class KwArgs:
    """
    The trailing keyword arguments of a protocol line

    "[from] ability: Drizzle" -> from_=Effect(ABILITY, "Drizzle", "drizzle")
    "[of] p2a: Politoed"      -> of=PokemonIdent(p2, "a", "Politoed")
    "[silent]"                -> "silent" in kwargs
    "[spread] p1a,p2a"        -> kwargs.get("spread") == "p1a,p2a"
    """

    from_: Effect | None = None
    of: PokemonIdent | None = None
    values: Mapping[str, str] = field(default_factory=dict)

    @classmethod
    def parse(cls, split_msg: list[str]) -> "KwArgs":
        # positional args never start with "[": idents start with the side id
        # and nicknames only ever appear inside idents
        values = {}
        for part in split_msg[2:]:
            match = KWARG_REGEX.match(part)
            if match is not None:
                key, value = match.groups()
                values.setdefault(key.strip(), value.strip())

        from_ = Effect.parse(values["from"]) if values.get("from") else None
        of = PokemonIdent.parse(values["of"]) if values.get("of") else None
        return cls(from_=from_, of=of, values=values)

    def __contains__(self, key: str) -> bool:
        return key in self.values

    def get(self, key: str) -> str | None:
        return self.values.get(key)

    def is_from(self, effect_id: str, kind: EffectKind | None = None) -> bool:
        return (
            self.from_ is not None
            and self.from_.id == effect_id
            and (kind is None or self.from_.kind == kind)
        )


def positional_args(split_msg: list[str]) -> list[str]:
    """The non-keyword arguments of a protocol line, excluding the message type"""
    return [p for p in split_msg[2:] if KWARG_REGEX.match(p) is None]
