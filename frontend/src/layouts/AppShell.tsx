import { useEffect, useMemo, useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router";
import { sessionApi } from "../api/sessions";
import { AppSidebar } from "../components/AppSidebar";
import type { SessionDetails, SessionSummary } from "../types";

export interface AppOutletContext {
  sessions: SessionSummary[];
  activeSession: SessionDetails | null;
  setActiveSession: (session: SessionDetails | null) => void;
  refreshSessions: () => Promise<void>;
  createSession: () => Promise<void>;
  openSidebar: () => void;
}

export function AppShell() {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [activeSession, setActiveSession] = useState<SessionDetails | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const activeId = useMemo(
    () => location.pathname.match(/^\/sessions\/([^/]+)/)?.[1] ?? null,
    [location.pathname],
  );

  const refreshSessions = async () => {
    setSessions(await sessionApi.list());
  };

  useEffect(() => {
    void refreshSessions();
  }, []);

  const createSession = async () => {
    const session = await sessionApi.create("Untitled analysis");
    setSessions((current) => [session, ...current]);
    setSidebarOpen(false);
    navigate(`/sessions/${session.id}`);
  };

  const renameSession = async (sessionId: string, title: string) => {
    const updated = await sessionApi.rename(sessionId, title);
    setSessions((current) => current.map((item) => (item.id === sessionId ? updated : item)));
    setActiveSession((current) => current && current.id === sessionId ? { ...current, title } : current);
  };

  const deleteSession = async (sessionId: string) => {
    await sessionApi.delete(sessionId);
    const remaining = sessions.filter((item) => item.id !== sessionId);
    setSessions(remaining);
    if (activeId === sessionId) {
      setActiveSession(null);
      navigate(remaining[0] ? `/sessions/${remaining[0].id}` : "/");
    }
  };

  return (
    <div className="app-grid bg-canvas">
      <AppSidebar
        sessions={sessions}
        activeId={activeId}
        activeSession={activeSession}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        onCreate={createSession}
        onRename={renameSession}
        onDelete={deleteSession}
      />
      <main className="min-w-0">
        <Outlet
          context={{
            sessions,
            activeSession,
            setActiveSession,
            refreshSessions,
            createSession,
            openSidebar: () => setSidebarOpen(true),
          } satisfies AppOutletContext}
        />
      </main>
    </div>
  );
}
