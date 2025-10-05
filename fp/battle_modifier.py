import re
import json
from copy import deepcopy, copy
import logging

import constants
from constants import BattleType
from data import all_move_json
from data import pokedex
from data.pkmn_sets import (
    SmogonSets,
    RandomBattleTeamDatasets,
    TeamDatasets,
    PredictedPokemonSet,
)
from fp.battle import Pokemon, Battler, Battle
from fp.battle import LastUsedMove
from fp.battle import DamageDealt
from fp.battle import StatRange
from fp.search.poke_engine_helpers import poke_engine_get_damage_rolls
from fp.helpers import normalize_name, type_effectiveness_modifier
from fp.helpers import get_pokemon_info_from_condition
from fp.helpers import calculate_stats
from fp.helpers import (
    is_not_very_effective,
    is_super_effective,
    is_neutral_effectiveness,
)
from fp.battle import boost_multiplier_lookup


logger = logging.getLogger(__name__)

MOVE_END_STRINGS = {"move", "switch", "upkeep", "-miss", ""}
ITEMS_REVEALED_ON_SWITCH_IN = [
    # boosterenergy technically only revealed if pkmn has quarkdrive/protosynthesis
    # but if they don't have that it doesn't matter
    "boosterenergy",
    "airballoon",
]
ABILITIES_REVEALED_ON_SWITCH_IN = [
    "intimidate",
    "pressure",
    "neutralizinggas",
    "sandstream",
    "drought",
    "drizzle",
    "snowwarning",
]

SIDE_CONDITION_DEFAULT_DURATION = {
    constants.REFLECT: 5,
    constants.LIGHT_SCREEN: 5,
    constants.AURORA_VEIL: 5,
    constants.SAFEGUARD: 5,
    constants.MIST: 5,
    constants.TAILWIND: 4,
}


def crit_rate_for_generation(generation):
    if generation == "gen1":
        return 205 / 105
    elif generation in [
        "gen2",
        "gen3",
        "gen4",
        "gen5",
    ]:
        return 2.0
    else:
        return 1.5


def can_have_priority_modified(battle, pokemon, move_name):
    return (
        "prankster"
        in [
            normalize_name(a)
            for a in pokedex[pokemon.name][constants.ABILITIES].values()
        ]
        or (move_name == "grassyglide" and battle.field == constants.GRASSY_TERRAIN)
        or (
            move_name in all_move_json
            and all_move_json[move_name][constants.CATEGORY] == constants.STATUS
            and "myceliummight"
            in [
                normalize_name(a)
                for a in pokedex[pokemon.name][constants.ABILITIES].values()
            ]
        )
    )


def can_have_speed_modified(battle, pokemon):
    return (
        (
            pokemon.item is None
            and "unburden"
            in [
                normalize_name(a)
                for a in pokedex[pokemon.name][constants.ABILITIES].values()
            ]
        )
        or (
            battle.weather == constants.RAIN
            and pokemon.ability is None
            and "swiftswim"
            in [
                normalize_name(a)
                for a in pokedex[pokemon.name][constants.ABILITIES].values()
            ]
        )
        or (
            battle.weather == constants.SUN
            and pokemon.ability is None
            and "chlorophyll"
            in [
                normalize_name(a)
                for a in pokedex[pokemon.name][constants.ABILITIES].values()
            ]
        )
        or (
            battle.weather == constants.SAND
            and pokemon.ability is None
            and "sandrush"
            in [
                normalize_name(a)
                for a in pokedex[pokemon.name][constants.ABILITIES].values()
            ]
        )
        or (
            battle.weather in constants.HAIL_OR_SNOW
            and pokemon.ability is None
            and "slushrush"
            in [
                normalize_name(a)
                for a in pokedex[pokemon.name][constants.ABILITIES].values()
            ]
        )
        or (
            battle.field == constants.ELECTRIC_TERRAIN
            and pokemon.ability is None
            and "surgesurfer"
            in [
                normalize_name(a)
                for a in pokedex[pokemon.name][constants.ABILITIES].values()
            ]
        )
        or (
            pokemon.status == constants.PARALYZED
            and pokemon.ability is None
            and "quickfeet"
            in [
                normalize_name(a)
                for a in pokedex[pokemon.name][constants.ABILITIES].values()
            ]
        )
    )


def remove_volatile(pkmn, volatile):
    pkmn.volatile_statuses = [vs for vs in pkmn.volatile_statuses if vs != volatile]


def unlikely_to_have_choice_item(move_name):
    try:
        move_dict = all_move_json[move_name]
    except KeyError:
        return False

    if (
        constants.BOOSTS in move_dict
        and move_dict[constants.CATEGORY] == constants.STATUS
    ):
        return True
    elif move_name in ["substitute", "roost", "recover"]:
        return True

    return False


def is_opponent(battle, split_msg):
    return not split_msg[2].startswith(battle.user.name)


def get_move_information(m):
    # Given a |move| line from the PS protocol, extract the user of the move and the move object
    try:
        split_move_line = m.split("|")
        return split_move_line[2], all_move_json[normalize_name(split_move_line[3])]
    except KeyError:
        logger.warning(
            "Unknown move {} - using standard 0 priority move".format(
                normalize_name(m.split("|")[3])
            )
        )
        return m.split("|")[2], {constants.ID: "unknown", constants.PRIORITY: 0}


def request(battle, split_msg):
    if len(split_msg) >= 2:
        battle_json = json.loads(split_msg[2].strip("'"))
        logger.debug("Received battle JSON from server: {}".format(battle_json))
        battle.rqid = battle_json[constants.RQID]

        if battle_json.get(constants.FORCE_SWITCH):
            battle.force_switch = True
        else:
            battle.force_switch = False

        if battle_json.get(constants.WAIT):
            battle.wait = True
        else:
            battle.wait = False

        battle.request_json = battle_json


def inactive(battle, split_msg):
    regex_string = r"(\d+) sec this turn"
    if split_msg[2].startswith(constants.TIME_LEFT):
        capture = re.search(regex_string, split_msg[2])
        try:
            time_left = int(capture.group(1))
            battle.time_remaining = time_left
            logger.debug("Time left: {}".format(time_left))
        except ValueError:
            logger.warning("{} is not a valid int".format(capture.group(1)))
        except AttributeError:
            logger.warning(
                "'{}' does not match the regex '{}'".format(split_msg[2], regex_string)
            )


def inactiveoff(battle, _):
    battle.time_remaining = None


def user_just_switched_into_zoroark(battle, switch_or_drag):
    """
    some truly heinous shit going on here, can we ban this fucker?

    Two scenarios we can detect we are a zoroark:
      1. We switched and the last action we selected starts with `switch zoroark` (to account for both zoroarks)
      2. We were dragged (circle throw, etc) AND the active pkmn on the next turn is zoroark

    is it not sound to check for "we switched or dragged and the request JSON has zoroark as active?"
    No. If we switched into zoroark and then got circle-thrown out then the request JSON would not have
        zoroark as active but our switch needs to have been into zoroark.

    This doesn't need to deal with the first-turn switch-in of the user's Zoroark because the first-turn is
    instantiated from the request_json
    """

    return (
        # Scenario 1
        (
            switch_or_drag == "switch"
            and battle.user.last_selected_move.move.startswith("switch zoroark")
        )
        # Scenario 2
        or (
            switch_or_drag == "drag"
            and battle.request_json is not None
            and battle.request_json[constants.SIDE][constants.POKEMON][0][
                constants.DETAILS
            ].startswith("Zoroark")
            and battle.request_json[constants.SIDE][constants.POKEMON][0][
                constants.ACTIVE
            ]
        )
    )


def switch(battle, split_msg):
    switch_or_drag(battle, split_msg, switch_or_drag="switch")


def drag(battle, split_msg):
    switch_or_drag(battle, split_msg, switch_or_drag="drag")


def switch_or_drag(battle, split_msg, switch_or_drag="switch"):
    if is_opponent(battle, split_msg):
        side_name = "opponent"
        side = battle.opponent
        other_side = battle.user
        logger.info("Opponent has switched - clearing the last used move")
    else:
        side_name = "user"
        side = battle.user
        other_side = battle.opponent
        side.side_conditions[constants.TOXIC_COUNT] = 0

    baton_passed_boosts = None
    switch_keep_volatiles = []
    if side.active is not None:
        # set the pkmn's types back to their original value if the types were changed
        # if the pkmn is terastallized, this does not happen
        if constants.TYPECHANGE in side.active.volatile_statuses:
            original_types = pokedex[side.active.name][constants.TYPES]
            logger.info(
                "{} had it's type changed - changing its types back to {}".format(
                    side.active.name, original_types
                )
            )
            side.active.types = original_types

        # if the target was transformed, reset its transformed attributes
        if constants.TRANSFORM in side.active.volatile_statuses:
            logger.info(
                "{} was transformed. Resetting its transformed attributes".format(
                    side.active.name
                )
            )
            side.active.stats = calculate_stats(
                side.active.base_stats, side.active.level
            )
            side.active.ability = side.active.original_ability
            side.active.moves = []
            side.active.types = pokedex[side.active.name][constants.TYPES]

        if (
            side.active.original_ability is not None
            and side.active.ability != side.active.original_ability
        ):
            logger.info(
                "{}'s ability was modified to {} - setting it back to {} on switch-out".format(
                    side.active.name, side.active.ability, side.active.original_ability
                )
            )
            side.active.ability = side.active.original_ability
            side.active.original_ability = None

        if split_msg[-1] == "[from] Baton Pass":
            side.baton_passing = False
            logger.info(
                "Baton passing, preserving boosts: {}".format(dict(side.active.boosts))
            )
            baton_passed_boosts = deepcopy(side.active.boosts)

            if constants.SUBSTITUTE in side.active.volatile_statuses:
                logger.info("Baton passing, preserving substitute")
                switch_keep_volatiles.append(constants.SUBSTITUTE)
            if constants.LEECH_SEED in side.active.volatile_statuses:
                logger.info("Baton passing, preserving leechseed")
                switch_keep_volatiles.append(constants.LEECH_SEED)
        elif split_msg[-1] == "[from] Shed Tail":
            side.shed_tailing = False

            if constants.SUBSTITUTE in side.active.volatile_statuses:
                logger.info("Shed tailing, preserving substitute")
                switch_keep_volatiles.append(constants.SUBSTITUTE)

        # gen5 rest turns are reset upon switching
        if battle.generation == "gen5" and side.active.status == constants.SLEEP:
            if side.active.rest_turns != 0:
                logger.info(
                    "{} switched while asleep and with non-zero rest turns, resetting rest turns to 3".format(
                        side.active.name
                    )
                )
                side.active.rest_turns = 3
            else:
                logger.info(
                    "{} switched while asleep, resetting sleep turns to 0".format(
                        side.active.name
                    )
                )
                side.active.sleep_turns = 0

        # gen3 rest turns are decremented by the number of consecutive sleep talks
        if battle.generation == "gen3" and side.active.status == constants.SLEEP:
            if side.active.rest_turns != 0:
                side.active.rest_turns += side.active.gen_3_consecutive_sleep_talks
                logger.info(
                    "gen3 {} switched with {} consecutive sleep talks. Incrementing rest turns by {}".format(
                        side.active.name,
                        side.active.gen_3_consecutive_sleep_talks,
                        side.active.gen_3_consecutive_sleep_talks,
                    )
                )
            elif side.active.sleep_turns != 0:
                logger.info(
                    "gen3 {} switched with {} consecutive sleep talks. Decrementing sleep turns by {}".format(
                        side.active.name,
                        side.active.gen_3_consecutive_sleep_talks,
                        side.active.gen_3_consecutive_sleep_talks,
                    )
                )
                side.active.sleep_turns -= side.active.gen_3_consecutive_sleep_talks

        side.active.gen_3_consecutive_sleep_talks = 0

        side.active.moves_used_since_switch_in.clear()

        # reset the boost of the pokemon being replaced
        side.active.boosts.clear()

        # reset the volatile statuses of the pokemon being replaced
        side.active.volatile_statuses.clear()
        side.active.volatile_status_durations.clear()

        # reset toxic count for this side
        side.side_conditions[constants.TOXIC_COUNT] = 0

        # if the side is alive and has regenerator, give it back 1/3 of it's maxhp
        if (
            side.active.hp > 0
            and not side.active.fainted
            and side.active.ability == "regenerator"
        ):
            health_healed = int(side.active.max_hp / 3)
            side.active.hp = min(side.active.hp + health_healed, side.active.max_hp)
            logger.info(
                "{} switched out with regenerator. Healing it to {}/{}".format(
                    side.active.name, side.active.hp, side.active.max_hp
                )
            )

        if side.active.name in ["cramorantgulping", "cramorantgorging"]:
            logger.info(
                "Resetting {} to 'cramorant' on switch out".format(side.active.name)
            )
            side.active.name = "cramorant"

    if side_name == "user" and user_just_switched_into_zoroark(battle, switch_or_drag):
        logger.info(
            "User switched/dragged into Zoroark - replacing the split_msg pokemon"
        )
        logger.info("Starting split_msg: {}".format(split_msg))
        request_json_zoroark = [
            p
            for p in battle.request_json[constants.SIDE][constants.POKEMON]
            if p[constants.DETAILS].startswith("Zoroark")
        ]
        assert len(request_json_zoroark) == 1
        request_json_zoroark = request_json_zoroark[0]
        split_msg[2] = f"{request_json_zoroark[constants.IDENT]}"
        split_msg[3] = f"{request_json_zoroark[constants.DETAILS]}"
        logger.info("New split_msg: {}".format(split_msg))

    # check if the pokemon exists in the reserves
    # if it does not, then the newly-created pokemon is used (for formats without team preview)
    nickname = split_msg[2]
    temp_pkmn = Pokemon.from_switch_string(split_msg[3], nickname=nickname)
    pkmn = side.find_pokemon_in_reserves(temp_pkmn.name)

    if pkmn is None:
        pkmn = Pokemon.from_switch_string(split_msg[3], nickname=nickname)

        # for standard battles gen4 and lower
        # we want to add the new pokemon to the datasets as they are revealed
        # because there is no teampreview
        if (
            battle.battle_type == BattleType.STANDARD_BATTLE
            and battle.generation in constants.NO_TEAM_PREVIEW_GENS
        ):
            SmogonSets.add_new_pokemon(pkmn.name)
            TeamDatasets.add_new_pokemon(pkmn.name)
            logger.info("Adding new pokemon '{}' to the datasets".format(pkmn.name))

        # some pokemon do not reveal their forme during team preview. Arceus, Silvally, Genesect, etc.
        # if this is the case, they would have been given a flag during team preview, and we can pull them out here
        unknown_forme_pkmn = side.find_reserve_pkmn_by_unknown_forme(temp_pkmn.name)
        if unknown_forme_pkmn:
            side.reserve.remove(unknown_forme_pkmn)
    else:
        if pkmn.name != temp_pkmn.name:
            logger.info("Renaming {} -> {}".format(pkmn.name, temp_pkmn.name))
            pkmn.name = temp_pkmn.name
        pkmn.nickname = temp_pkmn.nickname

        # Zoroark edge-case nonsense
        # if this pokemon turns out to be zoroark it may have permanent conditions change that need to be un-done after
        # finding out it is zoroark e.g. the HP value of this pokemon on switch-in is preserved so we can reset it if it
        # turns out to be zoroark
        pkmn.hp_at_switch_in = pkmn.hp
        pkmn.status_at_switch_in = pkmn.status

        side.reserve.remove(pkmn)

    split_hp_msg = split_msg[4].split("/")
    if is_opponent(battle, split_msg):
        new_hp_percentage = float(split_hp_msg[0]) / 100
        if (
            pkmn.hp != new_hp_percentage * pkmn.max_hp
            and "regenerator"
            in [
                normalize_name(a)
                for a in pokedex[pkmn.name][constants.ABILITIES].values()
            ]
            and pkmn.ability is None
        ):
            logger.info(
                "{} switched out with {}% HP but now has {}% HP, setting its ability to regenerator".format(
                    pkmn.name,
                    pkmn.hp / pkmn.max_hp * 100,
                    new_hp_percentage * 100,
                )
            )
            pkmn.ability = "regenerator"
        pkmn.hp = pkmn.max_hp * new_hp_percentage
    else:
        pkmn.hp = float(split_hp_msg[0])
        pkmn.max_hp = float(split_hp_msg[1].split()[0])

    side.last_used_move = LastUsedMove(
        pokemon_name=None, move="switch {}".format(pkmn.name), turn=battle.turn
    )

    # pkmn != active is a special edge-case for Zoroark
    if side.active is not None and pkmn != side.active:
        side.reserve.append(side.active)

    side.active = pkmn

    # zacian-crowned is technically still zacian before switching in for the first time
    # this is handled by set-prediction for the opponent, but for the bot's pkmn we
    # need to re-apply the stats that the P.S. server sends us because prior to the first
    # switch-in the stats would be for zacian, not zacian-crowned
    if side_name == "user" and pkmn.name in ["zaciancrowned", "zamazentacrowned"]:
        battle.user.re_initialize_active_pokemon_from_request_json(battle.request_json)

    for ability in ABILITIES_REVEALED_ON_SWITCH_IN:
        if battle.generation == "gen3" and ability == "pressure":
            # gen3 pressure is not revealed on switch-in
            continue

        if (
            (
                ability == "sandstream"
                and battle.weather
                in [constants.SAND, constants.HEAVY_RAIN, constants.DESOLATE_LAND]
            )
            or (
                ability == "drought"
                and battle.weather
                in [constants.SUN, constants.HEAVY_RAIN, constants.DESOLATE_LAND]
            )
            or (
                ability == "drizzle"
                and battle.weather
                in [constants.RAIN, constants.HEAVY_RAIN, constants.DESOLATE_LAND]
            )
            or (
                ability == "snowwarning"
                and battle.weather
                in [
                    constants.HAIL,
                    constants.SNOW,
                    constants.HEAVY_RAIN,
                    constants.DESOLATE_LAND,
                ]
            )
        ):
            logger.info(
                "Not adding {} to {}'s impossible abilities because the weather would not have triggered".format(
                    ability,
                    pkmn.name,
                )
            )
            continue

        if ability not in pkmn.impossible_abilities and (
            other_side.active is not None
            and other_side.active.ability != "neutralizinggas"
        ):
            logger.info(
                "{} switched in, adding {} to impossible abilities".format(
                    pkmn.name, ability
                )
            )
            pkmn.impossible_abilities.add(ability)

    for item in ITEMS_REVEALED_ON_SWITCH_IN:
        if item not in pkmn.impossible_items:
            logger.info(
                "{} switched in, adding {} to impossible items".format(pkmn.name, item)
            )
            pkmn.impossible_items.add(item)

    if baton_passed_boosts is not None:
        logger.info(
            "Applying baton passed boosts to {}: {}".format(
                side.active.name, dict(baton_passed_boosts)
            )
        )
        side.active.boosts = baton_passed_boosts
    for volatile in switch_keep_volatiles:
        logger.info("Keeping volatile on switch: {}".format(volatile))
        side.active.volatile_statuses.append(volatile)


def sethp(battle, split_msg):
    # |-sethp|p2a: Jellicent|317/403|[from] move: Pain Split|[silent]
    if is_opponent(battle, split_msg):
        pkmn = battle.opponent.active
        new_hp_percentage = float(split_msg[3].split("/")[0]) / 100
        pkmn.hp = int(pkmn.max_hp * new_hp_percentage)
    else:
        pkmn = battle.user.active
        pkmn.hp = int(split_msg[3].split("/")[0])
        pkmn.max_hp = int(split_msg[3].split("/")[1].split()[0])


def heal_or_damage(battle, split_msg):
    if is_opponent(battle, split_msg):
        side = battle.opponent
        other_side = battle.user
        pkmn = battle.opponent.active
        if len(split_msg) == 5 and split_msg[4] == "[from] move: Revival Blessing":
            nickname = Pokemon.extract_nickname_from_pokemonshowdown_string(
                split_msg[2]
            )
            pkmn = side.find_reserve_pokemon_by_nickname(nickname)

        # opponent hp is given as a percentage
        if constants.FNT in split_msg[3]:
            pkmn.hp = 0
        else:
            new_hp_percentage = float(split_msg[3].split("/")[0]) / 100
            pkmn.hp = pkmn.max_hp * new_hp_percentage

    else:
        side = battle.user
        other_side = battle.opponent
        pkmn = battle.user.active
        if len(split_msg) == 5 and split_msg[4] == "[from] move: Revival Blessing":
            nickname = Pokemon.extract_nickname_from_pokemonshowdown_string(
                split_msg[2]
            )
            pkmn = side.find_reserve_pokemon_by_nickname(nickname)
        if constants.FNT in split_msg[3]:
            pkmn.hp = 0
        else:
            pkmn.hp = float(split_msg[3].split("/")[0])
            pkmn.max_hp = float(split_msg[3].split("/")[1].split()[0])

    # increase the amount of turns toxic has been active
    if (
        len(split_msg) == 5
        and constants.TOXIC in split_msg[3]
        and "[from] psn" in split_msg[4]
    ):
        side.side_conditions[constants.TOXIC_COUNT] += 1

    if (
        len(split_msg) == 6
        and split_msg[4].startswith("[from] item:")
        and other_side.name in split_msg[5]
    ):
        item = normalize_name(split_msg[4].split("item:")[-1])
        logger.info("Setting {}'s item to: {}".format(other_side.active.name, item))
        other_side.active.item = item

    if (
        len(split_msg) >= 5
        and split_msg[-1].startswith("[from]")
        and split_msg[-1].endswith("Healing Wish")
    ):
        logger.info(
            "{} was healed from healing wish, setting side condition to 0".format(
                side.active.name
            )
        )
        side.side_conditions[constants.HEALING_WISH] = 0

    # set the ability for the other side (the side not taking damage, '-damage' only)
    if (
        len(split_msg) == 6
        and split_msg[4].startswith("[from] ability:")
        and other_side.name in split_msg[5]
        and split_msg[1] == "-damage"
    ):
        ability = normalize_name(split_msg[4].split("ability:")[-1])
        logger.info(
            "Setting {}'s ability to: {}".format(other_side.active.name, ability)
        )
        other_side.active.ability = ability

    # set the ability of the side (the side being healed, '-heal' only)
    if (
        len(split_msg) == 6
        and constants.ABILITY in split_msg[4]
        and other_side.name in split_msg[5]
        and split_msg[1] == "-heal"
    ):
        ability = normalize_name(split_msg[4].split(constants.ABILITY)[-1].strip(": "))
        logger.info("Setting {}'s ability to: {}".format(pkmn.name, ability))
        pkmn.ability = ability

    # give that pokemon an item if this string specifies one
    if len(split_msg) == 5 and constants.ITEM in split_msg[4] and pkmn.item is not None:
        item = normalize_name(split_msg[4].split(constants.ITEM)[-1].strip(": "))
        logger.info("Setting {}'s item to: {}".format(pkmn.name, item))
        pkmn.item = item


def faint(battle, split_msg):
    if is_opponent(battle, split_msg):
        side = battle.opponent
    else:
        side = battle.user

    side.active.hp = 0


def fail(battle, split_msg):
    # |-fail|p2a: Dragapult|unboost|[from] ability: Clear Body|[of] p2a: Dragapult
    if (
        len(split_msg) > 5
        and split_msg[4].startswith("[from] ability: ")
        and split_msg[5].startswith("[of]")
    ):
        ability_side = (
            battle.user
            if split_msg[5].startswith(f"[of] {battle.user.name}")
            else battle.opponent
        )
        ability = normalize_name(split_msg[4].split("ability: ")[-1])
        logger.info(
            "Setting {}'s ability to: {}".format(ability_side.active.name, ability)
        )
        ability_side.active.ability = ability


def move(battle, split_msg):
    if is_opponent(battle, split_msg):
        side = battle.opponent
        pkmn = battle.opponent.active
        opposing_pkmn = battle.user.active
    else:
        side = battle.user
        pkmn = battle.user.active
        opposing_pkmn = battle.opponent.active

    move_name = normalize_name(split_msg[3].strip().lower())

    zoroark_from_reserves = side.find_pokemon_in_reserves(
        "zoroark"
    ) or side.find_pokemon_in_reserves("zoroarkhisui")

    # in battle factory we can deduce that there is a zoroark in front of us
    # if we see a move that is not in the known moveset and a zoroark is in the reserves
    if (
        is_opponent(battle, split_msg)
        and zoroark_from_reserves is not None
        and "transform" not in pkmn.volatile_statuses
        and battle.battle_type
        in [BattleType.BATTLE_FACTORY, BattleType.STANDARD_BATTLE]
        and move_name not in TeamDatasets.get_all_possible_moves(pkmn)
        and move_name in TeamDatasets.get_all_possible_moves(zoroark_from_reserves)
        and "from" not in split_msg[-1]
    ):
        logger.info(
            "{} using {} means it is {}".format(
                pkmn.name, move_name, zoroark_from_reserves.name
            )
        )
        _switch_active_with_zoroark_from_reserves(side, zoroark_from_reserves)

        # the rest of this function uses `pkmn`, so we need to set it to the correct pkmn
        pkmn = zoroark_from_reserves

    # in randombattles we can deduce that there is a zoroark in front of us
    # if we see a move that is not in the known moveset, even if there is no
    # zoroark is in the reserves
    if (
        is_opponent(battle, split_msg)
        and battle.battle_type == BattleType.RANDOM_BATTLE
        and "transform" not in pkmn.volatile_statuses
        and move_name not in RandomBattleTeamDatasets.get_all_possible_moves(pkmn)
        and "from" not in split_msg[-1]
    ):
        actual_zoroark = None
        zoroark_hisui = Pokemon("zoroarkhisui", 100)
        zoroark_regular = Pokemon("zoroark", 100)
        if (
            zoroark_from_reserves is not None
            and move_name
            in RandomBattleTeamDatasets.get_all_possible_moves(zoroark_from_reserves)
        ):
            actual_zoroark = zoroark_from_reserves

        elif (
            battle.generation not in constants.NO_TEAM_PREVIEW_GENS
            and zoroark_from_reserves is None
            and move_name
            in RandomBattleTeamDatasets.get_all_possible_moves(zoroark_hisui)
        ):
            actual_zoroark = zoroark_hisui
            actual_zoroark.level = RandomBattleTeamDatasets.predict_set(
                actual_zoroark
            ).pkmn_set.level
            side.reserve.append(actual_zoroark)

        elif (
            battle.generation not in constants.NO_TEAM_PREVIEW_GENS
            and zoroark_from_reserves is None
            and move_name
            in RandomBattleTeamDatasets.get_all_possible_moves(zoroark_regular)
        ):
            actual_zoroark = zoroark_regular
            actual_zoroark.level = RandomBattleTeamDatasets.predict_set(
                actual_zoroark
            ).pkmn_set.level
            side.reserve.append(actual_zoroark)

        if actual_zoroark is not None:
            logger.info(
                "{} using {} means it is {}".format(
                    pkmn.name, move_name, actual_zoroark.name
                )
            )
            _switch_active_with_zoroark_from_reserves(side, actual_zoroark)

            # the rest of this function uses `pkmn`, so we need to set it to the correct pkmn
            pkmn = actual_zoroark

    if (
        any(msg == "[from]Sleep Talk" for msg in split_msg)
        and battle.generation == "gen3"
    ):
        pkmn.gen_3_consecutive_sleep_talks += 1
        logger.info(
            "{} gen3 consecutive sleep talks: {}".format(
                pkmn.name, pkmn.gen_3_consecutive_sleep_talks
            )
        )
    elif move_name != "sleeptalk":
        pkmn.gen_3_consecutive_sleep_talks = 0

    # gen1 stat modification glitches.
    # swordsdance and agility nullify the effects of burn and paralysis respectively
    # This is implemented by setting a custom volatile
    if battle.generation == "gen1":
        if (
            move_name == "swordsdance" or move_name == "meditate"
        ) and pkmn.status == constants.BURN:
            logger.info(
                "{} used swordsdance with burn, nullifying the effects of burn".format(
                    pkmn.name
                )
            )
            pkmn.volatile_statuses.append("gen1burnnullify")
        elif move_name == "agility" and pkmn.status == constants.PARALYZED:
            logger.info(
                "{} used agility while paralyzed, nullifying the effects of paralysis".format(
                    pkmn.name
                )
            )
            pkmn.volatile_statuses.append("gen1paralysisnullify")

    if split_msg[-1] == "[from]Sleep Talk" or split_msg[-1] == "[from]move: Sleep Talk":
        move_object = pkmn.get_move(move_name)
        if move_object is None:
            pkmn.add_move(move_name)
            logger.info(
                "Added unrevealed {} to {}'s moves because it was called by sleeptalk".format(
                    move_name, pkmn.name
                )
            )
        return

    elif any(
        "[from]" in msg and msg != "[from]lockedmove" and msg != "[from] lockedmove"
        for msg in split_msg
    ):
        if split_msg[-1].startswith("[from] ability:"):
            ability = normalize_name(split_msg[-1].split("ability: ")[-1])
            logger.info("Setting {}'s ability to: {}".format(pkmn.name, ability))
            pkmn.ability = ability
        return

    if "destinybond" in pkmn.volatile_statuses:
        logger.info("Removing destinybond from {}".format(pkmn.name))
        remove_volatile(pkmn, "destinybond")

    if "encore" in pkmn.volatile_statuses:
        pkmn.volatile_status_durations["encore"] += 1
        logger.info(
            "Incrementing encore duration for {} to {}".format(
                pkmn.name, pkmn.volatile_status_durations["encore"]
            )
        )

    if (
        "taunt" in pkmn.volatile_statuses
        and battle.generation not in constants.TAUNT_DURATION_INCREMENT_END_OF_TURN
    ):
        pkmn.volatile_status_durations[constants.TAUNT] += 1
        logger.info(
            "Incrementing taunt duration for {} to {}".format(
                pkmn.name, pkmn.volatile_status_durations[constants.TAUNT]
            )
        )

    # remove volatile status if they have it
    # this is for preparation moves like Phantom Force
    if move_name in pkmn.volatile_statuses:
        logger.info("Removing volatile status {} from {}".format(move_name, pkmn.name))
        remove_volatile(pkmn, move_name)

    if move_name == "struggle":
        logger.info("Not adding struggle to {}'s moves".format(pkmn.name))
        return

    if move_name == "healingwish":
        logger.info(
            "{} used healingwish, setting side_condition to 1".format(pkmn.name)
        )
        side.side_conditions[constants.HEALING_WISH] = 1

    pkmn.moves_used_since_switch_in.add(move_name)

    # add the move to it's moves if it hasn't been seen
    # decrement the PP by one
    # if the move is unknown, do nothing
    pp_to_decrement = 2 if opposing_pkmn.ability == "pressure" else 1
    move_object = pkmn.get_move(move_name)
    if move_object is None:
        new_move = pkmn.add_move(move_name)
        if new_move is not None:
            new_move.current_pp -= pp_to_decrement
    else:
        move_object.current_pp -= pp_to_decrement
        logger.info(
            "{} already has the move {}. Decrementing the PP by {}".format(
                pkmn.name, move_name, pp_to_decrement
            )
        )

    # if this pokemon used two different moves without switching,
    # set a flag to signify that it cannot have a choice item
    if (
        is_opponent(battle, split_msg)
        and side.last_used_move.pokemon_name == side.active.name
        and side.last_used_move.move != move_name
    ):
        logger.info(
            "{} used two different moves - it cannot have a choice item".format(
                pkmn.name
            )
        )
        pkmn.can_have_choice_item = False
        if pkmn.item in constants.CHOICE_ITEMS and pkmn.item_inferred:
            logger.warning(
                "{} has a choice item, but used two different moves - setting it's item to UNKNOWN".format(
                    pkmn.name
                )
            )
            pkmn.item = constants.UNKNOWN_ITEM

    if unlikely_to_have_choice_item(move_name):
        logger.info(
            "{} using {} makes it unlikely to have a choice item. Setting can_have_choice_item to False".format(
                pkmn.name, move_name
            )
        )
        pkmn.can_have_choice_item = False

    try:
        mv = all_move_json[move_name]
        move_type = mv[constants.TYPE]
        if mv[constants.CATEGORY] != constants.STATUS:
            logger.info(
                "{} used a {} move, removing {}gem from possible items".format(
                    pkmn.name, move_type, move_type
                )
            )
            pkmn.impossible_items.add("{}gem".format(move_type))
    except KeyError:
        pass

    try:
        if (
            all_move_json[move_name][constants.SELF][constants.VOLATILE_STATUS]
            == constants.LOCKED_MOVE
        ):
            logger.info("Adding lockedmove to {}".format(pkmn.name))
            pkmn.volatile_statuses.append(constants.LOCKED_MOVE)
    except KeyError:
        pass

    try:
        if all_move_json[move_name][constants.CATEGORY] == constants.STATUS:
            logger.info(
                "{} used a status-move. Adding `assaultvest` to impossible items".format(
                    pkmn.name
                )
            )
            pkmn.impossible_items.add(constants.ASSAULT_VEST)
    except KeyError:
        pass

    try:
        category = all_move_json[move_name][constants.CATEGORY]
        logger.info("Setting {}'s last used move: {}".format(pkmn.name, move_name))
        if not any(
            "[from]move: Sleep Talk" in msg or "[from]Sleep Talk" in msg
            for msg in split_msg
        ):
            side.last_used_move = LastUsedMove(
                pokemon_name=pkmn.name, move=move_name, turn=battle.turn
            )
    except KeyError:
        category = None
        if not any(
            "[from]move: Sleep Talk" in msg or "[from]Sleep Talk" in msg
            for msg in split_msg
        ):
            side.last_used_move = LastUsedMove(
                pokemon_name=pkmn.name, move=constants.DO_NOTHING_MOVE, turn=battle.turn
            )

    # if this pokemon used a damaging move, eliminate the possibility of guessing a lifeorb
    # the lifeorb will reveal itself if it has it
    if category in constants.DAMAGING_CATEGORIES and not any(
        [
            normalize_name(a) in ["sheerforce", "magicguard"]
            for a in pokedex[pkmn.name][constants.ABILITIES].values()
        ]
    ):
        logger.info(
            "{} used a damaging move - not guessing lifeorb anymore".format(pkmn.name)
        )
        pkmn.impossible_items.add(constants.LIFE_ORB)

    # there is nothing special in the protocol for "wish" - it must be extracted here
    if move_name == constants.WISH and "still" not in split_msg[4]:
        logger.info(
            "{} used wish - expecting {} health of recovery next turn".format(
                side.active.name, side.active.max_hp / 2
            )
        )
        side.wish = (2, side.active.max_hp / 2)

    if move_name == "batonpass":
        side.baton_passing = True

    # |move|p1a: Slaking|Earthquake|p2a: Heatran
    if pkmn.ability == "truant" or pkmn.name == "slaking":
        if "truant" not in pkmn.volatile_statuses:
            logger.info("Adding 'truant' to {}'s volatiles".format(pkmn.name))
            pkmn.volatile_statuses.append("truant")


def setboost(battle, split_msg):
    if is_opponent(battle, split_msg):
        pkmn = battle.opponent.active
    else:
        pkmn = battle.user.active

    stat = constants.STAT_ABBREVIATION_LOOKUPS[split_msg[3].strip()]
    amount = int(split_msg[4].strip())

    pkmn.boosts[stat] = amount


def boost(battle, split_msg):
    if is_opponent(battle, split_msg):
        pkmn = battle.opponent.active
    else:
        pkmn = battle.user.active

    stat = constants.STAT_ABBREVIATION_LOOKUPS[split_msg[3].strip()]
    amount = int(split_msg[4].strip())

    pkmn.boosts[stat] = min(pkmn.boosts[stat] + amount, constants.MAX_BOOSTS)
    logger.info(
        "{}'s {} was boosted by {} to {}".format(
            pkmn.name, stat, amount, pkmn.boosts[stat]
        )
    )


def unboost(battle, split_msg):
    if is_opponent(battle, split_msg):
        pkmn = battle.opponent.active
    else:
        pkmn = battle.user.active

    stat = constants.STAT_ABBREVIATION_LOOKUPS[split_msg[3].strip()]
    amount = int(split_msg[4].strip())

    pkmn.boosts[stat] = max(pkmn.boosts[stat] - amount, -1 * constants.MAX_BOOSTS)
    logger.info(
        "{}'s {} was unboosted by {} to {}".format(
            pkmn.name, stat, amount, pkmn.boosts[stat]
        )
    )


def status(battle, split_msg):
    if is_opponent(battle, split_msg):
        other_side = battle.user
        pkmn = battle.opponent.active
    else:
        pkmn = battle.user.active
        other_side = battle.opponent

    if len(split_msg) > 4 and "item: " in split_msg[4]:
        pkmn.item = normalize_name(split_msg[4].split("item:")[-1])

    if len(split_msg) == 5 and split_msg[3] == "slp":
        if split_msg[4] == "[from] move: Rest":
            logger.info("Setting rest_turns to 3 for {}".format(pkmn.name))
            pkmn.rest_turns = 3
        else:
            logger.info("Setting sleep_turns to 0 for {}".format(pkmn.name))
            pkmn.sleep_turns = 0

    status_name = split_msg[3].strip()
    logger.info("{} got status: {}".format(pkmn.name, status_name))
    pkmn.status = status_name

    if status_name is not None:
        logger.info(
            "No longer guessing lumberry because {} got status {}".format(
                pkmn.name, status_name
            )
        )
        pkmn.impossible_items.add("lumberry")

    # ["", "-status", "p1a: Caterpie", "brn", "[from] ability: Flame Body", "[of] p2a: Caterpie"]
    if (
        len(split_msg) > 5
        and split_msg[4].startswith("[from] ability: ")
        and split_msg[5].startswith("[of]")
        and split_msg[5].startswith(f"[of] {other_side.name}")
    ):
        ability = normalize_name(split_msg[4].split("ability: ")[-1])
        logger.info("Setting {}'s ability to: {}".format(pkmn.name, ability))
        other_side.active.ability = ability


def activate(battle, split_msg):
    if is_opponent(battle, split_msg):
        pkmn = battle.opponent.active
        other_pkmn = battle.user.active
    else:
        pkmn = battle.user.active
        other_pkmn = battle.opponent.active

    if (
        normalize_name(split_msg[3]) == constants.SUBSTITUTE
        and split_msg[4] == "[damage]"
    ):
        logger.info(
            "{}'s substitute took damage, setting substitute_hit to True".format(
                pkmn.name
            )
        )
        pkmn.substitute_hit = True

    if split_msg[3].lower() == "move: poltergeist":
        item = normalize_name(split_msg[4])
        logger.info("{} has the item {}".format(pkmn.name, item))
        pkmn.item = item

    if split_msg[3].lower().startswith("ability: "):
        ability = normalize_name(split_msg[3].split(":")[-1].strip())
        logger.info("Setting {}'s ability to {}".format(pkmn.name, ability))
        pkmn.ability = ability

        if ability in ["mummy", "lingeringaroma"]:
            original_ability = normalize_name(split_msg[4])
            other_pkmn.ability = ability
            other_pkmn.original_ability = original_ability
            logger.info(
                "{}'s ability was changed from {} to {}".format(
                    other_pkmn.name, original_ability, ability
                )
            )

    elif split_msg[3].lower().startswith("item: ") and not any(
        i == "[consumed]" for i in split_msg
    ):
        item = normalize_name(split_msg[3].split(":")[-1].strip())
        logger.info("Setting {}'s item to {}".format(pkmn.name, item))
        pkmn.item = item

    if split_msg[3].lower().startswith("move: "):
        move_name = normalize_name(split_msg[3].split(":")[-1].strip())
        if (
            move_name in all_move_json
            and all_move_json[move_name].get("volatileStatus") == "partiallytrapped"
        ):
            logger.info("{} was partially trapped by {}".format(pkmn.name, move_name))
            pkmn.volatile_statuses.append("partiallytrapped")


def anim(battle, split_msg):
    if is_opponent(battle, split_msg):
        pkmn = battle.opponent.active
    else:
        pkmn = battle.user.active

    anim_name = normalize_name(split_msg[3].strip())
    if anim_name in pkmn.volatile_statuses:
        logger.info(
            "Removing volatile status {} from {} because of -anim".format(
                anim_name, pkmn.name
            )
        )
        remove_volatile(pkmn, anim_name)


def prepare(battle, split_msg):
    if is_opponent(battle, split_msg):
        pkmn = battle.opponent.active
    else:
        pkmn = battle.user.active

    being_prepared = normalize_name(split_msg[3])
    if being_prepared in pkmn.volatile_statuses:
        logger.warning(
            "{} already has the volatile status {}".format(pkmn.name, being_prepared)
        )
    else:
        logger.info(
            "Adding the volatile status {} to {}".format(being_prepared, pkmn.name)
        )
        pkmn.volatile_statuses.append(being_prepared)


def terastallize(battle, split_msg):
    if is_opponent(battle, split_msg):
        pkmn = battle.opponent.active
    else:
        pkmn = battle.user.active

    pkmn.terastallized = True
    pkmn.tera_type = normalize_name(split_msg[3])
    logger.info(
        "{} terastallized. Tera type: {}, Original types: {}".format(
            pkmn.name, pkmn.tera_type, pkmn.types
        )
    )


def start_volatile_status(battle, split_msg):
    if is_opponent(battle, split_msg):
        pkmn = battle.opponent.active
        side = battle.opponent
    else:
        pkmn = battle.user.active
        side = battle.user

    volatile_status = normalize_name(split_msg[3].split(":")[-1])

    # for some reason futuresight is sent with the `-start` message
    # `-start` is typically reserved for volatile statuses
    if volatile_status == constants.FUTURE_SIGHT:
        side.future_sight = (3, pkmn.name)
        return

    if volatile_status.startswith("perish"):
        logger.info(
            "{} got {}. Removing other `perish` volatiles".format(
                pkmn.name, volatile_status
            )
        )
        logger.info("Starting volatiles: {}".format(pkmn.volatile_statuses))
        pkmn.volatile_statuses = [
            vs for vs in pkmn.volatile_statuses if not vs.startswith("perish")
        ]
        pkmn.volatile_statuses.append(volatile_status)
        logger.info("Ending volatiles: {}".format(pkmn.volatile_statuses))
        return

    if volatile_status not in pkmn.volatile_statuses:
        logger.info(
            "Starting the volatile status {} on {}".format(volatile_status, pkmn.name)
        )
        pkmn.volatile_statuses.append(volatile_status)

    if volatile_status == constants.SUBSTITUTE:
        if len(split_msg) >= 5 and split_msg[4] == "[from] move: Shed Tail":
            logger.info(
                "{} started a substitute from shed tail - setting shed_tailing to True".format(
                    pkmn.name
                )
            )
            side.shed_tailing = True
        logger.info(
            "{} started a substitute - setting substitute_hit to False".format(
                pkmn.name
            )
        )
        pkmn.substitute_hit = False

    if volatile_status == constants.SLOW_START:
        logger.info("{} started slow start - setting slow_start to 6".format(pkmn.name))
        pkmn.volatile_status_durations[constants.SLOW_START] = 6

    if volatile_status == constants.CONFUSION:
        logger.info("{} got confused, no longer guessing lumberry".format(pkmn.name))
        pkmn.impossible_items.add("lumberry")
        if split_msg[-1] == "[fatigue]":
            logger.info(
                "{} got confused from fatigue, removing lockedmove from volatile statuses".format(
                    pkmn.name
                )
            )
            remove_volatile(pkmn, constants.LOCKED_MOVE)
            side.active.volatile_status_durations[constants.LOCKED_MOVE] = 0

    if volatile_status == constants.DYNAMAX:
        pkmn.hp *= 2
        pkmn.max_hp *= 2
        logger.info(
            "{} started dynamax - doubling their HP to {}/{}".format(
                pkmn.name, pkmn.hp, pkmn.max_hp
            )
        )

    if constants.ABILITY in split_msg[3]:
        pkmn.ability = volatile_status

    if len(split_msg) == 6 and constants.ABILITY in normalize_name(split_msg[5]):
        pkmn.ability = normalize_name(split_msg[5].split("ability:")[-1])

    if volatile_status == constants.TYPECHANGE:
        if split_msg[4] == "[from] move: Reflect Type":
            pkmn_name = normalize_name(split_msg[5].split(":")[-1])
            new_types = deepcopy(pokedex[pkmn_name][constants.TYPES])
        else:
            new_types = [normalize_name(t) for t in split_msg[4].split("/")]

        logger.info("Setting {}'s types to {}".format(pkmn.name, new_types))
        pkmn.types = new_types


def end_volatile_status(battle, split_msg):
    if is_opponent(battle, split_msg):
        pkmn = battle.opponent.active
    else:
        pkmn = battle.user.active

    volatile_status = normalize_name(split_msg[3].split(":")[-1])
    if volatile_status == constants.SUBSTITUTE:
        logger.info("Substitute ended for {}".format(pkmn.name))
        pkmn.substitute_hit = False

    if volatile_status == "protosynthesis" or volatile_status == "quarkdrive":
        for vs in pkmn.volatile_statuses:
            if vs.startswith(volatile_status):
                logger.info("Removing {} from {}".format(vs, pkmn.name))
                pkmn.volatile_statuses.remove(vs)
    elif len(split_msg) >= 5 and "partiallytrapped" in split_msg[4]:
        remove_volatile(pkmn, "partiallytrapped")
    elif volatile_status not in pkmn.volatile_statuses:
        logger.warning(
            "{} does not have the volatile status '{}'. Volatiles: {}".format(
                pkmn, volatile_status, pkmn.volatile_statuses
            )
        )
    else:
        logger.info(
            "Removing the volatile status {} from {}".format(volatile_status, pkmn.name)
        )
        remove_volatile(pkmn, volatile_status)
        if volatile_status in pkmn.volatile_status_durations:
            pkmn.volatile_status_durations[volatile_status] = 0
            logger.info(
                "Setting {}'s {} duration to 0".format(pkmn.name, volatile_status)
            )
        if volatile_status == constants.DYNAMAX:
            pkmn.hp /= 2
            pkmn.max_hp /= 2
            logger.info(
                "{} ended dynamax - halving their HP to {}/{}".format(
                    pkmn.name, pkmn.hp, pkmn.max_hp
                )
            )


def curestatus(battle, split_msg):
    if is_opponent(battle, split_msg):
        side = battle.opponent
    else:
        side = battle.user

    pkmn_name = split_msg[2].split(":")[-1].strip()

    if normalize_name(pkmn_name) == side.active.name:
        pkmn = side.active
    else:
        try:
            pkmn = next(
                filter(lambda x: x.name == normalize_name(pkmn_name), side.reserve)
            )
        except StopIteration:
            logger.warning(
                "The pokemon {} does not exist in the party, defaulting to the active pokemon".format(
                    normalize_name(pkmn_name)
                )
            )
            pkmn = side.active

    # even if rest wasn't the cause of sleep, this should be set to 0
    if pkmn.status == constants.SLEEP:
        logger.info(
            "{} is being cured of sleep, setting rest_turns & sleep_turns to 0".format(
                pkmn.name
            )
        )
        pkmn.rest_turns = 0
        pkmn.sleep_turns = 0
    elif pkmn.status == constants.TOXIC:
        side.side_conditions[constants.TOXIC_COUNT] = 0

    pkmn.status = None


def cureteam(battle, split_msg):
    """Cure every pokemon on the opponent's team of it's status"""
    if is_opponent(battle, split_msg):
        side = battle.opponent
    else:
        side = battle.user

    side.active.status = None
    for pkmn in filter(lambda p: isinstance(p, Pokemon), side.reserve):
        pkmn.status = None
        pkmn.rest_turns = 0
        pkmn.sleep_turns = 0


def weather(battle, split_msg):
    # The weather message on its own `|-weather|RainDance` does not contain information about
    #  which side caused it unless it was from an ability
    #  `|-weather|RainDance|[from] ability: Drizzle|[of] p2a: Politoed`
    #
    # If that information is present, we can infer certain things about the Side
    side = None
    side_name = None
    if len(split_msg) == 5:
        if battle.opponent.name in split_msg[-1]:
            side = battle.opponent
            side_name = "opponent"
        else:
            side = battle.user
            side_name = "user"

    weather_name = normalize_name(split_msg[2].split(":")[-1].strip())
    logger.info("Weather {} is active".format(weather_name))
    battle.weather = weather_name

    if weather_name == "none":
        logger.info("Resetting weather source to None")
        battle.weather_source = None
    elif side is not None and side_name is not None:
        battle.weather_source = f"{side_name}:{side.active.name}"

    if split_msg[-1] == "[upkeep]" and battle.weather_turns_remaining > 0:
        battle.weather_turns_remaining -= 1
    elif split_msg[-1] == "[upkeep]":
        logger.debug("Weather {} permanently active".format(weather_name))
    elif (
        len(split_msg) > 3
        and battle.generation in ["gen3", "gen4", "gen5"]
        and split_msg[3].startswith("[from] ability:")
    ):
        battle.weather_turns_remaining = -1
    elif (
        side is not None
        and weather_name == constants.SUN
        and side.active.item == "heatrock"
    ):
        logger.info("{} has heatrock, assuming 8 turns of sun".format(side.active.name))
        battle.weather_turns_remaining = 8
    elif (
        side is not None
        and weather_name == constants.RAIN
        and side.active.item == "damprock"
    ):
        logger.info(
            "{} has damprock, assuming 8 turns of rain".format(side.active.name)
        )
        battle.weather_turns_remaining = 8
    elif (
        side is not None
        and weather_name == constants.SAND
        and side.active.item == "smoothrock"
    ):
        logger.info(
            "{} has smoothrock, assuming 8 turns of sand".format(side.active.name)
        )
        battle.weather_turns_remaining = 8
    elif (
        side is not None
        and weather_name in constants.HAIL_OR_SNOW
        and side.active.item == "icyrock"
    ):
        logger.info("{} has icyrock, assuming 8 turns of hail".format(side.active.name))
        battle.weather_turns_remaining = 8
    else:
        battle.weather_turns_remaining = 5

    logger.info("Weather turns remaining: {}".format(battle.weather_turns_remaining))
    if battle.weather_turns_remaining == 0:
        logger.info(
            "Weather {} did not end when expected, giving 3 more turns".format(
                weather_name
            )
        )
        battle.weather_turns_remaining = 3
        if (
            battle.weather_source is not None
            and battle.weather_source != ""
            and battle.weather_source.startswith("opponent")
        ):
            side = battle.opponent
            pkmn_name = battle.weather_source.split(":")[-1]
            pkmn = (
                side.active
                if side.active.name == pkmn_name
                else side.find_pokemon_in_reserves(pkmn_name)
            )
            if pkmn is not None and pkmn.item == constants.UNKNOWN_ITEM:
                if weather_name == constants.SUN:
                    item = "heatrock"
                elif weather_name == constants.RAIN:
                    item = "damprock"
                elif weather_name == constants.SAND:
                    item = "smoothrock"
                elif weather_name in constants.HAIL_OR_SNOW:
                    item = "icyrock"
                else:
                    item = constants.UNKNOWN_ITEM

                logger.info(
                    "Weather not ending means that opponent's {} has a {}".format(
                        pkmn.name, item
                    )
                )
                pkmn.item = item

    if side is not None and len(split_msg) >= 5 and side.name in split_msg[4]:
        ability = normalize_name(split_msg[3].split(":")[-1].strip())
        logger.info("Setting {} ability to {}".format(side.active.name, ability))
        side.active.ability = ability


def fieldstart(battle, split_msg):
    """Set the battle's field condition"""
    field_name = normalize_name(split_msg[2].split(":")[-1].strip())

    # some field effects show up as a `-fieldstart` item but are separate from the other fields
    if field_name == constants.TRICK_ROOM:
        logger.info("Setting trickroom")
        battle.trick_room = True
        battle.trick_room_turns_remaining = 5
    elif field_name == constants.GRAVITY:
        logger.info("Setting gravity")
        battle.gravity = True
    else:
        logger.info("Setting the field to {}".format(field_name))
        battle.field = field_name
        battle.field_turns_remaining = 5


def fieldend(battle, split_msg):
    """Remove the battle's field condition"""
    field_name = normalize_name(split_msg[2].split(":")[-1].strip())

    # some field effects show up as a `-fieldend` item but are separate from the other fields
    if field_name == constants.TRICK_ROOM:
        logger.info("Removing trick room")
        battle.trick_room = False
        battle.trick_room_turns_remaining = 0
    elif field_name == constants.GRAVITY:
        logger.info("Removing gravity")
        battle.gravity = False
    else:
        logger.info("Setting the field to None")
        battle.field = None
        battle.field_turns_remaining = 0


def sidestart(battle, split_msg):
    # Inconsistencies in the protocol mean parse after the `:` to get the side condition
    # |-sidestart|p2: Name|Reflect
    # |-sidestart|p2: Name|move: Light Screen
    # |-sidestart|p2: Name|Spikes
    # |-sidestart|p1: Name|move: Stealth Rock
    #
    # Some side conditions have an explicit duration such as lightscreen, reflect, etc.
    # Others are incremented by 1

    condition = split_msg[3].split(":")[-1].strip()
    condition = normalize_name(condition)
    if is_opponent(battle, split_msg):
        side = battle.opponent
    else:
        side = battle.user

    if condition in SIDE_CONDITION_DEFAULT_DURATION:
        increment_amount = SIDE_CONDITION_DEFAULT_DURATION[condition]
        if (
            condition in ["reflect", "lightscreen", "auroraveil"]
            and side.active.item == "lightclay"
        ):
            increment_amount += 3

        side.side_conditions[condition] = increment_amount
        logger.info(
            "Setting side condition {} to {} for {}".format(
                condition, SIDE_CONDITION_DEFAULT_DURATION[condition], side.active.name
            )
        )
    else:
        side.side_conditions[condition] += 1
        logger.info(
            "Incremented side condition {} to {} for {}".format(
                condition, side.side_conditions[condition], side.active.name
            )
        )


def sideend(battle, split_msg):
    """Remove a side effect such as stealth rock or sticky web"""
    condition = split_msg[3].split(":")[-1].strip()
    condition = normalize_name(condition)

    if is_opponent(battle, split_msg):
        logger.info("Side condition {} ending for opponent".format(condition))
        battle.opponent.side_conditions[condition] = 0
    else:
        logger.info("Side condition {} ending for user".format(condition))
        battle.user.side_conditions[condition] = 0


def swapsideconditions(battle, _):
    user_sc = battle.user.side_conditions
    opponent_sc = battle.opponent.side_conditions
    for side_condition in constants.COURT_CHANGE_SWAPS:
        user_sc[side_condition], opponent_sc[side_condition] = (
            opponent_sc[side_condition],
            user_sc[side_condition],
        )


def set_item(battle, split_msg):
    """Set the opponent's item"""
    if is_opponent(battle, split_msg):
        side = battle.opponent
        other_side = battle.user
    else:
        side = battle.user
        other_side = battle.opponent

    item = normalize_name(split_msg[3].strip())

    if (
        len(split_msg) >= 5
        and side.active.removed_item is None
        and item != side.active.item
        and side.active.item not in [constants.UNKNOWN_ITEM]
    ):
        logger.info("{}'s removed item is {}".format(side.active.name, item))
        side.active.removed_item = side.active.item

    # when the bot gets tricked we set the opponent's removed item
    if (
        len(split_msg) >= 5
        and "[from] move: Trick" in split_msg[4]
        and not is_opponent(battle, split_msg)
        and other_side.active.removed_item is None
    ):
        logger.info("Setting opponent's removed_item to {}".format(item))
        other_side.active.removed_item = item

    # for gen5 frisk only
    # the frisk message will (incorrectly imo) show the item as belonging to the
    # pokemon with frisk
    #
    # e.g. Furret is frisking the opponent:
    # |-item|p2a: Furret|Life Orb|[from] ability: Frisk|[of] p2a: Furret
    if (
        len(split_msg) == 6
        and split_msg[4] == "[from] ability: Frisk"
        and split_msg[2] in split_msg[5]
    ):
        logger.info(
            "{} frisked the opponent's item as {}".format(side.active.name, item)
        )
        logger.info("Setting {}'s item to {}".format(other_side.active.name, item))
        other_side.active.item = item
    else:
        logger.info("Setting {}'s item to {}".format(side.active.name, item))
        side.active.item = item


def remove_item(battle, split_msg):
    """Remove the opponent's item"""
    if is_opponent(battle, split_msg):
        side = battle.opponent
    else:
        side = battle.user

    item = normalize_name(split_msg[3].strip())

    logger.info("Removing {}'s item: {}".format(side.active.name, item))
    side.active.item = None

    if side.active.removed_item is None:
        logger.info("Setting {}'s removed item to {}".format(side.active.name, item))
        side.active.removed_item = item

    if "unburden" not in side.active.volatile_statuses and "unburden" in [
        normalize_name(a)
        for a in pokedex[side.active.name][constants.ABILITIES].values()
    ]:
        logger.info("Adding unburden volatile to {}".format(side.active.name))
        side.active.volatile_statuses.append("unburden")

    if len(split_msg) >= 5 and "knockoff" in normalize_name(split_msg[4]):
        logger.info("Knockoff removed {}'s item".format(side.active.name))
        side.active.knocked_off = True


def immune(battle, split_msg):
    if is_opponent(battle, split_msg):
        side = battle.opponent
        pkmn = side.active
    else:
        side = battle.user
        pkmn = side.active

    for msg in split_msg:
        if constants.ABILITY in normalize_name(msg):
            ability = normalize_name(msg.split(":")[-1])
            logger.info("Setting {}'s ability to {}".format(side.active.name, ability))
            side.active.ability = ability

    zoroark_from_reserves = side.find_pokemon_in_reserves(
        "zoroark"
    ) or side.find_pokemon_in_reserves("zoroarkhisui")

    expected_damage_rolls, _ = poke_engine_get_damage_rolls(
        deepcopy(battle), battle.user.last_used_move.move, "none", True
    )

    # Zoroark checks
    if (
        is_opponent(battle, split_msg)
        and not side.active.name.startswith("zoroark")
        and battle.user.last_used_move.move in all_move_json
        and all_move_json[battle.user.last_used_move.move][constants.CATEGORY]
        != constants.STATUS
        and type_effectiveness_modifier(
            all_move_json[battle.user.last_used_move.move][constants.TYPE],
            side.active.types,
        )
        != 0
        and "from" not in split_msg[-1]
        and not all(x == 0 for x in expected_damage_rolls)
        and battle.user.future_sight[0] != 1
        and not (
            side.active.terastallized
            and type_effectiveness_modifier(
                all_move_json[battle.user.last_used_move.move][constants.TYPE],
                [side.active.tera_type],
            )
            == 0
        )
    ):
        # Battle Factory: Zoroark must be in the reserves
        # and must be immune to the last used move by the bot
        if (
            battle.battle_type == BattleType.BATTLE_FACTORY
            and zoroark_from_reserves is not None
            and type_effectiveness_modifier(
                all_move_json[battle.user.last_used_move.move][constants.TYPE],
                zoroark_from_reserves.types,
            )
            == 0
        ):
            logger.info(
                "{} was immune to {} when it shouldn't be - it is {}".format(
                    pkmn.name,
                    battle.user.last_used_move.move,
                    zoroark_from_reserves.name,
                )
            )
            _switch_active_with_zoroark_from_reserves(side, zoroark_from_reserves)

        # Random Battle: Zoroark may be in the reserves so we need to check the move type
        # that it was immune to
        elif battle.battle_type == BattleType.RANDOM_BATTLE:
            actual_zoroark = None
            zoroark_hisui = Pokemon("zoroarkhisui", 100)
            zoroark_regular = Pokemon("zoroark", 100)

            # zoroark was in the reserves - just use that one
            if (
                zoroark_from_reserves is not None
                and type_effectiveness_modifier(
                    all_move_json[battle.user.last_used_move.move][constants.TYPE],
                    zoroark_from_reserves.types,
                )
                == 0
            ):
                actual_zoroark = zoroark_from_reserves

            # hisui zoroark
            elif (
                zoroark_from_reserves is None
                and type_effectiveness_modifier(
                    all_move_json[battle.user.last_used_move.move][constants.TYPE],
                    zoroark_hisui.types,
                )
                == 0
                and zoroark_hisui.name in RandomBattleTeamDatasets.pkmn_sets
            ):
                actual_zoroark = zoroark_hisui
                actual_zoroark.level = RandomBattleTeamDatasets.predict_set(
                    actual_zoroark
                ).pkmn_set.level
                side.reserve.append(actual_zoroark)

            # regular zoroark
            elif (
                zoroark_from_reserves is None
                and type_effectiveness_modifier(
                    all_move_json[battle.user.last_used_move.move][constants.TYPE],
                    zoroark_regular.types,
                )
                == 0
                and zoroark_regular.name in RandomBattleTeamDatasets.pkmn_sets
            ):
                actual_zoroark = zoroark_regular
                actual_zoroark.level = RandomBattleTeamDatasets.predict_set(
                    actual_zoroark
                ).pkmn_set.level
                side.reserve.append(actual_zoroark)

            # if we found a zoroark from one of those branches
            if actual_zoroark is not None:
                logger.info(
                    "{} was immune to {} when it shouldn't be - it is {}".format(
                        pkmn.name,
                        battle.user.last_used_move.move,
                        actual_zoroark.name,
                    )
                )
                _switch_active_with_zoroark_from_reserves(side, actual_zoroark)


def _switch_active_with_zoroark_from_reserves(
    opponent_side: Battler, zoroark_from_reserves: Pokemon
):
    """
    This is called when we are 100% sure that the opponent's active pkmn is a zoroark
    This swaps the active pkmn with the zoroark from the reserves

    Assumptions:
        - The `zoroark_from_reserves` MUST be in `opponent_side.reserve`
    """
    pkmn = opponent_side.active

    # any moves used by this pkmn since switching in need to be removed because we cannot guarantee that they
    # belong to this pkmn
    for mv in pkmn.moves_used_since_switch_in:
        logger.info(
            "Removing {} from {}'s moves because it is {}".format(
                mv, pkmn.name, zoroark_from_reserves.name
            )
        )
        pkmn.remove_move(mv)
        if zoroark_from_reserves.get_move(mv) is None:
            zoroark_from_reserves.add_move(mv)

    # set attributes on zoroark that were on the pokemon that we thought was zoroark
    # and clear those attributes from the pokemon that we thought was zoroark
    pkmn_hp_percent = float(pkmn.hp) / pkmn.max_hp
    zoroark_from_reserves.hp = zoroark_from_reserves.max_hp * pkmn_hp_percent
    zoroark_from_reserves.boosts = copy(pkmn.boosts)
    zoroark_from_reserves.status = pkmn.status
    zoroark_from_reserves.volatile_statuses = copy(pkmn.volatile_statuses)
    zoroark_from_reserves.terastallized = pkmn.terastallized
    zoroark_from_reserves.tera_type = pkmn.tera_type
    pkmn.boosts.clear()
    pkmn.status = None
    pkmn.volatile_statuses.clear()
    pkmn.volatile_status_durations.clear()

    if pkmn.terastallized:
        pkmn.terastallized = False
        pkmn.tera_type = None

    zoroark_from_reserves.zoroark_disguised_as = pkmn.name

    # swap the pkmn places
    opponent_side.reserve.append(pkmn)
    opponent_side.active = zoroark_from_reserves
    opponent_side.reserve.remove(zoroark_from_reserves)


def update_ability(battle, split_msg):
    if is_opponent(battle, split_msg):
        side = battle.opponent
        other_side = battle.user
    else:
        side = battle.user
        other_side = battle.opponent

    ability = normalize_name(split_msg[3])
    if len(split_msg) >= 6 and "ability:" in split_msg[4]:
        original_ability = normalize_name(split_msg[4].split(":")[-1])
        logger.info(
            "Setting {}'s original ability to {}".format(
                side.active.name, original_ability
            )
        )
        side.active.original_ability = original_ability

        if split_msg[5].startswith("[of]") and other_side.name in split_msg[5]:
            logger.info(
                "Setting {}'s ability to {}".format(other_side.active.name, ability)
            )
            other_side.active.ability = ability
    elif ability == "asone":
        if side.active.name == "calyrexice":
            ability = "asoneglastrier"
        elif side.active.name == "calyrexshadow":
            ability = "asonespectrier"
        else:
            logger.warning(
                "Unknown asone ability for {} - defaulting to asoneglastrier".format(
                    side.active.name
                )
            )
            ability = "asoneglastrier"
    elif side.active.ability in ["asoneglastrier", "asonespectrier"]:
        logger.info(
            "{} has the ability {}, will not change to {}".format(
                side.active.name, side.active.ability, ability
            )
        )
        ability = side.active.ability

    logger.info("Setting {}'s ability to {}".format(side.active.name, ability))
    side.active.ability = ability


def illusion_end(battle, split_msg):
    if is_opponent(battle, split_msg):
        side = battle.opponent
    else:
        side = battle.user

    if (
        is_opponent(battle, split_msg)
        and side.active.name not in ["zoroark", "zoroarkhisui"]
        and side.active.zoroark_disguised_as is None
    ):
        logger.info("Illusion ending for opponent")
        hp_percent = float(side.active.hp) / side.active.max_hp
        previous_boosts = side.active.boosts
        previous_status = side.active.status
        previous_item = side.active.item

        zoroark_from_switch_string = Pokemon.from_switch_string(split_msg[3])
        zoroark_reserve_index = None
        for index, pkmn in enumerate(side.reserve):
            if pkmn == zoroark_from_switch_string:
                zoroark_reserve_index = index
                break

        pkmn_disguised_as = side.active
        pkmn_disguised_as.item = constants.UNKNOWN_ITEM
        side.reserve.append(pkmn_disguised_as)
        if zoroark_reserve_index is not None:
            reserve_zoroark = side.reserve.pop(zoroark_reserve_index)
            side.active = reserve_zoroark
        else:
            side.active = zoroark_from_switch_string

        # the moves that have been used since this pkmn switched-in need
        # to be un-associated with the pkmn being disguised as and need to
        # be associated with the new pkmn instead
        for mv in pkmn_disguised_as.moves_used_since_switch_in:
            pkmn_disguised_as.remove_move(mv)
            if side.active.get_move(mv) is None:
                side.active.add_move(mv)

        # the pokemon that we thought was active needs some attributes reset to
        # whatever the values were at switch-in as any changes that happened to zoroark
        # since switching in have not happened to the actual pokemon
        if pkmn_disguised_as.hp_at_switch_in != pkmn_disguised_as.hp:
            logger.info(
                "Resetting {}'s HP {} to its value at switch-in: {}/{} ({}%)".format(
                    pkmn_disguised_as.name,
                    int(pkmn_disguised_as.hp),
                    pkmn_disguised_as.hp_at_switch_in,
                    pkmn_disguised_as.max_hp,
                    round(
                        100
                        * pkmn_disguised_as.hp_at_switch_in
                        / pkmn_disguised_as.max_hp,
                        1,
                    ),
                )
            )
            pkmn_disguised_as.hp = pkmn_disguised_as.hp_at_switch_in
        if pkmn_disguised_as.status_at_switch_in != pkmn_disguised_as.status:
            logger.info(
                "Resetting {}'s status {} to its value at switch-in: {}".format(
                    pkmn_disguised_as.name,
                    pkmn_disguised_as.status,
                    pkmn_disguised_as.status_at_switch_in,
                )
            )
            pkmn_disguised_as.status = pkmn_disguised_as.status_at_switch_in

        side.active.hp = hp_percent * side.active.max_hp
        side.active.boosts = previous_boosts
        side.active.status = previous_status
        side.active.item = previous_item

    side.active.zoroark_disguised_as = None


def form_change(battle, split_msg):
    if is_opponent(battle, split_msg):
        side = battle.opponent
        is_user = False
    else:
        side = battle.user
        is_user = True

    logger.info("Form Change: {} -> {}".format(side.active.name, split_msg[3]))
    side.active.forme_change(split_msg[3])
    if is_user:
        side.re_initialize_active_pokemon_from_request_json(battle.request_json)


def zpower(battle, split_msg):
    if is_opponent(battle, split_msg):
        side = battle.opponent
    else:
        side = battle.user

    logger.info("{} Used a Z-Move, setting item to None".format(side.active.name))
    side.active.item = None


def clearnegativeboost(battle, split_msg):
    if is_opponent(battle, split_msg):
        pkmn = battle.opponent.active
    else:
        pkmn = battle.user.active

    for stat, value in pkmn.boosts.items():
        if value < 0:
            logger.info("Setting {}'s {} boost to 0".format(pkmn.name, stat))
            pkmn.boosts[stat] = 0


def clearboost(battle, split_msg):
    if is_opponent(battle, split_msg):
        pkmn = battle.opponent.active
    else:
        pkmn = battle.user.active

    for stat, value in pkmn.boosts.items():
        logger.info("Setting {}'s {} boost to 0".format(pkmn.name, stat))
        pkmn.boosts[stat] = 0


def clearallboost(battle, _):
    pkmn = battle.user.active
    for stat, value in pkmn.boosts.items():
        if value != 0:
            logger.info("Setting {}'s {} boost to 0".format(pkmn.name, stat))
            pkmn.boosts[stat] = 0

    pkmn = battle.opponent.active
    for stat, value in pkmn.boosts.items():
        if value != 0:
            logger.info("Setting {}'s {} boost to 0".format(pkmn.name, stat))
            pkmn.boosts[stat] = 0


def singleturn(battle, split_msg):
    if is_opponent(battle, split_msg):
        side = battle.opponent
    else:
        side = battle.user

    move_name = normalize_name(split_msg[3].split(":")[-1])
    if move_name in constants.PROTECT_VOLATILE_STATUSES:
        # increment by 2 because the `upkeep` function will decrement by 1 on every end-of-turn
        side.side_conditions[constants.PROTECT] += 2
        logger.info(
            "{} used a protect move, set protect side condition to {}".format(
                side.active.name, side.side_conditions[constants.PROTECT]
            )
        )

    # |-singleturn|p1a: Skarmory|move: Roost
    elif move_name == constants.ROOST:
        # set to 2 because the `upkeep` function will decrement by 1 on every end-of-turn
        side.active.volatile_statuses.append(constants.ROOST)
        logger.info(
            "{} has acquired the 'roost' volatilestatus".format(side.active.name)
        )


def mustrecharge(battle, split_msg):
    # Bot's side does not get mustrecharge because the request JSON
    # will contain the only available `recharge` move
    if is_opponent(battle, split_msg):
        side = battle.opponent
        logger.info("{} must recharge".format(side.active.name))
        side.active.volatile_statuses.append("mustrecharge")
    else:
        side = battle.user

    # Truant and mustrecharge together means that you only recharge next turn
    if "truant" in side.active.volatile_statuses:
        logger.info(
            "{} must recharge with truant, removing truant".format(side.active.name)
        )
        remove_volatile(side.active, "truant")


def cant(battle, split_msg):
    if is_opponent(battle, split_msg):
        side = battle.opponent
        opponent = True
    else:
        side = battle.user
        opponent = False

    side.last_used_move = LastUsedMove(
        pokemon_name=side.active.name,
        move=side.last_used_move.move,
        turn=battle.turn,
    )

    # |cant|p1a: Slaking|ability: Truant
    if len(split_msg) == 4 and split_msg[3] == "ability: Truant":
        logger.info(
            "{} got 'cant' from truant, removing truant volatile".format(
                side.active.name
            )
        )
        remove_volatile(side.active, "truant")

    # |cant|p2a: Tauros|recharge
    if len(split_msg) == 4 and split_msg[3] == "recharge":
        logger.info(
            "{} got 'cant' from recharge, removing mustrecharge volatile".format(
                side.active.name
            )
        )
        if opponent and "mustrecharge" not in side.active.volatile_statuses:
            logger.warning(
                "{} did not have mustrecharge but recharged".format(side.active.name)
            )

        remove_volatile(side.active, "mustrecharge")

    # |cant|p2a: Politoed|move: Taunt|Toxic
    if len(split_msg) == 4 and split_msg[3].startswith("move: "):
        move_name = normalize_name(split_msg[3].split(":")[-1])
        move_object = side.active.get_move(move_name)
        if move_object is None:
            side.active.add_move(move_name)
            logger.info(
                "Adding {} to {}'s moves from 'cant'".format(
                    move_name, side.active.name
                )
            )

    if len(split_msg) == 4 and split_msg[3] == constants.SLEEP:
        logger.info("{} got 'cant' from sleep".format(side.active.name))
        if side.active.rest_turns > 1:
            side.active.rest_turns -= 1
            logger.info(
                "Decrementing {}'s rest_turns to {}".format(
                    side.active.name, side.active.rest_turns
                )
            )
        elif side.active.rest_turns == 1:
            logger.critical(
                "{} has rest_turns==1 and got 'cant' from sleep".format(
                    side.active.name
                )
            )
            exit(1)
        else:
            side.active.sleep_turns += 1
            logger.info(
                "Incrementing {}'s sleep_turns to {}".format(
                    side.active.name, side.active.sleep_turns
                )
            )


def upkeep(battle, _):
    if battle.trick_room:
        battle.trick_room_turns_remaining -= 1
        logger.info(
            "Trick Room turns remaining: {}".format(battle.trick_room_turns_remaining)
        )

    if battle.field is not None and battle.field_turns_remaining > 0:
        battle.field_turns_remaining -= 1
        logger.info(
            "{} turns remaining: {}".format(battle.field, battle.field_turns_remaining)
        )

    if battle.field is not None and battle.field_turns_remaining == 0:
        logger.info(
            "{} did not end when expected, giving 3 more turns".format(battle.field)
        )
        battle.field_turns_remaining = 3

    if constants.ROOST in battle.user.active.volatile_statuses:
        logger.info(
            "Removing 'roost' from {}'s volatiles".format(battle.user.active.name)
        )
        battle.user.active.volatile_statuses = [
            v for v in battle.user.active.volatile_statuses if v != constants.ROOST
        ]

    if constants.ROOST in battle.opponent.active.volatile_statuses:
        logger.info(
            "Removing 'roost' from {}'s volatiles".format(battle.opponent.active.name)
        )
        battle.opponent.active.volatile_statuses = [
            v for v in battle.opponent.active.volatile_statuses if v != constants.ROOST
        ]

    for side in [battle.user, battle.opponent]:
        side_string = "opponent" if side == battle.opponent else "user"

        if (
            "taunt" in side.active.volatile_statuses
            and battle.generation in constants.TAUNT_DURATION_INCREMENT_END_OF_TURN
        ):
            side.active.volatile_status_durations[constants.TAUNT] += 1
            logger.info(
                "Incrementing taunt duration for {} to {}".format(
                    side_string,
                    side.active.volatile_status_durations[constants.TAUNT],
                )
            )

        if constants.LOCKED_MOVE in side.active.volatile_statuses:
            side.active.volatile_status_durations[constants.LOCKED_MOVE] += 1
            logger.info(
                "Incremented lockedmove for {} to {}".format(
                    side_string,
                    side.active.volatile_status_durations[constants.LOCKED_MOVE],
                )
            )

        if side.side_conditions[constants.REFLECT] > 0:
            side.side_conditions[constants.REFLECT] -= 1
            logger.info(
                "Decrementing reflect for {} to {}".format(
                    side_string, side.side_conditions[constants.REFLECT]
                )
            )
            if side.side_conditions[constants.REFLECT] == 0:
                logger.info(
                    "reflect did not end for {} when expected, giving it 3 more turns".format(
                        side_string
                    )
                )
                side.side_conditions[constants.REFLECT] = 3

        if side.side_conditions[constants.LIGHT_SCREEN] > 0:
            side.side_conditions[constants.LIGHT_SCREEN] -= 1
            logger.info(
                "Decrementing lightscreen for {} to {}".format(
                    side_string, side.side_conditions[constants.LIGHT_SCREEN]
                )
            )
            if side.side_conditions[constants.LIGHT_SCREEN] == 0:
                logger.info(
                    "lightscreen did not end for {} when expected, giving it 3 more turns".format(
                        side_string
                    )
                )
                side.side_conditions[constants.LIGHT_SCREEN] = 3

        if side.side_conditions[constants.AURORA_VEIL] > 0:
            side.side_conditions[constants.AURORA_VEIL] -= 1
            logger.info(
                "Decrementing auroraveil for {} to {}".format(
                    side_string, side.side_conditions[constants.AURORA_VEIL]
                )
            )
            if side.side_conditions[constants.AURORA_VEIL] == 0:
                logger.info(
                    "auroraveil did not end for {} when expected, giving it 3 more turns".format(
                        side_string
                    )
                )
                side.side_conditions[constants.AURORA_VEIL] = 3

        if side.side_conditions[constants.TAILWIND] > 0:
            side.side_conditions[constants.TAILWIND] -= 1
            logger.info(
                "Decrementing tailwind for {} to {}".format(
                    side_string, side.side_conditions[constants.TAILWIND]
                )
            )

        if side.side_conditions[constants.MIST] > 0:
            side.side_conditions[constants.MIST] -= 1
            logger.info(
                "Decrementing mist for {} to {}".format(
                    side_string, side.side_conditions[constants.MIST]
                )
            )

        if side.side_conditions[constants.SAFEGUARD] > 0:
            side.side_conditions[constants.SAFEGUARD] -= 1
            logger.info(
                "Decrementing safeguard for {} to {}".format(
                    side_string, side.side_conditions[constants.SAFEGUARD]
                )
            )

        pkmn = side.active
        if constants.YAWN in pkmn.volatile_statuses:
            previous_duration = pkmn.volatile_status_durations[constants.YAWN]
            if previous_duration == 0:
                pkmn.volatile_status_durations[constants.YAWN] = 1
            elif previous_duration == 1:
                pkmn.volatile_status_durations[constants.YAWN] = 0
                remove_volatile(pkmn, constants.YAWN)
                logger.info("Removed yawn volatile from {}".format(pkmn.name))
            else:
                raise ValueError(
                    "Got yawn duration {} for {}".format(previous_duration, pkmn.name)
                )
            logger.info(
                "{} had yawn at the end of the turn, changed duration from {} to {}".format(
                    pkmn.name,
                    previous_duration,
                    pkmn.volatile_status_durations[constants.YAWN],
                )
            )
        if constants.SLOW_START in pkmn.volatile_statuses:
            pkmn.volatile_status_durations[constants.SLOW_START] -= 1
            logger.info(
                "Decremented slow start duration for {} to {}".format(
                    pkmn.name, pkmn.volatile_status_durations[constants.SLOW_START]
                )
            )

        if (
            battle.generation == "gen3"
            and pkmn.status == constants.SLEEP
            and side.last_used_move.move != "sleeptalk"
        ):
            pkmn.gen_3_consecutive_sleep_talks = 0
            logger.info(
                "{} is asleep but didn't use sleeptalk, decrementing gen_3_consecutive_sleep_talks to 0".format(
                    pkmn.name
                )
            )

    if battle.user.side_conditions[constants.PROTECT] > 0:
        battle.user.side_conditions[constants.PROTECT] -= 1
        logger.info(
            "Setting protect to {} for the bot".format(
                battle.user.side_conditions[constants.PROTECT]
            )
        )

    if battle.opponent.side_conditions[constants.PROTECT] > 0:
        battle.opponent.side_conditions[constants.PROTECT] -= 1
        logger.info(
            "Setting protect to {} for the opponent".format(
                battle.opponent.side_conditions[constants.PROTECT]
            )
        )

    if battle.user.wish[0] > 0:
        battle.user.wish = (battle.user.wish[0] - 1, battle.user.wish[1])
        logger.info("Decrementing wish to {} for the bot".format(battle.user.wish[0]))

    if battle.opponent.wish[0] > 0:
        battle.opponent.wish = (battle.opponent.wish[0] - 1, battle.opponent.wish[1])
        logger.info(
            "Decrementing wish to {} for the opponent".format(battle.opponent.wish[0])
        )

    if battle.user.future_sight[0] > 0:
        battle.user.future_sight = (
            battle.user.future_sight[0] - 1,
            battle.user.future_sight[1],
        )
        logger.info(
            "Decrementing future_sight to {} for the bot".format(
                battle.user.future_sight[0]
            )
        )

    if battle.opponent.future_sight[0] > 0:
        battle.opponent.future_sight = (
            battle.opponent.future_sight[0] - 1,
            battle.opponent.future_sight[1],
        )
        logger.info(
            "Decrementing future_sight to {} for the opponent".format(
                battle.opponent.future_sight[0]
            )
        )

    # If a pkmn has less than maxhp during upkeep,
    # we do not want to guess leftovers/blacksludge anymore when it is time to guess an item
    # leftovers and blacksludge will reveal themselves at the end of the turn if they exist
    opp_pkmn = battle.opponent.active
    if opp_pkmn.hp < opp_pkmn.max_hp:
        logger.info(
            "{} has less than maxhp during upkeep, no longer guessing leftovers or blacksludge".format(
                opp_pkmn.name
            )
        )
        opp_pkmn.impossible_items.add(constants.LEFTOVERS)
        opp_pkmn.impossible_items.add(constants.BLACK_SLUDGE)

    if opp_pkmn.status is None:
        opp_pkmn.impossible_items.add("flameorb")
        opp_pkmn.impossible_items.add("toxicorb")


def mega(battle, split_msg):
    if is_opponent(battle, split_msg):
        side = battle.opponent
    else:
        side = battle.user

    side.active.is_mega = True
    forced_mega_ability = normalize_name(
        pokedex[side.active.name][constants.ABILITIES]["0"]
    )
    side.active.ability = forced_mega_ability
    logger.info(
        "Mega-Pokemon: {} with ability {}".format(side.active.name, forced_mega_ability)
    )


def transform(battle, split_msg):
    if is_opponent(battle, split_msg):
        side = battle.opponent
        other_side = battle.user
    else:
        side = battle.user
        other_side = battle.opponent

    transformed_into_name = other_side.active.name
    logger.info(
        "{} transformed into {}".format(side.active.name, transformed_into_name)
    )
    side.active.boosts = deepcopy(other_side.active.boosts)
    logger.info(
        "Copied {}'s boosts: {}".format(side.active.name, dict(side.active.boosts))
    )

    if constants.TRANSFORM not in side.active.volatile_statuses:
        side.active.volatile_statuses.append(constants.TRANSFORM)

    transformed_into = other_side.active
    side.active.stats = deepcopy(transformed_into.stats)
    side.active.moves = deepcopy(transformed_into.moves)
    side.active.types = deepcopy(transformed_into.types)
    side.active.boosts = deepcopy(transformed_into.boosts)

    for mv in side.active.moves:
        mv.current_pp = 5

    if split_msg[-1].startswith("[from]") and "ability:" in split_msg[-1]:
        side.active.original_ability = normalize_name(
            split_msg[-1].split("ability:")[-1].strip()
        )
    elif side.active.ability is not None:
        side.active.original_ability = side.active.ability

    side.active.ability = deepcopy(transformed_into.ability)


def turn(battle, split_msg):
    battle.turn = int(split_msg[2])
    logger.info("")
    logger.info("Turn: {}".format(battle.turn))


def noinit(battle, split_msg):
    if split_msg[2] == "rename":
        battle.battle_tag = split_msg[3]
        logger.info("Renamed battle to {}".format(battle.battle_tag))


def check_speed_ranges(battle, msg_lines):
    """
    Intention:
        This function is intended to set the min or max possible speed that the opponent's
        active Pokemon could possibly have given a turn that just happened.

        For example: if both the bot and the opponent use an equal priority move but the
        opponent moves first, then the opponent's min_speed attribute will be set to the
        bots actual speed. This is because the opponent must have at least that much speed
        for it to have gone first.

        These min/max speeds are set without knowledge of items. If the opponent goes first
        when having a choice scarf then min speed will still be set to the bots speed. When
        it comes time to guess a Pokemon's possible set(s), the item must be taken into account
        as well when determining the final speed of a Pokemon. Abilities are NOT taken into
        consideration because their speed modifications are subject to certain conditions
        being present, whereas a choice scarf ALWAYS boosts speed.

        If there is a situation where an ability could have modified the turn order (either by
        changing a move's priority or giving a Pokemon more speed) then this check should be
        skipped. Examples are:
            - either side switched
            - the opponent COULD have a speed-boosting weather ability AND that weather is up
            - the opponent COULD have prankster and it used a status move
            - Grassy Glide is used when Grassy Terrain is up
    """
    for ln in msg_lines:
        # If either side switched this turn - don't do this check
        if ln.startswith("|switch|"):
            return

        # if anyone got `cant` or hit themselves in confusion
        # skip this check as we don't know if they used a priority move
        if ln.startswith("|cant|") or (
            ln.startswith("|-activate|") and ln.endswith("confusion")
        ):
            return

        # If anyone used a custapberry, skip this check
        if ln.startswith("|-enditem|") and (
            "custapberry" in normalize_name(ln) or "Custap Berry" in ln
        ):
            return

        # If anyone had quick claw activate, skip this check
        if "quickclaw" in normalize_name(ln) or "Quick Claw" in ln:
            return

        # If anyone had quick claw activate, skip this check
        if "quickdraw" in normalize_name(ln) or "Quick Draw" in ln:
            return

    moves = [get_move_information(m) for m in msg_lines if m.startswith("|move|")]
    number_of_moves = len(moves)
    if number_of_moves not in [1, 2]:
        return

    if (
        number_of_moves == 1
        and moves[0][0].startswith(battle.opponent.name)
        and moves[0][1][constants.ID] != "pursuit"
    ):
        moves.append(
            (
                "{}a: {}".format(battle.opponent.name, battle.user.active.name),
                all_move_json[normalize_name(battle.user.last_selected_move.move)],
            )
        )

    # if the bot knocked out the opponent there's nothing to do here
    elif number_of_moves == 1:
        return

    if (
        moves[0][1][constants.PRIORITY] != moves[1][1][constants.PRIORITY]
        or moves[0][1][constants.ID] == "encore"
    ):
        return

    bot_went_first = moves[0][0].startswith(battle.user.name)

    if (
        battle.opponent.active is None
        or battle.opponent.active.item == "choicescarf"
        or can_have_speed_modified(battle, battle.opponent.active)
        or (
            not bot_went_first
            and can_have_priority_modified(
                battle, battle.opponent.active, moves[0][1][constants.ID]
            )
        )
        or (
            bot_went_first
            and can_have_priority_modified(
                battle, battle.user.active, moves[0][1][constants.ID]
            )
        )
    ):
        return

    battle_copy = deepcopy(battle)
    battle_copy_for_stats = deepcopy(battle_copy)
    battle_copy.user.active.status = battle_copy_for_stats.user.active.stats

    speed_threshold = int(
        boost_multiplier_lookup[battle_copy.user.active.boosts[constants.SPEED]]
        * battle_copy.user.active.stats[constants.SPEED]
        / boost_multiplier_lookup[battle_copy.opponent.active.boosts[constants.SPEED]]
    )

    if "protosynthesisspe" in battle.opponent.active.volatile_statuses:
        speed_threshold = int(speed_threshold / 1.5)

    if battle.opponent.side_conditions[constants.TAILWIND]:
        speed_threshold = int(speed_threshold / 2)

    if battle.user.side_conditions[constants.TAILWIND]:
        speed_threshold = int(speed_threshold * 2)

    if battle.opponent.active.status == constants.PARALYZED:
        if battle.generation in ["gen4", "gen5", "gen6"]:
            speed_threshold = int(speed_threshold * 4)
        else:
            speed_threshold = int(speed_threshold * 2)

    if battle.user.active.status == constants.PARALYZED:
        if battle.generation in ["gen4", "gen5", "gen6"]:
            speed_threshold = int(speed_threshold / 4)
        else:
            speed_threshold = int(speed_threshold / 2)

    if battle.user.active.item == "choicescarf":
        speed_threshold = int(speed_threshold * 1.5)

    if "protosynthesisspe" in battle.user.active.volatile_statuses:
        speed_threshold = int(speed_threshold * 1.5)

    # we want to swap which attribute gets updated in trickroom because the slower pokemon goes first
    if battle.trick_room:
        bot_went_first = not bot_went_first

    if bot_went_first:
        opponent_max_speed = min(
            battle.opponent.active.speed_range.max, speed_threshold
        )
        battle.opponent.active.speed_range = StatRange(
            min=battle.opponent.active.speed_range.min, max=opponent_max_speed
        )
        logger.info(
            "Updated {}'s max speed to {}".format(
                battle.opponent.active.name, battle.opponent.active.speed_range.max
            )
        )

    else:
        opponent_min_speed = max(
            battle.opponent.active.speed_range.min, speed_threshold
        )
        battle.opponent.active.speed_range = StatRange(
            min=opponent_min_speed, max=battle.opponent.active.speed_range.max
        )
        logger.info(
            "Updated {}'s min speed to {}".format(
                battle.opponent.active.name, battle.opponent.active.speed_range.min
            )
        )


def check_opponent_hiddenpower(battle, msg_line):
    """
    `msg_line` is should be the line *after* |-move|...|Hidden Power|...
    and is meant to be called for the opponent's pkmn only

    This function checks if the move was resisted, super-effective, or neutral.
    It then updates pkmn.hidden_power_possibilities based on that information
    """
    attacker = battle.opponent.active
    defender_types = battle.user.active.types
    logger.info(
        "Checking hiddenpower possibilities for opponent's {}".format(attacker.name)
    )
    logger.info(
        "Starting hiddenpower possibilities {}".format(
            attacker.hidden_power_possibilities
        )
    )

    next_line_split_msg = msg_line.split("|")
    if next_line_split_msg[1] == "-resisted":
        logger.info("{} resisted hiddenpower".format(defender_types))
        for t in list(attacker.hidden_power_possibilities):
            if not is_not_very_effective(t, defender_types):
                attacker.hidden_power_possibilities.remove(t)

    elif next_line_split_msg[1] == "-supereffective":
        logger.info("{} was weak to hiddenpower".format(defender_types))
        for t in list(attacker.hidden_power_possibilities):
            if not is_super_effective(t, defender_types):
                attacker.hidden_power_possibilities.remove(t)

    elif next_line_split_msg[1] == "-damage":
        logger.info("{} was neutral to hiddenpower".format(defender_types))
        for t in list(attacker.hidden_power_possibilities):
            if not is_neutral_effectiveness(t, defender_types):
                attacker.hidden_power_possibilities.remove(t)

    else:
        logger.info(
            "Cannot update hiddenpower possibilities with: {}".format(
                next_line_split_msg[1]
            )
        )
        return

    logger.info(
        "Remaining hiddenpower possibilities: {}".format(
            attacker.hidden_power_possibilities
        )
    )


def check_choicescarf(battle, msg_lines):
    # If either side switched this turn - don't do this check
    if any(
        battle.generation in ["gen1", "gen2", "gen3"]
        or ln.startswith("|switch|")
        or ln.startswith("|cant|")
        or (ln.startswith("|-activate|") and ln.endswith("confusion"))
        for ln in msg_lines
    ) or battle.user.last_selected_move.move.startswith("switch "):
        return

    moves = [get_move_information(m) for m in msg_lines if m.startswith("|move|")]
    number_of_moves = len(moves)

    # if the bot went first we cannot ever infer a choicescarf
    if number_of_moves not in [1, 2] or moves[0][0].startswith(battle.user.name):
        return

    elif number_of_moves == 1:
        moves.append(
            (
                "{}a: {}".format(battle.opponent.name, battle.user.active.name),
                all_move_json[normalize_name(battle.user.last_selected_move.move)],
            )
        )

    if moves[0][1][constants.PRIORITY] != moves[1][1][constants.PRIORITY]:
        return

    battle_copy = deepcopy(battle)
    if (
        battle.opponent.active is None
        or battle.opponent.active.item != constants.UNKNOWN_ITEM
        or not battle.opponent.active.can_have_choice_item
        or can_have_speed_modified(battle, battle.opponent.active)
        or can_have_priority_modified(
            battle, battle.opponent.active, moves[0][1][constants.ID]
        )
        or can_have_priority_modified(
            battle, battle.user.active, moves[1][1][constants.ID]
        )
        or (
            battle_copy.user.active.ability == "unburden"
            and battle_copy.user.active.item is None
        )
    ):
        return

    if battle.battle_type == BattleType.RANDOM_BATTLE:
        battle_copy.opponent.active.set_spread(
            "serious", "85,85,85,85,85,85"
        )  # random battles have known spreads
    else:
        if battle.trick_room:
            battle_copy.opponent.active.set_spread(
                "quiet", "0,0,0,0,0,0"
            )  # assume as slow as possible in trickroom
        else:
            battle_copy.opponent.active.set_spread(
                "jolly", "0,0,0,0,0,252"
            )  # assume as fast as possible
    opponent_effective_speed = battle_copy.get_effective_speed(battle_copy.opponent)
    bot_effective_speed = battle_copy.get_effective_speed(battle_copy.user)

    if battle.trick_room:
        has_scarf = opponent_effective_speed > bot_effective_speed
    else:
        has_scarf = bot_effective_speed > opponent_effective_speed

    if has_scarf:
        logger.info(
            "Opponent {} could not have gone first - setting it's item to choicescarf".format(
                battle.opponent.active.name
            )
        )
        battle.opponent.active.item = "choicescarf"
        battle.opponent.active.item_inferred = True


def get_damage_dealt(battle, split_msg, next_messages):
    move_name = normalize_name(split_msg[3])
    critical_hit = False

    if is_opponent(battle, split_msg):
        attacking_side = battle.opponent
        defending_side = battle.user
    else:
        attacking_side = battle.user
        defending_side = battle.opponent

    for line in next_messages:
        next_line_split = line.split("|")
        # if one of these strings appears in index 1 then
        # exit out since we are done with this pokemon's move
        if len(next_line_split) < 2 or next_line_split[1] in MOVE_END_STRINGS:
            break

        elif next_line_split[1] == "-crit":
            critical_hit = True

        # if '-damage' appears, we want to parse the percentage damage dealt
        elif (
            next_line_split[1] == "-damage"
            and defending_side.name in next_line_split[2]
        ):
            final_health, maxhp, _ = get_pokemon_info_from_condition(next_line_split[3])
            # maxhp can be 0 if the targetted pokemon fainted
            # the message would be: "0 fnt"
            if maxhp == 0:
                maxhp = defending_side.active.max_hp

            damage_dealt = (
                defending_side.active.hp / defending_side.active.max_hp
            ) * maxhp - final_health
            damage_percentage = round(damage_dealt / maxhp, 4)

            logger.info(
                "{} did {}% damage to {} with {}".format(
                    attacking_side.active.name,
                    damage_percentage * 100,
                    defending_side.active.name,
                    move_name,
                )
            )
            return DamageDealt(
                attacker=attacking_side.active.name,
                defender=defending_side.active.name,
                move=move_name,
                percent_damage=damage_percentage,
                crit=critical_hit,
            )


def _do_check(
    battle,
    battle_copy,
    possibilites,
    check_type,
    damage_dealt,
    bot_went_first,
    check_lower_bound,
    allow_emptying=False,
):
    actual_damage_dealt = damage_dealt.percent_damage * battle_copy.user.active.max_hp

    indicies_to_remove = []
    num_starting_possibilites = len(possibilites)
    for i in range(num_starting_possibilites):
        p = possibilites[i]
        if isinstance(p, PredictedPokemonSet):
            p = p.pkmn_set

        if not battle.opponent.active.ability:
            battle_copy.opponent.active.ability = p.ability
        if battle.opponent.active.item == constants.UNKNOWN_ITEM:
            battle_copy.opponent.active.item = p.item
        battle_copy.opponent.active.set_spread(
            p.nature, ",".join(str(x) for x in p.evs)
        )

        if check_type == "damage_received":
            actual_damage_dealt = (
                damage_dealt.percent_damage * battle_copy.opponent.active.max_hp
            )

            if bot_went_first:
                opponent_move = constants.DO_NOTHING_MOVE
            else:
                opponent_move = battle_copy.opponent.last_used_move.move

            damage, _ = poke_engine_get_damage_rolls(
                battle_copy, damage_dealt.move, opponent_move, bot_went_first
            )
        elif check_type == "damage_dealt":
            _, damage = poke_engine_get_damage_rolls(
                battle_copy,
                battle_copy.user.last_selected_move.move,
                damage_dealt.move,
                bot_went_first,
            )
        else:
            raise ValueError("Invalid check_type: {}".format(check_type))

        if damage_dealt.crit:
            max_damage = damage[1]
        else:
            max_damage = damage[0]

        damage = [max_damage * 0.85, max_damage]
        lower_bound_violated = check_lower_bound and (
            actual_damage_dealt < (damage[0] * 0.975 - 5)
        )
        upper_bound_violated = actual_damage_dealt > (damage[1] * 1.025 + 5)
        if lower_bound_violated or upper_bound_violated:
            logger.debug(
                "{} is invalid based on reverse damage calc. damage_dealt={}, lower={}, upper={}".format(
                    p, actual_damage_dealt, damage[0], damage[1]
                )
            )
            indicies_to_remove.append(i)

    if len(indicies_to_remove) == num_starting_possibilites and not allow_emptying:
        logger.warning("Would remove all possibilities, not removing any")
        logger.warning(f"{actual_damage_dealt=}")
        return

    for i in reversed(indicies_to_remove):
        possibilites.pop(i)


def update_dataset_possibilities(
    battle,
    damage_dealt,
    check_type,
):
    if (
        battle.wait
        or battle.generation in {"gen1", "gen2"}
        or battle.opponent.active is None
        or battle.opponent.active.hp <= 0
        or battle.opponent.active.name
        in ["ditto", "shedinja", "terapagosterastal", "meloetta", "meloettapirouette"]
        or battle.user.active.name
        in ["ditto", "shedinja", "terapagosterastal", "meloetta", "meloettapirouette"]
        or damage_dealt.move not in all_move_json
        or all_move_json[damage_dealt.move][constants.CATEGORY] == constants.STATUS
        or "multiaccuracy" in all_move_json[damage_dealt.move]
        or damage_dealt.move.startswith(constants.HIDDEN_POWER)
        or damage_dealt.percent_damage == 0
        or (
            check_type == "damage_dealt"
            and battle.opponent.last_used_move.move != damage_dealt.move
        )
        or (
            check_type == "damage_received"
            and battle.user.last_used_move.move != damage_dealt.move
        )
        or damage_dealt.move
        in [
            "pursuit",
            "struggle",
            "counter",
            "mirrorcoat",
            "metalburst",
            "foulplay",
            "meteorbeam",
            "electroshot",
            "ficklebeam",
            "lashout",
            "ragefist",
            "shellsidearm",
            "futuresight",
        ]
    ):
        return

    battle_copy = deepcopy(battle)

    if battle.battle_type == BattleType.RANDOM_BATTLE:
        possibilites = RandomBattleTeamDatasets.get_pkmn_sets_from_pkmn_name(
            battle.opponent.active
        )
        smogon_possibilities = None
        allow_emptying = False
    elif battle.battle_type == BattleType.BATTLE_FACTORY:
        possibilites = TeamDatasets.get_pkmn_sets_from_pkmn_name(battle.opponent.active)
        smogon_possibilities = None
        allow_emptying = False
    else:
        possibilites = TeamDatasets.get_pkmn_sets_from_pkmn_name(battle.opponent.active)
        smogon_possibilities = SmogonSets.get_pkmn_sets_from_pkmn_name(
            battle.opponent.active
        )
        allow_emptying = True

    check_lower_bound = True
    if check_type == "damage_dealt":
        user_percent_hp = round(battle.user.active.hp / battle.user.active.max_hp, 2)
        if abs(damage_dealt.percent_damage - user_percent_hp) < 0.02:
            check_lower_bound = False
        bot_went_first = (
            battle.user.last_used_move.turn == battle.opponent.last_used_move.turn
        )
    elif check_type == "damage_received":
        opponent_percent_hp = round(
            battle.opponent.active.hp / battle.opponent.active.max_hp, 2
        )
        if abs(damage_dealt.percent_damage - opponent_percent_hp) < 0.02:
            check_lower_bound = False
        bot_went_first = (
            battle.opponent.last_used_move.turn != battle.user.last_used_move.turn
        )
    else:
        raise ValueError("Invalid check_type: {}".format(check_type))

    logger.debug(f"{check_type=}")
    logger.debug(f"{check_lower_bound=}")
    logger.debug(f"{bot_went_first=}")

    _do_check(
        battle,
        battle_copy,
        possibilites,
        check_type,
        damage_dealt,
        bot_went_first,
        check_lower_bound,
        allow_emptying=allow_emptying,
    )

    if smogon_possibilities is not None:
        _do_check(
            battle,
            battle_copy,
            smogon_possibilities,
            check_type,
            damage_dealt,
            bot_went_first,
            check_lower_bound,
            allow_emptying=False,  # never completely empty smogon stats
        )


def check_heavydutyboots(battle, msg_lines):
    side_to_check = battle.opponent

    if (
        battle.generation not in ["gen8", "gen9"]
        or side_to_check.active.item != constants.UNKNOWN_ITEM
        or "magicguard"
        in [
            normalize_name(a)
            for a in pokedex[side_to_check.active.name][constants.ABILITIES].values()
        ]
    ):
        return

    if side_to_check.side_conditions[constants.STEALTH_ROCK] > 0:
        pkmn_took_stealthrock_damage = False
        for line in msg_lines:
            split_line = line.split("|")

            # |-damage|p2a: Weedle|88/100|[from] Stealth Rock
            if (
                len(split_line) > 4
                and split_line[1] == "-damage"
                and split_line[2].startswith(side_to_check.name)
                and split_line[4] == "[from] Stealth Rock"
            ):
                pkmn_took_stealthrock_damage = True

        if not pkmn_took_stealthrock_damage:
            logger.info("{} has heavydutyboots".format(side_to_check.active.name))
            side_to_check.active.item = "heavydutyboots"
            side_to_check.active.item_inferred = True
        else:
            logger.info(
                "{} was affected by stealthrock, it cannot have heavydutyboots".format(
                    side_to_check.active.name
                )
            )
            side_to_check.active.impossible_items.add(constants.HEAVY_DUTY_BOOTS)

    elif (
        side_to_check.side_conditions[constants.SPIKES] > 0
        and "levitate"
        not in [
            normalize_name(a)
            for a in pokedex[side_to_check.active.name][constants.ABILITIES].values()
        ]
        and not side_to_check.active.has_type("flying")
        and side_to_check.active.ability != "levitate"
    ):
        pkmn_took_spikes_damage = False
        for line in msg_lines:
            split_line = line.split("|")

            # |-damage|p2a: Weedle|88/100|[from] Spikes
            if (
                len(split_line) > 4
                and split_line[1] == "-damage"
                and split_line[2].startswith(side_to_check.name)
                and split_line[4] == "[from] Spikes"
            ):
                pkmn_took_spikes_damage = True

        if not pkmn_took_spikes_damage:
            logger.info("{} has heavydutyboots".format(side_to_check.active.name))
            side_to_check.active.item = "heavydutyboots"
            side_to_check.active.item_inferred = True
        else:
            logger.info(
                "{} was affected by spikes, it cannot have heavydutyboots".format(
                    side_to_check.active.name
                )
            )
            side_to_check.active.impossible_items.add(constants.HEAVY_DUTY_BOOTS)
    elif (
        side_to_check.side_conditions[constants.TOXIC_SPIKES] > 0
        and side_to_check.active.status is None
        and not side_to_check.active.has_type("flying")
        and not side_to_check.active.has_type("poison")
        and not side_to_check.active.has_type("steel")
        and side_to_check.active.ability != "levitate"
        and "levitate"
        not in [
            normalize_name(a)
            for a in pokedex[side_to_check.active.name][constants.ABILITIES].values()
        ]
        and side_to_check.active.ability not in constants.IMMUNE_TO_POISON_ABILITIES
    ):
        pkmn_took_toxicspikes_poison = False
        for line in msg_lines:
            split_line = line.split("|")

            # a pokemon can be toxic-ed from sources other than toxicspikes
            # stopping at one of these strings ensures those other sources aren't considered
            if len(split_line) < 2 or split_line[1] in {"move", "upkeep", ""}:
                break

            # |-status|p2a: Pikachu|psn
            if (
                split_line[1] == "-status"
                and (
                    split_line[3] == constants.POISON
                    or split_line[3] == constants.TOXIC
                )
                and split_line[2].startswith(side_to_check.name)
            ):
                pkmn_took_toxicspikes_poison = True

        if not pkmn_took_toxicspikes_poison:
            logger.info("{} has heavydutyboots".format(side_to_check.active.name))
            side_to_check.active.item = "heavydutyboots"
            side_to_check.active.item_inferred = True
        else:
            logger.info(
                "{} was affected by toxicspikes, it cannot have heavydutyboots".format(
                    side_to_check.active.name
                )
            )
            side_to_check.active.impossible_items.add(constants.HEAVY_DUTY_BOOTS)

    elif (
        side_to_check.side_conditions[constants.STICKY_WEB] > 0
        and not side_to_check.active.has_type("flying")
        and "levitate"
        not in [
            normalize_name(a)
            for a in pokedex[side_to_check.active.name][constants.ABILITIES].values()
        ]
    ):
        pkmn_was_affected_by_stickyweb = False
        for line in msg_lines:
            split_line = line.split("|")

            # |-activate|p2a: Gengar|move: Sticky Web
            if (
                len(split_line) == 4
                and split_line[1] == "-activate"
                and split_line[2].startswith(side_to_check.name)
                and split_line[3] == "move: Sticky Web"
            ):
                pkmn_was_affected_by_stickyweb = True

        if not pkmn_was_affected_by_stickyweb:
            logger.info("{} has heavydutyboots".format(side_to_check.active.name))
            side_to_check.active.item = "heavydutyboots"
            side_to_check.active.item_inferred = True
        else:
            logger.debug(
                "{} was affected by sticky web, it cannot have heavydutyboots".format(
                    side_to_check.active.name
                )
            )
            side_to_check.active.impossible_items.add(constants.HEAVY_DUTY_BOOTS)


def update_battle(battle: Battle, msg: str):
    msg_lines = msg.split("\n")
    for line in msg_lines:
        split_msg = line.split("|")
        if len(split_msg) < 2:
            continue

        action = split_msg[1].strip()
        if action == "request":
            request(battle, split_msg)
            process_battle_updates(battle)
            return not battle.wait
        else:
            battle.msg_list.append(line)

    return False


def process_battle_updates(battle: Battle):
    msg_lines = battle.msg_list
    check_speed_ranges(battle, msg_lines)
    for i, line in enumerate(msg_lines):
        split_msg = line.split("|")
        if len(split_msg) < 2:
            continue

        action = split_msg[1].strip()

        battle_modifiers_lookup = {
            "switch": switch,
            "faint": faint,
            "-fail": fail,
            "drag": drag,
            "-heal": heal_or_damage,
            "-damage": heal_or_damage,
            "-sethp": sethp,
            "move": move,
            "-setboost": setboost,
            "-boost": boost,
            "-unboost": unboost,
            "-status": status,
            "-activate": activate,
            "-anim": anim,
            "-prepare": prepare,
            "-start": start_volatile_status,
            "-singlemove": start_volatile_status,
            "-end": end_volatile_status,
            "-curestatus": curestatus,
            "-cureteam": cureteam,
            "-weather": weather,
            "-fieldstart": fieldstart,
            "-fieldend": fieldend,
            "-sidestart": sidestart,
            "-sideend": sideend,
            "-swapsideconditions": swapsideconditions,
            "-item": set_item,
            "-enditem": remove_item,
            "-immune": immune,
            "-ability": update_ability,
            "detailschange": form_change,
            "replace": illusion_end,
            "-formechange": form_change,
            "-transform": transform,
            "-mega": mega,
            "-terastallize": terastallize,
            "-zpower": zpower,
            "-clearnegativeboost": clearnegativeboost,
            "-clearboost": clearboost,
            "-clearallboost": clearallboost,
            "-singleturn": singleturn,
            "-mustrecharge": mustrecharge,
            "upkeep": upkeep,
            "cant": cant,
            "inactive": inactive,
            "inactiveoff": inactiveoff,
            "turn": turn,
            "noinit": noinit,
        }

        function_to_call = battle_modifiers_lookup.get(action)
        if function_to_call is not None:
            function_to_call(battle, split_msg)

        if action == "move" and is_opponent(battle, split_msg):
            if normalize_name(split_msg[3].strip()) == constants.HIDDEN_POWER:
                check_opponent_hiddenpower(battle, msg_lines[i + 1])
            check_choicescarf(battle, msg_lines)
            damage_dealt = get_damage_dealt(battle, split_msg, msg_lines[i + 1 :])
            if damage_dealt:
                update_dataset_possibilities(battle, damage_dealt, "damage_dealt")

        elif action == "move" and not is_opponent(battle, split_msg):
            damage_dealt = get_damage_dealt(battle, split_msg, msg_lines[i + 1 :])
            if damage_dealt:
                update_dataset_possibilities(battle, damage_dealt, "damage_received")

        elif action == "switch" and is_opponent(battle, split_msg):
            check_heavydutyboots(battle, msg_lines[i + 1 :])

    battle.msg_list.clear()


async def async_update_battle(battle, msg):
    return update_battle(battle, msg)
