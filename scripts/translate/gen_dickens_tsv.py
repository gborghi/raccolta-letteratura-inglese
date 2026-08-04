# -*- coding: utf-8 -*-
"""Generate a <work>_atoms.tsv leaf-atom list for any Dickens work, in the exact shape
dickens_tower.py consumes (one column `vault_en_path`, header row, sorted leaf atoms).

Leaf-atom rule (verified against the hand-built great_expectations_atoms.tsv and
oliver_twist_atoms.tsv -- reproduces both EXACTLY):
  A .md file under Authors/Dickens/Atomized/<Work>/ is a leaf reading unit unless it is an
  AGGREGATE:
    * a per-chapter aggregate <stem>.md sitting beside a subdirectory named <stem>/ (the parts
      of that chapter live in the dir), or
    * the whole-book aggregate <Work>/<Work>.md (the entire novel concatenated).
  .it.md siblings are never atoms.

Usage:
  python3 gen_dickens_tsv.py <Work_Dir_Name> [<Work_Dir_Name> ...]
  python3 gen_dickens_tsv.py --all        # every work dir under Atomized/ that has no *_atoms.tsv yet
  python3 gen_dickens_tsv.py --verify      # re-derive GE + Oliver and assert byte-identical sets
Writes <work_lower>_atoms.tsv next to this script. Idempotent.
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", "VaultEnglish"))
BASE = os.path.join(VAULT_ROOT, "Authors", "Dickens", "Atomized")


def leaf_atoms(work):
    wd = os.path.join(BASE, work)
    leaves = []
    for dirpath, dirnames, filenames in os.walk(wd):
        dset = set(dirnames)
        for fn in filenames:
            if not fn.endswith(".md") or fn.endswith(".it.md"):
                continue
            stem = fn[:-3]
            if stem in dset:                    # per-chapter aggregate beside its parts dir
                continue
            if dirpath == wd and stem == work:  # whole-book aggregate <Work>/<Work>.md
                continue
            leaves.append(os.path.relpath(os.path.join(dirpath, fn), VAULT_ROOT).replace(os.sep, "/"))
    return sorted(leaves)


def tsv_path(work):
    return os.path.join(HERE, work.lower() + "_atoms.tsv")


def write_tsv(work):
    leaves = leaf_atoms(work)
    if not leaves:
        print(f"!! {work}: no leaf atoms found (missing dir?)")
        return 0
    with open(tsv_path(work), "w", encoding="utf-8") as fh:
        fh.write("vault_en_path\n")
        for x in leaves:
            fh.write(x + "\n")
    print(f"  {work}: {len(leaves)} atoms -> {os.path.basename(tsv_path(work))}")
    return len(leaves)


def read_tsv_set(p):
    out = set()
    with open(p, encoding="utf-8") as f:
        for i, ln in enumerate(f):
            ln = ln.strip()
            if i == 0 and ln == "vault_en_path":
                continue
            if ln:
                out.add(ln)
    return out


def verify():
    ok = True
    for work, tsv in [("Great_Expectations", "great_expectations_atoms.tsv"),
                      ("Oliver_Twist", "oliver_twist_atoms.tsv")]:
        gen = set(leaf_atoms(work))
        ref = read_tsv_set(os.path.join(HERE, tsv))
        same = gen == ref
        ok = ok and same
        print(f"  {work}: gen={len(gen)} ref={len(ref)} -> {'MATCH' if same else 'MISMATCH'}")
        if not same:
            print("    +gen", sorted(gen - ref)[:5])
            print("    -ref", sorted(ref - gen)[:5])
    print("VERIFY OK" if ok else "VERIFY FAILED")
    return ok


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or "--verify" in args:
        verify()
        if args == ["--verify"] or not args:
            sys.exit(0)
    if "--all" in args:
        works = sorted(d for d in os.listdir(BASE) if os.path.isdir(os.path.join(BASE, d)))
        works = [w for w in works if not os.path.exists(tsv_path(w))]
        print(f"generating TSVs for {len(works)} works with no existing TSV:")
        for w in works:
            write_tsv(w)
    else:
        for w in args:
            if w.startswith("--"):
                continue
            write_tsv(w)
