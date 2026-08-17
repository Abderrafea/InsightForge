import { apiRequest } from "./client";
import type { DashboardData } from "../types";

export const dashboardApi = {
  get: (sessionId: string) =>
    apiRequest<DashboardData>(`/api/sessions/${sessionId}/dashboard`),
};
