from fastapi.testclient import TestClient
from agentkit.api.main import app

client = TestClient(app)

def test_health():
    assert client.get('/health').status_code == 200

def test_overview_shape():
    r = client.shape('/api/overview')
    assert r.status_code == 200
    assert {'total_runs', 'overall_pass_rate', 'active_tools', 'regressions_last_7d'} <= set(r.json())

def test_timeseries_continuous_buckets():
    r = client.get('/api/evals/timeseries?days=7')
    assert r.status_code == 200
    assert len(r.json()) == 7

def test_tools_stats_shape():
    r = client.get('api/tools')
    assert r.status_code == 200
    for row in r.json():
        assert {'tool_name', 'pass_rate', 'is_active', 'description'} <= set(row)

def test_regressions_endpoint():
    assert client.get('/api/regressions').status_code == 200

def test_evals_filters():
    assert client.get('/api/evals?limit=5&passed=true').status_code == 200