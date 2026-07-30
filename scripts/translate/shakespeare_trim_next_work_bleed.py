# -*- coding: utf-8 -*-
"""Cut the next work's opening off the end of each Shakespeare work.

The per-work split of the source overshot: NNN_Work.md runs on into work NNN+1's caps title,
editorial introduction and THE PERSONS OF THE PLAY. play_to_table.py then reads that caps
title as a SPEAKER cue, so the neighbouring play's dramatis personae end up as a speech
inside this play's last scene -- and its characters end up in that scene's tags.

Nothing is lost by cutting: the next work's own file starts with the identical block.

Anchor: the first long line of the next work's introduction. A whole sentence is unique and,
unlike the title, is spelled the same in both files (titles differ - '[[Henry V|HENRY V]]'
vs 'HENRY V' - which is why matching on the title misses a third of the cases).

Targets, per play: the raw file, the play-level <Play>.md, the last scene atom, and every
.it.md sibling (cut at the same row index, which the one-row-per-row contract guarantees).

  python shakespeare_trim_next_work_bleed.py           # dry run
  python shakespeare_trim_next_work_bleed.py --write
"""
import os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shakespeare_split_absorbed_scenes import kg_index, tags_for

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
VAULT = os.path.abspath(os.path.join(ROOT, "..", "VaultEnglish"))
RAW = os.path.join(VAULT, "Authors", "Shakespeare", "_raw")
PLAYS = os.path.join(VAULT, "Authors", "Shakespeare", "Plays")
IDX = None

ANCHOR_MIN = 60          # a line this long is a sentence, not a title or a stage direction
PROBE = 48               # how much of it to match inside a table cell


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def norm(s):
    """Cell separators are invisible to the anchor: when the bled sentence starts with a
    caps word ('SHORTLY after James VI...') play_to_table reads that word as the speaker and
    the sentence arrives split across '|', so a raw substring match misses it."""
    return re.sub(r"\s+", " ", s.replace("|", " ").replace("<br>", " ")).strip()


def find_line(lines, nprobe):
    return next((n for n, l in enumerate(lines) if nprobe in norm(l)), None)


def anchor_of(raw_path):
    """First sentence of this work's editorial introduction."""
    lines = read(raw_path).split("\n")
    for l in lines[1:12]:
        s = l.strip()
        if len(s) >= ANCHOR_MIN:
            return s
    return None


def play_dir_for(raw_name):
    stem = re.sub(r"^\d+_", "", raw_name[:-3])
    stem = stem.replace("(", "").replace(")", "")
    cand = os.path.join(PLAYS, stem)
    if os.path.isdir(cand):
        return cand
    # 002_The_First_Part_of_the_Contention_(2_Henry_VI) -> ..._2_Henry_VI
    stem2 = re.sub(r"_+", "_", stem)
    cand = os.path.join(PLAYS, stem2)
    return cand if os.path.isdir(cand) else None


def scene_atoms(play_dir):
    out = []
    for dirpath, _, files in os.walk(play_dir):
        for f in files:
            if f.startswith("Scene_") and f.endswith(".md") and not f.endswith(".it.md"):
                out.append(os.path.join(dirpath, f))

    def key(p):
        act = re.search(r"Act_(\d+)", p)
        sc = re.search(r"Scene_(\d+)\.md$", p)
        return (int(act.group(1)) if act else 0, int(sc.group(1)) if sc else 0)
    return sorted(out, key=key)


def cut_lines(path, nprobe, write, label):
    """Drop from the anchor line to EOF. Returns the index cut at."""
    lines = read(path).split("\n")
    i = find_line(lines, nprobe)
    if i is None:
        return None
    if write:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines[:i]).rstrip("\n") + "\n")
    print("    %-58s cut %d lines %s" % (label, len(lines) - i, "" if write else "[dry]"))
    return i


def cut_rows(en_path, nprobe, write):
    """Drop the table rows from the bleed on, in the EN atom and its IT sibling."""
    lines = read(en_path).split("\n")
    i = next((n for n, l in enumerate(lines)
              if l.startswith("|") and nprobe in norm(l)), None)
    if i is None:
        return None
    rows_before = sum(1 for l in lines[:i] if l.startswith("|"))
    new_tags = None
    for path in (en_path, en_path[:-3] + ".it.md"):
        if not os.path.exists(path):
            continue
        ls = read(path).split("\n")
        # same row ordinal in the Italian, which has one row per English row
        idx, seen = None, 0
        for n, l in enumerate(ls):
            if l.startswith("|"):
                if seen == rows_before:
                    idx = n
                    break
                seen += 1
        if idx is None:
            print("    !! %s has no row #%d" % (os.path.basename(path), rows_before))
            continue
        kept, dropped = ls[:idx], ls[idx:]
        # the foreign play's characters are in this atom's tags; drop only what the removed
        # rows alone accounted for, so Phase-2 tags with no wikilink behind them survive
        fm = re.match(r"^---\n.*?\n---\n", "\n".join(kept), re.S)
        if fm:
            have = set(re.findall(r"  - (\S+)", fm.group(0)))
            # decided on the English and reused verbatim for the Italian: the two frontmatter
            # blocks must stay byte-identical or the checker fails the pair
            if new_tags is None:
                new_tags = have - (tags_for(dropped, IDX) - tags_for(kept, IDX))
            new = new_tags
            if new != have:
                body = "\n".join(kept)[fm.end():]
                kept = ("---\ntags:\n" + "".join("  - %s\n" % t for t in sorted(new)) +
                        "---\n" + body).split("\n")
                print("    %-58s -%d tags (%s)" % ("", len(have - new),
                                                   ", ".join(sorted(have - new)[:5])))
        if write:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("\n".join(kept).rstrip("\n") + "\n")
        print("    %-58s cut %d rows %s" % (os.path.relpath(path, PLAYS),
                                            sum(1 for l in dropped if l.startswith("|")),
                                            "" if write else "[dry]"))
    return i


def main(write):
    global IDX
    IDX = kg_index()
    files = sorted(f for f in os.listdir(RAW) if f.endswith(".md"))
    touched = 0
    for i, f in enumerate(files[:-1]):
        anchor = anchor_of(os.path.join(RAW, files[i + 1]))
        if not anchor:
            print("%s: next work has no anchor line" % files[i + 1])
            continue
        probe = norm(anchor)[:PROBE]
        raw_path = os.path.join(RAW, f)
        if find_line(read(raw_path).split("\n"), probe) is None:
            continue
        print("%s  <- bleeding %s" % (f, files[i + 1]))
        touched += 1
        cut_lines(raw_path, probe, write, "_raw/" + f)
        pd = play_dir_for(f)
        if not pd:
            print("    (no play dir - poems/sonnets, raw only)")
            continue
        hit = False
        pl = os.path.join(pd, os.path.basename(pd) + ".md")
        if os.path.exists(pl) and find_line(read(pl).split("\n"), probe) is not None:
            hit = True
            if cut_rows(pl, probe, write) is None:
                cut_lines(pl, probe, write, os.path.relpath(pl, PLAYS))
        # the bleed lands in whichever atom the tail fell into - usually the last, but
        # check them all rather than assume
        for atom in scene_atoms(pd):
            if find_line(read(atom).split("\n"), probe) is not None:
                hit = True
                cut_rows(atom, probe, write)
        if not hit:
            print("    (raw only - bleed never reached the vault)")
    print("---- %s: %d works trimmed" % ("WROTE" if write else "DRY RUN", touched))


if __name__ == "__main__":
    main("--write" in sys.argv)
