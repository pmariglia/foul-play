import logging
import random
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy

from fp.battle import Battle, Pokemon, Battler
from config import FoulPlayConfig
from .helpers import (
    calculate_opponent_team_preview_preferences,
    get_result_from_mcts,
    select_move_from_mcts_results,
)
from .standard_battles import prepare_battles, sample_mega_evolution, sample_pokemon

from fp.search.poke_engine_helpers import battle_to_poke_engine_state

logger = logging.getLogger(__name__)


def sample_pkmn_to_remove(battler: Battler, affinities: dict[str, float]):
    can_mega_evo = [k for k in battler.possible_mega_evolutions().keys()]
    pkmn_list = battler.reserve
    pkmn_to_sample_from = (
        # unrevealed mega. A mega would've been sampled already
        [p for p in pkmn_list if not p.revealed and p.name in can_mega_evo]
        # all unrevealed pokemon
        or [p for p in pkmn_list if not p.revealed]
    )
    weights = [1 / affinities[p.name] for p in pkmn_to_sample_from]
    return random.choices(pkmn_to_sample_from, weights=weights, k=1)[0]


def prepare_post_team_preview_bss_battles(
    battle: Battle, num_battles: int
) -> list[(Battle, float)]:
    sampled_battles = []
    for index in range(num_battles):
        logger.info("Sampling battle {}".format(index))
        battle_copy = deepcopy(battle)
        # for later: right here we should force-keep at least 1 mega evolution
        # and so some other intelligent sampling
        if battle_copy.mega_evolve_possible():
            sample_mega_evolution(battle_copy.opponent, index)

        while len(battle_copy.opponent.reserve) > 2:
            pkmn = sample_pkmn_to_remove(
                battle_copy.opponent, battle.opponent_team_preview_affinities
            )
            battle_copy.opponent.reserve.remove(pkmn)
        assert len(battle_copy.opponent.reserve) == 2

        sample_pokemon(battle_copy.opponent.active)
        for pkmn in filter(lambda x: x.is_alive(), battle_copy.opponent.reserve):
            sample_pokemon(pkmn)
        battle_copy.opponent.lock_moves()
        sampled_battles.append((battle_copy, 1 / num_battles))

    return sampled_battles


def bss_team_preview(battle: Battle) -> (str, dict[str, float]):
    battle = deepcopy(battle)
    if battle.team_preview:
        battle.user.active = battle.user.reserve.pop(0)
        battle.opponent.active = battle.opponent.reserve.pop(0)

    num_battles = FoulPlayConfig.parallelism * 2
    search_time_per_battle = FoulPlayConfig.search_time_ms

    battles = prepare_battles(battle, num_battles)

    logger.info("Searching for a move using MCTS...")
    logger.info(
        "Sampling {} battles at {}ms each".format(num_battles, search_time_per_battle)
    )
    with ProcessPoolExecutor(max_workers=FoulPlayConfig.parallelism) as executor:
        futures = []
        for index, (b, chance) in enumerate(battles):
            fut = executor.submit(
                get_result_from_mcts,
                battle_to_poke_engine_state(b).to_string(),
                search_time_per_battle,
                index,
                FoulPlayConfig.search_threads,
            )
            futures.append((fut, chance, index))

    mcts_results = [(fut.result(), chance, index) for (fut, chance, index) in futures]
    opponent_team_preview_affinities = calculate_opponent_team_preview_preferences(
        [(i[0].total_visits, i[0].side_two) for i in mcts_results]
    )
    choice = select_move_from_mcts_results(mcts_results)
    logger.info("Choice: {}".format(choice))
    return choice, opponent_team_preview_affinities
