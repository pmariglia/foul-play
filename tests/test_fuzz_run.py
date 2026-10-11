import argparse
import itertools
import multiprocessing

import pytest

from fuzz.detectors import Severity
from fuzz.run import battle_plan, parse_args, parse_severities, should_stop


def _args(*argv):
    args = parse_args(["--seed", "777", *argv])
    args.deadline = None
    return args


def test_battles_default_to_20_without_until_finding():
    assert 20 == _args().battles


def test_until_finding_has_no_battle_limit_by_default():
    assert _args("--until-finding").battles is None


def test_workers_split_the_same_battles_as_a_single_worker():
    args = _args("--battles", "10", "--formats", "gen9randombattle,gen4randombattle")
    single = list(battle_plan(args))
    split = [list(battle_plan(args, worker_id, 3)) for worker_id in range(3)]

    assert 10 == len(single)
    assert sorted(single) == sorted(itertools.chain(*split))
    assert single[1::3] == split[1]


def test_until_finding_plays_the_same_battles_as_a_fixed_run():
    fixed = list(battle_plan(_args("--battles", "6")))
    unlimited = battle_plan(_args("--until-finding"), worker_id=1, jobs=2)

    assert fixed[1::2] == list(itertools.islice(unlimited, 3))


def test_battle_seed_is_only_run_by_the_first_worker():
    args = _args("--battle-seed", "gen5,0123456789abcdef")
    assert [("gen9randombattle", "gen5,0123456789abcdef")] == list(battle_plan(args))
    assert [] == list(battle_plan(args, worker_id=1, jobs=2))


def test_stop_on_defaults_to_error_drift_and_info():
    assert {Severity.ERROR, Severity.DRIFT, Severity.INFO} == _args().stop_on


def test_stop_on_rejects_new_signature():
    with pytest.raises(argparse.ArgumentTypeError):
        parse_severities("error,new-signature")


def test_should_stop_when_the_event_is_set_or_the_deadline_passed():
    args = _args()
    event = multiprocessing.Event()
    assert not should_stop(args, event)

    args.deadline = 0
    assert should_stop(args, event)

    args.deadline = None
    event.set()
    assert should_stop(args, event)
