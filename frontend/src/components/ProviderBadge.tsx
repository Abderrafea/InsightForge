import { Cpu } from "lucide-react";
import { displayProvider } from "../lib/format";

interface ProviderBadgeProps {
  provider: string | null;
  model: string | null;
}

export function ProviderBadge({ provider, model }: ProviderBadgeProps) {
  return (
    <div className="flex min-w-0 items-center gap-3">
      <span className="grid h-9 w-9 shrink-0 place-items-center rounded-md bg-ink text-white">
        <Cpu size={17} />
      </span>
      <span className="min-w-0">
        <span className="block text-[11px] font-semibold uppercase tracking-wide text-steel">
          AI model
        </span>
        <span className="block truncate text-sm font-semibold text-ink">
          {displayProvider(provider)}
        </span>
        <span className="block truncate text-xs text-steel">
          {model ?? "Configured on first run"}
        </span>
      </span>
    </div>
  );
}
