import logging

from fp import constants
from fp.battle.inference import is_opponent
from fp.battle.protocol import process_battle_updates
from fp.battle.helpers import random_battles_evs, type_effectiveness_modifier
from fp.battle.state import Pokemon
from fp.config import FoulPlayConfig
from fp.data import all_move_json
from fp.data.sets import RandomBattleTeamDatasets
from fp.modes.base import (
    BattleMode,
    _switch_active_with_zoroark_from_reserves,
    async_pick_move,
    get_first_request_json,
)
from fp.search.random_battles import prepare_random_battles
from fp.websocket_client import PSWebsocketClient

logger = logging.getLogger(__name__)


class RandomBattleMode(BattleMode):
    requires_team = False

    def __init__(self):
        self.datasets = RandomBattleTeamDatasets()

    async def start_battle(
        self, ps_websocket_client: PSWebsocketClient, pokemon_battle_type, team_dict
    ):
        battle, msg = await self.start_battle_common(
            ps_websocket_client, pokemon_battle_type
        )
        self.datasets.initialize(battle.format_spec)

        while True:
            if constants.START_STRING in msg:
                battle.started = True

                # hold onto some messages to apply after we get the request JSON
                # omit the bot's switch-in message because we won't need that
                # parsing the request JSON will set the bot's active pkmn
                battle.msg_list = [
                    m
                    for m in msg.split(constants.START_STRING)[1].strip().split("\n")
                    if not (m.startswith("|switch|{}".format(battle.user.name)))
                ]
                break
            msg = await ps_websocket_client.receive_message()

        await get_first_request_json(ps_websocket_client, battle)

        # apply the messages that were held onto
        process_battle_updates(battle)

        best_move = await async_pick_move(battle)
        await ps_websocket_client.send_message(battle.battle_tag, best_move)

        return battle

    def search_params(self, battle):
        revealed_pkmn = len(battle.opponent.reserve)
        if battle.opponent.active is not None:
            revealed_pkmn += 1

        opponent_active_num_moves = len(battle.opponent.active.moves)
        in_time_pressure = (
            battle.time_remaining is not None and battle.time_remaining <= 60
        )

        # it is still quite early in the battle and the pkmn in front of us
        # hasn't revealed any moves: search a lot of battles shallowly
        if (
            revealed_pkmn <= 3
            and battle.opponent.active.hp > 0
            and opponent_active_num_moves == 0
        ):
            num_battles_multiplier = 2 if in_time_pressure else 4
            return FoulPlayConfig.parallelism * num_battles_multiplier, int(
                FoulPlayConfig.search_time_ms // 2
            )

        else:
            num_battles_multiplier = 1 if in_time_pressure else 2
            return FoulPlayConfig.parallelism * num_battles_multiplier, int(
                FoulPlayConfig.search_time_ms
            )

    def prepare_battles(self, battle, num_battles):
        return prepare_random_battles(battle, num_battles)

    def get_all_remaining_sets(self, pkmn):
        return self.datasets.get_all_remaining_sets(pkmn)

    def check_zoroark_from_move(
        self, battle, side, pkmn, move_name, split_msg, zoroark_from_reserves
    ):
        # in randombattles we can deduce that there is a zoroark in front of us
        # if we see a move that is not in the known moveset, even if there is no
        # zoroark is in the reserves
        if (
            is_opponent(battle, split_msg)
            and "transform" not in pkmn.volatile_statuses
            and move_name not in self.datasets.get_all_possible_moves(pkmn)
            and "from" not in split_msg[-1]
        ):
            actual_zoroark = None
            zoroark_hisui = Pokemon("zoroarkhisui", 100)
            zoroark_regular = Pokemon("zoroark", 100)
            if (
                zoroark_from_reserves is not None
                and move_name
                in self.datasets.get_all_possible_moves(zoroark_from_reserves)
            ):
                actual_zoroark = zoroark_from_reserves

            elif (
                battle.gen.has_team_preview
                and zoroark_from_reserves is None
                and move_name in self.datasets.get_all_possible_moves(zoroark_hisui)
            ):
                actual_zoroark = zoroark_hisui
                actual_zoroark.level = self.datasets.predicted_level(actual_zoroark)
                side.reserve.append(actual_zoroark)

            elif (
                battle.gen.has_team_preview
                and zoroark_from_reserves is None
                and move_name in self.datasets.get_all_possible_moves(zoroark_regular)
            ):
                actual_zoroark = zoroark_regular
                actual_zoroark.level = self.datasets.predicted_level(actual_zoroark)
                side.reserve.append(actual_zoroark)

            if actual_zoroark is not None:
                logger.info(
                    "{} using {} means it is {}".format(
                        pkmn.name, move_name, actual_zoroark.name
                    )
                )
                _switch_active_with_zoroark_from_reserves(side, actual_zoroark)

                # the rest of this function uses `pkmn`, so we need to set it to the correct pkmn
                pkmn = actual_zoroark

        return pkmn

    def check_zoroark_from_immune(self, battle, side, pkmn, zoroark_from_reserves):
        # Random Battle: Zoroark may be in the reserves so we need to check the move type
        # that it was immune to
        actual_zoroark = None
        zoroark_hisui = Pokemon("zoroarkhisui", 100)
        zoroark_regular = Pokemon("zoroark", 100)

        # zoroark was in the reserves - just use that one
        if (
            zoroark_from_reserves is not None
            and type_effectiveness_modifier(
                all_move_json[battle.user.last_used_move.move][constants.TYPE],
                zoroark_from_reserves.types,
            )
            == 0
        ):
            actual_zoroark = zoroark_from_reserves

        # hisui zoroark
        elif (
            zoroark_from_reserves is None
            and type_effectiveness_modifier(
                all_move_json[battle.user.last_used_move.move][constants.TYPE],
                zoroark_hisui.types,
            )
            == 0
            and zoroark_hisui.name in self.datasets.pkmn_sets
        ):
            actual_zoroark = zoroark_hisui
            actual_zoroark.level = self.datasets.predicted_level(actual_zoroark)
            side.reserve.append(actual_zoroark)

        # regular zoroark
        elif (
            zoroark_from_reserves is None
            and type_effectiveness_modifier(
                all_move_json[battle.user.last_used_move.move][constants.TYPE],
                zoroark_regular.types,
            )
            == 0
            and zoroark_regular.name in self.datasets.pkmn_sets
        ):
            actual_zoroark = zoroark_regular
            actual_zoroark.level = self.datasets.predicted_level(actual_zoroark)
            side.reserve.append(actual_zoroark)

        # if we found a zoroark from one of those branches
        if actual_zoroark is not None:
            logger.info(
                "{} was immune to {} when it shouldn't be - it is {}".format(
                    pkmn.name,
                    battle.user.last_used_move.move,
                    actual_zoroark.name,
                )
            )
            _switch_active_with_zoroark_from_reserves(side, actual_zoroark)

    def assume_spread_for_speed_check(self, battle, battle_copy):
        evs = ",".join(str(ev) for ev in random_battles_evs())
        battle_copy.opponent.active.set_spread(
            "serious", evs
        )  # random battles have known spreads

    def dataset_possibilities(self, battle):
        possibilites = self.datasets.get_pkmn_sets_from_pkmn_name(
            battle.opponent.active
        )
        return possibilites, None, False
