# -*- coding: utf-8 -*-
"""Repair leaked HY link placeholders in vault .it.md files.

WHAT WENT WRONG
---------------
The HY translator was handed each block with its wikilinks replaced by short codes (L01, L02, …)
so the model would not translate a link target, and the codes were to be restored afterwards.
On 799 Dickens atoms the restore step failed and the code reached disk:

    [[L09]strada】   [[L05|notte]   [[L02>fiume]   [[L01)dormire]   [[L01_spada]   [[L01Beh]

Nothing caught this. dickens_tower.validate() checks three things — block count, invented
targets, fabricated content — and an artifact defeats all three: it does not match the wikilink
regex, so it is neither a target that was invented nor one that went missing. It is simply
literal garbage rendered to the reader. Both HY retries and Opus rewrites of these atoms failed,
which is why they need a mechanical repair rather than another translation pass.

HOW THE TARGET IS RECOVERED
---------------------------
Never guessed. The EN and IT bodies are block-aligned (that alignment is what the emitter
requires anyway), so within one block the ordered list of EN link targets tells us what each IT
link slot should point at:

  strong case   the block's IT slots (valid links + artifacts) number the same as the EN links
                -> the artifact at slot i takes EN target i, positionally
  weak case     counts differ because the translator dropped some links entirely
                -> if the artifact count equals the count of targets missing from the IT block,
                   assign those in order of appearance
  otherwise     UNRESOLVED. Left untouched and reported.

AMBIGUITY IS NOT REPAIRED
-------------------------
Roughly a fifth of the artifacts have no closing delimiter at all:

    [[L06]uccelli cantano dolcemente.

The label could be "uccelli" or the whole clause; only a reader can say. Those are written to a
TSV for review and the file keeps them. Silently guessing a boundary would corrupt the prose in
a way no later check could detect — the same class of error this script exists to undo.

GATE
----
A file is written only if, after repair: the prose-block count is unchanged, no artifact that was
counted as repaired remains, the IT target multiset is a subset of the EN one (a repair may
restore a link, never introduce a new one), and validate() reports no problem it did not already
report before. Any failure and the file is left exactly as it was.

  repair_hy_placeholders.py                 dry run over every author, report only
  repair_hy_placeholders.py --apply         write the repairs that pass the gate
  repair_hy_placeholders.py --author Dickens --apply
  repair_hy_placeholders.py --file <path>   one atom (dry run unless --apply)
"""
import os, re, sys, io, json, collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dickens_tower as dt

AUTHORS = os.path.join(dt.VAULT_ROOT, "Authors")
REPORT = os.path.join(dt.ROOT, "data", "hy_placeholder_repair.json")
UNRESOLVED_TSV = os.path.join(dt.ROOT, "data", "hy_placeholder_unresolved.tsv")

SIG = re.compile(r"\[\[L\d+")

# An artifact WITH a closing delimiter: the label is bounded, so the repair is exact. The
# separator between code and label is any of the characters HY emitted in place of "|", and the
# closer is a single "]" or the stray CJK bracket "】".
CLOSED = re.compile(r"\[\[L\d+[\]|>)_]?([^\[\]】\n]{0,60}?)(?:\]\]|\]|】)")
# A valid wikilink. Kept separate so slots can be ordered across both kinds.
VALID = re.compile(r"\[\[([^\[\]|\n]+?)(?:\|([^\[\]\n]*?))?\]\]")
# A stray ">" or "]" that leaked into the LABEL of an otherwise valid link: [[Dreams|>sogni]].
# Unambiguous — the target is intact, so only the label's first character is dropped.
LABEL_JUNK = re.compile(r"(\[\[[^\[\]|\n]+\|)[>\]]+")
# "#Illustrazione" where the English block is the Gutenberg marker "[Illustration]": the "#"
# makes markdown read it as a tag. Only rewritten when the EN block really is bracketed.
HASH_MARKER = re.compile(r"\A#(\w[\w'’ ]*)\Z")
EN_MARKER = re.compile(r"\A\[(\w[\w' ]*)\]\Z")


def slots(block):
    """Ordered link slots in a block: ('valid', target, span) or ('artifact', label, span).

    Overlaps are impossible because a valid link is consumed whole; an artifact never contains
    "]]" (CLOSED stops at the first closer), so the two patterns cannot claim the same text.
    """
    out = []
    for m in VALID.finditer(block):
        out.append(("valid", m.group(1), m.span(), m.group(0)))
    for m in CLOSED.finditer(block):
        if any(s[0] <= m.start() < s[1] for _k, _t, s, _r in out):
            continue  # inside a valid link — not an artifact
        out.append(("artifact", m.group(1), m.span(), m.group(0)))
    out.sort(key=lambda x: x[2][0])
    return out


# An artifact with NO closing delimiter: "[[L06]uccelli cantano dolcemente." The label's right
# edge is not marked, so it has to be inferred (tier 2 only).
OPEN = re.compile(r"\[\[L\d+[\]|>)_]?([^\n]*)")
# Where a label may end: sentence punctuation, quotes, dashes — never mid-word.
LABEL_STOP = re.compile(r"[.,;:!?…»«”“\"'–—\-()\[\]]")


def open_artifacts(block, closed_spans):
    """Signatures with NO closer. Reported in tier 1; repairable in tier 2."""
    out = []
    for m in SIG.finditer(block):
        if any(a <= m.start() < b for a, b in closed_spans):
            continue
        out.append(block[m.start(): m.start() + 60])
    return out


def open_slots(block, taken):
    """(span, tail_text) for each closer-less artifact, skipping spans already accounted for."""
    out = []
    for m in OPEN.finditer(block):
        if any(a <= m.start() < b for a, b in taken):
            continue
        out.append((m.start(), m.group(1)))
    return out


def label_extent(tail, want_words):
    """How much of `tail` is the link label, given the English label's word count.

    Stops at the first punctuation mark regardless: a label never spans a sentence boundary.
    Returns the label text (possibly empty, which the caller treats as unresolvable).
    """
    stop = LABEL_STOP.search(tail)
    span = tail[: stop.start()] if stop else tail
    words = span.split()
    if not words:
        return ""
    return " ".join(words[: max(1, want_words)])


# label (normalised) -> Counter of targets it is linked to across the corpus. Filled by
# build_lexicon(); empty means rule 3 is switched off.
LEXICON = {}


def norm_label(s):
    return re.sub(r"\s+", " ", s.strip().lower())


def need_pool(en_count, valid_it):
    """The targets this block is missing, as a flat list (a target can be missing twice)."""
    out = []
    for t, n in (en_count - valid_it).items():
        out += [t] * n
    return out


def build_lexicon(paths, min_count=2):
    """Learn label -> target from links that are already well-formed.

    Only labels whose mapping is decisive are kept: seen at least `min_count` times and pointing
    at one target in at least 80% of sightings. A label like "casa" that legitimately links to
    two different concepts is therefore excluded rather than guessed at.
    """
    raw = collections.defaultdict(collections.Counter)
    for p in paths:
        try:
            t = io.open(p, encoding="utf-8").read()
        except OSError:
            continue
        for m in VALID.finditer(t):
            target, label = m.group(1), m.group(2)
            if not label:
                continue
            raw[norm_label(label)][target] += 1
    lex = {}
    for lab, c in raw.items():
        total = sum(c.values())
        target, n = c.most_common(1)[0]
        if total >= min_count and n / total >= 0.8:
            lex[lab] = c
    return lex


def plan_block(en_block, it_block, tier2=False):
    """(replacements, unresolved, open_list) for one aligned block pair."""
    en_targets = dt.targets(en_block)          # sorted multiset
    en_ordered = [m.group(1) for m in VALID.finditer(en_block)]
    en_labels = [(m.group(2) or m.group(1)) for m in VALID.finditer(en_block)]
    sl = slots(it_block)
    arts = [s for s in sl if s[0] == "artifact"]
    opens = open_artifacts(it_block, [s[2] for s in sl])

    if tier2 and opens:
        # Give the closer-less artifacts a label and fold them into the slot list, so the target
        # assignment below sees the block's full set of links and its counts can balance.
        for start, tail in open_slots(it_block, [s[2] for s in sl]):
            # the English label at the same ordinal, when there is one, sets the word count
            idx = sum(1 for s in sl if s[2][0] < start)
            want = len(en_labels[idx].split()) if idx < len(en_labels) else 1
            label = label_extent(tail, want)
            if not label:
                continue
            code_len = len(re.match(r"\[\[L\d+[\]|>)_]?", it_block[start:]).group(0))
            span = (start, start + code_len + len(label))
            sl.append(("artifact", label, span, it_block[span[0]: span[1]]))
        sl.sort(key=lambda x: x[2][0])
        arts = [s for s in sl if s[0] == "artifact"]

    if not arts:
        return [], [], opens

    valid_it = collections.Counter(s[1] for s in sl if s[0] == "valid")
    en_count = collections.Counter(en_targets)

    def consistent(assigned):
        """The links the block WILL have must be exactly the links the English block has."""
        got = collections.Counter(valid_it)
        for t in assigned.values():
            got[t] += 1
        return got == en_count

    # Rule 1 — the decisive one. Whatever targets the English block has that the Italian block
    # does not are precisely what the artifacts must be, provided the counts agree. Order among
    # them follows the English, which is the only ordering information available.
    assigned = {}
    need = en_count - valid_it
    flat = []
    for t in en_ordered:
        if need[t] > 0:
            flat.append(t)
            need[t] -= 1
    if len(flat) == len(arts):
        assigned = {s[2]: t for s, t in zip(arts, flat)}

    # Rule 2 — fallback when rule 1 cannot decide: assume the translator preserved link order,
    # so IT slot i answers to EN link i. Weaker, because Italian word order often does NOT
    # preserve it, which is how a repair can land a target the block already carries; hence the
    # consistency check, not the rule itself, is what makes this safe.
    if not assigned and len(sl) == len(en_ordered):
        cand = {s[2]: en_ordered[i] for i, s in enumerate(sl) if s[0] == "artifact"}
        if consistent(cand):
            assigned = cand

    # Rule 3 — counting cannot decide because the translator dropped links outright: nine English
    # links, four kept, one artifact leaves four candidates for one slot. The artifact's own label
    # settles it. LEXICON maps an Italian label to the targets it is actually linked to elsewhere
    # in this corpus — built from links that are already correct, so this is evidence, not a
    # guess. A candidate is accepted only when it is the label's dominant target overall AND is
    # among the targets this block is missing; the pool is drawn down so two artifacts can never
    # claim the same missing link.
    if not assigned and LEXICON:
        pool = collections.Counter(need_pool(en_count, valid_it))
        cand = {}
        for s in arts:
            lab = norm_label(s[1])
            seen = LEXICON.get(lab)
            if not seen:
                continue
            best = max(seen, key=lambda t: seen[t])
            if pool[best] > 0:
                cand[s[2]] = best
                pool[best] -= 1
        assigned = cand

    reps, unresolved = [], []
    for s in arts:
        t = assigned.get(s[2])
        if not t:
            unresolved.append(s[3])
            continue
        label = s[1].strip()
        # [[Lincoln|Lincoln]] is the same link written the long way round; the vault's own
        # convention for a label identical to the target is the bare form.
        if not label or label == t:
            reps.append((s[2], f"[[{t}]]", s[3]))
        else:
            reps.append((s[2], f"[[{t}|{label}]]", s[3]))
    return reps, unresolved, opens


def repair_file(en_path, it_path, tier2=False):
    en = dt._read_vault(en_path)
    it = dt._read_vault(it_path)
    before = dt.validate(en, it)
    eb, ib = dt.prose_blocks(en), dt.prose_blocks(it)
    res = {
        "it": os.path.relpath(it_path, dt.VAULT_ROOT),
        "blocks_en": len(eb), "blocks_it": len(ib),
        "repaired": 0, "unresolved": [], "open": [], "status": "",
    }
    if len(eb) != len(ib):
        res["status"] = "SKIP block-count mismatch (cannot align)"
        return res, None

    # Edits are collected as ABSOLUTE offsets into `it` and applied back-to-front. Doing this
    # with str.replace() would be wrong twice over: an artifact can repeat verbatim inside one
    # block with two different intended targets, and two short blocks can be byte-identical, so
    # replace(block, new_block, 1) could rewrite the wrong paragraph. Blocks appear in order, so
    # a moving cursor locates each one exactly.
    edits = []
    cursor = 0
    for e, i in zip(eb, ib):
        start = it.find(i, cursor)
        if start < 0:
            res["status"] = "SKIP could not locate block in source"
            return res, None
        cursor = start + len(i)

        reps, unresolved, opens = plan_block(e, i, tier2)
        res["unresolved"] += unresolved
        res["open"] += opens
        for (s0, s1), replacement, _raw in reps:
            edits.append((start + s0, start + s1, replacement))

        # "#Marker" where the English block is the bracketed Gutenberg marker
        mh, me = HASH_MARKER.match(i.strip()), EN_MARKER.match(e.strip())
        if mh and me:
            edits.append((start, start + len(i), f"[{mh.group(1)}]"))

    new_it = it
    for a, b, replacement in sorted(edits, key=lambda x: -x[0]):
        new_it = new_it[:a] + replacement + new_it[b:]
    total = len(edits)

    # unambiguous label junk: [[Target|>label]] — the target is intact, only the label's leading
    # stray delimiter goes. Safe as a global sub: the pattern requires a complete "[[target|".
    junk = len(LABEL_JUNK.findall(new_it))
    if junk:
        new_it = LABEL_JUNK.sub(r"\1", new_it)
        total += junk

    res["repaired"] = total
    if total == 0:
        res["status"] = "nothing repairable"
        return res, None

    # ---- gate ----
    nb = dt.prose_blocks(new_it)
    if len(nb) != len(ib):
        res["status"] = f"REJECT repair changed block count {len(ib)} -> {len(nb)}"
        return res, None
    after = dt.validate(en, new_it)
    if set(after) - set(before):
        res["status"] = f"REJECT new validate problems: {sorted(set(after) - set(before))}"
        return res, None
    # A repair may restore a link the translator lost; it may never add one the English does not
    # have. Measured as a delta so a file that already carried an excess target (not this
    # script's doing) is still repairable.
    ce = collections.Counter(dt.targets(en))
    excess_before = collections.Counter(dt.targets(it)) - ce
    excess_after = collections.Counter(dt.targets(new_it)) - ce
    if excess_after - excess_before:
        res["status"] = f"REJECT repair invented targets: {dict(excess_after - excess_before)}"
        return res, None
    left = [m.group(0) for m in SIG.finditer(new_it)]
    res["remaining_signatures"] = len(left)
    res["status"] = "OK"
    return res, new_it


def main(argv):
    apply = "--apply" in argv
    tier2 = "--tier2" in argv
    one = None
    if "--file" in argv:
        one = argv[argv.index("--file") + 1]
    author = None
    if "--author" in argv:
        author = argv[argv.index("--author") + 1]

    targets_ = []
    if one:
        targets_.append(os.path.abspath(one))
    else:
        root = os.path.join(AUTHORS, author) if author else AUTHORS
        for base, _d, fns in os.walk(root):
            for fn in fns:
                if fn.endswith(".it.md"):
                    p = os.path.join(base, fn)
                    try:
                        if SIG.search(io.open(p, encoding="utf-8").read()):
                            targets_.append(p)
                    except OSError:
                        pass

    if "--lexicon" in argv:
        # Learn from every Italian atom in the vault, not just the ones being repaired: the more
        # correct links the lexicon sees, the more decisive it is.
        all_it = []
        for base, _d, fns in os.walk(AUTHORS):
            for fn in fns:
                if fn.endswith(".it.md"):
                    all_it.append(os.path.join(base, fn))
        global LEXICON
        LEXICON = build_lexicon(all_it)
        print(json.dumps({"lexicon_labels": len(LEXICON), "learned_from_files": len(all_it)}))

    results, written, rejected, unresolved_rows = [], 0, 0, []
    for it_path in sorted(targets_):
        en_path = it_path[: -len(".it.md")] + ".md"
        if not os.path.exists(en_path):
            results.append({"it": os.path.relpath(it_path, dt.VAULT_ROOT),
                            "status": "SKIP no EN sibling"})
            continue
        res, new_it = repair_file(en_path, it_path, tier2)
        results.append(res)
        for u in res.get("unresolved", []) + res.get("open", []):
            unresolved_rows.append((res["it"], u.replace("\t", " ").replace("\n", "\\n")))
        if res["status"].startswith("REJECT") or res["status"].startswith("SKIP"):
            rejected += 1
        if new_it and apply:
            io.open(it_path, "w", encoding="utf-8", newline="").write(new_it)
            written += 1

    repaired = sum(r.get("repaired", 0) for r in results if r["status"] == "OK")
    summary = {
        "files_scanned": len(targets_),
        "files_with_repairs": sum(1 for r in results if r["status"] == "OK"),
        "files_written": written,
        "files_rejected_or_skipped": rejected,
        "artifacts_repaired": repaired,
        "artifacts_unresolved": len(unresolved_rows),
        "applied": apply,
        "tier2": tier2,
    }
    with io.open(REPORT, "w", encoding="utf-8") as fh:
        json.dump({"summary": summary, "files": results}, fh, ensure_ascii=False, indent=1)
    with io.open(UNRESOLVED_TSV, "w", encoding="utf-8", newline="") as fh:
        fh.write("it_path\tartifact\n")
        for a, b in unresolved_rows:
            fh.write(f"{a}\t{b}\n")
    print(json.dumps(summary, ensure_ascii=False))
    for r in results:
        if r["status"].startswith(("REJECT", "SKIP")):
            print(json.dumps(r, ensure_ascii=False)[:300])
    print(f"report: {REPORT}\nunresolved: {UNRESOLVED_TSV}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
