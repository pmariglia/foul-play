import re
from dataclasses import dataclass
from functools import lru_cache

from fp.constants import BattleType

_GEN_REGEX = re.compile(r"gen(\d+)")


@dataclass(frozen=True)
class FormatSpec:
    full_name: str
    gen_number: int
    battle_type: BattleType
    champions: bool = False
    blitz: bool = False
    national_dex: bool = False

    @property
    def gen_string(self) -> str:
        return "gen{}".format(self.gen_number)

    @property
    def generation(self) -> str:
        # the key for generation-based behaviour: champions is treated as its own generation
        if self.champions:
            return "gen{}champions".format(self.gen_number)
        return self.gen_string

    @property
    def base_name(self) -> str:
        # the format name without the blitz suffix, e.g. for dataset/stats lookups
        if self.blitz:
            return self.full_name[: -len("blitz")]
        return self.full_name

    @classmethod
    def from_format_string(cls, format_string: str) -> "FormatSpec":
        return _parse_format_string(format_string)

    def __str__(self):
        return self.full_name


@lru_cache(maxsize=None)
def _parse_format_string(format_string: str) -> FormatSpec:
    gen_match = _GEN_REGEX.search(format_string)
    if "random" in format_string:
        battle_type = BattleType.RANDOM_BATTLE
    elif "battlefactory" in format_string:
        battle_type = BattleType.BATTLE_FACTORY
    else:
        battle_type = BattleType.STANDARD_BATTLE
    return FormatSpec(
        full_name=format_string,
        gen_number=int(gen_match.group(1)) if gen_match else 0,
        battle_type=battle_type,
        champions="champions" in format_string,
        blitz=format_string.endswith("blitz"),
        national_dex="nationaldex" in format_string,
    )
