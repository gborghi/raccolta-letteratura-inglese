#!/usr/bin/env bash
# Self-standing runner for the remaining opus-filter-blocked Chesterton atoms (Tower 72B).
# Same shape as run_great_expectations.sh: survives SSH disconnect + Claude exit (nohup + disown),
# keeps the Mac awake (caffeinate), self-heals the model, fully resumable (skips existing .it.md,
# caches every block). Translation ONLY -- no deploy.
#
# Launch:  nohup bash run_chesterton_pending.sh </dev/null >/dev/null 2>&1 & disown
# Watch:   tail -f run_logs/chesterton_pending.log
# Done:    run_logs/chesterton_pending.DONE appears
set -u
cd "$(dirname "$0")"
export PATH="$HOME/.lmstudio/bin:$PATH"

RUNDIR="run_logs"
mkdir -p "$RUNDIR"
LOG="$RUNDIR/chesterton_pending.log"
DONE="$RUNDIR/chesterton_pending.DONE"
PIDFILE="$RUNDIR/chesterton_pending.pid"
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
/usr/bin/caffeinate -i -s python3 run_tower_pending.py >>"$LOG" 2>&1
rc=$?
log "=== translation finished (exit $rc) ==="

# 3. Completion marker (count TSV atoms that now have an .it.md).
done_n=$(python3 - <<'PY'
import os,csv
ROOT=os.path.abspath(os.path.join(os.path.dirname(__file__) if '__file__' in dir() else '.','..','..'))
V=os.path.abspath(os.path.join('..','..','..','VaultEnglish'))
rows=list(csv.DictReader(open(os.path.join('..','..','data','chesterton_tower_pending.tsv'),encoding='utf-8'),delimiter='\t'))
n=sum(1 for r in rows if os.path.exists(os.path.join(V,r['vault_en_path'][:-3]+'.it.md')))
print(f"{n}/{len(rows)}")
PY
)
{
  echo "exit_code=$rc"
  echo "finished=$(date '+%Y-%m-%d %H:%M:%S')"
  echo "atoms_translated=${done_n}"
} > "$DONE"
log "=== launcher done -> $DONE written (${done_n}) ==="
