import asyncio
import json
import logging
import traceback
import time
from copy import deepcopy

from config import FoulPlayConfig, init_logging, BotModes

from teams import load_team
from fp.run_battle import pokemon_battle
from fp.websocket_client import PSWebsocketClient

from data import all_move_json
from data import pokedex
from data.mods.apply_mods import apply_mods


logger = logging.getLogger(__name__)


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
            return True
            
        except Exception as e:
            logger.error(f"Reconnection attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                logger.error("Max reconnection attempts reached. Bot will exit.")
                return False
    
    return False


async def run_single_battle(ps_websocket_client, original_pokedex, original_move_json):
    """Run a single battle and return the result"""
    team_file_name = "None"
    team_dict = None
    
    if FoulPlayConfig.requires_team():
        team_packed, team_dict, team_file_name = load_team(FoulPlayConfig.team_name)
        await ps_websocket_client.update_team(team_packed)
    else:
        await ps_websocket_client.update_team("None")

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

    winner = await pokemon_battle(
        ps_websocket_client, FoulPlayConfig.pokemon_format, team_dict
    )
    
    check_dictionaries_are_unmodified(original_pokedex, original_move_json)
    
    return winner, team_file_name


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
        logger.info(f"Bot will run continuously. Use Ctrl+C to stop.")
        if FoulPlayConfig.battle_delay > 0:
            logger.info(f"Delay between battles: {FoulPlayConfig.battle_delay} seconds")
    else:
        logger.info(f"Bot will run {FoulPlayConfig.run_count} battle(s) then exit")
    
    try:
        while True:
            try:
                winner, team_file_name = await run_single_battle(
                    ps_websocket_client, original_pokedex, original_move_json
                )
                
                # Reset consecutive errors on successful battle
                consecutive_errors = 0
                
                if winner == FoulPlayConfig.username:
                    wins += 1
                    logger.info("Won with team: {}".format(team_file_name))
                else:
                    losses += 1
                    logger.info("Lost with team: {}".format(team_file_name))

                battles_run += 1
                runtime = time.time() - start_time
                win_rate = (wins / battles_run * 100) if battles_run > 0 else 0
                
                logger.info(f"W: {wins}\tL: {losses}\tWin Rate: {win_rate:.1f}%\tBattles: {battles_run}\tRuntime: {runtime/3600:.1f}h")
                
                # Check if we should exit (non-keep-alive mode)
                if not FoulPlayConfig.keep_alive and battles_run >= FoulPlayConfig.run_count:
                    logger.info(f"Completed {FoulPlayConfig.run_count} battles. Exiting.")
                    break
                
                # Add delay between battles if configured
                if FoulPlayConfig.battle_delay > 0:
                    logger.info(f"Waiting {FoulPlayConfig.battle_delay} seconds before next battle...")
                    await asyncio.sleep(FoulPlayConfig.battle_delay)
                
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