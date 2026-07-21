// Build the 4 tiered search shards from the TF-IDF master (data/search-full-index.json).
// Each tier's `content` is a SUPERSET of the previous (snippet+terms grow monotonically),
// so the client deepens by REPLACING doc content by slug — no term-union bookkeeping.
// Emits public/static/search-t{0,1,2,3}.json. Run AFTER compress-search-index.mjs
// (which builds the master, including injected `#`-keyed atom entries).
//
// Shard file shape: {"tier":N,"entries":[{s,t,g,l,c},…]}. Delta shards (t1,t3) carry
// only {s,c} (content replacement for existing slugs); t2 carries full new atom entries.
// Compact keys: s=slug t=title g=tags l=links c=content.
import fs from "fs"
import path from "path"
import { pathToFileURL } from "node:url"

const masterPath = path.join("data", "search-full-index.json")
const outDir = path.join("public", "static")
// Per-shard raw-byte budgets (Cloudflare per-file cap is 25 MiB; stay well under).
const BUDGET = { 0: 3_500_000, 1: 4_500_000, 2: 12_000_000, 3: 6_000_000 }

const isAtom = (slug) => slug.includes("#")

// contentFor(doc, n, S): readable S-char snippet + top-n ranked terms.
export function contentFor(doc, n, S) {
  const snip = (doc.snippet || "").slice(0, S)
  const terms = (Array.isArray(doc.terms) ? doc.terms : [])
    .slice(0, n)
    .map(([w]) => w)
    .join(" ")
  return snip ? `${snip} ${terms}` : terms
}

// buildShards(master) -> { t0, t1, t2, t3 }; each { tier, entries }.
export function buildShards(master) {
  const works = []
  const atoms = []
  for (const [slug, d] of Object.entries(master)) (isAtom(slug) ? atoms : works).push([slug, d])

  const t0 = works.map(([s, d]) => ({
    s,
    t: d.title || "",
    g: d.tags || [],
    l: d.links || [],
    c: contentFor(d, 30, 160),
  }))
  const t1 = works.map(([s, d]) => ({ s, c: contentFor(d, 150, 400) }))
  const t2 = atoms.map(([s, d]) => ({
    s,
    t: d.title || "",
    g: d.tags || [],
    l: d.links || [],
    c: contentFor(d, 80, 400),
  }))
  const t3 = [
    ...works.map(([s, d]) => ({ s, c: contentFor(d, 500, 700) })),
    ...atoms.map(([s, d]) => ({ s, c: contentFor(d, 500, 700) })),
  ]
  return {
    t0: { tier: 0, entries: t0 },
    t1: { tier: 1, entries: t1 },
    t2: { tier: 2, entries: t2 },
    t3: { tier: 3, entries: t3 },
  }
}

function main() {
  if (!fs.existsSync(masterPath)) {
    console.error(
      `build-search-shards: ${masterPath} not found — compress-search-index.mjs must run first (fatal)`,
    )
    process.exit(1)
  }
  const master = JSON.parse(fs.readFileSync(masterPath, "utf8"))
  const shards = buildShards(master)
  fs.mkdirSync(outDir, { recursive: true })
  for (const key of ["t0", "t1", "t2", "t3"]) {
    const shard = shards[key]
    const json = JSON.stringify(shard)
    const bytes = Buffer.byteLength(json)
    if (bytes > BUDGET[shard.tier]) {
      console.error(
        `build-search-shards: ${key} = ${(bytes / 1e6).toFixed(1)}MB exceeds budget ` +
          `${(BUDGET[shard.tier] / 1e6).toFixed(1)}MB (fatal — see t2-split note in the plan)`,
      )
      process.exit(1)
    }
    fs.writeFileSync(path.join(outDir, `search-${key}.json`), json)
    console.log(
      `build-search-shards: search-${key}.json = ${(bytes / 1e6).toFixed(2)}MB (${shard.entries.length} entries)`,
    )
  }
}

// cross-platform main-guard: `file://${argv[1]}` breaks on Windows (backslashes,
// drive-letter slash) — pathToFileURL normalizes both to the same file: URL.
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) main()
