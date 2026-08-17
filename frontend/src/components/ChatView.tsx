import { useEffect, useRef } from "react";
import type { Message } from "../types";
import { AgentStatus } from "./AgentStatus";
import { ChatMessage } from "./ChatMessage";

interface ChatViewProps {
  messages: Message[];
  sessionId: string;
  lastDashboardMessageId: string | null;
  dashboardVersion?: number;
  runningStatus: string | null;
  onSuggestion: (prompt: string) => void;
}

const suggestions = [
  "Build me a sales dashboard",
  "Show customer growth",
  "Analyze product performance",
];

export function ChatView({
  messages,
  sessionId,
  lastDashboardMessageId,
  dashboardVersion,
  runningStatus,
  onSuggestion,
}: ChatViewProps) {
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => endRef.current?.scrollIntoView({ behavior: "smooth" }), [messages, runningStatus]);

  return (
    <div className="mx-auto w-full max-w-4xl px-4 py-7 sm:px-7 sm:py-10">
      {messages.length === 0 && !runningStatus ? (
        <div className="flex min-h-[52vh] flex-col justify-center">
          <p className="text-sm font-semibold text-steel">Start with your business question</p>
          <h2 className="mt-2 max-w-xl text-2xl font-bold text-ink sm:text-3xl">
            What would you like to analyze?
          </h2>
          <div className="mt-7 flex flex-wrap gap-2">
            {suggestions.map((suggestion) => (
              <button
                key={suggestion}
                onClick={() => onSuggestion(suggestion)}
                className="rounded-md border border-mist bg-white px-3 py-2 text-left text-sm font-medium text-ink transition-colors hover:bg-cloud"
              >
                {suggestion}
              </button>
            ))}
          </div>
        </div>
      ) : (
        <div className="space-y-8">
          {messages.map((message) => (
            <ChatMessage
              key={message.id}
              message={message}
              sessionId={sessionId}
              showDashboardAction={message.id === lastDashboardMessageId}
              dashboardVersion={dashboardVersion}
            />
          ))}
          {runningStatus && <AgentStatus label={runningStatus} />}
        </div>
      )}
      <div ref={endRef} />
    </div>
  );
}
