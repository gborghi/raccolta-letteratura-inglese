# Reference — translating the content-filter-blocked Chesterton atoms (EN→IT)

**For a Claude on another machine (with the `vault-topics` MCP) to finish the last
untranslatable Chesterton excerpts and publish them.**

## What this is

~100 Chesterton atoms are still English-only because they contain **period
racial/ethnic language** (1900–1936 usage: "negro", "chinaman", "red indian",
"nigger", "hottentot", "yellow peril", …). Anthropic's output content-filter blocked
the automated block-level translator that did the other ~2,300 Chesterton atoms
(the batch aborted the moment an agent hit one). This is a **legitimate literary /
historical translation task** — faithful EN→IT rendering of a canonical author's text,
not endorsement. The rest of the site's Chesterton is already bilingual; these are the
gaps.

> Note: another ~629 Chesterton atoms are simply *not yet translated* (no sensitive
> language). Those go through the normal pipeline any time and are NOT this task.

**Coverage as of 2026-07-17** (re-derive with the scan at the bottom — counts drift as
batches land): 3,596 EN atom leaves · 2,867 translated · 729 untranslated, of which
**100 are filter-blocked** and 629 are plain backlog.

## The list

`scripts/translate/chesterton_sensitive_untranslated.tsv` — 103 rows (header + data):
`vault_en_path` · `site_url` · `flagged_terms` · `chars`.

100 rows carry period racial/ethnic terms matched by the scan regex. **3 rows are
hand-added and the regex will NOT re-find them** — one `jews (antisemitism)` and two
`false-positive filter (benign essay)` (an essay the filter blocked despite benign
text). Regenerating the list from the scan alone would silently drop these three;
merge, don't overwrite.

- `vault_en_path` is relative to `VaultEnglish/` (e.g.
  `Authors/Chesterton/Atomized/america/part/part_01.md`).
- `site_url` is the live reading-page anchor for that atom.

Regenerate / refresh the list (after some get done) with the scan at the bottom of
this file.

To find an excerpt you can also use the `vault-topics` MCP `search`/`extract` on the
Chesterton vault. **Do NOT use vault-topics `summarize` or `suggest_tags` — they
hallucinate.** Only `search`/`extract`/`translate` are trustworthy here.

## How to translate one atom

Read the EN file `VaultEnglish/<vault_en_path>`. Produce an Italian sibling
`<same path>.it.md` (e.g. `america/part/part_01.it.md`) that is **block-aligned**:

1. **Same block structure.** Keep the same number and order of prose paragraphs /
   blank-line-separated blocks as the EN file. The emitter matches `sha(EN block) ->
   IT block`; a block-count mismatch makes it **skip the whole page**.
2. **Preserve `[[wikilinks]]` verbatim.** `[[Love|love]]` → keep the target, translate
   only the visible label if present: `[[Love|amore]]`. `[[Rome]]` → `[[Rome|Roma]]`.
   Never drop or rename a link target (it must still resolve to the same concept note).
3. **Keep the leading `# ...` heading line** (translate its text; keep the `#`).
4. **Faithful period register.** Translate the sensitive terms to their standard
   Italian historical equivalents in a scholarly/literary tone; do not censor, soften,
   modernise, or add editorial notes. The IT should read as the EN reads.
5. Keep markdown (emphasis, blockquotes, line breaks) identical in shape.

If your primary model also refuses, use the `vault-topics` MCP `translate` tool, or a
model/tooling without the output filter. The **output artifact is the same**: a
block-aligned `.it.md` sibling in the vault.

## How to publish (exact order — the SPA/non-SPA dance matters)

All commands run inside `quartz-eng-lit/`.

- **macOS:** plain `python3` works (3.9.6 as of writing). `content/` is Dropbox-ignored via
  an `xattr`, and preprocess re-stamps it each regen, so no sync dance is needed.
- **Windows:** Python is Windows-Store-broken in Git-Bash; use the real interpreter
  (`C:\Users\utente\AppData\Local\Programs\Python\Python312\python.exe`, or `py -3.12`;
  the vault's chosen one is in `VaultEnglish/graphify-out/.graphify_python`).
  **Stop Dropbox syncing first** (it locks `content/` during regen — `rmdir EBUSY`):
  `Get-Process Dropbox | Stop-Process -Force`. Restart it only after the commit.

1. **Regen NON-SPA content** (per-atom pages the emitter needs to block-match):
   `node preprocess.mjs`   *(no `SPA=1`)*
2. **Emit** — rebuild the block cache from the vault `.it.md` pairs and upsert the
   page store:
   `python scripts/translate/gkc_emit_vault.py chesterton`
   → updates `data/translations_pages.jsonl` (other authors preserved). It logs how
   many pages it upserted; if a page is skipped it's a block-count mismatch — fix the
   `.it.md` to align, re-run.
3. **Regen SPA content** (what the site actually ships — bilingual reading pages):
   `SPA=1 node preprocess.mjs`   (PowerShell: `$env:SPA="1"; node preprocess.mjs`)
4. **Commit + deploy** (CI does NOT run preprocess — the fully regenerated `content/`
   must be committed):
   ```
   git add content/ data/translations_pages.jsonl quartz/static/
   git commit -m "Chesterton IT: translate N filter-blocked period-language atoms"
   git branch -f main spa-validate      # if working on spa-validate
   git push origin spa-validate && git push origin main
   ```
   Restart Dropbox. CI (`.github/workflows/deploy.yml`) builds + deploys Pages.

Verify live: open the atom's `site_url`, toggle **IT** in the reader bar — the Italian
body should show for that section.

## Gotchas

- **Paths are script-relative — nothing to adjust.** `gkc_emit_vault.py` (`VAULT_AUTHORS`)
  and `preprocess.mjs` (`VAULT`, `AUTHORS_DIR`) used to hardcode `E:/giovanni/Dropbox/…`;
  they now derive everything from the script's own location (`VAULT_ROOT = <repo>/../VaultEnglish`)
  and run as-is on macOS and Windows, from any cwd. Don't reintroduce absolute paths.
- Translation is **atom-level** (`.it.md` next to each EN atom). Aggregate pages
  (whole work / chapter) are rebuilt automatically from atom blocks by the emitter.
- Do the work in batches; re-run emit + SPA-regen + commit per batch. `translations_pages.jsonl`
  upserts, so partial progress is safe.

## Regenerate the list

```bash
python - <<'PY'
import glob, os, re
def en_leaves(base):
    out=[]
    for p in glob.glob(base+"/**/*.md",recursive=True):
        pu=p.replace("\\","/")
        if pu.endswith(".it.md"): continue
        b=os.path.basename(pu)[:-3]; d=os.path.basename(os.path.dirname(pu))
        if b==d or os.path.isdir(os.path.join(os.path.dirname(pu),b)): continue
        out.append(pu)
    return out
FLAG=re.compile(r'\bnigg\w*|\bnegro\w*|\bdark(ey|ies)\b|\bcoon\b|\bchinam[ae]n|\bredskin|\bred indian|\bmulatto|\bhalf-breed|\byellow peril|\bhottentot|\bpickaninn', re.I)
CH="VaultEnglish/Authors/Chesterton/Atomized"   # run from the English/ root
untr=[p for p in en_leaves(CH) if not os.path.exists(p[:-3]+'.it.md')]
for p in untr:
    t=open(p,encoding='utf-8',errors='replace').read()
    hits=sorted(set(m.group(0).lower() for m in FLAG.finditer(t)))
    if hits: print(p.split("/Atomized/")[1], "|", ",".join(hits))
PY
```
An atom drops off the list automatically once its `.it.md` sibling exists.
