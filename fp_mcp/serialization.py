"""
Battle state serialization for LLM consumption.

Converts Battle objects to JSON format suitable for LLM analysis,
properly handling hidden opponent information and computing available actions.
"""

import logging
from typing import Optional

import constants
from data import all_move_json
from fp.battle import Battle, Pokemon, Battler


logger = logging.getLogger(__name__)


def pokemon_to_dict(pokemon: Pokemon, hide_unknowns: bool = False, compact: bool = False) -> dict:
    """
    Convert Pokemon object to dict.

    Args:
        pokemon: Pokemon to serialize
        hide_unknowns: If True, replace unknown values with "unknown"
        compact: If True, return minimal info (name, HP, status, alive) for reserve pokemon

    Returns:
        Dict representation of pokemon
    """
    # Compact mode - minimal info for reserve pokemon
    if compact:
        return {
            "name": pokemon.name,
            "hp": pokemon.hp,
            "max_hp": pokemon.max_hp,
            "status": pokemon.status,
            "is_alive": pokemon.is_alive(),
        }

    # Full mode - complete details
    data = {
        "name": pokemon.name,
        "level": pokemon.level,
        "hp": pokemon.hp,
        "max_hp": pokemon.max_hp,
        "status": pokemon.status,
        "ability": pokemon.ability if pokemon.ability else (None if not hide_unknowns else "unknown"),
        "item": pokemon.item if pokemon.item and pokemon.item != constants.UNKNOWN_ITEM else (
            None if not hide_unknowns else "unknown"
        ),
        "types": list(pokemon.types),
        "tera_type": pokemon.tera_type,
        "terastallized": pokemon.terastallized,
        "is_alive": pokemon.is_alive(),
        "fainted": pokemon.fainted,
    }

    # Moves
    if pokemon.moves:
        data["moves"] = []
        for move in pokemon.moves:
            move_data = {
                "name": move.name,
                "pp": move.current_pp,
                "max_pp": move.max_pp,
                "disabled": move.disabled,
            }

            # Add move details from move JSON
            if move.name in all_move_json:
                move_info = all_move_json[move.name]
                move_data["type"] = move_info.get("type", "unknown")
                move_data["category"] = move_info.get("category", "unknown")
                move_data["power"] = move_info.get("basePower", 0)
                move_data["accuracy"] = move_info.get("accuracy", 100)
                move_data["priority"] = move_info.get("priority", 0)

            data["moves"].append(move_data)
    else:
        data["moves"] = []

    # Stats
    data["stats"] = dict(pokemon.stats)

    # Boosts
    data["boosts"] = dict(pokemon.boosts)

    # Volatile statuses
    data["volatile_statuses"] = list(pokemon.volatile_statuses)

    return data


def battler_to_dict(battler: Battler, is_opponent: bool = False, compact_reserve: bool = True) -> dict:
    """
    Convert Battler (one side) to dict.

    Args:
        battler: Battler to serialize
        is_opponent: If True, hide unknown information
        compact_reserve: If True, show minimal info for reserve pokemon

    Returns:
        Dict representation of battler
    """
    data = {
        "active": pokemon_to_dict(battler.active, hide_unknowns=is_opponent, compact=False) if battler.active else None,
        "reserve": [pokemon_to_dict(p, hide_unknowns=is_opponent, compact=compact_reserve) for p in battler.reserve],
        "side_conditions": dict(battler.side_conditions),
    }

    if not is_opponent:
        data["trapped"] = battler.trapped

    return data


def get_available_actions(battle: Battle) -> list[str]:
    """
    Get list of legal actions for current battle state.

    Returns:
        List of action strings (e.g., ["thunderbolt", "switch charizard"])
    """
    actions = []

    if battle.force_switch:
        # Must switch - only alive reserve pokemon
        for pkmn in battle.user.reserve:
            if pkmn.is_alive():
                actions.append(f"switch {pkmn.name}")
    else:
        # Regular turn - can use moves or switch
        # Add moves
        for move in battle.user.active.moves:
            if not move.disabled and move.current_pp > 0:
                actions.append(move.name)

                # Add tera variant if available
                if battle.user.active.can_terastallize:
                    actions.append(f"{move.name}-tera")

                # Add mega variant if available
                if battle.user.active.can_mega_evo:
                    actions.append(f"{move.name}-mega")

        # Add switches (if not trapped)
        if not battle.user.trapped:
            for pkmn in battle.user.reserve:
                if pkmn.is_alive():
                    actions.append(f"switch {pkmn.name}")

    return actions


def validate_action(battle: Battle, action: str) -> tuple[bool, Optional[str]]:
    """
    Validate if an action is legal.

    Args:
        battle: Current battle state
        action: Action string to validate

    Returns:
        (is_valid, error_message) tuple
    """
    available = get_available_actions(battle)

    if action not in available:
        return False, f"Action '{action}' is not legal. Available actions: {', '.join(available)}"

    return True, None


def battle_to_llm_json(battle: Battle, compact_reserve: bool = True) -> dict:
    """
    Convert Battle object to JSON for LLM consumption.

    Provides complete battle state with proper handling of hidden opponent info.

    Args:
        battle: Battle to serialize
        compact_reserve: If True, show minimal info for reserve pokemon (recommended to save tokens)

    Returns:
        Dict representation of battle state
    """
    data = {
        "meta": {
            "turn": battle.turn,
            "time_remaining": battle.time_remaining,
            "generation": battle.generation,
            "format": battle.pokemon_format,
            "force_switch": battle.force_switch,
            "wait": battle.wait,
        },
        "user": battler_to_dict(battle.user, is_opponent=False, compact_reserve=compact_reserve),
        "opponent": battler_to_dict(battle.opponent, is_opponent=True, compact_reserve=compact_reserve),
        "field": {
            "weather": battle.weather,
            "weather_turns_remaining": battle.weather_turns_remaining,
            "terrain": battle.field,
            "terrain_turns_remaining": battle.field_turns_remaining,
            "trick_room": battle.trick_room,
            "trick_room_turns_remaining": battle.trick_room_turns_remaining,
            "gravity": battle.gravity,
        },
        "available_actions": get_available_actions(battle),
    }

    # Add capability flags
    if battle.user.active:
        data["capabilities"] = {
            "can_mega": battle.user.active.can_mega_evo,
            "can_tera": battle.user.active.can_terastallize,
            "can_dynamax": battle.user.active.can_dynamax,
            "trapped": battle.user.trapped,
        }

    return data


def get_move_details(move_name: str) -> dict:
    """
    Get detailed information about a move.

    Args:
        move_name: Name of the move

    Returns:
        Dict with move details
    """
    if move_name not in all_move_json:
        return {"name": move_name, "error": "Move not found"}

    move_data = all_move_json[move_name]

    return {
        "name": move_name,
        "type": move_data.get("type", "unknown"),
        "category": move_data.get("category", "unknown"),
        "power": move_data.get("basePower", 0),
        "accuracy": move_data.get("accuracy", 100),
        "pp": move_data.get("pp", 5),
        "priority": move_data.get("priority", 0),
        "target": move_data.get("target", "normal"),
        "flags": move_data.get("flags", {}),
    }


def get_detailed_actions(battle: Battle) -> list[dict]:
    """
    Get available actions with detailed information.

    Args:
        battle: Current battle state

    Returns:
        List of dicts with action details
    """
    actions = []
    available = get_available_actions(battle)

    for action in available:
        if action.startswith("switch "):
            # Switch action
            pkmn_name = action.split("switch ")[1]
            pkmn = battle.user.find_pokemon_in_reserves(pkmn_name)
            if pkmn:
                actions.append({
                    "action": action,
                    "type": "switch",
                    "details": {
                        "name": pkmn.name,
                        "types": list(pkmn.types),
                        "hp": f"{pkmn.hp}/{pkmn.max_hp}",
                        "status": pkmn.status,
                        "ability": pkmn.ability,
                    }
                })
        else:
            # Move action
            base_move = action.replace("-tera", "").replace("-mega", "")
            move_details = get_move_details(base_move)

            action_data = {
                "action": action,
                "type": "move",
                "details": move_details
            }

            # Add modifier notes
            if action.endswith("-tera"):
                action_data["modifier"] = "terastallize"
                action_data["details"]["note"] = "Will terastallize and use this move"
            elif action.endswith("-mega"):
                action_data["modifier"] = "mega"
                action_data["details"]["note"] = "Will mega evolve and use this move"

            actions.append(action_data)

    return actions
