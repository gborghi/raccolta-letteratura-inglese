// Renders the static index.json into a sortable, paginated, text-filterable table
// of literary works. Powers the #opere-table div on the Works page, and also any
// #opere-table[data-author] / [data-cluster] scoped variants.

interface Work {
  href: string
  readHref?: string
  title: string
  author: string
  cluster: string
  topoi: string[]
  archetypes: string[]
  motifs: string[]
  concepts: string[]
  forms: string[]
  histrefs: string[]
  settings: string[]
  characters: string[]
  nconnections: number
  flesch?: number
  fkgrade?: number
  fog?: number
}

let cache: Work[] | null = null
async function loadData(prefix: string): Promise<Work[]> {
  if (cache) return cache
  const res = await fetch(prefix + "static/index.json")
  cache = (await res.json()) as Work[]
  return cache
}

let kwCache: Record<string, string> | null = null
let kwPromise: Promise<Record<string, string>> | null = null
function loadKw(prefix: string): Promise<Record<string, string>> {
  if (kwCache) return Promise.resolve(kwCache)
  if (!kwPromise) {
    kwPromise = fetch(prefix + "static/works_kw.json")
      .then((r) => r.json())
      .then((j) => (kwCache = j as Record<string, string>))
  }
  return kwPromise
}

function esc(s: unknown): string {
  return String(s).replace(/[&<>"]/g, (c) =>
    c === "&" ? "&amp;" : c === "<" ? "&lt;" : c === ">" ? "&gt;" : "&quot;",
  )
}

const PAGE_SIZES = [25, 50, 100, 250]

function buildTable(el: HTMLElement, rows: Work[], prefix: string) {
  let sortKey: keyof Work = "title"
  let sortDir = 1
  let filter = ""
  let page = 0
  let pageSize = 50
  let mode: "table" | "content" = "table"

  const search = document.createElement("input")
  search.type = "search"
  search.className = "lt-search"
  const setPlaceholder = () => {
    search.placeholder =
      mode === "content"
        ? `Search full content of the ${rows.length} works…`
        : `Filter ${rows.length.toLocaleString("en")} works by title, author or cluster…`
  }
  setPlaceholder()

  const modeBtn = document.createElement("button")
  modeBtn.className = "qtable-modebtn"
  modeBtn.type = "button"
  const syncModeBtn = () => {
    modeBtn.textContent = mode === "content" ? "Search: full content" : "Search: title/author"
    modeBtn.setAttribute("aria-pressed", String(mode === "content"))
  }
  syncModeBtn()
  modeBtn.addEventListener("click", async () => {
    mode = mode === "table" ? "content" : "table"
    syncModeBtn()
    setPlaceholder()
    page = 0
    if (mode === "content" && !kwCache) {
      modeBtn.textContent = "Loading index..."
      modeBtn.disabled = true
      try {
        await loadKw(prefix)
      } catch {}
      modeBtn.disabled = false
      syncModeBtn()
    }
    render()
  })

  const searchRow = document.createElement("div")
  searchRow.className = "qtable-searchrow"
  searchRow.append(search, modeBtn)

  const meta = document.createElement("div")
  meta.className = "lt-meta"

  const table = document.createElement("table")
  table.className = "lt-table"

  const pager = document.createElement("div")
  pager.className = "lt-pager"

  const cols: [keyof Work, string, boolean][] = [
    ["title", "Title", false],
    ["author", "Author", false],
    ["cluster", "Cluster", false],
    ["nconnections", "Links", true],
    ["flesch", "Flesch", true],
    ["fkgrade", "Grade", true],
    ["fog", "Fog", true],
  ]
  const NUMERIC = new Set(["nconnections", "flesch", "fkgrade", "fog"])

  const noArticle = (s: unknown) =>
    String(s)
      .toLowerCase()
      .replace(/^\s*(the|a|an)\s+/, "")
      .trim()

  function cmp(a: Work, b: Work): number {
    let av: any = a[sortKey]
    let bv: any = b[sortKey]
    if (NUMERIC.has(sortKey as string)) {
      av = Number(av)
      bv = Number(bv)
      const an = Number.isFinite(av), bn = Number.isFinite(bv)
      if (!an && !bn) return a.title.toLowerCase() < b.title.toLowerCase() ? -1 : 1
      if (!an) return 1 // works without this metric (poetry/theatre) sort last
      if (!bn) return -1
    } else {
      av = noArticle(av)
      bv = noArticle(bv)
    }
    if (av < bv) return -sortDir
    if (av > bv) return sortDir
    return a.title.toLowerCase() < b.title.toLowerCase() ? -1 : 1
  }

  function filtered(): Work[] {
    const q = filter.toLowerCase()
    return rows
      .filter((r) => {
        if (!q) return true
        if (mode === "content") {
          const kw = kwCache?.[r.href]
          return kw ? kw.includes(q) : false
        }
        return (
          r.title.toLowerCase().includes(q) ||
          r.author.toLowerCase().includes(q) ||
          r.cluster.toLowerCase().includes(q)
        )
      })
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
          ([k, label, num]) =>
            `<th data-k="${k}" class="lt-th${num ? " lt-num" : ""}${
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
            `<tr><td><a href="${prefix}${esc(r.readHref || r.href)}">${esc(r.title)}</a></td>` +
            `<td>${esc(r.author)}</td>` +
            `<td class="lt-cluster">${esc(r.cluster)}</td>` +
            `<td class="lt-num">${esc(r.nconnections)}</td>` +
            `<td class="lt-num">${r.flesch ?? "—"}</td>` +
            `<td class="lt-num">${r.fkgrade ?? "—"}</td>` +
            `<td class="lt-num">${r.fog ?? "—"}</td></tr>`,
        )
        .join("") +
      "</tbody>"
    table.innerHTML = head + body
    table.querySelectorAll<HTMLElement>("th.lt-th").forEach((th) => {
      th.addEventListener("click", () => {
        const k = th.dataset.k as keyof Work
        if (sortKey === k) sortDir *= -1
        else {
          sortKey = k
          sortDir = NUMERIC.has(k as string) ? -1 : 1
        }
        render()
      })
    })

    meta.innerHTML = `<span><strong>${all.length.toLocaleString("en")}</strong> works</span>`
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
    const first = document.createElement("button")
    first.textContent = "« First"
    first.disabled = page === 0
    first.addEventListener("click", () => {
      page = 0
      render()
    })
    const prev = document.createElement("button")
    prev.textContent = "‹ Prev"
    prev.disabled = page === 0
    prev.addEventListener("click", () => {
      page--
      render()
    })
    const info = document.createElement("span")
    info.className = "lt-page-info"
    info.textContent = `Page ${page + 1} of ${pages}`
    const next = document.createElement("button")
    next.textContent = "Next ›"
    next.disabled = page >= pages - 1
    next.addEventListener("click", () => {
      page++
      render()
    })
    const last = document.createElement("button")
    last.textContent = "Last »"
    last.disabled = page >= pages - 1
    last.addEventListener("click", () => {
      page = pages - 1
      render()
    })
    pager.append(first, prev, info, next, last)
  }

  search.addEventListener("input", () => {
    filter = search.value
    page = 0
    render()
  })

  el.replaceChildren(searchRow, meta, table, pager)
  render()
}

async function init() {
  const root = document.getElementById("opere-table")
  if (!root || root.dataset.rendered) return
  root.dataset.rendered = "1"

  const slug = document.body.dataset.slug || ""
  const prefix = "../".repeat((slug.match(/\//g) || []).length)

  let data: Work[]
  try {
    data = await loadData(prefix)
  } catch {
    root.textContent = "Could not load the works index."
    return
  }

  let rows = data
  if (root.dataset.author) rows = data.filter((w) => w.author === root.dataset.author)
  if (root.dataset.cluster) rows = data.filter((w) => w.cluster === root.dataset.cluster)
  buildTable(root, rows, prefix)
}

// Deep-link delegation for the home author cards: store the chosen author in
// sessionStorage and let the /cerca page pick it up. Done via JS so Quartz's
// link sluggifier (which mangles "?"/"=" in hrefs) never sees the parameter.
function wireAuthorCards() {
  document.querySelectorAll<HTMLElement>("a.author-card[data-cerca-author]").forEach((a) => {
    if (a.dataset.wired) return
    a.dataset.wired = "1"
    a.addEventListener("click", () => {
      try {
        sessionStorage.setItem("cercaPreselect", "author::" + a.dataset.cercaAuthor)
      } catch {}
    })
  })
}

document.addEventListener("nav", () => {
  init()
  wireAuthorCards()
})
init()
wireAuthorCards()

export {}
