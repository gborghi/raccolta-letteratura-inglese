# Handoff — traduzione EN→IT

**Fotografia del 2026-08-05, 00:05.** Misure rifatte da zero sul vault (non copiate da log
precedenti). I due processi vivi al momento della fotografia sono elencati in §1.

---

## 0. Le regole che non si negoziano

Prima di toccare qualunque cosa, queste sono decisioni già prese: non vanno ridiscusse,
vanno rispettate.

1. **La prosa si traduce con HY-MT** (server locale). Non con Opus.
2. **Opus si usa solo per** (a) la poesia e (b) gli atomi rifiutati due volte da HY.
   Eccezione esplicita: **Whitman va fatto con HY**, non con Opus, e raggruppato in cluster
   come Dickens.
3. **Keats si tratta come Emily Dickinson** a livello di vault (cluster + tail merge).
4. **Si traducono solo le foglie.** Gli aggregati (`Work/Work.md`, `Work/Chapter_NN.md` che
   hanno una directory sorella) **non si traducono mai**: si **assemblano** dalle foglie con
   `assemble_aggregates.py`. La regola è *strutturale*, non basata sul nome — la decide
   `leafcheck.is_leaf()`.
5. **I file-libro non si traducono**, si assemblano.
6. **Un solo processo**, non due in parallelo sullo stesso autore.
7. **Notifica via `wiligelmo-gas`** (`notify_gas_mail.py`) a ogni atomo finito.
8. **Non spegnere Dropbox sul Mac.** Il consiglio "stop sync" in CLAUDE.md vale solo su
   Windows; qui pausare Dropbox rompe l'idratazione del vault.
9. **Uccidere per PID esatto, mai `pkill -f`.**
10. **Hemingway è escluso** (`EXCLUDE_AUTHORS` in `preprocess.mjs`, copyright): le sue 197
    foglie non vanno tradotte, non finiscono sul sito.

---

## 1. Che cosa sta girando adesso

| PID | cosa | da quanto | log |
|---|---|---|---|
| `18185` | `./run_queue_all.sh Conan_Doyle Dickens Belloc Wilde Austen Whitman Poe Dickinson Bronte` | ~10 h (avviato 2026-08-04 14:00) | `scripts/translate/run_logs/authors_hy.log` |
| `73732` | `bash sync-and-build.sh` (build del sito, non traduzione) | pochi minuti | `sync-v5.log` |

La coda è ferma sul **primo** autore della lista: Conan_Doyle, atomo **285/317**, ritmo
~1 blocco/min ≈ **1,8 min/atomo**. Gli altri otto autori non sono ancora stati toccati da
questo giro.

Ordine effettivo della coda: `Conan_Doyle → Dickens → Belloc → Wilde → Austen → Whitman →
Poe → Dickinson → Bronte`. (L'ordine di default in `run_queue_all.sh` è un altro; questo
giro è stato lanciato con argomenti espliciti per chiudere prima i quasi-finiti.)

---

## 2. Stato: quanto è tradotto

### 2.1 Foglie (l'unica cosa che si traduce davvero)

Misurato ora, contando `X.md` che ha un `X.it.md` accanto, solo sulle foglie:

| autore | foglie | tradotte | mancano | % |
|---|---:|---:|---:|---:|
| Bronte | 966 | 221 | **745** | 22,9 % |
| Whitman | 738 | 0 | **738** | 0,0 % |
| Dickinson | 1730 | 1192 | **538** | 68,9 % |
| Poe | 452 | 0 | **452** | 0,0 % |
| Austen | 673 | 368 | **305** | 54,7 % |
| Hemingway | 197 | 0 | *197* | *escluso — non tradurre* |
| Wilde | 55 | 11 | **44** | 20,0 % |
| Conan_Doyle | 1017 | 983 | **34** | 96,7 % |
| Dickens | 4132 | 4129 | **3** | 99,9 % |
| Belloc | 3022 | 3021 | **1** | 100,0 % |
| Chesterton | 3568 | 3568 | 0 | ✅ |
| Keats | 134 | 134 | 0 | ✅ |
| Sayers | 65 | 65 | 0 | ✅ |
| Shakespeare | 154 | 154 | 0 | ✅ |
| **TOTALE** | **16 903** | **13 846** | **3 057** | **81,9 %** |

Al netto di Hemingway restano **2 860 foglie** da tradurre. A 1,8 min/atomo con la coda
attuale a 4 worker: **~86 ore di macchina**, cioè 3–4 giorni pieni se non si interrompe.
Whitman e Poe sono i due blocchi mai iniziati (1 190 foglie in due).

Copia congelata di questa tabella: `scripts/translate/handoff/stato_foglie_20260805.txt`.

### 2.2 Aggregati (si assemblano, non si traducono)

| autore | aggregati | con `.it.md` | mancano |
|---|---:|---:|---:|
| Chesterton | 697 | 532 | 165 |
| Bronte | 226 | 16 | 210 |
| Austen | 188 | 89 | 99 |
| Poe | 84 | 0 | 84 |
| Conan_Doyle | 88 | 32 | 56 |
| Hemingway | 41 | 0 | *41 — escluso* |
| Dickens | 863 | 845 | 18 |
| Belloc | 402 | 389 | 13 |
| Whitman | 13 | 0 | 13 |
| Wilde | 5 | 0 | 5 |
| Sayers | 14 | 14 | 0 |
| **TOTALE** | **2 621** | **1 917** | **704** |

Quasi tutti questi buchi si chiudono **da soli** rieseguendo `assemble_aggregates.py` quando
le foglie sotto sono complete: non sono lavoro di traduzione. I 165 di Chesterton sono un
caso a parte — vedi §5.

### 2.3 Pubblicato sul sito

`data/translations_pages.jsonl` — **16 891 pagine**, ultimo aggiornamento **2026-08-04
13:26** (190 MB). Campi: `rel`, `kind`, `title_it`, `body_it`.

| | pagine |
|---|---:|
| dickens | 4 905 |
| chesterton | 4 348 |
| belloc | 3 361 |
| dickinson | 1 192 |
| shakespeare | 1 047 |
| conan_doyle | 695 |
| austen | 456 |
| wilde | 424 |
| bronte | 238 |
| keats | 145 |
| sayers | 78 |

**Whitman e Poe non compaiono: zero pagine italiane pubblicate.**

Promemoria che è già costato tempo una volta: un `.it.md` nel vault **non è pubblicato**.
`preprocess.mjs` ignora i `.it.md`; il sito legge solo `translations_pages.jsonl`, e solo le
pagine **integralmente** tradotte vengono emesse. Dopo ogni blocco di traduzione va rifatto
il passo di emissione, altrimenti il lavoro resta invisibile.

---

## 3. Il backlog dei rifiuti

`run_logs/dickens_rejected.jsonl` — 1 699 righe, **1 649 atomi distinti**, ultimo rifiuto
**2026-08-04 14:11** (cioè: la coda attuale ne produce ancora).

Per autore (tutte le righe): Conan_Doyle 968 · Bronte 395 · Austen 205 · Chesterton 90 ·
Belloc 35 · Dickens 6.

Cause:

| n | causa |
|---:|---|
| 844 | `HY call failed: HTTPError 400` |
| ~530 | `leftover mask token(s)` (residui `[[L01…`, `[[L02…`, `[[L03…`) |
| 112 | `tower failed after 3 tries: HTTPError 400` |

**Ma il numero che conta è un altro.** Dei 1 649 atomi rifiutati, quelli **ancora senza
`.it.md`** sono solo **514**:

| autore | atomi rifiutati ancora scoperti |
|---|---:|
| Bronte | 362 |
| Austen | 105 |
| Conan_Doyle | 44 |
| Dickens | 3 |
| **TOT** | **514** |

Gli altri ~1 135 sono già stati recuperati da passaggi successivi. I 514 sono un
sottoinsieme dei 2 860 mancanti di §2.1, non un lavoro in più: **un rifiuto non scrive
nessun `.it.md`, quindi lo sweep per autore lo ripesca da solo**. Non esiste un consumatore
dedicato della coda dei rifiuti — l'unico modo di smaltirli è **rieseguire l'autore**.

Le due cause note e già diagnosticate:
- l'**HTTPError 400 di massa è overflow di contesto** sul server HY (8192 token), non
  richieste malformate;
- i **mask token residui** venivano in buona parte dalla **cache avvelenata**: la cache dei
  blocchi rigiocava output corrotto scavalcando ogni riparazione. Validare gli artefatti in
  cache **in lettura**, non solo in scrittura.

---

## 4. Poesia: quello che aspetta Opus

Due autori **non sono atomizzati affatto** — hanno solo `Long/`, niente `Atomized/`, quindi
non compaiono in nessuna tabella sopra:

- **Coleridge** — 15 file in `Long/`, `_raw/` presente. Fuori dalla catena HY di proposito.
- **Eliot** — 43 file in `Long/`. Fuori dalla catena HY **e** in copyright (PD 2036,
  `copyrightGuard.inline.ts`): il testo esiste sul sito ma è nascosto fino al 2036.
- **Auden** — solo `_raw/`, né `Long/` né `Atomized/`: non è mai entrato in pipeline.

Vanno tradotti con **Opus**, non con HY, e prima serve decidere l'atomizzazione (per
Coleridge probabilmente il trattamento Keats/Dickinson: cluster + tail merge, vedi
`data/keats_cluster_map.json` e `data/dickinson_cluster_map.json` come modello).

Whitman invece **resta su HY** per decisione esplicita, con clustering alla Dickens
(`data/whitman_cluster_map.json`, `data/whitman_tail_merge.json` già pronti).

---

## 5. Lavori aperti, in ordine di urgenza

### #14 — Riassemblare 24 aggregati con `--force` *(bloccato, non dimenticato)*
Lista e motivazioni: `scripts/translate/handoff/aggregati_da_riforzare.txt`.
Script: `scripts/translate/handoff/force_reassemble.py`.

Blocco 1 (19 opere): contenevano blocchi di cache corrotti — Belloc ×10, Dickens ×9.
Blocco 2 (aggiunte il 2026-08-04): l'aggregato **diverge dalle sue foglie**, con due prove
indipendenti che concordano (una `]]` orfana che nessuna foglia contiene; la riga-firma di
almeno una foglia assente dall'aggregato). Include `A_Tale_of_Two_Cities`,
`David_Copperfield`, `Oliver_Twist`, `The_Cricket_on_the_Hearth`,
`Sayers/The_Mind_of_the_Maker`.

**Bloccato da `force_reassemble.py::code_vive()`**: rifiuta di girare mentre una coda è
viva, e a ragione — assemblare mentre le foglie vengono scritte **tronca in silenzio**.
Va lanciato a coda ferma (PID 18185 spento).

Due trappole già pagate:
- **l'mtime non rivela lo stantio.** Pickwick, Oliver_Twist, The_Cricket_on_the_Hearth e
  Martin_Chuzzlewit hanno l'aggregato *più recente* delle foglie e contengono lo stesso
  un'orfana che le foglie non hanno.
- **senza `--force` l'assemblatore riusa i capitoli esistenti**: un libro costruito da
  foglie sane può nascere corrotto.

### #21 — Coda di riparazione link: 40 320 link mai riagganciati
Solo l'**87,3 %** dei wikilink sopravvive al passaggio in italiano. **Sayers è a 0 %**,
Chesterton al 98,7 %. La guardia in pipeline punisce il link *inventato*, non quello
*perso*: per questo il buco non si è mai auto-segnalato. I `*_linkfix.jsonl` in `data/`
sono il materiale grezzo; manca il consumatore.

### #20 — `#` spurio in 1 531 foglie
Rimuoverlo e mettere la guardia in pipeline, altrimenti si ricrea.

### #19 — 91 H1 troncati nelle sorgenti EN
Il **bloccante è già risolto in pipeline**; resta il cosmetico sulle sorgenti.

### #15 — 124 wikilink annidati nelle sorgenti EN
`[[South [[Africa]]]]`. La guardia ora li esenta **strutturalmente** (guarda la struttura,
non conta le quadre) — se tornasse a contare, quegli atomi si rifiuterebbero per sempre.
Resta da decidere se ripulire le sorgenti.

### Decisioni editoriali parcheggiate — **servono all'utente, non a me**
- **frontmatter Chesterton**;
- **139 vecchi aggregati** + i **162 aggregati Chesterton tradotti dal modello come blocco
  unico** (non assemblati dalle foglie: riassemblarli non è una riparazione, è una scelta
  editoriale — sono i 165 buchi di §2.2);
- **4 titoli Chesterton senza precedente**. Regola già valida: un titolo *già determinato da
  un precedente* in `work_titles.py` si aggiunge senza chiedere;
- **4 poesie Keats orfane**.

---

## 6. Trappole operative — leggere prima di rilanciare qualunque cosa

- **Una coda viva usa il modulo stantio.** Riparare `dickens_tower.py` non ripara la coda già
  avviata: confronta l'`mtime` del file con l'`lstart` del PID prima di credere a un reject.
- **Le copie in conflitto di Dropbox avvelenano gli atomi**: vengono tradotte *e*
  concatenate due volte negli aggregati. Controllarle dopo ogni sync.
- **Un offset che avanza non è prova di lavoro.** Nei tailer guarda `sent`/`fixed`, non
  l'offset; e riavvia il tailer dopo averlo modificato.
- **Livelock del rescue loop:** il watcher uccide `retranslate_rejected.py` a 3600 s, quindi
  `dickens_unresolved.jsonl` resta vuoto e `--skip-unresolved` non salta mai nulla.
- **`task_done()` doppio uccide i worker** — il ramo REJECT contava l'elemento due volte,
  ammazzando i thread al drain e perdendo atomi in silenzio. Corretto il 2026-08-03; non
  reintrodurlo.
- **Il leak `half` (U+534A):** HY rende il `half-` dei composti col carattere Han isolato. Va
  **riparato in `semi-` prima della cache**, non rifiutato, o l'atomo si blocca per sempre.
- **File `.md` di capitolo/libro ridondanti:** solo gli split `part_NN` ricevono `.it.md`.
  Contare i file capitolo/libro come non tradotti inventa un backlog fantasma.

---

## 7. Sequenza consigliata da qui

1. **Lasciar finire Conan_Doyle** (32 atomi, ~1 h). Poi la coda passa da sola a Dickens (3),
   Belloc (1), Wilde (44): tre autori che si chiudono in poche ore.
2. **A coda ferma**, lanciare `force_reassemble.py` sui 24 di #14 — è l'unico lavoro che
   *richiede* la coda spenta, quindi va incastrato in una finestra di pausa.
3. Rilanciare la coda su **Austen (305) → Whitman (738) → Poe (452) → Dickinson (538) →
   Bronte (745)**. Bronte è il palo più lungo e ha anche 362 dei 514 rifiuti scoperti:
   conviene tenerla per ultima ma non rimandarla oltre.
4. Dopo ogni autore chiuso: `assemble_aggregates.py` (senza `--force` va bene se le foglie
   sono fresche), poi **riemettere `translations_pages.jsonl`** — altrimenti nulla di tutto
   questo arriva sul sito.
5. **Solo alla fine**, con Opus: Coleridge, Eliot, Auden.
6. In parallelo, quando c'è tempo di testa e non di macchina: #21 (40 320 link), #20, #19.

---

## 8. Mappa dei file

**Runner**
`run_queue_all.sh` (coda per autore) · `run_author_hy.py` (un autore, applica la regola
foglia) · `run_dickens_all.sh` · `run_dickens_hy.py` · `opus_atom.py` (singolo atomo con
Opus) · `retranslate_rejected.py`

**Assemblaggio e riparazione**
`assemble_aggregates.py` · `handoff/force_reassemble.py` · `dickens_headings.py` (titoli
deterministici) · `repair_frontmatter.py` · `repair_hy_placeholders.py` ·
`repair_dickens_it_headings.py` · `dickens_relink.py` · `leafcheck.py` (`is_leaf`,
`walk_leaves` — importabile)

**Emissione verso il sito**
`gkc_prep.py`/`gkc_emit_vault.py` (Chesterton) · `fable_prep.py`/`fable_emit.py` (Sayers) ·
`shakespeare_emit_it.py` → tutto confluisce in `data/translations_pages.jsonl`, che
`preprocess.mjs` trasforma in pagine bilingui qlang (**non** in `.it.md`).

**Dati**
`data/translations_pages.jsonl` (il negozio pubblicato) · `data/*_cache.jsonl` (cache dei
blocchi — **gitignorate**, >100 MB, rigenerabili, viaggiano via Dropbox) ·
`data/*_linkfix.jsonl` · `data/{whitman,keats,dickinson}_cluster_map.json` ·
`data/work_titles.json` · `run_logs/authors_hy.log` · `run_logs/dickens_rejected.jsonl`

**Nota di igiene:** `notify_gas_mail.py` è ora in un repo **pubblico** e contiene un percorso
personale hardcoded più lo `SCRIPT_ID` dell'Apps Script. Nessun segreto vero (le credenziali
stanno in `GAS_DIR`, fuori dal repo), ma vale la pena decidere se lasciarlo lì.
