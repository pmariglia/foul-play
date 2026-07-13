from __future__ import annotations

import json
import logging
import os
import typing
from abc import ABC, abstractmethod
from copy import copy
from dataclasses import dataclass
from typing import Optional, Tuple

import requests

from fp import constants
from fp.battle.helpers import calculate_stats, natures, maximum_ev
from fp.data import pokedex, all_move_json
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

    evs_within = current_generation_mechanics().max_ev / 4
    return all(v <= evs_within for v in diff)


# checks if a damaging move, be it physical or special, is "utility"
# a bit of an arbitrary way to categorize, but this informs whether
# is allowed to be guessed on sets that have EVs in the other stat
# the most basic example is: physical pivot moves can be on special sets
def damaging_move_is_utility(move_data: dict) -> bool:
    if move_data[constants.ID] in {
        "uturn",
        "voltswitch",
        "flipturn",
        "nuzzle",
        "selfdestruct",
        "explosion",
        "knockoff",
    }:
        return True

    if move_data[constants.PRIORITY] > 0:
        return True

    return False


@dataclass
class PredictedPokemonSet:
    pkmn_set: PokemonSet
    pkmn_moveset: PokemonMoveset

    # Returns False if some observation in the Pokemon renders this an illogical set.
    # e.g. you used to different moves but this set has a choice item
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
        ) and self.pkmn_moveset.makes_sense_on_pkmn(pkmn)

    # Is this set on its own logical?
    # e.g. swordsdance with choiceband should return False
    def set_makes_logical_sense(self) -> bool:
        trickable_items = {
            "choicespecs",
            "choicescarf",
            "choiceband",
            "assaultvest",
            "blacksludge",
            "stickybarb",
            "flameorb",
            "toxicorb",
        }

        match self.pkmn_set.item:
            case "lightclay":
                has_screen = False
                screens = {"reflect", "lightscreen", "auroraveil"}
                for mv in self.pkmn_moveset.moves:
                    if mv in screens:
                        has_screen = True
                if not has_screen:
                    return False

            case "toxicorb":
                if self.pkmn_set.ability not in [
                    "poisonheal",
                    "quickfeet",
                    "magicguard",
                    "marvelscale",
                    "guts",
                    "toxicboost",
                ]:
                    return False

            case "flameorb":
                if self.pkmn_set.ability not in [
                    "quickfeet",
                    "magicguard",
                    "guts",
                    "flareboost",
                ]:
                    return False

            case "choiceband" | "choicespecs" | "choicescarf":
                if not self.choice_item_logical():
                    return False

            case "assaultvest":
                if self.pkmn_set.ability != "klutz" and any(
                    all_move_json[mv][constants.CATEGORY]
                    == constants.MoveCategory.STATUS
                    for mv in self.pkmn_moveset.moves
                ):
                    return False

        match self.pkmn_set.ability:
            case "poisonheal":
                if self.pkmn_set.item != "toxicorb":
                    return False

        for mv in self.pkmn_moveset.moves:
            move_data = all_move_json[mv]
            if not damaging_move_is_utility(move_data):
                match move_data[constants.CATEGORY]:
                    case constants.MoveCategory.PHYSICAL:
                        if self.pkmn_set.evs[3] > 0:
                            return False

                    case constants.MoveCategory.SPECIAL:
                        if self.pkmn_set.evs[1] > 0:
                            return False

                    case constants.MoveCategory.STATUS:
                        ...

            match mv:
                case "protect":
                    if self.pkmn_set.item in constants.CHOICE_ITEMS:
                        return False

                case (
                    "swordsdance"
                    | "dragondance"
                    | "tidyup"
                    | "sharpen"
                    | "meditate"
                    | "honeclaws"
                    | "bellydrum"
                    | "howl"
                    | "shiftgear"
                ):
                    if not self.physical_boosting_move_logical(mv):
                        return False

                case "nastyplot" | "tailglow":
                    if not self.special_boosting_move_logical(mv):
                        return False

                case "bulkup" | "curse":
                    if self.pkmn_set.item in constants.CHOICE_ITEMS:
                        return False
                    if self.pkmn_set.evs[3] > 0:
                        return False
                    if (
                        natures[self.pkmn_set.nature]["plus"]
                        == constants.SPECIAL_ATTACK
                    ):
                        return False

                case "calmmind":
                    if self.pkmn_set.item in constants.CHOICE_ITEMS:
                        return False
                    if self.pkmn_set.evs[1] > 0:
                        return False
                    if natures[self.pkmn_set.nature]["plus"] == constants.ATTACK:
                        return False

                case "trick" | "switcheroo":
                    if self.pkmn_set.item not in trickable_items:
                        return False

                case "batonpass":
                    has_boosting_move = False
                    for mv in self.pkmn_moveset.moves:
                        move_data = all_move_json[mv]
                        if (
                            constants.BOOSTS in move_data
                            and move_data[constants.TARGET] == constants.MoveTarget.SELF
                        ):
                            has_boosting_move = True
                    if not has_boosting_move:
                        return False

        return True

    def choice_item_logical(self):
        item = self.pkmn_set.item
        match item:
            case "choiceband":
                logical_moves = [constants.MoveCategory.PHYSICAL]
            case "choicespecs":
                logical_moves = [constants.MoveCategory.SPECIAL]
            case "choicescarf":
                logical_moves = [
                    constants.MoveCategory.PHYSICAL,
                    constants.MoveCategory.SPECIAL,
                ]
            case _:
                raise ValueError("Invalid choice item: {}".format(item))

        num_illogical_moves = 0
        for mv in self.pkmn_moveset.moves:
            if all_move_json[mv][
                constants.CATEGORY
            ] not in logical_moves and mv not in [
                "trick",
                "switcheroo",
                "flipturn",
                "uturn",
                "voltswitch",
            ]:
                num_illogical_moves += 1

        return num_illogical_moves <= 1

    def physical_boosting_move_logical(self, mv: str) -> bool:
        if self.pkmn_set.item in constants.CHOICE_ITEMS:
            return False

        # do not allow more than 1 non-physical move, excluding the boosting move
        if (
            sum(
                m != mv
                and all_move_json[m][constants.CATEGORY]
                != constants.MoveCategory.PHYSICAL
                for m in self.pkmn_moveset.moves
            )
            > 1
        ):
            return False

        minimum_offensive_ev = maximum_ev() / 4
        if self.pkmn_set.evs[1] < minimum_offensive_ev:
            return False

        if (
            natures[self.pkmn_set.nature]["plus"] == constants.SPECIAL_ATTACK
            or natures[self.pkmn_set.nature]["minus"] == constants.ATTACK
        ):
            return False

        return True

    def special_boosting_move_logical(self, mv: str) -> bool:
        if self.pkmn_set.item in constants.CHOICE_ITEMS:
            return False

        # do not allow more than 1 non-special move, excluding the boosting move
        if (
            sum(
                m != mv
                and all_move_json[m][constants.CATEGORY]
                != constants.MoveCategory.SPECIAL
                for m in self.pkmn_moveset.moves
            )
            > 1
        ):
            return False

        minimum_offensive_ev = maximum_ev() / 4
        if self.pkmn_set.evs[3] < minimum_offensive_ev:
            return False

        if (
            natures[self.pkmn_set.nature]["plus"] == constants.ATTACK
            or natures[self.pkmn_set.nature]["minus"] == constants.SPECIAL_ATTACK
        ):
            return False

        return True


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
        ability_check = (
            bool(pkmn.mega_name) or not match_ability or self.ability_check(pkmn)
        )
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

    def makes_sense_on_pkmn(self, pkmn: Pokemon) -> bool:
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
    def get_pkmn_by_name_in_dict(pkmn: Pokemon, d: dict):
        if pkmn.mega_name in d:
            return d[pkmn.mega_name]
        elif pkmn.name in d:
            return d[pkmn.name]
        elif pkmn.base_name in d:
            return d[pkmn.base_name]

        if pkmn.name in pokedex and "baseSpecies" in pokedex[pkmn.name]:
            pkmn_base_species = normalize_name(pokedex[pkmn.name]["baseSpecies"])
            if pkmn_base_species in d:
                return d[pkmn_base_species]

        if pkmn.name in pokedex and "name" in pokedex[pkmn.name]:
            pkmn_non_cosmetic_name = normalize_name(pokedex[pkmn.name]["name"])
            if pkmn_non_cosmetic_name in d:
                return d[pkmn_non_cosmetic_name]

        return []

    def get_pkmn_sets_from_pkmn_name(self, pkmn: Pokemon):
        return copy(self.get_pkmn_by_name_in_dict(pkmn, self.pkmn_sets))


class FullSetDatasets(PokemonSets):
    # datasets whose entries are complete sets: a trait combination
    # (ability/item/nature/evs/tera) joined with a full moveset.
    # SmogonSets is NOT one of these - smogon usage stats are marginal
    # distributions with no move associations
    @abstractmethod
    def get_all_remaining_sets(self, pkmn: Pokemon) -> list[PredictedPokemonSet]: ...

    @abstractmethod
    def get_all_possible_moves(self, pkmn: Pokemon) -> list: ...
