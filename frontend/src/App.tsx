import { useCallback, useEffect, useMemo, useState } from 'react';
import { api } from './api';
import type { EvalRun, Overview, Regression, RunState, TimeseriesPoint, VariantStat } from './api';
import Cards from './components/Cards';
import { PassRateChart, VariantChart } from './components/Charts';
import RunsTable from './components/RunsTable';
import SchemaBrowser from './components/SchemaBrowser';

export default function App() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [series, setSeries] = useState<TimeseriesPoint[]>([]);
  const [stats, setStats] = useState<VariantStat[]>([]);
  const [runs, setRuns] = useState<EvalRun[]>([]);
  const [regs, setRegs] = useState<Regression[]>([]);
  const [runState, setRunState] = useState<RunState | null>(null);
  const [tool, setTool] = useState('search_issues');
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [o, s, t, r, g, rs] = await Promise.all([
        api.overview(), api.timeseries(14), api.tools(),
        api.evals(100), api.regressions(), api.runState(),
      ]);
      setOverview(o); setSeries(s); setStats(t); setRuns(r); setRegs(g); setRunState(rs);
      setError(null);
    } catch (e) {
      setError(String(e));
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 10_000);
    return () => clearInterval(id);
  }, [refresh]);

  const tools = useMemo(() => Array.from(new Set(stats.map((s) => s.tool_name))), [stats]);

  return (
    <div className="min-h-screen bg-slate-900 p-6 text-slate-100">
      <header className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">AgentKit Eval Observatory</h1>
          <p className="text-sm text-slate-400">Agentic integration evals, tuning variants & regression alerts</p>
        </div>
        <div className="flex items-center gap-3">
          {runState?.running && (
            <span className="animate-pulse rounded bg-amber-500/20 px-2 py-1 text-amber-400">eval run in progress...</span>
          )}
          <button
            className="rounded bg-emerald-600 px-3 py-1.5 text-sm font-medium hover:bg-emerald-500"
            onClick={() => api.triggerRun(false).then(refresh).catch((e) => setError(String(e)))}
          >
            Run evals
          </button>
          <button className="rounded bg-slate-700 px-3 py-1.5 text-sm hover:bg-slate-600" onClick={refresh}>
            Refresh
          </button>
        </div>
      </header>

      {error && (
        <div className="mb-4 rounded border border-red-700 bg-red-900/30 p-3 text-sm text-red-300">
          {error}. Is the backend up? (`make run`)
        </div>
      )}
      {regs.length > 0 && (
        <div className="mb-4 rounded border border-red-700 bg-red-900/30 p-3 text-sm text-red-300">
          {regs.length} regression(s) detected. Most recent: <b>{regs[0].tool_name}</b>  “{regs[0].prompt}”
        </div>
      )}

      <Cards o={overview} />

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <section className="rounded-lg border border-slate-700 bg-slate-800/50 p-4">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">Pass rate, last 14 days</h2>
          <PassRateChart data={series} />
        </section>
        <section className="rounded-lg border border-slate-700 bg-slate-800/50 p-4">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">Description variants, pass rate</h2>
            <select
              value={tool}
              onChange={(e) => setTool(e.target.value)}
              className="rounded border border-slate-600 bg-slate-800 px-2 py-1 text-sm"
            >
              {(tools.length ? tools : ['search_issues']).map((t) => (<option key={t}>{t}</option>))}
            </select>
          </div>
          <VariantChart stats={stats} tool={tool} />
        </section>
      </div>

      <section className="mt-6">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">Latest eval runs</h2>
        <RunsTable runs={runs} />
      </section>

      <section className="mt-6">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">Tool schema browser</h2>
        <SchemaBrowser stats={stats} tool={tool} />
      </section>
    </div>
  );
}