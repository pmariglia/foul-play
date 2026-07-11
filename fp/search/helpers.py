import logging
import random

from fp import constants
from fp.data.sets import PredictedPokemonSet
from fp.battle.state import Pokemon, Battler

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


def sample_mega_evolution(battler: Battler, index: int, smogon_sets):
    def mega_lower_usage_than_non_mega(pkmn_name: str, pkmn_mega_name: str) -> bool:
        non_mega_raw_count = smogon_sets.get_raw_count(pkmn_name)
        mega_raw_count = smogon_sets.get_raw_count(pkmn_mega_name)
        if non_mega_raw_count is not None and mega_raw_count is not None:
            return mega_raw_count < non_mega_raw_count
        return False

    if battler.mega_revealed():
        logger.info("Mega evolution already revealed for {}".format(battler.name))
        return

    mega_formes = (
        battler.possible_mega_evolutions(must_be_revealed=True)
        or battler.possible_mega_evolutions()
    )

    mega_formes_to_select_from = []
    for pkmn, possible_mega_evos in mega_formes.items():
        for mega_info in possible_mega_evos:
            if not mega_lower_usage_than_non_mega(pkmn, mega_info[0]):
                mega_formes_to_select_from.append((pkmn, mega_info))

    if not mega_formes_to_select_from:
        logger.info("No possible mega evolutions for {}".format(battler.name))
        return

    selected_mega, (mega_pkmn_name, mega_item) = random.choice(
        list(mega_formes_to_select_from)
    )

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
    pkmn.revealed = True
