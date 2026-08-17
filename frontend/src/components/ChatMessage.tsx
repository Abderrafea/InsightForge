import { BrainCircuit } from "lucide-react";
import type { Message } from "../types";
import { DashboardAction } from "./DashboardAction";

interface ChatMessageProps {
  message: Message;
  sessionId: string;
  showDashboardAction: boolean;
  dashboardVersion?: number;
}

export function ChatMessage({
  message,
  sessionId,
  showDashboardAction,
  dashboardVersion,
}: ChatMessageProps) {
  if (message.role === "user") {
    return (
      <article className="flex justify-end">
        <div className="max-w-[78%] rounded-md bg-ink px-4 py-3 text-sm leading-6 text-white shadow-sm sm:max-w-[68%]">
          <p className="whitespace-pre-wrap break-words">{message.content}</p>
        </div>
      </article>
    );
  }

  return (
    <article className="flex items-start gap-3">
      <div className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-md bg-cloud text-ink">
        <BrainCircuit size={17} />
      </div>
      <div className="min-w-0 max-w-[86%] border-l-2 border-mist pl-4 text-sm leading-7 text-ink sm:max-w-[76%]">
        <p className="whitespace-pre-wrap break-words">{message.content}</p>
        {showDashboardAction && (
          <DashboardAction sessionId={sessionId} version={dashboardVersion} />
        )}
      </div>
    </article>
  );
}
