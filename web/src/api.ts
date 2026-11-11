/**
 * Thin fetch wrapper. Reads the token from localStorage and adds the
 * Authorization header automatically.
 */

const BASE = "/api";

function token(): string {
  return localStorage.getItem("eklavya_token") || "";
}

function headers(extra?: Record<string, string>): Record<string, string> {
  return {
    "Content-Type": "application/json",
    ...(token() ? { Authorization: `Bearer ${token()}` } : {}),
    ...extra,
  };
}

async function req<T>(
  method: string,
  path: string,
  body?: unknown
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: headers(),
    ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => res.statusText);
    throw new Error(detail || `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  // Auth
  login: (username: string, password: string) =>
    req<{ token: string; role: string; username: string }>("POST", "/login", { username, password }),
  logout: () => req<unknown>("POST", "/logout"),
  me: () => req<{ username: string; role: string }>("GET", "/me"),

  // Citizen
  schemes: () => req<unknown[]>("GET", "/schemes"),
  chat: (question: string, lang = "auto") =>
    req<ChatResponse>("POST", "/chat", { question, lang }),
  feedback: (id: number, vote: 1 | -1) =>
    req<unknown>("POST", `/chat/${id}/feedback`, { vote }),
  history: () => req<QueryRow[]>("GET", "/history"),
  sourcePage: (docId: number, pageNo: number, quote?: string) =>
    req<SourcePage>("GET", `/sources/${docId}/page/${pageNo}${quote ? `?quote=${encodeURIComponent(quote)}` : ""}`),

  // Admin – overview
  overview: () => req<OverviewData>("GET", "/admin/overview"),

  // Admin – sources
  sources: () => req<Source[]>("GET", "/admin/sources"),
  toggleSource: (id: number) => req<unknown>("POST", `/admin/sources/${id}/toggle`),

  // Admin – pipeline
  pipelineRun: (sourceId: number) =>
    req<{ run_id: number }>("POST", "/admin/pipeline/run", { source_id: sourceId }),
  pipelineRuns: () => req<PipelineRun[]>("GET", "/admin/pipeline/runs"),
  pipelineEvents: (runId: number) =>
    req<PipelineEvent[]>("GET", `/admin/pipeline/runs/${runId}/events`),

  // Admin – demo
  publishNext: () => req<{ published: string }>("POST", "/admin/demo/publish-next"),
  resetDemo: () => req<{ ok: boolean; seeded: number }>("POST", "/admin/demo/reset"),

  // Admin – documents
  documents: (params?: Record<string, string>) => {
    const qs = params ? "?" + new URLSearchParams(params).toString() : "";
    return req<Document[]>("GET", `/admin/documents${qs}`);
  },
  documentDetail: (id: number) => req<DocumentDetail>("GET", `/admin/documents/${id}`),

  // Admin – rules
  currentRules: () => req<Rule[]>("GET", "/admin/rules"),
  rulesHistory: (field?: string) => {
    const qs = field ? `?field=${encodeURIComponent(field)}` : "";
    return req<Record<string, Rule[]>>("GET", `/admin/rules/history${qs}`);
  },
  editRule: (id: number, patch: Record<string, string>) =>
    req<unknown>("PATCH", `/admin/rules/${id}`, patch),

  // Admin – review
  reviewList: () => req<ReviewItem[]>("GET", "/admin/review"),
  reviewApprove: (id: number) => req<unknown>("POST", `/admin/review/${id}/approve`),
  reviewReject: (id: number, note: string) =>
    req<unknown>("POST", `/admin/review/${id}/reject`, { note }),

  // Admin – notifications
  notifications: () => req<Notification[]>("GET", "/admin/notifications"),
  markRead: (ids?: number[]) =>
    req<unknown>("POST", "/admin/notifications/read", ids ? { ids } : {}),

  // Admin – questions
  questions: (tab = "all") => req<QueryRow[]>("GET", `/admin/questions?tab=${tab}`),

  // Admin – eval
  runEval: () => req<{ started: boolean }>("POST", "/admin/eval/run"),
  evalLatest: () => req<EvalResult>("GET", "/admin/eval/latest"),
  evalRuns: () => req<EvalRun[]>("GET", "/admin/eval/runs"),

  // Admin – audit
  audit: (params?: Record<string, string>) => {
    const qs = params ? "?" + new URLSearchParams(params).toString() : "";
    return req<AuditRow[]>("GET", `/admin/audit${qs}`);
  },

  // Admin – guardrails
  guardrails: () => req<GuardrailsStatus>("GET", "/admin/guardrails"),
  setKillSwitch: (active: boolean) =>
    req<unknown>("POST", "/admin/guardrails/kill-switch", { active }),

  // Admin – settings
  settings: () => req<Settings>("GET", "/admin/settings"),

  // LLM status (public, no auth needed)
  llmStatus: () => req<LlmStatus>("GET", "/system/llm"),
};

// ---------- Types ----------

export interface ChatResponse {
  id: number;
  answer: string;
  citations: Citation[];
  refused: boolean;
  confidence: number;
  latency_ms: number;
}

export interface Citation {
  chunk_id: number;
  doc_id: number;
  gr_number: string;
  gr_date: string;
  page: number;
  file: string;
  quote: string;
}

export interface QueryRow {
  id: number;
  ts: string;
  username: string;
  question_masked: string;
  answer: string;
  cited: Citation[];
  refused: number;
  confidence: number;
  latency_ms: number;
  feedback: number | null;
}

export interface SourcePage {
  doc_id: number;
  page_no: number;
  text: string;
  highlighted: string;
  gr_number: string;
  gr_date: string;
  title: string;
  file_path: string;
}

export interface OverviewData {
  docs_live: number;
  sources_healthy: string;
  review_pending: number;
  questions_today: number;
  refusal_rate_pct: number;
  avg_latency_ms: number;
  freshness_min: number | null;
  eval_score: string | null;
  recent_activity: { ts: string; who: string; action: string; msg: string }[];
}

export interface Source {
  id: number;
  name: string;
  url: string;
  department: string;
  kind: string;
  interval_min: number;
  enabled: number;
  last_check: string | null;
  last_status: string | null;
}

export interface PipelineRun {
  id: number;
  started_at: string;
  finished_at: string | null;
  mode: string;
  new_docs: number;
  status: string;
}

export interface PipelineEvent {
  id: number;
  run_id: number;
  ts: string;
  document_id: number | null;
  stage: string;
  status: string;
  message: string;
}

export interface Document {
  id: number;
  gr_number: string;
  gr_date: string;
  title: string;
  doc_type: string;
  status: string;
  ocr_used: number;
  confidence: number;
  detected_at: string;
  live_at: string | null;
}

export interface DocumentDetail extends Document {
  summary_mr: string;
  summary_en: string;
  file_path: string;
  rules: Rule[];
  refs: Ref[];
  pages: { page_no: number; chars: number }[];
}

export interface Rule {
  id: number;
  document_id: number;
  scheme: string;
  field: string;
  value: string;
  unit: string | null;
  condition_text: string;
  source_quote: string;
  page_no: number;
  effective_from: string | null;
  grounded: number;
  status: string;
  gr_number?: string;
  gr_date?: string;
}

export interface Ref {
  id: number;
  ref_gr_number: string;
  ref_gr_date: string;
  relation: string;
}

export interface ReviewItem {
  id: number;
  document_id: number;
  reason: string;
  status: string;
  run_id: number;
  gr_number: string;
  gr_date: string;
  title: string;
  doc_type: string;
  confidence: number;
  summary_en: string;
  file_path: string;
  rules: Rule[];
}

export interface Notification {
  id: number;
  ts: string;
  kind: string;
  message: string;
  read: number;
}

export interface EvalResult {
  run: EvalRun | null;
  results: EvalResultRow[];
}

export interface EvalRun {
  id: number;
  ts: string;
  total: number;
  passed: number;
  citation_ok: number;
}

export interface EvalResultRow {
  id: number;
  qid: string;
  question: string;
  answer: string;
  refused: number;
  citation_ok: number;
  answer_ok: number;
  note: string;
}

export interface AuditRow {
  id: number;
  ts: string;
  actor: string;
  action: string;
  detail: string;
}

export interface GuardrailsStatus {
  kill_switch: boolean;
  pii_masking: boolean;
  pii_masks_today: number;
  personal_status_refusals_today: number;
  cite_or_refuse: boolean;
  human_review_amendments: boolean;
  sources_allowlisted: boolean;
  offline_mode?: boolean;
  blocked_outbound_attempts?: number;
}

export interface Settings {
  llm_model: string;
  embed_model: string;
  total_queries: number;
  demo_users: string[];
}

export interface LlmStatus {
  backend: string;
  model: string;
  loaded: boolean;
  size: number;
  size_vram: number;
  expires_at: string;
  keep_alive: number;
  num_ctx: number;
  last_latency_ms: number;
  last_tokens_per_sec: number;
  last_load_duration_ms: number;
  queue_length: number;
  offline_mode: boolean;
  load_time_s: number;
}
