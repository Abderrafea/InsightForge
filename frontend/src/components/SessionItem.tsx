import { Check, Ellipsis, MessageSquare, Pencil, Trash2, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import { formatRelativeTime } from "../lib/format";
import type { SessionSummary } from "../types";

interface SessionItemProps {
  session: SessionSummary;
  active: boolean;
  onRename: (sessionId: string, title: string) => Promise<void>;
  onDelete: (sessionId: string) => Promise<void>;
}

export function SessionItem({ session, active, onRename, onDelete }: SessionItemProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(session.title);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => setTitle(session.title), [session.title]);
  useEffect(() => {
    if (!menuOpen) return;
    const close = (event: MouseEvent) => {
      if (!menuRef.current?.contains(event.target as Node)) setMenuOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [menuOpen]);

  const saveTitle = async () => {
    const cleaned = title.trim();
    if (!cleaned || cleaned === session.title) {
      setTitle(session.title);
      setEditing(false);
      return;
    }
    await onRename(session.id, cleaned);
    setEditing(false);
  };

  return (
    <div
      className={`group relative rounded-md border px-3 py-2.5 transition-colors ${
        active
          ? "border-mist bg-cloud text-ink"
          : "border-transparent text-ink hover:border-cloud hover:bg-canvas"
      }`}
    >
      {editing ? (
        <div className="flex items-center gap-1.5">
          <input
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") void saveTitle();
              if (event.key === "Escape") setEditing(false);
            }}
            className="min-w-0 flex-1 rounded border border-mist bg-white px-2 py-1 text-sm"
            aria-label="Session title"
            autoFocus
          />
          <button onClick={() => void saveTitle()} aria-label="Save session title" className="p-1 text-steel">
            <Check size={15} />
          </button>
          <button onClick={() => setEditing(false)} aria-label="Cancel rename" className="p-1 text-steel">
            <X size={15} />
          </button>
        </div>
      ) : (
        <div className="flex items-start gap-2">
          <MessageSquare size={15} className="mt-0.5 shrink-0 text-steel" />
          <Link to={`/sessions/${session.id}`} className="min-w-0 flex-1 pr-6" aria-current={active ? "page" : undefined}>
            <span className="block truncate text-sm font-semibold">{session.title}</span>
            <span className="mt-0.5 block text-xs text-steel">{formatRelativeTime(session.updated_at)}</span>
          </Link>
          <button
            onClick={() => setMenuOpen((value) => !value)}
            className="absolute right-2 top-2 rounded p-1 text-steel hover:bg-skywash hover:text-ink"
            aria-label={`Actions for ${session.title}`}
            aria-expanded={menuOpen}
          >
            <Ellipsis size={16} />
          </button>
        </div>
      )}
      {menuOpen && !editing && (
        <div ref={menuRef} className="absolute right-2 top-9 z-30 w-32 rounded-md border border-mist bg-white p-1 shadow-lg">
          <button
            className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-sm hover:bg-cloud"
            onClick={() => {
              setMenuOpen(false);
              setEditing(true);
            }}
          >
            <Pencil size={14} /> Rename
          </button>
          <button
            className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-sm text-red-700 hover:bg-red-50"
            onClick={() => {
              setMenuOpen(false);
              if (window.confirm(`Delete “${session.title}”? This cannot be undone.`)) {
                void onDelete(session.id);
              }
            }}
          >
            <Trash2 size={14} /> Delete
          </button>
        </div>
      )}
    </div>
  );
}
