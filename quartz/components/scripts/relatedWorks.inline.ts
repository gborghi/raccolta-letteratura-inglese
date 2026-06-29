// On a work page (slug under "Works/"), append an "Opere correlate" section
// listing the works that share the most (and rarest) concept tags. Data comes
// from static/related.json (precomputed in preprocess.mjs), fetched once and
// cached across SPA navigations — no per-note content rewrite needed.

interface Rel {
  href: string
  title: string
  author: string
  shared: number
}

let cache: Record<string, Rel[]> | null = null
let promise: Promise<Record<string, Rel[]>> | null = null
function load(prefix: string): Promise<Record<string, Rel[]>> {
  if (cache) return Promise.resolve(cache)
  if (!promise) {
    promise = fetch(prefix + "static/related.json")
      .then((r) => r.json())
      .then((j) => (cache = j as Record<string, Rel[]>))
  }
  return promise
}

async function init() {
  const slug = document.body.dataset.slug || ""
  if (!slug.startsWith("Works/")) return
  const article = document.querySelector("article")
  if (!article || article.querySelector(".related-works")) return

  const prefix = "../".repeat((slug.match(/\//g) || []).length)
  let data: Record<string, Rel[]>
  try {
    data = await load(prefix)
  } catch {
    return
  }
  const rels = data[slug]
  if (!rels || !rels.length) return

  // SPA may have navigated away (or another run already injected) while we awaited.
  if ((document.body.dataset.slug || "") !== slug) return
  if (article.querySelector(".related-works")) return

  const section = document.createElement("section")
  section.className = "related-works"
  const h = document.createElement("h2")
  h.textContent = "Opere correlate"
  section.appendChild(h)

  const ul = document.createElement("ul")
  for (const r of rels) {
    const li = document.createElement("li")
    const a = document.createElement("a")
    a.className = "internal"
    a.href = prefix + r.href
    a.textContent = r.title
    li.appendChild(a)
    if (r.author) {
      const span = document.createElement("span")
      span.className = "rw-author"
      span.textContent = " — " + r.author
      li.appendChild(span)
    }
    ul.appendChild(li)
  }
  section.appendChild(ul)
  article.appendChild(section)
}

document.addEventListener("nav", () => {
  init()
})
init()

export {}
