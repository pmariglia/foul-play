import math
import constants
from config import FoulPlayConfig

natures = {
    "lonely": {"plus": constants.ATTACK, "minus": constants.DEFENSE},
    "adamant": {"plus": constants.ATTACK, "minus": constants.SPECIAL_ATTACK},
    "naughty": {"plus": constants.ATTACK, "minus": constants.SPECIAL_DEFENSE},
    "brave": {"plus": constants.ATTACK, "minus": constants.SPEED},
    "bold": {"plus": constants.DEFENSE, "minus": constants.ATTACK},
    "impish": {"plus": constants.DEFENSE, "minus": constants.SPECIAL_ATTACK},
    "lax": {"plus": constants.DEFENSE, "minus": constants.SPECIAL_DEFENSE},
    "relaxed": {"plus": constants.DEFENSE, "minus": constants.SPEED},
    "modest": {"plus": constants.SPECIAL_ATTACK, "minus": constants.ATTACK},
    "mild": {"plus": constants.SPECIAL_ATTACK, "minus": constants.DEFENSE},
    "rash": {"plus": constants.SPECIAL_ATTACK, "minus": constants.SPECIAL_DEFENSE},
    "quiet": {"plus": constants.SPECIAL_ATTACK, "minus": constants.SPEED},
    "calm": {"plus": constants.SPECIAL_DEFENSE, "minus": constants.ATTACK},
    "gentle": {"plus": constants.SPECIAL_DEFENSE, "minus": constants.DEFENSE},
    "careful": {"plus": constants.SPECIAL_DEFENSE, "minus": constants.SPECIAL_ATTACK},
    "sassy": {"plus": constants.SPECIAL_DEFENSE, "minus": constants.SPEED},
    "timid": {"plus": constants.SPEED, "minus": constants.ATTACK},
    "hasty": {"plus": constants.SPEED, "minus": constants.DEFENSE},
    "jolly": {"plus": constants.SPEED, "minus": constants.SPECIAL_ATTACK},
    "naive": {"plus": constants.SPEED, "minus": constants.SPECIAL_DEFENSE},
    "hardy": {"plus": None, "minus": None},
    "docile": {"plus": None, "minus": None},
    "serious": {"plus": None, "minus": None},
    "bashful": {"plus": None, "minus": None},
    "quirky": {"plus": None, "minus": None},
}


def get_pokemon_info_from_condition(condition_string: str):
    if constants.FNT in condition_string:
        return 0, 0, None

    split_string = condition_string.split("/")
    hp = int(split_string[0])
    if any(s in condition_string for s in constants.NON_VOLATILE_STATUSES):
        maxhp, status = split_string[1].split(" ")
        maxhp = int(maxhp)
        return hp, maxhp, status
    else:
        maxhp = int(split_string[1])
        return hp, maxhp, None


def normalize_name(name):
    return (
        name.replace(" ", "")
        .replace("-", "")
        .replace(".", "")
        .replace("'", "")
        .replace("%", "")
        .replace("*", "")
        .replace(":", "")
        .replace("(", "")
        .replace(")", "")
        .strip()
        .lower()
        .encode("ascii", "ignore")
        .decode("utf-8")
    )


def update_stats_from_nature(stats, nature):
    new_stats = stats.copy()
    try:
        new_stats[natures[nature]["plus"]] *= 1.1
        new_stats[natures[nature]["minus"]] *= 0.9
    except KeyError:
        pass

    return new_stats


def common_pkmn_stat_calc(stat: int, iv: int, ev: int, level: int):
    return math.floor(((2 * stat + iv + math.floor(ev / 4)) * level) / 100)


def common_pkmn_stat_calc_gen_1_2(stat, level):
    return math.floor(((((stat + 15) * 2) + 63) * level) / 100)


def _calculate_stats_gen_1_2(base_stats, level):
    new_stats = dict()

    new_stats[constants.HITPOINTS] = (
        common_pkmn_stat_calc_gen_1_2(base_stats[constants.HITPOINTS], level)
        + level
        + 10
    )

    new_stats[constants.ATTACK] = (
        common_pkmn_stat_calc_gen_1_2(base_stats[constants.ATTACK], level) + 5
    )
    new_stats[constants.DEFENSE] = (
        common_pkmn_stat_calc_gen_1_2(base_stats[constants.DEFENSE], level) + 5
    )
    new_stats[constants.SPECIAL_ATTACK] = (
        common_pkmn_stat_calc_gen_1_2(base_stats[constants.SPECIAL_ATTACK], level) + 5
    )
    new_stats[constants.SPECIAL_DEFENSE] = (
        common_pkmn_stat_calc_gen_1_2(base_stats[constants.SPECIAL_DEFENSE], level) + 5
    )
    new_stats[constants.SPEED] = (
        common_pkmn_stat_calc_gen_1_2(base_stats[constants.SPEED], level) + 5
    )

    new_stats = {k: int(v) for k, v in new_stats.items()}

    return new_stats


def _calculate_stats(base_stats, level, ivs=(31,) * 6, evs=(85,) * 6, nature="serious"):
    new_stats = dict()

    new_stats[constants.HITPOINTS] = (
        common_pkmn_stat_calc(base_stats[constants.HITPOINTS], ivs[0], evs[0], level)
        + level
        + 10
    )

    new_stats[constants.ATTACK] = (
        common_pkmn_stat_calc(base_stats[constants.ATTACK], ivs[1], evs[1], level) + 5
    )

    new_stats[constants.DEFENSE] = (
        common_pkmn_stat_calc(base_stats[constants.DEFENSE], ivs[2], evs[2], level) + 5
    )

    new_stats[constants.SPECIAL_ATTACK] = (
        common_pkmn_stat_calc(
            base_stats[constants.SPECIAL_ATTACK], ivs[3], evs[3], level
        )
        + 5
    )

    new_stats[constants.SPECIAL_DEFENSE] = (
        common_pkmn_stat_calc(
            base_stats[constants.SPECIAL_DEFENSE], ivs[4], evs[4], level
        )
        + 5
    )

    new_stats[constants.SPEED] = (
        common_pkmn_stat_calc(base_stats[constants.SPEED], ivs[5], evs[5], level) + 5
    )

    new_stats = update_stats_from_nature(new_stats, nature)
    new_stats = {k: int(v) for k, v in new_stats.items()}
    return new_stats


def calculate_stats(base_stats, level, ivs=(31,) * 6, evs=(85,) * 6, nature="serious"):
    if any(g in FoulPlayConfig.pokemon_format for g in ["gen1", "gen2"]):
        return _calculate_stats_gen_1_2(base_stats, level)
    else:
        return _calculate_stats(base_stats, level, ivs, evs, nature)


POKEMON_TYPE_INDICES = {
    "normal": 0,
    "fire": 1,
    "water": 2,
    "electric": 3,
    "grass": 4,
    "ice": 5,
    "fighting": 6,
    "poison": 7,
    "ground": 8,
    "flying": 9,
    "psychic": 10,
    "bug": 11,
    "rock": 12,
    "ghost": 13,
    "dragon": 14,
    "dark": 15,
    "steel": 16,
    "fairy": 17,
    # ??? and typeless are the same thing
    "typeless": 18,
    "???": 18,
}


def possible_hidden_power_types():
    hidden_power_types = set(POKEMON_TYPE_INDICES)
    hidden_power_types.remove("typeless")
    hidden_power_types.remove("???")
    hidden_power_types.remove("fairy")
    hidden_power_types.remove("normal")
    return hidden_power_types


# fmt: off
DAMAGE_MULTIPICATION_ARRAY = [
    [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0.5, 0, 1, 1, 0.5, 1, 1],
    [1, 0.5, 0.5, 1, 2, 2, 1, 1, 1, 1, 1, 2, 0.5, 1, 0.5, 1, 2, 1, 1],
    [1, 2, 0.5, 1, 0.5, 1, 1, 1, 2, 1, 1, 1, 2, 1, 0.5, 1, 1, 1, 1],
    [1, 1, 2, 0.5, 0.5, 1, 1, 1, 0, 2, 1, 1, 1, 1, 0.5, 1, 1, 1, 1],
    [1, 0.5, 2, 1, 0.5, 1, 1, 0.5, 2, 0.5, 1, 0.5, 2, 1, 0.5, 1, 0.5, 1, 1],
    [1, 0.5, 0.5, 1, 2, 0.5, 1, 1, 2, 2, 1, 1, 1, 1, 2, 1, 0.5, 1, 1],
    [2, 1, 1, 1, 1, 2, 1, 0.5, 1, 0.5, 0.5, 0.5, 2, 0, 1, 2, 2, 0.5, 1],
    [1, 1, 1, 1, 2, 1, 1, 0.5, 0.5, 1, 1, 1, 0.5, 0.5, 1, 1, 0, 2, 1],
    [1, 2, 1, 2, 0.5, 1, 1, 2, 1, 0, 1, 0.5, 2, 1, 1, 1, 2, 1, 1],
    [1, 1, 1, 0.5, 2, 1, 2, 1, 1, 1, 1, 2, 0.5, 1, 1, 1, 0.5, 1, 1],
    [1, 1, 1, 1, 1, 1, 2, 2, 1, 1, 0.5, 1, 1, 1, 1, 0, 0.5, 1, 1],
    [1, 0.5, 1, 1, 2, 1, 0.5, 0.5, 1, 0.5, 2, 1, 1, 0.5, 1, 2, 0.5, 0.5, 1],
    [1, 2, 1, 1, 1, 2, 0.5, 1, 0.5, 2, 1, 2, 1, 1, 1, 1, 0.5, 1, 1],
    [0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 1, 1, 2, 1, 0.5, 1, 1, 1],
    [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 1, 0.5, 0, 1],
    [1, 1, 1, 1, 1, 1, 0.5, 1, 1, 1, 2, 1, 1, 2, 1, 0.5, 1, 0.5, 1],
    [1, 0.5, 0.5, 0.5, 1, 2, 1, 1, 1, 1, 1, 1, 2, 1, 1, 1, 0.5, 2, 1],
    [1, 0.5, 1, 1, 1, 1, 2, 0.5, 1, 1, 1, 1, 1, 1, 2, 2, 0.5, 1, 1],
    [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
]


def type_effectiveness_modifier(attacking_move_type, defending_types):
    modifier = 1
    attacking_type_index = POKEMON_TYPE_INDICES[attacking_move_type]
    for pkmn_type in defending_types:
        defending_type_index = POKEMON_TYPE_INDICES[pkmn_type]
        modifier *= DAMAGE_MULTIPICATION_ARRAY[attacking_type_index][
            defending_type_index
        ]

    return modifier


def is_neutral_effectiveness(move_type, defending_pokemon_types):
    multiplier = type_effectiveness_modifier(move_type, defending_pokemon_types)
    return multiplier == 1


def is_super_effective(move_type, defending_pokemon_types):
    multiplier = type_effectiveness_modifier(move_type, defending_pokemon_types)
    return multiplier > 1


def is_not_very_effective(move_type, defending_pokemon_types):
    multiplier = type_effectiveness_modifier(move_type, defending_pokemon_types)
    return multiplier < 1
