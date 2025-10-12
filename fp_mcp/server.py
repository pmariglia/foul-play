"""
MCP Server for LLM-controlled Pokemon battles.

Exposes 7 MCP tools for battle control:
1. initiate_battle - Start ladder search (waits for match to start)
2. challenge_user - Challenge specific user (gen9randombattle only, waits for acceptance)
3. get_battle_state - Get current battle state
4. get_available_actions - Get legal actions with details
5. make_move - Execute move decision with optimality evaluation
6. get_pokemon_details - Get detailed info about a specific pokemon
7. forfeit_battle - Forfeit battle

Battle IDs are the actual Pokemon Showdown battle tags (e.g., battle-gen9randombattle-2460601996).
"""

import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from typing import Optional

from fastmcp import FastMCP

from config import init_logging, FoulPlayConfig, BotModes, SaveReplay
from fp.battle import Battle
from fp.evaluate import BattleEvaluation
from fp.search.main import find_best_move
from fp.websocket_client import PSWebsocketClient
from fp_mcp.battle_session import BattleSession, BattleStatus
from fp_mcp.serialization import (
    battle_to_llm_json,
    get_detailed_actions,
    validate_action,
    pokemon_to_dict,
)
from fp_mcp.battle_loop import run_llm_battle_loop
from fp_mcp.markdown_formatters import (
    format_battle_state_md,
    format_actions_md,
    format_move_result_md,
    format_pokemon_details_md,
)


logger = logging.getLogger(__name__)


# Initialize FoulPlayConfig with environment variables
# This is needed because run_battle.py uses FoulPlayConfig.username
def _init_config():
    """Initialize FoulPlayConfig from environment variables."""
    FoulPlayConfig.username = os.getenv("PS_USERNAME", "LLMBot")
    FoulPlayConfig.password = os.getenv("PS_PASSWORD", "")
    FoulPlayConfig.websocket_uri = os.getenv("PS_SERVER", "wss://sim3.psim.us/showdown/websocket")
    FoulPlayConfig.user_id = FoulPlayConfig.username.lower()  # PS uses lowercase for user IDs
    FoulPlayConfig.avatar = None
    FoulPlayConfig.bot_mode = BotModes.search_ladder
    FoulPlayConfig.pokemon_format = "gen9randombattle"
    FoulPlayConfig.smogon_stats = None
    FoulPlayConfig.search_time_ms = 100
    FoulPlayConfig.parallelism = 1
    FoulPlayConfig.run_count = 1
    FoulPlayConfig.team_name = "gen9randombattle"
    FoulPlayConfig.user_to_challenge = None
    FoulPlayConfig.save_replay = SaveReplay.never
    FoulPlayConfig.room_name = None
    FoulPlayConfig.log_level = "INFO"
    FoulPlayConfig.log_to_file = False
    FoulPlayConfig.enable_evaluation = os.getenv("ENABLE_EVALUATION", "true").lower() == "true"
    FoulPlayConfig.stdout_log_handler = None
    FoulPlayConfig.file_log_handler = None
    logger.info(f"Initialized FoulPlayConfig with username: {FoulPlayConfig.username}")

_init_config()


# Create MCP server
mcp = FastMCP(name="foul-play-mcp")


# Global session storage
sessions: dict[str, BattleSession] = {}
battle_counter = 0

# Enable/disable move evaluation
ENABLE_EVALUATION = os.getenv("ENABLE_EVALUATION", "true").lower() == "true"


async def run_evaluation(battle: Battle, llm_action: str) -> Optional[BattleEvaluation]:
    """
    Run MCTS evaluation on current position.

    Args:
        battle: Current battle state
        llm_action: The action chosen by the LLM

    Returns:
        BattleEvaluation with move scores, or None if evaluation fails
    """
    try:
        # Deep copy to avoid modifying original battle
        battle_copy = deepcopy(battle)

        # Run evaluation in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as pool:
            best_move, evaluation = await loop.run_in_executor(
                pool, find_best_move, battle_copy, True
            )

        # Log comparison
        move_eval = evaluation.get_move_evaluation(llm_action)
        if move_eval:
            logger.info(
                f"LLM chose '{llm_action}' (optimality: {move_eval.optimality:.3f}). "
                f"Best move: '{best_move}' (optimality: 1.000)"
            )
        else:
            logger.warning(
                f"LLM chose '{llm_action}' not in MCTS search. Best: '{best_move}'"
            )

        return evaluation
    except Exception as e:
        logger.error(f"Evaluation failed: {e}", exc_info=True)
        return None


def _generate_temp_session_id() -> str:
    """Generate temporary session ID for tracking before we get the real battle tag."""
    global battle_counter
    battle_counter += 1
    import time
    timestamp = int(time.time())
    return f"temp-session-{timestamp}-{battle_counter}"


@mcp.tool()
async def initiate_battle(format: str = "gen9randombattle") -> str:
    """
    Start searching for a random battle on Pokemon Showdown.

    Args:
        format: Pokemon format to play (e.g., gen9randombattle, gen8randombattle)

    Returns:
        Markdown-formatted battle start confirmation with battle_id
    """
    logger.info(f"Initiating battle with format: {format}")

    # Get credentials from environment
    username = os.getenv("PS_USERNAME", "LLMBot")
    password = os.getenv("PS_PASSWORD", "")
    websocket_uri = os.getenv("PS_SERVER", "wss://sim3.psim.us/showdown/websocket")

    try:
        # Create websocket connection
        ps_client = await PSWebsocketClient.create(username, password, websocket_uri)
        await ps_client.login()

        # Use temporary session ID until we get the real battle tag from PS
        temp_id = _generate_temp_session_id()

        # Create session with temp ID
        session = BattleSession(
            battle_id=temp_id,
            websocket_client=ps_client,
            pokemon_format=format,
            team_dict=None,  # Random battles don't need teams
        )

        sessions[temp_id] = session
        session.status = BattleStatus.SEARCHING

        # Start battle loop in background - it will update the battle_id once battle starts
        async def run_and_update_session():
            try:
                await run_llm_battle_loop(session)
            finally:
                # Clean up temp session after battle ends
                if temp_id in sessions:
                    del sessions[temp_id]

        session.battle_loop_task = asyncio.create_task(run_and_update_session())

        # Wait for battle to start and get the real battle tag
        max_wait = 60  # 60 seconds timeout
        start_time = asyncio.get_event_loop().time()
        while session.status in [BattleStatus.INITIALIZING, BattleStatus.SEARCHING]:
            await asyncio.sleep(0.5)
            if asyncio.get_event_loop().time() - start_time > max_wait:
                session.mark_error("Timeout waiting for battle to start")
                if temp_id in sessions:
                    del sessions[temp_id]
                return "# Error\n\nTimeout waiting for opponent (60 seconds)."

        # Battle started, get the real battle tag
        if session.battle:
            real_battle_id = session.battle.battle_tag
            session.battle_id = real_battle_id
            # Move session to use real battle ID as key
            sessions[real_battle_id] = session
            if temp_id in sessions:
                del sessions[temp_id]

            logger.info(f"Battle started with ID: {real_battle_id}")

            return f"# Battle Started!\n\n**Battle ID:** `{real_battle_id}`\n**Format:** {format}\n\nBattle is ready - use `get_battle_state` to see your team!"
        else:
            if temp_id in sessions:
                del sessions[temp_id]
            error_msg = session.error_message or "Battle failed to start"
            return f"# Error\n\n{error_msg}"

    except Exception as e:
        logger.error(f"Error initiating battle: {e}", exc_info=True)
        return f"# Error\n\n{str(e)}"


@mcp.tool()
async def challenge_user(opponent: str) -> str:
    """
    Challenge a specific Pokemon Showdown user to a gen9randombattle.

    This tool only supports gen9randombattle format. It will wait for the
    opponent to accept the challenge before returning.

    Args:
        opponent: Pokemon Showdown username to challenge

    Returns:
        Markdown-formatted challenge result with battle_id
    """
    format = "gen9randombattle"  # Hardcoded - only support random battles
    logger.info(f"Challenging {opponent} to {format}")

    # Get credentials from environment
    username = os.getenv("PS_USERNAME", "LLMBot")
    password = os.getenv("PS_PASSWORD", "")
    websocket_uri = os.getenv("PS_SERVER", "wss://sim3.psim.us/showdown/websocket")

    try:
        # Create websocket connection
        ps_client = await PSWebsocketClient.create(username, password, websocket_uri)
        await ps_client.login()

        # Use temporary session ID until we get the real battle tag from PS
        temp_id = _generate_temp_session_id()

        # Create session with temp ID
        session = BattleSession(
            battle_id=temp_id,
            websocket_client=ps_client,
            pokemon_format=format,
            team_dict=None,
        )

        sessions[temp_id] = session
        session.status = BattleStatus.SEARCHING

        # Start battle loop with challenge
        async def run_and_update_session():
            try:
                await run_llm_battle_loop(session, challenge_user=opponent)
            finally:
                # Clean up temp session after battle ends
                if temp_id in sessions:
                    del sessions[temp_id]

        session.battle_loop_task = asyncio.create_task(run_and_update_session())

        logger.info(f"Challenge sent to {opponent}, waiting for acceptance...")

        # Wait for battle to start (opponent accepts) and get the real battle tag
        max_wait = 120  # 2 minutes timeout for user to accept
        start_time = asyncio.get_event_loop().time()
        while session.status in [BattleStatus.INITIALIZING, BattleStatus.SEARCHING]:
            await asyncio.sleep(0.5)
            if asyncio.get_event_loop().time() - start_time > max_wait:
                session.mark_error("Timeout waiting for opponent to accept challenge")
                if temp_id in sessions:
                    del sessions[temp_id]
                return f"# Challenge Timeout\n\n**{opponent}** did not accept the challenge within 2 minutes."

        # Battle started, get the real battle tag
        if session.battle:
            real_battle_id = session.battle.battle_tag
            session.battle_id = real_battle_id
            # Move session to use real battle ID as key
            sessions[real_battle_id] = session
            if temp_id in sessions:
                del sessions[temp_id]

            logger.info(f"Challenge accepted! Battle started with ID: {real_battle_id}")

            return f"# Challenge Accepted!\n\n**Opponent:** {opponent}\n**Battle ID:** `{real_battle_id}`\n**Format:** {format}\n\nBattle is ready - use `get_battle_state` to see your team!"
        else:
            if temp_id in sessions:
                del sessions[temp_id]
            error_msg = session.error_message or "Battle failed to start"
            return f"# Error\n\n{error_msg}"

    except Exception as e:
        logger.error(f"Error challenging user: {e}", exc_info=True)
        return f"# Error\n\n{str(e)}"


@mcp.tool()
async def get_battle_state(battle_id: str) -> str:
    """
    Get the current state of a battle including your team, opponent's visible info,
    field conditions, and available actions.

    Args:
        battle_id: Battle identifier from initiate_battle or challenge_user

    Returns:
        Markdown-formatted battle state
    """
    if battle_id not in sessions:
        return f"# Error\n\nBattle `{battle_id}` not found."

    session = sessions[battle_id]

    # Determine message for non-started battles
    message = None
    if not session.battle:
        if session.status == BattleStatus.SEARCHING:
            message = "Battle is still searching for an opponent. Please wait..."
        elif session.status == BattleStatus.INITIALIZING:
            message = "Battle is initializing..."
        elif session.status == BattleStatus.FOUND:
            message = "Opponent found! Battle starting..."
        else:
            message = f"Battle in status: {session.status.value}"

    return format_battle_state_md(
        battle_id=battle_id,
        status=session.status.value,
        awaiting_decision=session.awaiting_decision,
        battle=session.battle,
        winner=session.winner,
        error_message=session.error_message,
        error_log=session.error_log,
        message=message,
    )


@mcp.tool()
async def get_available_actions(battle_id: str) -> str:
    """
    Get detailed list of legal actions (moves and switches) with type effectiveness,
    power, and other details.

    Args:
        battle_id: Battle identifier

    Returns:
        Markdown-formatted list of available actions
    """
    if battle_id not in sessions:
        return f"# Error\n\nBattle `{battle_id}` not found."

    session = sessions[battle_id]

    if not session.battle:
        return f"# Error\n\nBattle not started yet.\n\n**Status:** {session.status.value}"

    actions = get_detailed_actions(session.battle)

    constraints = {
        "force_switch": session.battle.force_switch,
        "trapped": session.battle.user.trapped,
        "can_mega": session.battle.user.active.can_mega_evo if session.battle.user.active else False,
        "can_tera": session.battle.user.active.can_terastallize if session.battle.user.active else False,
    }

    return format_actions_md(battle_id, actions, constraints)


@mcp.tool()
async def make_move(battle_id: str, action: str, reasoning: Optional[str] = None) -> str:
    """
    Execute a move decision. Must be one of the available actions from get_available_actions.

    Examples: 'thunderbolt', 'switch charizard', 'earthquake-tera'

    Args:
        battle_id: Battle identifier
        action: Move name, 'switch <pokemon>', or move with modifier like 'thunderbolt-tera'
        reasoning: Optional reasoning for the move (for logging/analysis)

    Returns:
        Markdown-formatted result with validation and optimality evaluation
    """
    if battle_id not in sessions:
        return f"# Error\n\nBattle `{battle_id}` not found."

    session = sessions[battle_id]

    if not session.awaiting_decision:
        return f"# Error\n\nBattle is not waiting for a decision.\n\n**Status:** {session.status.value}"

    if not session.battle:
        return "# Error\n\nBattle not started yet."

    # Validate action
    is_valid, error_msg = validate_action(session.battle, action)

    if not is_valid:
        return format_move_result_md(
            battle_id=battle_id,
            status="invalid",
            action=action,
            message="Invalid action",
            validation={"valid": False, "reason": error_msg},
        )

    # Log reasoning if provided
    if reasoning:
        logger.info(f"[{battle_id}] Move reasoning: {reasoning}")

    # Run evaluation before submission
    evaluation_data = None
    if ENABLE_EVALUATION:
        evaluation = await run_evaluation(session.battle, action)
        if evaluation:
            move_eval = evaluation.get_move_evaluation(action)
            evaluation_data = {
                "optimality": move_eval.optimality if move_eval else 0.0,
                "best_move": evaluation.best_move,
                "scenarios_analyzed": evaluation.num_scenarios,
                "is_optimal": (action == evaluation.best_move),
            }

    # Submit decision
    try:
        await session.submit_decision(action)

        return format_move_result_md(
            battle_id=battle_id,
            status="sent",
            action=action,
            message="Move sent successfully",
            validation={"valid": True, "reason": None},
            evaluation=evaluation_data,
        )

    except Exception as e:
        logger.error(f"Error submitting decision: {e}", exc_info=True)
        return format_move_result_md(
            battle_id=battle_id,
            status="error",
            action=action,
            message="Error",
            validation={"valid": False, "reason": str(e)},
            error=str(e),
        )


@mcp.tool()
async def get_pokemon_details(battle_id: str, pokemon_name: str, opponent: bool = False) -> str:
    """
    Get detailed information about a specific pokemon (your team or opponent's).

    Use this to inspect reserve pokemon in detail. The main battle state shows
    reserve pokemon in compact form (just name, HP, status) to save tokens.

    Args:
        battle_id: Battle identifier
        pokemon_name: Name of pokemon to inspect (e.g., "charizard", "landorustherian")
        opponent: If True, inspect opponent's pokemon (shows only revealed information)

    Returns:
        Markdown-formatted pokemon details
    """
    if battle_id not in sessions:
        return f"# Error\n\nBattle `{battle_id}` not found."

    session = sessions[battle_id]

    if not session.battle:
        return "# Error\n\nBattle not started yet."

    battler = session.battle.opponent if opponent else session.battle.user

    # Search for pokemon
    if battler.active and battler.active.name == pokemon_name:
        pokemon = battler.active
    else:
        pokemon = None
        for pkmn in battler.reserve:
            if pkmn.name == pokemon_name:
                pokemon = pkmn
                break

    if not pokemon:
        available = [battler.active.name if battler.active else ""] + [p.name for p in battler.reserve]
        available = [name for name in available if name]
        details = {
            "error": f"Pokemon '{pokemon_name}' not found",
            "available_pokemon": available,
            "battle_id": battle_id,
        }
        return format_pokemon_details_md(details)

    # Return full details
    details = pokemon_to_dict(pokemon, hide_unknowns=opponent, compact=False)
    details["battle_id"] = battle_id
    details["is_opponent"] = opponent

    return format_pokemon_details_md(details)


@mcp.tool()
async def forfeit_battle(battle_id: str) -> str:
    """
    Forfeit the current battle.

    Args:
        battle_id: Battle identifier

    Returns:
        Markdown-formatted forfeit confirmation
    """
    if battle_id not in sessions:
        return f"# Error\n\nBattle `{battle_id}` not found."

    session = sessions[battle_id]
    session.forfeit()

    # Send forfeit command
    try:
        if session.battle:
            await session.websocket_client.send_message(
                session.battle.battle_tag, ["/forfeit"]
            )

        return f"# Battle Forfeited\n\n**Battle ID:** `{battle_id}`\n\nYou have forfeited the battle."

    except Exception as e:
        logger.error(f"Error forfeiting battle: {e}", exc_info=True)
        return f"# Error\n\nFailed to forfeit battle: {str(e)}"


if __name__ == "__main__":
    # Initialize logging
    init_logging("INFO", log_to_file=False)

    logger.info("Starting Foul Play MCP Server...")

    # Run the server
    mcp.run()
