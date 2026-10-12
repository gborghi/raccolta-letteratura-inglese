// Post-build (run right after `npx quartz build`, BEFORE inject-atom-search.mjs /
// compress-search-index.mjs). Clio's QA plan §3–§4.
//
// 1. Thin pages -> noindex. A knowledge-graph character page whose body is only the
//    generator's template (title, "appears in N work(s)" / "a character in X's works",
//    the works list) carries no
//    prose of its own. Such a page gets <meta name="robots" content="noindex, follow">,
//    leaves sitemap.xml, and is flagged `noindex: true` in contentIndex.json — the
//    Explorer filterFn (quartz.config.yaml) and build-search-shards.mjs skip flagged
//    entries. The page itself stays reachable from every link (no 404s). As soon as a
//    description is written into the page it becomes indexable again, automatically.
// 2. Redirects (data/redirects.json): a static page at each old URL that sends the
//    reader to the new one (meta refresh + canonical + JS), for both hosts.
//
//   node scripts/postbuild-pages.mjs [public-dir] [content-dir]
import fs from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"

const THIN_DIRS = ["characters"]
// Any sentence of its own (even a one-line description) makes a page worth indexing;
// below this the page is template only.
export const MIN_PROSE_CHARS = 40

const slugOf = (rel) =>
  rel
    .replace(/\.md$/, "")
    .split("/")
    .map((s) => s.replace(/\s/g, "-").replace(/&/g, "-and-").replace(/%/g, "-percent").replace(/[?#]/g, "").toLowerCase())
    .join("/")

// prose left once the generator's template is removed
export function ownProse(md) {
  let s = md.replace(/^---\r?\n[\s\S]*?\r?\n---\r?\n/, "")
  s = s.replace(/^\*[A-Za-z ]+\*\s+—\s+appears in \*\*\d+\*\* work\(s\)\.\s*$/m, "")
  s = s.replace(/^\*[A-Za-z ]+\*\s+—\s+a character in [^\n]*?works\.\s*$/m, "")
  s = s.replace(/^## Works[\s\S]*$/m, "") // the works section runs to the end of the template
  s = s.replace(/<[^>]+>/g, "").replace(/#[\w/-]+/g, "").replace(/\s+/g, " ").trim()
  return s
}

export function thinSlugs(contentDir) {
  const out = []
  for (const d of THIN_DIRS) {
    const dir = path.join(contentDir, d)
    if (!fs.existsSync(dir)) continue
    for (const f of fs.readdirSync(dir)) {
      if (!f.endsWith(".md")) continue
      const md = fs.readFileSync(path.join(dir, f), "utf8")
      if (/^noindex:\s*false\s*$/m.test(md)) continue // explicit opt-out
      if (ownProse(md).length < MIN_PROSE_CHARS || /^noindex:\s*true\s*$/m.test(md)) out.push(slugOf(`${d}/${f}`))
    }
  }
  return out
}

const META = '<meta name="robots" content="noindex, follow">'

function redirectPage(baseUrl, to) {
  const href = `/${to}`
  const canon = baseUrl ? `https://${baseUrl}${href}` : href
  return `<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>Redirecting…</title>${META}<link rel="canonical" href="${canon}"><meta http-equiv="refresh" content="0; url=${href}"><script>location.replace(${JSON.stringify(href)}+location.hash)</script></head><body><a href="${href}">${href}</a></body></html>\n`
}

export function run(pub, contentDir, root) {
  const thin = thinSlugs(contentDir)
  const thinSet = new Set(thin)
  let meta = 0
  for (const s of thin) {
    const p = path.join(pub, s + ".html")
    if (!fs.existsSync(p)) continue
    const h = fs.readFileSync(p, "utf8")
    if (h.includes('name="robots"')) continue
    fs.writeFileSync(p, h.replace(/<head([^>]*)>/i, `<head$1>${META}`))
    meta++
  }
  // sitemap
  const smPath = path.join(pub, "sitemap.xml")
  let smDropped = 0
  if (fs.existsSync(smPath)) {
    const sm = fs.readFileSync(smPath, "utf8")
    const next = sm.replace(/<url>\s*<loc>[^<]*?\/([^<]*)<\/loc>[\s\S]*?<\/url>/g, (m, loc) => {
      // loc is everything after the host's last "/"-run; recover the path robustly
      const full = /<loc>([^<]*)<\/loc>/.exec(m)[1]
      const p = decodeURI(full.replace(/^https?:\/\/[^/]+\/?/, ""))
      const parts = p.split("/")
      const cand = [p, parts.slice(1).join("/")] // second form: GitHub Pages subpath
      if (cand.some((c) => thinSet.has(c))) {
        smDropped++
        return ""
      }
      return m
    })
    fs.writeFileSync(smPath, next)
  }
  // contentIndex flag
  const ciPath = path.join(pub, "static", "contentIndex.json")
  let flagged = 0
  if (fs.existsSync(ciPath)) {
    const raw = JSON.parse(fs.readFileSync(ciPath, "utf8"))
    const idx = raw && raw.content && typeof raw.content === "object" && !raw.slug ? raw.content : raw
    for (const s of thin) if (idx[s]) ((idx[s].noindex = true), flagged++)
    fs.writeFileSync(ciPath, JSON.stringify(raw))
  }
  // redirects
  const red = JSON.parse(fs.readFileSync(path.join(root, "data", "redirects.json"), "utf8"))
  const cfg = fs.readFileSync(path.join(root, "quartz.config.yaml"), "utf8")
  const baseUrl = (/^\s*baseUrl:\s*(\S+)/m.exec(cfg) || [])[1] || ""
  const basePath = baseUrl.includes("/") ? baseUrl.slice(baseUrl.indexOf("/")) : ""
  let redirects = 0
  for (const [from, to] of Object.entries(red)) {
    if (from.startsWith("_")) continue
    const p = path.join(pub, from + ".html")
    if (fs.existsSync(p) && !fs.readFileSync(p, "utf8").includes("Redirecting")) {
      console.warn(`postbuild-pages: ${from} is a real page, redirect skipped`)
      continue
    }
    fs.mkdirSync(path.dirname(p), { recursive: true })
    fs.writeFileSync(p, redirectPage(baseUrl.split("/")[0], (basePath ? basePath.slice(1) + "/" : "") + to))
    redirects++
  }
  return { thin: thin.length, meta, smDropped, flagged, redirects }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const root = path.join(path.dirname(fileURLToPath(import.meta.url)), "..")
  const pub = process.argv[2] || path.join(root, "public")
  const contentDir = process.argv[3] || path.join(root, "content")
  const r = run(pub, contentDir, root)
  console.log(
    `postbuild-pages: ${r.thin} thin pages -> ${r.meta} noindex meta, ${r.smDropped} out of sitemap, ` +
      `${r.flagged} flagged in contentIndex; ${r.redirects} redirect pages`,
  )
}
