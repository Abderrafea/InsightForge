interface ApiErrorShape {
  error?: { message?: string };
}

export type AIProvider = "groq" | "openai" | "anthropic";
let visitorAI: { key: string; model: string; provider?: AIProvider } | null = null;

export function setVisitorAI(value: { key: string; model: string; provider?: AIProvider } | null) {
  visitorAI = value;
}

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
  }
}

export async function apiRequest<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-Requested-With": "InsightForge",
      ...(visitorAI && path.endsWith("/agent/messages")
        ? { "Authorization": `Bearer ${visitorAI.key}`, "X-AI-Model": visitorAI.model, "X-AI-Provider": visitorAI.provider ?? "groq" }
        : {}),
      ...init?.headers,
    },
  });
  if (!response.ok) {
    if (response.status === 401) window.dispatchEvent(new Event("visitor-session-expired"));
    const body = (await response.json().catch(() => ({}))) as ApiErrorShape;
    throw new ApiError(
      body.error?.message ?? "InsightForge could not complete the request.",
      response.status,
    );
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}
