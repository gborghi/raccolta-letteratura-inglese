# -*- coding: utf-8 -*-
"""Compute an NLP 'literary footprint' per author from the atomized corpus.
Metrics: works, total words, vocabulary, lexical richness (TTR + root-TTR),
avg sentence length, avg word length, top distinctive words (TF-IDF across the 13
authors), and top graph concepts/motifs/topoi (from Work-note tags). Writes
quartz/static/author_stats.json for the author landing pages."""
import os, re, glob, json, math
from collections import Counter, defaultdict

AUTHORS_DIR = "E:/giovanni/Dropbox/insegnamento/Wiligelmo/SubjectBrain/English/Authors"
WORKS = "E:/giovanni/Dropbox/insegnamento/Wiligelmo/SubjectBrain/English/Knowledge Graph/Works"
OUT = "E:/giovanni/Dropbox/insegnamento/Wiligelmo/SubjectBrain/quartz-eng-lit/quartz/static/author_stats.json"

STOP = set(("the a an and or but if then else of to in on at by for with from as is are was were be been being this that these those it its i you he she we they them his her their our your my me him us not no nor so too very can will would should could may might must shall do does did have has had having about into over under out up down off again further once here there when where why how all any both each few more most other some such only own same than that then thus yet also upmost thou thee thy hath doth shall unto o oh ye "
    "which what who whom whose said says one two upon now like man men come came go went see saw know knew think thought said say tell told make made take took give gave will would could should shall must may might let us mrs mr dr sir lady much many little great good old new day night time life man old long thing things way ways part place come "
    "html split work works word words body div span class href http https www com net org didascalia parla battuta chi scena atto entra esce").split())
WORD = re.compile(r"[a-zA-Z']+")

def clean(t):
    t = re.sub(r"^#.*$", " ", t, flags=re.M)              # headings
    t = re.sub(r"\[\[([^\]|]+\|)?([^\]]+)\]\]", r"\2", t)  # wikilinks -> display
    t = re.sub(r"[*_`>#\-]+", " ", t)
    return t

def author_atoms(author):
    base = f"{AUTHORS_DIR}/{author}"
    texts = []
    for p in glob.glob(base + "/**/*.md", recursive=True):
        if p.endswith(".it.md") or "/_raw/" in p.replace("\\", "/"): continue
        b = os.path.basename(p)[:-3]; d = os.path.basename(os.path.dirname(p))
        if b == d or os.path.isdir(os.path.join(os.path.dirname(p), b)): continue  # skip aggregates
        try: texts.append(clean(open(p, encoding="utf-8", errors="replace").read()))
        except Exception: pass
    return texts

AUTHORS = [d for d in os.listdir(AUTHORS_DIR) if os.path.isdir(f"{AUTHORS_DIR}/{d}")]

# author -> token list, doc freq for TF-IDF
tokens = {}
tf = {}
for au in AUTHORS:
    toks = []
    for t in author_atoms(au):
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
    # sentences: approximate from joined cleaned text
    full = " ".join(author_atoms(au))
    sents = [s for s in re.split(r"[.!?]+", full) if len(WORD.findall(s)) > 0]
    avg_sent = round(n / max(1, len(sents)), 1)
    avg_wordlen = round(sum(len(w) for w in toks) / n, 2)
    distinctive = [w for w, _ in sorted(tf[au].items(), key=lambda x: -x[1] * idf(x[0]))[:30]]
    top_concepts = [c for c, _ in tagc[au].most_common(10)]
    stats[au] = {
        "works": None, "words": n, "vocabulary": vocab,
        "lexical_richness_rttr": rttr, "ttr": ttr,
        "avg_sentence_words": avg_sent, "avg_word_len": avg_wordlen,
        "distinctive_words": distinctive, "top_concepts": top_concepts,
        "sentences": len(sents),
    }

# works count from index.json
idx = json.load(open("E:/giovanni/Dropbox/insegnamento/Wiligelmo/SubjectBrain/quartz-eng-lit/quartz/static/index.json", encoding="utf-8"))
wc = Counter(w.get("author", "") for w in (idx if isinstance(idx, list) else idx.values()))
for au in stats: stats[au]["works"] = wc.get(au, 0)

json.dump(stats, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("author_stats.json written for", len(stats), "authors")
for au in sorted(stats, key=lambda a: -stats[a]["words"]):
    s = stats[au]
    print(f"  {au:12} works={s['works']:4} words={s['words']:8} vocab={s['vocabulary']:6} "
          f"rTTR={s['lexical_richness_rttr']:6} sent~{s['avg_sentence_words']:5}w  top:{s['distinctive_words'][:5]}")
