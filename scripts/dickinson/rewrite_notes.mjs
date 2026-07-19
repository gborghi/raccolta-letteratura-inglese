// Rewrite the 1,532 Dickinson poem/letter work-notes into page-less subwork nodes:
//   - subwork: true   (inserted right after `type: work`)
//   - source: <new atomized path>   (repointed from _raw/_letters_raw to the moved atom)
//   - cluster: <finalLabel>   (absorbs the 36 tail clusters into their 34 parents)
// Preserves all other frontmatter + tags + body. Idempotent. ROOT script-relative.
import fs from "fs"
import path from "path"
import { fileURLToPath } from "url"

const ROOT = path.dirname(path.dirname(path.dirname(fileURLToPath(import.meta.url))))
const VAULT = path.join(ROOT, "..", "VaultEnglish")
const WORKS = path.join(VAULT, "Knowledge Graph", "Works")
const MANIFEST = path.join(ROOT, "data", "dickinson_move_manifest.json")

const manifest = JSON.parse(fs.readFileSync(MANIFEST, "utf8"))
let rewritten = 0,
  already = 0,
  err = 0

for (const m of manifest) {
  if (!m.noteFile) continue // orphan atom, no note
  const p = path.join(WORKS, m.noteFile)
  if (!fs.existsSync(p)) {
    console.error("missing note:", m.noteFile)
    err++
    continue
  }
  const raw = fs.readFileSync(p, "utf8")
  const fmMatch = raw.match(/^(---\r?\n)([\s\S]*?)(\r?\n---\r?\n?)([\s\S]*)$/)
  if (!fmMatch) {
    console.error("no frontmatter:", m.noteFile)
    err++
    continue
  }
  let [, open, block, close, body] = fmMatch
  const eol = raw.includes("\r\n") ? "\r\n" : "\n"

  // 1. source: -> new atom path (quoted, matching existing style)
  block = block.replace(/^source:.*$/m, `source: "${m.newAtomRel}"`)
  // 2. cluster: -> finalLabel (quoted)
  block = block.replace(/^cluster:.*$/m, `cluster: "${m.finalLabel}"`)
  // 3. subwork: true after `type: work` (skip if already present). Operate on the
  // line array + rejoin with the detected eol: a regex with `\s*`/`$` on CRLF files
  // silently swallows the CR into `type`'s value ("work\r"), which then fails the
  // `data.type === "work"` gate downstream and drops the note entirely.
  const flines = block.split(/\r?\n/)
  const hasSub = flines.some((l) => /^subwork:\s*true\s*$/.test(l))
  if (hasSub) {
    already++
  } else {
    const si = flines.findIndex((l) => /^subwork:/.test(l))
    if (si >= 0) flines[si] = "subwork: true"
    else {
      const ti = flines.findIndex((l) => /^type:\s*work\s*$/.test(l))
      if (ti >= 0) flines.splice(ti + 1, 0, "subwork: true")
    }
    block = flines.join(eol)
  }

  fs.writeFileSync(p, open + block + close + body)
  rewritten++
}

console.log("notes rewritten:", rewritten, "| already-subwork:", already, "| errors:", err)
