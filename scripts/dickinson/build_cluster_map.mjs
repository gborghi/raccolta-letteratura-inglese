// Build the Dickinson cluster-merge map: 70 source clusters -> 34 final clusters.
// Groups every Dickinson work-note by its `cluster:` scalar, classifies poem vs
// letter by the `source:` path (_raw vs _letters_raw), then folds the <10-member
// tail clusters into a big (>=10) cluster using data/dickinson_tail_merge.json
// (produced by a one-shot Opus curation). Emits data/dickinson_cluster_map.json.
// ROOT script-relative; vault is the repo's sibling.
import fs from "fs"
import path from "path"
import { fileURLToPath } from "url"

const ROOT = path.dirname(path.dirname(path.dirname(fileURLToPath(import.meta.url))))
const VAULT = path.join(ROOT, "..", "VaultEnglish")
const WORKS = path.join(VAULT, "Knowledge Graph", "Works")
const ATOMIZED = path.join(VAULT, "Authors", "Dickinson", "Atomized")
const TAIL_MERGE = path.join(ROOT, "data", "dickinson_tail_merge.json")
const OUT = path.join(ROOT, "data", "dickinson_cluster_map.json")

function fm(raw) {
  const m = raw.match(/^---\r?\n([\s\S]*?)\r?\n---/)
  return m ? m[1] : ""
}
function field(block, key) {
  const m = block.match(new RegExp(`^${key}:\\s*"?(.+?)"?\\s*$`, "m"))
  return m ? m[1].trim() : ""
}
function slugify(label) {
  let s = label
    .toLowerCase()
    .replace(/[·’']/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
  if (s.length > 60) {
    s = s.slice(0, 60)
    const cut = s.lastIndexOf("-")
    if (cut > 30) s = s.slice(0, cut) // trim trailing partial word
  }
  return s.replace(/-+$/g, "")
}

// 1. group
const files = fs.readdirSync(WORKS).filter((f) => /\(Dickinson\)\.md$/.test(f))
const byCluster = new Map() // label -> {members:[{noteFile, srcBase, kind}], poem, letter}
for (const f of files) {
  const block = fm(fs.readFileSync(path.join(WORKS, f), "utf8"))
  const cluster = field(block, "cluster")
  const source = field(block, "source")
  if (!cluster || !source) {
    console.error("SKIP (no cluster/source):", f)
    continue
  }
  const kind = /_letters_raw/.test(source) ? "letter" : "poem"
  const srcBase = path.basename(source).replace(/\.md$/, "")
  if (!byCluster.has(cluster)) byCluster.set(cluster, { members: [], poem: 0, letter: 0 })
  const g = byCluster.get(cluster)
  g.members.push({ noteFile: f, srcBase, kind })
  g[kind]++
}

const big = [] // labels with total >=10
const tail = [] // labels with total <10
for (const [label, g] of byCluster) {
  ;(g.poem + g.letter >= 10 ? big : tail).push(label)
}
big.sort()
tail.sort()

// 2. resolve tail -> big via curation map (if present)
let tailMerge = {}
if (fs.existsSync(TAIL_MERGE)) tailMerge = JSON.parse(fs.readFileSync(TAIL_MERGE, "utf8"))
const unresolved = tail.filter((t) => !big.includes(tailMerge[t]))

// 3. resolve final + slug
const finalOf = (label) => (big.includes(label) ? label : tailMerge[label])
const slugByFinal = new Map(big.map((b) => [b, slugify(b)]))

// finals: label -> { slug, label, atoms:[{srcBase, kind, noteFile|null}] }
const finals = {}
for (const b of big) finals[b] = { slug: slugByFinal.get(b), label: b, atoms: [] }
for (const [label, g] of byCluster) {
  const finalLabel = finalOf(label)
  for (const m of g.members) finals[finalLabel].atoms.push({ ...m, noteFile: m.noteFile })
}

// 3b. fold in orphan atom dirs (letters atomized but never given a KG note).
// Assign each to the nearest classified LETTER's final cluster by |L-number|.
const lettersByNum = [] // {num, finalLabel}
for (const [label, g] of byCluster) {
  const finalLabel = finalOf(label)
  for (const m of g.members) {
    if (m.kind !== "letter") continue
    const mm = m.srcBase.match(/^L0*(\d+)/i)
    if (mm) lettersByNum.push({ num: +mm[1], finalLabel })
  }
}
lettersByNum.sort((a, b) => a.num - b.num)
const nearestLetterFinal = (num) => {
  let best = null,
    bestD = Infinity
  for (const l of lettersByNum) {
    const d = Math.abs(l.num - num)
    if (d < bestD) {
      bestD = d
      best = l.finalLabel
    }
  }
  return best
}
const noteSrcBases = new Set()
for (const g of byCluster.values()) for (const m of g.members) noteSrcBases.add(m.srcBase)
const atomDirs = fs.readdirSync(ATOMIZED).filter((d) => fs.statSync(path.join(ATOMIZED, d)).isDirectory())
let orphans = 0
for (const d of atomDirs) {
  if (noteSrcBases.has(d)) continue
  const mm = d.match(/^L0*(\d+)/i)
  const finalLabel = mm ? nearestLetterFinal(+mm[1]) : null
  if (!finalLabel) {
    console.error("ORPHAN with no L-number, unassigned:", d)
    continue
  }
  finals[finalLabel].atoms.push({ noteFile: null, srcBase: d, kind: "letter" })
  orphans++
}

const map = { finals, generatedAtoms: Object.values(finals).reduce((n, f) => n + f.atoms.length, 0), orphansFolded: orphans }

// slug uniqueness + length report
const slugs = [...slugByFinal.values()]
const dupSlugs = slugs.filter((s, i) => slugs.indexOf(s) !== i)
const longest = slugs.reduce((a, b) => (b.length > a.length ? b : a), "")

console.log("distinct source clusters:", byCluster.size)
console.log("big (>=10):", big.length, "| tail (<10):", tail.length)
console.log("unresolved tail (need merge entry):", unresolved.length)
if (unresolved.length) {
  console.log("\n=== BIG CLUSTERS (34 targets) ===")
  big.forEach((b) => console.log("  " + b))
  console.log("\n=== TAIL CLUSTERS NEEDING MERGE ===")
  unresolved.forEach((t) => {
    const g = byCluster.get(t)
    console.log(`  (${g.poem + g.letter}) ${t}`)
  })
  console.log("\nWrite data/dickinson_tail_merge.json = {tailLabel: bigLabel} then rerun.")
} else {
  const minAtoms = Math.min(...Object.values(finals).map((f) => f.atoms.length))
  console.log("dup slugs:", dupSlugs.length, "| longest slug:", longest.length, longest)
  console.log("finals:", Object.keys(finals).length, "| total atoms:", map.generatedAtoms, "| orphans folded:", orphans)
  console.log("smallest final (atoms):", minAtoms, "(must be >=10)")
  fs.writeFileSync(OUT, JSON.stringify(map, null, 2))
  console.log("WROTE", path.relative(ROOT, OUT))
}
