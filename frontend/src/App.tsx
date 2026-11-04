import { useCallback, useEffect, useState } from "react";
import { api, hasToken, setToken, User } from "./api/client";
import { AppCtx, Health, TabId } from "./app/context";
import { Header, TABS } from "./app/Header";
import { LoginPage } from "./app/LoginPage";
import { AnalyticsPage } from "./features/analytics/AnalyticsPage";
import { AskPage } from "./features/ask/AskPage";
import { DataHubPage } from "./features/data/DataHubPage";
import { FollowupsPage } from "./features/followups/FollowupsPage";
import { HomePage } from "./features/home/HomePage";
import { JourneyPage } from "./features/journey/JourneyPage";
import { KpiPage } from "./features/kpi/KpiPage";
import { ReviewsPage } from "./features/reviews/ReviewsPage";
import { TrustPage } from "./features/trust/TrustPage";
import { Aurora, BackToTop, Loading } from "./ui/components";

const readTab = (): TabId => (window.location.hash.replace("#/", "") || "home") as TabId;

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [checking, setChecking] = useState(hasToken());
  const [tab, setTab] = useState<TabId>(readTab());
  const [health, setHealth] = useState<Health | null>(null);
  const [patientId, setPatientId] = useState<string | null>(null);
  const [pendingAsk, setPendingAsk] = useState<string | null>(null);

  useEffect(() => {
    if (hasToken()) api.get<User>("/api/auth/me").then(setUser).catch(() => setToken(null)).finally(() => setChecking(false));
    const onHash = () => setTab(readTab());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);
  useEffect(() => {
    if (!user) return;
    const load = () => api.get<Health>("/api/health").then(setHealth).catch(() => null);
    load(); const id = setInterval(load, 30000); return () => clearInterval(id);
  }, [user]);

  // browser tab title follows the page ("Follow-ups · ClinieSync")
  useEffect(() => {
    const label = user ? TABS.find(t => t.id === tab)?.label : null;
    document.title = label && tab !== "home" ? `${label} · ClinieSync` : "ClinieSync";
  }, [tab, user]);

  const nav = useCallback((t: TabId, opts?: { patientId?: string; askText?: string }) => {
    if (opts?.patientId) setPatientId(opts.patientId);
    if (opts?.askText) setPendingAsk(opts.askText);
    window.location.hash = `#/${t}`; setTab(t); window.scrollTo({ top: 0, behavior: "instant" });
  }, []);
  const logout = () => { setToken(null); setUser(null); setPatientId(null); window.location.hash = "#/home"; };

  if (checking) return <Loading label="Starting ClinieSync" />;
  if (!user) return <LoginPage onLogin={u => { setUser(u); nav("home"); }} />;

  const allowed = TABS.filter(t => t.roles.includes(user.role)).map(t => t.id);
  const current: TabId = allowed.includes(tab) ? tab : "home";
  const Page = { home: HomePage, ask: AskPage, journey: JourneyPage, followups: FollowupsPage, analytics: AnalyticsPage,
    reviews: ReviewsPage, kpi: KpiPage, trust: TrustPage, data: DataHubPage }[current];

  return (
    <AppCtx.Provider value={{ user, health, nav, patientId, setPatientId, pendingAsk, clearPendingAsk: () => setPendingAsk(null), logout }}>
      <Aurora />
      <Header tab={current} />
      <main key={current} className="page-enter"><Page /></main>
      <BackToTop />
    </AppCtx.Provider>
  );
}
