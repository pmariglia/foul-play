import asyncio
import json
import logging
import traceback
from copy import deepcopy

from config import FoulPlayConfig, init_logging, BotModes

from teams import load_team, TeamListIterator
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

    team_iterator = (
        None
        if FoulPlayConfig.team_list is None
        else TeamListIterator(FoulPlayConfig.team_list)
    )
    battles_run = 0
    wins = 0
    losses = 0
    team_file_name = "None"
    team_dict = None
    while True:
        if FoulPlayConfig.requires_team():
            team_name = (
                team_iterator.get_next_team()
                if team_iterator is not None
                else FoulPlayConfig.team_name
            )
            team_packed, team_dict, team_file_name = load_team(team_name)
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
        if winner == FoulPlayConfig.username:
            wins += 1
            logger.info("Won with team: {}".format(team_file_name))
        else:
            losses += 1
            logger.info("Lost with team: {}".format(team_file_name))

        logger.info("W: {}\tL: {}".format(wins, losses))
        check_dictionaries_are_unmodified(original_pokedex, original_move_json)

        battles_run += 1
        if battles_run >= FoulPlayConfig.run_count:
            break
    await ps_websocket_client.close()


if __name__ == "__main__":
    try:
        asyncio.run(run_foul_play())
    except Exception:
        logger.error(traceback.format_exc())
        raise
