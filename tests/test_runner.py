import textwrap
from agentkit.evals.tuner import VariantResult, load_variants, select_winner

def _vr(name: str, passes: int, trials: int, avg: float = 100.0) -> VariantResult:
    r = VariantResult(name=name, description=name, duration_ms=[int(avg)] * trials)
    r.passes = passes
    r.trials = trials

    return r

def test_pass_rate_and_avg():
    r = _vr('x', 3, 4, avg=50.0)
    assert r.pass_rate == 0.75
    assert r.avg_ms == 50.0

def test_winner_beats_baseline():
    winner, reason = select_winner([_vr('baseline', 6, 10), _vr('detailed', 9, 10)])
    assert winner.name == 'detailed'
    assert 'beats baseline' in reason

def test_promotion_blocked_when_below_baseline():
    winner, reason = select_winner([_vr('baseline', 9, 10), _vr('minimal', 4, 10), _vr('contextual', 5, 10)])
    assert winner.name == 'baseline'
    assert 'promotion blocked' in reason

def test_tie_keeps_baseline_for_stability():
    winner, reason = select_winner([_vr('baseline', 7, 10, avg=120), _vr('contextual', 7, 10, avg=80)])
    assert winner.name == 'baseline'
    assert 'tie' in reason

def test_latency_tiebreak_between_candidates():
    winner, _ = select_winner([_vr('baseline', 5, 10), _vr('a', 8, 10, avg=200), _vr('b', 8, 10, avg=90)])
    assert winner.name == 'b'

def test_load_variants_from_tmp(tmp_path):
    p = tmp_path / 'variants.yaml'
    p.write_text(textwrap.dedent("""
        search_issues:
          - name: baseline
            description: "base"
          - name: minimal
            description: "min"
    """))
    data = load_variants(str(p))
    assert [v['name'] for v in data['search_issues']] == ['baseline', 'minimal']