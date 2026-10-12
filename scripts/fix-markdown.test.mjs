import { test } from "node:test"
import assert from "node:assert/strict"
import { fixMarkdown as f } from "./fix-markdown.mjs"

test("stray tilde fence is escaped", () => assert.equal(f("~~~ End of Text ~~~"), "\\~~~ End of Text ~~~"))
test("line-broken wikilink is joined", () =>
  assert.equal(f("l'intera [[motifs/great-house|grande\ncasa]], con"), "l'intera [[motifs/great-house|grande casa]], con"))
test("padded bold is tightened", () => assert.equal(f("**In ritardo con i tempi, **  "), "**In ritardo con i tempi,**   "))
test("odd ** count is left alone", () => assert.equal(f("**a **b** c"), "**a **b** c"))
test("nested link collapses", () => {
  assert.equal(f("Show me [[The [[motifs/bells|Bells]]|the Bells]] —"), "Show me [[motifs/bells|the Bells]] —")
  assert.equal(
    f("FOR [[South [[settings/africa|Africa]]|SOUTH [[settings/africa|AFRICA]]]]"),
    "FOR [[settings/africa|SOUTH AFRICA]]",
  )
})
test("unclosed link keeps its text", () => {
  assert.equal(f("- [Book 1: [[Poverty|POVERTY](/x#a)"), "- [Book 1: POVERTY](/x#a)")
  assert.equal(f('data-title="FROM [[Home|HOME (part 1)" data-k="a"'), 'data-title="FROM HOME (part 1)" data-k="a"')
})
test("valid links and quotes untouched", () => assert.equal(f('a [[x|"q" w]] [[c]]'), 'a [[x|"q" w]] [[c]]'))
test("mangled placeholder", () => assert.equal(f("dell’[[]L09|umorismo]] è"), "dell’umorismo è"))
test("frontmatter untouched + idempotent", () => {
  const s = "---\ntitle: \"** x **\"\n---\n**a, ** b\n"
  assert.equal(f(s), "---\ntitle: \"** x **\"\n---\n**a,**  b\n")
  assert.equal(f(f(s)), f(s))
})
test("stray [ before a link never ends up in the target", () => {
  assert.equal(
    f("says.  [[[characters/lord-darlington\\|LORD DARLINGTON]] crosses R.C.]  No"),
    "says.  &#91;[[characters/lord-darlington\\|LORD DARLINGTON]] crosses R.C.]  No",
  )
  assert.ok(!f("[[[[motifs/x|X]]").includes("[[["))
  assert.equal(f("a [[motifs/[time|Time]] b"), "a [[motifs/time|Time]] b")
  assert.equal(f("[[[forms/epigram|Epigram"), "Epigram")
  const s = "x [[[motifs/home|Home]] y"
  assert.equal(f(f(s)), f(s))
  assert.ok(!/\[\[[^\]|]*\[/.test(f("[[ [[[a|b]]")))
})
