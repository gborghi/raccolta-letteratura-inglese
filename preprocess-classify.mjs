// Pure classifier extracted out of preprocess.mjs so it can be unit-tested without
// triggering preprocess.mjs's top-level main() (which wipes+regenerates content/).
// Classify a unit relative path (under an author dir) -> { unitType, order }.
export function classifyUnit(relParts, fileName) {
  const f = fileName.replace(/\.md$/, "")
  let m
  if ((m = f.match(/^part_(\d+)$/i))) return { unitType: "excerpt", order: parseInt(m[1], 10) }
  if ((m = f.match(/^Chapter_(\d+)/i))) return { unitType: "chapter", order: parseInt(m[1], 10) }
  if ((m = f.match(/^Story_(\d+)/i))) return { unitType: "story", order: parseInt(m[1], 10) }
  if ((m = f.match(/^Section_(\d+)/i))) return { unitType: "section", order: parseInt(m[1], 10) }
  if ((m = f.match(/^Scene_(\d+)/i))) return { unitType: "scene", order: parseInt(m[1], 10) }
  if ((m = f.match(/^Act_(\d+)/i))) return { unitType: "scene", order: 100 + parseInt(m[1], 10) }
  if (/^Prologue/i.test(f)) return { unitType: "scene", order: 100 }
  return { unitType: "work", order: 0 }
}
