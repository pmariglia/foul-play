from __future__ import annotations

import logging
import os
import typing

from fp.battle.helpers import normalize_name
from fp.data.sets.base import (
    PKMN_SETS_CACHE_DIR,
    PokemonMoveset,
    PokemonSet,
    FullSetDatasets,
    PredictedPokemonSet,
    get_sets_file,
)
from fp.format_spec import FormatSpec

if typing.TYPE_CHECKING:
    from fp.battle.state import Pokemon

logger = logging.getLogger(__name__)

PKMN_SETS_REMOTE_BASE_URL = "https://data.foulplay.cc/{}/{}"
PS_SETS_REMOTE_BASE_URL = "https://play.pokemonshowdown.com/data/sets/{}"


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


class TeamDatasets(FullSetDatasets):
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

    def initialize(self, format_spec: FormatSpec, pkmn_names: set[str]):
        self.raw_pkmn_sets = {}
        self.pkmn_sets = {}
        self.pkmn_mode = format_spec.full_name
        get_all_pkmn = format_spec.gen_number in (1, 2, 3, 4)
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

        return remaining_sets

    def get_all_possible_move_combinations(self, pkmn: Pokemon, pkmn_set: PokemonSet):
        valid_movesets = []
        for pkmn_moveset in self.get_pkmn_by_name_in_dict(pkmn, self.raw_pkmn_moves):
            if PredictedPokemonSet(
                pkmn_set=pkmn_set, pkmn_moveset=pkmn_moveset
            ).full_set_pkmn_can_have_set(pkmn):
                valid_movesets.append(pkmn_moveset)

        return valid_movesets

    def get_all_possible_moves(self, pkmn: Pokemon):
        if not self.pkmn_sets:
            logger.warning("Called `get_all_possible_moves` when pkmn_sets was empty")
            return []

        possible_moves = set()
        for pkmn_set in self.get_pkmn_sets_from_pkmn_name(pkmn):
            for mv in pkmn_set.pkmn_moveset.moves:
                possible_moves.add(mv)

        return list(possible_moves)


class BattleFactoryTeamDatasets(TeamDatasets):
    # a battle factory dataset is scoped to a single tier's set pool,
    # so the tier is part of the instance's identity rather than an initialize arg
    def __init__(self, battle_factory_tier_name: str):
        super().__init__()
        self.battle_factory_tier_name = battle_factory_tier_name

    def _get_battle_factory_sets_dict(self, tier_name):
        return get_pkmn_sets_file(self.pkmn_mode, "factory-sets.json")[tier_name]

    def _load_battle_factory_team_datasets(self, pkmn_names: set[str], tier_name: str):
        sets_dict = self._get_battle_factory_sets_dict(tier_name)
        for pkmn in pkmn_names:
            try:
                self.raw_pkmn_sets[pkmn] = sets_dict[pkmn]
            except KeyError:
                logger.warning("No pokemon sets for {}".format(pkmn))

    def initialize(self, format_spec: FormatSpec, pkmn_names: set[str]):
        self.raw_pkmn_sets = {}
        self.pkmn_sets = {}
        self.pkmn_mode = format_spec.full_name
        self._load_battle_factory_team_datasets(
            pkmn_names, self.battle_factory_tier_name
        )
        self._add_to_pkmn_sets(self.raw_pkmn_sets)

    def get_all_remaining_sets(self, pkmn: Pokemon) -> list[PredictedPokemonSet]:
        remaining_sets = super().get_all_remaining_sets(pkmn)

        # do not do this extra check for TeamDatasets unless in battlefactory mode
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
