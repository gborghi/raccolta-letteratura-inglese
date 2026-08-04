// Write the deterministic wikilink-derived tags (data/leaf_wikilink_tags.json) into
// each leaf atom's frontmatter as a YAML `tags:` block list. Idempotent + resumable:
// an atom that already has a frontmatter `tags:` block is skipped. Preserves the
// original body verbatim (frontmatter is PREPENDED; preprocess.splitUnit strips it
// from the rendered body and parseFrontmatter reads the tags).
//
// Usage:
//   node scripts/tag/write_wikilink_tags.mjs --dry-run        # counts only
//   node scripts/tag/write_wikilink_tags.mjs --limit 1        # write first N (smoke test)
//   node scripts/tag/write_wikilink_tags.mjs                  # full run
//
// ROOT script-relative; vault is the repo's sibling.
import fs from "fs"
import path from "path"
import { fileURLToPath } from "url"

const ROOT = path.dirname(path.dirname(path.dirname(fileURLToPath(import.meta.url))))
const VAULT = path.join(ROOT, "..", "VaultEnglish")
const TAGS = path.join(ROOT, "data", "leaf_wikilink_tags.json")
const MANIFEST = path.join(ROOT, "data", "leaf_atoms.json")

const args = process.argv.slice(2)
const dryRun = args.includes("--dry-run")
const limIdx = args.indexOf("--limit")
const limit = limIdx >= 0 ? parseInt(args[limIdx + 1], 10) : Infinity

const tagsByFrag = JSON.parse(fs.readFileSync(TAGS, "utf8"))
const manRaw = JSON.parse(fs.readFileSync(MANIFEST, "utf8"))
const manifest = Array.isArray(manRaw) ? manRaw : Object.values(manRaw)
const srcByFrag = new Map(manifest.map((a) => [a.frag, a.source]))

// already has a frontmatter `tags:` (block list OR inline) → treat as tagged
function hasTagsFrontmatter(raw) {
  const m = raw.match(/^---\r?\n([\s\S]*?)\r?\n---/)
  if (!m) return false
  return /^tags:\s*(\r?\n\s+-\s+|\[)/m.test(m[1]) || /^\s+-\s+\S/m.test(m[1])
}

let written = 0,
  skipped = 0,
  missing = 0
const frags = Object.keys(tagsByFrag)
for (const frag of frags) {
  if (written >= limit) break
  const src = srcByFrag.get(frag)
  if (!src) {
    missing++
    continue
  }
  const p = path.join(VAULT, src)
  if (!fs.existsSync(p)) {
    missing++
    continue
  }
  const raw = fs.readFileSync(p, "utf8")
  if (hasTagsFrontmatter(raw)) {
    skipped++
    continue
  }
  const eol = raw.includes("\r\n") ? "\r\n" : "\n"
  const tags = tagsByFrag[frag]
  const fmBlock =
    `---${eol}tags:${eol}` + tags.map((t) => `  - ${t}`).join(eol) + `${eol}---${eol}${eol}`
  if (dryRun) {
    written++
    continue
  }
  fs.writeFileSync(p, fmBlock + raw)
  written++
}

console.log(
  `${dryRun ? "[dry-run] " : ""}written ${written} | skipped(already-tagged) ${skipped} | missing-src ${missing} | total-frags ${frags.length}`,
)
