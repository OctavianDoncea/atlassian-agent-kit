import { useEffect, useState } from 'react';
import { api, type PendingAction } from '../api';

export default function ApprovalQueue({ version, onChanged }: {version: number; onChanged: () => void }) {
    const [pending, setPending] = useState<PendingAction[]>([]);
    const [busy, setBusy] = useState<string | null>(null);

    useEffect(() => {
        api.hitlPending().then((r) => setPending(r.pending)).catch(() => setPending([]));
    }, [version]);

    const act = async (id: string, decision: 'approve' | 'reject') => {
        setBusy(id);
        try {
            await api.hitlDecide(id, decision);
            onChanged();
        } finally {
            setBusy(null);
        }
    };

    return (
        <section className="mt-6">
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
                Human approval queue {pending.length > 0 && <span className="ml-1 rounded bg-amber-500/20 px-2 py-0.5 text-amber-400">{pending.length} waiting</span>}
            </h2>
            {pending.length === 0 ? (
                <p className="text-sm text-slate-500">No destructive actions awaiting approval.</p>
            ) : (
                <div className="space-y-3">
                {pending.map((a) => (
                    <div key={a.id} className="rounded-lg border border-amber-700/60 bg-amber-900/10 p-4">
                        <div className="flex flex-wrap items-center justify-between gap-3">
                            <div>
                                <span className="font-mono text-sm text-amber-300">{a.tool_name}</span>
                                <span className="ml-2 text-xs text-slate-400">action {a.id.slice(0, 8)}, session {a.session_id ?? '—'}</span>
                            </div>
                            <div className="flex gap-2">
                                <button disabled={busy === a.id} onClick={() => act(a.id, 'approve')}
                                    className="rounded bg-emerald-600 px-3 py-1 text-sm hover:bg-emerald-500 disabled:opacity-50">Approve</button>
                                <button disabled={busy === a.id} onClick={() => act(a.id, 'reject')}
                                    className="rounded bg-red-700 px-3 py-1 text-sm hover:bg-red-600 disabled:opacity-50">Reject</button>
                            </div>
                        </div>
                        {a.prompt && <p className="mt-2 text-xs text-slate-400">User asked: "{a.prompt}"</p>}
                        <pre className="mt-2 max-h-40 overflow-auto rounded bg-slate-950 p-2 text-xs text-slate-300">
                            {JSON.stringify(a.arguments, null, 2)}
                        </pre>
                    </div>
                ))}
                </div>
            )}
        </section>
    );
}