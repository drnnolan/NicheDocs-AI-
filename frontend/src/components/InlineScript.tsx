/**
 * An inline <script> that runs during HTML parsing, before first paint.
 *
 * React warns in development when a component renders a <script> tag, because
 * scripts inserted via client-side DOM updates never execute. This is the
 * pattern Next.js documents for the legitimate case: emit a real executable
 * script on the server, and `text/plain` (inert, ignored) on the client, with
 * `suppressHydrationWarning` covering the deliberate `type` mismatch.
 *
 * See node_modules/next/dist/docs/01-app/02-guides/preventing-flash-before-hydration.md
 */
export function InlineScript({ html }: { html: string }) {
  return (
    <script
      type={typeof window === "undefined" ? "text/javascript" : "text/plain"}
      suppressHydrationWarning
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
