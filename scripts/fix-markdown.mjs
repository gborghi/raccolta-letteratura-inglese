// Markdown hygiene for vault-derived pages (run by preprocess.mjs's final pass over
// content/, and runnable on its own: `node scripts/fix-markdown.mjs [content-dir]`).
//
// Three defects of the imported texts, each of which made markup leak onto the page:
//  1. Stray code fences. Gutenberg texts carry decorative lines such as
//     "~~~ End of Text ~~~"; Markdown reads a line opening with ~~~ or ``` as a code
//     fence, so everything after it (often the whole Italian translation) rendered as
//     a code block with raw [[wikilinks]]. Such a line is escaped so it shows as text.
//  2. Wikilinks broken across a line ("[[motifs/great-house|grande\ncasa]]"): the
//     wikilink parser is line-bound, so the link showed raw. The break is joined.
//  4. Nested links from a second tagging pass ("[[The [[motifs/bells|Bells]]|the Bells]]")
//     become the inner target with the outer label ("[[motifs/bells|the Bells]]").
//  5. Unclosed links ("[[Home|HOME (part 1)" in a chapter title or a TOC entry, where
//     the title was cut after tagging) lose the dangling "[[target|" and keep the text.
//  6. Mangled translation placeholders ("[[]L07|Inquisizione spagnola]]") keep the text.
//  3. Bold with inner padding ("**In ritardo con i tempi, **"): CommonMark refuses a
//     closing ** preceded by a space, so the asterisks showed. Padding is moved out.
// Pure and idempotent; frontmatter is left untouched.

import fs from "node:fs/promises"
import path from "node:path"
import { fileURLToPath } from "node:url"

const FENCE = /^( {0,3})(~{3,}|`{3,})/

function fixFences(body) {
  return body.replace(/^.*$/gm, (line) => {
    const m = FENCE.exec(line)
    return m ? `${m[1]}\\${line.slice(m[1].length)}` : line
  })
}

function fixLinkBreaks(body) {
  // only inside a single [[...]] with no nested brackets; \r?\n plus indentation -> one space
  return body.replace(/\[\[([^\[\]\n]*?)[ \t]*\r?\n[ \t]*([^\[\]\n]*?)\]\]/g, "[[$1 $2]]")
}

const INNER = /\[\[([^\[\]|\n]+)(?:\|([^\[\]\n]*))?\]\]/g
const plain = (x) => x.replace(INNER, (_m, t, l) => (l !== undefined ? l : t))

// Depth-aware: find "[[ ... ]]" spans on one line that contain another "[[...]]" and
// collapse each to one link: the first inner target, labelled with the outer alias
// (or the outer target) in plain text.
function fixNested(body) {
  let out = ""
  let i = 0
  for (;;) {
    const j = body.indexOf("[[", i)
    if (j < 0) return out + body.slice(i)
    out += body.slice(i, j)
    let depth = 0
    let k = j
    let nested = false
    let end = -1
    while (k < body.length) {
      if (body.startsWith("[[", k)) {
        depth++
        if (depth > 1) nested = true
        k += 2
      } else if (body.startsWith("]]", k)) {
        depth--
        k += 2
        if (depth === 0) {
          end = k
          break
        }
      } else if (body[k] === "\n") break
      else k++
    }
    if (!nested || end < 0) {
      out += "[["
      i = j + 2
      continue
    }
    const inner = body.slice(j + 2, end - 2)
    // split at the top-level pipe
    let d = 0
    let pipe = -1
    for (let q = 0; q < inner.length; q++) {
      if (inner.startsWith("[[", q)) (d++, q++)
      else if (inner.startsWith("]]", q)) (d--, q++)
      else if (inner[q] === "|" && d === 0) {
        pipe = q
        break
      }
    }
    const tgtPart = pipe >= 0 ? inner.slice(0, pipe) : inner
    const label = plain(pipe >= 0 ? inner.slice(pipe + 1) : inner).trim()
    const first = new RegExp(INNER.source).exec(tgtPart) || new RegExp(INNER.source).exec(inner)
    out += first ? `[[${first[1]}|${label}]]` : label
    i = end
  }
}

// "[[" whose link never closes: the next of "]]" / "[[" / newline / the '"' closing an
// HTML attribute is not "]]". Drop the opener and an optional "target|" prefix.
function fixUnclosed(body) {
  let out = ""
  let i = 0
  for (;;) {
    const j = body.indexOf("[[", i)
    if (j < 0) return out + body.slice(i)
    out += body.slice(i, j)
    const rest = body.slice(j + 2)
    const m = /\]\]|\[\[|\n|"(?=\s+[a-z-]+=|\s*\/?>)/.exec(rest)
    if (m && m[0] === "]]") {
      out += "[[" + rest.slice(0, m.index + 2)
      i = j + 2 + m.index + 2
      continue
    }
    const end = m ? m.index : rest.length
    const span = rest.slice(0, end)
    const pipe = span.indexOf("|")
    out += pipe >= 0 ? span.slice(pipe + 1) : span
    i = j + 2 + end
  }
}

// A literal "[" glued to a link ("[[[characters/x|X]] crosses R.C.]", a stage direction
// whose name was tagged): the wikilink parser reads the target as "[characters/x" and the
// href comes out as ".../[characters/x" (404). Any "[" left in a target is moved out in
// front of the link as &#91; (which the wikilink parser does not see) and dropped from the target.
function fixBracketTargets(body) {
  return body.replace(/\[\[([^\]|\n]*\[[^\]|\n]*)((?:\\?\|[^\]\n]*)?)\]\]/g, (_m, tgt, rest) => {
    const lead = tgt.match(/^\[*/)[0].length
    const clean = tgt.replace(/\[/g, "").trim()
    return "&#91;".repeat(lead) + (clean ? `[[${clean}${rest}]]` : rest.replace(/^\\?\|/, ""))
  })
}

function fixBoldLine(line) {
  if (!line.includes("**")) return line
  // skip *** runs (bold-italic) — pairing is ambiguous there
  if (/\*{3,}/.test(line)) return line
  const parts = line.split("**")
  if (parts.length < 3 || parts.length % 2 === 0) return line // odd number of ** -> leave
  let changed = false
  for (let i = 1; i < parts.length; i += 2) {
    const inner = parts[i]
    const t = inner.trim()
    if (!t || t === inner) continue
    const lead = inner.slice(0, inner.length - inner.trimStart().length)
    const trail = inner.slice(inner.trimEnd().length)
    parts[i - 1] += lead
    parts[i] = t
    parts[i + 1] = trail + parts[i + 1]
    changed = true
  }
  if (!changed) return line
  let out = parts[0]
  for (let i = 1; i < parts.length; i += 2) out += "**" + parts[i] + "**" + parts[i + 1]
  return out
}

function fixBold(body) {
  return body.replace(/^.*$/gm, fixBoldLine)
}

export function fixMarkdown(text) {
  let fm = ""
  let body = text
  const m = /^---\r?\n[\s\S]*?\r?\n---\r?\n/.exec(text)
  if (m) {
    fm = m[0]
    body = text.slice(fm.length)
  }
  body = fixFences(body)
  // a link can be broken more than once; loop until stable (bounded)
  for (let k = 0; k < 5; k++) {
    const next = fixLinkBreaks(body)
    if (next === body) break
    body = next
  }
  // translation placeholders the model mangled ("[[]L07|Inquisizione spagnola]]"):
  // the target is lost, keep the words
  body = body.replace(/\[\[\]?L\d+\|([^\[\]\n]+)\]\]/g, "$1")
  body = fixNested(body)
  body = fixUnclosed(body)
  body = fixBracketTargets(body)
  body = fixBold(body)
  return fm + body
}

export async function fixTree(dir) {
  const stats = { files: 0, changed: 0 }
  const walk = async (d) => {
    for (const e of await fs.readdir(d, { withFileTypes: true })) {
      const p = path.join(d, e.name)
      if (e.isDirectory()) await walk(p)
      else if (e.name.endsWith(".md")) {
        stats.files++
        const before = await fs.readFile(p, "utf8")
        const after = fixMarkdown(before)
        if (after !== before) {
          await fs.writeFile(p, after)
          stats.changed++
        }
      }
    }
  }
  await walk(dir)
  return stats
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const dir = process.argv[2] || path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "content")
  const s = await fixTree(dir)
  console.log(`fix-markdown: ${s.changed} of ${s.files} pages changed`)
}
