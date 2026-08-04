// Promote recurring tag_candidates (concept axis) to real concept nodes:
//  (1) create minimal Concept notes in the vault KG,
//  (2) add the concept/<slug> tag to each atom that suggested it (from candidates),
//  (3) extend data/tag_vocab.json so validation recognizes the new slugs.
// Character candidates + one-off niche concepts are NOT promoted (left as candidates).
// Idempotent: skips existing notes and atoms already carrying the tag.
// ROOT script-relative; vault is the repo's sibling.
import fs from "fs"
import path from "path"
import { fileURLToPath } from "url"

const ROOT = path.dirname(path.dirname(path.dirname(fileURLToPath(import.meta.url))))
const VAULT = path.join(ROOT, "..", "VaultEnglish")
const CONCEPTS = path.join(VAULT, "Knowledge Graph", "Concepts")
const CAND = path.join(ROOT, "data", "tag_candidates.jsonl")
const MANIFEST = path.join(ROOT, "data", "leaf_atoms.json")
const VOCAB = path.join(ROOT, "data", "tag_vocab.json")

// variant slug -> canonical slug (unify press/surveillance variants); value present = promote
const CANON = {
  usury: "usury",
  bureaucracy: "bureaucracy",
  anticlericalism: "anticlericalism",
  journalism: "journalism",
  journalism_and_the_press: "journalism",
  the_press_and_journalism: "journalism",
  plutocracy: "plutocracy",
  propaganda: "propaganda",
  forgery: "forgery",
  blackmail: "blackmail",
  financial_speculation: "financial_speculation",
  surveillance: "surveillance",
  espionage_surveillance: "surveillance",
  monopoly: "monopoly",
  sale_of_honours: "sale_of_honours",
}
const TITLE = {
  usury: "Usury",
  bureaucracy: "Bureaucracy",
  anticlericalism: "Anticlericalism",
  journalism: "Journalism",
  plutocracy: "Plutocracy",
  propaganda: "Propaganda",
  forgery: "Forgery",
  blackmail: "Blackmail",
  financial_speculation: "Financial Speculation",
  surveillance: "Surveillance",
  monopoly: "Monopoly",
  sale_of_honours: "Sale of Honours",
}

const man = JSON.parse(fs.readFileSync(MANIFEST, "utf8"))
const srcByFrag = new Map((Array.isArray(man) ? man : Object.values(man)).map((a) => [a.frag, a.source]))

// collect canonical -> Set(frag)
const atomsByConcept = {}
for (const line of fs.readFileSync(CAND, "utf8").trim().split(/\r?\n/)) {
  let o
  try {
    o = JSON.parse(line)
  } catch {
    continue
  }
  if (o.axis !== "concept") continue
  const canon = CANON[o.slug]
  if (!canon) continue
  ;(atomsByConcept[canon] = atomsByConcept[canon] || new Set()).add(o.atom)
}

// (1) create concept notes
let notesCreated = 0
for (const canon of Object.keys(atomsByConcept)) {
  const p = path.join(CONCEPTS, `${TITLE[canon]}.md`)
  if (fs.existsSync(p)) continue
  fs.writeFileSync(p, `---\ntitle: "${TITLE[canon]}"\ntype: concept\ntags:\n  - graph/concept\n---\n\n# ${TITLE[canon]}\n`)
  notesCreated++
}

// (2) tag the suggesting atoms — insert `  - concept/<canon>` into their tags block
function addTag(atomPath, tag) {
  const raw = fs.readFileSync(atomPath, "utf8")
  const m = raw.match(/^(---\r?\n)([\s\S]*?)(\r?\n---\r?\n?)([\s\S]*)$/)
  if (!m) return false // no frontmatter — skip (shouldn't happen for tagged leaves)
  const [, open, body, close, rest] = m
  if (body.includes(`- ${tag}`)) return false // already present
  const eol = raw.includes("\r\n") ? "\r\n" : "\n"
  const newBody = body.replace(/(tags:\s*(?:\r?\n\s+-\s+[^\r\n]+)+)/, (blk) => blk + eol + `  - ${tag}`)
  if (newBody === body) return false // no tags block found
  fs.writeFileSync(atomPath, open + newBody + close + rest)
  return true
}
let atomsTagged = 0,
  atomsMissing = 0
for (const [canon, frags] of Object.entries(atomsByConcept)) {
  for (const frag of frags) {
    const src = srcByFrag.get(frag)
    if (!src) {
      atomsMissing++
      continue
    }
    const p = path.join(VAULT, src)
    if (!fs.existsSync(p)) {
      atomsMissing++
      continue
    }
    if (addTag(p, `concept/${canon}`)) atomsTagged++
  }
}

// (3) extend vocab
const vocab = JSON.parse(fs.readFileSync(VOCAB, "utf8"))
const set = new Set(vocab.axes.concept)
for (const canon of Object.keys(atomsByConcept)) set.add(canon)
vocab.axes.concept = [...set].sort()
vocab.counts.concept = vocab.axes.concept.length
fs.writeFileSync(VOCAB, JSON.stringify(vocab))

console.log("concepts promoted:", Object.keys(atomsByConcept).join(", "))
console.log("notes created:", notesCreated, "| atoms tagged:", atomsTagged, "| atoms missing-src:", atomsMissing)
console.log("vocab concept axis now:", vocab.counts.concept)
