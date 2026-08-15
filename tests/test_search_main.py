import logging

import pytest

from poke_engine import MctsResult, MctsSideResult

from fp.search.main import (
    REGRET_ALERT_THRESHOLD,
    SHRINKAGE_VISITS,
    compute_move_expected_values,
    compute_q_matrix,
    compute_regret_matrix,
    expected_value_choice_with_cvar,
    regret_cvar,
    world_q_values,
)


def make_world(options):
    # options: list of (move, q, visits)
    side_one = [
        MctsSideResult(move_choice=move, total_score=q * visits, visits=visits)
        for move, q, visits in options
    ]
    return MctsResult(
        side_one=side_one,
        side_two=[],
        total_visits=sum(visits for _, _, visits in options),
    )


def uniform_results(worlds):
    return [(world, 1 / len(worlds), index) for index, world in enumerate(worlds)]


# 3 worlds where earthquake is marginally best, 1 scarf-style world where
# it is a disaster
SCARF_SCENARIO = uniform_results(
    [
        make_world(
            [
                ("earthquake", 0.56, 7000),
                ("voltswitch", 0.54, 2600),
                ("switch slowbro", 0.40, 400),
            ]
        ),
        make_world(
            [
                ("earthquake", 0.55, 6500),
                ("voltswitch", 0.53, 3100),
                ("switch slowbro", 0.42, 400),
            ]
        ),
        make_world(
            [
                ("earthquake", 0.57, 7200),
                ("voltswitch", 0.55, 2400),
                ("switch slowbro", 0.41, 400),
            ]
        ),
        make_world(
            [
                ("earthquake", 0.15, 900),
                ("voltswitch", 0.52, 8500),
                ("switch slowbro", 0.45, 600),
            ]
        ),
    ]
)

UNANIMOUS_SCENARIO = uniform_results(
    [
        make_world([("earthquake", 0.7, 8000), ("voltswitch", 0.5, 2000)]),
        make_world([("earthquake", 0.72, 7500), ("voltswitch", 0.48, 2500)]),
    ]
)


def test_world_q_values_shrinks_low_visit_moves_toward_world_average():
    world = make_world(
        [("earthquake", 0.9, SHRINKAGE_VISITS), ("voltswitch", 0.5, 10000)]
    )
    q_values = world_q_values(world)

    world_avg = (0.9 * SHRINKAGE_VISITS + 0.5 * 10000) / (SHRINKAGE_VISITS + 10000)

    # earthquake has exactly SHRINKAGE_VISITS visits so its q and the world
    # average get equal weight
    assert q_values["earthquake"] == pytest.approx((0.9 + world_avg) / 2)

    # voltswitch is heavily visited so shrinkage barely moves it
    assert q_values["voltswitch"] == pytest.approx(0.5, abs=0.005)


def test_expected_values_prefer_robust_move_in_scarf_scenario():
    expected_values = compute_move_expected_values(SCARF_SCENARIO)
    assert max(expected_values, key=expected_values.get) == "voltswitch"


def test_q_matrix_shape_matches_worlds_and_moves():
    q_matrix = compute_q_matrix(SCARF_SCENARIO)

    assert set(q_matrix) == {"earthquake", "voltswitch", "switch slowbro"}
    for move in q_matrix:
        assert set(q_matrix[move]) == {0, 1, 2, 3}

    # world 3 is the scarf world where earthquake collapses
    assert q_matrix["earthquake"][3] < 0.2
    assert q_matrix["voltswitch"][3] > 0.5


def test_regret_matrix_zero_for_best_move_in_each_world():
    regret_matrix = compute_regret_matrix(compute_q_matrix(SCARF_SCENARIO))

    # earthquake is the best move in worlds 0-2, voltswitch in world 3
    for index in range(3):
        assert regret_matrix["earthquake"][index] == 0.0
        assert regret_matrix["voltswitch"][index] > 0.0
    assert regret_matrix["voltswitch"][3] == 0.0
    assert regret_matrix["earthquake"][3] > 0.3


def test_regret_cvar_alpha_one_is_weighted_mean():
    assert regret_cvar([1, 2, 3, 4], [1, 1, 1, 1], 1.0) == pytest.approx(2.5)


def test_regret_cvar_small_alpha_is_worst_regret():
    assert regret_cvar([1, 2, 3, 4], [1, 1, 1, 1], 0.25) == pytest.approx(4.0)


def test_regret_cvar_fractional_boundary():
    # budget = 1.5 units of weight: all of regret=3 plus half of regret=2
    assert regret_cvar([3, 1, 2], [1, 1, 1], 0.5) == pytest.approx((3 + 2 * 0.5) / 1.5)


def test_regret_cvar_weighted():
    # budget = 0.5, consumed entirely inside the worst regret's 0.9 weight
    assert regret_cvar([10.0, 0.0], [0.9, 0.1], 0.5) == pytest.approx(10.0)


def test_regret_cvar_invalid_alpha():
    with pytest.raises(ValueError):
        regret_cvar([1.0], [1.0], 0.0)
    with pytest.raises(ValueError):
        regret_cvar([1.0], [1.0], 1.5)


def test_log_expected_value_shadow_disagreement(caplog):
    with caplog.at_level(logging.INFO):
        expected_value_choice_with_cvar(SCARF_SCENARIO, "earthquake")

    assert "EV shadow disagrees: would pick voltswitch" in caplog.text
    assert "a sampled world strongly disagrees with earthquake" in caplog.text
    assert "EV shadow q-value matrix" in caplog.text
    assert "EV shadow regret matrix" in caplog.text
    assert "EV shadow regret CVaR" in caplog.text


def test_log_expected_value_shadow_unanimous(caplog):
    with caplog.at_level(logging.INFO):
        expected_value_choice_with_cvar(UNANIMOUS_SCENARIO, "earthquake")

    assert "EV shadow disagrees" not in caplog.text
    assert "strongly disagrees" not in caplog.text
    assert "max regret 0.0 in battle None" in caplog.text


def test_log_expected_value_shadow_chosen_move_regret(caplog):
    # voltswitch's worst world is one of the three where earthquake is
    # marginally better, so regret is small and no alert fires
    regret_matrix = compute_regret_matrix(compute_q_matrix(SCARF_SCENARIO))
    assert 0.0 < max(regret_matrix["voltswitch"].values()) < REGRET_ALERT_THRESHOLD

    with caplog.at_level(logging.INFO):
        expected_value_choice_with_cvar(SCARF_SCENARIO, "voltswitch")

    assert "strongly disagrees" not in caplog.text
