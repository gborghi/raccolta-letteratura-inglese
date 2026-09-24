// The community darkmode script follows prefers-color-scheme and, on every SPA
// "nav", re-binds a media listener that writes localStorage.theme. Opening a
// reading page with a hash (#chapter_01, the Brani links) can fire that path and
// lock the whole site into dark. First paint may follow the OS; after that only
// a click on the Dark mode button may change the theme.

const root = document.documentElement
let locked = root.getAttribute("saved-theme") || "light"
let allow = false

document.addEventListener(
  "click",
  (ev) => {
    const t = ev.target as Element | null
    if (!t || typeof t.closest !== "function" || !t.closest(".darkmode")) return
    allow = true
    queueMicrotask(() => {
      locked = root.getAttribute("saved-theme") || locked
      allow = false
    })
  },
  true,
)

const origSet = root.setAttribute.bind(root)
root.setAttribute = (name: string, value: string) => {
  if (name === "saved-theme" && !allow && value !== locked) return origSet(name, locked)
  return origSet(name, value)
}

const origItem = localStorage.setItem.bind(localStorage)
localStorage.setItem = (key: string, value: string) => {
  if (key === "theme" && !allow) return
  return origItem(key, value)
}

export {}
