import asyncio
import json
import logging
import traceback
import time
import signal
import threading
from copy import deepcopy

from config import FoulPlayConfig, init_logging, BotModes

from teams import load_team
from fp.run_battle import pokemon_battle
from fp.websocket_client import PSWebsocketClient

from data import all_move_json
from data import pokedex
from data.mods.apply_mods import apply_mods


logger = logging.getLogger(__name__)

# Global state for graceful shutdown
class BotState:
    def __init__(self):
        self.shutdown_requested = False
        self.in_battle = False
        self.current_battle_tag = None
        self.battle_start_time = None
        self.lock = threading.Lock()
    
    def request_shutdown(self):
        with self.lock:
            self.shutdown_requested = True
            if self.in_battle:
                logger.info("Shutdown requested. Bot will stop after the current battle finishes.")
            else:
                logger.info("Shutdown requested. Bot will stop after the current operation.")
    
    def set_battle_state(self, in_battle, battle_tag=None):
        with self.lock:
            self.in_battle = in_battle
            self.current_battle_tag = battle_tag
            if in_battle:
                self.battle_start_time = time.time()
            else:
                self.battle_start_time = None
    
    def should_shutdown(self):
        with self.lock:
            return self.shutdown_requested and not self.in_battle
    
    def get_battle_info(self):
        with self.lock:
            return {
                'in_battle': self.in_battle,
                'battle_tag': self.current_battle_tag,
                'battle_duration': time.time() - self.battle_start_time if self.battle_start_time else 0
            }

bot_state = BotState()

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    logger.info(f"Received signal {signum}")
    bot_state.request_shutdown()

# Set up signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def check_dictionaries_are_unmodified(original_pokedex, original_move_json):
    # The bot should not modify the data dictionaries
    # This is a "just-in-case" check to make sure and will stop the bot if it mutates either of them
    if original_move_json != all_move_json:
        logger.critical(
            "Move JSON changed!\nDumping modified version to `modified_moves.json`"
        )
        with open("modified_moves.json", "w") as f:
            json.dump(all_move_json, f, indent=4)
        exit(1)
    else:
        logger.debug("Move JSON unmodified!")

    if original_pokedex != pokedex:
        logger.critical(
            "Pokedex JSON changed!\nDumping modified version to `modified_pokedex.json`"
        )
        with open("modified_pokedex.json", "w") as f:
            json.dump(pokedex, f, indent=4)
        exit(1)
    else:
        logger.debug("Pokedex JSON unmodified!")


async def check_for_ongoing_battle(ps_websocket_client):
    """Check if there's an ongoing battle after reconnection"""
    try:
        # Send a ping to get current status
        await ps_websocket_client.send_message("", ["/cmd rooms"])
        
        # Wait for a short time to receive any ongoing battle messages
        try:
            msg = await asyncio.wait_for(ps_websocket_client.receive_message(), timeout=2.0)
            
            # Check if we're in a battle room
            if msg.startswith(">") and "battle-" in msg:
                battle_tag = msg.split("\n")[0].replace(">", "").strip()
                if "battle-" in battle_tag:
                    logger.info(f"Detected ongoing battle: {battle_tag}")
                    return battle_tag
        except asyncio.TimeoutError:
            # No immediate battle messages, continue normally
            pass
        
        return None
    except Exception as e:
        logger.debug(f"Error checking for ongoing battle: {e}")
        return None


async def resume_battle(ps_websocket_client, battle_tag):
    """Resume an ongoing battle after reconnection"""
    logger.info(f"Attempting to resume battle: {battle_tag}")
    
    try:
        bot_state.set_battle_state(True, battle_tag)
        
        # Try to rejoin the battle room
        await ps_websocket_client.send_message("", [f"/join {battle_tag}"])
        
        # Wait for battle messages and try to continue
        while True:
            if bot_state.should_shutdown():
                logger.info("Shutdown requested during battle resumption")
                break
                
            msg = await ps_websocket_client.receive_message()
            
            # Check if battle is finished
            if battle_tag in msg and ("win" in msg.lower() or "tie" in msg.lower()):
                winner = None
                if "|win|" in msg:
                    winner = msg.split("|win|")[-1].split("\n")[0].strip()
                logger.info(f"Resumed battle finished. Winner: {winner}")
                
                await ps_websocket_client.send_message(battle_tag, ["gg"])
                await ps_websocket_client.leave_battle(battle_tag)
                bot_state.set_battle_state(False)
                return winner
            
            # If we get a request for action, we can't easily resume without full battle state
            # So we'll just forfeit the battle gracefully
            if "|request|" in msg and battle_tag in msg:
                logger.warning("Cannot resume battle mid-turn. Forfeiting gracefully.")
                await ps_websocket_client.send_message(battle_tag, ["/forfeit"])
                await ps_websocket_client.leave_battle(battle_tag)
                bot_state.set_battle_state(False)
                return None
                
    except Exception as e:
        logger.error(f"Error resuming battle: {e}")
        bot_state.set_battle_state(False)
        return None


async def handle_disconnection_recovery(ps_websocket_client, max_retries=5, base_delay=5):
    """Handle websocket disconnections with exponential backoff retry"""
    for attempt in range(max_retries):
        try:
            if ps_websocket_client.is_connected():
                return True
            
            delay = base_delay * (2 ** attempt)
            logger.warning(f"Connection lost. Retrying in {delay} seconds (attempt {attempt + 1}/{max_retries})...")
            await asyncio.sleep(delay)
            
            # Reconnect
            await ps_websocket_client.reconnect()
            FoulPlayConfig.user_id = await ps_websocket_client.login()
            
            if FoulPlayConfig.avatar is not None:
                await ps_websocket_client.avatar(FoulPlayConfig.avatar)
            
            logger.info("Successfully reconnected to Pokemon Showdown")
            
            # Check for ongoing battle after reconnection
            ongoing_battle = await check_for_ongoing_battle(ps_websocket_client)
            if ongoing_battle:
                winner = await resume_battle(ps_websocket_client, ongoing_battle)
                logger.info(f"Battle resumption completed. Winner: {winner}")
            
            return True
            
        except Exception as e:
            logger.error(f"Reconnection attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                logger.error("Max reconnection attempts reached. Bot will exit.")
                return False
    
    return False


async def run_single_battle_with_monitoring(ps_websocket_client, original_pokedex, original_move_json):
    """Run a single battle with state monitoring for graceful shutdown"""
    team_file_name = "None"
    team_dict = None
    
    # Check for shutdown request before starting battle
    if bot_state.should_shutdown():
        return None, team_file_name
    
    if FoulPlayConfig.requires_team():
        team_packed, team_dict, team_file_name = load_team(FoulPlayConfig.team_name)
        await ps_websocket_client.update_team(team_packed)
    else:
        await ps_websocket_client.update_team("None")

    # Check for shutdown request again
    if bot_state.should_shutdown():
        return None, team_file_name

    if FoulPlayConfig.bot_mode == BotModes.challenge_user:
        await ps_websocket_client.challenge_user(
            FoulPlayConfig.user_to_challenge,
            FoulPlayConfig.pokemon_format,
        )
    elif FoulPlayConfig.bot_mode == BotModes.accept_challenge:
        await ps_websocket_client.accept_challenge(
            FoulPlayConfig.pokemon_format, FoulPlayConfig.room_name
        )
    elif FoulPlayConfig.bot_mode == BotModes.search_ladder:
        await ps_websocket_client.search_for_match(FoulPlayConfig.pokemon_format)
    else:
        raise ValueError("Invalid Bot Mode: {}".format(FoulPlayConfig.bot_mode))

    # Mark that we're starting a battle
    bot_state.set_battle_state(True)
    
    try:
        winner = await pokemon_battle_with_monitoring(
            ps_websocket_client, FoulPlayConfig.pokemon_format, team_dict
        )
    finally:
        # Mark that battle is finished
        bot_state.set_battle_state(False)
    
    check_dictionaries_are_unmodified(original_pokedex, original_move_json)
    
    return winner, team_file_name


async def pokemon_battle_with_monitoring(ps_websocket_client, pokemon_battle_type, team_dict):
    """Modified pokemon_battle function that respects shutdown requests"""
    from fp.run_battle import start_battle, battle_is_finished
    from constants import WIN_STRING, TIE_STRING, CHAT_STRING
    from fp.battle_modifier import async_update_battle
    from fp.run_battle import async_pick_move
    
    battle = await start_battle(ps_websocket_client, pokemon_battle_type, team_dict)
    bot_state.set_battle_state(True, battle.battle_tag)
    
    while True:
        # Check for shutdown during battle
        if bot_state.shutdown_requested:
            battle_info = bot_state.get_battle_info()
            logger.info(f"Shutdown requested during battle. Battle duration: {battle_info['battle_duration']:.1f}s")
            # Continue playing but log the request
        
        msg = await ps_websocket_client.receive_message()
        
        if battle_is_finished(battle.battle_tag, msg):
            winner = (
                msg.split(WIN_STRING)[-1].split("\n")[0].strip()
                if WIN_STRING in msg
                else None
            )
            logger.info("Winner: {}".format(winner))
            await ps_websocket_client.send_message(battle.battle_tag, ["gg"])
            
            if FoulPlayConfig.save_replay.name == "always" or (
                FoulPlayConfig.save_replay.name == "on_loss"
                and winner != FoulPlayConfig.username
            ):
                await ps_websocket_client.save_replay(battle.battle_tag)
            
            await ps_websocket_client.leave_battle(battle.battle_tag)
            return winner
        else:
            action_required = await async_update_battle(battle, msg)
            if action_required and not battle.wait:
                best_move = await async_pick_move(battle)
                await ps_websocket_client.send_message(battle.battle_tag, best_move)


async def run_foul_play():
    FoulPlayConfig.configure()
    init_logging(FoulPlayConfig.log_level, FoulPlayConfig.log_to_file)
    apply_mods(FoulPlayConfig.pokemon_format)

    original_pokedex = deepcopy(pokedex)
    original_move_json = deepcopy(all_move_json)

    ps_websocket_client = await PSWebsocketClient.create(
        FoulPlayConfig.username, FoulPlayConfig.password, FoulPlayConfig.websocket_uri
    )

    FoulPlayConfig.user_id = await ps_websocket_client.login()

    if FoulPlayConfig.avatar is not None:
        await ps_websocket_client.avatar(FoulPlayConfig.avatar)

    battles_run = 0
    wins = 0
    losses = 0
    consecutive_errors = 0
    max_consecutive_errors = 10
    
    start_time = time.time()
    
    logger.info(f"Starting Foul Play bot in {'continuous' if FoulPlayConfig.keep_alive else 'limited'} mode")
    if FoulPlayConfig.keep_alive:
        logger.info(f"Bot will run continuously. Use Ctrl+C to stop gracefully.")
        if FoulPlayConfig.battle_delay > 0:
            logger.info(f"Delay between battles: {FoulPlayConfig.battle_delay} seconds")
    else:
        logger.info(f"Bot will run {FoulPlayConfig.run_count} battle(s) then exit")
    
    logger.info("Enhanced features enabled:")
    logger.info("- Graceful shutdown: Bot will finish current battle before stopping")
    logger.info("- Battle resumption: Bot will attempt to resume battles after reconnection")
    
    try:
        while True:
            try:
                # Check for shutdown before starting new battle
                if bot_state.should_shutdown():
                    logger.info("Graceful shutdown initiated.")
                    break
                
                winner, team_file_name = await run_single_battle_with_monitoring(
                    ps_websocket_client, original_pokedex, original_move_json
                )
                
                # If battle was skipped due to shutdown, break
                if winner is None and bot_state.should_shutdown():
                    break
                
                # Reset consecutive errors on successful battle
                consecutive_errors = 0
                
                if winner == FoulPlayConfig.username:
                    wins += 1
                    logger.info("Won with team: {}".format(team_file_name))
                elif winner is not None:
                    losses += 1
                    logger.info("Lost with team: {}".format(team_file_name))
                else:
                    logger.info("Battle result unclear or forfeited")

                if winner is not None:  # Only count completed battles
                    battles_run += 1
                    
                runtime = time.time() - start_time
                win_rate = (wins / battles_run * 100) if battles_run > 0 else 0
                
                logger.info(f"W: {wins}\tL: {losses}\tWin Rate: {win_rate:.1f}%\tBattles: {battles_run}\tRuntime: {runtime/3600:.1f}h")
                
                # Check if we should exit (non-keep-alive mode)
                if not FoulPlayConfig.keep_alive and battles_run >= FoulPlayConfig.run_count:
                    logger.info(f"Completed {FoulPlayConfig.run_count} battles. Exiting.")
                    break
                
                # Check for shutdown before delay
                if bot_state.should_shutdown():
                    logger.info("Graceful shutdown initiated.")
                    break
                
                # Add delay between battles if configured
                if FoulPlayConfig.battle_delay > 0:
                    logger.info(f"Waiting {FoulPlayConfig.battle_delay} seconds before next battle...")
                    for i in range(FoulPlayConfig.battle_delay):
                        if bot_state.should_shutdown():
                            logger.info("Graceful shutdown initiated during delay.")
                            break
                        await asyncio.sleep(1)
                    
                    if bot_state.should_shutdown():
                        break
                
            except (ConnectionError, OSError, asyncio.TimeoutError) as e:
                consecutive_errors += 1
                logger.error(f"Connection error (#{consecutive_errors}): {e}")
                
                if consecutive_errors >= max_consecutive_errors:
                    logger.error(f"Too many consecutive errors ({consecutive_errors}). Exiting.")
                    break
                
                # Try to recover connection
                if not await handle_disconnection_recovery(ps_websocket_client):
                    logger.error("Failed to recover connection. Exiting.")
                    break
                    
            except KeyboardInterrupt:
                logger.info("Received interrupt signal. Gracefully shutting down...")
                bot_state.request_shutdown()
                if not bot_state.in_battle:
                    break
                
            except Exception as e:
                consecutive_errors += 1
                logger.error(f"Unexpected error in battle loop: {e}")
                logger.debug(traceback.format_exc())
                
                if consecutive_errors >= max_consecutive_errors:
                    logger.error(f"Too many consecutive errors ({consecutive_errors}). Exiting.")
                    break
                
                # Wait a bit before retrying on unexpected errors
                await asyncio.sleep(5)
    
    except KeyboardInterrupt:
        logger.info("Received interrupt signal. Gracefully shutting down...")
        bot_state.request_shutdown()
    
    finally:
        # Final statistics
        runtime = time.time() - start_time
        win_rate = (wins / battles_run * 100) if battles_run > 0 else 0
        logger.info("=" * 50)
        logger.info("FINAL STATISTICS")
        logger.info(f"Total Battles: {battles_run}")
        logger.info(f"Wins: {wins} | Losses: {losses}")
        logger.info(f"Win Rate: {win_rate:.1f}%")
        logger.info(f"Total Runtime: {runtime/3600:.2f} hours")
        if battles_run > 0:
            logger.info(f"Average time per battle: {runtime/battles_run:.1f} seconds")
        logger.info("=" * 50)
        
        try:
            await ps_websocket_client.close()
        except Exception as e:
            logger.debug(f"Error closing websocket: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(run_foul_play())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
    except Exception:
        logger.error(traceback.format_exc())
        raise