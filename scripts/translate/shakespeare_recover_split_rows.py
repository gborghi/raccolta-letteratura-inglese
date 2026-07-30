# -*- coding: utf-8 -*-
"""Recover scenes whose marker ended up INSIDE a table row.

shakespeare_split_absorbed_scenes.py handles the easy shape, where the swallowed scene starts
its own `| *(didascalia)* | N.M Enter ... |` row. But the converter sometimes folded the
marker into the previous speech instead, either as a continuation segment

    | MACBETH | It is concluded...<br>...must find it out tonight. Exit<br><br>3.2 Enter Lady Macbeth and a Servant |

or under a leftover speaker cue

    | ARIEL | 2.2 Enter Caliban, wearing a gaberdine, and with a<br>burden of wood |

or, once in the whole corpus, trailing the previous speech - '| SIR JOHN | Come up into my
chamber. Exeunt 4.6 |' - where the marker is mere litter and the scene starts on the next row.

In the first two the marker begins a <br> segment, so the cut is by segment, not by row. The
translation contract preserves every <br>, so the same segment index applies to the Italian
and the recovered scene needs no retranslation. If the Italian row has fewer segments the
pair is left alone and reported rather than guessed at.

  python shakespeare_recover_split_rows.py [--write] [Play ...]
"""
import os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shakespeare_split_absorbed_scenes import (kg_index, tags_for, parse, write_atom,
                                               retitle, PLAYS, VAULT)

RAW = os.path.join(VAULT, "Authors", "Shakespeare", "_raw")
SCENE = re.compile(r"(?m)^[ \t]*(\d+)\.(\d+)(?=[ \t]|$)")
SD = "| *(didascalia)* | "
# a scene marker trailing a line of text, with real content before it
TAIL = re.compile(r"\S.*\s(\d+)\.(\d+)$")


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


LINKPIPE = re.compile(r"\[\[[^\]]*\]\]")


def cells_of(row):
    """Split a row into its cells. A wikilink alias carries its own '|' ([[Ariel|ARIEL]]),
    so mask links before splitting or the speaker cell comes back cut in half."""
    holes = []

    def stash(m):
        holes.append(m.group(0))
        return "\x00%d\x00" % (len(holes) - 1)

    masked = LINKPIPE.sub(stash, row)
    parts = [p for p in masked.split("|")]
    if parts and not parts[0].strip():
        parts = parts[1:]
    if parts and not parts[-1].strip():
        parts = parts[:-1]
    return [re.sub(r"\x00(\d+)\x00", lambda m: holes[int(m.group(1))], p) for p in parts]


def locate(rows, act, sc):
    """(row index, segment index) of the marker, or None."""
    pat = re.compile(r"^\s*%d\.%d(?=[ \t])" % (act, sc))
    for n, r in enumerate(rows):
        for s, seg in enumerate(r.split("<br>")):
            # segment 0 still carries the '| speaker |' prefix; the marker would open the
            # second cell there, so probe that cell rather than the raw segment
            probe = (cells_of(seg + " |")[1] if s == 0 and len(cells_of(seg + " |")) > 1
                     else seg)
            if pat.match(probe):
                return n, s
    return None


def locate_trailing(rows, act, sc):
    """Row index where the marker sits at the END of a cell - '...Exeunt 4.6 |'.

    One case in the whole corpus (Merry Wives 4.6), but it is invisible to every other rule:
    the scene that follows starts on the NEXT row, and the marker is just litter on this one."""
    pat = re.compile(r"\s%d\.%d\s*\|?\s*$" % (act, sc))
    for n, r in enumerate(rows):
        if pat.search(r):
            return n
    return None


def cut_cell(row, seg_i, act, sc):
    """Split one row at a <br> segment: (row kept above, text of the new scene's first row)."""
    segs = row.split("<br>")
    head, tail = segs[:seg_i], segs[seg_i:]
    if seg_i == 0:
        cs = cells_of(segs[0] + " |")
        speaker, kept_text = cs[0], ""
        tail[0] = cs[1] if len(cs) > 1 else ""
        kept = "| %s |  |" % speaker.strip()
    else:
        kept = "<br>".join(head).rstrip()
        if not kept.endswith("|"):
            kept += " |"
        cs = cells_of(kept)
        kept_text = cs[1].strip() if len(cs) > 1 else ""
    tail[0] = re.sub(r"^\s*%d\.%d\s*" % (act, sc), "", tail[0])
    new = SD + "<br>".join(tail).strip().rstrip("|").strip() + " |"
    return (kept if kept_text else None), new


def recover(pd, act, sc, idx, write):
    target = os.path.join(pd, "Act_%d" % act, "Scene_%d.md" % sc)
    if os.path.exists(target):
        return False
    for dirpath, _, files in os.walk(pd):
        for f in sorted(files):
            if not f.startswith("Scene_") or not f.endswith(".md") or f.endswith(".it.md"):
                continue
            en = os.path.join(dirpath, f)
            fm, head, rows = parse(en)
            if head is None or len(rows) < 3:
                continue
            body = rows[2:]
            hit = locate(body, act, sc)
            trailing = None if hit else locate_trailing(body, act, sc)
            if not hit and trailing is None:
                continue
            n, s = hit if hit else (trailing, None)
            have = set(re.findall(r"  - (\S+)", fm))
            residue = have - tags_for([head] + body, idx)
            plan = []
            for ext in (".md", ".it.md"):
                path = en[:-3] + ext if ext == ".it.md" else en
                if not os.path.exists(path):
                    continue
                fm_x, head_x, rows_x = parse(path)
                body_x = rows_x[2:]
                if len(body_x) != len(body):
                    print("    !! %s row count differs - skipped" % os.path.basename(path))
                    return False
                if s is None:
                    # marker trailing this row: it stays with the row, stripped, and the new
                    # scene simply begins on the next one
                    kept = re.sub(r"\s%d\.%d(\s*\|?\s*)$" % (act, sc), r"\1", body_x[n])
                    a, b = body_x[:n] + [kept], body_x[n + 1:]
                else:
                    if len(body_x[n].split("<br>")) <= s:
                        print("    !! %s has %d segments, need %d - skipped" %
                              (os.path.basename(path), len(body_x[n].split("<br>")), s + 1))
                        return False
                    kept, new_first = cut_cell(body_x[n], s, act, sc)
                    a = body_x[:n] + ([kept] if kept else [])
                    b = [new_first] + body_x[n + 1:]
                plan.append((path, ext == ".it.md", head_x, rows_x[0], rows_x[1], a, b))
            print("    %-40s %d.%d out of %s (row %d, seg %s): %d + %d rows%s" %
                  (os.path.basename(pd), act, sc, os.path.relpath(en, pd), n,
                   "trailing" if s is None else s,
                   len(plan[0][5]), len(plan[0][6]), "" if write else "  [dry]"))
            if not write:
                return True
            for path, it, head_x, hdr, sep, a, b in plan:
                b_head = retitle(head_x, act, sc, it)
                write_atom(path, (tags_for([head_x] + a, idx) & have) | residue,
                           head_x, hdr, sep, a)
                npath = os.path.join(pd, "Act_%d" % act,
                                     "Scene_%d%s" % (sc, ".it.md" if it else ".md"))
                os.makedirs(os.path.dirname(npath), exist_ok=True)
                write_atom(npath, (tags_for([b_head] + b, idx) & have) | residue,
                           b_head, hdr, sep, b)
            return True
    return False


def main(argv):
    write = "--write" in argv
    only = [a for a in argv if not a.startswith("--")]
    idx = kg_index()
    total = 0
    for f in sorted(os.listdir(RAW)):
        if not f.endswith(".md"):
            continue
        pd = play_dir_for(f)
        if not pd or (only and os.path.basename(pd) not in only):
            continue
        raw = read(os.path.join(RAW, f))
        hits = [(int(a), int(b)) for a, b in SCENE.findall(raw)]
        if len(hits) < 2:
            continue
        # a marker can also trail a line of dialogue ('...Exeunt 4.6'), where neither the
        # splitter's rule nor its fixed version sees it
        for line in raw.split("\n"):
            m = TAIL.match(line.strip())
            if m and (int(m.group(1)), int(m.group(2))) not in hits:
                hits.append((int(m.group(1)), int(m.group(2))))
        for act, sc in hits:
            if (act, sc) in scene_set(pd):
                continue
            if recover(pd, act, sc, idx, write):
                total += 1
    print("---- %s: %d scenes recovered" % ("WROTE" if write else "DRY RUN", total))


if __name__ == "__main__":
    main(sys.argv[1:])
