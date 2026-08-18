// Pure helpers for the tiered depth search (searchDepth.inline.ts). Kept separate so
// they can be unit-tested without a DOM. Shard entries use compact keys to save bytes:
// s=slug t=title g=tags c=content. (`l`/links is dropped — the search client never reads
// it; the graph + backlinks read links from contentIndex.json instead.)

export type Entry = { s: string; t?: string; g?: string[]; l?: string[]; c: string }
export type Doc = {
  id: string
  slug: string
  title: string
  content: string
  tags: string[]
  links: string[]
}

export function entryToDoc(e: Entry): Doc {
  return {
    id: e.s,
    slug: e.s,
    title: e.t ?? "",
    content: e.c ?? "",
    tags: e.g ?? [],
    links: e.l ?? [],
  }
}

// Merge a tier's entries into the doc store: add new slugs, or REPLACE the content of
// existing ones (each tier's content is a superset of the shallower tier). Returns the
// slugs that must be (re)indexed in FlexSearch.
export function mergeTier(store: Map<string, Doc>, entries: Entry[]): string[] {
  const changed: string[] = []
  for (const e of entries) {
    const prev = store.get(e.s)
    if (prev) {
      prev.content = e.c ?? prev.content
      if (e.t !== undefined) prev.title = e.t
      if (e.g !== undefined) prev.tags = e.g
      if (e.l !== undefined) prev.links = e.l
    } else {
      store.set(e.s, entryToDoc(e))
    }
    changed.push(e.s)
  }
  return changed
}

export function clampStop(stop: number, isMobile: boolean): number {
  let s = Number.isFinite(stop) ? Math.floor(stop) : 0
  if (s < 0) s = 0
  if (s > 3) s = 3
  if (isMobile && s > 1) s = 1
  return s
}

// Author display name for a result. Works carry an `author/<name>` tag; atom entries
// don't, so fall back to the author segment of `testi/<author>/…` slugs. Both use the
// underscored vault form ("conan_doyle"), which is prettified for display.
const AUTHOR_FIXUP: Record<string, string> = { conan_doyle: "Conan Doyle" }
export function authorForDoc(d: Doc): string {
  const fromTag = (d.tags || []).find((t) => t.startsWith("author/"))
  const raw = fromTag ? fromTag.slice("author/".length) : authorFromSlug(d.slug)
  if (!raw) return ""
  if (AUTHOR_FIXUP[raw]) return AUTHOR_FIXUP[raw]
  return raw
    .split("_")
    .filter(Boolean)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ")
}

function authorFromSlug(slug: string): string {
  const seg = String(slug || "")
    .split("#")[0]
    .split("/")
  if (seg[0] !== "testi" || !seg[1]) return ""
  return seg[1]
}

export const STOP_LABELS = ["Fast", "Standard", "Deep", "Max"] as const

export function stopHint(stop: number): string {
  return [
    "Works & concepts — instant",
    "More terms per work — better recall",
    "Search inside chapters (atoms)",
    "Full depth + typo-tolerant (fuzzy)",
  ][clampStop(stop, false)]
}

// Insertion-ordered union: FlexSearch (exact/prefix) hits first, MiniSearch (fuzzy)
// fills the remainder. Deduped, capped at `limit`.
export function mergeResults(flexIds: string[], fuzzyIds: string[], limit: number): string[] {
  const out: string[] = []
  const seen = new Set<string>()
  for (const id of [...flexIds, ...fuzzyIds]) {
    if (!seen.has(id)) {
      seen.add(id)
      out.push(id)
    }
    if (out.length >= limit) break
  }
  return out
}
