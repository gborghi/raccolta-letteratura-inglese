#!/bin/bash
# Chain the HY translation: wait for the running Dickens run to finish, then
# translate Belloc -> Conan_Doyle -> Bronte -> Austen, in that order, one after
# the other. Each author reuses the exact HY pipeline (retry + reject-recording;
# the watcher does the Opus rescue + per-work e-mail).
#
# Detached by design: launch with nohup so it outlives the SSH session, e.g.
#   nohup ./run_after_dickens.sh <dickens_pid> >> run_logs/authors_orch.log 2>&1 &
#   disown
#
# $1 = pid of the currently-running run_dickens_hy.py (optional; if omitted or
#      already gone, the authors start immediately).
cd "$(dirname "$0")" || exit 1
LOG="run_logs/authors_hy.log"
mkdir -p run_logs
DICKPID="${1:-}"
AUTHORS=(Belloc Conan_Doyle Bronte Austen)
PY="${PY:-/usr/bin/python3}"        # match the running Dickens process (3.9.6)

ts() { date '+%F %T'; }
echo "$(ts) [orch] up | pid=$$ | dickens_pid=${DICKPID:-none} | authors=${AUTHORS[*]}" >> "$LOG"

# Wait for the Dickens run to end (match the cmdline so a reused PID doesn't fool us).
if [ -n "$DICKPID" ]; then
  while ps -p "$DICKPID" -o command= 2>/dev/null | grep -q "run_dickens_hy"; do
    sleep 60
  done
fi
echo "$(ts) [orch] Dickens run finished -> starting authors" >> "$LOG"

for A in "${AUTHORS[@]}"; do
  echo "$(ts) [orch] === START $A ===" >> "$LOG"
  HY_WORKERS="${HY_WORKERS:-4}" "$PY" run_author_hy.py "$A" >> "$LOG" 2>&1
  rc=$?
  echo "$(ts) [orch] === END $A (rc=$rc) ===" >> "$LOG"
done

echo "$(ts) [orch] ALL AUTHORS DONE (Belloc, Conan_Doyle, Bronte, Austen)" >> "$LOG"
