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
  en: Node[]
  it: Node[]
}

const LANG_KEY = "eng-reader-lang"

function partition(container: HTMLElement, mount: HTMLElement): Atom[] {
  const atoms: Atom[] = []
  let cur: Atom | null = null
  let lang: "en" | "it" = "en"
  for (const node of Array.from(container.childNodes)) {
    if (node === mount) continue
    if (node.nodeType === Node.ELEMENT_NODE) {
      const el = node as HTMLElement
      if (el.classList && el.classList.contains("atom-split")) {
        cur = {
          id: el.dataset.atom || `atom-${atoms.length}`,
          title: el.dataset.title || "",
          chapter: el.dataset.chapter || "",
          kind: el.dataset.kind || "",
          en: [],
          it: [],
        }
        atoms.push(cur)
        lang = "en"
        continue
      }
      if (el.classList && el.classList.contains("qlang-split")) {
        lang = "it"
        continue
      }
    }
    if (cur) (lang === "en" ? cur.en : cur.it).push(node)
  }
  return atoms
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

function build(reader: HTMLElement) {
  if (reader.dataset.mounted) return
  reader.dataset.mounted = "1"
  const container = reader.parentElement
  if (!container) return

  const atoms = partition(container, reader)
  if (!atoms.length) return
  const anyIt = atoms.some((a) => a.it.length > 0)

  // detach every atom's nodes + the marker spans from the flow
  container
    .querySelectorAll(".atom-split, .qlang-split")
    .forEach((m) => m.remove())
  for (const a of atoms) for (const n of [...a.en, ...a.it]) n.parentNode?.removeChild(n)

  const order = atoms.map((a) => a.id)
  const byId = new Map(atoms.map((a) => [a.id, a]))
  let lang: "en" | "it" =
    anyIt && localStorage.getItem(LANG_KEY) === "it" ? "it" : "en"

  // ---- reader chrome ----
  const worktitle = reader.dataset.worktitle || document.title
  const bar = el("div", "ar-bar")
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

  reader.replaceChildren(bar, shell)

  // ---- table of contents (grouped by chapter) ----
  const tocList = el("ul", "ar-toc-list")
  let curChap: string | null = null
  let curUl: HTMLUListElement | null = null
  for (const a of atoms) {
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
    const link = el("a", "ar-toc-link", a.title.replace(/^.*—\s*/, "") || a.id)
    link.href = `#${a.id}`
    link.dataset.id = a.id
    li.append(link)
    curUl?.append(li)
  }
  toc.append(tocList)

  // ---- rendering ----
  function idx(id: string) {
    return order.indexOf(id)
  }
  function applyLangButtons() {
    enBtn.classList.toggle("active", lang === "en")
    itBtn.classList.toggle("active", lang === "it")
  }
  function render(id: string) {
    const a = byId.get(id) || atoms[0]
    let nodes = lang === "it" && a.it.length ? a.it : a.en
    pane.replaceChildren(...nodes.map((n) => n))
    if (lang === "it" && !a.it.length && anyIt) {
      pane.append(el("p", "ar-notr", "— traduzione non disponibile per questa sezione —"))
    }
    // crumb + counter
    const pos = idx(a.id) + 1
    const label = a.kind === "intro" ? a.title || "Inizio" : a.title
    crumb.innerHTML =
      (a.chapter ? `<b>${a.chapter}</b> &middot; ` : "") +
      `${label} <span class="ar-count">${pos} / ${order.length}</span>`
    // toc active
    toc.querySelectorAll(".ar-toc-link").forEach((l) =>
      l.classList.toggle("active", (l as HTMLElement).dataset.id === a.id),
    )
    const active = toc.querySelector(".ar-toc-link.active") as HTMLElement | null
    active?.scrollIntoView({ block: "nearest" })
    const i = idx(a.id)
    prevBtn.disabled = i <= 0
    nextBtn.disabled = i >= order.length - 1
    pane.scrollTo?.(0, 0)
    window.scrollTo(0, 0)
  }
  function go(id: string, push: boolean) {
    if (!byId.has(id)) id = order[0]
    render(id)
    if (push && location.hash.slice(1) !== id) history.pushState(null, "", `#${id}`)
    shell.classList.remove("toc-open")
  }
  function current(): string {
    const h = decodeURIComponent(location.hash.slice(1))
    return byId.has(h) ? h : order[0]
  }

  enBtn.onclick = () => {
    lang = "en"
    localStorage.setItem(LANG_KEY, "en")
    applyLangButtons()
    render(current())
  }
  itBtn.onclick = () => {
    lang = "it"
    localStorage.setItem(LANG_KEY, "it")
    applyLangButtons()
    render(current())
  }
  prevBtn.onclick = () => {
    const i = idx(current())
    if (i > 0) go(order[i - 1], true)
  }
  nextBtn.onclick = () => {
    const i = idx(current())
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
      const i = idx(current())
      if (i < order.length - 1) go(order[i + 1], true)
    } else if (e.key === "ArrowLeft") {
      const i = idx(current())
      if (i > 0) go(order[i - 1], true)
    }
  })

  applyLangButtons()
  go(current(), false)
}

function init() {
  document
    .querySelectorAll<HTMLElement>("div.atom-reader")
    .forEach((r) => build(r))
}

document.addEventListener("nav", init)
init()

export {}
