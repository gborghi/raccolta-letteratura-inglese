import { QuartzComponent, QuartzComponentConstructor } from "./types"
// @ts-ignore  bundled as client-side script
import script from "./scripts/conceptWorks.inline"

const style = `
.concept-works { margin: 1rem 0; }
.cw-search {
  width: 100%; box-sizing: border-box; padding: 0.55rem 0.8rem; margin-bottom: 0.5rem;
  border: 1px solid var(--lightgray); border-radius: 10px; background: var(--light);
  color: var(--dark); font-size: 0.95rem; font-family: inherit;
}
.cw-meta { font-size: 0.82rem; color: var(--gray); margin-bottom: 0.5rem; display:flex; gap:0.6rem; align-items:center; flex-wrap:wrap; }
.cw-meta select { font-family: inherit; padding: 0.2rem 0.4rem; border-radius:6px; border:1px solid var(--lightgray); background:var(--light); color:var(--dark); }
table.cw-table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
table.cw-table th, table.cw-table td {
  text-align: left; padding: 0.45rem 0.6rem; border-bottom: 1px solid var(--lightgray); vertical-align: top;
}
table.cw-table th.cw-th { cursor: pointer; user-select: none; white-space: nowrap; color: var(--gray); font-weight: 600; }
table.cw-table th.cw-th:hover { color: var(--secondary); }
table.cw-table th.sorted-asc::after { content: " \\2191"; color: var(--secondary); }
table.cw-table th.sorted-desc::after { content: " \\2193"; color: var(--secondary); }
table.cw-table td.cw-summary { color: var(--darkgray); font-size: 0.84rem; }
table.cw-table tr:hover td { background: var(--highlight); }
.cw-pager { display:flex; gap:0.4rem; align-items:center; margin-top:0.7rem; flex-wrap:wrap; }
.cw-pager button { padding: 0.3rem 0.7rem; border: 1px solid var(--lightgray); border-radius: 8px; background: var(--light); color: var(--dark); cursor: pointer; font-size: 0.85rem; font-family: inherit; }
.cw-pager button:disabled { opacity: 0.4; cursor: default; }
.cw-pager .cw-page-info { color: var(--gray); font-size: 0.85rem; }
mark.cw-hl { background: var(--textHighlight); color: inherit; padding: 0 1px; border-radius: 2px; }
`

export default (() => {
  const ConceptWorks: QuartzComponent = () => null
  ConceptWorks.afterDOMLoaded = script
  ConceptWorks.css = style
  return ConceptWorks
}) satisfies QuartzComponentConstructor
