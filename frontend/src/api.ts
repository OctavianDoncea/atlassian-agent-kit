export interface EvalRun {
    id: string; tool_schema_id: string; created_at: string; tool_name: string; variant: string | null; prompt: string; expected_tool: string;
    expected_params: Record<string, unknown> | null; actual_tool: string | null; actual_params: Record<string, unknown> | null;
    passed: boolean; judge_provider: string | null; judge_reasoning: string | null; duration_ms: number | null;
}

export interface VariantStat {
    tool_name: string; variant: string | null; version: number; is_active: boolean; description: string; json_schema: Record<string, unknown> | null;
    trials: number; passes: number; pass_rate: number; avg_duration_ms: number;
}

export interface TimeseriesPoint {
    bucket: string; total: number; passed: number; pass_rate: number;
}

export interface Overview {
    total_runs: number; overall_pass_rate: number; active_tools: number; regressions_last_7d: number; last_run_at: string | null;
}

export interface Regression {
    id: string; created_at: string; tool_name: string; prompt: string; reasoning: string | null;
}

export interface UsageSummary {
    totals: { calls: number; input_tokens: number; output_tokens: number; cost_usd: number };
    by_purpose: { purpose: string; calls: number; tokens: number; cost_usd: number }[];
    by_model: { model: string; calls: number; tokens: number; cost_usd: number }[];
    daily: { bucket: string; tokens: number; cost_usd: number }[];
}

export interface PendingAction {
    id: string;
    session_id: string | null;
    tool_name: string;
    arguments: Record<string, unknown>;
    status: string;
    prompt: string | null;
    decided_by: string | null;
    decision_note: string | null;
    result: unknown; error: string | null;
    created_at: string;
    expires_at: string;
}

export interface RunState {
    running: boolean; started_at: string | null; finished_at: string | null; 
    last_summary: { total: number; passed: number; failed: number; regressions: string[] }
}

async function get<T>(path: string): Promise<T> {
    const res = await fetch(path);
    if (!res.ok) throw new Error(`${path} -> HTTP ${res.status}`);
    return (await res.json()) as T;
}

export const api = {
    overview: () => get<Overview>('/api/overview'),
    evals: (limit = 100) => get<EvalRun[]>(`/api/evals?limit=${limit}`),
    timeseries: (days = 14) => get<TimeseriesPoint[]>(`/api/evals/timeseries?days=${days}`),
    tools: () => get<VariantStat[]>(`/api/tools`),
    usageSummary: (days = 30) => get<UsageSummary>(`/api/usage/summary?days=${days}`),
    regressions: () => get<Regression[]>(`/api/regressions`),
    runState: () => get<RunState>('/api/evals/run/status'),
    triggerRun: async (dry = false): Promise<RunState> => {
        const res = await fetch(`/api/evals/run?dry_run=${dry}`, { method: 'POST' });
        if (!res.ok) throw new Error(`trigger -> HTTP ${res.status}`);
        return (await res.json()) as RunState;
    },
    hitlPending: () => get<{ pending: PendingAction[] }>('/api/hitl/pending'),
    hitlDecide: async (id: string, decision: 'approve' | 'reject', note?: string) => {
        const res = await fetch(`/api/hitl/${id}/decide`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ decision, note }),
        });
        if (!res.ok) throw new Error(`decide -> HTTP ${res.status}`);
        return res.json();
    },
    agentRun: async (prompt: string, authMode = 'basic') => {
        const res = await fetch('/api/agent/run', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ prompt, auth_mode: authMode }),
        });
        if (!res.ok) throw new Error(`agent run -> HTTP ${res.status}`);
        return res.json();
    },
};