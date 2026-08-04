# -*- coding: utf-8 -*-
"""Build the aggregate .it.md files by CONCATENATING the leaf translations.

Atomization is redundant on purpose (see leafcheck.py): a work exists as the
whole book, as whole chapters, and as the part_NN atoms. Only the leaves are
translated by the model -- the aggregates must never be sent to it, they are
assembled from the leaves they contain. This closes that half of the pipeline.

Shape of a translated file:

    # <titolo> (parte 2)        <- leaves carry the "(parte N)" suffix
    <blank>
    <body>

so a parent is: its own "# <titolo>" (the leaf title minus the suffix) followed
by every child body, in filename order, joined by a blank line. Parents are
built depth-first, so a book can be assembled from chapters that were themselves
just assembled from parts.

A parent is only written when EVERY child has a translation -- a half-assembled
chapter would silently ship a truncated text.

Usage:
  python3 assemble_aggregates.py                 # dry-run, reports what it would do
  python3 assemble_aggregates.py --write         # actually write
  python3 assemble_aggregates.py --author Sayers --verify   # regenerate existing
                                                 # .it.md and diff (self-test)
"""
import os, sys, time, argparse, difflib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from leafcheck import is_leaf, VAULT_ROOT  # noqa: E402
from work_titles import TITLES             # noqa: E402

# "(parte 3)", "(parte 3 di 7)", and the English "(part 3)" the atomizer also emits
import re
from collections import Counter

ORDINALS = ("prima|seconda|terza|quarta|quinta|sesta|settima|ottava|nona|decima"
            "|undicesima|dodicesima|tredicesima|quattordicesima|quindicesima")
PART_SUFFIX = re.compile(
    r"\s*\((?:(?:parte|part)\s+(?:\d+(?:\s+(?:di|of)\s+\d+)?|%s)"
    r"|(?:%s)\s+parte)\)\s*$" % (ORDINALS, ORDINALS), re.IGNORECASE)

# Some parts wear the suffix without its parentheses ("... — Parte 5"). Stripped only when
# COMPARING two children's titles, never in split_title: without the parentheses there is no
# telling it from a work whose sections really are called "Parte 5".
PART_TAIL = re.compile(r"\s*[—]\s*(?:parte|part)\s+\d+\s*$", re.IGNORECASE)

# The model spells the same title with whatever dash and apostrophe it feels like, so two parts of
# one chapter come back as "L’abbazia — Capitolo 2" and "L'abbazia – Capitolo 2". They are the same
# title and must not look like two: normalisation is for COMPARING only, never for what gets
# written -- the winning spelling is the children's own, kept verbatim.
DASHES = {"–": "—", "‒": "—", "−": "—", "-": "—"}
QUOTES = {"’": "'", "‘": "'", "“": '"', "”": '"'}


# "[[Mansfield Park|>Mansfield Park]]": an alias that only repeats its own target, with the
# blockquote marker of the line above swept into it. It renders as ">Mansfield Park" and is
# simply the plain link, so it is unpicked rather than allowed to split one chapter's parts
# into two rival titles.
DEGENERATE_ALIAS = re.compile(r"\[\[([^\]|]+)\|\s*>*\s*([^\]]*?)\s*\]\]")


def _dash(title):
    for src, dst in DASHES.items():
        title = title.replace(src, dst)
    return title


def _delink(title):
    return DEGENERATE_ALIAS.sub(
        lambda m: "[[%s]]" % m.group(1) if m.group(2) == m.group(1).strip() else m.group(0),
        title)


def _norm(title):
    title = _delink(_dash(title))
    for src, dst in QUOTES.items():
        title = title.replace(src, dst)
    title = PART_TAIL.sub("", PART_SUFFIX.sub("", title))
    return " ".join(title.split()).casefold().rstrip(".…")


def _read(path, retries=5, delay=0.4):
    """Dropbox occasionally holds a lock on a file mid-sync; retry briefly."""
    for attempt in range(retries):
        try:
            with open(path, encoding="utf-8") as fh:
                return fh.read()
        except OSError:
            if attempt == retries - 1:
                raise
            time.sleep(delay)


def _write(path, text, retries=5, delay=0.4):
    for attempt in range(retries):
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
            return
        except OSError:
            if attempt == retries - 1:
                raise
            time.sleep(delay)


def strip_frontmatter(text):
    """Drop a leading YAML block. Leaves come in two conventions: Sayers-style
    (H1 first) and Dickens-style (tags frontmatter, then the H1). No aggregate
    carries frontmatter -- the per-leaf tags belong to the leaf, so the parent
    is title + bodies, exactly like its English counterpart."""
    if not text.startswith("---"):
        return text
    end = text.find("\n---", 3)
    if end < 0:
        return text
    return text[end + 4:].lstrip("\n")


def split_title(text):
    """-> (titolo senza '(parte N)', corpo). Titolo None se non c'e' un H1."""
    lines = strip_frontmatter(text).split("\n")
    if not lines or not lines[0].startswith("# "):
        return None, text.strip("\n")
    title = PART_SUFFIX.sub("", lines[0][2:].strip())
    body = "\n".join(lines[1:]).strip("\n")
    return title, body


def children_of(path):
    """The .md files an aggregate is made of, in order. [] if it isn't one."""
    stem = path[:-3]
    if os.path.isdir(stem):
        base = stem
    elif os.path.basename(stem) == os.path.basename(os.path.dirname(path)):
        base = os.path.dirname(path)          # Work/Work.md -> the work dir
    else:
        return []
    out = []
    for e in sorted(os.listdir(base)):
        p = os.path.join(base, e)
        if os.path.isdir(p):
            inner = os.path.join(p, os.path.basename(p) + ".md")
            if os.path.exists(inner):         # a sub-work with its own book file
                out.append(inner)
            continue
        if e.endswith(".md") and not e.endswith(".it.md") and p != path:
            out.append(p)
    # a chapter dir holds both Chapter_07.md and Chapter_07/: keep the .md, the
    # directory is reached through it
    seen, uniq = set(), []
    for p in out:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq


def assemble(path, stats, write=False, force=False):
    """Ensure path's .it.md exists, building children first. -> True if present.

    walk_aggregates yields the chapter file AND the book that recurses into it, so every
    aggregate is reached more than once; memoised, or the report counts each of them twice.
    """
    if path not in stats["seen"]:
        stats["seen"][path] = _assemble(path, stats, write, force)
    return stats["seen"][path]


def _assemble(path, stats, write, force):
    it_path = path[:-3] + ".it.md"
    if is_leaf(os.path.relpath(path, VAULT_ROOT), VAULT_ROOT):
        return os.path.exists(it_path)

    kids = children_of(path)
    if not kids:
        return os.path.exists(it_path)

    ok = [assemble(k, stats, write, force) for k in kids]
    if not all(ok):
        stats["incomplete"].append((os.path.relpath(path, VAULT_ROOT),
                                    sum(1 for x in ok if not x), len(kids)))
        return os.path.exists(it_path)

    if os.path.exists(it_path) and not force:
        return True

    titles, bodies = [], []
    for k in kids:
        kit = k[:-3] + ".it.md"
        # under dry-run the child was "built" in memory only, so read it back
        # from there -- otherwise every book-level aggregate would look blocked
        t, b = split_title(stats["texts"][kit] if kit in stats["texts"]
                           else _read(kit))
        if t:
            titles.append(t)
        if b:
            bodies.append(b)
    title = parent_title(titles, path)
    if title is None:
        stats["no_title"].append(os.path.relpath(path, VAULT_ROOT))
        return False

    text = "# %s\n\n%s\n" % (title, "\n\n".join(bodies))
    if write:
        _write(it_path, text)
    else:
        stats["texts"][it_path] = text
    stats["built"].append((os.path.relpath(path, VAULT_ROOT), len(text), len(kids)))
    return True


def parent_title(titles, path):
    """The parent's own title, derived from the children's -- never invented.

    parts of a chapter all share the chapter title once '(parte N)' is stripped;
    chapters of a book share the 'Book -- Chapter n: ...' prefix. Both are decided on the
    NORMALISED titles (see _norm) so that a stray curly apostrophe in one part of a chapter
    doesn't make it look like a different chapter from the other part, and answered with a
    raw title exactly as one child wrote it.

    A single odd sibling out of many is a mistranslated title, not a different chapter, so a
    strict majority wins -- the alternative, refusing to build, throws away a whole correct
    book for one bad heading. Without a majority nothing is guessed and the parent is skipped,
    unless a human already wrote the title down in work_titles.TITLES.
    """
    curated = TITLES.get(os.path.relpath(path, VAULT_ROOT).replace(os.sep, "/"))
    if curated:
        return curated
    if not titles:
        return None
    groups = {}
    for t in titles:
        groups.setdefault(_norm(t), []).append(t)
    best = max(groups.values(), key=len)
    if len(best) * 2 > len(titles):
        # among identical titles prefer the one with the fewest degenerate links, so a stray
        # ">" swept into an alias by one part never becomes the whole chapter's heading
        return min(Counter(best).most_common(),
                   key=lambda kv: (len(kv[0]) - len(_delink(kv[0])), -kv[1]))[0]

    sep = " — "
    split = [_dash(t).split(sep, 1) for t in titles]
    if any(len(s) != 2 for s in split):
        return None
    works, rests = [s[0] for s in split], [s[1] for s in split]

    # different chapters of one book: keep what they agree on, the work part. A majority and not
    # unanimity, because one chapter left with an untranslated "BEYOND THE CITY" among sixteen
    # "OLTRE LA CITTÀ" would otherwise cost the book its title.
    heads = {}
    for w in works:
        heads.setdefault(_norm(w), []).append(w)
    top = max(heads.values(), key=len)
    if len(top) * 2 > len(works) and top[0]:
        return Counter(top).most_common(1)[0][0]

    # Same chapter, and the parts agree on WHICH chapter -- they only disagree on how the work
    # itself is called ("La Nuova Gerusalemme" / "Nuova Gerusalemme"). That is a property of the
    # work, not of this chapter, so it is settled once across every chapter of the work rather
    # than by whichever of two parts happens to come first.
    if len({_norm(r) for r in rests}) == 1:
        winner = work_part_vote(path)
        if winner:
            return winner + sep + Counter(rests).most_common(1)[0][0]
    return None


_WORK_VOTE = {}


def work_part_vote(path):
    """The spelling the work's own chapters use most for the part before the em dash."""
    work = os.path.dirname(path)
    while os.path.basename(os.path.dirname(work)) not in ("Atomized", ""):
        work = os.path.dirname(work)
    if work not in _WORK_VOTE:
        # grouped by _norm first: counting raw spellings would let "La Locanda Volante" and
        # "La locanda volante" split the Italian vote and hand the work to an English straggler
        votes = {}
        for root, _dirs, files in os.walk(work):
            for f in files:
                if not f.endswith(".it.md"):
                    continue
                t, _b = split_title(_read(os.path.join(root, f)))
                if t and " — " in _dash(t):
                    head = _dash(t).split(" — ", 1)[0]
                    votes.setdefault(_norm(head), Counter())[head] += 1
        top = sorted(votes.values(), key=lambda c: -sum(c.values()))[:2]
        _WORK_VOTE[work] = (top[0].most_common(1)[0][0]
                            if top and (len(top) == 1 or
                                        sum(top[0].values()) > sum(top[1].values()))
                            else None)
    return _WORK_VOTE[work]


def walk_aggregates(author=None):
    base = os.path.join(VAULT_ROOT, "Authors")
    for name in sorted(os.listdir(base)):
        if author and name != author:
            continue
        atom = os.path.join(base, name, "Atomized")
        if not os.path.isdir(atom):
            continue
        for root, _dirs, files in os.walk(atom):
            for f in sorted(files):
                if not f.endswith(".md") or f.endswith(".it.md"):
                    continue
                p = os.path.join(root, f)
                if not is_leaf(os.path.relpath(p, VAULT_ROOT), VAULT_ROOT):
                    yield p


def verify(author):
    """Regenerate aggregates that already have a .it.md and diff -- self-test."""
    same = diff = skipped = 0
    for p in walk_aggregates(author):
        it_path = p[:-3] + ".it.md"
        if not os.path.exists(it_path):
            continue
        kids = children_of(p)
        if not kids or not all(os.path.exists(k[:-3] + ".it.md") for k in kids):
            skipped += 1
            continue
        titles, bodies = [], []
        for k in kids:
            t, b = split_title(_read(k[:-3] + ".it.md"))
            if t:
                titles.append(t)
            if b:
                bodies.append(b)
        title = parent_title(titles, p)
        if title is None:
            skipped += 1
            continue
        got = "# %s\n\n%s\n" % (title, "\n\n".join(bodies))
        want = _read(it_path)
        if got.strip() == want.strip():
            same += 1
        else:
            diff += 1
            if diff <= 2:
                print("=== DIVERGE: %s" % os.path.relpath(p, VAULT_ROOT))
                d = difflib.unified_diff(want.split("\n"), got.split("\n"),
                                         "esistente", "assemblato", lineterm="", n=1)
                for i, line in enumerate(d):
                    if i > 40:
                        print("   ...")
                        break
                    print("   " + line[:160])
    print("verify %s: identici %d | divergenti %d | non confrontabili %d"
          % (author or "tutti", same, diff, skipped))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--author", default=None)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--force", action="store_true", help="rebuild existing .it.md")
    ap.add_argument("--verify", action="store_true")
    a = ap.parse_args()

    if a.verify:
        return verify(a.author)

    stats = {"built": [], "incomplete": [], "no_title": [], "texts": {}, "seen": {}}
    for p in walk_aggregates(a.author):
        assemble(p, stats, a.write, a.force)

    tag = "scritti" if a.write else "da scrivere (dry-run)"
    print("aggregati %s: %d" % (tag, len(stats["built"])))
    for rel, n, k in stats["built"][:5]:
        print("   %s  (%d B da %d figli)" % (rel, n, k))
    if stats["incomplete"]:
        print("\nbloccati da figli non tradotti: %d" % len(stats["incomplete"]))
        for rel, miss, tot in stats["incomplete"][:5]:
            print("   %s  (%d/%d figli senza .it.md)" % (rel, miss, tot))
    if stats["no_title"]:
        print("\nsenza titolo derivabile dai figli: %d" % len(stats["no_title"]))
        for rel in stats["no_title"][:5]:
            print("   %s" % rel)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
