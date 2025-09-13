import asyncio
import json
import logging
import traceback
from copy import deepcopy

import constants
from config import FoulPlayConfig, init_logging

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


async def run_foul_play():
    FoulPlayConfig.configure()
    init_logging(FoulPlayConfig.log_level, FoulPlayConfig.log_to_file)
    apply_mods(FoulPlayConfig.pokemon_mode)

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
    while True:
        team_export, team_dict, file_name = load_team(FoulPlayConfig.team)
        if FoulPlayConfig.bot_mode == constants.CHALLENGE_USER:
            await ps_websocket_client.challenge_user(
                FoulPlayConfig.user_to_challenge,
                FoulPlayConfig.pokemon_mode,
                team_export,
            )
        elif FoulPlayConfig.bot_mode == constants.ACCEPT_CHALLENGE:
            await ps_websocket_client.accept_challenge(
                FoulPlayConfig.pokemon_mode, team_export, FoulPlayConfig.room_name
            )
        elif FoulPlayConfig.bot_mode == constants.SEARCH_LADDER:
            await ps_websocket_client.search_for_match(
                FoulPlayConfig.pokemon_mode, team_export
            )
        else:
            raise ValueError("Invalid Bot Mode: {}".format(FoulPlayConfig.bot_mode))

        winner = await pokemon_battle(
            ps_websocket_client, FoulPlayConfig.pokemon_mode, team_dict
        )
        if winner == FoulPlayConfig.username:
            wins += 1
            logger.info("Won with team: {}".format(file_name))
        else:
            losses += 1
            logger.info("Lost with team: {}".format(file_name))

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
