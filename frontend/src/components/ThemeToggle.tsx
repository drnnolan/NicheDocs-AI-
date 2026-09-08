"use client";

import { useEffect, useState } from "react";
import { MoonIcon, SunIcon, SystemIcon } from "./icons";

export type Theme = "light" | "dark" | "system";

export const THEME_STORAGE_KEY = "nichedocs-theme";

const ORDER: Theme[] = ["light", "dark", "system"];

const LABEL: Record<Theme, string> = {
  light: "Light",
  dark: "Dark",
  system: "System",
};

/** Mirror the choice onto <html> so the CSS token layer can react to it. */
function apply(theme: Theme) {
  const root = document.documentElement;
  if (theme === "system") {
    // No attribute: prefers-color-scheme takes over.
    root.removeAttribute("data-theme");
  } else {
    root.setAttribute("data-theme", theme);
  }
}

function readStoredTheme(): Theme {
  // Guard for the server render, where there is no localStorage at all.
  if (typeof window === "undefined") return "system";
  try {
    const stored = localStorage.getItem(THEME_STORAGE_KEY) as Theme | null;
    if (stored && ORDER.includes(stored)) return stored;
  } catch {
    // Private mode or blocked storage — fall back to following the OS.
  }
  return "system";
}

export function ThemeToggle() {
  // Lazy initialiser rather than a state-setting effect: the value is known at
  // first client render, so there is no reason to render once and correct.
  const [theme, setTheme] = useState<Theme>(readStoredTheme);

  useEffect(() => {
    apply(theme);
    try {
      localStorage.setItem(THEME_STORAGE_KEY, theme);
    } catch {
      // Not fatal: the theme still applies for this session.
    }
  }, [theme]);

  function cycle() {
    setTheme((current) => ORDER[(ORDER.indexOf(current) + 1) % ORDER.length]);
  }

  const Icon = theme === "light" ? SunIcon : theme === "dark" ? MoonIcon : SystemIcon;

  return (
    <button
      type="button"
      onClick={cycle}
      title={`Theme: ${LABEL[theme]} — click to change`}
      aria-label={`Theme: ${LABEL[theme]}. Click to switch theme.`}
      className="inline-flex items-center gap-2 rounded-lg border border-header-line bg-surface/70 px-3 py-1.5 text-xs font-semibold text-header-title shadow-sm transition hover:bg-surface hover:shadow focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-1 focus-visible:ring-offset-header"
    >
      {/*
        suppressHydrationWarning: the server always renders the "system" icon,
        but the inline boot script may already have applied a stored theme by
        the time React hydrates.
      */}
      <span suppressHydrationWarning>
        <Icon className="h-4 w-4" />
      </span>
      <span className="hidden sm:inline" suppressHydrationWarning>
        {LABEL[theme]}
      </span>
    </button>
  );
}
