# -*- coding: utf-8 -*-
"""Translate all Sayers content pages EN->IT with nllb600 (CT2 int8, batched).
Reuses the gather/segment/reassemble helpers from translate_sayers.py; only the
translation step changes (batched NMT instead of per-sentence tower).
Run with the vault_topics venv python (needs ctranslate2 + transformers):
  E:/.../transformers/.venv/Scripts/python.exe translate_sayers_nllb.py
Env: NLLB_CT2_DIR, HF_HOME.
"""
import os, sys, json, time
sys.path.insert(0, os.path.dirname(__file__))
import translate_sayers as T   # gather, parse, body_sentences, reassemble_*, Cache, stores

import ctranslate2
from transformers import AutoTokenizer

NLLB_DIR = os.environ.get("NLLB_CT2_DIR", r"E:/giovanni/models/nllb600-ct2")
SRC, TGT = "eng_Latn", "ita_Latn"

def build_translator():
    tr = ctranslate2.Translator(NLLB_DIR, device="auto", compute_type="int8")
    tok = AutoTokenizer.from_pretrained("facebook/nllb-200-distilled-600M")
    tok.src_lang = SRC
    return tr, tok

def translate_batch(tr, tok, texts, max_batch=64):
    toks = [tok.convert_ids_to_tokens(tok.encode(t)) for t in texts]
    res = tr.translate_batch(toks, target_prefix=[[TGT]] * len(toks),
                             max_batch_size=max_batch, beam_size=2)
    out = []
    for r in res:
        ids = tok.convert_tokens_to_ids(r.hypotheses[0][1:])  # drop target tag
        out.append(tok.decode(ids, skip_special_tokens=True))
    return out

def main():
    os.makedirs(T.DATA, exist_ok=True)
    cache = T.Cache(T.SEG_STORE)
    pages = T.gather()
    print(f"Sayers pages: {len(pages)}", flush=True)

    segset, = (set(),)
    for kind, rel, path in pages:
        meta, body, _ = T.parse(path)
        if meta.get("title"):
            segset.add(meta["title"])
        for s in T.body_sentences(kind, body):
            segset.add(s)
    todo = [s for s in segset if cache.get(s) is None]
    print(f"unique segments: {len(segset)} | to translate: {len(todo)}", flush=True)

    tr, tok = build_translator()
    print("nllb loaded (device auto, int8)", flush=True)
    t0 = time.time()
    B = 64
    for i in range(0, len(todo), B):
        chunk = todo[i:i + B]
        its = translate_batch(tr, tok, chunk)
        for s, it in zip(chunk, its):
            cache.put(s, it)
        if (i // B) % 5 == 0:
            el = time.time() - t0
            n = i + len(chunk)
            print(f"  {n}/{len(todo)}  {n/max(el,1e-9):.1f} seg/s  eta {(len(todo)-n)/max(n/max(el,1e-9),1e-9)/60:.1f}m", flush=True)
    print(f"translated {len(todo)} in {time.time()-t0:.0f}s", flush=True)

    # emit per-page store
    done_rel = set()
    if os.path.exists(T.PAGE_STORE):
        for ln in open(T.PAGE_STORE, encoding="utf-8"):
            if ln.strip():
                done_rel.add(json.loads(ln)["rel"])
    with open(T.PAGE_STORE, "a", encoding="utf-8") as fh:
        for kind, rel, path in pages:
            if rel in done_rel:
                continue
            meta, body, _ = T.parse(path)
            title_it = cache.get(meta["title"]) if meta.get("title") else None
            body_it = T.reassemble_work(body, cache) if kind == "work" else T.reassemble_testi(body, cache)
            fh.write(json.dumps({"rel": rel, "kind": kind,
                                 "title_it": title_it, "body_it": body_it},
                                ensure_ascii=False) + "\n")
    print(f"DONE. {len(pages)} pages -> {T.PAGE_STORE}", flush=True)

if __name__ == "__main__":
    main()
