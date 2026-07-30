// Axis-grouped tag chips.
//
// A leaf of this vault carries up to forty tags, and every one of them is a
// namespaced concept id: `concept/ambition`, `motif/blood`, `character/falstaff`.
// Rendered as one flat row of `#concept/self_and_soul` chips they are noise — the
// namespace is repeated forty times and the distinctions between the axes of the
// knowledge graph, which are the whole point of the graph, are invisible.
//
// This regroups the flat `ul.tags` into one row per axis, with the axis named once
// as a rubric and the chips carrying only the part that varies. Nothing is added or
// removed: every anchor keeps its original href, so /tags/<id> still resolves and
// the tag pages are unaffected. Purely presentational, and reversible by deleting
// this script.
//
// Runs on every content page; no-ops where there is no tag list (folder and tag
// pages exclude the component — see layout.byPageType in quartz.config.yaml).

// The eight axes of the knowledge graph, in reading order: meaning first, then the
// people it happens to, then where, then in what form. Anything unrecognised keeps
// its own prefix as the rubric and sorts to the end, so a new axis in the vault
// degrades to "shown, unstyled" rather than "dropped".
const AXES: [prefix: string, label: string][] = [
  ["concept", "Concept"],
  ["motif", "Motif"],
  ["topos", "Topos"],
  ["archetype", "Archetype"],
  ["character", "Character"],
  ["setting", "Setting"],
  ["form", "Form"],
  ["cluster", "Cluster"],
]

const ORDER = new Map(AXES.map(([prefix], i) => [prefix, i]))
const LABEL = new Map(AXES)

// `concept/self_and_soul` -> "self and soul". The id is the link target and stays
// untouched; this is only what the reader sees on the chip.
function chipText(id: string): string {
  return id.replace(/_/g, " ")
}

function axisOf(tag: string): { axis: string; rest: string } {
  const slash = tag.indexOf("/")
  if (slash < 1) return { axis: "", rest: tag }
  return { axis: tag.slice(0, slash), rest: tag.slice(slash + 1) }
}

// The tag as authored, recovered from the chip rather than from the href: the href
// is slugified (lowercased, punctuation folded) while the text keeps the id.
function tagId(a: HTMLAnchorElement): string {
  return (a.textContent || "").trim().replace(/^#/, "")
}

function build(list: HTMLUListElement): HTMLDivElement | null {
  const anchors = Array.from(list.querySelectorAll<HTMLAnchorElement>("a.tag-link"))
  if (anchors.length < 2) return null

  const groups = new Map<string, HTMLAnchorElement[]>()
  for (const a of anchors) {
    const { axis } = axisOf(tagId(a))
    const key = axis || "—"
    const bucket = groups.get(key)
    if (bucket) bucket.push(a)
    else groups.set(key, [a])
  }

  // A single group means the grouping tells the reader nothing they cannot see.
  if (groups.size < 2) return null

  const keys = Array.from(groups.keys()).sort((x, y) => {
    const ix = ORDER.has(x) ? ORDER.get(x)! : AXES.length
    const iy = ORDER.has(y) ? ORDER.get(y)! : AXES.length
    return ix !== iy ? ix - iy : x.localeCompare(y)
  })

  const wrap = document.createElement("div")
  wrap.className = "axis-tags"

  for (const key of keys) {
    const row = document.createElement("div")
    row.className = "axis-row"

    const name = document.createElement("span")
    name.className = "axis-name"
    name.textContent = LABEL.get(key) ?? key
    row.appendChild(name)

    const chips = document.createElement("span")
    chips.className = "axis-chips"
    for (const a of groups.get(key)!) {
      const { rest } = axisOf(tagId(a))
      const chip = document.createElement("a")
      chip.href = a.getAttribute("href") || "#"
      chip.textContent = chipText(rest)
      // the full id stays available to the reader on hover and to assistive tech
      chip.title = tagId(a)
      chips.appendChild(chip)
    }
    row.appendChild(chips)
    wrap.appendChild(row)
  }
  return wrap
}

function apply() {
  for (const list of document.querySelectorAll<HTMLUListElement>("ul.tags")) {
    // idempotent across SPA navigations: the rebuilt row sits next to the original
    if (list.dataset.axisGrouped === "1") continue
    const grouped = build(list)
    list.dataset.axisGrouped = "1"
    if (!grouped) continue
    list.insertAdjacentElement("afterend", grouped)
    // the flat list is kept in the DOM (search, the graph and the tag plugin read it)
    // but taken out of the visual and accessibility trees
    list.style.display = "none"
    list.setAttribute("aria-hidden", "true")
  }
}

document.addEventListener("nav", apply)
