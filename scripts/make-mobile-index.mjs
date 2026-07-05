// Post-build: derive a LIGHT search index for mobile from the full contentIndex.json.
// Mobile browsers OOM parsing the full ~27MB index; this keeps title/tags/links + a
// short content snippet so the on-device FlexSearch build stays small. Desktop keeps
// the full index (loaded via fetchData); only mobile fetches contentIndexMobile.json.
// Run AFTER `npx quartz build`, before uploading the Pages artifact.
import fs from "fs"
import path from "path"

const dir = "public/static"
const full = path.join(dir, "contentIndex.json")
const outPath = path.join(dir, "contentIndexMobile.json")
const SNIPPET = 160 // chars of content kept per entry

if (!fs.existsSync(full)) {
  console.error(`make-mobile-index: ${full} not found — skipping`)
  process.exit(0)
}
const raw = JSON.parse(fs.readFileSync(full, "utf8"))
// contentIndex.json top level is a map slug -> item (defensive: unwrap {content:{...}})
const map = raw && raw.content && typeof raw.content === "object" && !raw.content.slug ? raw.content : raw
const out = {}
for (const [slug, it] of Object.entries(map)) {
  if (!it || typeof it !== "object") continue
  // Drop links/filePath: the FlexSearch index only uses title/content/tags, and
  // aggregator notes carry huge links[] (every work) that bloat the index.
  out[slug] = {
    slug: it.slug,
    title: it.title,
    tags: it.tags,
    content: typeof it.content === "string" ? it.content.slice(0, SNIPPET) : "",
  }
}
const json = JSON.stringify(out)
fs.writeFileSync(outPath, json)
const fullSize = fs.statSync(full).size
console.log(
  `make-mobile-index: ${Object.keys(out).length} entries | ` +
    `${(fullSize / 1e6).toFixed(1)}MB -> ${(json.length / 1e6).toFixed(1)}MB (mobile)`,
)
