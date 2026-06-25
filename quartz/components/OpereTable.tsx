import { QuartzComponent, QuartzComponentConstructor } from "./types"
// @ts-ignore  bundled as client-side script
import script from "./scripts/opereTable.inline"

const style = `
#opere-table { margin-top: 1rem; }
.lt-search {
  width: 100%; box-sizing: border-box; padding: 0.55rem 0.8rem; margin-bottom: 0.5rem;
  border: 1px solid var(--lightgray); border-radius: 10px; background: var(--light);
  color: var(--dark); font-size: 0.95rem; font-family: inherit;
}
.lt-meta { font-size: 0.82rem; color: var(--gray); margin-bottom: 0.5rem; display:flex; gap:0.6rem; align-items:center; flex-wrap:wrap; }
.lt-meta select { font-family: inherit; padding: 0.2rem 0.4rem; border-radius:6px; border:1px solid var(--lightgray); background:var(--light); color:var(--dark); }
table.lt-table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
table.lt-table th, table.lt-table td {
  text-align: left; padding: 0.45rem 0.6rem; border-bottom: 1px solid var(--lightgray); vertical-align: top;
}
table.lt-table th.lt-th { cursor: pointer; user-select: none; white-space: nowrap; color: var(--gray); font-weight: 600; }
table.lt-table th.lt-th:hover { color: var(--secondary); }
table.lt-table th.sorted-asc::after { content: " \\2191"; color: var(--secondary); }
table.lt-table th.sorted-desc::after { content: " \\2193"; color: var(--secondary); }
table.lt-table td.lt-num, table.lt-table th.lt-num { text-align: center; }
table.lt-table tr:hover td { background: var(--highlight); }
.lt-cluster { color: var(--gray); font-size: 0.82rem; }
.lt-pager { display:flex; gap:0.4rem; align-items:center; margin-top:0.7rem; flex-wrap:wrap; }
.lt-pager button {
  padding: 0.3rem 0.7rem; border: 1px solid var(--lightgray); border-radius: 8px;
  background: var(--light); color: var(--dark); cursor: pointer; font-size: 0.85rem;
}
.lt-pager button:disabled { opacity: 0.4; cursor: default; }
.lt-pager .lt-page-info { color: var(--gray); font-size: 0.85rem; }
`

export default (() => {
  const OpereTable: QuartzComponent = () => null
  OpereTable.afterDOMLoaded = script
  OpereTable.css = style
  return OpereTable
}) satisfies QuartzComponentConstructor
