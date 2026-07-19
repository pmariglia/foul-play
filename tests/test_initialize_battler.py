import pytest

from fp import constants
from fp.battle.state import Battler, Move, LastUsedMove
from fp.battle.state import Pokemon


class TestUpdateFromRequestJson:
    @pytest.fixture(autouse=True)
    def _setup(self):
        self.battler = Battler()

    def test_basic_updating_attributes_for_active_pkmn(self):
        request_dict = {
            "active": [
                {
                    "moves": [
                        {
                            "move": "Volt Tackle",
                            "id": "volttackle",
                            "pp": 32,
                            "maxpp": 32,
                            "target": "self",
                            "disabled": False,
                        },
                        {
                            "move": "Thunderbolt",
                            "id": "thunderbolt",
                            "pp": 8,
                            "maxpp": 8,
                            "target": "normal",
                            "disabled": False,
                        },
                        {
                            "move": "Hidden Power Ice 60",
                            "id": "hiddenpower",
                            "pp": 16,
                            "maxpp": 16,
                            "target": "allAdjacent",
                            "disabled": False,
                        },
                        {
                            "move": "Nasty Plot",
                            "id": "nastyplot",
                            "pp": 8,
                            "maxpp": 8,
                            "target": "normal",
                            "disabled": False,
                        },
                    ],
                }
            ],
            "side": {
                "name": "BigBluePikachu",
                "id": "p2",
                "pokemon": [
                    {
                        "ident": "p2: PikachuNickname",
                        "details": "Pikachu, L84, M",
                        "condition": "152/335",
                        "active": True,
                        "stats": {
                            "atk": 200,
                            "def": 210,
                            "spa": 220,
                            "spd": 230,
                            "spe": 240,
                        },
                        "moves": [
                            "volttackle",
                            "thunderbolt",
                            "hiddenpowerice60",
                            "nastyplot",
                        ],
                        "baseAbility": "static",
                        "item": "lightball",
                        "ability": "static",
                    },
                ],
            },
        }
        self.battler.active = Pokemon("pikachu", 100)

        self.battler.update_from_request_json(request_dict)

        assert self.battler.active.nickname == "PikachuNickname"
        assert self.battler.active.status is None
        assert self.battler.active.level == 84
        assert self.battler.active.hp == 152
        assert self.battler.active.max_hp == 335
        assert self.battler.active.ability == "static"
        assert self.battler.active.item == "lightball"
        assert self.battler.active.stats == {
            "attack": 200,
            "defense": 210,
            "special-attack": 220,
            "special-defense": 230,
            "speed": 240,
        }
        assert self.battler.active.moves == [
            Move("volttackle"),
            Move("thunderbolt"),
            Move("hiddenpowerice"),
            Move("nastyplot"),
        ]

    def test_gigatonhammer_un_disabled_if_it_is_last_used_move(self):
        request_dict = {
            "active": [
                {
                    "moves": [
                        {
                            "move": "Gigaton Hammer",
                            "id": "gigatonhammer",
                            "pp": 31,
                            "maxpp": 32,
                            "target": "self",
                            "disabled": True,
                        },
                        {
                            "move": "Thunderbolt",
                            "id": "thunderbolt",
                            "pp": 8,
                            "maxpp": 8,
                            "target": "normal",
                            "disabled": False,
                        },
                        {
                            "move": "Hidden Power Ice 60",
                            "id": "hiddenpower",
                            "pp": 16,
                            "maxpp": 16,
                            "target": "allAdjacent",
                            "disabled": False,
                        },
                        {
                            "move": "Nasty Plot",
                            "id": "nastyplot",
                            "pp": 8,
                            "maxpp": 8,
                            "target": "normal",
                            "disabled": False,
                        },
                    ],
                }
            ],
            "side": {
                "name": "BigBluePikachu",
                "id": "p2",
                "pokemon": [
                    {
                        "ident": "p2: PikachuNickname",
                        "details": "Pikachu, L84, M",
                        "condition": "152/335",
                        "active": True,
                        "stats": {
                            "atk": 200,
                            "def": 210,
                            "spa": 220,
                            "spd": 230,
                            "spe": 240,
                        },
                        "moves": [
                            "volttackle",
                            "thunderbolt",
                            "hiddenpowerice60",
                            "nastyplot",
                        ],
                        "baseAbility": "static",
                        "item": "lightball",
                        "ability": "static",
                    },
                ],
            },
        }
        self.battler.active = Pokemon("pikachu", 100)
        self.battler.last_used_move = LastUsedMove(
            pokemon_name="pikachu", move="gigatonhammer", turn=0
        )

        self.battler.update_from_request_json(request_dict)

        assert self.battler.active.get_move("gigatonhammer").disabled is False

    def test_gigatonhammer_remains_disabled_when_choice_item_selecting_another_move(
        self,
    ):
        request_dict = {
            "active": [
                {
                    "moves": [
                        {
                            "move": "Gigaton Hammer",
                            "id": "gigatonhammer",
                            "pp": 31,
                            "maxpp": 32,
                            "target": "self",
                            "disabled": True,
                        },
                        {
                            "move": "Thunderbolt",
                            "id": "thunderbolt",
                            "pp": 8,
                            "maxpp": 8,
                            "target": "normal",
                            "disabled": False,
                        },
                        {
                            "move": "Hidden Power Ice 60",
                            "id": "hiddenpower",
                            "pp": 16,
                            "maxpp": 16,
                            "target": "allAdjacent",
                            "disabled": True,
                        },
                        {
                            "move": "Nasty Plot",
                            "id": "nastyplot",
                            "pp": 8,
                            "maxpp": 8,
                            "target": "normal",
                            "disabled": True,
                        },
                    ],
                }
            ],
            "side": {
                "name": "BigBluePikachu",
                "id": "p2",
                "pokemon": [
                    {
                        "ident": "p2: PikachuNickname",
                        "details": "Pikachu, L84, M",
                        "condition": "152/335",
                        "active": True,
                        "stats": {
                            "atk": 200,
                            "def": 210,
                            "spa": 220,
                            "spd": 230,
                            "spe": 240,
                        },
                        "moves": [
                            "volttackle",
                            "thunderbolt",
                            "hiddenpowerice60",
                            "nastyplot",
                        ],
                        "baseAbility": "static",
                        "item": "lightball",
                        "ability": "static",
                    },
                ],
            },
        }
        self.battler.active = Pokemon("pikachu", 100)
        self.battler.last_used_move = LastUsedMove(
            pokemon_name="pikachu", move="thunderbolt", turn=0
        )

        self.battler.update_from_request_json(request_dict)

        assert self.battler.active.get_move("gigatonhammer").disabled is True

    def test_sets_trapped(self):
        request_dict = {
            "active": [
                {
                    "trapped": True,
                    "moves": [
                        {
                            "move": "Volt Tackle",
                            "id": "volttackle",
                            "pp": 32,
                            "maxpp": 32,
                            "target": "self",
                            "disabled": False,
                        },
                        {
                            "move": "Thunderbolt",
                            "id": "thunderbolt",
                            "pp": 8,
                            "maxpp": 8,
                            "target": "normal",
                            "disabled": False,
                        },
                        {
                            "move": "Hidden Power Ice 60",
                            "id": "hiddenpower",
                            "pp": 16,
                            "maxpp": 16,
                            "target": "allAdjacent",
                            "disabled": False,
                        },
                        {
                            "move": "Nasty Plot",
                            "id": "nastyplot",
                            "pp": 8,
                            "maxpp": 8,
                            "target": "normal",
                            "disabled": False,
                        },
                    ],
                }
            ],
            "side": {
                "name": "BigBluePikachu",
                "id": "p2",
                "pokemon": [
                    {
                        "ident": "p2: PikachuNickname",
                        "details": "Pikachu, L84, M",
                        "condition": "152/335",
                        "active": True,
                        "stats": {
                            "atk": 200,
                            "def": 210,
                            "spa": 220,
                            "spd": 230,
                            "spe": 240,
                        },
                        "moves": [
                            "volttackle",
                            "thunderbolt",
                            "hiddenpowerice60",
                            "nastyplot",
                        ],
                        "baseAbility": "static",
                        "item": "lightball",
                        "ability": "static",
                    },
                ],
            },
        }
        self.battler.active = Pokemon("pikachu", 100)

        self.battler.update_from_request_json(request_dict)

        assert self.battler.trapped

    def test_active_optional_attributes(self):
        request_dict = {
            "active": [
                {
                    constants.CAN_MEGA_EVO: True,
                    constants.CAN_ULTRA_BURST: True,
                    constants.CAN_DYNAMAX: True,
                    constants.CAN_TERASTALLIZE: True,
                    "moves": [
                        {
                            "move": "Volt Tackle",
                            "id": "volttackle",
                            "pp": 32,
                            "maxpp": 32,
                            "target": "self",
                            "disabled": False,
                        },
                        {
                            "move": "Thunderbolt",
                            "id": "thunderbolt",
                            "pp": 8,
                            "maxpp": 8,
                            "target": "normal",
                            "disabled": False,
                        },
                        {
                            "move": "Hidden Power Ice 60",
                            "id": "hiddenpower",
                            "pp": 16,
                            "maxpp": 16,
                            "target": "allAdjacent",
                            "disabled": False,
                        },
                        {
                            "move": "Nasty Plot",
                            "id": "nastyplot",
                            "pp": 8,
                            "maxpp": 8,
                            "target": "normal",
                            "disabled": False,
                        },
                    ],
                }
            ],
            "side": {
                "name": "BigBluePikachu",
                "id": "p2",
                "pokemon": [
                    {
                        "ident": "p2: PikachuNickname",
                        "details": "Pikachu, L84, M",
                        "condition": "152/335",
                        "active": True,
                        "stats": {
                            "atk": 200,
                            "def": 210,
                            "spa": 220,
                            "spd": 230,
                            "spe": 240,
                        },
                        "moves": [
                            "volttackle",
                            "thunderbolt",
                            "hiddenpowerice60",
                            "nastyplot",
                        ],
                        "baseAbility": "static",
                        "item": "lightball",
                        "ability": "static",
                    },
                ],
            },
        }
        self.battler.active = Pokemon("pikachu", 100)

        self.battler.update_from_request_json(request_dict)

        assert self.battler.active.can_mega_evo
        assert self.battler.active.can_ultra_burst
        assert self.battler.active.can_dynamax
        assert self.battler.active.can_terastallize

    def test_basic_updating_attributes_for_reserve_pkmn(self):
        request_dict = {
            "active": [
                {
                    "moves": [
                        {
                            "move": "Volt Tackle",
                            "id": "volttackle",
                            "pp": 32,
                            "maxpp": 32,
                            "target": "self",
                            "disabled": False,
                        },
                        {
                            "move": "Thunderbolt",
                            "id": "thunderbolt",
                            "pp": 8,
                            "maxpp": 8,
                            "target": "normal",
                            "disabled": False,
                        },
                        {
                            "move": "Hidden Power Ice 60",
                            "id": "hiddenpower",
                            "pp": 16,
                            "maxpp": 16,
                            "target": "allAdjacent",
                            "disabled": False,
                        },
                        {
                            "move": "Nasty Plot",
                            "id": "nastyplot",
                            "pp": 8,
                            "maxpp": 8,
                            "target": "normal",
                            "disabled": False,
                        },
                    ],
                }
            ],
            "side": {
                "name": "BigBluePikachu",
                "id": "p2",
                "pokemon": [
                    {
                        "ident": "p2: MyPikachu",
                        "details": "Pikachu, L84, M",
                        "condition": "152/335",
                        "active": True,
                        "stats": {
                            "atk": 200,
                            "def": 210,
                            "spa": 220,
                            "spd": 230,
                            "spe": 240,
                        },
                        "moves": [
                            "volttackle",
                            "thunderbolt",
                            "hiddenpowerice60",
                            "nastyplot",
                        ],
                        "baseAbility": "static",
                        "item": "lightball",
                        "ability": "static",
                    },
                    {
                        "ident": "p2: RattataNickName",
                        "details": "Rattata",
                        "condition": "100/300 par",
                        "active": False,
                        "stats": {
                            "atk": 100,
                            "def": 110,
                            "spa": 120,
                            "spd": 130,
                            "spe": 140,
                        },
                        "moves": [
                            "tackle",
                            "tailwhip",
                            "hiddenpowerrock60",
                            "growl",
                        ],
                        "baseAbility": "runaway",
                        "item": "leftovers",
                        "ability": "runaway",
                    },
                ],
            },
        }
        self.battler.active = Pokemon("pikachu", 100)
        rattata = Pokemon("rattata", 50)
        self.battler.reserve.append(rattata)

        self.battler.update_from_request_json(request_dict)

        assert rattata.level == 100
        assert rattata.status == constants.Status.PARALYZED
        assert rattata.ability == "runaway"
        assert rattata.ability == "runaway"
        assert rattata.item == "leftovers"
        assert rattata.stats == {
            "attack": 100,
            "defense": 110,
            "special-attack": 120,
            "special-defense": 130,
            "speed": 140,
        }
        assert rattata.moves == [
            Move("tackle"),
            Move("tailwhip"),
            Move("hiddenpowerrock"),
            Move("growl"),
        ]

    def test_reserve_pkmn_has_pp_preserved(self):
        request_dict = {
            "active": [
                {
                    "moves": [
                        {
                            "move": "Volt Tackle",
                            "id": "volttackle",
                            "pp": 32,
                            "maxpp": 32,
                            "target": "self",
                            "disabled": False,
                        },
                        {
                            "move": "Thunderbolt",
                            "id": "thunderbolt",
                            "pp": 8,
                            "maxpp": 8,
                            "target": "normal",
                            "disabled": False,
                        },
                        {
                            "move": "Hidden Power Ice 60",
                            "id": "hiddenpower",
                            "pp": 16,
                            "maxpp": 16,
                            "target": "allAdjacent",
                            "disabled": False,
                        },
                        {
                            "move": "Nasty Plot",
                            "id": "nastyplot",
                            "pp": 8,
                            "maxpp": 8,
                            "target": "normal",
                            "disabled": False,
                        },
                    ],
                }
            ],
            "side": {
                "name": "BigBluePikachu",
                "id": "p2",
                "pokemon": [
                    {
                        "ident": "p2: MyPikachu",
                        "details": "Pikachu, L84, M",
                        "condition": "152/335",
                        "active": True,
                        "stats": {
                            "atk": 200,
                            "def": 210,
                            "spa": 220,
                            "spd": 230,
                            "spe": 240,
                        },
                        "moves": [
                            "volttackle",
                            "thunderbolt",
                            "hiddenpowerice60",
                            "nastyplot",
                        ],
                        "baseAbility": "static",
                        "item": "lightball",
                        "ability": "static",
                    },
                    {
                        "ident": "p2: RattataNickName",
                        "details": "Rattata, L84, M",
                        "condition": "100/300",
                        "active": False,
                        "stats": {
                            "atk": 100,
                            "def": 110,
                            "spa": 120,
                            "spd": 130,
                            "spe": 140,
                        },
                        "moves": [
                            "tackle",
                            "tailwhip",
                            "hiddenpowerrock60",
                            "growl",
                        ],
                        "baseAbility": "runaway",
                        "item": "leftovers",
                        "ability": "runaway",
                    },
                ],
            },
        }
        self.battler.active = Pokemon("pikachu", 100)
        rattata = Pokemon("rattata", 100)
        tackle = Move("tackle")
        tackle.max_pp = 32
        tackle.current_pp = 16
        rattata.moves.append(tackle)
        self.battler.reserve.append(rattata)

        self.battler.update_from_request_json(request_dict)

        assert 16 == rattata.get_move("tackle").current_pp
