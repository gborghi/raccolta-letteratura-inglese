# -*- coding: utf-8 -*-
"""Watch the EN->IT translation of several authors and e-mail (via wiligelmo-gas)
each time a WORK completes, each time an AUTHOR completes, and once when the whole
set is done.

Authors watched (in the order the pipeline processes them): Dickens, then Belloc,
Conan_Doyle, Bronte, Austen. A work is complete when every leaf atom under it has
an .it.md sibling (same leaf rule as run_author_hy). Works/authors already
complete at startup are baselined (no mail); only ones finishing DURING the watch
notify. Every poll also runs the reject rescue (HY retry -> Opus-5) and alerts
about atoms nothing could translate -- so a dropped atom never silently pins a
work. State in run_logs, resumable, best-effort mail, detached, stdlib only.

Env: DICKENS_WATCH_TO, DICKENS_WATCH_POLL.
"""
import os, sys, time, json, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from notify_gas_mail import send

AUTHORS = ["Dickens", "Belloc", "Conan_Doyle", "Bronte", "Austen"]
AROOT = ("/Users/g.borghi/Library/CloudStorage/Dropbox/insegnamento/Wiligelmo/"
         "SubjectBrain/English/VaultEnglish/Authors")
TO = os.environ.get("DICKENS_WATCH_TO", "gio.borghi@gmail.com")
POLL = int(os.environ.get("DICKENS_WATCH_POLL", "300"))
STATE = os.path.join(HERE, "run_logs", "dickens_watch_state.json")       # works notified
ADONE = os.path.join(HERE, "run_logs", "dickens_authors_done.json")      # authors notified
GRAND = os.path.join(HERE, "run_logs", "dickens_grand_done.flag")        # final sent
ALERTED = os.path.join(HERE, "run_logs", "dickens_alerted.json")
UNRESOLVED = os.path.join(HERE, "run_logs", "dickens_unresolved.jsonl")
RESCUE = os.path.join(HERE, "retranslate_rejected.py")


def log(m):
    print(time.strftime("%H:%M:%S"), m, flush=True)


def is_leaf_atom(root, f):
    """Leaf translation target: a .md that is not an aggregate (folder-name.md or
    a chapter split into a same-named subfolder) and not under a *_raw dir."""
    if not f.endswith(".md") or f.endswith(".it.md"):
        return False
    parts = root.split(os.sep)
    if any(p.startswith("_") or p.endswith("_raw") for p in parts):
        return False
    stem = f[:-3]
    if stem == os.path.basename(root):
        return False
    if os.path.isdir(os.path.join(root, stem)):
        return False
    return True


def run_fixes(key):
    """On a completed work: strip HY ellipses (global sweep) + reattach lost
    wikilinks when a matching *_atoms.tsv exists (Dickens works have one; other
    authors rely on the inline link handling). Idempotent, best-effort."""
    work = key.split("/", 1)[1] if "/" in key else key
    tsv = os.path.join(HERE, work.lower() + "_atoms.tsv")
    try:
        subprocess.run([sys.executable, os.path.join(HERE, "fix_dickens_it.py"),
                        "--apply"], timeout=600, capture_output=True)
        if os.path.exists(tsv):
            r = subprocess.run([sys.executable,
                                os.path.join(SCRIPTS, "repair_dickens_links.py"),
                                "--apply", tsv], timeout=1200, capture_output=True, text=True)
            fixed = [l for l in r.stdout.splitlines() if "wrapped" in l]
            log(f"  fixes su {key}: {fixed[0].strip() if fixed else 'ok'}")
    except Exception as e:
        log(f"  fixes FAILED su {key}: {e}")


def rescue_and_alert(alerted):
    """Auto-repair rejected atoms (HY retry -> Opus-5) and e-mail once about any
    the pipeline genuinely can't fix -- a silent REJECT becomes a fixed atom or a
    loud notification, never a stall nobody hears."""
    try:
        subprocess.run([sys.executable, RESCUE, "--skip-unresolved"],
                       timeout=3600, capture_output=True)
    except Exception as e:
        log(f"  rescue tool error: {e}")
    if not os.path.exists(UNRESOLVED):
        return
    new = []
    for line in open(UNRESOLVED, encoding="utf-8", errors="replace"):
        try:
            d = json.loads(line)
        except Exception:
            continue
        a = d.get("atom")
        if a and a not in alerted:
            new.append(d)
            alerted.add(a)
    if new:
        body = ("Questi atomi sono stati RIGETTATI dalla traduzione e ne' HY "
                "(con retry) ne' Opus-5 sono riusciti a produrne una versione "
                "valida. Vanno guardati a mano:\n\n"
                + "\n".join(f"- {d['atom']}\n    {d.get('problem', '')}" for d in new))
        try:
            send(TO, f"⚠ Traduzione: {len(new)} atomi NON risolti", body)
            log(f"  MAIL alert: {len(new)} atomi non risolti")
        except Exception as e:
            log(f"  alert mail FAILED (ritento): {e}")
            for d in new:
                alerted.discard(d.get("atom"))
        json.dump(sorted(alerted), open(ALERTED, "w"))


def book_stats():
    """{"Author/Work": (it_leaf, en_leaf)} over every watched author, counting
    only leaf atoms (same rule as the driver)."""
    stats = {}
    for author in AUTHORS:
        base = os.path.join(AROOT, author, "Atomized")
        if not os.path.isdir(base):
            continue
        for d in sorted(os.listdir(base)):
            p = os.path.join(base, d)
            if not os.path.isdir(p):
                continue
            en = it = 0
            for root, _dirs, files in os.walk(p):
                for f in files:
                    if is_leaf_atom(root, f):
                        en += 1
                        if os.path.exists(os.path.join(root, f[:-3] + ".it.md")):
                            it += 1
            if en > 0:
                stats[author + "/" + d] = (it, en)
    return stats


def done(v):
    it, en = v
    return en > 0 and it >= en


def author_done(stats, a):
    ks = [k for k in stats if k.startswith(a + "/")]
    return bool(ks) and all(done(stats[k]) for k in ks)


def overall(stats):
    it = sum(v[0] for v in stats.values())
    en = sum(v[1] for v in stats.values())
    return it, en, (100 * it // en if en else 0)


def main():
    stats = book_stats()
    notified = (set(json.load(open(STATE))) if os.path.exists(STATE)
                else {k for k, v in stats.items() if done(v)})
    json.dump(sorted(notified), open(STATE, "w"))
    authors_done = (set(json.load(open(ADONE))) if os.path.exists(ADONE)
                    else {a for a in AUTHORS if author_done(stats, a)})
    json.dump(sorted(authors_done), open(ADONE, "w"))
    alerted = set(json.load(open(ALERTED))) if os.path.exists(ALERTED) else set()
    grand = os.path.exists(GRAND)
    log(f"watcher up | autori {AUTHORS} | opere {len(stats)} | "
        f"baseline: opere complete {len(notified)}, autori completi {len(authors_done)}")

    while True:
        rescue_and_alert(alerted)
        stats = book_stats()
        it, en, pct = overall(stats)

        # per-work completion
        for k in sorted(stats):
            if done(stats[k]) and k not in notified:
                author, work = k.split("/", 1)
                nice = work.replace("_", " ")
                nwork = sum(1 for x in stats if done(stats[x]))
                body = (f"«{nice}» ({author}) e' stata tradotta ({stats[k][0]} atomi).\n\n"
                        f"Avanzamento English complessivo: {it}/{en} atomi ({pct}%).\n"
                        f"Opere completate: {nwork}/{len(stats)}.")
                run_fixes(k)
                try:
                    send(TO, f"{author}: completata «{nice}»", body)
                    notified.add(k)
                    json.dump(sorted(notified), open(STATE, "w"))
                    log(f"MAIL opera completata: {k}")
                except Exception as e:
                    log(f"mail FAILED for {k} (ritento): {e}")

        # per-author completion
        for a in AUTHORS:
            if a not in authors_done and author_done(stats, a):
                try:
                    send(TO, f"✅ {a} COMPLETO",
                         f"Tutte le opere di {a} sono state tradotte EN->IT.\n\n"
                         f"Avanzamento English complessivo: {it}/{en} atomi ({pct}%).")
                    authors_done.add(a)
                    json.dump(sorted(authors_done), open(ADONE, "w"))
                    log(f"MAIL autore completato: {a}")
                except Exception as e:
                    log(f"mail autore FAILED {a} (ritento): {e}")

        # grand final (once) -- watcher keeps running in case more work is queued
        if not grand and stats and all(done(v) for v in stats.values()):
            try:
                send(TO, "🎉 Traduzione English COMPLETA",
                     f"Tutti gli autori seguiti sono tradotti EN->IT.\n\n"
                     f"Totale: {it}/{en} atomi ({pct}%). Opere: {len(stats)}.")
                open(GRAND, "w").write("done")
                grand = True
                log("MAIL FINALE inviata: English completo")
            except Exception as e:
                log(f"mail finale FAILED (ritento): {e}")

        time.sleep(POLL)


if __name__ == "__main__":
    main()
