import re
from copy import deepcopy
from dataclasses import replace
import logging

from fp import constants
from fp.data import all_move_json
from fp.data import pokedex
from fp.battle.state import Pokemon, Battle
from fp.battle.state import LastUsedMove
from fp.search.poke_engine_helpers import poke_engine_get_damage_rolls
from fp.battle.helpers import (
    normalize_name,
    type_effectiveness_modifier,
)
from fp.battle.helpers import calculate_stats
from fp.battle.protocol_types import EffectKind
from fp.battle.protocol_messages import (
    Ability,
    Activate,
    Anim,
    Boost,
    Cant,
    ClearAllBoost,
    ClearBoost,
    ClearNegativeBoost,
    CureStatus,
    CureTeam,
    Damage,
    End,
    EndItem,
    Fail,
    Faint,
    FieldEnd,
    FieldStart,
    FormeChange,
    Heal,
    Immune,
    Inactive,
    InactiveOff,
    Item,
    Mega,
    Message,
    Move,
    MustRecharge,
    NoInit,
    Prepare,
    Replace,
    SetBoost,
    SetHp,
    SideEnd,
    SideStart,
    SingleTurn,
    Start,
    Status,
    SwapSideConditions,
    Switch,
    Terastallize,
    Transform,
    Turn,
    Unboost,
    Upkeep,
    Weather,
    ZPower,
    RequestMessage,
    parse_line,
    parse_lines,
)
from fp.battle.inference import check_speed_ranges
from fp.battle.inference import check_opponent_hiddenpower
from fp.battle.inference import check_choicescarf
from fp.battle.inference import get_damage_dealt
from fp.battle.inference import update_dataset_possibilities
from fp.battle.inference import check_heavydutyboots


logger = logging.getLogger(__name__)

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


def remove_volatile(pkmn, volatile):
    pkmn.volatile_statuses = [vs for vs in pkmn.volatile_statuses if vs != volatile]


def unlikely_to_have_choice_item(move_name):
    try:
        move_dict = all_move_json[move_name]
    except KeyError:
        return False

    if (
        constants.BOOSTS in move_dict
        and move_dict[constants.CATEGORY] == constants.MoveCategory.STATUS
    ):
        return True
    elif move_name in ["substitute", "roost", "recover"]:
        return True

    return False


def request(battle, msg: RequestMessage):
    battle_request = msg.request
    logger.debug("Received battle request from server: {}".format(battle_request))
    battle.rqid = battle_request.rqid
    battle.force_switch = bool(battle_request.force_switch)
    battle.wait = battle_request.wait
    battle.request = battle_request


def inactive(battle, msg: Inactive):
    regex_string = r"(\d+) sec this turn"
    if msg.message.startswith(constants.TIME_LEFT):
        capture = re.search(regex_string, msg.message)
        try:
            time_left = int(capture.group(1))
            battle.time_remaining = time_left
            logger.debug("Time left: {}".format(time_left))
        except ValueError:
            logger.warning("{} is not a valid int".format(capture.group(1)))
        except AttributeError:
            logger.warning(
                "'{}' does not match the regex '{}'".format(msg.message, regex_string)
            )


def inactiveoff(battle, _: InactiveOff):
    battle.time_remaining = None


def user_just_switched_into_zoroark(battle, is_drag):
    """
    some truly heinous shit going on here, can we ban this fucker?

    Two scenarios we can detect we are a zoroark:
      1. We switched and the last action we selected starts with `switch zoroark` (to account for both zoroarks)
      2. We were dragged (circle throw, etc) AND the active pkmn on the next turn is zoroark

    is it not sound to check for "we switched or dragged and the request JSON has zoroark as active?"
    No. If we switched into zoroark and then got circle-thrown out then the request JSON would not have
        zoroark as active but our switch needs to have been into zoroark.

    This doesn't need to deal with the first-turn switch-in of the user's Zoroark because the first-turn is
    instantiated from the request
    """

    return (
        # Scenario 1
        (
            not is_drag
            and battle.user.last_selected_move.move.startswith("switch zoroark")
        )
        # Scenario 2
        or (
            is_drag
            and battle.request is not None
            and battle.request.side.pokemon[0].details.species.startswith("Zoroark")
            and battle.request.side.pokemon[0].active
        )
    )


def switch_or_drag(battle, msg: Switch):
    side = battle.side(msg.pokemon.side)
    other_side = battle.other_side(side)
    if side is battle.opponent:
        side_name = "opponent"
        logger.info("Opponent has switched - clearing the last used move")
    else:
        side_name = "user"
        side.side_conditions[constants.TOXIC_COUNT] = 0

    kwargs = msg.kwargs
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

        if kwargs.is_from("batonpass"):
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
        elif kwargs.is_from("shedtail"):
            side.shed_tailing = False

            if constants.SUBSTITUTE in side.active.volatile_statuses:
                logger.info("Shed tailing, preserving substitute")
                switch_keep_volatiles.append(constants.SUBSTITUTE)

        # gen5 rest turns are reset upon switching
        if (
            battle.gen.rest_turns_reset_on_switch
            and side.active.status == constants.Status.SLEEP
        ):
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
        if (
            battle.gen.tracks_consecutive_sleep_talks
            and side.active.status == constants.Status.SLEEP
        ):
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
            battle.gen.regenerator_heals_on_switch_out
            and side.active.hp > 0
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

    if side_name == "user" and user_just_switched_into_zoroark(battle, msg.is_drag):
        logger.info(
            "User switched/dragged into Zoroark - replacing the message pokemon"
        )
        logger.info("Starting message: {}".format(msg))
        request_zoroark = [
            p
            for p in battle.request.side.pokemon
            if p.details.species.startswith("Zoroark")
        ]
        assert len(request_zoroark) == 1
        request_zoroark = request_zoroark[0]
        msg = replace(
            msg, pokemon=request_zoroark.ident, details=request_zoroark.details
        )
        logger.info("New message: {}".format(msg))

    # check if the pokemon exists in the reserves
    # if it does not, then the newly-created pokemon is used (for formats without team preview)
    nickname = msg.pokemon.nickname
    temp_pkmn = Pokemon.from_details(msg.details, nickname=nickname)
    pkmn = side.find_pokemon_in_reserves(temp_pkmn.name)

    if pkmn is None:
        pkmn = Pokemon.from_details(msg.details, nickname=nickname)

        battle.mode.add_revealed_pokemon(battle, pkmn)

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

    condition = msg.condition
    pkmn.revealed = True
    if side is battle.opponent:
        new_hp_percentage = condition.fraction
        if (
            pkmn.hp != new_hp_percentage * pkmn.max_hp
            and "regenerator"
            in [
                normalize_name(a)
                for a in pokedex[pkmn.name][constants.ABILITIES].values()
            ]
            and pkmn.ability is None
            and battle.gen.regenerator_heals_on_switch_out
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
        pkmn.hp = condition.hp
        pkmn.max_hp = condition.max_hp

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
        battle.user.re_initialize_active_pokemon_from_request(battle.request)

    for ability in ABILITIES_REVEALED_ON_SWITCH_IN:
        if not battle.gen.pressure_revealed_on_switch_in and ability == "pressure":
            # gen3 pressure is not revealed on switch-in
            continue

        if (
            (
                ability == "sandstream"
                and battle.weather
                in [
                    constants.Weather.SAND,
                    constants.Weather.HEAVY_RAIN,
                    constants.Weather.DESOLATE_LAND,
                ]
            )
            or (
                ability == "drought"
                and battle.weather
                in [
                    constants.Weather.SUN,
                    constants.Weather.HEAVY_RAIN,
                    constants.Weather.DESOLATE_LAND,
                ]
            )
            or (
                ability == "drizzle"
                and battle.weather
                in [
                    constants.Weather.RAIN,
                    constants.Weather.HEAVY_RAIN,
                    constants.Weather.DESOLATE_LAND,
                ]
            )
            or (
                ability == "snowwarning"
                and battle.weather
                in [
                    constants.Weather.HAIL,
                    constants.Weather.SNOW,
                    constants.Weather.HEAVY_RAIN,
                    constants.Weather.DESOLATE_LAND,
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


def sethp(battle, msg: SetHp):
    # |-sethp|p2a: Jellicent|317/403|[from] move: Pain Split|[silent]
    condition = msg.condition
    if battle.is_opponent_side(msg.pokemon.side):
        pkmn = battle.opponent.active
        pkmn.hp = int(pkmn.max_hp * condition.fraction)
    else:
        pkmn = battle.user.active
        pkmn.hp = condition.hp
        pkmn.max_hp = condition.max_hp


def heal(battle, msg: Heal):
    _heal_or_damage(battle, msg)


def damage(battle, msg: Damage):
    _heal_or_damage(battle, msg)


def _heal_or_damage(battle, msg: Heal | Damage):
    condition = msg.condition
    kwargs = msg.kwargs
    if battle.is_opponent_side(msg.pokemon.side):
        side = battle.opponent
        other_side = battle.user
        pkmn = battle.opponent.active
        if kwargs.is_from("revivalblessing", EffectKind.MOVE):
            pkmn = side.find_reserve_pokemon_by_nickname(msg.pokemon.nickname)

        # opponent hp is given as a percentage
        if condition.fainted:
            pkmn.hp = 0
        else:
            pkmn.hp = pkmn.max_hp * condition.fraction

    else:
        side = battle.user
        other_side = battle.opponent
        pkmn = battle.user.active
        if kwargs.is_from("revivalblessing", EffectKind.MOVE):
            pkmn = side.find_reserve_pokemon_by_nickname(msg.pokemon.nickname)
        if condition.fainted:
            pkmn.hp = 0
        else:
            pkmn.hp = condition.hp
            pkmn.max_hp = condition.max_hp

    # increase the amount of turns toxic has been active
    if condition.status == constants.Status.TOXIC and kwargs.is_from(
        constants.Status.POISON
    ):
        side.side_conditions[constants.TOXIC_COUNT] += 1

    if (
        kwargs.from_ is not None
        and kwargs.from_.kind == EffectKind.ITEM
        and kwargs.of is not None
        and kwargs.of.side == other_side.name
    ):
        item = kwargs.from_.id
        logger.info("Setting {}'s item to: {}".format(other_side.active.name, item))
        other_side.active.item = item

    if kwargs.is_from("healingwish"):
        logger.info(
            "{} was healed from healing wish, setting side condition to 0".format(
                side.active.name
            )
        )
        side.side_conditions[constants.HEALING_WISH] = 0

    # set the ability for the other side (the side not taking damage, '-damage' only)
    if (
        kwargs.from_ is not None
        and kwargs.from_.kind == EffectKind.ABILITY
        and kwargs.of is not None
        and kwargs.of.side == other_side.name
        and isinstance(msg, Damage)
    ):
        ability = kwargs.from_.id
        logger.info(
            "Setting {}'s ability to: {}".format(other_side.active.name, ability)
        )
        other_side.active.ability = ability

    # set the ability of the side (the side being healed, '-heal' only)
    if (
        kwargs.from_ is not None
        and kwargs.from_.kind == EffectKind.ABILITY
        and kwargs.of is not None
        and kwargs.of.side == other_side.name
        and isinstance(msg, Heal)
    ):
        ability = kwargs.from_.id
        logger.info("Setting {}'s ability to: {}".format(pkmn.name, ability))
        pkmn.ability = ability

    # give that pokemon an item if this string specifies one
    if (
        kwargs.from_ is not None
        and kwargs.from_.kind == EffectKind.ITEM
        and kwargs.of is None
        and pkmn.item is not None
    ):
        item = kwargs.from_.id
        logger.info("Setting {}'s item to: {}".format(pkmn.name, item))
        pkmn.item = item

    # gen 1 if you are trapping the opponent and hit yourself in confusion, the opponent is released
    if (
        battle.gen.partial_trapping_mechanics
        and kwargs.is_from(constants.CONFUSION)
        and (
            constants.PARTIALLY_TRAPPED in other_side.active.volatile_statuses
            or other_side.active.volatile_status_durations[constants.PARTIALLY_TRAPPED]
            > 0
        )
    ):
        logger.info(
            f"{pkmn.name} hit itself in confusion, releasing partially trapped volatile on {other_side.active.name}"
        )
        remove_volatile(other_side.active, constants.PARTIALLY_TRAPPED)
        other_side.active.volatile_status_durations[constants.PARTIALLY_TRAPPED] = 0


def faint(battle, msg: Faint):
    side = battle.side(msg.pokemon.side)
    side.active.hp = 0


def fail(battle, msg: Fail):
    # |-fail|p2a: Dragapult|unboost|[from] ability: Clear Body|[of] p2a: Dragapult
    kwargs = msg.kwargs
    if (
        kwargs.from_ is not None
        and kwargs.from_.kind == EffectKind.ABILITY
        and kwargs.of is not None
    ):
        ability_side = battle.side(kwargs.of.side)
        ability = kwargs.from_.id
        logger.info(
            "Setting {}'s ability to: {}".format(ability_side.active.name, ability)
        )
        ability_side.active.ability = ability


def move(battle, msg: Move):
    side = battle.side(msg.user.side)
    pkmn = side.active
    opposing_pkmn = battle.other_side(side).active

    move_name = msg.move_id
    kwargs = msg.kwargs
    from_sleeptalk = kwargs.is_from("sleeptalk")

    zoroark_from_reserves = side.find_pokemon_in_reserves(
        "zoroark"
    ) or side.find_pokemon_in_reserves("zoroarkhisui")

    pkmn = battle.mode.check_zoroark_from_move(
        battle, side, pkmn, msg, zoroark_from_reserves
    )

    if from_sleeptalk and battle.gen.tracks_consecutive_sleep_talks:
        pkmn.gen_3_consecutive_sleep_talks += 1
        logger.info(
            "{} gen3 consecutive sleep talks: {}".format(
                pkmn.name, pkmn.gen_3_consecutive_sleep_talks
            )
        )
    elif move_name != "sleeptalk":
        pkmn.gen_3_consecutive_sleep_talks = 0

    # in gen1, if you successfully hit with a partially trapping move, the volatile is applied here
    # cannot use the 'cant' message because a slow wrap still needs the volatile/duration applied
    # e.g. |move|p1a: Dragonite|Wrap|p2a: Tauros|
    # does not activate on a miss: |move|p1a: Dragonite|Wrap|p2a: Tauros|[miss]
    if (
        battle.gen.partial_trapping_mechanics
        and all_move_json.get(move_name, {}).get(constants.VOLATILE_STATUS)
        == constants.PARTIALLY_TRAPPED
        and "miss" not in kwargs
    ):
        opposing_pkmn.volatile_status_durations[constants.PARTIALLY_TRAPPED] += 1
        if constants.PARTIALLY_TRAPPED not in opposing_pkmn.volatile_statuses:
            opposing_pkmn.volatile_statuses.append(constants.PARTIALLY_TRAPPED)

        logger.info(
            f"{pkmn.name} successfully used Wrap, incrementing partially trapped volatile on "
            f"{opposing_pkmn.name} to {opposing_pkmn.volatile_status_durations[constants.PARTIALLY_TRAPPED]}"
        )

    # in gen1 if you just moved, you are released from partially trapped
    if battle.gen.partial_trapping_mechanics and (
        pkmn.volatile_status_durations[constants.PARTIALLY_TRAPPED] > 0
        or constants.PARTIALLY_TRAPPED in pkmn.volatile_statuses
    ):
        logger.info(f"{pkmn.name} used a move, removing partially trapped volatile")
        remove_volatile(pkmn, constants.PARTIALLY_TRAPPED)
        pkmn.volatile_status_durations[constants.PARTIALLY_TRAPPED] = 0

    # gen1 stat modification glitches.
    # swordsdance and agility nullify the effects of burn and paralysis respectively
    # This is implemented by setting a custom volatile
    if battle.gen.stat_modification_glitches:
        if (
            move_name == "swordsdance" or move_name == "meditate"
        ) and pkmn.status == constants.Status.BURN:
            logger.info(
                "{} used swordsdance with burn, nullifying the effects of burn".format(
                    pkmn.name
                )
            )
            pkmn.volatile_statuses.append("gen1burnnullify")
        elif move_name == "agility" and pkmn.status == constants.Status.PARALYZED:
            logger.info(
                "{} used agility while paralyzed, nullifying the effects of paralysis".format(
                    pkmn.name
                )
            )
            pkmn.volatile_statuses.append("gen1paralysisnullify")

    if from_sleeptalk:
        move_object = pkmn.get_move(move_name)
        if move_object is None:
            pkmn.add_move(move_name)
            logger.info(
                "Added unrevealed {} to {}'s moves because it was called by sleeptalk".format(
                    move_name, pkmn.name
                )
            )
        return

    elif kwargs.from_ is not None and not kwargs.is_from(constants.LOCKED_MOVE):
        if kwargs.from_.kind == EffectKind.ABILITY:
            ability = kwargs.from_.id
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
        and not battle.gen.taunt_duration_increments_end_of_turn
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
        side is battle.opponent
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
        if mv[constants.CATEGORY] != constants.MoveCategory.STATUS:
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
        if (
            all_move_json[move_name][constants.CATEGORY]
            == constants.MoveCategory.STATUS
        ):
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
        if not from_sleeptalk:
            side.last_used_move = LastUsedMove(
                pokemon_name=pkmn.name, move=move_name, turn=battle.turn
            )
    except KeyError:
        category = None
        if not from_sleeptalk:
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
    if move_name == constants.WISH and "still" not in kwargs:
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


def setboost(battle, msg: SetBoost):
    pkmn = battle.side(msg.pokemon.side).active
    stat = constants.STAT_ABBREVIATION_LOOKUPS[msg.stat]
    amount = msg.amount

    pkmn.boosts[stat] = amount


def boost(battle, msg: Boost):
    pkmn = battle.side(msg.pokemon.side).active
    stat = constants.STAT_ABBREVIATION_LOOKUPS[msg.stat]
    amount = msg.amount

    pkmn.boosts[stat] = min(pkmn.boosts[stat] + amount, constants.MAX_BOOSTS)
    logger.info(
        "{}'s {} was boosted by {} to {}".format(
            pkmn.name, stat, amount, pkmn.boosts[stat]
        )
    )


def unboost(battle, msg: Unboost):
    pkmn = battle.side(msg.pokemon.side).active
    stat = constants.STAT_ABBREVIATION_LOOKUPS[msg.stat]
    amount = msg.amount

    pkmn.boosts[stat] = max(pkmn.boosts[stat] - amount, -1 * constants.MAX_BOOSTS)
    logger.info(
        "{}'s {} was unboosted by {} to {}".format(
            pkmn.name, stat, amount, pkmn.boosts[stat]
        )
    )


def status(battle, msg: Status):
    side = battle.side(msg.pokemon.side)
    other_side = battle.other_side(side)
    pkmn = side.active

    kwargs = msg.kwargs
    if kwargs.from_ is not None and kwargs.from_.kind == EffectKind.ITEM:
        pkmn.item = kwargs.from_.id

    if msg.status == constants.Status.SLEEP:
        if kwargs.is_from("rest", EffectKind.MOVE):
            logger.info("Setting rest_turns to 3 for {}".format(pkmn.name))
            pkmn.rest_turns = 3
        else:
            logger.info("Setting sleep_turns to 0 for {}".format(pkmn.name))
            pkmn.sleep_turns = 0

    status_name = msg.status
    logger.info("{} got status: {}".format(pkmn.name, status_name))
    pkmn.status = status_name

    if status_name is not None:
        logger.info(
            "No longer guessing lumberry because {} got status {}".format(
                pkmn.name, status_name
            )
        )
        pkmn.impossible_items.add("lumberry")

    # |-status|p1a: Caterpie|brn|[from] ability: Flame Body|[of] p2a: Caterpie
    if (
        kwargs.from_ is not None
        and kwargs.from_.kind == EffectKind.ABILITY
        and kwargs.of is not None
        and kwargs.of.side == other_side.name
    ):
        ability = kwargs.from_.id
        logger.info("Setting {}'s ability to: {}".format(pkmn.name, ability))
        other_side.active.ability = ability


def activate(battle, msg: Activate):
    side = battle.side(msg.pokemon.side)
    pkmn = side.active
    other_pkmn = battle.other_side(side).active

    effect = msg.effect
    kwargs = msg.kwargs

    if effect.id == constants.SUBSTITUTE and "damage" in kwargs:
        logger.info(
            "{}'s substitute took damage, setting substitute_hit to True".format(
                pkmn.name
            )
        )
        pkmn.substitute_hit = True

    # |-activate|p2a: Gengar|move: Poltergeist|Leftovers
    if effect.kind == EffectKind.MOVE and effect.id == "poltergeist":
        item = normalize_name(msg.args[0])
        logger.info("{} has the item {}".format(pkmn.name, item))
        pkmn.item = item

    if effect.kind == EffectKind.ABILITY:
        ability = effect.id
        logger.info("Setting {}'s ability to {}".format(pkmn.name, ability))
        pkmn.ability = ability

        if ability in ["mummy", "lingeringaroma"]:
            # |-activate|p2a: Cofagrigus|ability: Mummy|p1a: Garchomp|[ability] Rough Skin
            original_ability = normalize_name(kwargs.get("ability"))
            other_pkmn.ability = ability
            other_pkmn.original_ability = original_ability
            logger.info(
                "{}'s ability was changed from {} to {}".format(
                    other_pkmn.name, original_ability, ability
                )
            )

    elif effect.kind == EffectKind.ITEM and "consumed" not in kwargs:
        item = effect.id
        logger.info("Setting {}'s item to {}".format(pkmn.name, item))
        pkmn.item = item

    if effect.kind == EffectKind.MOVE:
        move_name = effect.id
        if (
            move_name in all_move_json
            and all_move_json[move_name].get("volatileStatus")
            == constants.PARTIALLY_TRAPPED
        ):
            logger.info("{} was partially trapped by {}".format(pkmn.name, move_name))
            pkmn.volatile_statuses.append(constants.PARTIALLY_TRAPPED)


def anim(battle, msg: Anim):
    pkmn = battle.side(msg.pokemon.side).active

    anim_name = normalize_name(msg.move)
    if anim_name in pkmn.volatile_statuses:
        logger.info(
            "Removing volatile status {} from {} because of -anim".format(
                anim_name, pkmn.name
            )
        )
        remove_volatile(pkmn, anim_name)


def prepare(battle, msg: Prepare):
    pkmn = battle.side(msg.pokemon.side).active

    being_prepared = normalize_name(msg.move)
    if being_prepared in pkmn.volatile_statuses:
        logger.warning(
            "{} already has the volatile status {}".format(pkmn.name, being_prepared)
        )
    else:
        logger.info(
            "Adding the volatile status {} to {}".format(being_prepared, pkmn.name)
        )
        pkmn.volatile_statuses.append(being_prepared)


def terastallize(battle, msg: Terastallize):
    pkmn = battle.side(msg.pokemon.side).active

    pkmn.terastallized = True
    pkmn.tera_type = normalize_name(msg.tera_type)
    logger.info(
        "{} terastallized. Tera type: {}, Original types: {}".format(
            pkmn.name, pkmn.tera_type, pkmn.types
        )
    )


def start_volatile_status(battle, msg: Start):
    side = battle.side(msg.pokemon.side)
    pkmn = side.active

    effect = msg.effect
    kwargs = msg.kwargs
    volatile_status = effect.id

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
        if kwargs.is_from("shedtail", EffectKind.MOVE):
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
        if "fatigue" in kwargs:
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

    if effect.kind == EffectKind.ABILITY:
        pkmn.ability = volatile_status

    # |-start|p1a: Greninja|typechange|Water|[from] ability: Protean
    if (
        kwargs.from_ is not None
        and kwargs.from_.kind == EffectKind.ABILITY
        and kwargs.of is None
    ):
        pkmn.ability = kwargs.from_.id

    if volatile_status == constants.TYPECHANGE:
        # |-start|p1a: Starmie|typechange|[from] move: Reflect Type|[of] p2a: Dragapult
        if kwargs.is_from("reflecttype", EffectKind.MOVE) and kwargs.of is not None:
            new_types = deepcopy(battle.side(kwargs.of.side).active.types)
        else:
            # |-start|p1a: Greninja|typechange|Water|[from] ability: Protean
            new_types = [normalize_name(t) for t in msg.args[0].split("/")]

        logger.info("Setting {}'s types to {}".format(pkmn.name, new_types))
        pkmn.types = new_types


def end_volatile_status(battle, msg: End):
    pkmn = battle.side(msg.pokemon.side).active

    kwargs = msg.kwargs
    volatile_status = msg.effect.id
    if volatile_status == constants.SUBSTITUTE:
        logger.info("Substitute ended for {}".format(pkmn.name))
        pkmn.substitute_hit = False

    if volatile_status == "protosynthesis" or volatile_status == "quarkdrive":
        for vs in pkmn.volatile_statuses:
            if vs.startswith(volatile_status):
                logger.info("Removing {} from {}".format(vs, pkmn.name))
                pkmn.volatile_statuses.remove(vs)
    elif constants.PARTIALLY_TRAPPED in kwargs:
        remove_volatile(pkmn, constants.PARTIALLY_TRAPPED)
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


def curestatus(battle, msg: CureStatus):
    side = battle.side(msg.pokemon.side)

    ident = msg.pokemon
    pkmn_name = ident.nickname
    pkmn_by_nickname = next(
        (p for p in [side.active] + side.reserve if p.nickname == ident.nickname),
        None,
    )

    if ident.is_active or normalize_name(pkmn_name) == side.active.name:
        pkmn = side.active
    elif pkmn_by_nickname is not None:
        pkmn = pkmn_by_nickname
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
    if pkmn.status == constants.Status.SLEEP:
        logger.info(
            "{} is being cured of sleep, setting rest_turns & sleep_turns to 0".format(
                pkmn.name
            )
        )
        pkmn.rest_turns = 0
        pkmn.sleep_turns = 0
    elif pkmn.status == constants.Status.TOXIC:
        side.side_conditions[constants.TOXIC_COUNT] = 0

    pkmn.status = None


def cureteam(battle, msg: CureTeam):
    """Cure every pokemon on the opponent's team of it's status"""
    side = battle.side(msg.pokemon.side)

    side.active.status = None
    for pkmn in filter(lambda p: isinstance(p, Pokemon), side.reserve):
        pkmn.status = None
        pkmn.rest_turns = 0
        pkmn.sleep_turns = 0


def weather(battle, msg: Weather):
    # The weather message on its own `|-weather|RainDance` does not contain information about
    #  which side caused it unless it was from an ability
    #  `|-weather|RainDance|[from] ability: Drizzle|[of] p2a: Politoed`
    #
    # If that information is present, we can infer certain things about the Side
    kwargs = msg.kwargs
    side = None
    side_name = None
    if kwargs.of is not None:
        if kwargs.of.side == battle.opponent.name:
            side = battle.opponent
            side_name = "opponent"
        else:
            side = battle.user
            side_name = "user"

    weather_name = msg.weather.id
    logger.info("Weather {} is active".format(weather_name))
    battle.weather = weather_name

    if weather_name == "none":
        logger.info("Resetting weather source to None")
        battle.weather_source = None
    elif side is not None and side_name is not None:
        battle.weather_source = f"{side_name}:{side.active.name}"

    if "upkeep" in kwargs and battle.weather_turns_remaining > 0:
        battle.weather_turns_remaining -= 1
    elif "upkeep" in kwargs:
        logger.debug("Weather {} permanently active".format(weather_name))
    elif (
        battle.gen.ability_weather_is_permanent
        and kwargs.from_ is not None
        and kwargs.from_.kind == EffectKind.ABILITY
    ):
        battle.weather_turns_remaining = -1
    elif (
        side is not None
        and weather_name == constants.Weather.SUN
        and side.active.item == "heatrock"
    ):
        logger.info("{} has heatrock, assuming 8 turns of sun".format(side.active.name))
        battle.weather_turns_remaining = 8
    elif (
        side is not None
        and weather_name == constants.Weather.RAIN
        and side.active.item == "damprock"
    ):
        logger.info(
            "{} has damprock, assuming 8 turns of rain".format(side.active.name)
        )
        battle.weather_turns_remaining = 8
    elif (
        side is not None
        and weather_name == constants.Weather.SAND
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
                if weather_name == constants.Weather.SUN:
                    item = "heatrock"
                elif weather_name == constants.Weather.RAIN:
                    item = "damprock"
                elif weather_name == constants.Weather.SAND:
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

    if (
        side is not None
        and kwargs.from_ is not None
        and kwargs.from_.kind == EffectKind.ABILITY
    ):
        ability = kwargs.from_.id
        logger.info("Setting {} ability to {}".format(side.active.name, ability))
        side.active.ability = ability


def fieldstart(battle, msg: FieldStart):
    """Set the battle's field condition"""
    field_name = msg.effect.id

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


def fieldend(battle, msg: FieldEnd):
    """Remove the battle's field condition"""
    field_name = msg.effect.id

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


def sidestart(battle, msg: SideStart):
    # Inconsistencies in the protocol mean parse after the `:` to get the side condition
    # |-sidestart|p2: Name|Reflect
    # |-sidestart|p2: Name|move: Light Screen
    # |-sidestart|p2: Name|Spikes
    # |-sidestart|p1: Name|move: Stealth Rock
    #
    # Some side conditions have an explicit duration such as lightscreen, reflect, etc.
    # Others are incremented by 1

    condition = msg.effect.id
    side = battle.side(msg.side)

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


def sideend(battle, msg: SideEnd):
    """Remove a side effect such as stealth rock or sticky web"""
    condition = msg.effect.id

    if battle.is_opponent_side(msg.side):
        logger.info("Side condition {} ending for opponent".format(condition))
        battle.opponent.side_conditions[condition] = 0
    else:
        logger.info("Side condition {} ending for user".format(condition))
        battle.user.side_conditions[condition] = 0


def swapsideconditions(battle, _: SwapSideConditions):
    user_sc = battle.user.side_conditions
    opponent_sc = battle.opponent.side_conditions
    for side_condition in constants.COURT_CHANGE_SWAPS:
        user_sc[side_condition], opponent_sc[side_condition] = (
            opponent_sc[side_condition],
            user_sc[side_condition],
        )


def set_item(battle, msg: Item):
    """Set the opponent's item"""
    kwargs = msg.kwargs

    # frisk reveals the item of the pokemon opposing the frisker
    # gen4/5 do not identify the pokemon holding the item:
    # |-item||Life Orb|[from] ability: Frisk|[of] p2a: Furret
    if kwargs.is_from("frisk", EffectKind.ABILITY) and kwargs.of is not None:
        side = battle.other_side(battle.side(kwargs.of.side))
    else:
        side = battle.side(msg.pokemon.side)
    other_side = battle.other_side(side)

    item = normalize_name(msg.item)

    if (
        kwargs.from_ is not None
        and side.active.removed_item is None
        and item != side.active.item
        and side.active.item not in [constants.UNKNOWN_ITEM]
    ):
        logger.info("{}'s removed item is {}".format(side.active.name, item))
        side.active.removed_item = side.active.item

    # when the bot gets tricked we set the opponent's removed item
    if (
        kwargs.is_from("trick", EffectKind.MOVE)
        and side is battle.user
        and other_side.active.removed_item is None
    ):
        logger.info("Setting opponent's removed_item to {}".format(item))
        other_side.active.removed_item = item

    logger.info("Setting {}'s item to {}".format(side.active.name, item))
    side.active.item = item


def remove_item(battle, msg: EndItem):
    """Remove the opponent's item"""
    side = battle.side(msg.pokemon.side)

    item = normalize_name(msg.item)

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

    if msg.kwargs.is_from("knockoff"):
        logger.info("Knockoff removed {}'s item".format(side.active.name))
        side.active.knocked_off = True


def immune(battle, msg: Immune):
    side = battle.side(msg.pokemon.side)
    pkmn = side.active

    kwargs = msg.kwargs
    if kwargs.from_ is not None and kwargs.from_.kind == EffectKind.ABILITY:
        ability = kwargs.from_.id
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
        side is battle.opponent
        and not side.active.name.startswith("zoroark")
        and battle.user.last_used_move.move in all_move_json
        and all_move_json[battle.user.last_used_move.move][constants.CATEGORY]
        != constants.MoveCategory.STATUS
        and type_effectiveness_modifier(
            all_move_json[battle.user.last_used_move.move][constants.TYPE],
            side.active.types,
        )
        != 0
        and kwargs.from_ is None
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
        battle.mode.check_zoroark_from_immune(battle, side, pkmn, zoroark_from_reserves)


def update_ability(battle, msg: Ability):
    side = battle.side(msg.pokemon.side)
    other_side = battle.other_side(side)

    ability = normalize_name(msg.ability)
    kwargs = msg.kwargs

    if kwargs.from_ is not None and kwargs.from_.kind == EffectKind.ABILITY:
        # |-ability|p2a: Porygon2|Levitate|Trace|[from] ability: Trace|[of] p1a: Claydol
        original_ability = normalize_name(msg.args[0])
        logger.info(
            "Setting {}'s original ability to {}".format(
                side.active.name, original_ability
            )
        )
        side.active.original_ability = original_ability

        if (
            kwargs.from_.id == "trace"
            and kwargs.of is not None
            and kwargs.of.side == other_side.name
        ):
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


def illusion_end(battle, msg: Replace):
    side = battle.side(msg.pokemon.side)

    if (
        side is battle.opponent
        and side.active.name not in ["zoroark", "zoroarkhisui"]
        and side.active.zoroark_disguised_as is None
    ):
        logger.info("Illusion ending for opponent")
        hp_percent = float(side.active.hp) / side.active.max_hp
        previous_boosts = side.active.boosts
        previous_status = side.active.status
        previous_item = side.active.item

        zoroark_from_switch_string = Pokemon.from_details(msg.details)
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


def form_change(battle, msg: FormeChange):
    side = battle.side(msg.pokemon.side)

    logger.info("Form Change: {} -> {}".format(side.active.name, msg.details.species))
    side.active.forme_change(msg.details.species)
    if side is battle.user:
        side.re_initialize_active_pokemon_from_request(battle.request)


def zpower(battle, msg: ZPower):
    side = battle.side(msg.pokemon.side)

    logger.info("{} Used a Z-Move, setting item to None".format(side.active.name))
    side.active.item = None


def clearnegativeboost(battle, msg: ClearNegativeBoost):
    pkmn = battle.side(msg.pokemon.side).active

    for stat, value in pkmn.boosts.items():
        if value < 0:
            logger.info("Setting {}'s {} boost to 0".format(pkmn.name, stat))
            pkmn.boosts[stat] = 0


def clearboost(battle, msg: ClearBoost):
    pkmn = battle.side(msg.pokemon.side).active

    for stat, value in pkmn.boosts.items():
        logger.info("Setting {}'s {} boost to 0".format(pkmn.name, stat))
        pkmn.boosts[stat] = 0


def clearallboost(battle, _: ClearAllBoost):
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


def singleturn(battle, msg: SingleTurn):
    side = battle.side(msg.pokemon.side)

    move_name = msg.effect.id
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


def mustrecharge(battle, msg: MustRecharge):
    # Bot's side does not get mustrecharge because the request JSON
    # will contain the only available `recharge` move
    if battle.is_opponent_side(msg.pokemon.side):
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


def cant(battle, msg: Cant):
    side = battle.side(msg.pokemon.side)
    other_side = battle.other_side(side)
    opponent = side is battle.opponent

    side.last_used_move = LastUsedMove(
        pokemon_name=side.active.name,
        move=side.last_used_move.move,
        turn=battle.turn,
    )

    reason = msg.reason

    # |cant|p1a: Slaking|ability: Truant
    if reason.kind == EffectKind.ABILITY and reason.id == "truant":
        logger.info(
            "{} got 'cant' from truant, removing truant volatile".format(
                side.active.name
            )
        )
        remove_volatile(side.active, "truant")

    # |cant|p2a: Tauros|recharge
    if reason.id == "recharge":
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

    # the move that could not be used belongs to the pokemon that could not use it
    # |cant|p2a: Politoed|move: Taunt|Toxic
    if (
        reason.kind == EffectKind.MOVE
        and msg.move is not None
        and normalize_name(msg.move) in all_move_json
    ):
        move_name = normalize_name(msg.move)
        move_object = side.active.get_move(move_name)
        if move_object is None:
            side.active.add_move(move_name)
            logger.info(
                "Adding {} to {}'s moves from 'cant'".format(
                    move_name, side.active.name
                )
            )

    if reason.id == constants.Status.SLEEP:
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

    # gen1 if you get `cant` from full paralysis while the opponent is partiallytrapped, they are freed
    if (
        battle.gen.partial_trapping_mechanics
        and reason.id == constants.Status.PARALYZED
        and (
            constants.PARTIALLY_TRAPPED in other_side.active.volatile_statuses
            or other_side.active.volatile_status_durations[constants.PARTIALLY_TRAPPED]
            > 0
        )
    ):
        logger.info(
            f"{side.active.name} got 'cant' while target {other_side.active.name} was partially trapped, "
            f"removing partiallytrapped volatile from {other_side.active.name}"
        )
        remove_volatile(other_side.active, constants.PARTIALLY_TRAPPED)
        other_side.active.volatile_status_durations[constants.PARTIALLY_TRAPPED] = 0


def upkeep(battle, _: Upkeep):
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
            and battle.gen.taunt_duration_increments_end_of_turn
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
            battle.gen.tracks_consecutive_sleep_talks
            and pkmn.status == constants.Status.SLEEP
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


def mega(battle, msg: Mega):
    side = battle.side(msg.pokemon.side)

    side.active.is_mega = True
    forced_mega_ability = normalize_name(
        pokedex[side.active.name][constants.ABILITIES]["0"]
    )
    side.active.ability = forced_mega_ability
    logger.info(
        "Mega-Pokemon: {} with ability {}".format(side.active.name, forced_mega_ability)
    )


def transform(battle, msg: Transform):
    side = battle.side(msg.pokemon.side)
    other_side = battle.other_side(side)

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

    kwargs = msg.kwargs
    if kwargs.from_ is not None and kwargs.from_.kind == EffectKind.ABILITY:
        side.active.original_ability = kwargs.from_.id
    elif side.active.ability is not None:
        side.active.original_ability = side.active.ability

    side.active.ability = deepcopy(transformed_into.ability)


def turn(battle, msg: Turn):
    battle.turn = msg.number
    logger.info("")
    logger.info("Turn: {}".format(battle.turn))


def noinit(battle, msg: NoInit):
    # |noinit|rename|NEWID|TITLE
    if msg.reason == "rename":
        battle.battle_tag = msg.args[0]
        logger.info("Renamed battle to {}".format(battle.battle_tag))


def update_battle(battle: Battle, msg: str):
    msg_lines = msg.split("\n")
    for line in msg_lines:
        parsed = parse_line(line)
        if parsed is None:
            continue

        if isinstance(parsed, RequestMessage):
            # an empty request means there is nothing to decide
            if parsed.request is None:
                process_battle_updates(battle)
                return False

            request(battle, parsed)
            process_battle_updates(battle)
            return not battle.wait
        else:
            battle.msg_list.append(line)

    return False


MESSAGE_HANDLERS = {
    Switch: switch_or_drag,
    Faint: faint,
    Fail: fail,
    Heal: heal,
    Damage: damage,
    SetHp: sethp,
    Move: move,
    SetBoost: setboost,
    Boost: boost,
    Unboost: unboost,
    Status: status,
    Activate: activate,
    Anim: anim,
    Prepare: prepare,
    Start: start_volatile_status,
    End: end_volatile_status,
    CureStatus: curestatus,
    CureTeam: cureteam,
    Weather: weather,
    FieldStart: fieldstart,
    FieldEnd: fieldend,
    SideStart: sidestart,
    SideEnd: sideend,
    SwapSideConditions: swapsideconditions,
    Item: set_item,
    EndItem: remove_item,
    Immune: immune,
    Ability: update_ability,
    FormeChange: form_change,
    Replace: illusion_end,
    Transform: transform,
    Mega: mega,
    Terastallize: terastallize,
    ZPower: zpower,
    ClearNegativeBoost: clearnegativeboost,
    ClearBoost: clearboost,
    ClearAllBoost: clearallboost,
    SingleTurn: singleturn,
    MustRecharge: mustrecharge,
    Upkeep: upkeep,
    Cant: cant,
    Inactive: inactive,
    InactiveOff: inactiveoff,
    Turn: turn,
    NoInit: noinit,
}


def apply_message(battle: Battle, msg: Message):
    handler = MESSAGE_HANDLERS.get(type(msg))
    if handler is not None:
        handler(battle, msg)


def process_battle_updates(battle: Battle):
    messages = parse_lines(battle.msg_list)
    check_speed_ranges(battle, messages)
    for i, msg in enumerate(messages):
        apply_message(battle, msg)

        if isinstance(msg, Move) and battle.is_opponent_side(msg.user.side):
            if msg.move_id == constants.HIDDEN_POWER:
                check_opponent_hiddenpower(battle, messages[i + 1])
            check_choicescarf(battle, messages)
            damage_dealt = get_damage_dealt(battle, msg, messages[i + 1 :])
            if damage_dealt:
                update_dataset_possibilities(battle, damage_dealt, "damage_dealt")

        elif isinstance(msg, Move):
            damage_dealt = get_damage_dealt(battle, msg, messages[i + 1 :])
            if damage_dealt:
                update_dataset_possibilities(battle, damage_dealt, "damage_received")

        elif (
            isinstance(msg, Switch)
            and not msg.is_drag
            and battle.is_opponent_side(msg.pokemon.side)
        ):
            check_heavydutyboots(battle, messages[i + 1 :])

    battle.msg_list.clear()


async def async_update_battle(battle, msg):
    return update_battle(battle, msg)
