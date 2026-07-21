import test from "node:test"
import assert from "node:assert/strict"
import { buildShards, contentFor, chunkBySize } from "./build-search-shards.mjs"

const master = {
  "works/w1": {
    title: "W1",
    slug: "works/w1",
    tags: ["x"],
    links: ["works/w2"],
    snippet: "s".repeat(700),
    terms: Array.from({ length: 500 }, (_, i) => [`term${i}`, 500 - i]),
  },
  "testi/w1#a2": {
    title: "A2 — W1",
    slug: "testi/w1#a2",
    tags: [],
    links: ["works/w1"],
    snippet: "atomtext ".repeat(100).trim(),
    terms: Array.from({ length: 500 }, (_, i) => [`av${i}`, 1]),
  },
}

test("contentFor slices snippet + top-n terms", () => {
  const c = contentFor(master["works/w1"], 30, 160)
  assert.equal(c.slice(0, 160), "s".repeat(160))
  assert.ok(c.includes("term0"))
  assert.ok(c.includes("term29"))
  assert.ok(!/\bterm30\b/.test(c))
})

test("t0 = works/concepts only, top30/160; excludes '#' atoms", () => {
  const { t0 } = buildShards(master)
  const slugs = t0.entries.map((e) => e.s)
  assert.ok(slugs.includes("works/w1"))
  assert.ok(!slugs.some((s) => s.includes("#")))
  const e = t0.entries.find((e) => e.s === "works/w1")
  assert.deepEqual(Object.keys(e).sort(), ["c", "g", "l", "s", "t"])
  assert.ok(e.c.includes("term29") && !/\bterm30\b/.test(e.c))
})

test("t1 delta = works, {s,c} only, top150/400 (superset of t0)", () => {
  const { t1 } = buildShards(master)
  const e = t1.entries.find((e) => e.s === "works/w1")
  assert.deepEqual(Object.keys(e).sort(), ["c", "s"])
  assert.ok(e.c.includes("term149") && !/\bterm150\b/.test(e.c))
  assert.equal(e.c.slice(0, 400), "s".repeat(400))
})

test("t2 = atom entries only, full shape, top80", () => {
  const { t2 } = buildShards(master)
  assert.equal(t2.entries.length, 1)
  const e = t2.entries[0]
  assert.equal(e.s, "testi/w1#a2")
  assert.deepEqual(e.l, ["works/w1"])
  assert.ok(e.c.includes("av79") && !/\bav80\b/.test(e.c))
})

test("t3 delta = WORKS ONLY, {s,c}, top500/700 (atoms not re-shipped)", () => {
  const { t3 } = buildShards(master)
  const w = t3.entries.find((e) => e.s === "works/w1")
  assert.ok(w.c.includes("term499"))
  assert.equal(w.c.slice(0, 700), "s".repeat(700))
  assert.ok(!t3.entries.some((e) => e.s.includes("#"))) // atoms excluded
})

test("chunkBySize splits into size-bounded contiguous buckets covering all entries", () => {
  const entries = Array.from({ length: 20 }, (_, i) => ({ s: `a${i}`, c: "x".repeat(100) }))
  const buckets = chunkBySize(entries, 400) // each entry ~ >100 bytes → a few per bucket
  assert.ok(buckets.length > 1)
  for (const b of buckets) assert.ok(Buffer.byteLength(JSON.stringify(b)) <= 400 || b.length === 1)
  assert.deepEqual(
    buckets.flat().map((e) => e.s),
    entries.map((e) => e.s), // order + completeness preserved
  )
})
