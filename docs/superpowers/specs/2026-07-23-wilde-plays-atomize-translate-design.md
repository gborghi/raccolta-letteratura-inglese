# Wilde — plays/prose atomization + full-corpus EN→IT translation

**Date:** 2026-07-23
**Status:** Approved (design), pending implementation plan
**Repo:** `quartz-eng-lit/` (vault at sibling `VaultEnglish/`)

## Problem

Wilde has 61 atomized atoms on the site (Dorian Gray, Intentions essays, De Profundis,
Ballad, a few stories/fairy tales), but **15 works exist only as `_raw` + KG work-notes
with no `Atomized/` split** — so they render as a single page, and Wilde's plays are
absent as navigable reading units:

- **9 plays** — Vera, The Duchess of Padua, Lady Windermere's Fan, A Woman of No
  Importance, Salomé, An Ideal Husband, The Importance of Being Earnest,
  La Sainte Courtisane, A Florentine Tragedy.
- **3 fairy tales** — The Happy Prince, The Nightingale and the Rose, The Selfish Giant.
- **2 stories** — The Sphinx Without a Secret, The Model Millionaire.
- **1 poem** — The Sphinx (030).

Goal: atomize all 15 (plays in Shakespeare `Plays/` table style), fully integrate them
into the knowledge graph (per-atom tags, backlinks; clusters/graph already present via
work-notes), ensure each play's acts land on **one SPA reading page**, then translate the
entire Wilde corpus EN→IT with the Chesterton Opus workflow.

## Findings (established during brainstorming)

- **Raw plays are already table-formatted** (`| Chi parla | Battuta |`) and split by
  `### ACT ONE/TWO/…` headings. The `play_to_table` conversion was already applied.
- **Wilde source has no scenes** — only acts (real `Act.Scene` numbering, as in
  Shakespeare `1.2`, does not exist in Wilde). Faithful atom unit = **one atom per act**.
  Per-scene atoms would fabricate divisions Wilde never wrote.
- **An Ideal Husband** is malformed in `_raw`: only `### ACT ONE` is a heading; acts 2–4
  are trapped inside a table cell (`| MRS | ACT DROPS<br><br>FOURTH ACT<br>… |`). Needs
  repair before/while splitting.
- **Salomé, La Sainte Courtisane, A Florentine Tragedy** are single continuous acts.
- **Vera** has a `### PROLOGUE` plus 4 acts.
- All 15 work-notes already carry `cluster:` **and** work-level `tags:` → cluster / graph /
  wheel membership is already satisfied (these feed off `type:work` notes, not atom
  frontmatter — see memory `eng-lit-tags-only-from-work-notes`).
- `preprocess.mjs:604` iterates `["Atomized","Plays","Long"]` under **every** author dir →
  a new `Authors/Wilde/Plays/` is auto-discovered and SPA-emitted per work. No
  Shakespeare-specific hardcoding.
- `classifyUnit` (`preprocess.mjs:535`) recognizes `Scene_(\d+)` but **not** `Act_(\d+)`;
  an `Act_1.md` would default to `unitType:"work"` (treated as intro). Requires a small
  classifier patch OR the `Act_N/Scene_1.md` nesting workaround.
- Existing play pipeline scripts live in `VaultEnglish/graphify-out/lit/`:
  `split_shakespeare.py` (split raw → Plays/Act/Scene units, incl. `LONG_SCENE=6000`
  speech-split), `play_to_table.py`, `convert_all_plays.py`.

## Design

### 1. Atomization

**Plays** → `Authors/Wilde/Plays/<Play>/`:
- `<Play>.md` — intro atom (title, blurb, PERSONS list), taken from the raw preamble.
- One atom per act: `Act_N/…` (Vera also `Prologue`). Raw table content copied verbatim.
- **Long acts** (>6000 chars, e.g. Importance Act 1) → Shakespeare-style monologue /
  dialogue-exchange speech sub-units (reuse `split_shakespeare.py` machinery:
  `MONO=900`, `EXCH=2800`).
- **An Ideal Husband** — recover acts 2–4 from the trapped table cell, re-split as headings.
- **Salomé / La Sainte / Florentine** — single `Act_1` atom (whole).
- Repoint the 9 play work-notes `source →` `Authors/Wilde/Plays/<Play>/<Play>.md`.

**preprocess patch:** add `Act_(\d+)` to `classifyUnit` so acts classify as a scene-like
reading unit (frag `#act_N`, label "Act N"), not `work`/intro. Surgical, in the existing
classifier block. This is a fork core-patch (documented as such).

**Fairy tales + stories** → `Authors/Wilde/Atomized/<NNN_Work>/` via the standard prose
atomizer (whole, or `Section_NN` / `Chapter_NN`). Short tales may stay single-atom.
Repoint their work-notes source.

**Sphinx poem (030)** → verse atomization (Ballad of Reading Gaol / Dickinson model —
whole or stanza-group). Repoint work-note source.

### 2. KG integration (BEFORE translation)

- **Clusters + graph/wheel** — already done via work-notes. No action.
- **Per-atom tags** — generate for every new atom: deterministic character-name match
  (free) + capped Opus for themes/motifs against the constrained vocab (Phase-2
  pipeline, `data/tag_vocab.json` / `tag_batches`). Feeds per-atom search
  (`atom_search.json.gz`) and reader chips. Do NOT use `vault-topics summarize` /
  `suggest_tags` (they hallucinate — memory `vault-topics-summarize-hallucinates`).
- **Links** — inline `[[wikilinks]]` are already in the raw text. Run `inject_backlinks.py`
  so new atoms get concept back-refs → `related.json` → "Capitoli correlati" cards.

### 3. SPA (automatic)

Preprocess emits one SPA reading page per work; acts/chapters become `work#frag`
fragments routed client-side by `atomRouter.inline.ts`. Plays ride the generic
`["Atomized","Plays","Long"]` loop, so **each play = one SPA page** with its acts as
`#act_N` fragments (mirrors Shakespeare `testi/shakespeare/plays/macbeth#act_1--scene_1`).
The generated redirect map keeps any old per-atom URLs alive.

### 4. Translation (AFTER integration)

- Engine: **Claude Opus 4.8**, **7 atoms per agent** (memory
  `chesterton-batch-7-atoms-per-agent`), skip-if-exists for resumability.
- Workflow (Chesterton): batch of 7 → on content-filter block, **retry 1 atom/agent** →
  residual blocked atoms appended to `data/wilde_tower_pending.tsv` for the macOS
  **tower72** model (Windows box can't run it).
- **Contract A (play tables):** translate the `Battuta` column (dialogue) and
  `*(didascalia)*` stage directions → Italian; keep `Chi parla` speaker labels as-is
  (proper nouns); preserve `[[link]]` targets, translating only the visible alias
  (`[[Marriage|matrimonio]]`); keep the table structure and `<br>` line breaks.
- **Prose / verse** (Dorian already done; new fairy tales, stories, essays, Sphinx,
  Ballad) translate as normal atoms, same link-preservation contract.
- Output: **bilingual qlang pages** (EN/IT toggle) — same emit as Chesterton →
  `data/translations_pages.jsonl` → preprocess (NOT `.it.md`).
- STOP Dropbox sync during large regen.

### 5. Build / deploy

`SPA=1 node preprocess.mjs` → `npx quartz plugin restore` → build (14 GB heap) →
`make-mobile-index.mjs` → `compress-search-index.mjs` → `gen-tags-table.mjs`. Commit the
fully regenerated `content/` + `quartz/static/`, push; CI restore→build→post-chain deploys.
Commit the full content/ (memory `quartz-eng-lit-commit-full-content`) — CI does not run
preprocess.

## Order of operations

1. Split plays → `Plays/` (incl. Ideal Husband repair, long-act splits) + prose/poem atomize.
2. `preprocess.mjs` `Act_` classifier patch.
3. Repoint the 15 work-notes' `source`.
4. Per-atom tagging for new atoms.
5. `inject_backlinks.py` → `related.json`.
6. Local SPA preprocess + build to verify plays render as one SPA each (Playwright, not curl).
7. Translate all Wilde atoms (Opus 7/agent + retry + tower72 residual).
8. Emit bilingual pages, full preprocess/build, commit, push, CI deploy.

## Non-goals (YAGNI)

- No per-scene fabrication (Wilde has no scenes).
- No new KG concept/cluster nodes (work-notes already tagged + clustered).
- No re-atomization of the existing 61 Wilde atoms.
- No translation of Shakespeare plays (separate future work).

## Risks / gotchas

- An Ideal Husband malformed raw — the split must detect and recover the trapped acts, else
  the play collapses to one atom.
- `Act_` classifier patch is a fork core-patch — must survive future Quartz plugin restores
  (document alongside the other `content-index` / `graph` fork patches).
- Play-table translation is new territory — verify one act end-to-end (links intact, table
  intact, EN/IT toggle) before fanning out agents.
- Content-filter blocks likely on Salomé (violence) and Vera (assassination) — expect
  tower72 residuals.
- Keep everything script-relative (macOS + Windows); never hardcode a machine path.
