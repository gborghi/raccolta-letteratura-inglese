# -*- coding: utf-8 -*-
"""Translate all 14 untranslated Coleridge 'Self-Knowledge' cluster poems EN->IT via DeepSeek V4 Flash."""
import os, sys, json, re, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
VAULT = os.path.normpath(os.path.join(ROOT, "..", "VaultEnglish"))
CLUSTER_DIR = os.path.join(VAULT, "Authors", "Coleridge", "Atomized", "self-knowledge-immortality-self-reliance")

DEEPSEEK_HOST = os.environ.get("DEEPSEEK_HOST", "https://api.deepseek.com")
DEEPSEEK_MODEL = "deepseek-v4-pro"
API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")

WIKILINK_RE = re.compile(r"\[\[([^\]|\n]+)(?:\|([^\]\n]*))?\]\]")

SYSTEM_PROMPT = """You are translating Coleridge poems from English to literary Italian.
Rules:
- Preserve ALL [[Target|label]] wikilinks EXACTLY — translate ONLY the display label after the pipe, never the target
- If a wikilink has no pipe ([[Target]]), add an Italian label: [[Target|Italian label]]
- Keep frontmatter (--- ... ---) unchanged EXCEPT translate 'title:' field value
- Keep # headings, translate their text
- Translate the poem body preserving line breaks and poetic form
- Use literary Italian suitable for Romantic-era poetry
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
        "max_tokens": 4096,
    }
    req = urllib.request.Request(
        f"{DEEPSEEK_HOST}/v1/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read())
            it_text = result["choices"][0]["message"]["content"]
            return unmask_wikilinks(it_text, mask_map)
        except Exception as e:
            print(f"  Attempt {attempt+1} failed: {e}")
            time.sleep(5)
    raise RuntimeError("All attempts failed")


def main():
    if not API_KEY:
        print("Set DEEPSEEK_API_KEY"); sys.exit(1)

    # Find .md files WITHOUT .it.md siblings
    missing = []
    for f in sorted(os.listdir(CLUSTER_DIR)):
        if f.endswith(".it.md"):
            continue
        if not f.endswith(".md"):
            continue
        en_path = os.path.join(CLUSTER_DIR, f)
        it_path = en_path[:-3] + ".it.md"
        if not os.path.exists(it_path):
            missing.append((f, en_path, it_path))

    print(f"Found {len(missing)} untranslated poems in Self-Knowledge cluster\n")

    for i, (name, en_path, it_path) in enumerate(missing):
        print(f"[{i+1}/{len(missing)}] {name}...")
        with open(en_path, encoding="utf-8") as fh:
            en_text = fh.read()

        try:
            it_text = translate(en_text, label=name)
            with open(it_path, "w", encoding="utf-8") as fh:
                fh.write(it_text)
            print(f"  -> {len(it_text)} chars")
        except Exception as e:
            print(f"  FAILED: {e}")

    print(f"\nDone! Translated {len(missing)} poems.")


if __name__ == "__main__":
    main()
