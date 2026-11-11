import { useEffect, useState } from "react";
import { api, OverviewData, LlmStatus } from "../../api";
import Spinner from "../../components/Spinner";
import LlmStatusChip from "../../components/LlmStatusChip";
import { FileText, Globe, ClipboardCheck, MessageSquare, Zap, Clock, BarChart2, AlertTriangle, Cpu } from "lucide-react";

function Tile({ icon: Icon, label, value, sub, color = "navy" }: {
  icon: React.ElementType; label: string; value: string | number; sub?: string; color?: string;
}) {
  return (
    <div className="bg-white rounded-xl border border-gray-100 p-5 shadow-sm flex items-start gap-4">
      <div className={`p-2 rounded-lg bg-${color === "saffron" ? "saffron" : "navy"}/10`}>
        <Icon size={20} className={color === "saffron" ? "text-saffron" : "text-navy"} />
      </div>
      <div>
        <p className="text-2xl font-bold text-ink">{value ?? "—"}</p>
        <p className="text-sm text-gray-500 mt-0.5">{label}</p>
        {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
      </div>
    </div>
  );
}

export default function OverviewPage() {
  const [data, setData] = useState<OverviewData | null>(null);
  const [err, setErr] = useState("");
  const [llm, setLlm] = useState<LlmStatus | null>(null);

  useEffect(() => {
    const load = () => api.overview().then(setData).catch(() => setErr("Failed to load overview"));
    load();
    const t = setInterval(load, 10000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    const pollLlm = () => api.llmStatus().then(setLlm).catch(() => {});
    pollLlm();
    const t = setInterval(pollLlm, 5000);
    return () => clearInterval(t);
  }, []);

  if (!data && !err) return <div className="flex items-center justify-center h-32"><Spinner /></div>;
  if (err) return <div className="p-8 text-red-500">{err}</div>;

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <h2 className="text-xl font-bold text-navy mb-6">Overview — शबरी महामंडळ</h2>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <Tile icon={FileText}      label="Documents live"           value={data!.docs_live} />
        <Tile icon={Globe}         label="Sources healthy"          value={data!.sources_healthy} />
        <Tile icon={ClipboardCheck} label="Review pending"         value={data!.review_pending}
              color={data!.review_pending > 0 ? "saffron" : "navy"} />
        <Tile icon={MessageSquare} label="Questions today"          value={data!.questions_today} />
        <Tile icon={AlertTriangle} label="Refusal rate today"       value={`${data!.refusal_rate_pct}%`} />
        <Tile icon={Clock}         label="Avg latency"              value={`${data!.avg_latency_ms} ms`} />
        <Tile icon={Zap}           label="Last detection→answerable"
              value={data!.freshness_min != null ? `${data!.freshness_min} min` : "—"} />
        <Tile icon={BarChart2}     label="Evaluation score"
              value={data!.eval_score ?? "—"} sub="Run eval to update" />
      </div>

      {/* Local AI model tile */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5 mb-6">
        <div className="flex items-center gap-2 mb-3">
          <Cpu size={16} className="text-navy" />
          <h3 className="font-semibold text-navy text-sm">Local AI model</h3>
          <span className="ml-auto text-xs text-gray-400">Offline · Ollama</span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
          <div>
            <p className="text-xs text-gray-400">Status</p>
            <LlmStatusChip variant="footer" />
          </div>
          <div>
            <p className="text-xs text-gray-400">Tokens / sec</p>
            <p className="font-semibold text-ink mt-1">
              {llm?.last_tokens_per_sec ? `${llm.last_tokens_per_sec} t/s` : "—"}
            </p>
          </div>
          <div>
            <p className="text-xs text-gray-400">Last latency</p>
            <p className="font-semibold text-ink mt-1">
              {llm?.last_latency_ms ? `${llm.last_latency_ms} ms` : "—"}
            </p>
          </div>
          <div>
            <p className="text-xs text-gray-400">Load time</p>
            <p className="font-semibold text-ink mt-1">
              {llm
                ? llm.last_load_duration_ms < 500
                  ? `${llm.last_load_duration_ms} ms (already in memory)`
                  : `${llm.last_load_duration_ms} ms`
                : "—"}
            </p>
          </div>
        </div>
      </div>

      {/* Recent activity */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm">
        <div className="px-5 py-4 border-b border-gray-50">
          <h3 className="font-semibold text-navy text-sm">Recent activity</h3>
        </div>
        {data!.recent_activity.length === 0 ? (
          <p className="px-5 py-6 text-sm text-gray-400">No activity yet.</p>
        ) : (
          <ul className="divide-y divide-gray-50">
            {data!.recent_activity.map((r, i) => (
              <li key={i} className="px-5 py-3 flex items-start gap-3 text-sm">
                <span className="text-xs text-gray-400 whitespace-nowrap mt-0.5 w-36 shrink-0">
                  {new Date(r.ts).toLocaleString()}
                </span>
                <span className="font-medium text-navy shrink-0 w-24">{r.action}</span>
                <span className="text-gray-600 truncate">{r.msg}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
