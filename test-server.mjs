import http from "node:http"
import { promises as fs } from "node:fs"
import path from "node:path"
const ROOT = path.resolve("public")
const TYPES = { ".html":"text/html",".js":"text/javascript",".css":"text/css",".json":"application/json",".svg":"image/svg+xml",".png":"image/png",".ico":"image/x-icon",".woff2":"font/woff2",".xml":"application/xml" }
async function tryFiles(p){ for(const c of [p, p+".html", path.join(p,"index.html")]){ try{ const s=await fs.stat(c); if(s.isFile()) return c }catch{} } return null }
http.createServer(async (req,res)=>{
  const u = decodeURIComponent(req.url.split("?")[0])
  let f = await tryFiles(path.join(ROOT, u))
  if(!f){ res.writeHead(404); res.end("404"); return }
  const data = await fs.readFile(f)
  res.writeHead(200, {"content-type": TYPES[path.extname(f)] || "application/octet-stream"})
  res.end(data)
}).listen(8137, ()=>console.log("up on 8137"))
