import type { SessionSummary } from "../types";
import { SessionItem } from "./SessionItem";

interface SessionListProps {
  sessions: SessionSummary[];
  activeId: string | null;
  onRename: (sessionId: string, title: string) => Promise<void>;
  onDelete: (sessionId: string) => Promise<void>;
}

export function SessionList({ sessions, activeId, onRename, onDelete }: SessionListProps) {
  return (
    <div className="space-y-1" aria-label="Session history">
      {sessions.map((session) => (
        <SessionItem
          key={session.id}
          session={session}
          active={session.id === activeId}
          onRename={onRename}
          onDelete={onDelete}
        />
      ))}
      {sessions.length === 0 && (
        <p className="px-3 py-5 text-sm leading-6 text-steel">
          Your analysis sessions will appear here.
        </p>
      )}
    </div>
  );
}
