// Physically move every Dickinson atom (.md + optional .it.md sibling) out of its
// per-poem dir into the flat per-cluster dir Authors/Dickinson/Atomized/<slug>/,
// mirroring the Shakespeare-Sonnets physical-workDir SPA model. Emits the move
// manifest that drives note-rewrite, collection-notes, and redirect emit.
// Idempotent-ish: skips an atom already at its destination. ROOT script-relative.
import fs from "fs"
import path from "path"
import { fileURLToPath } from "url"

const ROOT = path.dirname(path.dirname(path.dirname(fileURLToPath(import.meta.url))))
const VAULT = path.join(ROOT, "..", "VaultEnglish")
const ATOMIZED = path.join(VAULT, "Authors", "Dickinson", "Atomized")
const MAP = path.join(ROOT, "data", "dickinson_cluster_map.json")
const MANIFEST = path.join(ROOT, "data", "dickinson_move_manifest.json")
const REL_BASE = "Authors/Dickinson/Atomized"

// Windows MAX_PATH guard: prefix \\?\ on long absolute paths.
const win = process.platform === "win32"
const L = (p) => (win && path.isAbsolute(p) && p.length > 240 ? "\\\\?\\" + path.resolve(p) : p)

const map = JSON.parse(fs.readFileSync(MAP, "utf8"))
const manifest = []
let moved = 0,
  skipped = 0,
  itMoved = 0,
  err = 0

for (const final of Object.values(map.finals)) {
  const destDir = path.join(ATOMIZED, final.slug)
  if (!fs.existsSync(L(destDir))) fs.mkdirSync(L(destDir), { recursive: true })
  for (const atom of final.atoms) {
    const srcDir = path.join(ATOMIZED, atom.srcBase)
    const destMd = path.join(destDir, atom.srcBase + ".md")
    const newRel = `${REL_BASE}/${final.slug}/${atom.srcBase}.md`
    // already moved?
    if (fs.existsSync(L(destMd)) && !fs.existsSync(L(srcDir))) {
      manifest.push(mk(atom, final, newRel))
      skipped++
      continue
    }
    if (!fs.existsSync(L(srcDir))) {
      console.error("MISSING src dir:", atom.srcBase)
      err++
      continue
    }
    // find the .md and optional .it.md inside srcDir
    const inside = fs.readdirSync(L(srcDir))
    const mdName = inside.find((f) => f.endsWith(".md") && !f.endsWith(".it.md"))
    const itName = inside.find((f) => f.endsWith(".it.md"))
    if (!mdName) {
      console.error("no .md inside:", atom.srcBase)
      err++
      continue
    }
    fs.renameSync(L(path.join(srcDir, mdName)), L(path.join(destDir, atom.srcBase + ".md")))
    moved++
    if (itName) {
      fs.renameSync(L(path.join(srcDir, itName)), L(path.join(destDir, atom.srcBase + ".it.md")))
      itMoved++
    }
    // remove now-empty src dir
    const leftover = fs.readdirSync(L(srcDir))
    if (leftover.length === 0) fs.rmdirSync(L(srcDir))
    else console.error("src dir not empty after move:", atom.srcBase, leftover)
    manifest.push(mk(atom, final, newRel, itName ? true : false))
  }
}

function mk(atom, final, newRel, hasIt) {
  return {
    srcBase: atom.srcBase,
    atomId: atom.srcBase, // fragment id = flat stem
    kind: atom.kind,
    noteFile: atom.noteFile || null,
    finalLabel: final.label,
    finalSlug: final.slug,
    newAtomRel: newRel,
    hasIt: hasIt === undefined ? fs.existsSync(L(path.join(ATOMIZED, final.slug, atom.srcBase + ".it.md"))) : hasIt,
  }
}

fs.writeFileSync(MANIFEST, JSON.stringify(manifest, null, 2))
console.log("moved:", moved, "| .it moved:", itMoved, "| skipped(already):", skipped, "| errors:", err)
console.log("manifest entries:", manifest.length)
console.log("WROTE", path.relative(ROOT, MANIFEST))
