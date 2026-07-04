from dataclasses import dataclass, replace
from enum import Enum, auto
from typing import Callable

from fp.config import FoulPlayConfig


class StatCalculation(Enum):
    MODERN = auto()
    GEN_1_2 = auto()
    CHAMPIONS = auto()


def _modern_max_pp(base_pp: int) -> int:
    return int(base_pp * 1.6)


def _champions_max_pp(base_pp: int) -> int:
    return int(int(base_pp / 5 + 1) * 4)


@dataclass(frozen=True)
class GenerationMechanics:
    # gen1-4 formats reveal the opponent's pokemon one at a time instead of via team preview
    has_team_preview: bool = True

    # items/abilities that only exist (or can only be inferred) in certain generations
    heavy_duty_boots_exists: bool = True
    choice_scarf_exists: bool = True
    megas_exist: bool = False

    # reverse damage calculation to narrow down sets is unreliable in gen1/gen2
    supports_reverse_damage_checking: bool = True

    # paralysis quarters speed in gen1-6, halves it in gen7+
    paralysis_speed_divisor: int = 2

    # gen3/gen4 increment taunt duration at end-of-turn rather than when the move is used
    taunt_duration_increments_end_of_turn: bool = False

    # gen3-5 weather set by an ability lasts forever
    ability_weather_is_permanent: bool = False

    # gen3 does not announce pressure on switch-in
    pressure_revealed_on_switch_in: bool = True

    # gen5 rest turns are reset upon switching
    rest_turns_reset_on_switch: bool = False

    # gen3 consecutive sleep talks modify rest/sleep turns on switch-out
    tracks_consecutive_sleep_talks: bool = False

    # gen1 binding moves (wrap etc.) lock the opponent until released
    partial_trapping_mechanics: bool = False

    # gen1 swordsdance/agility nullify the effects of burn/paralysis
    stat_modification_glitches: bool = False

    # champions has no regenerator healing on switch-out
    regenerator_heals_on_switch_out: bool = True

    # champions uses different EV budgets than other randombattle formats
    randombattle_evs: tuple[int, int, int, int, int, int] = (85,) * 6
    max_ev: int = 252

    # the key for a pokemon's ability in the request JSON: gen1-6 use "baseAbility"
    request_dict_ability: str = "ability"

    # the base power appended to hiddenpower move names (e.g. hiddenpowerice60):
    # gen1-5 hiddenpower has 70 base power
    hidden_power_base_damage_string: str = "60"

    stat_calculation: StatCalculation = StatCalculation.MODERN
    max_pp: Callable[[int], int] = _modern_max_pp


GEN9 = GenerationMechanics()
GEN9CHAMPIONS = replace(
    GEN9,
    megas_exist=True,
    regenerator_heals_on_switch_out=False,
    randombattle_evs=(11,) * 6,
    max_ev=32,
    stat_calculation=StatCalculation.CHAMPIONS,
    max_pp=_champions_max_pp,
)
GEN8 = replace(GEN9)
GEN7 = replace(GEN8, heavy_duty_boots_exists=False, megas_exist=True)
GEN6 = replace(GEN7, paralysis_speed_divisor=4, request_dict_ability="baseAbility")
GEN5 = replace(
    GEN6,
    megas_exist=False,
    ability_weather_is_permanent=True,
    rest_turns_reset_on_switch=True,
    hidden_power_base_damage_string="70",
)
GEN4 = replace(
    GEN5,
    has_team_preview=False,
    rest_turns_reset_on_switch=False,
    taunt_duration_increments_end_of_turn=True,
)
GEN3 = replace(
    GEN4,
    choice_scarf_exists=False,
    pressure_revealed_on_switch_in=False,
    tracks_consecutive_sleep_talks=True,
)
GEN2 = replace(
    GEN3,
    taunt_duration_increments_end_of_turn=False,
    ability_weather_is_permanent=False,
    pressure_revealed_on_switch_in=True,
    tracks_consecutive_sleep_talks=False,
    supports_reverse_damage_checking=False,
    stat_calculation=StatCalculation.GEN_1_2,
)
GEN1 = replace(
    GEN2,
    partial_trapping_mechanics=True,
    stat_modification_glitches=True,
)

GENERATIONS = {
    "gen1": GEN1,
    "gen2": GEN2,
    "gen3": GEN3,
    "gen4": GEN4,
    "gen5": GEN5,
    "gen6": GEN6,
    "gen7": GEN7,
    "gen8": GEN8,
    "gen9": GEN9,
    "gen9champions": GEN9CHAMPIONS,
}


def generation_mechanics(generation: str) -> GenerationMechanics:
    return GENERATIONS[generation]


def current_generation_mechanics() -> GenerationMechanics:
    return generation_mechanics(FoulPlayConfig.format_spec.generation)
