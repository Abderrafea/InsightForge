import { BrainCircuit, Plus, X } from "lucide-react";
import type { SessionDetails, SessionSummary } from "../types";
import { DatabaseStatus } from "./DatabaseStatus";
import { ProviderBadge } from "./ProviderBadge";
import { SessionList } from "./SessionList";

interface AppSidebarProps {
  sessions: SessionSummary[];
  activeId: string | null;
  activeSession: SessionDetails | null;
  open: boolean;
  onClose: () => void;
  onCreate: () => Promise<void>;
  onRename: (sessionId: string, title: string) => Promise<void>;
  onDelete: (sessionId: string) => Promise<void>;
}

export function AppSidebar({
  sessions,
  activeId,
  activeSession,
  open,
  onClose,
  onCreate,
  onRename,
  onDelete,
}: AppSidebarProps) {
  return (
    <>
      {open && (
        <button
          className="fixed inset-0 z-40 bg-ink/30 backdrop-blur-[1px] min-[861px]:hidden"
          onClick={onClose}
          aria-label="Close navigation"
        />
      )}
      <aside
        className={`fixed inset-y-0 left-0 z-50 flex w-[284px] flex-col border-r border-cloud bg-white transition-transform min-[861px]:sticky min-[861px]:top-0 min-[861px]:z-20 min-[861px]:h-dvh min-[861px]:translate-x-0 ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex h-20 items-center border-b border-cloud px-5">
          <div className="grid h-10 w-10 place-items-center rounded-md bg-ink text-white shadow-sm">
            <BrainCircuit size={22} />
          </div>
          <div className="ml-3 min-w-0">
            <p className="text-base font-bold text-ink">InsightForge</p>
            <p className="text-xs text-steel">Conversational analytics</p>
          </div>
          <button
            className="ml-auto rounded p-2 text-steel hover:bg-cloud min-[861px]:hidden"
            onClick={onClose}
            aria-label="Close sidebar"
          >
            <X size={19} />
          </button>
        </div>

        <div className="px-4 pt-4">
          <button
            onClick={() => void onCreate()}
            className="flex h-10 w-full items-center justify-center gap-2 rounded-md bg-ink px-4 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-steel"
          >
            <Plus size={17} /> New Session
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-3 py-5">
          <p className="mb-2 px-2 text-[11px] font-bold uppercase tracking-wide text-steel">
            Recent sessions
          </p>
          <SessionList
            sessions={sessions}
            activeId={activeId}
            onRename={onRename}
            onDelete={onDelete}
          />
        </div>

        <div className="space-y-4 border-t border-cloud bg-canvas px-4 py-4">
          <DatabaseStatus
            connected={Boolean(activeSession?.database_connection)}
            name={activeSession?.database_connection?.name}
            compact
          />
          <ProviderBadge
            provider={activeSession?.ai_provider ?? null}
            model={activeSession?.ai_model ?? null}
          />
        </div>
      </aside>
    </>
  );
}
