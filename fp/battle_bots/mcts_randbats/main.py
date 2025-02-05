import logging
from concurrent.futures import ProcessPoolExecutor

from poke_engine import MctsResult

import constants
from data.pkmn_sets import TeamDatasets, SmogonSets
from fp.battle import Battle
from config import FoulPlayConfig
from .standard_battles import prepare_battles

from .team_sampler import (
    prepare_random_battles,
    fill_in_opponent_unrevealed_pkmn,
)

from poke_engine import (
    State as PokeEngineState,
    monte_carlo_tree_search,
)

from ..poke_engine_helpers import battle_to_poke_engine_state

logger = logging.getLogger(__name__)

# the number of revealed pkmn on the opponent's team determines the number of battles to sample
# fewer revealed pokemon means more battles are sampled and a shallower search
PARALLELISM_MULTIPLIER = {6: 1, 5: 1, 4: 2, 3: 4, 2: 4, 1: 4, 0: 4}


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
    logger.info("Final policy: {}".format(final_policy))
    return final_policy[0][0]


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

    def _num_battles_randombattles(self, revealed_pkmn):
        return int(FoulPlayConfig.parallelism * PARALLELISM_MULTIPLIER[revealed_pkmn])

    def _search_time_per_battle_randombattles(self, num_battles):
        return FoulPlayConfig.search_time_ms // (
            max(num_battles // FoulPlayConfig.parallelism, 1)
        )

    def _num_battles_battle_factory(self, datasets):
        opponent_active_num_sets = len(
            datasets.get_all_remaining_sets(self.opponent.active)
        )
        if self.team_preview or (
            self.opponent.active.hp > 0
            and opponent_active_num_sets > (FoulPlayConfig.parallelism * 2)
        ):
            num_battles = FoulPlayConfig.parallelism * 4
        elif opponent_active_num_sets > FoulPlayConfig.parallelism:
            num_battles = FoulPlayConfig.parallelism * 2
        else:
            num_battles = FoulPlayConfig.parallelism

        return num_battles

    def _search_time_per_battle_battle_factory(self, num_battles):
        if (
            self.team_preview
            or self.turn < 3
            or (self.time_remaining is not None and self.time_remaining > 60)
        ):
            search_time_per_battle = FoulPlayConfig.search_time_ms
        else:
            search_time_per_battle = self._search_time_per_battle_randombattles(
                num_battles
            )

        return search_time_per_battle

    def _search_time_num_battles_standard_battle(self):
        num_opponent_fainted = self.opponent.num_fainted_pkmn()
        opponent_active_num_moves = len(self.opponent.active.moves)
        in_time_pressure = self.time_remaining is not None and self.time_remaining <= 60

        # team preview or opponent has no revealed moves
        # search a lot of battles shallowly
        if self.team_preview or (
            self.opponent.active.hp > 0 and opponent_active_num_moves == 0
        ):
            num_battles_multiplier = 4 if in_time_pressure else 16
            return FoulPlayConfig.parallelism * num_battles_multiplier, int(
                FoulPlayConfig.search_time_ms // 4
            )

        # opponent has a lot of pkmn remaining
        # search many battles a bit shallower
        elif num_opponent_fainted < 3:
            return FoulPlayConfig.parallelism * 2, int(
                FoulPlayConfig.search_time_ms // 2
            )

        # opponent has few pokemon remaining and few revealed moves on their active
        # search many battles deeply if time allows
        elif opponent_active_num_moves < 3:
            search_time_divisor = 2 if in_time_pressure else 1
            return FoulPlayConfig.parallelism * 2, int(
                FoulPlayConfig.search_time_ms // search_time_divisor
            )

        # opponent has few pokemon remaining and lots of revealed moves on their active
        # search few battles deeply
        else:
            return FoulPlayConfig.parallelism, FoulPlayConfig.search_time_ms

    def find_best_move(self):
        if self.team_preview:
            self.user.active = self.user.reserve.pop(0)
            self.opponent.active = self.opponent.reserve.pop(0)

        revealed_pkmn = len(self.opponent.reserve)
        if self.opponent.active is not None:
            revealed_pkmn += 1

        if self.battle_type == constants.RANDOM_BATTLE:
            num_battles = self._num_battles_randombattles(revealed_pkmn)
            search_time_per_battle = self._search_time_per_battle_randombattles(
                num_battles
            )
            battles = prepare_random_battles(self, num_battles)
        elif self.battle_type == constants.BATTLE_FACTORY:
            num_battles = self._num_battles_battle_factory(TeamDatasets)
            search_time_per_battle = self._search_time_per_battle_battle_factory(
                num_battles
            )
            battles = prepare_random_battles(self, num_battles)
        elif self.battle_type == constants.STANDARD_BATTLE:
            num_battles, search_time_per_battle = (
                self._search_time_num_battles_standard_battle()
            )
            battles = prepare_battles(self, num_battles)
        else:
            raise ValueError("Unsupported battle type: {}".format(self.battle_type))

        for b, _ in battles:
            fill_in_opponent_unrevealed_pkmn(b)

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
