import { useEffect, useState } from "react";
import { api, AuditRow } from "../../api";
import Spinner from "../../components/Spinner";

export default function AuditPage() {
  const [rows, setRows] = useState<AuditRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterActor, setFilterActor] = useState("");
  const [filterAction, setFilterAction] = useState("");

  useEffect(() => { load(); }, [filterActor, filterAction]);

  async function load() {
    setLoading(true);
    const p: Record<string, string> = {};
    if (filterActor) p.actor = filterActor;
    if (filterAction) p.action = filterAction;
    api.audit(p).then(setRows).catch(() => {}).finally(() => setLoading(false));
  }

  const actors = [...new Set(rows.map(r => r.actor))];
  const actions = [...new Set(rows.map(r => r.action))];

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-4">
      <h2 className="text-xl font-bold text-navy">Audit Log</h2>

      <div className="flex gap-2">
        <select value={filterActor} onChange={e => setFilterActor(e.target.value)}
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none">
          <option value="">All actors</option>
          {actors.map(a => <option key={a} value={a}>{a}</option>)}
        </select>
        <select value={filterAction} onChange={e => setFilterAction(e.target.value)}
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none">
          <option value="">All actions</option>
          {actions.map(a => <option key={a} value={a}>{a}</option>)}
        </select>
      </div>

      {loading ? <div className="flex justify-center h-24"><Spinner /></div> :
       rows.length === 0 ? (
        <div className="bg-white rounded-xl border border-gray-100 p-8 text-center text-sm text-gray-400">No audit entries yet.</div>
       ) : (
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="bg-gray-50 text-gray-500">
                <th className="text-left px-4 py-2 font-medium">Time</th>
                <th className="text-left px-4 py-2 font-medium">Actor</th>
                <th className="text-left px-4 py-2 font-medium">Action</th>
                <th className="text-left px-4 py-2 font-medium">Detail</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {rows.map(r => (
                <tr key={r.id} className="hover:bg-gray-50">
                  <td className="px-4 py-2.5 text-gray-400 whitespace-nowrap">{new Date(r.ts).toLocaleString()}</td>
                  <td className="px-4 py-2.5 font-medium text-navy">{r.actor}</td>
                  <td className="px-4 py-2.5">
                    <span className="bg-gray-100 text-gray-600 px-2 py-0.5 rounded font-mono">{r.action}</span>
                  </td>
                  <td className="px-4 py-2.5 text-gray-600 max-w-sm truncate">{r.detail}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
