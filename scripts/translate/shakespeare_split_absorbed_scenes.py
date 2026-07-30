# -*- coding: utf-8 -*-
"""Recover the scenes split_shakespeare.py absorbed.

That splitter only recognised a scene marker sitting alone on its line
(`^\\s*(\\d+)\\.(\\d+)\\s*$`). Where the edition printed the marker inline with the opening
stage direction -- "1.2 Enter Sir John Falstaff, followed by his Page" -- no split happened
and the scene was swallowed by the previous atom. 24 of the 41 plays are affected.

The swallowed text is present and already wikilinked, so recovery is a pure re-atomisation:
cut the atom at the marker row, strip the marker, rebuild the heading, recompute tags.

Where the play is already translated the .it.md is cut at the SAME row index (the contract
guarantees one IT row per EN row), so the Italian for the recovered scenes comes free.

Tags: a wikilink target maps to a tag through the KG folder that defines it (a title defined
in two folders yields both tags). Tags in the source atom that no link accounts for -- the
Phase-2 LLM vocabulary -- are non-attributable and stay on both halves.

  python shakespeare_split_absorbed_scenes.py            # dry run over every play
  python shakespeare_split_absorbed_scenes.py --write
  python shakespeare_split_absorbed_scenes.py --write Cymbeline King_John
"""
import os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
VAULT = os.path.abspath(os.path.join(ROOT, "..", "VaultEnglish"))
PLAYS = os.path.join(VAULT, "Authors", "Shakespeare", "Plays")
KG = os.path.join(VAULT, "Knowledge Graph")

FOLDERS = {
    "Archetypes": "archetype", "Characters": "character", "Concepts": "concept",
    "Motifs": "motif", "Topoi": "topos", "Settings": "setting", "Forms": "form",
    "Historical References": "historical", "Clusters": "cluster", "Works": "work",
}

ROMAN = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI", 7: "VII"}
LINK = re.compile(r"\[\[([^\]|#]+)(?:\|[^\]]*)?\]\]")
MARKER = re.compile(r"^\| \*\(didascalia\)\* \| (\d+)\.(\d+) (?=\S)")
HEAD_TAIL = re.compile(r"\s+[—-]\s+(?:Act|Atto)\s+[IVXLC]+,\s*(?:Scene|Scena)\s+\d+\s*$")


def slug(s):
    s = s.lower().replace("'", "").replace("\u2019", "")
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")


def kg_index():
    idx = {}
    for folder, prefix in FOLDERS.items():
        d = os.path.join(KG, folder)
        if not os.path.isdir(d):
            continue
        for _, _, files in os.walk(d):
            for f in files:
                if f.endswith(".md"):
                    idx.setdefault(f[:-3], set()).add("%s/%s" % (prefix, slug(f[:-3])))
    return idx


def tags_for(lines, idx):
    out = set()
    for l in lines:
        for t in LINK.findall(l):
            out |= idx.get(t.strip(), set())
    return out


def parse(path):
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    m = re.match(r"^---\n(.*?\n)---\n", text, re.S)
    fm, body = (m.group(0), text[m.end():]) if m else ("", text)
    lines = body.split("\n")
    head = next((l for l in lines if l.startswith("#")), None)
    rows = [l for l in lines if l.startswith("|")]
    return fm, head, rows


def write_atom(path, tags, head, hdr, sep, rows):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("---\ntags:\n" + "".join("  - %s\n" % t for t in sorted(tags)) + "---\n")
        fh.write("\n" + head + "\n\n" + hdr + "\n" + sep + "\n" + "\n".join(rows) + "\n")


def retitle(head, act, scene, it):
    tail = " — %s %s, %s %d" % ("Atto" if it else "Act", ROMAN[act],
                                "Scena" if it else "Scene", scene)
    return HEAD_TAIL.sub("", head) + tail


def split_atom(play_dir, rel, idx, write):
    """Cut one atom at its first embedded marker. Returns the new atom's rel path or None.
    Recursive: an absorbed scene can itself have absorbed the next one."""
    en_path = os.path.join(play_dir, rel + ".md")
    fm, head, rows = parse(en_path)
    if head is None or len(rows) < 3:
        return None
    body = rows[2:]
    hit = next(((n, m) for n, r in enumerate(body) for m in [MARKER.match(r)] if m), None)
    if not hit:
        return None
    n, m = hit
    act, scene = int(m.group(1)), int(m.group(2))
    new_rel = "Act_%d/Scene_%d" % (act, scene)
    if os.path.exists(os.path.join(play_dir, new_rel + ".md")):
        print("    SKIP %s -> %s already exists" % (rel, new_rel))
        return None

    have = set(re.findall(r"  - (\S+)", fm))
    residue = have - tags_for([head] + body, idx)

    for ext in (".md", ".it.md"):
        path = os.path.join(play_dir, rel + ext)
        if not os.path.exists(path):
            continue
        it = ext == ".it.md"
        fm_x, head_x, rows_x = parse(path)
        body_x = rows_x[2:]
        if not MARKER.match(body_x[n]):
            print("    ABORT %s%s row %d is not the marker row" % (rel, ext, n))
            return None
        a, b = body_x[:n], list(body_x[n:])
        b[0] = MARKER.sub("| *(didascalia)* | ", b[0], 1)
        b_head = retitle(head_x, act, scene, it)
        if not write:
            continue
        write_atom(path, (tags_for([head_x] + a, idx) & have) | residue,
                   head_x, rows_x[0], rows_x[1], a)
        os.makedirs(os.path.dirname(os.path.join(play_dir, new_rel + ext)), exist_ok=True)
        write_atom(os.path.join(play_dir, new_rel + ext),
                   (tags_for([b_head] + b, idx) & have) | residue,
                   b_head, rows_x[0], rows_x[1], b)
    print("    %-38s %s -> %s  (%d kept / %d moved)%s" %
          (os.path.basename(play_dir), rel, new_rel, n, len(body) - n,
           "" if write else "  [dry]"))
    return new_rel if write else None


def main(argv):
    write = "--write" in argv
    only = [a for a in argv if not a.startswith("--")]
    idx = kg_index()
    plays = only or sorted(d for d in os.listdir(PLAYS)
                           if os.path.isdir(os.path.join(PLAYS, d)))
    total = 0
    for play in plays:
        play_dir = os.path.join(PLAYS, play)
        found = []
        for dirpath, _, files in os.walk(play_dir):
            for f in sorted(files):
                if f.startswith("Scene_") and f.endswith(".md") and not f.endswith(".it.md"):
                    rel = os.path.relpath(os.path.join(dirpath, f), play_dir)[:-3]
                    found.append(rel.replace("\\", "/"))
        queue, made = list(found), []
        while queue:
            rel = queue.pop(0)
            new = split_atom(play_dir, rel, idx, write)
            if new:
                made.append(new)
                queue.append(new)          # the recovered scene may hide another marker
                queue.append(rel)          # and so may what is left of the source atom
        if made or any(True for _ in ()):
            total += len(made)
        if made:
            print("  %s: recovered %d" % (play, len(made)))
    print("---- %s: %d scenes recovered" % ("WROTE" if write else "DRY RUN", total))


if __name__ == "__main__":
    main(sys.argv[1:])
