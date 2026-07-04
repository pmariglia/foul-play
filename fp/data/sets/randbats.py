from __future__ import annotations

import logging
import os
import typing

from fp.battle.helpers import random_battles_evs
from fp.data.sets.base import (
    PKMN_SETS_CACHE_DIR,
    PokemonMoveset,
    PokemonSet,
    PokemonSets,
    PredictedPokemonSet,
    get_sets_file,
)
from fp.format_spec import FormatSpec

if typing.TYPE_CHECKING:
    from fp.battle.state import Pokemon

logger = logging.getLogger(__name__)

PKMN_RANDBATS_REMOTE_BASE_URL = "https://pkmn.github.io/randbats/data/full/{}.json"


def get_randbats_sets_file(pkmn_randbats_mode: str) -> dict:
    cache_path = os.path.join(PKMN_SETS_CACHE_DIR, f"{pkmn_randbats_mode}.json")
    remote_url = PKMN_RANDBATS_REMOTE_BASE_URL.format(pkmn_randbats_mode)
    return get_sets_file(cache_path, remote_url)


class RandomBattleTeamDatasets(PokemonSets):
    def __init__(self):
        self.raw_pkmn_sets = {}
        self.pkmn_sets = {}
        self.pkmn_mode = "uninitialized"

    def _load_raw_sets(self, format_spec: FormatSpec):
        self.raw_pkmn_sets = get_randbats_sets_file(format_spec.base_name)

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
                            evs=random_battles_evs(),
                            count=count,
                            tera_type=tera_type,
                            level=level,
                        ),
                        pkmn_moveset=PokemonMoveset(moves=moves),
                    )
                )
            self.pkmn_sets[pkmn].sort(key=lambda x: x.pkmn_set.count, reverse=True)

    def initialize(self, format_spec: FormatSpec, pkmn_names=None):
        # pkmn_names unused here since randombattles don't have team preview
        # always load entire JSON into memory
        self.raw_pkmn_sets = {}
        self.pkmn_sets = {}
        self.pkmn_mode = format_spec.full_name
        self._load_raw_sets(format_spec)
        self._initialize_pkmn_sets()

    def predicted_level(self, pkmn: Pokemon) -> int:
        # randombattle levels are fixed per-pokemon, so the level of the first
        # set that could apply to this pokemon is the level it would have
        for pkmn_set in self.get_pkmn_sets_from_pkmn_name(pkmn):
            if pkmn_set.full_set_pkmn_can_have_set(
                pkmn,
                match_ability=True,
                match_item=True,
                speed_check=False,
                level_check=False,
                tera_check=True,
            ):
                return pkmn_set.pkmn_set.level

        raise ValueError("No set to predict a level from for {}".format(pkmn.name))

    def get_all_remaining_sets(self, pkmn: Pokemon) -> list[PredictedPokemonSet]:
        if not self.pkmn_sets:
            logger.warning("Called `get_all_remaining_sets` when pkmn_sets was empty")
            return []

        remaining_sets = []
        for pkmn_set in self.get_pkmn_sets_from_pkmn_name(pkmn):
            if pkmn_set.full_set_pkmn_can_have_set(
                pkmn,
                match_ability=True,
                match_item=True,
                speed_check=True,
                level_check=True,
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
                    level_check=False,
                    tera_check=False,
                ):
                    remaining_sets.append(pkmn_set)

        return remaining_sets

    def get_all_possible_moves(self, pkmn: Pokemon):
        if not self.pkmn_sets:
            logger.warning("Called `get_all_possible_moves` when pkmn_sets was empty")
            return []

        possible_moves = set()
        for pkmn_set in self.get_pkmn_sets_from_pkmn_name(pkmn):
            for mv in pkmn_set.pkmn_moveset.moves:
                possible_moves.add(mv)

        return list(possible_moves)
