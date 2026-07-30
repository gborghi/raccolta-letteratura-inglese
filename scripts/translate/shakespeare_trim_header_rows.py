# -*- coding: utf-8 -*-
"""Second pass: drop the next work's header rows left above the cut.

shakespeare_trim_next_work_bleed.py anchors on the first sentence of the next work's introduction, so
whatever precedes that sentence -- the caps title, the 'BY WILLIAM SHAKESPEARE (ADAPTED BY
THOMAS MIDDLETON)' byline -- survives as the last rows of this play's last scene.

Those rows are matched against the actual header lines of the next raw work, so nothing is
removed on a guess: a row goes only if its text is one of those lines.

  python shakespeare_trim_header_rows.py [--write]
"""
import os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
VAULT = os.path.abspath(os.path.join(ROOT, "..", "VaultEnglish"))
RAW = os.path.join(VAULT, "Authors", "Shakespeare", "_raw")
PLAYS = os.path.join(VAULT, "Authors", "Shakespeare", "Plays")
ANCHOR_MIN = 60
MAX_WALK = 6


def read(p):
    with open(p, encoding="utf-8") as fh:
        return fh.read()


def flat(s):
    """Text as the reader sees it: no link syntax, no cell pipes, no case."""
    s = re.sub(r"\[\[[^\]|]*\|([^\]]*)\]\]", r"\1", s)
    s = re.sub(r"\[\[([^\]]*)\]\]", r"\1", s)
    s = s.replace("|", " ").replace("<br>", " ").replace("*(didascalia)*", " ")
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip().lower()


def header_lines(raw_path):
    """Everything the next work prints before its introduction proper."""
    out = []
    for l in read(raw_path).split("\n")[:12]:
        s = l.strip()
        if len(s) >= ANCHOR_MIN:
            break
        if s:
            out.append(flat(s))
    return [h for h in out if h]


def play_dir_for(raw_name):
    stem = re.sub(r"^\d+_", "", raw_name[:-3]).replace("(", "").replace(")", "")
    d = os.path.join(PLAYS, re.sub(r"_+", "_", stem))
    return d if os.path.isdir(d) else None


def scene_atoms(pd):
    out = []
    for dirpath, _, files in os.walk(pd):
        for f in files:
            if f.startswith("Scene_") and f.endswith(".md") and not f.endswith(".it.md"):
                out.append(os.path.join(dirpath, f))

    def key(p):
        a = re.search(r"Act_(\d+)", p)
        s = re.search(r"Scene_(\d+)\.md$", p)
        return (int(a.group(1)) if a else 0, int(s.group(1)) if s else 0)
    return sorted(out, key=key)


def trim(path, heads, write):
    """Drop trailing rows whose text is one of the next work's header lines."""
    lines = read(path).split("\n")
    row_idx = [n for n, l in enumerate(lines) if l.startswith("|")]
    drop = 0
    for n in reversed(row_idx[2:]):
        if drop >= MAX_WALK:
            break
        f = flat(lines[n])
        if f and any(f == h or (len(f) > 8 and f in h) for h in heads):
            drop += 1
        else:
            break
    if not drop:
        return 0
    cut_at = row_idx[len(row_idx) - drop]
    if write:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines[:cut_at]).rstrip("\n") + "\n")
    print("    %-56s -%d header rows %s" % (os.path.relpath(path, VAULT), drop,
                                            "" if write else "[dry]"))
    return drop


def main(write):
    files = sorted(f for f in os.listdir(RAW) if f.endswith(".md"))
    total = 0
    for i, f in enumerate(files[:-1]):
        heads = header_lines(os.path.join(RAW, files[i + 1]))
        pd = play_dir_for(f)
        if not pd or not heads:
            continue
        targets = [os.path.join(pd, os.path.basename(pd) + ".md")]
        atoms = scene_atoms(pd)
        if atoms:
            targets.append(atoms[-1])
        for t in targets:
            if not os.path.exists(t):
                continue
            n = trim(t, heads, write)
            total += n
            it = t[:-3] + ".it.md"
            if n and os.path.exists(it):
                # same count off the end: EN and IT are row-for-row
                lines = read(it).split("\n")
                ridx = [k for k, l in enumerate(lines) if l.startswith("|")]
                cut_at = ridx[len(ridx) - n]
                if write:
                    with open(it, "w", encoding="utf-8") as fh:
                        fh.write("\n".join(lines[:cut_at]).rstrip("\n") + "\n")
                print("    %-56s -%d header rows %s" %
                      (os.path.relpath(it, VAULT), n, "" if write else "[dry]"))
    print("---- %s: %d header rows dropped" % ("WROTE" if write else "DRY RUN", total))


if __name__ == "__main__":
    main("--write" in sys.argv)
