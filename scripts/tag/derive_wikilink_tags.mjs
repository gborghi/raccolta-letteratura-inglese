// Deterministic per-leaf-atom tags from the wikilinks already present in each atom
// body (placed by graphify). For every untagged non-intro leaf atom in the manifest,
// extract [[target|alias]] link targets, slugify, look up data/axis_map.json → emit
// `axis/slug` tags (ALL axes for a dual-axis slug, e.g. Napoleon = character+histref).
// This is the FREE, accurate base; Opus later augments with implicit thematic tags.
// Output: data/leaf_wikilink_tags.json = { frag: ["axis/slug", ...] }  (only atoms with >=1 tag)
// Also prints coverage stats to guide how much Opus augmentation is needed.
// ROOT script-relative; vault is the repo's sibling.
import fs from "fs"
import path from "path"
import { fileURLToPath } from "url"
import { slugify } from "./build_axis_map.mjs"

const ROOT = path.dirname(path.dirname(path.dirname(fileURLToPath(import.meta.url))))
const VAULT = path.join(ROOT, "..", "VaultEnglish")
const MANIFEST = path.join(ROOT, "data", "leaf_atoms.json")
const AXIS_MAP = path.join(ROOT, "data", "axis_map.json")
const OUT = path.join(ROOT, "data", "leaf_wikilink_tags.json")

const SKIP_UNIT = new Set(["intro"]) // whole-work fallback atoms — not per-leaf targets

const axisMap = JSON.parse(fs.readFileSync(AXIS_MAP, "utf8")) // slug -> [axis,...]
const manRaw = JSON.parse(fs.readFileSync(MANIFEST, "utf8"))
const manifest = Array.isArray(manRaw) ? manRaw : Object.values(manRaw)

const LINK_RE = /\[\[([^\]|]+)(?:\|[^\]]*)?\]\]/g
function linkTargets(txt) {
  const out = new Set()
  let m
  while ((m = LINK_RE.exec(txt))) out.add(m[1].trim())
  return out
}

const result = {}
let targets = 0,
  withTags = 0,
  missingFile = 0
const perAxisCount = {}
const tagCountHist = [] // #tags per atom (for atoms with >=1)

for (const a of manifest) {
  if (a.hasTags) continue // already tagged (154 sonnets) — skip
  if (SKIP_UNIT.has(a.unitType)) continue
  targets++
  const p = path.join(VAULT, a.source)
  if (!fs.existsSync(p)) {
    missingFile++
    continue
  }
  const txt = fs.readFileSync(p, "utf8")
  const tags = new Set()
  for (const tgt of linkTargets(txt)) {
    const slug = slugify(tgt)
    const axes = axisMap[slug]
    if (!axes) continue
    for (const ax of axes) {
      tags.add(`${ax}/${slug}`)
      perAxisCount[ax] = (perAxisCount[ax] || 0) + 1
    }
  }
  if (tags.size) {
    result[a.frag] = [...tags].sort()
    withTags++
    tagCountHist.push(tags.size)
  }
}

fs.writeFileSync(OUT, JSON.stringify(result, null, 0))
tagCountHist.sort((x, y) => x - y)
const pct = (p) => tagCountHist[Math.floor(tagCountHist.length * p)] || 0
console.log("target leaf atoms (untagged, non-intro):", targets)
console.log("missing source files:", missingFile)
console.log("atoms with >=1 wikilink tag:", withTags, `(${((withTags / targets) * 100).toFixed(1)}%)`)
console.log("atoms with ZERO wikilink tags:", targets - missingFile - withTags, "(need Opus / no links)")
console.log("tags/atom (with >=1): median", pct(0.5), "| p90", pct(0.9), "| max", tagCountHist[tagCountHist.length - 1])
console.log("axis tag totals:", JSON.stringify(perAxisCount))
console.log("wrote", path.relative(ROOT, OUT), fs.statSync(OUT).size, "bytes")
