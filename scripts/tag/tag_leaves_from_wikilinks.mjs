// Prepend the deterministic wikilink-derived tag block to leaf atoms that have no
// frontmatter at all.
//
// derive_wikilink_tags.mjs + write_wikilink_tags.mjs do the same derivation, but they work
// through data/leaf_atoms.json - the manifest of atoms preprocess already knows about. An
// atom that has just been created in the vault is in no manifest yet, so it cannot be
// tagged that way without rebuilding the whole manifest first. This script addresses the
// files directly instead, and is the tool to reach for after an atomizer runs.
//
// The rule is theirs, unchanged: collect [[target]] / [[target|alias]] from the body,
// slugify, look the slug up in data/axis_map.json, emit `axis/slug` for every axis it
// belongs to (a name can be dual-axis), sorted, deduplicated.
//
//   node scripts/tag/tag_leaves_from_wikilinks.mjs --author Eliot --sub Plays
//   node scripts/tag/tag_leaves_from_wikilinks.mjs --author Eliot --sub Plays --write
//   node scripts/tag/tag_leaves_from_wikilinks.mjs --check <vault-relative.md>   compare
//     what this script would derive against a file that is already tagged
//
// ROOT is script-relative; the vault is the repo's sibling.
import fs from "fs"
import path from "path"
import { fileURLToPath } from "url"
import { slugify } from "./build_axis_map.mjs"

const ROOT = path.dirname(path.dirname(path.dirname(fileURLToPath(import.meta.url))))
const VAULT = path.join(ROOT, "..", "VaultEnglish")
const AXIS_MAP = path.join(ROOT, "data", "axis_map.json")

const axisMap = JSON.parse(fs.readFileSync(AXIS_MAP, "utf8"))
const LINK_RE = /\[\[([^\]|]+)(?:\|[^\]]*)?\]\]/g

function tagsOf(body) {
  const out = new Set()
  let m
  LINK_RE.lastIndex = 0
  while ((m = LINK_RE.exec(body))) {
    const slug = slugify(m[1].trim())
    for (const axis of axisMap[slug] || []) out.add(`${axis}/${slug}`)
  }
  return [...out].sort()
}

// Sources written on the Windows box are CRLF, everything the macOS pipeline writes is LF,
// and both live side by side in the vault. Read normalised; write back with whatever the
// file already used, so a tag block never leaves a file with mixed endings.
function read(p) {
  const raw = fs.readFileSync(p, "utf8")
  return [raw.replace(/\r\n/g, "\n"), raw.includes("\r\n") ? "\r\n" : "\n"]
}

function hasFrontmatter(text) {
  return text.startsWith("---\n")
}

const args = process.argv.slice(2)
const val = (f) => {
  const i = args.indexOf(f)
  return i >= 0 ? args[i + 1] : null
}
const write = args.includes("--write")

const check = val("--check")
if (check) {
  const [text] = read(path.join(VAULT, check))
  const end = text.indexOf("\n---\n", 4)
  const existing = hasFrontmatter(text)
    ? text
        .slice(4, end)
        .split("\n")
        .filter((l) => l.trim().startsWith("- "))
        .map((l) => l.trim().slice(2))
    : []
  const derived = tagsOf(hasFrontmatter(text) ? text.slice(end + 5) : text)
  const miss = existing.filter((t) => !derived.includes(t))
  const extra = derived.filter((t) => !existing.includes(t))
  console.log(
    JSON.stringify({ file: check, esistenti: existing.length, derivati: derived.length, solo_esistenti: miss, solo_derivati: extra }, null, 1),
  )
  process.exit(0)
}

const author = val("--author")
const sub = val("--sub")
if (!author || !sub) {
  console.error("serve --author NOME --sub SOTTOALBERO (oppure --check <file>)")
  process.exit(2)
}

// A leaf here is the same structural notion leafcheck.py uses: a .md with no sibling
// directory of its own name, and not the <Work>/<Work>.md book file of a populated dir.
function isLeaf(p) {
  const stem = p.slice(0, -3)
  if (fs.existsSync(stem) && fs.statSync(stem).isDirectory()) return false
  const parent = path.dirname(p)
  if (path.basename(stem) === path.basename(parent)) {
    for (const e of fs.readdirSync(parent)) {
      if (path.join(parent, e) === p) continue
      if (e.endsWith(".md") && !e.endsWith(".it.md")) return false
      if (fs.statSync(path.join(parent, e)).isDirectory()) return false
    }
  }
  return true
}

const base = path.join(VAULT, "Authors", author, sub)
const files = []
;(function walk(d) {
  for (const e of fs.readdirSync(d).sort()) {
    const p = path.join(d, e)
    if (fs.statSync(p).isDirectory()) walk(p)
    else if (e.endsWith(".md") && !e.endsWith(".it.md") && isLeaf(p)) files.push(p)
  }
})(base)

let tagged = 0,
  already = 0,
  empty = 0
for (const p of files) {
  const [text, eol] = read(p)
  if (hasFrontmatter(text)) {
    already++
    continue
  }
  const tags = tagsOf(text)
  if (!tags.length) {
    empty++
    continue
  }
  const block = ["---", "tags:", ...tags.map((t) => `  - ${t}`), "---", ""].join(eol)
  if (write) fs.writeFileSync(p, (block + text).replace(/\n/g, eol === "\r\n" ? "\r\n" : "\n"))
  tagged++
  console.log(`${tags.length}\t${path.relative(VAULT, p)}`)
}
console.log(
  `\n${files.length} foglie: ${tagged} da taggare, ${already} gia' con frontmatter, ${empty} senza wikilink noti${write ? " -- SCRITTE" : " (dry run)"}`,
)
