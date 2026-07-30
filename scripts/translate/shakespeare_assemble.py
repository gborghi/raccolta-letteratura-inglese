# -*- coding: utf-8 -*-
"""Assemble <Play>.it.md from the already-translated scene atoms.

Every `<Play>/<Play>.md` inlines the whole play: an editorial preamble (introduction + dramatis
personae), then each scene reproduced verbatim as a `### Act N, Scene M` section whose table is
byte-identical to the corresponding `Act_N/Scene_M.md` atom.

Translating that file separately would double the work AND guarantee the play page and the scene
pages render different Italian for the same speech. So we build it instead: substitute each scene's
validated Italian rows into the English skeleton, in order.

  assemble <Play> [...]     write <Play>.it.md for each play named (all plays if none)
  assemble --all
  assemble extract-preambles  dump every play's English preamble for separate translation

Substitution is POSITIONAL, not by string lookup: a row like `| [[Macbeth|MACBETH]] | Ay. |` recurs
across scenes with different translations, so each scene's row sequence is located as a contiguous
block starting at a cursor that only moves forward.

The preamble is not translated here - it has no scene to draw from. Lines left in English are
counted and reported per play; `shakespeare_check.py` CANNOT catch them (an untranslated preamble
has the same links and row count as its source), so the count printed here is the only signal.
"""
import os, sys, re, json, difflib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dickens_tower as dt

PLAYS_ABS = os.path.join(dt.VAULT_ROOT, "Authors", "Shakespeare", "Plays")

# The preamble - title, editorial introduction, dramatis personae - is the one part of <Play>.md
# with no scene to draw from. It is translated separately into this store, keyed by play, as a list
# of lines the same length as the English preamble, and injected at assembly time.
PREAMBLES_EN = os.path.join(dt.ROOT, "data", "shakespeare_preambles_en.json")
PREAMBLES_IT = os.path.join(dt.ROOT, "data", "shakespeare_preambles_it.json")

# Fraction of non-blank lines allowed to remain English before assembly refuses to write.
MAX_UNTRANSLATED = 0.25

SECTION_RE = re.compile(r"^(#{1,6}\s*)Act\s+([IVXLC\d]+)\s*,\s*Scene\s+([IVXLC\d]+)\s*$", re.I)

# Every scene atom repeats the table header. The play-level file does too, once per inlined scene -
# except in the plays that hold one continuous table for the whole play (Pericles has 880 rows under
# a single header), where an atom's header row has no counterpart and blocks the whole scene from
# matching. Excluded from matching on both sides; it needs no translating either way, being Italian
# scaffolding already.
HEADER_ROW_RE = re.compile(r"^\|\s*Chi parla\s*\|\s*Battuta\s*\|$")

# The play file keeps the editorial scene marker inside the first stage direction of each scene -
# `| *(didascalia)* | 1.2 Enter Sir John Falstaff... |` - and the atomizer strips it. That one
# character difference is the single commonest reason a scene cannot be found (52 scenes).
SCENE_MARKER_RE = re.compile(r"(\|\s*)(?:\d+\.\d+|\d+)\s+(?=\S)")

# Two copies of the same speech may still differ in a row or two: a mislabelled speaker cell
# (`| KING HENRY |` where the atom has `| *(didascalia)* |`) or a trailing marker the split left
# behind (`Exeunt<br><br>Sc. 3`). Allow a couple of such rows, but only when the block is otherwise
# an exact, uniquely-best match AND each divergent pair is recognisably the same text - measured,
# the real ones sit at 0.59-1.00 similarity, so 0.55 admits them and nothing else.
MAX_FUZZY_ROWS = 2
MIN_ROW_SIMILARITY = 0.55

# The vault's play files already carry `### Atto N, Scena M`, like `| Chi parla | Battuta |` and
# `*(didascalia)*` - scaffolding preprocess emits in Italian. Such a line is correct output even
# though it is byte-identical to the English source, so it must not count as untranslated.
IT_SECTION_RE = re.compile(r"^#{1,6}\s*Atto\s+[IVXLC\d]+\s*,\s*Scena\s+[IVXLC\d]+\s*$", re.I)


def _table_rows(text):
    """Indices and values of table rows, excluding the |---| separator."""
    out = []
    for i, line in enumerate(text.split("\n")):
        s = line.strip()
        if s.startswith("|") and not re.match(r"^\|[\s\-|:]+\|$", s):
            out.append((i, line))
    return out


def preamble_len(lines):
    """Number of leading lines before the first table row - the preamble block."""
    for i, l in enumerate(lines):
        if l.strip().startswith("|"):
            return i
    return len(lines)


def cmd_extract_preambles():
    """Dump every play's English preamble, for separate translation into PREAMBLES_IT."""
    out = {}
    for play in sorted(os.listdir(PLAYS_ABS)):
        p = os.path.join(PLAYS_ABS, play, play + ".md")
        if not os.path.isdir(os.path.join(PLAYS_ABS, play)) or not os.path.exists(p):
            continue
        lines = dt._read_vault(p).split("\n")
        out[play] = lines[:preamble_len(lines)]
    os.makedirs(os.path.dirname(PREAMBLES_EN), exist_ok=True)
    with open(PREAMBLES_EN, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    tot = sum(len(v) for v in out.values())
    words = sum(len(l.split()) for v in out.values() for l in v)
    print(json.dumps({"plays": len(out), "preamble_lines": tot, "words": words,
                      "file": PREAMBLES_EN}))


def scene_tag(en_path):
    """`Act_N/Scene_M.md` - Scene_1.md alone is ambiguous across five acts."""
    return os.path.basename(os.path.dirname(en_path)) + "/" + os.path.basename(en_path)


def _norm(row):
    """Row reduced to its visible text: every [[Target|label]] becomes `label`.

    The two English copies of a speech occasionally disagree on the link *target* only - The
    Tempest's epilogue is `[[prayer]]` in the play file and `[[Prayer|prayer]]` in the scene atom.
    Matching on visible text alone lets such a scene still be located.
    """
    return dt.WIKILINK_RE.sub(lambda m: m.group(2) if m.group(2) is not None else m.group(1), row)


def _match_norm(row):
    """`_norm` plus the editorial scene marker - the form rows are COMPARED in, never written."""
    return SCENE_MARKER_RE.sub(r"\1", _norm(row)).strip()


def _is_header(row):
    return bool(HEADER_ROW_RE.match(_norm(row).strip()))


def _locate(hay, seq, cursor):
    """Start index of `seq` within `hay` at or after `cursor`, or -1. Both are match-normalised.

    Three tiers, each only reached when the one above finds nothing:
      exact           the contiguous block, scanning forward from the cursor;
      exact-anywhere  the same block before the cursor, accepted only if it occurs exactly once
                      (a unique hit cannot be the wrong scene, so the cursor is worth overriding);
      fuzzy           up to MAX_FUZZY_ROWS divergent rows, accepted only if this start is strictly
                      better than every other candidate and each divergent pair is >= MIN_ROW_
                      SIMILARITY - i.e. demonstrably the same speech, differently transcribed;
      fuzzy-unique    the same tolerance across the whole file, accepted only when exactly one
                      start in it qualifies. Needed because a scene whose opening row the play
                      file merged into the previous scene's last row sits at cursor-1, behind a
                      cursor that has already stepped over it. No similarity floor here: a sole
                      candidate among hundreds of rows is itself the evidence, and the floor would
                      throw out real merges whose divergent cell is empty or rewritten.

    Returns (index, tier).
    """
    n = len(seq)
    if not n or n > len(hay):
        return -1, "miss"

    for s in range(cursor, len(hay) - n + 1):
        if hay[s] == seq[0] and hay[s:s + n] == seq:
            return s, "exact"

    hits = [s for s in range(len(hay) - n + 1) if hay[s:s + n] == seq]
    if len(hits) == 1:
        return hits[0], "exact-anywhere"

    def mismatches(s):
        mis = 0
        for k in range(n):
            if hay[s + k] != seq[k]:
                mis += 1
                if mis > MAX_FUZZY_ROWS:
                    return None
        return mis

    best, best_mis, runner_up = -1, MAX_FUZZY_ROWS + 1, MAX_FUZZY_ROWS + 1
    for s in range(cursor, len(hay) - n + 1):
        mis = mismatches(s)
        if mis is None:
            continue
        if mis < best_mis:
            runner_up, best, best_mis = best_mis, s, mis
        elif mis < runner_up:
            runner_up = mis
    if best >= 0 and best_mis < runner_up:
        if all(difflib.SequenceMatcher(None, seq[k], hay[best + k]).ratio() >= MIN_ROW_SIMILARITY
               for k in range(n) if seq[k] != hay[best + k]):
            return best, "fuzzy"

    candidates = [s for s in range(len(hay) - n + 1) if mismatches(s) is not None]
    if len(candidates) == 1:
        return candidates[0], "fuzzy-unique"
    return -1, "miss"


def _split_cells(row):
    """`| A | B |` -> ['', ' A ', ' B ', ''], without splitting inside a wikilink.

    A plain `row.split("|")` tears `[[Ariel|ARIEL]]` in half and shifts every cell index after it,
    which silently rewrites rows into `| [[Ariel| ...`. The alias pipe is masked for the split and
    restored afterwards.
    """
    masked = dt.WIKILINK_RE.sub(lambda m: m.group(0).replace("|", "\x00"), row)
    return [c.replace("\x00", "|") for c in masked.split("|")]


def _merge_row(prev_it, new_it):
    """Append `new_it`'s speech cell to `prev_it`, the way the play file merged the English.

    Three rows in the corpus belong to two scenes at once: the play file runs a scene's closing
    speech and the next scene's opening stage direction together in ONE row -
    `| BRUTUS | Let's along. Exeunt<br><br>1.2 Enter Aufidius... |` - where the atoms, split at the
    scene boundary, hold the two halves separately. Letting the second scene simply overwrite the
    row drops the first speech from the Italian page (and the link check downstream catches it as
    missing targets). Concatenating reproduces the English row's own structure.
    """
    pc, nc = _split_cells(prev_it), _split_cells(new_it)
    if len(pc) < 4 or len(nc) < 4:
        return prev_it, False
    add = nc[2].strip()
    if not add:                       # the second half is an empty cell - nothing to append
        return prev_it, False
    pc[2] = " %s<br><br>%s " % (pc[2].strip(), add)
    return "|".join(pc), True


def _keep_speaker(it_row, play_en_row, atom_en_row):
    """Restore the play file's own speaker cell when it disagrees with the atom's.

    A handful of rows are attributed differently by the two English copies: the play file files an
    opening stage direction under the last character to speak - `| [[Ariel|ARIEL]] | Enter Caliban,
    wearing a gaberdine |` - where the atom calls it `*(didascalia)*`. Taking the atom's cell would
    drop that link from the Italian, and this page has to link exactly what its own English links
    or it cannot be published. The speech itself still comes from the translation; only the speaker
    cell is held back.
    """
    ic, pc, ac = _split_cells(it_row), _split_cells(play_en_row), _split_cells(atom_en_row)
    if min(len(ic), len(pc), len(ac)) < 4 or pc[1].strip() == ac[1].strip():
        return it_row, False
    ic[1] = pc[1]
    return "|".join(ic), True


def _retarget(it_row, play_en_row):
    """Rewrite it_row's link targets to the ones the play-level file uses, positionally.

    The Italian comes from the scene atom, so it carries the atom's targets. The play page must link
    exactly what its own English does, or the EN/IT link check on <Play>.md fails. Only applied when
    both rows hold the same number of links; otherwise the Italian is left untouched.
    """
    src = dt.WIKILINK_RE.findall(play_en_row)
    dst = dt.WIKILINK_RE.findall(it_row)
    if len(src) != len(dst):
        return it_row, False
    seq = iter(src)

    def repl(m):
        target = next(seq)[0]
        label = m.group(2)
        return "[[%s|%s]]" % (target, label) if label is not None else "[[%s]]" % target

    return dt.WIKILINK_RE.sub(repl, it_row), True


def scene_pairs(play):
    """[(en_path, it_path)] for the play's scene atoms, in Act/Scene order."""
    out = []
    for dirpath, _, files in os.walk(os.path.join(PLAYS_ABS, play)):
        for f in files:
            if f.startswith("Scene_") and f.endswith(".md") and not f.endswith(".it.md"):
                en = os.path.join(dirpath, f)
                out.append((en, en[:-3] + ".it.md"))

    def key(p):
        # A lettered scene (`Scene_8a`, a passage some editions insert after 8) must sort straight
        # after its number, so the letter is a third component - not part of the number, or 8a and 8
        # tie and their order falls to os.walk.
        s = p[0].replace(os.sep, "/")
        m = re.search(r"Act_(\d+).*?Scene_(\d+)([a-z]?)", s)
        if m:
            return (int(m.group(1)), int(m.group(2)), m.group(3))
        # Scene-only plays (Pericles, Edward III, Sir Thomas More, the Lear quarto) hold their
        # atoms flat in `Scenes/Scene_N.md`, which the Act pattern cannot read. They used to fall
        # through to a constant key, leaving them in os.walk order - Scene_1, Scene_10, Scene_11,
        # ..., Scene_2 - and since the cursor only moves forward, every scene after the first
        # lexicographic one was searched for behind it and reported missing.
        m = re.search(r"Scene_(\d+)([a-z]?)", s)
        return (0, int(m.group(1)), m.group(2)) if m else (99, 99, "")

    return sorted(out, key=key)


def assemble(play):
    play_en = os.path.join(PLAYS_ABS, play, play + ".md")
    if not os.path.exists(play_en):
        return {"play": play, "status": "SKIP", "reason": "no play-level file"}

    lines = dt._read_vault(play_en).split("\n")
    out = list(lines)
    cursor, placed, misses = 0, 0, []

    # Match in row-space, not line-space: the |---|---| separator sits between the header and the
    # first data row in the file but is excluded from the row lists, so no contiguous slice of raw
    # lines can equal a scene's rows. Keep each row's line index to write the translation back.
    play_rows = [(i, v) for i, v in _table_rows("\n".join(lines)) if not _is_header(v)]
    row_vals = [v for _, v in play_rows]
    row_norm = [_match_norm(v) for v in row_vals]
    row_idx = [i for i, _ in play_rows]
    retargeted = 0
    tiers = {}
    # Line numbers a scene has already written to, so a row two scenes share is merged, not clobbered.
    claimed, merged, speakers_kept = set(), 0, 0

    for en_path, it_path in scene_pairs(play):
        if not os.path.exists(it_path):
            misses.append(scene_tag(en_path) + " (no .it.md)")
            continue
        all_en = [v for _, v in _table_rows(dt._read_vault(en_path))]
        all_it = [v for _, v in _table_rows(dt._read_vault(it_path))]
        if len(all_en) != len(all_it):
            misses.append(scene_tag(en_path) + " (row count %d/%d)" % (len(all_it), len(all_en)))
            continue
        if not all_en:
            continue

        # Drop the header row from BOTH sides together, so the k-th English row still answers to the
        # k-th Italian one, and the sequence matches a play file that carries only one header.
        pairs = [(e, i) for e, i in zip(all_en, all_it) if not _is_header(e)]
        if not pairs:
            continue
        en_rows = [e for e, _ in pairs]
        it_rows = [i for _, i in pairs]

        # Locate this scene's rows as a contiguous run at or after the cursor, comparing visible
        # text so a link-target disagreement between the two English copies can't hide the scene.
        en_norm = [_match_norm(r) for r in en_rows]
        n = len(en_rows)
        found, tier = _locate(row_norm, en_norm, cursor)
        if found < 0:
            misses.append(scene_tag(en_path) + " (rows not found in play file)")
            continue
        tiers[tier] = tiers.get(tier, 0) + 1
        for k in range(n):
            row = it_rows[k]
            if row_vals[found + k] != en_rows[k]:
                row, kept = _keep_speaker(row, row_vals[found + k], en_rows[k])
                speakers_kept += kept
                row, ok = _retarget(row, row_vals[found + k])
                retargeted += ok
            line_no = row_idx[found + k]
            if line_no in claimed:
                row, did = _merge_row(out[line_no], row)
                merged += did
            out[line_no] = row
            claimed.add(line_no)
        cursor = found + n
        placed += n

    # `### Act N, Scene M` section headings inside the play file.
    for i, line in enumerate(out):
        m = SECTION_RE.match(line.strip())
        if m:
            out[i] = "%sAtto %s, Scena %s" % (m.group(1), m.group(2), m.group(3))

    # Never write a partial assembly. A play whose scenes are not all translated would be written
    # as Italian-where-available and English everywhere else, and if a hand-translated <Play>.it.md
    # already existed that half-English file would silently replace it.
    if misses:
        return {"play": play, "status": "PARTIAL", "written": False,
                "rows_substituted": placed, "misses": misses}

    # Preserve a preamble that was already translated by hand. Some plays were done before the
    # assemble-instead-of-retranslate decision and their <Play>.it.md carries a real Italian
    # introduction + dramatis personae; rebuilding from the English skeleton would silently revert
    # it. The preamble is the contiguous head of the file above the first table row, and the hand
    # translations keep it line-for-line, so the two heads are interchangeable.
    play_it = play_en[:-3] + ".it.md"
    reused_preamble = False

    # Preferred source for the preamble: the translation store. Line counts must match exactly, or
    # the injected block would shift the file against its English original.
    if os.path.exists(PREAMBLES_IT):
        with open(PREAMBLES_IT, encoding="utf-8") as fh:
            store = json.load(fh)
        it_pre = store.get(play)
        n_pre = preamble_len(lines)
        if it_pre and len(it_pre) == n_pre:
            out[:n_pre] = it_pre
            reused_preamble = "store"
        elif it_pre:
            return {"play": play, "status": "PARTIAL", "written": False,
                    "rows_substituted": placed,
                    "misses": ["preamble: store has %d lines, source has %d - the injected block "
                               "would shift the file against its English original"
                               % (len(it_pre), n_pre)]}

    if not reused_preamble and os.path.exists(play_it):
        prev = dt._read_vault(play_it).split("\n")
        first_en = next((i for i, l in enumerate(out) if l.strip().startswith("|")), None)
        first_prev = next((i for i, l in enumerate(prev) if l.strip().startswith("|")), None)
        if first_en is not None and first_prev is not None and first_en == first_prev:
            if prev[:first_en] != out[:first_en]:
                out[:first_en] = prev[:first_en]
                reused_preamble = "existing"

    # Anything still identical to the English source and not blank is untranslated (the preamble).
    untranslated = [b for a, b in zip(lines, out)
                    if a == b and a.strip() and not a.strip().startswith("|")
                    and not IT_SECTION_RE.match(a.strip())]

    # A few plays are barely tabled at all: King John's play file carries 1126 lines of untabled
    # dramatic verse ahead of its first table row, Titus Andronicus 882. Assembling those yields a
    # page that is mostly English, which the checker cannot catch (same links, same row count) and
    # which would go live looking like a finished translation. Hold them until the preamble store
    # covers them; assembly is deterministic, so re-running once it does costs nothing.
    body = sum(1 for l in lines if l.strip())
    if body and len(untranslated) > MAX_UNTRANSLATED * body:
        return {"play": play, "status": "PARTIAL", "written": False,
                "rows_substituted": placed,
                "misses": ["%d of %d non-blank lines still English (%.0f%%) - the untranslated "
                           "preamble dominates the file; translate it into %s first"
                           % (len(untranslated), body, 100.0 * len(untranslated) / body,
                              os.path.basename(PREAMBLES_IT))]}

    dt._write_vault(play_it, "\n".join(out))
    return {"play": play, "status": "OK", "written": True,
            "rows_substituted": placed, "retargeted_rows": retargeted, "located_via": tiers,
            "merged_shared_rows": merged, "speakers_kept": speakers_kept,
            "untranslated_lines": len(untranslated), "reused_preamble": reused_preamble,
            "untranslated_sample": [l[:80] for l in untranslated[:5]]}


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "extract-preambles":
        cmd_extract_preambles()
        sys.exit(0)
    args = [a for a in sys.argv[1:] if a != "--all"]
    plays = args or sorted(d for d in os.listdir(PLAYS_ABS)
                           if os.path.isdir(os.path.join(PLAYS_ABS, d)))
    for p in plays:
        r = assemble(p)
        print(json.dumps(r, ensure_ascii=False))
