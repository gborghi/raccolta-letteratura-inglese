# -*- coding: utf-8 -*-
"""Line-for-line verse workflow around opus_atom, for the Opus agent.

opus_atom's mask/write pair is built for prose: the agent gets N masked blocks and hands
back N translated blocks as one JSON array. That is awkward for verse, where a block is a
whole poem of a hundred lines and the one invariant that matters is that line k of the
Italian answers line k of the English -- a silently dropped or merged line is exactly the
failure validate() cannot always catch, and it is invisible in a JSON string full of \\n.

So this splits the same masked blocks into one plain-text file per block, one line per
line, and puts them back together afterwards:

    python3 opus_verse.py plan  <vault_rel> <workdir>   # writes NN.en.txt + NN.it.txt seeds
    python3 opus_verse.py build <vault_rel> <workdir>   # checks, rebuilds, calls opus_atom.write

`plan` seeds each NN.it.txt with the English so the agent edits in place and a forgotten
file fails loudly (identical to the source) instead of quietly writing English.
`build` refuses when a block's line count changed: verse keeps its lines.

Blocks that are pure frontmatter are copied verbatim and get no .it.txt -- the tag block is
the English one, byte for byte, and translating it would break the axis slugs.

Hard line breaks: markdown needs two trailing spaces to keep a verse line from being reflowed
into the previous one. They are stripped from the .txt files (invisible, easy to lose while
editing) and restored here on every line but the block's last.

    python3 opus_verse.py plan Authors/Wilde/Long/The_Ballad_of_Reading_Gaol/Section_01_part_i.md /tmp/wilde01
"""
import io
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import opus_atom
import dickens_tower as dt

FM = "---\ntags:"
# `L%02d` is two digits only up to 99: past that the code is L100, L101, ... A `\d\d`
# pattern reads [[L100|x]] as L10, so on atoms with 100+ links the per-line check below
# compares mangled codes and a lost token can slip through it. Same idiom as everywhere
# else in the pipeline (dickens_tower.CODE_RE).
CODE_RE = re.compile(r"\[\[(L\d{2,})\|")


def _blocks(rel):
    body = io.open(opus_atom._abs(rel), encoding="utf-8").read()
    return [dt.mask_links(b)[0] for b in dt.prose_blocks(body)]


def _is_frontmatter(b):
    return b.startswith(FM) and b.rstrip().endswith("---")


def cmd_plan(rel, workdir):
    os.makedirs(workdir, exist_ok=True)
    for i, b in enumerate(_blocks(rel)):
        lines = [ln.rstrip() for ln in b.split("\n")]
        io.open(os.path.join(workdir, "%02d.en.txt" % i), "w", encoding="utf-8",
                newline="\n").write("\n".join(lines) + "\n")
        kind = "frontmatter (verbatim)" if _is_frontmatter(b) else "%d righe" % len(lines)
        if not _is_frontmatter(b):
            io.open(os.path.join(workdir, "%02d.it.txt" % i), "w", encoding="utf-8",
                    newline="\n").write("\n".join(lines) + "\n")
        print("%02d  %s" % (i, kind))


def cmd_build(rel, workdir, verse=True, same_ok=()):
    out, problems = [], []
    for i, b in enumerate(_blocks(rel)):
        if _is_frontmatter(b):
            out.append(b)
            continue
        p = os.path.join(workdir, "%02d.it.txt" % i)
        if not os.path.exists(p):
            problems.append("blocco %02d: manca %s" % (i, os.path.basename(p)))
            continue
        it = [ln.rstrip() for ln in io.open(p, encoding="utf-8").read().split("\n")]
        while it and not it[-1]:
            it.pop()
        en = b.split("\n")
        if len(it) != len(en):
            problems.append("blocco %02d: %d righe IT vs %d EN" % (i, len(it), len(en)))
            continue
        # A block identical to the English is nearly always a file the agent forgot to edit.
        # Nearly: an H1 that is a place name -- "Burnt Norton — I", "East Coker — III" -- is
        # the same in both languages, and there the guard would block a correct translation
        # for ever. So it is opt-in per block, declared on the command line, never inferred.
        if it == [ln.rstrip() for ln in en] and i not in same_ok:
            problems.append("blocco %02d: identico all'inglese (non tradotto)" % i)
            continue
        # Same masks, same lines, same order. opus_atom checks the block as a whole and
        # silently drops a code the model failed to carry; in verse a link that slid to the
        # neighbouring line is a wrong link, not a lost one, and nothing downstream sees it.
        for k, (e, t) in enumerate(zip(en, it), 1):
            ce, ct = CODE_RE.findall(e), CODE_RE.findall(t)
            if ce != ct:
                problems.append("blocco %02d riga %d: token %s invece di %s"
                                % (i, k, ct or "[]", ce or "[]"))
        out.append("  \n".join(it))
    if problems:
        print("\n".join(problems))
        return 2
    tmp = os.path.join(workdir, "_blocks.json")
    io.open(tmp, "w", encoding="utf-8", newline="\n").write(
        json.dumps(out, ensure_ascii=False))
    argv = [sys.executable, os.path.join(HERE, "opus_atom.py"), "write"]
    if verse:
        argv.append("--verse")
    argv += [rel, tmp]
    return subprocess.call(argv)


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) < 3:
        print(__doc__.strip().splitlines()[-1])
        sys.exit(1)
    if a[0] == "plan":
        cmd_plan(a[1], a[2])
    elif a[0] == "build":
        same = ()
        for k, v in enumerate(a):
            if v == "--same-ok" and k + 1 < len(a):
                same = tuple(int(n) for n in a[k + 1].split(","))
        sys.exit(cmd_build(a[1], a[2], verse="--prose" not in a, same_ok=same))
    else:
        print("comandi: plan | build")
        sys.exit(1)
