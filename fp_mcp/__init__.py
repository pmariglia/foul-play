"""
MCP (Model Context Protocol) interface for Foul Play.

Enables LLMs like Claude to play Pokemon battles through a clean API.

Main components:
- server: MCP server with 6 core tools
- battle_session: Session management for active battles
- battle_loop: Modified battle loop for LLM control
- serialization: Battle state to JSON conversion
"""

from fp_mcp.battle_session import BattleSession, BattleStatus
from fp_mcp.serialization import (
    battle_to_llm_json,
    get_available_actions,
    validate_action,
)

__all__ = [
    "BattleSession",
    "BattleStatus",
    "battle_to_llm_json",
    "get_available_actions",
    "validate_action",
]
