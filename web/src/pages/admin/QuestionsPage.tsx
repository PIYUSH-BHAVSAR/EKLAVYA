import { useEffect, useState } from "react";
import { api, QueryRow, Citation } from "../../api";
import Spinner from "../../components/Spinner";
import { X } from "lucide-react";

const TABS = [
  { key: "all",            label: "All" },
  { key: "refused",        label: "Refused" },
  { key: "low_confidence", label: "Low confidence" },
  { key: "thumbs_down",    label: "Thumbs-down" },
];

export default function QuestionsPage() {
  const [tab, setTab] = useState("all");
  const [rows, setRows] = useState<QueryRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<QueryRow | null>(null);

  useEffect(() => {
    setLoading(true);
    api.questions(tab).then(setRows).catch(() => {}).finally(() => setLoading(false));
  }, [tab]);

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-4">
      <h2 className="text-xl font-bold text-navy">Questions</h2>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-gray-200">
        {TABS.map(t => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={`px-4 py-2 text-sm font-medium transition border-b-2 -mb-px ${
              tab === t.key ? "border-navy text-navy" : "border-transparent text-gray-500 hover:text-gray-700"
            }`}>
            {t.label}
          </button>
        ))}
      </div>

      {loading ? <div className="flex justify-center h-24"><Spinner /></div> :
       rows.length === 0 ? (
        <div className="bg-white rounded-xl border border-gray-100 p-8 text-center text-sm text-gray-400">No questions yet.</div>
       ) : (
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
          <table className="w-full text-xs">
            <thead>
              <tr className="bg-gray-50 text-gray-500">
                <th className="text-left px-4 py-2 font-medium">Time</th>
                <th className="text-left px-4 py-2 font-medium">Question</th>
                <th className="text-left px-4 py-2 font-medium">Confidence</th>
                <th className="text-left px-4 py-2 font-medium">Refused</th>
                <th className="text-left px-4 py-2 font-medium">Feedback</th>
                <th className="text-left px-4 py-2 font-medium">Latency</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {rows.map(r => (
                <tr key={r.id} onClick={() => setSelected(r)} className="hover:bg-gray-50 cursor-pointer">
                  <td className="px-4 py-2.5 text-gray-400 whitespace-nowrap">{new Date(r.ts).toLocaleString()}</td>
                  <td className="px-4 py-2.5 text-gray-700 max-w-xs truncate">{r.question_masked}</td>
                  <td className="px-4 py-2.5">
                    <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${
                      r.confidence >= 0.7 ? "bg-green-100 text-green-700" :
                      r.confidence >= 0.4 ? "bg-amber-100 text-amber-700" : "bg-red-100 text-red-600"
                    }`}>{Math.round(r.confidence * 100)}%</span>
                  </td>
                  <td className="px-4 py-2.5">{r.refused ? <span className="text-red-500">✗ Refused</span> : <span className="text-green-600">✓</span>}</td>
                  <td className="px-4 py-2.5">{r.feedback === 1 ? "👍" : r.feedback === -1 ? "👎" : "—"}</td>
                  <td className="px-4 py-2.5 text-gray-400">{r.latency_ms}ms</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Detail modal */}
      {selected && (
        <div className="fixed inset-0 bg-black/30 z-40 flex items-center justify-center p-4" onClick={() => setSelected(null)}>
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-xl max-h-[80vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100 sticky top-0 bg-white">
              <h3 className="font-bold text-navy">Question detail</h3>
              <button onClick={() => setSelected(null)}><X size={18} className="text-gray-400" /></button>
            </div>
            <div className="p-5 space-y-4 text-sm">
              <div>
                <p className="text-xs text-gray-400 font-medium mb-1">Question (masked)</p>
                <p className="bg-gray-50 rounded-lg px-3 py-2 text-gray-700">{selected.question_masked}</p>
              </div>
              <div>
                <p className="text-xs text-gray-400 font-medium mb-1">Answer</p>
                <p className="bg-gray-50 rounded-lg px-3 py-2 text-gray-700 text-xs leading-relaxed whitespace-pre-wrap">{selected.answer}</p>
              </div>
              {selected.cited?.length > 0 && (
                <div>
                  <p className="text-xs text-gray-400 font-medium mb-2">Citations</p>
                  {(selected.cited as Citation[]).map((c, i) => (
                    <div key={i} className="flex items-center gap-2 text-xs text-gray-600 mb-1">
                      <span className="font-medium text-navy">GR {c.gr_number}</span>
                      <span>·</span>
                      <span>{c.gr_date}</span>
                      <span>·</span>
                      <span>p.{c.page}</span>
                    </div>
                  ))}
                </div>
              )}
              <div className="flex gap-4 text-xs text-gray-500">
                <span>Confidence: {Math.round(selected.confidence * 100)}%</span>
                <span>Latency: {selected.latency_ms}ms</span>
                <span>Refused: {selected.refused ? "Yes" : "No"}</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
