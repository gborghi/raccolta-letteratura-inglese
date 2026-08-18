#!/usr/bin/env bash
# Self-standing Dickens catalogue runner (Tower 72B) -- translates the remaining Dickens works
# ONE BOOK AT A TIME, in a fixed order, unattended. Same hardening as run_great_expectations.sh:
# survives SSH disconnect + Claude exit (nohup + disown), keeps the Mac awake (caffeinate),
# self-heals the model (reloads Tower 72B lean if LM Studio dropped it), fully resumable
# (dickens_tower.py skips atoms with an existing .it.md and caches every block; a finished book is
# skipped instantly). Translation ONLY -- no preprocess, no build, no deploy, no commit.
#
# Order rationale: A Christmas Carol first (small + iconic) de-risks the fresh-book machinery in
# ~20 min; then the major novels; then the remaining Christmas books, minor novels and non-fiction.
# Great_Expectations and Oliver_Twist are already complete and intentionally absent.
#
# Per Tower FAIL/REJECT: the atom is simply left without an .it.md (the run moves on). Those
# residuals are mopped up SEPARATELY and interactively -- Opus with masking/unmasking of any
# guard-triggering terms -- exactly as was done for Great Expectations. This script never blocks on
# them.
#
# Launch:  nohup bash run_dickens_all.sh </dev/null >/dev/null 2>&1 & disown
# Watch:   tail -f run_logs/dickens_all.log
# Done:    run_logs/dickens_all.DONE appears (whole catalogue swept once)
set -u
cd "$(dirname "$0")"
export PATH="$HOME/.lmstudio/bin:$PATH"

RUNDIR="run_logs"
mkdir -p "$RUNDIR"
LOG="$RUNDIR/dickens_all.log"
DONE="$RUNDIR/dickens_all.DONE"
PIDFILE="$RUNDIR/dickens_all.pid"
rm -f "$DONE"
echo $$ > "$PIDFILE"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG"; }

# --- Model backend: local MLX (mixed 4/6-bit Tower 72B) via mlx_lm.server ---------------------
# Replaces the old LM Studio GGUF path. The mixed46 MLX model is ~1.4x faster (7.2 vs 5.1 tok/s)
# at GGUF-equivalent quality. dickens_tower.py talks OpenAI-style to LMSTUDIO_HOST/TOWER_MODEL.
MLX_MODEL="/Users/g.borghi/mlx-models/Tower-Plus-72B-mixed46"
MLX_PORT=8081
MLX_LOG="$RUNDIR/mlx_server.log"
export LMSTUDIO_HOST="http://localhost:$MLX_PORT"
export TOWER_MODEL="$MLX_MODEL"
export LOG RUNDIR MLX_MODEL MLX_PORT MLX_LOG   # so the caffeinate subshell's self-heal sees them

# Start (or revive) the MLX server and wait until it answers. Self-healing + idempotent: if it is
# already listening this returns immediately; if it crashed, it relaunches it detached.
ensure_mlx_server() {
  curl -s -m 4 "http://localhost:$MLX_PORT/v1/models" >/dev/null 2>&1 && return 0
  echo "[$(date '+%F %T')] mlx server down -> starting on :$MLX_PORT" >> "$LOG"
  nohup caffeinate -i uv run --with mlx-lm python -m mlx_lm.server \
      --model "$MLX_MODEL" --port "$MLX_PORT" >> "$MLX_LOG" 2>&1 &
  disown
  for _ in $(seq 1 72); do          # up to ~6 min for the 44G weights to become servable
    curl -s -m 4 "http://localhost:$MLX_PORT/v1/models" >/dev/null 2>&1 && { \
      echo "[$(date '+%F %T')] mlx server up" >> "$LOG"; return 0; }
    sleep 5
  done
  echo "[$(date '+%F %T')] mlx server FAILED to come up" >> "$LOG"; return 1
}
export -f ensure_mlx_server

# Fixed translation order (my chosen starting point = A_Christmas_Carol).
WORKS=(
  A_Christmas_Carol
  A_Tale_of_Two_Cities
  Hard_Times
  The_Chimes
  The_Cricket_on_the_Hearth
  The_Battle_of_Life
  The_Haunted_Man_and_the_Ghosts_Bargain
  The_Old_Curiosity_Shop
  Nicholas_Nickleby
  David_Copperfield
  Bleak_House
  Little_Dorrit
  Dombey_and_Son
  Our_Mutual_Friend
  Martin_Chuzzlewit
  Barnaby_Rudge
  The_Pickwick_Papers
  The_Mystery_of_Edwin_Drood
  Sketches_by_Boz
  American_Notes
  A_Childs_History_of_England
)

log "=== catalogue launcher start (pid $$) -- ${#WORKS[@]} works queued ==="

# Ensure the MLX server is up with Tower 72B (mixed46) loaded, ONCE up front.
ensure_mlx_server || { log "FATAL: MLX server would not start -> aborting"; exit 1; }

# One caffeinate wraps the WHOLE catalogue sweep (prevents idle + system sleep for its lifetime).
/usr/bin/caffeinate -i -s bash -c '
  set -u
  for W in '"${WORKS[*]}"'; do
    V="../../../VaultEnglish/Authors/Dickens/Atomized/$W"
    tsv="$(echo "$W" | tr "[:upper:]" "[:lower:]")_atoms.tsv"
    # Skip a book already fully translated (every TSV atom has an .it.md sibling).
    total=$(tail -n +2 "$tsv" | grep -c .)
    have=0
    while IFS= read -r p; do
      [ -z "$p" ] && continue
      [ -f "../../../VaultEnglish/${p%.md}.it.md" ] && have=$((have+1))
    done < <(tail -n +2 "$tsv")
    if [ "$have" -ge "$total" ]; then
      echo "[$(date "+%F %T")] === SKIP $W (already $have/$total) ===" >> "'"$LOG"'"
      continue
    fi
    echo "[$(date "+%F %T")] === BOOK START $W ($have/$total done) ===" >> "'"$LOG"'"
    # Self-heal the MLX server between books in case it crashed.
    ensure_mlx_server || { echo "[$(date "+%F %T")] mlx server dead, skipping $W" >> "'"$LOG"'"; continue; }
    DICKENS_WORK="$W" python3 run_dickens_book.py >> "'"$LOG"'" 2>&1
    rc=$?
    now_have=0
    while IFS= read -r p; do
      [ -z "$p" ] && continue
      [ -f "../../../VaultEnglish/${p%.md}.it.md" ] && now_have=$((now_have+1))
    done < <(tail -n +2 "$tsv")
    echo "[$(date "+%F %T")] === BOOK END $W (exit $rc, now $now_have/$total) ===" >> "'"$LOG"'"
    # Email notification at every BOOK END (shell-callable wiligelmo-gas Apps Script; best-effort).
    python3 notify_gas_mail.py --to gio.borghi@gmail.com \
      --subject "[Dickens] $W  $now_have/$total (exit $rc)" \
      --body "Libro terminato: $W
Atomi tradotti: $now_have/$total
Exit code run_dickens_book.py: $rc
Ora: $(date "+%F %T")" \
      >> "'"$LOG"'" 2>&1 \
      || echo "[$(date "+%F %T")] mail hook FAILED for $W" >> "'"$LOG"'"
  done
'

log "=== catalogue sweep finished ==="

# Completion marker: per-work tally of atoms translated.
{
  echo "finished=$(date '+%Y-%m-%d %H:%M:%S')"
  for W in "${WORKS[@]}"; do
    tsv="$(echo "$W" | tr '[:upper:]' '[:lower:]')_atoms.tsv"
    total=$(tail -n +2 "$tsv" | grep -c .)
    have=0
    while IFS= read -r p; do
      [ -z "$p" ] && continue
      [ -f "../../../VaultEnglish/${p%.md}.it.md" ] && have=$((have+1))
    done < <(tail -n +2 "$tsv")
    echo "$W=$have/$total"
  done
} > "$DONE"
log "=== catalogue launcher done -> $DONE written ==="

# Final summary email for the whole catalogue sweep (best-effort).
python3 notify_gas_mail.py --to gio.borghi@gmail.com \
  --subject "[Dickens] catalogue sweep FINISHED" \
  --body "$(cat "$DONE")" >> "$LOG" 2>&1 \
  || log "final summary mail hook FAILED"
