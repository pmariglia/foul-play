from __future__ import annotations

import ntpath
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
from data import all_move_json, pokedex
from fp.helpers import calculate_stats
from fp.helpers import normalize_name

PWD = os.path.dirname(os.path.abspath(__file__))
SMOGON_CACHE_DIR = os.path.join(PWD, "smogon_stats_cache")
os.makedirs(SMOGON_CACHE_DIR, exist_ok=True)
PKMN_SETS_CACHE_DIR = os.path.join(PWD, "pkmn_sets_cache")
os.makedirs(PKMN_SETS_CACHE_DIR, exist_ok=True)

PKMN_SETS_REMOTE_BASE_URL = "https://data.foulplay.cc/{}/{}"
PS_SETS_REMOTE_BASE_URL = "https://play.pokemonshowdown.com/data/sets/{}"
PKMN_RANDBATS_REMOTE_BASE_URL = "https://pkmn.github.io/randbats/data/full/{}.json"

OTHER_STRING = "other"
MOVES_STRING = "moves"
ITEM_STRING = "items"
SPREADS_STRING = "spreads"
ABILITY_STRING = "abilities"
TERA_TYPE_STRING = "tera_types"
EFFECTIVENESS = "effectiveness"
TEAMMATES = "teammates"
RAW_COUNT = "raw_count"

if typing.TYPE_CHECKING:
    from fp.battle import Pokemon

logger = logging.getLogger(__name__)


def get_sets_file(cache_path: str, remote_url: str) -> dict:
    if os.path.exists(cache_path):
        with open(cache_path, "r") as f:
            sets = json.load(f)
        logger.info(f"Loaded from cache: {cache_path}")
        return sets

    r = requests.get(remote_url)
    if r.status_code == 200:
        sets = r.json()
    else:
        logger.warning(
            f"Could not retrieve from remote: {remote_url} "
            f"(status code {r.status_code})"
        )
        sets = {}

    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    with open(cache_path, "w") as f:
        json.dump(sets, f)
    logger.info(f"Downloaded and cached from remote: {remote_url}")
    return sets


def get_ps_sets_file(pkmn_mode: str) -> dict:
    def add_new_set(d: dict, p: str, s: str):
        if p not in d:
            d[p] = {}
        if s not in d[p]:
            d[p][s] = 0
        d[p][s] += 1

    def get_pkmn_data(n: dict, s: dict):
        for pkmn_name, pkmn_sets in s.items():
            pkmn_name = normalize_name(pkmn_name)
            for pkmn_set in pkmn_sets.values():
                moves = "|".join(sorted([normalize_name(m) for m in pkmn_set["moves"]]))
                ability = normalize_name(pkmn_set.get("ability", "noability"))
                item = normalize_name(pkmn_set.get("item", "none"))
                nature = normalize_name(pkmn_set.get("nature", "serious"))
                tera_type = normalize_name(pkmn_set.get("teraType", ""))

                # this EV handling looks stupid, but it is to deal with all generations
                # if evs dict isn't present we are in gen1 or gen2: set all to 252
                evs = pkmn_set.get(
                    "evs",
                    {
                        "hp": 252,
                        "atk": 252,
                        "def": 252,
                        "spa": 252,
                        "spd": 252,
                        "spe": 252,
                    },
                )
                # missing individual ev keys means we didn't trigger the default in the above line (we are in gen3+)
                # missing ev keys means it is 0
                evs = (
                    evs.get("hp", 0),
                    evs.get("atk", 0),
                    evs.get("def", 0),
                    evs.get("spa", 0),
                    evs.get("spd", 0),
                    evs.get("spe", 0),
                )
                evs = ",".join(str(v) for v in evs)
                set_string = f"{tera_type}|{ability}|{item}|{nature}|{evs}|{moves}"
                add_new_set(n, pkmn_name, set_string)

    cache_path = os.path.join(PKMN_SETS_CACHE_DIR, pkmn_mode, "showdown_sets.json")
    remote_url = PS_SETS_REMOTE_BASE_URL.format(f"{pkmn_mode}.json")
    sets_dict = get_sets_file(cache_path, remote_url)
    new_sets = {}
    get_pkmn_data(new_sets, sets_dict.get("dex", {}))
    get_pkmn_data(new_sets, sets_dict.get("stats", {}))
    return new_sets


def get_pkmn_sets_file(pkmn_mode: str, file_name: str) -> dict:
    cache_path = os.path.join(PKMN_SETS_CACHE_DIR, pkmn_mode, file_name)
    remote_url = PKMN_SETS_REMOTE_BASE_URL.format(pkmn_mode, file_name)
    return get_sets_file(cache_path, remote_url)


def get_randbats_sets_file(pkmn_randbats_mode: str) -> dict:
    cache_path = os.path.join(PKMN_SETS_CACHE_DIR, f"{pkmn_randbats_mode}.json")
    remote_url = PKMN_RANDBATS_REMOTE_BASE_URL.format(pkmn_randbats_mode)
    return get_sets_file(cache_path, remote_url)


def spreads_are_alike(s1, s2):
    if s1[0] != s2[0]:
        return False

    s1 = [int(v) for v in s1[1].split(",")]
    s2 = [int(v) for v in s2[1].split(",")]

    diff = [abs(i - j) for i, j in zip(s1, s2)]

    # 24 is arbitrarily chosen as the threshold for EVs to be "alike"
    return all(v <= 48 for v in diff)


@dataclass
class PredictedPokemonSet:
    pkmn_set: PokemonSet
    pkmn_moveset: PokemonMoveset

    def full_set_pkmn_can_have_set(
        self,
        pkmn: Pokemon,
        match_ability=True,
        match_item=True,
        speed_check=True,
        tera_check=True,
    ) -> bool:
        return self.pkmn_set.set_makes_sense(
            pkmn,
            match_ability=match_ability,
            match_item=match_item,
            speed_check=speed_check,
            match_tera=tera_check,
        ) and self.pkmn_moveset.full_set_pkmn_can_have_moves(pkmn)


@dataclass
class PokemonSet:
    ability: str
    item: str
    nature: str
    evs: tuple[int, ...] | list[int]
    count: int
    level: Optional[int] = 100
    tera_type: Optional[str] = None

    def speed_check(self, pkmn: Pokemon):
        """
        The only non-observable speed modifier that should allow a
        Pokemon's speed_range to be set is choicescarf
        """
        stats = calculate_stats(
            pkmn.base_stats,
            pkmn.level,
            evs=self.evs,
            nature=self.nature,
        )
        speed = stats[constants.SPEED]
        if self.item == "choicescarf":
            speed = int(speed * 1.5)

        return pkmn.speed_range.min <= speed <= pkmn.speed_range.max

    def item_check(self, pkmn: Pokemon) -> bool:
        if pkmn.mega_name is None and self.item in [
            mpi[1] for mpi in pkmn.get_mega_pkmn_info()
        ]:
            return False
        if pkmn.item == self.item and pkmn.removed_item is None:
            return True
        elif pkmn.removed_item == self.item:
            return True
        elif pkmn.item is None and pkmn.removed_item is None:
            return False
        if self.item in pkmn.impossible_items:
            return False
        elif self.item in constants.CHOICE_ITEMS and not pkmn.can_have_choice_item:
            return False
        else:
            return pkmn.item == constants.UNKNOWN_ITEM

    def ability_check(self, pkmn: Pokemon) -> bool:
        if self.ability == pkmn.ability:
            return True
        elif self.ability in pkmn.impossible_abilities:
            return False
        else:
            return pkmn.ability is None

    def set_makes_sense(
        self,
        pkmn: Pokemon,
        match_ability=True,
        match_item=True,
        speed_check=True,
        match_tera=True,
    ):
        ability_check = not match_ability or self.ability_check(pkmn)
        item_check = not match_item or self.item_check(pkmn)
        speed_check = not speed_check or self.speed_check(pkmn)
        tera_check = True
        if (
            match_tera
            and self.tera_type is not None
            and pkmn.terastallized
            and self.tera_type != pkmn.tera_type
        ):
            tera_check = False

        return ability_check and item_check and speed_check and tera_check


@dataclass
class PokemonMoveset:
    moves: Tuple[str, ...] | list[str]
    count: int = 1

    def __post_init__(self):
        new_moves = []
        for mv in self.moves:
            if mv.startswith(constants.HIDDEN_POWER) and not mv.endswith("0"):
                new_moves.append(
                    f"{mv}{constants.HIDDEN_POWER_ACTIVE_MOVE_BASE_DAMAGE_STRING}"
                )
            else:
                new_moves.append(mv)

        self.moves = tuple(new_moves)

    def full_set_pkmn_can_have_moves(self, pkmn: Pokemon) -> bool:
        for mv in pkmn.moves:
            if mv.name == constants.HIDDEN_POWER:
                hidden_power_possibilities = [
                    f"{constants.HIDDEN_POWER}{p}{constants.HIDDEN_POWER_ACTIVE_MOVE_BASE_DAMAGE_STRING}"
                    for p in pkmn.hidden_power_possibilities
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


class PokemonSets:
    raw_pkmn_sets: dict[str, list]
    pkmn_sets: dict[str, list]
    pkmn_mode: str

    def initialize(self, pkmn_mode: str, pkmn_names: set[str]): ...

    def predict_set(self, pkmn: Pokemon) -> Optional[PredictedPokemonSet]: ...

    @staticmethod
    def get_key_in_dict_from_pkmn_name(
        pkmn_name: str, pkmn_base_name: str, pkmn_mega_name: str | None, d: dict
    ):
        if pkmn_mega_name in d:
            return d[pkmn_mega_name]
        elif pkmn_name in d:
            return d[pkmn_name]
        elif pkmn_base_name in d:
            return d[pkmn_base_name]

        if pkmn_name in pokedex and "baseSpecies" in pokedex[pkmn_name]:
            pkmn_base_species = normalize_name(pokedex[pkmn_name]["baseSpecies"])
            if pkmn_base_species in d:
                return d[pkmn_base_species]

        if pkmn_name in pokedex and "name" in pokedex[pkmn_name]:
            pkmn_non_cosmetic_name = normalize_name(pokedex[pkmn_name]["name"])
            if pkmn_non_cosmetic_name in d:
                return d[pkmn_non_cosmetic_name]

        return []

    def get_pkmn_sets_from_pkmn_name(self, pkmn: Pokemon):
        return self.get_key_in_dict_from_pkmn_name(
            pkmn.name, pkmn.base_name, pkmn.mega_name, self.pkmn_sets
        )

    def get_raw_pkmn_sets_from_pkmn_name(self, pkmn_name: str, pkmn_base_name: str):
        if pkmn_name in self.raw_pkmn_sets:
            return self.raw_pkmn_sets[pkmn_name]
        elif pkmn_base_name in self.raw_pkmn_sets:
            return self.raw_pkmn_sets[pkmn_base_name]

        if pkmn_name in pokedex and "baseSpecies" in pokedex[pkmn_name]:
            pkmn_base_species = normalize_name(pokedex[pkmn_name]["baseSpecies"])
            if pkmn_base_species in self.raw_pkmn_sets:
                return self.raw_pkmn_sets[pkmn_base_species]

        if pkmn_name in pokedex and "name" in pokedex[pkmn_name]:
            pkmn_non_cosmetic_name = normalize_name(pokedex[pkmn_name]["name"])
            if pkmn_non_cosmetic_name in self.raw_pkmn_sets:
                return self.raw_pkmn_sets[pkmn_non_cosmetic_name]

        return {}


class _RandomBattleSets(PokemonSets):
    def __init__(self):
        self.raw_pkmn_sets = {}
        self.pkmn_sets = {}
        self.pkmn_mode = "uninitialized"

    def _load_raw_sets(self, generation):
        if generation.endswith("blitz"):
            generation = generation[:-5]
        self.raw_pkmn_sets = get_randbats_sets_file(f"{generation}randombattle")

    def _initialize_pkmn_sets(self):
        for pkmn, sets in self.raw_pkmn_sets.items():
            self.pkmn_sets[pkmn] = []
            for set_, count in sets.items():
                set_split = set_.split(",")
                level = int(set_split[0])
                item = set_split[1]
                ability = set_split[2]
                moves = set_split[3:7]
                tera_type = None
                if len(set_split) > 7:
                    tera_type = set_split[7]
                self.pkmn_sets[pkmn].append(
                    PredictedPokemonSet(
                        pkmn_set=PokemonSet(
                            ability=ability,
                            item=item,
                            nature="serious",
                            evs=(85, 85, 85, 85, 85, 85),
                            count=count,
                            tera_type=tera_type,
                            level=level,
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

    def predict_set(
        self, pkmn: Pokemon, match_traits=True
    ) -> Optional[PredictedPokemonSet]:
        if not self.pkmn_sets:
            logger.warning("Called `predict_set` when pkmn_sets was empty")

        for pkmn_set in self.get_pkmn_sets_from_pkmn_name(pkmn):
            if pkmn_set.full_set_pkmn_can_have_set(
                pkmn,
                match_ability=match_traits,
                match_item=match_traits,
                speed_check=False,  # speed check never makes sense for randombattles because we know the nature/evs
                tera_check=match_traits,
            ):
                return pkmn_set

        return None

    def get_all_remaining_sets(self, pkmn: Pokemon) -> list[PredictedPokemonSet]:
        if not self.pkmn_sets:
            logger.warning("Called `predict_set` when pkmn_sets was empty")
            return []

        remaining_sets = []
        for pkmn_set in self.get_pkmn_sets_from_pkmn_name(pkmn):
            if pkmn_set.full_set_pkmn_can_have_set(
                pkmn,
                match_ability=True,
                match_item=True,
                speed_check=False,  # speed check never makes sense for randombattles because we know the nature/evs
                tera_check=True,
            ):
                remaining_sets.append(pkmn_set)

        if not remaining_sets:
            for pkmn_set in self.get_pkmn_sets_from_pkmn_name(pkmn):
                if pkmn_set.full_set_pkmn_can_have_set(
                    pkmn,
                    match_ability=False,
                    match_item=False,
                    speed_check=False,
                    tera_check=False,
                ):
                    remaining_sets.append(pkmn_set)

        return remaining_sets

    def get_all_possible_moves(self, pkmn: Pokemon):
        if not self.pkmn_sets:
            logger.warning("Called `predict_set` when pkmn_sets was empty")
            return []

        possible_moves = set()
        for pkmn_set in self.get_pkmn_sets_from_pkmn_name(pkmn):
            for mv in pkmn_set.pkmn_moveset.moves:
                possible_moves.add(mv)

        return list(possible_moves)


class _TeamDatasets(PokemonSets):
    def __init__(self):
        self.raw_pkmn_sets = {}
        self.raw_pkmn_moves = {}
        self.pkmn_sets = {}
        self.pkmn_mode = "uninitialized"

    def _get_sets_dict(self):
        ps_sets = get_ps_sets_file(self.pkmn_mode)
        full_sets = get_pkmn_sets_file(self.pkmn_mode, "pokemon_full_sets.json")
        for pkmn, sets in ps_sets.items():
            if pkmn not in full_sets:
                full_sets[pkmn] = sets
            else:
                for set_, count in sets.items():
                    if set_ not in full_sets[pkmn]:
                        full_sets[pkmn][set_] = count
                    else:
                        full_sets[pkmn][set_] += count
        return full_sets

    def _get_moves_dict(self):
        return get_pkmn_sets_file(self.pkmn_mode, "replay_moves.json")

    def _get_battle_factory_sets_dict(self, tier_name):
        return get_pkmn_sets_file(self.pkmn_mode, "factory-sets.json")[tier_name]

    def _load_battle_factory_team_datasets(self, pkmn_names: set[str], tier_name: str):
        sets_dict = self._get_battle_factory_sets_dict(tier_name)
        for pkmn in pkmn_names:
            try:
                self.raw_pkmn_sets[pkmn] = sets_dict[pkmn]
            except KeyError:
                logger.warning("No pokemon sets for {}".format(pkmn))

    def _load_team_datasets(self, pkmn_names: set[str], get_all_pkmn: bool):
        sets_dict = self._get_sets_dict()
        all_pkmn_moves = self._get_moves_dict()
        iter_list = all_pkmn_moves.keys() if get_all_pkmn else pkmn_names
        for pkmn in iter_list:
            if pkmn not in sets_dict:
                sets_dict[pkmn] = {}
            self.raw_pkmn_sets[pkmn] = sets_dict[pkmn]
            self.raw_pkmn_moves[pkmn] = []
            for moves_str, count in all_pkmn_moves.get(pkmn, {}).items():
                moves = moves_str.split("|")
                self.raw_pkmn_moves[pkmn].append(
                    PokemonMoveset(moves=tuple(moves), count=count)
                )

    def _add_to_pkmn_sets(self, raw_sets: dict[str, list]):
        for pkmn, sets in raw_sets.items():
            self.pkmn_sets[pkmn] = []
            for set_, count in sets.items():
                set_split = set_.split("|")
                tera_type = set_split[0] or "typeless"
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
        get_all_pkmn = any(
            g in pkmn_mode
            for g in [
                "gen1",
                "gen2",
                "gen3",
                "gen4",
            ]
        )
        if battle_factory_tier_name:
            self._load_battle_factory_team_datasets(
                pkmn_names, battle_factory_tier_name
            )
        else:
            self._load_team_datasets(pkmn_names, get_all_pkmn)
        self._add_to_pkmn_sets(self.raw_pkmn_sets)

    def add_new_pokemon(self, pkmn_name: str):
        sets_dict = self._get_sets_dict()
        all_pkmn_moves = self._get_moves_dict()
        if pkmn_name not in sets_dict:
            return
        self.raw_pkmn_moves[pkmn_name] = []
        for moves_str, count in all_pkmn_moves.get(pkmn_name, {}).items():
            moves = moves_str.split("|")
            self.raw_pkmn_moves[pkmn_name].append(
                PokemonMoveset(moves=tuple(moves), count=count)
            )
        self._add_to_pkmn_sets({pkmn_name: sets_dict[pkmn_name]})

    def get_all_remaining_sets(self, pkmn: Pokemon) -> list[PredictedPokemonSet]:
        if not self.pkmn_sets:
            return []

        remaining_sets = []
        for pkmn_set in self.get_pkmn_sets_from_pkmn_name(pkmn):
            if pkmn_set.full_set_pkmn_can_have_set(
                pkmn,
                match_ability=True,
                match_item=True,
                speed_check=True,
                tera_check=True,
            ):
                remaining_sets.append(pkmn_set)

        # do not do this extra check for TeamDatasets unless in battlefactory mode
        if not remaining_sets and self.pkmn_mode.endswith("battlefactory"):
            for pkmn_set in self.get_pkmn_sets_from_pkmn_name(pkmn):
                if pkmn_set.full_set_pkmn_can_have_set(
                    pkmn,
                    match_ability=False,
                    match_item=False,
                    speed_check=False,
                    tera_check=False,
                ):
                    remaining_sets.append(pkmn_set)

        return remaining_sets

    def get_all_possible_move_combinations(self, pkmn: Pokemon, pkmn_set: PokemonSet):
        valid_movesets = []
        for pkmn_moveset in self.get_key_in_dict_from_pkmn_name(
            pkmn.name, pkmn.base_name, pkmn.mega_name, self.raw_pkmn_moves
        ):
            if PredictedPokemonSet(
                pkmn_set=pkmn_set, pkmn_moveset=pkmn_moveset
            ).full_set_pkmn_can_have_set(pkmn):
                valid_movesets.append(pkmn_moveset)

        return valid_movesets

    def get_all_possible_moves(self, pkmn: Pokemon):
        if not self.pkmn_sets:
            logger.warning("Called `predict_set` when pkmn_sets was empty")
            return []

        possible_moves = set()
        for pkmn_set in self.get_pkmn_sets_from_pkmn_name(pkmn):
            for mv in pkmn_set.pkmn_moveset.moves:
                possible_moves.add(mv)

        return list(possible_moves)

    def predict_set(
        self, pkmn: Pokemon, match_traits=True
    ) -> Optional[PredictedPokemonSet]:
        for pkmn_set in self.get_pkmn_sets_from_pkmn_name(pkmn):
            if pkmn_set.full_set_pkmn_can_have_set(
                pkmn,
                match_ability=match_traits,
                match_item=match_traits,
                speed_check=True,
                tera_check=match_traits,
            ):
                return pkmn_set

        return None


class _SmogonSets(PokemonSets):
    def __init__(self):
        self.current_pkmn_sets_url = ""
        self.raw_pkmn_sets = {}
        self.all_pkmn_counts = {}
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

    def _get_pokemon_information(self, smogon_stats_url, pkmn_names) -> dict:
        infos = self._get_smogon_stats_json(smogon_stats_url)
        self.all_pkmn_counts.clear()

        final_infos = {}
        for pkmn_name, pkmn_information in infos.items():
            normalized_name = normalize_name(pkmn_name)
            self.all_pkmn_counts[normalized_name] = {}
            self.all_pkmn_counts[normalized_name][RAW_COUNT] = pkmn_information[
                "Raw count"
            ]
            self.all_pkmn_counts[normalized_name][TEAMMATES] = {}
            for teammate_name, teammate_count in pkmn_information["Teammates"].items():
                self.all_pkmn_counts[normalized_name][TEAMMATES][
                    normalize_name(teammate_name)
                ] = teammate_count

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
                percentage = count / total_count
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
                    items.append((item, count / total_count))

            for move, count in pkmn_information["Moves"].items():
                if count > 0 and move and move.lower() != "nothing":
                    if move.startswith(constants.HIDDEN_POWER):
                        move = f"{move}{constants.HIDDEN_POWER_ACTIVE_MOVE_BASE_DAMAGE_STRING}"
                    moves.append((move, count / total_count))

            for ability, count in pkmn_information["Abilities"].items():
                if count > 0:
                    abilities.append((ability, count / total_count))

            for tera_type, count in pkmn_information["Tera Types"].items():
                if tera_type == "nothing":
                    tera_type = "typeless"
                if count > 0:
                    tera_types.append((tera_type, count / total_count))

            final_infos[normalized_name][SPREADS_STRING] = sorted(
                spreads, key=lambda x: x[2], reverse=True
            )[:20]
            final_infos[normalized_name][ITEM_STRING] = sorted(
                items, key=lambda x: x[1], reverse=True
            )[:10]
            final_infos[normalized_name][MOVES_STRING] = sorted(
                moves, key=lambda x: x[1], reverse=True
            )[:100]
            final_infos[normalized_name][ABILITY_STRING] = sorted(
                abilities, key=lambda x: x[1], reverse=True
            )
            final_infos[normalized_name][TERA_TYPE_STRING] = sorted(
                tera_types, key=lambda x: x[1], reverse=True
            )[:6]
            final_infos[normalized_name][EFFECTIVENESS] = matchup_effectiveness

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
        # Without a large amount in the supporting stat choice items don't make sense
        if pkmn_set.item == "choiceband" and pkmn_set.evs[1] < 204:
            return False
        if pkmn_set.item == "choicespecs" and pkmn_set.evs[3] < 204:
            return False
        if pkmn_set.item == "choicescarf" and pkmn_set.evs[5] < 204:
            return False

        # without a large amount in an offensive stat life orb and expert belt don't make sense
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
                                count=(ability[1] * item[1] * spread[2] * tera_type[1]),
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

    def get_all_remaining_sets(self, pkmn: Pokemon) -> list[PredictedPokemonSet]:
        if not self.pkmn_sets:
            logger.warning("Called `predict_set` when pkmn_sets was empty")
            return []

        remaining_sets = []
        for pkmn_set in self.get_pkmn_sets_from_pkmn_name(pkmn):
            if pkmn_set.set_makes_sense(
                pkmn,
            ):
                remaining_sets.append(pkmn_set)

        if not remaining_sets:
            for pkmn_set in self.get_pkmn_sets_from_pkmn_name(pkmn):
                if pkmn_set.set_makes_sense(
                    pkmn,
                    match_ability=False,
                    match_item=False,
                    match_tera=False,
                    speed_check=False,
                ):
                    remaining_sets.append(pkmn_set)

        return remaining_sets

    def predict_set(
        self, pkmn: Pokemon, num_predicted_moves=4, match_traits=True
    ) -> Optional[PredictedPokemonSet]:
        if not self.pkmn_sets:
            logger.warning("Called `predict_set` when pkmn_sets was empty")

        pokemon_set = None
        for pkmn_set in self.get_pkmn_sets_from_pkmn_name(pkmn):
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
            for mv, _count in self.get_raw_pkmn_sets_from_pkmn_name(
                pkmn.name, pkmn.base_name
            )[MOVES_STRING]:
                if mv in hidden_power_possibilities:
                    predicted_pokemon_set.pkmn_moveset.remove_move("hiddenpower")
                    predicted_pokemon_set.pkmn_moveset.add_move(mv)
                    break

        for mv, _count in self.get_raw_pkmn_sets_from_pkmn_name(
            pkmn.name, pkmn.base_name
        )[MOVES_STRING]:
            if len(predicted_pokemon_set.pkmn_moveset.moves) >= num_predicted_moves:
                break

            if mv in predicted_pokemon_set.pkmn_moveset.moves:
                continue

            predicted_pokemon_set.pkmn_moveset.add_move(mv)
            if not self._smogon_predicted_move_set_makes_sense(predicted_pokemon_set):
                predicted_pokemon_set.pkmn_moveset.remove_move(mv)

        return predicted_pokemon_set


TeamDatasets = _TeamDatasets()
RandomBattleTeamDatasets = _RandomBattleSets()
SmogonSets = _SmogonSets()
