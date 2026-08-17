import { useEffect } from "react";
import { BrainCircuit, Plus } from "lucide-react";
import { useNavigate, useOutletContext } from "react-router";
import type { AppOutletContext } from "../layouts/AppShell";

export function HomePage() {
  const { createSession, sessions } = useOutletContext<AppOutletContext>();
  const navigate = useNavigate();

  useEffect(() => {
    if (sessions[0]) navigate(`/sessions/${sessions[0].id}`, { replace: true });
  }, [navigate, sessions]);
  return (
    <div className="flex min-h-dvh items-center justify-center px-5 py-10">
      <section className="max-w-lg text-center">
        <span className="mx-auto grid h-14 w-14 place-items-center rounded-md bg-ink text-white shadow-sm">
          <BrainCircuit size={27} />
        </span>
        <h1 className="mt-5 text-2xl font-bold text-ink">InsightForge</h1>
        <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-steel">
          Start a session, connect a PostgreSQL database, and shape your dashboard through conversation.
        </p>
        <button onClick={() => void createSession()} className="mx-auto mt-6 flex h-10 items-center gap-2 rounded-md bg-ink px-4 text-sm font-semibold text-white hover:bg-steel">
          <Plus size={17} /> New Session
        </button>
      </section>
    </div>
  );
}
