"use client";

import type { Conversation } from "@/lib/types";
import DeleteConversation from "./DeleteConversation";
import RenameConversation from "./RenameConversation";

interface ConversationItemProps {
  conversation: Conversation;
  active?: boolean;
  onSelect: (id: string) => void;
  onRenamed: (conversation: Conversation) => void;
  onDeleted: (id: string) => void;
}

// Partie 8.1.10 -- one row in ConversationList: title, last-modified
// date, rename/delete actions.
export default function ConversationItem({ conversation, active, onSelect, onRenamed, onDeleted }: ConversationItemProps) {
  return (
    <div
      className={`group flex items-center justify-between gap-2 rounded-xl px-3 py-2 ${
        active ? "bg-accent-soft" : "hover:bg-surface-muted"
      }`}
    >
      <button type="button" onClick={() => onSelect(conversation.id)} className="min-w-0 flex-1 text-left">
        <RenameConversation conversation={conversation} onRenamed={onRenamed} />
        <p className="text-xs text-foreground-muted">
          {new Date(conversation.updated_at).toLocaleDateString(undefined, { month: "short", day: "numeric" })}
        </p>
      </button>
      <div className="opacity-0 group-hover:opacity-100">
        <DeleteConversation conversationId={conversation.id} onDeleted={() => onDeleted(conversation.id)} />
      </div>
    </div>
  );
}
