// Re-key the 1,192 Dickinson entries in translations_pages.jsonl to the new
// per-cluster atom paths. The IT bodies are unchanged (atoms only moved on disk),
// so a key rewrite is equivalent to a full gkc_emit_vault re-run and skips the
// ~20k transient non-SPA pages that re-emit would produce.
//   old rel: testi/dickinson/atomized/<stem>/<stem>.md   (nested single-atom)
//   new rel: testi/dickinson/atomized/<clusterSlug>/<stem>.md   (SPA unitRel)
// Non-Dickinson entries pass through untouched. ROOT script-relative.
import fs from "fs"
import path from "path"
import { fileURLToPath } from "url"

const ROOT = path.dirname(path.dirname(path.dirname(fileURLToPath(import.meta.url))))
const STORE = path.join(ROOT, "data", "translations_pages.jsonl")
const MANIFEST = path.join(ROOT, "data", "dickinson_move_manifest.json")

// stem(lowercased) -> finalSlug
const manifest = JSON.parse(fs.readFileSync(MANIFEST, "utf8"))
const slugByStem = new Map(manifest.map((m) => [m.srcBase.toLowerCase(), m.finalSlug]))

const lines = fs.readFileSync(STORE, "utf8").split(/\r?\n/).filter((l) => l.trim())
let rekeyed = 0,
  passthru = 0,
  unmapped = 0
const out = []
for (const line of lines) {
  const o = JSON.parse(line)
  const rel = o.rel || ""
  const parts = rel.split("/")
  if (parts[1] !== "dickinson") {
    out.push(line)
    passthru++
    continue
  }
  // parts: testi / dickinson / atomized / <stem> / <stem>.md
  const stem = parts[3]
  const slug = slugByStem.get(stem)
  if (!slug) {
    console.error("UNMAPPED dickinson stem:", stem)
    out.push(line)
    unmapped++
    continue
  }
  o.rel = `testi/dickinson/atomized/${slug}/${stem}.md`
  out.push(JSON.stringify(o))
  rekeyed++
}

fs.writeFileSync(STORE, out.join("\n") + "\n")
console.log("dickinson rekeyed:", rekeyed, "| passthru(other authors):", passthru, "| unmapped:", unmapped)
