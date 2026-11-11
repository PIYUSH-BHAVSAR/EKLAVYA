import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, Settings } from "../../api";
import Spinner from "../../components/Spinner";
import { RotateCcw } from "lucide-react";

export default function SettingsPage() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [loading, setLoading] = useState(true);
  const [resetting, setResetting] = useState(false);
  const nav = useNavigate();

  useEffect(() => {
    api.settings().then(setSettings).catch(() => {}).finally(() => setLoading(false));
  }, []);

  async function handleReset() {
    if (!confirm(
      "This will delete all data and re-seed from pdfs_seed/.\n" +
      "The held PDF stays in pdfs_held/.\n\n" +
      "Continue?"
    )) return;
    setResetting(true);
    try {
      const res = await api.resetDemo();
      alert(`Reset complete. ${res.seeded} document(s) seeded.`);
      nav("/admin/overview");
    } catch (e: any) {
      alert("Reset failed: " + e.message);
    } finally {
      setResetting(false);
    }
  }

  return (
    <div className="p-6 max-w-2xl mx-auto space-y-6">
      <h2 className="text-xl font-bold text-navy">Settings</h2>

      {loading ? <div className="flex justify-center h-24"><Spinner /></div> : settings && (
        <>
          <div className="bg-white rounded-xl border border-gray-100 shadow-sm divide-y divide-gray-50">
            <div className="px-5 py-4">
              <h3 className="font-semibold text-navy text-sm mb-3">System info</h3>
              <div className="space-y-3">
                <Row label="LLM model" value={settings.llm_model} />
                <Row label="Embedding model" value={settings.embed_model} />
                <Row label="Total queries" value={String(settings.total_queries)} />
                <Row label="Demo accounts" value={settings.demo_users.join(", ")} />
              </div>
            </div>
          </div>

          {/* Reset demo */}
          <div className="bg-white rounded-xl border border-red-100 shadow-sm p-5">
            <h3 className="font-semibold text-red-700 text-sm mb-2 flex items-center gap-2">
              <RotateCcw size={15} />
              Reset demo
            </h3>
            <p className="text-xs text-gray-500 mb-4 leading-relaxed">
              Deletes the database, clears the archive and portal_published folders, re-seeds
              from <code>data/pdfs_seed/</code>, and rebuilds the index.
              The held PDF in <code>data/pdfs_held/</code> is not touched.
              Target time: under 30 seconds.
            </p>
            <button
              onClick={handleReset}
              disabled={resetting}
              className="flex items-center gap-2 bg-red-600 text-white rounded-lg px-4 py-2 text-sm font-semibold hover:bg-red-700 disabled:opacity-50 transition"
            >
              {resetting ? <Spinner size={16} /> : <RotateCcw size={15} />}
              {resetting ? "Resetting…" : "Reset demo"}
            </button>
          </div>
        </>
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-4">
      <p className="text-xs text-gray-400 font-medium shrink-0">{label}</p>
      <p className="text-xs text-gray-700 font-mono text-right">{value}</p>
    </div>
  );
}
