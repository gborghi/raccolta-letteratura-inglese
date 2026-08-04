#!/usr/bin/env python3
"""Tail the rescue/translation logs and e-mail (via wiligelmo-gas) per finished atom.

The rescue runners (retranslate_rejected.py) log one atom per attempt:

    07:41:30   atom Authors/Bronte/Atomized/Agnes_Grey/Chapter_01/part_04.md  (was: ...)
    07:43:02     -> FIXED via HY retry #1

This follows those logs and sends one mail for every `-> FIXED` / `-> UNRESOLVED`
outcome, so the mail arrives without an MCP client in the loop. Byte offsets are
persisted so a restart doesn't re-send anything already notified.

stdlib only (runs under /usr/bin/python3 3.9.6). Mail is best-effort: a failed
send is logged and skipped, never retried into a loop and never fatal.

Usage:  atom_mail_tailer.py --glob 'run_logs/rescue_*.log' [--to a@b.com]
                            [--every 1] [--poll 20]
        --every N  mail only every Nth finished atom (1 = every atom)
"""
import argparse
import glob as globmod
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from notify_gas_mail import send  # noqa: E402

STATE = os.path.join(HERE, "run_logs", "atom_mail_state.json")

ATOM_RE = re.compile(r"^\d\d:\d\d:\d\d\s+atom (Authors/\S+?\.md)\s*(?:\(was: (.*)\))?")
DONE_RE = re.compile(r"^\d\d:\d\d:\d\d\s+-> (FIXED|UNRESOLVED)[: ]\s*(.*)")

# The ordinary queue (run_dickens_hy via run_author_hy) reports each atom on ONE line instead of
# the rescue driver's two, so it needs its own patterns: an atom is announced and resolved at once.
QUEUE_OK_RE = re.compile(r"^\[(\d+)/(\d+)\]\s+ok (Authors/\S+?\.md)\s*(?:\|\s*(.*))?")
QUEUE_BAD_RE = re.compile(r"^(REJECT|FAIL) (Authors/\S+?\.md):\s*(.*)")


def log(m):
    print(time.strftime("%H:%M:%S"), m, flush=True)


def load_state():
    try:
        return json.load(open(STATE, encoding="utf-8"))
    except Exception:
        return {"offsets": {}, "sent": 0, "fixed": 0, "unresolved": 0}


def save_state(st):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    tmp = STATE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(st, fh)
    os.replace(tmp, STATE)


def mail(to, rel, outcome, detail, was, st):
    short = rel[len("Authors/"):-3] if rel.startswith("Authors/") else rel
    subject = "[EN>IT] %s %s" % (outcome, short)
    body = (
        "Atomo:      %s\n"
        "Esito:      %s\n"
        "Dettaglio:  %s\n"
        "Problema originale: %s\n"
        "\n"
        "Totale finora: %d tradotti, %d irrisolti.\n"
        % (rel, outcome, detail or "-", was or "-", st["fixed"], st["unresolved"])
    )
    try:
        send(to, subject, body)
        st["sent"] += 1
        return True
    except Exception as e:
        log("mail FAILED for %s: %s" % (rel, e))
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--glob", default=os.path.join(HERE, "run_logs", "rescue_*.log"))
    ap.add_argument("--to", default=os.environ.get("DICKENS_WATCH_TO", "gio.borghi@gmail.com"))
    ap.add_argument("--every", type=int, default=1)
    ap.add_argument("--poll", type=int, default=20)
    args = ap.parse_args()

    st = load_state()
    pending_atom = {}   # path -> (rel, was) of the atom currently being worked
    seen = 0
    log("### atom mail tailer | glob=%s to=%s every=%d" % (args.glob, args.to, args.every))

    while True:
        for path in sorted(globmod.glob(args.glob)):
            off = st["offsets"].get(path, 0)
            try:
                size = os.path.getsize(path)
            except OSError:
                continue
            if size < off:          # truncated/rotated: start over
                off = 0
            if size == off:
                continue
            with open(path, encoding="utf-8", errors="replace") as fh:
                fh.seek(off)
                for line in fh:
                    if not line.endswith("\n"):     # partial last line: leave it
                        break
                    off += len(line.encode("utf-8"))
                    line = line.rstrip("\n")
                    m = ATOM_RE.match(line.strip()) or ATOM_RE.match(line)
                    if m:
                        pending_atom[path] = (m.group(1), (m.group(2) or "").strip())
                        continue
                    q = QUEUE_OK_RE.match(line.strip())
                    if q:
                        st["fixed"] += 1
                        seen += 1
                        if seen % args.every == 0:
                            mail(args.to, q.group(3), "TRADOTTO",
                                 "%s (%s/%s dell'autore)" % (q.group(4) or "-",
                                                             q.group(1), q.group(2)),
                                 "", st)
                        save_state(st)
                        continue
                    q = QUEUE_BAD_RE.match(line.strip())
                    if q:
                        st["unresolved"] += 1
                        seen += 1
                        if seen % args.every == 0:
                            mail(args.to, q.group(2), q.group(1), q.group(3), "", st)
                        save_state(st)
                        continue
                    d = DONE_RE.match(line.strip())
                    if not d:
                        continue
                    outcome, detail = d.group(1), d.group(2).strip()
                    rel, was = pending_atom.pop(path, ("(sconosciuto)", ""))
                    if outcome == "FIXED":
                        st["fixed"] += 1
                    else:
                        st["unresolved"] += 1
                    seen += 1
                    if args.every <= 1 or seen % args.every == 0:
                        mail(args.to, rel, outcome, detail, was, st)
                st["offsets"][path] = off
            save_state(st)
        time.sleep(args.poll)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(0)
