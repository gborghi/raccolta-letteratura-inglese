# -*- coding: utf-8 -*-
"""Bring Eliot's five verse plays into the vault in the shape Shakespeare's plays have.

They were never brought in at all: they sat in `_raw/095..100`, outside Atomized/ and
Long/, so they had no scene atoms, no tags, no translation and no page - while Eliot's
poems were cluster-atomized and Shakespeare's plays were split into
`Plays/<Play>/Act_N/Scene_M.md` beside a `<Play>/<Play>.md` book file. The raws are
already in the same "lit" table form as Shakespeare's (`| Chi parla | Battuta |` with
`*(didascalia)*` stage directions), so nothing has to be re-parsed from prose: the plays
only have to be cut apart along their own act/scene headings.

Three defects have to be undone on the way in, all artefacts of how the source was sliced.

1. *Next-work bleed.* Each raw holds its own play AND the whole of the next one. This is
   exact, not approximate: 096's tail from its second `### PART I` is the same line
   sequence as 097 from its own first heading, byte for byte. So the cut point is found by
   equality against the next raw, and asserted - never guessed from the heading alone,
   which repeats inside a play.
2. *Absorbed cast rows.* The rows just before the bleed are the NEXT play's dramatis
   personae, swallowed into the last speech table because a title's full stop reads as a
   cell boundary: `| COL | THE HON. GERALD PIPER ... |`, `| MRS | GUZZARD |`. They cannot
   be recognised by their speaker cell - `MRS` is a real speaker 130 times in 099 - so a
   trailing row is dropped only when its text is also in the next raw's preamble.
3. *Table-of-contents blocks.* 100 opens with `ACT ONE/TWO/THREE` sections holding just
   the setting line, ahead of the real acts of the same name. Handled by the general rule
   that on a repeated act/scene key the longer body wins.

095_PLAYS is discarded: it is the untabled transcription of Murder in the Cathedral -
97.5% of its normalized text lies inside 096 - i.e. the same play without speaker cells.

    python3 eliot_atomize_plays.py             dry run: report what would be written
    python3 eliot_atomize_plays.py --write
"""
import os, sys, re, json, argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from leafcheck import VAULT_ROOT  # noqa: E402

AUTHOR = "Eliot"
RAW = os.path.join(VAULT_ROOT, "Authors", AUTHOR, "_raw")
PLAYS = os.path.join(VAULT_ROOT, "Authors", AUTHOR, "Plays")

# Raw file -> (play directory, title as it should read in a scene heading). The directory
# name follows Shakespeare's: the title in Title_Case joined by underscores.
PLAYS_IN_ORDER = [
    ("096_MURDER_IN_THE_CATHEDRAL.md", "Murder_in_the_Cathedral", "Murder in the Cathedral"),
    ("097_THE_FAMILY_REUNION.md",      "The_Family_Reunion",      "The Family Reunion"),
    ("098_THE_COCKTAIL_PARTY.md",      "The_Cocktail_Party",      "The Cocktail Party"),
    ("099_THE_CONFIDENTIAL_CLERK.md",  "The_Confidential_Clerk",  "The Confidential Clerk"),
    ("100_THE_ELDER_STATESMAN.md",     "The_Elder_Statesman",     "The Elder Statesman"),
]

SECTION_RE = re.compile(r"^###\s+(.*?)\s*$")
# `Part I`, `ACT ONE`, `Act One. Scene 1` - the division word carries meaning (Murder in
# the Cathedral has Parts, not Acts) and is kept for the scene heading.
DIVISION_RE = re.compile(r"^(Part|Act)\s+([A-Za-z]+|[IVXL]+|\d+)"
                         r"(?:\s*[.,]?\s*Scene\s+([IVXL]+|\d+|[A-Za-z]+))?$", re.I)
SCENE_ONLY_RE = re.compile(r"^Scene\s+([IVXL]+|\d+|[A-Za-z]+)$", re.I)

WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
         "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
ROMAN = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5,
         "vi": 6, "vii": 7, "viii": 8, "ix": 9, "x": 10}
ROMAN_OUT = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V",
             6: "VI", 7: "VII", 8: "VIII", 9: "IX", 10: "X"}

HEADER_ROW_RE = re.compile(r"^\|\s*Chi parla\s*\|\s*Battuta\s*\|$")
SEP_ROW_RE = re.compile(r"^\|[\s\-|:]+\|$")


def num(tok):
    t = tok.lower()
    if t.isdigit():
        return int(t)
    return WORDS.get(t) or ROMAN.get(t)


def norm(text):
    """Visible text, lowercased down to words - for comparing two transcriptions."""
    text = text.replace("<br>", " ")
    text = re.sub(r"\[\[([^\]|]*)\|([^\]]*)\]\]", r"\2", text)
    text = re.sub(r"\[\[([^\]]*)\]\]", r"\1", text)
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def split_sections(lines):
    """[(heading, first_line_index, body_lines)] plus the preamble ahead of the first."""
    heads = [i for i, l in enumerate(lines) if SECTION_RE.match(l)]
    if not heads:
        return lines, []
    out = []
    for k, i in enumerate(heads):
        end = heads[k + 1] if k + 1 < len(heads) else len(lines)
        out.append([SECTION_RE.match(lines[i]).group(1), i, lines[i + 1:end]])
    return lines[:heads[0]], out


def bleed_cut(lines, next_lines):
    """Index of the first line of the next play's text inside this raw, or len(lines).

    Anchored on equality, not on a heading: the tail of this file and the head of the next
    are the same lines. Take the next file's first section heading, and accept a candidate
    only if a long window matches from there.
    """
    if next_lines is None:
        return len(lines)
    nheads = [i for i, l in enumerate(next_lines) if SECTION_RE.match(l)]
    if not nheads:
        return len(lines)
    start = nheads[0]
    window = next_lines[start:start + 40]
    for i in range(len(lines) - 1, -1, -1):
        if lines[i:i + len(window)] == window:
            return i
    return len(lines)


def trim_absorbed_cast(sections, next_preamble):
    """Drop trailing rows of the last section that are really the next play's cast list."""
    if not sections or next_preamble is None:
        return []
    hay = norm("\n".join(next_preamble))
    body = sections[-1][2]
    dropped = []
    while body:
        j = len(body) - 1
        while j >= 0 and not body[j].strip():
            j -= 1
        if j < 0:
            break
        row = body[j]
        if not row.startswith("|") or HEADER_ROW_RE.match(row) or SEP_ROW_RE.match(row):
            break
        n = norm(row)
        if len(n) < 4 or n not in hay:
            break
        dropped.append(row)
        del body[j:]
    return dropped


def key_sections(sections):
    """Give every section an (act, scene) key; scene is None when the heading is act-only."""
    keyed, act, div = [], None, "Act"
    for head, i, body in sections:
        m = DIVISION_RE.match(head)
        if m:
            div = "Part" if m.group(1).lower() == "part" else "Act"
            act = num(m.group(2))
            scene = num(m.group(3)) if m.group(3) else None
        else:
            m = SCENE_ONLY_RE.match(head)
            if not m:
                raise SystemExit("intestazione non riconosciuta: %r" % head)
            scene = num(m.group(1))
        if act is None:
            raise SystemExit("scena senza atto: %r" % head)
        keyed.append([act, scene, div, head, i, body])
    return keyed


def dedupe(keyed):
    """On a repeated (act, scene) the longer body wins - this is what kills the ToC blocks."""
    best, dropped = {}, []
    for s in keyed:
        k = (s[0], s[1])
        prev = best.get(k)
        if prev is None:
            best[k] = s
        elif len(s[5]) > len(prev[5]):
            best[k], loser = s, prev
            dropped.append(loser)
        else:
            dropped.append(s)
    keep = [s for s in keyed if not any(s is d for d in dropped)]
    return keep, dropped


def rows_of(body):
    """Data rows only: the table header and its separator are scaffolding, re-emitted."""
    return [l for l in body if l.strip().startswith("|")
            and not HEADER_ROW_RE.match(l.strip()) and not SEP_ROW_RE.match(l.strip())]


def scenes_of(keyed):
    """[(act, scene, div, rows)] - act-only sections become scene 1, or the setting note
    of an act that does have scenes, in which case their rows open its first scene."""
    with_scene = {a for a, s, *_ in keyed if s is not None}
    out, pending = [], {}
    for act, scene, div, head, i, body in keyed:
        if scene is None:
            if act in with_scene:
                pending[act] = rows_of(body)
                continue
            scene = 1
        rows = rows_of(body)
        if act in pending:
            rows = pending.pop(act) + rows
        out.append((act, scene, div, rows))
    for act, rows in pending.items():          # an act whose scenes all vanished
        out.append((act, 1, "Act", rows))
    return sorted(out, key=lambda t: (t[0], t[1]))


def scene_heading(title, act, scene, div, only_scene):
    label = "%s %s" % (div, ROMAN_OUT[act])
    if not only_scene:
        label += ", Scene %d" % scene
    return "# [[%s]] — %s" % (title, label)


def build(raw_name, dirname, title, next_lines, next_preamble):
    lines = open(os.path.join(RAW, raw_name), encoding="utf-8").read().split("\n")
    cut = bleed_cut(lines, next_lines)
    bled = len(lines) - cut
    preamble, sections = split_sections(lines[:cut])
    cast = trim_absorbed_cast(sections, next_preamble)
    keyed = key_sections(sections)
    keyed, tossed = dedupe(keyed)
    scenes = scenes_of(keyed)

    per_act = {}
    for act, scene, _div, _rows in scenes:
        per_act[act] = per_act.get(act, 0) + 1

    files, book = {}, list(preamble)
    while book and not book[-1].strip():
        book.pop()
    for act, scene, div, rows in scenes:
        only = per_act[act] == 1
        head = scene_heading(title, act, scene, div, only)
        table = ["| Chi parla | Battuta |", "|---|---|"] + rows
        rel = os.path.join("Authors", AUTHOR, "Plays", dirname,
                           "Act_%d" % act, "Scene_%d.md" % scene)
        files[rel] = "\n".join([head, ""] + table) + "\n"
        book += ["", "### Atto %d, Scena %d" % (act, scene), ""] + table
    files[os.path.join("Authors", AUTHOR, "Plays", dirname, dirname + ".md")] = \
        "\n".join(book) + "\n"
    return {"raw": raw_name, "play": dirname, "righe_bleed_tagliate": bled,
            "righe_cast_assorbite": len(cast), "sezioni_toc_scartate": len(tossed),
            "scene": [("%s%d.%d" % ("P" if d == "Part" else "A", a, s), len(r))
                      for a, s, d, r in scenes],
            "file": len(files)}, files, cast, tossed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    raws = {}
    for name, _d, _t in PLAYS_IN_ORDER:
        raws[name] = open(os.path.join(RAW, name), encoding="utf-8").read().split("\n")

    total = {}
    for k, (name, dirname, title) in enumerate(PLAYS_IN_ORDER):
        nxt = PLAYS_IN_ORDER[k + 1][0] if k + 1 < len(PLAYS_IN_ORDER) else None
        nlines = raws[nxt] if nxt else None
        npre = split_sections(nlines)[0] if nlines else None
        rep, files, cast, tossed = build(name, dirname, title, nlines, npre)
        print(json.dumps(rep, ensure_ascii=False))
        for r in cast:
            print("   cast assorbito: %s" % r[:100])
        for s in tossed:
            print("   sezione scartata: %r (%d righe)" % (s[3], len(s[5])))
        total.update(files)

    if not a.write:
        print("\nDRY RUN - %d file. Rilancia con --write." % len(total))
        return 0
    for rel, text in sorted(total.items()):
        p = os.path.join(VAULT_ROOT, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
    print("\nscritti %d file sotto %s" % (len(total), PLAYS))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
