# -*- coding: utf-8 -*-
"""Compute an NLP 'literary footprint' per author from the atomized corpus.
Metrics: works, total words, vocabulary, lexical richness (TTR + root-TTR),
avg sentence length, avg word length, top distinctive words (TF-IDF across the
authors), and top graph concepts/motifs/topoi (from Work-note tags). Writes
quartz/static/author_stats.json for the author landing pages."""
import os, re, glob, json, math
from collections import Counter, defaultdict

# Paths derive from this file's location so the script runs from any cwd:
# <repo parent>/quartz-eng-lit/scripts/nlp-footprint.py -> vault is the sibling VaultEnglish/.
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
VAULT_ROOT = os.path.abspath(os.path.join(ROOT, "..", "VaultEnglish"))
AUTHORS_DIR = os.path.join(VAULT_ROOT, "Authors")
WORKS = os.path.join(VAULT_ROOT, "Knowledge Graph", "Works")
STATIC = os.path.join(ROOT, "quartz", "static")
OUT = os.path.join(STATIC, "author_stats.json")
# Folder names may use underscores; the site keys authors by the spaced form.
PRETTY = lambda d: d.replace("_", " ")

STOP = set(("the a an and or but if then else of to in on at by for with from as is are was were be been being this that these those it its i you he she we they them his her their our your my me him us not no nor so too very can will would should could may might must shall do does did have has had having about into over under out up down off again further once here there when where why how all any both each few more most other some such only own same than that then thus yet also upmost thou thee thy hath doth shall unto o oh ye "
    "which what who whom whose said says one two upon now like man men come came go went see saw know knew think thought said say tell told make made take took give gave will would could should shall must may might let us mrs mr dr sir lady much many little great good old new day night time life man old long thing things way ways part place come "
    "html split work works word words body div span class href http https www com net org didascalia parla battuta chi scena atto entra esce").split())
WORD = re.compile(r"[a-zA-Z']+")

def syllables(w):
    w = re.sub(r"[^a-z]", "", w.lower())
    if not w: return 0
    if len(w) <= 3: return 1
    w = re.sub(r"(?:[^laeiouy]es|ed|[^laeiouy]e)$", "", w)
    w = re.sub(r"^y", "", w)
    return max(1, len(re.findall(r"[aeiouy]{1,2}", w)))

def clean(t):
    t = re.sub(r"^#.*$", " ", t, flags=re.M)              # headings
    t = re.sub(r"\[\[([^\]|]+\|)?([^\]]+)\]\]", r"\2", t)  # wikilinks -> display
    t = re.sub(r"[*_`>#\-]+", " ", t)
    return t

def author_atoms(author):
    base = f"{AUTHORS_DIR}/{author}"
    def scan(raw_only):
        out = []
        for p in glob.glob(base + "/**/*.md", recursive=True):
            if p.endswith(".it.md"): continue
            is_raw = "/_raw/" in p.replace("\\", "/")
            if raw_only != is_raw: continue
            b = os.path.basename(p)[:-3]; d = os.path.basename(os.path.dirname(p))
            if b == d or os.path.isdir(os.path.join(os.path.dirname(p), b)): continue  # skip aggregates
            try: out.append(clean(open(p, encoding="utf-8", errors="replace").read()))
            except Exception: pass
        return out
    texts = scan(False)                 # normal: atomized/Long tree, skip _raw
    if not texts:                       # poet with no atomized tree (e.g. Dickinson):
        texts = scan(True)              # her individual _raw poem files ARE the atoms
    return texts

AUTHORS = [d for d in os.listdir(AUTHORS_DIR) if os.path.isdir(f"{AUTHORS_DIR}/{d}")]

# author -> token list, doc freq for TF-IDF. Read+clean each author's atoms ONCE
# and cache them (reused below for the sentence split).
tokens = {}
tf = {}
atoms_by_au = {}
for au in AUTHORS:
    ats = author_atoms(au)
    atoms_by_au[au] = ats
    toks = []
    for t in ats:
        toks += [w.lower() for w in WORD.findall(t) if len(w) > 2]
    tokens[au] = toks
    tf[au] = Counter(w for w in toks if w not in STOP)

# IDF over authors
df = Counter()
for au in AUTHORS:
    for w in set(tf[au]): df[w] += 1
N = len(AUTHORS)
def idf(w): return math.log(N / df[w]) if df[w] else 0   # words in ALL authors -> 0 (killed)

# concept tags per author from Work notes
tagc = defaultdict(Counter)
for wf in glob.glob(WORKS + "/*.md"):
    h = open(wf, encoding="utf-8", errors="replace").read(2500)
    am = re.search(r'author:\s*"?(.+?)"?\s*$', h, re.M)
    if not am: continue
    au = am.group(1).strip()
    for tag in re.findall(r'- (concept|topos|motif)/([a-z0-9_]+)', h):
        tagc[au][tag[1].replace("_", " ")] += 1

stats = {}
for au in AUTHORS:
    toks = tokens[au]
    n = len(toks)
    if n == 0: continue
    vocab = len(set(toks))
    # root TTR (Guiraud) — stable across text length
    rttr = round(vocab / math.sqrt(n), 1)
    ttr = round(vocab / n, 4)
    # sentences: approximate from joined cleaned text (reuse the cached atoms)
    full = " ".join(atoms_by_au[au])
    sents = [s for s in re.split(r"[.!?]+", full) if len(WORD.findall(s)) > 0]
    ns = max(1, len(sents))
    avg_sent = round(n / ns, 1)
    # readability (syllable-based)
    syl = sum(syllables(w) for w in toks)
    complex_w = sum(1 for w in toks if syllables(w) >= 3)
    W = n / ns                 # words per sentence
    Sy = syl / n               # syllables per word
    flesch = round(206.835 - 1.015 * W - 84.6 * Sy, 1)
    fk_grade = round(0.39 * W + 11.8 * Sy - 15.59, 1)
    fog = round(0.4 * (W + 100 * complex_w / n), 1)
    pct_complex = round(100 * complex_w / n, 1)
    distinctive = [w for w, _ in sorted(tf[au].items(), key=lambda x: -x[1] * idf(x[0]))[:30]]
    top_concepts = [c for c, _ in tagc[PRETTY(au)].most_common(10)]
    stats[PRETTY(au)] = {
        "works": None,
        "lexical_richness_rttr": rttr,
        "avg_sentence_words": avg_sent,
        "flesch_reading_ease": flesch,
        "flesch_kincaid_grade": fk_grade,
        "gunning_fog": fog,
        "pct_complex_words": pct_complex,
        "distinctive_words": distinctive, "top_concepts": top_concepts,
        "words": n, "sentences": len(sents),  # kept for tagline, not shown as a stat cell
    }

# works count from index.json
idx = json.load(open(os.path.join(STATIC, "index.json"), encoding="utf-8"))
wc = Counter(w.get("author", "") for w in (idx if isinstance(idx, list) else idx.values()))
for au in stats: stats[au]["works"] = wc.get(au, 0)

json.dump(stats, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("author_stats.json written for", len(stats), "authors")
for au in sorted(stats, key=lambda a: -stats[a]["words"]):
    s = stats[au]
    print(f"  {au:12} works={s['works']:4} rTTR={s['lexical_richness_rttr']:6} "
          f"Flesch={s['flesch_reading_ease']:6} FK={s['flesch_kincaid_grade']:5} Fog={s['gunning_fog']:5} "
          f"sent~{s['avg_sentence_words']:5}w")
