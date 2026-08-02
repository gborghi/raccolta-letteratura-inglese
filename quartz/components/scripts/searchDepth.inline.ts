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
import { Doc, Entry, mergeTier, clampStop, STOP_LABELS, stopHint } from "./searchDepth"

const NUM_RESULTS = 8
// Pull a WIDE candidate pool from FlexSearch, then re-rank it ourselves (see search()).
// FlexSearch's built-in order for a common term returns whatever it resolves first — with
// ~19k atoms and a term like "disgrace" in ~190 of them, the late-indexed entries (all of
// Shakespeare sorts last) never made the old 8-result cut, so e.g. Sonnet 29 was invisible.
// A big pool + relevance re-rank fixes recall without depending on insertion order.
const CANDIDATE_LIMIT = 250
// How many FlexSearch (re)index operations to run before yielding the main thread back to
// the browser. The Deep/Max tiers add ~19k per-atom docs; doing them all in one synchronous
// loop froze the tab (the whole point of this file's async plumbing), so we cooperatively
// yield every REINDEX_CHUNK docs to keep the UI — spinner, typing, closing — responsive.
const REINDEX_CHUNK = 400
const store = new Map<string, Doc>()
let index: any = null
let fuzzy: MiniSearch | null = null
let loadedStop = -1
let loading = false

// Yield to the event loop so the browser can paint / handle input between heavy batches.
function yieldToUI(): Promise<void> {
  return new Promise((r) => setTimeout(r, 0))
}

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
  let i = 0
  for (const id of changed) {
    const d = store.get(id)!
    index.remove(id)
    index.add({ id: d.id, title: d.title, content: d.content, tags: (d.tags || []).join(" ") })
    // Deep/Max tiers reindex ~19k docs; yield periodically so the tab never freezes.
    if (++i % REINDEX_CHUNK === 0) await yieldToUI()
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
    if (target >= 3) await buildFuzzy()
    document.dispatchEvent(new CustomEvent("searchdepth-loaded", { detail: { stop: loadedStop } }))
  } finally {
    loading = false
  }
}

async function buildFuzzy(): Promise<void> {
  fuzzy = new MiniSearch({
    fields: ["title", "content", "tags"],
    storeFields: [],
    searchOptions: { fuzzy: 0.2, prefix: true, boost: { title: 3, tags: 2 } },
  })
  // addAllAsync chunks the ~19k-doc build and yields between chunks, so indexing the Max
  // tier no longer blocks the main thread (addAll did, freezing the tab on every open).
  await fuzzy.addAllAsync(
    [...store.values()].map((d) => ({
      id: d.id,
      title: d.title,
      content: d.content,
      tags: (d.tags || []).join(" "),
    })),
  )
}

// Count non-overlapping occurrences of `needle` in `hay` (both already lower-cased).
function countOcc(hay: string, needle: string): number {
  if (!needle) return 0
  let n = 0
  let i = hay.indexOf(needle)
  while (i !== -1) {
    n++
    i = hay.indexOf(needle, i + needle.length)
  }
  return n
}

// Relevance score for a candidate against the query tokens. A title hit dominates; in the
// body, a term that RECURS scores higher — the stored content is a prose snippet PLUS the
// doc's top tf-idf terms, so a word central to a short entry (a sonnet whose theme *is*
// "disgrace") appears in both halves and outscores an incidental mention in a long chapter.
// Returns -1 for a doc that matches no token so it can be dropped (keeps OR-recall, but
// only over things that actually matched).
function scoreDoc(d: Doc, tokens: string[]): number {
  const title = (d.title || "").toLowerCase()
  const content = (d.content || "").toLowerCase()
  let score = 0
  let matched = false
  for (const tk of tokens) {
    const tHits = countOcc(title, tk)
    const cHits = countOcc(content, tk)
    if (tHits) {
      score += 100 + tHits * 10 // title match dominates
      matched = true
    }
    if (cHits) {
      score += cHits * 10 // body prominence (snippet + tf-idf terms => recurrence)
      matched = true
    }
  }
  return matched ? score : -1
}

// Collapse the multi-part splits of ONE section ("chapter_04…--part_01..07") to a single
// result, so a query doesn't waste the whole page on near-identical fragments of the same
// chapter. Distinct chapters and distinct sonnets (no "--part" suffix) stay separate.
function sectionKey(slug: string): string {
  return slug.replace(/--part_\d+$/, "")
}

function search(q: string): Doc[] {
  const query = q.trim()
  if (!index || !query) return []
  const tokens = query.toLowerCase().split(/\s+/).filter(Boolean)
  const seen = new Set<string>()
  const pool: string[] = []
  const push = (id: string) => {
    if (!seen.has(id)) {
      seen.add(id)
      pool.push(id)
    }
  }
  // Wide candidate pool from FlexSearch (prefix/token match across title+content+tags)…
  for (const group of index.search(query, { limit: CANDIDATE_LIMIT, enrich: false }) as any[]) {
    for (const id of group.result ?? group) push(id)
  }
  // …plus MiniSearch's typo-tolerant hits once the Max tier is loaded (its own ranking is
  // discarded here; both feed the same re-rank below so exact and fuzzy are scored alike).
  if (fuzzy) {
    for (const r of (fuzzy.search(query, { prefix: true }) as any[]).slice(0, CANDIDATE_LIMIT)) {
      push(r.id as string)
    }
  }
  // Re-rank the whole pool by relevance. This is what surfaces a prominent-but-late-indexed
  // hit (a Shakespeare sonnet for "disgrace") that FlexSearch's raw top-N would have dropped.
  const ranked = pool
    .map((id) => store.get(id))
    .filter(Boolean)
    .map((d) => ({ d: d as Doc, s: scoreDoc(d as Doc, tokens) }))
    .filter((x) => x.s >= 0)
    .sort((a, b) => b.s - a.s)
  // Take the page, collapsing multi-part splits of the same section so results stay diverse.
  const out: Doc[] = []
  const usedSection = new Set<string>()
  for (const { d } of ranked) {
    const k = sectionKey(d.slug)
    if (usedSection.has(k)) continue
    usedSection.add(k)
    out.push(d)
    if (out.length >= NUM_RESULTS) break
  }
  return out
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
  btn.setAttribute("aria-label", "Search")
  btn.innerHTML = `<span class="sd-button-icon" aria-hidden="true">🔍</span><span class="sd-button-label">Search</span>`
  btn.dataset.persist = "" // survive SPA micromorph (mirrors sidebarToggle)
  const slot = document.querySelector(".flex-component") ?? document.body
  slot.appendChild(btn)

  const modal = document.createElement("div")
  modal.className = "sd-modal"
  modal.dataset.persist = ""
  modal.innerHTML = `
    <div class="sd-inner" role="dialog" aria-modal="true" aria-label="Search">
      <input class="sd-input" type="text" placeholder="Search the corpus…" aria-label="Search" autocomplete="off" />
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
    <input class="sd-slider" type="range" min="0" max="${maxStop}" step="1" value="${cur}" aria-label="Search depth" />
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
