"""
Extended MCP tools for detailed pokemon inspection.

These tools provide deeper inspection capabilities beyond the core battle state.
"""

import logging
from typing import Optional

from fp_mcp.serialization import pokemon_to_dict


logger = logging.getLogger(__name__)


def get_pokemon_details(battle, pokemon_name: str, is_opponent: bool = False) -> Optional[dict]:
    """
    Get detailed information about a specific pokemon.

    Args:
        battle: Battle object
        pokemon_name: Name of pokemon to inspect
        is_opponent: If True, look in opponent's team

    Returns:
        Full pokemon details or None if not found
    """
    battler = battle.opponent if is_opponent else battle.user

    # Check active pokemon
    if battler.active and battler.active.name == pokemon_name:
        return pokemon_to_dict(battler.active, hide_unknowns=is_opponent, compact=False)

    # Check reserve
    for pkmn in battler.reserve:
        if pkmn.name == pokemon_name:
            return pokemon_to_dict(pkmn, hide_unknowns=is_opponent, compact=False)

    return None
