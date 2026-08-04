// Independent validator: every tag written into a leaf atom's frontmatter MUST be
// an existing vocab slug (axis/slug present in data/tag_vocab.json). Catches any
// fabricated slug (the hard rule). Pass a batch file or --all to scan every
// link-less atom. Reports invalid (axis/slug) with the offending atom.
// Also flags malformed frontmatter (body corruption sentinel).
import fs from "fs"
import path from "path"
import { fileURLToPath } from "url"

const ROOT = path.dirname(path.dirname(path.dirname(fileURLToPath(import.meta.url))))
const VAULT = path.join(ROOT, "..", "VaultEnglish")
const VOCAB = path.join(ROOT, "data", "tag_vocab.json")

const V = JSON.parse(fs.readFileSync(VOCAB, "utf8"))
const allow = new Set()
for (const [ax, slugs] of Object.entries(V.axes)) for (const s of slugs) allow.add(`${ax}/${s}`)

const arg = process.argv[2]
let sources = []
if (arg === "--all") {
  const ll = JSON.parse(fs.readFileSync(path.join(ROOT, "data", "leaf_linkless.json"), "utf8"))
  sources = ll.map((a) => a.source)
} else {
  const batch = JSON.parse(fs.readFileSync(arg, "utf8"))
  sources = batch.map((a) => a.source)
}

let checked = 0,
  tagged = 0,
  bad = 0,
  malformed = 0,
  totalTags = 0
const invalids = []
for (const src of sources) {
  const p = path.join(VAULT, src)
  if (!fs.existsSync(p)) continue
  checked++
  const raw = fs.readFileSync(p, "utf8")
  const m = raw.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/)
  if (!m) continue // untagged (no frontmatter) — fine
  tagged++
  // body must still start with an H1 (corruption sentinel)
  if (!/^\s*#\s+/m.test(m[2].slice(0, 200))) malformed++
  const fmLines = m[1].split(/\r?\n/)
  for (const line of fmLines) {
    const t = line.match(/^\s+-\s+(.+?)\s*$/)
    if (!t) continue
    const tag = t[1].replace(/^["']|["']$/g, "")
    totalTags++
    if (!allow.has(tag)) {
      bad++
      invalids.push(`${src}: ${tag}`)
    }
  }
}
console.log(`checked ${checked} | tagged ${tagged} | total-tags ${totalTags} | INVALID ${bad} | malformed-body ${malformed}`)
if (bad) console.log("INVALID TAGS:\n  " + invalids.slice(0, 60).join("\n  "))
else console.log("all tags valid vocab ✓")
if (malformed) console.log("MALFORMED (body lost H1):", malformed)
