// Chunk the link-less leaf atoms (data/leaf_linkless.json) into batches for Opus
// tagging. Each batch is bounded by a cumulative character budget (so long atoms
// make smaller batches) and a max atom count. Each atom's text is truncated to
// TRUNC chars (themes surface early; keeps prompts bounded). SKIPS atoms that
// already have a frontmatter `tags:` block (resumable — re-run after partial waves).
// Batches written to data/tag_batches/batch_NNN.json = [{frag, source, text}].
// ROOT script-relative; vault is the repo's sibling.
import fs from "fs"
import path from "path"
import { fileURLToPath } from "url"

const ROOT = path.dirname(path.dirname(path.dirname(fileURLToPath(import.meta.url))))
const VAULT = path.join(ROOT, "..", "VaultEnglish")
const LINKLESS = path.join(ROOT, "data", "leaf_linkless.json")
const OUTDIR = path.join(ROOT, "data", "tag_batches")

const CHAR_BUDGET = 180_000 // per batch (atom text)
const MAX_ATOMS = 35 // per batch
const TRUNC = 8_000 // per atom

function hasTags(raw) {
  const m = raw.match(/^---\r?\n([\s\S]*?)\r?\n---/)
  return m && /^tags:\s*(\r?\n\s+-\s+|\[)/m.test(m[1])
}

const linkless = JSON.parse(fs.readFileSync(LINKLESS, "utf8"))
fs.rmSync(OUTDIR, { recursive: true, force: true })
fs.mkdirSync(OUTDIR, { recursive: true })

const batches = []
let cur = [],
  curChars = 0,
  skipped = 0
function flush() {
  if (cur.length) {
    batches.push(cur)
    cur = []
    curChars = 0
  }
}
for (const a of linkless) {
  const p = path.join(VAULT, a.source)
  if (!fs.existsSync(p)) continue
  const raw = fs.readFileSync(p, "utf8")
  if (hasTags(raw)) {
    skipped++
    continue
  }
  // strip frontmatter (none expected) + take body text truncated
  const body = raw.replace(/^---\r?\n[\s\S]*?\r?\n---\r?\n?/, "")
  const text = body.slice(0, TRUNC)
  if (cur.length >= MAX_ATOMS || curChars + text.length > CHAR_BUDGET) flush()
  cur.push({ frag: a.frag, source: a.source, text })
  curChars += text.length
}
flush()

let n = 0
for (const b of batches) {
  const name = `batch_${String(n).padStart(3, "0")}.json`
  fs.writeFileSync(path.join(OUTDIR, name), JSON.stringify(b, null, 0))
  n++
}
console.log(
  `batches: ${batches.length} | atoms queued: ${batches.reduce((s, b) => s + b.length, 0)} | already-tagged skipped: ${skipped}`,
)
console.log(`wrote ${OUTDIR}`)
