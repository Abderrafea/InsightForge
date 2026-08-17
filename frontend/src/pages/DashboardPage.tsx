import { ArrowLeft, Menu, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useOutletContext, useParams } from "react-router";
import { dashboardApi } from "../api/dashboards";
import { sessionApi } from "../api/sessions";
import { DashboardWidget } from "../components/DashboardWidget";
import type { AppOutletContext } from "../layouts/AppShell";
import type { DashboardData } from "../types";

export function DashboardPage() {
  const { sessionId = "" } = useParams();
  const { setActiveSession, openSidebar } = useOutletContext<AppOutletContext>();
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [dashboard, session] = await Promise.all([
        dashboardApi.get(sessionId),
        sessionApi.get(sessionId),
      ]);
      setData(dashboard);
      setActiveSession(session);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Dashboard could not be loaded.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, [sessionId]);

  return (
    <div className="min-h-dvh bg-canvas">
      <header className="sticky top-0 z-20 flex min-h-20 items-center gap-3 border-b border-cloud bg-white/95 px-4 py-3 backdrop-blur sm:px-7">
        <button onClick={openSidebar} className="rounded p-2 text-steel hover:bg-cloud min-[861px]:hidden" aria-label="Open sidebar"><Menu size={20} /></button>
        <Link to={`/sessions/${sessionId}`} className="grid h-9 w-9 shrink-0 place-items-center rounded-md border border-cloud text-steel hover:bg-cloud" aria-label="Back to conversation"><ArrowLeft size={17} /></Link>
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-base font-bold text-ink sm:text-lg">{data?.dashboard.title ?? "Dashboard"}</h1>
          {data && <p className="text-xs text-steel">Version {data.dashboard.current_version} · {data.dashboard.config_json.widgets.length} widgets</p>}
        </div>
        <button onClick={() => void load()} disabled={loading} className="flex h-9 items-center gap-2 rounded-md border border-mist bg-white px-3 text-sm font-semibold text-ink hover:bg-cloud disabled:opacity-50">
          <RefreshCw size={15} className={loading ? "animate-spin" : ""} /> <span className="hidden sm:inline">Refresh data</span>
        </button>
      </header>

      <div className="px-4 py-5 sm:px-7 sm:py-7">
        {loading && !data && <div className="grid min-h-[60vh] place-items-center text-sm text-steel" role="status">Running safe dashboard queries...</div>}
        {error && <div className="mx-auto mt-16 max-w-lg rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800" role="alert">{error}</div>}
        {data && (
          <div className="dashboard-grid">
            {data.dashboard.config_json.widgets.map((widget) => {
              const layout = data.dashboard.config_json.layout.find((item) => item.widget_id === widget.id);
              if (!layout) return null;
              return <DashboardWidget key={widget.id} widget={widget} layout={layout} result={data.query_results[widget.query_id ?? ""]} />;
            })}
          </div>
        )}
      </div>
    </div>
  );
}
