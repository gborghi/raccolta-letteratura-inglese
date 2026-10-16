#!/usr/bin/env python3
"""Corpus for the Semantic search tier (EmbeddingGemma 2).

Writes data/semantic/corpus.jsonl, one record per unit:
  {"id": slug-or-slug#atom, "k": "atom"|"page"|"line", "t": title, "x": text, ["sp": speaker]}
- atom: every atom in data/atom_search.json.gz (title + text, already capped)
- page: every content/**/*.md page outside testi/ and tags/ (works, characters, concepts...),
        plus testi works that have no atoms; full text (cleaned, capped).
- line: every spoken line (battuta) of the Shakespeare plays, English half only,
        linked to its scene atom (work#act_N--scene_M).
"""
import gzip, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CAP = 1500
WIKI = re.compile(r"\[\[([^\]|]+?)(?:\\?\|([^\]]+))?\]\]")

def clean(s: str) -> str:
    s = WIKI.sub(lambda m: m.group(2) or m.group(1).split("/")[-1].replace("-", " "), s)
    s = re.sub(r"<br\s*/?>", " ", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", s)
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
    s = re.sub(r"[#*_`>|]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def front(md: str):
    if md.startswith("---"):
        end = md.find("\n---", 3)
        if end > 0:
            fm, body = md[3:end], md[end + 4:]
            m = re.search(r'^title:\s*"?(.*?)"?\s*$', fm, re.M)
            return (m.group(1) if m else ""), body
    return "", md

def main():
    out = ROOT / "data" / "semantic"
    out.mkdir(parents=True, exist_ok=True)
    recs = []
    atoms = json.load(gzip.open(ROOT / "data" / "atom_search.json.gz"))
    works_with_atoms = {k.split("#")[0] for k in atoms}
    for k, v in atoms.items():
        t = v.get("title") or ""
        x = clean(v.get("text") or "")[:CAP]
        if x or t:
            recs.append({"id": k, "k": "atom", "t": t, "x": x})
    content = ROOT / "content"
    for p in sorted(content.rglob("*.md")):
        rel = p.relative_to(content).as_posix()
        if rel.endswith(".it.md") or rel.startswith("tags/"):
            continue
        slug = rel[:-3]
        if slug in works_with_atoms or slug in ("404", "index"):
            continue
        t, body = front(p.read_text(encoding="utf-8", errors="ignore"))
        body = body.split('<span class="qlang-split" data-lang="it"></span>')[0]
        x = clean(body)[:CAP]
        if len(x) < 20 and not t:
            continue
        recs.append({"id": slug, "k": "page", "t": t or slug.split("/")[-1], "x": x})
    # battute
    plays = content / "testi" / "shakespeare" / "plays"
    nlines = 0
    for p in sorted(plays.glob("*.md")):
        if p.name.endswith(".it.md"):
            continue
        work = "testi/shakespeare/plays/" + p.stem
        md = p.read_text(encoding="utf-8", errors="ignore")
        parts = re.split(r'(<span class="atom-split"[^>]*></span>)', md)
        cur = None
        for seg in parts:
            m = re.match(r'<span class="atom-split" data-atom="([^"]+)" data-title="([^"]*)"[^>]*data-kind="([^"]*)"', seg)
            if m:
                cur = (m.group(1), m.group(2), m.group(3))
                continue
            if not cur or cur[2] != "scene":
                continue
            en = seg.split('<span class="qlang-split" data-lang="it"></span>')[0]
            for row in en.splitlines():
                row = row.replace("\\|", "\x00")
                rm = re.match(r"^\|\s*([^|]+?)\s*\|\s*(.+?)\s*\|\s*$", row)
                if not rm:
                    continue
                sp, ln = clean(rm.group(1).replace("\x00", "|")), rm.group(2).replace("\x00", "|")
                if sp in ("Speaker", "---") or "didascalia" in sp or set(sp) <= set("-"):
                    continue
                x = clean(ln)
                if len(x) < 12:
                    continue
                recs.append({"id": f"{work}#{cur[0]}", "k": "line", "t": cur[1], "sp": sp.title(), "x": x[:CAP]})
                nlines += 1
    with open(out / "corpus.jsonl", "w", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    from collections import Counter
    print(Counter(r["k"] for r in recs), "total", len(recs), file=sys.stderr)

main()
