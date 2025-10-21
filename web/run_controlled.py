import asyncio
import logging
from config import FoulPlayConfig, BotModes
from fp.websocket_client import PSWebsocketClient
from fp.run_battle import pokemon_battle
from teams import load_team
from data.mods.apply_mods import apply_mods
from data import pokedex, all_move_json
from copy import deepcopy

# This module provides a controlled run function used by the web panel
# It reads credentials and settings from bot_manager (passed in) instead of argparse

logger = logging.getLogger(__name__)

async def run_foul_play_controlled(bot_manager):
    # Validate minimal config
    if not bot_manager.username or not bot_manager.password or not bot_manager.websocket_uri:
        raise ValueError('Missing username/password/websocket_uri')
    if not bot_manager.pokemon_format:
        raise ValueError('Missing pokemon_format')
    if not bot_manager.bot_mode:
        bot_manager.bot_mode = 'search_ladder'

    class Dummy:
        pass

    # Patch FoulPlayConfig with values from web panel
    FoulPlayConfig.username = bot_manager.username
    FoulPlayConfig.password = bot_manager.password
    FoulPlayConfig.websocket_uri = bot_manager.websocket_uri
    FoulPlayConfig.pokemon_format = bot_manager.pokemon_format
    FoulPlayConfig.bot_mode = getattr(BotModes, bot_manager.bot_mode)
    FoulPlayConfig.team_name = bot_manager.pokemon_format
    FoulPlayConfig.run_count = 1
    FoulPlayConfig.save_replay = type('X', (), {'name': 'never'})

    apply_mods(FoulPlayConfig.pokemon_format)

    original_pokedex = deepcopy(pokedex)
    original_move_json = deepcopy(all_move_json)

    ps = await PSWebsocketClient.create(FoulPlayConfig.username, FoulPlayConfig.password, FoulPlayConfig.websocket_uri)

    try:
        user_id = await ps.login()
        bot_manager.update_connection(True)
    except Exception:
        bot_manager.update_connection(False)
        raise

    battles = bot_manager.stats['battles_played']
    wins = bot_manager.stats['wins']
    losses = bot_manager.stats['losses']

    try:
        if 'random' in FoulPlayConfig.pokemon_format or 'battlefactory' in FoulPlayConfig.pokemon_format:
            await ps.update_team('None')
        else:
            team_packed, team_dict, team_file_name = load_team(FoulPlayConfig.team_name)
            await ps.update_team(team_packed)

        if FoulPlayConfig.bot_mode == BotModes.challenge_user:
            pass
        elif FoulPlayConfig.bot_mode == BotModes.accept_challenge:
            await ps.accept_challenge(FoulPlayConfig.pokemon_format, None)
        elif FoulPlayConfig.bot_mode == BotModes.search_ladder:
            await ps.search_for_match(FoulPlayConfig.pokemon_format)

        winner = await pokemon_battle(ps, FoulPlayConfig.pokemon_format, None)
        battles += 1
        if winner == FoulPlayConfig.username:
            wins += 1
        else:
            losses += 1
        bot_manager.update_stats(battles_played=battles, wins=wins, losses=losses, current_battle=None)
    finally:
        bot_manager.update_connection(False)
        try:
            await ps.close()
        except Exception:
            pass
