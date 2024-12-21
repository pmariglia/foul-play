from __future__ import annotations

import ntpath
from abc import ABC, abstractmethod
from dataclasses import dataclass

import requests
from dateutil import relativedelta
from datetime import datetime
import os
import json
import logging
import typing
from typing import Tuple
from typing import Optional


import constants
from data import all_move_json
from fp.helpers import calculate_stats
from fp.helpers import normalize_name

PWD = os.path.dirname(os.path.abspath(__file__))
SMOGON_CACHE_DIR = os.path.join(PWD, "smogon_stats_cache")
os.makedirs(SMOGON_CACHE_DIR, exist_ok=True)

OTHER_STRING = "other"
MOVES_STRING = "moves"
ITEM_STRING = "items"
SPREADS_STRING = "spreads"
ABILITY_STRING = "abilities"
TERA_TYPE_STRING = "tera_types"
EFFECTIVENESS = "effectiveness"

if typing.TYPE_CHECKING:
    from fp.battle import Pokemon

logger = logging.getLogger(__name__)
PWD = os.path.dirname(os.path.abspath(__file__))


def spreads_are_alike(s1, s2):
    if s1[0] != s2[0]:
        return False

    s1 = [int(v) for v in s1[1].split(",")]
    s2 = [int(v) for v in s2[1].split(",")]

    diff = [abs(i - j) for i, j in zip(s1, s2)]

    # 24 is arbitrarily chosen as the threshold for EVs to be "alike"
    return all(v < 24 for v in diff)


@dataclass
class PredictedPokemonSet:
    pkmn_set: PokemonSet
    pkmn_moveset: PokemonMoveset

    def speed_check(self, pkmn: Pokemon):
        """
        The only non-observable speed modifier that should allow a
        Pokemon's speed_range to be set is choicescarf
        """
        stats = calculate_stats(
            pkmn.base_stats,
            pkmn.level,
            evs=self.pkmn_set.evs,
            nature=self.pkmn_set.nature,
        )
        speed = stats[constants.SPEED]
        if self.pkmn_set.item == "choicescarf":
            speed = int(speed * 1.5)

        return pkmn.speed_range.min <= speed <= pkmn.speed_range.max

    def item_check(self, pkmn: Pokemon) -> bool:
        if pkmn.item == self.pkmn_set.item:
            return True
        if self.pkmn_set.item in pkmn.impossible_items:
            return False
        elif (
            self.pkmn_set.item in constants.CHOICE_ITEMS
            and not pkmn.can_have_choice_item
        ):
            return False
        else:
            return pkmn.item is None or pkmn.item == constants.UNKNOWN_ITEM

    def moveset_makes_sense(self):
        has_hiddenpower = False
        for mv in self.pkmn_moveset.moves:
            # only 1 hiddenpower in a moveset
            if mv.startswith(constants.HIDDEN_POWER) and has_hiddenpower:
                return False
            elif mv.startswith(constants.HIDDEN_POWER):
                has_hiddenpower = True

            # dont pick certain moves with choice items
            if self.pkmn_set.item in constants.CHOICE_ITEMS:
                if all_move_json[mv][
                    constants.CATEGORY
                ] not in constants.DAMAGING_CATEGORIES and mv not in [
                    "trick",
                    "switcheroo",
                ]:
                    return False
        return True

    def predicted_set_makes_sense(
        self, pkmn: Pokemon, match_ability=True, match_item=True, speed_check=True
    ) -> bool:
        ability_check = not match_ability or (
            self.pkmn_set.ability == pkmn.ability or pkmn.ability is None
        )
        item_check = not match_item or self.item_check(pkmn)
        speed_check = not speed_check or self.speed_check(pkmn)
        tera_check = True
        if (
            self.pkmn_set.tera_type is not None
            and pkmn.terastallized
            and self.pkmn_set.tera_type != pkmn.tera_type
        ):
            tera_check = False

        return ability_check and item_check and speed_check and tera_check

    def full_set_pkmn_can_have_set(
        self, pkmn: Pokemon, match_ability=True, match_item=True, speed_check=True
    ) -> bool:
        return self.predicted_set_makes_sense(
            pkmn,
            match_ability=match_ability,
            match_item=match_item,
            speed_check=speed_check,
        ) and self.pkmn_moveset.full_set_pkmn_can_have_moves(pkmn)


@dataclass
class PokemonSet:
    ability: str
    item: str
    nature: str
    evs: Tuple[int, int, int, int, int, int]
    count: int
    tera_type: Optional[str] = None

    def set_makes_sense(self, pkmn: Pokemon, match_traits):
        p = PredictedPokemonSet(pkmn_set=self, pkmn_moveset=PokemonMoveset(moves=()))
        return p.predicted_set_makes_sense(
            pkmn,
            match_ability=match_traits,
            match_item=match_traits,
            speed_check=True,
        )


@dataclass
class PokemonMoveset:
    moves: Tuple[str, ...]

    def full_set_pkmn_can_have_moves(self, pkmn: Pokemon) -> bool:
        for mv in pkmn.moves:
            if mv.name == constants.HIDDEN_POWER:
                hidden_power_possibilities = [
                    constants.HIDDEN_POWER + p for p in pkmn.hidden_power_possibilities
                ]
                hidden_power_in_this_pkmn_set = [
                    m for m in self.moves if m.startswith(constants.HIDDEN_POWER)
                ]
                if (
                    len(hidden_power_in_this_pkmn_set) == 1
                    and hidden_power_in_this_pkmn_set[0] in hidden_power_possibilities
                ):
                    pass
                else:
                    return False
            elif mv.name not in self.moves:
                return False
        return True

    def add_move(self, mv: str):
        self.moves += (mv,)

    def remove_move(self, mv: str):
        self.moves = tuple(m for m in self.moves if m != mv)

    def __iter__(self):
        yield from self.moves

    def __len__(self):
        return len(self.moves)


class PokemonSets(ABC):
    raw_pkmn_sets: dict[str, list]
    pkmn_sets: dict[str, list]
    pkmn_mode: str

    @abstractmethod
    def initialize(self, pkmn_mode: str, pkmn_names: set[str]): ...

    @abstractmethod
    def predict_set(self, pkmn: Pokemon) -> Optional[PredictedPokemonSet]: ...

    @abstractmethod
    def remove_item_possibility(self, pkmn_name: str, item: str): ...

    @abstractmethod
    def remove_ability_possibility(self, pkmn_name: str, ability: str): ...

    def get_pkmn_sets_from_pkmn_name(self, pkmn_name: str, pkmn_base_name: str):
        if pkmn_name in self.pkmn_sets:
            return self.pkmn_sets[pkmn_name]
        elif pkmn_base_name in self.pkmn_sets:
            return self.pkmn_sets[pkmn_base_name]

        # Fallback: check for a partial match
        for p in self.pkmn_sets:
            if pkmn_name.startswith(p) or p.startswith(pkmn_name):
                return self.pkmn_sets[p]

        # Return empty list if no match is found
        return []

    def get_raw_pkmn_sets_from_pkmn_name(self, pkmn_name: str):
        try:
            return self.raw_pkmn_sets[pkmn_name]
        except KeyError:
            for p in self.raw_pkmn_sets:
                if pkmn_name.startswith(p) or p.startswith(pkmn_name):
                    return self.raw_pkmn_sets[p]
        return []


class _RandomBattleSets(PokemonSets):
    def __init__(self):
        self.raw_pkmn_sets = {}
        self.pkmn_sets = {}
        self.pkmn_mode = "uninitialized"

    def _load_raw_sets(self, generation):
        if generation.endswith("blitz"):
            generation = generation[:-5]
        randombattle_sets_path = os.path.join(
            PWD, f"pkmn_sets/{generation}randombattle.json"
        )
        with open(randombattle_sets_path, "r") as f:
            sets = json.load(f)
        self.raw_pkmn_sets = sets

    def _initialize_pkmn_sets(self):
        for pkmn, sets in self.raw_pkmn_sets.items():
            self.pkmn_sets[pkmn] = []
            for set_, count in sets.items():
                set_split = set_.split(",")
                item = set_split[0]
                ability = set_split[1]
                moves = set_split[2:6]
                tera_type = None
                if len(set_split) > 6:
                    tera_type = set_split[6]
                self.pkmn_sets[pkmn].append(
                    PredictedPokemonSet(
                        pkmn_set=PokemonSet(
                            ability=ability,
                            item=item,
                            nature="serious",
                            evs=(85, 85, 85, 85, 85, 85),
                            count=count,
                            tera_type=tera_type,
                        ),
                        pkmn_moveset=PokemonMoveset(moves=moves),
                    )
                )
            self.pkmn_sets[pkmn].sort(key=lambda x: x.pkmn_set.count, reverse=True)

    def initialize(self, pkmn_mode: str, _pkmn_names=None):
        # pkmn_names unused here since randombattles don't have team preview
        # always load entire JSON into memory
        self.raw_pkmn_sets = {}
        self.pkmn_sets = {}
        self.pkmn_mode = pkmn_mode
        self._load_raw_sets(pkmn_mode)
        self._initialize_pkmn_sets()

    def remove_item_possibility(self, pkmn_name: str, item: str):
        pkmn_sets = self.pkmn_sets.get(pkmn_name, [])
        for i in reversed(range(len(pkmn_sets))):
            if pkmn_sets[i].pkmn_set.item == item:
                pkmn_sets.pop(i)

    def remove_ability_possibility(self, pkmn_name: str, ability: str):
        pkmn_sets = self.pkmn_sets.get(pkmn_name, [])
        for i in reversed(range(len(pkmn_sets))):
            if pkmn_sets[i].pkmn_set.ability == ability:
                pkmn_sets.pop(i)

    def predict_set(
        self, pkmn: Pokemon, match_traits=True
    ) -> Optional[PredictedPokemonSet]:
        if not self.pkmn_sets:
            logger.warning("Called `predict_set` when pkmn_sets was empty")

        for pkmn_set in self.get_pkmn_sets_from_pkmn_name(pkmn.name, pkmn.base_name):
            if pkmn_set.full_set_pkmn_can_have_set(
                pkmn,
                match_ability=match_traits,
                match_item=match_traits,
                speed_check=False,  # speed check never makes sense for randombattles because we know the nature/evs
            ):
                return pkmn_set

        return None

    def pokemon_can_have_move(self, pkmn: Pokemon, move: str) -> bool:
        for pkmn_set in self.get_pkmn_sets_from_pkmn_name(pkmn.name, pkmn.base_name):
            if move in pkmn_set.pkmn_moveset.moves:
                return True
        return False


class _TeamDatasets(PokemonSets):
    def __init__(self):
        self.raw_pkmn_sets = {}
        self.pkmn_sets = {}
        self.pkmn_mode = "uninitialized"

    def _get_sets_dict(self):
        if not os.path.exists(os.path.join(PWD, f"pkmn_sets/{self.pkmn_mode}.json")):
            return {}
        sets = os.path.join(PWD, f"pkmn_sets/{self.pkmn_mode}.json")
        with open(sets, "r") as f:
            sets_dict = json.load(f)["pokemon"]
        return sets_dict

    def _get_battle_factory_sets_dict(self, tier_name):
        sets = os.path.join(PWD, f"pkmn_sets/{self.pkmn_mode}.json")
        with open(sets, "r") as f:
            sets_dict = json.load(f)[tier_name]
        return sets_dict

    def _load_team_datasets(self, pkmn_names: set[str], battle_factory_tier_name=None):
        if battle_factory_tier_name:
            sets_dict = self._get_battle_factory_sets_dict(battle_factory_tier_name)
        else:
            sets_dict = self._get_sets_dict()
        for pkmn in pkmn_names:
            try:
                self.raw_pkmn_sets[pkmn] = sets_dict[pkmn]
            except KeyError:
                logger.warning("No pokemon sets for {}".format(pkmn))

    def _add_to_pkmn_sets(self, raw_sets: dict[str, list]):
        for pkmn, sets in raw_sets.items():
            self.pkmn_sets[pkmn] = []
            for set_, count in sets.items():
                set_split = set_.split("|")
                tera_type = set_split[0] or "normal"
                ability = set_split[1]
                item = set_split[2]
                nature = set_split[3]
                evs = tuple(int(i) for i in set_split[4].split(","))
                moves = set_split[5:]

                self.pkmn_sets[pkmn].append(
                    PredictedPokemonSet(
                        pkmn_set=PokemonSet(
                            ability=ability,
                            item=item,
                            nature=nature,
                            evs=evs,
                            count=count,
                            tera_type=tera_type,
                        ),
                        pkmn_moveset=PokemonMoveset(moves=moves),
                    )
                )
            self.pkmn_sets[pkmn].sort(key=lambda x: x.pkmn_set.count, reverse=True)

    def initialize(
        self, pkmn_mode: str, pkmn_names: set[str], battle_factory_tier_name=None
    ):
        self.raw_pkmn_sets = {}
        self.pkmn_sets = {}
        self.pkmn_mode = pkmn_mode
        self._load_team_datasets(
            pkmn_names, battle_factory_tier_name=battle_factory_tier_name
        )
        self._add_to_pkmn_sets(self.raw_pkmn_sets)

    def add_new_pokemon(self, pkmn_name: str):
        sets_dict = self._get_sets_dict()
        if pkmn_name not in sets_dict:
            return
        self._add_to_pkmn_sets({pkmn_name: sets_dict[pkmn_name]})

    def remove_item_possibility(self, pkmn_name: str, item: str):
        pkmn_sets = self.pkmn_sets.get(pkmn_name, [])
        for i in reversed(range(len(pkmn_sets))):
            if pkmn_sets[i].pkmn_set.item == item:
                pkmn_sets.pop(i)

    def remove_ability_possibility(self, pkmn_name: str, ability: str):
        pkmn_sets = self.pkmn_sets.get(pkmn_name, [])
        for i in reversed(range(len(pkmn_sets))):
            if pkmn_sets[i].pkmn_set.ability == ability:
                pkmn_sets.pop(i)

    def predict_set(
        self, pkmn: Pokemon, match_traits=True
    ) -> Optional[PredictedPokemonSet]:
        for pkmn_set in self.get_pkmn_sets_from_pkmn_name(pkmn.name, pkmn.base_name):
            if pkmn_set.full_set_pkmn_can_have_set(
                pkmn,
                match_ability=match_traits,
                match_item=match_traits,
                speed_check=True,
            ):
                return pkmn_set

        return None


class _SmogonSets(PokemonSets):
    def __init__(self):
        self.current_pkmn_sets_url = ""
        self.raw_pkmn_sets = {}
        self.pkmn_sets = {}
        self.pkmn_mode = "uninitialized"

    def _smogon_predicted_move_set_makes_sense(
        self, predicted_set: PredictedPokemonSet
    ):
        has_hiddenpower = False
        for mv in predicted_set.pkmn_moveset.moves:
            # only 1 hiddenpower in a moveset
            if mv.startswith(constants.HIDDEN_POWER) and has_hiddenpower:
                return False
            elif mv.startswith(constants.HIDDEN_POWER):
                has_hiddenpower = True

            # dont pick certain moves with choice items
            if predicted_set.pkmn_set.item in constants.CHOICE_ITEMS:
                if all_move_json[mv][
                    constants.CATEGORY
                ] not in constants.DAMAGING_CATEGORIES and mv not in [
                    "trick",
                    "switcheroo",
                ]:
                    return False
        return True

    def smogon_set_makes_sense(self, pkmn: Pokemon, predicted_set: PredictedPokemonSet):
        return self._smogon_predicted_move_set_makes_sense(predicted_set)

    def _pokemon_is_similar(self, normalized_name, list_of_pkmn_names):
        return any(normalized_name.startswith(n) for n in list_of_pkmn_names) or any(
            n.startswith(normalized_name) for n in list_of_pkmn_names
        )

    def _get_smogon_stats_json(self, smogon_stats_url):
        cache_file_name = ntpath.basename(smogon_stats_url)
        cache_file = os.path.join(SMOGON_CACHE_DIR, cache_file_name)
        if os.path.exists(cache_file):
            with open(cache_file, "r") as f:
                infos = json.load(f)
        else:
            r = requests.get(smogon_stats_url)
            if r.status_code == 404:
                r = requests.get(
                    self._get_smogon_stats_file_name(
                        ntpath.basename(smogon_stats_url.replace("-0.json", "")),
                        month_delta=2,
                    )
                )
            infos = r.json()["data"]
            with open(cache_file, "w") as f:
                json.dump(infos, f)

        return infos

    def _get_pokemon_information(self, smogon_stats_url, pkmn_names=None):
        infos = self._get_smogon_stats_json(smogon_stats_url)

        final_infos = {}
        for pkmn_name, pkmn_information in infos.items():
            normalized_name = normalize_name(pkmn_name)

            # if `pkmn_names` is provided, only find data on pkmn in that list
            if (
                pkmn_names
                and normalized_name not in pkmn_names
                and not self._pokemon_is_similar(normalized_name, pkmn_names)
            ):
                continue
            else:
                logger.debug(
                    "Adding {} to sets lookup for this battle".format(normalized_name)
                )

            spreads = []
            items = []
            moves = []
            abilities = []
            tera_types = []
            matchup_effectiveness = {}
            total_count = pkmn_information["Raw count"]
            final_infos[normalized_name] = {}

            for counter_name, counter_information in pkmn_information[
                "Checks and Counters"
            ].items():
                counter_name = normalize_name(counter_name)
                if counter_name in pkmn_names:
                    matchup_effectiveness[counter_name] = round(
                        1 - counter_information[1], 2
                    )

            for spread, count in sorted(
                pkmn_information["Spreads"].items(), key=lambda x: x[1], reverse=True
            ):
                percentage = round(100 * count / total_count, 2)
                if percentage > 0:
                    nature, evs = [normalize_name(i) for i in spread.split(":")]
                    evs = evs.replace("/", ",")
                    for sp in spreads:
                        if spreads_are_alike(sp, (nature, evs)):
                            sp[2] += percentage
                            break
                    else:
                        spreads.append([nature, evs, percentage])

            for item, count in pkmn_information["Items"].items():
                if count > 0:
                    items.append((item, round(100 * count / total_count, 2)))

            for move, count in pkmn_information["Moves"].items():
                if count > 0 and move and move.lower() != "nothing":
                    if move.startswith(constants.HIDDEN_POWER):
                        move = f"{move}{constants.HIDDEN_POWER_ACTIVE_MOVE_BASE_DAMAGE_STRING}"
                    moves.append((move, round(100 * count / total_count, 2)))

            for ability, count in pkmn_information["Abilities"].items():
                if count > 0:
                    abilities.append((ability, round(100 * count / total_count, 2)))

            for tera_type, count in pkmn_information["Tera Types"].items():
                if count > 0:
                    tera_types.append((tera_type, round(100 * count / total_count, 2)))

            final_infos[normalized_name][SPREADS_STRING] = sorted(
                spreads, key=lambda x: x[2], reverse=True
            )[:20]
            final_infos[normalized_name][ITEM_STRING] = sorted(
                items, key=lambda x: x[1], reverse=True
            )[:10]
            final_infos[normalized_name][MOVES_STRING] = sorted(
                moves, key=lambda x: x[1], reverse=True
            )[:20]
            final_infos[normalized_name][ABILITY_STRING] = sorted(
                abilities, key=lambda x: x[1], reverse=True
            )
            final_infos[normalized_name][TERA_TYPE_STRING] = sorted(
                tera_types, key=lambda x: x[1], reverse=True
            )[:3]
            final_infos[normalized_name][EFFECTIVENESS] = matchup_effectiveness

            cumsum = 0
            for i, item in enumerate(final_infos[normalized_name][SPREADS_STRING]):
                cumsum += item[2]
                if cumsum > 85 and i >= 14:
                    final_infos[normalized_name][SPREADS_STRING] = final_infos[
                        normalized_name
                    ][SPREADS_STRING][: i + 1]
                    break

        return final_infos

    def _get_smogon_stats_file_name(self, game_mode, month_delta=1):
        """
        Gets the smogon stats url based on the game mode
        Uses the previous-month's statistics
        """

        if game_mode.endswith("blitz"):
            game_mode = game_mode[:-5]

        # always use the `-0` file - the higher ladder is for noobs
        smogon_url = "https://www.smogon.com/stats/{}-{}/chaos/{}-0.json"

        previous_month = datetime.now() - relativedelta.relativedelta(
            months=month_delta
        )
        year = previous_month.year
        month = "{:02d}".format(previous_month.month)

        return smogon_url.format(year, month, game_mode)

    def _pokemon_set_makes_sense(self, pkmn_set: PokemonSet):
        if pkmn_set.item == "choiceband" and pkmn_set.evs[1] < 230:
            return False
        if pkmn_set.item == "choicespecs" and pkmn_set.evs[3] < 230:
            return False
        if pkmn_set.item == "choicescarf" and pkmn_set.evs[5] < 200:
            return False
        if pkmn_set.item in ["lifeorb", "expertbelt"] and (
            pkmn_set.evs[1] < 200 and pkmn_set.evs[3] < 200
        ):
            return False

        return True

    def _initialize(self, raw_pkmn_sets: dict):
        for pkmn, sets in raw_pkmn_sets.items():
            self.pkmn_sets[pkmn] = []
            for spread in sets[SPREADS_STRING]:
                for ability in sets[ABILITY_STRING]:
                    for item in sets[ITEM_STRING]:
                        for tera_type in sets[TERA_TYPE_STRING]:
                            pkmn_set = PokemonSet(
                                ability=ability[0],
                                item=item[0],
                                nature=spread[0],
                                evs=tuple(int(i) for i in spread[1].split(",")),
                                tera_type=tera_type[0],
                                count=(ability[1] + item[1] + spread[2]),
                            )
                            if self._pokemon_set_makes_sense(pkmn_set):
                                self.pkmn_sets[pkmn].append(pkmn_set)
            self.pkmn_sets[pkmn].sort(key=lambda x: x.count, reverse=True)

    def initialize(self, pkmn_mode: str, pkmn_names: set[str]):
        self.pkmn_mode = pkmn_mode
        smogon_stats_url = self._get_smogon_stats_file_name(pkmn_mode)
        if self.current_pkmn_sets_url != smogon_stats_url:
            self.raw_pkmn_sets = self._get_pokemon_information(
                smogon_stats_url, pkmn_names
            )
            self.current_pkmn_sets_url = smogon_stats_url
        else:
            new_pkmn_names = [p for p in pkmn_names if p not in self.raw_pkmn_sets]
            if new_pkmn_names:
                self.raw_pkmn_sets = self._get_pokemon_information(
                    smogon_stats_url, pkmn_names
                )

        self._initialize(self.raw_pkmn_sets)

    def add_new_pokemon(self, pkmn_name: str):
        pkmn_information = self._get_pokemon_information(
            self.current_pkmn_sets_url, {pkmn_name}
        )
        self.raw_pkmn_sets.update(pkmn_information)
        self._initialize(pkmn_information)

    def remove_item_possibility(self, pkmn_name: str, item: str):
        pkmn_sets = self.pkmn_sets.get(pkmn_name, [])
        for i in reversed(range(len(pkmn_sets))):
            if pkmn_sets[i].item == item:
                pkmn_sets.pop(i)

    def remove_ability_possibility(self, pkmn_name: str, ability: str):
        pkmn_sets = self.pkmn_sets.get(pkmn_name, [])
        for i in reversed(range(len(pkmn_sets))):
            if pkmn_sets[i].ability == ability:
                pkmn_sets.pop(i)

    def predict_set(
        self, pkmn: Pokemon, num_predicted_moves=4, match_traits=True
    ) -> Optional[PredictedPokemonSet]:
        if not self.pkmn_sets:
            logger.warning("Called `predict_set` when pkmn_sets was empty")

        pokemon_set = None
        for pkmn_set in self.get_pkmn_sets_from_pkmn_name(pkmn.name, pkmn.base_name):
            if pkmn_set.set_makes_sense(pkmn, match_traits):
                pokemon_set = pkmn_set
                break

        if pokemon_set is None:
            return None

        predicted_pokemon_set = PredictedPokemonSet(
            pkmn_set=pokemon_set,
            pkmn_moveset=PokemonMoveset(moves=tuple(m.name for m in pkmn.moves)),
        )

        if pkmn.get_move(constants.HIDDEN_POWER) is not None:
            hidden_power_possibilities = [
                f"{constants.HIDDEN_POWER}{p}{constants.HIDDEN_POWER_ACTIVE_MOVE_BASE_DAMAGE_STRING}"
                for p in pkmn.hidden_power_possibilities
            ]
            for mv, _count in self.get_raw_pkmn_sets_from_pkmn_name(pkmn.name)[
                MOVES_STRING
            ]:
                if mv in hidden_power_possibilities:
                    predicted_pokemon_set.pkmn_moveset.remove_move("hiddenpower")
                    predicted_pokemon_set.pkmn_moveset.add_move(mv)
                    break

        for mv, _count in self.get_raw_pkmn_sets_from_pkmn_name(pkmn.name)[
            MOVES_STRING
        ]:
            if len(predicted_pokemon_set.pkmn_moveset.moves) >= num_predicted_moves:
                break

            if mv in predicted_pokemon_set.pkmn_moveset.moves:
                continue

            predicted_pokemon_set.pkmn_moveset.add_move(mv)
            if not self.smogon_set_makes_sense(pkmn, predicted_pokemon_set):
                predicted_pokemon_set.pkmn_moveset.remove_move(mv)

        return predicted_pokemon_set

    def pokemon_can_have_move(self, pkmn_name: str, move: str) -> bool:
        for mv, _count in self.get_raw_pkmn_sets_from_pkmn_name(pkmn_name)[
            MOVES_STRING
        ]:
            if move == mv:
                return True
        return False


TeamDatasets = _TeamDatasets()
RandomBattleTeamDatasets = _RandomBattleSets()
SmogonSets = _SmogonSets()
