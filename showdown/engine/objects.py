from collections import defaultdict
from copy import copy

from data import all_move_json
import constants
from showdown.helpers import boost_multiplier_lookup


class State(object):
    __slots__ = ('self', 'opponent', 'weather', 'force_switch', 'field', 'trick_room', 'wait')

    def __init__(self, user, opponent, weather, field, trick_room, force_switch, wait):
        self.self = user
        self.opponent = opponent
        self.weather = weather
        self.field = field
        self.trick_room = trick_room
        self.force_switch = force_switch
        self.wait = wait

    def get_self_options(self, force_switch):
        if force_switch:
            possible_moves = []
        else:
            possible_moves = [m[constants.ID] for m in self.self.active.moves if not m[constants.DISABLED]]

        if self.self.trapped:
            possible_switches = []
        else:
            possible_switches = self.self.get_switches()

        return possible_moves + possible_switches

    def get_opponent_options(self):
        if self.opponent.active.hp <= 0:
            possible_moves = []
        else:
            possible_moves = [m[constants.ID] for m in self.opponent.active.moves if not m[constants.DISABLED]]

        possible_switches = self.opponent.get_switches()

        return possible_moves + possible_switches

    def get_all_options(self):
        force_switch = self.self.active.hp <= 0
        wait = self.opponent.active.hp <= 0

        # double faint or team preview
        if force_switch and wait:
            user_options = self.get_self_options(force_switch) or [constants.DO_NOTHING_MOVE]
            opponent_options = self.get_opponent_options() or [constants.DO_NOTHING_MOVE]
            return user_options, opponent_options

        if force_switch:
            opponent_options = [constants.DO_NOTHING_MOVE]
        else:
            opponent_options = self.get_opponent_options()

        if wait:
            user_options = [constants.DO_NOTHING_MOVE]
        else:
            user_options = self.get_self_options(force_switch)

        if not user_options:
            user_options = [constants.DO_NOTHING_MOVE]

        if not opponent_options:
            opponent_options = [constants.DO_NOTHING_MOVE]

        return user_options, opponent_options

    @classmethod
    def from_dict(cls, state_dict):
        return State(
            Side.from_dict(state_dict[constants.SELF]),
            Side.from_dict(state_dict[constants.OPPONENT]),
            state_dict[constants.WEATHER],
            state_dict[constants.FIELD],
            state_dict[constants.TRICK_ROOM],
            state_dict[constants.FORCE_SWITCH],
            state_dict[constants.WAIT],
        )

    def __repr__(self):
        return str(
            {
                constants.SELF: self.self,
                constants.OPPONENT: self.opponent,
                constants.WEATHER: self.weather,
                constants.FIELD: self.field,
                constants.TRICK_ROOM: self.trick_room,
                constants.FORCE_SWITCH: self.force_switch,
                constants.WAIT: self.wait
            }
        )

    def __key(self):
        return (
            hash(self.self),
            hash(self.opponent),
            self.weather,
            self.field,
            self.trick_room,
            self.force_switch,
            self.wait
        )

    def __hash__(self):
        return hash(self.__key())

    def __eq__(self, other):
        return self.__key() == other.__key()


class Side(object):
    __slots__ = ('active', 'reserve', 'side_conditions', 'trapped')

    def __init__(self, active, reserve, side_conditions, trapped):
        self.active = active
        self.reserve = reserve
        self.side_conditions = side_conditions
        self.trapped = trapped

    def get_switches(self):
        switches = []
        for pkmn_name, pkmn in self.reserve.items():
            if pkmn.hp > 0:
                switches.append("{} {}".format(constants.SWITCH_STRING, pkmn_name))
        return switches

    @classmethod
    def from_dict(cls, side_dict):
        return Side(
            Pokemon.from_dict(side_dict[constants.ACTIVE]),
            {p[constants.ID]: Pokemon.from_dict(p) for p in side_dict[constants.RESERVE].values()},
            defaultdict(int, side_dict[constants.SIDE_CONDITIONS]),
            side_dict[constants.TRAPPED]
        )

    def __repr__(self):
        return str({
                constants.ACTIVE: self.active,
                constants.RESERVE: self.reserve,
                constants.SIDE_CONDITIONS: dict(self.side_conditions),
                constants.TRAPPED: self.trapped
            })

    def __key(self):
        return (
            hash(self.active),
            sum(hash(p.reserve_hash()) for p in self.reserve.values()),
            hash(frozenset(self.side_conditions.items())),
            self.trapped
        )

    def __eq__(self, other):
        return self.__key() == other.__key()

    def __hash__(self):
        return hash(self.__key())


class Pokemon(object):
    __slots__ = (
        'id',
        'level',
        'hp',
        'maxhp',
        'ability',
        'item',
        'base_stats',
        'attack',
        'defense',
        'special_attack',
        'special_defense',
        'speed',
        'attack_boost',
        'defense_boost',
        'special_attack_boost',
        'special_defense_boost',
        'speed_boost',
        'accuracy_boost',
        'evasion_boost',
        'status',
        'volatile_status',
        'moves',
        'types',
        'can_mega_evo',
        'burn_multiplier',
        'scoring_multiplier'
    )

    def __init__(self,
                 identifier,
                 level,
                 hp,
                 maxhp,
                 ability,
                 item,
                 base_stats,
                 attack,
                 defense,
                 special_attack,
                 special_defense,
                 speed,
                 attack_boost,
                 defense_boost,
                 special_attack_boost,
                 special_defense_boost,
                 speed_boost,
                 accuracy_boost,
                 evasion_boost,
                 status,
                 volatile_status,
                 moves,
                 types,
                 can_mega_evo,
                 scoring_multiplier=1):
        self.id = identifier
        self.level = level
        self.hp = hp
        self.maxhp = maxhp
        self.ability = ability
        self.item = item
        self.base_stats = base_stats
        self.attack = attack
        self.defense = defense
        self.special_attack = special_attack
        self.special_defense = special_defense
        self.speed = speed
        self.attack_boost = attack_boost
        self.defense_boost = defense_boost
        self.special_attack_boost = special_attack_boost
        self.special_defense_boost = special_defense_boost
        self.speed_boost = speed_boost
        self.accuracy_boost = accuracy_boost
        self.evasion_boost = evasion_boost
        self.status = status
        self.volatile_status = volatile_status
        self.moves = moves
        self.types = types
        self.can_mega_evo = can_mega_evo
        self.scoring_multiplier = scoring_multiplier

        # evaluation relies on a multiplier for the burn status
        # it is calculated here to save time during evaluation
        self.burn_multiplier = self.calculate_burn_multiplier()

    def calculate_burn_multiplier(self):
        # +1 to the multiplier for each physical move
        burn_multiplier = len([m for m in self.moves if all_move_json[m[constants.ID]][constants.CATEGORY] == constants.PHYSICAL])

        # evaluation could use more than 4 moves for opponent's pokemon - dont go over 4
        burn_multiplier = min(4, burn_multiplier)

        # dont make this as punishing for special attackers
        if self.special_attack > self.attack:
            burn_multiplier = int(burn_multiplier / 2)

        return burn_multiplier

    @classmethod
    def from_state_pokemon_dict(cls, d):
        return Pokemon(
            d[constants.ID],
            d[constants.LEVEL],
            d[constants.HITPOINTS],
            d[constants.MAXHP],
            d[constants.ABILITY],
            d[constants.ITEM],
            d[constants.BASESTATS],
            d[constants.STATS][constants.ATTACK],
            d[constants.STATS][constants.DEFENSE],
            d[constants.STATS][constants.SPECIAL_ATTACK],
            d[constants.STATS][constants.SPECIAL_DEFENSE],
            d[constants.STATS][constants.SPEED],
            d[constants.BOOSTS][constants.ATTACK],
            d[constants.BOOSTS][constants.DEFENSE],
            d[constants.BOOSTS][constants.SPECIAL_ATTACK],
            d[constants.BOOSTS][constants.SPECIAL_DEFENSE],
            d[constants.BOOSTS][constants.SPEED],
            d[constants.BOOSTS][constants.ACCURACY],
            d[constants.BOOSTS][constants.EVASION],
            d[constants.STATUS],
            d[constants.VOLATILE_STATUS],
            d[constants.MOVES],
            d[constants.TYPES],
            d[constants.CAN_MEGA_EVO],
            d.get(constants.SCORING_MULTIPLIER, 1)
        )

    @classmethod
    def from_dict(cls, d):
        return Pokemon(
            d[constants.ID],
            d[constants.LEVEL],
            d[constants.HITPOINTS],
            d[constants.MAXHP],
            d[constants.ABILITY],
            d[constants.ITEM],
            d[constants.BASESTATS],
            d[constants.ATTACK],
            d[constants.DEFENSE],
            d[constants.SPECIAL_ATTACK],
            d[constants.SPECIAL_DEFENSE],
            d[constants.SPEED],
            d[constants.ATTACK_BOOST],
            d[constants.DEFENSE_BOOST],
            d[constants.SPECIAL_ATTACK_BOOST],
            d[constants.SPECIAL_DEFENSE_BOOST],
            d[constants.SPEED_BOOST],
            d.get(constants.ACCURACY_BOOST, 0),
            d.get(constants.EVASION_BOOST, 0),
            d[constants.STATUS],
            set(d[constants.VOLATILE_STATUS]),
            d[constants.MOVES],
            d[constants.TYPES],
            d[constants.CAN_MEGA_EVO],
            d.get(constants.SCORING_MULTIPLIER, 1)
        )

    def calculate_boosted_stats(self):
        return {
            constants.ATTACK: boost_multiplier_lookup[self.attack_boost] * self.attack,
            constants.DEFENSE: boost_multiplier_lookup[self.defense_boost] * self.defense,
            constants.SPECIAL_ATTACK: boost_multiplier_lookup[self.special_attack_boost] * self.special_attack,
            constants.SPECIAL_DEFENSE: boost_multiplier_lookup[self.special_defense_boost] * self.special_defense,
            constants.SPEED: boost_multiplier_lookup[self.speed_boost] * self.speed,
        }

    def is_grounded(self):
        if 'flying' in self.types or self.ability == 'levitate' or self.item == 'airballoon':
            return False
        return True

    def __repr__(self):
        return str({
                constants.ID: self.id,
                constants.LEVEL: self.level,
                constants.HITPOINTS: self.hp,
                constants.MAXHP: self.maxhp,
                constants.ABILITY: self.ability,
                constants.ITEM: self.item,
                constants.BASESTATS: self.base_stats,
                constants.ATTACK: self.attack,
                constants.DEFENSE: self.defense,
                constants.SPECIAL_ATTACK: self.special_attack,
                constants.SPECIAL_DEFENSE: self.special_defense,
                constants.SPEED: self.speed,
                constants.ATTACK_BOOST: self.attack_boost,
                constants.DEFENSE_BOOST: self.defense_boost,
                constants.SPECIAL_ATTACK_BOOST: self.special_attack_boost,
                constants.SPECIAL_DEFENSE_BOOST: self.special_defense_boost,
                constants.SPEED_BOOST: self.speed_boost,
                constants.ACCURACY_BOOST: self.accuracy_boost,
                constants.EVASION_BOOST: self.evasion_boost,
                constants.STATUS: self.status,
                constants.VOLATILE_STATUS: list(self.volatile_status),
                constants.MOVES: self.moves,
                constants.TYPES: self.types,
                constants.CAN_MEGA_EVO: self.can_mega_evo,
                constants.SCORING_MULTIPLIER: self.scoring_multiplier
            })

    def active_hash(self):
        """Unique identifier for a pokemon"""
        return (
            self.id,  # id is used instead of types
            self.hp,
            self.maxhp,
            self.ability,
            self.item,
            self.status,
            frozenset(self.volatile_status),
            self.attack,
            self.defense,
            self.special_attack,
            self.special_defense,
            self.speed,
            self.attack_boost,
            self.defense_boost,
            self.special_attack_boost,
            self.special_defense_boost,
            self.speed_boost,
        )

    def reserve_hash(self):
        """Unique identifier for a pokemon in the reserves
           This exists because it is a lighter calculation than active_hash"""
        return (
            self.hp,
            self.maxhp,
            self.ability,
            self.item,
            self.status,
            self.attack,
            self.defense,
            self.special_attack,
            self.special_defense,
            self.speed,
        )

    def __eq__(self, other):
        return self.active_hash() == other.active_hash()

    def __hash__(self):
        return hash(self.active_hash())


class TransposeInstruction:
    __slots__ = ('percentage', 'instructions', 'frozen')

    def __init__(self, percentage, instructions, frozen):
        self.percentage = percentage
        self.instructions = instructions
        self.frozen = frozen

    def update_percentage(self, modifier):
        self.percentage *= modifier

    def add_instruction(self, instruction):
        self.instructions.append(instruction)

    def has_same_instructions_as(self, other):
        return self.instructions == other.instructions

    def __copy__(self):
        return TransposeInstruction(self.percentage, copy(self.instructions), self.frozen)

    def __repr__(self):
        return "{}: {}".format(self.percentage, str(self.instructions))

    def __eq__(self, other):
        return self.percentage == other.percentage and \
            self.instructions == other.instructions and \
            self.frozen == other.frozen


class StateMutator:

    def __init__(self, state):
        self.state = state
        self.apply_instructions = {
            constants.MUTATOR_SWITCH: self.switch,
            constants.MUTATOR_APPLY_VOLATILE_STATUS: self.apply_volatile_status,
            constants.MUTATOR_REMOVE_VOLATILE_STATUS: self.remove_volatile_status,
            constants.MUTATOR_DAMAGE: self.damage,
            constants.MUTATOR_HEAL: self.heal,
            constants.MUTATOR_BOOST: self.boost,
            constants.MUTATOR_UNBOOST: self.unboost,
            constants.MUTATOR_APPLY_STATUS: self.apply_status,
            constants.MUTATOR_REMOVE_STATUS: self.remove_status,
            constants.MUTATOR_SIDE_START: self.side_start,
            constants.MUTATOR_SIDE_END: self.side_end,
            constants.MUTATOR_DISABLE_MOVE: self.disable_move,
            constants.MUTATOR_ENABLE_MOVE: self.enable_move,
            constants.MUTATOR_WEATHER_START: self.start_weather,
            constants.MUTATOR_FIELD_START: self.start_field,
            constants.MUTATOR_FIELD_END: self.end_field,
            constants.MUTATOR_TOGGLE_TRICKROOM: self.toggle_trickroom
        }
        self.reverse_instructions = {
            constants.MUTATOR_SWITCH: self.reverse_switch,
            constants.MUTATOR_APPLY_VOLATILE_STATUS: self.remove_volatile_status,
            constants.MUTATOR_REMOVE_VOLATILE_STATUS: self.apply_volatile_status,
            constants.MUTATOR_DAMAGE: self.heal,
            constants.MUTATOR_HEAL: self.damage,
            constants.MUTATOR_BOOST: self.unboost,
            constants.MUTATOR_UNBOOST: self.boost,
            constants.MUTATOR_APPLY_STATUS: self.remove_status,
            constants.MUTATOR_REMOVE_STATUS: self.apply_status,
            constants.MUTATOR_SIDE_START: self.reverse_side_start,
            constants.MUTATOR_SIDE_END: self.reverse_side_end,
            constants.MUTATOR_DISABLE_MOVE: self.enable_move,
            constants.MUTATOR_ENABLE_MOVE: self.disable_move,
            constants.MUTATOR_WEATHER_START: self.reverse_start_weather,
            constants.MUTATOR_FIELD_START: self.reverse_start_field,
            constants.MUTATOR_FIELD_END: self.reverse_end_field,
            constants.MUTATOR_TOGGLE_TRICKROOM: self.toggle_trickroom
        }

    def apply_one(self, instruction):
        method = self.apply_instructions[instruction[0]]
        method(*instruction[1:])

    def apply(self, instructions):
        for instruction in instructions:
            method = self.apply_instructions[instruction[0]]
            method(*instruction[1:])

    def reverse(self, instructions):
        for instruction in reversed(instructions):
            method = self.reverse_instructions[instruction[0]]
            method(*instruction[1:])

    def get_side(self, side):
        return getattr(self.state, side)

    def disable_move(self, side, move_name):
        side = self.get_side(side)
        try:
            move = next(filter(lambda x: x[constants.ID] == move_name, side.active.moves))
        except StopIteration:
            raise ValueError("{} not in pokemon's moves: {}".format(move_name, side.active.moves))

        move[constants.DISABLED] = True

    def enable_move(self, side, move_name):
        side = self.get_side(side)
        try:
            move = next(filter(lambda x: x[constants.ID] == move_name, side.active.moves))
        except StopIteration:
            raise ValueError("{} not in pokemon's moves: {}".format(move_name, side.active.moves))

        move[constants.DISABLED] = False

    def switch(self, side, _, switch_pokemon_name):
        # the second parameter to this function is the current active pokemon
        # this value must be here for reversing purposes
        side = self.get_side(side)

        side.reserve[side.active.id] = side.active
        side.active = side.reserve.pop(switch_pokemon_name)

    def reverse_switch(self, side, previous_active, current_active):
        self.switch(side, current_active, previous_active)

    def apply_volatile_status(self, side, volatile_status):
        side = self.get_side(side)
        side.active.volatile_status.add(volatile_status)

    def remove_volatile_status(self, side, volatile_status):
        side = self.get_side(side)
        side.active.volatile_status.remove(volatile_status)

    def damage(self, side, amount):
        side = self.get_side(side)
        side.active.hp -= amount

    def heal(self, side, amount):
        side = self.get_side(side)
        side.active.hp += amount

    def boost(self, side, stat, amount):
        side = self.get_side(side)
        if stat == constants.ATTACK:
            side.active.attack_boost += amount
        elif stat == constants.DEFENSE:
            side.active.defense_boost += amount
        elif stat == constants.SPECIAL_ATTACK:
            side.active.special_attack_boost += amount
        elif stat == constants.SPECIAL_DEFENSE:
            side.active.special_defense_boost += amount
        elif stat == constants.SPEED:
            side.active.speed_boost += amount
        elif stat == constants.ACCURACY:
            side.active.accuracy_boost += amount
        elif stat == constants.EVASION:
            side.active.evasion_boost += amount
        else:
            raise ValueError("Invalid stat: {}".format(stat))

    def unboost(self, side, stat, amount):
        self.boost(side, stat, -1*amount)

    def apply_status(self, side, status):
        side = self.get_side(side)
        side.active.status = status

    def remove_status(self, side, _):
        # the second parameter of this function is the status being removed
        # this value must be here for reverse purposes
        self.apply_status(side, None)

    def side_start(self, side, effect, amount):
        side = self.get_side(side)
        side.side_conditions[effect] += amount

    def reverse_side_start(self, side, effect, amount):
        side = self.get_side(side)
        side.side_conditions[effect] -= amount

    def side_end(self, side, effect, _):
        # the third parameter of this function is the amount being removed
        # this value must be here for reverse purposes
        side = self.get_side(side)
        side.side_conditions[effect] = 0

    def reverse_side_end(self, side, effect, amount):
        self.side_start(side, effect, amount)

    def start_weather(self, weather, _):
        # the second parameter is the current weather
        # the value is here for reversing purposes
        self.state.weather = weather

    def reverse_start_weather(self, _, old_weather):
        self.state.weather = old_weather

    def start_field(self, field, _):
        # the second parameter is the current field
        # the value is here for reversing purposes
        self.state.field = field

    def reverse_start_field(self, _, old_field):
        self.state.field = old_field

    def end_field(self, _):
        # the second parameter is the current field
        # the value is here for reversing purposes
        self.state.field = None

    def reverse_end_field(self, old_field):
        self.state.field = old_field

    def toggle_trickroom(self):
        self.state.trick_room ^= True

    def __key(self):
        return self.state

    def __eq__(self, other):
        return self.__key() == other.__key()

    def __hash__(self):
        return hash(self.__key())
