from __future__ import annotations

import json
import logging
import os
import typing
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Tuple

import requests

from fp import constants
from fp.battle.helpers import calculate_stats
from fp.data import pokedex
from fp.battle.helpers import normalize_name
from fp.format_spec import FormatSpec
from fp.generations import current_generation_mechanics

if typing.TYPE_CHECKING:
    from fp.battle.state import Pokemon

logger = logging.getLogger(__name__)

# cache directories live in fp/data/, one level above this package
DATA_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKMN_SETS_CACHE_DIR = os.path.join(DATA_DIR, "pkmn_sets_cache")
os.makedirs(PKMN_SETS_CACHE_DIR, exist_ok=True)


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
        level_check=False,
        tera_check=True,
    ) -> bool:
        return self.pkmn_set.set_makes_sense(
            pkmn,
            match_ability=match_ability,
            match_item=match_item,
            speed_check=speed_check,
            level_check=level_check,
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
        level_check=False,
        match_tera=True,
    ):
        ability_check = not match_ability or self.ability_check(pkmn)
        item_check = not match_item or self.item_check(pkmn)
        level_check = not level_check or pkmn.level == self.level
        speed_check = not speed_check or self.speed_check(pkmn)
        tera_check = True
        if (
            match_tera
            and self.tera_type is not None
            and pkmn.terastallized
            and self.tera_type != pkmn.tera_type
        ):
            tera_check = False

        return (
            ability_check and item_check and speed_check and level_check and tera_check
        )


@dataclass
class PokemonMoveset:
    moves: Tuple[str, ...] | list[str]
    count: int = 1

    def __post_init__(self):
        new_moves = []
        for mv in self.moves:
            if mv.startswith(constants.HIDDEN_POWER) and not mv.endswith("0"):
                new_moves.append(
                    f"{mv}{current_generation_mechanics().hidden_power_base_damage_string}"
                )
            else:
                new_moves.append(mv)

        self.moves = tuple(new_moves)

    def full_set_pkmn_can_have_moves(self, pkmn: Pokemon) -> bool:
        for mv in pkmn.moves:
            if mv.name == constants.HIDDEN_POWER:
                hidden_power_possibilities = [
                    f"{constants.HIDDEN_POWER}{p}{current_generation_mechanics().hidden_power_base_damage_string}"
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


class PokemonSets(ABC):
    raw_pkmn_sets: dict[str, list]
    pkmn_sets: dict[str, list]
    pkmn_mode: str

    @abstractmethod
    def initialize(self, format_spec: FormatSpec, pkmn_names: Optional[set[str]]): ...

    def add_new_pokemon(self, pkmn_name: str):
        # by default there is nothing to learn mid-battle;
        # datasets that can incrementally learn new pokemon override this
        pass

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
        ret = []
        ret += self.get_key_in_dict_from_pkmn_name(
            pkmn.name, pkmn.base_name, pkmn.mega_name, self.pkmn_sets
        )

        pkmn_mega_info = pkmn.get_mega_pkmn_info()
        for pkmn_mega_name, _ in pkmn_mega_info:
            ret += self.get_key_in_dict_from_pkmn_name(
                pkmn_mega_name, pkmn_mega_name, None, self.pkmn_sets
            )

        return ret

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


class FullSetDatasets(PokemonSets):
    # datasets whose entries are complete sets: a trait combination
    # (ability/item/nature/evs/tera) joined with a full moveset.
    # SmogonSets is NOT one of these - smogon usage stats are marginal
    # distributions with no move associations
    @abstractmethod
    def get_all_remaining_sets(self, pkmn: Pokemon) -> list[PredictedPokemonSet]: ...

    @abstractmethod
    def get_all_possible_moves(self, pkmn: Pokemon) -> list: ...
