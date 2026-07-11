// Shrink the committed keyword search indexes (excerpts_kw.json ~56MB, works_kw.json
// ~13MB) with TF-IDF. Each entry currently stores every content word of the page; the
// brani/cerca content-search only needs discriminating terms. We re-read each page's
// real text from content/, rank its words by TF-IDF across the corpus, and keep the
// top-N. Corpus-ubiquitous boilerplate (nav, readability box, "chapter") gets idf~0 and
// drops out naturally. Overwrites the two JSON files in place. Run after preprocess
// (needs content/ to exist). Idempotent-ish: re-reads source text each run, so re-running
// reproduces the same result.
import fs from "fs"
import path from "path"

const STATIC = "quartz/static"
const CONTENT = "content"
const TOP_TERMS = 40
const MIN_LEN = 3

const STOP = new Set(
  (
    "the a an and or but if then else of to in on at by for with from as is are was were be been being this that these " +
    "those it its he she we they them his her their our your my me him us not no nor so too very can will would should " +
    "could may might must shall do does did have has had having about into over under out up down off again once here " +
    "there when where why how all any both each few more most other some such only own same than thus yet also which " +
    "what who whom whose said says say one two upon now like man men come came go went see saw know knew think thought " +
    "tell told make made take took give gave let mrs mr dr sir lady much many little day night time life old new long " +
    "thing things way part place your you i o oh ye thou thee thy hath doth unto shall " +
    // rendered-page boilerplate (also killed by idf, but drop early)
    "div span nav class href http https testi html body chapter part story section works work text testo integrale " +
    "readability prose flesch fog complex sent crumb excerpt"
  ).split(/\s+/),
)
const WORD = /[a-zà-ÿ][a-zà-ÿ']+/g

function tokens(md) {
  const cleaned = md
    .replace(/^---\n[\s\S]*?\n---\n/, " ") // frontmatter
    .replace(/<[^>]+>/g, " ") // html tags
    .replace(/\[\[(?:[^\]|]+\|)?([^\]]+)\]\]/g, " $1 ") // wikilink label
    .replace(/\[[^\]]*\]\([^)]*\)/g, " ") // md links
    .replace(/[`*_>#|]/g, " ")
    .toLowerCase()
  const counts = new Map()
  for (const m of cleaned.matchAll(WORD)) {
    const w = m[0]
    if (w.length < MIN_LEN || STOP.has(w)) continue
    counts.set(w, (counts.get(w) || 0) + 1)
  }
  return counts
}

function trim(file, resolve) {
  const p = path.join(STATIC, file)
  if (!fs.existsSync(p)) {
    console.error(`trim-kw-index: ${p} not found — skipping`)
    return
  }
  const idx = JSON.parse(fs.readFileSync(p, "utf8"))
  const keys = Object.keys(idx)
  const before = fs.statSync(p).size

  // pass 1: TF per entry (re-read source text) + DF
  const tf = new Map()
  const df = new Map()
  let missing = 0
  for (const href of keys) {
    const mdPath = resolve(href)
    let counts
    try {
      counts = tokens(fs.readFileSync(mdPath, "utf8"))
    } catch {
      // SPA restructure: atomized excerpts have no standalone file (their key is a
      // `workSlug#atomId` fragment). preprocess already stored the excerpt's vocab as
      // the index value, so tokenize that instead of failing.
      const stored = idx[href]
      if (typeof stored === "string" && stored) {
        counts = tokens(stored)
      } else {
        missing++
        counts = new Map()
      }
    }
    tf.set(href, counts)
    for (const w of counts.keys()) df.set(w, (df.get(w) || 0) + 1)
  }
  const N = keys.length

  // pass 2: keep top-N by TF-IDF
  for (const href of keys) {
    const counts = tf.get(href)
    if (!counts.size) continue // leave original value if we couldn't read the text
    const scored = []
    for (const [w, c] of counts) {
      const idf = Math.log(N / (df.get(w) || 1))
      if (idf <= 0) continue
      scored.push([w, c * idf])
    }
    scored.sort((a, b) => b[1] - a[1])
    idx[href] = scored
      .slice(0, TOP_TERMS)
      .map((x) => x[0])
      .join(" ")
  }

  const out = JSON.stringify(idx)
  fs.writeFileSync(p, out)
  console.log(
    `trim-kw-index: ${file} | ${keys.length} entries, ${missing} unreadable | ` +
      `${(before / 1e6).toFixed(1)}MB -> ${(out.length / 1e6).toFixed(1)}MB (top-${TOP_TERMS} tf-idf)`,
  )
}

// excerpts_kw keys are underscored paths that map 1:1 to content/<key>.md.
const resolveExcerpt = (href) => path.join(CONTENT, href + ".md")

// works_kw keys are hyphenated slugs ("works/1-henry-iv-(shakespeare)") while the work
// files keep spaces ("1 henry iv (shakespeare).md"). Build a slug->file map: each file's
// slug = basename with spaces turned to hyphens (matches how preprocess sluggifies).
function buildWorksResolver() {
  const dir = path.join(CONTENT, "works")
  const map = new Map()
  for (const f of fs.readdirSync(dir)) {
    if (!f.endsWith(".md")) continue
    map.set("works/" + f.slice(0, -3).replaceAll(" ", "-"), path.join(dir, f))
  }
  return (href) => map.get(href) || ""
}

trim("excerpts_kw.json", resolveExcerpt)
trim("works_kw.json", buildWorksResolver())
