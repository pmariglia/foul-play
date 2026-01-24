import logging
import random
from copy import deepcopy

import constants
from data import all_move_json, pokedex
from fp.search.helpers import populate_pkmn_from_set
from fp.helpers import natures, normalize_name
from fp.battle import Pokemon, Battle, Battler
from data.pkmn_sets import (
    SmogonSets,
    PokemonSet,
    PredictedPokemonSet,
    PokemonMoveset,
    MOVES_STRING,
    TeamDatasets,
    RAW_COUNT,
    TEAMMATES,
)

logger = logging.getLogger(__name__)


TRICKABLE_ITEMS = {
    "choicespecs",
    "choicescarf",
    "choiceband",
    "assaultvest",
    "blacksludge",
    "stickybarb",
    "flameorb",
    "toxicorb",
}


def physical_boosting_move(mv: str, predicted_pkmn_set: PredictedPokemonSet) -> bool:
    if predicted_pkmn_set.pkmn_set.item in constants.CHOICE_ITEMS:
        return False

    # do not allow more than 1 non-physical move, excluding the boosting move
    if (
        sum(
            m != mv and all_move_json[m][constants.CATEGORY] != constants.PHYSICAL
            for m in predicted_pkmn_set.pkmn_moveset.moves
        )
        > 1
    ):
        return False

    return True


def special_boosting_move(mv: str, predicted_pkmn_set: PredictedPokemonSet) -> bool:
    if predicted_pkmn_set.pkmn_set.item in constants.CHOICE_ITEMS:
        return False

    # do not allow more than 1 non-special move, excluding the boosting move
    if (
        sum(
            m != mv and all_move_json[m][constants.CATEGORY] != constants.SPECIAL
            for m in predicted_pkmn_set.pkmn_moveset.moves
        )
        > 1
    ):
        return False

    return True


def choice_item(predicted_pkmn_set: PredictedPokemonSet):
    item = predicted_pkmn_set.pkmn_set.item
    match item:
        case "choiceband":
            logical_moves = [constants.PHYSICAL]
        case "choicespecs":
            logical_moves = [constants.SPECIAL]
        case "choicescarf":
            logical_moves = [constants.PHYSICAL, constants.SPECIAL]
        case _:
            raise ValueError("Invalid choice item: {}".format(item))

    num_illogical_moves = 0
    for mv in predicted_pkmn_set.pkmn_moveset.moves:
        if all_move_json[mv][constants.CATEGORY] not in logical_moves and mv not in [
            "trick",
            "switcheroo",
            "flipturn",
            "uturn",
            "voltswitch",
        ]:
            num_illogical_moves += 1

    return num_illogical_moves <= 1


def smogon_set_makes_sense(predicted_pkmn_set: PredictedPokemonSet):
    match predicted_pkmn_set.pkmn_set.item:
        case "toxicorb":
            if predicted_pkmn_set.pkmn_set.ability not in [
                "poisonheal",
                "quickfeet",
                "magicguard",
                "marvelscale",
                "guts",
                "toxicboost",
            ]:
                return False

        case "flameorb":
            if predicted_pkmn_set.pkmn_set.ability not in [
                "quickfeet",
                "magicguard",
                "guts",
                "flareboost",
            ]:
                return False

        case "choiceband" | "choicespecs" | "choicescarf":
            if not choice_item(predicted_pkmn_set):
                return False

        case "assaultvest":
            if predicted_pkmn_set.pkmn_set.ability != "klutz" and any(
                all_move_json[mv][constants.CATEGORY] == constants.STATUS
                for mv in predicted_pkmn_set.pkmn_moveset.moves
            ):
                return False

    match predicted_pkmn_set.pkmn_set.ability:
        case "poisonheal":
            if predicted_pkmn_set.pkmn_set.item != "toxicorb":
                return False

    for mv in predicted_pkmn_set.pkmn_moveset.moves:
        match mv:
            case "protect":
                if predicted_pkmn_set.pkmn_set.item in constants.CHOICE_ITEMS:
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
                if not physical_boosting_move(mv, predicted_pkmn_set):
                    return False

            case "nastyplot" | "tailglow":
                if not special_boosting_move(mv, predicted_pkmn_set):
                    return False

            case "bulkup" | "curse":
                if predicted_pkmn_set.pkmn_set.item in constants.CHOICE_ITEMS:
                    return False
                if predicted_pkmn_set.pkmn_set.evs[3] > 0:
                    return False
                if (
                    natures[predicted_pkmn_set.pkmn_set.nature]["plus"]
                    == constants.SPECIAL_ATTACK
                ):
                    return False

            case "calmmind":
                if predicted_pkmn_set.pkmn_set.item in constants.CHOICE_ITEMS:
                    return False
                if predicted_pkmn_set.pkmn_set.evs[1] > 0:
                    return False
                if (
                    natures[predicted_pkmn_set.pkmn_set.nature]["plus"]
                    == constants.ATTACK
                ):
                    return False

            case "trick" | "switcheroo":
                if predicted_pkmn_set.pkmn_set.item not in TRICKABLE_ITEMS:
                    return False

    return True


def adjust_probabilities_for_sampling(move_rates, num_moves=4):
    adjusted_rates = []

    for move, rate in move_rates:
        # Compute the adjusted rate for sampling
        adjusted_rate = 1 - (1 - rate) ** (1 / num_moves)
        adjusted_rates.append((move, adjusted_rate))

    return adjusted_rates


def get_filtered_sets(
    pkmn: Pokemon, remaining_sets: list[PokemonSet]
) -> list[PokemonSet]:
    filtered_sets = []
    for pkmn_set in remaining_sets:
        if smogon_set_makes_sense(
            PredictedPokemonSet(
                pkmn_set=pkmn_set,
                pkmn_moveset=PokemonMoveset(moves=tuple(m.name for m in pkmn.moves)),
            )
        ):
            filtered_sets.append(pkmn_set)

    return filtered_sets


def sample_pokemon_moveset_with_known_pkmn_set(pkmn: Pokemon, pkmn_set: PokemonSet):
    pkmn_known_moves = [m.name for m in pkmn.moves]
    num_known_moves = len(pkmn_known_moves)
    if num_known_moves >= 4:
        return pkmn_known_moves

    # 1: Use TeamDatasets' movesets to sample a moveset, if possible
    remaining_team_movesets = []
    for pkmn_moveset in TeamDatasets.get_all_possible_move_combinations(pkmn, pkmn_set):
        if not smogon_set_makes_sense(
            PredictedPokemonSet(
                pkmn_set=pkmn_set,
                pkmn_moveset=pkmn_moveset,
            )
        ):
            continue
        num_pkmn_moves = len(pkmn_moveset)

        # movesets with more moves known are more likely to be sampled
        if num_pkmn_moves == 2:
            count = pkmn_moveset.count
        elif num_pkmn_moves == 3:
            count = pkmn_moveset.count * 2
        else:
            count = pkmn_moveset.count * 3
        remaining_team_movesets.append((pkmn_moveset, count))

    if remaining_team_movesets:
        sampled_moveset, count = random.choices(
            remaining_team_movesets, weights=[m[1] for m in remaining_team_movesets]
        )[0]
        for mv in sampled_moveset:
            if mv not in pkmn_known_moves:
                pkmn_known_moves.append(mv)

    # If a full moveset was acquired from #1, we don't need to sample smogon moves
    if len(pkmn_known_moves) >= 4:
        return pkmn_known_moves

    # 2: Use SmogonSets to sample a moveset
    smogon_moves = [
        m
        for m in SmogonSets.get_raw_pkmn_sets_from_pkmn_name(
            pkmn.name, pkmn.base_name
        ).get(constants.MOVES, [])
        if m[0] not in pkmn_known_moves
    ]
    moves_adjusted_probabilities = adjust_probabilities_for_sampling(
        smogon_moves, 4 - num_known_moves
    )
    index = 0
    while True:
        if len(pkmn_known_moves) >= 4 or not moves_adjusted_probabilities:
            break
        index = index % len(moves_adjusted_probabilities)
        mv, chance = moves_adjusted_probabilities[index]
        if random.random() < chance:
            pkmn_known_moves.append(mv)
            if not smogon_set_makes_sense(
                PredictedPokemonSet(
                    pkmn_set=pkmn_set,
                    pkmn_moveset=PokemonMoveset(moves=pkmn_known_moves),
                )
            ):
                pkmn_known_moves.pop()

            moves_adjusted_probabilities.pop(index)
        else:
            index += 1  # index is only incremented if the move is not added

    return pkmn_known_moves


def set_most_likely_hidden_power(pkmn: Pokemon):
    # hidden power type isn't revealed so if the pokemon used hiddenpower it should
    # be replaced by the most likely hiddenpower that is still possible
    if pkmn.get_move(constants.HIDDEN_POWER) is not None:
        hidden_power_possibilities = [
            f"{constants.HIDDEN_POWER}{p}{constants.HIDDEN_POWER_ACTIVE_MOVE_BASE_DAMAGE_STRING}"
            for p in pkmn.hidden_power_possibilities
        ]
        for mv, _count in SmogonSets.get_raw_pkmn_sets_from_pkmn_name(
            pkmn.name, pkmn.base_name
        )[MOVES_STRING]:
            if mv in hidden_power_possibilities:
                pkmn.remove_move("hiddenpower")
                pkmn.add_move(mv)
                break


def pokemon_guaranteed_move(pkmn: Pokemon):
    if pkmn.name in pokedex and pokedex[pkmn.name].get("requiredMove"):
        required_move = normalize_name(pokedex[pkmn.name]["requiredMove"])
        if len(pkmn.moves) < 4 and pkmn.get_move(required_move) is None:
            logger.info(
                f"Adding guaranteed move {required_move} to {pkmn.name}'s moveset"
            )
            pkmn.add_move(required_move)


def sample_pokemon(pkmn: Pokemon):
    if not pkmn.mega_name:
        _sample_pokemon(pkmn)
        return

    # the ability of a mega pokemon that has not yet mega-evolved
    # needs to be sampled from its non-mega version
    pkmn_without_mega = deepcopy(pkmn)
    pkmn_without_mega.mega_name = None
    _sample_pokemon(pkmn_without_mega)
    pkmn.ability = pkmn_without_mega.ability
    _sample_pokemon(pkmn)


def _sample_pokemon(pkmn: Pokemon):
    pokemon_guaranteed_move(pkmn)
    set_most_likely_hidden_power(pkmn)

    # 1: TeamDatasets is not emptied and `get_all_remaining_sets` returned at least one set
    # Note: TeamDatasets are not sampled according to their counts
    # because the counts are not indicative of the actual distribution of sets
    # Skip this step an amount of the time to get some variety
    # if at least 1 move is known
    remaining_team_sets = TeamDatasets.get_all_remaining_sets(pkmn)
    if remaining_team_sets and (not pkmn.moves or random.random() < 0.75):
        sampled_set = deepcopy(random.choice(remaining_team_sets))
        populate_pkmn_from_set(pkmn, sampled_set, source="teamdatasets-full")
        return

    # 2: TeamDatasets has at least 1 set in it that hasn't been invalidated,
    # but `get_all_remaining_sets` returned no sets because the accompanying movesets are invalid
    remaining_team_sets = [
        s
        for s in TeamDatasets.get_pkmn_sets_from_pkmn_name(pkmn)
        if s.pkmn_set.set_makes_sense(pkmn) and smogon_set_makes_sense(s)
    ]
    if remaining_team_sets:
        sampled_set = deepcopy(random.choice(remaining_team_sets).pkmn_set)
        moves = sample_pokemon_moveset_with_known_pkmn_set(pkmn, sampled_set)
        sampled_set = PredictedPokemonSet(
            pkmn_set=sampled_set,
            pkmn_moveset=PokemonMoveset(moves=moves),
        )
        populate_pkmn_from_set(pkmn, sampled_set, source="teamdatasets-partial")
        return

    # 3: Try to sample from SmogonSets including moves
    # Sample a SmogonSet and then repeat the same process as in 2 to get a moveset
    remaining_smogon_sets = SmogonSets.get_all_remaining_sets(pkmn)
    remaining_smogon_sets = get_filtered_sets(pkmn, remaining_smogon_sets)
    if remaining_smogon_sets:
        sampled_smogon_set = deepcopy(
            random.choices(
                remaining_smogon_sets,
                weights=[s.count for s in remaining_smogon_sets],
            )[0]
        )
        moves = sample_pokemon_moveset_with_known_pkmn_set(pkmn, sampled_smogon_set)
        sampled_set = PredictedPokemonSet(
            pkmn_set=sampled_smogon_set,
            pkmn_moveset=PokemonMoveset(moves=moves),
        )
        populate_pkmn_from_set(pkmn, sampled_set, source="smogonsets")
        return

    logger.warning(f"Could not sample {pkmn.name}")


def predict_team_likelihood(revealed_pokemon, all_pkmn_counts):
    revealed_set = set(revealed_pokemon)
    likelihoods = {}

    for pkmn in all_pkmn_counts.keys():
        if pkmn in revealed_set:
            continue

        joint_probs = []
        for revealed in revealed_set:
            try:
                co_count = all_pkmn_counts[revealed][TEAMMATES][pkmn]
            except KeyError:
                co_count = 0

            prob = co_count / all_pkmn_counts[revealed][RAW_COUNT]
            joint_probs.append(prob)

        likelihoods[pkmn] = sum(joint_probs) / len(joint_probs)

    sorted_likelihoods = dict(
        sorted(likelihoods.items(), key=lambda x: x[1], reverse=True)
    )

    return sorted_likelihoods


def sample_standardbattle_pokemon(existing_pokemon: list[Pokemon]) -> Pokemon:
    existing_pokemon_names = {pkmn.name for pkmn in existing_pokemon}
    selected_pkmn_name = ""
    ok = False
    while not ok:
        ok = True
        sample_weights = predict_team_likelihood(
            existing_pokemon_names,
            SmogonSets.all_pkmn_counts,
        )
        keys = list(sample_weights.keys())[:50]
        values = list(sample_weights.values())[:50]
        selected_pkmn_name = random.choices(keys, weights=values)[0]
        if selected_pkmn_name in existing_pokemon_names:
            ok = False

    pkmn = Pokemon(selected_pkmn_name, 100)
    sample_pokemon(pkmn)
    return pkmn


# take a Battle and fill in the unrevealed pkmn for the opponent
def populate_standardbattle_unrevealed_pkmn(battle: Battle):
    num_revealed_pkmn = 0
    existing_pkmn = []
    for pkmn in battle.opponent.reserve:
        existing_pkmn.append(pkmn)
        num_revealed_pkmn += 1
    if battle.opponent.active is not None:
        existing_pkmn.append(battle.opponent.active)
        num_revealed_pkmn += 1

    if num_revealed_pkmn == 6:
        return

    logger.info("Sampling {} unrevealed pokemon".format(6 - num_revealed_pkmn))
    while num_revealed_pkmn < 6:
        pkmn = sample_standardbattle_pokemon(existing_pkmn)
        existing_pkmn.append(pkmn)
        battle.opponent.reserve.append(pkmn)
        num_revealed_pkmn += 1


def sample_mega_evolution(battler: Battler, index: int):
    if battler.mega_revealed():
        logger.info("Mega evolution already revealed for {}".format(battler.name))
        return
    mega_formes = battler.possible_mega_evolutions()
    if not mega_formes:
        logger.info("No possible mega evolutions for {}".format(battler.name))
        return
    selected_mega = random.choice(list(mega_formes.keys()))
    mega_pkmn_name, mega_item = random.choice(mega_formes[selected_mega])

    if battler.active.name == selected_mega:
        pkmn = battler.active
    else:
        pkmn = battler.find_pokemon_in_reserves(selected_mega)

    logger.info(
        "Sampled mega evolution {}->{} with item {} for battle {}".format(
            selected_mega, mega_pkmn_name, mega_item, index
        )
    )
    pkmn.item = mega_item
    pkmn.mega_name = mega_pkmn_name


def prepare_battles(battle: Battle, num_battles: int) -> list[(Battle, float)]:
    sampled_battles = []
    for index in range(num_battles):
        logger.info("Sampling battle {}".format(index))
        battle_copy = deepcopy(battle)
        if battle_copy.mega_evolve_possible():
            sample_mega_evolution(battle_copy.opponent, index)

        sample_pokemon(battle_copy.opponent.active)
        for pkmn in filter(lambda x: x.is_alive(), battle_copy.opponent.reserve):
            sample_pokemon(pkmn)

        if battle.generation in constants.NO_TEAM_PREVIEW_GENS:
            populate_standardbattle_unrevealed_pkmn(battle_copy)
        battle_copy.opponent.lock_moves()
        sampled_battles.append((battle_copy, 1 / num_battles))

    return sampled_battles
