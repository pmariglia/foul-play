import logging

from fp import constants
from fp.battle.helpers import normalize_name, type_effectiveness_modifier
from fp.constants import BattleType
from fp.data import all_move_json
from fp.data.sets import BattleFactoryTeamDatasets
from fp.format_spec import FormatSpec
from fp.modes.base import _switch_active_with_zoroark_from_reserves
from fp.modes.standard_battle import StandardBattleMode
from fp.search.random_battles import prepare_random_battles

logger = logging.getLogger(__name__)


def extract_battle_factory_tier_from_msg(msg):
    start = msg.find("Battle Factory Tier: ") + len("Battle Factory Tier: ")
    end = msg.find("</b>", start)
    tier_name = msg[start:end]

    return normalize_name(tier_name)


class BattleFactoryMode(StandardBattleMode):
    name = BattleType.BATTLE_FACTORY
    requires_team = False

    def __init__(self):
        super().__init__()
        # constructed once the tier is revealed during team preview
        self.team_datasets = None

    def initialize_team_preview_datasets(
        self, pokemon_battle_type, unique_pkmn_names, msg
    ):
        tier_name = extract_battle_factory_tier_from_msg(msg)
        logger.info("Battle Factory Tier: {}".format(tier_name))
        self.team_datasets = BattleFactoryTeamDatasets(tier_name)
        self.team_datasets.initialize(
            FormatSpec.from_format_string(pokemon_battle_type), unique_pkmn_names
        )

    def add_revealed_pokemon(self, battle, pkmn):
        # battle factory pkmn are known from team preview; nothing to add mid-battle
        pass

    def prepare_battles(self, battle, num_battles):
        return prepare_random_battles(battle, num_battles)

    def get_all_remaining_sets(self, pkmn):
        return self.team_datasets.get_all_remaining_sets(pkmn)

    def check_zoroark_from_immune(self, battle, side, pkmn, zoroark_from_reserves):
        # Battle Factory: Zoroark must be in the reserves
        # and must be immune to the last used move by the bot
        if (
            zoroark_from_reserves is not None
            and type_effectiveness_modifier(
                all_move_json[battle.user.last_used_move.move][constants.TYPE],
                zoroark_from_reserves.types,
            )
            == 0
        ):
            logger.info(
                "{} was immune to {} when it shouldn't be - it is {}".format(
                    pkmn.name,
                    battle.user.last_used_move.move,
                    zoroark_from_reserves.name,
                )
            )
            _switch_active_with_zoroark_from_reserves(side, zoroark_from_reserves)

    def dataset_possibilities(self, battle):
        possibilites = self.team_datasets.get_pkmn_sets_from_pkmn_name(
            battle.opponent.active
        )
        return possibilites, None, False
