import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { apiRequest, setVisitorAI } from "../api/client";
import { AccessGate } from "./AccessGate";

afterEach(() => { setVisitorAI(null); vi.unstubAllGlobals(); });

describe("visitor access", () => {
  it("asks for a masked key and starts the workspace without storing the key", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({ public_visitors: true, models: ["openai/gpt-oss-120b"], session_hours: 8 }))).mockResolvedValueOnce(new Response('{"ready":true}'));
    vi.stubGlobal("fetch", fetchMock);
    const local = vi.spyOn(Storage.prototype, "setItem");
    render(<AccessGate><p>Private workspace</p></AccessGate>);
    const input = await screen.findByLabelText("Groq API key");
    expect(input).toHaveAttribute("type", "password");
    fireEvent.change(input, { target: { value: "gsk_disposable_example_for_ui_test" } });
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.submit(screen.getByRole("button", { name: "Start private session" }).closest("form")!);
    expect(await screen.findByText("Private workspace")).toBeInTheDocument();
    expect(JSON.stringify(fetchMock.mock.calls[1])).not.toContain("gsk_");
    expect(local).not.toHaveBeenCalled();
    local.mockRestore();
  });

  it("sends the key only to agent requests and clears it on demand", async () => {
    const fetchMock = vi.fn().mockImplementation(async () => new Response("{}"));
    vi.stubGlobal("fetch", fetchMock);
    setVisitorAI({ key: "visitor-secret", model: "openai/gpt-oss-120b" });
    await apiRequest("/api/sessions");
    expect(fetchMock.mock.calls[0][1].headers.Authorization).toBeUndefined();
    await apiRequest("/api/sessions/example/agent/messages", { method: "POST", body: "{}" });
    expect(fetchMock.mock.calls[1][1].headers.Authorization).toBe("Bearer visitor-secret");
    setVisitorAI(null);
    await apiRequest("/api/sessions/example/agent/messages", { method: "POST", body: "{}" });
    expect(fetchMock.mock.calls[2][1].headers.Authorization).toBeUndefined();
  });

  it("keeps the owner workflow available without asking for a visitor key", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response('{"public_visitors":false,"models":[],"session_hours":8}')));
    render(<AccessGate><p>Owner workspace</p></AccessGate>);
    await waitFor(() => expect(screen.getByText("Owner workspace")).toBeInTheDocument());
    expect(screen.queryByLabelText("Groq API key")).not.toBeInTheDocument();
  });

  it("lets visitors choose a provider and custom model while clearing old credentials and consent", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ public_visitors: true, models: ["groq-model"], session_hours: 8, allow_custom_models: true, providers: [
        { id: "groq", label: "Groq", models: ["groq-model"] },
        { id: "openai", label: "OpenAI (GPT)", models: ["gpt-6-luna"] },
        { id: "anthropic", label: "Anthropic (Claude)", models: ["claude-sonnet-5-5"] },
      ] })))
      .mockImplementation(async () => new Response("{}"));
    vi.stubGlobal("fetch", fetchMock);
    render(<AccessGate><p>Private workspace</p></AccessGate>);
    const firstKey = await screen.findByLabelText("Groq API key");
    fireEvent.change(firstKey, { target: { value: "old-groq-key-which-must-be-cleared" } });
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.change(screen.getByLabelText("AI provider"), { target: { value: "openai" } });
    expect(screen.getByLabelText("OpenAI (GPT) API key")).toHaveValue("");
    expect(screen.getByRole("checkbox")).not.toBeChecked();
    fireEvent.change(screen.getByLabelText("AI model"), { target: { value: "__custom__" } });
    fireEvent.change(screen.getByLabelText("Custom model ID"), { target: { value: "my-gpt-model-2026" } });
    fireEvent.change(screen.getByLabelText("OpenAI (GPT) API key"), { target: { value: "my-openai-key-for-this-browser-only" } });
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.submit(screen.getByRole("button", { name: "Start private session" }).closest("form")!);
    await screen.findByText("Private workspace");
    await apiRequest("/api/sessions/example/agent/messages", { method: "POST", body: "{}" });
    const headers = fetchMock.mock.calls.at(-1)![1].headers;
    expect(headers["X-AI-Provider"]).toBe("openai");
    expect(headers["X-AI-Model"]).toBe("my-gpt-model-2026");
    expect(headers.Authorization).toBe("Bearer my-openai-key-for-this-browser-only");
    expect(JSON.stringify(fetchMock.mock.calls)).not.toContain("old-groq-key");
  });
});
