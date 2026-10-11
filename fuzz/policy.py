"""
A random stand-in for `fp.modes.base.async_pick_move`

The search is irrelevant to protocol parsing, so it is replaced with a random choice
among the options foul-play itself believes are legal after applying the request JSON.
Decisions are still formatted with foul-play's own `format_decision`, so a request that
foul-play misreads tends to surface as an `[Invalid choice]` from PS.
"""

import random
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import dataclass

from fp.battle.state import LastUsedMove
from fp.modes.base import format_decision

# each bot runs in its own asyncio task, so per-bot state lives in context variables
POLICY_RNG: ContextVar[random.Random] = ContextVar("POLICY_RNG")


@dataclass
class PolicyOptions:
    switch_probability: float = 0.15
    tera_probability: float = 0.2
    mega_probability: float = 0.6


OPTIONS = PolicyOptions()

# foul-play re-enables these after PS disables them, and leaves it to poke-engine to not pick
# them twice in a row (see `Battler._initialize_user_active_from_request`), so do the same here
CANNOT_USE_TWICE_IN_A_ROW = {"gigatonhammer", "bloodmoon"}


def _switch_decisions(battle_copy):
    # revival blessing targets never get here: `fp.run_battle` answers those with `default`
    return ["switch {}".format(p.name) for p in battle_copy.user.reserve if p.hp > 0]


def _move_decisions(battle_copy):
    rng = POLICY_RNG.get()
    active = battle_copy.user.active
    last_used_move = battle_copy.user.last_used_move.move
    decisions = []
    for mv in active.moves:
        if mv.disabled or mv.current_pp <= 0:
            continue
        if mv.name in CANNOT_USE_TWICE_IN_A_ROW and mv.name == last_used_move:
            continue
        decision = mv.name
        if active.can_terastallize and rng.random() < OPTIONS.tera_probability:
            decision += "-tera"
        elif active.can_mega_evo and rng.random() < OPTIONS.mega_probability:
            decision += "-mega"
        decisions.append(decision)
    return decisions


def _pick(battle_copy) -> str | None:
    rng = POLICY_RNG.get()
    if battle_copy.force_switch:
        switches = _switch_decisions(battle_copy)
        return rng.choice(switches) if switches else None

    moves = _move_decisions(battle_copy)
    switches = [] if battle_copy.user.trapped else _switch_decisions(battle_copy)
    if switches and (not moves or rng.random() < OPTIONS.switch_probability):
        return rng.choice(switches)
    return rng.choice(moves) if moves else None


async def random_pick_move(battle):
    rng = POLICY_RNG.get()

    if battle.team_preview:
        # `handle_team_preview` expects a "/switch <n>" decision
        return ["/switch {}".format(rng.randint(1, len(battle.user.reserve))), ""]

    battle_copy = deepcopy(battle)
    battle_copy.user.update_from_request(battle_copy.request)

    decision = _pick(battle_copy)
    if decision is None:
        return ["/choose default", str(battle.rqid)]

    battle.user.last_selected_move = LastUsedMove(
        battle.user.active.name,
        decision.removesuffix("-tera").removesuffix("-mega"),
        battle.turn,
    )
    return format_decision(battle_copy, decision)
