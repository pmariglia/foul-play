import logging
from copy import deepcopy

import constants
from data.pkmn_sets import RandomBattleTeamDatasets, TeamDatasets, SmogonSets
from fp.battle import Pokemon, Battle

logger = logging.getLogger(__name__)


def log_predicted_set(pkmn, source=None):
    s = "Predicted set: {} {} {} {} {} {}".format(
        pkmn.name.rjust(15),
        pkmn.nature.ljust(7),
        str(pkmn.evs).ljust(25),
        str(pkmn.ability).ljust(12),
        str(pkmn.item).ljust(12),
        pkmn.moves,
    )
    if pkmn.tera_type is not None:
        s += " ttype={}".format(pkmn.tera_type)
    if source:
        s += ", source={}".format(source)

    logger.info(s)


def prepare_battle(battle: Battle, fn: callable):
    battle = deepcopy(battle)

    fn(battle.opponent.active)
    for pkmn in filter(lambda x: x.is_alive(), battle.opponent.reserve):
        fn(pkmn)

    battle.opponent.lock_moves()
    return battle


def fill_in_randombattle_unknowns(pkmn: Pokemon):
    predicted_set = RandomBattleTeamDatasets.predict_set(pkmn, match_traits=True)
    if predicted_set is None:
        predicted_set = RandomBattleTeamDatasets.predict_set(pkmn, match_traits=False)

    known_pokemon_moves = pkmn.moves
    if predicted_set is not None:
        pkmn.moves = []
        for mv in predicted_set.pkmn_moveset.moves:
            pkmn.add_move(mv)
        pkmn.ability = pkmn.ability or predicted_set.pkmn_set.ability
        if pkmn.item == constants.UNKNOWN_ITEM:
            pkmn.item = predicted_set.pkmn_set.item
        pkmn.set_spread(
            predicted_set.pkmn_set.nature,
            ",".join(str(x) for x in predicted_set.pkmn_set.evs),
        )
        if predicted_set.pkmn_set.tera_type is not None:
            pkmn.tera_type = predicted_set.pkmn_set.tera_type
        log_predicted_set(pkmn)
    else:
        logger.info("Could not predict set for {}".format(pkmn.name))

    # newly created moves have max PP
    # copy over the current pp from the known moves
    for known_move in known_pokemon_moves:
        for mv in pkmn.moves:
            if known_move.name.startswith("hiddenpower") and mv.name.startswith(
                "hiddenpower"
            ):
                mv.current_pp = known_move.current_pp
                break
            elif mv.name == known_move.name:
                mv.current_pp = known_move.current_pp
                break


def fill_in_battle_factory_unknowns(pkmn: Pokemon):
    predicted_team_set = TeamDatasets.predict_set(pkmn)
    predicted_team_set_no_ability_item_match = TeamDatasets.predict_set(
        pkmn, match_traits=False
    )

    if predicted_team_set:
        predicted_set = predicted_team_set
        source = "team_datasets"
    elif predicted_team_set_no_ability_item_match:
        predicted_set = predicted_team_set_no_ability_item_match
        source = "team_datasets_no_trait_match"
    else:
        predicted_set = None

    if predicted_set is not None:
        pkmn.moves = []
        for mv in predicted_set.pkmn_moveset.moves:
            pkmn.add_move(mv)
        pkmn.ability = pkmn.ability or predicted_set.pkmn_set.ability
        if pkmn.item == constants.UNKNOWN_ITEM:
            pkmn.item = predicted_set.pkmn_set.item
        pkmn.set_spread(predicted_set.pkmn_set.nature, predicted_set.pkmn_set.evs)
        if predicted_set.pkmn_set.tera_type is not None:
            pkmn.tera_type = predicted_set.pkmn_set.tera_type
        log_predicted_set(pkmn, source)
    else:
        logger.info("Could not predict set for {}".format(pkmn.name))


def fill_in_standardbattle_unknowns(pkmn: Pokemon):
    predicted_team_set = TeamDatasets.predict_set(pkmn)
    predicted_team_set_no_ability_item_match = TeamDatasets.predict_set(
        pkmn, match_traits=False
    )
    predicted_smogon_sets = SmogonSets.predict_set(pkmn)
    predicted_smogon_sets_no_trait_match = SmogonSets.predict_set(
        pkmn, match_traits=False
    )

    if predicted_team_set:
        predicted_set = predicted_team_set
        source = "team_datasets"
    elif predicted_team_set_no_ability_item_match:
        predicted_set = predicted_team_set_no_ability_item_match
        source = "team_datasets_no_trait_match"
    elif predicted_smogon_sets:
        predicted_set = predicted_smogon_sets
        source = "smogon_stats"
    elif predicted_smogon_sets_no_trait_match:
        predicted_set = predicted_smogon_sets_no_trait_match
        source = "smogon_stats_no_trait_match"
    else:
        predicted_set = RandomBattleTeamDatasets.predict_set(pkmn, match_traits=False)
        source = "randombattle_datasets"

    if predicted_set is not None:
        pkmn.moves = []
        for mv in predicted_set.pkmn_moveset.moves:
            pkmn.add_move(mv)
        pkmn.ability = pkmn.ability or predicted_set.pkmn_set.ability
        if pkmn.item == constants.UNKNOWN_ITEM:
            pkmn.item = predicted_set.pkmn_set.item
        pkmn.set_spread(predicted_set.pkmn_set.nature, predicted_set.pkmn_set.evs)
        if predicted_set.pkmn_set.tera_type is not None:
            pkmn.tera_type = predicted_set.pkmn_set.tera_type
        log_predicted_set(pkmn, source)
    else:
        logger.info("Could not predict set for {}".format(pkmn.name))


def format_decision(battle, decision):
    # Formats a decision for communication with Pokemon-Showdown
    # If the pokemon can mega-evolve, it will
    # If the move can be used as a Z-Move, it will be

    if decision.startswith(constants.SWITCH_STRING + " "):
        switch_pokemon = decision.split("switch ")[-1]
        for pkmn in battle.user.reserve:
            if pkmn.name == switch_pokemon:
                message = "/switch {}".format(pkmn.index)
                break
        else:
            raise ValueError("Tried to switch to: {}".format(switch_pokemon))
    else:
        tera = False
        mega = False
        if decision.endswith("-tera"):
            decision = decision.replace("-tera", "")
            tera = True
        elif decision.endswith("-mega"):
            decision = decision.replace("-mega", "")
            mega = True
        message = "/choose move {}".format(decision)

        if battle.user.active.can_mega_evo and mega:
            message = "{} {}".format(message, constants.MEGA)
        elif battle.user.active.can_ultra_burst:
            message = "{} {}".format(message, constants.ULTRA_BURST)

        # only dynamax on last pokemon
        if battle.user.active.can_dynamax and all(
            p.hp == 0 for p in battle.user.reserve
        ):
            message = "{} {}".format(message, constants.DYNAMAX)

        if tera:
            message = "{} {}".format(message, constants.TERASTALLIZE)

        if battle.user.active.get_move(decision).can_z:
            message = "{} {}".format(message, constants.ZMOVE)

    return [message, str(battle.rqid)]
