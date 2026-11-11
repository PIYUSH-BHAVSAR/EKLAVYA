import { useEffect, useState } from "react";
import { api, EvalResult, EvalRun } from "../../api";
import Spinner from "../../components/Spinner";
import { Play, CheckCircle, XCircle, AlertCircle } from "lucide-react";

export default function EvaluationPage() {
  const [result, setResult] = useState<EvalResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);

  useEffect(() => { load(); }, []);

  async function load() {
    setLoading(true);
    api.evalLatest().then(setResult).catch(() => {}).finally(() => setLoading(false));
  }

  async function startEval() {
    setRunning(true);
    try {
      await api.runEval();
      // Poll for result
      let attempts = 0;
      const poll = setInterval(async () => {
        attempts++;
        const r = await api.evalLatest();
        if (r.run && r.results.length > 0) {
          setResult(r);
          clearInterval(poll);
          setRunning(false);
        }
        if (attempts > 120) { clearInterval(poll); setRunning(false); }
      }, 2000);
    } catch { setRunning(false); }
  }

  const run = result?.run;
  const results = result?.results || [];

  const pct = run && run.total ? Math.round(run.passed / run.total * 100) : 0;
  const citePct = run && run.total ? Math.round(run.citation_ok / run.total * 100) : 0;

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-navy">Evaluation</h2>
        <button
          onClick={startEval}
          disabled={running}
          className="flex items-center gap-2 bg-navy text-white rounded-lg px-4 py-2 text-sm font-semibold hover:bg-navy/90 disabled:opacity-50 transition"
        >
          {running ? <Spinner size={16} /> : <Play size={16} />}
          {running ? "Running…" : "Run evaluation"}
        </button>
      </div>

      {running && (
        <div className="bg-blue-50 border border-blue-100 rounded-xl px-4 py-3 text-sm text-blue-700 flex items-center gap-2">
          <Spinner size={16} />
          Running {20} questions against the live index. This may take 1–3 minutes…
        </div>
      )}

      {loading ? <div className="flex justify-center h-24"><Spinner /></div> :
       !run ? (
        <div className="bg-white rounded-xl border border-gray-100 p-8 text-center text-sm text-gray-400">
          No evaluation run yet. Click "Run evaluation" to start.
        </div>
       ) : (
        <>
          {/* Score tiles */}
          <div className="grid grid-cols-3 gap-4">
            <ScoreTile label="Answers correct" value={run.passed} total={run.total} pct={pct} color="green" />
            <ScoreTile label="Citations correct" value={run.citation_ok} total={run.total} pct={citePct} color="blue" />
            <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
              <p className="text-xs text-gray-400 font-medium mb-1">Run timestamp</p>
              <p className="text-sm font-medium text-ink">{new Date(run.ts).toLocaleString()}</p>
              <p className="text-xs text-gray-400 mt-2">Total questions: {run.total}</p>
            </div>
          </div>

          {/* Results table */}
          <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-50">
              <h3 className="font-semibold text-navy text-sm">Per-question results</h3>
            </div>
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-gray-50 text-gray-500">
                  <th className="text-left px-4 py-2 font-medium">ID</th>
                  <th className="text-left px-4 py-2 font-medium">Question</th>
                  <th className="text-left px-4 py-2 font-medium">Answer</th>
                  <th className="text-left px-4 py-2 font-medium">Citation</th>
                  <th className="text-left px-4 py-2 font-medium">Correct</th>
                  <th className="text-left px-4 py-2 font-medium">Refused</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {results.map(r => (
                  <tr key={r.id} className={r.answer_ok ? "" : "bg-red-50/30"}>
                    <td className="px-4 py-2 font-mono text-gray-400">{r.qid}</td>
                    <td className="px-4 py-2 text-gray-700 max-w-xs">{r.question}</td>
                    <td className="px-4 py-2 text-gray-600 max-w-xs truncate">{r.answer}</td>
                    <td className="px-4 py-2">{r.citation_ok ? <CheckCircle size={13} className="text-green-500" /> : <XCircle size={13} className="text-red-400" />}</td>
                    <td className="px-4 py-2">{r.answer_ok ? <CheckCircle size={13} className="text-green-500" /> : <XCircle size={13} className="text-red-400" />}</td>
                    <td className="px-4 py-2">{r.refused ? <AlertCircle size={13} className="text-amber-500" /> : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

function ScoreTile({ label, value, total, pct, color }: {
  label: string; value: number; total: number; pct: number; color: "green" | "blue";
}) {
  return (
    <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
      <p className="text-xs text-gray-400 font-medium mb-2">{label}</p>
      <p className={`text-3xl font-bold ${color === "green" ? "text-green-600" : "text-navy"}`}>
        {value}<span className="text-lg text-gray-300">/{total}</span>
      </p>
      <div className="mt-2 h-1.5 bg-gray-100 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full ${color === "green" ? "bg-green-500" : "bg-navy"}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <p className="text-xs text-gray-400 mt-1">{pct}%</p>
    </div>
  );
}
