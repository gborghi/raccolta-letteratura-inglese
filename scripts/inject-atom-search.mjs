import fs from "fs"
import path from "path"
import zlib from "node:zlib"

// Merge per-atom search entries (frag -> {title, work, text}) into a
// contentIndex-shaped object (slug -> {title, content, tags, links, slug}).
// Pure function: mutates + returns `index` for convenience.
export function mergeAtoms(index, atoms) {
  for (const [frag, a] of Object.entries(atoms)) {
    const parent = a.work && a.work !== a.title ? a.work : ""
    const title = parent ? `${a.title || ""} — ${parent}` : a.title || ""
    index[frag] = { title, content: a.text || "", tags: [], links: [], slug: frag }
  }
  return index
}

function main() {
  const file = path.join("public", "static", "contentIndex.json")
  if (!fs.existsSync(file)) {
    console.error("inject-atom-search: contentIndex.json not found — skipping")
    process.exit(0)
  }
  const atomsFile = path.join("data", "atom_search.json.gz")
  if (!fs.existsSync(atomsFile)) {
    console.error("inject-atom-search: atom_search.json.gz not found — skipping")
    process.exit(0)
  }
  const raw = JSON.parse(fs.readFileSync(file, "utf8"))
  const wrapped = raw && raw.content && typeof raw.content === "object" && !raw.content.slug
  const index = wrapped ? raw.content : raw
  const atoms = JSON.parse(zlib.gunzipSync(fs.readFileSync(atomsFile)))
  const before = Object.keys(index).length
  mergeAtoms(index, atoms)
  fs.writeFileSync(file, JSON.stringify(raw))
  console.log(
    `inject-atom-search: ${before} -> ${Object.keys(index).length} entries (+${Object.keys(atoms).length} atoms)`,
  )
}

if (import.meta.url === `file://${process.argv[1]}`) main()
