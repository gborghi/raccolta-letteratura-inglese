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

test("Scene_8a sorts between Scene_8 and Scene_9", () => {
  const r = classifyUnit(["Plays", "Pericles"], "Scene_8a")
  assert.equal(r.unitType, "scene")
  assert.equal(r.order, 8.01)
  assert.ok(classifyUnit(["Plays", "Pericles"], "Scene_8").order < r.order)
  assert.ok(r.order < classifyUnit(["Plays", "Pericles"], "Scene_9").order)
})

test("Scene_4a and Scene_4b keep their letter order", () => {
  const a = classifyUnit(["Plays", "Sir_Thomas_More"], "Scene_4a")
  const b = classifyUnit(["Plays", "Sir_Thomas_More"], "Scene_4b")
  assert.ok(a.order < b.order)
  assert.ok(b.order < classifyUnit(["Plays", "Sir_Thomas_More"], "Scene_5").order)
})

test("a scene whose name merely continues in letters is not read as a half-scene", () => {
  // Scene_1_Prologue must not turn into order 1.16 via a stray 'p'
  const r = classifyUnit(["Plays", "SomePlay"], "Scene_1_Prologue")
  assert.equal(r.order, 1)
})
