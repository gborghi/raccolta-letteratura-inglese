#!/usr/bin/env bash
# Self-standing Oliver Twist translation runner.
# Survives SSH disconnect and Claude Code exit (launched via nohup + disown),
# keeps the Mac awake for the whole run (caffeinate), self-heals the model
# (reloads Tower 72B lean if LM Studio dropped it), and is fully resumable
# (dickens_tower.py skips atoms with an existing .it.md and caches every block).
#
# Launch:  nohup bash run_oliver_twist.sh </dev/null >/dev/null 2>&1 & disown
# Watch:   tail -f run_logs/oliver_twist.log
# Done:    run_logs/oliver_twist.DONE appears (contains the final summary line)
set -u
cd "$(dirname "$0")"
export PATH="$HOME/.lmstudio/bin:$PATH"

RUNDIR="run_logs"
mkdir -p "$RUNDIR"
LOG="$RUNDIR/oliver_twist.log"
DONE="$RUNDIR/oliver_twist.DONE"
PIDFILE="$RUNDIR/oliver_twist.pid"
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
#    dickens_tower.py is resumable, so a mid-run kill loses at most the block in flight.
log "=== translation start ==="
/usr/bin/caffeinate -i -s python3 dickens_tower.py >>"$LOG" 2>&1
rc=$?
log "=== translation finished (exit $rc) ==="

# 3. Completion marker.
{
  echo "exit_code=$rc"
  echo "finished=$(date '+%Y-%m-%d %H:%M:%S')"
  echo "atoms_translated=$(find ../../../VaultEnglish/Authors/Dickens/Atomized/Oliver_Twist -name '*.it.md' | wc -l | tr -d ' ')/149"
} > "$DONE"
log "=== launcher done -> $DONE written ==="
