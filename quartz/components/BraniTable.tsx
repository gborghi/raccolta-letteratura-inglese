import { QuartzComponent, QuartzComponentConstructor } from "./types"
// @ts-ignore  bundled as client-side script
import script from "./scripts/braniTable.inline"

// Reuses the .lt-* table styles defined by OpereTable; only adds excerpt-nav styling.
const style = `
.qtable-searchrow { display: flex; gap: 0.5rem; align-items: stretch; margin: 0.4rem 0; flex-wrap: wrap; }
.qtable-searchrow .lt-search { flex: 1 1 16rem; margin: 0; }
.qtable-modebtn {
  flex: 0 0 auto; cursor: pointer; white-space: nowrap;
  font-family: inherit; font-weight: 600; font-size: 0.8rem;
  padding: 0.3rem 0.7rem; border-radius: 999px;
  border: 1.5px solid var(--lightgray); background: var(--light); color: var(--darkgray);
}
.qtable-modebtn:hover { border-color: var(--secondary); color: var(--dark); }
.qtable-modebtn[aria-pressed="true"] { background: var(--secondary); color: var(--light); border-color: var(--secondary); }
.qtable-modebtn:disabled { opacity: 0.6; cursor: progress; }
.excerpt-nav { margin: 0.2rem 0 1.4rem; padding-bottom: 0.8rem; border-bottom: 1px solid var(--lightgray); }
.excerpt-crumb { font-size: 0.85rem; color: var(--gray); }
.excerpt-pn { display: flex; justify-content: space-between; gap: 1rem; margin-top: 0.5rem; font-size: 0.9rem; }
.excerpt-pn a { text-decoration: none; color: var(--secondary); font-weight: 600; }
.excerpt-pn a:hover { text-decoration: underline; }
.excerpt-pn .ex-next { margin-left: auto; text-align: right; }
.lt-type { color: var(--gray); font-size: 0.8rem; text-transform: capitalize; }
`

export default (() => {
  const BraniTable: QuartzComponent = () => null
  BraniTable.afterDOMLoaded = script
  BraniTable.css = style
  return BraniTable
}) satisfies QuartzComponentConstructor
