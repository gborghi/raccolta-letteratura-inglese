# -*- coding: utf-8 -*-
"""Repair truncated wikilinks in Dickens H1 headings (source-data artifact from atomisation).

The atomiser cut the closing ']]' off the final wikilink of a chapter-title heading, sometimes
leaving a ' (part N)' suffix jammed INSIDE the link:
    '# ... MARLEY'S [[Ghost|GHOST (part 1)'   ->  '# ... MARLEY'S [[Ghost|GHOST]] (part 1)'
    '# ... On the [[Road'                      ->  '# ... On the [[Road]]'
These render as literal '[[...' text on the published English pages (and break masking for the
Italian translation). Fix: on any line with more '[[' than ']]', close the LAST unclosed link,
pushing any trailing ' (part N)' back outside the brackets.

Usage:
  python3 fix_malformed_headings.py            # DRY RUN: print every before/after, change nothing
  python3 fix_malformed_headings.py --write     # apply in place
Only lines that become bracket-balanced after the fix are written; anything else is reported and
left untouched.
"""
import os, re, sys

BASE = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "..", "..", "..", "VaultEnglish", "Authors", "Dickens", "Atomized"))

# Close the last unclosed '[[<body>' at end of line, moving a trailing ' (part N)' out of the link.
# [^\[\]]+? = the link body (target, or target|label); it cannot cross a ']' so an earlier
# well-formed link on the same line is never touched. The optional group captures ' (part N)'.
FIX_RE = re.compile(r"\[\[([^\[\]]+?)(\s*\(part \d+\))?$")


def fix_line(line):
    if line.count("[[") <= line.count("]]"):
        return line, False
    new = FIX_RE.sub(lambda m: "[[%s]]%s" % (m.group(1), m.group(2) or ""), line, count=1)
    if new == line:
        return line, False
    if new.count("[[") != new.count("]]"):   # still unbalanced -> refuse, report
        return line, None
    return new, True


def main():
    write = "--write" in sys.argv
    files_changed = lines_changed = refused = 0
    for dp, _, fns in os.walk(BASE):
        for fn in sorted(fns):
            if not fn.endswith(".md") or fn.endswith(".it.md"):
                continue
            p = os.path.join(dp, fn)
            try:
                lines = open(p, encoding="utf-8").read().split("\n")
            except Exception:
                continue
            changed = False
            for i, line in enumerate(lines):
                new, ok = fix_line(line)
                if ok is None:
                    print(f"!! REFUSED (still unbalanced) {os.path.relpath(p, BASE)}:{i+1}\n   {line}")
                    refused += 1
                    continue
                if ok:
                    print(f"{os.path.relpath(p, BASE)}:{i+1}")
                    print(f"  -  {line}")
                    print(f"  +  {new}")
                    lines[i] = new
                    changed = True
                    lines_changed += 1
            if changed:
                files_changed += 1
                if write:
                    with open(p, "w", encoding="utf-8") as fh:
                        fh.write("\n".join(lines))
    print(f"\n{'WROTE' if write else 'DRY RUN'}: {lines_changed} lines in {files_changed} files"
          + (f", {refused} REFUSED" if refused else ""))


if __name__ == "__main__":
    main()
