# -*- coding: utf-8 -*-
"""Continue the Dickens EN->IT translation with HY-MT1.5-7B (LM Studio :1234),
reusing dickens_tower.py wholesale but swapping the model call for HY:

  * PROMPT: few-shot (the [[Lxx|word]] link convention is taught by EXAMPLE, not
    by rules — HY, a specialised MT model, ignores rule-prose but pattern-matches
    examples). This lifts link preservation from 11/17 to ~15/17 on the probe atom.
  * POST-PROCESS: strip_ellipses() removes the ellipsis character HY adds of its
    own accord (unfixable by prompt), restoring normal punctuation.
  * PARALLEL: N worker threads translate N atoms at once. On Apple Silicon the
    llama.cpp continuous-batcher gives ~1.8x aggregate throughput at 4 streams.

Separate cache (dickens_hy_cache.jsonl) + linkfix (dickens_hy_linkfix.jsonl) so
the Tower run's artifacts stay pristine. Resumable: atoms with an existing .it.md
are skipped. Env: HY_WORKERS (default 4), HY_LIMIT (optional, for a smoke test).
"""
import os, sys, re, csv, json, time, glob, threading, queue, urllib.request

os.environ.setdefault("TOWER_MODEL", "hy-mt1.5-7b")
os.environ.setdefault("LMSTUDIO_HOST", "http://localhost:1234")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import dickens_tower as dt

WORKERS = int(os.environ.get("HY_WORKERS", "4"))
LIMIT = int(os.environ["HY_LIMIT"]) if os.environ.get("HY_LIMIT") else None

dt.CACHE_PATH = os.path.join(dt.ROOT, "data", "dickens_hy_cache.jsonl")
FIXUPS_PATH = os.path.join(dt.ROOT, "data", "dickens_hy_linkfix.jsonl")
# Every rejected/failed atom is recorded here (structured, not just the log) so
# retranslate_rejected.py / the watcher can retry+Opus them -- no silent drops.
REJECTED_PATH = os.path.join(HERE, "run_logs", "dickens_rejected.jsonl")


# ---------- ellipsis post-processing (HY adds '…' of its own) ----------
def strip_ellipses(s: str) -> str:
    s = s.replace("...", "…")
    s = re.sub(r"\s*…\s*$", ".", s, flags=re.M)
    s = re.sub(r"\s*…\s+(?=[A-ZÀ-Þ\[\"«])", ". ", s)
    s = re.sub(r"\s*…\s*", ", ", s)
    s = re.sub(r"\s+([.,;:!?])", r"\1", s)
    s = re.sub(r",\s*\.", ".", s)
    return s


# ---------- few-shot HY call, monkeypatched over dt._ask ----------
FEWSHOT = [
    {"role": "system", "content":
        "You are a literary English-to-Italian translator. Every [[Lxx|word]] "
        "marker MUST reappear EXACTLY as [[Lxx|parola]]: keep the Lxx code, keep "
        "the vertical bar '|' (never ']' nor a space), translate ONLY the word "
        "after '|'. Never drop a marker or flatten it to plain text. Punctuation: "
        "only . , ; : ! ? and quotes; NEVER output the ellipsis character; keep "
        "every sentence whole."},
    {"role": "user", "content": "Translate to Italian:\n\nThe boys were paralysed "
        "with [[L01|wonder]]; the young [[L02|rebel]] felt no [[L03|fear]]."},
    {"role": "assistant", "content": "I ragazzi erano paralizzati dallo "
        "[[L01|stupore]]; il giovane [[L02|ribelle]] non provava alcuna [[L03|paura]]."},
    {"role": "user", "content": "Translate to Italian:\n\n[[L01|Child]] as he was, "
        "at [[L02|night]] he plucked a [[L03|rose]] and ran to [[L04|Oliver]]."},
    {"role": "assistant", "content": "[[L01|Bambino]] com'era, di [[L02|notte]] "
        "colse una [[L03|rosa]] e corse da [[L04|Oliver]]."},
]
# (the old _PIPE_REPAIR for [[Lnn]label]] now lives in dt.repair_mask_codes, with the
#  wrong-separator and single-closing-bracket variants it never covered)


def _call_msgs(messages, max_tokens, retries=3):
    body = json.dumps({"model": dt.MODEL, "temperature": 0,
                       "max_tokens": max_tokens, "messages": messages}).encode()
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(dt.HOST + "/v1/chat/completions", data=body,
                                         headers={"Content-Type": "application/json"})
            r = json.loads(urllib.request.urlopen(req, timeout=900).read())
            out = r["choices"][0]["message"]["content"].strip()
            if out:
                return out
            last = "empty"
        except Exception as e:
            last = repr(e)
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"HY call failed: {last}")


def _ask_hy(masked_text, want, verse=False):
    if not want and dt.is_heading(masked_text):
        out = dt.call_tower("Title:\n" + masked_text, dt.SYSTEM_TITLE, max_tokens=48)
        out = dt.repair_half_leak(out)
        out = dt.repair_cjk_span(out)
        return re.sub(r"\s*\n[ \t]*\n+\s*", " ", out).strip()
    msgs = FEWSHOT + [{"role": "user",
                       "content": "Translate to Italian:\n\n" + masked_text}]
    budget = min(4096, max(64, int(len(masked_text) / 1.4)))
    out = _call_msgs(msgs, budget)
    out = dt.repair_mask_codes(out)   # subsumes the old glued/pipe repairs, plus [[Lnn|x] and [[Lnn>x]
    out = dt.repair_half_leak(out)    # HY writes the "half-" of a compound as the bare Han U+534A
    out = dt.repair_cjk_span(out)     # ultima istanza: ritraduce la sola frase dove resta del cinese
    out = strip_ellipses(out)
    return re.sub(r"\s*\n[ \t]*\n+\s*", " ", out).strip()


dt._ask = _ask_hy   # <-- the whole pipeline now translates through HY few-shot


# ---------- thread-safe cache + fixups ----------
class SafeCache(dt.Cache):
    def __init__(self, path):
        super().__init__(path)
        self._lock = threading.Lock()

    def get(self, s):
        with self._lock:
            return super().get(s)

    def put(self, s, it):
        with self._lock:
            super().put(s, it)


_fix_lock = threading.Lock()
_log_lock = threading.Lock()


def _log(msg):
    with _log_lock:
        print(msg, flush=True)


_rej_lock = threading.Lock()


REJECTED_BODIES = os.path.join(os.path.dirname(REJECTED_PATH), "rejected_bodies")


def _record_reject(rel, problems, it_body=None):
    """Append a rejected atom to dickens_rejected.jsonl so it is never silently
    lost: retranslate_rejected.py / the watcher pick it up for retry+Opus.

    Also keep the offending TRANSLATION. The jsonl records only atom/problems/ts,
    and the log line truncates the reason ("leftover mask token(s): 1 (e.g. [[L01..")
    -- so a systematic malformation could never be seen, only guessed at. Without a
    body there is nothing to write a repair regex against."""
    try:
        os.makedirs(os.path.dirname(REJECTED_PATH), exist_ok=True)
        with _rej_lock, open(REJECTED_PATH, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"atom": rel, "problems": list(problems),
                                 "ts": time.time()}, ensure_ascii=False) + "\n")
    except Exception:
        pass
    if it_body is None:
        return
    try:
        os.makedirs(REJECTED_BODIES, exist_ok=True)
        name = rel.replace("/", "__").replace(os.sep, "__")
        with open(os.path.join(REJECTED_BODIES, name), "w", encoding="utf-8") as fh:
            fh.write(it_body)
    except Exception:
        pass


# ---------- gather pending atoms across ALL Dickens works ----------
def gather_pending():
    tsvs = sorted(glob.glob(os.path.join(HERE, "*_atoms.tsv")))
    # continue David Copperfield first (it was mid-flight), then the rest
    tsvs.sort(key=lambda p: (0 if "david_copperfield" in p else 1, p))
    pending = []
    for tsv in tsvs:
        for r in csv.DictReader(open(tsv, encoding="utf-8"), delimiter="\t"):
            en = os.path.join(dt.VAULT_ROOT, r["vault_en_path"])
            if os.path.exists(en) and not os.path.exists(en[:-3] + ".it.md"):
                pending.append(en)
    return pending


def main():
    pending = gather_pending()
    if LIMIT:
        pending = pending[:LIMIT]
    _log(f"### HY Dickens run | model={dt.MODEL} host={dt.HOST} | workers={WORKERS} "
         f"| pending atoms={len(pending)}")
    cache = SafeCache(dt.CACHE_PATH)
    _log(f"cache warm with {len(cache.d)} blocks")

    q = queue.Queue()
    for p in pending:
        q.put(p)
    counts = {"ok": 0, "fail": 0, "blocks": 0}
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
                verse = "/Poems/" in en_path or "/Long/" in en_path
                problems = dt.validate(en_body, it_body, verse)
                if problems:
                    _log(f"REJECT {rel}: {'; '.join(problems)}")
                    _record_reject(rel, problems, it_body)
                    counts["fail"] += 1
                    # NIENTE task_done() qui: il `continue` esegue comunque il `finally` in fondo,
                    # quindi contarlo due volte scala di 2 il contatore della coda per un solo
                    # elemento. A fine run il contatore arriva a zero in anticipo e la chiamata di
                    # troppo solleva ValueError DAL finally, uccidendo il thread worker: un reject
                    # costava un worker, e con abbastanza reject il run finisce a corto di braccia.
                    continue
                dt._write_vault(en_path[:-3] + ".it.md", it_body)
                if fixups:
                    with _fix_lock, open(FIXUPS_PATH, "a", encoding="utf-8") as fh:
                        for f in fixups:
                            fh.write(json.dumps(f, ensure_ascii=False) + "\n")
                counts["ok"] += 1
                counts["blocks"] += len(dt.prose_blocks(en_body))
                el = time.time() - t0
                nmiss = sum(len(f["missing"]) for f in fixups)
                tag = f" | {nmiss} links to repair" if nmiss else ""
                rate = counts["blocks"] / el if el else 0
                _log(f"[{counts['ok'] + counts['fail']}/{len(pending)}] ok {rel} | "
                     f"blocks {counts['blocks']} | {el/60:.0f}m | {rate*60:.0f} blk/min{tag}")
            except Exception as e:
                _log(f"FAIL {rel}: {e}")
                _record_reject(rel, [str(e)])
                counts["fail"] += 1
            finally:
                q.task_done()

    threads = [threading.Thread(target=worker, daemon=True) for _ in range(WORKERS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    _log(f"\nDONE: {counts['ok']} written, {counts['fail']} failed, "
         f"cache {len(cache.d)} blocks, {(time.time()-t0)/60:.0f}m")


if __name__ == "__main__":
    main()
