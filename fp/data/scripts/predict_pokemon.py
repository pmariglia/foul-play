import logging
from copy import deepcopy

from fp.battle.state import Pokemon
from fp.config import FoulPlayConfig, init_logging
from fp.modes import StandardBattleMode
from fp.search.standard_battles import sample_pokemon

init_logging(logging.DEBUG, False)

pkmn_name = "tyranitar"

FoulPlayConfig.pokemon_format = "gen9championsou"

btl_mode = StandardBattleMode()
btl_mode.smogon_sets.initialize(FoulPlayConfig.format_spec, {pkmn_name})

pkmn = Pokemon(pkmn_name, 50)

NUM_SAMPLES = 100
for _ in range(NUM_SAMPLES):
    sample_pokemon(deepcopy(pkmn), btl_mode)
