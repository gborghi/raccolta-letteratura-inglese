import { test } from "node:test"
import assert from "node:assert"
// NOTE: import from preprocess-classify.mjs, NOT preprocess.mjs — preprocess.mjs
// executes its main() at module top-level (wipes+regenerates content/). classifyUnit
// is extracted to this tiny pure module precisely so it can be unit-tested safely.
// @ts-ignore — plain .mjs, no declaration file (same pattern as componentResources.ts)
import { classifyUnit } from "./preprocess-classify.mjs"

test("Act_N classifies as scene", () => {
  const r = classifyUnit(["Plays", "Salome"], "Act_1")
  assert.equal(r.unitType, "scene")
  assert.equal(r.order, 101)
})

test("Prologue classifies as scene", () => {
  const r = classifyUnit(["Plays", "Vera"], "Prologue")
  assert.equal(r.unitType, "scene")
  assert.equal(r.order, 100)
})

test("bare work file stays unitType work (intro unchanged)", () => {
  const r = classifyUnit(["Plays", "Vera"], "Vera")
  assert.equal(r.unitType, "work")
  assert.equal(r.order, 0)
})

test("pre-existing: Chapter_01 still classifies as chapter", () => {
  const r = classifyUnit(["Prose", "SomeNovel"], "Chapter_01")
  assert.equal(r.unitType, "chapter")
  assert.equal(r.order, 1)
})

test("pre-existing: Scene_1 still classifies as scene with numeric order", () => {
  const r = classifyUnit(["Plays", "SomePlay"], "Scene_1")
  assert.equal(r.unitType, "scene")
  assert.equal(r.order, 1)
})
