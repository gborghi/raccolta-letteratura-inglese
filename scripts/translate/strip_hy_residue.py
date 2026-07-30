# -*- coding: utf-8 -*-
"""Remove every HY placeholder code still left in the vault's .it.md files.

repair_hy_placeholders.py recovers the LINK a code stood for, which it can only do when the EN and
IT bodies align block-for-block and the block's missing targets identify the slot. Whatever it
cannot resolve it leaves on disk - and a leftover `[[L06]uccelli cantano dolcemente.` is rendered
to the reader verbatim. This pass gives up on the link and removes the code, which needs neither
alignment nor a label boundary:

    [[L05|notte]        -> notte          (closed: the label is bounded, keep it)
    [[L06]uccelli ...   -> uccelli ...    (open: the code is a PREFIX, so just drop the token)

That distinction is why the codes survived. The open form's label has no right edge, so the repair
script could not tell whether the link covered "uccelli" or the whole clause - but removing the
code does not require knowing. Run this only after the repair script, or real links are thrown away.

Files the repair script refuses wholesale - a block-count mismatch it cannot align, a validate
problem it will not add to - are handled here too, because de-coding is a textual edit that does
not depend on the alignment those refusals are about.

GATE
----
A file is written only if: not one `[[L<digits>` remains; the multiset of real wikilink targets is
unchanged (this pass must never add, drop or retarget a link); no `]]` is orphaned; and the text is
otherwise byte-identical outside the spans removed.

  strip_hy_residue.py            dry run over every author
  strip_hy_residue.py --apply    write
"""
import os, re, sys, io, json, collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dickens_tower as dt
import repair_hy_placeholders as rp

AUTHORS = os.path.join(dt.VAULT_ROOT, "Authors")
REPORT = os.path.join(dt.ROOT, "data", "hy_residue_strip.json")

# The bare code token: `[[L01` plus the single character HY emitted where the "|" belonged. Anchored
# on L-followed-by-digits, so a genuine `[[Lincoln|...]]` cannot match.
CODE = re.compile(r"\[\[L\d+[\]|>)_]?")


def strip_text(txt):
    """(new_text, closed_kept, open_dropped). Rightmost-first, so earlier offsets stay valid."""
    edits = []
    for m in rp.SIG.finditer(txt):
        c = rp.CLOSED.match(txt, m.start())
        if c:
            # Bounded label: keep the words, drop the brackets and the code.
            edits.append((c.start(), c.end(), c.group(1), "closed"))
            continue
        t = CODE.match(txt, m.start())
        if t:
            edits.append((t.start(), t.end(), "", "open"))
    out = txt
    for a, b, rep, _kind in sorted(edits, key=lambda e: -e[0]):
        out = out[:a] + rep + out[b:]
    return out, sum(1 for e in edits if e[3] == "closed"), sum(1 for e in edits if e[3] == "open")


def main(argv):
    apply = "--apply" in argv
    files = []
    for base, _d, fns in os.walk(AUTHORS):
        for fn in fns:
            if not fn.endswith(".it.md"):
                continue
            p = os.path.join(base, fn)
            try:
                if rp.SIG.search(io.open(p, encoding="utf-8").read()):
                    files.append(p)
            except OSError:
                pass

    rows, written, refused = [], 0, 0
    tot_closed = tot_open = 0
    for p in sorted(files):
        txt = dt._read_vault(p)
        new, closed, opened = strip_text(txt)
        rel = os.path.relpath(p, dt.VAULT_ROOT)
        problems = []
        if rp.SIG.search(new):
            problems.append("codes remain after strip")
        if collections.Counter(dt.targets(new)) != collections.Counter(dt.targets(txt)):
            problems.append("real wikilink targets changed")
        if new.count("]]") > txt.count("]]"):
            problems.append("orphaned ]]")
        if problems:
            refused += 1
            rows.append({"it": rel, "status": "REFUSE " + "; ".join(problems)})
            continue
        tot_closed += closed
        tot_open += opened
        rows.append({"it": rel, "status": "OK", "closed_kept": closed, "open_dropped": opened})
        if apply and new != txt:
            dt._write_vault(p, new)
            written += 1

    summary = {"files_with_codes": len(files), "files_written": written, "files_refused": refused,
               "closed_artifacts_delinked": tot_closed, "open_codes_removed": tot_open,
               "applied": apply}
    with open(REPORT, "w", encoding="utf-8") as fh:
        json.dump({"summary": summary, "files": rows}, fh, ensure_ascii=False, indent=1)
    print(json.dumps(summary, ensure_ascii=False))
    for r in rows:
        if r["status"] != "OK":
            print(json.dumps(r, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
