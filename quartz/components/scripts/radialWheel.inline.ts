// Reusable radial "option wheel": renders <div class="radial-wheel" data-wheel="...">
// placeholders into a circle of clickable emblem tiles, with a center medallion,
// counter-rotated upright labels, hover lift, keyboard focus, and a grid fallback
// on narrow screens. Data comes from quartz/static/wheel.json.

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

function buildSpoke(s: Spoke, prefix: string, imgPrefix: string): HTMLAnchorElement {
  const a = document.createElement("a")
  a.className = "rw-spoke"
  // Author spokes deep-link via the existing sessionStorage -> Cerca handoff.
  a.href = prefix + s.href
  if (s.cercaAuthor) {
    a.dataset.cercaAuthor = s.cercaAuthor
    a.addEventListener("click", () => {
      try {
        sessionStorage.setItem("cercaPreselect", "author::" + s.cercaAuthor)
      } catch {}
    })
  }
  a.innerHTML =
    `<span class="rw-tile"><img src="${imgPrefix}static/wheel/${esc(s.img)}.webp" alt="${esc(s.label)} emblem" loading="lazy" width="320" height="320"></span>` +
    `<span class="rw-label">${esc(s.label)}` +
    (s.sub ? `<span class="rw-sub">${esc(s.sub)}</span>` : "") +
    `</span>`
  return a
}

function layoutCircle(stage: HTMLElement, spokes: HTMLElement[]) {
  // Place each spoke center on a circle of radius ~37% of the stage, starting at top.
  const n = spokes.length
  const radiusPct = 37
  for (let i = 0; i < n; i++) {
    const angle = (i / n) * 2 * Math.PI - Math.PI / 2 // start at 12 o'clock
    const x = 50 + radiusPct * Math.cos(angle)
    const y = 50 + radiusPct * Math.sin(angle)
    const sp = spokes[i]
    sp.style.left = x + "%"
    sp.style.top = y + "%"
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
  stage.appendChild(center)

  const circleSpokes: HTMLElement[] = []
  const fallback = document.createElement("div")
  fallback.className = "rw-fallback"

  for (const s of spokes) {
    circleSpokes.push(buildSpoke(s, prefix, imgPrefix))
    fallback.appendChild(buildSpoke(s, prefix, imgPrefix))
  }
  for (const sp of circleSpokes) stage.appendChild(sp)
  layoutCircle(stage, circleSpokes)

  root.replaceChildren(stage, fallback)

  // Responsive: switch to grid when the wheel would be cramped.
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
