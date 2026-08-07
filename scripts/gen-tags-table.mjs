// Post-build: replace the giant /tags/ aggregator page (was ~48 MB: it inlined every
// tag -> all member pages -> each page's full tag-chip set) with a lightweight client
// table. Two outputs, both written into the built site (run AFTER the Quartz build,
// BEFORE deploy):
//   1) static/tags.json  — [{tag,type,count}] for every tag INCLUDING segment prefixes
//      (person/x also yields the `person` tag), matching Quartz's own tag-page set so
//      every row links to an existing /tags/<tag>/ page.
//   2) tags/index.html   — body swapped for <div id="tags-table">; tags-table.js/.css
//      render the searchable/sortable/paginated table client-side from tags.json.
//
// Usage: node scripts/gen-tags-table.mjs <builtSiteDir>
import fs from "fs"
import path from "path"

const OUT = process.argv[2] || "public"
const ci = path.join(OUT, "static", "contentIndex.json")
const tagsHtml = path.join(OUT, "tags", "index.html")

if (!fs.existsSync(ci)) {
  console.error("gen-tags-table: missing", ci)
  process.exit(1)
}

// ---- 1. aggregate tags (with segment prefixes) from the content index ----
const index = JSON.parse(fs.readFileSync(ci, "utf8"))
const counts = new Map() // tag -> Set of slugs (dedupe a page counted once per tag)

// person/amedeo-avogadro -> ["person", "person/amedeo-avogadro"]
function prefixes(tag) {
  const parts = tag.split("/")
  const out = []
  for (let i = 1; i <= parts.length; i++) out.push(parts.slice(0, i).join("/"))
  return out
}

for (const slug of Object.keys(index)) {
  const tags = index[slug]?.tags
  if (!Array.isArray(tags)) continue
  const seen = new Set()
  for (const raw of tags) {
    if (!raw || raw === "") continue
    for (const t of prefixes(String(raw))) seen.add(t)
  }
  for (const t of seen) {
    if (!counts.has(t)) counts.set(t, 0)
    counts.set(t, counts.get(t) + 1)
  }
}

const rows = [...counts.entries()]
  .map(([tag, count]) => ({
    tag,
    type: tag.includes("/") ? tag.split("/")[0] : "generale",
    count,
  }))
  .sort((a, b) => b.count - a.count || a.tag.localeCompare(b.tag))

fs.writeFileSync(path.join(OUT, "static", "tags.json"), JSON.stringify(rows))
console.log(`gen-tags-table: wrote static/tags.json (${rows.length} tags)`)

// ---- 2. slim the tag index pages: swap the huge listing for the table placeholder ----
// Quartz emits the SAME page twice — tags/index.html and tags.html — and both carry the
// full listing. Slimming only the first left a 25.3 MB tags.html, which Cloudflare Pages
// refuses outright (25 MiB per-file cap), failing the whole deploy.
// The asset paths are relative because the GitHub Pages copy is served from a subpath
// (/raccolta-letteratura-inglese/), where an absolute /static would 404 — so each copy
// gets the prefix its own depth requires.
function slim(file, assetPrefix) {
  if (!fs.existsSync(file)) {
    console.error("gen-tags-table: missing", file, "(skipped)")
    return false
  }
  let h = fs.readFileSync(file, "utf8")
  const before = h.length

  // Content starts at the first popover-hint that actually wraps an <article> and ends at
  // the afterBody stacked-pages container — replace that whole span with one placeholder.
  // Anchoring on the header text instead ("Tag Index</h1>") only works for tags/index.html:
  // the flat tags.html twin carries an EMPTY page-header — no title, no h1 — so it kept its
  // full 25 MB listing. The page-header's own popover-hint is empty, hence the <article>.
  const start = h.indexOf('<div class="popover-hint"><article')
  const end = h.indexOf('<div class="page-footer"')
  if (!(start > 0 && end > start)) {
    console.error(
      `gen-tags-table: anchors not found in ${file} (start,end)=`,
      start,
      end,
      "— NOT rewritten",
    )
    return false
  }
  const placeholder =
    '<div class="popover-hint"><article class=""><div id="tags-table"></div></article></div>'
  h = h.slice(0, start) + placeholder + h.slice(end)

  if (!h.includes("tags-table.css")) {
    h = h.replace("</head>", `<link rel="stylesheet" href="${assetPrefix}tags-table.css"></head>`)
  }
  if (!h.includes("tags-table.js")) {
    h = h.replace("</body>", `<script src="${assetPrefix}tags-table.js" defer></script></body>`)
  }

  fs.writeFileSync(file, h)
  console.log(
    `gen-tags-table: rewrote ${path.relative(OUT, file)} ${(before / 1e6).toFixed(1)}MB -> ${(h.length / 1e3).toFixed(1)}KB`,
  )
  return true
}

const okNested = slim(tagsHtml, "../static/")
const okFlat = slim(path.join(OUT, "tags.html"), "static/")
if (!okNested && !okFlat) process.exit(1)

// ---- 3. guard the Cloudflare Pages per-file cap ----
// A single oversized file rejects the whole deploy, and the build itself gives no hint:
// the 25.3 MB tags.html surfaced only when wrangler refused the upload.
const CAP = 25 * 1024 * 1024
const oversized = []
const walk = (dir) => {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name)
    if (e.isDirectory()) walk(p)
    else if (fs.statSync(p).size > CAP) oversized.push([path.relative(OUT, p), fs.statSync(p).size])
  }
}
walk(OUT)
if (oversized.length) {
  for (const [f, s] of oversized) {
    console.error(`gen-tags-table: ${f} is ${(s / 1024 / 1024).toFixed(1)} MiB — over the 25 MiB`)
  }
  console.error("gen-tags-table: Cloudflare Pages will refuse this deploy")
  process.exit(1)
}
