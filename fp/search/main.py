import logging
import random
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy

from fp.battle.state import Battle
from fp.config import FoulPlayConfig

from poke_engine import State as PokeEngineState, monte_carlo_tree_search, MctsResult

from fp.search.poke_engine_helpers import battle_to_poke_engine_state

logger = logging.getLogger(__name__)

# visits worth of confidence placed in a world's average value when shrinking
# a move's q-value. raw q-values from barely-visited moves are noisy, so they
# get dragged toward the world's average until they accumulate enough visits
SHRINKAGE_VISITS = 50

# regret (in score units) above which a sampled world is considered to strongly
# disagree with the chosen move
CVAR_REGRET_THRESHOLD = 0.003

# fraction of world probability-mass considered "the tail" when computing
# CVaR over regrets. 1.0 is the plain expected regret, values near 0
# approach the single worst world
CVAR_ALPHA = 0.5


def world_q_values(mcts_result: MctsResult) -> dict[str, float]:
    """
    Per-move q-values for a single sampled world, shrunk toward the world's
    average value proportional to how few visits the move received.
    """
    total_visits = sum(s.visits for s in mcts_result.side_one)
    total_score = sum(s.total_score for s in mcts_result.side_one)
    if total_visits == 0:
        return {}
    world_avg = total_score / total_visits

    q_values = {}
    for s1_option in mcts_result.side_one:
        if s1_option.visits == 0:
            continue
        q = s1_option.total_score / s1_option.visits
        q_values[s1_option.move_choice] = (
            s1_option.visits * q + SHRINKAGE_VISITS * world_avg
        ) / (s1_option.visits + SHRINKAGE_VISITS)

    return q_values


def compute_move_expected_values(
    mcts_results: list[(MctsResult, float, int)],
) -> dict[str, float]:
    """
    Aggregate per-world q-values into a cross-world expected value for each move.
    q-values are (total_score / visits)
    """
    weighted_scores = {}
    weights = {}
    for mcts_result, sample_chance, _index in mcts_results:
        for move, q in world_q_values(mcts_result).items():
            weighted_scores[move] = weighted_scores.get(move, 0.0) + sample_chance * q
            weights[move] = weights.get(move, 0.0) + sample_chance

    # normalize by the weight actually seen in case a move was not
    # available in every sampled world
    return {move: score / weights[move] for move, score in weighted_scores.items()}


def compute_q_matrix(
    mcts_results: list[(MctsResult, float, int)],
) -> dict[str, dict[int, float]]:
    """
    Per-world shrunk q-value of every move, as move -> {battle index -> q}.
    """
    q_matrix = {}
    for mcts_result, _sample_chance, index in mcts_results:
        for move, q in world_q_values(mcts_result).items():
            q_matrix.setdefault(move, {})[index] = q

    return q_matrix


def compute_regret_matrix(
    q_matrix: dict[str, dict[int, float]],
) -> dict[str, dict[int, float]]:
    """
    Per-world regret of every move: the value a move gives up relative to the
    best move in that same world. 0 means the move is that world's best.

    Same shape as the q-value matrix: move -> {battle index -> regret}.
    """
    best_q_by_index = {}
    for q_values in q_matrix.values():
        for index, q in q_values.items():
            if q > best_q_by_index.get(index, float("-inf")):
                best_q_by_index[index] = q

    return {
        move: {index: best_q_by_index[index] - q for index, q in q_values.items()}
        for move, q_values in q_matrix.items()
    }


def regret_cvar(regrets: list[float], weights: list[float], alpha: float) -> float:
    """
    Conditional value at risk over regrets: the weighted mean of the worst
    (largest) alpha-mass of regret values. alpha=1.0 is the plain weighted
    mean, alpha near 0 approaches the single worst regret.

    If alpha's weight budget lands inside a regret's weight, only the
    fraction of the weight needed to fill the budget is counted.
    """
    if not 0.0 < alpha <= 1.0:
        raise ValueError("alpha must be in (0, 1]")

    pairs = sorted(zip(regrets, weights), key=lambda p: p[0], reverse=True)
    budget = alpha * sum(weight for _, weight in pairs)
    consumed = 0.0
    acc = 0.0
    for regret, weight in pairs:
        take = min(weight, budget - consumed)
        if take <= 0.0:
            break
        acc += regret * take
        consumed += take

    return acc / consumed if consumed > 0.0 else 0.0


def compute_regret_cvar_by_move(
    regret_matrix: dict[str, dict[int, float]],
    world_weights: dict[int, float],
    alpha: float,
) -> dict[str, float]:
    cvar_by_move = {}
    for move, regrets in regret_matrix.items():
        indices = list(regrets)
        cvar_by_move[move] = regret_cvar(
            [regrets[i] for i in indices],
            [world_weights[i] for i in indices],
            alpha,
        )

    return cvar_by_move


def expected_value_choice_with_cvar(
    mcts_results: list[(MctsResult, float, int)], chosen_move: str
) -> str:
    expected_values = compute_move_expected_values(mcts_results)
    if not expected_values:
        raise ValueError("No expected values?")

    ranked = sorted(expected_values.items(), key=lambda x: x[1], reverse=True)
    logger.info("EV ranking:")
    for move, value in ranked[:5]:
        logger.info("\t{}: {}".format(round(value, 3), move))

    q_matrix = compute_q_matrix(mcts_results)
    regret_matrix = compute_regret_matrix(q_matrix)

    world_weights = {index: sample_chance for _, sample_chance, index in mcts_results}
    cvar_by_move = compute_regret_cvar_by_move(regret_matrix, world_weights, CVAR_ALPHA)
    logger.info("EV regret CVaR (alpha={}):".format(CVAR_ALPHA))
    for move, value in sorted(cvar_by_move.items(), key=lambda x: x[1]):
        logger.info("\t{}: {}".format(round(value, 3), move))

    ev_choice, ev_value = ranked[0]
    considerations = [(ev_choice, ev_value, cvar_by_move[ev_choice])]
    for c, v in ranked[1:]:
        if ev_value - v <= CVAR_REGRET_THRESHOLD:
            considerations.append((c, v, cvar_by_move[c]))

    considerations = sorted(considerations, key=lambda x: x[2])
    choice = considerations[0][0]
    if choice != chosen_move:
        logger.info(f"picked a new move: {choice}, original: {chosen_move}")
    return choice


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

    choice = random.choices(final_policy, weights=[p[1] for p in final_policy])[0][0]
    choice = expected_value_choice_with_cvar(mcts_results, choice)
    return choice


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
    choice = select_move_from_mcts_results(mcts_results)
    logger.info("Choice: {}".format(choice))
    return choice
