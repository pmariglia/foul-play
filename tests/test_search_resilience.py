"""Regression for discarding a better KO line through near-top random selection."""

from types import SimpleNamespace
import logging
import pytest


@pytest.fixture
def enabled_logs():
    previous = logging.root.manager.disable
    logging.disable(logging.NOTSET)
    try:
        yield
    finally:
        logging.disable(previous)


def result(options):
    return SimpleNamespace(
        total_visits=sum(visits for _, visits in options),
        side_one=[
            SimpleNamespace(move_choice=move, visits=visits, total_score=visits * 0.4)
            for move, visits in options
        ],
    )


def test_native_panic_crosses_process_boundary_as_a_normal_exception():
    from concurrent.futures import ProcessPoolExecutor
    import pytest
    from fp.search.main import EngineSearchError, get_result_from_mcts

    # Invalid engine input deliberately raises a PyO3 PanicException in a real
    # child process. The parent must receive our serializable error, not a
    # PicklingError or ModuleNotFoundError for the virtual pyo3_runtime module.
    with ProcessPoolExecutor(max_workers=1) as executor:
        future = executor.submit(get_result_from_mcts, "invalid", 10, 0, 1)
        with pytest.raises(EngineSearchError, match="sample 0"):
            future.result(timeout=20)


def test_failed_sample_is_excluded_and_survivors_are_reweighted(caplog, enabled_logs):
    from concurrent.futures import Future
    from fp.search.main import EngineSearchError, collect_search_results

    failed, first, second = Future(), Future(), Future()
    failed.set_exception(EngineSearchError("native failure"))
    first.set_result(result([("tackle", 90), ("splash", 10)]))
    second.set_result(result([("tackle", 10), ("splash", 90)]))
    surviving = collect_search_results(
        [(failed, 0.5, 0), (first, 0.1, 1), (second, 0.4, 2)]
    )
    assert [chance for _, chance, _ in surviving] == [0.2, 0.8]
    assert "excluding this sample" in caplog.text


def test_unrelated_worker_error_is_not_silently_discarded():
    from concurrent.futures import Future
    import pytest
    from fp.search.main import collect_search_results

    future = Future()
    future.set_exception(ValueError("unexpected programming error"))
    with pytest.raises(ValueError):
        collect_search_results([(future, 1, 0)])


def fallback_battle():
    from fp.battle.state import Battle, Pokemon, Move

    battle = Battle("battle-gen6randombattle-1")
    battle.user.active = Pokemon("mew", 100)
    disabled = Move("splash")
    disabled.disabled = True
    exhausted = Move("protect")
    exhausted.current_pp = 0
    battle.user.active.moves = [disabled, exhausted, Move("tackle")]
    battle.user.reserve = [Pokemon("pikachu", 100), Pokemon("snorlax", 100)]
    battle.user.reserve[0].hp = 0
    battle.user.reserve[1].index = 3
    battle.rqid = 42
    return battle


def test_emergency_move_respects_disabled_moves_and_exhausted_pp():
    from fp.search.main import emergency_move
    from fp.modes.base import format_decision

    battle = fallback_battle()
    choice = emergency_move(battle)
    assert choice == "tackle"
    assert format_decision(battle, choice) == ["/choose move tackle", "42"]
    battle.user.active.moves[-1].disabled = True
    assert emergency_move(battle) == "struggle"


def test_emergency_forced_switch_only_chooses_a_living_reserve():
    from fp.search.main import emergency_move
    from fp.modes.base import format_decision

    battle = fallback_battle()
    battle.force_switch = True
    choice = emergency_move(battle)
    assert choice == "switch snorlax"
    assert format_decision(battle, choice) == ["/switch 3", "42"]


def test_all_failed_samples_choose_a_legal_move_and_log_failure(
    monkeypatch, caplog, enabled_logs
):
    from concurrent.futures import Future
    from fp.config import FoulPlayConfig
    from fp.search import main

    battle = fallback_battle()
    battle.mode = SimpleNamespace(
        search_params=lambda b: (2, 10),
        prepare_battles=lambda b, n: [(b, 0.5), (b, 0.5)],
    )

    class FailedExecutor:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def submit(self, *args):
            future = Future()
            future.set_exception(main.EngineSearchError("native failure"))
            return future

    monkeypatch.setattr(main, "ProcessPoolExecutor", FailedExecutor)
    monkeypatch.setattr(
        main,
        "battle_to_poke_engine_state",
        lambda b: SimpleNamespace(to_string=lambda: "unused"),
    )
    monkeypatch.setattr(FoulPlayConfig, "parallelism", 1, raising=False)
    monkeypatch.setattr(FoulPlayConfig, "search_threads", 1, raising=False)
    assert main.find_best_move(battle) == "tackle"
    assert (
        "All native search samples failed; using legal fallback: tackle" in caplog.text
    )


def test_worker_does_not_convert_keyboard_interrupt(monkeypatch):
    import pytest
    from fp.search import main

    def interrupt(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(main, "PokeEngineState", SimpleNamespace(from_string=interrupt))
    with pytest.raises(KeyboardInterrupt):
        main.get_result_from_mcts("unused", 10, 0, 1)
