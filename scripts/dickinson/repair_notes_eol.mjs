// One-shot repair: the first rewrite_notes.mjs inserted `subwork: true` with a
// `\s*`-anchored regex that swallowed the CR, producing `type: work\r\r\nsubwork`.
// The stray CR made parseFrontmatter read type as "work\r", failing the
// `data.type === "work"` gate and dropping all 1532 notes from the works index.
// Fix: normalize EOLs (strip trailing CRs per line, rejoin CRLF). Idempotent.
import fs from "fs"
import path from "path"
import { fileURLToPath } from "url"

const ROOT = path.dirname(path.dirname(path.dirname(fileURLToPath(import.meta.url))))
const VAULT = path.join(ROOT, "..", "VaultEnglish")
const WORKS = path.join(VAULT, "Knowledge Graph", "Works")
const MANIFEST = path.join(ROOT, "data", "dickinson_move_manifest.json")

const manifest = JSON.parse(fs.readFileSync(MANIFEST, "utf8"))
const noteFiles = [...new Set(manifest.map((m) => m.noteFile).filter(Boolean))]
let fixed = 0,
  clean = 0
for (const nf of noteFiles) {
  const p = path.join(WORKS, nf)
  const raw = fs.readFileSync(p, "utf8")
  const norm = raw.split(/\r?\n/).map((l) => l.replace(/\r+$/, "")).join("\r\n")
  if (norm !== raw) {
    fs.writeFileSync(p, norm)
    fixed++
  } else clean++
}
console.log("notes normalized:", fixed, "| already clean:", clean, "| total:", noteFiles.length)
