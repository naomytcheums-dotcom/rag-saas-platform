"use client";

import { useTranslation } from "@/lib/i18n";
import ConversationList from "./ConversationList";
import ConversationSearch from "./ConversationSearch";

interface ChatSidebarProps {
  open: boolean;
  onClose: () => void;
}

// Real conversation sidebar (Partie 8.1.10/8.1.12), wired against the
// real backend -- shows a real, honest empty state ("No conversations
// yet") when no backend/auth session is present, rather than fake
// data. Slides in as a real overlay on mobile (<768px), a real, fixed
// column on desktop.
export default function ChatSidebar({ open, onClose }: ChatSidebarProps) {
  const { t } = useTranslation();
  return (
    <>
      {open && (
        <div className="fixed inset-0 z-40 bg-black/20 md:hidden" onClick={onClose} role="presentation" />
      )}
      <aside
        className={`fixed inset-y-0 left-0 z-50 flex w-72 shrink-0 flex-col gap-3 border-r border-border bg-surface p-4 transition-transform md:static md:z-auto md:translate-x-0 md:shadow-none ${
          open ? "translate-x-0 shadow-md" : "-translate-x-full"
        }`}
      >
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-foreground">{t("conversations")}</h2>
          <button type="button" onClick={onClose} aria-label={t("close_sidebar")} className="rounded-lg p-1 text-foreground-muted hover:bg-surface-muted md:hidden">
            ✕
          </button>
        </div>

        <button type="button" className="rounded-lg bg-accent px-3 py-2 text-sm font-medium text-white hover:bg-accent-hover">
          {t("new_conversation_button")}
        </button>

        <ConversationSearch onSelect={() => onClose()} />

        <div className="flex-1 overflow-y-auto">
          <ConversationList onSelect={() => onClose()} />
        </div>
      </aside>
    </>
  );
}
