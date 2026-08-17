import { Database, LoaderCircle, X } from "lucide-react";
import { useState, type FormEvent } from "react";
import { databaseApi } from "../api/database";
import type { DatabaseConnectionInput } from "../types";

interface ConnectionDialogProps {
  onClose: () => void;
  onConnected: (connectionId: string) => Promise<void>;
}

const initialInput: DatabaseConnectionInput = {
  name: "",
  host: "",
  port: 5432,
  database_name: "",
  username: "",
  password: "",
  ssl_mode: "prefer",
};

export function ConnectionDialog({ onClose, onConnected }: ConnectionDialogProps) {
  const [input, setInput] = useState(initialInput);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const update = (field: keyof DatabaseConnectionInput, value: string | number) => {
    setInput((current) => ({ ...current, [field]: value }));
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const { name: _name, ...credentials } = input;
      await databaseApi.test(credentials);
      const connection = await databaseApi.create(input);
      await onConnected(connection.id);
      setInput(initialInput);
      onClose();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The database could not be connected.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[70] grid place-items-center bg-ink/45 p-4" role="presentation">
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="connection-title"
        className="max-h-[92dvh] w-full max-w-2xl overflow-y-auto rounded-md bg-white shadow-2xl"
      >
        <header className="flex items-start border-b border-cloud px-5 py-4 sm:px-6">
          <span className="mr-3 grid h-10 w-10 shrink-0 place-items-center rounded-md bg-cloud text-ink">
            <Database size={20} />
          </span>
          <div>
            <h2 id="connection-title" className="text-lg font-bold text-ink">Connect PostgreSQL</h2>
            <p className="mt-0.5 text-sm text-steel">Credentials are encrypted by the backend.</p>
          </div>
          <button onClick={onClose} className="ml-auto rounded p-2 text-steel hover:bg-cloud" aria-label="Close connection dialog">
            <X size={19} />
          </button>
        </header>

        <form onSubmit={(event) => void submit(event)} className="space-y-5 px-5 py-5 sm:px-6">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Connection name">
              <input required value={input.name} onChange={(event) => update("name", event.target.value)} placeholder="Production analytics" className="field-input" />
            </Field>
            <Field label="Database name">
              <input required value={input.database_name} onChange={(event) => update("database_name", event.target.value)} placeholder="analytics" className="field-input" />
            </Field>
            <Field label="Host">
              <input required value={input.host} onChange={(event) => update("host", event.target.value)} placeholder="db.example.com" className="field-input" autoComplete="off" />
            </Field>
            <Field label="Port">
              <input required type="number" min={1} max={65535} value={input.port} onChange={(event) => update("port", Number(event.target.value))} className="field-input" />
            </Field>
            <Field label="Username">
              <input required value={input.username} onChange={(event) => update("username", event.target.value)} className="field-input" autoComplete="off" />
            </Field>
            <Field label="Password">
              <input required type="password" value={input.password} onChange={(event) => update("password", event.target.value)} className="field-input" autoComplete="new-password" />
            </Field>
            <Field label="SSL mode">
              <select value={input.ssl_mode} onChange={(event) => update("ssl_mode", event.target.value)} className="field-input">
                <option value="prefer">Prefer</option>
                <option value="require">Require</option>
                <option value="verify-ca">Verify CA</option>
                <option value="verify-full">Verify full</option>
                <option value="disable">Disable</option>
              </select>
            </Field>
          </div>
          {error && <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800" role="alert">{error}</p>}
          <footer className="flex justify-end gap-2 border-t border-cloud pt-4">
            <button type="button" onClick={onClose} className="h-10 rounded-md border border-mist px-4 text-sm font-semibold text-ink hover:bg-cloud">Cancel</button>
            <button type="submit" disabled={submitting} className="flex h-10 items-center gap-2 rounded-md bg-ink px-4 text-sm font-semibold text-white hover:bg-steel disabled:opacity-50">
              {submitting && <LoaderCircle size={16} className="animate-spin" />}
              Test & connect
            </button>
          </footer>
        </form>
      </section>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="space-y-1.5 text-sm font-semibold text-ink">
      <span>{label}</span>
      {children}
    </label>
  );
}
