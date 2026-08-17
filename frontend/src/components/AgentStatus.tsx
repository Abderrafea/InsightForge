import { LoaderCircle } from "lucide-react";

interface AgentStatusProps {
  label: string;
}

export function AgentStatus({ label }: AgentStatusProps) {
  return (
    <div className="flex items-center gap-3 text-sm text-steel" role="status" aria-live="polite">
      <span className="grid h-8 w-8 place-items-center rounded-md bg-cloud">
        <LoaderCircle size={17} className="animate-spin" />
      </span>
      <span>{label}</span>
    </div>
  );
}
