# -*- coding: utf-8 -*-
r"""Atomize scenes that never became atoms at all.

Where the FIRST scene marker of a play (or of an act) sat inline with its stage direction,
the old splitter's first match landed further down the text and everything above it was never
written to any atom -- it survives only inside the play-level <Play>.md. Seven scenes are in
this state, among them the opening scenes of Titus Andronicus, King John, Cymbeline, Henry
VIII and The Two Noble Kinsmen.

The scene is rebuilt from the raw with the same converter the vault was built with. Two
things have changed since that build: the raw is now linkified, and the converter reads a
speaker cue by its capitals -- so '[[Saturninus|SATURNINUS]]' is not recognised and a whole
speech is filed as a stage direction. So its speaker test is wrapped to run on the rendered
text while the cue keeps its markup, and the converter's pipe-escaping (`\|` inside a cell,
which no existing atom has) is undone afterwards. No link may be lost in the process, or the
scene is skipped rather than written wrong.

The play-level <Play>.md is NOT a usable source here: for most plays it is a verbatim copy of
the raw, not a finished table.

No .it.md is produced: this text has never been translated. Translate these scenes afterwards
for the plays that are otherwise complete.

  python shakespeare_atomize_missing_scenes.py [--write]
"""
import collections, os, re, sys, importlib.util

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shakespeare_split_absorbed_scenes import kg_index, tags_for, parse, ROMAN, VAULT, PLAYS
from shakespeare_recover_split_rows import cells_of

RAW = os.path.join(VAULT, "Authors", "Shakespeare", "_raw")
SCENE = re.compile(r"(?m)^[ \t]*(\d+)\.(\d+)(?=[ \t]|$)")
HDR, SEP = "| Chi parla | Battuta |", "|---|---|"


def read(p):
    with open(p, encoding="utf-8") as fh:
        return fh.read()


def play_dir_for(raw_name):
    stem = re.sub(r"^\d+_", "", raw_name[:-3]).replace("(", "").replace(")", "")
    d = os.path.join(PLAYS, re.sub(r"_+", "_", stem))
    return d if os.path.isdir(d) else None


def scene_set(pd):
    have = set()
    for dirpath, _, files in os.walk(pd):
        for f in files:
            if f.startswith("Scene_") and f.endswith(".md") and not f.endswith(".it.md"):
                a = re.search(r"Act_(\d+)", os.path.join(dirpath, f))
                s = re.search(r"Scene_(\d+)\.md$", f)
                have.add((int(a.group(1)) if a else 0, int(s.group(1))))
    return have


def title_from_sibling(pd):
    """The play name exactly as the existing atoms' headings spell it, links and all."""
    for dirpath, _, files in os.walk(pd):
        for f in sorted(files):
            if f.startswith("Scene_") and f.endswith(".md") and not f.endswith(".it.md"):
                _, head, _ = parse(os.path.join(dirpath, f))
                if head:
                    return re.sub(r"^#\s*", "", head).split(" — ")[0]
    return os.path.basename(pd).replace("_", " ")


TARGETS = re.compile(r"\[\[([^\]|#]+)(?:\|[^\]]*)?\]\]")
LINKTEXT = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]*))?\]\]")
TOKEN = re.compile(r"\[\[[^\]]*\]\]\S*|\S+")


def visible(s):
    """The text as rendered: [[Saturninus|SATURNINUS]] -> SATURNINUS."""
    return LINKTEXT.sub(lambda m: m.group(2) or m.group(1), s)


def link_aware_split_speaker(orig_fn):
    """Teach the converter's speaker test to see through wikilinks.

    It decides a speaker cue by looking for capitals, so a linkified cue is invisible to it
    and the speech is filed as a stage direction. Stripping the links before conversion and
    restoring them by label afterwards does not work either: the same label also appears as a
    plain, unlinked cue elsewhere in the scene, and restoring by label invents links that the
    source never had. So the test runs on the rendered text while the cue keeps its original
    markup, matched token by token (a link may render as several tokens)."""
    def patched(s):
        r = orig_fn(visible(s))
        if not r:
            return None
        need, used, end = len(r[0].split()), 0, 0
        # a link is ONE token however many words it renders as: '[[King John|KING JOHN]]'
        # renders two, and splitting on whitespace would cut the cue in half mid-link
        for tok in TOKEN.finditer(s):
            if used >= need:
                break
            used += len(visible(tok.group(0)).split())
            end = tok.end()
        if used != need:
            return None
        return s[:end].strip(), s[end:].strip()
    return patched


def load_converter():
    """The very converter the vault was built with, loaded from the graph-build tree."""
    spec = importlib.util.spec_from_file_location(
        "play_to_table", os.path.join(VAULT, "graphify-out", "lit", "play_to_table.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.split_speaker = link_aware_split_speaker(mod.split_speaker)
    return mod


def convert_slice(slice_text, p2t):
    """Table one scene of raw text, with the linkified cues protected and the converter's
    pipe-escaping undone. Returns (rows, problem)."""
    table = p2t.convert_block(slice_text).replace("\\|", "|")
    rows = [l for l in table.split("\n") if l.startswith("|")][2:]
    if len(rows) < 1:
        return None, "converter produced no table"

    # Nothing may be lost. Something may be gained, but only a speaker link: a speech resumed
    # after a stage direction gets its speaker cell repeated, and with a linkified cue that
    # legitimately multiplies the link. Anything else gained means text was mangled.
    src = collections.Counter(TARGETS.findall(slice_text))
    got = collections.Counter(TARGETS.findall("\n".join(rows)))
    speakers = set()
    for r in rows:
        cs = cells_of(r)
        if cs:
            speakers |= set(TARGETS.findall(cs[0]))
    lost = src - got
    if lost:
        return None, "links lost: %s" % sorted(lost)[:6]
    gained = set(got - src) - speakers
    if gained:
        return None, "links invented outside speaker cells: %s" % sorted(gained)[:6]
    return rows, None


def main(write):
    idx = kg_index()
    p2t = load_converter()
    total = 0
    for f in sorted(os.listdir(RAW)):
        if not f.endswith(".md"):
            continue
        pd = play_dir_for(f)
        if not pd:
            continue
        text = read(os.path.join(RAW, f))
        ms = list(SCENE.finditer(text))
        if len(ms) < 2:
            continue
        have = scene_set(pd)
        title = title_from_sibling(pd)
        for i, m in enumerate(ms):
            act, sc = int(m.group(1)), int(m.group(2))
            if (act, sc) in have:
                continue
            end = ms[i + 1].start() if i + 1 < len(ms) else len(text)
            rows, problem = convert_slice(text[m.end():end].strip(), p2t)
            if problem:
                print("    %-40s %d.%d SKIPPED - %s" %
                      (os.path.basename(pd), act, sc, problem))
                continue
            head = "# %s — Act %s, Scene %d" % (title, ROMAN[act], sc)
            tags = tags_for([head] + rows, idx)
            out = os.path.join(pd, "Act_%d" % act, "Scene_%d.md" % sc)
            print("    %-40s %d.%d -> %s  (%d rows, %d tags)%s" %
                  (os.path.basename(pd), act, sc, os.path.relpath(out, PLAYS),
                   len(rows), len(tags), "" if write else "  [dry]"))
            total += 1
            if not write:
                continue
            os.makedirs(os.path.dirname(out), exist_ok=True)
            with open(out, "w", encoding="utf-8") as fh:
                fh.write("---\ntags:\n" + "".join("  - %s\n" % t for t in sorted(tags)) +
                         "---\n\n" + head + "\n\n" + HDR + "\n" + SEP + "\n" +
                         "\n".join(rows) + "\n")
    print("---- %s: %d scenes atomized (no .it.md - these need translating)" %
          ("WROTE" if write else "DRY RUN", total))


if __name__ == "__main__":
    main("--write" in sys.argv)
