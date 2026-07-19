// Create one collection work-note per final Dickinson cluster (34 total), mirroring
// `Sonnets (Shakespeare).md`: type:work, NO subwork, source = the cluster atom DIR
// (basename == workDir, which binds the note to the single SPA reading page), cluster
// = the final label, and aggregated tags (union of member-atom tags, top-N by frequency).
// ROOT script-relative. Idempotent (overwrites its own collection notes).
import fs from "fs"
import path from "path"
import { fileURLToPath } from "url"

const ROOT = path.dirname(path.dirname(path.dirname(fileURLToPath(import.meta.url))))
const VAULT = path.join(ROOT, "..", "VaultEnglish")
const WORKS = path.join(VAULT, "Knowledge Graph", "Works")
const ATOMIZED = path.join(VAULT, "Authors", "Dickinson", "Atomized")
const MAP = path.join(ROOT, "data", "dickinson_cluster_map.json")
const REL_BASE = "Authors/Dickinson/Atomized"
const TAG_CAP = 28

const map = JSON.parse(fs.readFileSync(MAP, "utf8"))

// Dickinson atom FILES carry no frontmatter; the per-poem tags live on the subwork
// NOTES (surfaced onto atoms at build time via preprocess sourceTagAxes). So aggregate
// the collection's tags from the member subwork notes, not the atom bodies.
function noteTags(noteFile) {
  const p = path.join(WORKS, noteFile)
  if (!fs.existsSync(p)) return []
  const raw = fs.readFileSync(p, "utf8")
  const m = raw.match(/^---\r?\n([\s\S]*?)\r?\n---/)
  if (!m) return []
  const tm = m[1].match(/tags:\s*((?:\r?\n\s+-\s+[^\r\n]+)+)/)
  if (!tm) return []
  return [...tm[1].matchAll(/-\s+([^\r\n]+)/g)].map((x) => x[1].trim())
}

let created = 0
for (const final of Object.values(map.finals)) {
  // frequency-count tags across all member subwork notes
  const freq = new Map()
  let dominantForm = null
  const formFreq = new Map()
  for (const atom of final.atoms) {
    if (!atom.noteFile) continue // orphan letter, no note/tags
    for (const t of noteTags(atom.noteFile)) {
      if (t.startsWith("author/") || t.startsWith("graph/")) continue
      freq.set(t, (freq.get(t) || 0) + 1)
      if (t.startsWith("form/")) formFreq.set(t, (formFreq.get(t) || 0) + 1)
    }
  }
  dominantForm = [...formFreq.entries()].sort((a, b) => b[1] - a[1])[0]?.[0]
  const ranked = [...freq.entries()].sort((a, b) => b[1] - a[1]).map((x) => x[0])
  const picked = []
  const seen = new Set()
  for (const t of ["graph/work", "author/Dickinson", dominantForm].filter(Boolean)) {
    if (!seen.has(t)) (seen.add(t), picked.push(t))
  }
  for (const t of ranked) {
    if (picked.length >= TAG_CAP) break
    if (!seen.has(t)) (seen.add(t), picked.push(t))
  }

  const title = final.label // full thematic cluster label
  const notePath = path.join(WORKS, `${title} (Dickinson).md`)
  const fmLines = [
    "---",
    `title: "${title}"`,
    `author: "Dickinson"`,
    "type: work",
    `cluster: "${final.label}"`,
    `source: "${REL_BASE}/${final.slug}"`,
    "tags:",
    ...picked.map((t) => `  - ${t}`),
    "---",
    "",
    `# ${title}`,
    "",
  ]
  fs.writeFileSync(notePath, fmLines.join("\n") + "\n")
  created++
}
console.log("collection notes created:", created)
