import logging
import random
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy

from fp.battle.state import Battle
from fp.config import FoulPlayConfig

from poke_engine import State as PokeEngineState, monte_carlo_tree_search, MctsResult

from fp.search.poke_engine_helpers import battle_to_poke_engine_state

logger = logging.getLogger(__name__)


def select_move_from_mcts_results(mcts_results: list[(MctsResult, float, int)]) -> str:
    # the engine's search runs CFR: total_score holds each move's weight in the
    # normalized average strategy, which is a mixed strategy to be sampled from
    final_policy = {}
    for mcts_result, sample_chance, index in mcts_results:
        this_policy = max(mcts_result.side_one, key=lambda x: x.total_score)
        logger.info(
            "Policy {}: {} strategy={}% sample_chance_multiplier={}".format(
                index,
                this_policy.move_choice,
                round(100 * this_policy.total_score, 2),
                round(sample_chance, 3),
            )
        )
        for s1_option in mcts_result.side_one:
            final_policy[s1_option.move_choice] = final_policy.get(
                s1_option.move_choice, 0
            ) + (sample_chance * s1_option.total_score)

    final_policy = sorted(final_policy.items(), key=lambda x: x[1], reverse=True)

    # drop the low-probability tail: it is mostly unconverged exploration noise,
    # while genuine mixing keeps moves with comparable weight
    highest_percentage = final_policy[0][1]
    final_policy = [i for i in final_policy if i[1] >= highest_percentage * 0.75]
    logger.info("Considered Choices:")
    for i, policy in enumerate(final_policy):
        logger.info(f"\t{round(policy[1] * 100, 3)}%: {policy[0]}")

    choice = random.choices(final_policy, weights=[p[1] for p in final_policy])[0]
    return choice[0]


def get_result_from_mcts(
    state: str, search_time_ms: int, index: int, threads: int
) -> MctsResult:
    logger.debug("Calling with {} state: {}".format(index, state))
    poke_engine_state = PokeEngineState.from_string(state)

    # threads>1 would route to the threaded DUCT search in the engine;
    # CFR is single-threaded only
    res = monte_carlo_tree_search(poke_engine_state, search_time_ms, threads=1)
    logger.info("Iterations {}: {}".format(index, res.total_visits))
    return res


def find_best_move(battle: Battle) -> str:
    battle = deepcopy(battle)
    if battle.team_preview:
        battle.user.active = battle.user.reserve.pop(0)
        battle.opponent.active = battle.opponent.reserve.pop(0)

    num_battles, search_time_per_battle = battle.mode.search_params(battle)
    battles = battle.mode.prepare_battles(battle, num_battles)

    logger.info("Searching for a move using MCTS...")
    logger.info(
        "Sampling {} battles at {}ms each".format(num_battles, search_time_per_battle)
    )
    with ProcessPoolExecutor(max_workers=FoulPlayConfig.parallelism) as executor:
        futures = []
        for index, (b, chance) in enumerate(battles):
            state = battle_to_poke_engine_state(b).to_string()
            logger.debug("Calling with {} state: {}".format(index, state))
            fut = executor.submit(
                get_result_from_mcts,
                state,
                search_time_per_battle,
                index,
                FoulPlayConfig.search_threads,
            )
            futures.append((fut, chance, index))

    mcts_results = []
    for fut, chance, index in futures:
        res = fut.result()
        logger.info("Iterations {}: {}".format(index, res.total_visits))
        mcts_results.append((res, chance, index))

    choice = select_move_from_mcts_results(mcts_results)
    logger.info("Choice: {}".format(choice))
    return choice
