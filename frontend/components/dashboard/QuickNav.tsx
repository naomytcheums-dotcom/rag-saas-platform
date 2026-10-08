"use client";

import { Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { navIcon } from "./nav";

export interface QuickNavItem {
  href: string;
  label: string;
  section: string;
}

/** The header search of the Figma dashboard, made real: it filters every destination of the app by name and opens it (Enter / click). Ctrl+K or Cmd+K focuses it. */
export default function QuickNav({ items, placeholder }: { items: QuickNavItem[]; placeholder: string }) {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [highlight, setHighlight] = useState(0);

  const matches = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return [];
    return items.filter((item) => `${item.label} ${item.section}`.toLowerCase().includes(needle)).slice(0, 8);
  }, [items, query]);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        inputRef.current?.focus();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  function go(item: QuickNavItem) {
    setQuery("");
    setOpen(false);
    router.push(item.href);
  }

  return (
    <div className="relative w-full max-w-sm">
      <div className="flex items-center gap-2.5 rounded-md border border-accent bg-surface px-3 py-2 focus-within:ring-2 focus-within:ring-accent/20">
        <Search className="h-4 w-4 shrink-0 text-foreground-muted" aria-hidden />
        <input
          ref={inputRef}
          value={query}
          onChange={(event) => { setQuery(event.target.value); setHighlight(0); setOpen(true); }}
          onFocus={() => setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 120)}
          onKeyDown={(event) => {
            if (event.key === "ArrowDown") { event.preventDefault(); setHighlight((value) => Math.min(value + 1, matches.length - 1)); }
            else if (event.key === "ArrowUp") { event.preventDefault(); setHighlight((value) => Math.max(value - 1, 0)); }
            else if (event.key === "Enter" && matches[highlight]) { event.preventDefault(); go(matches[highlight]); }
            else if (event.key === "Escape") { setOpen(false); inputRef.current?.blur(); }
          }}
          placeholder={placeholder}
          aria-label={placeholder}
          className="min-w-0 flex-1 bg-transparent text-sm text-foreground outline-none placeholder:text-foreground-muted/70"
        />
        <kbd className="hidden shrink-0 rounded bg-accent-soft px-1.5 py-0.5 text-[11px] font-medium text-accent sm:block">Ctrl K</kbd>
      </div>
      {open && matches.length > 0 && (
        <ul className="absolute left-0 right-0 top-full z-50 mt-1.5 overflow-hidden rounded-lg border border-border bg-surface p-1 shadow-md" role="listbox">
          {matches.map((item, index) => {
            const Icon = navIcon(item.href);
            return (
              <li key={item.href} role="option" aria-selected={index === highlight}>
                <button
                  type="button"
                  onMouseDown={(event) => { event.preventDefault(); go(item); }}
                  onMouseEnter={() => setHighlight(index)}
                  className={`flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-left text-sm ${index === highlight ? "bg-accent-soft text-accent" : "text-foreground"}`}
                >
                  <Icon className="h-4 w-4 shrink-0" aria-hidden />
                  <span className="flex-1 truncate">{item.label}</span>
                  <span className="text-xs text-foreground-muted">{item.section}</span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
