// Faceted multi-select search for the /cerca page. Loads index.json and lets the
// user combine tags across facets (Author, Cluster, Topos, Archetype, Motif,
// Theme/Concept, Form, Historical Reference, Setting, Character) with an
// AND/OR (ALL/ANY) toggle, rendering matches into a sortable, paginated table.

interface Work {
  href: string
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
}

interface Facet {
  key: keyof Work
  label: string
  multi?: boolean
}

const FACETS: Facet[] = [
  { key: "author", label: "Author" },
  { key: "cluster", label: "Cluster" },
  { key: "topoi", label: "Topos", multi: true },
  { key: "archetypes", label: "Archetype", multi: true },
  { key: "motifs", label: "Motif", multi: true },
  { key: "concepts", label: "Theme / Concept", multi: true },
  { key: "forms", label: "Form", multi: true },
  { key: "histrefs", label: "Historical Reference", multi: true },
  { key: "settings", label: "Setting", multi: true },
  { key: "characters", label: "Character", multi: true },
]

const PAGE_SIZE = 50

function esc(s: unknown): string {
  return String(s).replace(/[&<>"]/g, (c) =>
    c === "&" ? "&amp;" : c === "<" ? "&lt;" : c === ">" ? "&gt;" : "&quot;",
  )
}
function pretty(v: string): string {
  const s = v.replace(/_/g, " ")
  return s.charAt(0).toUpperCase() + s.slice(1)
}

async function init() {
  const root = document.getElementById("cerca")
  if (!root || root.dataset.rendered) return
  root.dataset.rendered = "1"

  const slug = document.body.dataset.slug || ""
  const prefix = "../".repeat((slug.match(/\//g) || []).length)
  let data: Work[]
  try {
    data = await (await fetch(prefix + "static/index.json")).json()
  } catch {
    root.textContent = "Could not load the works index."
    return
  }

  // selected tags as "facetKey::value"
  const selected = new Set<string>()
  let mode: "AND" | "OR" = "AND"
  let page = 0

  // Deep-link: the home author cards stash an "author::Name" token in
  // sessionStorage (Quartz mangles query/hash params in hrefs, so JS is used).
  // Also honour an explicit ?author= / ?cluster= query string if present.
  try {
    const pre = sessionStorage.getItem("cercaPreselect")
    if (pre) {
      selected.add(pre)
      sessionStorage.removeItem("cercaPreselect")
    }
  } catch {}
  const params = new URLSearchParams(location.search.replace(/^\?/, ""))
  const qpAuthor = params.get("author")
  if (qpAuthor) selected.add(`author::${decodeURIComponent(qpAuthor)}`)
  const qpCluster = params.get("cluster")
  if (qpCluster) selected.add(`cluster::${decodeURIComponent(qpCluster)}`)

  const facetValues: { facet: Facet; values: [string, number][] }[] = FACETS.map((facet) => {
    const counts = new Map<string, number>()
    for (const w of data) {
      const raw = w[facet.key] as unknown
      const vals = facet.multi
        ? ((raw as string[]) || [])
        : raw === "" || raw == null
          ? []
          : [String(raw)]
      for (const v of vals) counts.set(v, (counts.get(v) || 0) + 1)
    }
    const values = [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    return { facet, values }
  })

  function matches(w: Work): boolean {
    if (selected.size === 0) return false
    const test = (token: string) => {
      const idx = token.indexOf("::")
      const key = token.slice(0, idx)
      const val = token.slice(idx + 2)
      const facet = FACETS.find((f) => f.key === key)!
      if (facet.multi) return ((w[facet.key] as unknown as string[]) || []).includes(val)
      return String(w[facet.key]) === val
    }
    const tokens = [...selected]
    return mode === "AND" ? tokens.every(test) : tokens.some(test)
  }

  const controls = document.createElement("div")
  controls.className = "cerca-controls"
  const facetsBox = document.createElement("div")
  facetsBox.className = "cerca-facets"
  const selectedBar = document.createElement("div")
  selectedBar.className = "cerca-selected"
  const resultsBox = document.createElement("div")
  resultsBox.className = "cerca-results"
  root.replaceChildren(controls, facetsBox, selectedBar, resultsBox)

  const toggle = document.createElement("button")
  toggle.className = "cerca-toggle"
  function syncToggle() {
    toggle.textContent = mode === "AND" ? "Match: ALL selected tags" : "Match: ANY selected tag"
  }
  toggle.addEventListener("click", () => {
    mode = mode === "AND" ? "OR" : "AND"
    syncToggle()
    page = 0
    render()
  })
  syncToggle()
  controls.appendChild(toggle)

  for (const { facet, values } of facetValues) {
    const sec = document.createElement("details")
    sec.className = "cerca-facet"
    const sum = document.createElement("summary")
    sum.textContent = `${facet.label} (${values.length})`
    sec.appendChild(sum)
    const chips = document.createElement("div")
    chips.className = "cerca-chips"
    for (const [val, count] of values) {
      const token = `${facet.key}::${val}`
      const chip = document.createElement("button")
      chip.className = "cerca-chip"
      chip.dataset.token = token
      chip.innerHTML = `${esc(facet.multi ? pretty(val) : val)} <span class="cerca-n">${count}</span>`
      chip.addEventListener("click", () => {
        if (selected.has(token)) selected.delete(token)
        else selected.add(token)
        page = 0
        render()
      })
      chips.appendChild(chip)
    }
    sec.appendChild(chips)
    facetsBox.appendChild(sec)
  }

  let sortKey: keyof Work = "title"
  let sortDir = 1
  function renderResults() {
    if (selected.size === 0) {
      resultsBox.innerHTML = `<p class="cerca-hint">Select one or more tags above to see matching works.</p>`
      return
    }
    const rows = data.filter(matches)
    rows.sort((a, b) => {
      let av: any = a[sortKey]
      let bv: any = b[sortKey]
      if (sortKey === "nconnections") {
        av = Number(av)
        bv = Number(bv)
      } else {
        av = String(av).toLowerCase()
        bv = String(bv).toLowerCase()
      }
      if (av < bv) return -sortDir
      if (av > bv) return sortDir
      return a.title.toLowerCase() < b.title.toLowerCase() ? -1 : 1
    })
    const pages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE))
    if (page >= pages) page = pages - 1
    const slice = rows.slice(page * PAGE_SIZE, page * PAGE_SIZE + PAGE_SIZE)
    const cols: [keyof Work, string, boolean][] = [
      ["title", "Title", false],
      ["author", "Author", false],
      ["cluster", "Cluster", false],
      ["nconnections", "Links", true],
    ]
    const head = cols
      .map(
        ([k, l, num]) =>
          `<th data-k="${k}" class="lt-th${num ? " lt-num" : ""}${sortKey === k ? " sorted-" + (sortDir > 0 ? "asc" : "desc") : ""}">${l}</th>`,
      )
      .join("")
    const body = slice
      .map(
        (r) =>
          `<tr><td><a href="${prefix}${esc(r.href)}">${esc(r.title)}</a></td>` +
          `<td>${esc(r.author)}</td><td class="lt-cluster">${esc(r.cluster)}</td><td class="lt-num">${esc(r.nconnections)}</td></tr>`,
      )
      .join("")
    resultsBox.innerHTML =
      `<div class="cerca-count"><strong>${rows.length.toLocaleString("en")}</strong> works</div>` +
      `<table class="lt-table"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>` +
      `<div class="cerca-pager"></div>`
    resultsBox.querySelectorAll<HTMLElement>("th.lt-th").forEach((th) =>
      th.addEventListener("click", () => {
        const k = th.dataset.k as keyof Work
        if (sortKey === k) sortDir *= -1
        else {
          sortKey = k
          sortDir = k === "nconnections" ? -1 : 1
        }
        renderResults()
      }),
    )
    const pager = resultsBox.querySelector(".cerca-pager")!
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
        renderResults()
      }),
      mk("‹ Prev", page === 0, () => {
        page--
        renderResults()
      }),
    )
    const info = document.createElement("span")
    info.className = "lt-page-info"
    info.textContent = `Page ${page + 1} of ${pages}`
    pager.appendChild(info)
    pager.append(
      mk("Next ›", page >= pages - 1, () => {
        page++
        renderResults()
      }),
      mk("Last »", page >= pages - 1, () => {
        page = pages - 1
        renderResults()
      }),
    )
  }

  function renderSelected() {
    if (selected.size === 0) {
      selectedBar.innerHTML = ""
      return
    }
    selectedBar.innerHTML =
      `<span class="cerca-sel-label">Active tags:</span> ` +
      [...selected]
        .map((token) => {
          const idx = token.indexOf("::")
          const key = token.slice(0, idx)
          const val = token.slice(idx + 2)
          const f = FACETS.find((x) => x.key === key)!
          return `<button class="cerca-chip active" data-token="${esc(token)}">${esc(f.label)}: ${esc(f.multi ? pretty(val) : val)} ✕</button>`
        })
        .join("") +
      ` <button class="cerca-clear">Clear all</button>`
    selectedBar.querySelectorAll<HTMLElement>(".cerca-chip.active").forEach((b) =>
      b.addEventListener("click", () => {
        selected.delete(b.dataset.token!)
        page = 0
        render()
      }),
    )
    selectedBar.querySelector(".cerca-clear")?.addEventListener("click", () => {
      selected.clear()
      page = 0
      render()
    })
  }

  function syncChipStates() {
    facetsBox.querySelectorAll<HTMLElement>(".cerca-chip").forEach((c) => {
      c.classList.toggle("active", selected.has(c.dataset.token!))
    })
  }

  function render() {
    syncChipStates()
    renderSelected()
    renderResults()
  }

  render()
}

document.addEventListener("nav", () => {
  init()
})
init()
