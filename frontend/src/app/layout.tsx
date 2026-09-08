import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "HandbookIQ — NicheDocs AI",
  description:
    "Ask questions about your university student handbook and get answers grounded in the document, with page and section citations.",
};

/*
  Applied before first paint, ahead of React hydrating. Without it a user who
  chose dark would get a white flash on every page load while the JS bundle
  downloads. Kept deliberately tiny and dependency-free, and wrapped in
  try/catch because localStorage throws outright in some privacy modes.
*/
const THEME_BOOT_SCRIPT = `
(function () {
  try {
    var t = localStorage.getItem("nichedocs-theme");
    if (t === "light" || t === "dark") {
      document.documentElement.setAttribute("data-theme", t);
    }
  } catch (e) {}
})();
`;

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    // suppressHydrationWarning on <html>: the boot script sets data-theme
    // before React hydrates, so the attribute legitimately differs from SSR.
    <html lang="en" suppressHydrationWarning>
      <head>
        <script
          // The content is a build-time constant, never user input.
          dangerouslySetInnerHTML={{ __html: THEME_BOOT_SCRIPT }}
        />
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
