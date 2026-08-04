#!/usr/bin/env bash
# Self-standing Great Expectations translation runner (Tower 72B).
# Same shape as run_oliver_twist.sh: survives SSH disconnect + Claude exit (nohup + disown),
# keeps the Mac awake (caffeinate), self-heals the model, fully resumable (skips existing .it.md,
# caches every block). Translation ONLY -- no deploy.
#
# Launch:  nohup bash run_great_expectations.sh </dev/null >/dev/null 2>&1 & disown
# Watch:   tail -f run_logs/great_expectations.log
# Done:    run_logs/great_expectations.DONE appears
set -u
cd "$(dirname "$0")"
export PATH="$HOME/.lmstudio/bin:$PATH"

RUNDIR="run_logs"
mkdir -p "$RUNDIR"
LOG="$RUNDIR/great_expectations.log"
DONE="$RUNDIR/great_expectations.DONE"
PIDFILE="$RUNDIR/great_expectations.pid"
rm -f "$DONE"
echo $$ > "$PIDFILE"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG"; }

log "=== launcher start (pid $$) ==="

# 1. Ensure the LM Studio server is up and Tower 72B is loaded lean.
lms server start >>"$LOG" 2>&1 || true
if ! lms ps 2>/dev/null | grep -q "tower-plus-72b"; then
  log "model not resident -> loading Tower 72B lean"
  lms load tower-plus-72b --context-length 8192 --parallel 1 --gpu max \
      --identifier tower-plus-72b -y >>"$LOG" 2>&1
fi

# 2. Translate. caffeinate -i -s prevents idle + system sleep for the run's lifetime.
log "=== translation start ==="
/usr/bin/caffeinate -i -s python3 run_ge_tower.py >>"$LOG" 2>&1
rc=$?
log "=== translation finished (exit $rc) ==="

# 3. Completion marker.
{
  echo "exit_code=$rc"
  echo "finished=$(date '+%Y-%m-%d %H:%M:%S')"
  echo "atoms_translated=$(find ../../../VaultEnglish/Authors/Dickens/Atomized/Great_Expectations -name '*.it.md' | wc -l | tr -d ' ')/167"
} > "$DONE"
log "=== launcher done -> $DONE written ==="
