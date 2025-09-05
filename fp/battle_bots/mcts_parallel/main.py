import logging
import random
from concurrent.futures import ProcessPoolExecutor

from poke_engine import MctsResult

import constants
from fp.battle import Battle
from config import FoulPlayConfig
from .standard_battles import prepare_battles
from .random_battles import prepare_random_battles

from poke_engine import (
    State as PokeEngineState,
    monte_carlo_tree_search,
)

from ..poke_engine_helpers import battle_to_poke_engine_state

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
    poke_engine_state: PokeEngineState, search_time_ms: int, index: int
) -> MctsResult:
    state_string = poke_engine_state.to_string()
    logger.debug("Calling with {} state: {}".format(index, state_string))

    res = monte_carlo_tree_search(poke_engine_state, search_time_ms)
    logger.info("Iterations {}: {}".format(index, res.total_visits))
    return res


class BattleBot(Battle):
    def __init__(self, *args, **kwargs):
        super(BattleBot, self).__init__(*args, **kwargs)

    def _search_time_num_battles_randombattles(self):
        revealed_pkmn = len(self.opponent.reserve)
        if self.opponent.active is not None:
            revealed_pkmn += 1

        opponent_active_num_moves = len(self.opponent.active.moves)
        in_time_pressure = self.time_remaining is not None and self.time_remaining <= 60

        # it is still quite early in the battle and the pkmn in front of us
        # hasn't revealed any moves: search a lot of battles shallowly
        if (
            revealed_pkmn <= 3
            and self.opponent.active.hp > 0
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

    def _search_time_num_battles_standard_battle(self):
        opponent_active_num_moves = len(self.opponent.active.moves)
        in_time_pressure = self.time_remaining is not None and self.time_remaining <= 60

        if (
            self.team_preview
            or (self.opponent.active.hp > 0 and opponent_active_num_moves == 0)
            or opponent_active_num_moves < 3
        ):
            num_battles_multiplier = 1 if in_time_pressure else 2
            return FoulPlayConfig.parallelism * num_battles_multiplier, int(
                FoulPlayConfig.search_time_ms
            )
        else:
            return FoulPlayConfig.parallelism, FoulPlayConfig.search_time_ms

    def find_best_move(self):
        if self.team_preview:
            self.user.active = self.user.reserve.pop(0)
            self.opponent.active = self.opponent.reserve.pop(0)

        if self.battle_type == constants.RANDOM_BATTLE:
            num_battles, search_time_per_battle = (
                self._search_time_num_battles_randombattles()
            )
            battles = prepare_random_battles(self, num_battles)
        elif self.battle_type == constants.BATTLE_FACTORY:
            num_battles, search_time_per_battle = (
                self._search_time_num_battles_standard_battle()
            )
            battles = prepare_random_battles(self, num_battles)
        elif self.battle_type == constants.STANDARD_BATTLE:
            num_battles, search_time_per_battle = (
                self._search_time_num_battles_standard_battle()
            )
            battles = prepare_battles(self, num_battles)
        else:
            raise ValueError("Unsupported battle type: {}".format(self.battle_type))

        logger.info("Searching for a move using MCTS...")
        logger.info(
            "Sampling {} battles at {}ms each".format(
                num_battles, search_time_per_battle
            )
        )
        with ProcessPoolExecutor(max_workers=FoulPlayConfig.parallelism) as executor:
            futures = []
            for index, (b, chance) in enumerate(battles):
                fut = executor.submit(
                    get_result_from_mcts,
                    battle_to_poke_engine_state(b),
                    search_time_per_battle,
                    index,
                )
                futures.append((fut, chance, index))

        mcts_results = [
            (fut.result(), chance, index) for (fut, chance, index) in futures
        ]
        choice = select_move_from_mcts_results(mcts_results)
        logger.info("Choice: {}".format(choice))

        if self.team_preview:
            self.user.reserve.insert(0, self.user.active)
            self.user.active = None
            self.opponent.reserve.insert(0, self.opponent.active)
            self.opponent.active = None

        return choice
