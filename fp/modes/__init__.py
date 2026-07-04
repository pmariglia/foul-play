from fp.constants import BattleType
from fp.modes.base import BattleMode
from fp.modes.battle_factory import BattleFactoryMode
from fp.modes.random_battle import RandomBattleMode
from fp.modes.standard_battle import StandardBattleMode

BATTLE_MODES = {
    BattleType.RANDOM_BATTLE: RandomBattleMode(),
    BattleType.STANDARD_BATTLE: StandardBattleMode(),
    BattleType.BATTLE_FACTORY: BattleFactoryMode(),
}


def battle_mode(battle_type: BattleType) -> BattleMode:
    return BATTLE_MODES[battle_type]
