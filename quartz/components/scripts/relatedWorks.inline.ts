// Append a "related" section to the bottom of the article:
//  - on a work page (slug under "Works/"): "Opere correlate" — works that share
//    the most (and rarest) concept tags (static/related.json).
//  - on any other content page (chapters/scenes): "Capitoli correlati" — units
//    that share the most (and rarest) characters/themes (static/chapter_related.json).
// Both indexes are precomputed in preprocess.mjs, fetched once and cached across
// SPA navigations — no per-note content rewrite needed.

interface WorkRel {
  href: string
  title: string
  author: string
  shared?: number
}
interface ChapterRel {
  href: string
  title: string
  work: string
  shared: number
  plot: string
}

const caches: Record<string, Record<string, unknown[]> | undefined> = {}
const promises: Record<string, Promise<Record<string, unknown[]>> | undefined> = {}
function load(prefix: string, file: string): Promise<Record<string, unknown[]>> {
  if (caches[file]) return Promise.resolve(caches[file]!)
  if (!promises[file]) {
    promises[file] = fetch(prefix + "static/" + file)
      .then((r) => (r.ok ? r.json() : {}))
      .then((j) => (caches[file] = j as Record<string, unknown[]>))
      .catch(() => (caches[file] = {}))
  }
  return promises[file]!
}

function makeSection(heading: string): { section: HTMLElement; ul: HTMLElement } {
  const section = document.createElement("section")
  section.className = "related-works"
  const h = document.createElement("h2")
  h.textContent = heading
  section.appendChild(h)
  const ul = document.createElement("ul")
  section.appendChild(ul)
  return { section, ul }
}

function link(prefix: string, href: string, text: string): HTMLAnchorElement {
  const a = document.createElement("a")
  a.className = "internal"
  a.href = prefix + href
  a.textContent = text
  return a
}

async function init() {
  const slug = document.body.dataset.slug || ""
  const article = document.querySelector("article")
  if (!article || article.querySelector(".related-works")) return
  const prefix = "../".repeat((slug.match(/\//g) || []).length)
  const isWork = slug.startsWith("Works/")

  let data: Record<string, unknown[]>
  try {
    data = await load(prefix, isWork ? "related.json" : "chapter_related.json")
  } catch {
    return
  }
  const rels = data[slug]
  if (!rels || !rels.length) return
  // SPA may have navigated away (or another run already injected) while awaiting.
  if ((document.body.dataset.slug || "") !== slug) return
  if (article.querySelector(".related-works")) return

  if (isWork) {
    const { section, ul } = makeSection("Opere correlate")
    for (const r of rels as WorkRel[]) {
      const li = document.createElement("li")
      li.appendChild(link(prefix, r.href, r.title))
      if (r.author) {
        const span = document.createElement("span")
        span.className = "rw-author"
        span.textContent = " — " + r.author
        li.appendChild(span)
      }
      ul.appendChild(li)
    }
    article.appendChild(section)
  } else {
    const { section, ul } = makeSection("Capitoli correlati")
    for (const r of rels as ChapterRel[]) {
      const li = document.createElement("li")
      li.className = "rw-chapter"
      li.appendChild(link(prefix, r.href, r.title))
      if (r.plot) {
        const p = document.createElement("div")
        p.className = "rw-plot"
        p.textContent = r.plot
        li.appendChild(p)
      }
      ul.appendChild(li)
    }
    article.appendChild(section)
  }
}

document.addEventListener("nav", () => {
  init()
})
init()

export {}
