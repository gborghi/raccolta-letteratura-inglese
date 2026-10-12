import { test } from "node:test"
import assert from "node:assert/strict"
import { MOJIBAKE, GREEK_MOJIBAKE } from "./check-mojibake.mjs"

const hits = (re, s) => (s.match(new RegExp(re.source, "g")) || []).length

test("Kubla Khan legacy Greek is caught", () => {
  assert.ok(hits(GREEK_MOJIBAKE, "given to him. £±¼µÁ¿½ ±´¹¿½ ±ÃÉ") >= 2)
  assert.ok(hits(MOJIBAKE, "which he calls º±¸±ÁÃ¹Â is") >= 1)
})
test("UTF-8 Greek read as cp1252 is caught", () => {
  const garbled = Buffer.from("Σαμερον", "utf8").toString("latin1")
  assert.ok(hits(GREEK_MOJIBAKE, garbled) >= 1)
})
test("Latin patterns still caught", () => {
  assert.equal(hits(MOJIBAKE, "mÃªlÃ©e soupÃ§on â€” emigr\uFFFD"), 5)
})
test("clean text is not flagged", () => {
  for (const s of ["Σαμερον αδιον ασω", "café mêlée Napoléon £5 ½ mile", "sa la strada.  ······  Quando", "Ἀνάγκη", "ÎLE-DE-FRANCE"])
    assert.equal(hits(MOJIBAKE, s), 0, s)
})
