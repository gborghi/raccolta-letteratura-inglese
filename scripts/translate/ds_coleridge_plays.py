# -*- coding: utf-8 -*-
"""Translate 6 untranslated Coleridge plays EN->IT via DeepSeek V4 Flash.

One-shot: reads each EN .md, sends to DeepSeek API, writes .it.md.
Preserves [[Target|label]] wikilinks, translates only display labels.
"""
import os, sys, json, re, time, urllib.request, hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
VAULT = os.path.normpath(os.path.join(ROOT, "..", "VaultEnglish"))
PLAY_DIR = os.path.join(VAULT, "Authors", "Coleridge", "Plays")

DEEPSEEK_HOST = os.environ.get("DEEPSEEK_HOST", "https://api.deepseek.com")
DEEPSEEK_MODEL = "deepseek-v4-flash"
API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")

WIKILINK_RE = re.compile(r"\[\[([^\]|\n]+)(?:\|([^\]\n]*))?\]\]")

SYSTEM_PROMPT = """You are translating Coleridge play introductions from English to literary Italian.
Rules:
- Preserve ALL [[Target|label]] wikilinks EXACTLY — translate ONLY the display label after the pipe, never the target
- If a wikilink has no pipe ([[Target]]), add an Italian label: [[Target|Italian label]]
- Keep frontmatter (--- ... ---) unchanged
- Keep # headings, translate their text
- Use literary Italian suitable for a Romantic-era play introduction
- Output ONLY the translated markdown, nothing else."""

UNTRANSLATED = [
    "Osorio/Osorio.md",
    "Piccolomini/Piccolomini.md",
    "Remorse/Remorse.md",
    "The_Death_of_Wallenstein/The_Death_of_Wallenstein.md",
    "The_Fall_of_Robespierre/The_Fall_of_Robespierre.md",
    "Zapolya_A_Christmas_Tale_in_Two_Parts/Zapolya_A_Christmas_Tale_in_Two_Parts.md",
]


def mask_wikilinks(text):
    """Replace [[target|label]] and [[target]] with masked tokens."""
    mask_map = {}
    counter = [0]

    def replacer(m):
        target = m.group(1)
        label = m.group(2) if m.group(2) else target
        token = f"[[L{counter[0]:02d}|{label}]]"
        mask_map[token] = target
        counter[0] += 1
        return token

    masked = WIKILINK_RE.sub(replacer, text)
    return masked, mask_map


def unmask_wikilinks(text, mask_map):
    """Restore masked tokens to proper [[target|label]] format."""
    for token, target in mask_map.items():
        escaped = re.escape(token)
        # Extract the (possibly translated) label
        m = re.search(r"\[\[L\d{2}\|([^\]]*)\]\]", token)
        if m:
            text = text.replace(token, f"[[{target}|{m.group(1)}]]")
    return text


def translate(en_text):
    """Send EN text to DeepSeek, get IT back."""
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
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read())
            it_text = result["choices"][0]["message"]["content"]
            it_text = unmask_wikilinks(it_text, mask_map)
            return it_text
        except Exception as e:
            print(f"  Attempt {attempt+1} failed: {e}")
            time.sleep(5)
    raise RuntimeError("All attempts failed")


def main():
    if not API_KEY:
        print("Set DEEPSEEK_API_KEY")
        sys.exit(1)

    for rel in UNTRANSLATED:
        en_path = os.path.join(PLAY_DIR, rel)
        it_path = en_path[:-3] + ".it.md"

        if os.path.exists(it_path):
            print(f"SKIP {rel} (already translated)")
            continue

        print(f"Translating {rel}...")
        with open(en_path, encoding="utf-8") as f:
            en_text = f.read()

        try:
            it_text = translate(en_text)
            with open(it_path, "w", encoding="utf-8") as f:
                f.write(it_text)
            print(f"  -> {os.path.basename(it_path)} ({len(it_text)} chars)")
        except Exception as e:
            print(f"  FAILED: {e}")
            continue

    print("\nDone!")


if __name__ == "__main__":
    main()
