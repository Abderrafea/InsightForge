import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";
import { AppSidebar } from "./AppSidebar";
import { ChatView } from "./ChatView";
import { DatabaseStatus } from "./DatabaseStatus";
import { MessageComposer } from "./MessageComposer";
import { SessionList } from "./SessionList";
import type { Message, SessionSummary } from "../types";

const sessions: SessionSummary[] = [
  {
    id: "session-a",
    user_id: null,
    title: "Sales Performance",
    database_connection_id: null,
    ai_provider: "groq",
    ai_model: "llama-test",
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: "session-b",
    user_id: null,
    title: "Customer Analysis",
    database_connection_id: null,
    ai_provider: null,
    ai_model: null,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
];

const messages: Message[] = [
  {
    id: "user-1",
    session_id: "session-a",
    role: "user",
    content: "Build a sales dashboard",
    created_at: new Date().toISOString(),
  },
  {
    id: "assistant-1",
    session_id: "session-a",
    role: "assistant",
    content: "I created the dashboard.",
    created_at: new Date().toISOString(),
  },
  {
    id: "assistant-2",
    session_id: "session-a",
    role: "assistant",
    content: "Which chart did you mean?",
    created_at: new Date().toISOString(),
  },
];

describe("session UI", () => {
  it("renders sessions and marks the selected session", () => {
    render(
      <MemoryRouter>
        <SessionList sessions={sessions} activeId="session-a" onRename={vi.fn()} onDelete={vi.fn()} />
      </MemoryRouter>,
    );
    expect(screen.getByText("Sales Performance")).toBeInTheDocument();
    expect(screen.getByText("Customer Analysis")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Sales Performance/i })).toHaveAttribute("aria-current", "page");
  });

  it("starts a new session from the sidebar", async () => {
    const create = vi.fn().mockResolvedValue(undefined);
    render(
      <MemoryRouter>
        <AppSidebar sessions={sessions} activeId={null} activeSession={null} open onClose={vi.fn()} onCreate={create} onRename={vi.fn()} onDelete={vi.fn()} />
      </MemoryRouter>,
    );
    await userEvent.click(screen.getByRole("button", { name: /New Session/i }));
    expect(create).toHaveBeenCalledOnce();
  });
});

describe("chat UI", () => {
  it("shows the dashboard action only on the message that created the current version", () => {
    render(
      <MemoryRouter>
        <ChatView messages={messages} sessionId="session-a" lastDashboardMessageId="assistant-1" dashboardVersion={2} runningStatus={null} onSuggestion={vi.fn()} />
      </MemoryRouter>,
    );
    expect(screen.getAllByRole("link", { name: /Open Dashboard/i })).toHaveLength(1);
    expect(screen.getByRole("link", { name: /Open Dashboard/i })).toHaveAttribute("href", "/sessions/session-a/dashboard");
  });

  it("renders the empty state and prompt suggestions", () => {
    render(
      <MemoryRouter>
        <ChatView messages={[]} sessionId="session-a" lastDashboardMessageId={null} runningStatus={null} onSuggestion={vi.fn()} />
      </MemoryRouter>,
    );
    expect(screen.getByText("What would you like to analyze?")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Build me a sales dashboard" })).toBeInTheDocument();
  });

  it("sends on Enter and supports a disabled loading state", async () => {
    const send = vi.fn().mockResolvedValue(undefined);
    const { rerender } = render(<MessageComposer onSend={send} disabled={false} />);
    const input = screen.getByRole("textbox", { name: "Message" });
    await userEvent.type(input, "Show customer growth");
    fireEvent.keyDown(input, { key: "Enter", code: "Enter" });
    expect(send).toHaveBeenCalledWith("Show customer growth");

    rerender(<MessageComposer onSend={send} disabled />);
    expect(screen.getByRole("textbox", { name: "Message" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Send message" })).toBeDisabled();
  });

  it("renders the disconnected database state", () => {
    render(<DatabaseStatus connected={false} />);
    expect(screen.getByText("No database connected")).toBeInTheDocument();
    expect(screen.getByLabelText("No database connected")).toBeInTheDocument();
  });

  it("renders lightweight agent progress", () => {
    render(
      <MemoryRouter>
        <ChatView messages={messages} sessionId="session-a" lastDashboardMessageId={null} runningStatus="Inspecting schema..." onSuggestion={vi.fn()} />
      </MemoryRouter>,
    );
    expect(screen.getByRole("status")).toHaveTextContent("Inspecting schema...");
  });
});
