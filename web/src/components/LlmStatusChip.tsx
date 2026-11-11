/**
 * LlmStatusChip
 *
 * Polls /api/system/llm every 5 seconds and shows one of three states:
 *   ● green  – "Gemma loaded in memory · X.X GB · always on"
 *   ● amber  – "Loading local model…"
 *   ● red    – "Local model not running. Start Ollama."
 *
 * variant="compact" → single-line chip (used in admin top bar)
 * variant="footer"  → small footer line (used in citizen view)
 */
import { useEffect, useState } from "react";
import { api, LlmStatus } from "../api";

interface Props {
  variant?: "compact" | "footer";
}

function fmtSize(bytes: number): string {
  if (!bytes) return "";
  return (bytes / 1e9).toFixed(1) + " GB";
}

export default function LlmStatusChip({ variant = "compact" }: Props) {
  const [status, setStatus] = useState<LlmStatus | null>(null);
  const [error,  setError]  = useState(false);

  useEffect(() => {
    let mounted = true;
    const poll = () => {
      api.llmStatus()
        .then(s  => { if (mounted) { setStatus(s); setError(false); } })
        .catch(() => { if (mounted) setError(true); });
    };
    poll();
    const t = setInterval(poll, 5000);
    return () => { mounted = false; clearInterval(t); };
  }, []);

  // ── Determine chip state ────────────────────────────────────────────────
  let state: "loaded" | "loading" | "offline" = "loading";
  if (error || (status && !status.loaded && status.last_latency_ms === 0)) {
    state = "offline";
  } else if (status?.loaded) {
    state = "loaded";
  }

  const dot: Record<typeof state, string> = {
    loaded:  "bg-green-500",
    loading: "bg-amber-400 animate-pulse",
    offline: "bg-red-500",
  };

  const label: Record<typeof state, string> = {
    loaded:  status
      ? [
          "Gemma loaded in memory",
          fmtSize(status.size_vram || status.size),
          status.expires_at === "always" ? "always on" : "",
        ].filter(Boolean).join(" · ")
      : "Gemma loaded",
    loading: "Loading local model…",
    offline: "Local model not running. Start Ollama.",
  };

  const textColor: Record<typeof state, string> = {
    loaded:  "text-green-700",
    loading: "text-amber-700",
    offline: "text-red-700",
  };

  const bgColor: Record<typeof state, string> = {
    loaded:  "bg-green-50 border-green-200",
    loading: "bg-amber-50 border-amber-200",
    offline: "bg-red-50 border-red-200",
  };

  if (variant === "footer") {
    return (
      <div className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-xs border ${bgColor[state]} ${textColor[state]}`}>
        <span className={`inline-block w-1.5 h-1.5 rounded-full shrink-0 ${dot[state]}`} />
        <span>{label[state]}</span>
        {state === "loaded" && status && status.last_tokens_per_sec > 0 && (
          <span className="opacity-60">· {status.last_tokens_per_sec} t/s</span>
        )}
        {status?.offline_mode && (
          <span className="opacity-50 ml-0.5">(offline)</span>
        )}
      </div>
    );
  }

  // compact — used in the admin sidebar top section
  return (
    <div className={`flex items-center gap-1.5 px-2 py-1 rounded-md text-xs border ${bgColor[state]} ${textColor[state]} max-w-full`}>
      <span className={`inline-block w-2 h-2 rounded-full shrink-0 ${dot[state]}`} />
      <span className="truncate leading-tight">{label[state]}</span>
    </div>
  );
}
