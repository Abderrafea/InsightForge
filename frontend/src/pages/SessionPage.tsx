import { AlertCircle, Database, LayoutDashboard, Menu } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useOutletContext, useParams } from "react-router";
import { agentApi } from "../api/agent";
import { sessionApi } from "../api/sessions";
import { ChatView } from "../components/ChatView";
import { ConnectionDialog } from "../components/ConnectionDialog";
import { DatabaseStatus } from "../components/DatabaseStatus";
import { MessageComposer } from "../components/MessageComposer";
import type { AppOutletContext } from "../layouts/AppShell";
import type { Message, SessionDetails } from "../types";

const progressLabels = [
  "Understanding request...",
  "Inspecting schema...",
  "Planning dashboard changes...",
  "Validating analytical queries...",
  "Building dashboard...",
];

export function SessionPage() {
  const { sessionId = "" } = useParams();
  const { setActiveSession, refreshSessions, openSidebar } = useOutletContext<AppOutletContext>();
  const [session, setSession] = useState<SessionDetails | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(true);
  const [runningStatus, setRunningStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [connectionOpen, setConnectionOpen] = useState(false);
  const progressRef = useRef<number | null>(null);

  const loadSession = async () => {
    const details = await sessionApi.get(sessionId);
    setSession(details);
    setMessages(details.messages);
    setActiveSession(details);
    return details;
  };

  useEffect(() => {
    let active = true;
    setLoading(true);
    sessionApi
      .get(sessionId)
      .then((details) => {
        if (!active) return;
        setSession(details);
        setMessages(details.messages);
        setActiveSession(details);
      })
      .catch((caught) => {
        if (active) setError(caught instanceof Error ? caught.message : "Session could not be loaded.");
      })
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
      if (progressRef.current) window.clearInterval(progressRef.current);
    };
  }, [sessionId, setActiveSession]);

  const send = async (content: string) => {
    if (!session?.database_connection || runningStatus) {
      if (!session?.database_connection) setConnectionOpen(true);
      return;
    }
    setError(null);
    const optimistic: Message = {
      id: `pending-${Date.now()}`,
      session_id: sessionId,
      role: "user",
      content,
      created_at: new Date().toISOString(),
    };
    setMessages((current) => [...current, optimistic]);
    let progressIndex = 0;
    setRunningStatus(progressLabels[progressIndex]);
    progressRef.current = window.setInterval(() => {
      progressIndex = Math.min(progressIndex + 1, progressLabels.length - 1);
      setRunningStatus(progressLabels[progressIndex]);
    }, 1400);

    try {
      const response = await agentApi.send(sessionId, content);
      setMessages((current) => [...current, response.message]);
      await loadSession();
      await refreshSessions();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The agent could not complete this request.");
      await loadSession().catch(() => undefined);
    } finally {
      if (progressRef.current) window.clearInterval(progressRef.current);
      progressRef.current = null;
      setRunningStatus(null);
    }
  };

  const attachConnection = async (connectionId: string) => {
    const attached = await sessionApi.attachDatabase(sessionId, connectionId);
    setSession(attached);
    setMessages(attached.messages);
    setActiveSession(attached);
    await refreshSessions();
  };

  if (loading) {
    return (
      <div className="grid min-h-dvh place-items-center text-sm text-steel" role="status">
        Loading session...
      </div>
    );
  }

  if (!session) {
    return <div className="grid min-h-dvh place-items-center text-sm text-red-800">{error ?? "Session not found."}</div>;
  }

  const connected = Boolean(session.database_connection);

  return (
    <div className="flex h-dvh min-h-[620px] flex-col overflow-hidden bg-canvas">
      <header className="flex min-h-20 items-center gap-3 border-b border-cloud bg-white px-4 py-3 sm:px-7">
        <button onClick={openSidebar} className="rounded p-2 text-steel hover:bg-cloud min-[861px]:hidden" aria-label="Open sidebar">
          <Menu size={20} />
        </button>
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-base font-bold text-ink sm:text-lg">{session.title}</h1>
          <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-steel">
            <DatabaseStatus connected={connected} name={session.database_connection?.name} compact />
            {session.dashboard && (
              <span className="flex items-center gap-1.5 font-medium">
                <LayoutDashboard size={13} /> Dashboard v{session.dashboard.current_version}
              </span>
            )}
          </div>
        </div>
        {!connected && (
          <button onClick={() => setConnectionOpen(true)} className="flex h-9 shrink-0 items-center gap-2 rounded-md bg-ink px-3 text-sm font-semibold text-white hover:bg-steel">
            <Database size={15} /> <span className="hidden sm:inline">Connect database</span>
          </button>
        )}
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {!connected && messages.length === 0 ? (
          <div className="mx-auto flex min-h-full max-w-xl flex-col items-center justify-center px-6 py-12 text-center">
            <span className="grid h-12 w-12 place-items-center rounded-md bg-cloud text-ink"><Database size={22} /></span>
            <h2 className="mt-4 text-xl font-bold text-ink">Connect your data source</h2>
            <p className="mt-2 text-sm leading-6 text-steel">Connect a PostgreSQL database to start analyzing your data and building dashboards.</p>
            <button onClick={() => setConnectionOpen(true)} className="mt-5 h-10 rounded-md bg-ink px-4 text-sm font-semibold text-white hover:bg-steel">Connect database</button>
          </div>
        ) : (
          <ChatView
            messages={messages}
            sessionId={sessionId}
            lastDashboardMessageId={session.dashboard?.last_modified_by_message_id ?? null}
            dashboardVersion={session.dashboard?.current_version}
            runningStatus={runningStatus}
            onSuggestion={(prompt) => void send(prompt)}
          />
        )}
      </div>

      {error && (
        <div className="mx-auto flex w-full max-w-4xl items-center gap-2 px-4 pb-2 text-sm text-red-800 sm:px-7" role="alert">
          <AlertCircle size={16} className="shrink-0" /> {error}
        </div>
      )}
      <MessageComposer onSend={send} disabled={!connected || Boolean(runningStatus)} />

      {connectionOpen && (
        <ConnectionDialog onClose={() => setConnectionOpen(false)} onConnected={attachConnection} />
      )}
    </div>
  );
}
