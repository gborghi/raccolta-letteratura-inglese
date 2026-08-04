// Build the authoritative slug -> axis map from the concept-note DIRECTORIES.
// Each KG concept dir is one tag axis; a note's filename slug is the tag slug.
// This disambiguates wikilink targets (e.g. [[King]]) to their real axis far more
// reliably than "first axis in the work-tag vocab", because the note's own home
// directory declares its type. Reports slug collisions across axes (a slug living
// in >1 dir → ambiguous wikilink target; kept as a list, resolver picks per rules).
// Output: data/axis_map.json = { slug: [axis,...] }  (+ collisions report to stderr)
// ROOT is script-relative; vault is the repo's sibling.
import fs from "fs"
import path from "path"
import { fileURLToPath } from "url"

const ROOT = path.dirname(path.dirname(path.dirname(fileURLToPath(import.meta.url))))
const KG = path.join(ROOT, "..", "VaultEnglish", "Knowledge Graph")
const OUT = path.join(ROOT, "data", "axis_map.json")

// dir name -> axis prefix
const DIRS = {
  Concepts: "concept",
  Motifs: "motif",
  Forms: "form",
  Characters: "character",
  Archetypes: "archetype",
  Topoi: "topos",
  Settings: "setting",
  "Historical References": "histref",
}

export function slugify(s) {
  return s
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
}

const map = {} // slug -> Set(axis)
const perAxis = {}
for (const [dir, axis] of Object.entries(DIRS)) {
  const d = path.join(KG, dir)
  if (!fs.existsSync(d)) {
    console.error("axis_map: missing dir", dir)
    continue
  }
  let n = 0
  for (const f of fs.readdirSync(d)) {
    if (!f.endsWith(".md")) continue
    const slug = slugify(f.slice(0, -3))
    if (!slug) continue
    ;(map[slug] = map[slug] || new Set()).add(axis)
    n++
  }
  perAxis[axis] = n
}

const flat = {}
const collisions = []
for (const [slug, set] of Object.entries(map)) {
  flat[slug] = [...set]
  if (set.size > 1) collisions.push(`${slug}: ${[...set].join(",")}`)
}

fs.mkdirSync(path.dirname(OUT), { recursive: true })
fs.writeFileSync(OUT, JSON.stringify(flat, null, 0))
console.log("notes per axis:", JSON.stringify(perAxis))
console.log("distinct slugs:", Object.keys(flat).length)
console.log("collisions (slug in >1 axis):", collisions.length)
if (collisions.length) console.error("COLLISIONS:\n  " + collisions.slice(0, 40).join("\n  "))
console.log("wrote", path.relative(ROOT, OUT))
