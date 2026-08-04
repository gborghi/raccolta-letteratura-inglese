#!/bin/bash
# Ordinary EN->IT queue: every author's pending LEAF atoms, one author at a time.
#
# Only leaves are translated here (run_author_hy.py enforces that): the aggregate
# Work/Work.md and Chapter_NN.md files are NOT translated, they are concatenated
# from the leaves afterwards by assemble_aggregates.py.
#
# Hemingway is deliberately absent: EXCLUDE_AUTHORS drops him from the published
# site for copyright, so translating him would be work no reader can ever see.
#
# Authors are ordered biggest-backlog-first, so the long pole starts immediately.
# Pass authors as arguments to override the order (used to close nearly-finished
# authors first). Prose goes through HY here; POETRY does NOT -- Dickinson and
# Keats are translated with Opus, so keep them out of the argument list.
#
#   nohup ./run_queue_all.sh >> run_logs/queue_all.log 2>&1 &
#   nohup ./run_queue_all.sh Conan_Doyle Dickens Belloc >> ... &
#
cd "$(dirname "$0")" || exit 1
LOG="run_logs/authors_hy.log"
mkdir -p run_logs
AUTHORS=(Conan_Doyle Bronte Poe Austen Whitman Wilde Dickinson Chesterton Dickens Belloc Sayers)
[ $# -gt 0 ] && AUTHORS=("$@")
PY="${PY:-/usr/bin/python3}"

ts() { date '+%F %T'; }
echo "$(ts) [queue] up | pid=$$ | authors=${AUTHORS[*]}" >> "$LOG"

for A in "${AUTHORS[@]}"; do
  echo "$(ts) [queue] === START $A ===" >> "$LOG"
  HY_WORKERS="${HY_WORKERS:-4}" "$PY" run_author_hy.py "$A" >> "$LOG" 2>&1
  echo "$(ts) [queue] === END $A (rc=$?) ===" >> "$LOG"
done

echo "$(ts) [queue] ALL AUTHORS DONE" >> "$LOG"
