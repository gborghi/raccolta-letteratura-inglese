// Reusable radial "option wheel": renders <div class="radial-wheel" data-wheel="...">
// placeholders into a circle of clickable emblem tiles, with a center medallion and
// upright labels placed on the INNER side of each emblem in a top layer (so a label
// is always in the foreground and never hidden when the emblem is hovered/scaled).
// A grid fallback kicks in on narrow screens. Data: quartz/static/wheel.json.

interface Spoke {
  label: string
  sub?: string
  img: string
  href: string
  cercaAuthor?: string
}
type WheelData = Record<string, Spoke[]>

let cache: WheelData | null = null
async function load(prefix: string): Promise<WheelData> {
  if (cache) return cache
  cache = (await (await fetch(prefix + "static/wheel.json")).json()) as WheelData
  return cache
}

function esc(s: unknown): string {
  return String(s).replace(/[&<>"]/g, (c) =>
    c === "&" ? "&amp;" : c === "<" ? "&lt;" : c === ">" ? "&gt;" : "&quot;",
  )
}

// point an author emblem straight at that author's landing page (content/authors/<slug>).
// (wheel.json still ships href:"cerca" + cercaAuthor for back-compat; we rewrite here.)
function wireCerca(a: HTMLAnchorElement, s: Spoke) {
  if (!s.cercaAuthor) return
  a.dataset.author = s.cercaAuthor
  const cur = a.getAttribute("href") || ""
  // Slugify the author name for the landing-page URL: multi-word authors (e.g.
  // "Conan Doyle") emit at /authors/conan-doyle, so spaces must become hyphens —
  // otherwise the link is /authors/conan%20doyle which 404s.
  const slug = s.cercaAuthor.toLowerCase().replace(/\s+/g, "-")
  a.setAttribute("href", cur.replace(/cerca\/?$/, "authors/" + slug))
}

// emblem-only clickable tile (circle layout)
function buildTile(s: Spoke, prefix: string, imgPrefix: string): HTMLAnchorElement {
  const a = document.createElement("a")
  a.className = "rw-spoke rw-tilespoke"
  a.href = prefix + s.href
  a.setAttribute("aria-label", s.label)
  wireCerca(a, s)
  a.innerHTML = `<span class="rw-tile"><img src="${imgPrefix}static/wheel/${esc(
    s.img,
  )}.webp" alt="${esc(s.label)} emblem" loading="lazy" width="320" height="320"></span>`
  return a
}

// standalone label chip (circle layout, lives in the top label layer)
function buildLabelAnchor(s: Spoke, prefix: string): HTMLAnchorElement {
  const a = document.createElement("a")
  a.className = "rw-label-anchor"
  a.href = prefix + s.href
  wireCerca(a, s)
  a.innerHTML =
    `<span class="rw-label">${esc(s.label)}</span>` +
    (s.sub ? `<span class="rw-sub">${esc(s.sub)}</span>` : "")
  return a
}

// combined tile+label stack, used only by the narrow-screen grid fallback
function buildCombined(s: Spoke, prefix: string, imgPrefix: string): HTMLAnchorElement {
  const a = document.createElement("a")
  a.className = "rw-spoke"
  a.href = prefix + s.href
  wireCerca(a, s)
  a.innerHTML =
    `<span class="rw-tile"><img src="${imgPrefix}static/wheel/${esc(
      s.img,
    )}.webp" alt="${esc(s.label)} emblem" loading="lazy" width="320" height="320"></span>` +
    `<span class="rw-label">${esc(s.label)}` +
    (s.sub ? `<span class="rw-sub">${esc(s.sub)}</span>` : "") +
    `</span>`
  return a
}

function layoutCircle(tiles: HTMLElement[], labels: HTMLElement[]) {
  const n = tiles.length
  const tileR = 37 // emblem ring radius (% of stage)
  // For crowded wheels (≥10 spokes) alternate between two inner radii so adjacent
  // labels sit at different distances and don't overlap each other.
  const crowded = n >= 10
  const labelR_inner = crowded ? 19 : 22 // closer ring (even spokes)
  const labelR_outer = crowded ? 25 : 22 // farther ring (odd spokes, still inner side)
  for (let i = 0; i < n; i++) {
    const angle = (i / n) * 2 * Math.PI - Math.PI / 2 // start at 12 o'clock
    const cos = Math.cos(angle)
    const sin = Math.sin(angle)
    const t = tiles[i]
    t.style.left = 50 + tileR * cos + "%"
    t.style.top = 50 + tileR * sin + "%"
    // Consistent clockwise shingle: each tile overlaps its counter-clockwise
    // neighbour and is overlapped by its clockwise one. (i+1)%n keeps tile 0
    // (12 o'clock apex, e.g. Austen) above its left neighbour but below tile 1
    // (e.g. Belloc), moving the unavoidable circular seam off the apex.
    t.style.zIndex = String((i + 1) % n)
    const labelR = i % 2 === 0 ? labelR_inner : labelR_outer
    const l = labels[i]
    l.style.left = 50 + labelR * cos + "%"
    l.style.top = 50 + labelR * sin + "%"
  }
}

function renderWheel(root: HTMLElement, spokes: Spoke[], prefix: string, imgPrefix: string) {
  const title = root.dataset.center || ""
  const sub = root.dataset.centerSub || ""

  const stage = document.createElement("div")
  stage.className = "rw-stage"
  const ring = document.createElement("div")
  ring.className = "rw-ring"
  stage.appendChild(ring)

  const center = document.createElement("div")
  center.className = "rw-center"
  center.innerHTML =
    `<span class="rw-center-title">${esc(title)}</span>` +
    (sub ? `<span class="rw-center-sub">${esc(sub)}</span>` : "")

  const tiles: HTMLElement[] = []
  const labels: HTMLElement[] = []
  const fallback = document.createElement("div")
  fallback.className = "rw-fallback"

  for (const s of spokes) {
    tiles.push(buildTile(s, prefix, imgPrefix))
    labels.push(buildLabelAnchor(s, prefix))
    fallback.appendChild(buildCombined(s, prefix, imgPrefix))
  }
  // Mark crowded wheels so CSS can reduce label font size
  if (spokes.length >= 10) stage.dataset.crowded = "1"
  // paint order: ring -> tiles -> center medallion -> LABELS (top layer)
  for (const t of tiles) stage.appendChild(t)
  stage.appendChild(center)
  for (const l of labels) stage.appendChild(l)
  layoutCircle(tiles, labels)

  root.replaceChildren(stage, fallback)

  const apply = () => {
    const narrow = root.clientWidth < 460
    root.classList.toggle("rw-grid", narrow)
  }
  apply()
  if ("ResizeObserver" in window) {
    const ro = new ResizeObserver(apply)
    ro.observe(root)
  } else {
    window.addEventListener("resize", apply)
  }
}

async function init() {
  const roots = Array.from(
    document.querySelectorAll<HTMLElement>("div.radial-wheel"),
  ).filter((el) => !el.dataset.rendered)
  if (!roots.length) return

  const slug = document.body.dataset.slug || ""
  const prefix = "../".repeat((slug.match(/\//g) || []).length)
  let data: WheelData
  try {
    data = await load(prefix)
  } catch {
    return
  }

  for (const root of roots) {
    root.dataset.rendered = "1"
    const key = root.dataset.wheel || ""
    const spokes = data[key]
    if (!spokes) continue
    renderWheel(root, spokes, prefix, prefix)
  }
}

document.addEventListener("nav", () => {
  init()
})
init()

export {}
