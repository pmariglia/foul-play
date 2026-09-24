import logging
import math
import random
from copy import deepcopy

from fp.battle.state import Battle
from fp.config import FoulPlayConfig

from poke_engine import (
    State as PokeEngineState,
    monte_carlo_tree_search,
    monte_carlo_tree_search_shared_root,
    MctsResult,
)

from fp.search.poke_engine_helpers import battle_to_poke_engine_state

logger = logging.getLogger(__name__)


def select_move_from_mcts_results(mcts_results: list[(MctsResult, float, int)]) -> str:
    final_policy = {}
    for mcts_result, sample_chance, index in mcts_results:
        this_policy = max(mcts_result.side_one, key=lambda x: x.visits)
        logger.info(
            "Policy {}: {} visited {}% avg_score={} sample_chance_multiplier={}".format(
                index,
                this_policy.move_choice,
                round(100 * this_policy.visits / mcts_result.total_visits, 2),
                round(this_policy.total_score / this_policy.visits, 3),
                round(sample_chance, 3),
            )
        )
        for s1_option in mcts_result.side_one:
            final_policy[s1_option.move_choice] = final_policy.get(
                s1_option.move_choice, 0
            ) + (sample_chance * (s1_option.visits / mcts_result.total_visits))

    final_policy = sorted(final_policy.items(), key=lambda x: x[1], reverse=True)

    # Consider all moves that are close to the best move
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

    res = monte_carlo_tree_search(poke_engine_state, search_time_ms, threads=threads)
    logger.info("Iterations {}: {}".format(index, res.total_visits))
    return res


def find_best_move(battle: Battle) -> str:
    battle = deepcopy(battle)
    if battle.team_preview:
        battle.user.active = battle.user.reserve.pop(0)
        battle.opponent.active = battle.opponent.reserve.pop(0)

    num_battles, search_time_per_battle = battle.mode.search_params(battle)
    battles = battle.mode.prepare_battles(battle, num_battles)

    # one shared-root search over all determinizations; the engine gives each
    # determinization its own thread and tree, and side one's root stats are
    # pooled across them. the total duration preserves the wall-clock of the
    # one-search-per-determinization approach, which ran `parallelism`
    # processes at a time
    total_search_time_ms = search_time_per_battle * math.ceil(
        len(battles) / FoulPlayConfig.parallelism
    )

    states = []
    for index, (b, _chance) in enumerate(battles):
        state = battle_to_poke_engine_state(b)
        logger.debug("Determinization {} state: {}".format(index, state.to_string()))
        states.append(state)

    logger.info("Searching for a move using shared-root MCTS...")
    logger.info(
        "Sampling {} determinizations at {}ms total".format(
            len(states), total_search_time_ms
        )
    )
    result = monte_carlo_tree_search_shared_root(
        states, duration_ms=total_search_time_ms
    )
    logger.info("Total iterations: {}".format(result.total_visits))
    for index, determinization in enumerate(result.determinizations):
        this_policy = max(determinization.side_one, key=lambda x: x.visits)
        logger.info(
            "Determinization {}: {} iterations, {} visited {}% avg_score={}".format(
                index,
                determinization.total_visits,
                this_policy.move_choice,
                round(100 * this_policy.visits / determinization.total_visits, 2),
                round(this_policy.total_score / this_policy.visits, 3),
            )
        )

    # the pooled side-one stats are one MctsResult-shaped policy, so the
    # existing selection logic applies to it directly
    pooled = MctsResult(
        side_one=result.side_one,
        side_two=[],
        total_visits=sum(m.visits for m in result.side_one),
    )
    choice = select_move_from_mcts_results([(pooled, 1.0, 0)])
    logger.info("Choice: {}".format(choice))
    return choice
