import { useEffect, useState } from "react";
import { api, Source } from "../../api";
import Spinner from "../../components/Spinner";
import { Globe, ToggleLeft, ToggleRight } from "lucide-react";

export default function SourcesPage() {
  const [sources, setSources] = useState<Source[]>([]);
  const [loading, setLoading] = useState(true);
  const [toggling, setToggling] = useState<number | null>(null);

  useEffect(() => { api.sources().then(setSources).catch(() => {}).finally(() => setLoading(false)); }, []);

  async function toggle(id: number) {
    setToggling(id);
    try {
      await api.toggleSource(id);
      setSources(s => s.map(src => src.id === id ? { ...src, enabled: src.enabled ? 0 : 1 } : src));
    } catch { }
    finally { setToggling(null); }
  }

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-4">
      <h2 className="text-xl font-bold text-navy">Sources</h2>
      <p className="text-sm text-gray-500">Only listed sources are fetched. No external URLs are added without admin action.</p>

      {loading ? <div className="flex justify-center h-24"><Spinner /></div> : (
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 text-gray-500 text-xs">
                <th className="text-left px-4 py-3 font-medium">Name</th>
                <th className="text-left px-4 py-3 font-medium">Kind</th>
                <th className="text-left px-4 py-3 font-medium">Last check</th>
                <th className="text-left px-4 py-3 font-medium">Status</th>
                <th className="text-left px-4 py-3 font-medium">Enabled</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {sources.map(s => (
                <tr key={s.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <p className="font-medium text-ink text-sm">{s.name}</p>
                    <a href={s.url} target="_blank" rel="noopener noreferrer"
                      className="text-xs text-gray-400 hover:text-navy truncate max-w-xs block">{s.url}</a>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                      s.kind === "sample" ? "bg-blue-100 text-blue-700" : "bg-green-100 text-green-700"
                    }`}>{s.kind}</span>
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-500">
                    {s.last_check ? new Date(s.last_check).toLocaleString() : "Never"}
                  </td>
                  <td className="px-4 py-3">
                    {s.last_status ? (
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                        s.last_status === "ok" ? "bg-green-100 text-green-700" : "bg-amber-100 text-amber-700"
                      }`}>{s.last_status}</span>
                    ) : <span className="text-gray-400 text-xs">—</span>}
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => toggle(s.id)}
                      disabled={toggling === s.id}
                      className="text-navy hover:text-saffron transition disabled:opacity-50"
                      aria-label={s.enabled ? "Disable source" : "Enable source"}
                    >
                      {s.enabled
                        ? <ToggleRight size={24} className="text-green-500" />
                        : <ToggleLeft size={24} className="text-gray-300" />}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
