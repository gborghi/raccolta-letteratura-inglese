// Titles of split reading pages (Clio's QA plan §5).
//
// Some reading pages under content/testi/ were emitted with the FILE NAME as title
// ("ascetic") instead of the work's title ("THE SONG of the STRANGE ASCETIC"), and their
// split units are labelled "<file name> (part N)". When a page's title is just its file
// stem and its parentWork has a real, different title, this pass uses the work title:
//   title: "ascetic"                    -> title: "THE SONG of the STRANGE ASCETIC"
//   data-title="ascetic"                -> data-title="THE SONG of the STRANGE ASCETIC"
//   data-title="ascetic (part 1)"       -> data-title="THE SONG of the STRANGE ASCETIC — part 1 of 2"
// Pure, idempotent; run by preprocess.mjs's final pass and on its own:
//   node scripts/fix-titles.mjs [content-dir]
import fs from "node:fs/promises"
import path from "node:path"
import { fileURLToPath } from "node:url"

const slugOf = (rel) =>
  rel
    .replace(/\.md$/, "")
    .split("/")
    .map((s) => s.replace(/\s/g, "-").replace(/&/g, "-and-").replace(/%/g, "-percent").replace(/[?#]/g, "").toLowerCase())
    .join("/")

const norm = (s) => String(s).toLowerCase().replace(/[_\-\s]+/g, " ").trim()
const fmField = (fm, k) => {
  const m = new RegExp(`^${k}:\\s*(.*)$`, "m").exec(fm)
  if (!m) return null
  let v = m[1].trim()
  if ((v.startsWith('"') && v.endsWith('"')) || (v.startsWith("'") && v.endsWith("'"))) {
    v = v.slice(1, -1).replace(/''/g, "'").replace(/\\"/g, '"')
  }
  return v
}
const escAttr = (s) => s.replace(/&/g, "&amp;").replace(/"/g, "&quot;")
const yamlStr = (s) => JSON.stringify(s)

export function fixTitle(text, stem, workTitle) {
  const m = /^---\r?\n([\s\S]*?)\r?\n---\r?\n/.exec(text)
  if (!m || !workTitle) return text
  const title = fmField(m[1], "title")
  if (title == null || norm(title) !== norm(stem) || norm(workTitle) === norm(title)) return text
  const fm = m[1].replace(/^title:.*$/m, `title: ${yamlStr(workTitle)}`)
  let body = text.slice(m[0].length)
  const esc = title.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
  const partRe = new RegExp(`data-title="${esc} \\(part (\\d+)\\)"`, "g")
  const total = (body.match(partRe) || []).length
  body = body
    .replace(partRe, (_m, n) =>
        total > 1 ? `data-title="${escAttr(workTitle)} — part ${n} of ${total}"` : `data-title="${escAttr(workTitle)}"`)
    .replace(new RegExp(`data-title="${esc}"`, "g"), `data-title="${escAttr(workTitle)}"`)
  return `---\n${fm}\n---\n` + body
}

export async function workTitles(contentDir) {
  const map = new Map()
  const dir = path.join(contentDir, "works")
  for (const f of await fs.readdir(dir)) {
    if (!f.endsWith(".md")) continue
    const head = (await fs.readFile(path.join(dir, f), "utf8")).slice(0, 2000)
    const m = /^---\r?\n([\s\S]*?)\r?\n---/.exec(head)
    const t = m && fmField(m[1], "title")
    if (t) map.set(slugOf("works/" + f), t)
  }
  return map
}

export async function fixTitlesTree(contentDir) {
  const titles = await workTitles(contentDir)
  const stats = { changed: 0, files: [] }
  const walk = async (d) => {
    for (const e of await fs.readdir(d, { withFileTypes: true })) {
      const p = path.join(d, e.name)
      if (e.isDirectory()) await walk(p)
      else if (e.name.endsWith(".md")) {
        const t = await fs.readFile(p, "utf8")
        const m = /^---\r?\n([\s\S]*?)\r?\n---/.exec(t)
        const pw = m && fmField(m[1], "parentWork")
        if (!pw) continue
        const out = fixTitle(t, e.name.slice(0, -3), titles.get(pw.toLowerCase()))
        if (out !== t) {
          await fs.writeFile(p, out)
          stats.changed++
          stats.files.push(path.relative(contentDir, p))
        }
      }
    }
  }
  await walk(path.join(contentDir, "testi"))
  return stats
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const dir = process.argv[2] || path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "content")
  const s = await fixTitlesTree(dir)
  console.log(`fix-titles: ${s.changed} reading pages retitled`)
  for (const f of s.files) console.log("  " + f)
}
