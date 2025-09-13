import logging
import os
import sys
from enum import Enum, auto
from logging.handlers import RotatingFileHandler
from typing import Optional

from environs import Env

import constants

env = Env()
env.read_env(path="env", recurse=False)


class CustomFormatter(logging.Formatter):
    def format(self, record):
        lvl = "{}".format(record.levelname)
        return "{} {}".format(lvl.ljust(8), record.msg)


class CustomRotatingFileHandler(RotatingFileHandler):
    def __init__(self, file_name, **kwargs):
        self.base_dir = "logs"
        if not os.path.exists(self.base_dir):
            os.mkdir(self.base_dir)

        super().__init__("{}/{}".format(self.base_dir, file_name), **kwargs)

    def do_rollover(self, new_file_name):
        new_file_name = new_file_name.replace("/", "_")
        self.baseFilename = "{}/{}".format(self.base_dir, new_file_name)
        self.doRollover()


def init_logging(level, log_to_file):
    websockets_logger = logging.getLogger("websockets")
    websockets_logger.setLevel(logging.INFO)
    requests_logger = logging.getLogger("urllib3")
    requests_logger.setLevel(logging.INFO)

    # Gets the root logger to set handlers/formatters
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(level)
    stdout_handler.setFormatter(CustomFormatter())
    logger.addHandler(stdout_handler)
    FoulPlayConfig.stdout_log_handler = stdout_handler

    if log_to_file:
        file_handler = CustomRotatingFileHandler("init.log")
        file_handler.setLevel(logging.DEBUG)  # file logs are always debug
        file_handler.setFormatter(CustomFormatter())
        logger.addHandler(file_handler)
        FoulPlayConfig.file_log_handler = file_handler


class SaveReplay(Enum):
    Always = auto()
    Never = auto()
    OnLoss = auto()


class _FoulPlayConfig:
    battle_bot_module: str
    websocket_uri: str
    username: str
    password: str
    user_id: str
    avatar: str
    bot_mode: str
    pokemon_mode: str = ""
    smogon_stats: str = None
    search_time_ms: int
    parallelism: int
    run_count: int
    team: str
    user_to_challenge: str
    save_replay: SaveReplay
    room_name: str
    damage_calc_type: str
    log_level: str
    log_to_file: bool
    stdout_log_handler: logging.StreamHandler
    file_log_handler: Optional[CustomRotatingFileHandler]

    def configure(self):
        self.battle_bot_module = env("BATTLE_BOT")
        self.websocket_uri = env("WEBSOCKET_URI")
        self.username = env("PS_USERNAME")
        self.password = env("PS_PASSWORD")
        self.avatar = env("PS_AVATAR", None)
        self.bot_mode = env("BOT_MODE")
        self.pokemon_mode = env("POKEMON_MODE")
        self.smogon_stats = env("SMOGON_STATS", None)

        self.search_time_ms = env.int("SEARCH_TIME_MS", 100)
        self.parallelism = env.int("MCTS_PARALLELISM", 1)

        self.run_count = env.int("RUN_COUNT", 1)
        self.team = env("TEAM_NAME", None)
        self.user_to_challenge = env("USER_TO_CHALLENGE", None)

        self.save_replay = SaveReplay[env.str("SAVE_REPLAY", "Never")]
        self.room_name = env("ROOM_NAME", None)
        self.damage_calc_type = env("DAMAGE_CALC_TYPE", "average")

        self.log_level = env("LOG_LEVEL", "DEBUG")
        self.log_to_file = env.bool("LOG_TO_FILE", False)

        self.validate_config()

    def validate_config(self):
        assert self.bot_mode in constants.BOT_MODES

        if self.bot_mode == constants.CHALLENGE_USER:
            assert (
                self.user_to_challenge is not None
            ), "If bot_mode is `CHALLENGE_USER, you must declare USER_TO_CHALLENGE"


FoulPlayConfig = _FoulPlayConfig()
