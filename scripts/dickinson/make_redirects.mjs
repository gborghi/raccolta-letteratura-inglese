// Build the old->new redirect map for the retired per-poem/letter Dickinson URLs.
// After the cluster-SPA restructure the ~1730 single-atom reading pages and their
// ~1532 works/ metadata pages no longer exist; each maps to a fragment on the new
// cluster SPA. Emitted to quartz/static/ (served, survives preprocess content-wipe);
// consulted by the 404 client script. Keys are DECODED url paths (after the site base).
//   reading: testi/dickinson/atomized/<srcbase_lower>      (all 1730 atoms, incl orphans)
//   works:   works/<noteTitle_lower, spaces->->            (only atoms with a KG note)
// Value: testi/dickinson/atomized/<finalSlug>#<srcbase_lower>   (relative, base prepended by 404).
import fs from "fs"
import path from "path"
import { fileURLToPath } from "url"

const ROOT = path.dirname(path.dirname(path.dirname(fileURLToPath(import.meta.url))))
const MANIFEST = path.join(ROOT, "data", "dickinson_move_manifest.json")
const OUT = path.join(ROOT, "quartz", "static", "dickinson_redirects.json")

// Quartz URL slug (verified live): lowercase, each space -> "-", all other chars kept.
const qslug = (s) => s.toLowerCase().replaceAll(" ", "-")

const manifest = JSON.parse(fs.readFileSync(MANIFEST, "utf8"))
const map = {}
let reading = 0,
  works = 0
for (const m of manifest) {
  const idLower = m.srcBase.toLowerCase()
  const newUrl = `testi/dickinson/atomized/${m.finalSlug}#${idLower}`
  // 1. old reading page (every atom had one)
  map[`testi/dickinson/atomized/${idLower}`] = newUrl
  reading++
  // 2. old works metadata page (only atoms with a KG note had one)
  if (m.noteFile) {
    const title = m.noteFile.replace(/\.md$/, "")
    map[`works/${qslug(title)}`] = newUrl
    works++
  }
}

fs.writeFileSync(OUT, JSON.stringify(map))
console.log("redirect keys:", Object.keys(map).length, "(reading:", reading, "works:", works, ")")
console.log("bytes:", fs.statSync(OUT).size, "| WROTE", path.relative(ROOT, OUT))
