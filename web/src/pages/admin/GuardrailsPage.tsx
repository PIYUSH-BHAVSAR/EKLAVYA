import { useEffect, useState } from "react";
import { api, GuardrailsStatus } from "../../api";
import Spinner from "../../components/Spinner";
import { ShieldCheck, AlertOctagon, WifiOff } from "lucide-react";

function StatusRow({ label, active, count, note }: { label: string; active: boolean; count?: number; note?: string }) {
  return (
    <div className="flex items-center justify-between py-3 border-b border-gray-50 last:border-0">
      <div>
        <p className="text-sm font-medium text-ink">{label}</p>
        {note && <p className="text-xs text-gray-400 mt-0.5">{note}</p>}
      </div>
      <div className="flex items-center gap-3">
        {count != null && (
          <span className="text-xs text-gray-400">{count} today</span>
        )}
        <span className={`px-2.5 py-1 rounded-full text-xs font-semibold ${
          active ? "bg-green-100 text-green-700" : "bg-red-100 text-red-600"
        }`}>{active ? "ON" : "OFF"}</span>
      </div>
    </div>
  );
}

export default function GuardrailsPage() {
  const [data, setData] = useState<GuardrailsStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [killing, setKilling] = useState(false);

  useEffect(() => {
    api.guardrails().then(setData).catch(() => {}).finally(() => setLoading(false));
  }, []);

  async function toggleKill() {
    if (!data) return;
    const next = !data.kill_switch;
    if (next && !confirm("This will disable the citizen chat endpoint. Continue?")) return;
    setKilling(true);
    try {
      await api.setKillSwitch(next);
      setData(d => d ? { ...d, kill_switch: next } : d);
    } catch { }
    finally { setKilling(false); }
  }

  if (loading) return <div className="flex justify-center h-24"><Spinner /></div>;

  return (
    <div className="p-6 max-w-3xl mx-auto space-y-6">
      <h2 className="text-xl font-bold text-navy">Guardrails</h2>
      <p className="text-sm text-gray-500">All guardrails are on by default and cannot be disabled in the demo except the kill switch.</p>

      {/* Offline mode banner */}
      {data?.offline_mode && (
        <div className="flex items-start gap-3 bg-blue-50 border border-blue-200 rounded-xl p-4">
          <WifiOff size={18} className="text-blue-600 mt-0.5 shrink-0" />
          <div>
            <p className="font-semibold text-blue-800 text-sm">Offline mode active</p>
            <p className="text-xs text-blue-600 mt-0.5">
              No external API calls are made. All AI processing runs on the local
              Ollama instance. Blocked outbound attempts:{" "}
              <strong>{data.blocked_outbound_attempts ?? 0}</strong> (should be 0).
            </p>
          </div>
        </div>
      )}

      <div className="bg-white rounded-xl border border-gray-100 shadow-sm divide-y divide-gray-50 overflow-hidden">
        <div className="px-5 py-4">
          <div className="flex items-center gap-2 mb-1">
            <ShieldCheck size={16} className="text-navy" />
            <h3 className="font-semibold text-navy text-sm">Active guardrails</h3>
          </div>
        </div>
        <div className="px-5">
          {data && (
            <>
              <StatusRow label="Allow-listed sources only"
                active={data.sources_allowlisted}
                note="Only sources in the sources table are fetched" />
              <StatusRow label="PII masking"
                active={data.pii_masking}
                count={data.pii_masks_today}
                note="Aadhaar, phone, and long numbers masked before logging" />
              <StatusRow label="Personal-status refusals"
                active={true}
                count={data.personal_status_refusals_today}
                note="Questions about individual payment/application status are refused" />
              <StatusRow label="Cite or refuse"
                active={data.cite_or_refuse}
                note="All answers must cite a source; otherwise the question is refused" />
              <StatusRow label="Human review for amendments"
                active={data.human_review_amendments}
                note="Any amendment GR stops at the review queue before going live" />
            </>
          )}
        </div>
      </div>

      {/* Kill switch */}
      <div className={`rounded-xl border p-5 shadow-sm ${data?.kill_switch ? "bg-red-50 border-red-200" : "bg-white border-gray-100"}`}>
        <div className="flex items-start justify-between">
          <div className="flex items-start gap-3">
            <AlertOctagon size={20} className={data?.kill_switch ? "text-red-600 mt-0.5" : "text-gray-400 mt-0.5"} />
            <div>
              <p className="font-semibold text-sm text-ink">Kill switch — disable citizen chat</p>
              <p className="text-xs text-gray-500 mt-0.5">
                When active, the /chat endpoint returns a maintenance message to all citizens.
                Use for emergency stops only.
              </p>
            </div>
          </div>
          <button
            onClick={toggleKill}
            disabled={killing}
            className={`ml-4 px-4 py-2 rounded-lg text-sm font-semibold transition disabled:opacity-50 shrink-0 ${
              data?.kill_switch
                ? "bg-red-600 text-white hover:bg-red-700"
                : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            }`}
          >
            {data?.kill_switch ? "Deactivate" : "Activate"}
          </button>
        </div>
        {data?.kill_switch && (
          <p className="mt-3 text-xs text-red-600 font-medium">
            ⚠ Kill switch is active — citizens cannot ask questions.
          </p>
        )}
      </div>
    </div>
  );
}
