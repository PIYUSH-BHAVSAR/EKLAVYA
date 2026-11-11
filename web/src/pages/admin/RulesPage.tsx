import { useEffect, useState } from "react";
import { api, Rule } from "../../api";
import Spinner from "../../components/Spinner";
import { ChevronDown, ChevronRight, Clock } from "lucide-react";

export default function RulesPage() {
  const [current, setCurrent] = useState<Rule[]>([]);
  const [history, setHistory] = useState<Record<string, Rule[]>>({});
  const [expandedField, setExpandedField] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.currentRules(),
      api.rulesHistory(),
    ]).then(([cur, hist]) => {
      setCurrent(cur);
      setHistory(hist);
    }).catch(() => {}).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="flex items-center justify-center h-32"><Spinner /></div>;

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <h2 className="text-xl font-bold text-navy">Current Rules</h2>
      <p className="text-sm text-gray-500">
        One row per field — the most recently approved value. Click a row to see its amendment history.
      </p>

      {current.length === 0 ? (
        <div className="bg-white rounded-xl border border-gray-100 p-8 text-center text-sm text-gray-400">
          No approved rules yet. Seed some GRs first.
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 text-gray-500 text-xs">
                <th className="text-left px-4 py-3 font-medium">Field</th>
                <th className="text-left px-4 py-3 font-medium">Value</th>
                <th className="text-left px-4 py-3 font-medium">Unit</th>
                <th className="text-left px-4 py-3 font-medium">GR Number</th>
                <th className="text-left px-4 py-3 font-medium">GR Date</th>
                <th className="text-left px-4 py-3 font-medium">Page</th>
                <th className="text-left px-4 py-3 font-medium">History</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {current.map(r => {
                const fieldHistory = history[r.field] || [];
                const isExpanded = expandedField === r.field;
                return (
                  <>
                    <tr
                      key={r.id}
                      onClick={() => setExpandedField(isExpanded ? null : r.field)}
                      className="hover:bg-gray-50 cursor-pointer transition"
                    >
                      <td className="px-4 py-3 font-medium text-navy capitalize">
                        {r.field.replace(/_/g, " ")}
                      </td>
                      <td className="px-4 py-3 font-semibold text-ink">{r.value}</td>
                      <td className="px-4 py-3 text-gray-500">{r.unit || "—"}</td>
                      <td className="px-4 py-3 font-mono text-xs text-navy">{r.gr_number || "—"}</td>
                      <td className="px-4 py-3 text-xs text-gray-600">{r.gr_date || "—"}</td>
                      <td className="px-4 py-3 text-xs text-gray-500">{r.page_no}</td>
                      <td className="px-4 py-3">
                        {fieldHistory.length > 1 && (
                          <span className="flex items-center gap-1 text-xs text-saffron font-medium">
                            {isExpanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                            {fieldHistory.length} versions
                          </span>
                        )}
                      </td>
                    </tr>

                    {/* History rows */}
                    {isExpanded && fieldHistory.length > 1 && (
                      <tr key={`${r.id}-hist`}>
                        <td colSpan={7} className="px-4 py-0 bg-amber-50">
                          <div className="py-3 pl-4 border-l-2 border-saffron">
                            <p className="text-xs text-gray-400 font-semibold mb-2 flex items-center gap-1">
                              <Clock size={11} /> Amendment timeline — oldest to newest
                            </p>
                            <div className="space-y-2">
                              {fieldHistory.map((h, i) => (
                                <div key={h.id} className={`flex items-start gap-3 text-xs ${
                                  i === fieldHistory.length - 1 ? "font-semibold text-green-700" : "text-gray-500 line-through"
                                }`}>
                                  <span className="w-24 shrink-0">{h.gr_date}</span>
                                  <span className="font-mono w-36 shrink-0">{h.gr_number}</span>
                                  <span>{h.value} {h.unit || ""}</span>
                                  {i === fieldHistory.length - 1 && (
                                    <span className="ml-1 text-green-600 font-normal">(current)</span>
                                  )}
                                  {i < fieldHistory.length - 1 && (
                                    <span className="ml-1 text-gray-400 font-normal no-underline"
                                      style={{ textDecoration: "none" }}>
                                      → superseded
                                    </span>
                                  )}
                                </div>
                              ))}
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
