import os
import json
import logging
import constants
from data import all_move_json
from data import pokedex

logger = logging.getLogger(__name__)

CURRENT_GEN = 9
PWD = os.path.dirname(os.path.abspath(__file__))


PRE_PHYSICAL_SPECIAL_SPLIT_CATEGORY_LOOKUP = {
    "normal": constants.PHYSICAL,
    "fighting": constants.PHYSICAL,
    "flying": constants.PHYSICAL,
    "poison": constants.PHYSICAL,
    "ground": constants.PHYSICAL,
    "rock": constants.PHYSICAL,
    "bug": constants.PHYSICAL,
    "ghost": constants.PHYSICAL,
    "steel": constants.PHYSICAL,
    "fire": constants.SPECIAL,
    "water": constants.SPECIAL,
    "grass": constants.SPECIAL,
    "electric": constants.SPECIAL,
    "psychic": constants.SPECIAL,
    "ice": constants.SPECIAL,
    "dragon": constants.SPECIAL,
    "dark": constants.SPECIAL,
}


def apply_move_mods(gen_number):
    logger.debug("Applying move mod for gen {}".format(gen_number))
    for gen_number in reversed(range(gen_number, CURRENT_GEN)):
        with open("{}/gen{}_move_mods.json".format(PWD, gen_number), "r") as f:
            move_mods = json.load(f)
        for move, modifications in move_mods.items():
            all_move_json[move].update(modifications)


def apply_pokedex_mods(gen_number):
    logger.debug("Applying dex mod for gen {}".format(gen_number))
    for gen_number in reversed(range(gen_number, CURRENT_GEN)):
        with open("{}/gen{}_pokedex_mods.json".format(PWD, gen_number), "r") as f:
            pokedex_mods = json.load(f)
        for pokemon, modifications in pokedex_mods.items():
            pokedex[pokemon].update(modifications)


def apply_gen_3_mods():
    constants.HIDDEN_POWER_TYPE_STRING_INDEX = -2
    constants.HIDDEN_POWER_ACTIVE_MOVE_BASE_DAMAGE_STRING = "70"
    constants.REQUEST_DICT_ABILITY = "baseAbility"
    apply_move_mods(3)
    apply_pokedex_mods(4)  # no pokedex mods in gen3 so use gen4
    undo_physical_special_split()


# these are the same as gen3
apply_gen_2_mods = apply_gen_3_mods


def apply_gen_1_mods():
    apply_gen_2_mods()
    logger.info("Applying dex mod for gen 1")
    with open("{}/gen1_pokedex_mods.json".format(PWD), "r") as f:
        pokedex_mods = json.load(f)
    for pokemon, modifications in pokedex_mods.items():
        pokedex[pokemon].update(modifications)


def apply_gen_4_mods():
    constants.HIDDEN_POWER_TYPE_STRING_INDEX = -2
    constants.HIDDEN_POWER_ACTIVE_MOVE_BASE_DAMAGE_STRING = "70"
    constants.REQUEST_DICT_ABILITY = "baseAbility"
    apply_move_mods(4)
    apply_pokedex_mods(4)


def apply_gen_5_mods():
    constants.HIDDEN_POWER_TYPE_STRING_INDEX = -2
    constants.HIDDEN_POWER_ACTIVE_MOVE_BASE_DAMAGE_STRING = "70"
    constants.REQUEST_DICT_ABILITY = "baseAbility"
    apply_move_mods(5)
    apply_pokedex_mods(5)


def apply_gen_6_mods():
    constants.REQUEST_DICT_ABILITY = "baseAbility"
    apply_move_mods(6)
    apply_pokedex_mods(6)


def apply_gen_7_mods():
    apply_move_mods(7)
    apply_pokedex_mods(7)


def apply_gen_8_mods():
    apply_move_mods(8)
    apply_pokedex_mods(8)


def undo_physical_special_split():
    for move_name, move_data in all_move_json.items():
        if move_data[constants.CATEGORY] in constants.DAMAGING_CATEGORIES:
            try:
                move_data[constants.CATEGORY] = (
                    PRE_PHYSICAL_SPECIAL_SPLIT_CATEGORY_LOOKUP[
                        move_data[constants.TYPE]
                    ]
                )
            except KeyError:
                pass


def apply_mods(game_mode):
    if "gen1" in game_mode:
        apply_gen_1_mods()
    if "gen2" in game_mode:
        apply_gen_2_mods()
    if "gen3" in game_mode:
        apply_gen_3_mods()
    if "gen4" in game_mode:
        apply_gen_4_mods()
    elif "gen5" in game_mode:
        apply_gen_5_mods()
    elif "gen6" in game_mode:
        apply_gen_6_mods()
    elif "gen7" in game_mode:
        apply_gen_7_mods()
    elif "gen8" in game_mode:
        apply_gen_8_mods()
