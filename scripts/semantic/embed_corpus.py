#!/usr/bin/env python3
"""Embed data/semantic/corpus.jsonl with EmbeddingGemma 2 (text encoder only) and write
the static assets of the Semantic search tier to quartz/static/semantic/:
  vec.bin   int8, N x DIM, row-major; each row = round(127 * L2-normalised MRL-truncated vector)
  meta.json {"model","dim","n","prefix_query","ids":[...unique slugs], "rows":[[idIdx, kind, title, speaker, snippet]...]}
Run with ~/.venvs/embeddinggemma2/bin/python (bf16 on MPS; NEVER float16 -> NaN).
Document prompt: "title: {title} | text: {text}"  Query prompt: "task: search result | query: {q}".
"""
import json, os, re, subprocess, sys, time
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
CKPT = Path(os.environ.get("EMBEDDINGGEMMA2_CKPT", Path.home() / "AI/models/llm/embeddinggemma-2"))
DIM = int(os.environ.get("SEM_DIM", "256"))
MAXLEN = int(os.environ.get("SEM_MAXLEN", "512"))
OUT = ROOT / "quartz" / "static" / "semantic"
CACHE = ROOT / "data" / "semantic" / "emb768.npy"

def free_pct():
    try:
        out = subprocess.run(["memory_pressure"], capture_output=True, text=True).stdout
        return int(re.search(r"free percentage: (\d+)%", out).group(1))
    except Exception:
        return 100

def doc_text(r):
    t = r["t"] or "none"
    x = f'{r["sp"]}: {r["x"]}' if r.get("sp") else r["x"]
    return f"title: {t} | text: {x}"

def main():
    recs = [json.loads(l) for l in open(ROOT / "data/semantic/corpus.jsonl", encoding="utf-8")]
    texts = [doc_text(r) for r in recs]
    if CACHE.exists() and np.load(CACHE, mmap_mode="r").shape[0] == len(texts):
        E = np.load(CACHE)
    else:
        import torch
        from sentence_transformers import SentenceTransformer
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        dev = "mps" if torch.backends.mps.is_available() else "cpu"
        dt = torch.bfloat16 if dev == "mps" else torch.float32
        m = SentenceTransformer(str(CKPT), device=dev, model_kwargs={"torch_dtype": dt},
                                config_kwargs={"vision_config": None, "audio_config": None}, local_files_only=True)
        m.max_seq_length = MAXLEN
        order = np.argsort([len(t) for t in texts])[::-1]
        E = np.zeros((len(texts), 768), np.float32)
        t0 = time.time(); B = 1024
        for i in range(0, len(order), B):
            if free_pct() < 15:
                sys.exit("stop: RAM libera < 15%")
            idx = order[i:i + B]
            v = m.encode([texts[j] for j in idx], batch_size=32, normalize_embeddings=True, convert_to_numpy=True)
            E[idx] = v.astype(np.float32)
            print(f"{i + len(idx)}/{len(texts)} {time.time() - t0:.0f}s", file=sys.stderr, flush=True)
        assert np.isfinite(E).all(), "NaN in embeddings"
        np.save(CACHE, E)
    V = E[:, :DIM].copy()
    V /= np.linalg.norm(V, axis=1, keepdims=True)
    Q = np.clip(np.round(V * 127), -127, 127).astype(np.int8)
    OUT.mkdir(parents=True, exist_ok=True)
    Q.tofile(OUT / "vec.bin")
    ids, pos, rows = [], {}, []
    for r in recs:
        s = r["id"]
        if s not in pos:
            pos[s] = len(ids); ids.append(s)
        kind = {"atom": 0, "page": 1, "line": 2}[r["k"]]
        snip = r["x"][:140] if kind == 2 else ""
        rows.append([pos[s], kind, r["t"], r.get("sp", ""), snip])
    meta = {"model": "onnx-community/embeddinggemma-2-ONNX", "dim": DIM, "n": len(rows), "quant": "int8/127",
            "prefix_query": "task: search result | query: ", "ids": ids, "rows": rows}
    (OUT / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("written", len(rows), "rows", len(ids), "ids", file=sys.stderr)

main()
