import type { EvalRun } from "../api";

export default function RunsTable({ runs }: { runs: EvalRun[] }) {
    return (
        <div className="overflow-x-auto rounded-lg border border-slate-700">
            <table className="w-full text-left text-sm">
                <thead className="bg-slate-800 text-xs uppercase text-slate-400">
                    <tr>
                        <th className="px-3 py-2">When</th>
                        <th className="px-3 py-2">Tool / variant</th>
                        <th className="px-3 py-2">Prompt & judgement</th>
                        <th className="px-3 py-2">Actual tool</th>
                        <th className="px-3 py-2">Status</th>
                        <th className="px-3 py-2">ms</th>
                    </tr>
                </thead>
                <tbody className="divide-y divide-slate-700 bg-slate-900">
                    {runs.map((r) => (
                        <tr key={r.id} className="align-top">
                            <td className="whitespace-nowrap px-3 py-2 text-slate-400">{new Date(r.created_at).toLocaleString()}</td>
                            <td className="px-3 py-2">
                                {r.tool_name}
                                <span className="text-slate-500"> / {r.variant ?? '-'}</span>
                            </td>
                            <td className="max-w-pd px-3 py-2">
                                <details>
                                    <summary className="cursor-pointer truncate">{r.prompt}</summary>
                                    <pre className="mt-2 max-h-48 overflow-auto rounded bg-slate-950 p-2 text-xs text-slate-300">
                                        {JSON.stringify({ expected: r.expected_params, actual: r.actual_params }, null, 2)}
                                    </pre>
                                    {r.judge_reasoning && <p className="mt-1 text-xs ">{r.judge_reasoning}</p>}
                                </details>
                            </td>
                            <td className="px-3 py-2 text-slate-300">{r.actual_tool ?? '-'}</td>
                            <td className="px-3 py-2">
                                {r.passed ? (
                                    <span className="rounded bg-emerald-500/20 px-2 py-0.5 text-emerald-400">PASS</span>
                                ) : (
                                    <span className="rounded bg-red-500/20 px-2 py-0.5 text-red-400">FAIL</span>
                                )}
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    )
}