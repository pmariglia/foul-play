import logging
import random
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy

from fp.battle.state import Battle
from fp.config import FoulPlayConfig

from poke_engine import State as PokeEngineState, monte_carlo_tree_search, MctsResult

from fp.search.poke_engine_helpers import battle_to_poke_engine_state

logger = logging.getLogger(__name__)


class EngineSearchError(RuntimeError):
    """Serializable native-engine failure that can cross the process boundary."""


def emergency_move(battle: Battle) -> str:
    """Choose a legal action from the parsed server request after all samples fail."""
    if battle.team_preview:
        return "switch " + battle.user.active.name
    if battle.force_switch or battle.user.active.hp <= 0:
        for pokemon in battle.user.reserve:
            if pokemon.is_alive():
                return "switch " + pokemon.name
        raise EngineSearchError("No living replacement available after search failure")
    for move in battle.user.active.moves:
        if not move.disabled and move.current_pp > 0:
            return move.name
    return "struggle"


def collect_search_results(futures):
    results = []
    for future, chance, index in futures:
        try:
            result = future.result()
        except EngineSearchError:
            logger.error(
                "Native engine failed for sample %s; excluding this sample", index
            )
            continue
        logger.info("Iterations %s: %s", index, result.total_visits)
        results.append((result, chance, index))
    # Preserve the relative probabilities of the surviving hidden-team samples.
    total_chance = sum(chance for _, chance, _ in results)
    if results and total_chance > 0:
        return [
            (result, chance / total_chance, index) for result, chance, index in results
        ]
    return []


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
    try:
        poke_engine_state = PokeEngineState.from_string(state)
        res = monte_carlo_tree_search(
            poke_engine_state, search_time_ms, threads=threads
        )
    except BaseException as error:
        # PyO3's PanicException inherits BaseException and lives in a virtual
        # module. Letting it escape a worker causes a second, unpicklable error.
        if (
            type(error).__module__ == "pyo3_runtime"
            and type(error).__name__ == "PanicException"
        ):
            raise EngineSearchError(
                f"Native engine panicked in sample {index}"
            ) from None
        raise
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

    mcts_results = collect_search_results(futures)
    if mcts_results:
        choice = select_move_from_mcts_results(mcts_results)
    else:
        choice = emergency_move(battle)
        logger.error(
            "All native search samples failed; using legal fallback: %s", choice
        )
    logger.info("Choice: {}".format(choice))
    return choice
