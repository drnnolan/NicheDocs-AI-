"use client";

import { useLayoutEffect, useState, useSyncExternalStore } from "react";
import { MoonIcon, SunIcon } from "./icons";

export type Theme = "light" | "dark";

export const THEME_STORAGE_KEY = "nichedocs-theme";

const ORDER: Theme[] = ["light", "dark"];

const LABEL: Record<Theme, string> = {
  light: "Light",
  dark: "Dark",
};

/** Mirror the choice onto <html> so the CSS token layer can react to it. */
function apply(theme: Theme) {
  document.documentElement.setAttribute("data-theme", theme);
}

function readStoredTheme(): Theme {
  // Guard for the server render, where there is no localStorage at all.
  if (typeof window === "undefined") return "light";
  try {
    const stored = localStorage.getItem(THEME_STORAGE_KEY) as Theme | null;
    if (stored && ORDER.includes(stored)) return stored;
  } catch {
    // Private mode or blocked storage — fall through to the OS preference.
  }
  // There is no longer an explicit "System" setting, but a first-time visitor
  // should still land on whichever theme their OS is set to. After that, their
  // toggle choice is stored and wins.
  try {
    if (window.matchMedia?.("(prefers-color-scheme: dark)").matches) return "dark";
  } catch {
    // matchMedia is unavailable in some embedded browsers.
  }
  return "light";
}

const BUTTON_CLASS =
  "inline-flex items-center gap-2 rounded-full border border-line bg-header-btn px-4 py-2 text-sm font-semibold text-header-title shadow-md shadow-shadow transition hover:border-accent-line hover:shadow-lg focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-header";

export function ThemeToggle() {
  // The server cannot know the visitor's stored theme, so the first client
  // render must match the server's output exactly or React reports a hydration
  // mismatch. `useSyncExternalStore` is built for precisely this: the third
  // argument is the server snapshot, so React renders `false` during SSR and
  // the first hydration pass, then `true` immediately after — no state-setting
  // effect, and no mismatch.
  //
  // `suppressHydrationWarning` was the wrong tool for the button: it only
  // covers an element's own attributes one level deep, so it silenced nothing
  // on the title/aria-label or the swapped SVG children.
  const mounted = useSyncExternalStore(
    () => () => {},
    () => true,
    () => false,
  );

  // Only read once mounted; during SSR this returns the neutral default.
  const [override, setOverride] = useState<Theme | null>(null);
  const theme: Theme = override ?? (mounted ? readStoredTheme() : "light");

  // Runs before paint. In development, React's Strict Mode remounts once and
  // resets <html> to only the attributes it manages from JSX, wiping the
  // data-theme the boot script set during parsing. Re-applying here restores
  // it before anything is painted. A no-op in production.
  useLayoutEffect(() => {
    if (!mounted) return;
    apply(theme);
    try {
      localStorage.setItem(THEME_STORAGE_KEY, theme);
    } catch {
      // Not fatal: the theme still applies for this session.
    }
  }, [theme, mounted]);

  function cycle() {
    setOverride(theme === "light" ? "dark" : "light");
  }

  if (!mounted) {
    // Same box, same classes, no theme-dependent content — so server and client
    // agree. `aria-hidden` keeps a label-less control out of the a11y tree for
    // the moment it exists.
    return (
      <span className={BUTTON_CLASS} aria-hidden>
        <span className="h-4 w-4" />
        <span className="hidden sm:inline">Theme</span>
      </span>
    );
  }

  // Show the icon for the theme you'd switch *to* — a moon while in light mode
  // reads as "click for dark", which is the convention users expect.
  const Icon = theme === "light" ? MoonIcon : SunIcon;
  const next: Theme = theme === "light" ? "dark" : "light";

  return (
    <button
      type="button"
      onClick={cycle}
      title={`Switch to ${LABEL[next].toLowerCase()} mode`}
      aria-label={`Switch to ${LABEL[next].toLowerCase()} mode`}
      className={BUTTON_CLASS}
    >
      <Icon className="h-4 w-4" />
      <span className="hidden sm:inline">{LABEL[next]}</span>
    </button>
  );
}
