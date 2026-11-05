import { Area, AreaChart, Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { UsageSummary } from '../api';

const tooltipStyle = { background: '#0f172a', border: '1px solid #334155', borderRadius: 8 };

export default function UsagePanel({ summary }: { summary: UsageSummary | null }) {
  if (!summary) return null;
  const daily = summary.daily.map((point) => ({ ...point, cost: +point.cost_usd.toFixed(6) }));
  const purposes = summary.by_purpose.map((point) => ({ ...point, cost: +point.cost_usd.toFixed(6) }));

  return (
    <section className="mt-6 grid gap-6 lg:grid-cols-3">
      <div className="rounded-lg border border-slate-700 bg-slate-800/50 p-4 lg:col-span-3">
        <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-400">LLM spend, last 30 days</h2>
        <div className="text-3xl font-semibold text-emerald-400">${summary.totals.cost_usd.toFixed(4)}</div>
        <p className="mt-1 text-sm text-slate-400">
          {summary.totals.calls.toLocaleString()} calls · {summary.totals.input_tokens.toLocaleString()} in / {summary.totals.output_tokens.toLocaleString()} out
        </p>
      </div>
      <div className="rounded-lg border border-slate-700 bg-slate-800/50 p-4 lg:col-span-2">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">Daily cost (USD)</h2>
        <div className="h-64">
          <ResponsiveContainer>
            <AreaChart data={daily}>
              <CartesianGrid stroke="#334155" strokeDasharray="3 3" />
              <XAxis dataKey="bucket" stroke="#94a3b8" fontSize={10} />
              <YAxis stroke="#94a3b8" fontSize={10} />
              <Tooltip contentStyle={tooltipStyle} />
              <Area type="monotone" dataKey="cost" name="USD" stroke="#f59e0b" fill="#f59e0b33" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
      <div className="rounded-lg border border-slate-700 bg-slate-800/50 p-4">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">Cost by purpose</h2>
        <div className="h-64">
          <ResponsiveContainer>
            <BarChart data={purposes}>
              <CartesianGrid stroke="#334155" strokeDasharray="3 3" />
              <XAxis dataKey="purpose" stroke="#94a3b8" fontSize={10} />
              <YAxis stroke="#94a3b8" fontSize={10} />
              <Tooltip contentStyle={tooltipStyle} />
              <Bar dataKey="cost" name="USD" fill="#f59e0b" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </section>
  );
}