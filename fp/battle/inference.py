from copy import deepcopy
import logging

from fp import constants
from fp.data import all_move_json
from fp.data import pokedex
from fp.battle.state import DamageDealt
from fp.battle.state import StatRange
from fp.search.poke_engine_helpers import poke_engine_get_damage_rolls
from fp.battle.helpers import (
    normalize_name,
)
from fp.battle.helpers import get_pokemon_info_from_condition
from fp.battle.helpers import (
    is_not_very_effective,
    is_super_effective,
    is_neutral_effectiveness,
)
from fp.battle.state import boost_multiplier_lookup


logger = logging.getLogger(__name__)

MOVE_END_STRINGS = {"move", "switch", "upkeep", "-miss", ""}


def can_have_priority_modified(battle, pokemon, move_name):
    return (
        "prankster"
        in [
            normalize_name(a)
            for a in pokedex[pokemon.name][constants.ABILITIES].values()
        ]
        or (move_name == "grassyglide" and battle.field == constants.Terrain.GRASSY)
        or (
            move_name in all_move_json
            and all_move_json[move_name][constants.CATEGORY]
            == constants.MoveCategory.STATUS
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
            battle.weather == constants.Weather.RAIN
            and pokemon.ability is None
            and "swiftswim"
            in [
                normalize_name(a)
                for a in pokedex[pokemon.name][constants.ABILITIES].values()
            ]
        )
        or (
            battle.weather == constants.Weather.SUN
            and pokemon.ability is None
            and "chlorophyll"
            in [
                normalize_name(a)
                for a in pokedex[pokemon.name][constants.ABILITIES].values()
            ]
        )
        or (
            battle.weather == constants.Weather.SAND
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
            battle.field == constants.Terrain.ELECTRIC
            and pokemon.ability is None
            and "surgesurfer"
            in [
                normalize_name(a)
                for a in pokedex[pokemon.name][constants.ABILITIES].values()
            ]
        )
        or (
            pokemon.status == constants.Status.PARALYZED
            and pokemon.ability is None
            and "quickfeet"
            in [
                normalize_name(a)
                for a in pokedex[pokemon.name][constants.ABILITIES].values()
            ]
        )
    )


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

    speed_threshold = int(
        boost_multiplier_lookup[battle.user.active.boosts[constants.SPEED]]
        * battle.user.active.stats[constants.SPEED]
        / boost_multiplier_lookup[battle.opponent.active.boosts[constants.SPEED]]
    )

    if "protosynthesisspe" in battle.opponent.active.volatile_statuses:
        speed_threshold = int(speed_threshold / 1.5)

    if battle.opponent.side_conditions[constants.TAILWIND]:
        speed_threshold = int(speed_threshold / 2)

    if battle.user.side_conditions[constants.TAILWIND]:
        speed_threshold = int(speed_threshold * 2)

    if battle.opponent.active.status == constants.Status.PARALYZED:
        speed_threshold = int(speed_threshold * battle.gen.paralysis_speed_divisor)

    if battle.user.active.status == constants.Status.PARALYZED:
        speed_threshold = int(speed_threshold / battle.gen.paralysis_speed_divisor)

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
        not battle.gen.choice_scarf_exists
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

    battle.mode.assume_spread_for_speed_check(battle, battle_copy)
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
    get_pkmn_set,
    allow_emptying=False,
):
    actual_damage_dealt = damage_dealt.percent_damage * battle_copy.user.active.max_hp

    indicies_to_remove = []
    num_starting_possibilites = len(possibilites)
    for i in range(num_starting_possibilites):
        p = get_pkmn_set(possibilites[i])

        if not battle.opponent.active.ability:
            battle_copy.opponent.active.ability = p.ability
        if battle.opponent.active.item == constants.UNKNOWN_ITEM:
            battle_copy.opponent.active.item = p.item
        battle_copy.opponent.active.set_spread(
            p.nature, ",".join(str(x) for x in p.evs)
        )

        if check_type == "damage_received":
            constant_hp_errror_allowance = battle_copy.opponent.active.level / 20
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
            constant_hp_errror_allowance = battle_copy.user.active.level / 20
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
            actual_damage_dealt < (damage[0] * 0.975 - constant_hp_errror_allowance)
        )
        upper_bound_violated = actual_damage_dealt > (
            damage[1] * 1.025 + constant_hp_errror_allowance
        )
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
        or not battle.gen.supports_reverse_damage_checking
        or battle.opponent.active is None
        or battle.opponent.active.hp <= 0
        or battle.opponent.active.name
        in ["ditto", "shedinja", "terapagosterastal", "meloetta", "meloettapirouette"]
        or battle.user.active.name
        in ["ditto", "shedinja", "terapagosterastal", "meloetta", "meloettapirouette"]
        or damage_dealt.move not in all_move_json
        or all_move_json[damage_dealt.move][constants.CATEGORY]
        == constants.MoveCategory.STATUS
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

    possibilites, smogon_possibilities, allow_emptying = (
        battle.mode.dataset_possibilities(battle)
    )

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
        get_pkmn_set=lambda p: p.pkmn_set,  # full sets: PredictedPokemonSet
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
            get_pkmn_set=lambda p: p,  # smogon: bare PokemonSet trait combinations
            allow_emptying=False,  # never completely empty smogon stats
        )


def check_heavydutyboots(battle, msg_lines):
    side_to_check = battle.opponent

    if (
        not battle.gen.heavy_duty_boots_exists
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
                    split_line[3] == constants.Status.POISON
                    or split_line[3] == constants.Status.TOXIC
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
