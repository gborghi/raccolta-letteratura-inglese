# -*- coding: utf-8 -*-
"""Translate the content-filter-blocked Chesterton atoms EN->IT with Tower+ 72B (local).

Why this exists: ~100 Chesterton atoms carry period racial/ethnic language that made the
hosted block-level translator abort. Tower+ 72B runs locally in LM Studio with no output
filter, so it can render these faithfully. See SENSITIVE_TRANSLATION_REFERENCE.md.

Design (mirrors sbtrans/gkc_emit_vault so the emitter can consume the output):
- WHOLE BLOCK PER CALL. Each prose block is translated in ONE call so the model has the entire
  passage in view. Never sentence-wise: that wrecks the cohesion (pronouns, connectives,
  Chesterton's rhetorical build) that makes a literary translation worth doing.
- The emitter matches sha(EN prose block) -> IT block and SKIPS ANY PAGE whose block count
  differs, so we rejoin with the original separators and collapse any blank line the model
  emits. Block count matches by construction, never by luck.
- Non-prose blocks (blank runs, <nav>, bare roman numerals) pass through untouched --
  exactly what the emitter's prose_parts() skips.
- LINKS. Targets are masked to opaque [[Lnn|label]] codes first, because the translator renders
  a real target word into Italian ([[Song|song]] -> [[Canzone|canzone]]) and silently breaks the
  link. Codes survive; the true target is restored afterwards. Italian still restructures
  phrases, so a token can migrate or vanish -- those blocks are written anyway (structure is
  what gates publishing) and queued to data/gkc_tower_linkfix.jsonl for a repair pass over the
  Italian text. Repairing markup afterwards is cheap; re-translating blind is not.
- Content-addressed append-only cache: sha1(EN block) -> IT. Resumable and shared across
  atoms (Chesterton repeats blocks between part/chapter/whole variants).

Usage:
  python3 gkc_tower_sensitive.py            # translate all pending atoms in the TSV
  python3 gkc_tower_sensitive.py --limit 2  # smoke-test on the first 2 pending atoms
  python3 gkc_tower_sensitive.py --dry-run  # list what would be done, translate nothing
Requires: LM Studio server on :1234 with tower-plus-72b loaded (context 8192, parallel 1 --
          the stock 27904/parallel-4 config OOMs on a 64GB box and returns "Compute error").
"""
import os, re, sys, csv, json, time, hashlib, urllib.request, urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sbtrans import clean_body, split_blocks, has_prose

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
VAULT_ROOT = os.path.abspath(os.path.join(ROOT, "..", "VaultEnglish"))
TSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chesterton_sensitive_untranslated.tsv")
CACHE_PATH = os.path.join(ROOT, "data", "gkc_tower_cache.jsonl")
FIXUPS_PATH = os.path.join(ROOT, "data", "gkc_tower_linkfix.jsonl")

HOST = os.environ.get("LMSTUDIO_HOST", "http://localhost:1234")
MODEL = os.environ.get("TOWER_MODEL", "tower-plus-72b")

_BRIEF = """You are a literary translator rendering G.K. Chesterton (1900-1936) from English into Italian.

1. NEVER FABRICATE. Translate the given text and NOTHING else. Do not continue it, complete it, explain it, or add examples, context or commentary. Never write a sentence that is not in the source. Turning a title into a sentence, or a line into a paragraph, is a serious error - far worse than an awkward phrase.
2. MEANING FIRST, WITH MARGIN. Rendering the sense freely is not only allowed but wanted: do NOT translate word-for-word, and if a literal rendering would be obscure, rephrase so the meaning is unmistakable to an Italian reader. You MAY take more room than the English where Italian needs it: five words may become ten, ten lines may become thirteen (or eight). What you must NEVER do is approach TWICE the length of the source. Extra room is only ever for expressing the SAME meaning more clearly - never for adding meaning that is not there.
3. STYLE. Preserve Chesterton's voice - his paradox, irony, cadence and rhetorical shape. Keep the period register of the original; do not modernise, censor, soften, or add editorial notes or footnotes.
"""

_SHAPE = """SHAPE. Keep the leading '#' of a heading and any existing '>' marker, but never ADD markers of your own.
Use Italian quotation marks. Return exactly ONE paragraph with NO blank lines: never split or merge paragraphs.

Output ONLY the Italian translation. No preface, no commentary, no notes, no added text."""

# Two briefs: a block with no links must NOT be told about [[Lnn]] tokens, or the model invents
# them (a bare '# Chapter 5 (part 7)' heading came back sprouting L01..L05).
SYSTEM_LINKS = _BRIEF + """4. BRACKETED WORDS - CRITICAL. The text contains [[Lnn|word]] tokens, each holding TWO parts: an
   Lnn code (L01, L02, ...) and a word. TRANSLATE ONLY THE WORD - the part after the '|'. The Lnn
   code is an opaque identifier, NOT English: copy it EXACTLY, never translate it, never renumber it.
   Example: [[L42|song]] -> [[L42|canzone]].

   Every bracketed word must survive, translated, still inside its own brackets with its own code.
   Never drop one, never merge two into one.

   EMBED IT SEAMLESSLY, NEVER REPEAT IT. Write the sentence you would write anyway, in natural
   flowing Italian, and put the brackets around the word already standing in it. The brackets go
   around the word itself, wherever that word falls - they must never bend the sentence, and the
   word must never appear twice.
       WRONG: "la croce scarlatta [[L07|croce]]"   (says "croce" twice - the token was bolted on)
       RIGHT: "la [[L07|croce]] scarlatta"          (one word, brackets around it, sentence intact)
   The brackets follow the WORD, not the English position. Italian reorders - an English adjective
   comes before its noun, an Italian one after - so the brackets move with the noun:
       "the English [[L01|sword]]"   -> "la [[L01|spada]] inglese"    NOT "la spada inglese [[L01|spada]]"
       "religious [[L02|doubt]]"     -> "il [[L02|dubbio]] religioso" NOT "il dubbio religioso [[L02|dubbio]]"
       "Christmas [[L03|bells]]"     -> "le [[L03|campane]] di Natale" NOT "le campane di Natale [[L03|campane]]"
   Inflect the word as Italian grammar requires (gender, number, article); the brackets follow it.
   The reader must not be able to tell a token was ever there.
5. """ + _SHAPE

SYSTEM_PLAIN = _BRIEF + """4. Output plain prose. Do NOT add square brackets, links, or markup of any kind.
5. """ + _SHAPE

# A bare heading ("ENVOI", "AFRICA", "THE MEANING OF THE CRUSADE") reads to the model as a writing
# prompt, and it answers with an essay: ENVOI produced 14,136 chars. Naming the input as a TITLE and
# demanding one line stops it dead - all of ENVOI/AFRICA/CRUSADE/Isle-of-Wight then came back as
# correct one-line titles. Truncating instead would not work: the invention runs straight on from
# the real translation with no sentence break, so a cut leaves fabricated text glued to good text.
SYSTEM_TITLE = """You are translating EN->IT. The input is a TITLE or HEADING from a book of essays by G.K. Chesterton.

Translate ONLY the title itself, and STOP. Output exactly ONE short line.
Never write a sentence about the subject. Never continue, explain or illustrate the text. No commentary.
Render the sense idiomatically rather than word-for-word, but the output must stay a title of about the same length.
Keep a leading '#' if present. Output ONLY the Italian title."""


VERSE_RULE = """

THIS IS VERSE. The margin allowed for prose does NOT apply here: keep the line count and the line
length close to the original. A line of verse becomes a line of verse - never a sentence of
explanation. Preserve the line breaks exactly as they are."""


def is_heading(block):
    """Short, no sentence-ending punctuation -> a title/heading, not prose."""
    s = block.strip().lstrip("#").strip()
    return len(s) <= 90 and not re.search(r"[.!?][\"')\]]*$", s)


# Project Gutenberg's licence/footer survived atomisation into a few atoms (35 of the 287 blocks in
# Poems/part/part_08.md alone). It is not Chesterton, it must not be translated -- the PG licence is
# not ours to render into Italian -- and its hard-wrapped mid-sentence fragments ("...a refund from
# the person or") make the model COMPLETE them, which trips the fabrication guard and kills the
# whole atom. Pass these through verbatim: the block count stays intact and the licence stays in
# the language it was written in.
BOILERPLATE_RE = re.compile(
    r"project gutenberg|gutenberg\.org|gutenberg ebook|gutenberg-tm|www\.|https?://"
    r"|public domain print edition|archive foundation|copyright royalt|paying copyright"
    r"|electronic works?\b|redistribut|\brefund\b|\btrademark\b|terms of this agreement"
    r"|\beBook\b|donations",
    re.I)

# Keywords alone miss 18 of the 49 licence blocks ("Produced by Marc D'Hooghe", "will be renamed.",
# "*** START: FULL LICENSE ***") -- they are ordinary English and only boilerplate BY POSITION.
# The tail is structural: everything from the END marker onward is licence, so detect the region.
GUT_TAIL_RE = re.compile(r"\*\*\*\s*END OF (THIS|THE)\s+PROJECT GUTENBERG"
                         r"|End of (the )?Project Gutenberg"
                         r"|\*\*\*\s*START:\s*FULL LICENSE", re.I)


def is_boilerplate(block):
    return bool(BOILERPLATE_RE.search(block))


def boilerplate_mask(parts):
    """Which parts are Gutenberg boilerplate: the licence TAIL (positional) plus keyword hits."""
    tail = False
    mask = []
    for p in parts:
        if GUT_TAIL_RE.search(p):
            tail = True                          # everything from the END marker on is licence
        mask.append(tail or is_boilerplate(p))
    return mask

# \n excluded from both groups: see the note in dickens_tower.py -- an unclosed [[ in a
# truncated H1 otherwise swallows the next real link and fakes an "invented target" reject.
WIKILINK_RE = re.compile(r"\[\[([^\]|\n]+)(?:\|([^\]\n]*))?\]\]")
UNCLOSED_LINK_RE = re.compile(r"\[\[([^\]|\n]+)(?:\|[^\]\n]*)?$", re.M)  # see dickens_tower.py
CODE_RE = re.compile(r"\[\[(L\d{2,})\|([^\]]*)\]\]")


def mask_links(block):
    """[[Target|label]] -> [[Lnn|label]]; [[Word]] -> [[Lnn|Word]].

    Targets are concept-note ids like [[Song]] or [[Death]] -- real English words, which the
    translator 'helpfully' renders into Italian ([[Song|song]] -> [[Canzone|canzone]]), silently
    breaking the link. Opaque Lnn codes have nothing to translate, so they survive verbatim and we
    restore the true target afterwards.
    """
    targets = []

    def sub(m):
        target, label = m.group(1), m.group(2)
        targets.append(target)
        code = "L%02d" % len(targets)
        return "[[%s|%s]]" % (code, label if label is not None else target)

    return WIKILINK_RE.sub(sub, block), targets


def unmask_links(it_block, targets):
    """[[Lnn|label]] -> [[Target|label]] (or bare [[Target]] when the label is unchanged)."""
    def sub(m):
        idx = int(m.group(1)[1:]) - 1
        label = m.group(2).strip()
        if idx < 0 or idx >= len(targets):
            return m.group(0)                     # unknown code: leave, validation will catch it
        target = targets[idx]
        if label == target:
            return "[[%s]]" % target              # matches existing style, e.g. [[Milton]]
        return "[[%s|%s]]" % (target, label)

    return CODE_RE.sub(sub, it_block)


def sha(s):
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


class Cache:
    """Append-only sha1(EN block) -> IT block. Makes the 13h run resumable."""

    def __init__(self, path):
        self.path = path
        self.d = {}
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if os.path.exists(path):
            for ln in open(path, encoding="utf-8"):
                ln = ln.strip()
                if ln:
                    r = json.loads(ln)
                    self.d[r["h"]] = r["it"]
        self._fh = open(path, "a", encoding="utf-8")

    def get(self, s):
        return self.d.get(sha(s))

    def put(self, s, it):
        h = sha(s)
        if h in self.d:
            return
        self.d[h] = it
        self._fh.write(json.dumps({"h": h, "en": s, "it": it}, ensure_ascii=False) + "\n")
        self._fh.flush()


def call_tower(user_msg, system, max_tokens=4096, retries=3):
    body = json.dumps({
        "model": MODEL, "temperature": 0, "max_tokens": max_tokens,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user_msg}],
    }).encode()
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(HOST + "/v1/chat/completions", data=body,
                                         headers={"Content-Type": "application/json"})
            r = json.loads(urllib.request.urlopen(req, timeout=900).read())
            out = r["choices"][0]["message"]["content"].strip()
            if out:
                return out
            last = "empty completion"
        except Exception as e:  # transient engine/compute hiccups
            last = repr(e)
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"tower failed after {retries} tries: {last}")


def prose_blocks(body):
    """Ordered prose blocks, exactly as gkc_emit_vault.prose_parts() sees them."""
    out = []
    for part in split_blocks(clean_body(body)):
        s = part.strip()
        if not s or s.startswith("<nav") or not has_prose(s):
            continue
        out.append(s)
    return out


def targets(text):
    """Multiset of wikilink targets, to prove none were dropped or renamed."""
    return sorted([m.group(1) for m in WIKILINK_RE.finditer(text)] +
                  [m.group(1) for m in UNCLOSED_LINK_RE.finditer(text)])


def _codes_of(text):
    return [g[0] for g in CODE_RE.findall(text)]


STRAY_CODE_RE = re.compile(r"\[\[L\d{2,}\|([^\]]*)\]\]")


def is_fabricated(en_block, it_block, verse=False):
    """True if the IT block is too long to be a translation of the EN block.

    THE failure mode of this pipeline. Given a short input the model stops translating and starts
    writing: the limerick line "An author in the Isle of Wight" (30 chars) produced 13,759 chars of
    invented Chesterton pastiche, and "AFRICA" produced an essay on the continent. Structure and
    link checks CANNOT see this -- block counts and targets were both perfect -- so the fabrication
    sailed through validation and would have been published as Chesterton's own words.

    Prose gets margin on purpose: Italian needs room, and a cramped translation is its own kind of
    failure. Five words may become ten. The line is TWICE the source -- past that it is not room for
    the same meaning, it is new meaning. Verse gets no such margin: a poem's line must stay a line.
    """
    if verse:
        return len(it_block) > 1.5 * len(en_block) + 24
    return len(it_block) > 2 * len(en_block) + 80


def _ask(masked_text, want, verse=False):
    """One whole-block translation call over already-masked text. Returns raw IT text."""
    if not want and is_heading(masked_text):
        # Titles get their own brief and a tight budget: this is where fabrication came from.
        out = call_tower("Title:\n" + masked_text, SYSTEM_TITLE, max_tokens=48)
        return re.sub(r"\s*\n[ \t]*\n+\s*", " ", out).strip()
    system = (SYSTEM_LINKS if want else SYSTEM_PLAIN) + (VERSE_RULE if verse else "")
    # No token inventory here on purpose. Demanding "your translation MUST contain all N tokens,
    # each exactly once" made the model satisfy the count by TACKING a token onto a phrase it had
    # already translated -- "la croce scarlatta [[Cross|croce]]" reads "la croce scarlatta croce".
    # Placement is what matters, not a quota; a token that has no home is a repair-pass job.
    user = "Translate this passage to Italian:\n\n" + masked_text
    # Hard ceiling proportional to the source. Given a short line the model stops translating and
    # starts WRITING: the limerick line "An author in the Isle of Wight" (30 chars) came back as
    # 13,759 chars of invented Chesterton pastiche. Italian runs ~1.1-1.3x English, so len/1.5
    # tokens leaves generous headroom while making that fabrication physically impossible.
    budget = min(4096, max(64, int(len(masked_text) / 1.5)))
    out = call_tower(user, system, max_tokens=budget)
    # A block must never contain a blank line, or it would split in two and the emitter would skip
    # the whole page. Collapse defensively rather than trusting the model.
    return re.sub(r"\s*\n[ \t]*\n+\s*", " ", out).strip()


def translate_block(en_block, verse=False, tries=3):
    """Translate a whole prose block in ONE call, so the model always has the full context.

    Returns (it_block, missing_targets). The block is NEVER chopped up: sentence-wise translation
    destroys the cohesion (pronouns, connectives, Chesterton's rhetorical build) that makes this
    worth doing. Links are a separate concern: Italian restructures phrases, so a token can migrate
    or vanish (a 12-link block put [[Wind]] on "nord" and dropped [[Death]]). We keep the best
    attempt and report the casualties for a follow-up repair pass over the Italian text -- fixing
    markup afterwards is cheap; re-translating blind is not.
    """
    masked, targets = mask_links(en_block)
    want = ["L%02d" % (i + 1) for i in range(len(targets))]

    if not want:
        for _ in range(tries):
            out = _ask(masked, want, verse)
            out = WIKILINK_RE.sub(lambda m: m.group(2) or m.group(1), out)    # strip invented markup
            if not is_fabricated(en_block, out, verse):
                return out, []
        raise RuntimeError(f"fabricated output: {len(en_block)} chars EN -> {len(out)} chars IT")

    best, best_got = None, []
    for attempt in range(tries):
        out = _ask(masked, want, verse)
        if is_fabricated(en_block, out, verse):
            continue                              # invented text: never keep it, even as `best`
        got = _codes_of(out)
        if got == want:
            return unmask_links(out, targets), []                             # clean hit
        # `best is None` seeds the first candidate: a block where the model strips EVERY token
        # scores 0, and `0 > 0` would leave best unset -> unmask_links(None) TypeError. Verse does
        # exactly this (it drops the markup wholesale), so this path is real, not theoretical.
        if best is None or len(set(got) & set(want)) > len(set(best_got) & set(want)):
            best, best_got = out, got
        # Retries pay off only when the model ALMOST got it (a token or two drifted) -- then another
        # sample often lands it. When it returns zero codes it has decided this text takes no markup
        # (verse does this every time), and re-sampling at temperature 0 just burns ~6s/call to get
        # the same answer. Bail: the links go to the repair pass anyway.
        if not got:
            break
    if best is None:                              # every attempt fabricated
        raise RuntimeError(f"fabricated output on all {tries} tries ({len(en_block)} chars EN)")
    it = unmask_links(best, targets)
    it = STRAY_CODE_RE.sub(lambda m: m.group(1), it)      # drop codes we couldn't map back
    missing = [targets[int(c[1:]) - 1] for c in want if c not in best_got]
    return it, missing


def translate_atom(en_path, cache, fixups):
    # Verse lives under Poems/ and in the Long/ tree; it gets no expansion margin.
    verse = "/Poems/" in en_path.replace(os.sep, "/") or "/Long/" in en_path.replace(os.sep, "/")
    body = open(en_path, encoding="utf-8").read()
    parts = split_blocks(clean_body(body))
    bp = boilerplate_mask(parts)
    out = []
    for k, part in enumerate(parts):
        s = part.strip()
        if not s or s.startswith("<nav") or not has_prose(s):
            out.append(part)                      # separator / nav / non-prose: verbatim
            continue
        if bp[k]:
            out.append(part)                      # Gutenberg licence/footer: verbatim, never translated
            continue
        it = cache.get(s)
        if it is None:
            it, missing = translate_block(s, verse)
            cache.put(s, it)
            if missing:
                # Structure is fine (block count preserved) so the page still publishes; these
                # links just need re-attaching to the right Italian word in a repair pass.
                fixups.append({"atom": os.path.relpath(en_path, VAULT_ROOT),
                               "missing": missing, "en": s, "it": it})
        # keep the block's surrounding whitespace so the rejoin is byte-faithful, and carry over a
        # leading blockquote marker ('> ') which the sentence units don't see
        lead = part[:len(part) - len(part.lstrip())]
        trail = part[len(part.rstrip()):]
        qm = re.match(r"(>+\s*)", s)
        if qm and not it.startswith(">"):
            it = qm.group(1) + it
        out.append(lead + it.strip() + trail)
    return "".join(out)


def validate(en_body, it_body, verse=False):
    """Hard errors only -- things that make the atom unpublishable. Returns list of problems.

    Block count is fatal: gkc_emit_vault skips any page whose EN/IT prose-block counts differ, so a
    mismatch means the work silently never goes bilingual. Missing links are NOT fatal (the page
    publishes fine, just with fewer concept links) -- they go to the fixups report instead.
    Invented/renamed targets ARE fatal: they would link to concept notes that don't exist.
    """
    problems = []
    ep, ip = prose_blocks(en_body), prose_blocks(it_body)
    if len(ep) != len(ip):
        problems.append(f"block count {len(ep)} EN vs {len(ip)} IT (emitter would skip page)")
    else:
        # Second line of defence against invented text. The block-level guard should have caught it,
        # but a fabrication written to disk is the worst outcome this pipeline has -- it publishes
        # words Chesterton never wrote under his name. Structure/link checks are blind to it.
        bp = boilerplate_mask(ep)                 # licence tail is passed through, never "fabricated"
        fab = [(len(e), len(i)) for k, (e, i) in enumerate(zip(ep, ip))
               if not bp[k] and is_fabricated(e, i, verse)]
        if fab:
            problems.append(f"FABRICATED content in {len(fab)} block(s), e.g. {fab[0][0]} chars EN "
                            f"-> {fab[0][1]} chars IT")
    et, itt = set(targets(en_body)), set(targets(it_body))
    invented = sorted(itt - et)
    if invented:
        problems.append(f"invented wikilink targets: {invented[:6]}")
    return problems


def main():
    args = sys.argv[1:]
    dry = "--dry-run" in args
    limit = None
    if "--limit" in args:
        limit = int(args[args.index("--limit") + 1])

    rows = list(csv.DictReader(open(TSV, encoding="utf-8"), delimiter="\t"))
    pending = []
    for r in rows:
        en = os.path.join(VAULT_ROOT, r["vault_en_path"])
        if not os.path.exists(en):
            print(f"!! missing EN file: {r['vault_en_path']}")
            continue
        if os.path.exists(en[:-3] + ".it.md"):
            continue                              # already done -> resumable
        pending.append(en)
    if limit:
        pending = pending[:limit]

    print(f"pending atoms: {len(pending)} / {len(rows)} in TSV")
    if dry:
        for p in pending:
            print("  would translate:", os.path.relpath(p, VAULT_ROOT))
        return

    cache = Cache(CACHE_PATH)
    print(f"cache warm with {len(cache.d)} blocks", flush=True)
    # Progress must be measured in BLOCKS, not atoms: a block is one model call, and atoms vary
    # wildly (a verse atom is 307 one-line blocks; a prose atom is ~4). Extrapolating from atoms
    # projected 75h off a single poem.
    total_blocks = sum(len(prose_blocks(open(p, encoding="utf-8").read())) for p in pending)
    print(f"work: {total_blocks} prose blocks across {len(pending)} atoms", flush=True)
    ok = failed = done_blocks = 0
    t0 = time.time()
    for i, en_path in enumerate(pending, 1):
        rel = os.path.relpath(en_path, VAULT_ROOT)
        fixups = []
        try:
            it_body = translate_atom(en_path, cache, fixups)
        except Exception as e:
            print(f"[{i}/{len(pending)}] FAIL {rel}: {e}", flush=True)
            failed += 1
            continue
        en_body = open(en_path, encoding="utf-8").read()
        problems = validate(en_body, it_body, "/Poems/" in en_path.replace(os.sep, "/") or "/Long/" in en_path.replace(os.sep, "/"))
        if problems:
            print(f"[{i}/{len(pending)}] REJECT {rel}: {'; '.join(problems)}", flush=True)
            failed += 1
            continue
        with open(en_path[:-3] + ".it.md", "w", encoding="utf-8") as fh:
            fh.write(it_body)
        if fixups:
            with open(FIXUPS_PATH, "a", encoding="utf-8") as fh:
                for f in fixups:
                    fh.write(json.dumps(f, ensure_ascii=False) + "\n")
        ok += 1
        done_blocks += len(prose_blocks(en_body))
        el = time.time() - t0
        nmiss = sum(len(f["missing"]) for f in fixups)
        tag = f" | {nmiss} links need repair" if nmiss else ""
        left = (el / done_blocks) * (total_blocks - done_blocks) / 3600 if done_blocks else 0
        print(f"[{i}/{len(pending)}] ok {rel} | blocks {done_blocks}/{total_blocks} | "
              f"{el/60:.0f}m elapsed, ~{left:.1f}h left{tag}", flush=True)
    print(f"\ndone: {ok} written, {failed} failed/rejected, cache {len(cache.d)} blocks")
    if os.path.exists(FIXUPS_PATH):
        n = sum(1 for _ in open(FIXUPS_PATH, encoding="utf-8"))
        print(f"link-repair queue: {n} blocks -> {os.path.relpath(FIXUPS_PATH, ROOT)}")


if __name__ == "__main__":
    main()
