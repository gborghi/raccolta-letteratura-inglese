# -*- coding: utf-8 -*-
"""Continue the Dickens EN->IT translation with TranslateGemma-27B (Ollama),
reusing dickens_tower.py but swapping translate_block for:
  translate the block PLAIN (TranslateGemma's strong suit; it strips markup) ->
  reattach [[Target|label]] wikilinks with dickens_relink (verbatim names +
  concept-word re-translation) -> unresolved links go to the repair queue.

TranslateGemma needs its rigid format: ONE user message, no system prompt, the
exact "You are a professional English (en) to Italian (it) translator ...
Please translate the following English text into Italian:\n\n{text}". Ollama's
official build applies the correct gemma template, so we just send that content.

Parallelism: N atom-workers (default 4). Requires the Ollama server started with
OLLAMA_NUM_PARALLEL=4 to actually batch (else concurrent requests serialise).

NOTE (measured): on one atom this pipeline ran ~6x SLOWER than the HY few-shot
one and recovered fewer links (11-13/17 vs 15/17). Kept for quality passes /
comparison, not recommended for the bulk. Separate cache: dickens_tg_cache.jsonl.
"""
import os, sys, re, csv, json, time, glob, threading, queue, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import dickens_tower as dt
import dickens_relink as dl

WORKERS = int(os.environ.get("TG_WORKERS", "4"))
LIMIT = int(os.environ["TG_LIMIT"]) if os.environ.get("TG_LIMIT") else None
OLLAMA = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
TG_MODEL = os.environ.get("TG_MODEL", "translategemma:27b")

dt.CACHE_PATH = os.path.join(dt.ROOT, "data", "dickens_tg_cache.jsonl")
FIXUPS_PATH = os.path.join(dt.ROOT, "data", "dickens_tg_linkfix.jsonl")

TR = ("You are a professional English (en) to Italian (it) translator. Produce only the "
      "Italian translation, without any additional explanations or commentary.\n\n"
      "Please translate the following English text into Italian:\n\n{t}")


def tg_raw(text, retries=3):
    body = json.dumps({"model": TG_MODEL, "stream": False, "options": {"temperature": 0},
                       "messages": [{"role": "user", "content": TR.format(t=text)}]}).encode()
    last = None
    for a in range(retries):
        try:
            r = json.loads(urllib.request.urlopen(urllib.request.Request(
                OLLAMA + "/api/chat", data=body, headers={"Content-Type": "application/json"}),
                timeout=900).read())
            out = r["message"]["content"].strip()
            if out:
                return out
            last = "empty"
        except Exception as e:
            last = repr(e); time.sleep(5 * (a + 1))
    raise RuntimeError(f"TG call failed: {last}")


_wc, _wl = {}, threading.Lock()


def tr_word(w):
    with _wl:
        if w in _wc:
            return _wc[w]
    it = tg_raw(w).strip().strip('.,;:!?«»"\'').split("\n")[0]
    it = re.sub(r"^(la |il |lo |le |i |gli |un |una |uno )", "", it, flags=re.I).strip()
    with _wl:
        _wc[w] = it
    return it


def _tg_translate_block(en_block, verse=False, tries=1):
    it = tg_raw(dl.strip_markup(en_block))
    it = re.sub(r"\s*\n[ \t]*\n+\s*", " ", it).strip()
    it, missing = dl.reattach_links(en_block, it, tr_word)
    return it, missing


dt.translate_block = _tg_translate_block   # the pipeline now goes through TG+reattach


class SafeCache(dt.Cache):
    def __init__(self, path):
        super().__init__(path); self._lock = threading.Lock()

    def get(self, s):
        with self._lock:
            return super().get(s)

    def put(self, s, it):
        with self._lock:
            super().put(s, it)


_fix_lock, _log_lock = threading.Lock(), threading.Lock()


def _log(m):
    with _log_lock:
        print(m, flush=True)


def gather_pending():
    tsvs = sorted(glob.glob(os.path.join(HERE, "*_atoms.tsv")))
    tsvs.sort(key=lambda p: (0 if "david_copperfield" in p else 1, p))
    out = []
    for tsv in tsvs:
        for r in csv.DictReader(open(tsv, encoding="utf-8"), delimiter="\t"):
            en = os.path.join(dt.VAULT_ROOT, r["vault_en_path"])
            if os.path.exists(en) and not os.path.exists(en[:-3] + ".it.md"):
                out.append(en)
    return out


def main():
    pending = gather_pending()
    if LIMIT:
        pending = pending[:LIMIT]
    _log(f"### TG Dickens run | model={TG_MODEL} | workers={WORKERS} | pending={len(pending)}")
    cache = SafeCache(dt.CACHE_PATH)
    q = queue.Queue()
    for p in pending:
        q.put(p)
    counts = {"ok": 0, "fail": 0}
    t0 = time.time()

    def worker():
        while True:
            try:
                en_path = q.get_nowait()
            except queue.Empty:
                return
            rel = os.path.relpath(en_path, dt.VAULT_ROOT)
            fixups = []
            try:
                it_body = dt.translate_atom(en_path, cache, fixups)
                en_body = dt._read_vault(en_path)
                problems = dt.validate(en_body, it_body,
                                       "/Poems/" in en_path or "/Long/" in en_path)
                if problems:
                    _log(f"REJECT {rel}: {'; '.join(problems)}"); counts["fail"] += 1
                    # NIENTE task_done() qui: il `continue` esegue comunque il `finally` in fondo.
                    # Contarlo due volte scala di 2 il contatore della coda per un solo elemento;
                    # a fine run la chiamata di troppo solleva ValueError DAL finally e uccide il
                    # thread. Vedi la stessa correzione in run_dickens_hy.py.
                    continue
                dt._write_vault(en_path[:-3] + ".it.md", it_body)
                if fixups:
                    with _fix_lock, open(FIXUPS_PATH, "a", encoding="utf-8") as fh:
                        for f in fixups:
                            fh.write(json.dumps(f, ensure_ascii=False) + "\n")
                counts["ok"] += 1
                _log(f"[{counts['ok']+counts['fail']}/{len(pending)}] ok {rel} | "
                     f"{(time.time()-t0)/60:.0f}m")
            except Exception as e:
                _log(f"FAIL {rel}: {e}"); counts["fail"] += 1
            finally:
                q.task_done()

    ths = [threading.Thread(target=worker, daemon=True) for _ in range(WORKERS)]
    for t in ths:
        t.start()
    for t in ths:
        t.join()
    _log(f"DONE: {counts['ok']} ok, {counts['fail']} fail, {(time.time()-t0)/60:.0f}m")


if __name__ == "__main__":
    main()
