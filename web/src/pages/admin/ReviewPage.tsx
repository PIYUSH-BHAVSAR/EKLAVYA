import { useEffect, useState } from "react";
import { CheckCircle, XCircle, ChevronDown, ChevronUp, AlertCircle } from "lucide-react";
import { api, ReviewItem, Rule } from "../../api";
import Spinner from "../../components/Spinner";

export default function ReviewPage() {
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [rejectNote, setRejectNote] = useState<Record<number, string>>({});
  const [busy, setBusy] = useState<number | null>(null);
  const [done, setDone] = useState<number[]>([]);

  useEffect(() => { load(); }, []);

  async function load() {
    setLoading(true);
    api.reviewList().then(setItems).catch(() => {}).finally(() => setLoading(false));
  }

  async function approve(id: number) {
    setBusy(id);
    try {
      await api.reviewApprove(id);
      setDone(d => [...d, id]);
    } catch (e: any) { alert(e.message); }
    finally { setBusy(null); }
  }

  async function reject(id: number) {
    const note = rejectNote[id] || "";
    if (!note.trim()) { alert("Please enter a rejection note."); return; }
    setBusy(id);
    try {
      await api.reviewReject(id, note);
      setDone(d => [...d, id]);
    } catch (e: any) { alert(e.message); }
    finally { setBusy(null); }
  }

  const visible = items.filter(i => !done.includes(i.id));

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-4">
      <h2 className="text-xl font-bold text-navy">Review Queue</h2>
      <p className="text-sm text-gray-500">
        All amendments and low-confidence documents stop here for human approval before going live.
      </p>

      {loading ? <div className="flex justify-center h-24"><Spinner /></div> :
       visible.length === 0 ? (
        <div className="bg-white rounded-xl border border-gray-100 p-8 text-center text-sm text-gray-400">
          No items pending review. 🎉
        </div>
       ) : visible.map(item => (
        <ReviewCard
          key={item.id}
          item={item}
          expanded={expanded === item.id}
          onToggle={() => setExpanded(expanded === item.id ? null : item.id)}
          onApprove={() => approve(item.id)}
          onReject={() => reject(item.id)}
          busy={busy === item.id}
          rejectNote={rejectNote[item.id] || ""}
          setRejectNote={v => setRejectNote(n => ({ ...n, [item.id]: v }))}
        />
      ))}
    </div>
  );
}

function ReviewCard({ item, expanded, onToggle, onApprove, onReject, busy, rejectNote, setRejectNote }: {
  item: ReviewItem;
  expanded: boolean;
  onToggle: () => void;
  onApprove: () => void;
  onReject: () => void;
  busy: boolean;
  rejectNote: string;
  setRejectNote: (v: string) => void;
}) {
  const reasons = item.reason.split(";").map(r => r.trim()).filter(Boolean);

  return (
    <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
      {/* Header */}
      <div className="flex items-start justify-between px-5 py-4 cursor-pointer hover:bg-gray-50 transition" onClick={onToggle}>
        <div className="flex items-start gap-3">
          <AlertCircle size={18} className="text-amber-500 mt-0.5 shrink-0" />
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-semibold text-navy text-sm">GR {item.gr_number || "—"}</span>
              <span className="text-xs text-gray-400">{item.gr_date}</span>
              <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-saffron/10 text-saffron">{item.doc_type}</span>
              {item.confidence != null && (
                <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                  item.confidence >= 0.9 ? "bg-green-100 text-green-700" : "bg-red-100 text-red-600"
                }`}>{Math.round(item.confidence * 100)}% grounded</span>
              )}
            </div>
            <p className="text-xs text-gray-500 mt-1 line-clamp-1">{item.title || item.summary_en}</p>
            <div className="flex gap-2 mt-1.5 flex-wrap">
              {reasons.map((r, i) => (
                <span key={i} className="bg-amber-100 text-amber-700 px-2 py-0.5 rounded text-xs">{r}</span>
              ))}
            </div>
          </div>
        </div>
        {expanded ? <ChevronUp size={16} className="text-gray-400 shrink-0" /> : <ChevronDown size={16} className="text-gray-400 shrink-0" />}
      </div>

      {expanded && (
        <div className="border-t border-gray-100">
          <div className="grid grid-cols-2 gap-0">
            {/* Left: extracted rules */}
            <div className="border-r border-gray-100 p-4 overflow-y-auto max-h-80">
              <p className="text-xs font-semibold text-gray-400 mb-3">EXTRACTED RULES</p>
              {item.rules.length === 0 ? (
                <p className="text-xs text-gray-400">No rules extracted.</p>
              ) : item.rules.map(r => <ReviewRuleRow key={r.id} rule={r} />)}
            </div>

            {/* Right: PDF link + actions */}
            <div className="p-4 space-y-4">
              <div>
                <p className="text-xs font-semibold text-gray-400 mb-2">SOURCE DOCUMENT</p>
                {item.file_path ? (
                  <a
                    href={`/files/${item.file_path.split(/[\\/]/).pop()}`}
                    target="_blank" rel="noopener noreferrer"
                    className="text-xs text-navy underline hover:no-underline"
                  >
                    Open PDF ↗
                  </a>
                ) : <p className="text-xs text-gray-400">PDF not available</p>}
              </div>

              {item.summary_en && (
                <div>
                  <p className="text-xs font-semibold text-gray-400 mb-1">SUMMARY</p>
                  <p className="text-xs text-gray-600 leading-relaxed">{item.summary_en}</p>
                </div>
              )}

              {/* Approve */}
              <button
                onClick={onApprove}
                disabled={busy}
                className="w-full flex items-center justify-center gap-2 bg-green-600 text-white rounded-lg py-2 text-sm font-semibold hover:bg-green-700 disabled:opacity-50 transition"
              >
                <CheckCircle size={15} />
                Approve &amp; go live
              </button>

              {/* Reject */}
              <div className="space-y-1.5">
                <textarea
                  value={rejectNote}
                  onChange={e => setRejectNote(e.target.value)}
                  placeholder="Rejection reason (required)"
                  rows={2}
                  className="w-full text-xs border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-red-200 resize-none"
                />
                <button
                  onClick={onReject}
                  disabled={busy || !rejectNote.trim()}
                  className="w-full flex items-center justify-center gap-2 bg-white border border-red-300 text-red-600 rounded-lg py-2 text-sm font-semibold hover:bg-red-50 disabled:opacity-50 transition"
                >
                  <XCircle size={15} />
                  Reject
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function ReviewRuleRow({ rule }: { rule: Rule }) {
  return (
    <div className="mb-2 text-xs border border-gray-100 rounded-lg px-3 py-2 bg-gray-50">
      <div className="flex items-center gap-2 mb-1">
        <span className="font-semibold text-navy capitalize">{rule.field.replace(/_/g, " ")}</span>
        <span className="font-medium text-ink">{rule.value} {rule.unit || ""}</span>
        <span className={`ml-auto px-1.5 py-0.5 rounded text-xs ${
          rule.grounded ? "bg-green-100 text-green-700" : "bg-red-100 text-red-600"
        }`}>{rule.grounded ? "✓" : "✗"}</span>
      </div>
      {rule.source_quote && (
        <p className="text-gray-500 italic border-l-2 border-saffron pl-2 leading-relaxed">{rule.source_quote}</p>
      )}
    </div>
  );
}
