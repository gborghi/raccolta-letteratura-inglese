# -*- coding: utf-8 -*-
"""Retranslate Cymbeline scenes EN->IT using DeepSeek via ds.py CLI.

Each scene's EN .md body is sent to ds.py (DeepSeek API) for literary translation.
Preserves wikilinks, pipe-table format, <br> line breaks, and stage directions.

Usage: python ds_retranslate_cymbeline.py [--dry-run] [--start N]
"""
import os, sys, subprocess, time, argparse, glob

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..")
VAULT = os.path.join(ROOT, "..", "VaultEnglish")
PLAY_DIR = os.path.join(VAULT, "Authors", "Shakespeare", "Plays", "Cymbeline")

SYSTEM_PROMPT = """You are translating Shakespeare's Cymbeline from English to literary Italian.
Rules:
- Preserve the EXACT pipe-table format: | Speaker | Line |
- Translate speaker names to Italian (FIRST GENTLEMAN -> PRIMO GENTILUOMO, etc.)
- Translate stage directions: *(didascalia)* | Enter... -> *(didascalia)* | Entra/Entrano...
- Translate the scene heading: # [[Cymbeline]] — Act I, Scene 1 -> # [[Cymbeline|Cimbelino]] — Atto I, Scena 1
- Preserve ALL [[Target|display]] wikilinks EXACTLY — translate ONLY the display part after the pipe, never the target slug
- Keep <br> line breaks exactly where they are
- Use literary Italian suitable for a Shakespeare play
- Use guillemets « » for any quoted speech within dialogue
- Translate verse lines preserving their rhythmic quality where possible
- Output ONLY the translated markdown, with frontmatter tags preserved unchanged

The column headers MUST be: | Chi parla | Battuta |
The scene heading format MUST follow the Italian pattern shown above."""


def translate_scene(en_path, dry_run=False):
    """Translate one scene file. Returns True on success."""
    rel = os.path.relpath(en_path, PLAY_DIR)
    it_path = en_path[:-3] + ".it.md"

    with open(en_path, encoding="utf-8") as f:
        en_text = f.read()

    # Extract frontmatter and body
    parts = en_text.split("---\n", 2)
    if len(parts) < 3:
        print(f"  SKIP {rel}: no frontmatter")
        return False

    fm = parts[1]
    body = parts[2]

    prompt = f"Translate this scene to Italian:\n\n---\n{fm}---\n{body}"

    if dry_run:
        print(f"  DRY-RUN {rel}: {len(en_text)} chars EN")
        return True

    print(f"  Translating {rel} ({len(en_text)} chars)...")

    # Write prompt to temp file (stdin pipe has encoding issues on Windows)
    import tempfile
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", encoding="utf-8", delete=False)
    tmp.write(prompt)
    tmp.close()

    try:
        result = subprocess.run(
            ["python", os.path.expanduser("~/bin/ds.py"),
             "--system", SYSTEM_PROMPT,
             "--model", "deepseek-v4-flash",
             "--timeout", "300",
             "-"],
            stdin=open(tmp.name, "r", encoding="utf-8"),
            capture_output=True, text=True, encoding="utf-8", timeout=360,
            cwd=HERE,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        os.unlink(tmp.name)

        # ds.py prints answer to stdout, stats to stderr
        if result.returncode != 0:
            print(f"  ERROR {rel}: ds.py exit {result.returncode}")
            print(f"  stderr: {result.stderr[:500]}")
            return False

        it_text = result.stdout.strip()
        if not it_text or len(it_text) < 100:
            print(f"  ERROR {rel}: output too short ({len(it_text)} chars)")
            print(f"  stdout: {it_text[:200]}")
            return False

        # Write .it.md
        with open(it_path, "w", encoding="utf-8", newline="") as f:
            f.write(it_text)
        print(f"  OK {rel}: {len(en_text)} EN -> {len(it_text)} IT chars")
        return True

    except subprocess.TimeoutExpired:
        print(f"  TIMEOUT {rel}")
        return False
    except Exception as e:
        print(f"  EXCEPTION {rel}: {e}")
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--start", type=int, default=1, help="start from scene N (1-based order)")
    args = ap.parse_args()

    scenes = sorted(glob.glob(os.path.join(PLAY_DIR, "**", "Scene_*.md"), recursive=True))
    # exclude .it.md
    scenes = [s for s in scenes if not s.endswith(".it.md")]

    print(f"Found {len(scenes)} scenes in Cymbeline")
    ok, fail = 0, 0

    for i, en_path in enumerate(scenes, 1):
        if i < args.start:
            continue
        rel = os.path.relpath(en_path, PLAY_DIR)
        if translate_scene(en_path, args.dry_run):
            ok += 1
        else:
            fail += 1
        if not args.dry_run and i < len(scenes):
            time.sleep(1)  # rate-limit between calls

    print(f"\nDone: {ok} OK, {fail} failed, {len(scenes)} total")

    if fail == 0 and not args.dry_run:
        print("\nReady for: python shakespeare_assemble.py --author Shakespeare --play Cymbeline")
        print("Then: python emit_vault_units.py Shakespeare && SPA=1 node preprocess.mjs")


if __name__ == "__main__":
    main()
