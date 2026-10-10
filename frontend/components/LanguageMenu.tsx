"use client";

import { FR, GB } from "country-flag-icons/react/3x2";
import { useEffect, useRef, useState, type ComponentType } from "react";
import { useTranslation } from "@/lib/i18n";

const LANGUAGES: { code: string; name: string; Flag: ComponentType<{ className?: string; "aria-hidden"?: boolean }> }[] = [
  { code: "en", name: "English", Flag: GB },
  { code: "fr", name: "Français", Flag: FR },
];

/** Language switcher: just the current flag; a click on it opens the list of the two interface languages, each with its country flag. */
export default function LanguageMenu() {
  const { language, setLanguage } = useTranslation();
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const current = LANGUAGES.find((entry) => entry.code === language) ?? LANGUAGES[0];

  useEffect(() => {
    if (!open) return;
    const close = (event: MouseEvent | KeyboardEvent) => {
      if (event instanceof KeyboardEvent) { if (event.key === "Escape") setOpen(false); return; }
      if (root.current && !root.current.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => { document.removeEventListener("mousedown", close); document.removeEventListener("keydown", close); };
  }, [open]);

  return (
    <div ref={root} className="relative">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={current.name}
        title={current.name}
        className="block rounded-[3px] outline-offset-4 transition-transform hover:scale-110 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#ff541f]"
      >
        <current.Flag className="h-4 w-6 rounded-[3px] shadow-[0_0_0_1px_rgba(128,128,128,0.35)]" aria-hidden />
      </button>
      {open && (
        <ul role="listbox" className="absolute right-0 top-full z-[60] mt-2 w-48 overflow-hidden rounded-lg border border-border bg-surface p-1 text-foreground shadow-md">
          {LANGUAGES.map(({ code, name, Flag }) => (
            <li key={code} role="option" aria-selected={code === language}>
              <button
                type="button"
                onClick={() => { setLanguage(code); setOpen(false); }}
                className={`flex w-full items-center gap-3 rounded-md px-3 py-2 text-left text-sm ${code === language ? "bg-accent-soft font-medium text-accent" : "hover:bg-surface-muted"}`}
              >
                <Flag className="h-4 w-6 shrink-0 rounded-[2px]" aria-hidden />
                {name}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
