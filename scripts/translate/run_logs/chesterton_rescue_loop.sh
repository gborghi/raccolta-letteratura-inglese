#!/bin/bash
# Rincorre i reject di Chesterton finche' il run principale (run_author_hy Chesterton)
# e' vivo, poi fa un passaggio finale. Opus+masking diretto: i reject sono tutti
# "leftover mask token(s)", cioe' il modo in cui HY fallisce -- ritentare HY
# riproduce lo stesso errore e contende il server locale al run principale.
cd "$(dirname "$0")/.."
D="$(pwd)"
pass=0
while true; do
  alive=$(pgrep -f "run_author_hy.py Chesterton" | head -1)
  pass=$((pass+1))
  echo "=== PASS $pass $(date +%H:%M) | run principale: ${alive:-finito} ==="
  for i in 0 1 2 3; do
    DICKENS_UNRESOLVED="$D/run_logs/chesterton_unresolved_$i.jsonl" \
      python3 retranslate_rejected.py --book Chesterton --hy-tries 0 --shard $i/4 \
      >> "$D/run_logs/rescue_chesterton_$i.log" 2>&1 &
  done
  wait
  echo "--- pass $pass finito $(date +%H:%M) ---"
  [ -z "$alive" ] && { echo "=== run principale finito, passaggio finale completato ==="; break; }
  sleep 120
done
