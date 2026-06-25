// On a concept-axis note (Topoi/Archetypes/Motifs/Concepts/Forms/Historical
// References/Settings/Characters), render the works that use it as a sortable,
// paginated table with a quick filter that searches over the work's title,
// author AND its abstract/summary text (the internal .md text).

interface Work {
  href: string
  title: string
  author: string
  cluster: string
  summary: string
  nconnections: number
}
interface ConceptEntry {
  title: string
  type: string
  works: string[]
}

let workIndex: Map<string, Work> | null = null
let conceptMap: Record<string, ConceptEntry> | null = null

async function load(prefix: string) {
  if (!workIndex) {
    const arr = (await (await fetch(prefix + "static/index.json")).json()) as Work[]
    workIndex = new Map(arr.map((w) => [w.href, w]))
  }
  if (!conceptMap) {
    conceptMap = (await (await fetch(prefix + "static/concepts.json")).json()) as Record<
      string,
      ConceptEntry
    >
  }
}

function esc(s: unknown): string {
  return String(s).replace(/[&<>"]/g, (c) =>
    c === "&" ? "&amp;" : c === "<" ? "&lt;" : c === ">" ? "&gt;" : "&quot;",
  )
}
function highlight(text: string, q: string): string {
  const e = esc(text)
  if (!q) return e
  const idx = e.toLowerCase().indexOf(q.toLowerCase())
  if (idx < 0) return e
  return e.slice(0, idx) + `<mark class="cw-hl">` + e.slice(idx, idx + q.length) + `</mark>` + e.slice(idx + q.length)
}

const PAGE_SIZES = [25, 50, 100]

function buildTable(el: HTMLElement, rows: Work[], prefix: string) {
  let sortKey: keyof Work = "author"
  let sortDir = 1
  let filter = ""
  let page = 0
  let pageSize = 25

  const search = document.createElement("input")
  search.type = "search"
  search.className = "cw-search"
  search.placeholder = `Filter ${rows.length} works by title, author or text…`

  const meta = document.createElement("div")
  meta.className = "cw-meta"
  const table = document.createElement("table")
  table.className = "cw-table"
  const pager = document.createElement("div")
  pager.className = "cw-pager"

  const cols: [keyof Work, string][] = [
    ["title", "Work"],
    ["author", "Author"],
    ["summary", "Abstract"],
  ]

  function cmp(a: Work, b: Work): number {
    let av = String(a[sortKey]).toLowerCase()
    let bv = String(b[sortKey]).toLowerCase()
    if (av < bv) return -sortDir
    if (av > bv) return sortDir
    return a.title.toLowerCase() < b.title.toLowerCase() ? -1 : 1
  }
  function filtered(): Work[] {
    const q = filter.toLowerCase()
    return rows
      .filter(
        (r) =>
          !q ||
          r.title.toLowerCase().includes(q) ||
          r.author.toLowerCase().includes(q) ||
          (r.summary || "").toLowerCase().includes(q),
      )
      .sort(cmp)
  }

  function render() {
    const all = filtered()
    const pages = Math.max(1, Math.ceil(all.length / pageSize))
    if (page >= pages) page = pages - 1
    if (page < 0) page = 0
    const slice = all.slice(page * pageSize, page * pageSize + pageSize)
    const q = filter

    const head =
      "<thead><tr>" +
      cols
        .map(
          ([k, l]) =>
            `<th data-k="${k}" class="cw-th${sortKey === k ? " sorted-" + (sortDir > 0 ? "asc" : "desc") : ""}">${l}</th>`,
        )
        .join("") +
      "</tr></thead>"
    const body =
      "<tbody>" +
      slice
        .map(
          (r) =>
            `<tr><td><a href="${prefix}${esc(r.href)}">${highlight(r.title, q)}</a></td>` +
            `<td>${esc(r.author)}</td>` +
            `<td class="cw-summary">${highlight(r.summary || "", q)}</td></tr>`,
        )
        .join("") +
      "</tbody>"
    table.innerHTML = head + body
    table.querySelectorAll<HTMLElement>("th.cw-th").forEach((th) =>
      th.addEventListener("click", () => {
        const k = th.dataset.k as keyof Work
        if (sortKey === k) sortDir *= -1
        else {
          sortKey = k
          sortDir = 1
        }
        render()
      }),
    )

    meta.innerHTML = `<span><strong>${all.length}</strong> works</span>`
    const sel = document.createElement("select")
    PAGE_SIZES.forEach((s) => {
      const o = document.createElement("option")
      o.value = String(s)
      o.textContent = `${s} / page`
      if (s === pageSize) o.selected = true
      sel.appendChild(o)
    })
    sel.addEventListener("change", () => {
      pageSize = Number(sel.value)
      page = 0
      render()
    })
    meta.appendChild(sel)

    pager.innerHTML = ""
    const mk = (label: string, disabled: boolean, fn: () => void) => {
      const b = document.createElement("button")
      b.textContent = label
      b.disabled = disabled
      b.addEventListener("click", fn)
      return b
    }
    pager.append(
      mk("« First", page === 0, () => {
        page = 0
        render()
      }),
      mk("‹ Prev", page === 0, () => {
        page--
        render()
      }),
    )
    const info = document.createElement("span")
    info.className = "cw-page-info"
    info.textContent = `Page ${page + 1} of ${pages}`
    pager.appendChild(info)
    pager.append(
      mk("Next ›", page >= pages - 1, () => {
        page++
        render()
      }),
      mk("Last »", page >= pages - 1, () => {
        page = pages - 1
        render()
      }),
    )
  }

  search.addEventListener("input", () => {
    filter = search.value
    page = 0
    render()
  })
  el.replaceChildren(search, meta, table, pager)
  render()
}

async function init() {
  const placeholders = Array.from(
    document.querySelectorAll<HTMLElement>("div.concept-works"),
  ).filter((el) => !el.dataset.rendered)
  if (!placeholders.length) return

  const slug = document.body.dataset.slug || ""
  const prefix = "../".repeat((slug.match(/\//g) || []).length)
  try {
    await load(prefix)
  } catch {
    return
  }

  for (const el of placeholders) {
    el.dataset.rendered = "1"
    const entry = conceptMap![el.dataset.slug || ""]
    if (!entry) continue
    const rows = entry.works.map((h) => workIndex!.get(h)).filter(Boolean) as Work[]
    buildTable(el, rows, prefix)
  }
}

document.addEventListener("nav", () => {
  init()
})
init()
