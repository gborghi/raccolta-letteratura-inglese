// Wikilink -> full-slug resolution.
//
// The vault writes Obsidian-style bare wikilinks (`[[Nature|nature]]`, `[[Alone]]`).
// Quartz resolves those with `markdownLinkResolution: shortest`, which matches a
// single-segment target against every page BASENAME — and when the basename is
// ambiguous (or absent) it silently falls back to a bare root slug that 404s. That
// fallback accounted for ~74k dead links: `nature` exists under both concepts/ and
// motifs/, `hamlet` under characters/ and as a reading page, `alone` only ever as
// `works/alone-(poe)`.
//
// So preprocess resolves every wikilink itself, emitting the full slug plus an
// explicit alias (`[[motifs/nature|nature]]`) — a multi-segment target is matched by
// `shortest` against the whole slug, so no fallback can fire. Links we cannot resolve
// are left exactly as they were: they stay visible to the broken-link census instead
// of being rewritten into a different kind of wrong.
//
// Pure + importable (no top-level side effects), so preprocess-links.test.mjs can
// exercise it without triggering preprocess.mjs's content wipe.

// Folder preference when one basename exists in several knowledge-graph folders.
// Ordered by how a bare in-prose link is meant: an idea first, then the concrete
// figure or place, with the aggregation pages (clusters, works) last.
export const LINK_FOLDER_RANK = [
  "authors",
  "concepts",
  "motifs",
  "archetypes",
  "topoi",
  "forms",
  "settings",
  "historical-references",
  "characters",
  "clusters",
  "works",
]
const RANK = new Map(LINK_FOLDER_RANK.map((f, i) => [f, i]))
const rankOf = (slug) => {
  const r = RANK.get(slug.split("/")[0])
  return r === undefined ? LINK_FOLDER_RANK.length : r
}

// Author pages carry prose, not a "## Works" aggregate, so their weight is always 0
// and the populated-node preference below would wrongly demote them.
const alwaysPopulated = (slug) => slug.startsWith("authors/")

// Normalize an author for the work-title tiebreak: the vault's folder form
// ("Conan_Doyle"), the frontmatter form ("Conan Doyle") and the filename suffix
// form ("(Conan Doyle)") all have to collapse to the same key.
export function authorKey(s) {
  return String(s || "")
    .toLowerCase()
    .replace(/[_\s]+/g, " ")
    .trim()
}

const push = (map, key, val) => {
  const cur = map.get(key)
  if (cur) cur.push(val)
  else map.set(key, [val])
}

// buildLinkIndex(notes, sluggify) -> { resolve(target, ctx), size }
//   notes: [{ slug, weight, author }] — every knowledge-graph note that emits a page.
//     `weight` = how many works the node aggregates (0 for an empty node).
//   sluggify: preprocess's own slugifier, so target slugs and page slugs agree.
export function buildLinkIndex(notes, sluggify) {
  const bySlug = new Map() // slug -> note
  const byBase = new Map() // basename -> [slug]
  const byWorkKey = new Map() // work title minus its "(Author)"/"(2)" suffixes -> [{slug, dist}]

  for (const n of notes) {
    if (bySlug.has(n.slug)) continue
    bySlug.set(n.slug, n)
    const base = n.slug.split("/").pop()
    push(byBase, base, n.slug)
    if (!n.slug.startsWith("works/")) continue
    // "the-sphinx-(poe)" -> "the-sphinx"; "sonnet-(coleridge)-(2)" -> "sonnet-(coleridge)"
    // -> "sonnet". Each strip costs one point of distance, so the closest title wins.
    let key = base
    for (let dist = 1; ; dist++) {
      const stripped = key.replace(/[-\s]*\([^()]*\)$/, "")
      if (!stripped || stripped === key) break
      key = stripped
      push(byWorkKey, key, { slug: n.slug, dist })
    }
  }

  // Pick among knowledge-graph notes sharing a basename: prefer a node that actually
  // aggregates works over an empty stub (sending a reader to an empty page is the
  // worse failure), then the folder order above, then alphabetically for determinism.
  const pickNote = (slugs) => {
    if (slugs.length === 1) return slugs[0]
    const populated = slugs.filter((s) => alwaysPopulated(s) || (bySlug.get(s)?.weight || 0) > 0)
    const pool = populated.length ? populated : slugs
    return pool.slice().sort((a, b) => rankOf(a) - rankOf(b) || (a < b ? -1 : a > b ? 1 : 0))[0]
  }

  // Pick among works sharing a bare title: closest title first, then the work by the
  // author whose page we are on ("The Sphinx" inside Poe means Poe's, not Wilde's).
  const pickWork = (cands, ctx) => {
    const best = Math.min(...cands.map((c) => c.dist))
    const pool = cands.filter((c) => c.dist === best)
    if (pool.length === 1) return pool[0].slug
    const a = authorKey(ctx && ctx.author)
    const mine = a ? pool.filter((c) => authorKey(bySlug.get(c.slug)?.author) === a) : []
    const use = mine.length ? mine : pool
    return use
      .map((c) => c.slug)
      .sort((x, y) => (x < y ? -1 : x > y ? 1 : 0))[0]
  }

  // A bare title only counts as a reference to a WORK when it is written as a title:
  // no alias (or an alias identical to it) and an initial capital. The vault's tagger
  // matched bare words against work titles, so it linked every "alone" in the corpus
  // to Poe's poem, every "song" and "romance" and "a dream" likewise — ~19k links that
  // mean the word in the sentence, not the work. Resolving them would replace a dead
  // link with a wrong one, and leaving them is 19k 404s, so they are degraded to plain
  // text (STRIP). The vault keeps the links, so the repair queue still sees them; only
  // the published page loses them, the same way transform() drops links to unpublished
  // full texts.
  const readsAsTitle = (target, ctx) => {
    const shown = ctx && ctx.alias != null ? ctx.alias : target
    return shown === target && /^\p{Lu}/u.test(target.trim())
  }

  const resolve = (target, ctx) => {
    const t = sluggify(String(target).trim())
    if (!t) return null
    if (t.includes("/")) return bySlug.has(t) ? t : null
    const notesFor = byBase.get(t)
    if (notesFor) return pickNote(notesFor)
    const works = byWorkKey.get(t)
    if (works && readsAsTitle(target, ctx)) return pickWork(works, ctx)
    // A surface form is left exactly as written here. Whether it should be dropped
    // depends on whether anything else on the site answers to that name, which is
    // only knowable once every page has been emitted — see stripDeadSurfaceForms.
    return null
  }

  const isSurfaceForm = (target, alias) => {
    const t = sluggify(String(target).trim())
    return !t.includes("/") && byWorkKey.has(t) && !readsAsTitle(target, { alias })
  }

  return { resolve, isSurfaceForm, size: bySlug.size }
}

// [[target]] / [[target|alias]] / [[target\|alias]] / [[target#anchor|alias]].
// The target class excludes "[" and "]" so a nested `[[South [[Africa]]]]` (see the
// EN-source defect) matches only its inner link, and excludes "\" so the escaped
// alias pipe of a table row is read as a separator, not as part of the target.
const WIKILINK_RE = /\[\[([^\[\]|#\\]+?)(#[^\[\]|]*)?(?:(\\?\|)([^\[\]]*))?\]\]/g

const inTableRow = (s, at) => /^[ \t]*\|/.test(s.slice(s.lastIndexOf("\n", at) + 1, at + 1))

// Rewrite every resolvable wikilink in `md` to its full slug, keeping the rendered
// text identical: a link that had no alias gains one carrying its original target.
// Inside a GFM table row that alias pipe is escaped, or the tokenizer would read it
// as a column divider (same reason as escapeTableAliasPipes).
export function resolveWikilinks(md, resolve, ctx) {
  if (!md || md.indexOf("[[") < 0) return md
  return String(md).replace(WIKILINK_RE, (m, target, anchor, pipe, alias, at, s) => {
    const slug = resolve(target, { ...ctx, alias: pipe ? alias : null })
    if (!slug || slug === target) return m
    const sep = pipe || (inTableRow(s, at) ? "\\|" : "|")
    return `[[${slug}${anchor || ""}${sep}${pipe ? alias : target}]]`
  })
}

// Final pass, once every page slug is known: drop the wikilink around anything that
// leads nowhere, keeping the words. Two defects arrive here.
//
// Surface forms: the vault's tagger matched bare words against work titles, so it
// linked every "alone" in the corpus to Poe's poem, every "song", "romance", "a dream".
// Some of those names do belong to a page — Chesterton's essays "house", "sword",
// "philosophy" — so the link lands; it still does not mean the essay. Both halves come
// from the same defect, and `keep` is what decides between them.
//
// Dead targets: "[[Cardenio]]", "[[Pastoral]]" name something the vault never carried.
// However the link is written, it is a 404, and the reader is better served by the
// plain word.
//
// keep(target, alias) -> should this link survive? (alias is null when there is none)
export function stripDeadLinks(md, keep) {
  if (!md || md.indexOf("[[") < 0) return { md, stripped: [] }
  const stripped = []
  const out = String(md).replace(WIKILINK_RE, (m, target, anchor, pipe, alias) => {
    if (keep(target, pipe ? alias : null)) return m
    stripped.push(target)
    return pipe ? alias : target
  })
  return { md: out, stripped }
}
