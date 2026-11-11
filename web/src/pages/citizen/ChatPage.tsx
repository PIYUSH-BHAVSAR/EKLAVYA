import { useState, useRef, useEffect, KeyboardEvent } from "react";
import { Send, Mic, Copy, ThumbsUp, ThumbsDown, ExternalLink, AlertCircle } from "lucide-react";
import { api, ChatResponse, Citation } from "../../api";
import { useAuth } from "../../AuthContext";
import { t } from "../../i18n";
import Spinner from "../../components/Spinner";

interface Message {
  id: string;
  role: "user" | "assistant";
  text: string;
  response?: ChatResponse;
  ts: Date;
}

const STARTER_CHIPS = [
  { en: "Who is eligible for loans from this corporation?",  mr: "या महामंडळाच्या कर्जासाठी कोण पात्र आहे?" },
  { en: "What is the maximum loan amount available?",         mr: "जास्तीत जास्त किती कर्ज मिळू शकते?" },
  { en: "What is the interest rate on loans?",                mr: "कर्जावरील व्याजदर किती आहे?" },
  { en: "What documents are required to apply?",              mr: "अर्जासाठी कोणते कागदपत्रे लागतात?" },
];

interface Props {
  openDrawer: (c: Citation) => void;
  prefillQuestion?: string;
}

export default function ChatPage({ openDrawer, prefillQuestion }: Props) {
  const { lang } = useAuth();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState(prefillQuestion ?? "");
  const [loading, setLoading] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  useEffect(() => {
    if (prefillQuestion && prefillQuestion.trim()) {
      send(prefillQuestion);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prefillQuestion]);

  async function send(question: string) {
    if (!question.trim() || loading) return;
    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: "user",
      text: question.trim(),
      ts: new Date(),
    };
    setMessages(m => [...m, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const res = await api.chat(question.trim(), lang);
      const assistantMsg: Message = {
        id: crypto.randomUUID(),
        role: "assistant",
        text: res.answer,
        response: res,
        ts: new Date(),
      };
      setMessages(m => [...m, assistantMsg]);
    } catch {
      setMessages(m => [...m, {
        id: crypto.randomUUID(),
        role: "assistant",
        text: t(lang, "error"),
        ts: new Date(),
      }]);
    } finally {
      setLoading(false);
    }
  }

  function handleKey(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send(input);
    }
  }

  async function handleCopy(msg: Message) {
    await navigator.clipboard.writeText(msg.text);
    setCopiedId(msg.id);
    setTimeout(() => setCopiedId(null), 2000);
  }

  function handleFeedback(msgId: string, qid: number, vote: 1 | -1) {
    api.feedback(qid, vote).catch(() => {});
  }

  // Latest GR date across citations
  function latestDate(cites: Citation[]): string {
    if (!cites.length) return "";
    return cites.map(c => c.gr_date).sort().reverse()[0];
  }

  return (
    <div className="flex flex-col h-full">
      {/* Saffron strip */}
      <div className="h-1 bg-saffron shrink-0" />

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-6 space-y-6">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full gap-6 pb-20">
            <div className="text-center">
              <h2 className="text-2xl font-bold text-navy">
                {lang === "mr" ? "नमस्कार 🙏" : "Hello 🙏"}
              </h2>
              <p className="text-gray-500 mt-2 max-w-sm">
                {lang === "mr"
                  ? "शबरी आदिवासी वित्त व विकास महामंडळाच्या योजनांबद्दल प्रश्न विचारा."
                  : "Ask about schemes of Shabari Adivasi Finance & Development Corporation."}
              </p>
              <p className="text-xs text-gray-400 mt-1">
                {lang === "mr"
                  ? "उत्तरे केवळ प्रकाशित शासन निर्णयांवरून दिली जातात."
                  : "Answers come only from published government orders."}
              </p>
            </div>
            <div className="flex flex-wrap gap-2 justify-center max-w-lg">
              {STARTER_CHIPS.map((c, i) => (
                <button
                  key={i}
                  onClick={() => send(lang === "mr" ? c.mr : c.en)}
                  className="bg-white border border-gray-200 rounded-full px-4 py-2 text-sm text-gray-600 hover:border-navy hover:text-navy transition"
                >
                  {lang === "mr" ? c.mr : c.en}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map(msg => (
          <div key={msg.id} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            {msg.role === "user" ? (
              <div className="max-w-xl bg-navy text-white rounded-2xl rounded-tr-sm px-4 py-3 text-sm shadow-sm">
                {msg.text}
              </div>
            ) : (
              <div className="max-w-2xl w-full">
                <AssistantBubble
                  msg={msg}
                  lang={lang}
                  onCopy={() => handleCopy(msg)}
                  copied={copiedId === msg.id}
                  onFeedback={v => msg.response && handleFeedback(msg.id, msg.response.id, v)}
                  onOpenSource={openDrawer}
                />
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="bg-white border border-gray-100 rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm flex items-center gap-2">
              <Spinner size={16} />
              <span className="text-sm text-gray-400">{t(lang, "thinking")}</span>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input bar */}
      <div className="shrink-0 border-t border-gray-100 bg-white px-4 py-3">
        <div className="max-w-2xl mx-auto flex gap-2 items-end">
          <textarea
            ref={inputRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKey}
            placeholder={t(lang, "sendMessage")}
            rows={1}
            className="flex-1 resize-none rounded-xl border border-gray-200 px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-navy/20 max-h-40 overflow-y-auto"
            style={{ lineHeight: "1.5" }}
          />
          <button
            title={t(lang, "voicePhase2")}
            disabled
            className="p-3 rounded-xl border border-gray-200 text-gray-300 cursor-not-allowed"
          >
            <Mic size={18} />
          </button>
          <button
            onClick={() => send(input)}
            disabled={!input.trim() || loading}
            className="p-3 rounded-xl bg-navy text-white hover:bg-navy/90 disabled:opacity-40 transition"
          >
            <Send size={18} />
          </button>
        </div>
        <p className="text-center text-xs text-gray-300 mt-2">
          {t(lang, "refusalNote")}
        </p>
      </div>
    </div>
  );
}

// ── Assistant message bubble ─────────────────────────────────────────────────

function AssistantBubble({
  msg, lang, onCopy, copied, onFeedback, onOpenSource,
}: {
  msg: Message;
  lang: "en" | "mr";
  onCopy: () => void;
  copied: boolean;
  onFeedback: (v: 1 | -1) => void;
  onOpenSource: (c: Citation) => void;
}) {
  const res = msg.response;
  const isRefusal = res?.refused;

  return (
    <div className={`rounded-2xl rounded-tl-sm shadow-sm border px-4 py-4 ${
      isRefusal ? "bg-gray-50 border-gray-200" : "bg-white border-gray-100"
    }`}>
      {/* Refusal icon */}
      {isRefusal && (
        <div className="flex items-center gap-2 text-amber-600 mb-2 text-xs font-medium">
          <AlertCircle size={14} />
          {lang === "mr" ? "वैयक्तिक माहिती उपलब्ध नाही" : "Personal or unavailable information"}
        </div>
      )}

      {/* Answer text */}
      <p className="text-sm text-ink leading-relaxed whitespace-pre-wrap">{msg.text}</p>

      {/* "As of" chip */}
      {res && !isRefusal && res.citations.length > 0 && (
        <div className="mt-2 flex items-center gap-1 text-xs text-gray-400">
          <span className="bg-gray-100 px-2 py-0.5 rounded-full">
            {t(lang, "asOf")} {res.citations[0].gr_date}
          </span>
          <span className="bg-gray-100 px-2 py-0.5 rounded-full text-navy font-medium">
            {Math.round((res.confidence || 0) * 100)}% confidence
          </span>
        </div>
      )}

      {/* Citation chips */}
      {res && !isRefusal && res.citations.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {res.citations.map((c, i) => (
            <button
              key={i}
              onClick={() => onOpenSource(c)}
              className="flex items-center gap-1 bg-navy/5 hover:bg-navy/10 border border-navy/10 text-navy rounded-lg px-3 py-1.5 text-xs font-medium transition"
            >
              <span>{t(lang, "sourceGR")} {c.gr_number}</span>
              <span className="text-navy/50">·</span>
              <span>{c.gr_date}</span>
              <span className="text-navy/50">·</span>
              <span>{t(lang, "page")} {c.page}</span>
              <ExternalLink size={11} className="ml-0.5 opacity-50" />
            </button>
          ))}
        </div>
      )}

      {/* Actions */}
      <div className="mt-3 flex items-center gap-1 border-t border-gray-50 pt-2">
        <button
          onClick={onCopy}
          className="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-600 px-2 py-1 rounded transition"
        >
          <Copy size={12} />
          {copied ? "Copied!" : t(lang, "copyAnswer")}
        </button>
        {res && !isRefusal && (
          <>
            <button
              onClick={() => onFeedback(1)}
              className="flex items-center gap-1 text-xs text-gray-400 hover:text-green-600 px-2 py-1 rounded transition"
            >
              <ThumbsUp size={12} /> {t(lang, "thumbsUp")}
            </button>
            <button
              onClick={() => onFeedback(-1)}
              className="flex items-center gap-1 text-xs text-gray-400 hover:text-red-500 px-2 py-1 rounded transition"
            >
              <ThumbsDown size={12} /> {t(lang, "thumbsDown")}
            </button>
          </>
        )}
      </div>
    </div>
  );
}
