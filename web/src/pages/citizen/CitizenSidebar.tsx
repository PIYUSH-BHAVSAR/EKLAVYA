import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  MessageSquare, PlusCircle, BookOpen, LogOut,
  ChevronLeft, ChevronRight, Globe, HelpCircle,
} from "lucide-react";
import { useAuth } from "../../AuthContext";
import { api, QueryRow } from "../../api";
import { t } from "../../i18n";

const SCHEME_NAME = "शबरी आदिवासी वित्त व विकास महामंडळ";
const SCHEME_NAME_MR = "शबरी आदिवासी वित्त व विकास महामंडळ";

const STARTER = [
  { en: "Who is eligible for loans from this corporation?",    mr: "या महामंडळाच्या कर्जासाठी कोण पात्र आहे?" },
  { en: "What is the maximum loan amount available?",          mr: "जास्तीत जास्त किती कर्ज मिळू शकते?" },
  { en: "What is the interest rate on loans?",                 mr: "कर्जावरील व्याजदर किती आहे?" },
  { en: "What documents are required to apply?",               mr: "अर्जासाठी कोणते कागदपत्रे लागतात?" },
  { en: "What is the repayment period for loans?",             mr: "कर्जाची परतफेड किती वर्षांत करायची आहे?" },
  { en: "Which tribes or communities are covered?",            mr: "या योजनेत कोणत्या जमाती किंवा समुदायांचा समावेश आहे?" },
];

interface Props {
  open: boolean;
  onToggle: () => void;
  onStarterClick?: (q: string) => void;
}

export default function CitizenSidebar({ open, onToggle, onStarterClick }: Props) {
  const { lang, setLang, clearAuth, username } = useAuth();
  const nav = useNavigate();
  const [history, setHistory] = useState<QueryRow[]>([]);
  const [schemesOpen, setSchemesOpen] = useState(false);

  useEffect(() => {
    api.history().then(setHistory).catch(() => {});
  }, []);

  function handleLogout() {
    api.logout().catch(() => {});
    clearAuth();
    nav("/login");
  }

  if (!open) {
    return (
      <div className="w-12 bg-navy flex flex-col items-center py-4 gap-4 shrink-0">
        <button onClick={onToggle} className="text-white/60 hover:text-white transition" aria-label="Open sidebar">
          <ChevronRight size={20} />
        </button>
        <div className="flex-1" />
        <button onClick={handleLogout} className="text-white/60 hover:text-white transition" aria-label="Logout">
          <LogOut size={18} />
        </button>
      </div>
    );
  }

  const today = new Date().toDateString();
  const todayItems = history.filter(h => new Date(h.ts).toDateString() === today);
  const earlierItems = history.filter(h => new Date(h.ts).toDateString() !== today);

  return (
    <aside className="w-64 bg-navy flex flex-col shrink-0 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-4 border-b border-white/10">
        <div>
          <h1 className="text-white font-bold text-lg leading-none">EKLAVYA</h1>
          <p className="text-white/50 text-xs mt-0.5">
            {lang === "mr" ? "नागरिक" : "Citizen"}
            {username && <> · {username}</>}
          </p>
        </div>
        <button onClick={onToggle} className="text-white/60 hover:text-white transition" aria-label="Close sidebar">
          <ChevronLeft size={18} />
        </button>
      </div>

      {/* New chat */}
      <div className="px-3 pt-3">
        <button
          onClick={() => nav("/app/chat")}
          className="w-full flex items-center gap-2 bg-saffron text-white rounded-lg px-3 py-2 text-sm font-medium hover:bg-saffron/90 transition"
        >
          <PlusCircle size={16} />
          {t(lang, "newChat")}
        </button>
      </div>

      {/* Browse schemes */}
      <div className="px-3 pt-3">
        <button
          onClick={() => setSchemesOpen(o => !o)}
          className="w-full flex items-center gap-2 text-white/70 hover:text-white rounded-lg px-3 py-2 text-sm transition"
        >
          <BookOpen size={15} />
          {t(lang, "browseSchemes")}
          <ChevronRight size={14} className={`ml-auto transition ${schemesOpen ? "rotate-90" : ""}`} />
        </button>
        {schemesOpen && (
          <div className="ml-6 mt-1 bg-navy/80 rounded-lg border border-white/10 overflow-hidden">
            <p className="text-white/40 text-xs px-3 py-2 border-b border-white/10">
              {lang === "mr" ? SCHEME_NAME_MR : SCHEME_NAME}
            </p>
            {STARTER.map((q, i) => (
              <button
                key={i}
                onClick={() => onStarterClick?.(lang === "mr" ? q.mr : q.en)}
                className="w-full text-left text-white/70 hover:text-white hover:bg-white/5 px-3 py-2 text-xs transition"
              >
                {lang === "mr" ? q.mr : q.en}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Recent chats */}
      <div className="flex-1 overflow-y-auto px-3 pt-3 pb-2 min-h-0">
        {history.length > 0 && (
          <>
            {todayItems.length > 0 && (
              <>
                <p className="text-white/30 text-xs px-2 mb-1">{t(lang, "today")}</p>
                {todayItems.slice(0, 8).map(h => (
                  <div key={h.id} className="text-white/60 hover:text-white/90 px-2 py-1.5 rounded text-xs truncate cursor-default transition hover:bg-white/5">
                    {h.question_masked}
                  </div>
                ))}
              </>
            )}
            {earlierItems.length > 0 && (
              <>
                <p className="text-white/30 text-xs px-2 mt-3 mb-1">{t(lang, "earlier")}</p>
                {earlierItems.slice(0, 8).map(h => (
                  <div key={h.id} className="text-white/60 hover:text-white/90 px-2 py-1.5 rounded text-xs truncate cursor-default transition hover:bg-white/5">
                    {h.question_masked}
                  </div>
                ))}
              </>
            )}
          </>
        )}
      </div>

      {/* Footer */}
      <div className="border-t border-white/10 px-3 py-3 space-y-1">
        {/* Language toggle */}
        <button
          onClick={() => setLang(lang === "en" ? "mr" : "en")}
          className="w-full flex items-center gap-2 text-white/60 hover:text-white px-3 py-2 rounded text-sm transition"
        >
          <Globe size={15} />
          {lang === "en" ? "मराठी" : "English"}
        </button>
        <a
          href="https://tribal.maharashtra.gov.in"
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-2 text-white/60 hover:text-white px-3 py-2 rounded text-sm transition"
        >
          <HelpCircle size={15} />
          Official portal
        </a>
        <button
          onClick={handleLogout}
          className="w-full flex items-center gap-2 text-white/60 hover:text-white px-3 py-2 rounded text-sm transition"
        >
          <LogOut size={15} />
          {t(lang, "logout")}
        </button>
      </div>
    </aside>
  );
}
