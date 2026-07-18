import { test } from "node:test"
import assert from "node:assert"
import { buildFullIndex, projectToTarget } from "./compress-search-index.mjs"

test("buildFullIndex ranks terms by tf-idf, caps per doc", () => {
  const raw = {}
  for (let i = 0; i < 40; i++)
    raw["p" + i] = {
      title: "t" + i,
      slug: "p" + i,
      content: Array.from({ length: 60 }, (_, j) => "w" + ((i * 3 + j) % 200)).join(" "),
    }
  const full = buildFullIndex(raw)
  assert.equal(Object.keys(full).length, 40)
  const d = full["p0"]
  assert.ok(Array.isArray(d.terms) && d.terms.length > 0)
  for (let k = 1; k < d.terms.length; k++) assert.ok(d.terms[k - 1][1] >= d.terms[k][1]) // sorted desc
})

test("projectToTarget lands under target and near it", () => {
  const raw = {}
  for (let i = 0; i < 500; i++)
    raw["p" + i] = {
      title: "t" + i,
      slug: "p" + i,
      content: Array.from({ length: 300 }, (_, j) => "word" + ((i * 7 + j) % 900)).join(" "),
    }
  const full = buildFullIndex(raw)
  const target = 200_000
  const out = projectToTarget(full, target)
  const size = Buffer.byteLength(JSON.stringify(out))
  assert.ok(size <= target, `size ${size} <= ${target}`)
  assert.ok(size >= target * 0.9, `size ${size} >= ${target * 0.9}`)
})
