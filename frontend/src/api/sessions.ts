import { apiRequest } from "./client";
import type { SessionDetails, SessionSummary } from "../types";

export const sessionApi = {
  list: () => apiRequest<SessionSummary[]>("/api/sessions"),
  get: (sessionId: string) =>
    apiRequest<SessionDetails>(`/api/sessions/${sessionId}`),
  create: (title: string) =>
    apiRequest<SessionSummary>("/api/sessions", {
      method: "POST",
      body: JSON.stringify({ title }),
    }),
  rename: (sessionId: string, title: string) =>
    apiRequest<SessionSummary>(`/api/sessions/${sessionId}`, {
      method: "PATCH",
      body: JSON.stringify({ title }),
    }),
  delete: (sessionId: string) =>
    apiRequest<void>(`/api/sessions/${sessionId}`, { method: "DELETE" }),
  attachDatabase: (sessionId: string, connectionId: string) =>
    apiRequest<SessionDetails>(
      `/api/sessions/${sessionId}/database-connection/${connectionId}`,
      { method: "PUT" },
    ),
};
