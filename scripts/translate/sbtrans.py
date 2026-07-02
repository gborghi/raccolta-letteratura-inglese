# -*- coding: utf-8 -*-
"""SubjectBrain EN->IT translator core (tower / Ollama TowerInstruct).

Design notes (learned this session):
- Tower is a 7B LLM via Ollama: it DROPS inline <MSK/> placeholders, so we do NOT
  mask inline spans. Sayers pages are plain prose (no wikilinks/<br>/math), so the
  only structural things to shield are the <nav> block and empty footnote-link
  artifacts. We translate SENTENCE BY SENTENCE (tower merges multi-sentence input).
- Content-addressed cache: sha1(source sentence) -> IT. A paragraph in the full
  work, a chapter, and a part_NN fragment share sentences, so each unique sentence
  is translated ONCE and reused everywhere -> full-work IT == sum of fragment IT,
  by construction. Store is append-only jsonl, resumable.
"""
import re, json, hashlib, os, sys, threading, urllib.request
from concurrent.futures import ThreadPoolExecutor

HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
MODEL = os.environ.get("TOWER_MODEL", "hf.co/tensorblock/TowerInstruct-7B-v0.2-GGUF:Q3_K_M")

# ---- tower call ---------------------------------------------------------------
def tower(text, tgt="Italian", src="English"):
    prompt = f"Translate the following {src} text to {tgt}.\n{src}: {text}\n{tgt}:"
    body = json.dumps({"model": MODEL, "stream": False, "options": {"temperature": 0},
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request(HOST + "/api/chat", data=body,
                                 headers={"Content-Type": "application/json"})
    r = json.loads(urllib.request.urlopen(req, timeout=600).read())
    return r["message"]["content"].strip()

# ---- source cleaning ----------------------------------------------------------
NAV_RE = re.compile(r"<nav\b.*?</nav>", re.S)
EMPTY_FN_RE = re.compile(r"\[ *\]\([^)]*\)")           # [ ](...fn...) artifacts
SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'“‘*])")

def clean_body(text):
    text = EMPTY_FN_RE.sub("", text)
    return text

def has_prose(s):
    return re.search(r"[^\W\d_]{3,}", s) is not None

# ---- segmentation: block-aware, sentence-level --------------------------------
def split_blocks(body):
    """Split into blocks on blank lines; keep the blank runs so we can rejoin
    with identical spacing."""
    return re.split(r"(\n[ \t]*\n)", body)

def split_sentences(block):
    return [s for s in SENT_SPLIT.split(block.strip()) if s]

# ---- cache --------------------------------------------------------------------
class Cache:
    def __init__(self, path):
        self.path = path
        self.d = {}
        self._lock = threading.Lock()
        if os.path.exists(path):
            for ln in open(path, encoding="utf-8"):
                ln = ln.strip()
                if ln:
                    r = json.loads(ln)
                    self.d[r["h"]] = r["it"]
        self._fh = open(path, "a", encoding="utf-8")

    def key(self, s):
        return hashlib.sha1(s.encode("utf-8")).hexdigest()

    def get(self, s):
        return self.d.get(self.key(s))

    def put(self, s, it):
        h = self.key(s)
        with self._lock:
            if h in self.d:
                return
            self.d[h] = it
            self._fh.write(json.dumps({"h": h, "en": s, "it": it}, ensure_ascii=False) + "\n")
            self._fh.flush()

# ---- translate a body (returns IT body, same block structure) -----------------
def translate_body(body, cache, submit):
    body = clean_body(body)
    parts = split_blocks(body)
    out = []
    for part in parts:
        if part.startswith("\n") or not part.strip():
            out.append(part)                     # blank-line separator: keep
            continue
        # protect a nav block verbatim
        if part.lstrip().startswith("<nav"):
            out.append(part); continue
        sents = split_sentences(part)
        if not sents:
            out.append(part); continue
        new = []
        for s in sents:
            if not has_prose(s):
                new.append(s); continue
            it = cache.get(s)
            if it is None:
                it = submit(s)                   # blocking future .result via submit
            new.append(it)
        # preserve leading indentation of the block (e.g. "> " blockquote)
        lead = re.match(r"^\s*(>+\s*)?", part).group(0)
        out.append(lead + " ".join(new))
    return "".join(out)
