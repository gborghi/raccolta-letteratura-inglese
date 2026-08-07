// Preprocess the Obsidian "Knowledge Graph" (English literature) vault into Quartz content.
// - copies notes into ./content
// - strips wikilinks to unpublished Authors/* full-text + section files (keeps the label as text)
// - builds ./quartz/static/index.json consumed by the works-table + faceted search renderers
// - generates an editorial home page (index.md), the works table page (opere.md),
//   and the faceted search page (cerca.md)
import { promises as fs } from "node:fs"
import { readFileSync, existsSync } from "node:fs"
import path from "node:path"
import matter from "gray-matter"
import { fileURLToPath } from "node:url"
import { execSync } from "node:child_process"
import zlib from "node:zlib"
import { classifyUnit } from "./preprocess-classify.mjs"
import { buildLinkIndex, resolveWikilinks, stripDeadLinks } from "./preprocess-links.mjs"

// ---- per-work readability (prose only) ----------------------------------------
const POETRY_FORMS = new Set(["ballad","narrative_poem","lyric","sonnet","shakespearean_sonnet","petrarchan_sonnet","ode","pindaric_ode","elegy","epic","mock_epic","free_verse","blank_verse","heroic_couplet","hexameter_verse","conversation_poem","comic_verse_song","dirge","hymn","litany","inscription","ottava_rima","rhyme_royal","spenserian_stanza","terza_rima","verse_epistle","poem_sequence","riddle","epigram","fragment","dramatic_monologue"])
const THEATRE_FORMS = new Set(["comedy","tragedy","history_play","problem_play","romance_play","verse_drama","tragicomedy","masque","melodrama"])
function nSyll(w) {
  w = w.toLowerCase().replace(/[^a-z]/g, "")
  if (!w) return 0
  if (w.length <= 3) return 1
  w = w.replace(/(?:[^laeiouy]es|ed|[^laeiouy]e)$/, "").replace(/^y/, "")
  const m = w.match(/[aeiouy]{1,2}/g)
  return Math.max(1, m ? m.length : 0)
}
// The same work's full text is scored up to 3× (index rec, work-page box,
// publishUnits). Memoize on a cheap content key so the syllable scan runs once.
const _readabilityCache = new Map()
function readabilityOf(text) {
  const key = text.length + "\u0000" + text.slice(0, 48) + text.slice(-48)
  if (_readabilityCache.has(key)) return _readabilityCache.get(key)
  const r = _computeReadability(text)
  _readabilityCache.set(key, r)
  return r
}
function _computeReadability(text) {
  const words = text.match(/[a-zA-Z']+/g) || []
  const n = words.length
  if (n < 200) return null // too short to be meaningful
  const sents = Math.max(1, text.split(/[.!?]+/).filter((s) => /[a-zA-Z]/.test(s)).length)
  let syl = 0, cplx = 0
  for (const w of words) { const s = nSyll(w); syl += s; if (s >= 3) cplx++ }
  const W = n / sents, Sy = syl / n
  return {
    flesch: +(206.835 - 1.015 * W - 84.6 * Sy).toFixed(1),
    fk: +(0.39 * W + 11.8 * Sy - 15.59).toFixed(1),
    fog: +(0.4 * (W + (100 * cplx) / n)).toFixed(1),
    cplx: Math.round((100 * cplx) / n),
    wps: +W.toFixed(1),
  }
}
function isProseWork(data, fullText) {
  const forms = (data.tags || []).filter((t) => typeof t === "string" && t.startsWith("form/")).map((t) => t.slice(5))
  if (forms.some((f) => POETRY_FORMS.has(f) || THEATRE_FORMS.has(f))) return false
  const lines = fullText.split("\n").filter((l) => l.trim())
  if (lines.length) {
    const hb = lines.filter((l) => /\s\s\r?$/.test(l)).length / lines.length
    if (hb > 0.4) return false // verse: hard line-breaks
  }
  return true
}
function readabilityBox(r) {
  const cell = (v, l) => `<span style="display:inline-block;margin:0 .5rem"><b style="font-size:1.05em">${v}</b> <span style="color:var(--gray,#888);font-size:.8em">${l}</span></span>`
  return `\n<div class="work-readability" style="border:1px solid var(--lightgray,#e5e5e5);border-radius:8px;padding:.5rem .7rem;margin:.7rem 0;font-size:.9rem">` +
    `<span style="color:var(--gray,#888);text-transform:uppercase;font-size:.72rem;letter-spacing:.03em;margin-right:.4rem">Readability (prose)</span>` +
    cell(r.flesch, "Flesch ease") + cell(r.fk, "FK grade") + cell(r.fog, "Fog") + cell(r.cplx + "%", "complex") + cell(r.wps, "words/sent") +
    `</div>\n\n`
}

const NUL = String.fromCharCode(0)

// Real work titles keyed by `<author-lower>/<workDir-slug>`, overriding the ugly
// source-filename-derived slug (e.g. chesterton/ortho14 -> "Orthodoxy") for the
// reading-page title and breadcrumb. Absent key -> keep the slug. Optional file.
const WORK_TITLES = (() => {
  try {
    const p = path.join(path.dirname(fileURLToPath(import.meta.url)), "data", "work_titles.json")
    return existsSync(p) ? JSON.parse(readFileSync(p, "utf8")) : {}
  } catch {
    return {}
  }
})()
function workTitle(author, workDir) {
  return WORK_TITLES[`${String(author).toLowerCase()}/${workDir}`] || null
}
// Replace a leading self-reference `[[workslug]]` in a unit H1 with the real work
// title, preserving any " — chapter" suffix and cleaning remaining wikilinks. The
// vault H1 keeps its brackets (correct for Obsidian); only the emitted title changes.
function applyWorkTitle(h1, wt) {
  const s = String(h1)
  if (!/^\s*\[\[/.test(s)) return cleanWikilinks(s) // no leading work link → leave as-is
  return cleanWikilinks(wt + s.replace(/^\s*\[\[[^\]]+\]\]/, ""))
}

// Convert Obsidian wikilink markup to its display text so it never renders as
// literal "[[...]]" on the site: [[target|label]] -> label, [[target]] -> target.
// (The vault keeps the brackets — correct for Obsidian — but a Quartz frontmatter
// `title:` is plain text, so a bracketed title would show the brackets verbatim.)
function cleanWikilinks(s) {
  return String(s)
    .replace(/\[\[([^\]|]+)\|([^\]]+)\]\]/g, "$2")
    .replace(/\[\[([^\]]+)\]\]/g, "$1")
}

// Normalize a string for title comparison: strip wikilink markup, lower-case,
// collapse whitespace, and convert typographic variants (curly quotes →
// straight, em/en dash → hyphen). Wikilink stripping keeps the body-H1 match in
// stripLeadingH1IfMatchesTitle working after the frontmatter title is cleaned.
function normTitle(s) {
  return cleanWikilinks(s)
    .replace(/[‘’]/g, "'")   // curly single quotes → '
    .replace(/[“”]/g, '"')   // curly double quotes → "
    .replace(/[–—]/g, "-")   // en dash, em dash → -
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase()
}

// Remove NotebookLM / export-tool junk separator lines that can leak into
// vault files (e.g. "===== FINE FILE: foo.txt =====", "--- FINE ---").
// These must never appear on the live site.
function stripJunkSeparators(content) {
  return content
    .replace(/^[ \t]*=+[ \t]*(INIZIO|FINE)[ \t]+FILE[ \t]*:.*$/gim, "")
    .replace(/^[ \t]*-{2,}[ \t]*FINE[ \t]*-{2,}[ \t]*$/gim, "")
}

// Strip the first body H1 line if it matches the frontmatter title (after
// typographic normalization). Only the very first non-empty line is checked;
// if it is not a matching H1, the content is returned unchanged.
function stripLeadingH1IfMatchesTitle(content, title) {
  if (!title) return content
  const norm = normTitle(title)
  // Match the first line; allow leading blank lines before the H1.
  return content.replace(/^([ \t]*\r?\n)*[ \t]*#[ \t]+(.+?)[ \t]*\r?\n/, (match, _blanks, h1Text) => {
    if (normTitle(h1Text) === norm) return ""
    return match
  })
}

// Lenient flat-frontmatter parser (the vault has key: value / key: [..] / block lists).
function parseFrontmatter(raw) {
  raw = raw.split(NUL).join("")
  const m = raw.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/)
  if (!m) return { data: {}, content: raw }
  const data = {}
  const lines = m[1].split(/\r?\n/)
  let i = 0
  while (i < lines.length) {
    const line = lines[i]
    const kv = line.match(/^(\w[\w.-]*):\s?(.*)$/)
    if (!kv) {
      i++
      continue
    }
    const key = kv[1]
    let v = kv[2].trim()
    if (v === "") {
      // possible block list ("tags:\n  - a\n  - b")
      const arr = []
      let j = i + 1
      while (j < lines.length && /^\s+-\s+/.test(lines[j])) {
        arr.push(lines[j].replace(/^\s+-\s+/, "").trim().replace(/^["']|["']$/g, ""))
        j++
      }
      if (arr.length) {
        data[key] = arr
        i = j
        continue
      }
      data[key] = ""
      i++
      continue
    }
    if (v.startsWith("[") && v.endsWith("]")) {
      data[key] = v
        .slice(1, -1)
        .split(",")
        .map((x) => x.trim().replace(/^["']|["']$/g, ""))
        .filter(Boolean)
    } else {
      if (
        (v.startsWith('"') && v.endsWith('"') && v.length > 1) ||
        (v.startsWith("'") && v.endsWith("'") && v.length > 1)
      ) {
        v = v.slice(1, -1)
      }
      data[key] = v
    }
    i++
  }
  return { data, content: m[2] }
}

// All paths derive from this file's own location, so the build runs from any cwd
// and on any machine: <repo parent>/quartz-eng-lit/preprocess.mjs -> vault is the
// sibling VaultEnglish/.
const ROOT = path.dirname(fileURLToPath(import.meta.url))
const VAULT_ROOT = path.resolve(ROOT, "..", "VaultEnglish")
const VAULT = path.join(VAULT_ROOT, "Knowledge Graph")
const AUTHORS_DIR = path.join(VAULT_ROOT, "Authors")
// Authors fully excluded from the PUBLIC site (e.g. still under copyright).
// Their work pages, full text, atomized units and index rows are all dropped.
const EXCLUDE_AUTHORS = new Set(["Hemingway"])
const CONTENT = path.join(ROOT, "content")
const DATA = path.join(ROOT, "data")

// Re-stamp content/ as Dropbox-ignored after each regen — main() recreates the dir,
// which drops any prior flag. content/ stays git-tracked (git syncs it to CI); this only
// stops Dropbox cloud-syncing the thousands of generated files. Dropbox reads the flag
// from an NTFS alternate data stream on Windows and an xattr on macOS. Best-effort:
// never fail the build.
async function markDropboxIgnored(dir) {
  try {
    if (process.platform === "win32") {
      await fs.writeFile(`${dir}:com.dropbox.ignored`, "1")
    } else if (process.platform === "darwin") {
      // BOTH flags, as sync-and-build.sh already does: the current File Provider engine
      // under ~/Library/CloudStorage/Dropbox honors only com.apple.fileprovider.ignore#P,
      // the old sync engine only com.dropbox.ignored. Stamping the legacy one alone left
      // content/ syncing and Dropbox laid 1554 "Copia in conflitto" files into it.
      execSync("xattr -w 'com.apple.fileprovider.ignore#P' 1 " + JSON.stringify(dir), { stdio: "ignore" })
      execSync("xattr -w com.dropbox.ignored 1 " + JSON.stringify(dir), { stdio: "ignore" })
    }
  } catch {}
}
// Where atomized excerpts / play scenes / long-poem sections get published.
const TESTI_REL = "Testi"
const STATIC_JSON = path.join(ROOT, "quartz", "static", "index.json")
// Leaf-fragment rows (~15k tagged leaf atoms not already a subwork rec) used to be
// appended onto STATIC_JSON, ballooning it 2.37MB -> 9.9MB even though the works-only
// table (/opere) never reads them. Sharded out here; only by-tag/faceted consumers
// (cerca.inline.ts) lazy-fetch this on first tag/search interaction.
const LEAF_JSON = path.join(ROOT, "quartz", "static", "index_leaf.json")
const KW_JSON = path.join(ROOT, "quartz", "static", "works_kw.json")
// LLM-extracted per-chapter tags (characters/themes/plot), committed source of
// truth for #17 chapter interlinking. Optional: absent on a fresh checkout.
const CHAPTER_TAGS = path.join(ROOT, "data", "chapter_tags.json")

// --- Reading-page SPA restructure (file-count reduction for Cloudflare Pages) ---
// When SPA=1, a work's atomized reading units are emitted as ONE markdown page: each
// atom's body (bilingual, unchanged) is concatenated behind an inline
// `<span class="atom-split" data-atom …>` marker. Quartz renders the whole page
// normally (wikilinks, prose, translations — full text stays in the HTML, so SEO is
// preserved); atomRouter.inline.ts then partitions the rendered DOM at those markers
// into sections and shows one at a time (the proven qlang DOM-partition pattern).
// Cuts ~19.8k pages -> ~460, clearing Cloudflare Pages' 20k-file cap. Every atom
// stays deep-linkable at <workSlug>#<atomId>. Default OFF until the path is verified.
const SPA = process.env.SPA === "1"

const STOPWORDS = new Set((
  // English
  "a about an and are as at be been but by can did do does each for from had has have he her here him his how i if in into is it its no not of on one or our so that the their them then there these they this to too two up was we were what when where which who will with you your " +
  // Italian
  "ad ai al alla alle allo agli anche ancora avere aveva avevano che chi ci coi col come con cosa cui da dai dal dalla dalle dallo degli dei del della delle dello di dove due ecco ed era erano essere fa fare fino fra gli ha hai hanno ho il in io la le lei li lo loro ma me mentre mi mia mie miei mio ne negli nei nel nella nelle nello no noi non nostra nostre nostri nostro o od ogni ognuno oppure per perche perché piu più po poi puo può qual quale quali quando quanta quante quanti quanto quasi quel quella quelle quelli quello questa queste questi questo qui se sei senza si sia siamo siete solo sono sopra sotto sta stata state stati stato su sua sue sui sul sulla sulle sullo suo suoi tra tre tu tua tue tuo tuoi tutta tutte tutti tutto un una uno vi voi"
).split(/\s+/).filter(Boolean))

// Per-doc term frequencies (Map<word,count>) for the content-search indexes.
function keywordCounts(content) {
  const cleaned = content
    .replace(/\[\[(?:[^\]|]+\|)?([^\]]+)\]\]/g, " $1 ") // keep wikilink label
    .replace(/\[[^\]]*\]\([^)]*\)/g, " ")      // md links
    .replace(/[`*_>#|]/g, " ")                  // md syntax
    .toLowerCase()
    .replace(/[^a-zà-ÿ\s]/g, " ")               // letters only
  const counts = new Map()
  for (const w of cleaned.split(/\s+/)) {
    if (w.length < 3 || STOPWORDS.has(w)) continue
    counts.set(w, (counts.get(w) || 0) + 1)
  }
  return counts
}

// Rank each doc's terms by TF-IDF across the corpus and keep the top-N as a
// space-joined string (the brani/cerca content-search format). Computed inline so
// preprocess writes the trimmed index directly — no write-full-vocab-then-re-read
// pass (the old scripts/trim-kw-index.mjs, now removed).
function topTfIdf(countsByKey, N = 40) {
  const df = new Map()
  for (const counts of Object.values(countsByKey))
    for (const w of counts.keys()) df.set(w, (df.get(w) || 0) + 1)
  const total = Object.keys(countsByKey).length || 1
  const out = {}
  for (const [key, counts] of Object.entries(countsByKey)) {
    if (!counts.size) { out[key] = ""; continue }
    const scored = []
    for (const [w, c] of counts) {
      const idf = Math.log(total / (df.get(w) || 1))
      if (idf <= 0) continue
      scored.push([w, c * idf])
    }
    scored.sort((a, b) => b[1] - a[1])
    out[key] = scored.slice(0, N).map((x) => x[0]).join(" ")
  }
  return out
}

// Replicate Quartz's slugifyFilePath (quartz/util/path.ts: sluggify)
function sluggify(s) {
  return s
    .split("/")
    .map((seg) =>
      seg
        .replace(/\s/g, "-")
        .replace(/&/g, "-and-")
        .replace(/%/g, "-percent")
        .replace(/\?/g, "")
        .replace(/#/g, "")
        // v5: @quartz-community/utils lowercases wikilink slugs while core emits
        // pages at the (lowercased) file path. Lowercase here so every href we emit
        // matches the lowercased content filenames (see the dest .toLowerCase() below).
        .toLowerCase(),
    )
    .join("/")
    .replace(/\/$/, "")
}
function slugFromRel(rel) {
  const noExt = rel.replace(/\.md$/, "").split(path.sep).join("/")
  return sluggify(noExt)
}
function esc(s) {
  return String(s).replace(/[&<>"]/g, (c) =>
    c === "&" ? "&amp;" : c === "<" ? "&lt;" : c === ">" ? "&gt;" : "&quot;",
  )
}

const AXES = [
  ["topos", "topoi"],
  ["archetype", "archetypes"],
  ["motif", "motifs"],
  ["concept", "concepts"],
  ["form", "forms"],
  ["histref", "histrefs"],
  ["setting", "settings"],
  ["character", "characters"],
]

// Split a flat "axis/slug" tag list (a leaf atom's own frontmatter `tags:`) into the
// same per-axis field buckets as the PASS-1 work-note scan, plus a bare-slug
// `clusters` bucket for any `cluster/<slug>` tags. Mirrors the AXES loop below.
function axesFromFlatTags(tags) {
  const out = {}
  for (const [prefix, field] of AXES)
    out[field] = tags.filter((t) => t.startsWith(prefix + "/")).map((t) => t.slice(prefix.length + 1))
  out.clusters = tags.filter((t) => t.startsWith("cluster/")).map((t) => t.slice("cluster/".length))
  return out
}
// Reverse of axesFromFlatTags: rebuild the flat "axis/slug" list from axis buckets
// (used for the atom-split data-tags attribute + atomSearch tags field).
function flatTagsFromAxes(axesObj) {
  const flat = []
  for (const [prefix, field] of AXES)
    for (const slug of axesObj[field] || []) flat.push(`${prefix}/${slug}`)
  for (const slug of axesObj.clusters || []) flat.push(`cluster/${slug}`)
  return flat
}
// Lowercase / non-alnum-collapse a single cluster-scalar token into a tag-safe slug.
function slugifyToken(s) {
  return String(s).toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "")
}
// A work note's `cluster: "A · B · C"` scalar (U+00B7-separated) -> bare cluster-axis
// slugs, e.g. ["a", "b", "c"]. Same bucket shape as the other axis arrays.
function deriveClusters(clusterScalar) {
  if (!clusterScalar) return []
  return String(clusterScalar).split(" · ").map(slugifyToken).filter(Boolean)
}

// Pull the [!abstract] callout body out of a work note as a plain-text summary.
function extractSummary(content) {
  const lines = content.split(/\r?\n/)
  let i = lines.findIndex((l) => /^>\s*\[!abstract\]/.test(l))
  if (i < 0) return ""
  const out = []
  for (let j = i + 1; j < lines.length; j++) {
    if (/^>/.test(lines[j])) out.push(lines[j].replace(/^>\s?/, ""))
    else break
  }
  return out.join(" ").replace(/\s+/g, " ").trim()
}

const AXIS_FOLDERS = {
  Topoi: "topos",
  Archetypes: "archetype",
  Motifs: "motif",
  Concepts: "concept",
  Forms: "form",
  "Historical References": "histref",
  Settings: "setting",
  Characters: "character",
  Clusters: "cluster",
}

// Transform note body: rewrite wikilinks that point at Authors/* unit files
// (atomized chapters/excerpts, play scenes, long-poem sections) to the published
// "Testi/..." slug so the links resolve. unitHref maps an Authors/... path
// (with or without .md) to its published slug. Anything not in the map (e.g. a
// stray Authors/_raw reference) falls back to plain text so no dead link remains.
function transform(content, unitHref) {
  const resolve = (target) => {
    const t = target.replace(/\.md$/, "")
    return unitHref.get(t) || unitHref.get(target) || null
  }
  // [[Authors/...|Label]]
  content = content.replace(/\[\[(Authors\/[^\]|#]+)(?:#[^\]|]*)?\|([^\]]+)\]\]/g, (_m, tgt, label) => {
    const href = resolve(tgt.trim())
    return href ? `[${label}](/${href})` : label
  })
  // [[Authors/...]]
  content = content.replace(/\[\[(Authors\/[^\]|#]+)(?:#[^\]|]*)?\]\]/g, (_m, tgt) => {
    const href = resolve(tgt.trim())
    const seg = tgt.split("/").pop().replace(/\.md$/, "")
    return href ? `[${seg}](/${href})` : seg
  })
  // Remove wikilinks to excluded-author work pages (e.g. "[[Title (Hemingway)]]")
  // so no dead links remain, plus their "**Hemingway**" group header + the now
  // empty bullet lines under it.
  for (const ex of EXCLUDE_AUTHORS) {
    // bullet list items that are solely a link to an excluded work -> drop the line
    const bulletRe = new RegExp(`^[ \\t]*[-*][ \\t]*\\[\\[[^\\]]*\\(${ex}\\)(?:\\|[^\\]]*)?\\]\\][ \\t]*$\\n?`, "gm")
    content = content.replace(bulletRe, "")
    // any remaining inline wikilink to an excluded work -> keep label as plain text
    const inlineRe = new RegExp(`\\[\\[([^\\]|]*\\(${ex}\\))(?:\\|([^\\]]*))?\\]\\]`, "g")
    content = content.replace(inlineRe, (_m, tgt, label) => label || tgt)
    // a bold author header line ("**Hemingway**") left with no items under it
    const headerRe = new RegExp(`^[ \\t]*\\*\\*${ex}\\*\\*[ \\t]*$\\n?`, "gm")
    content = content.replace(headerRe, "")
  }
  return content
}

async function walk(dir, base = dir, out = []) {
  for (const ent of await fs.readdir(dir, { withFileTypes: true })) {
    const full = path.join(dir, ent.name)
    if (ent.isDirectory()) await walk(full, base, out)
    // Skip ".it.md" siblings: these are Italian reading copies kept in the vault
    // for Obsidian. The site's Italian pages are emitted separately from the
    // translation store, so preprocess must NOT publish vault .it.md as units.
    else if (ent.name.endsWith(".md") && !ent.name.endsWith(".it.md"))
      out.push(path.relative(base, full))
  }
  return out
}

// Strip frontmatter (if any) and pull a title from the first H1, else fall back.
function splitUnit(raw) {
  raw = raw.split(NUL).join("")
  let body = raw
  const fm = raw.match(/^---\r?\n[\s\S]*?\r?\n---\r?\n?([\s\S]*)$/)
  if (fm) body = fm[1]
  const h1 = body.match(/^\s*#\s+(.+?)\s*$/m)
  const title = h1 ? h1[1].trim() : ""
  return { body, title }
}

// Normalize a work-dir / title to a comparable key (case/article/punct-insensitive).
function normWorkKey(s) {
  return String(s)
    .toLowerCase()
    .replace(/\.md$/, "")
    .replace(/[_\-]+/g, " ")
    .replace(/\b(the|a|an)\b/g, " ")
    .replace(/[^a-z0-9]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
}


function prettyFromFilename(name) {
  return name
    .replace(/\.md$/, "")
    .replace(/_/g, " ")
    .replace(/\s+/g, " ")
    .trim()
}

// A roman numeral like "II"/"IV" gets title-cased to "Ii"/"Iv" when the atomizer
// derives a filename/heading (reads on the site as "li"/"lv"). Re-uppercase any
// token that is a valid roman numeral of length >= 2 (a lone "I" stays — usually
// the pronoun; "Mix" is the only realistic English false positive, not a chapter).
const ROMAN_RE = /^M{0,4}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$/i
function fixRoman(s) {
  return String(s).replace(/[A-Za-z]+/g, (t) =>
    t.length > 1 && ROMAN_RE.test(t) ? t.toUpperCase() : t,
  )
}

// Chapter/section display label from a unit filename: drop the structural
// "Story_04"/"Chapter_02"/… ordinal prefix (redundant once grouped under the
// chapter) and fix title-cased roman numerals. Falls back to the raw pretty name
// if stripping would leave nothing (an unnamed "Story 12").
function chapterLabel(name) {
  const pretty = prettyFromFilename(name)
  const stripped = pretty.replace(
    /^(Story|Chapter|Section|Scene|Part|Canto|Book|Act|Letter)\s+\d+\s+/i,
    "",
  )
  return fixRoman(stripped || pretty)
}

// Neutralize markdown code artifacts in raw literary prose:
//   • Gutenberg paragraph indents (the first line of every paragraph is indented
//     ≥4 spaces) otherwise render as <pre><code> boxes — left-trim leading space.
//   • Gutenberg uses a backtick as an opening single quote (`word') — convert to a
//     real curly quote so it never pairs into inline <code>.
// These corpora contain no genuine code, so both transforms are safe.
function normalizeProse(s) {
  return String(s)
    .replace(/^[ \t]+/gm, "")
    .replace(/`/g, "‘")
}

// Drop a redundant leading self-referential H1 ("# [[workslug]] — Chapter"): the
// reader shows the title in its crumb/TOC, so the in-pane heading only repeats it
// (and would render the bare "[[slug]]" self-link).
function stripLeadingSelfH1(content) {
  return content.replace(/^([ \t]*\r?\n)*[ \t]*#[ \t]+\[\[[^\]]*\]\][^\n]*\r?\n/, "")
}

// Corpus-wide per-leaf-atom search (data/atom_search.json, SPA only): reduce an
// atom's markdown body to plain searchable text — strip html markers (atom-split /
// qlang-split spans, nav), collapse wikilinks to their display label, drop MD
// syntax chars, collapse whitespace.
function plainForSearch(md) {
  return String(md || "")
    .replace(/<[^>]+>/g, " ")
    .replace(/\[\[([^\]|]+\|)?([^\]]+)\]\]/g, "$2")
    .replace(/[#>*_`~]/g, " ")
    .replace(/\s+/g, " ")
    .trim()
}

// classifyUnit now lives in ./preprocess-classify.mjs (imported above) so it can be
// unit-tested without triggering this file's top-level main().

// Publish all atomized excerpts, play scenes and long-poem sections as pages.
// Returns { unitHref, excerpts } where unitHref maps "Authors/.../x[.md]" -> slug,
// and excerpts is the excerpt-level index for the Brani page.
// Merge English + Italian into one page (the OlimpiadiMatematica/qlang pattern):
// the default (EN) body, a hidden `<span class="qlang-split">` marker, then the
// translated (IT) body — all plain markdown so it renders normally. qlang.inline.ts
// partitions the article DOM at the marker and toggles language client-side (no
// navigation, no server call).
// SPA mode: lift an atom's translated body into a section by removing the page
// chrome preprocess bakes into a standalone unit page (nav, in-section child list,
// qlang switch, readability box, and the leading "# [[..]]" H1), leaving only text.
// The EN side needs no stripping — it is built from the clean source body directly.
// Escape the alias-pipe of wikilinks that sit inside a markdown table row, so the GFM
// tokenizer does not read `[[Witch|STREGA]]`'s pipe as a column divider — which splits the
// cell in half and leaves the link malformed, rendering as literal "[[Witch" text. The
// backslash is invisible to Quartz's wikilink regex, so the TARGET is untouched (this is a
// display-time escape only; the vault keeps the unescaped form, where an escaped pipe would
// change the link target).
//
// The EN side has done this since the plays were added. The IT side needs it too, and did
// not have it: while every translation was prose there were no tables to break.
//
// Idempotent: an already-escaped `[[X\|y]]` (the form resolveWikilinks emits when it
// adds an alias inside a table row) matches too and comes back unchanged, instead of
// growing a second backslash.
function escapeTableAliasPipes(s) {
  return s.replace(/^\|.*$/gm, (row) =>
    row.replace(/\[\[([^\]|]+?)\\?\|([^\]]*)\]\]/g, "[[$1\\|$2]]"),
  )
}

function stripUnitChrome(s) {
  return s
    .replace(/<div class="qlang-switch"[^>]*><\/div>/g, "")
    .replace(/<nav class="excerpt-nav">[\s\S]*?<\/nav>/g, "")
    .replace(/<nav class="excerpt-children">[\s\S]*?<\/nav>/g, "")
    .replace(/<div class="work-readability"[\s\S]*?<\/div>/g, "")
    .replace(/^#\s*\[\[[^\]]*\]\].*$/gm, "")
    .trim()
}

// SPA: map an old per-atom slug (testi/author/sub/work/chapter[/part]) to its new
// fragment url (testi/author/sub/work#chapter[--part]). First 4 segments are the
// work page; the rest is the atom id. Used to repoint #17 chapter interlinks.
function slugToFrag(s) {
  const p = s.split("/")
  return p.length > 4 ? p.slice(0, 4).join("/") + "#" + p.slice(4).join("--") : s
}

function bilingualBody(en, it) {
  return (
    `<div class="qlang-switch" data-default="en"></div>\n\n` +
    en +
    `\n\n<span class="qlang-split" data-lang="it"></span>\n\n` +
    it
  )
}

// resolveLinks(md, ctx) rewrites bare wikilinks to full slugs (see preprocess-links.mjs);
// it is built in main() from the PASS-1 note scan, so it arrives as a parameter.
async function publishUnits(
  rawSourceToWork,
  translations = new Map(),
  sourceTagAxes = new Map(),
  resolveLinks = (md) => md,
) {
  const unitHref = new Map()
  const excerpts = []
  const excerptsKw = {}
  const readHrefByWork = new Map() // work-node href -> reading-page (SPA) slug, so the
  // works table + search + emblems link to the READER (atoms + EN/IT toggle), not the
  // bare KG metadata node.
  const workUnits = new Map() // work href -> [{ slug, title, relU }] reading units (TOC)
  const workContainers = new Map() // work href -> { slug, title, relU } full-text page (single-essay fallback)
  const workParts = new Map() // work href -> [{ slug, order, relU }] flat "part_NN" excerpts (no chapter layer)
  const atomMeta = new Map() // SPA: frag href -> { title, work, workHref } for EVERY unit (powers #17 chapter cards)
  const atomSourceToFrag = new Map() // "Authors/<Author>/<sub>/<relU>" -> "workSlug#atomId" (subwork href resolution)
  const atomSearch = {} // SPA: frag (or bare reading slug for atomless works) -> { title, work, text }, corpus-wide search
  const unitPlainText = new Map() // SPA: reading slug (workSlug) -> plain text of its intro unit, for atomless works
  const introTrim = { trimmed: 0, empty: 0, missed: 0, saved: 0 } // intro atom cut back to the container's head
  const leafAtoms = [] // SPA: one entry per emitted leaf atom -> data/leaf_atoms.json (tagging-run manifest)
  const leafFragRows = [] // SPA: synthetic works-index rows for tagged leaf atoms not already covered by a subwork rec
  let copied = 0

  const authors = await fs.readdir(AUTHORS_DIR, { withFileTypes: true })
  for (const adir of authors) {
    if (!adir.isDirectory()) continue
    const author = adir.name
    // Display author: folder names may use underscores (e.g. "Conan_Doyle"); the work
    // notes and wheel use the spaced form ("Conan Doyle"), so units must match.
    const authorName = author.replace(/_/g, " ")
    if (EXCLUDE_AUTHORS.has(author)) continue // excluded from public site
    for (const sub of ["Atomized", "Plays", "Long"]) {
      const subRoot = path.join(AUTHORS_DIR, author, sub)
      let stat
      try {
        stat = await fs.stat(subRoot)
      } catch {
        continue
      }
      if (!stat.isDirectory()) continue
      const rels = await walk(subRoot)
      // Group units by their work directory (first path segment under sub) so we
      // can compute prev/next ordering and a parent-work link per work.
      const byWork = new Map()
      for (const rel of rels) {
        const relU = rel.replace(/\\/g, "/")
        const segs = relU.split("/")
        const workDir = segs[0] // e.g. A_Childs_History_of_England or play slug
        if (!byWork.has(workDir)) byWork.set(workDir, [])
        byWork.get(workDir).push(relU)
      }

      for (const [workDir, relList] of byWork) {
        // Resolve the parent work note (by raw-source basename, else normalized).
        // Author-qualified first (see addKey): same-named cluster dirs across poets.
        const aKey = authorName.toLowerCase()
        const parentWorkHref =
          rawSourceToWork.get(`${aKey}|${workDir}`) ||
          rawSourceToWork.get(`${aKey}|${normWorkKey(workDir)}`) ||
          rawSourceToWork.get(workDir) ||
          rawSourceToWork.get(normWorkKey(workDir)) ||
          null
        // Order units: the work-level file first, then by (path, order).
        const items = relList.map((relU) => {
          const segs = relU.split("/")
          const fileName = segs[segs.length - 1]
          const { unitType, order } = classifyUnit(segs, fileName)
          const slug = sluggify(`${TESTI_REL}/${author}/${sub}/${relU}`.replace(/\.md$/, ""))
          return { relU, segs, fileName, unitType, order, slug }
        })
        items.sort((a, b) => {
          if (a.unitType === "work" && b.unitType !== "work") return -1
          if (b.unitType === "work" && a.unitType !== "work") return 1
          // Order by the full relative path with NUMERIC collation, so chapters and their parts
          // interleave in reading order regardless of granularity. Keying on the parent directory
          // (the old approach) grouped whole-chapter atoms — short chapters with no subparts —
          // ahead of every subpart atom, which put The Everlasting Man's two appendices (Ch18/19,
          // unsplit) right after Ch01, before Ch02. relU numeric compare fixes mixed granularity
          // and is identical to the old result for uniform works.
          return a.relU.localeCompare(b.relU, undefined, { numeric: true })
        })

        // Register hrefs first (so prev/next + link rewrite can see all of them).
        for (const it of items) {
          const authPath = `Authors/${author}/${sub}/${it.relU}`
          unitHref.set(authPath, it.slug)
          unitHref.set(authPath.replace(/\.md$/, ""), it.slug)
        }

        // Sequence for prev/next excludes the work-level container file.
        const seq = items.filter((it) => it.unitType !== "work")

        // Parent/child hierarchy from slugs: a unit whose slug is another unit's
        // slug + "/…" is that unit's child (e.g. chapter_02 -> chapter_02/part_01).
        // Powers the crumb chain (part › chapter › work) and the in-page child list
        // (a chapter links down to each of its parts, and vice-versa).
        const bySlug = new Map(items.map((it) => [it.slug, it]))
        const childrenOf = new Map()
        for (const it of items) {
          const psl = it.slug.split("/").slice(0, -1).join("/")
          const parent = bySlug.get(psl)
          if (parent && parent.slug !== it.slug) {
            it.parentItem = parent
            if (!childrenOf.has(parent.slug)) childrenOf.set(parent.slug, [])
            childrenOf.get(parent.slug).push(it)
          }
        }
        const childLabel = (k) =>
          k.unitType === "excerpt" ? `Part ${k.order}` : prettyFromFilename(k.fileName)

        // ---- SPA mode: emit ONE page per work (atoms behind atom-split markers) ----
        if (SPA) {
          const workSlug = sluggify(`${TESTI_REL}/${author}/${sub}/${workDir}`)
          if (parentWorkHref) readHrefByWork.set(parentWorkHref, workSlug)
          const wt = workTitle(author, workDir)
          const workLabel = wt || workDir.replace(/_/g, " ")
          // Page title: prefer the work-root H1 (real, punctuated poem/essay title)
          // over the raw folder name ("0001 Awake ye muses…") when no WORK_TITLES
          // override exists. Set from the intro unit below; falls back to workLabel.
          let pageTitle = workLabel
          const atomIdOf = (it) =>
            it.slug.slice(workSlug.length + 1).replace(/\//g, "--") || "intro"
          // The work-level file <W>/<W>.md is the concatenation of its leaves PLUS the
          // edition's front matter (title page, illustration list, CONTENTS with the paper
          // edition's page numbers) that no leaf carries. Emitted whole as the "intro" atom
          // it shipped every book a second time on its own reading page — 39% of the reading
          // pages' bytes — and that second copy had no Italian, because the vault translates
          // leaves, not containers. Keep only the head: what precedes the first leaf's first
          // line, which is exactly the part that is NOT already in the leaves.
          // A work with no top-level sections at all (an unatomized essay or poem) IS its
          // work-level file: there is nothing to trim, and headLines stays null.
          //
          // Anchoring on the first section's opening line alone is not enough — "CHAPTER I"
          // occurs three times in Hard_Times (twice in the CONTENTS) and the first hit would
          // cut in the wrong place. So: take every occurrence of that line, keep the one that
          // leaves a tail as long as the sections, and accept it only when the arithmetic is
          // exact or the container's last 30 lines really are the sections' last 30. Anything
          // else keeps the container whole — 230 of 234 are identified, 4 are left alone.
          // splitUnit keeps each section's own "# H1", which the container does not carry:
          // strip it, or the tails can never line up.
          const topSections = items.filter((x) => x.unitType !== "work" && !x.parentItem)
          let headLines = null
          if (topSections.length) {
            const nonBlank = (t) => t.split("\n").map((l) => l.trim()).filter(Boolean)
            const secLines = []
            for (const s of topSections) {
              const abs = path.join(subRoot, s.relU.split("/").join(path.sep))
              const sBody = splitUnit(await fs.readFile(abs, "utf8")).body.replace(/^\s*#[^\n]*\n/, "")
              secLines.push(...nonBlank(sBody))
            }
            const contAbs = path.join(subRoot, `${workDir}/${workDir}.md`.split("/").join(path.sep))
            const contBody = await fs.readFile(contAbs, "utf8").catch(() => null)
            if (contBody !== null && secLines.length) {
              const cont = nonBlank(splitUnit(contBody).body)
              const k = Math.min(30, secLines.length)
              const tailOk =
                cont.length >= k && cont.slice(-k).every((l, i) => l === secLines[secLines.length - k + i])
              let best = -1
              let bestErr = Infinity
              for (let p = 0; p < cont.length; p++) {
                if (cont[p] !== secLines[0]) continue
                const err = Math.abs(cont.length - p - secLines.length)
                if (err < bestErr) { bestErr = err; best = p }
              }
              if (best > 0 && (bestErr === 0 || (tailOk && bestErr <= Math.max(3, 0.02 * secLines.length))))
                headLines = best
            }
          }
          const blocks = []
          const workDirFrags = [] // atomSearch keys emitted for THIS workDir, so a
          // single-unit work (exactly one leaf atom = the whole work) can be
          // re-keyed below to its bare reading slug, matching readHrefByWork /
          // rec.readHref (the canonical link every other index uses for it).
          for (const it of items) {
            const atomId = atomIdOf(it)
            const authPath = `Authors/${author}/${sub}/${it.relU}`
            const frag = `${workSlug}#${atomId}`
            atomSourceToFrag.set(authPath, frag)
            // every unit — leaf, aggregate chapter, or work root — resolves into the
            // one work page (aggregates land on their own anchor; the router maps a
            // chapter id to its first leaf).
            unitHref.set(authPath, frag)
            unitHref.set(authPath.replace(/\.md$/, ""), frag)
            atomMeta.set(frag, { title: prettyFromFilename(it.fileName), work: workLabel, workHref: parentWorkHref || "" })
            const isIntro = it.unitType === "work"
            const isLeaf = !isIntro && !childrenOf.has(it.slug)
            if (!isIntro && !isLeaf) continue // aggregate chapter -> TOC grouping only

            const srcAbs = path.join(subRoot, it.relU.split("/").join(path.sep))
            const raw = await fs.readFile(srcAbs, "utf8")
            let { body, title: h1Title } = splitUnit(raw)
            if (isIntro) {
              if (headLines === null) introTrim.missed++ // container is not head + sections: leave it whole
              else {
                // cut at the raw line that holds the (headLines+1)-th non-blank line
                const lines = body.split("\n")
                let seen = 0
                let at = lines.length
                for (let i = 0; i < lines.length; i++) {
                  if (!lines[i].trim()) continue
                  if (seen++ === headLines) { at = i; break }
                }
                const head = lines.slice(0, at).join("\n").replace(/\n+$/, "")
                introTrim.saved += body.length - head.length
                introTrim.trimmed++
                body = head
              }
            }
            const title = fixRoman(
              (wt ? applyWorkTitle(h1Title, wt) : cleanWikilinks(h1Title)) ||
                prettyFromFilename(it.fileName),
            )
            atomMeta.set(frag, { title, work: workLabel, workHref: parentWorkHref || "" })
            if (isIntro && !wt) pageTitle = title
            const chapLabel = it.parentItem
              ? chapterLabel(it.parentItem.fileName)
              : isIntro
                ? ""
                : chapterLabel(it.fileName)
            let enBody = resolveLinks(
              normalizeProse(
                stripLeadingSelfH1(stripLeadingH1IfMatchesTitle(stripJunkSeparators(body), title)),
              ),
              { author: authorName },
            )
            // plays: EN-only dialogue → English table header (source vault bakes Italian)
            enBody = enBody.replace(/^\|\s*Chi parla\s*\|\s*Battuta\s*\|$/gm, "| Speaker | Line |")
            // plays: escape the alias-pipe of wikilinks inside dialogue-table rows so the GFM
            // table tokenizer does not read it as a column divider (wikilinkRegex allows \| — target intact)
            enBody = escapeTableAliasPipes(enBody)
            const atomText = plainForSearch(enBody)

            // ---- Phase-2 leaf-tag join: leaf's own frontmatter tags (source #2,
            // wins when present) else the subwork work-note's tags via sourceTagAxes
            // (source #1, e.g. the 154 sonnets). Neither exists for most atoms yet —
            // that's expected before the tagging run.
            const { data: atomFm } = parseFrontmatter(raw)
            const leafTags = Array.isArray(atomFm.tags) ? atomFm.tags : atomFm.tags ? [atomFm.tags] : []
            const tagAxes = leafTags.length ? axesFromFlatTags(leafTags) : sourceTagAxes.get(authPath) || null
            const flatTags = tagAxes ? flatTagsFromAxes(tagAxes) : []
            const hasTags = flatTags.length > 0

            atomSearch[frag] = { title, work: workLabel, text: atomText, ...(hasTags ? { tags: flatTags } : {}) }
            workDirFrags.push(frag)
            if (isIntro) unitPlainText.set(workSlug, atomText)
            const kind = isIntro ? "intro" : it.unitType
            let block =
              `\n\n<span class="atom-split" data-atom="${esc(atomId)}" ` +
              `data-title="${esc(title)}" data-chapter="${esc(chapLabel)}" data-kind="${kind}"` +
              (hasTags ? ` data-tags="${esc(flatTags.join(","))}"` : "") +
              `></span>\n\n` +
              enBody

            leafAtoms.push({
              frag, source: authPath, work: workLabel, author: authorName,
              unitType: kind, hasTags, len: atomText.length,
            })
            // Emit an index.json fragment row for a tagged leaf that ISN'T already a
            // subwork's source atom (subwork recs get their row via the resolver in
            // main() — sourceTagAxes is keyed by exactly those source paths).
            if (hasTags && !sourceTagAxes.has(authPath)) {
              leafFragRows.push({
                href: frag, title, author: authorName, parentWork: workLabel,
                topoi: tagAxes.topoi, archetypes: tagAxes.archetypes, motifs: tagAxes.motifs,
                concepts: tagAxes.concepts, forms: tagAxes.forms, histrefs: tagAxes.histrefs,
                settings: tagAxes.settings, characters: tagAxes.characters, clusters: tagAxes.clusters,
                // Exclude the cluster axis, matching the work-note nconnections
                // semantics (computed over the 8 non-cluster axes only, see :1062).
                nconnections: flatTags.filter((t) => !t.startsWith("cluster/")).length,
                _leaf: true,
              })
            }
            const unitRel = `${TESTI_REL}/${author}/${sub}/${it.relU}`.toLowerCase()
            const tr = translations.get(unitRel)
            if (tr) {
              const itBody = escapeTableAliasPipes(
                resolveLinks(normalizeProse(stripUnitChrome(tr.body_it || "")), { author: authorName }),
              )
              block += `\n\n<span class="qlang-split" data-lang="it"></span>\n\n` + itBody
            }
            blocks.push(block)

            // indexes (Brani / cerca / #17 / work-note TOC) point at the fragment url
            if (isIntro) {
              if (parentWorkHref) workContainers.set(parentWorkHref, { slug: frag, title, relU: it.relU })
            } else {
              if (parentWorkHref && ["chapter", "scene", "story", "section"].includes(it.unitType)) {
                if (!workUnits.has(parentWorkHref)) workUnits.set(parentWorkHref, [])
                workUnits.get(parentWorkHref).push({ slug: frag, title, relU: it.relU })
              }
              if (parentWorkHref && it.unitType === "excerpt" && !it.parentItem) {
                if (!workParts.has(parentWorkHref)) workParts.set(parentWorkHref, [])
                workParts.get(parentWorkHref).push({ slug: frag, order: it.order, relU: it.relU })
              }
              excerpts.push({
                href: frag, title, author,
                work: workLabel, workHref: parentWorkHref || "",
                unitType: it.unitType, order: it.order,
              })
              const kw = keywordCounts(body)
              if (kw.size) excerptsKw[frag] = kw
            }
          }

          // Single-unit work (exactly one leaf atom emitted): its whole content IS
          // the work, and every other index (readHrefByWork, rec.readHref) points at
          // the bare workSlug, not "workSlug#intro"/"#part_01". Re-key so search
          // results land on the same canonical URL, and Step 2 below doesn't treat
          // it as already covered under a fragment nobody else links to.
          if (workDirFrags.length === 1) {
            const onlyFrag = workDirFrags[0]
            atomSearch[workSlug] = atomSearch[onlyFrag]
            delete atomSearch[onlyFrag]
            unitPlainText.set(workSlug, atomSearch[workSlug].text)
          }

          const fm =
            `---\n` +
            `title: ${JSON.stringify(pageTitle)}\n` +
            `author: ${JSON.stringify(authorName)}\n` +
            `unitType: work\n` +
            (parentWorkHref ? `parentWork: ${JSON.stringify(parentWorkHref)}\n` : "") +
            `tags:\n  - graph/excerpt\n  - author/${author}\n` +
            `---\n\n`
          const mount =
            `<div class="atom-reader" data-work="${esc(workSlug)}" data-author="${esc(authorName)}"` +
            (parentWorkHref ? ` data-workhref="${esc(parentWorkHref)}"` : "") +
            `></div>\n`
          const dest = path.join(CONTENT, `${workSlug}.md`.split("/").join(path.sep))
          await fs.mkdir(path.dirname(dest), { recursive: true })
          await fs.writeFile(dest, fm + mount + blocks.join("\n\n"))
          copied++
          continue // skip the classic per-atom emission for this work
        }

        for (let i = 0; i < items.length; i++) {
          const it = items[i]
          const srcAbs = path.join(subRoot, it.relU.split("/").join(path.sep))
          const raw = await fs.readFile(srcAbs, "utf8")
          const { body, title: h1Title } = splitUnit(raw)
          const wt = workTitle(author, workDir)
          const title =
            (wt ? applyWorkTitle(h1Title, wt) : cleanWikilinks(h1Title)) ||
            prettyFromFilename(it.fileName)

          // Collect reading units (chapters/scenes/stories/sections — not the
          // whole-work container nor paragraph fragments) so the parent work page
          // can render a chapter index. This is the primary way to reach the text
          // now that the Explorer sidebar is off.
          if (parentWorkHref && ["chapter", "scene", "story", "section"].includes(it.unitType)) {
            if (!workUnits.has(parentWorkHref)) workUnits.set(parentWorkHref, [])
            workUnits.get(parentWorkHref).push({ slug: it.slug, title, relU: it.relU })
          }
          // The full-text container (unitType "work", e.g. a single essay atomized
          // only into paragraph fragments) is the reading page for works with no
          // chapters/scenes. Keep it as a fallback so the work note can link to it.
          if (parentWorkHref && it.unitType === "work") {
            workContainers.set(parentWorkHref, { slug: it.slug, title, relU: it.relU })
          }
          // Flat "part_NN" excerpts of a work that has NO chapter layer (their slug
          // parent is a bare "part/" dir, so they have no parentItem). These would
          // otherwise be reachable only as backlinks — collect them so the work page
          // can list them alongside the full text.
          if (parentWorkHref && it.unitType === "excerpt" && !it.parentItem) {
            if (!workParts.has(parentWorkHref)) workParts.set(parentWorkHref, [])
            workParts.get(parentWorkHref).push({ slug: it.slug, order: it.order, relU: it.relU })
          }

          // prev/next within the reading sequence
          let prevHref = "",
            nextHref = "",
            prevTitle = "",
            nextTitle = ""
          if (it.unitType !== "work") {
            const si = seq.indexOf(it)
            if (si > 0) {
              prevHref = "/" + seq[si - 1].slug
              prevTitle = prettyFromFilename(seq[si - 1].fileName)
            }
            if (si >= 0 && si < seq.length - 1) {
              nextHref = "/" + seq[si + 1].slug
              nextTitle = prettyFromFilename(seq[si + 1].fileName)
            }
          }

          // breadcrumb + prev/next nav block
          const crumbLabel = wt || workDir.replace(/_/g, " ")
          const crumbs = []
          if (parentWorkHref) crumbs.push(`<a href="/${parentWorkHref}">${esc(crumbLabel)}</a>`)
          else crumbs.push(esc(crumbLabel))
          // parent chapter/section, so a part breadcrumbs up to its chapter
          if (it.parentItem)
            crumbs.push(
              `<a href="/${it.parentItem.slug}">${esc(prettyFromFilename(it.parentItem.fileName))}</a>`,
            )
          // in-page list of this unit's children (chapter -> its parts)
          const kids = (childrenOf.get(it.slug) || []).slice().sort((a, b) => a.order - b.order)
          const childrenNav = kids.length
            ? `<nav class="excerpt-children">\n` +
              `<div class="excerpt-children-label">In questa sezione</div>\n<ul>` +
              kids.map((k) => `<li><a href="/${k.slug}">${esc(childLabel(k))}</a></li>`).join("") +
              `</ul>\n</nav>\n`
            : ""
          const nav =
            `<nav class="excerpt-nav">\n` +
            `<div class="excerpt-crumb">${author} · ${crumbs.join(" › ")}</div>\n` +
            (prevHref || nextHref
              ? `<div class="excerpt-pn">` +
                (prevHref ? `<a class="ex-prev" href="${prevHref}">‹ ${esc(prevTitle)}</a>` : `<span></span>`) +
                (nextHref ? `<a class="ex-next" href="${nextHref}">${esc(nextTitle)} ›</a>` : `<span></span>`) +
                `</div>\n`
              : "") +
            `</nav>\n` +
            childrenNav +
            `\n`

          const fm =
            `---\n` +
            `title: ${JSON.stringify(title)}\n` +
            `author: ${JSON.stringify(authorName)}\n` +
            `unitType: ${it.unitType}\n` +
            (parentWorkHref ? `parentWork: ${JSON.stringify(parentWorkHref)}\n` : "") +
            `tags:\n  - graph/excerpt\n  - author/${author}\n` +
            `---\n\n`

          // Remove junk separators, strip the leading H1 (Quartz renders the
          // frontmatter title as a page heading automatically; keeping the body
          // H1 produces a double-title), then prepend the nav block.
          let outBody = resolveLinks(stripJunkSeparators(body), { author: authorName })
          outBody = stripLeadingH1IfMatchesTitle(outBody, title)

          // The full-text aggregate page (unitType "work") has no slug-children, so
          // it never showed a chapter index or readability. Add both here: a chapters
          // list from the work's reading units, and (prose only) a readability box.
          if (it.unitType === "work") {
            const readingUnits = items
              .filter((u) => ["chapter", "scene", "story", "section"].includes(u.unitType))
              .sort((a, b) => a.relU.localeCompare(b.relU, undefined, { numeric: true }))
            if (readingUnits.length) {
              outBody =
                `<nav class="excerpt-children">\n<div class="excerpt-children-label">Capitoli / Chapters</div>\n<ul>` +
                readingUnits
                  .map((u) => `<li><a href="/${u.slug}">${esc(prettyFromFilename(u.fileName))}</a></li>`)
                  .join("") +
                `</ul>\n</nav>\n\n` +
                outBody
            }
            const ftText = body.replace(/\[\[([^\]|]+\|)?([^\]]+)\]\]/g, "$2")
            const L = ftText.split("\n").filter((l) => l.trim())
            const isVerse = L.length && L.filter((l) => /\s\s\r?$/.test(l)).length / L.length > 0.4
            const hasScenes = items.some((u) => u.unitType === "scene")
            if (!isVerse && !hasScenes) {
              const r = readabilityOf(ftText)
              if (r) outBody = readabilityBox(r) + "\n" + outBody
            }
          }

          outBody = nav + outBody

          // Lowercase the output path so the emitted page slug matches the
          // lowercased hrefs from sluggify() (v5 link-case fix).
          const unitRel = `${TESTI_REL}/${author}/${sub}/${it.relU}`.toLowerCase()
          const dest = path.join(CONTENT, unitRel.split("/").join(path.sep))
          await fs.mkdir(path.dirname(dest), { recursive: true })
          const tr = translations.get(unitRel)
          if (tr) {
            // One bilingual page; the toggle swaps EN/IT client-side (no sibling
            // page, no navigation).
            await fs.writeFile(
              dest,
              fm +
                bilingualBody(
                  outBody,
                  escapeTableAliasPipes(resolveLinks(tr.body_it || outBody, { author: authorName })),
                ),
            )
          } else {
            await fs.writeFile(dest, fm + outBody)
          }
          copied++

          if (it.unitType !== "work") {
            excerpts.push({
              href: it.slug,
              title,
              author,
              work: wt || workDir.replace(/_/g, " "),
              workHref: parentWorkHref || "",
              unitType: it.unitType,
              order: it.order,
            })
            const kw = keywordCounts(body)
            if (kw.size) excerptsKw[it.slug] = kw
          }
        }
      }
    }
  }

  // Leaf-atom manifest: the authoritative untagged-enumeration source for the
  // tagging run (an atom is "untagged" when hasTags is false). len lets the tagger
  // batch atoms by size. Only meaningful under SPA (the atom loop above only
  // populates leafAtoms in that mode).
  if (SPA) {
    await fs.mkdir(DATA, { recursive: true })
    await fs.writeFile(path.join(DATA, "leaf_atoms.json"), JSON.stringify(leafAtoms))
    console.log(
      `intro atoms: ${introTrim.trimmed} trimmed to the container head, ${introTrim.missed} kept whole ` +
        `(container is not head + sections); ${(introTrim.saved / 1e6).toFixed(1)}MB of duplicated body dropped`,
    )
  }

  return { unitHref, excerpts, excerptsKw, copied, workUnits, workContainers, workParts, atomMeta, readHrefByWork, atomSourceToFrag, atomSearch, unitPlainText, leafFragRows }
}

async function main() {
  await fs.rm(CONTENT, { recursive: true, force: true })
  await fs.mkdir(CONTENT, { recursive: true })
  await markDropboxIgnored(CONTENT)
  const files = await walk(VAULT)

  // ---- PASS 1: read everything, build the works index + a title->href map ----
  const parsed = [] // { rel, data, content }
  const works = []
  const kwCounts = {} // work href -> Map<word,count>, trimmed to top-40 TF-IDF at write
  const titleToHref = new Map() // note basename (wikilink target) -> work href
  const rawSourceToWork = new Map() // raw-source basename (= unit work-dir) -> work href
  for (const rel of files) {
    const relU = rel.replace(/\\/g, "/")
    if (relU === "_Home.md") continue
    const raw = await fs.readFile(path.join(VAULT, rel), "utf8")
    const { data, content } = parseFrontmatter(raw)
    // Drop excluded-author notes entirely: no page, no index row, no links.
    if (data.author && EXCLUDE_AUTHORS.has(data.author)) continue
    parsed.push({ rel, relU, data, content })
    if (data.type === "work") {
      const tags = Array.isArray(data.tags) ? data.tags : data.tags ? [data.tags] : []
      const href = slugFromRel(rel)
      const base = path.basename(rel).replace(/\.md$/, "")
      // Map the raw-source basename (e.g. "A_Childs_History_of_England") to this
      // work's href so unit pages can breadcrumb back to their parent work.
      // Register several normalized keys so Atomized/Plays/Long work-dir names
      // (which may differ in casing, numeric prefixes or articles) still match.
      // Cluster work-dirs are NOT unique across authors ("friendship-tears" exists
      // for Keats, Coleridge and Dickinson alike), so a bare key lets the last work
      // note written win and every other poet's cluster page breadcrumbs to it.
      // Register an author-qualified key too; the bare one stays as the fallback.
      const wAuthor = typeof data.author === "string" ? data.author.toLowerCase() : ""
      // A sub-work never owns a work directory — its source is one atom inside another
      // work's — so it must not take a key a real work answers to. Whitman's poem "The
      // Wound-Dresser" (atom 162 of a cluster) was claiming "the_wound_dresser", the
      // directory of his prose book of the same name, whose reading page then
      // breadcrumbed to a page-less node.
      const isSub = data.subwork === true || data.subwork === "true"
      const put = (key, val) => {
        if (isSub && rawSourceToWork.has(key)) return
        rawSourceToWork.set(key, val)
      }
      const addKey = (k) => {
        if (!k) return
        if (wAuthor) {
          put(`${wAuthor}|${k}`, href)
          put(`${wAuthor}|${normWorkKey(k)}`, href)
        }
        put(k, href)
        put(normWorkKey(k), href)
      }
      if (typeof data.source === "string") {
        const srcBase = data.source.split("/").pop().replace(/\.md$/, "")
        addKey(srcBase)
        addKey(srcBase.replace(/^\d+_/, "")) // strip leading "018_" style prefix
      }
      if (typeof data.title === "string") addKey(data.title)
      const rec = {
        href,
        title: data.title ?? base,
        author: data.author ?? "",
        cluster: data.cluster ?? "",
        summary: extractSummary(content),
      }
      // Hand-rolled frontmatter parser (see parseFrontmatter above) stores every
      // scalar as a string — booleans included — so "subwork: true" arrives as
      // the string "true", not the JS boolean.
      rec._subwork = data.subwork === true || data.subwork === "true"
      rec._source = typeof data.source === "string" ? data.source.replace(/\\/g, "/") : ""
      // Filename basename, kept for the subwork href-resolver below: wikilinks
      // to a work (e.g. a concept note's "## Works" list) target the filename,
      // which is what got registered into titleToHref just below — not
      // necessarily rec.title (frontmatter "title" can be a shorter display
      // name, as with "Sonnet 18 (Shakespeare).md" -> title "Sonnet 18").
      rec._base = base
      let n = 0
      for (const [prefix, field] of AXES) {
        const vals = tags
          .filter((t) => t.startsWith(prefix + "/"))
          .map((t) => t.slice(prefix.length + 1))
        rec[field] = vals
        n += vals.length
      }
      rec.nconnections = n
      // 9th axis, derived from the `cluster:` scalar (not from tags): see
      // deriveClusters. Left untouched: the wheel/landing page reads rec.cluster
      // (the scalar) directly, not this array.
      rec.clusters = deriveClusters(rec.cluster)
      // Readability indices (prose only) as searchable/sortable work properties.
      {
        const ftIdx = content.search(/##\s+Testo integrale/i)
        const ftText = (ftIdx >= 0 ? content.slice(ftIdx) : content).replace(
          /\[\[([^\]|]+\|)?([^\]]+)\]\]/g, "$2")
        if (isProseWork(data, ftText)) {
          const r = readabilityOf(ftText)
          if (r) {
            rec.flesch = r.flesch
            rec.fkgrade = r.fk
            rec.fog = r.fog
            rec.complexpct = r.cplx
            rec.wordspersent = r.wps
          }
        }
      }
      works.push(rec)
      titleToHref.set(base, href)
      
      const kw = keywordCounts(content)
      if (kw.size) kwCounts[href] = kw
    }
  }

  // ---- wikilink -> full-slug resolver (see preprocess-links.mjs) ----
  // Vault notes link by bare basename; Quartz's "shortest" resolution 404s whenever
  // that basename is ambiguous or missing. Resolve every link here instead, using the
  // node's own weight (how many works it aggregates) to pick between namesakes — so
  // "[[Nature]]" lands on the 337-work motif, not on the empty concept of the same
  // name. Sub-work notes emit no page (see PASS 2), so they are not link targets.
  const linkNotes = []
  {
    const linkRe = /\[\[([^\]|#]+?)(?:\|[^\]]+)?\]\]/g
    for (const { rel, data, content } of parsed) {
      if (data.subwork === true || data.subwork === "true") continue
      const seen = new Set()
      let m
      while ((m = linkRe.exec(content))) {
        const href = titleToHref.get(m[1].trim())
        if (href) seen.add(href)
      }
      linkNotes.push({ slug: slugFromRel(rel), weight: seen.size, author: data.author || "" })
    }
  }
  const linkIndex = buildLinkIndex(linkNotes, sluggify)
  // Tally what the resolver does, so a regression shows up as a number rather than as
  // a silently different page.
  const linkStats = { resolved: 0, subwork: 0, left: 0 }
  // Sub-work notes emit no page, so the index above cannot answer for them; their
  // reading target is a fragment of the cluster page, and that is only known once
  // publishUnits() has run. The map is filled in right after (see `_subwork` below)
  // and read here at emit time, when PASS 2 copies the notes that cite them.
  const subworkFrag = new Map() // sluggified title/filename -> "workSlug#atomId"
  const countingResolve = (target, ctx) => {
    const r = linkIndex.resolve(target, ctx)
    if (r) {
      linkStats.resolved++
      return r
    }
    const frag = subworkFrag.get(sluggify(String(target).trim()))
    // Same guard as the work titles: a poem called "Life" or "The Child" is cited by
    // name, not by the word in the sentence. The rendered text has to be one of that
    // poem's own names, capitalised — which lets a cluster note's
    // "[[X (Whitman)|X]]" through and stops "[[Life|life]]".
    if (frag) {
      const shown = String(ctx && ctx.alias != null ? ctx.alias : target).trim()
      if (/^\p{Lu}/u.test(shown) && subworkFrag.get(sluggify(shown)) === frag) {
        linkStats.subwork++
        return frag
      }
    }
    linkStats.left++
    return null
  }
  const resolveLinks = (md, ctx) => resolveWikilinks(md, countingResolve, ctx)
  console.log(`link index: ${linkIndex.size} note slugs`)

  // ---- source -> tags join map (Phase-2 leaf-tag plumbing) ----
  // publishUnits() below runs AFTER this PASS-1 scan (works[] is already fully built
  // here), so its atom loop can join straight off `works` — no separate re-scan of the
  // vault is needed. Keyed by each work-note's own `source:` field; in practice only
  // subwork notes (e.g. the 154 Shakespeare sonnets) have one that resolves to an
  // atomized leaf path — non-subwork work notes' `source` points at their _raw file,
  // which never matches an Atomized/Plays/Long atom path, so those entries are
  // harmless dead keys.
  const sourceTagAxes = new Map() // "Authors/<Author>/<sub>/<relU>" -> axis-bucket object
  for (const rec of works) {
    if (!rec._source) continue
    const axes = {}
    for (const [, field] of AXES) axes[field] = rec[field] || []
    axes.clusters = rec.clusters || []
    sourceTagAxes.set(rec._source, axes)
  }

  // ---- Load precomputed IT translations (data/translations_pages.jsonl) ----
  // Keyed by lowercased content-relative path. When a page has a translation we
  // also emit a "<slug>.it.md" sibling and inject a per-page language-toggle
  // marker into both the EN page and its IT sibling.
  const translations = new Map()
  try {
    const raw = await fs.readFile(path.join(ROOT, "data", "translations_pages.jsonl"), "utf8")
    for (const ln of raw.split("\n")) {
      if (!ln.trim()) continue
      const e = JSON.parse(ln)
      translations.set(e.rel.toLowerCase(), e)
    }
    console.log(`translations: ${translations.size} pages`)
  } catch (e) {
    if (e.code !== "ENOENT") throw e
  }

  // ---- Publish atomized excerpts / play scenes / long-poem sections ----
  const { unitHref, excerpts, excerptsKw, copied: unitsCopied, workUnits, workContainers, workParts, atomMeta, readHrefByWork, atomSourceToFrag, atomSearch, unitPlainText, leafFragRows } = await publishUnits(rawSourceToWork, translations, sourceTagAxes, resolveLinks)

  // Page-less sub-work nodes: their href is the SPA fragment of their source atom, and
  // they emit NO content/works page (see PASS 2). Resolve href from source now, so the
  // works index + conceptIndex (PASS 2) + link-rewriting all use the fragment.
  for (const rec of works) {
    if (!rec._subwork) continue
    const frag = atomSourceToFrag.get(rec._source)
    if (!frag) {
      console.warn(`subwork: no atom fragment for source "${rec._source}" (title "${rec.title}") — skipping node`)
      rec._drop = true
      continue
    }
    rec.href = frag
    rec.readHref = frag
    rec.parentWork = atomMeta.get(frag)?.work || ""
    // Re-key on the same string(s) originally registered for this work (base
    // filename, plus rec.title if it differs) so wikilinks anywhere — concept
    // notes' "## Works" lists included — resolve to the new fragment instead
    // of the stale pre-subwork href.
    titleToHref.set(rec._base, frag)
    if (rec.title !== rec._base) titleToHref.set(rec.title, frag)
    // Same two keys for the wikilink resolver. A cluster note lists its poems as
    // "[[The Wound-Dresser (Whitman)|The Wound-Dresser]]" — filename form as target,
    // bare title as alias — so both spellings have to reach the fragment, and so does
    // the title with its "(Author)" suffix stripped, which is how prose cites them.
    for (const k of [rec._base, rec.title, String(rec.title).replace(/[-\s]*\([^()]*\)$/, "")]) {
      const s = sluggify(String(k || "").trim())
      if (s && !subworkFrag.has(s)) subworkFrag.set(s, frag)
    }
  }

  // Leaf-atom fragment rows: atoms that resolved tags (join or own frontmatter) but
  // are NOT a subwork's source atom (those already got a row via the resolver just
  // above). publishUnits() pre-filtered on the same sourceTagAxes.has() check, so
  // every row here is additive. Kept OUT of `works` (deliberately, do not push here):
  // every work-level aggregate computed below (authorCounts, wheel sublabels, homepage
  // hero counts, opere.md/cerca.md counts, build summary) reads `works` directly, and a
  // leaf fragment is not a work. leafFragRows is written to its own LEAF_JSON shard —
  // not merged into `works`/worksOut — right before it's written, after all those
  // stats are computed. See worksOut/leafOut below.

  // Cover atomless works: a single-unit work IS its own leaf atom, but if the
  // whole workDir produced no leaf-atom entry (e.g. a readable work with a reading
  // slug but no atom-level text was captured), add one entry keyed by its bare
  // reading slug (no #fragment) so it is still corpus-searchable.
  if (SPA) {
    const fraggedWorks = new Set(Object.keys(atomSearch).map((f) => f.split("#")[0]))
    for (const rec of works) {
      const readSlug = readHrefByWork.get(rec.href)
      if (!readSlug) continue // no reading page (pure concept note)
      if (fraggedWorks.has(readSlug)) continue // already covered by its atoms
      if (atomSearch[readSlug]) continue
      atomSearch[readSlug] = { title: rec.title, work: rec.title, text: unitPlainText.get(readSlug) || "" }
    }
    // Cap every entry's text before writing — full per-atom text made this file
    // 232MB (over GitHub's 100MB limit). 2000 chars is ample for search terms;
    // the deployed FlexSearch index truncates far more anyway.
    for (const k in atomSearch) atomSearch[k].text = String(atomSearch[k].text || "").slice(0, 2000)
    await fs.writeFile(path.join(DATA, "atom_search.json.gz"), zlib.gzipSync(Buffer.from(JSON.stringify(atomSearch))))
  }

  await fs.writeFile(
    path.join(ROOT, "quartz", "static", "excerpts.json"),
    JSON.stringify(excerpts),
  )
  await fs.writeFile(
    path.join(ROOT, "quartz", "static", "excerpts_kw.json"),
    JSON.stringify(topTfIdf(excerptsKw)),
  )

  // ---- PASS 2: write content; convert concept-note "## Works" lists to tables ----
  // concepts.json maps a concept-note slug -> { title, type, works: [{href,...}] }
  const conceptIndex = {}
  let written = 0
  for (const { rel, relU, data, content } of parsed) {
    let newContent = transform(content, unitHref)
    // Remove any NotebookLM/export-tool separator lines that might have leaked
    // into vault files (belt-and-suspenders guard).
    newContent = stripJunkSeparators(newContent)
    // Strip the leading H1 when it duplicates the frontmatter title (Quartz
    // renders the title from frontmatter as a page heading automatically, so
    // leaving the body H1 produces a visible double-title).
    newContent = stripLeadingH1IfMatchesTitle(newContent, data.title)
    // After the H1 strip: resolving a link inside the H1 would change the text the
    // title comparison matches on.
    newContent = resolveLinks(newContent, { author: data.author })
    const topFolder = relU.split("/")[0]
    const axis = AXIS_FOLDERS[topFolder]

    if (axis && data.type) {
      // Collect the work wikilinks under "## Works" and map them to hrefs.
      const linkRe = /\[\[([^\]|#]+?)(?:\|[^\]]+)?\]\]/g
      const seen = new Set()
      const found = []
      const labels = []
      let m
      while ((m = linkRe.exec(content))) {
        const target = m[1].trim()
        const href = titleToHref.get(target)
        if (href && !seen.has(href)) {
          seen.add(href)
          found.push(href)
          labels.push(target)
        }
      }
      if (found.length) {
        const slug = slugFromRel(rel)
        conceptIndex[slug] = {
          title: data.title ?? path.basename(rel).replace(/\.md$/, ""),
          type: data.type,
          works: found,
        }
        // Replace the "## Works" section (heading + the bullet list that follows)
        // with a placeholder div; the client renders a searchable/paginated table.
        // A plain list of the same works is kept after the placeholder rather than
        // discarded: it is the only server-side node -> work link there is, and
        // dropping it left every work reachable only from a node orphaned in the
        // link graph. It is rebuilt from the hrefs resolved above, not from the
        // vault's own bullets, so a list entry with no work page cannot come back
        // as a broken link. Hidden by default (the table shows the same works);
        // conceptWorks reveals it if the table fails to render. The blank lines
        // around it matter: they close the HTML block so the wikilinks inside are
        // still parsed as markdown.
        const fallback = found
          .map((href, i) => `- [[${href}|${labels[i]}]]`)
          .join("\n")
        // Replacement as a function, not a string: a work title containing "$" would
        // otherwise be read as a substitution pattern.
        newContent = newContent.replace(
          /(^|\n)##\s+Works\s*\n[\s\S]*?(?=\n##\s|\n#[^#]|\n#graph|$)/,
          (_all, lead) =>
            `${lead}## Works\n\n<div class="concept-works" data-slug="${slug}"></div>\n\n` +
            `<div class="concept-works-fallback">\n\n${fallback}\n\n</div>\n`,
        )
      }
    }

    // Chapter index on work pages: with the Explorer sidebar off, this is how a
    // reader reaches the atomized chapters/scenes/stories from a work. Insert it
    // before "## Connections" (so: byline, abstract, chapters, connections), else
    // append. Strip the repeated "<Work> — " prefix from each unit title.
    let workTocMd = ""
    if (data.type === "work") {
      let units = workUnits.get(slugFromRel(rel))
      if (!units || !units.length) {
        // No chapters/scenes: fall back to the single full-text page ("Testo / Text").
        const c = workContainers.get(slugFromRel(rel))
        if (c) units = [c]
      }
      if (units && units.length) {
        const sorted = [...units].sort((a, b) =>
          a.relU.localeCompare(b.relU, undefined, { numeric: true }))
        const label = sorted.length > 1 ? "Capitoli / Chapters" : "Testo / Text"
        workTocMd =
          `## ${label}\n\n` +
          sorted
            .map((u) => {
              const t = u.title.includes(" — ")
                ? u.title.slice(u.title.indexOf(" — ") + 3)
                : u.title
              return `- [${t}](/${u.slug})`
            })
            .join("\n") +
          "\n\n"
        // Works split straight into "part_NN" excerpts (no chapter layer) get the
        // full-text link above plus an explicit parts list, so the parts are reachable
        // from the work page instead of only as backlinks. Skip single-part works
        // (part_01 just mirrors the full text).
        const parts = (workParts.get(slugFromRel(rel)) || [])
          .slice()
          .sort((a, b) => a.order - b.order)
        if (parts.length > 1) {
          workTocMd +=
            `## Parti / Parts\n\n` +
            parts.map((p) => `- [Part ${p.order}](/${p.slug})`).join("\n") +
            "\n\n"
        }
        // The KG note may already carry a "## Chapters / scenes / sections" list;
        // drop it so the generated "## Capitoli / Chapters" TOC is not duplicated.
        newContent = newContent.replace(
          /\n##\s+Chapters \/ scenes \/ sections[\s\S]*?(?=\n##\s|$)/, "")
        newContent = /\n##\s+Connections/.test(newContent)
          ? newContent.replace(/\n##\s+Connections/, `\n${workTocMd}## Connections`)
          : newContent.trimEnd() + "\n\n" + workTocMd
      }
    }

    // Readability box on PROSE work pages only (skip poetry/theatre/verse).
    if (data.type === "work") {
      const ft = newContent.search(/##\s+Testo integrale/i)
      const fullText = (ft >= 0 ? newContent.slice(ft) : newContent).replace(
        /\[\[([^\]|]+\|)?([^\]]+)\]\]/g, "$2")
      if (isProseWork(data, fullText)) {
        const r = readabilityOf(fullText)
        if (r) {
          const box = readabilityBox(r)
          newContent = /\n##\s+Connections/.test(newContent)
            ? newContent.replace(/\n##\s+Connections/, `\n${box}## Connections`)
            : newContent.trimEnd() + "\n\n" + box
        }
      }
    }

    // Page-less sub-work nodes (see PASS 2 resolver above): the note's href is
    // already the SPA fragment of its source atom, so no content/works page
    // should be emitted for it — conceptIndex population above (from
    // titleToHref, which already carries the resolved fragment) still ran
    // unconditionally, so back-links survive even though the page does not.
    // Hand-rolled frontmatter parser stores scalars as strings, so
    // "subwork: true" arrives as the string "true", not the JS boolean.
    const isSubwork = data.subwork === true || data.subwork === "true"
    if (isSubwork) continue

    // Lowercase the output path (v5 link-case fix): pages emit at the file path,
    // and our hrefs are lowercased in sluggify(), so the files must be lowercase too.
    const dest = path.join(CONTENT, rel.toLowerCase())
    await fs.mkdir(path.dirname(dest), { recursive: true })
    const trPage = translations.get(relU.toLowerCase())
    if (trPage) {
      let itBody = escapeTableAliasPipes(
        resolveLinks(trPage.body_it || newContent, { author: data.author }),
      )
      if (workTocMd) {
        itBody = itBody.replace(/\n##\s+Chapters \/ scenes \/ sections[\s\S]*?(?=\n##\s|$)/, "")
        itBody = /\n##\s+Connections/.test(itBody)
          ? itBody.replace(/\n##\s+Connections/, `\n${workTocMd}## Connections`)
          : itBody.trimEnd() + "\n\n" + workTocMd
      }
      await fs.writeFile(dest, matter.stringify(bilingualBody(newContent, itBody), { ...data }))
    } else {
      await fs.writeFile(dest, matter.stringify(newContent, { ...data }))
    }
    written++
  }

  // Point each work at its reading page (reader) where one exists; the works table,
  // faceted search and emblems use readHref so selecting a work opens the atoms +
  // EN/IT toggle instead of the bare KG metadata node. Sub-work recs already had
  // their href/readHref resolved to an atom fragment above — leave them alone, or
  // this lookup (keyed by the ORIGINAL work href, not the fragment) blanks them.
  for (const rec of works) {
    if (rec._subwork) continue
    rec.readHref = readHrefByWork.get(rec.href) || ""
  }
  // Drop sub-work recs whose source atom never resolved to a fragment (see the
  // resolver above), and strip the temp tagging fields before publishing. Leaf
  // fragment rows are appended here — AFTER every work-level stat above has already
  // read `works` leaf-free — so they still reach quartz/static/index.json without
  // ever counting toward a work aggregate. They carry no _subwork/_source/_drop/_base
  // fields, so the strip is a no-op for them; readHref is intentionally left unset —
  // the table renderers fall back to `r.readHref || r.href`, and href is already the
  // atom fragment itself.
  const stripTagFields = (r) => {
    const { _subwork, _source, _drop, _base, ...clean } = r
    return clean
  }
  // Cluster inheritance fallback: a leaf fragment row (e.g. an Emma chapter, an
  // Orthodoxy part) has no cluster of its own — leaf frontmatter tags (Opus/
  // wikilink-derived) carry no cluster/ entries — so it inherits its parent
  // work's clusters. Sonnets (and any leaf whose own tags DO include a cluster,
  // via sourceTagAxes) already have clusters and are left untouched — no
  // override. Key off readHref, not href: a work's `href` is its KG-note slug
  // (e.g. "works/ortho14-(chesterton)"), while a leaf row's href is
  // `${workSlug}#${atomId}` where workSlug is the Testi reading-page slug —
  // that's rec.readHref (set just above), not rec.href.
  const workClustersByHref = new Map()
  for (const rec of works) {
    if (rec._drop) continue
    const key = rec.readHref || rec.href
    if (key) workClustersByHref.set(key, rec.clusters || [])
  }
  // Fallback join by (author, normalized title) for works whose workDir got
  // truncated at ~70 chars on disk (see publishUnits): the truncation breaks
  // BOTH rawSourceToWork's lookup (so parentWorkHref never resolves) AND
  // workSlug registration in readHrefByWork, so rec.readHref stays "" and the
  // href-keyed map above misses. The leaf row's `parentWork` label is derived
  // from the same truncated workDir, so it's a truncated PREFIX of the work
  // note's real title, not an exact match — compare via normWorkKey (strips
  // punctuation/case/articles) and match if either normalized string is a
  // prefix of the other. Also compare a SQUASHED (spaces removed) form: the
  // on-disk workDir strips apostrophes bare ("Wells's" -> "Wellss") while
  // normWorkKey turns them into a space ("wells s") — squashing sidesteps
  // that tokenization mismatch. Scoped per-author to avoid cross-author
  // collisions. Titles with no matching work note at all (no KG "work" note
  // was ever created for that atom's parent) legitimately stay clusterless —
  // there is nothing to inherit.
  const squash = (s) => s.replace(/\s+/g, "")
  const worksByAuthorNorm = new Map()
  for (const rec of works) {
    if (rec._drop || !rec.title) continue
    const norm = normWorkKey(rec.title)
    if (!norm) continue
    if (!worksByAuthorNorm.has(rec.author)) worksByAuthorNorm.set(rec.author, [])
    worksByAuthorNorm.get(rec.author).push({ normTitle: norm, sq: squash(norm), clusters: rec.clusters || [] })
  }
  for (const row of leafFragRows) {
    if (row.clusters && row.clusters.length) continue // sonnets: keep their own
    const parentWorkHref = row.href.split("#")[0]
    row.clusters = workClustersByHref.get(parentWorkHref) || []
    if (!row.clusters.length && row.parentWork) {
      const norm = normWorkKey(row.parentWork)
      const sq = squash(norm)
      const candidates = worksByAuthorNorm.get(row.author) || []
      const hit = norm && candidates.find(
        (c) => c.normTitle.startsWith(norm) || norm.startsWith(c.normTitle) ||
          c.sq.startsWith(sq) || sq.startsWith(c.sq))
      if (hit) row.clusters = hit.clusters
    }
  }
  // index.json stays works-only (fast for /opere and every page that loads it up
  // front); the ~15k leaf rows go to index_leaf.json, lazy-loaded only by consumers
  // that actually surface leaf-level tag results (see cerca.inline.ts).
  const worksOut = works.filter((r) => !r._drop).map(stripTagFields)
  const leafOut = leafFragRows.map(stripTagFields)
  await fs.mkdir(path.dirname(STATIC_JSON), { recursive: true })
  await fs.writeFile(STATIC_JSON, JSON.stringify(worksOut))
  await fs.writeFile(LEAF_JSON, JSON.stringify(leafOut))
  await fs.writeFile(KW_JSON, JSON.stringify(topTfIdf(kwCounts)))
  await fs.writeFile(
    path.join(ROOT, "quartz", "static", "concepts.json"),
    JSON.stringify(conceptIndex),
  )

  // ---- Horizontal work<->work links: "Opere correlate" ----
  // For each work, find the works that share the most (and rarest) concept
  // tags. Concept rarity is weighted (1/log2(df+1)) so a niche shared archetype
  // counts more than a ubiquitous one; very generic concepts (linking more than
  // DF_CAP works) are dropped as noise and to bound the O(df^2) pairing cost.
  // Emit related.json keyed by work href; the RelatedWorks component renders it
  // client-side on each work page (no per-note content rewrite).
  {
    const DF_CAP = 80
    const TOP_N = 8
    const workMeta = new Map(works.map((w) => [w.href, w]))
    const workConcepts = new Map() // work href -> [{ slug, weight }]
    for (const [slug, entry] of Object.entries(conceptIndex)) {
      const df = entry.works.length
      if (df < 2 || df > DF_CAP) continue
      const weight = 1 / Math.log2(df + 1)
      for (const h of entry.works) {
        if (!workMeta.has(h)) continue
        let arr = workConcepts.get(h)
        if (!arr) workConcepts.set(h, (arr = []))
        arr.push({ slug, weight })
      }
    }
    const related = {}
    for (const [h, concepts] of workConcepts) {
      const score = new Map() // other href -> { s, shared }
      for (const { slug, weight } of concepts) {
        for (const other of conceptIndex[slug].works) {
          if (other === h || !workMeta.has(other)) continue
          let v = score.get(other)
          if (!v) score.set(other, (v = { s: 0, shared: 0 }))
          v.s += weight
          v.shared += 1
        }
      }
      if (!score.size) continue
      const top = [...score.entries()]
        .sort((a, b) => b[1].s - a[1].s || b[1].shared - a[1].shared)
        .slice(0, TOP_N)
        .map(([oh, v]) => {
          const m = workMeta.get(oh)
          return { href: oh, title: m.title, author: m.author, shared: v.shared }
        })
      if (top.length) related[h] = top
    }
    await fs.writeFile(
      path.join(ROOT, "quartz", "static", "related.json"),
      JSON.stringify(related),
    )
    console.log(
      `related.json: ${Object.keys(related).length} works with related links`,
    )
  }

  // ---- Chapter-level interlinking by characters/themes/plot (#17) ----
  // Reads the LLM-extracted per-chapter tags (data/chapter_tags.json) and links
  // each chapter to the chapters that share the most (and rarest) characters and
  // themes, rarity-weighted exactly like the work-level pass. Characters are
  // work-specific so they bind chapters within a work; themes are cross-work, so
  // a chapter in one novel can surface a thematically-twin chapter in another.
  // Emits chapter_related.json; the RelatedWorks component renders it on chapter
  // pages ("Capitoli correlati"). Skipped silently if the tags file is absent.
  try {
    const raw = await fs.readFile(CHAPTER_TAGS, "utf8")
    // chapter_tags.json is keyed by the (case-preserved) #17 hrefs; lowercase the
    // keys so they match the now-lowercased unit hrefs/slugs (v5 link-case fix).
    const tags = Object.fromEntries(
      Object.entries(JSON.parse(raw)).map(([k, v]) => [k.toLowerCase(), v]),
    )
    const unitMeta = new Map() // href -> { title, work, workHref }
    for (const u of Object.values(excerpts)) {
      unitMeta.set(u.href, {
        title: String(u.title || "").replace(/\[\[|\]\]/g, ""),
        work: u.work || "",
        workHref: u.workHref || "",
      })
    }
    // SPA: excerpts only cover leaf frags; atomMeta also carries aggregate chapters,
    // so a chapter-level related item still resolves a title/work.
    if (SPA) for (const [k, v] of atomMeta) if (!unitMeta.has(k)) unitMeta.set(k, v)
    const TOP_N = 6
    const DF_CAP = 200
    // token = "c:<character>" or "t:<theme>"; build per-chapter token lists + df.
    const chapTokens = new Map()
    const df = new Map()
    for (const [href, t] of Object.entries(tags)) {
      const toks = [
        ...(t.characters || []).map((c) => "c:" + c),
        ...(t.themes || []).map((x) => "t:" + String(x).toLowerCase().trim()),
      ]
      chapTokens.set(href, toks)
      for (const tok of new Set(toks)) df.set(tok, (df.get(tok) || 0) + 1)
    }
    const tokenWorks = new Map() // token -> [chapter hrefs]
    for (const [href, toks] of chapTokens) {
      for (const tok of new Set(toks)) {
        if ((df.get(tok) || 0) > DF_CAP) continue
        let arr = tokenWorks.get(tok)
        if (!arr) tokenWorks.set(tok, (arr = []))
        arr.push(href)
      }
    }
    const chapterRelated = {}
    for (const [href, toks] of chapTokens) {
      const score = new Map() // other href -> { s, shared }
      for (const tok of new Set(toks)) {
        const d = df.get(tok) || 0
        if (d < 2 || d > DF_CAP) continue
        const weight = 1 / Math.log2(d + 1)
        for (const other of tokenWorks.get(tok) || []) {
          if (other === href) continue
          let v = score.get(other)
          if (!v) score.set(other, (v = { s: 0, shared: 0 }))
          v.s += weight
          v.shared += 1
        }
      }
      if (!score.size) continue
      const top = [...score.entries()]
        .sort((a, b) => b[1].s - a[1].s || b[1].shared - a[1].shared)
        .slice(0, TOP_N)
        .map(([oh, v]) => {
          const key = SPA ? slugToFrag(oh) : oh
          const m = unitMeta.get(key) || {}
          const plot = tags[oh]?.plot || ""
          return {
            href: key,
            title: m.title || oh,
            work: m.work || "",
            shared: v.shared,
            plot: plot.length > 160 ? plot.slice(0, 157) + "…" : plot,
          }
        })
      if (top.length) chapterRelated[SPA ? slugToFrag(href) : href] = top
    }
    // Shard by work so a reading page fetches only its own related-cards (few KB)
    // instead of the whole ~7MB index. atomRouter loads
    // static/chapter_related/<workSlug with / -> __>.json. The reading-page keys are
    // "<workSlug>#<atomId>"; group them by the pre-# workSlug.
    const shardDir = path.join(ROOT, "quartz", "static", "chapter_related")
    await fs.rm(shardDir, { recursive: true, force: true })
    await fs.mkdir(shardDir, { recursive: true })
    // drop the old monolith if a previous build left it behind
    await fs.rm(path.join(ROOT, "quartz", "static", "chapter_related.json"), { force: true })
    const byWork = new Map()
    for (const [key, val] of Object.entries(chapterRelated)) {
      const workSlug = key.split("#")[0]
      if (!byWork.has(workSlug)) byWork.set(workSlug, {})
      byWork.get(workSlug)[key] = val
    }
    const shardKeys = []
    for (const [workSlug, obj] of byWork) {
      const key = workSlug.replace(/\//g, "__")
      shardKeys.push(key)
      await fs.writeFile(path.join(shardDir, key + ".json"), JSON.stringify(obj))
    }
    // Manifest of shard keys. atomRouter fetches this once and only requests a shard
    // when its key is present — the large majority of reading pages have no shard, so
    // without the manifest every one of them logs a 404 for a missing file.
    await fs.writeFile(path.join(shardDir, "_index.json"), JSON.stringify(shardKeys))
    console.log(
      `chapter_related: ${Object.keys(chapterRelated).length} chapters -> ${byWork.size} per-work shards`,
    )
  } catch (e) {
    if (e.code !== "ENOENT") throw e
    console.log("chapter_tags.json absent — skipping chapter interlinking")
  }

  const authors = [...new Set(works.map((w) => w.author).filter(Boolean))].sort()
  const clusters = [...new Set(works.map((w) => w.cluster).filter(Boolean))].sort()

  // ---------- Home (editorial landing) ----------
  const authorCounts = {}
  for (const w of works) authorCounts[w.author] = (authorCounts[w.author] || 0) + 1

  const topClustersAll = clusters
    .map((c) => ({ c, n: works.filter((w) => w.cluster === c).length }))
    .sort((a, b) => b.n - a.n)
  const topClusters = topClustersAll.slice(0, 18)
  const clusterChips = topClusters
    .map((x) => `<a class="cluster-chip" href="${sluggify("Clusters/" + x.c)}">${x.c} <span>${x.n}</span></a>`)
    .join("\n")

  // ---------- Radial-wheel data (quartz/static/wheel.json) ----------
  // Each spoke: { label, sub, img, href, cercaAuthor? }. The author wheel uses the
  // sessionStorage->Cerca deep-link (cercaAuthor); axis + cluster wheels link to pages.
  const authorEmblem = {
    Shakespeare: "author-shakespeare", Keats: "author-keats", Dickinson: "author-dickinson",
    Eliot: "author-eliot", Chesterton: "author-chesterton", Dickens: "author-dickens",
    Austen: "author-austen", Bronte: "author-bronte", Poe: "author-poe", Wilde: "author-wilde",
    Coleridge: "author-coleridge", Whitman: "author-whitman", Sayers: "author-sayers",
    "Conan Doyle": "author-conan-doyle", Belloc: "author-belloc",
  }
  const authorsWheel = authors
    .filter((a) => !EXCLUDE_AUTHORS.has(a))
    .map((a) => ({
    label: a === "Bronte" ? "Brontë" : a,
    sub: `${authorCounts[a] || 0} works`,
    img: authorEmblem[a] || "author-shakespeare",
    href: "cerca",
    cercaAuthor: a,
  }))

  // Live per-axis note counts (so e.g. Characters reflects 712, not a stale number).
  const axisNoteCount = (folder) =>
    parsed.filter((p) => p.relU.startsWith(folder + "/") && p.relU.endsWith(".md")).length
  const axesWheel = [
    { label: "Topoi", img: "axis-topoi", href: "topoi/", n: axisNoteCount("Topoi") },
    { label: "Archetypes", img: "axis-archetipi", href: "archetypes/", n: axisNoteCount("Archetypes") },
    { label: "Motifs", img: "axis-motivi", href: "motifs/", n: axisNoteCount("Motifs") },
    { label: "Concepts", img: "axis-concetti", href: "concepts/", n: axisNoteCount("Concepts") },
    { label: "Forms", img: "axis-forme", href: "forms/", n: axisNoteCount("Forms") },
    { label: "Historical References", img: "axis-storia", href: "historical-references/", n: axisNoteCount("Historical References") },
    { label: "Settings", img: "axis-ambientazioni", href: "settings/", n: axisNoteCount("Settings") },
    { label: "Characters", img: "axis-personaggi", href: "characters/", n: axisNoteCount("Characters") },
  ].map((a) => ({ label: a.label, sub: String(a.n), img: a.img, href: a.href }))

  // Map the 12 biggest clusters to their emblem files (by leading keyword).
  const clusterEmblem = [
    [/^Death/, "cluster-death"],
    [/Frustrated Love/, "cluster-love"],
    [/^Grief/, "cluster-grief"],
    [/^Wonder/, "cluster-wonder"],
    [/^Satire/, "cluster-satire"],
    [/^Transience/, "cluster-transience"],
    [/^Money/, "cluster-money"],
    [/^Seasons/, "cluster-seasons"],
    [/^Nature ·/, "cluster-nature"],
    [/^Sea ·/, "cluster-sea"],
    // Added 2026-07-11: cross-author theme spokes (see Clusters notes' "Connected
    // works · other authors" sections). Each regex matches one existing Louvain cluster.
    // NB: "Sonnet …", "Letters and Writing …" and "Lyric …" clusters were REMOVED from
    // the wheel 2026-07-12 — the wheel is MEANING-only, and all three were form-defined
    // Louvain communities. Sonnet/Lyric are surfaced via the Forms axis (Forms/Sonnet,
    // Forms/Lyric, …); their members were reassigned to meaning clusters (love /
    // poetic-immortality) and the cluster notes deleted.
    [/^Faith/, "cluster-faith"],
    [/^Appearance/, "cluster-appearance"],
    [/^Greek Mythology/, "cluster-myth"],
    [/^Alienation/, "cluster-alienation"],
  ]
  const clustersWheel = clusterEmblem
    .map(([re, img]) => {
      const hit = topClustersAll.find((x) => re.test(x.c))
      if (!hit) return null
      const short = hit.c.split(" · ")[0]
      // The on-disk cluster filename has no "/" (Obsidian can't put it in a name),
      // so strip it from the frontmatter value before slugging to match the page.
      const fileName = hit.c.replace(/\s*\/\s*/g, " ").replace(/\s+/g, " ").trim()
      return {
        label: short,
        sub: `${hit.n} works`,
        img,
        href: sluggify("Clusters/" + fileName),
      }
    })
    .filter(Boolean)

  // Social Issues is a hand-authored cross-author aggregator note (not a Louvain
  // community), so it never appears in topClustersAll — push its spoke explicitly.
  clustersWheel.push({
    label: "Social Issues",
    sub: "23 works",
    img: "cluster-social",
    href: sluggify("Clusters/Social Issues · Labour · Reform"),
  })

  const wheelData = { authors: authorsWheel, axes: axesWheel, clusters: clustersWheel }
  await fs.writeFile(
    path.join(ROOT, "quartz", "static", "wheel.json"),
    JSON.stringify(wheelData),
  )

  // ---------- Home (design plate 1b) ----------
  // Editorial nameplate, hero, eight-axis grid, the two wheels, century timeline.
  // Everything here is raw HTML on purpose: Quartz passes it through untouched, and the
  // markup carries the classes that quartz/styles/custom.scss styles (`hp-*`). Keep the
  // blocks free of blank lines — a blank line inside an HTML block makes the markdown
  // parser resume and wrap the remainder in <p>.

  // One glossing line per concept axis, in the order axesWheel is built. Editorial text,
  // so it lives next to the markup rather than in the data.
  const axisGloss = {
    Topoi: "recurring situations",
    Archetypes: "universal figures",
    Motifs: "images that return",
    Concepts: "themes and ideas",
    Forms: "genres and metres",
    "Historical References": "history in the text",
    Settings: "places and landscapes",
    Characters: "who recurs",
  }
  const axisTiles = axesWheel
    .map(
      (a) =>
        `<a class="hp-axis" href="${a.href}"><span class="hp-axis-em"><img src="static/wheel/${a.img}.webp" alt=""></span><span class="hp-axis-body"><span class="hp-axis-head"><span class="hp-axis-name">${a.label}</span><span class="hp-axis-n">${a.sub}</span></span><span class="hp-axis-gloss">${axisGloss[a.label] || ""}</span></span></a>`,
    )
    .join("")

  // The year of each author's central work — an editorial judgement, not vault data (no
  // work in the graph carries a date), which is why it is a literal table: edit a year
  // here and the timeline moves. An author absent from this map is dropped from the
  // chart with a warning rather than plotted at a guessed position.
  const CENTRAL_WORK_YEAR = {
    Shakespeare: 1600, // Hamlet
    Coleridge: 1798, // Lyrical Ballads
    Austen: 1813, // Pride and Prejudice
    Keats: 1819, // the great odes
    Poe: 1845, // The Raven
    "Brontë": 1847, // Jane Eyre / Wuthering Heights
    Dickens: 1853, // Bleak House
    Whitman: 1855, // Leaves of Grass
    Dickinson: 1862, // her most prolific year
    Wilde: 1891, // The Picture of Dorian Gray
    "Conan Doyle": 1892, // The Adventures of Sherlock Holmes
    Belloc: 1902, // The Path to Rome
    Chesterton: 1908, // Orthodoxy · The Man Who Was Thursday
    Eliot: 1922, // The Waste Land
    Sayers: 1935, // Gaudy Night
  }
  const TL_FROM = 1580
  const TL_TO = 1950
  const tlX = (y) => (((y - TL_FROM) / (TL_TO - TL_FROM)) * 100).toFixed(2) + "%"
  const tlTicks = [1600, 1650, 1700, 1750, 1800, 1850, 1900, 1950]
  const tlGrid = tlTicks
    .map((t) => `<span class="hp-tl-grid" style="left:${tlX(t)}"></span>`)
    .join("")
  const tlRows = authorsWheel
    .map((a) => {
      const year = CENTRAL_WORK_YEAR[a.label]
      if (!year) {
        console.warn(`home timeline: no central-work year for author "${a.label}" — omitted`)
        return null
      }
      return { label: a.label, year, n: parseInt(a.sub, 10) || 0, href: a.href }
    })
    .filter(Boolean)
    .sort((x, y) => x.year - y.year)
    .map(
      (a) =>
        `<a class="hp-tl-row" href="${a.href}"><span class="hp-tl-name">${a.label}</span><span class="hp-tl-track">${tlGrid}<span class="hp-tl-dot" style="left:${tlX(a.year)}"></span><span class="hp-tl-year" style="left:${tlX(a.year)}">${a.year}</span></span><span class="hp-tl-n">${a.n}</span></a>`,
    )
    .join("")
  const tlAxis = tlTicks
    .map((t) => `<span class="hp-tl-tick" style="left:${tlX(t)}">${t}</span>`)
    .join("")

  const conceptNotes = axesWheel.reduce((s, a) => s + (parseInt(a.sub, 10) || 0), 0)
  const num = (n) => n.toLocaleString("en")

  const home = `---
title: English Literature — A Knowledge Graph
---

<div class="hp-mast">
  <p class="hp-eyebrow">English literature · a graph of ideas</p>
  <div class="hp-rule-thin"></div>
  <div class="hp-nameplate">
    <span class="hp-wordmark"><span class="hp-wm-title">English Literature</span><span class="hp-wm-bar"></span><span class="hp-wm-sub">a knowledge graph</span></span>
    <span class="hp-mast-stats">${num(works.length)} works · ${authors.length} authors · ${num(excerpts.length)} excerpts</span>
  </div>
  <div class="hp-rule-double"><span></span><span></span></div>
  <nav class="hp-nav" aria-label="Sections">
    <a href="opere">Works</a><a href="brani">Excerpts</a><a href="cerca">Search</a><a href="naviga">Navigate</a>
  </nav>
  <div class="hp-rule-thin"></div>
</div>

<div class="hp-hero">
  <div class="hp-hero-text">
    <p class="hp-kicker">A connected reading of the English canon</p>
    <h1 class="hp-headline">Not an archive.<br><em>A network of ideas.</em></h1>
    <p class="hp-lead">Every work is divided into reading units and tied to all the others through what they share: themes, archetypes, motifs, forms, settings, historical references, characters.</p>
    <p class="hp-lead-alt">Open a work to follow its links; open a concept to see every work that carries it.</p>
    <p class="hp-actions"><a class="btn btn-primary" href="cerca">Enter through a theme</a><a class="btn" href="opere">All works</a></p>
  </div>
  <aside class="hp-plate">
    <div class="hp-plate-art" aria-hidden="true">
      <svg viewBox="0 0 200 200" width="150" height="150" role="img" aria-label="open book">
        <g fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M100 50 C70 35 40 35 20 45 L20 150 C40 140 70 140 100 155"/>
          <path d="M100 50 C130 35 160 35 180 45 L180 150 C160 140 130 140 100 155"/>
          <path d="M100 55 L100 150"/>
          <path d="M35 65 H80 M35 85 H80 M35 105 H80 M120 65 H165 M120 85 H165 M120 105 H165"/>
        </g>
      </svg>
    </div>
    <div class="hp-stats">
      <div class="hp-stat"><span class="hp-stat-k">Works</span><span class="hp-stat-v">${num(works.length)}</span></div>
      <div class="hp-stat"><span class="hp-stat-k">Authors</span><span class="hp-stat-v">${authors.length}</span></div>
      <div class="hp-stat"><span class="hp-stat-k">Reading units</span><span class="hp-stat-v">${num(excerpts.length)}</span></div>
      <div class="hp-stat"><span class="hp-stat-k">Concept notes</span><span class="hp-stat-v">${num(conceptNotes)}</span></div>
      <div class="hp-stat"><span class="hp-stat-k">Bilingual pages</span><span class="hp-stat-v">${num(translations.size)}</span></div>
    </div>
    <p class="hp-plate-note">Italian translations go up chapter by chapter, alongside the English — never in place of it.</p>
  </aside>
</div>

<div class="hp-sec"><h2>The eight ways of meaning</h2><a class="hp-sec-link" href="naviga">Navigate the concept spaces →</a></div>

<div class="hp-axes">${axisTiles}</div>

<div class="hp-sec"><h2>Thematic families</h2><span class="hp-sec-note">${clustersWheel.length} of ${clusters.length} · the constellations that cross authors</span></div>

<div class="radial-wheel" data-wheel="clusters" data-center="Clusters" data-center-sub="${clusters.length} in all"></div>

<div class="hp-sec"><h2>Fifteen voices</h2><span class="hp-sec-note">click an emblem to enter an author's work</span></div>

<div class="radial-wheel" data-wheel="authors" data-center="Authors" data-center-sub="${authorsWheel.length} voices"></div>

<div class="hp-sec"><h2>Three and a half centuries</h2><span class="hp-sec-note">each author placed at the year of their central work</span></div>

<div class="hp-timeline">
  <div class="hp-tl-axis"><span class="hp-tl-name"></span><span class="hp-tl-track">${tlAxis}</span><span class="hp-tl-n"></span></div>
  <div class="hp-tl-body">${tlRows}</div>
  <div class="hp-tl-foot"><span class="hp-tl-name">Author</span><span class="hp-tl-track"><em>year of the central work</em></span><span class="hp-tl-n">Works</span></div>
</div>
`
  await fs.writeFile(path.join(CONTENT, "index.md"), home)

  // ---------- Opere (main sortable/paginated works table) ----------
  const opere = `---
title: Works
---

All **${works.length.toLocaleString("en")}** works, sortable by any column, paginated, with a quick text filter. Click a heading to sort; type to filter by title, author or cluster. **Level** estimates how hard the English is to read, on the European (CEFR) scale — verse and drama leave it blank, because their line breaks make sentence-length measures meaningless.

<div id="opere-table"></div>
`
  await fs.writeFile(path.join(CONTENT, "opere.md"), opere)

  // ---------- Cerca (faceted multi-select search) ----------
  const cerca = `---
title: Search
---

Filter the ${works.length.toLocaleString("en")} works by author, cluster and any concept axis. Select chips across facets and use the **ALL / ANY** toggle to require every selected tag (intersection) or at least one (union).

<div id="cerca"></div>
`
  await fs.writeFile(path.join(CONTENT, "cerca.md"), cerca)

  // ---------- Naviga (concept-spaces wheel) ----------
  const naviga = `---
title: Navigate the concept spaces
---

Works connect through eight kinds of shared meaning. Each spoke opens the index of that concept space, where every note lists the works that use it as a searchable table.

<div class="radial-wheel" data-wheel="axes" data-center="Concept spaces" data-center-sub="8 axes"></div>

You can also [browse all works](opere) or [search by theme](cerca).
`
  await fs.writeFile(path.join(CONTENT, "naviga.md"), naviga)

  // ---------- Brani / Excerpts (atomized-unit index) ----------
  const brani = `---
title: Brani / Excerpts
---

Every chapter, story, scene, section and paragraph-level excerpt across the prose works, plays and long poems — **${excerpts.length.toLocaleString("en")}** atomized units in all, each a page of its own with a link back to its work and prev/next navigation. Sort by any column, page through, or filter by text.

<div id="brani-table"></div>
`
  await fs.writeFile(path.join(CONTENT, "brani.md"), brani)

  // ---------- Sostieni il sito (PayPal donate) ----------
  // Reuses the same PayPal business account as the sibling Physics/Mathematics sites
  // (item_name changed to "Letteratura Inglese"). Static HTML — no client script needed.
  const sostieni = `---
title: Sostieni il sito
description: Se questa raccolta di letteratura inglese ti è utile, puoi lasciare un contributo con PayPal.
---

Questo sito è **gratuito e senza pubblicità**. Se ti è utile e vuoi contribuire alle spese (dominio, costi di sviluppo), puoi lasciare un piccolo contributo con PayPal. Grazie!

<div style="display:flex;flex-wrap:wrap;gap:12px;margin:26px 0 14px;">
  <a href="https://www.paypal.com/donate/?business=4ZM48BHWAGTDL&currency_code=EUR&amount=1&item_name=Letteratura+Inglese" target="_blank" rel="noopener" style="flex:1 1 100px;text-align:center;padding:16px 12px;border-radius:10px;background:#ffc439;color:#003087;font-weight:800;font-size:1.1rem;text-decoration:none;box-shadow:0 2px 6px rgba(0,0,0,.15);">1&nbsp;€</a>
  <a href="https://www.paypal.com/donate/?business=4ZM48BHWAGTDL&currency_code=EUR&amount=2&item_name=Letteratura+Inglese" target="_blank" rel="noopener" style="flex:1 1 100px;text-align:center;padding:16px 12px;border-radius:10px;background:#ffc439;color:#003087;font-weight:800;font-size:1.1rem;text-decoration:none;box-shadow:0 2px 6px rgba(0,0,0,.15);">2&nbsp;€</a>
  <a href="https://www.paypal.com/donate/?business=4ZM48BHWAGTDL&currency_code=EUR&amount=5&item_name=Letteratura+Inglese" target="_blank" rel="noopener" style="flex:1 1 100px;text-align:center;padding:16px 12px;border-radius:10px;background:#ffc439;color:#003087;font-weight:800;font-size:1.1rem;text-decoration:none;box-shadow:0 2px 6px rgba(0,0,0,.15);">5&nbsp;€</a>
  <a href="https://www.paypal.com/donate/?business=4ZM48BHWAGTDL&currency_code=EUR&amount=10&item_name=Letteratura+Inglese" target="_blank" rel="noopener" style="flex:1 1 100px;text-align:center;padding:16px 12px;border-radius:10px;background:#ffc439;color:#003087;font-weight:800;font-size:1.1rem;text-decoration:none;box-shadow:0 2px 6px rgba(0,0,0,.15);">10&nbsp;€</a>
</div>

<p style="font-size:.92rem;margin-bottom:22px;"><a href="https://www.paypal.com/donate/?business=4ZM48BHWAGTDL&currency_code=EUR&item_name=Letteratura+Inglese" target="_blank" rel="noopener">↗ Dona un altro importo</a> · il pagamento avviene sui server sicuri di PayPal.</p>

Oppure offrimi un caffè:

<p style="margin:14px 0 6px;"><a href="https://buymeacoffee.com/gio.borghi" target="_blank" rel="noopener" style="display:inline-flex;align-items:center;gap:8px;padding:13px 22px;border-radius:10px;background:#ffdd00;color:#000;font-weight:800;font-size:1.05rem;text-decoration:none;box-shadow:0 2px 6px rgba(0,0,0,.15);">☕ Offrimi un caffè</a></p>
`
  await fs.writeFile(path.join(CONTENT, "sostieni.md"), sostieni)

  // ---------- Segnala un errore o dai un suggerimento (email relay) ----------
  // The form is hydrated by feedbackForm.inline.ts, which POSTs (no-cors, fire-and-forget)
  // to the shared Google Apps Script mail relay — the message is emailed to the teacher.
  // No database, no login. Slug -> /feedback (matches the footer link).
  const feedback = `---
title: Segnala un errore o dai un suggerimento
description: Segnala errori o proponi miglioramenti — il messaggio arriva direttamente al docente.
---

<style>
.eng-feedback{display:flex;flex-direction:column;gap:14px;max-width:640px;margin:22px 0;}
.eng-feedback .eng-field{display:flex;flex-direction:column;gap:5px;font-size:.92rem;flex:1;}
.eng-feedback .eng-row{display:flex;flex-wrap:wrap;gap:14px;}
.eng-feedback textarea,.eng-feedback input{font:inherit;padding:10px 12px;border:1px solid var(--lightgray);border-radius:8px;background:var(--light);color:var(--dark);width:100%;box-sizing:border-box;}
.eng-feedback textarea:focus,.eng-feedback input:focus{outline:2px solid var(--secondary);border-color:var(--secondary);}
.eng-feedback button{align-self:flex-start;padding:10px 20px;border:0;border-radius:8px;background:var(--secondary);color:#fff;font-weight:700;font-size:1rem;cursor:pointer;}
.eng-feedback button:disabled{opacity:.5;cursor:default;}
.eng-feedback em{color:var(--secondary);font-style:normal;}
#eng-fb-status{margin:0;font-size:.92rem;}
#eng-fb-status.fb-ok{color:#1a7f37;}
#eng-fb-status.fb-err{color:#b00020;}
.eng-privacy{font-size:.86rem;opacity:.75;}
</style>

Hai trovato un **errore**, un refuso, un problema, o hai un **suggerimento** su cosa migliorare o aggiungere? Scrivimi qui sotto — leggo tutti i messaggi.

<form id="eng-feedback-form" class="eng-feedback" autocomplete="off">
  <label class="eng-field">
    <span>Messaggio <em>*</em></span>
    <textarea name="message" rows="6" required placeholder="Es. nell'opera … c'è un refuso / un link rotto / un errore di traduzione…"></textarea>
  </label>
  <div class="eng-row">
    <label class="eng-field">
      <span>Nome <small>(facoltativo)</small></span>
      <input name="name" type="text" placeholder="Come ti chiami">
    </label>
    <label class="eng-field">
      <span>Email <small>(facoltativa, se vuoi risposta)</small></span>
      <input name="email" type="email" placeholder="tua@email.it">
    </label>
  </div>
  <button type="submit">Invia messaggio</button>
  <p id="eng-fb-status" aria-live="polite"></p>
</form>

<p class="eng-privacy">Il messaggio viene inviato al docente via email. Non serve accedere. Nessun dato viene condiviso con terzi.</p>
`
  await fs.writeFile(path.join(CONTENT, "feedback.md"), feedback)

  // ---------- Intelligenza artificiale: dichiarazione esplicita ----------
  // The footer links here with the disclosure spelled out in the link text itself,
  // so the statement is visible on every page and this page holds the detail: what
  // was generated by a model (this interface, and every Italian translation) and
  // what was not (the English texts, which are public-domain editions).
  // Slug -> /intelligenza-artificiale (matches the footer link in quartz.config.yaml).
  const ia = `---
title: Intelligenza artificiale
description: Questa interfaccia e le traduzioni italiane sono state realizzate con l'intelligenza artificiale.
---

**L'interfaccia di questo sito e tutte le traduzioni dall'inglese all'italiano sono state realizzate con l'intelligenza artificiale.**

## Che cosa è generato dall'IA

- **Il frontend.** Le pagine, la ruota della home, le tabelle delle opere e dei brani, la ricerca a faccette, le schede dei capitoli correlati: il codice che le produce è stato scritto con l'assistenza di modelli linguistici (Claude, di Anthropic).
- **Le traduzioni italiane.** Ogni testo italiano affiancato all'originale è una **traduzione automatica**, prodotta da modelli di traduzione e da modelli linguistici, e **non è stata rivista parola per parola da un traduttore umano**. Va letta come un aiuto alla lettura dell'originale, non come un'edizione italiana d'autore. Può contenere errori, fraintendimenti e resa infedele di immagini e giochi di parole.

## Che cosa non è generato dall'IA

- **I testi inglesi.** Sono edizioni di pubblico dominio (in gran parte dal Project Gutenberg), riprodotte come sono.
- **La struttura critica.** La selezione delle opere, i temi, i motivi, le forme, i personaggi e i raggruppamenti tematici sono scelte editoriali, anche là dove l'estrazione è stata assistita da un modello.

Se trovi una traduzione sbagliata o un errore in una pagina, [segnalalo](/feedback): è il modo più veloce per farlo correggere.
`
  await fs.writeFile(path.join(CONTENT, "intelligenza-artificiale.md"), ia)

  // SPA backward-compat: old per-atom URLs (/testi/<author>/<sub>/<work>/<chapter>/
  // <part>) no longer exist as pages. Emit a 404 that rewrites any such path to the
  // work's single page + atom fragment (/testi/<author>/<sub>/<work>#<chapter>--<part>),
  // so existing deep links, bookmarks and search-engine results keep resolving. One
  // file, works on GitHub Pages and Cloudflare Pages alike. SPA-only (in classic mode
  // the atom pages exist, so a redirect here could mis-fire on genuine 404s).
  if (SPA) {
    const notFound =
      `---\ntitle: "Pagina non trovata · Not found"\n---\n\n` +
      `<div class="nf-msg"><p><strong>Pagina non trovata.</strong> Reindirizzamento in corso…</p>\n` +
      // Drive the home link via onclick (href="#", a same-page fragment) so Quartz does NOT
      // crawl it as an internal link — otherwise the 404 page becomes a backlink source for
      // the homepage, leaving a junk "Backlinks" box (only "Pagina non trovata") on a page
      // that has no real backlinks. The JS redirect above already handles atom/legacy URLs.
      `<p><a href="#" onclick="location.replace('/');return false;">Torna alla home</a></p></div>\n\n` +
      `<script>\n(function(){\n` +
      `  var p=decodeURIComponent(location.pathname).replace(/\\/index\\.html$/,"").replace(/\\/$/,"");\n` +
      `  var m=p.match(/^(.*)\\/testi\\/([^/]+)\\/(atomized|plays|long)\\/([^/]+)\\/(.+)$/i);\n` +
      `  if(m){\n` +
      `    var atom=m[5].replace(/\\//g,"--");\n` +
      `    location.replace(m[1]+"/testi/"+m[2]+"/"+m[3]+"/"+m[4]+"#"+atom);\n` +
      `    return;\n` +
      `  }\n` +
      // Dickinson cluster-SPA restructure: retired per-poem reading + works metadata
      // URLs (no trailing segment, so the regex above skips them) -> new cluster frag,
      // via a static lookup map. Fetched only on a 404, no cost on real pages.
      `  var d=p.match(/^(.*)\\/((?:testi\\/dickinson\\/atomized|works)\\/.+)$/i);\n` +
      `  if(d){\n` +
      `    fetch(d[1]+"/static/dickinson_redirects.json").then(function(r){return r.ok?r.json():null;}).then(function(map){\n` +
      `      if(map&&map[d[2]]) location.replace(d[1]+"/"+map[d[2]]);\n` +
      `    }).catch(function(){});\n` +
      `  }\n})();\n</script>\n`
    await fs.writeFile(path.join(CONTENT, "404.md"), notFound)
  }

  // author landing pages (NLP footprint + EN/IT bio tabs + scoped works table).
  // Regenerated here every run because content/ is wiped at the top of main().
  // Interpreter: macOS/CI have no bare `python` (only `python3`), Windows has no `python3`.
  // Hardcoding either silently skips the author pages -- the try/catch below turns a missing
  // interpreter into a one-line warning that is easy to miss in a long build log.
  const PY = process.env.PYTHON || (process.platform === "win32" ? "python" : "python3")
  try {
    execSync(`${PY} scripts/make-author-pages.py`, {
      cwd: ROOT,
      stdio: "inherit",
    })
  } catch (e) {
    // Loud: without these, every author landing page is missing from the build.
    console.error("\n!!! AUTHOR PAGES NOT GENERATED — the site will be missing them !!!")
    console.error("    " + e.message)
    console.error(`    interpreter tried: ${PY} (override with PYTHON=/path/to/python)\n`)
  }

  console.log(
    `copied ${written} notes, ${unitsCopied} unit pages; indexed ${works.length} works, ` +
      `${excerpts.length} excerpts, ${authors.length} authors, ${clusters.length} clusters`,
  )

  // ---- final pass: unlink what leads nowhere ----
  // The vault's tagger linked every bare occurrence of a word that also happens to be a
  // work title. Where nothing answers to the name that is a plain 404 ("[[Alone|alone]]");
  // where something does ("[[house]]" -> Chesterton's essay page) the link lands, but it
  // still does not mean the essay. Both come from the same defect, so both are degraded
  // to plain text: a genuine reference is written as a title ("see [[House]]") and keeps
  // resolving. The same pass drops links to a name the vault never carried at all
  // ("[[Cardenio]]", "[[Pastoral]]"), which is only decidable here, once every page is
  // emitted. The counters keep the two halves apart in the log.
  const SPARE_LINKED_SURFACE_FORMS = false
  const emitted = []
  const walkOut = async (dir) => {
    for (const e of await fs.readdir(dir, { withFileTypes: true })) {
      const p = path.join(dir, e.name)
      if (e.isDirectory()) await walkOut(p)
      else if (e.name.endsWith(".md")) emitted.push(p)
    }
  }
  await walkOut(CONTENT)
  const pageSlugs = new Set()
  const pageBasenames = new Set()
  for (const p of emitted) {
    const rel = path.relative(CONTENT, p).slice(0, -3).split(path.sep).join("/")
    pageSlugs.add(sluggify(rel))
    pageBasenames.add(sluggify(path.basename(p, ".md")))
  }
  // Quartz resolves a single-segment target against page basenames, a multi-segment one
  // against the whole slug — so "lands somewhere" has to be tested the same way.
  const lands = (t) => {
    const s = sluggify(String(t).trim())
    return pageSlugs.has(s) || (!s.includes("/") && pageBasenames.has(s))
  }
  const keepLink = (target, alias) =>
    linkIndex.isSurfaceForm(target, alias)
      ? SPARE_LINKED_SURFACE_FORMS && lands(target)
      : lands(target)
  const deadStripped = new Map()
  let noisyTotal = 0
  for (const p of emitted) {
    const before = await fs.readFile(p, "utf8")
    const { md, stripped } = stripDeadLinks(before, keepLink)
    if (!stripped.length) continue
    for (const t of stripped) {
      deadStripped.set(t, (deadStripped.get(t) || 0) + 1)
      if (lands(t)) noisyTotal++
    }
    await fs.writeFile(p, md)
  }
  const deadTotal = [...deadStripped.values()].reduce((a, b) => a + b, 0)
  const topDead = [...deadStripped.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)
    .map(([t, n]) => `${t}=${n}`)
    .join(" ")
  console.log(
    `wikilinks: ${linkStats.resolved} resolved, ${linkStats.subwork} to sub-work fragments, ` +
      `${linkStats.left} left as-is; ${deadTotal} unlinked over ${deadStripped.size} targets ` +
      `(${deadTotal - noisyTotal} leading nowhere, ${noisyTotal} noisy-but-live) [${topDead}]`,
  )
}
main()
