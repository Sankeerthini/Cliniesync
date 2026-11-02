import { createContext, useContext } from "react";
import type { User } from "../api/client";

export type TabId = "home" | "ask" | "journey" | "followups" | "analytics" | "reviews" | "kpi" | "trust" | "data";

export interface Health {
  reference_date: string;
  llm: { available: boolean; model: string; mode: string };
  guardrails: { status: string; llm_self_check: boolean; input_flows: string[]; output_flows: string[] };
  vector_store: { backend: string; chunks?: number };
  voice: { server_stt: boolean };
  delivery: { mode: string; channels: Record<string, string>; email_from?: string | null };
  database: { patients: number };
}

export interface AppState {
  user: User;
  health: Health | null;
  nav: (tab: TabId, opts?: { patientId?: string; askText?: string }) => void;
  patientId: string | null;           // patient in focus (Journey -> Ask context)
  setPatientId: (p: string | null) => void;
  pendingAsk: string | null;
  clearPendingAsk: () => void;
  logout: () => void;
}

export const AppCtx = createContext<AppState>(null as unknown as AppState);
export const useApp = () => useContext(AppCtx);
