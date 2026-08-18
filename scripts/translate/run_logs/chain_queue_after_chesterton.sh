#!/bin/bash
# Aspetta la fine del run Chesterton fuori coda, poi riavvia la coda ordinaria.
#
# La coda copre da sola il backlog dei reject: gather_author() enumera ogni leaf
# che non ha ancora il suo .it.md, e un atomo rifiutato non ne ha scritto nessuno.
# Quindi i 1131 reject di Conan_Doyle/Bronte/Austen tornano in lavorazione con HY
# (locale, gratis) invece di costare 1131 chiamate Opus; l'Opus resta per chi
# fallisce di nuovo, via retranslate_rejected.py.
cd "$(dirname "$0")/.."
while pgrep -f "run_author_hy.py Chesterton" > /dev/null; do sleep 60; done
echo "$(date '+%F %T') [chain] Chesterton finito, riavvio la coda ordinaria"
nohup ./run_queue_all.sh >> run_logs/queue_all.log 2>&1 &
echo "$(date '+%F %T') [chain] coda ripartita pid $!"
