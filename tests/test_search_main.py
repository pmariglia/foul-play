from types import SimpleNamespace

from fp.search.main import select_move_from_mcts_results


def _option(move_choice, visits, total_score=0.0):
    return SimpleNamespace(
        move_choice=move_choice, visits=visits, total_score=total_score
    )


def _result(options):
    return SimpleNamespace(
        side_one=options, total_visits=sum(o.visits for o in options)
    )


def test_picks_the_most_visited_move():
    result = _result([_option("tackle", 90, 50.0), _option("growl", 10, 2.0)])
    assert select_move_from_mcts_results([(result, 1.0, 0)]) == "tackle"


def test_skips_a_search_with_no_visits():
    empty = _result([_option("revivalblessing", 0), _option("splash", 0)])
    good = _result([_option("tackle", 90, 50.0), _option("growl", 10, 2.0)])
    assert select_move_from_mcts_results([(empty, 0.5, 0), (good, 0.5, 1)]) == "tackle"


def test_falls_back_to_first_option_when_no_search_has_visits():
    empty = _result([_option("switch a", 0), _option("switch b", 0)])
    assert select_move_from_mcts_results([(empty, 1.0, 0)]) == "switch a"
