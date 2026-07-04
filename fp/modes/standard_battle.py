import logging

from fp import constants
from fp.battle.inference import is_opponent
from fp.battle.protocol import process_battle_updates
from fp.battle.helpers import maximum_ev
from fp.config import FoulPlayConfig
from fp.data.pkmn_sets import SmogonSets, TeamDatasets
from fp.modes.base import (
    BattleMode,
    _switch_active_with_zoroark_from_reserves,
    async_pick_move,
    get_first_request_json,
    handle_team_preview,
)
from fp.search import standard_battles
from fp.websocket_client import PSWebsocketClient

logger = logging.getLogger(__name__)


class StandardBattleMode(BattleMode):
    requires_team = True

    async def start_battle(
        self, ps_websocket_client: PSWebsocketClient, pokemon_battle_type, team_dict
    ):
        battle, msg = await self.start_battle_common(
            ps_websocket_client, pokemon_battle_type
        )
        battle.user.team_dict = team_dict

        if not battle.gen.has_team_preview:
            while True:
                if constants.START_STRING in msg:
                    battle.started = True

                    # hold onto some messages to apply after we get the request JSON
                    # omit the bot's switch-in message because we won't need that
                    # parsing the request JSON will set the bot's active pkmn
                    battle.msg_list = [
                        m
                        for m in msg.split(constants.START_STRING)[1]
                        .strip()
                        .split("\n")
                        if not (m.startswith("|switch|{}".format(battle.user.name)))
                    ]
                    break
                msg = await ps_websocket_client.receive_message()

            await get_first_request_json(ps_websocket_client, battle)

            unique_pkmn_names = set(
                [p.name for p in battle.user.reserve] + [battle.user.active.name]
            )
            SmogonSets.initialize(
                FoulPlayConfig.smogon_stats or pokemon_battle_type, unique_pkmn_names
            )
            TeamDatasets.initialize(pokemon_battle_type, unique_pkmn_names)

            # apply the messages that were held onto
            process_battle_updates(battle)

            best_move = await async_pick_move(battle)
            await ps_websocket_client.send_message(battle.battle_tag, best_move)

        else:
            while constants.START_TEAM_PREVIEW not in msg:
                msg = await ps_websocket_client.receive_message()

            preview_string_lines = msg.split(constants.START_TEAM_PREVIEW)[-1].split(
                "\n"
            )

            opponent_pokemon = []
            for line in preview_string_lines:
                if not line:
                    continue

                split_line = line.split("|")
                if (
                    split_line[1] == constants.TEAM_PREVIEW_POKE
                    and split_line[2].strip() == battle.opponent.name
                ):
                    opponent_pokemon.append(split_line[3])

            await get_first_request_json(ps_websocket_client, battle)
            battle.initialize_team_preview(opponent_pokemon, pokemon_battle_type)
            battle.during_team_preview()

            unique_pkmn_names = set(
                p.name for p in battle.opponent.reserve + battle.user.reserve
            )

            self.initialize_team_preview_datasets(
                pokemon_battle_type, unique_pkmn_names, msg
            )

            await handle_team_preview(battle, ps_websocket_client)

        return battle

    def initialize_team_preview_datasets(
        self, pokemon_battle_type, unique_pkmn_names, msg
    ):
        SmogonSets.initialize(
            FoulPlayConfig.smogon_stats or pokemon_battle_type, unique_pkmn_names
        )
        TeamDatasets.initialize(pokemon_battle_type, unique_pkmn_names)

    def add_revealed_pokemon(self, battle, pkmn):
        # for standard battles gen4 and lower
        # we want to add the new pokemon to the datasets as they are revealed
        # because there is no teampreview
        if not battle.gen.has_team_preview:
            SmogonSets.add_new_pokemon(pkmn.name)
            TeamDatasets.add_new_pokemon(pkmn.name)
            logger.info("Adding new pokemon '{}' to the datasets".format(pkmn.name))

    def search_params(self, battle):
        opponent_active_num_moves = len(battle.opponent.active.moves)
        in_time_pressure = (
            battle.time_remaining is not None and battle.time_remaining <= 60
        )

        if (
            battle.team_preview
            or (battle.opponent.active.hp > 0 and opponent_active_num_moves == 0)
            or opponent_active_num_moves < 3
        ):
            num_battles_multiplier = 1 if in_time_pressure else 2
            return FoulPlayConfig.parallelism * num_battles_multiplier, int(
                FoulPlayConfig.search_time_ms
            )
        else:
            return FoulPlayConfig.parallelism, FoulPlayConfig.search_time_ms

    def prepare_battles(self, battle, num_battles):
        return standard_battles.prepare_battles(battle, num_battles)

    def check_zoroark_from_move(
        self, battle, side, pkmn, move_name, split_msg, zoroark_from_reserves
    ):
        # in battle factory we can deduce that there is a zoroark in front of us
        # if we see a move that is not in the known moveset and a zoroark is in the reserves
        if (
            is_opponent(battle, split_msg)
            and zoroark_from_reserves is not None
            and "transform" not in pkmn.volatile_statuses
            and move_name not in TeamDatasets.get_all_possible_moves(pkmn)
            and move_name in TeamDatasets.get_all_possible_moves(zoroark_from_reserves)
            and "from" not in split_msg[-1]
        ):
            logger.info(
                "{} using {} means it is {}".format(
                    pkmn.name, move_name, zoroark_from_reserves.name
                )
            )
            _switch_active_with_zoroark_from_reserves(side, zoroark_from_reserves)

            # the rest of this function uses `pkmn`, so we need to set it to the correct pkmn
            pkmn = zoroark_from_reserves

        return pkmn

    def assume_spread_for_speed_check(self, battle, battle_copy):
        if battle.trick_room:
            battle_copy.opponent.active.set_spread(
                "quiet", "0,0,0,0,0,0"
            )  # assume as slow as possible in trickroom
        else:
            battle_copy.opponent.active.set_spread(
                "jolly", f"0,0,0,0,0,{maximum_ev()}"
            )  # assume as fast as possible

    def dataset_possibilities(self, battle):
        possibilites = TeamDatasets.get_pkmn_sets_from_pkmn_name(battle.opponent.active)
        smogon_possibilities = SmogonSets.get_pkmn_sets_from_pkmn_name(
            battle.opponent.active
        )
        return possibilites, smogon_possibilities, True
