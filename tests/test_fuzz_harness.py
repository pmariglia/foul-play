import contextvars

from fp.constants import BattleType
from fuzz.harness import USERNAME, USERNAMES, bot_battle_mode, prepare_format


def _mode_for(username, battle_type):
    def get():
        USERNAME.set(username)
        return bot_battle_mode(battle_type)

    return contextvars.copy_context().run(get)


def test_each_bot_gets_its_own_battle_mode():
    # the modes hold per-battle state, e.g. the randbats sets narrowed by the reverse damage calc
    p1 = _mode_for(USERNAMES["p1"], BattleType.RANDOM_BATTLE)
    p2 = _mode_for(USERNAMES["p2"], BattleType.RANDOM_BATTLE)

    assert p1 is not p2
    assert p1.datasets is not p2.datasets


def test_a_bot_keeps_the_same_battle_mode():
    assert _mode_for(USERNAMES["p1"], BattleType.RANDOM_BATTLE) is _mode_for(
        USERNAMES["p1"], BattleType.RANDOM_BATTLE
    )


def test_prepare_format_applies_the_generations_data_mods(monkeypatch):
    applied = []
    monkeypatch.setattr(
        "fuzz.harness.apply_mods", lambda format_spec: applied.append(format_spec)
    )

    prepare_format("gen4randombattle")

    assert ["gen4"] == [f.generation for f in applied]
