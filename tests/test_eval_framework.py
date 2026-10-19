import pytest
from agentkit.evals.judges import exact_match, subset_match, evaluate_case

def test_exact_pass():
    res = exact_match({'a': 1, 'b': 'two'}, {'a': 1, 'b': 'two'})
    assert res.passed is True

def test_exact_match_fail():
    res = exact_match({'a': 1}, {'a': 2})
    assert res.passed is False

def test_subset_match_pass():
    # Agent returned extra params (e.g. default values), which is fine
    res = subset_match({'a': 1}, {'a': 1, 'b': 2, 'c': 3})
    assert res.passed is True


def test_subset_match_fail():
    res = subset_match({'a': 1, 'b': 2}, {'a': 1})
    assert res.passed is False
    assert 'Missing' in res.reasoning


def test_evaluate_case_wrong_tool():
    case = {'expected_tool': 'search_issues', 'expected_params': {}, 'judge_mode': 'exact_match'}
    res = evaluate_case(case, 'create_issue', {})
    assert res.passed is False
    assert 'Wrong tool' in res.reasoning


def test_evaluate_case_dry_run_simulation():
    case = {
        'id': 'test', 'prompt': 'hi', 'expected_tool': 'list_spaces', 
        'expected_params': {'limit': 25}, 'judge_mode': 'exact_match'
    }
    res = evaluate_case(case, 'list_spaces', {'limit': 25})
    assert res.passed is True