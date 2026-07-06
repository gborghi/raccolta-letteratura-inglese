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
function readabilityOf(text) {
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

const VAULT = "E:/giovanni/Dropbox/insegnamento/Wiligelmo/SubjectBrain/English/Knowledge Graph"
const AUTHORS_DIR = "E:/giovanni/Dropbox/insegnamento/Wiligelmo/SubjectBrain/English/Authors"
// Authors fully excluded from the PUBLIC site (e.g. still under copyright).
// Their work pages, full text, atomized units and index rows are all dropped.
const EXCLUDE_AUTHORS = new Set(["Hemingway"])
const ROOT = path.resolve(".")
const CONTENT = path.join(ROOT, "content")
// Where atomized excerpts / play scenes / long-poem sections get published.
const TESTI_REL = "Testi"
const STATIC_JSON = path.join(ROOT, "quartz", "static", "index.json")
const KW_JSON = path.join(ROOT, "quartz", "static", "works_kw.json")
// LLM-extracted per-chapter tags (characters/themes/plot), committed source of
// truth for #17 chapter interlinking. Optional: absent on a fresh checkout.
const CHAPTER_TAGS = path.join(ROOT, "data", "chapter_tags.json")

const STOPWORDS = new Set((
  // English
  "a about an and are as at be been but by can did do does each for from had has have he her here him his how i if in into is it its no not of on one or our so that the their them then there these they this to too two up was we were what when where which who will with you your " +
  // Italian
  "ad ai al alla alle allo agli anche ancora avere aveva avevano che chi ci coi col come con cosa cui da dai dal dalla dalle dallo degli dei del della delle dello di dove due ecco ed era erano essere fa fare fino fra gli ha hai hanno ho il in io la le lei li lo loro ma me mentre mi mia mie miei mio ne negli nei nel nella nelle nello no noi non nostra nostre nostri nostro o od ogni ognuno oppure per perche perché piu più po poi puo può qual quale quali quando quanta quante quanti quanto quasi quel quella quelle quelli quello questa queste questi questo qui se sei senza si sia siamo siete solo sono sopra sotto sta stata state stati stato su sua sue sui sul sulla sulle sullo suo suoi tra tre tu tua tue tuo tuoi tutta tutte tutti tutto un una uno vi voi"
).split(/\s+/).filter(Boolean))

function keywords(content) {
  const cleaned = content
    .replace(/\[\[(?:[^\]|]+\|)?([^\]]+)\]\]/g, " $1 ") // keep wikilink label
    .replace(/\[[^\]]*\]\([^)]*\)/g, " ")      // md links
    .replace(/[`*_>#|]/g, " ")                  // md syntax
    .toLowerCase()
    .replace(/[^a-zà-ÿ\s]/g, " ")               // letters only
  const seen = new Set()
  for (const w of cleaned.split(/\s+/)) {
    if (w.length < 3 || STOPWORDS.has(w)) continue
    seen.add(w)
  }
  return [...seen].join(" ")
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

// Sort key that ignores a leading article (for tables/listings).
function sortKeyNoArticle(s) {
  return String(s)
    .toLowerCase()
    .replace(/^\s*(the|a|an)\s+/, "")
    .trim()
}

function prettyFromFilename(name) {
  return name
    .replace(/\.md$/, "")
    .replace(/_/g, " ")
    .replace(/\s+/g, " ")
    .trim()
}

// Classify a unit relative path (under an author dir) -> { unitType, order }.
function classifyUnit(relParts, fileName) {
  const f = fileName.replace(/\.md$/, "")
  let m
  if ((m = f.match(/^part_(\d+)$/i))) return { unitType: "excerpt", order: parseInt(m[1], 10) }
  if ((m = f.match(/^Chapter_(\d+)/i))) return { unitType: "chapter", order: parseInt(m[1], 10) }
  if ((m = f.match(/^Story_(\d+)/i))) return { unitType: "story", order: parseInt(m[1], 10) }
  if ((m = f.match(/^Section_(\d+)/i))) return { unitType: "section", order: parseInt(m[1], 10) }
  if ((m = f.match(/^Scene_(\d+)/i))) return { unitType: "scene", order: parseInt(m[1], 10) }
  return { unitType: "work", order: 0 }
}

// Publish all atomized excerpts, play scenes and long-poem sections as pages.
// Returns { unitHref, excerpts } where unitHref maps "Authors/.../x[.md]" -> slug,
// and excerpts is the excerpt-level index for the Brani page.
// Merge English + Italian into one page (the OlimpiadiMatematica/qlang pattern):
// the default (EN) body, a hidden `<span class="qlang-split">` marker, then the
// translated (IT) body — all plain markdown so it renders normally. qlang.inline.ts
// partitions the article DOM at the marker and toggles language client-side (no
// navigation, no server call).
function bilingualBody(en, it) {
  return (
    `<div class="qlang-switch" data-default="en"></div>\n\n` +
    en +
    `\n\n<span class="qlang-split" data-lang="it"></span>\n\n` +
    it
  )
}

async function publishUnits(rawSourceToWork, translations = new Map()) {
  const unitHref = new Map()
  const excerpts = []
  const excerptsKw = {}
  const workUnits = new Map() // work href -> [{ slug, title, relU }] reading units (TOC)
  const workContainers = new Map() // work href -> { slug, title, relU } full-text page (single-essay fallback)
  let copied = 0

  const authors = await fs.readdir(AUTHORS_DIR, { withFileTypes: true })
  for (const adir of authors) {
    if (!adir.isDirectory()) continue
    const author = adir.name
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
        const parentWorkHref =
          rawSourceToWork.get(workDir) || rawSourceToWork.get(normWorkKey(workDir)) || null
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
          const ad = a.segs.slice(0, -1).join("/")
          const bd = b.segs.slice(0, -1).join("/")
          if (ad !== bd) return ad < bd ? -1 : 1
          return a.order - b.order
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
            `author: ${JSON.stringify(author)}\n` +
            `unitType: ${it.unitType}\n` +
            (parentWorkHref ? `parentWork: ${JSON.stringify(parentWorkHref)}\n` : "") +
            `tags:\n  - graph/excerpt\n  - author/${author}\n` +
            `---\n\n`

          // Remove junk separators, strip the leading H1 (Quartz renders the
          // frontmatter title as a page heading automatically; keeping the body
          // H1 produces a double-title), then prepend the nav block.
          let outBody = stripJunkSeparators(body)
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
            await fs.writeFile(dest, fm + bilingualBody(outBody, tr.body_it || outBody))
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
            const kw = keywords(body)
            if (kw) excerptsKw[it.slug] = kw
          }
        }
      }
    }
  }
  return { unitHref, excerpts, excerptsKw, copied, workUnits, workContainers }
}

async function main() {
  await fs.rm(CONTENT, { recursive: true, force: true })
  await fs.mkdir(CONTENT, { recursive: true })
  const files = await walk(VAULT)

  // ---- PASS 1: read everything, build the works index + a title->href map ----
  const parsed = [] // { rel, data, content }
  const works = []
  const kwIndex = {} // kw mapping for works
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
      const addKey = (k) => {
        if (!k) return
        rawSourceToWork.set(k, href)
        rawSourceToWork.set(normWorkKey(k), href)
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
      let n = 0
      for (const [prefix, field] of AXES) {
        const vals = tags
          .filter((t) => t.startsWith(prefix + "/"))
          .map((t) => t.slice(prefix.length + 1))
        rec[field] = vals
        n += vals.length
      }
      rec.nconnections = n
      works.push(rec)
      titleToHref.set(base, href)
      
      const kw = keywords(content)
      if (kw) kwIndex[href] = kw
    }
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
  const { unitHref, excerpts, excerptsKw, copied: unitsCopied, workUnits, workContainers } = await publishUnits(rawSourceToWork, translations)
  await fs.writeFile(
    path.join(ROOT, "quartz", "static", "excerpts.json"),
    JSON.stringify(excerpts),
  )
  await fs.writeFile(
    path.join(ROOT, "quartz", "static", "excerpts_kw.json"),
    JSON.stringify(excerptsKw),
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
    const topFolder = relU.split("/")[0]
    const axis = AXIS_FOLDERS[topFolder]

    if (axis && data.type) {
      // Collect the work wikilinks under "## Works" and map them to hrefs.
      const linkRe = /\[\[([^\]|#]+?)(?:\|[^\]]+)?\]\]/g
      const seen = new Set()
      const found = []
      let m
      while ((m = linkRe.exec(content))) {
        const target = m[1].trim()
        const href = titleToHref.get(target)
        if (href && !seen.has(href)) {
          seen.add(href)
          found.push(href)
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
        newContent = newContent.replace(
          /(^|\n)##\s+Works\s*\n[\s\S]*?(?=\n##\s|\n#[^#]|\n#graph|$)/,
          `$1## Works\n\n<div class="concept-works" data-slug="${slug}"></div>\n`,
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

    // Lowercase the output path (v5 link-case fix): pages emit at the file path,
    // and our hrefs are lowercased in sluggify(), so the files must be lowercase too.
    const dest = path.join(CONTENT, rel.toLowerCase())
    await fs.mkdir(path.dirname(dest), { recursive: true })
    const trPage = translations.get(relU.toLowerCase())
    if (trPage) {
      let itBody = trPage.body_it || newContent
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

  await fs.mkdir(path.dirname(STATIC_JSON), { recursive: true })
  await fs.writeFile(STATIC_JSON, JSON.stringify(works))
  await fs.writeFile(KW_JSON, JSON.stringify(kwIndex))
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
          const m = unitMeta.get(oh) || {}
          const plot = tags[oh]?.plot || ""
          return {
            href: oh,
            title: m.title || oh,
            work: m.work || "",
            shared: v.shared,
            plot: plot.length > 160 ? plot.slice(0, 157) + "…" : plot,
          }
        })
      if (top.length) chapterRelated[href] = top
    }
    await fs.writeFile(
      path.join(ROOT, "quartz", "static", "chapter_related.json"),
      JSON.stringify(chapterRelated),
    )
    console.log(
      `chapter_related.json: ${Object.keys(chapterRelated).length} chapters with related links`,
    )
  } catch (e) {
    if (e.code !== "ENOENT") throw e
    console.log("chapter_tags.json absent — skipping chapter interlinking")
  }

  const authors = [...new Set(works.map((w) => w.author).filter(Boolean))].sort()
  const clusters = [...new Set(works.map((w) => w.cluster).filter(Boolean))].sort()

  // ---------- Home (editorial landing) ----------
  const authorBlurb = {
    Shakespeare: "Plays, sonnets, the whole canon of the English stage.",
    Keats: "Odes, sonnets and the Romantic pursuit of beauty.",
    Dickinson: "The compressed lyric interior — death, faith, the self.",
    Eliot: "Modernist fragments, the metropolis, spiritual drought.",
    Chesterton: "Essays, paradox, ballads and Christian wit.",
    Dickens: "The social novel, the city, the common life.",
    Austen: "Irony, manners and the marriage plot.",
    Bronte: "Passion, the gothic and the moral interior.",
    Poe: "Terror, the grotesque and the architecture of dread.",
    Wilde: "Epigram, aestheticism and the comedy of surfaces.",
    Coleridge: "Imagination, the supernatural and the One Life.",
    Whitman: "The open road, democracy and the body electric.",
  }
  const authorCounts = {}
  for (const w of works) authorCounts[w.author] = (authorCounts[w.author] || 0) + 1
  void authorBlurb

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
    { label: "Topoi", img: "axis-topoi", href: "Topoi/", n: axisNoteCount("Topoi") },
    { label: "Archetipi", img: "axis-archetipi", href: "Archetypes/", n: axisNoteCount("Archetypes") },
    { label: "Motivi", img: "axis-motivi", href: "Motifs/", n: axisNoteCount("Motifs") },
    { label: "Concetti", img: "axis-concetti", href: "Concepts/", n: axisNoteCount("Concepts") },
    { label: "Forme", img: "axis-forme", href: "Forms/", n: axisNoteCount("Forms") },
    { label: "Riferimenti Storici", img: "axis-storia", href: "Historical-References/", n: axisNoteCount("Historical References") },
    { label: "Ambientazioni", img: "axis-ambientazioni", href: "Settings/", n: axisNoteCount("Settings") },
    { label: "Personaggi", img: "axis-personaggi", href: "Characters/", n: axisNoteCount("Characters") },
  ].map((a) => ({ label: a.label, sub: String(a.n), img: a.img, href: a.href }))

  // Map the 12 biggest clusters to their emblem files (by leading keyword).
  const clusterEmblem = [
    [/^Death/, "cluster-death"],
    [/Frustrated Love/, "cluster-love"],
    [/^Grief/, "cluster-grief"],
    [/^Sonnet/, "cluster-sonnet"],
    [/^Wonder/, "cluster-wonder"],
    [/^Satire/, "cluster-satire"],
    [/^Transience/, "cluster-transience"],
    [/^Lyric/, "cluster-lyric"],
    [/^Money/, "cluster-money"],
    [/^Seasons/, "cluster-seasons"],
    [/^Nature ·/, "cluster-nature"],
    [/^Sea ·/, "cluster-sea"],
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

  const wheelData = { authors: authorsWheel, axes: axesWheel, clusters: clustersWheel }
  await fs.writeFile(
    path.join(ROOT, "quartz", "static", "wheel.json"),
    JSON.stringify(wheelData),
  )

  const home = `---
title: English Literature — A Knowledge Graph
---

<div class="hero">
  <div class="hero-art" aria-hidden="true">
    <!-- PLACEHOLDER hero art — replace with a hand-crafted SVG/illustration -->
    <svg viewBox="0 0 200 200" width="180" height="180" role="img" aria-label="open book">
      <g fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
        <path d="M100 50 C70 35 40 35 20 45 L20 150 C40 140 70 140 100 155"/>
        <path d="M100 50 C130 35 160 35 180 45 L180 150 C160 140 130 140 100 155"/>
        <path d="M100 55 L100 150"/>
        <path d="M35 65 H80 M35 85 H80 M35 105 H80 M120 65 H165 M120 85 H165 M120 105 H165"/>
      </g>
    </svg>
  </div>
  <div class="hero-text">
    <p class="hero-kicker">A connected reading of the English canon</p>
    <h1 class="hero-title">English Literature</h1>
    <p class="hero-lead">${works.length.toLocaleString("en")} works by ${authors.length} authors, woven together through shared <em>topoi, archetypes, motifs, themes, forms, settings and characters</em>. Open a work to follow its connections; open a concept to see every work that shares it.</p>
    <p class="hero-actions">
      <a class="btn btn-primary" href="opere">Browse all works</a>
      <a class="btn" href="cerca">Search by theme</a>
    </p>
  </div>
</div>

## Authors

Spin through the thirteen authors — each emblem opens that author's works.

<div class="radial-wheel" data-wheel="authors" data-center="Authors" data-center-sub="13 voices"></div>

## Thematic clusters

The ${clusters.length} clusters group works by the constellations of theme and form they share. Here are the twelve largest.

<div class="radial-wheel" data-wheel="clusters" data-center="Clusters" data-center-sub="62 in all"></div>

<p style="margin-top:1.2rem; text-align:center"><a class="btn" href="naviga">Explore the concept spaces →</a> &nbsp; <a class="btn btn-primary" href="opere">All works table →</a></p>
`
  await fs.writeFile(path.join(CONTENT, "index.md"), home)

  // ---------- Opere (main sortable/paginated works table) ----------
  const opere = `---
title: Works
---

All **${works.length.toLocaleString("en")}** works, sortable by any column, paginated, with a quick text filter. Click a heading to sort; type to filter by title, author or cluster.

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

  // author landing pages (NLP footprint + EN/IT bio tabs + scoped works table).
  // Regenerated here every run because content/ is wiped at the top of main().
  try {
    execSync("python scripts/make-author-pages.py", {
      cwd: path.dirname(fileURLToPath(import.meta.url)),
      stdio: "inherit",
    })
  } catch (e) {
    console.warn("author pages generation skipped:", e.message)
  }

  console.log(
    `copied ${written} notes, ${unitsCopied} unit pages; indexed ${works.length} works, ` +
      `${excerpts.length} excerpts, ${authors.length} authors, ${clusters.length} clusters`,
  )
}
main()
