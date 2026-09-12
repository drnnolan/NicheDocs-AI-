import type { Metadata } from "next";
import "./globals.css";
import { InlineScript } from "@/components/InlineScript";

export const metadata: Metadata = {
  title: "NicheDocs AI — Grounded Document Q&A",
  description:
    "Upload a PDF and ask questions about it. Every answer is grounded in the document and cites the page it came from — and says so plainly when the document does not cover your question.",
};

/*
  Applied before first paint, ahead of React hydrating. Without it a user who
  chose dark would get a white flash on every page load while the JS bundle
  downloads. Kept deliberately tiny and dependency-free, and wrapped in
  try/catch because localStorage throws outright in some privacy modes.
*/
const THEME_BOOT_SCRIPT = `
(function () {
  var t = null;
  try {
    t = localStorage.getItem("nichedocs-theme");
  } catch (e) {}
  if (t !== "light" && t !== "dark") {
    // No stored choice: fall back to the OS preference, so a first-time
    // visitor on a dark desktop does not get a white page.
    try {
      t = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    } catch (e) {
      t = "light";
    }
  }
  document.documentElement.setAttribute("data-theme", t);
})();
`;

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    // suppressHydrationWarning on <html>: the boot script sets data-theme
    // before React hydrates, so the attribute legitimately differs from SSR.
    <html lang="en" data-theme="light" suppressHydrationWarning>
      <head>
        {/*
          Deliberately an inline script, not next/script: `beforeInteractive` is
          documented as *not* blocking hydration, so it cannot guarantee the
          theme lands before first paint — which is the entire job here. An
          inline script in <head> runs synchronously during HTML parsing.

          InlineScript handles the dev-only "scripts are never executed"
          warning. The content is a build-time constant, never user input.
        */}
        <InlineScript html={THEME_BOOT_SCRIPT} />
      </head>
      {/*
        suppressHydrationWarning: browser extensions (Grammarly, password
        managers) inject attributes onto <body> before React hydrates, which
        React reports as a server/client mismatch. It only suppresses warnings
        for this element's own attributes, one level deep — real hydration bugs
        inside the tree still surface.
      */}
      <body className="h-full" suppressHydrationWarning>
        {children}
      </body>
    </html>
  );
}
