import logging
import random
from collections import defaultdict

from poke_engine import (
    State as PokeEngineState,
    monte_carlo_tree_search,
    MctsResult,
    MctsSideResult,
)

import constants
from data.pkmn_sets import PredictedPokemonSet
from fp.battle import Pokemon

logger = logging.getLogger(__name__)


def log_pkmn_set(pkmn: Pokemon, source=None):
    nature_evs = f"{pkmn.nature},{','.join(str(x) for x in pkmn.evs)}"
    if nature_evs in [
        "serious,85,85,85,85,85,85",
        "serious,252,252,252,252,252,252",
        "serious,11,11,11,11,11,11",
    ]:
        s = "\t{} {} {} {}".format(
            pkmn.name.rjust(15),
            str(pkmn.ability).rjust(12),
            str(pkmn.item).rjust(12),
            pkmn.moves,
        )
    else:
        s = "\t{} {} {} {} {}".format(
            pkmn.name.rjust(15),
            nature_evs.rjust(25),
            str(pkmn.ability).rjust(12),
            str(pkmn.item).rjust(12),
            pkmn.moves,
        )
    if pkmn.tera_type is not None and pkmn.tera_type not in ["nothing", "typeless"]:
        s += " ttype={}".format(pkmn.tera_type)
    if source is not None:
        s += " source={}".format(source)

    logger.info(s)


def populate_pkmn_from_set(
    pkmn: Pokemon, set_: PredictedPokemonSet, source: str = None
):
    known_pokemon_moves = pkmn.moves

    pkmn.moves = []
    for mv in set_.pkmn_moveset.moves:
        pkmn.add_move(mv)
    pkmn.ability = pkmn.ability or set_.pkmn_set.ability
    if pkmn.item == constants.UNKNOWN_ITEM:
        pkmn.item = set_.pkmn_set.item
    pkmn.set_spread(
        set_.pkmn_set.nature,
        ",".join(str(x) for x in set_.pkmn_set.evs),
    )
    if (
        set_.pkmn_set.tera_type is not None
        and not pkmn.terastallized
        and not pkmn.tera_type
    ):
        pkmn.tera_type = set_.pkmn_set.tera_type
    log_pkmn_set(pkmn, source)

    # newly created moves have max PP
    # copy over the current pp from the known moves
    for known_move in known_pokemon_moves:
        for mv in pkmn.moves:
            if known_move.name.startswith("hiddenpower") and mv.name.startswith(
                "hiddenpower"
            ):
                mv.current_pp = known_move.current_pp
                break
            elif mv.name == known_move.name:
                mv.current_pp = known_move.current_pp
                break


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


def calculate_opponent_team_preview_preferences(
    team_preview_results: list[tuple[int, list[MctsSideResult]]],
) -> dict[str, float]:
    if not team_preview_results:
        return {}

    pkmn_scores = defaultdict(lambda: 0)
    for search_iterations, search_result in team_preview_results:
        for side_result in search_result:
            for pkmn_name in side_result.move_choice.split(","):
                pkmn_scores[pkmn_name] += side_result.visits / search_iterations

    return dict(pkmn_scores)
