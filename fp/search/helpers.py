import logging

from fp import constants
from fp.data.sets import PredictedPokemonSet
from fp.battle.state import Pokemon, Battle

logger = logging.getLogger(__name__)


def log_pkmn_set(pkmn: Pokemon, source=None):
    nature_evs = f"{pkmn.nature},{','.join(str(x) for x in pkmn.evs)}"
    if nature_evs in [
        "serious,85,85,85,85,85,85",
        "serious,252,252,252,252,252,252",
        "serious,11,11,11,11,11,11",
    ]:
        s = "\t{} {} {} {}".format(
            pkmn.name.rjust(15),
            str(pkmn.ability).rjust(12),
            str(pkmn.item).rjust(12),
            pkmn.moves,
        )
    else:
        s = "\t{} {} {} {} {}".format(
            pkmn.name.rjust(15),
            nature_evs.rjust(25),
            str(pkmn.ability).rjust(12),
            str(pkmn.item).rjust(12),
            pkmn.moves,
        )
    if pkmn.tera_type is not None and pkmn.tera_type not in ["nothing", "typeless"]:
        s += " ttype={}".format(pkmn.tera_type)
    if source is not None:
        s += " source={}".format(source)

    logger.info(s)


def populate_pkmn_from_set(
    pkmn: Pokemon, set_: PredictedPokemonSet, source: str = None
):
    known_pokemon_moves = pkmn.moves

    pkmn.moves = []
    for mv in set_.pkmn_moveset.moves:
        pkmn.add_move(mv)
    pkmn.ability = pkmn.ability or set_.pkmn_set.ability
    if pkmn.item == constants.UNKNOWN_ITEM:
        pkmn.item = set_.pkmn_set.item
    pkmn.set_spread(
        set_.pkmn_set.nature,
        ",".join(str(x) for x in set_.pkmn_set.evs),
    )
    if (
        set_.pkmn_set.tera_type is not None
        and not pkmn.terastallized
        and not pkmn.tera_type
    ):
        pkmn.tera_type = set_.pkmn_set.tera_type
    log_pkmn_set(pkmn, source)

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


def opponent_previously_attacked(battle: Battle):
    observed_matchups = battle.observed_matchups.get(battle)
    return len(observed_matchups) >= 2


def should_assume_choicescarf(battle):
    user_active = battle.user.active
    opponent_active = battle.opponent.active
    choice_scarf_usage_rate = battle.mode.smogon_sets.item_usage_rate(
        opponent_active, constants.CHOICE_SCARF
    )

    # situations where we _dont_ want to assume a choice scarf
    if (
        # if this matchup has occurred enough times
        # arguably this one is a bad one to check for choicescarf and should be removed
        opponent_previously_attacked(battle)
        # if we are naturally slower
        or user_active.base_stats["speed"] < opponent_active.base_stats["speed"]
        # if another choice scarf has 100% been revealed
        or any(pkmn.item == constants.CHOICE_SCARF for pkmn in battle.opponent.reserve)
        # if the "they can't possibly have a choice item" flag has been set
        or not opponent_active.can_have_choice_item
        # if their item has been revealed
        or opponent_active.item != constants.UNKNOWN_ITEM
        # less than 5% usage means this is too rare to consider
        or choice_scarf_usage_rate < 0.05
    ):
        return False

    return True


def maybe_sample_opponent_active_choicescarf(battle: Battle):
    if (
        battle.team_preview
        or battle.opponent.active is None
        or battle.user.active is None
    ):
        return

    if not should_assume_choicescarf(battle):
        return

    opponent_active = battle.opponent.active
    logger.info(f"Forcing opponent's {opponent_active.name} to have a choice scarf")
    opponent_active.item = constants.CHOICE_SCARF

    a = 5
