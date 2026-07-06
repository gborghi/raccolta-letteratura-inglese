# -*- coding: utf-8 -*-
"""Generate one author landing page per author under content/authors/<slug>.md:
hero + NLP literary-footprint stats + SVG wordcloud + EN/IT bio/poetics (CSS-only
language tabs) + the works table scoped to that author (#opere-table[data-author])."""
import os, re, json, html

Q = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATS = json.load(open(f"{Q}/quartz/static/author_stats.json", encoding="utf-8"))
BIOS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "author_bios")
OUTDIR = f"{Q}/content/authors"
os.makedirs(OUTDIR, exist_ok=True)
PALETTE = ["#8a5cf6","#2563eb","#0891b2","#059669","#ca8a04","#dc2626","#db2777","#7c3aed","#0d9488","#4f46e5"]

def esc(s): return html.escape(str(s), quote=True)

def wordcloud_svg(words, author):
    W = 680; pad = 16; x = pad; y = 48; line_h = 0
    rows = [[]]
    for i, w in enumerate(words[:28]):
        fs = max(13, round(46 - i * 1.25))
        wpx = len(w) * fs * 0.58 + 16
        if x + wpx > W - pad and rows[-1]:
            rows.append([]); x = pad; y += line_h + 10; line_h = 0
        rows[-1].append((w, fs, x)); x += wpx; line_h = max(line_h, fs)
    # recompute total height + center rows
    svg = []; yy = 44; H = 0
    parts = []
    for ri, row in enumerate(rows):
        if not row: continue
        rh = max(f for _, f, _ in row)
        total_w = row[-1][2] + len(row[-1][0]) * row[-1][1] * 0.58 + 16 - pad
        offset = (W - total_w) / 2 - pad
        for j, (w, fs, xx) in enumerate(row):
            c = PALETTE[(ri * 3 + j) % len(PALETTE)]
            parts.append(f'<text x="{round(xx+offset)}" y="{yy}" font-size="{fs}" fill="{c}" '
                         f'font-weight="{700 if fs>28 else 500}" font-family="Georgia,serif">{esc(w)}</text>')
        yy += rh + 12; H = yy
    return (f'<svg class="author-cloud" viewBox="0 0 {W} {H+8}" width="100%" role="img" '
            f'aria-label="Distinctive words of {esc(author)}">' + "".join(parts) + "</svg>")

STYLE = """<style>
.author-hero{margin:0 0 .3rem}.author-hero h1{margin:.2rem 0}
.author-tagline{color:var(--gray,#888);font-size:.95rem;margin:.2rem 0 1rem}
.author-cloud{display:block;margin:.5rem auto 1.4rem;max-width:720px}
.fp-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:.6rem;margin:1rem 0 1.6rem}
.fp-cell{border:1px solid var(--lightgray,#e5e5e5);border-radius:10px;padding:.6rem .7rem;text-align:center}
.fp-num{font-size:1.5rem;font-weight:700;line-height:1.1}.fp-lab{font-size:.72rem;color:var(--gray,#888);text-transform:uppercase;letter-spacing:.03em}
.fp-tags{margin:.2rem 0 1.4rem}.fp-tags .chip{display:inline-block;background:var(--lightgray,#eee);border-radius:999px;padding:.1rem .6rem;margin:.15rem;font-size:.82rem}
.lang-tabs input{position:absolute;opacity:0;pointer-events:none}
.lang-tabbar{display:flex;gap:.4rem;margin:.4rem 0 .8rem;border-bottom:1px solid var(--lightgray,#e5e5e5)}
.lang-tabbar label{cursor:pointer;padding:.35rem .9rem;border-radius:8px 8px 0 0;font-weight:600;color:var(--gray,#888)}
.lang-pane{display:none}
.lang-tabs input.en:checked~.lang-tabbar label.en,.lang-tabs input.it:checked~.lang-tabbar label.it{color:var(--secondary,#284b8c);border-bottom:2px solid var(--secondary,#284b8c)}
.lang-tabs input.en:checked~.pane-en,.lang-tabs input.it:checked~.pane-it{display:block}
.lang-pane h3{margin:.6rem 0 .2rem;font-size:1.05rem}
</style>"""

def page(author, s, bio):
    slug = author.lower()
    cloud = wordcloud_svg(s.get("distinctive_words", []), author)
    def cell(num, lab): return f'<div class="fp-cell"><div class="fp-num">{num}</div><div class="fp-lab">{lab}</div></div>'
    grid = ('<div class="fp-grid">'
        + cell(f"{s['works']:,}", "works")
        + cell(f"{s['words']:,}", "words")
        + cell(f"{s['vocabulary']:,}", "vocabulary")
        + cell(s["lexical_richness_rttr"], "lexical richness")
        + cell(f"{s['avg_sentence_words']}", "words / sentence")
        + cell(s["avg_word_len"], "avg word length")
        + "</div>")
    concepts = ('<div class="fp-tags">' + "".join(f'<span class="chip">{esc(c)}</span>' for c in s.get("top_concepts", [])[:8]) + "</div>") if s.get("top_concepts") else ""
    tabs = f"""<div class="lang-tabs">
<input type="radio" name="lang-{slug}" id="en-{slug}" class="en" checked>
<input type="radio" name="lang-{slug}" id="it-{slug}" class="it">
<div class="lang-tabbar"><label for="en-{slug}" class="en">English</label><label for="it-{slug}" class="it">Italiano</label></div>
<div class="lang-pane pane-en"><h3>Life</h3><p>{esc(bio['bio_en'])}</p><h3>Poetics</h3><p>{esc(bio['poetics_en'])}</p></div>
<div class="lang-pane pane-it"><h3>Vita</h3><p>{esc(bio['bio_it'])}</p><h3>Poetica</h3><p>{esc(bio['poetics_it'])}</p></div>
</div>"""
    body = f"""---
title: {author}
---
{STYLE}
<div class="author-hero"><h1>{esc(author)}</h1>
<p class="author-tagline">{s['works']:,} works · {s['words']:,} words · {s['sentences']:,} sentences · literary footprint below</p></div>

{cloud}

{grid}
{concepts}

{tabs}

## Works

<div id="opere-table" data-author="{esc(author)}"></div>
"""
    open(f"{OUTDIR}/{slug}.md", "w", encoding="utf-8").write(body)
    return slug

made = []
for author, s in STATS.items():
    bp = f"{BIOS}/{author}.json"
    if not os.path.exists(bp): print("no bio:", author); continue
    bio = json.load(open(bp, encoding="utf-8"))
    made.append(page(author, s, bio))
print("author pages written:", len(made), sorted(made))
