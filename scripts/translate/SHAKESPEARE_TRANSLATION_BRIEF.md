# Shakespeare EN→IT translation brief (Opus agents)

Shared contract for the play-translation run. One agent per play; every agent follows this file so
all 41 plays come out consistent. Companion validator: `shakespeare_check.py`.

## Paths

Vault root: `/Users/g.borghi/Library/CloudStorage/Dropbox/insegnamento/Wiligelmo/SubjectBrain/English/VaultEnglish`
Plays: `<vault>/Authors/Shakespeare/Plays/<Play>/`

Leaves to translate for your play — **the scene atoms only**:

- `<Play>/Act_*/Scene_*.md` — scene atoms (frontmatter + heading + one markdown table)

**Do NOT translate the play-level `<Play>/<Play>.md`.** It contains every scene of the play inline,
verbatim, plus an editorial introduction and dramatis personae. It is assembled separately from your
scene translations (`shakespeare_assemble.py`) so that the play page and the scene pages render the
same Italian for the same speech. Translating it here would double the work and guarantee the two
copies disagree.

For each leaf `X.md` write a sibling `X.it.md` in the same directory.
**Never modify an English source file.** Never touch another author's or another play's files.

## Method — strictly one file at a time

Read one leaf → translate → Write its `.it.md` → validate → next. Do **not** read several leaves up
front, and do **not** batch writes: the largest scenes are tens of KB and batching will exhaust
context mid-play, losing work already done.

## The contract

### 1. Links are graph edges — never change a target

This is an Obsidian knowledge-graph vault. In `[[Target|label]]`, `Target` is an English
concept-note id. Copy it **byte-for-byte**; translate only the visible `label`.

```
[[Well|well]]            ->  [[Well|bene]]
[[Ambition|ambition]]    ->  [[Ambition|ambizione]]
[[Lady Macbeth|LADY MACBETH]] -> [[Lady Macbeth|LADY MACBETH]]
[[Juliet]]               ->  [[Juliet|Giulietta]]        (alias form, NOT [[Giulietta]])
[[Duncan]]               ->  [[Duncan]]                  (leave bare when Italian is identical)
```

The finished file must contain **exactly the same multiset of link targets** as the source: none
dropped, none invented, none renamed. This is the check most likely to fail you.

### 2. Frontmatter passes through verbatim

The leading `---` … `---` YAML block is copied **untranslated**. The tags are concept ids
(`concept/ambition`, `motif/blood`), not prose. Translating them is a hard failure. Scene atoms have
frontmatter; play-level files generally do not.

### 3. Heading

`# [[Macbeth]] — Act I, Scene 7`  →  `# [[Macbeth]] — Atto I, Scena 7`

- `Act` → `Atto`, `Scene` → `Scena`. Keep the numerals and the `—` exactly.
- Titles appear in three shapes; all obey rule 1:
  - single link: `# [[Macbeth]] — …`
  - **no link at all**: `# The Tempest — …` → `# La tempesta — …` (plain text, add no link)
  - split across links: `# [[Romeo]] and [[Juliet]] — …` → `# [[Romeo]] e [[Juliet|Giulietta]] — …`

### 4. The table is the scene body

- Header `| Chi parla | Battuta |` and separator `|---|---|`: copy **exactly**. Already Italian.
- Stage-direction marker `*(didascalia)*`: copy **exactly**. Translate the direction text beside it.
- **One output row per input row**, same order, same count. Never merge, split, drop, or reorder.
- Preserve every `<br>` exactly — they are verse line breaks, one per line of verse.
- Speaker cells stay ALL-CAPS. Translate a speaker name only where an established Italian form
  exists (`KING` → `RE`, `DUKE` → `DUCA`, `FIRST LORD` → `PRIMO SIGNORE`); personal names
  (PROSPERO, CALIBAN, MACBETH) stay as they are.

### 5. Register

Shakespearean drama, largely blank verse. Produce faithful literary Italian in the register of the
standard Italian Shakespeare.

- **A line of verse stays a line of verse.** Never expand a verse line into a prose sentence; never
  fuse two lines into one. Prose passages stay prose.
- Keep the period register. Do not modernize, do not paraphrase loosely, do not soften.
- Add nothing: no translator's notes, no glosses, no commentary, no fences around the file.

## Validate every leaf

After writing each `.it.md`:

```
cd /Users/g.borghi/Library/CloudStorage/Dropbox/insegnamento/Wiligelmo/SubjectBrain/English/quartz-eng-lit/scripts/translate
/usr/bin/python3 shakespeare_check.py check "Authors/Shakespeare/Plays/<Play>/<...>.md"
```

Pass the path of the **English** file, relative to `VaultEnglish/`. It prints JSON with `status`
(`OK` / `FAIL`) and a `problems` list.

If `FAIL`: read the problems, fix the `.it.md`, re-check. Up to **2 fix attempts** per leaf. If it
still fails, leave the file, note it, and continue — one bad leaf must not stop the play.

Common problems and what they mean:

| problem | meaning |
|---|---|
| `dropped links: [...]` | those targets vanished — restore them |
| `invented links: [...]` | you renamed a target (usually translated it) — restore the English id |
| `frontmatter altered` | you translated or reformatted the YAML — copy it verbatim |
| `table rows N IT vs M EN` | you merged/split/dropped rows — one row per row |
| `length ratio ...` | truncated (stopped early) or padded — translate the whole leaf, nothing extra |

## Dropbox

The vault sits inside Dropbox; its File Provider intermittently throws `Operation not permitted`
(EPERM) on a read or write. On EPERM, wait ~2s and retry the same operation, a few times.

## Report

Finish with a compact report: leaves total, leaves OK, and for anything not OK its path plus the
final `problems`. Be accurate — never report a leaf OK unless the checker said `OK`.
