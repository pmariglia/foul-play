"""
Modified battle loop for LLM control.

This module provides the async battle loop that integrates with BattleSession
to pause and wait for LLM decisions instead of using MCTS.
"""

import asyncio
import logging
import traceback
from typing import Optional

import constants
from constants import BattleType
from data.pkmn_sets import RandomBattleTeamDatasets
from fp.run_battle import (
    start_battle_common,
    get_first_request_json,
    process_battle_updates,
    battle_is_finished,
    format_decision,
)
from fp.battle_modifier import async_update_battle
from fp.battle import LastUsedMove
from fp_mcp.battle_session import BattleSession, BattleStatus


logger = logging.getLogger(__name__)


def set_last_selected_move(battle, decision: str):
    """Set battle.user.last_selected_move required by battle_modifier functions."""
    move_name = decision.removesuffix("-tera").removesuffix("-mega")
    pokemon_name = battle.user.active.name if battle.user.active else ""

    battle.user.last_selected_move = LastUsedMove(
        pokemon_name,
        move_name,
        battle.turn,
    )
    logger.debug(f"Set last_selected_move: pokemon={pokemon_name}, move={move_name}, turn={battle.turn}")


async def start_random_battle_llm(ps_websocket_client, pokemon_battle_type):
    """Start battle without auto-making the first move (LLM will decide)."""
    battle, msg = await start_battle_common(ps_websocket_client, pokemon_battle_type)
    battle.battle_type = BattleType.RANDOM_BATTLE
    RandomBattleTeamDatasets.initialize(battle.generation)

    while True:
        if constants.START_STRING in msg:
            battle.started = True
            battle.msg_list = [
                m
                for m in msg.split(constants.START_STRING)[1].strip().split("\n")
                if not (m.startswith("|switch|{}".format(battle.user.name)))
            ]
            break
        msg = await ps_websocket_client.receive_message()

    await get_first_request_json(ps_websocket_client, battle)
    process_battle_updates(battle)

    return battle


async def start_battle_llm(ps_websocket_client, pokemon_battle_type):
    """Start battle for LLM control (currently only supports random battles)."""
    if "random" in pokemon_battle_type:
        battle = await start_random_battle_llm(ps_websocket_client, pokemon_battle_type)
    else:
        raise NotImplementedError("MCP server currently only supports random battles")

    await ps_websocket_client.send_message(battle.battle_tag, ["hf"])
    await ps_websocket_client.send_message(battle.battle_tag, ["/timer on"])

    return battle


async def run_llm_battle_loop(
    session: BattleSession,
    challenge_user: Optional[str] = None,
) -> str:
    """Run battle loop with LLM control instead of MCTS."""
    ps_client = session.websocket_client

    try:
        if challenge_user:
            await ps_client.challenge_user(challenge_user, session.pokemon_format)
        else:
            await ps_client.search_for_match(session.pokemon_format)

        battle = await start_battle_llm(ps_client, session.pokemon_format)

        session.update_state(battle)
        session.status = BattleStatus.ACTIVE
        logger.info(f"[{session.battle_id}] Battle started: {battle.battle_tag}")

        last_sent_rqid = None
        pending_msg = None

        if not battle.wait and not battle.force_switch:
            logger.info(f"[{session.battle_id}] Turn {battle.turn}: Waiting for LLM decision (initial)")

            try:
                decision = await session.wait_for_decision(timeout=session.decision_timeout)
                logger.info(f"[{session.battle_id}] Turn {battle.turn}: LLM chose: {decision}")

                set_last_selected_move(battle, decision)

                try:
                    formatted = format_decision(battle, decision)
                    logger.info(f"[{session.battle_id}] Formatted decision: {formatted} (rqid: {battle.rqid}, turn: {battle.turn})")

                    last_sent_rqid = battle.rqid

                    await ps_client.send_message(battle.battle_tag, formatted)
                    logger.info(f"[{session.battle_id}] Initial decision sent, waiting for acknowledgment...")

                    session.awaiting_decision = False
                    session.status = BattleStatus.ACTIVE

                    try:
                        pending_msg = await asyncio.wait_for(ps_client.receive_message(), timeout=15.0)
                        logger.info(f"[{session.battle_id}] Server acknowledged initial move")
                    except asyncio.TimeoutError:
                        error_log = f"NO SERVER RESPONSE after initial move! Server never received move."
                        logger.error(f"[{session.battle_id}] {error_log}")
                        session.mark_error("Server did not acknowledge initial move", error_log=error_log)
                        await ps_client.send_message(battle.battle_tag, ["/forfeit"])
                        return None

                except Exception as format_error:
                    error_log = traceback.format_exc()
                    logger.error(f"[{session.battle_id}] Error formatting/sending decision: {format_error}", exc_info=True)
                    session.mark_error(f"Failed to send move: {format_error}", error_log=error_log)
                    raise

            except asyncio.TimeoutError:
                logger.error(f"[{session.battle_id}] Decision timeout! Forfeiting battle.")
                await ps_client.send_message(battle.battle_tag, ["/forfeit"])
                session.mark_error("Decision timeout")
                return None
            except Exception as e:
                error_log = traceback.format_exc()
                logger.error(f"[{session.battle_id}] Error getting decision: {e}", exc_info=True)
                session.mark_error(str(e), error_log=error_log)
                raise

        while True:
            if pending_msg:
                msg = pending_msg
                pending_msg = None
                logger.debug(f"[{session.battle_id}] Processing pending ack message: {msg[:200]}...")
            else:
                try:
                    msg = await asyncio.wait_for(ps_client.receive_message(), timeout=60.0)
                    logger.debug(f"[{session.battle_id}] Received message: {msg[:200]}...")
                except asyncio.TimeoutError:
                    error_log = f"Timeout waiting for server message at turn {battle.turn}. awaiting_decision={session.awaiting_decision}"
                    logger.error(f"[{session.battle_id}] {error_log}")
                    session.mark_error("Server communication timeout", error_log=error_log)
                    await ps_client.send_message(battle.battle_tag, ["/forfeit"])
                    return None

            if battle_is_finished(battle.battle_tag, msg):
                winner = (
                    msg.split(constants.WIN_STRING)[-1].split("\n")[0].strip()
                    if constants.WIN_STRING in msg
                    else None
                )
                logger.info(f"[{session.battle_id}] Battle finished. Winner: {winner}")
                await ps_client.send_message(battle.battle_tag, ["gg"])
                await ps_client.leave_battle(battle.battle_tag)
                session.mark_finished(winner)
                return winner

            prev_rqid = battle.rqid
            action_required = await async_update_battle(battle, msg)
            session.update_state(battle)

            if last_sent_rqid is not None and battle.rqid == last_sent_rqid and action_required:
                error_log = (
                    f"MOVE REJECTION DETECTED! Server still waiting with same rqid={battle.rqid}. "
                    f"Move was not processed. force_switch={battle.force_switch}, wait={battle.wait}, turn={battle.turn}"
                )
                logger.error(f"[{session.battle_id}] {error_log}")
                session.mark_error("Server did not process move", error_log=error_log)
                await ps_client.send_message(battle.battle_tag, ["/forfeit"])
                return None

            if prev_rqid != battle.rqid:
                last_sent_rqid = None

            if action_required and not battle.wait:
                logger.info(f"[{session.battle_id}] Turn {battle.turn}: Waiting for LLM decision")

                if battle.request_json:
                    battle.user.update_from_request_json(battle.request_json)
                    logger.debug(f"[{session.battle_id}] Updated battle state from request JSON")

                session.awaiting_decision = True
                session.update_state(battle)

                try:
                    decision = await session.wait_for_decision(timeout=session.decision_timeout)
                    logger.info(f"[{session.battle_id}] Turn {battle.turn}: LLM chose: {decision}")

                    set_last_selected_move(battle, decision)

                    try:
                        formatted = format_decision(battle, decision)
                        logger.info(f"[{session.battle_id}] Formatted decision: {formatted} (rqid: {battle.rqid}, turn: {battle.turn})")

                        last_sent_rqid = battle.rqid

                        await ps_client.send_message(battle.battle_tag, formatted)
                        logger.info(f"[{session.battle_id}] Decision sent to server, waiting for acknowledgment...")

                        session.awaiting_decision = False
                        session.status = BattleStatus.ACTIVE

                        try:
                            pending_msg = await asyncio.wait_for(ps_client.receive_message(), timeout=15.0)
                            logger.info(f"[{session.battle_id}] Server acknowledged move within 15s")
                        except asyncio.TimeoutError:
                            error_log = (
                                f"NO SERVER RESPONSE after 15s! Sent rqid={last_sent_rqid}, turn={battle.turn}. "
                                f"Server never received/processed move. Forfeiting to avoid inactivity loss."
                            )
                            logger.error(f"[{session.battle_id}] {error_log}")
                            session.mark_error("Server did not acknowledge move", error_log=error_log)
                            await ps_client.send_message(battle.battle_tag, ["/forfeit"])
                            return None

                    except Exception as format_error:
                        error_log = traceback.format_exc()
                        logger.error(f"[{session.battle_id}] Error formatting/sending decision: {format_error}", exc_info=True)
                        session.mark_error(f"Failed to send move: {format_error}", error_log=error_log)
                        raise

                except asyncio.TimeoutError:
                    # Decision timeout - forfeit or pick random move
                    logger.error(f"[{session.battle_id}] Decision timeout! Forfeiting battle.")
                    await ps_client.send_message(battle.battle_tag, ["/forfeit"])
                    session.mark_error("Decision timeout")
                    return None

                except Exception as e:
                    error_log = traceback.format_exc()
                    logger.error(f"[{session.battle_id}] Error getting decision: {e}", exc_info=True)
                    session.mark_error(str(e), error_log=error_log)
                    raise

    except Exception as e:
        error_log = traceback.format_exc()
        logger.error(f"[{session.battle_id}] Battle loop error: {e}", exc_info=True)
        session.mark_error(str(e), error_log=error_log)
        raise
