// Promote ALL residual tag_candidates (every axis) to real KG nodes + tag their atoms.
// Generalizes create_concepts.mjs across all 8 axes. Idempotent (skips existing notes
// + atoms already carrying the tag). Canonicalizes a few known variant slugs.
// ROOT script-relative; vault is the repo's sibling.
import fs from "fs"
import path from "path"
import { fileURLToPath } from "url"

const ROOT = path.dirname(path.dirname(path.dirname(fileURLToPath(import.meta.url))))
const VAULT = path.join(ROOT, "..", "VaultEnglish")
const KG = path.join(VAULT, "Knowledge Graph")
const CAND = path.join(ROOT, "data", "tag_candidates.jsonl")
const MANIFEST = path.join(ROOT, "data", "leaf_atoms.json")
const VOCAB = path.join(ROOT, "data", "tag_vocab.json")

// axis -> { dir, type }
const AXIS = {
  concept: { dir: "Concepts", type: "concept" },
  character: { dir: "Characters", type: "character" },
  motif: { dir: "Motifs", type: "motif" },
  form: { dir: "Forms", type: "form" },
  topos: { dir: "Topoi", type: "topos" },
  histref: { dir: "Historical References", type: "histref" },
  setting: { dir: "Settings", type: "setting" },
  archetype: { dir: "Archetypes", type: "archetype" },
}
// unify obvious variant slugs
const CANON = {
  journalism_and_the_press: "journalism",
  the_press_and_journalism: "journalism",
  espionage_surveillance: "surveillance",
}
function titleOf(slug) {
  return slug
    .split("_")
    .map((w) => (w ? w[0].toUpperCase() + w.slice(1) : w))
    .join(" ")
}

const man = JSON.parse(fs.readFileSync(MANIFEST, "utf8"))
const srcByFrag = new Map((Array.isArray(man) ? man : Object.values(man)).map((a) => [a.frag, a.source]))

// group (axis -> canonicalSlug -> Set(frag))
const byAxis = {}
for (const line of fs.readFileSync(CAND, "utf8").trim().split(/\r?\n/)) {
  let o
  try {
    o = JSON.parse(line)
  } catch {
    continue
  }
  if (!AXIS[o.axis] || !o.slug) continue
  const slug = CANON[o.slug] || o.slug
  byAxis[o.axis] = byAxis[o.axis] || {}
  ;(byAxis[o.axis][slug] = byAxis[o.axis][slug] || new Set()).add(o.atom)
}

function addTag(atomPath, tag) {
  const raw = fs.readFileSync(atomPath, "utf8")
  const m = raw.match(/^(---\r?\n)([\s\S]*?)(\r?\n---\r?\n?)([\s\S]*)$/)
  if (!m) return false
  const [, open, body, close, rest] = m
  if (body.includes(`- ${tag}`)) return false
  const eol = raw.includes("\r\n") ? "\r\n" : "\n"
  const newBody = body.replace(/(tags:\s*(?:\r?\n\s+-\s+[^\r\n]+)+)/, (blk) => blk + eol + `  - ${tag}`)
  if (newBody === body) return false
  fs.writeFileSync(atomPath, open + newBody + close + rest)
  return true
}

const vocab = JSON.parse(fs.readFileSync(VOCAB, "utf8"))
let notes = 0,
  tagged = 0,
  missing = 0
const perAxis = {}
for (const [axis, slugs] of Object.entries(byAxis)) {
  const { dir, type } = AXIS[axis]
  const set = new Set(vocab.axes[axis] || [])
  perAxis[axis] = 0
  for (const [slug, frags] of Object.entries(slugs)) {
    const title = titleOf(slug)
    const notePath = path.join(KG, dir, `${title}.md`)
    if (!fs.existsSync(notePath)) {
      fs.writeFileSync(notePath, `---\ntitle: "${title}"\ntype: ${type}\ntags:\n  - graph/${type}\n---\n\n# ${title}\n`)
      notes++
      perAxis[axis]++
    }
    set.add(slug)
    for (const frag of frags) {
      const src = srcByFrag.get(frag)
      if (!src) {
        missing++
        continue
      }
      const p = path.join(VAULT, src)
      if (!fs.existsSync(p)) {
        missing++
        continue
      }
      if (addTag(p, `${axis}/${slug}`)) tagged++
    }
  }
  vocab.axes[axis] = [...set].sort()
  vocab.counts[axis] = vocab.axes[axis].length
}
fs.writeFileSync(VOCAB, JSON.stringify(vocab))
console.log("new notes:", notes, "| per axis:", JSON.stringify(perAxis))
console.log("atoms tagged:", tagged, "| missing-src:", missing)
console.log("vocab counts:", JSON.stringify(vocab.counts))
