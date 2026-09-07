import logging
import math
import random
from copy import deepcopy

from fp.battle.state import Battle
from fp.config import FoulPlayConfig

from poke_engine import (
    State as PokeEngineState,
    monte_carlo_tree_search,
    MctsResult,
    CfrResult,
    cfr_search,
)

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


def select_move_from_cfr_result(result: CfrResult) -> str:
    policy = sorted(
        ((r.move_choice, r.total_score) for r in result.side_one),
        key=lambda x: x[1],
        reverse=True,
    )

    # drop the low-probability tail: it is mostly unconverged exploration noise,
    # while genuine mixing keeps moves with comparable weight
    highest_percentage = policy[0][1]
    policy = [p for p in policy if p[1] >= highest_percentage * 0.75]
    logger.info("Considered Choices:")
    for move, weight in policy:
        logger.info(f"\t{round(weight * 100, 3)}%: {move}")

    choice = random.choices(policy, weights=[p[1] for p in policy])[0]
    return choice[0]


def find_best_move(battle: Battle) -> str:
    battle = deepcopy(battle)
    if battle.team_preview:
        battle.user.active = battle.user.reserve.pop(0)
        battle.opponent.active = battle.opponent.reserve.pop(0)

    num_battles, search_time_per_battle = battle.mode.search_params(battle)
    battles = battle.mode.prepare_battles(battle, num_battles)

    # one shared-root cfr search over all determinizations. the total duration
    # preserves the wall-clock of the old one-search-per-determinization
    # approach, which ran `parallelism` searches at a time
    total_search_time_ms = search_time_per_battle * math.ceil(
        len(battles) / FoulPlayConfig.parallelism
    )

    states = []
    weights = []
    for index, (b, chance) in enumerate(battles):
        state = battle_to_poke_engine_state(b)
        logger.debug("Determinization {} state: {}".format(index, state.to_string()))
        states.append(state)
        weights.append(chance)

    logger.info("Searching for a move using CFR...")
    logger.info(
        "Sampling {} determinizations at {}ms total".format(
            len(states), total_search_time_ms
        )
    )
    result = cfr_search(states, weights, duration_ms=total_search_time_ms)
    logger.info("Total iterations: {}".format(result.total_visits))
    logger.info(
        "Iterations per determinization: {}".format(result.determinization_visits)
    )

    choice = select_move_from_cfr_result(result)
    logger.info("Choice: {}".format(choice))
    return choice
