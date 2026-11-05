// Thin typed client for the ClinieSync FastAPI backend.
export type Role = "doctor" | "coordinator" | "admin";
export interface User { username: string; display_name: string; role: Role }

export interface ChartSeries { key: string; label: string }
export interface ChartSpec {
  id: string; type: "bar" | "stacked_bar" | "line" | "hbar" | "stacked_hbar" | "funnel" | "stat";
  title: string; subtitle?: string; x: string; series: ChartSeries[]; data: Record<string, unknown>[];
  value_format?: "int" | "pct" | "num"; y_label?: string;
}
export interface TableSpec { columns: { key: string; label: string }[]; rows: Record<string, unknown>[] }
export interface Stat { label: string; value: number | null; unit?: string; delta?: number; delta_label?: string }
export interface Citation { id: string; kind: string; date: string | null; title: string; text: string; ref_type: string; ref_id: string }
export interface GuardLayer { layer?: string; check?: string; verdict: string; detail: string }
export interface Action { type: string; label: string; followup_ids?: string[] }

export interface QueryResponse {
  response_id: string; status: "pending_review" | "blocked" | "needs_clarification" | "info";
  intent: string; intent_label: string; route: string; answer: string; generated_by?: "template" | "llm";
  llm_available: boolean; llm_model: string | null; latency_ms: number; disclaimer: string; query: string;
  input_mode: string;
  patient?: { patient_id: string; name: string; preferred_language: string };
  table?: TableSpec | null; charts?: ChartSpec[]; stats?: Stat[]; sql?: string; citations?: Citation[];
  caveats?: string[]; definition?: string | null; actions?: Action[]; notes?: string[];
  measurements?: Record<string, { date: string; value: number; visit_type: string; ga_weeks: number | null }[]>;
  refusal?: { category: string; message: string; alternatives: string[] };
  candidates?: { patient_id: string; name: string }[];
  guard_trace: { input: GuardLayer[]; access: GuardLayer | null; output: GuardLayer[] };
}

export interface MetricResult {
  metric: string; title: string; sql: string; narrative: string; charts: ChartSpec[]; table: TableSpec | null;
  caveats: string[]; stats: Stat[]; definition: string | null;
}

const TOKEN_KEY = "cliniesync.token";
let token: string | null = null;
try { token = sessionStorage.getItem(TOKEN_KEY); } catch { token = null; }

export function setToken(t: string | null) {
  token = t;
  try { if (t) sessionStorage.setItem(TOKEN_KEY, t); else sessionStorage.removeItem(TOKEN_KEY); } catch { /* storage blocked */ }
}
export const hasToken = () => !!token;

export class ApiError extends Error {
  constructor(public status: number, message: string, public detail?: unknown) { super(message); }
}

async function request<T>(method: string, path: string, body?: unknown, isForm = false): Promise<T> {
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined && !isForm) headers["Content-Type"] = "application/json";
  const res = await fetch(path, { method, headers, body: isForm ? (body as FormData) : body !== undefined ? JSON.stringify(body) : undefined });
  if (!res.ok) {
    let detail: unknown = undefined;
    try { detail = (await res.json()).detail; } catch { /* not json */ }
    if (res.status === 401) setToken(null);
    const msg = typeof detail === "string" ? detail : (detail as { message?: string })?.message || `${res.status} ${res.statusText}`;
    throw new ApiError(res.status, msg, detail);
  }
  return res.json() as Promise<T>;
}

export const api = {
  get: <T>(p: string) => request<T>("GET", p),
  post: <T>(p: string, b?: unknown) => request<T>("POST", p, b ?? {}),
  upload: <T>(p: string, f: FormData) => request<T>("POST", p, f, true),
};

// Ask runs as a server-side job that the page polls with short requests, so a slow model answer (minutes on a
// CPU-only server) never hangs on one long connection. A poll lost to the network is simply retried.
type JobState = { status: "running"; elapsed_s: number } | { status: "done"; result: QueryResponse };

export async function runQuery(body: { text: string; patient_id?: string | null; input_mode: "text" | "voice" },
                               onWait?: (seconds: number) => void): Promise<QueryResponse> {
  const { job_id } = await api.post<{ job_id: string }>("/api/query/jobs", body);
  let misses = 0;
  for (let delay = 350; ; delay = Math.min(delay * 1.4, 1500)) {
    await new Promise(r => setTimeout(r, delay));
    try {
      const job = await api.get<JobState>(`/api/query/jobs/${job_id}`);
      misses = 0;
      if (job.status === "done") return job.result;
      onWait?.(job.elapsed_s);
    } catch (e) {
      if (e instanceof ApiError || ++misses > 30) throw e;   // the server said no - or the network has been gone ~45 s
    }
  }
}
