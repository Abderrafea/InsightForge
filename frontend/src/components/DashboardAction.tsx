import { ArrowUpRight, LayoutDashboard } from "lucide-react";
import { Link } from "react-router";

interface DashboardActionProps {
  sessionId: string;
  version?: number;
}

export function DashboardAction({ sessionId, version }: DashboardActionProps) {
  return (
    <Link
      to={`/sessions/${sessionId}/dashboard`}
      className="mt-4 inline-flex h-9 items-center gap-2 rounded-md border border-mist bg-white px-3 text-sm font-semibold text-ink transition-colors hover:border-steel hover:bg-cloud"
    >
      <LayoutDashboard size={16} />
      Open Dashboard
      {version ? <span className="text-xs font-medium text-steel">v{version}</span> : null}
      <ArrowUpRight size={15} />
    </Link>
  );
}
