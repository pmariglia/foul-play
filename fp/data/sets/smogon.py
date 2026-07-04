from __future__ import annotations

import json
import logging
import ntpath
import os
import typing
from datetime import datetime

import requests
from dateutil import relativedelta

from fp import constants
from fp.battle.helpers import normalize_name
from fp.data.sets.base import (
    DATA_DIR,
    PokemonSet,
    PokemonSets,
    spreads_are_alike,
)
from fp.format_spec import FormatSpec
from fp.generations import current_generation_mechanics

if typing.TYPE_CHECKING:
    from fp.battle.state import Pokemon

logger = logging.getLogger(__name__)

SMOGON_CACHE_DIR = os.path.join(DATA_DIR, "smogon_stats_cache")
os.makedirs(SMOGON_CACHE_DIR, exist_ok=True)

OTHER_STRING = "other"
MOVES_STRING = "moves"
ITEM_STRING = "items"
SPREADS_STRING = "spreads"
ABILITY_STRING = "abilities"
TERA_TYPE_STRING = "tera_types"
EFFECTIVENESS = "effectiveness"
TEAMMATES = "teammates"
RAW_COUNT = "raw_count"


class SmogonSets(PokemonSets):
    def __init__(self):
        self.current_pkmn_sets_url = ""
        self.raw_pkmn_sets = {}
        self.all_pkmn_counts = {}
        self.pkmn_sets = {}
        self.pkmn_mode = "uninitialized"

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
                        1 - counter_information["p"], 2
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
                        move = f"{move}{current_generation_mechanics().hidden_power_base_damage_string}"
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

    def initialize(self, format_spec: FormatSpec, pkmn_names: set[str]):
        self.pkmn_mode = format_spec.full_name
        smogon_stats_url = self._get_smogon_stats_file_name(format_spec.base_name)
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

    def get_all_remaining_trait_combinations(self, pkmn: Pokemon) -> list[PokemonSet]:
        if not self.pkmn_sets:
            logger.warning(
                "Called `get_all_remaining_trait_combinations` when pkmn_sets was empty"
            )
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

    def move_usage_rates(self, pkmn: Pokemon) -> list[tuple[str, float]]:
        # (move, usage_rate) pairs sorted by usage; smogon stats carry no
        # move associations so this is the only moveset information available
        return self.get_raw_pkmn_sets_from_pkmn_name(pkmn.name, pkmn.base_name).get(
            MOVES_STRING, []
        )
