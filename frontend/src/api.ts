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
    regressions: () => get<Regression[]>(`/api/regressions`),
    runState: () => get<RunState>('/api/evals/run/status'),
    triggerRun: async (dry = false): Promise<RunState> => {
        const res = await fetch(`/api/evals/run?dry_run=${dry}`, { method: 'POST' });
        if (!res.ok) throw new Error(`trigger -> HTTP ${res.status}`);
        return (await res.json()) as RunState;
    }
};