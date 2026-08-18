# -*- coding: utf-8 -*-
"""Translate all missing IT atoms (Belloc, Conan Doyle, Wilde) via DeepSeek V4 Flash."""
import os, sys, json, re, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
VAULT = os.path.normpath(os.path.join(ROOT, "..", "VaultEnglish"))

DEEPSEEK_HOST = os.environ.get("DEEPSEEK_HOST", "https://api.deepseek.com")
DEEPSEEK_MODEL = "deepseek-v4-flash"
API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")

WIKILINK_RE = re.compile(r"\[\[([^\]|\n]+)(?:\|([^\]\n]*))?\]\]")

SYSTEM_PROMPT = """You are translating English literature (novels and plays) to literary Italian.
Rules:
- Preserve ALL [[Target|label]] wikilinks EXACTLY — translate ONLY the display label after the pipe, never the target slug
- If a wikilink has no pipe ([[Target]]), add an Italian label: [[Target|Italian label]]
- Keep ALL frontmatter (--- ... ---) completely unchanged
- Keep # headings but translate their text
- Preserve paragraph breaks and formatting
- For plays: translate character names to Italian where appropriate
- Use literary Italian suitable for late 19th/early 20th century prose
- Output ONLY the translated markdown, nothing else."""


def mask_wikilinks(text):
    mask_map = {}
    counter = [0]
    def replacer(m):
        target = m.group(1)
        label = m.group(2) if m.group(2) else target
        token = f"[[L{counter[0]:02d}|{label}]]"
        mask_map[token] = target
        counter[0] += 1
        return token
    return WIKILINK_RE.sub(replacer, text), mask_map


def unmask_wikilinks(text, mask_map):
    for token, target in mask_map.items():
        m = re.search(r"\[\[L\d{2}\|([^\]]*)\]\]", token)
        if m:
            text = text.replace(token, f"[[{target}|{m.group(1)}]]")
    return text


def translate(en_text, label=""):
    masked, mask_map = mask_wikilinks(en_text)
    body = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": masked},
        ],
        "temperature": 0.3,
        "max_tokens": 8192,
    }
    req = urllib.request.Request(
        f"{DEEPSEEK_HOST}/v1/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                result = json.loads(resp.read())
            it_text = result["choices"][0]["message"]["content"]
            return unmask_wikilinks(it_text, mask_map)
        except Exception as e:
            print(f"    Attempt {attempt+1}: {e}")
            time.sleep(5)
    raise RuntimeError("All attempts failed")


def find_missing():
    """Find all .md atoms without .it.md siblings in Belloc, Conan Doyle, Wilde."""
    missing = []
    for author in ["Belloc", "Conan_Doyle", "Wilde"]:
        author_dir = os.path.join(VAULT, "Authors", author)
        for sub in ["Atomized", "Plays", "Long"]:
            sub_dir = os.path.join(author_dir, sub)
            if not os.path.isdir(sub_dir):
                continue
            for work in sorted(os.listdir(sub_dir)):
                work_dir = os.path.join(sub_dir, work)
                if not os.path.isdir(work_dir):
                    continue
                for f in sorted(os.listdir(work_dir)):
                    if not f.endswith(".md") or f.endswith(".it.md"):
                        continue
                    en_path = os.path.join(work_dir, f)
                    it_path = en_path[:-3] + ".it.md"
                    if not os.path.exists(it_path):
                        rel = os.path.relpath(en_path, VAULT)
                        missing.append((author, rel, en_path, it_path))
    return missing


def main():
    if not API_KEY:
        print("Set DEEPSEEK_API_KEY"); sys.exit(1)

    missing = find_missing()
    print(f"Found {len(missing)} atoms without IT translation\n")

    for i, (author, rel, en_path, it_path) in enumerate(missing):
        label = f"[{i+1}/{len(missing)}] {author}/{os.path.basename(os.path.dirname(en_path))}/{os.path.basename(en_path)}"
        size = os.path.getsize(en_path)
        print(f"{label} ({size:,} bytes)...")

        with open(en_path, encoding="utf-8") as fh:
            en_text = fh.read()

        try:
            it_text = translate(en_text, label=rel)
            os.makedirs(os.path.dirname(it_path), exist_ok=True)
            with open(it_path, "w", encoding="utf-8") as fh:
                fh.write(it_text)
            print(f"  -> OK ({len(it_text):,} chars)")
        except Exception as e:
            print(f"  -> FAILED: {e}")

    print(f"\nDone! {len(missing)} atoms translated.")


if __name__ == "__main__":
    main()
