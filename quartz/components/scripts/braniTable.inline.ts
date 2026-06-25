// Renders quartz/static/excerpts.json into a sortable, paginated, text-filterable
// table of atomized units (chapters / stories / scenes / sections / excerpts).
// Powers the #brani-table div on the Brani / Excerpts page.

interface Excerpt {
  href: string
  title: string
  author: string
  work: string
  workHref: string
  unitType: string
  order: number
}

let cache: Excerpt[] | null = null
async function loadData(prefix: string): Promise<Excerpt[]> {
  if (cache) return cache
  cache = (await (await fetch(prefix + "static/excerpts.json")).json()) as Excerpt[]
  return cache
}

function esc(s: unknown): string {
  return String(s).replace(/[&<>"]/g, (c) =>
    c === "&" ? "&amp;" : c === "<" ? "&lt;" : c === ">" ? "&gt;" : "&quot;",
  )
}

const PAGE_SIZES = [25, 50, 100, 250]

function buildTable(el: HTMLElement, rows: Excerpt[], prefix: string) {
  let sortKey: keyof Excerpt = "work"
  let sortDir = 1
  let filter = ""
  let page = 0
  let pageSize = 50

  const search = document.createElement("input")
  search.type = "search"
  search.placeholder = `Filter ${rows.length.toLocaleString("en")} excerpts by title, work, author or type…`
  search.className = "lt-search"

  const meta = document.createElement("div")
  meta.className = "lt-meta"
  const table = document.createElement("table")
  table.className = "lt-table"
  const pager = document.createElement("div")
  pager.className = "lt-pager"

  const cols: [keyof Excerpt, string, boolean][] = [
    ["title", "Excerpt", false],
    ["work", "Work", false],
    ["author", "Author", false],
    ["unitType", "Type", false],
  ]

  const noArticle = (s: unknown) =>
    String(s)
      .toLowerCase()
      .replace(/^\s*(the|a|an)\s+/, "")
      .trim()

  function cmp(a: Excerpt, b: Excerpt): number {
    let av: any = noArticle(a[sortKey])
    let bv: any = noArticle(b[sortKey])
    if (av < bv) return -sortDir
    if (av > bv) return sortDir
    // secondary: keep reading order within a work
    if (a.work !== b.work) return a.work < b.work ? -1 : 1
    return a.order - b.order
  }

  function filtered(): Excerpt[] {
    const q = filter.toLowerCase()
    return rows
      .filter(
        (r) =>
          !q ||
          r.title.toLowerCase().includes(q) ||
          r.work.toLowerCase().includes(q) ||
          r.author.toLowerCase().includes(q) ||
          r.unitType.toLowerCase().includes(q),
      )
      .sort(cmp)
  }

  function render() {
    const all = filtered()
    const pages = Math.max(1, Math.ceil(all.length / pageSize))
    if (page >= pages) page = pages - 1
    if (page < 0) page = 0
    const slice = all.slice(page * pageSize, page * pageSize + pageSize)

    const head =
      "<thead><tr>" +
      cols
        .map(
          ([k, label]) =>
            `<th data-k="${k}" class="lt-th${
              sortKey === k ? " sorted-" + (sortDir > 0 ? "asc" : "desc") : ""
            }">${label}</th>`,
        )
        .join("") +
      "</tr></thead>"
    const body =
      "<tbody>" +
      slice
        .map(
          (r) =>
            `<tr><td><a href="${prefix}${esc(r.href)}">${esc(r.title)}</a></td>` +
            `<td class="lt-cluster">${
              r.workHref ? `<a href="${prefix}${esc(r.workHref)}">${esc(r.work)}</a>` : esc(r.work)
            }</td>` +
            `<td>${esc(r.author)}</td>` +
            `<td class="lt-type">${esc(r.unitType)}</td></tr>`,
        )
        .join("") +
      "</tbody>"
    table.innerHTML = head + body
    table.querySelectorAll<HTMLElement>("th.lt-th").forEach((th) => {
      th.addEventListener("click", () => {
        const k = th.dataset.k as keyof Excerpt
        if (sortKey === k) sortDir *= -1
        else {
          sortKey = k
          sortDir = 1
        }
        render()
      })
    })

    meta.innerHTML = `<span><strong>${all.length.toLocaleString("en")}</strong> excerpts</span>`
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
    const info = document.createElement("span")
    info.className = "lt-page-info"
    info.textContent = `Page ${page + 1} of ${pages}`
    pager.append(
      mk("« First", page === 0, () => ((page = 0), render())),
      mk("‹ Prev", page === 0, () => (page--, render())),
      info,
      mk("Next ›", page >= pages - 1, () => (page++, render())),
      mk("Last »", page >= pages - 1, () => ((page = pages - 1), render())),
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
  const root = document.getElementById("brani-table")
  if (!root || root.dataset.rendered) return
  root.dataset.rendered = "1"
  const slug = document.body.dataset.slug || ""
  const prefix = "../".repeat((slug.match(/\//g) || []).length)
  let data: Excerpt[]
  try {
    data = await loadData(prefix)
  } catch {
    root.textContent = "Could not load the excerpts index."
    return
  }
  buildTable(root, data, prefix)
}

document.addEventListener("nav", () => init())
init()
