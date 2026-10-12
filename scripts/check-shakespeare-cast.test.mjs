import { test } from "node:test"
import assert from "node:assert/strict"
import { castCounts } from "./check-shakespeare-cast.mjs"

test("one cast per language half passes", () => {
  const s = "THE PERSONS OF THE PLAY\nx\n<span class=\"qlang-split\" data-lang=\"it\"></span>\nTHE PERSONS OF THE PLAY\n"
  assert.deepEqual(castCounts(s), [1, 1])
})
test("next play's cast bled into the end is caught", () => {
  const s = "THE PERSONS OF THE PLAY\n5.1 PUCK\n\nKING JOHN\n\nIntro\n\nTHE PERSONS OF THE PLAY\n"
  assert.deepEqual(castCounts(s), [2])
})
test("in a table cell / heading too", () => {
  assert.deepEqual(castCounts("## The Persons of the Play\n| PERSONS OF THE PLAY | |\n"), [2])
})
