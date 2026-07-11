import asyncio
import concurrent.futures
import logging
from copy import deepcopy

from fp.battle.state import LastUsedMove, Pokemon
from fp.config import FoulPlayConfig
from fp.modes.standard_battle import StandardBattleMode
from fp.search import standard_battles
from fp.search.bss import bss_team_preview, prepare_post_team_preview_bss_battles

logger = logging.getLogger(__name__)


class BSSMode(StandardBattleMode):
    async def handle_team_preview(self, battle, ps_websocket_client):
        battle_copy = deepcopy(battle)
        battle_copy.user.active = Pokemon.get_dummy()
        battle_copy.opponent.active = Pokemon.get_dummy()
        battle_copy.team_preview = True

        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            (best_move, opponent_affinities) = await loop.run_in_executor(
                pool, bss_team_preview, battle_copy
            )

        battle.opponent_team_preview_affinities = opponent_affinities

        lead, reserve_1, reserve_2 = best_move.split(",")

        team_index_string = ""
        team_dont_bring_string = ""
        lead_pkmn = battle.user.find_pokemon_in_reserves(lead)
        bring_names = [
            battle.user.find_pokemon_in_reserves(reserve_1).name,
            battle.user.find_pokemon_in_reserves(reserve_2).name,
        ]

        for pkmn in battle.user.reserve:
            if pkmn.name in bring_names:
                team_index_string = f"{pkmn.index}{team_index_string}"
                logger.debug(f"Bringing {pkmn.name}")
            elif pkmn.name == lead_pkmn.name:
                logger.debug(f"Leading with {pkmn.name}")
            else:
                team_dont_bring_string = f"{team_dont_bring_string}{pkmn.index}"
                logger.debug(f"Leaving behind {pkmn.name}")
                pkmn.hp = 0
                pkmn.name = "none"

        message = [
            "/team {}{}{}|{}".format(
                lead_pkmn.index, team_index_string, team_dont_bring_string, battle.rqid
            )
        ]
        battle.user.last_selected_move = LastUsedMove(
            "teampreview", f"switch {lead_pkmn.name}", battle.turn
        )

        logger.info(f"Team: {lead}, [{reserve_1}, {reserve_2}]")
        await ps_websocket_client.send_message(battle.battle_tag, message)

    def prepare_battles(self, battle, num_battles):
        if battle.team_preview:
            return standard_battles.prepare_battles(battle, num_battles)
        return prepare_post_team_preview_bss_battles(battle, num_battles)

    def search_params(self, battle):
        # even after team preview the opponent's brought 3 are partly hidden,
        # so sample more battles than a standard singles battle
        return FoulPlayConfig.parallelism * 2, FoulPlayConfig.search_time_ms
