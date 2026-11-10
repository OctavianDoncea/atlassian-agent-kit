import { useState } from 'react';
import { api } from '../api';

export default function AgentConsole({ onChanged }: { onChanged: () => void }) {
    const [prompt, setPrompt] = useState('Create a Bug in ENG with summary "HITL demo crash"');
    const [log, setLog] = useState<string[]>([]);
    const [running, setRunning] = useState(false);

    const run = async () => {
        setRunning(true);
        setLog(['Session started...']);

        try {
            await api.agentRun(prompt);
            const id = setInterval(async () => {
                try {
                    const r = await fetch('/api/hitl/pending');
                    if (!r.ok) onChanged();
                } catch { /* ignore */ }
            }, 2000);
            setTimeout(() => { clearInterval(id); setRunning(false); }, 60_000);
        } catch (e) {
            setLog((l) => [...l, `ERROR: ${e}`]);
            setRunning(false);
        }
    };

    return (
        <section className="mt-6 rounded-lg border border-slate-700 bg-slate-800/50 p-4">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">🤖 Agent console (HITL-gated)</h2>
          <div className="flex gap-2">
            <input value={prompt} onChange={(e) => setPrompt(e.target.value)}
              className="flex-1 rounded border border-slate-600 bg-slate-900 px-3 py-2 text-sm" />
            <button onClick={run} disabled={running}
              className="rounded bg-emerald-600 px-4 py-2 text-sm hover:bg-emerald-500 disabled:opacity-50">
              {running ? 'Running…' : 'Run agent'}
            </button>
          </div>
          <pre className="mt-3 max-h-40 overflow-auto rounded bg-slate-950 p-2 text-xs text-slate-300">{log.join('\n')}</pre>
        </section>
    );
}