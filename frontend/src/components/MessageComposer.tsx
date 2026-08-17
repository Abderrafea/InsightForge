import { ArrowUp, LoaderCircle } from "lucide-react";
import { useState } from "react";

interface MessageComposerProps {
  onSend: (content: string) => Promise<void>;
  disabled: boolean;
}

export function MessageComposer({ onSend, disabled }: MessageComposerProps) {
  const [content, setContent] = useState("");

  const submit = async () => {
    const cleaned = content.trim();
    if (!cleaned || disabled) return;
    setContent("");
    await onSend(cleaned);
  };

  return (
    <div className="mx-auto w-full max-w-4xl px-4 pb-4 sm:px-7 sm:pb-6">
      <div className="flex min-h-14 items-end gap-2 rounded-md border border-mist bg-white p-2 shadow-[0_10px_30px_rgba(47,65,87,0.08)] focus-within:border-steel">
        <textarea
          value={content}
          onChange={(event) => setContent(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              void submit();
            }
          }}
          rows={1}
          placeholder="Ask about your data..."
          disabled={disabled}
          aria-label="Message"
          className="max-h-36 min-h-10 min-w-0 flex-1 resize-none bg-transparent px-2 py-2 text-sm leading-6 text-ink placeholder:text-steel/80 disabled:cursor-not-allowed"
        />
        <button
          onClick={() => void submit()}
          disabled={disabled || !content.trim()}
          className="grid h-10 w-10 shrink-0 place-items-center rounded-md bg-ink text-white transition-colors hover:bg-steel disabled:cursor-not-allowed disabled:opacity-40"
          aria-label="Send message"
        >
          {disabled ? <LoaderCircle size={17} className="animate-spin" /> : <ArrowUp size={18} />}
        </button>
      </div>
    </div>
  );
}
