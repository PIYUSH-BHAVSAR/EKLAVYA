import { useEffect, useState } from "react";
import { X, FileText, ExternalLink } from "lucide-react";
import { api, SourcePage } from "../../api";
import { useAuth } from "../../AuthContext";
import { t } from "../../i18n";
import Spinner from "../../components/Spinner";

interface Props {
  docId: number;
  pageNo: number;
  quote: string;
  grNumber: string;
  grDate: string;
  onClose: () => void;
}

export function SourceDrawer({ docId, pageNo, quote, grNumber, grDate, onClose }: Props) {
  const { lang } = useAuth();
  const [page, setPage] = useState<SourcePage | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<"text" | "pdf">("text");

  useEffect(() => {
    setLoading(true);
    setError("");
    api.sourcePage(docId, pageNo, quote)
      .then(setPage)
      .catch(() => setError("Could not load source page."))
      .finally(() => setLoading(false));
  }, [docId, pageNo, quote]);

  // Turn the <<<...>>> markers into <mark> HTML
  function toHighlightedHtml(raw: string): string {
    return raw
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/&lt;&lt;&lt;/g, "<mark>")
      .replace(/&gt;&gt;&gt;/g, "</mark>")
      .replace(/\n/g, "<br/>");
  }

  const pdfUrl = page?.file_path
    ? `/files/${page.file_path.split(/[\\/]/).pop()}#page=${pageNo}`
    : null;

  return (
    <aside className="w-[480px] shrink-0 bg-white border-l border-gray-200 flex flex-col shadow-xl">
      {/* Header */}
      <div className="flex items-start justify-between px-4 py-4 border-b border-gray-100">
        <div>
          <div className="flex items-center gap-2">
            <FileText size={16} className="text-navy" />
            <span className="font-semibold text-navy text-sm">
              {t(lang, "sourceGR")} {grNumber}
            </span>
            <span className="text-xs text-gray-400">{grDate}</span>
          </div>
          {page?.title && (
            <p className="text-xs text-gray-500 mt-0.5 ml-6 line-clamp-1">{page.title}</p>
          )}
        </div>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-700 transition" aria-label="Close">
          <X size={18} />
        </button>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-gray-100 shrink-0">
        <button
          onClick={() => setTab("text")}
          className={`px-4 py-2.5 text-sm font-medium transition border-b-2 ${
            tab === "text" ? "border-navy text-navy" : "border-transparent text-gray-500 hover:text-gray-700"
          }`}
        >
          Extracted text
        </button>
        <button
          onClick={() => setTab("pdf")}
          className={`px-4 py-2.5 text-sm font-medium transition border-b-2 ${
            tab === "pdf" ? "border-navy text-navy" : "border-transparent text-gray-500 hover:text-gray-700"
          }`}
        >
          PDF
        </button>
        {pdfUrl && (
          <a
            href={pdfUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="ml-auto flex items-center gap-1 px-4 py-2.5 text-xs text-gray-400 hover:text-navy transition"
          >
            Open <ExternalLink size={12} />
          </a>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto min-h-0">
        {loading ? (
          <div className="flex items-center justify-center h-full">
            <Spinner />
          </div>
        ) : error ? (
          <div className="p-6 text-sm text-red-500">{error}</div>
        ) : tab === "text" ? (
          <div className="p-4">
            <div className="bg-gray-50 rounded-lg p-4 text-xs font-mono text-gray-700 leading-relaxed">
              {/* Page label */}
              <p className="text-gray-400 mb-2 text-xs">
                {t(lang, "page")} {pageNo}
              </p>
              {/* Highlighted text */}
              <div
                dangerouslySetInnerHTML={{ __html: toHighlightedHtml(page?.highlighted || "") }}
                className="whitespace-pre-wrap break-words"
              />
            </div>

            {/* Cited quote callout */}
            {quote && (
              <div className="mt-4 border-l-4 border-saffron pl-3 py-1">
                <p className="text-xs text-gray-400 mb-1">Cited excerpt</p>
                <p className="text-xs text-gray-700 italic leading-relaxed">{quote}</p>
              </div>
            )}
          </div>
        ) : (
          /* PDF tab */
          pdfUrl ? (
            <iframe
              src={pdfUrl}
              className="w-full h-full"
              title={`GR ${grNumber} page ${pageNo}`}
            />
          ) : (
            <div className="p-6 text-sm text-gray-400">PDF not available</div>
          )
        )}
      </div>

      {/* Footer */}
      <div className="shrink-0 border-t border-gray-100 px-4 py-3">
        <p className="text-xs text-gray-400">{t(lang, "disclaimer")}</p>
      </div>
    </aside>
  );
}
