# -*- coding: utf-8 -*-
"""Rescue atoms the bulk HY run REJECTED, so nothing fails silently.

The bulk driver (run_dickens_hy.py) drops any atom whose assembled translation
fails validate() -- a malformed wikilink, a fabricated block, a block-count
mismatch -- into the log and moves on, no retry. A single dropped atom pins its
whole book at 99% forever and no completion mail ever fires. This tool closes
that hole:

  discover  -> rejected atoms (from the run log + dickens_rejected.jsonl) that
               are STILL missing their .it.md sibling
  per atom  -> 1. HY retry: re-translate with a FRESH cache (new stochastic
                  sample) up to --hy-tries times, strip stray codes, validate.
               2. Opus-5 fallback: mask the blocks, ask `claude -p --model
                  claude-opus-5` for a JSON array of N Italian blocks (tokens
                  carried through), write via opus_atom.py (unmask+validate).
               3. still failing -> dickens_unresolved.jsonl + a LOUD report.

Never silent: every atom prints a result, the run prints a summary, unresolved
atoms are listed and the process exits non-zero so a caller (the watcher) can
alert. stdlib + the local pipeline only.

Usage:
  python3 retranslate_rejected.py [--hy-tries 2] [--no-opus] [--book NAME]
"""
import os, sys, re, json, time, hashlib, tempfile, subprocess, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run_dickens_hy as _R          # noqa: F401  (applies the HY few-shot _ask patch)
import dickens_tower as dt

LOGFILES = [os.path.join(HERE, "run_logs", "dickens_hy.log"),
            os.path.join(HERE, "run_logs", "authors_hy.log")]
REJECTED = os.path.join(HERE, "run_logs", "dickens_rejected.jsonl")
UNRESOLVED = os.environ.get(
    "DICKENS_UNRESOLVED",
    os.path.join(HERE, "run_logs", "dickens_unresolved.jsonl"))
OPUS_ATOM = os.path.join(HERE, "opus_atom.py")
VAULT = dt.VAULT_ROOT

REJ_RE = re.compile(r"(?:REJECT|FAIL) (Authors/\S+?\.md):?\s*(.*)")


def log(m):
    print(time.strftime("%H:%M:%S"), m, flush=True)


def _load_unresolved():
    seen = set()
    if os.path.exists(UNRESOLVED):
        for line in open(UNRESOLVED, encoding="utf-8", errors="replace"):
            try:
                seen.add(json.loads(line)["atom"])
            except Exception:
                pass
    return seen


def discover(book=None, skip_unresolved=False, shard=None):
    """rel -> problems, for rejected atoms that still lack a .it.md.

    shard = (i, n): keep only atoms whose stable hash falls in slice i of n, so
    several runners can chew the same book concurrently without overlapping.
    """
    atoms = {}
    for logf in LOGFILES:
        if os.path.exists(logf):
            for line in open(logf, encoding="utf-8", errors="replace"):
                m = REJ_RE.search(line)
                if m:
                    atoms[m.group(1)] = m.group(2).strip()
    if os.path.exists(REJECTED):
        for line in open(REJECTED, encoding="utf-8", errors="replace"):
            try:
                d = json.loads(line)
                atoms[d["atom"]] = "; ".join(d.get("problems", [])) or d.get("problem", "")
            except Exception:
                pass
    skip = _load_unresolved() if skip_unresolved else set()
    out = {}
    for rel, prob in atoms.items():
        if book and book not in rel:
            continue
        if rel in skip:
            continue
        if shard:
            i, n = shard
            h = int(hashlib.sha1(rel.encode("utf-8")).hexdigest()[:8], 16)
            if h % n != i:
                continue
        if not os.path.exists(os.path.join(VAULT, rel[:-3] + ".it.md")):
            out[rel] = prob
    return out


def hy_retry(rel, tries):
    """Re-translate via HY with a throwaway cache (forces a fresh sample)."""
    en_path = os.path.join(VAULT, rel)
    en_body = dt._read_vault(en_path)
    verse = "/Poems/" in en_path or "/Long/" in en_path
    # --hy-tries 0 skips HY entirely and hands the atom straight to the Opus
    # fallback: when the reject reason is a leftover mask token, HY reproduces the
    # same failure and only contends with the bulk run for the local server.
    problems = ["HY skipped (--hy-tries 0)"]
    for t in range(tries):
        tmpcache = tempfile.mktemp(suffix=".jsonl")
        try:
            it_body = dt.translate_atom(en_path, dt.Cache(tmpcache), [])
            it_body = dt.strip_mask_codes(it_body)
            problems = dt.validate(en_body, it_body, verse)
            if not problems:
                dt._write_vault(en_path[:-3] + ".it.md", it_body)
                return True, f"HY retry #{t + 1}"
        except Exception as e:
            problems = [str(e)]
        finally:
            try:
                os.remove(tmpcache)
            except OSError:
                pass
    return False, f"HY {tries}x -> {problems}"


_PROMPT = (
    "You are a professional English->Italian literary translator. Below is a JSON "
    "array of {n} text blocks from a Dickens atom (simplified English). Translate "
    "EACH block into natural Italian.\n"
    "RULES, obey exactly:\n"
    "- Return ONLY a JSON array of EXACTLY {n} strings, block i = translation of "
    "input block i. No prose, no markdown, no code fence.\n"
    "- Keep every [[Lnn|label]] token: translate ONLY the label word after '|', keep "
    "the Lnn code and the [[ ]] brackets intact. Never invent new [[...]] tokens.\n"
    "- Block 0 is YAML frontmatter (starts with ---): return it BYTE-FOR-BYTE "
    "unchanged. Any heading keeps its structure.\n"
    "- Keep the same number of paragraphs inside each block.\n\n"
    "INPUT:\n{blocks}"
)


def _parse_array(text, n):
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.S).strip()
    i, j = t.find("["), t.rfind("]")
    if i < 0 or j < 0:
        return None
    try:
        arr = json.loads(t[i:j + 1])
    except Exception:
        return None
    return arr if isinstance(arr, list) and len(arr) == n else None


def opus_fallback(rel, timeout=900):
    en_path = os.path.join(VAULT, rel)
    body = open(en_path, encoding="utf-8").read()
    blocks = [dt.mask_links(b)[0] for b in dt.prose_blocks(body)]
    prompt = _PROMPT.format(n=len(blocks),
                            blocks=json.dumps(blocks, ensure_ascii=False))
    try:
        r = subprocess.run(["claude", "-p", prompt, "--model", "claude-opus-5"],
                           capture_output=True, text=True, timeout=timeout)
    except Exception as e:
        return False, f"opus CLI error: {e}"
    arr = _parse_array(r.stdout, len(blocks))
    if arr is None:
        return False, "opus output not a JSON array of N blocks"
    tmp = tempfile.mktemp(suffix=".json")
    json.dump(arr, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
    w = subprocess.run([sys.executable, OPUS_ATOM, "write", rel, tmp],
                       capture_output=True, text=True)
    try:
        os.remove(tmp)
    except OSError:
        pass
    if '"status": "OK"' in w.stdout:
        return True, "Opus-5"
    return False, f"opus write rejected: {w.stdout.strip()[:200]}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hy-tries", type=int, default=2)
    ap.add_argument("--no-opus", action="store_true")
    ap.add_argument("--book", default=None)
    ap.add_argument("--skip-unresolved", action="store_true",
                    help="don't re-attempt atoms already logged unresolved "
                         "(avoids re-hammering Opus every watcher poll)")
    ap.add_argument("--shard", default=None, metavar="I/N",
                    help="take only slice I of N of the atoms (0-based), so "
                         "several runners can share one book without overlap")
    args = ap.parse_args()

    shard = None
    if args.shard:
        i, n = (int(x) for x in args.shard.split("/"))
        shard = (i, n)

    rejected = discover(args.book, args.skip_unresolved, shard)
    log(f"### rescue rejected atoms | found {len(rejected)} still-missing")
    if not rejected:
        log("nothing to do -- no rejected atom lacks a .it.md")
        return 0

    fixed, unresolved = [], []
    for rel, prob in sorted(rejected.items()):
        log(f"  atom {rel}  (was: {prob or 'n/a'})")
        ok, how = hy_retry(rel, args.hy_tries)
        if not ok and not args.no_opus:
            ok2, how2 = opus_fallback(rel)
            ok, how = ok2, (how2 if ok2 else f"{how} | {how2}")
        if ok:
            fixed.append(rel)
            log(f"    -> FIXED via {how}")
        else:
            u = {"atom": rel, "problem": how, "ts": time.time()}
            unresolved.append(u)
            # Append now, not at the end: a run killed mid-loop (the watcher caps
            # it at 3600 s) would otherwise never persist its give-up set, and
            # --skip-unresolved would skip nothing on the next pass.
            os.makedirs(os.path.dirname(UNRESOLVED), exist_ok=True)
            with open(UNRESOLVED, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(u, ensure_ascii=False) + "\n")
            log(f"    -> UNRESOLVED: {how}")

    # Merge with any pre-existing unresolved atoms (that we may have skipped this
    # pass) so the give-up set persists across runs; drop any now fixed.
    fixed_set = set(fixed)
    merged = {u["atom"]: u for u in unresolved}
    if os.path.exists(UNRESOLVED):
        for line in open(UNRESOLVED, encoding="utf-8", errors="replace"):
            try:
                d = json.loads(line)
            except Exception:
                continue
            rel = d.get("atom")
            if not rel or rel in fixed_set or rel in merged:
                continue
            if os.path.exists(os.path.join(VAULT, rel[:-3] + ".it.md")):
                continue          # got fixed elsewhere
            merged[rel] = d
    os.makedirs(os.path.dirname(UNRESOLVED), exist_ok=True)
    with open(UNRESOLVED, "w", encoding="utf-8") as fh:
        for u in merged.values():
            fh.write(json.dumps(u, ensure_ascii=False) + "\n")

    log(f"### done | fixed {len(fixed)} | UNRESOLVED {len(unresolved)}")
    for u in unresolved:
        log(f"    !!! still broken: {u['atom']} -- {u['problem']}")
    return 1 if unresolved else 0


if __name__ == "__main__":
    raise SystemExit(main())
