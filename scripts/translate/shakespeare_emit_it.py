# -*- coding: utf-8 -*-
"""Upsert the translated play scenes into data/translations_pages.jsonl.

The scene translations live in the vault as `.it.md` siblings — `Plays/Macbeth/Act_1/Scene_1.md`
next to `Scene_1.it.md` — and 882 of them exist. preprocess.mjs does NOT read them: it looks
every atom up in data/translations_pages.jsonl, keyed by the content-relative path the atom
WOULD have had as a standalone page:

    testi/shakespeare/plays/macbeth/act_1/scene_1.md

(that key survives SPA mode, where the atom is a fragment of one play page rather than a page
of its own — see the `translations.get(unitRel)` call in publishUnits). Nothing had ever written
those keys, so every translated scene was silently published English-only: no error, no warning,
the page simply had no Italian half.

This is the missing step. It is NOT gkc_emit_vault.py's job — that one reconstructs a page by
matching sha(EN prose block), and a play scene is a markdown table, not prose blocks.

  emit [Play ...]        upsert the named plays (all plays if none)
  emit --check           validate only, write nothing

Each scene is gated before it is written: the EN and IT tables must have the same number of rows
and the same multiset of wikilink targets. A scene that fails is reported and skipped, never
written — the same contract shakespeare_check.py enforces, re-checked here because this is the
step that makes a translation public.
"""
import os, re, sys, json, collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dickens_tower as dt

PLAYS = os.path.join(dt.VAULT_ROOT, "Authors", "Shakespeare", "Plays")
STORE = os.path.join(dt.ROOT, "data", "translations_pages.jsonl")
REL_PREFIX = "testi/shakespeare/plays"

FM_RE = re.compile(r"^---\r?\n.*?\r?\n---\r?\n?", re.S)
H1_RE = re.compile(r"\A\s*#\s+[^\n]*\n")
# A wikilink's TARGET is everything before the first pipe. Two files agree when the ordered
# multiset of targets agrees — the labels differ by design (they are translated).
LINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]")
ROW_RE = re.compile(r"^\|.*\|\s*$", re.M)


def body_of(path):
    with open(path, encoding="utf-8") as fh:
        txt = fh.read()
    txt = FM_RE.sub("", txt, count=1)
    # preprocess strips a leading wikilink H1 for us but not a plain one, and a play scene's
    # heading is plain ("# Macbeth — Atto I, Scena 1"), so it would otherwise surface inside
    # the reader as a stray heading.
    txt = H1_RE.sub("", txt, count=1)
    return txt.strip()


def links(s):
    return collections.Counter(m.group(1) for m in LINK_RE.finditer(s))


def rows(s):
    return [r for r in ROW_RE.findall(s) if not re.match(r"^\|[\s:|-]+\|$", r)]


def scene_pairs(play_dir):
    """(rel, en_path, it_path) for every translated scene atom of one play."""
    out = []
    for root, _dirs, files in os.walk(play_dir):
        for fn in sorted(files):
            if not fn.endswith(".it.md"):
                continue
            en = os.path.join(root, fn[: -len(".it.md")] + ".md")
            if not os.path.exists(en):
                print(json.dumps({"skip": "no EN sibling", "it": os.path.join(root, fn)}))
                continue
            rel_fs = os.path.relpath(en, PLAYS).replace(os.sep, "/")
            parts = rel_fs.split("/")
            if len(parts) < 3:
                # The play-level `<Play>/<Play>.it.md`, which shakespeare_assemble.py builds from
                # the scenes. It is a page in its own right - content/testi/shakespeare/plays/
                # macbeth.md - so it needs its own, shallower key. Skipping it here (as this did
                # until now) left every assembled play published English-only, the same silent
                # failure that kept the scenes untranslated: assembling into the vault is not
                # publishing.
                if len(parts) == 2 and parts[1] == parts[0] + ".md":
                    out.append((f"{REL_PREFIX}/{parts[0]}.md".lower(), en, os.path.join(root, fn)))
                continue
            out.append((f"{REL_PREFIX}/{rel_fs}".lower(), en, os.path.join(root, fn)))
    return out


def main(argv):
    check_only = "--check" in argv
    names = [a for a in argv if not a.startswith("--")]
    plays = names or sorted(
        d for d in os.listdir(PLAYS) if os.path.isdir(os.path.join(PLAYS, d))
    )

    fresh, failures = {}, []
    for play in plays:
        d = os.path.join(PLAYS, play)
        if not os.path.isdir(d):
            print(json.dumps({"play": play, "status": "NO SUCH PLAY"}))
            continue
        ok = 0
        for rel, en_path, it_path in scene_pairs(d):
            en, it = body_of(en_path), body_of(it_path)
            en_rows, it_rows = rows(en), rows(it)
            if len(en_rows) != len(it_rows):
                failures.append((rel, f"rows {len(en_rows)} EN vs {len(it_rows)} IT"))
                continue
            if links(en) != links(it):
                missing = links(en) - links(it)
                extra = links(it) - links(en)
                failures.append((rel, f"links -{sorted(missing)} +{sorted(extra)}"))
                continue
            fresh[rel] = {"rel": rel, "kind": "testi", "body_it": it}
            ok += 1
        print(json.dumps({"play": play, "scenes_ok": ok}))

    for rel, why in failures:
        print(json.dumps({"FAIL": rel, "why": why}))
    print(json.dumps({"total_ok": len(fresh), "total_failed": len(failures)}))

    if check_only:
        return 0 if not failures else 1

    # Upsert: keep every entry this run did not produce, then append ours. Other authors'
    # translations live in the same file and must survive untouched.
    kept = []
    if os.path.exists(STORE):
        with open(STORE, encoding="utf-8") as fh:
            for ln in fh:
                if not ln.strip():
                    continue
                e = json.loads(ln)
                if e.get("rel") not in fresh:
                    kept.append(e)
    tmp = STORE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        for e in kept:
            fh.write(json.dumps(e, ensure_ascii=False) + "\n")
        for rel in sorted(fresh):
            fh.write(json.dumps(fresh[rel], ensure_ascii=False) + "\n")
    os.replace(tmp, STORE)
    print(json.dumps({"store": STORE, "kept": len(kept), "written": len(fresh)}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
