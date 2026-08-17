import { apiRequest } from "./client";
import type { DatabaseConnectionInput } from "../types";

interface CreatedConnection {
  id: string;
}

export const databaseApi = {
  test: (input: Omit<DatabaseConnectionInput, "name">) =>
    apiRequest<{ success: true }>("/api/database-connections/test", {
      method: "POST",
      body: JSON.stringify(input),
    }),
  create: (input: DatabaseConnectionInput) =>
    apiRequest<CreatedConnection>("/api/database-connections", {
      method: "POST",
      body: JSON.stringify(input),
    }),
};
