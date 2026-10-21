import type { Overview } from "../api";


export default function Cards({ o }: { o: Overview | null }) {
    const cards = [
        { label: 'Total eval runs', value: o ? String(o.total_runs) : '-', danger: false },
        { label: 'Overll pass rate', value: o ? `${(o.overall_pass_rate * 100).toFixed(1)}%` : '-', danger: false },
        { label: 'Active tool schemas', value: o ? String(o.active_tools) : '-', danger: false },
        { label: 'Regerssions (7d)', value: o ? String(o.regressions_last_7d) : '-', danger: (o?.regressions_last_7d ?? 0) > 0 }
    ];
    return (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            {cards.map((c) => (
                <div key={c.label} className="rounded-lg border border-slate-700 bg-slate-800 p-4">
                    <div className="text-xs uppercase tracking-wide text-slate-400">{c.label}</div>
                    <div className={`mt-1 text-2xl font-semibold ${c.danger ? 'text-red-400' : 'text-emerald-400'}`}>{c.value}</div>
                </div>
            ))}
        </div>
    )
}