import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "HandbookIQ — NicheDocs AI",
  description:
    "Ask questions about your university student handbook and get answers grounded in the document, with page and section citations.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
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
