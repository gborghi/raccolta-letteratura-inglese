# -*- coding: utf-8 -*-
"""Rebuild The Everlasting Man's Italian atoms after re-atomisation.

Re-atomising only REGROUPS the English text, so every EN prose block is byte-identical to one in the
old atoms. We harvested sha(EN block)->IT from the old .it.md pairs (ev_it_cache.json) BEFORE
--apply destroyed them; here we walk each NEW .md atom and emit a block-aligned .it.md, translating
each block via that cache. The only blocks the cache can't hold are the NEW chapter headings
(# everlasting man - Chapter N: Title, and the ALL-CAPS in-text title) -- those get Italian from an
explicit title map, so every block is Italian and the emitter publishes the page (miss==0).

Run AFTER reatomize-everlasting-man.py --apply.
"""
import sys, os, re, json, glob, hashlib
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "translate"))
from sbtrans import clean_body, split_blocks, has_prose

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
VAULT = os.path.abspath(os.path.join(ROOT, "..", "VaultEnglish"))
ATOMS = os.path.join(VAULT, "Authors", "Chesterton", "Atomized", "everlasting_man")
CACHE_JSON = os.environ.get("EV_CACHE", "/private/tmp/claude-501/-Users-g-borghi-Library-CloudStorage-Dropbox-insegnamento-Wiligelmo-SubjectBrain-English/1e594d69-34c3-4b85-bdd8-616e625633e5/scratchpad/ev_it_cache.json")

def sha(s): return hashlib.sha1(s.encode("utf-8")).hexdigest()

# EN chapter title -> IT (Chesterton's own chapter titles).
TITLES = {
    "The Man In The Cave": "L'uomo nella caverna",
    "Professors And Prehistoric Men": "I professori e gli uomini preistorici",
    "The Antiquity Of Civilisation": "L'antichità della civiltà",
    "God And Comparative Religion": "Dio e la religione comparata",
    "Man And Mythologies": "L'uomo e le mitologie",
    "The Demons And The Philosophers": "I demoni e i filosofi",
    "The War Of The Gods And Demons": "La guerra degli dèi e dei demoni",
    "The End Of The World": "La fine del mondo",
    "The God In The Cave": "Il Dio nella caverna",
    "The Riddles Of The Gospel": "Gli enigmi del Vangelo",
    "The Strangest Story In The World": "La storia più strana del mondo",
    "The Witness Of The Heretics": "La testimonianza degli eretici",
    "The Escape From Paganism": "La fuga dal paganesimo",
    "The Five Deaths Of The Faith": "Le cinque morti della fede",
    "PREFARATORY NOTE": "Nota preliminare",
    "INTRODUCTION": "Introduzione",
    "CONCLUSION": "Conclusione",
    "APPENDIX I": "Appendice I",
    "APPENDIX II": "Appendice II",
}
# ALL-CAPS in-text titles that appear as their own block, e.g. "THE MAN IN THE [[Cave|CAVE]]".
CAPS_TITLES = {k.upper(): v.upper() for k, v in TITLES.items()}


def it_heading(block):
    """Translate a '# everlasting man - Chapter N: Title [(part M)]' heading to Italian, or None."""
    m = re.match(r"^#\s+everlasting man\s+[—-]\s+Chapter\s+(\d+)(?::\s*(.*?))?\s*(\(part (\d+)\))?$", block.strip())
    if not m:
        return None
    num, title, _, part = m.groups()
    it_title = TITLES.get((title or "").strip(), (title or "").strip())
    head = f"# everlasting man — Capitolo {num}"
    if it_title:
        head += f": {it_title}"
    if part:
        head += f" (parte {part})"
    return head


def it_caps_title(block):
    """Translate a stand-alone ALL-CAPS in-text title block (may carry a wikilink)."""
    plain = re.sub(r"\[\[[^\]|]+\|([^\]]+)\]\]", r"\1", block)
    plain = re.sub(r"\[\[([^\]]+)\]\]", r"\1", plain).strip()
    it = CAPS_TITLES.get(plain.upper())
    return it


def translate_block(block, cache, stats):
    s = block.strip()
    if not s or s.startswith("<nav") or not has_prose(s):
        stats["passthrough"] += 1
        return block                                   # separators, bare roman numerals, nav
    hit = cache.get(sha(s))
    if hit is not None:
        stats["hit"] += 1
        return _reindent(block, hit)
    h = it_heading(s)
    if h is not None:
        stats["heading"] += 1
        return _reindent(block, h)
    c = it_caps_title(s)
    if c is not None:
        stats["caps"] += 1
        return _reindent(block, c)
    stats["miss"] += 1
    stats["misses"].append(s[:70])
    return block                                        # last resort: leave English (rare)


def _reindent(orig, new):
    lead = orig[:len(orig) - len(orig.lstrip())]
    return lead + new.strip()


def main():
    cache = json.load(open(CACHE_JSON, encoding="utf-8"))
    print(f"cache: {len(cache)} EN->IT blocks")
    md_files = [p for p in glob.glob(ATOMS + "/**/*.md", recursive=True)
                if not p.endswith(".it.md") and os.path.basename(p) != "everlasting_man.md"]
    # also the full-work file gets an .it.md
    md_files.append(os.path.join(ATOMS, "everlasting_man.md"))

    total = dict(hit=0, heading=0, caps=0, passthrough=0, miss=0, misses=[], atoms=0, written=0)
    for md in sorted(md_files):
        body = open(md, encoding="utf-8").read()
        parts = split_blocks(clean_body(body))
        out = "".join(translate_block(p, cache, total) for p in parts)
        it_path = md[:-3] + ".it.md"
        open(it_path, "w", encoding="utf-8").write(out.rstrip("\n") + "\n")
        total["atoms"] += 1
        total["written"] += 1
    print(f"atoms rebuilt: {total['written']}")
    print(f"  block hits (cache): {total['hit']} | headings: {total['heading']} | caps titles: {total['caps']}")
    print(f"  passthrough (sep/roman): {total['passthrough']} | MISSES (left EN): {total['miss']}")
    for m in total["misses"][:12]:
        print(f"     miss: {m!r}")


if __name__ == "__main__":
    main()
