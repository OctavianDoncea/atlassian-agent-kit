import type { VariantStat } from "../api";

export default function SchemaBrowser({ stats, tool }: { stats: VariantStat[]; tool: string }) {
    const rows = stats.filter((s) => s.tool_name === tool);
    return (
        <div className="space-y-3">
            {rows.map((s) => (
                <details key={`${s.tool_name}-${s.version}`} className="rounded-lg border border-slate-700 bg-slate-800/50 p-3">
                    <summary className="flex flex-wrap items-center gap-3 text-sm">
                        <span className="font-mono">{s.tool_name}</span>
                        <span className="text-slate-400">v{s.version} / {s.variant ?? 'unnamed'}</span>
                        <span className="text-slate-400">{s.trials} trials / {(s.pass_rate * 100).toFixed(0)}% pass</span>
                        {s.is_active && <span className="rounded bg-emerald-500/20 px-2 py-0.5 text-xs text-emerald-400">ACTIVE</span>}
                    </summary>
                    <p className="mt-2 whitespace-pre-wrap text-sm text-slate-300">{s.description}</p>
                    {s.is_active && s.json_schema && (
                        <pre className="mt-2 max-h-64 overflow-auto rounded bg-slate-950 p-3 text-xs text-slate-300">
                            {JSON.stringify(s.json_schema, null, 2)}
                        </pre>
                    )}
                </details>
            ))}
            {rows.length === 0 && (
                <p className="text-sm text-slate-500">
                    No schemas for {tool}. Run `python scripts/seed_tool_schemas.py` or a tuning run first.
                </p>
            )}
        </div>
    )
}