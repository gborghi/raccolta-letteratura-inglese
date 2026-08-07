import { test } from "node:test"
import assert from "node:assert"
// NOTE: import from preprocess-links.mjs, NOT preprocess.mjs — preprocess.mjs executes
// its main() at module top-level (wipes+regenerates content/). Same pattern as
// preprocess-classify.mjs.
// @ts-ignore — plain .mjs, no declaration file (same pattern as componentResources.ts)
import { buildLinkIndex, resolveWikilinks, stripDeadLinks, authorKey } from "./preprocess-links.mjs"

// preprocess.mjs's sluggify, verbatim (kept in sync by the tests below).
const sluggify = (s: string) =>
  s
    .split("/")
    .map((seg) =>
      seg
        .replace(/\s/g, "-")
        .replace(/&/g, "-and-")
        .replace(/%/g, "-percent")
        .replace(/\?/g, "")
        .replace(/#/g, "")
        .toLowerCase(),
    )
    .join("/")
    .replace(/\/$/, "")

const NOTES = [
  { slug: "concepts/nature", weight: 0, author: "" },
  { slug: "motifs/nature", weight: 337, author: "" },
  { slug: "concepts/history", weight: 0, author: "" },
  { slug: "forms/history", weight: 0, author: "" },
  { slug: "historical-references/milton", weight: 1, author: "" },
  { slug: "characters/milton", weight: 1, author: "" },
  { slug: "characters/hamlet", weight: 12, author: "" },
  { slug: "concepts/well", weight: 4, author: "" },
  { slug: "works/alone-(poe)", weight: 0, author: "Poe" },
  { slug: "works/song-(whitman)", weight: 0, author: "Whitman" },
  { slug: "works/house-(chesterton)", weight: 0, author: "Chesterton" },
  { slug: "works/the-sphinx-(poe)", weight: 0, author: "Poe" },
  { slug: "works/the-sphinx-(wilde)", weight: 0, author: "Wilde" },
  { slug: "works/sonnet-(coleridge)-(2)", weight: 0, author: "Coleridge" },
]
const { resolve, isSurfaceForm } = buildLinkIndex(NOTES, sluggify)
const rw = (md: string, ctx?: any) => resolveWikilinks(md, resolve, ctx)
// The final pass, with preprocess's own policy: `pages` is the set of emitted page
// slugs, "house" standing for Chesterton's essay. A surface form goes whether or not
// it lands (SPARE_LINKED_SURFACE_FORMS = false); anything else goes only when nothing
// answers to the name.
const pages = new Set(["house", "motifs/nature", "works/alone-(poe)"])
const lands = (t: string) => {
  const s = sluggify(String(t).trim())
  return pages.has(s) || (!s.includes("/") && [...pages].some((p) => p.split("/").pop() === s))
}
const keepLink = (spare: boolean) => (target: string, alias: string | null) =>
  isSurfaceForm(target, alias) ? spare && lands(target) : lands(target)
const sweep = (md: string) => stripDeadLinks(md, keepLink(false)).md
const sweepSparing = (md: string) => stripDeadLinks(md, keepLink(true)).md

test("a populated node beats an empty namesake", () => {
  assert.equal(resolve("Nature", null), "motifs/nature")
})

test("all-empty namesakes fall back to the folder order", () => {
  assert.equal(resolve("History", null), "concepts/history")
})

test("equally populated namesakes fall back to the folder order", () => {
  assert.equal(resolve("Milton", null), "historical-references/milton")
})

test("a target that is already a full slug resolves to itself", () => {
  assert.equal(resolve("characters/hamlet", null), "characters/hamlet")
  assert.equal(resolve("characters/nobody", null), null)
})

test("a bare work title resolves to its (Author)-suffixed slug", () => {
  assert.equal(resolve("Alone", null), "works/alone-(poe)")
})

test("a bare title shared by two authors picks the page's own author", () => {
  assert.equal(resolve("The Sphinx", { author: "Wilde" }), "works/the-sphinx-(wilde)")
  assert.equal(resolve("The Sphinx", { author: "Conan_Doyle" }), "works/the-sphinx-(poe)") // deterministic
})

test("a de-duplicated work title strips both suffixes", () => {
  assert.equal(resolve("Sonnet (Coleridge)", null), "works/sonnet-(coleridge)-(2)")
})

test("a surface form is never linked to the same-named work", () => {
  // "[[Alone|alone]]" is the word in the sentence, not Poe's poem; the vault tagger
  // linked it anyway. resolveWikilinks leaves it for the final pass to judge.
  assert.equal(rw("I [[Alone|alone]] fed him"), "I [[Alone|alone]] fed him")
  assert.equal(rw("the [[alone]] cat"), "the [[alone]] cat")
  assert.equal(rw("[[Alone|Solo]] qui"), "[[Alone|Solo]] qui")
})

test("the final pass unlinks a dead surface form, keeping the words", () => {
  assert.equal(sweep("I [[Alone|alone]] fed him"), "I alone fed him")
  assert.equal(sweep("the [[alone]] cat"), "the alone cat")
  assert.equal(sweep("[[Alone|Solo]] qui"), "Solo qui") // translated surface form
  assert.equal(sweep("| a | [[Song|canto]] |"), "| a | canto |") // inside a table cell
})

test("a surface form goes even where something answers to the name", () => {
  // "house" is also Chesterton's essay, so that link lands somewhere — it still does
  // not mean the essay, so it is unlinked with the rest.
  assert.equal(sweep("a [[house]] here"), "a house here")
  assert.equal(sweep("a [[House|house]] here"), "a house here")
})

test("sparing surface forms is a decision the policy can reverse", () => {
  // The module strips whatever `keep` rejects; which surface forms count as noise is
  // preprocess's call, and with SPARE_LINKED_SURFACE_FORMS the linked half survives.
  assert.equal(sweepSparing("a [[house]] here"), "a [[house]] here")
  assert.equal(sweepSparing("I [[Alone|alone]] fed him"), "I alone fed him") // nothing to land on
})

test("the final pass leaves a link that lands alone", () => {
  assert.equal(sweep("[[motifs/nature|nature]]"), "[[motifs/nature|nature]]")
  assert.equal(sweep("see [[works/alone-(poe)|Alone]]"), "see [[works/alone-(poe)|Alone]]")
  assert.equal(sweep("[[motifs/nature#Works|nature]]"), "[[motifs/nature#Works|nature]]")
})

test("the final pass unlinks a target no page answers to", () => {
  // "[[Cardenio]]" and "[[Pastoral]]" name works the vault never carried: however they
  // are written they 404, and the words read fine on their own.
  assert.equal(sweep("[[Nowhere In Particular]]"), "Nowhere In Particular")
  assert.equal(sweep("the lost [[Cardenio]] of 1613"), "the lost Cardenio of 1613")
  assert.equal(sweep("a [[Pastoral|pastoral]] scene"), "a pastoral scene")
})

test("a title written as a title still resolves to the work", () => {
  assert.equal(rw("see [[Alone]]"), "see [[works/alone-(poe)|Alone]]")
  assert.equal(rw("see [[Alone|Alone]]"), "see [[works/alone-(poe)|Alone]]")
})

test("the surface-form guard does not apply to concept nodes", () => {
  assert.equal(rw("in [[Nature|nature]]"), "in [[motifs/nature|nature]]")
})

test("an unresolvable target is left untouched", () => {
  // Only work-title surface forms are stripped. Anything else may well be a link to a
  // page this index does not carry (a reading page, opere/cerca/naviga, an author page),
  // so rewriting or dropping it would be guesswork.
  assert.equal(rw("see [[Nowhere In Particular]] here"), "see [[Nowhere In Particular]] here")
  assert.equal(rw("see [[opere]] here"), "see [[opere]] here")
  assert.equal(rw("see [[nowhere in particular]] here"), "see [[nowhere in particular]] here")
})

test("an aliasless link keeps its rendered text", () => {
  assert.equal(rw("a [[Well]] here"), "a [[concepts/well|Well]] here")
})

test("an aliased link keeps its alias", () => {
  assert.equal(rw("a [[Nature|natura]] here"), "a [[motifs/nature|natura]] here")
})

test("an escaped alias pipe stays escaped", () => {
  assert.equal(rw("| [[Nature\\|natura]] |"), "| [[motifs/nature\\|natura]] |")
})

test("an alias added inside a table row is escaped", () => {
  assert.equal(rw("| x | [[Well]] |"), "| x | [[concepts/well\\|Well]] |")
})

test("an anchor survives resolution", () => {
  assert.equal(rw("[[Nature#Works|n]]"), "[[motifs/nature#Works|n]]")
})

test("a nested wikilink rewrites only its inner link", () => {
  assert.equal(rw("[[South [[Nature]]]]"), "[[South [[motifs/nature|Nature]]]]")
})

test("authorKey collapses folder, frontmatter and filename forms", () => {
  assert.equal(authorKey("Conan_Doyle"), "conan doyle")
  assert.equal(authorKey("Conan Doyle"), "conan doyle")
})
