import logging

import constants
from data import pokedex
from fp.battle import Battle, Pokemon, Battler, LastUsedMove

from poke_engine import (
    State as PokeEngineState,
    Side as PokeEngineSide,
    SideConditions as PokeEngineSideConditions,
    Pokemon as PokeEnginePokemon,
    Move as PokeEngineMove,
    monte_carlo_tree_search,
    calculate_damage,
    iterative_deepening_expectiminimax,
)

logger = logging.getLogger(__name__)


def status_to_string(status):
    if status == constants.SLEEP:
        return "Sleep"
    elif status == constants.BURN:
        return "Burn"
    elif status == constants.FROZEN:
        return "Freeze"
    elif status == constants.PARALYZED:
        return "Paralyze"
    elif status == constants.POISON:
        return "Poison"
    elif status == constants.TOXIC:
        return "Toxic"
    elif status is None:
        return "None"
    raise ValueError(f"Unknown status: {status}")


def pokemon_to_poke_engine_pkmn(pkmn: Pokemon):
    """
    id,level,type0,type1,hp,maxhp,ability,item,atk,def,spa,spd,spe,atkb,defb,spab,spdb,speb,accb,evab,status,subhp,restturns
    nature,volatiles,m0,m1,m2,m3
    """

    # Gen 3/4 don't remove items if knocked off
    # but the item is not active, so lets remove it
    if pkmn.knocked_off or pkmn.item == "" or pkmn.item is None:
        pkmn.item = "None"

    num_moves = len(pkmn.moves)
    p = PokeEnginePokemon(
        id=str(pkmn.name),
        level=pkmn.level,
        types=pkmn.types,
        hp=int(pkmn.hp),
        maxhp=int(pkmn.max_hp),
        ability=str(pkmn.ability),
        item=str(pkmn.item),
        attack=pkmn.stats[constants.ATTACK],
        defense=pkmn.stats[constants.DEFENSE],
        special_attack=pkmn.stats[constants.SPECIAL_ATTACK],
        special_defense=pkmn.stats[constants.SPECIAL_DEFENSE],
        speed=pkmn.stats[constants.SPEED],
        status=status_to_string(pkmn.status),
        rest_turns=pkmn.rest_turns,
        sleep_turns=pkmn.sleep_turns,
        weight_kg=float(pokedex[pkmn.name][constants.WEIGHT]),
        moves=[
            PokeEngineMove(id=str(m.name), disabled=m.disabled, pp=m.current_pp)
            for m in pkmn.moves
        ],
        tera_type=pkmn.tera_type or "typeless",
        terastallized=pkmn.terastallized,
    )

    if len(pkmn.types) == 1:
        pkmn.types = (pkmn.types[0], "typeless")

    while num_moves < 6:
        p.moves.append(PokeEngineMove(id="none", disabled=True, pp=0))
        num_moves += 1

    return p


def get_dummy_poke_engine_pkmn():
    return PokeEnginePokemon(id="pikachu", level=1, hp=0)


def battler_to_poke_engine_side(
    battler: Battler, force_switch=False, stayed_in_on_switchout_move=False
):
    num_reserves = len(battler.reserve)
    last_used_move = "move:none"
    if battler.last_used_move.move.startswith("switch "):
        last_used_move = "switch:0"
    elif battler.last_used_move.move:
        pkmn_moves = [m.name for m in battler.active.moves]
        for i, move in enumerate(pkmn_moves):
            if move == battler.last_used_move.move:
                last_used_move = "move:{}".format(i)
                break
        else:
            last_used_move = "move:0"

    # substitute health can't be known with certainty but the client can keep track of if the substitute was hit
    # to approximate: the substitute health is 1/10 of the pokemon's max_hp if it was hit, 1/4 if it wasn't
    substitute_health = 0
    if constants.SUBSTITUTE in battler.active.volatile_statuses:
        if battler.active.substitute_hit:
            substitute_health = int(battler.active.max_hp / 10)
        else:
            substitute_health = int(battler.active.max_hp / 4)

    future_sight_index = 0
    if battler.future_sight[0] > 0:
        if battler.active.name == battler.future_sight[1]:
            future_sight_index = 0
        else:
            index = 1
            for pkmn in battler.reserve:
                if pkmn.name == battler.future_sight[1]:
                    future_sight_index = index
                    break
                index += 1
            else:
                raise ValueError(
                    "Couldnt find future sight source: {} not in {} + {}".format(
                        battler.future_sight[1],
                        battler.active.name,
                        [p.name for p in battler.reserve],
                    )
                )

    side = PokeEngineSide(
        active_index="0",
        baton_passing=battler.baton_passing,
        pokemon=[pokemon_to_poke_engine_pkmn(battler.active)]
        + [pokemon_to_poke_engine_pkmn(p) for p in battler.reserve],
        side_conditions=PokeEngineSideConditions(
            aurora_veil=battler.side_conditions[constants.AURORA_VEIL],
            crafty_shield=battler.side_conditions["craftyshield"],
            healing_wish=battler.side_conditions[constants.HEALING_WISH],
            light_screen=battler.side_conditions[constants.LIGHT_SCREEN],
            lucky_chant=battler.side_conditions["luckychant"],
            lunar_dance=battler.side_conditions["lunardance"],
            mat_block=battler.side_conditions["matblock"],
            mist=battler.side_conditions["mist"],
            protect=battler.side_conditions[constants.PROTECT],
            quick_guard=battler.side_conditions["quickguard"],
            reflect=battler.side_conditions[constants.REFLECT],
            safeguard=battler.side_conditions[constants.SAFEGUARD],
            spikes=battler.side_conditions[constants.SPIKES],
            stealth_rock=battler.side_conditions[constants.STEALTH_ROCK],
            sticky_web=battler.side_conditions[constants.STICKY_WEB],
            tailwind=battler.side_conditions[constants.TAILWIND],
            toxic_count=battler.side_conditions[constants.TOXIC_COUNT],
            toxic_spikes=battler.side_conditions[constants.TOXIC_SPIKES],
            wide_guard=battler.side_conditions["wideguard"],
        ),
        wish=(int(battler.wish[0]), int(battler.wish[1])),
        future_sight=(battler.future_sight[0], str(future_sight_index)),
        force_switch=force_switch,
        force_trapped=battler.trapped,
        slow_uturn_move=stayed_in_on_switchout_move,
        volatile_statuses=battler.active.volatile_statuses,
        substitute_health=substitute_health,
        attack_boost=battler.active.boosts[constants.ATTACK],
        defense_boost=battler.active.boosts[constants.DEFENSE],
        special_attack_boost=battler.active.boosts[constants.SPECIAL_ATTACK],
        special_defense_boost=battler.active.boosts[constants.SPECIAL_DEFENSE],
        speed_boost=battler.active.boosts[constants.SPEED],
        accuracy_boost=0,
        evasion_boost=0,
        last_used_move=last_used_move,
        switch_out_move_second_saved_move="NONE",  # always none because we can't know this
    )

    while num_reserves < 5:
        side.pokemon.append(get_dummy_poke_engine_pkmn())
        num_reserves += 1

    return side


def get_weather_string(weather):
    if weather == constants.RAIN:
        return "rain"
    elif weather == constants.SUN:
        return "sun"
    elif weather == constants.SAND:
        return "sand"
    elif weather == constants.HAIL:
        return "hail"
    elif weather == constants.SNOW:
        return "snow"
    elif weather == constants.DESOLATE_LAND:
        return "harshsun"
    elif weather == constants.HEAVY_RAIN:
        return "heavyrain"
    elif weather is None:
        return "none"
    elif weather == "none":
        return "none"
    else:
        raise ValueError(f"Unknown weather {weather}")


def get_terrain_string(terrain):
    if terrain == constants.ELECTRIC_TERRAIN:
        return "electricterrain"
    elif terrain == constants.GRASSY_TERRAIN:
        return "grassyterrain"
    elif terrain == constants.MISTY_TERRAIN:
        return "mistyterrain"
    elif terrain == constants.PSYCHIC_TERRAIN:
        return "psychicterrain"
    elif terrain is None:
        return "none"
    elif terrain == "none":
        return "none"
    else:
        raise ValueError(f"Unknown terrain {terrain}")


def replace_hidden_power_last_used_move(battler: Battler):
    for mv in battler.active.moves:
        if mv.name.startswith(constants.HIDDEN_POWER):
            battler.last_used_move = LastUsedMove(
                pokemon_name=battler.last_used_move.pokemon_name,
                move=mv.name,
                turn=battler.last_used_move.turn,
            )
            break
    else:
        logger.warning("Could not replace hiddenpower")
        battler.last_used_move = LastUsedMove(
            pokemon_name=battler.last_used_move.pokemon_name,
            move="switch {}".format(battler.active.name),
            turn=battler.last_used_move.turn,
        )


def replace_return_last_used_move(battler: Battler):
    for mv in battler.active.moves:
        if mv.name.startswith("return"):
            battler.last_used_move = LastUsedMove(
                pokemon_name=battler.last_used_move.pokemon_name,
                move=mv.name,
                turn=battler.last_used_move.turn,
            )
            break
    else:
        logger.warning("Could not replace return")
        battler.last_used_move = LastUsedMove(
            pokemon_name=battler.last_used_move.pokemon_name,
            move="switch {}".format(battler.active.name),
            turn=battler.last_used_move.turn,
        )


def battle_to_poke_engine_state(battle: Battle, swap=False):
    # Boolean that represents if we have used a switch-out move first (i.e. fast uturn)
    # this is toggled to True if we did, and signifies to the engine that the opponent has
    # selected a move and that should be accounted for in the search
    opponent_switchout_move_stayed_in = False
    bot_lum = battle.user.last_used_move
    opp_lum = battle.opponent.last_used_move
    if bot_lum.move in constants.SWITCH_OUT_MOVES and opp_lum.turn != bot_lum.turn:
        opponent_switchout_move_stayed_in = True

    if battle.opponent.last_used_move.move == constants.HIDDEN_POWER:
        replace_hidden_power_last_used_move(battle.opponent)
    elif battle.opponent.last_used_move.move == "return":
        replace_return_last_used_move(battle.opponent)

    if battle.user.last_used_move.move == constants.HIDDEN_POWER:
        replace_hidden_power_last_used_move(battle.user)
    if battle.user.last_used_move.move == "return":
        replace_return_last_used_move(battle.user)

    side_one = battler_to_poke_engine_side(
        battle.user, force_switch=battle.force_switch
    )
    side_two = battler_to_poke_engine_side(
        battle.opponent, stayed_in_on_switchout_move=opponent_switchout_move_stayed_in
    )

    if swap:
        side_one, side_two = side_two, side_one

    state = PokeEngineState(
        side_one=side_one,
        side_two=side_two,
        weather=get_weather_string(battle.weather),
        weather_turns_remaining=battle.weather_turns_remaining,
        terrain=get_terrain_string(battle.field),
        terrain_turns_remaining=battle.field_turns_remaining,
        trick_room=battle.trick_room,
        trick_room_turns_remaining=battle.trick_room_turns_remaining,
        team_preview=battle.team_preview,
    )

    return state


def poke_engine_get_damage_rolls(
    battle: Battle, side_one_move, side_two_move, side_one_went_first
):
    if side_one_move.startswith("switch"):
        side_one_move = "switch"
    if side_two_move.startswith("switch"):
        side_two_move = "switch"

    state = battle_to_poke_engine_state(battle)

    logger.debug(
        "Calling calculate damage with state: {}, m1: {}, m2: {}, s1_went_first: {}".format(
            state.to_string(),
            side_one_move,
            side_two_move,
            side_one_went_first,
        )
    )

    s1_rolls, s2_rolls = calculate_damage(
        state,
        side_one_move,
        side_two_move,
        side_one_went_first,
    )

    logger.debug(
        "Got Rolls s1_rolls: {}, s2_rolls: {}".format(
            s1_rolls,
            s2_rolls,
        )
    )

    return s1_rolls, s2_rolls


def get_payoff_matrix_from_mcts(
    poke_engine_state: PokeEngineState, search_time_ms: int
):
    state_string = poke_engine_state.to_string()
    logger.debug("Calling with state: {}".format(state_string))

    mcts_result = monte_carlo_tree_search(poke_engine_state, search_time_ms)

    iterations = mcts_result.total_visits

    most_visits = -1
    choice = None
    win_percentage = 0
    for option in mcts_result.side_one:
        visits = option.visits
        if visits > most_visits:
            most_visits = visits
            win_percentage = round(float(option.total_score) / most_visits, 2)
            choice = option.move_choice

    if choice is None:
        raise ValueError("No move found")

    return (
        choice,
        win_percentage,
        iterations,
    )


def get_payoff_matrix_with_minimax(
    poke_engine_state: PokeEngineState, search_time_ms: int
):
    state_string = poke_engine_state.to_string()
    logger.debug("Calling with state: {}".format(state_string))

    id_result = iterative_deepening_expectiminimax(poke_engine_state, search_time_ms)

    return id_result.get_safest_move()
