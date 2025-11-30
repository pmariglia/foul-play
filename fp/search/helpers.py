import logging

import constants
from data.pkmn_sets import PredictedPokemonSet
from fp.battle import Pokemon

logger = logging.getLogger(__name__)


def log_pkmn_set(pkmn: Pokemon, source=None):
    nature_evs = f"{pkmn.nature},{','.join(str(x) for x in pkmn.evs)}"
    if nature_evs in ["serious,85,85,85,85,85,85", "serious,252,252,252,252,252,252"]:
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
