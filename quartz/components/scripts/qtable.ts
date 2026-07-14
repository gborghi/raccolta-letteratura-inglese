// Shared helpers for the client-side table scripts (opere / brani / cerca / concept).
//
// PROBE STAGE: for now this only exports esc(), imported by braniTable.inline.ts, to
// verify that the inline-script loader (componentResources imports each *.inline.ts as
// a separately esbuild-bundled string) resolves + inlines a relative import to a plain
// (non-.inline) module. If /brani still renders after deploy, the rest of the shared
// table machinery (loadKw, mode toggle, pager, page-size select, renderTable) moves
// here and the four table scripts become thin adapters.
export function esc(s: unknown): string {
  return String(s).replace(/[&<>"]/g, (c) =>
    c === "&" ? "&amp;" : c === "<" ? "&lt;" : c === ">" ? "&gt;" : "&quot;",
  )
}
