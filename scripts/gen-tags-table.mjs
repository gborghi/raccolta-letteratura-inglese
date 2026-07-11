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

const OUT = process.argv[2] || "E:/giovanni/quartz-build/fisica-public"
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

// ---- 2. slim tags/index.html: swap the huge listing for the table placeholder ----
if (!fs.existsSync(tagsHtml)) {
  console.error("gen-tags-table: missing", tagsHtml, "(skipped html rewrite)")
  process.exit(0)
}
let h = fs.readFileSync(tagsHtml, "utf8")
const before = h.length

// content starts right after the page-header (…Tag Index</h1></div></div>) and ends at
// the afterBody stacked-pages container — replace that whole span with one placeholder.
const hdr = h.indexOf("Tag Index</h1>")
const start = hdr >= 0 ? h.indexOf("</div></div>", hdr) + "</div></div>".length : -1
const end = h.indexOf('<div class="page-footer"')
if (start > 0 && end > start) {
  const placeholder =
    '<div class="popover-hint"><article class=""><div id="tags-table"></div></article></div>'
  h = h.slice(0, start) + placeholder + h.slice(end)
} else {
  console.error("gen-tags-table: anchors not found (start,end)=", start, end, "— html NOT rewritten")
  process.exit(1)
}

// inject css in <head> and js before </body> (absolute /static paths; site served from root)
// Relative ../static paths: eng-lit is served from a subpath
// (/raccolta-letteratura-inglese/), so absolute /static would 404. From /tags/,
// ../static resolves to the subpath's static dir on any host.
if (!h.includes("tags-table.css")) {
  h = h.replace("</head>", '<link rel="stylesheet" href="../static/tags-table.css"></head>')
}
if (!h.includes("tags-table.js")) {
  h = h.replace("</body>", '<script src="../static/tags-table.js" defer></script></body>')
}

fs.writeFileSync(tagsHtml, h)
console.log(
  `gen-tags-table: rewrote tags/index.html ${(before / 1e6).toFixed(1)}MB -> ${(h.length / 1e3).toFixed(1)}KB`,
)
