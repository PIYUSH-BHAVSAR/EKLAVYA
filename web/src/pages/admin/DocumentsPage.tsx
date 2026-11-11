import { useEffect, useState } from "react";
import { api, Document, DocumentDetail, Rule } from "../../api";
import Spinner from "../../components/Spinner";
import { X, ChevronDown } from "lucide-react";

const STATUS_COLORS: Record<string, string> = {
  live: "bg-green-100 text-green-700",
  review: "bg-amber-100 text-amber-700",
  new: "bg-blue-100 text-blue-700",
  rejected: "bg-red-100 text-red-600",
  failed: "bg-red-100 text-red-600",
};

const TYPE_COLORS: Record<string, string> = {
  new: "bg-navy/10 text-navy",
  amendment: "bg-saffron/10 text-saffron",
  extension: "bg-purple-100 text-purple-700",
  clarification: "bg-gray-100 text-gray-600",
  other: "bg-gray-100 text-gray-500",
};

export default function DocumentsPage() {
  const [docs, setDocs] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [filterType, setFilterType] = useState("");
  const [detail, setDetail] = useState<DocumentDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  useEffect(() => {
    loadDocs();
  }, [search, filterStatus, filterType]);

  async function loadDocs() {
    setLoading(true);
    const p: Record<string, string> = {};
    if (search) p.search = search;
    if (filterStatus) p.status = filterStatus;
    if (filterType) p.doc_type = filterType;
    api.documents(p).then(setDocs).catch(() => {}).finally(() => setLoading(false));
  }

  async function openDetail(id: number) {
    setDetailLoading(true);
    api.documentDetail(id).then(setDetail).catch(() => {}).finally(() => setDetailLoading(false));
  }

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <h2 className="text-xl font-bold text-navy mb-4">Documents</h2>

      {/* Filters */}
      <div className="flex flex-wrap gap-2 mb-4">
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search GR number or title…"
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-navy/20 w-60"
        />
        <select
          value={filterStatus}
          onChange={e => setFilterStatus(e.target.value)}
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none"
        >
          <option value="">All statuses</option>
          {["live", "review", "new", "rejected", "failed"].map(s => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
        <select
          value={filterType}
          onChange={e => setFilterType(e.target.value)}
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none"
        >
          <option value="">All types</option>
          {["new", "amendment", "extension", "clarification", "other"].map(t => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-x-auto">
        {loading ? (
          <div className="flex items-center justify-center h-32"><Spinner /></div>
        ) : docs.length === 0 ? (
          <p className="px-6 py-8 text-sm text-gray-400 text-center">No documents found.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 text-gray-500 text-xs">
                <th className="text-left px-4 py-3 font-medium">GR Number</th>
                <th className="text-left px-4 py-3 font-medium">Date</th>
                <th className="text-left px-4 py-3 font-medium">Title</th>
                <th className="text-left px-4 py-3 font-medium">Type</th>
                <th className="text-left px-4 py-3 font-medium">Status</th>
                <th className="text-left px-4 py-3 font-medium">OCR</th>
                <th className="text-left px-4 py-3 font-medium">Confidence</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {docs.map(d => (
                <tr key={d.id} onClick={() => openDetail(d.id)}
                  className="hover:bg-gray-50 cursor-pointer transition">
                  <td className="px-4 py-3 font-mono text-xs text-navy font-medium">{d.gr_number || "—"}</td>
                  <td className="px-4 py-3 text-xs text-gray-600">{d.gr_date || "—"}</td>
                  <td className="px-4 py-3 text-xs text-gray-700 max-w-xs truncate">{d.title || "—"}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${TYPE_COLORS[d.doc_type] || "bg-gray-100 text-gray-500"}`}>
                      {d.doc_type}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_COLORS[d.status] || "bg-gray-100 text-gray-600"}`}>
                      {d.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-500">{d.ocr_used ? "Yes" : "No"}</td>
                  <td className="px-4 py-3 text-xs text-gray-500">
                    {d.confidence != null ? `${Math.round(d.confidence * 100)}%` : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Detail drawer */}
      {(detail || detailLoading) && (
        <div className="fixed inset-0 bg-black/30 z-40 flex justify-end" onClick={() => setDetail(null)}>
          <div className="w-[540px] bg-white h-full overflow-y-auto shadow-2xl" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
              <h3 className="font-bold text-navy">Document detail</h3>
              <button onClick={() => setDetail(null)}><X size={18} className="text-gray-400" /></button>
            </div>
            {detailLoading ? (
              <div className="flex items-center justify-center h-32"><Spinner /></div>
            ) : detail && (
              <div className="p-5 space-y-4 text-sm">
                <div className="grid grid-cols-2 gap-3">
                  <Field label="GR Number" value={detail.gr_number} />
                  <Field label="Date" value={detail.gr_date} />
                  <Field label="Type" value={detail.doc_type} />
                  <Field label="Status" value={detail.status} />
                  <Field label="Confidence" value={detail.confidence != null ? `${Math.round(detail.confidence*100)}%` : "—"} />
                  <Field label="OCR used" value={detail.ocr_used ? "Yes" : "No"} />
                </div>
                {detail.summary_en && (
                  <div>
                    <p className="text-xs text-gray-400 font-medium mb-1">Summary (English)</p>
                    <p className="text-xs text-gray-700 leading-relaxed bg-gray-50 p-3 rounded-lg">{detail.summary_en}</p>
                  </div>
                )}
                {detail.summary_mr && (
                  <div>
                    <p className="text-xs text-gray-400 font-medium mb-1">सारांश (मराठी)</p>
                    <p className="text-xs text-gray-700 leading-relaxed bg-gray-50 p-3 rounded-lg">{detail.summary_mr}</p>
                  </div>
                )}
                {detail.rules.length > 0 && (
                  <div>
                    <p className="text-xs text-gray-400 font-medium mb-2">Extracted rules ({detail.rules.length})</p>
                    <div className="space-y-2">
                      {detail.rules.map(r => <RuleCard key={r.id} rule={r} />)}
                    </div>
                  </div>
                )}
                {detail.refs.length > 0 && (
                  <div>
                    <p className="text-xs text-gray-400 font-medium mb-2">References</p>
                    {detail.refs.map(ref => (
                      <p key={ref.id} className="text-xs text-gray-600">
                        {ref.relation} GR {ref.ref_gr_number} ({ref.ref_gr_date})
                      </p>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function Field({ label, value }: { label: string; value?: string | number | null }) {
  return (
    <div>
      <p className="text-xs text-gray-400 font-medium">{label}</p>
      <p className="text-sm text-gray-700 font-medium mt-0.5">{value ?? "—"}</p>
    </div>
  );
}

function RuleCard({ rule }: { rule: Rule }) {
  return (
    <div className="bg-gray-50 rounded-lg px-3 py-2 text-xs space-y-1 border border-gray-100">
      <div className="flex items-center gap-2">
        <span className="font-semibold text-navy capitalize">{rule.field.replace(/_/g, " ")}</span>
        <span className="text-gray-700 font-medium">{rule.value} {rule.unit || ""}</span>
        <span className={`ml-auto px-1.5 py-0.5 rounded text-xs font-medium ${
          rule.grounded ? "bg-green-100 text-green-700" : "bg-red-100 text-red-600"
        }`}>{rule.grounded ? "Grounded ✓" : "Ungrounded ✗"}</span>
      </div>
      {rule.source_quote && (
        <p className="text-gray-500 italic border-l-2 border-saffron pl-2">{rule.source_quote}</p>
      )}
    </div>
  );
}
