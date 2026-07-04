import asyncio
import concurrent.futures
import json
import logging
from copy import copy, deepcopy

from fp import constants
from fp.battle.state import Battle, Battler, LastUsedMove, Pokemon
from fp.config import FoulPlayConfig
from fp.search.main import find_best_move
from fp.websocket_client import PSWebsocketClient

logger = logging.getLogger(__name__)


class BattleMode:
    requires_team: bool

    async def start_battle(
        self, ps_websocket_client: PSWebsocketClient, pokemon_battle_type, team_dict
    ) -> Battle:
        raise NotImplementedError

    def search_params(self, battle) -> tuple[int, int]:
        raise NotImplementedError

    def prepare_battles(self, battle, num_battles) -> list[tuple[Battle, float]]:
        raise NotImplementedError

    def get_all_remaining_sets(self, pkmn) -> list:
        raise ValueError("Only random battles are supported")

    def dataset_possibilities(self, battle) -> tuple[list, list | None, bool]:
        raise NotImplementedError

    def assume_spread_for_speed_check(self, battle, battle_copy):
        raise NotImplementedError

    def add_revealed_pokemon(self, battle, pkmn):
        pass

    def check_zoroark_from_move(
        self, battle, side, pkmn, move_name, split_msg, zoroark_from_reserves
    ) -> Pokemon:
        return pkmn

    def check_zoroark_from_immune(self, battle, side, pkmn, zoroark_from_reserves):
        pass

    async def start_battle_common(
        self, ps_websocket_client: PSWebsocketClient, pokemon_battle_type
    ):
        battle_tag, opponent_name = await get_battle_tag_and_opponent(
            ps_websocket_client
        )
        if FoulPlayConfig.log_to_file:
            FoulPlayConfig.file_log_handler.do_rollover(
                "{}_{}.log".format(battle_tag, opponent_name)
            )

        battle = Battle(battle_tag)
        battle.opponent.account_name = opponent_name
        battle.pokemon_format = pokemon_battle_type
        battle.generation = battle.format_spec.generation
        battle.battle_type = battle.format_spec.battle_type
        battle.mode = self

        # wait until the opponent's identifier is received. This will be `p1` or `p2`.
        #
        # e.g.
        # '>battle-gen9randombattle-44733
        # |player|p1|OpponentName|2|'
        while True:
            msg = await ps_websocket_client.receive_message()
            if "|player|" in msg and battle.opponent.account_name in msg:
                battle.opponent.name = msg.split("|")[2]
                battle.user.name = constants.ID_LOOKUP[battle.opponent.name]
                break

        return battle, msg


def format_decision(battle, decision):
    # Formats a decision for communication with Pokemon-Showdown
    # If the move can be used as a Z-Move, it will be

    if decision.startswith(constants.SWITCH_STRING + " "):
        switch_pokemon = decision.split("switch ")[-1]
        for pkmn in battle.user.reserve:
            if pkmn.name == switch_pokemon:
                message = "/switch {}".format(pkmn.index)
                break
        else:
            raise ValueError("Tried to switch to: {}".format(switch_pokemon))
    else:
        tera = False
        mega = False
        if decision.endswith("-tera"):
            decision = decision.replace("-tera", "")
            tera = True
        elif decision.endswith("-mega"):
            decision = decision.replace("-mega", "")
            mega = True
        message = "/choose move {}".format(decision)

        if battle.user.active.can_mega_evo and mega:
            message = "{} {}".format(message, constants.MEGA)
        elif battle.user.active.can_ultra_burst:
            message = "{} {}".format(message, constants.ULTRA_BURST)

        # only dynamax on last pokemon
        if battle.user.active.can_dynamax and all(
            p.hp == 0 for p in battle.user.reserve
        ):
            message = "{} {}".format(message, constants.DYNAMAX)

        if tera:
            message = "{} {}".format(message, constants.TERASTALLIZE)

        if battle.user.active.get_move(decision).can_z:
            message = "{} {}".format(message, constants.ZMOVE)

    return [message, str(battle.rqid)]


async def async_pick_move(battle):
    battle_copy = deepcopy(battle)
    if not battle_copy.team_preview:
        battle_copy.user.update_from_request_json(battle_copy.request_json)

    loop = asyncio.get_event_loop()
    with concurrent.futures.ThreadPoolExecutor() as pool:
        best_move = await loop.run_in_executor(pool, find_best_move, battle_copy)
    battle.user.last_selected_move = LastUsedMove(
        battle.user.active.name,
        best_move.removesuffix("-tera").removesuffix("-mega"),
        battle.turn,
    )
    return format_decision(battle_copy, best_move)


async def handle_team_preview(battle, ps_websocket_client):
    battle_copy = deepcopy(battle)
    battle_copy.user.active = Pokemon.get_dummy()
    battle_copy.opponent.active = Pokemon.get_dummy()
    battle_copy.team_preview = True

    best_move = await async_pick_move(battle_copy)

    # because we copied the battle before sending it in, we need to update the last selected move here
    pkmn_name = battle.user.reserve[int(best_move[0].split()[1]) - 1].name
    battle.user.last_selected_move = LastUsedMove(
        "teampreview", "switch {}".format(pkmn_name), battle.turn
    )

    size_of_team = len(battle.user.reserve) + 1
    team_list_indexes = list(range(1, size_of_team))
    choice_digit = int(best_move[0].split()[-1])

    team_list_indexes.remove(choice_digit)
    message = [
        "/team {}{}|{}".format(
            choice_digit, "".join(str(x) for x in team_list_indexes), battle.rqid
        )
    ]

    await ps_websocket_client.send_message(battle.battle_tag, message)


async def get_battle_tag_and_opponent(ps_websocket_client: PSWebsocketClient):
    while True:
        msg = await ps_websocket_client.receive_message()
        split_msg = msg.split("|")
        first_msg = split_msg[0]
        if "battle" in first_msg:
            battle_tag = first_msg.replace(">", "").strip()
            user_name = FoulPlayConfig.username
            opponent_name = (
                split_msg[4].replace(user_name, "").replace("vs.", "").strip()
            )
            logger.info("Initialized {} against: {}".format(battle_tag, opponent_name))
            return battle_tag, opponent_name


async def get_first_request_json(
    ps_websocket_client: PSWebsocketClient, battle: Battle
):
    while True:
        msg = await ps_websocket_client.receive_message()
        msg_split = msg.split("|")
        if msg_split[1].strip() == "request" and msg_split[2].strip():
            user_json = json.loads(msg_split[2].strip("'"))
            battle.request_json = user_json
            battle.user.initialize_first_turn_user_from_json(user_json)
            battle.rqid = user_json[constants.RQID]
            return


def _switch_active_with_zoroark_from_reserves(
    opponent_side: Battler, zoroark_from_reserves: Pokemon
):
    """
    This is called when we are 100% sure that the opponent's active pkmn is a zoroark
    This swaps the active pkmn with the zoroark from the reserves

    Assumptions:
        - The `zoroark_from_reserves` MUST be in `opponent_side.reserve`
    """
    pkmn = opponent_side.active

    # any moves used by this pkmn since switching in need to be removed because we cannot guarantee that they
    # belong to this pkmn
    for mv in pkmn.moves_used_since_switch_in:
        logger.info(
            "Removing {} from {}'s moves because it is {}".format(
                mv, pkmn.name, zoroark_from_reserves.name
            )
        )
        pkmn.remove_move(mv)
        if zoroark_from_reserves.get_move(mv) is None:
            zoroark_from_reserves.add_move(mv)

    # set attributes on zoroark that were on the pokemon that we thought was zoroark
    # and clear those attributes from the pokemon that we thought was zoroark
    pkmn_hp_percent = float(pkmn.hp) / pkmn.max_hp
    zoroark_from_reserves.hp = zoroark_from_reserves.max_hp * pkmn_hp_percent
    zoroark_from_reserves.boosts = copy(pkmn.boosts)
    zoroark_from_reserves.status = pkmn.status
    zoroark_from_reserves.volatile_statuses = copy(pkmn.volatile_statuses)
    zoroark_from_reserves.terastallized = pkmn.terastallized
    zoroark_from_reserves.tera_type = pkmn.tera_type
    pkmn.boosts.clear()
    pkmn.status = None
    pkmn.volatile_statuses.clear()
    pkmn.volatile_status_durations.clear()

    if pkmn.terastallized:
        pkmn.terastallized = False
        pkmn.tera_type = None

    zoroark_from_reserves.zoroark_disguised_as = pkmn.name

    # swap the pkmn places
    opponent_side.reserve.append(pkmn)
    opponent_side.active = zoroark_from_reserves
    opponent_side.reserve.remove(zoroark_from_reserves)
