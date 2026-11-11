import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Play, Upload, CheckCircle, Clock, XCircle, Loader2, ArrowRight } from "lucide-react";
import { api, PipelineEvent, PipelineRun, Source } from "../../api";
import Spinner from "../../components/Spinner";

const STAGES = ["fetch", "archive", "read", "extract", "verify", "review", "index", "live"];

type StageStatus = "idle" | "running" | "done" | "waiting" | "error";

interface StageState { status: StageStatus; message: string; elapsed?: number }

function stageIcon(s: StageStatus) {
  if (s === "done")    return <CheckCircle size={16} className="text-green-500" />;
  if (s === "running") return <Loader2 size={16} className="text-navy animate-spin" />;
  if (s === "waiting") return <Clock size={16} className="text-amber-500" />;
  if (s === "error")   return <XCircle size={16} className="text-red-500" />;
  return <div className="w-4 h-4 rounded-full border-2 border-gray-200" />;
}

export default function PipelinePage() {
  const nav = useNavigate();
  const [sources, setSources] = useState<Source[]>([]);
  const [selectedSource, setSelectedSource] = useState<number>(1);
  const [running, setRunning] = useState(false);
  const [runId, setRunId] = useState<number | null>(null);
  const [stages, setStages] = useState<Record<string, StageState>>({});
  const [log, setLog] = useState<PipelineEvent[]>([]);
  const [runs, setRuns] = useState<PipelineRun[]>([]);
  const [freshness, setFreshness] = useState<string | null>(null);
  const [reviewPending, setReviewPending] = useState(false);
  const logRef = useRef<HTMLDivElement>(null);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    api.sources().then(setSources).catch(() => {});
    api.pipelineRuns().then(setRuns).catch(() => {});
  }, []);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight, behavior: "smooth" });
  }, [log]);

  function resetStages() {
    const init: Record<string, StageState> = {};
    STAGES.forEach(s => { init[s] = { status: "idle", message: "" }; });
    setStages(init);
  }

  async function handleFetch() {
    setRunning(true);
    setLog([]);
    setFreshness(null);
    setReviewPending(false);
    resetStages();

    try {
      const res = await api.pipelineRun(selectedSource);
      const rid = res.run_id;
      setRunId(rid);

      // Open SSE stream
      const token = localStorage.getItem("eklavya_token") || "";
      const es = new EventSource(`/api/admin/pipeline/stream?run_id=${rid}&token=${token}`);
      esRef.current = es;

      es.onmessage = (e) => {
        const ev: PipelineEvent & { stage?: string; status?: string } = JSON.parse(e.data);

        if (ev.stage === "end") {
          es.close();
          setRunning(false);
          api.pipelineRuns().then(setRuns).catch(() => {});
          return;
        }

        setLog(l => [...l, ev as PipelineEvent]);

        const stage = ev.stage;
        const status = ev.status as StageStatus;
        const msg = (ev as any).message || "";

        setStages(prev => ({ ...prev, [stage]: { status, message: msg } }));

        if (stage === "review" && status === "waiting") {
          setReviewPending(true);
        }
        if (stage === "live" && status === "done") {
          setFreshness(msg);
        }
      };

      es.onerror = () => {
        es.close();
        setRunning(false);
      };
    } catch {
      setRunning(false);
    }
  }

  async function handlePublishNext() {
    try {
      const res = await api.publishNext();
      alert(`Published: ${res.published}`);
    } catch (e: any) {
      alert(e.message || "Nothing to publish");
    }
  }

  const src = sources.find(s => s.id === selectedSource);

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <h2 className="text-xl font-bold text-navy">Pipeline</h2>

      {/* Controls */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
        <div className="flex flex-wrap items-center gap-3">
          <select
            value={selectedSource}
            onChange={e => setSelectedSource(Number(e.target.value))}
            className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-navy/20"
          >
            {sources.map(s => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>

          <button
            onClick={handleFetch}
            disabled={running}
            className="flex items-center gap-2 bg-navy text-white rounded-lg px-4 py-2 text-sm font-semibold hover:bg-navy/90 disabled:opacity-50 transition"
          >
            {running ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
            Fetch now
          </button>

          <button
            onClick={handlePublishNext}
            disabled={running}
            className="flex items-center gap-2 bg-white border border-saffron text-saffron rounded-lg px-4 py-2 text-sm font-semibold hover:bg-saffron/5 disabled:opacity-50 transition"
          >
            <Upload size={16} />
            Publish next GR (sample)
          </button>

          {src && (
            <span className="ml-auto text-xs bg-gray-100 text-gray-500 rounded-full px-3 py-1">
              {src.kind === "sample" ? "Prepared sample source" : "Live source"}
            </span>
          )}
        </div>
      </div>

      {/* Stepper */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
        <h3 className="text-sm font-semibold text-navy mb-4">Pipeline stages</h3>
        <div className="flex items-center gap-1 flex-wrap">
          {STAGES.map((s, i) => {
            const st = stages[s] || { status: "idle", message: "" };
            return (
              <div key={s} className="flex items-center gap-1">
                <div className={`flex items-center gap-2 rounded-lg px-3 py-2 text-xs font-medium transition ${
                  st.status === "done"    ? "bg-green-50 text-green-700 border border-green-100" :
                  st.status === "running" ? "bg-blue-50 text-navy border border-blue-100" :
                  st.status === "waiting" ? "bg-amber-50 text-amber-700 border border-amber-200" :
                  st.status === "error"   ? "bg-red-50 text-red-600 border border-red-100" :
                  "bg-gray-50 text-gray-400 border border-gray-100"
                }`}>
                  {stageIcon(st.status)}
                  <span className="capitalize">{s}</span>
                </div>
                {i < STAGES.length - 1 && (
                  <ArrowRight size={12} className="text-gray-300 shrink-0" />
                )}
              </div>
            );
          })}
        </div>

        {/* Stage messages */}
        {Object.entries(stages).some(([, v]) => v.message) && (
          <div className="mt-3 space-y-1">
            {STAGES.filter(s => stages[s]?.message).map(s => (
              <p key={s} className="text-xs text-gray-500">
                <span className="font-medium capitalize">{s}:</span> {stages[s].message}
              </p>
            ))}
          </div>
        )}

        {/* Review waiting banner */}
        {reviewPending && (
          <div className="mt-4 bg-amber-50 border border-amber-200 rounded-lg px-4 py-3 flex items-center justify-between">
            <div className="flex items-center gap-2 text-amber-700 text-sm font-medium">
              <Clock size={16} />
              Waiting for human review — amendment detected
            </div>
            <button
              onClick={() => nav("/admin/review")}
              className="text-sm text-amber-700 underline hover:no-underline"
            >
              Open review
            </button>
          </div>
        )}

        {/* Done banner */}
        {freshness && (
          <div className="mt-4 bg-green-50 border border-green-200 rounded-lg px-4 py-3 flex items-center justify-between">
            <div className="flex items-center gap-2 text-green-700 text-sm font-medium">
              <CheckCircle size={16} />
              Answerable now · {freshness}
            </div>
            <button
              onClick={() => nav("/app/chat")}
              className="text-sm text-green-700 underline hover:no-underline"
            >
              Ask the same question →
            </button>
          </div>
        )}
      </div>

      {/* Log pane */}
      {log.length > 0 && (
        <div className="bg-gray-900 rounded-xl overflow-hidden">
          <div className="px-4 py-2 border-b border-gray-700">
            <span className="text-xs text-gray-400 font-mono">Pipeline log</span>
          </div>
          <div ref={logRef} className="p-4 space-y-1 max-h-56 overflow-y-auto">
            {log.map((ev, i) => (
              <p key={i} className="text-xs font-mono text-gray-300">
                <span className="text-gray-500">{ev.ts.slice(11, 19)}</span>
                {" "}
                <span className={`font-semibold ${
                  ev.status === "done"    ? "text-green-400" :
                  ev.status === "error"   ? "text-red-400" :
                  ev.status === "waiting" ? "text-amber-400" :
                  "text-blue-400"
                }`}>[{ev.stage}/{ev.status}]</span>
                {" "}{(ev as any).message}
              </p>
            ))}
          </div>
        </div>
      )}

      {/* Run history */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm">
        <div className="px-5 py-4 border-b border-gray-50">
          <h3 className="text-sm font-semibold text-navy">Run history</h3>
        </div>
        {runs.length === 0 ? (
          <p className="px-5 py-6 text-sm text-gray-400">No runs yet.</p>
        ) : (
          <table className="w-full text-xs">
            <thead>
              <tr className="bg-gray-50 text-gray-500">
                <th className="text-left px-4 py-2 font-medium">Started</th>
                <th className="text-left px-4 py-2 font-medium">Mode</th>
                <th className="text-left px-4 py-2 font-medium">New docs</th>
                <th className="text-left px-4 py-2 font-medium">Status</th>
                <th className="text-left px-4 py-2 font-medium">Duration</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {runs.map(r => {
                const dur = r.finished_at
                  ? Math.round((new Date(r.finished_at).getTime() - new Date(r.started_at).getTime()) / 1000)
                  : null;
                return (
                  <tr key={r.id} className="hover:bg-gray-50">
                    <td className="px-4 py-2 text-gray-600">{new Date(r.started_at).toLocaleString()}</td>
                    <td className="px-4 py-2">{r.mode}</td>
                    <td className="px-4 py-2">{r.new_docs}</td>
                    <td className="px-4 py-2">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                        r.status === "done" ? "bg-green-100 text-green-700" :
                        r.status === "awaiting_review" ? "bg-amber-100 text-amber-700" :
                        r.status === "running" ? "bg-blue-100 text-blue-700" :
                        "bg-gray-100 text-gray-600"
                      }`}>{r.status}</span>
                    </td>
                    <td className="px-4 py-2">{dur != null ? `${dur}s` : "—"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
