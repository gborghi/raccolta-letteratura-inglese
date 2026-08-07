# -*- coding: utf-8 -*-
"""Translate Dickens atoms EN->IT with Tower+ 72B (local). Adapted from gkc_tower_sensitive.py.

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
from sbtrans import clean_body, split_blocks, has_prose, split_sentences
import dickens_headings as dh

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
VAULT_ROOT = os.path.abspath(os.path.join(ROOT, "..", "VaultEnglish"))
TSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "oliver_twist_atoms.tsv")
CACHE_PATH = os.path.join(ROOT, "data", "dickens_tower_cache.jsonl")
FIXUPS_PATH = os.path.join(ROOT, "data", "dickens_tower_linkfix.jsonl")

HOST = os.environ.get("LMSTUDIO_HOST", "http://localhost:1234")
MODEL = os.environ.get("TOWER_MODEL", "tower-plus-72b")

def _read_vault(path, retries=8, delay=2.0):
    """Read a vault file, retrying transient Dropbox locks. The whole tree lives in
    CloudStorage; the macOS File Provider intermittently evicts/relocks a file mid-run,
    surfacing as OSError/PermissionError (EPERM). A single lock must not abort the atom
    or the whole catalogue sweep (it did on 2026-07-24, Old Curiosity Ch.06)."""
    for attempt in range(retries):
        try:
            with open(path, encoding="utf-8") as fh:
                return fh.read()
        except OSError:
            if attempt == retries - 1:
                raise
            time.sleep(delay)

def _write_vault(path, text, retries=8, delay=2.0):
    """Write a vault file, retrying transient Dropbox locks (see _read_vault)."""
    for attempt in range(retries):
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
            return
        except OSError:
            if attempt == retries - 1:
                raise
            time.sleep(delay)

_BRIEF = """You are a literary translator rendering Charles Dickens (1812-1870) from English into Italian.

1. NEVER FABRICATE. Translate the given text and NOTHING else. Do not continue it, complete it, explain it, or add examples, context or commentary. Never write a sentence that is not in the source. Turning a title into a sentence, or a line into a paragraph, is a serious error - far worse than an awkward phrase.
2. MEANING FIRST, WITH MARGIN. Rendering the sense freely is not only allowed but wanted: do NOT translate word-for-word, and if a literal rendering would be obscure, rephrase so the meaning is unmistakable to an Italian reader. You MAY take more room than the English where Italian needs it: five words may become ten, ten lines may become thirteen (or eight). What you must NEVER do is approach TWICE the length of the source. Extra room is only ever for expressing the SAME meaning more clearly - never for adding meaning that is not there.
3. STYLE. Preserve Dickens's voice - his narrative warmth, irony, sentiment, comic characterisation and rhetorical cadence. Keep the period register of the original; do not modernise, censor, soften, or add editorial notes or footnotes.
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
SYSTEM_TITLE = """You are translating EN->IT. The input is a TITLE or HEADING from a novel by Charles Dickens.

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

# A wikilink never spans a line, so \n is excluded from both groups. Without that,
# an unclosed [[ swallows forward to the NEXT ]] and eats the real link inside it:
# 91 atoms carry a truncated H1 ("MARLEY'S [[Ghost|GHOST (part 3)"), and in 38 of them
# the greedy alias hid a genuine target from targets(), so a faithful translation was
# rejected as "invented" -- permanently, since temperature 0 regenerates the same output.
WIKILINK_RE = re.compile(r"\[\[([^\]|\n]+)(?:\|([^\]\n]*))?\]\]")
# A [[ that runs to end of line without closing. The source still DECLARES that target,
# and the model often closes the bracket when translating the title, so targets() must
# count it -- otherwise the repaired Italian looks like it invented the link. Well-formed
# links never match: their `]` is excluded from the classes, so `$` cannot be reached.
UNCLOSED_LINK_RE = re.compile(r"\[\[([^\]|\n]+)(?:\|[^\]\n]*)?$", re.M)
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


# A finished IT block must never contain a mask code: unmask_links() replaces every one of
# them. A survivor means the code was mangled beyond what repair_mask_codes() could normalise,
# and validate() will reject the atom -- so it must not be cached, nor served from cache.
POISONED_RE = re.compile(r"\[\[L\d{1,3}\b")

# The model occasionally leaks CJK into an Italian block, and it lands *inside* a wikilink label:
#     [[cheese]]  ->  [[cheese|形式]]formaggio]]
# That slips past every existing check -- the target is real (not invented), there is no mask code
# left, and the block count is unchanged -- yet it writes broken markup and drops the neighbouring
# links. Han/Kana/Hangul never legitimately appear in an Italian rendering of an English text, so
# their presence in the output but NOT in the source is proof of corruption.
# Scritto con gli escape, non con i caratteri veri: cosi' il file resta greppabile e diff-abile
# comunque sia configurato il terminale (stessa ragione per cui il separatore NUL si scrive come escape).
CJK_RE = re.compile("[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uac00-\ud7af\uff01-\uff60]")


def cjk_leak(en, it):
    """Characters from a CJK script present in the translation and absent from its source."""
    return sorted(set(CJK_RE.findall(it)) - set(CJK_RE.findall(en)))


# HY has ONE systematic CJK leak: it renders the English "half-" of a compound as the bare Han
# character U+534A, leaving the rest of the phrase in Italian -- "gli occhi<U+534A>chiusi",
# "il bicchiere<U+534A> vuoto", "una pietra<U+534A>nascosta", "rimanere<U+534A> sdraiato".
# 23 of the 47 poisoned cache blocks are this one substitution, and it is the ONLY reason the
# Conan_Doyle atoms were rejecting after the bracket rule landed.
#
# It has to be repaired, not merely rejected: at temperature 0 the retry regenerates the very same
# character, so the atom rejects forever and never gets an .it.md -- the same permanent block the
# nested-wikilink atoms had (see bracket_defect). Prefixing "semi-" is safe because the character
# always sits in front of an ALREADY INFLECTED adjective or participle, so agreement is whatever
# the model already produced: "semi-chiusi", "semi-nascosta", "semi-vuoto".
#
# Only an ISOLATED U+534A is repaired. Where it sits inside a longer Han run the model dropped a
# whole Chinese phrase rather than a prefix (U+534A U+6B7B U+4E0D U+6D3B for "half dead",
# U+534A U+900F U+660E for "translucent"): that is a real mistranslation, and it must keep failing
# cjk_leak() so a human or Opus deals with it.
# Come CJK_RE, scritto con gli escape e non con i caratteri veri, cosi' il file resta greppabile.
HAN_RANGES = "\u3400-\u4dbf\u4e00-\u9fff"
HALF_LEAK_RE = re.compile("[ \\t]*(?<![" + HAN_RANGES + "])\u534a"
                          "(?![" + HAN_RANGES + "])[ \\t]*")


def repair_half_leak(s):
    s = HALF_LEAK_RE.sub(" semi-", s)
    # the substitution always prepends a space; drop it again where it landed at a line start,
    # so the repair can never move text onto the previous line or indent it.
    return re.sub(r"(?m)^ semi-", "semi-", s)


# Where the leak is NOT the half- prefix, HY dropped a whole Chinese word into otherwise fine
# Italian: "un<粗鲁>o giubbotto", "dei<犹太人> stessi", "pane e<奶酪>". No regex can undo that -- the
# Italian word is simply absent -- and temperature does not help: measured on the pea-jacket
# sentence, T=0 leaked 2/2, T=0.3 leaked 2/2, T=0.6 leaked 1/2 and the one clean output invented a
# word ("vecchio") that is not in the English. So a retry loop trades a permanent reject for a
# quiet mistranslation, which is worse.
#
# What does work is asking the model to translate the leaked span IN ITS ITALIAN CONTEXT: 6/6 clean
# on the real cases, with correct agreement ("degli stessi ebrei", "ruvido giubbotto", "mezzo
# vuoto"). This is a LAST RESORT and nothing else: it only runs on a block that cjk_leak() would
# otherwise throw away for good, so its worst case (a slightly loose sentence -- it rendered the
# "rude" of "a rude couch" as "semplice") is still strictly better than an atom that never gets an
# .it.md at all. Everything it cannot verify it leaves alone, so the guard still rejects.
_SENT_SPLIT_RE = re.compile(r"(?<=[.!?;:])\s+|\n")
_MARKER_RE = re.compile(r"\[\[[^\[\]]*\]\]|\[\[L\d{1,3}\b")
SYSTEM_CJK_SPAN = (
    "Sei un traduttore letterario. Ti do una frase italiana in cui una o piu' parole sono rimaste "
    "in cinese. Riscrivi la frase INTERA in italiano corretto, traducendo le parole cinesi e "
    "rispettando l'accordo di genere e numero. Non aggiungere e non togliere nulla, e lascia "
    "invariato ogni marcatore fra doppie quadre. Rispondi solo con la frase."
)


def repair_cjk_span(s, ask=None):
    """Retranslate only the sentences where a Han run survived repair_half_leak()."""
    if not CJK_RE.search(s):
        return s
    ask = ask or (lambda t: call_tower(t, SYSTEM_CJK_SPAN, max_tokens=400))
    out = []
    for piece in re.split(r"(\n)", s):
        if piece == "\n" or not CJK_RE.search(piece):
            out.append(piece)
            continue
        parts = _SENT_SPLIT_RE.split(piece)
        rebuilt, cursor = [], 0
        for sent in parts:
            start = piece.find(sent, cursor)
            gap = piece[cursor:start] if start >= 0 else ""
            cursor = (start + len(sent)) if start >= 0 else cursor
            rebuilt.append(gap)
            rebuilt.append(_repair_one_sentence(sent, ask))
        rebuilt.append(piece[cursor:])
        out.append("".join(rebuilt))
    return "".join(out)


def _repair_one_sentence(sent, ask):
    if not CJK_RE.search(sent) or not sent.strip():
        return sent
    try:
        fixed = ask(sent).strip()
    except Exception:
        return sent
    # every guard below is a reason to KEEP the broken sentence: a repair we cannot verify must
    # leave cjk_leak() free to reject, never smuggle an unchecked rewrite into the cache.
    if not fixed or CJK_RE.search(fixed):
        return sent
    if sorted(_MARKER_RE.findall(fixed)) != sorted(_MARKER_RE.findall(sent)):
        return sent
    if not 0.4 <= len(fixed) / max(1, len(sent)) <= 2.5:
        return sent
    # the model answers as if the fragment were a standalone sentence and capitalises it; mid-
    # sentence that would be a new error, so restore whatever case the original actually had.
    if sent[:1].islower() and fixed[:1].isupper():
        fixed = fixed[:1].lower() + fixed[1:]
    return fixed


# Some EN sources in the vault carry a NESTED wikilink -- graphify's linker wrapped a concept
# inside an already-linked phrase:  [[South [[Africa]]]] , [[The [[Bells]] , [[[[River]] .
# 124 occurrences over 117 atoms (Dickens 87, Conan_Doyle 26). That is malformed markup in the
# SOURCE; the model cannot mirror it faithfully, so the IT brackets come out uneven through no
# fault of the translation. Counting alone does not spot it -- [[South [[Africa]]]] is *numerically*
# balanced -- so the exemption has to look at the structure. Without this, such atoms reject
# forever: at temperature 0 the retry reproduces the same output, so it is a permanent block,
# not a flake, and no .it.md is ever written for them.
NESTED_OPEN_RE = re.compile(r"\[\[[^\[\]]*\[\[")


def bracket_defect(en, it):
    """IT wikilink brackets don't balance by more than the EN source can account for.

    A nested source link buys exactly ONE missing bracket, not a free pass for the atom:
    `[[South [[Africa]]]]` comes back as `[[South [[Africa|Sudafrica]]`, one `]]` short, every
    time. Measured over the nine Conan_Doyle atoms that hit this, the IT imbalance equalled the
    nesting count exactly (2/2, 1/1, 3/3) -- so allowing N of them is faithful, while exempting
    the whole atom on the strength of one would also wave through brackets lost elsewhere."""
    if en.count("[[") != en.count("]]"):
        return False
    allowed = len(NESTED_OPEN_RE.findall(en))
    return abs(it.count("[[") - it.count("]]")) > allowed


def _corrupt_block(en, it):
    """Is this IT block unusable? Used both to reject and to refuse to cache/serve it.

    Kept deliberately narrow: only defects that make the markup broken or the text non-Italian,
    never matters of taste. A block the model merely translated badly is not this function's
    business -- it must stay cacheable, or every run would redo the whole catalogue."""
    if POISONED_RE.search(it):
        return True
    if cjk_leak(en, it):
        return True
    # Unbalanced wikilink brackets, but only when the SOURCE was sound: several EN atoms carry a
    # genuine "[[[" typo or a nested link, and mirroring the source's own defect is correct.
    if bracket_defect(en, it):
        return True
    return False


class Cache:
    """Append-only sha1(EN block) -> IT block. Makes the 13h run resumable.

    Poison-aware: entries carrying a leftover [[Lnn mask code, leaked CJK or unbalanced wikilink
    brackets are treated as misses on read and overwritten on write, so one bad generation can't
    be replayed forever. This matters more than it looks: a cache sitting in front of a repair
    silently disables that repair, which is exactly how the mask-token epidemic survived three
    successive fixes."""

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
        it = self.d.get(sha(s))
        # A cache HIT bypasses _ask() entirely, so repair_mask_codes() never runs on it.
        # That is why fixing the repair regex kept "not working": the malformed [[Lnn]label]
        # bodies were being replayed from cache, not re-generated. Anything corrupt is reported
        # as a MISS so the block is retranslated instead of being replayed forever.
        if it is not None and _corrupt_block(s, it):
            return None
        return it

    def put(self, s, it):
        h = sha(s)
        if h in self.d and not _corrupt_block(s, self.d[h]):
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

# Tower sometimes drops the '|' of a masked code and glues the code to the translated word:
# [[L04|estate]] -> [[L04estate]]. unmask_links (which needs the '|') then can't map it, so the
# bogus target 'L04estate' survives -> invented-target REJECT. Re-insert the '|' before unmasking so
# the code maps back to its real target and the link is preserved. Leaves well-formed [[L04|x]]
# untouched (the char after the code is '|', excluded by the label class).
GLUED_CODE_RE = re.compile(r"\[\[(L\d{2,})([^\]|][^\]|]*)\]\]")
# Same failure, much wider: the model mangles the SEPARATOR ([[L04>estate]], [[L04:estate]],
# [[L04]estate]) and the CLOSER ([[L04|estate] with one bracket) -- and, being a Chinese-trained MT,
# it also reaches for CJK/full-width punctuation: the real reject that exposed this was
# "[[L01>sogno】" with a RIGHT BLACK LENTICULAR BRACKET U+3011 for the ']]'. Every repair above
# needs a well-formed ASCII ']]', so none of those was ever normalised: unmask couldn't map them,
# the Lnn code survived into the body and validate()'s stray-code check rejected the atom. That is
# the whole 'leftover mask token(s)' reject class, and it hits link-dense authors hardest
# (Chesterton: ~70% of atoms, single atoms logging "26 links to repair").
#
# Accepts a wrong/missing separator, a single closing bracket, and full-width 【】［］｜＞： in place
# of their ASCII forms. Requires a NON-EMPTY label, so a bare [[L04]] is left alone rather than
# turned into an empty-labelled link; the label class excludes brackets of both widths, so a stray
# 【...】 carrying no Lnn code is never touched. Subsumes GLUED_CODE_RE and is idempotent.
MALFORMED_CODE_RE = re.compile(
    r"(?:\[\[|【)(L\d{2,})\s*[|>:｜＞：\]］】]?\s*([^\[\]|｜【】［］]+?)\s*[\]］】]{1,2}")
# MALFORMED_CODE_RE still needs SOME closing bracket. When the masked link ends a quoted title the
# model sometimes closes it with the QUOTE instead, emitting no bracket at all:
#     EN “Light and Shadow of [[Spiritualism]]”   ->   IT “Luci e ombre dello [[L02]spiritualismo”»
#     EN “The Song of the Strange [[Ascetic]]”    ->   IT “La canzone dello strano [[L02]asceta””
# Nothing above matches, so the Lnn code reaches validate() and the atom rejects for good.
#
# The quote is the only trustworthy boundary here, and it is CONTENT: it belongs to the sentence, not
# to the link. So this inserts the missing ']]' in front of it and leaves it in place -- consuming it
# would silently delete a closing quotation mark from the text.
#
# Deliberately limited to the quote-closed case. The other bracket-less shape ('[[L01]periodo di
# tempo.' -- nothing but prose after the code) is left to reject: there is no delimiter, so the label
# boundary can only be guessed, and a wrong guess swallows a clause into a link label and publishes
# it as the author's own words. A reject is recoverable; that is not.
#
# Two traps, both found by replaying this over the 188k cached blocks before shipping it:
#   * The closer must be a DOUBLE quote. U+2019 is the ordinary Italian apostrophe -- accepting it
#     would cut `[[L02|notte d'inverno]]` into `[[L02|notte d]]'inverno]]`, breaking sound links by
#     the hundred. So the apostrophe is allowed INSIDE the label and never ends it.
#   * A code already carrying its ']]' after the quote (`[[L01|offensivo"]]`) is ugly but valid, and
#     validate() lets it through. Inserting another ']]' would leave two closers for one opener and
#     turn a passing atom into a bracket-count reject, so _unclosed_code() checks the tail first.
UNCLOSED_CODE_RE = re.compile(
    r"(?:\[\[|【)(L\d{2,})\s*[|>:｜＞：\]］】]?\s*([^\[\]|｜【】［］“”«»\n]{1,60}?)\s*(?=[”»])")


def _unclosed_code(m):
    tail = m.string[m.end():m.end() + 8]
    if "]" in tail or "］" in tail or "】" in tail:
        return m.group(0)                         # already closed, just past the quote: leave alone
    # Punctuation between the label and the quote belongs to the sentence. Push it back OUT of the
    # link rather than dropping it: rstrip alone would delete characters the regex has consumed.
    label = m.group(2)
    trimmed = label.rstrip(" ,;:!?.’‘")
    if not trimmed:
        return m.group(0)
    return "[[%s|%s]]%s" % (m.group(1), trimmed, label[len(trimmed):])

# Use-time safety net: strip ANY residual mask code (glued or piped) to its visible word, so a leak
# that slipped through can never publish a bogus 'Lnn...' wikilink target.
ANY_CODE_RE = re.compile(r"\[\[L\d{2,}\|?([^\]|]*)\]\]")


def drop_stray_close(text):
    """Delete a ']]' that has no '[[' open on its line: the model dropped the mask head and
    kept the tail ("un'espressione di  dolore]]"). That link is already logged as missing, so
    removing the orphan loses no word -- while leaving it in place fails bracket_defect and
    rejects the whole atom, permanently at temperature 0. Measured: 31 orphans in 27 accepted
    .it.md, so it is a small recurring family, not a one-off.

    Depth-counted rather than a regex, so the two look-alike shapes are left alone: a nested
    source link ([[South [[Africa]]]] is balanced) and a truncated H1 ([[Ghost|GHOST, which
    has no close at all -- only EXCESS closes are dropped, never an open).

    The depth is counted over the WHOLE text, never per line: 13 .it.md hold a link whose alias
    really does straddle a newline ([[house|Salem\\nHouse]]), and a per-line count would read
    "House]]" as an orphan and delete the closing bracket of a perfectly good link. Counting
    globally is also the safe way to be wrong: an earlier unclosed [[ keeps the depth above zero,
    so a later orphan is missed rather than some valid bracket being eaten."""
    buf, depth, i = [], 0, 0
    while i < len(text):
        if text.startswith("[[", i):
            depth += 1
            buf.append("[[")
            i += 2
        elif text.startswith("]]", i):
            if depth:                              # depth 0 -> orfana, si scarta
                depth -= 1
                buf.append("]]")
            i += 2
        else:
            buf.append(text[i])
            i += 1
    return "".join(buf)


def repair_mask_codes(text):
    """Normalise every mangled mask code to [[Lnn|label]], BEFORE unmasking."""
    text = MALFORMED_CODE_RE.sub(r"[[\1|\2]]", text)
    text = UNCLOSED_CODE_RE.sub(_unclosed_code, text)
    return drop_stray_close(text)                   # per ultima: le altre possono chiudere quadre


def strip_mask_codes(text):
    return ANY_CODE_RE.sub(lambda m: m.group(1), text)


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


def is_truncated(en_block, it_block):
    """True if the IT block is too short to be a translation of the EN block.

    The mirror image of is_fabricated, and the failure mode that actually corrupted the vault:
    _ask() caps output at max_tokens=4096, so a source block bigger than roughly 16k chars CANNOT
    come back whole. Asked the impossible, the model returns a sentence or two and stops -- a
    39,617-char Conan Doyle story came back as 100 chars of plausible Italian. Block counts matched
    and no link was invented, so every other check passed and the stub was written to disk.

    Italian runs longer than English, never half as long: below half the source there is no reading
    of the text under which the meaning survived. The 200-char floor keeps headings and one-word
    blocks (where length ratios are meaningless) out of it.
    """
    if len(en_block) < 200:
        return False
    return 2 * len(it_block) + 80 < len(en_block)


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
    # Repair codes Tower mangled ([[L04estate]], [[L04>estate]], [[L04|estate] -> [[L04|estate]])
    # so unmask can map them back to the real target. Idempotent on well-formed [[L04|x]].
    out = repair_mask_codes(out)
    # A block must never contain a blank line, or it would split in two and the emitter would skip
    # the whole page. Collapse defensively rather than trusting the model.
    return re.sub(r"\s*\n[ \t]*\n+\s*", " ", out).strip()


# Two independent ceilings meet here. _ask caps output at 4096 tokens, so a source past ~14k chars
# cannot come back whole whatever the model does; and HY-MT degenerates well before that -- handed
# a long passage it returns one plausible sentence and stops. Measured on Conan Doyle: 2,896 and
# 3,158 chars translate cleanly (ratio 1.13), 2,919 collapses to 46 chars. So the trigger is the
# CONTENT, not the length, and at temperature 0 it is deterministic -- retrying the same text is
# pointless, only a different split escapes it. 3000 is the largest size that translated reliably;
# the finer limits are the recovery ladder.
MAX_BLOCK_CHARS = 3000
RESPLIT_LADDER = (1200, 500)


def _chunk_oversized(block, limit=MAX_BLOCK_CHARS):
    """Split a block too big for one call, at the least damaging seam available.

    translate_block refuses to chop blocks on principle, and it is right to: sentence-wise
    translation destroys the cohesion this pipeline exists to preserve. But that trade-off only
    exists for blocks the model can actually translate. Conan Doyle's atomizer writes one paragraph
    per LINE with no blank line between them, so a whole 39,617-char story arrives as a single
    block; there the choice is not cohesion versus chopping, it is chopping versus a stub. So:
    split on line breaks (real paragraph seams, cohesion mostly intact), and only inside a line --
    on sentences -- when one line alone still overflows. Returns [block] unchanged when it fits.

    A markdown table row is the exception: the caller rejoins pieces with a newline, so cutting
    inside a row would turn one row into several lines and the table would stop being a table.
    That is invisible to every guard -- no blank line is introduced, so the block count and the
    link set both still match. The plays are written as one row per speech, and the longest row
    in the whole corpus (a chorus in Murder in the Cathedral) is ~7k chars, which still fits the
    output cap comfortably, so an oversized row is sent whole as its own chunk instead.
    """
    if len(block) <= limit:
        return [block]
    pieces, buf = [], ""
    for line in block.split("\n"):
        if len(line) > limit and line.lstrip().startswith("|"):
            if buf:
                pieces.append(buf)
                buf = ""
            pieces.append(line)                   # unsplittable: one row, one call
            continue
        if len(line) > limit:                     # one paragraph overflows on its own
            if buf:
                pieces.append(buf)
                buf = ""
            sent = ""
            for s in split_sentences(line):
                if sent and len(sent) + len(s) + 1 > limit:
                    pieces.append(sent)
                    sent = s
                else:
                    sent = (sent + " " + s).strip()
            if sent:
                pieces.append(sent)
            continue
        if buf and len(buf) + len(line) + 1 > limit:
            pieces.append(buf)
            buf = line
        else:
            buf = (buf + "\n" + line) if buf else line
    if buf:
        pieces.append(buf)
    return pieces


def translate_block(en_block, verse=False, tries=3):
    """Translate a prose block, splitting only as far as the model forces us to.

    Whole-block-in-one-call is the rule (see _translate_whole): cohesion is the point. But a block
    the model silently truncates is not a translation at all, and since the collapse is
    deterministic, another sample of the same text returns the same stub. So: translate whole; if
    the result comes back truncated, split finer and retry, walking down RESPLIT_LADDER. Blocks
    already past MAX_BLOCK_CHARS start split. Sub-blocks rejoin with a single newline, never a
    blank line -- a blank line would split the block in two and the emitter would skip the page.
    """
    attempted_whole = False
    it, missing = "", []
    for limit in (MAX_BLOCK_CHARS,) + RESPLIT_LADDER:
        chunks = _chunk_oversized(en_block, limit)
        if len(chunks) == 1:
            if attempted_whole:
                continue                          # this limit doesn't split it either
            attempted_whole = True
            it, missing = _translate_whole(en_block, verse, tries)
        else:
            outs, missing = [], []
            for c in chunks:
                it_c, miss_c = translate_block(c, verse, tries)
                outs.append(it_c)
                missing.extend(miss_c)
            it = "\n".join(outs)
        if not is_truncated(en_block, it):
            return it, missing
    return it, missing                            # exhausted: validate() will reject the atom


def _translate_whole(en_block, verse=False, tries=3):
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


def _ensure_prose(en_block, it_block):
    """Keep a curt reply countable as a prose block.

    The emitter counts a block as prose only if it holds >=3 consecutive letters (has_prose, run on
    the RAW block). Curt Italian replies lose that where English kept it -- "Yes." (3 letters) ->
    "Sì." (max 2). The block then drops from the IT prose count, the EN/IT counts diverge, and the
    emitter skips the WHOLE page (REJECT). Append a neutral intensifier ("davvero" = indeed/really)
    after the last word so the block survives with its meaning essentially intact. Idempotent: once
    has_prose holds, it is left alone.
    """
    if not has_prose(en_block) or has_prose(it_block):
        return it_block
    fixed = re.sub(r"([^\W\d_]+)(?=[^\w]*$)", r"\1, davvero", it_block, count=1)
    return fixed if has_prose(fixed) else it_block


def _plain_title(text):
    """Translate a LINK-FREE chapter subtitle to Italian (strict one-line title register)."""
    out = call_tower("Translate this title to Italian:\n" + text, SYSTEM_TITLE, max_tokens=160)
    out = re.sub(r"\s*\n[ \t]*\n+\s*", " ", out).strip()
    return re.sub(r"^#+\s*", "", out).strip()


def is_verse_path(en_path):
    """True for the subtrees whose atoms are verse and get no expansion margin.

    Plays/ belongs here as much as Poems/ and Long/: Coleridge's and Eliot's drama is
    verse laid out one line per <br> inside a speech row, and read as prose it comes back
    reflowed -- three lines fused into one sentence, which no structural check sees
    (the block count and the link set are both untouched). It was missing for a long
    time, so every Plays/ atom was translated without VERSE_RULE and judged by the
    prose fabrication margin.

    Kept as one function because the caller in run_dickens_hy needs the same verdict for
    validate() that translate_atom uses for the prompt; two copies of the test drifted."""
    p = en_path.replace(os.sep, "/")
    return any(("/%s/" % sub) in p for sub in ("Poems", "Long", "Plays"))


def translate_atom(en_path, cache, fixups):
    verse = is_verse_path(en_path)
    body = _read_vault(en_path)
    parts = split_blocks(clean_body(body))
    bp = boilerplate_mask(parts)
    out = []
    for k, part in enumerate(parts):
        s = part.strip()
        if not s or s.startswith("<nav") or s.startswith("---") or not has_prose(s):
            # separator / nav / YAML frontmatter / non-prose: verbatim. Frontmatter is passed
            # through (never sent to Tower): a long tag list reads to the model as a prompt and it
            # over-generates (fabrication FAIL on block 1, aborting the whole atom); the emitter
            # strips heading/frontmatter chrome anyway, so an English tag block is invisible.
            out.append(part)
            continue
        if bp[k]:
            out.append(part)                      # Gutenberg licence/footer: verbatim, never translated
            continue
        it = cache.get(s)
        if it is None:
            if dh.is_heading_block(s):
                # Headings get deterministic, link-preserving treatment (canonical work titles +
                # curated concept-link titles); only a link-free subtitle hits the model. This can
                # never invent a wikilink target, so it never trips the emitter's REJECT guard.
                it, unknown = dh.translate_heading(s, _plain_title)
                if unknown:
                    it, missing = translate_block(s, verse)
                    if missing:
                        fixups.append({"atom": os.path.relpath(en_path, VAULT_ROOT),
                                       "missing": missing, "en": s, "it": it})
            else:
                it, missing = translate_block(s, verse)
                if missing:
                    # Structure is fine (block count preserved) so the page still publishes; these
                    # links just need re-attaching to the right Italian word in a repair pass.
                    fixups.append({"atom": os.path.relpath(en_path, VAULT_ROOT),
                                   "missing": missing, "en": s, "it": it})
            cache.put(s, it)
        it = strip_mask_codes(it)                 # safety net: kill any leaked [[Lnn..]] code
        it = _ensure_prose(s, it)                 # curt reply must stay a countable prose block
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
        trunc = [(len(e), len(i)) for k, (e, i) in enumerate(zip(ep, ip))
                 if not bp[k] and is_truncated(e, i)]
        if trunc:
            problems.append(f"TRUNCATED content in {len(trunc)} block(s), e.g. {trunc[0][0]} chars "
                            f"EN -> {trunc[0][1]} chars IT")
    et, itt = set(targets(en_body)), set(targets(it_body))
    invented = sorted(itt - et)
    if invented:
        problems.append(f"invented wikilink targets: {invented[:6]}")
    # Leftover unmasked link placeholders. HY sometimes emits [[Lxx|word] with a single
    # closing bracket or a wrong separator ([[Lxx]word], [[Lxx>word]), so unmask/targets()
    # cannot restore them: they slip past the invented-target check (no ]] to capture) and
    # get written to disk as corruption. Any [[LNN token in the output is always a stray
    # mask -- Lxx codes are never real concept targets -- so reject and let it be retried.
    stray = re.findall(r"\[\[L\d{1,3}\b", it_body)
    if stray:
        problems.append(f"leftover mask token(s): {len(stray)} (e.g. {stray[0]}..)")
    # Leaked CJK. Observed as "[[cheese|<CJK>]]formaggio]]": the target is real and no mask code
    # survives, so every check above passes while the markup is broken and neighbouring links are
    # dropped. Flag only scripts absent from the source, so an atom that legitimately quotes CJK
    # is not rejected for quoting it.
    leak = cjk_leak(en_body, it_body)
    if leak:
        problems.append(f"leaked CJK character(s): {len(leak)} (e.g. {''.join(leak[:4])})")
    # Unbalanced wikilink brackets -- but only when the source itself was sound: some EN atoms
    # carry a genuine "[[[" typo or a nested [[South [[Africa]]]], and reproducing the source's
    # own defect is not a translation bug. See bracket_defect() for why counting isn't enough.
    if bracket_defect(en_body, it_body):
        problems.append(f"unbalanced wikilink brackets: {it_body.count('[[')} [[ vs "
                        f"{it_body.count(']]')} ]] (EN balanced at {en_body.count('[[')})")
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
    total_blocks = sum(len(prose_blocks(_read_vault(p))) for p in pending)
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
        en_body = _read_vault(en_path)
        problems = validate(en_body, it_body, "/Poems/" in en_path.replace(os.sep, "/") or "/Long/" in en_path.replace(os.sep, "/"))
        if problems:
            print(f"[{i}/{len(pending)}] REJECT {rel}: {'; '.join(problems)}", flush=True)
            failed += 1
            continue
        _write_vault(en_path[:-3] + ".it.md", it_body)
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
