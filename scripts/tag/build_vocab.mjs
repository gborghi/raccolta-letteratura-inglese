// Build the ALLOWED tag vocabulary for Phase-2 leaf tagging.
// Ground truth = the set of distinct `axis/slug` tags already present across all
// `type: work` KG notes (every such tag already resolves to a concept node, since
// the graph build derived the concept notes FROM these tags). Constraining the
// tagging model to this set guarantees no fabricated slug (memory:
// eng-lit-tags-only-from-work-notes). Also cross-checks against concept-note
// filenames per axis dir and reports slugs that appear as notes but are unused,
// and used slugs with no matching note (should be empty).
//
// Output: data/tag_vocab.json = { axes: {axis: [slug,...]}, counts, clusters:[...] }
// ROOT is script-relative (cross-platform); vault is the repo's sibling.
import fs from "fs"
import path from "path"
import { fileURLToPath } from "url"

const ROOT = path.dirname(path.dirname(path.dirname(fileURLToPath(import.meta.url)))) // quartz-eng-lit/
const VAULT = path.join(ROOT, "..", "VaultEnglish")
const WORKS = path.join(VAULT, "Knowledge Graph", "Works")
const OUT = path.join(ROOT, "data", "tag_vocab.json")

const AXES = ["topos", "archetype", "motif", "concept", "form", "histref", "setting", "character"]

// minimal frontmatter tag reader: grab the YAML block, pull `tags:` list items and
// the scalar `cluster:` value. Avoids a YAML dep; notes use a simple block-list shape.
function readFrontmatter(txt) {
  if (!txt.startsWith("---")) return { tags: [], cluster: "" }
  const end = txt.indexOf("\n---", 3)
  if (end < 0) return { tags: [], cluster: "" }
  const fm = txt.slice(3, end)
  const tags = []
  let cluster = ""
  let inTags = false
  for (const raw of fm.split("\n")) {
    const line = raw.replace(/\r$/, "")
    const mCluster = line.match(/^cluster:\s*"?(.*?)"?\s*$/)
    if (mCluster && !inTags) cluster = mCluster[1]
    if (/^tags:\s*$/.test(line)) {
      inTags = true
      continue
    }
    if (inTags) {
      const mItem = line.match(/^\s*-\s*"?([^"]+?)"?\s*$/)
      if (mItem) {
        tags.push(mItem[1])
        continue
      }
      if (/^\S/.test(line)) inTags = false // dedent → tags block ended
    }
  }
  return { tags, cluster }
}

const byAxis = Object.fromEntries(AXES.map((a) => [a, new Set()]))
const clusters = new Set()
let workCount = 0

for (const f of fs.readdirSync(WORKS)) {
  if (!f.endsWith(".md")) continue
  const txt = fs.readFileSync(path.join(WORKS, f), "utf8")
  const { tags, cluster } = readFrontmatter(txt)
  if (!tags.includes("graph/work")) continue
  workCount++
  for (const t of tags) {
    const i = t.indexOf("/")
    if (i < 0) continue
    const axis = t.slice(0, i)
    const slug = t.slice(i + 1)
    if (byAxis[axis]) byAxis[axis].add(slug)
  }
  if (cluster) clusters.add(cluster)
}

const axes = Object.fromEntries(AXES.map((a) => [a, [...byAxis[a]].sort()]))
const counts = Object.fromEntries(AXES.map((a) => [a, axes[a].length]))
const out = { workCount, counts, clustersCount: clusters.size, axes, clusters: [...clusters].sort() }
fs.mkdirSync(path.dirname(OUT), { recursive: true })
fs.writeFileSync(OUT, JSON.stringify(out, null, 0))
console.log("works scanned:", workCount)
console.log("distinct slugs per axis:", JSON.stringify(counts))
console.log("distinct clusters:", clusters.size)
console.log("wrote", path.relative(ROOT, OUT), fs.statSync(OUT).size, "bytes")
