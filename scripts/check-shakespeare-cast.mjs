// One "PERSONS OF THE PLAY" per play (per language half of a bilingual page).
// A second one means the next play's title/introduction/cast bled into this play's end
// (the _raw 0NN_ splitter overshooting into play NN+1, then the atomizer putting it in the
// last scene). Scans content/testi/shakespeare; exits 1 on any offender.
import fs from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"

const PERSONS = /^[ \t#*|]*(?:THE[ \t]+)?PERSONS[ \t]+OF[ \t]+THE[ \t]+PLAY\b/gim
const SPLIT = /<span class="qlang-split"[^>]*><\/span>/

export function castCounts(text) {
  const body = text.replace(/^---\r?\n[\s\S]*?\r?\n---\r?\n/, "")
  return body.split(SPLIT).map((half) => (half.match(PERSONS) || []).length)
}

export function scan(dir) {
  const bad = []
  const walk = (d) => {
    for (const e of fs.readdirSync(d, { withFileTypes: true })) {
      const p = path.join(d, e.name)
      if (e.isDirectory()) walk(p)
      else if (e.name.endsWith(".md")) {
        const c = castCounts(fs.readFileSync(p, "utf8"))
        if (c.some((n) => n > 1)) bad.push({ file: p, counts: c })
      }
    }
  }
  if (fs.existsSync(dir)) walk(dir)
  return bad
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const dir = process.argv[2] || "content/testi/shakespeare"
  const bad = scan(dir)
  const gha = !!process.env.GITHUB_ACTIONS
  for (const b of bad)
    console.log(`${gha ? `::error file=${b.file}::` : `${b.file}: `}${b.counts.join("+")} × PERSONS OF THE PLAY (max 1 per play)`)
  console.log(`shakespeare cast check: ${bad.length} offending pages`)
  if (bad.length) process.exit(1)
}
