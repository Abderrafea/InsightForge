import { createContext, useContext, useEffect, useState, type FormEvent, type ReactNode } from "react";
import { apiRequest, setVisitorAI, type AIProvider } from "../api/client";

interface ProviderOption { id: AIProvider; label: string; models: string[] }

interface AccessInfo {
  public_visitors: boolean;
  models: string[];
  providers?: ProviderOption[];
  allow_custom_models?: boolean;
  session_hours: number;
}

const VisitorContext = createContext<null | { endSession: () => Promise<void>; changeKey: () => void }>(null);
export const useVisitorControls = () => useContext(VisitorContext);

export function AccessGate({ children }: { children: ReactNode }) {
  const [info, setInfo] = useState<AccessInfo | null>(null);
  const [ready, setReady] = useState(false);
  const [key, setKey] = useState("");
  const [model, setModel] = useState("");
  const [provider, setProvider] = useState<AIProvider>("groq");
  const [customModel, setCustomModel] = useState("");
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setError(null);
    try {
      const result = await apiRequest<AccessInfo>("/api/access");
      setInfo(result);
      const first = result.providers?.[0];
      setProvider(first?.id ?? "groq");
      setModel(first?.models[0] ?? result.models[0] ?? "");
      setReady(!result.public_visitors);
    } catch {
      setError("The application could not be reached. Please try again.");
    }
  };

  useEffect(() => {
    void load();
    const expired = () => {
      setVisitorAI(null);
      setReady(false);
      setError("Your private session expired. Enter your key to start a new session.");
    };
    window.addEventListener("visitor-session-expired", expired);
    return () => window.removeEventListener("visitor-session-expired", expired);
  }, []);

  const begin = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await apiRequest("/api/access", { method: "POST", body: "{}" });
      setVisitorAI({ key: key.trim(), provider, model: model === "__custom__" ? customModel.trim() : model });
      setKey("");
      setReady(true);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Your session could not be started.");
    } finally {
      setBusy(false);
    }
  };

  const changeKey = () => {
    setVisitorAI(null);
    setReady(false);
    setConsent(false);
  };

  const endSession = async () => {
    try {
      await apiRequest("/api/access", { method: "DELETE" });
      window.history.replaceState(null, "", "/");
      changeKey();
    } catch (caught) {
      changeKey();
      setError(caught instanceof Error ? caught.message : "Your session could not be erased. Please retry.");
    }
  };

  const providers = info?.providers ?? [{ id: "groq" as AIProvider, label: "Groq", models: info?.models ?? [] }];
  const selectedProvider = providers.find((item) => item.id === provider) ?? providers[0];
  const changeProvider = (value: AIProvider) => {
    setProvider(value);
    setKey("");
    setCustomModel("");
    setConsent(false);
    setModel(providers.find((item) => item.id === value)?.models[0] ?? "__custom__");
    setError(null);
  };

  if (ready) return <VisitorContext.Provider value={info?.public_visitors ? { endSession, changeKey } : null}>{children}</VisitorContext.Provider>;

  return (
    <main className="grid min-h-dvh place-items-center bg-canvas px-5 py-10 text-ink">
      <section className="w-full max-w-md rounded-lg border border-cloud bg-white p-7 shadow-sm">
        <h1 className="text-2xl font-bold">Welcome to InsightForge</h1>
        {!info ? (
          <>
            <p className="mt-3 text-sm text-steel">{error ?? "Checking access..."}</p>
            {error && <button onClick={() => void load()} className="mt-4 rounded bg-ink px-4 py-2 text-white">Try again</button>}
          </>
        ) : (
          <form onSubmit={(event) => void begin(event)} className="mt-5 space-y-4">
            <p className="text-sm leading-6 text-steel">Choose your AI provider and connect your PostgreSQL database. Your workspace is private to this browser session for up to {info.session_hours} hours.</p>
            <label className="block text-sm font-semibold">AI provider
              <select value={provider} onChange={(event) => changeProvider(event.target.value as AIProvider)} className="field-input mt-2 w-full">
                {providers.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
              </select>
            </label>
            <label className="block text-sm font-semibold">{selectedProvider.label} API key
              <input type="password" required minLength={20} maxLength={512} autoComplete="off" value={key} onChange={(event) => setKey(event.target.value)} className="field-input mt-2 w-full" />
            </label>
            <label className="block text-sm font-semibold">AI model
              <select value={model} onChange={(event) => setModel(event.target.value)} className="field-input mt-2 w-full">
                {selectedProvider.models.map((option) => <option key={option} value={option}>{option}</option>)}
                {info.allow_custom_models && <option value="__custom__">Other model — enter an ID</option>}
              </select>
            </label>
            {model === "__custom__" && <label className="block text-sm font-semibold">Custom model ID
              <input required maxLength={128} value={customModel} onChange={(event) => setCustomModel(event.target.value)} placeholder="Exact model ID from your provider" className="field-input mt-2 w-full" />
            </label>}
            <p className="text-xs leading-5 text-steel">These are suggestions, not your account's full model list. Choose a text model available to your API key that supports structured responses. Model access and billing depend on your provider account.</p>
            <p className="text-xs leading-5 text-steel">Your key stays in page memory and must be entered again after a reload. Database passwords are stored encrypted until you erase the session or it is cleaned up.</p>
            <label className="flex items-start gap-2 text-xs leading-5 text-steel">
              <input type="checkbox" required checked={consent} onChange={(event) => setConsent(event.target.checked)} className="mt-1" />
              <span>I authorize sending my prompts, database schema and bounded query samples to {selectedProvider.label}, using my key. I will connect a database I am authorized to use with a read-only account.</span>
            </label>
            {error && <p role="alert" className="text-sm text-red-800">{error}</p>}
            <button disabled={busy} className="w-full rounded-md bg-ink px-4 py-3 text-sm font-semibold text-white disabled:opacity-50">{busy ? "Starting session..." : "Start private session"}</button>
          </form>
        )}
      </section>
    </main>
  );
}
