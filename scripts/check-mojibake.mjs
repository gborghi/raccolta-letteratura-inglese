// Mojibake check over content/ (Clio's QA plan §2). Pattern from the plan:
//   Ã<non-space> | â€ | Â£ | U+FFFD
// Default: WARN (GitHub ::warning annotations + step summary, exit 0) while Clio's
// vault fixes land. Set MOJIBAKE_STRICT=1 (or pass --strict) to fail the build.
import fs from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"

// Latin (plan §2): Ã<non-space> | â€ | Â£ | U+FFFD.
// Greek read as Latin-1/cp1252, two shapes:
//  - lead byte kept: "Î±Î¼" / "Ï€" -> [ÎÏ] followed by a C1/Latin-1 continuation char;
//  - lead byte lost (legacy Greek font, Kubla Khan "£±¼µÁ¿½"): a run of 3+ chars from
//    £ ± ² ³ ´ µ ¶ ¸ ¹ º » ¼ ½ ¾ ¿ À–É (U+00B7 · excluded: "······" is a real dot leader).
export const GREEK_MOJIBAKE = /[ÎÏ][\u0080-\u00BF]|[\u00A3\u00B1-\u00B6\u00B8-\u00C9]{3,}/g
// Residual shapes (Clio, recheck 2026-10-12): Greek/Latin-1 pairs, ¿ glued to a letter,
// superscript digit glued to a capital inside a word (a footnote mark after a space or
// at line start, "e ¹Il termine" in Robespierre, is real and not flagged), OCR "1T[" and Â + lowercase.
export const EXTRA_MOJIBAKE = /[´¿¶½±µ][¿¹½±µÁÃÄÅÆÇÈÉ´¶]|(?<=\S)¹[¿¹½±µÁÃÄÅÆÇÈÉ´¶]|[a-z]¿|¿[a-z]|(?<=[^\s"«(*>])[¹²³][A-ZÀ-Ý]|\d[A-Z]\[|Â[a-z]/g
// Real words these shapes would catch; blanked out before matching.
export const ALLOW = /CHÂTILLON|FLÂNEURS|THÉÂTRE|MAÎTRE|Île|[ÂÅ]ppott/gi
export const MOJIBAKE = new RegExp(
  [/Ã[^\s]|â€|Â£|\uFFFD/.source, GREEK_MOJIBAKE.source, EXTRA_MOJIBAKE.source].join("|"),
  "g",
)
export const mask = (s) => s.replace(ALLOW, (m) => " ".repeat(m.length))

export function scan(dir) {
  const hits = []
  const walk = (d) => {
    for (const e of fs.readdirSync(d, { withFileTypes: true })) {
      const p = path.join(d, e.name)
      if (e.isDirectory()) walk(p)
      else if (e.name.endsWith(".md")) {
        const s = mask(fs.readFileSync(p, "utf8"))
        const m = s.match(MOJIBAKE)
        if (m) {
          const i = s.search(MOJIBAKE)
          const line = s.slice(0, i).split("\n").length
          hits.push({ file: path.relative(process.cwd(), p), count: m.length, line, sample: s.slice(Math.max(0, i - 30), i + 30).replace(/\s+/g, " ") })
        }
      }
    }
  }
  walk(dir)
  return hits
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const args = process.argv.slice(2)
  const strict = args.includes("--strict") || process.env.MOJIBAKE_STRICT === "1"
  const dir = args.find((a) => !a.startsWith("--")) || "content"
  const hits = scan(dir)
  const total = hits.reduce((a, h) => a + h.count, 0)
  const level = strict ? "error" : "warning"
  const gha = !!process.env.GITHUB_ACTIONS
  for (const h of hits) {
    const msg = `mojibake x${h.count}: …${h.sample}…`
    console.log(gha ? `::${level} file=${h.file},line=${h.line}::${msg}` : `${h.file}:${h.line} ${msg}`)
  }
  const summary = `mojibake: ${total} occurrences in ${hits.length} files (${strict ? "strict: failing" : "warning only"})`
  console.log(summary)
  if (process.env.GITHUB_STEP_SUMMARY) fs.appendFileSync(process.env.GITHUB_STEP_SUMMARY, `## Mojibake\n${summary}\n`)
  if (strict && hits.length) process.exit(1)
}
