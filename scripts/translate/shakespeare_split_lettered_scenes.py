# -*- coding: utf-8 -*-
"""Split out the editorial half-scenes numbered with a letter: 'Sc. 8a', 'Sc. 4a'.

Two in the whole corpus (Pericles 8a, Sir Thomas More 4a). The old splitter's alternative
rule, `(?:Scene|Sc\\.?)\\s+([0-9IVXLC]+)\\b`, closes on a word boundary, and between the '8'
and the 'a' there is none - so the marker never matched and the half-scene stayed inside the
scene before it.

Requires preprocess-classify.mjs to order `Scene_<N><letter>` as N + letter/100, or the new
atom sorts as if it were Scene_8 and lands in the wrong place on the reading page.

Both plays are already translated, and the marker sits at a cell or <br>-segment boundary in
the Italian too, so the same row/segment index splits both languages - no retranslation.

  python shakespeare_split_lettered_scenes.py [--write]
"""
import os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shakespeare_split_absorbed_scenes import kg_index, tags_for, parse, write_atom, PLAYS
from shakespeare_recover_split_rows import cells_of, SD

# play dir -> (scene file holding it, marker, new atom stem, heading number)
JOBS = [
    ("Pericles", "Scenes/Scene_8", "Sc. 8a", "Scenes/Scene_8a", "8a"),
    ("Sir_Thomas_More", "Scenes/Scene_17", "Sc. 4a", "Scenes/Scene_4a", "4a"),
]


def locate(rows, marker):
    """(row, segment) where the marker opens a cell or a <br> segment."""
    for n, r in enumerate(rows):
        for s, seg in enumerate(r.split("<br>")):
            probe = (cells_of(seg + " |")[1] if s == 0 and len(cells_of(seg + " |")) > 1
                     else seg)
            if probe.strip().startswith(marker):
                return n, s
    return None


def cut(row, seg_i, marker):
    segs = row.split("<br>")
    head, tail = segs[:seg_i], list(segs[seg_i:])
    if seg_i == 0:
        cs = cells_of(segs[0] + " |")
        tail[0] = cs[1] if len(cs) > 1 else ""
        kept, kept_text = "| %s |  |" % cs[0].strip(), ""
    else:
        kept = "<br>".join(head).rstrip()
        if not kept.endswith("|"):
            kept += " |"
        cs = cells_of(kept)
        kept_text = cs[1].strip() if len(cs) > 1 else ""
    tail[0] = re.sub(r"^\s*%s\s*" % re.escape(marker), "", tail[0])
    new = SD + "<br>".join(tail).strip().rstrip("|").strip() + " |"
    return (kept if kept_text else None), new


def main(write):
    idx = kg_index()
    for play, src, marker, dst, label in JOBS:
        pd = os.path.join(PLAYS, play)
        en = os.path.join(pd, src + ".md")
        if os.path.exists(os.path.join(pd, dst + ".md")):
            print("    %s %s already split" % (play, label))
            continue
        fm, head, rows = parse(en)
        hit = locate(rows[2:], marker)
        if not hit:
            print("    %s: marker %r not found in %s" % (play, marker, src))
            continue
        n, s = hit
        have = set(re.findall(r"  - (\S+)", fm))
        residue = have - tags_for([head] + rows[2:], idx)
        for ext in (".md", ".it.md"):
            path = os.path.join(pd, src + ext)
            if not os.path.exists(path):
                continue
            fm_x, head_x, rows_x = parse(path)
            body = rows_x[2:]
            kept, first = cut(body[n], s, marker)
            a, b = body[:n] + ([kept] if kept else []), [first] + body[n + 1:]
            b_head = re.sub(r"(—\s*(?:Scene|Scena)\s+)\S+\s*$", r"\g<1>%s" % label, head_x)
            print("    %-18s %-6s %s%-8s  %d + %d rows%s" %
                  (play, label, dst, ext, len(a), len(b), "" if write else "  [dry]"))
            if not write:
                continue
            write_atom(path, (tags_for([head_x] + a, idx) & have) | residue,
                       head_x, rows_x[0], rows_x[1], a)
            write_atom(os.path.join(pd, dst + ext),
                       (tags_for([b_head] + b, idx) & have) | residue,
                       b_head, rows_x[0], rows_x[1], b)
    print("---- %s" % ("WROTE" if write else "DRY RUN"))


if __name__ == "__main__":
    main("--write" in sys.argv)
