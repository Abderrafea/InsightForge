import { apiRequest } from "./client";
import type { AgentMessageResponse } from "../types";

export const agentApi = {
  send: (sessionId: string, content: string) =>
    apiRequest<AgentMessageResponse>(
      `/api/sessions/${sessionId}/agent/messages`,
      { method: "POST", body: JSON.stringify({ content }) },
    ),
};
