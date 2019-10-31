import constants
from data import pokedex


def suckerpunch(attacking_move, defending_move, attacking_pokemon, defending_pokemon, first_move, weather):
    if not first_move or defending_move.get(constants.CATEGORY) not in constants.DAMAGING_CATEGORIES:
        attacking_move = attacking_move.copy()
        attacking_move[constants.ACCURACY] = 0

    return attacking_move


def eruption(attacking_move, defending_move, attacking_pokemon, defending_pokemon, first_move, weather):
    attacking_move = attacking_move.copy()
    attacker_hp_percent = attacking_pokemon.hp / attacking_pokemon.maxhp
    attacking_move[constants.BASE_POWER] *= attacker_hp_percent
    return attacking_move


def tailslap(attacking_move, defending_move, attacking_pokemon, defending_pokemon, first_move, weather):
    # skill-link will boost damage by 5x, so no need to do it again here if that is the pokemon's ability
    if attacking_pokemon.ability != 'skilllink':
        attacking_move = attacking_move.copy()
        attacking_move[constants.BASE_POWER] *= 3.2
    return attacking_move


def freezedry(attacking_move, defending_move, attacking_pokemon, defending_pokemon, first_move, weather):
    if 'water' in defending_pokemon.types:
        attacking_move = attacking_move.copy()
        attacking_move[constants.BASE_POWER] *= 4
    return attacking_move


def hex(attacking_move, defending_move, attacking_pokemon, defending_pokemon, first_move, weather):
    if defending_pokemon.status is not None:
        attacking_move = attacking_move.copy()
        attacking_move[constants.BASE_POWER] *= 2
    return attacking_move


def foulplay(attacking_move, defending_move, attacking_pokemon, defending_pokemon, first_move, weather):
    attacking_move = attacking_move.copy()
    attacking_move[constants.BASE_POWER] *= defending_pokemon.calculate_boosted_stats()[constants.ATTACK] / \
                                            attacking_pokemon.calculate_boosted_stats()[constants.ATTACK]
    return attacking_move


def storedpower(attacking_move, defending_move, attacking_pokemon, defending_pokemon, first_move, weather):
    multiplier = attacking_pokemon.attack_boost + attacking_pokemon.defense_boost + \
                 attacking_pokemon.special_attack_boost + attacking_pokemon.special_defense_boost + \
                 attacking_pokemon.speed_boost
    if multiplier > 0:
        attacking_move = attacking_move.copy()
        attacking_move[constants.BASE_POWER] *= multiplier
    return attacking_move


def psyshock(attacking_move, defending_move, attacking_pokemon, defending_pokemon, first_move, weather):
    defending_stats = defending_pokemon.calculate_boosted_stats()
    attacking_move = attacking_move.copy()
    attacking_move[constants.BASE_POWER] *= (defending_stats[constants.SPECIAL_DEFENSE] / defending_stats[constants.DEFENSE])
    return attacking_move


def facade(attacking_move, defending_move, attacking_pokemon, defending_pokemon, first_move, weather):
    if attacking_pokemon.status is not None:
        attacking_move = attacking_move.copy()
        attacking_move[constants.BASE_POWER] *= 2
    return attacking_move


def avalanche(attacking_move, defending_move, attacking_pokemon, defending_pokemon, first_move, weather):
    if first_move is False and defending_move.get(constants.CATEGORY) in constants.DAMAGING_CATEGORIES:
        attacking_move = attacking_move.copy()
        attacking_move[constants.BASE_POWER] *= 2
    return attacking_move


def gyroball(attacking_move, defending_move, attacking_pokemon, defending_pokemon, first_move, weather):
    # power = 25 × TargetSpeed ÷ UserSpeed
    attacking_move = attacking_move.copy()
    attacker_speed = attacking_pokemon.calculate_boosted_stats()[constants.SPEED]
    defender_speed = defending_pokemon.calculate_boosted_stats()[constants.SPEED]
    attacking_move[constants.BASE_POWER] = min(150, 25 * defender_speed / attacker_speed)
    return attacking_move


def focuspunch(attacking_move, defending_move, attacking_pokemon, defending_pokemon, first_move, weather):
    # technically wrong - a move missing would allow focuspunch to hit, however that information is not present here
    if first_move or defending_move.get(constants.CATEGORY) in constants.DAMAGING_CATEGORIES:
        attacking_move = attacking_move.copy()
        attacking_move[constants.BASE_POWER] = 0
    return attacking_move


def acrobatics(attacking_move, defending_move, attacking_pokemon, defending_pokemon, first_move, weather):
    # acrobatics is 110 by default. If the pokemon has an item, it will go to 55
    # technically this should be the other way around, but the evaluation logic should
    # assume that the opponent's pokemon has a 110 BP move (worst case unless known)
    if attacking_pokemon.item not in [None, constants.UNKNOWN_ITEM]:
        attacking_move = attacking_move.copy()
        attacking_move[constants.BASE_POWER] *= 0.5
    return attacking_move


def technoblast(attacking_move, defending_move, attacking_pokemon, defending_pokemon, first_move, weather):
    if attacking_pokemon.item == 'burndrive':
        attacking_move = attacking_move.copy()
        attacking_move[constants.TYPE] = 'fire'

    elif attacking_pokemon.item == 'chilldrive':
        attacking_move = attacking_move.copy()
        attacking_move[constants.TYPE] = 'ice'

    elif attacking_pokemon.item == 'dousedrive':
        attacking_move = attacking_move.copy()
        attacking_move[constants.TYPE] = 'water'

    elif attacking_pokemon.item == 'shockdrive':
        attacking_move = attacking_move.copy()
        attacking_move[constants.TYPE] = 'electric'

    return attacking_move


def multiattack(attacking_move, defending_move, attacking_pokemon, defending_pokemon, first_move, weather):
    if attacking_pokemon.item.endswith('memory'):
        attacking_move = attacking_move.copy()
        attacking_move[constants.TYPE] = attacking_pokemon.item.replace('memory', '')

    return attacking_move


def knockoff(attacking_move, defending_move, attacking_pokemon, defending_pokemon, first_move, weather):
    # .endswith("mega|primal") is a hack but w/e sue me
    if defending_pokemon.item is not None and not defending_pokemon.id.endswith("mega") and not defending_pokemon.id.endswith("primal"):
        attacking_move = attacking_move.copy()
        attacking_move[constants.BASE_POWER] *= 1.5
    return attacking_move


def hurricane(attacking_move, defending_move, attacking_pokemon, defending_pokemon, first_move, weather):
    if weather == constants.SUN:
        attacking_move = attacking_move.copy()
        attacking_move[constants.ACCURACY] = 50
    elif weather == constants.RAIN:
        attacking_move = attacking_move.copy()
        attacking_move[constants.ACCURACY] = True
    return attacking_move


def blizzard(attacking_move, defending_move, attacking_pokemon, defending_pokemon, first_move, weather):
    if weather == constants.HAIL:
        attacking_move = attacking_move.copy()
        attacking_move[constants.ACCURACY] = True
    return attacking_move


def solarbeam(attacking_move, defending_move, attacking_pokemon, defending_pokemon, first_move, weather):
    if weather == constants.SUN:
        attacking_move = attacking_move.copy()
        attacking_move[constants.FLAGS] = attacking_move[constants.FLAGS].copy()
        attacking_move[constants.FLAGS].pop(constants.CHARGE)
    return attacking_move


def toxic(attacking_move, defending_move, attacking_pokemon, defending_pokemon, first_move, weather):
    if 'poison' in attacking_pokemon.types:
        attacking_move = attacking_move.copy()
        attacking_move[constants.ACCURACY] = True
    return attacking_move


def strengthsap(attacking_move, defending_move, attacking_pokemon, defending_pokemon, first_move, weather):
    attacking_move = attacking_move.copy()
    attacking_move[constants.BOOSTS] = {
        constants.ATTACK: -1
    }
    attacking_move[constants.HEAL] = [
        defending_pokemon.calculate_boosted_stats()[constants.ATTACK],
        attacking_pokemon.maxhp
    ]
    attacking_move[constants.HEAL_TARGET] = constants.SELF

    return attacking_move


def revelationdance(attacking_move, defending_move, attacking_pokemon, defending_pokemon, first_move, weather):
    attacking_move = attacking_move.copy()
    attacking_move[constants.TYPE] = attacking_pokemon.types[0]

    return attacking_move


def lowkick(attacking_move, defending_move, attacking_pokemon, defending_pokemon, first_move, weather):
    attacking_move = attacking_move.copy()
    defending_pokemon_weight = pokedex[defending_pokemon.id][constants.WEIGHT]

    if defending_pokemon_weight < 10:
        attacking_move[constants.BASE_POWER] = 20
    elif defending_pokemon_weight < 25:
        attacking_move[constants.BASE_POWER] = 40
    elif defending_pokemon_weight < 60:
        attacking_move[constants.BASE_POWER] = 60
    elif defending_pokemon_weight < 100:
        attacking_move[constants.BASE_POWER] = 80
    elif defending_pokemon_weight < 200:
        attacking_move[constants.BASE_POWER] = 100
    else:
        attacking_move[constants.BASE_POWER] = 120

    return attacking_move


def painsplit(attacking_move, defending_move, attacking_pokemon, defending_pokemon, first_move, weather):
    # damage done to the opponent is handled in the damage calculation module
    attacking_move = attacking_move.copy()
    total_hp = attacking_pokemon.hp + defending_pokemon.hp
    damage_done = attacking_pokemon.hp - total_hp / 2
    damage_fraction = -1*damage_done / attacking_pokemon.maxhp

    attacking_move[constants.HEAL] = damage_fraction.as_integer_ratio()
    attacking_move[constants.HEAL_TARGET] = constants.SELF

    # this needs to be set so that the damage calculation is performed
    attacking_move[constants.CATEGORY] = constants.PHYSICAL

    return attacking_move


move_lookup = {
    'painsplit': painsplit,
    'lowkick': lowkick,
    'revelationdance': revelationdance,
    'strengthsap': strengthsap,
    'toxic': toxic,
    'multiattack': multiattack,
    'solarbeam': solarbeam,
    'hurricane': hurricane,
    'thunder': hurricane,
    'blizzard': blizzard,
    'suckerpunch': suckerpunch,
    'eruption': eruption,
    'waterspout': eruption,
    'hex': hex,
    'freezedry': freezedry,
    'tailslap': tailslap,
    'bulletseed': tailslap,
    'rockblast': tailslap,
    'bonerush': tailslap,
    'iciclespear': tailslap,
    'pinmissile': tailslap,
    'watershuriken': tailslap,
    'foulplay': foulplay,
    'storedpower': storedpower,
    'psyshock': psyshock,
    'psystrike': psyshock,
    'secretsword': psyshock,
    'avalanche': avalanche,
    'facade': facade,
    'gyroball': gyroball,
    'focuspunch': focuspunch,
    'acrobatics': acrobatics,
    'technoblast': technoblast,
    'knockoff': knockoff
}


def modify_attack_being_used(attacking_move, defending_move, attacking_pokemon, defending_pokemon, first_move, weather):
    move_func = move_lookup.get(attacking_move[constants.ID])
    if move_func is not None:
        return move_func(attacking_move, defending_move, attacking_pokemon, defending_pokemon, first_move, weather)
    else:
        return attacking_move
