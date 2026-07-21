// Tiered depth search — replaces the core FlexSearch top-bar search with an in-repo
// component whose depth SLIDER progressively loads shard tiers (search-t{0..3}.json):
//   0 Fast     works + concepts, top-30 terms          (default, instant)
//   1 Standard works, top-150 terms                    (better recall)
//   2 Deep     + ~19k per-atom entries                 (search inside chapters)
//   3 Max      full terms + 700-char snippets + fuzzy  (MiniSearch typo tolerance)
// Each tier's `content` is a superset of the shallower one, so deepening = replace doc
// content by slug + add new atom slugs (see searchDepth.ts mergeTier). Mobile clamps ≤1.
// Shipped globally via componentResources (see that emitter). The community search
// plugin is disabled in quartz.config.yaml.
import FlexSearch from "flexsearch"
import MiniSearch from "minisearch"
import {
  Doc,
  Entry,
  mergeTier,
  clampStop,
  STOP_LABELS,
  stopHint,
  mergeResults,
} from "./searchDepth"

const NUM_RESULTS = 8
const store = new Map<string, Doc>()
let index: any = null
let fuzzy: MiniSearch | null = null
let loadedStop = -1
let loading = false

function basePath(): string {
  return document.body.dataset.basepath ?? ""
}
function isMobile(): boolean {
  return matchMedia("(max-width: 800px)").matches || matchMedia("(pointer: coarse)").matches
}
function savedStop(): number {
  return clampStop(parseInt(localStorage.getItem("search-depth") ?? "0", 10), isMobile())
}

function newIndex(): any {
  return new (FlexSearch as any).Document({
    document: { id: "id", index: ["title", "content", "tags"], store: false },
    tokenize: "forward",
  })
}

async function fetchJson(file: string): Promise<any> {
  try {
    const r = await fetch(`${basePath()}/static/${file}`)
    return r.ok ? await r.json() : null
  } catch {
    return null
  }
}

// Merge one shard file (either {entries} or, for t2, a {buckets:[…]} manifest whose
// bucket files are fetched + merged) into the store + FlexSearch.
async function mergeFile(file: string): Promise<void> {
  const j = await fetchJson(file)
  if (!j) return
  if (Array.isArray(j.buckets)) {
    for (const b of j.buckets) await mergeFile(b)
    return
  }
  const changed = mergeTier(store, (j.entries ?? []) as Entry[])
  for (const id of changed) {
    const d = store.get(id)!
    index.remove(id)
    index.add({ id: d.id, title: d.title, content: d.content, tags: (d.tags || []).join(" ") })
  }
}

// The delta file(s) each stop adds on top of the shallower tier.
function stopFile(s: number): string {
  return ["search-t0.json", "search-t1.json", "search-t2.json", "search-t3.json"][s]
}

// Load every tier up to `target`, merging into the store + FlexSearch. At Max, also
// build the MiniSearch fuzzy index off the accumulated store.
async function loadUpTo(target: number): Promise<void> {
  if (loading) return
  loading = true
  try {
    if (!index) index = newIndex()
    for (let s = loadedStop + 1; s <= target; s++) {
      await mergeFile(stopFile(s))
      loadedStop = s
    }
    if (target >= 3) buildFuzzy()
    document.dispatchEvent(new CustomEvent("searchdepth-loaded", { detail: { stop: loadedStop } }))
  } finally {
    loading = false
  }
}

function buildFuzzy(): void {
  fuzzy = new MiniSearch({
    fields: ["title", "content", "tags"],
    storeFields: [],
    searchOptions: { fuzzy: 0.2, prefix: true, boost: { title: 3, tags: 2 } },
  })
  fuzzy.addAll(
    [...store.values()].map((d) => ({
      id: d.id,
      title: d.title,
      content: d.content,
      tags: (d.tags || []).join(" "),
    })),
  )
}

function search(q: string): Doc[] {
  const query = q.trim()
  if (!index || !query) return []
  const flexIds: string[] = []
  const seen = new Set<string>()
  for (const group of index.search(query, { limit: NUM_RESULTS, enrich: false }) as any[]) {
    for (const id of group.result ?? group) {
      if (!seen.has(id)) {
        seen.add(id)
        flexIds.push(id)
      }
    }
  }
  let ids = flexIds
  // Fuzzy top-up: only when FlexSearch under-fills a page and the Max tier is loaded.
  if (flexIds.length < NUM_RESULTS && fuzzy) {
    const fuzzyIds = fuzzy.search(query).map((r: any) => r.id as string)
    ids = mergeResults(flexIds, fuzzyIds, NUM_RESULTS)
  }
  return ids
    .slice(0, NUM_RESULTS)
    .map((id) => store.get(id))
    .filter(Boolean) as Doc[]
}

function hitHref(d: Doc): string {
  return `${basePath()}/${d.slug}`.replace(/([^:])\/\/+/g, "$1/")
}
function esc(s: string): string {
  return s.replace(
    /[&<>"]/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]!,
  )
}

function ensureUI(): void {
  if (document.querySelector(".sd-button")) return

  const btn = document.createElement("button")
  btn.className = "sd-button"
  btn.type = "button"
  btn.setAttribute("aria-label", "Cerca")
  btn.innerHTML = `<span class="sd-button-icon" aria-hidden="true">🔍</span><span class="sd-button-label">Cerca</span>`
  btn.dataset.persist = "" // survive SPA micromorph (mirrors sidebarToggle)
  const slot = document.querySelector(".flex-component") ?? document.body
  slot.appendChild(btn)

  const modal = document.createElement("div")
  modal.className = "sd-modal"
  modal.dataset.persist = ""
  modal.innerHTML = `
    <div class="sd-inner" role="dialog" aria-modal="true" aria-label="Ricerca">
      <input class="sd-input" type="text" placeholder="Cerca nel corpus…" aria-label="Cerca" autocomplete="off" />
      <div class="sd-slider-wrap"></div>
      <ul class="sd-results" role="listbox"></ul>
    </div>`
  document.body.appendChild(modal)

  const input = modal.querySelector(".sd-input") as HTMLInputElement
  const results = modal.querySelector(".sd-results") as HTMLUListElement
  const wrap = modal.querySelector(".sd-slider-wrap") as HTMLElement

  // --- depth slider ---
  const maxStop = isMobile() ? 1 : 3
  const cur = savedStop()
  wrap.innerHTML = `
    <input class="sd-slider" type="range" min="0" max="${maxStop}" step="1" value="${cur}" aria-label="Profondità ricerca" />
    <span class="sd-slider-label"></span>
    <span class="sd-spin" hidden aria-hidden="true">⏳</span>`
  const slider = wrap.querySelector(".sd-slider") as HTMLInputElement
  const label = wrap.querySelector(".sd-slider-label") as HTMLElement
  const spin = wrap.querySelector(".sd-spin") as HTMLElement
  const paint = () => {
    label.textContent = `${STOP_LABELS[+slider.value]} — ${stopHint(+slider.value)}`
  }
  paint()

  const render = () => {
    const hits = search(input.value)
    results.innerHTML = hits
      .map(
        (d) =>
          `<li role="option"><a class="sd-hit" href="${esc(hitHref(d))}"><span class="sd-hit-title">${esc(
            d.title || d.slug,
          )}</span></a></li>`,
      )
      .join("")
  }

  slider.addEventListener("change", async () => {
    const want = clampStop(+slider.value, isMobile())
    slider.value = String(want)
    localStorage.setItem("search-depth", String(want))
    paint()
    if (want > loadedStop) {
      spin.hidden = false
      await loadUpTo(want)
      spin.hidden = true
    }
    render()
  })

  let t: number | undefined
  input.addEventListener("input", () => {
    clearTimeout(t)
    t = window.setTimeout(render, 90)
  })

  const open = async () => {
    modal.classList.add("active")
    document.documentElement.style.overflow = "hidden"
    const want = savedStop()
    if (loadedStop < want) {
      spin.hidden = false
      await loadUpTo(want)
      spin.hidden = true
    }
    input.focus()
  }
  const close = () => {
    modal.classList.remove("active")
    document.documentElement.style.overflow = ""
  }

  btn.addEventListener("click", open)
  modal.addEventListener("click", (e) => {
    if (e.target === modal) close()
  })
  results.addEventListener("click", close) // navigate then dismiss
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") close()
    if (
      e.key === "/" &&
      !modal.classList.contains("active") &&
      (document.activeElement === document.body || document.activeElement === null)
    ) {
      e.preventDefault()
      open()
    }
  })
}

function init(): void {
  ensureUI()
  // Belt-and-suspenders: if SPA micromorph dropped the persisted button, re-append.
  if (!document.querySelector(".sd-button")) ensureUI()
}

document.addEventListener("nav", init)
init()
