import { promises as fs } from "node:fs"
import path from "node:path"
import sharp from "sharp"
const DIR = path.resolve("quartz/static/wheel")
const files = (await fs.readdir(DIR)).filter(f => f.endsWith(".png"))
const sleep = (ms) => new Promise(r => setTimeout(r, ms))
let done = 0
for (const f of files) {
  const src = path.join(DIR, f)
  const out = path.join(DIR, f.replace(/\.png$/, ".webp"))
  const buf = await fs.readFile(src)
  await sharp(buf).resize(320, 320, { fit: "cover" }).webp({ quality: 82 }).toFile(out)
  for (let i = 0; i < 5; i++) {
    try { await fs.rm(src); break } catch { await sleep(300) }
  }
  done++
}
let total = 0
for (const f of await fs.readdir(DIR)) total += (await fs.stat(path.join(DIR, f))).size
console.log(`processed ${done} pngs; dir now total ${(total/1024).toFixed(0)} KB`)
