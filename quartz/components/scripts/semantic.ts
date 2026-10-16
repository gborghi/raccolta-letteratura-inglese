// Semantic search tier (EmbeddingGemma 2, in-browser). Shared by the top-bar search
// (searchDepth.inline.ts, "Semantic" stop above Max) and the aggregator tables (Works,
// Excerpts, concept works, /cerca tag search) via makeSemanticToggle().
//
// - Query embedding: onnx-community/embeddinggemma-2-ONNX through Transformers.js (>=4.3.1,
//   loaded lazily from the jsDelivr CDN only when the user switches the tier on), TEXT
//   encoder only (config.vision_config = config.audio_config = null), WebGPU + q4; without
//   WebGPU it falls back to WASM fp16 (then WASM q8 if fp16 fails).
// - Corpus embeddings are precomputed on the Mac with the same model
//   (scripts/semantic/*.py): static/semantic/vec.bin (int8, N x dim, Matryoshka-truncated
//   + re-normalised) + static/semantic/meta.json (ids, rows: [idIdx, kind, title, speaker, snippet]).
// - Query prefix "task: search result | query: ", document prefix "title: {t} | text: {x}".
// - Desktop only for now: semanticSupported() is false on phones/tablets.
// Each inline script is bundled separately, so the loaded model + index live on `window`
// and are shared by every caller on the page.

export const TJS_URL = "https://cdn.jsdelivr.net/npm/@huggingface/transformers@4.3.1"
export const MODEL_ID = "onnx-community/embeddinggemma-2-ONNX"

export type SemRow = [number, number, string, string, string] // idIdx, kind 0 atom/1 page/2 line, title, speaker, snippet
export type SemHit = { id: string; score: number; kind: number; title: string; speaker: string; snippet: string }

type SemState = {
  meta?: { dim: number; n: number; prefix_query: string; ids: string[]; rows: SemRow[] }
  vec?: Int8Array
  embed?: (q: string) => Promise<Float32Array>
  device?: string
  loading?: Promise<void>
  qcache: Map<string, Float32Array>
}

function S(): SemState {
  const w = window as any
  if (!w.__semState) w.__semState = { qcache: new Map() }
  return w.__semState as SemState
}

export function semanticSupported(): boolean {
  if (typeof window === "undefined") return false
  const ua = navigator.userAgent || ""
  if (/Android|iPhone|iPad|iPod|Mobile|Silk|Kindle/i.test(ua)) return false
  if ((navigator as any).userAgentData?.mobile) return false
  if (matchMedia("(max-width: 800px)").matches || matchMedia("(pointer: coarse)").matches) return false
  return true
}

function basePath(): string {
  return document.body.dataset.basepath ?? ""
}

async function loadIndex(st: SemState) {
  const base = `${basePath()}/static/semantic/`
  const [meta, buf] = await Promise.all([
    fetch(base + "meta.json").then((r) => {
      if (!r.ok) throw new Error("meta " + r.status)
      return r.json()
    }),
    fetch(base + "vec.bin").then((r) => {
      if (!r.ok) throw new Error("vec " + r.status)
      return r.arrayBuffer()
    }),
  ])
  st.meta = meta
  st.vec = new Int8Array(buf)
}

async function loadModel(st: SemState, onStatus?: (s: string) => void) {
  const url = TJS_URL
  const T: any = await import(/* @vite-ignore */ url)
  const config = await T.AutoConfig.from_pretrained(MODEL_ID)
  config.vision_config = null
  config.audio_config = null
  const tokenizer = await T.AutoTokenizer.from_pretrained(MODEL_ID)
  const progress_callback = (p: any) => {
    if (p?.status === "progress" && p.total) onStatus?.(`Downloading model… ${Math.round((100 * p.loaded) / p.total)}%`)
  }
  let model: any = null
  const tries: [string, string][] = []
  let hasGpu = false
  try {
    hasGpu = !!(navigator as any).gpu && !!(await (navigator as any).gpu.requestAdapter())
  } catch {}
  if (hasGpu) tries.push(["webgpu", "q4"])
  tries.push(["wasm", "fp16"], ["wasm", "q8"])
  let lastErr: any
  for (const [device, dtype] of tries) {
    try {
      model = await T.AutoModel.from_pretrained(MODEL_ID, { config, device, dtype, progress_callback })
      st.device = `${device}/${dtype}`
      break
    } catch (e) {
      lastErr = e
    }
  }
  if (!model) throw lastErr
  const dim = st.meta!.dim
  const prefix = st.meta!.prefix_query
  st.embed = async (q: string) => {
    const inputs = await tokenizer([prefix + q], { padding: true, truncation: true })
    const out = await model(inputs)
    const e = out.sentence_embedding.data as Float32Array
    const v = new Float32Array(dim)
    let n = 0
    for (let i = 0; i < dim; i++) {
      v[i] = e[i]
      n += e[i] * e[i]
    }
    n = Math.sqrt(n) || 1
    for (let i = 0; i < dim; i++) v[i] /= n
    return v
  }
}

// Load index + model once per page (shared across bundles). onStatus gets progress text.
export function ensureSemantic(onStatus?: (s: string) => void): Promise<void> {
  const st = S()
  if (st.embed && st.meta) return Promise.resolve()
  if (!st.loading) {
    st.loading = (async () => {
      onStatus?.("Loading semantic index…")
      await loadIndex(st)
      onStatus?.("Loading EmbeddingGemma 2…")
      await loadModel(st, onStatus)
      onStatus?.("")
    })().catch((e) => {
      st.loading = undefined
      throw e
    })
  }
  return st.loading
}

export function semanticReady(): boolean {
  const st = S()
  return !!(st.embed && st.meta)
}
export function semanticDevice(): string {
  return S().device ?? ""
}

// Top-k rows by cosine (int8 dot product). `accept(id)` optionally restricts the pool.
export async function semanticSearch(q: string, k = 200, accept?: (id: string) => boolean): Promise<SemHit[]> {
  const st = S()
  await ensureSemantic()
  const query = q.trim()
  if (!query) return []
  let qv = st.qcache.get(query)
  if (!qv) {
    qv = await st.embed!(query)
    st.qcache.set(query, qv)
  }
  const { dim, rows, ids } = st.meta!
  const vec = st.vec!
  const n = rows.length
  const scores = new Float32Array(n)
  for (let r = 0, o = 0; r < n; r++, o += dim) {
    let s = 0
    for (let i = 0; i < dim; i++) s += qv[i] * vec[o + i]
    scores[r] = s / 127
  }
  const order: number[] = []
  for (let r = 0; r < n; r++) if (!accept || accept(ids[rows[r][0]])) order.push(r)
  order.sort((a, b) => scores[b] - scores[a])
  return order.slice(0, k).map((r) => {
    const [ii, kind, title, speaker, snippet] = rows[r]
    return { id: ids[ii], score: scores[r], kind, title, speaker, snippet }
  })
}

// Normalise an href/slug to the corpus id form ("a/b#c", no leading slash/./, no .html).
export function normId(h: string | undefined): string {
  return String(h || "")
    .replace(/^\.?\/+/, "")
    .replace(/\.html(?=#|$)/, "")
}

// Best score per id AND per base work (part before "#"), for ranking table rows.
export async function semanticScoreMap(q: string, k = 3000): Promise<Map<string, number>> {
  const hits = await semanticSearch(q, k)
  const m = new Map<string, number>()
  const put = (key: string, s: number) => {
    if (!m.has(key) || m.get(key)! < s) m.set(key, s)
  }
  for (const h of hits) {
    put(h.id, h.score)
    put(h.id.split("#")[0], h.score)
  }
  return m
}

// Score for a table row given its candidate hrefs (first defined wins by max).
export function rowScore(m: Map<string, number>, ...hrefs: (string | undefined)[]): number {
  let best = -Infinity
  for (const h of hrefs) {
    if (!h) continue
    const id = normId(h)
    const s = m.get(id) ?? m.get(id.split("#")[0])
    if (s !== undefined && s > best) best = s
  }
  return best
}

// "Semantic" toggle button for the aggregator tables (desktop only; returns null on mobile).
// The caller keeps a `semOn` flag via isOn/setOn and re-renders; scores() gives the latest
// score map for the current query (or null while computing / when off).
export function makeSemanticToggle(opts: {
  input: HTMLInputElement
  rerender: () => void
}): { button: HTMLButtonElement | null; isOn: () => boolean; scores: () => Map<string, number> | null } {
  let on = false
  let map: Map<string, number> | null = null
  let mapQ = ""
  let seq = 0
  if (!semanticSupported()) return { button: null, isOn: () => false, scores: () => null }
  const btn = document.createElement("button")
  btn.type = "button"
  btn.className = "qtable-modebtn sem-btn"
  btn.title = "Semantic search (EmbeddingGemma 2, runs in your browser; desktop only)"
  const sync = (txt?: string) => {
    btn.textContent = txt || (on ? "Semantic: on" : "Semantic: off")
    btn.setAttribute("aria-pressed", String(on))
  }
  sync()
  const recompute = async () => {
    const q = opts.input.value.trim()
    const my = ++seq
    if (!on || !q) {
      map = null
      mapQ = ""
      opts.rerender()
      return
    }
    if (q === mapQ && map) return opts.rerender()
    try {
      const m = await semanticScoreMap(q)
      if (my !== seq) return
      map = m
      mapQ = q
      sync()
      opts.rerender()
    } catch (e) {
      console.error("semantic search", e)
      sync("Semantic: error")
    }
  }
  let t: number | undefined
  opts.input.addEventListener("input", () => {
    if (!on) return
    clearTimeout(t)
    t = window.setTimeout(recompute, 350)
  })
  btn.addEventListener("click", async () => {
    on = !on
    sync()
    if (on && !semanticReady()) {
      btn.disabled = true
      try {
        await ensureSemantic((s) => s && sync(s))
      } catch (e) {
        console.error("semantic load", e)
        on = false
        btn.disabled = false
        sync("Semantic: unavailable")
        return
      }
      btn.disabled = false
      sync()
    }
    void recompute()
  })
  return { button: btn, isOn: () => on, scores: () => (on && opts.input.value.trim() ? map : null) }
}
