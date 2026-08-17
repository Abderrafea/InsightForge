import { CircleCheck, Database, Unplug } from "lucide-react";

interface DatabaseStatusProps {
  connected: boolean;
  name?: string;
  compact?: boolean;
}

export function DatabaseStatus({
  connected,
  name,
  compact = false,
}: DatabaseStatusProps) {
  const Icon = connected ? CircleCheck : Unplug;
  return (
    <div
      className={`flex items-center gap-2 ${compact ? "text-xs" : "text-sm"}`}
      aria-label={connected ? "Database connected" : "No database connected"}
    >
      <span
        className={`grid h-6 w-6 shrink-0 place-items-center rounded-full ${
          connected ? "bg-skywash text-ink" : "bg-cloud text-steel"
        }`}
      >
        {compact ? <Icon size={13} /> : <Database size={14} />}
      </span>
      <span className="min-w-0 truncate font-medium">
        {connected ? name ?? "PostgreSQL connected" : "No database connected"}
      </span>
    </div>
  );
}
