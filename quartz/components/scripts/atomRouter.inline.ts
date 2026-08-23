// Reading-page SPA router.
//
// When preprocess runs with SPA=1 it emits ONE page per work: every atom's body is
// concatenated behind an inline `<span class="atom-split" data-atom data-title
// data-chapter data-kind>` marker (and each atom's optional Italian body behind the
// existing `<span class="qlang-split" data-lang="it">` marker). Quartz renders the
// whole page normally — wikilinks, prose, popovers, translations — so the full text
// is in the HTML (SEO-safe). This script then:
//   1. partitions the rendered article DOM at the markers into per-atom node groups
//      (same DOM-slicing trick the qlang toggle uses), splitting each into EN/IT;
//   2. detaches them and shows ONE atom at a time inside a reading pane, so the live
//      DOM stays small even for a 400-atom novel (render-on-demand);
//   3. deep-links each atom at `#atomId` (history + back/forward + arrow keys);
//   4. builds a chapter/part table of contents and prev/next;
//   5. offers a single work-level EN/IT toggle that governs every atom.
//
// Mounted only on pages that carry a `<div class="atom-reader">` placeholder.

interface Atom {
  id: string
  title: string
  chapter: string
  kind: string
  tags: string[]
  en: Node[]
  it: Node[]
}

const LANG_KEY = "eng-reader-lang"

// The set of work-shard keys that actually have chapter-related data, loaded once from
// static/chapter_related/_index.json (emitted by preprocess). Gating shard fetches on
// this avoids a 404 on every reading page that has no shard (the large majority).
let relatedIndexPromise: Promise<Set<string>> | null = null
function relatedIndex(bp: string): Promise<Set<string>> {
  if (!relatedIndexPromise) {
    relatedIndexPromise = fetch(`${bp}/static/chapter_related/_index.json`)
      .then((r) => (r.ok ? (r.json() as Promise<string[]>) : []))
      .then((a) => new Set(a))
      .catch(() => new Set<string>())
  }
  return relatedIndexPromise
}

// A marker (`.atom-split` / `.qlang-split`) is emitted as an inline <span>; the
// markdown renderer wraps a lone inline element in a <p>, so the marker is usually
// NOT a direct child of the article — it sits inside a <p> that contains nothing
// else. Detect both shapes: the bare marker element, or a wrapper whose only element
// child is a marker and which carries no text of its own.
function markerOf(el: HTMLElement): HTMLElement | null {
  if (el.classList && (el.classList.contains("atom-split") || el.classList.contains("qlang-split")))
    return el
  if (el.childElementCount === 1 && !(el.textContent || "").trim()) {
    const c = el.firstElementChild as HTMLElement | null
    if (
      c &&
      c.classList &&
      (c.classList.contains("atom-split") || c.classList.contains("qlang-split"))
    )
      return c
  }
  return null
}

function partition(
  container: HTMLElement,
  mount: HTMLElement,
): { atoms: Atom[]; markerNodes: Node[] } {
  const atoms: Atom[] = []
  const markerNodes: Node[] = [] // the top-level nodes (bare marker or its wrapping <p>) to detach
  let cur: Atom | null = null
  let lang: "en" | "it" = "en"
  for (const node of Array.from(container.childNodes)) {
    if (node === mount) continue
    if (node.nodeType === Node.ELEMENT_NODE) {
      const marker = markerOf(node as HTMLElement)
      if (marker) {
        markerNodes.push(node)
        if (marker.classList.contains("atom-split")) {
          cur = {
            id: marker.dataset.atom || `atom-${atoms.length}`,
            title: marker.dataset.title || "",
            chapter: marker.dataset.chapter || "",
            kind: marker.dataset.kind || "",
            tags: (marker.dataset.tags || "")
              .split(",")
              .map((s) => s.trim())
              .filter(Boolean),
            en: [],
            it: [],
          }
          atoms.push(cur)
          lang = "en"
        } else {
          lang = "it"
        }
        continue
      }
    }
    if (cur) (lang === "en" ? cur.en : cur.it).push(node)
  }
  return { atoms, markerNodes }
}

function el<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  cls?: string,
  html?: string,
): HTMLElementTagNameMap[K] {
  const e = document.createElement(tag)
  if (cls) e.className = cls
  if (html != null) e.innerHTML = html
  return e
}

// The emitted title is the full "Work — Chapter (part N)"; crumb/TOC only want the
// chapter/part portion (the work title is already in the page header + breadcrumb).
function chapterOf(t: string): string {
  return t.replace(/^.*—\s*/, "")
}
// TOC leaf under a chapter group: strip the repeated chapter name so a part reads
// just "Parte 3" instead of "II The Maniac (part 3)".
// KG aggregator axis -> /cerca facet key (must match the FACET.key values in
// cerca.inline.ts's FACETS array — verified: topoi/archetypes/motifs/concepts/
// forms/histrefs/settings/characters/cluster).
const AXIS_TO_FACET: Record<string, string> = {
  topos: "topoi",
  archetype: "archetypes",
  motif: "motifs",
  concept: "concepts",
  form: "forms",
  histref: "histrefs",
  setting: "settings",
  character: "characters",
  cluster: "cluster",
}

// Chip label for a leaf tag: name the KG aggregator axis explicitly, e.g.
// "motif/autumn" -> "#motif:autumn", "concept/faith_and_doubt" -> "#concept:faith and doubt".
function tagLabel(t: string): string {
  const slash = t.indexOf("/")
  const axis = slash === -1 ? t : t.slice(0, slash)
  const slug = slash === -1 ? "" : t.slice(slash + 1)
  return "#" + axis + ":" + slug.replace(/_/g, " ")
}

// A leaf tag chip that deep-links to /cerca with that facet value preselected —
// same sessionStorage handoff as the home author cards (see wireAuthorCards in
// opereTable.inline.ts). Falls back to a plain (non-clickable) span if the axis
// has no matching /cerca facet.
function tagChip(t: string, bp: string): HTMLElement {
  const slash = t.indexOf("/")
  const axis = slash === -1 ? t : t.slice(0, slash)
  const slug = slash === -1 ? "" : t.slice(slash + 1)
  const facetKey = AXIS_TO_FACET[axis]
  if (!facetKey || !slug) return el("span", "ar-tag", tagLabel(t))
  const a = el("a", "ar-tag", tagLabel(t))
  a.href = `${bp}/cerca`
  a.addEventListener("click", () => {
    try {
      sessionStorage.setItem("cercaPreselect", `${facetKey}::${slug}`)
    } catch {}
  })
  return a
}
function leafLabel(a: Atom): string {
  let s = chapterOf(a.title)
  if (a.chapter && s.startsWith(a.chapter)) {
    s = s
      .slice(a.chapter.length)
      .replace(/^[\s—–-]+/, "")
      .trim()
    if (!s || /^[\s.,;:!?—–-]*$/.test(s)) s = chapterOf(a.title) || a.title
  }
  return s.replace(/^\((?:part|parte)\s*(\d+)\)$/i, "Parte $1")
}

/** Part-title / CONTENTS-only atoms (Chesterton CharlesDickens Chapter_08 etc.). */
function isStubAtom(a: Atom): boolean {
  const label = (chapterOf(a.title) || a.title || "").trim()
  if (/^Part\s+\d+$/i.test(label)) return true
  const words = a.en.map((n) => n.textContent || "").join(" ")
  const t = words.replace(/\s+/g, " ").trim()
  if (t.length < 280 && /PART\s+(ONE|TWO)|^\s*CONTENTS\b/i.test(t)) return true
  return false
}

function literaryChapter(a: Atom): number | null {
  const m = (a.title || "").match(/Chapter\s+(\d+)\b/i)
  return m ? Number(m[1]) : null
}

function build(reader: HTMLElement) {
  if (reader.dataset.mounted) return
  reader.dataset.mounted = "1"
  const container = reader.parentElement
  if (!container) return

  const { atoms, markerNodes } = partition(container, reader)
  if (!atoms.length) return
  const anyIt = atoms.some((a) => a.it.length > 0)

  // detach every atom's nodes + the marker nodes (bare span or its wrapping <p>) so
  // no empty marker boxes linger in the flow
  for (const m of markerNodes) m.parentNode?.removeChild(m)
  for (const a of atoms) for (const n of [...a.en, ...a.it]) n.parentNode?.removeChild(n)

  const order = atoms.filter((a) => !isStubAtom(a)).map((a) => a.id)
  const byId = new Map(atoms.map((a) => [a.id, a]))
  function resolveHash(raw: string): string {
    const m = raw.match(/^chapter_0*(\d+)$/)
    if (m) {
      const n = Number(m[1])
      const hit = order.find((id) => {
        const a = byId.get(id)
        return a ? literaryChapter(a) === n : false
      })
      if (hit) return hit
    }
    if (!byId.has(raw) || isStubAtom(byId.get(raw)!)) {
      const leaf = order.find((o) => o.startsWith(`${raw}--`))
      if (leaf) return leaf
      if (order.includes(raw)) return raw
      return order[0]
    }
    return raw
  }
  let lang: "en" | "it" = anyIt && localStorage.getItem(LANG_KEY) === "it" ? "it" : "en"

  // per-atom "Capitoli correlati" (#17): keyed by workSlug#atomId. Loaded async; a
  // re-render fires once it arrives. The router owns this (not relatedWorks.inline.ts)
  // because the reading pane is swapped on every atom change.
  const workSlug = reader.dataset.work || ""
  const BP = (document.body && (document.body as HTMLElement).dataset.basepath) || ""
  let relatedData: Record<string, Array<Record<string, unknown>>> | null = null
  // Per-work shard (few KB) instead of the whole ~7MB index. Only ~231 of the 2000+
  // reading pages have chapter-related data, so gate the shard fetch on a tiny manifest
  // (relatedIndex) — otherwise every other reading page logs a 404 for a missing shard.
  const shardKey = workSlug.replace(/\//g, "__")
  relatedIndex(BP).then((idx) => {
    if (!idx.has(shardKey)) return // no shard for this work → skip the fetch (no 404)
    fetch(`${BP}/static/chapter_related/${shardKey}.json`)
      .then((r) => (r.ok ? r.json() : {}))
      .then((d) => {
        relatedData = d
        render(shownId)
      })
      .catch(() => {})
  })

  // ---- reader chrome ----
  const bar = el("div", "ar-bar")
  // The global Explorer/search left-sidebar toggle is owned site-wide by
  // sidebarToggle.inline.ts (fixed ☰/✕). The reader only supplies its own chapter-TOC
  // toggle below.
  const tocBtn = el("button", "ar-tocbtn", "&#9776;")
  tocBtn.setAttribute("aria-label", "Indice")
  const crumb = el("div", "ar-crumb")
  const spacer = el("div", "ar-spacer")
  const langWrap = el("div", "ar-lang")
  const enBtn = el("button", "", "EN")
  const itBtn = el("button", "", "IT")
  enBtn.dataset.l = "en"
  itBtn.dataset.l = "it"
  langWrap.append(enBtn, itBtn)
  const pager = el("div", "ar-pager")
  const prevBtn = el("button", "ar-prev", "&#8249;")
  const nextBtn = el("button", "ar-next", "&#8250;")
  prevBtn.setAttribute("aria-label", "Precedente")
  nextBtn.setAttribute("aria-label", "Successivo")
  pager.append(prevBtn, nextBtn)
  bar.append(tocBtn, crumb, spacer)
  if (anyIt) bar.append(langWrap)
  bar.append(pager)

  const shell = el("div", "ar-shell")
  const toc = el("nav", "ar-toc")
  toc.setAttribute("aria-label", "Indice")
  const pane = el("article", "ar-pane")
  shell.append(toc, pane)
  const relatedEl = el("aside", "ar-related")
  const tagsEl = el("div", "ar-tags")

  reader.replaceChildren(bar, tagsEl, shell, relatedEl)

  // Poem collections: hide the chapter TOC sidebar — standalone poems don't form a
  // sequential work, so the flat list adds noise, not navigation value.
  const isPoems = reader.dataset.collection === "poems"
  if (isPoems) {
    shell.classList.add("no-toc")
    tocBtn.style.display = "none"
  }

  // ---- table of contents (grouped by chapter) ----
  const tocList = el("ul", "ar-toc-list")
  let curChap: string | null = null
  let curUl: HTMLUListElement | null = null
  for (const a of atoms) {
    if (isStubAtom(a)) continue
    const label = a.kind === "intro" ? a.title || "Inizio" : a.title
    if (a.kind === "intro" || !a.chapter) {
      const li = el("li", "ar-toc-top")
      const link = el("a", "ar-toc-link", label)
      link.href = `#${a.id}`
      link.dataset.id = a.id
      li.append(link)
      tocList.append(li)
      curChap = null
      curUl = null
      continue
    }
    if (a.chapter !== curChap) {
      curChap = a.chapter
      const li = el("li", "ar-toc-chap")
      li.append(el("span", "ar-toc-chaplabel", a.chapter))
      curUl = el("ul")
      li.append(curUl)
      tocList.append(li)
    }
    const li = el("li")
    const link = el("a", "ar-toc-link", leafLabel(a) || a.id)
    link.href = `#${a.id}`
    link.dataset.id = a.id
    li.append(link)
    curUl?.append(li)
  }
  toc.append(tocList)

  // ---- rendering ----
  let shownId = order[0] // the resolved leaf currently displayed (drives prev/next)
  function idx(id: string) {
    return order.indexOf(id)
  }
  function applyLangButtons() {
    enBtn.classList.toggle("active", lang === "en")
    itBtn.classList.toggle("active", lang === "it")
  }
  function render(id: string) {
    const a = byId.get(id) || atoms[0]
    shownId = a.id
    let nodes = lang === "it" && a.it.length ? a.it : a.en
    pane.replaceChildren(...nodes.map((n) => n))
    if (lang === "it" && !a.it.length && anyIt) {
      pane.append(el("p", "ar-notr", "— traduzione non disponibile per questa sezione —"))
    }
    // crumb + counter: chapter in bold, then the leaf only when it adds info
    const pos = idx(a.id) + 1
    const leaf = a.kind === "intro" ? a.title || "Inizio" : leafLabel(a)
    const showLeaf = !a.chapter || leaf !== a.chapter
    crumb.innerHTML =
      (a.chapter ? `<b>${a.chapter}</b>` : "") +
      (a.chapter && showLeaf ? " &middot; " : "") +
      (showLeaf ? leaf : "") +
      ` <span class="ar-count">${pos} / ${order.length}</span>`
    // leaf tag chips: rebuilt fresh every render() call (same pattern as relatedEl
    // below) so they update per atom and survive micromorph body-diffing on nav.
    tagsEl.replaceChildren()
    if (a.tags.length) {
      for (const t of a.tags) {
        tagsEl.append(tagChip(t, BP))
      }
    }
    // toc active
    toc
      .querySelectorAll(".ar-toc-link")
      .forEach((l) => l.classList.toggle("active", (l as HTMLElement).dataset.id === a.id))
    const active = toc.querySelector(".ar-toc-link.active") as HTMLElement | null
    active?.scrollIntoView({ block: "nearest" })
    // related chapters for this atom
    relatedEl.replaceChildren()
    relatedEl.className = "ar-related"
    // #17 tags are chapter-level; a part atom (chapter_01--part_01) inherits its
    // chapter's related set, so fall back to the chapter id.
    const rel =
      relatedData &&
      (relatedData[`${workSlug}#${a.id}`] || relatedData[`${workSlug}#${a.id.split("--")[0]}`])
    if (rel && rel.length) {
      relatedEl.className = "ar-related related-works"
      relatedEl.append(el("h2", undefined, "Related chapters"))
      const ul = document.createElement("ul")
      for (const it of rel) {
        const li = document.createElement("li")
        li.className = "rw-chapter"
        const parts = String(it.href).split("#")
        const link = document.createElement("a")
        link.href = parts[0] === workSlug ? `#${parts[1]}` : `${BP}/${it.href}`
        link.textContent = String(it.title || "")
        li.append(link)
        if (it.work) {
          const w = document.createElement("span")
          w.className = "rw-author"
          w.textContent = ` — ${it.work}`
          li.append(w)
        }
        if (it.plot) {
          const p = document.createElement("div")
          p.className = "rw-plot"
          p.textContent = String(it.plot)
          li.append(p)
        }
        ul.append(li)
      }
      relatedEl.append(ul)
    }
    const i = idx(a.id)
    prevBtn.disabled = i <= 0
    nextBtn.disabled = i >= order.length - 1
    pane.scrollTo?.(0, 0)
    window.scrollTo(0, 0)
  }
  function go(id: string, push: boolean) {
    id = resolveHash(id)
    render(id)
    if (push && location.hash.slice(1) !== id) history.pushState(null, "", `#${id}`)
    shell.classList.remove("toc-open")
  }
  function current(): string {
    // raw hash — go() resolves chapter/aggregate ids to a leaf.
    return decodeURIComponent(location.hash.slice(1)) || order[0]
  }

  enBtn.onclick = () => {
    lang = "en"
    localStorage.setItem(LANG_KEY, "en")
    applyLangButtons()
    render(shownId)
  }
  itBtn.onclick = () => {
    lang = "it"
    localStorage.setItem(LANG_KEY, "it")
    applyLangButtons()
    render(shownId)
  }
  prevBtn.onclick = () => {
    const i = idx(shownId)
    if (i > 0) go(order[i - 1], true)
  }
  nextBtn.onclick = () => {
    const i = idx(shownId)
    if (i < order.length - 1) go(order[i + 1], true)
  }
  tocBtn.onclick = () => shell.classList.toggle("toc-open")
  reader.addEventListener("click", (e) => {
    const a = (e.target as HTMLElement).closest?.('a[href^="#"]') as HTMLAnchorElement | null
    if (!a || !reader.contains(a)) return
    const id = decodeURIComponent(a.getAttribute("href")!.slice(1))
    if (byId.has(id)) {
      e.preventDefault()
      go(id, true)
    }
  })
  window.addEventListener("popstate", () => go(current(), false))
  document.addEventListener("keydown", (e) => {
    if ((e.target as HTMLElement).matches?.("input,textarea")) return
    if (e.key === "ArrowRight") {
      const i = idx(shownId)
      if (i < order.length - 1) go(order[i + 1], true)
    } else if (e.key === "ArrowLeft") {
      const i = idx(shownId)
      if (i > 0) go(order[i - 1], true)
    }
  })

  applyLangButtons()
  go(current(), false)
}

function init() {
  const readers = document.querySelectorAll<HTMLElement>("div.atom-reader")
  // reading pages collapse the global left sidebar (see build()); leaving one must
  // restore normal layout for the next SPA-navigated page. The ☰/✕ chrome that opens
  // and closes that sidebar is owned globally by sidebarToggle.inline.ts.
  document.body.classList.toggle("reading-page", readers.length > 0)
  if (!readers.length) document.body.classList.remove("left-open")
  readers.forEach((r) => build(r))
}

document.addEventListener("nav", init)
init()

export {}
