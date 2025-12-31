from enum import StrEnum


class BattleType(StrEnum):
    STANDARD_BATTLE = "standard_battle"
    BATTLE_FACTORY = "battle_factory"
    RANDOM_BATTLE = "random_battle"


NO_TEAM_PREVIEW_GENS = {"gen1", "gen2", "gen3", "gen4"}

START_STRING = "|start"
RQID = "rqid"
TEAM_PREVIEW_POKE = "poke"
START_TEAM_PREVIEW = "clearpoke"

MOVES = "moves"
ABILITIES = "abilities"
ITEMS = "items"
COUNT = "count"
SETS = "sets"

UNKNOWN_ITEM = "unknownitem"

# a lookup for the opponent's name given the bot's name
# this has to do with the Pokemon-Showdown PROTOCOL
ID_LOOKUP = {"p1": "p2", "p2": "p1"}

FORCE_SWITCH = "forceSwitch"
REVIVING = "reviving"
WAIT = "wait"
TRAPPED = "trapped"
MAYBE_TRAPPED = "maybeTrapped"
ITEM = "item"

CONDITION = "condition"
DISABLED = "disabled"
PP = "pp"

SELF = "self"

DO_NOTHING_MOVE = "splash"

ID = "id"
BASESTATS = "baseStats"
NAME = "name"
STATUS = "status"
TYPES = "types"
TYPE = "type"
WEIGHT = "weightkg"

SIDE = "side"
POKEMON = "pokemon"
FNT = "fnt"

SWITCH_STRING = "switch"
WIN_STRING = "|win|"
TIE_STRING = "|tie"
CHAT_STRING = "|c|"
TIME_LEFT = "Time left:"
DETAILS = "details"
IDENT = "ident"
TERA_TYPE = "teraType"

MEGA_EVOLVE_GENERATIONS = ["gen6", "gen7"]
CAN_MEGA_EVO = "canMegaEvo"
CAN_ULTRA_BURST = "canUltraBurst"
CAN_DYNAMAX = "canDynamax"
CAN_TERASTALLIZE = "canTerastallize"
CAN_Z_MOVE = "canZMove"
ZMOVE = "zmove"
ULTRA_BURST = "ultra"
MEGA = "mega"

ACTIVE = "active"

PRIORITY = "priority"
STATS = "stats"
BOOSTS = "boosts"

HITPOINTS = "hp"
ATTACK = "attack"
DEFENSE = "defense"
SPECIAL_ATTACK = "special-attack"
SPECIAL_DEFENSE = "special-defense"
SPEED = "speed"
ACCURACY = "accuracy"
EVASION = "evasion"

ABILITY = "ability"
REQUEST_DICT_ABILITY = ABILITY

MAX_BOOSTS = 6

STAT_ABBREVIATION_LOOKUPS = {
    "atk": ATTACK,
    "def": DEFENSE,
    "spa": SPECIAL_ATTACK,
    "spd": SPECIAL_DEFENSE,
    "spe": SPEED,
    "accuracy": ACCURACY,
    "evasion": EVASION,
}

HIDDEN_POWER = "hiddenpower"
HIDDEN_POWER_TYPE_STRING_INDEX = -1
HIDDEN_POWER_ACTIVE_MOVE_BASE_DAMAGE_STRING = "60"

PHYSICAL = "physical"
SPECIAL = "special"
CATEGORY = "category"

DAMAGING_CATEGORIES = [PHYSICAL, SPECIAL]

VOLATILE_STATUS = "volatileStatus"
LOCKED_MOVE = "lockedmove"

# Side-Effects
REFLECT = "reflect"
LIGHT_SCREEN = "lightscreen"
AURORA_VEIL = "auroraveil"
SAFEGUARD = "safeguard"
MIST = "mist"
TAILWIND = "tailwind"
STICKY_WEB = "stickyweb"
WISH = "wish"
FUTURE_SIGHT = "futuresight"
HEALING_WISH = "healingwish"

# weather
RAIN = "raindance"
SUN = "sunnyday"
SAND = "sandstorm"
HAIL = "hail"
SNOW = "snowscape"
DESOLATE_LAND = "desolateland"
HEAVY_RAIN = "primordialsea"

HAIL_OR_SNOW = {HAIL, SNOW}

# Hazards
STEALTH_ROCK = "stealthrock"
SPIKES = "spikes"
TOXIC_SPIKES = "toxicspikes"

TYPECHANGE = "typechange"

FIRST_TURN_MOVES = {"fakeout", "firstimpression"}

WEIGHT_BASED_MOVES = {
    "heavyslam",
    "heatcrash",
    "lowkick",
    "grassknot",
}

SPEED_BASED_MOVES = {"gyroball", "electroball"}

COURT_CHANGE_SWAPS = {
    "spikes",
    "toxicspikes",
    "stealthrock",
    "stickyweb",
    "lightscreen",
    "reflect",
    "auroraveil",
    "tailwind",
}

TRICK_ROOM = "trickroom"
GRAVITY = "gravity"

ELECTRIC_TERRAIN = "electricterrain"
GRASSY_TERRAIN = "grassyterrain"
MISTY_TERRAIN = "mistyterrain"
PSYCHIC_TERRAIN = "psychicterrain"

# switch-out moves
SWITCH_OUT_MOVES = {
    "uturn",
    "voltswitch",
    "partingshot",
    "teleport",
    "flipturn",
    "chillyreception",
    "shedtail",
}

# volatile statuses
CONFUSION = "confusion"
LEECH_SEED = "leechseed"
SUBSTITUTE = "substitute"
TAUNT = "taunt"
ROOST = "roost"
PROTECT = "protect"
BANEFUL_BUNKER = "banefulbunker"
SILK_TRAP = "silktrap"
ENDURE = "endure"
SPIKY_SHIELD = "spikyshield"
DYNAMAX = "dynamax"
SLOW_START = "slowstart"
TERASTALLIZE = "terastallize"
TRANSFORM = "transform"
YAWN = "yawn"
PARTIALLY_TRAPPED = "partiallytrapped"

PROTECT_VOLATILE_STATUSES = [PROTECT, BANEFUL_BUNKER, SPIKY_SHIELD, SILK_TRAP, ENDURE]

TAUNT_DURATION_INCREMENT_END_OF_TURN = {"gen3", "gen4"}

# non-volatile statuses
SLEEP = "slp"
BURN = "brn"
FROZEN = "frz"
PARALYZED = "par"
POISON = "psn"
TOXIC = "tox"
TOXIC_COUNT = "toxic_count"
NON_VOLATILE_STATUSES = {SLEEP, BURN, FROZEN, PARALYZED, POISON, TOXIC}

IMMUNE_TO_POISON_ABILITIES = {"immunity", "pastelveil"}

ASSAULT_VEST = "assaultvest"
HEAVY_DUTY_BOOTS = "heavydutyboots"
LEFTOVERS = "leftovers"
BLACK_SLUDGE = "blacksludge"
LIFE_ORB = "lifeorb"
CHOICE_SCARF = "choicescarf"
CHOICE_BAND = "choiceband"
CHOICE_SPECS = "choicespecs"
CHOICE_ITEMS = {CHOICE_BAND, CHOICE_SPECS, CHOICE_SCARF}
