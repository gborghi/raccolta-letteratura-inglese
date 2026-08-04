import {unified} from "unified"
import remarkParse from "remark-parse"
import remarkGfm from "remark-gfm"

function cellsInFirstRow(md) {
  const tree = unified().use(remarkParse).use(remarkGfm).parse(md)
  const table = tree.children.find((n) => n.type === "table")
  if (!table) return 0
  return table.children[0].children.length // cells in the header/first row
}
const RAW = "| [[Horatio|HORATIO]] | Friends to this ground. |\n|---|---|\n| A | B |"
const ESC = "| [[Horatio\\|HORATIO]] | Friends to this ground. |\n|---|---|\n| A | B |"
console.log("raw cells (bug, expect >2):", cellsInFirstRow(RAW))
console.log("escaped cells (fixed, expect 2):", cellsInFirstRow(ESC))

// wikilink target survives the escape:
const RE = /!?\[\[([^[\]#|\\]+)?(#+[^[\]#|\\]+)?(\\?\|[^[\]#]*)?\]\]/g
const m = RE.exec("[[Horatio\\|HORATIO]]")
console.log("wikilink target (expect Horatio):", m && m[1], "| alias group:", m && m[3])
