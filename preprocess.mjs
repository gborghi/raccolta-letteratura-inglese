// Preprocess the Obsidian "Knowledge Graph" (English literature) vault into Quartz content.
// - copies notes into ./content
// - strips wikilinks to unpublished Authors/* full-text + section files (keeps the label as text)
// - builds ./quartz/static/index.json consumed by the works-table + faceted search renderers
// - generates an editorial home page (index.md), the works table page (opere.md),
//   and the faceted search page (cerca.md)
import { promises as fs } from "node:fs"
import path from "node:path"
import matter from "gray-matter"

const NUL = String.fromCharCode(0)

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
const ROOT = path.resolve(".")
const CONTENT = path.join(ROOT, "content")
const STATIC_JSON = path.join(ROOT, "quartz", "static", "index.json")

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
        .replace(/#/g, ""),
    )
    .join("/")
    .replace(/\/$/, "")
}
function slugFromRel(rel) {
  const noExt = rel.replace(/\.md$/, "").split(path.sep).join("/")
  return sluggify(noExt)
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
}

// Transform note body: strip wikilinks pointing at unpublished Authors/* files,
// keeping the display label (or last path segment) as plain text.
function transform(content) {
  // [[Authors/...|Label]] -> Label ; [[Authors/...]] -> last segment
  content = content.replace(/\[\[Authors\/[^\]|]*\|([^\]]+)\]\]/g, "$1")
  content = content.replace(/\[\[Authors\/([^\]|]+)\]\]/g, (_m, p) => {
    const seg = p.split("/").pop().replace(/\.md$/, "")
    return seg
  })
  // The whole "### Sections / scenes" block links into Authors/* — drop those bullet links,
  // leaving labels. Already handled by the two replaces above (labels remain).
  return content
}

async function walk(dir, base = dir, out = []) {
  for (const ent of await fs.readdir(dir, { withFileTypes: true })) {
    const full = path.join(dir, ent.name)
    if (ent.isDirectory()) await walk(full, base, out)
    else if (ent.name.endsWith(".md")) out.push(path.relative(base, full))
  }
  return out
}

async function main() {
  await fs.rm(CONTENT, { recursive: true, force: true })
  await fs.mkdir(CONTENT, { recursive: true })
  const files = await walk(VAULT)

  // ---- PASS 1: read everything, build the works index + a title->href map ----
  const parsed = [] // { rel, data, content }
  const works = []
  const titleToHref = new Map() // note basename (wikilink target) -> work href
  for (const rel of files) {
    const relU = rel.replace(/\\/g, "/")
    if (relU === "_Home.md") continue
    const raw = await fs.readFile(path.join(VAULT, rel), "utf8")
    const { data, content } = parseFrontmatter(raw)
    parsed.push({ rel, relU, data, content })
    if (data.type === "work") {
      const tags = Array.isArray(data.tags) ? data.tags : data.tags ? [data.tags] : []
      const href = slugFromRel(rel)
      const base = path.basename(rel).replace(/\.md$/, "")
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
    }
  }

  // ---- PASS 2: write content; convert concept-note "## Works" lists to tables ----
  // concepts.json maps a concept-note slug -> { title, type, works: [{href,...}] }
  const conceptIndex = {}
  let written = 0
  for (const { rel, relU, data, content } of parsed) {
    let newContent = transform(content)
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

    const dest = path.join(CONTENT, rel)
    await fs.mkdir(path.dirname(dest), { recursive: true })
    await fs.writeFile(dest, matter.stringify(newContent, { ...data }))
    written++
  }

  await fs.mkdir(path.dirname(STATIC_JSON), { recursive: true })
  await fs.writeFile(STATIC_JSON, JSON.stringify(works))
  await fs.writeFile(
    path.join(ROOT, "quartz", "static", "concepts.json"),
    JSON.stringify(conceptIndex),
  )

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
    Hemingway: "Grace under pressure, the spare modern sentence.",
  }
  const authorCounts = {}
  for (const w of works) authorCounts[w.author] = (authorCounts[w.author] || 0) + 1
  const authorCards = authors
    .map(
      (a) =>
        `<a class="author-card" href="cerca" data-cerca-author="${a}"><span class="author-card-name">${a}</span><span class="author-card-count">${authorCounts[a] || 0} works</span><span class="author-card-blurb">${authorBlurb[a] || ""}</span></a>`,
    )
    .join("\n")

  const topClusters = clusters
    .map((c) => ({ c, n: works.filter((w) => w.cluster === c).length }))
    .sort((a, b) => b.n - a.n)
    .slice(0, 18)
  const clusterChips = topClusters
    .map((x) => `<a class="cluster-chip" href="${sluggify("Clusters/" + x.c)}">${x.c} <span>${x.n}</span></a>`)
    .join("\n")

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

<div class="author-grid">
${authorCards}
</div>

## Thematic clusters

The ${clusters.length} clusters group works by the constellations of theme and form they share.

<div class="cluster-cloud">
${clusterChips}
</div>

<p style="margin-top:1.2rem"><a href="opere">See the full sortable table of works →</a></p>
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

  console.log(`copied ${written} notes, indexed ${works.length} works, ${authors.length} authors, ${clusters.length} clusters`)
}
main()
