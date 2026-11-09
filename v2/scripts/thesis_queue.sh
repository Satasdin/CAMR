#!/bin/zsh
# The E-74 benchmarks, one after another, from a frozen copy of the engine. A step that fails is logged and the next runs.
ROOT=${0:A:h:h:h}
WT=$ROOT
FROZEN=$WT/work/thesis/frozen
PY=$WT/v2/.venv/bin/python
HAUL=$WT/work/haul/s4-16m
MEM=$WT/work/memories/s4-4b
R=$WT/v2/records/thesis
LOG=$WT/work/thesis/queue.log
APP="closest=6,finder=words,asleep=lines,read=lines,follow=3,hop=2"
BASE="camr:$APP"
export PYTHONPATH=$FROZEN HF_HUB_OFFLINE=1
cd $FROZEN
pause() { $PY -c "import time; time.sleep($1)"; }
say() { echo "$(date '+%H:%M:%S') $*" >> $LOG; }
run() { local name=$1; shift; say "START $name"; "$@" >> $WT/work/thesis/$name.log 2>&1; say "END $name exit $?"; }
desk() { local name=$1 cut=$2 per=$3; shift 3; local args=(); for v in "$@"; do args+=(--variant "$v"); done
  run $name $PY -m camr_engine.bench.desk --memory $MEM/$cut.nosync --haul $HAUL --cut $cut --per-family $per --records $R "${args[@]}"; }

say "queue started; waiting for the 16M memory"
for i in {1..2000}; do grep -q '^16M ' $WT/work/thesis/ingest.log && break; pause 30; done
pause 30

# A: growth
for c in 64K 256K 1M 2M 4M 8M 16M; do desk A-$c $c 10 "$BASE"; done
# C: knowledge against reasoning
for c in 1M 4M 16M; do desk C-$c $c 50 "$BASE" "rag:k=8,budget=1536,finder=words"; done
run C-bare $PY scripts/thesis_bench.py bare --haul $HAUL --records $R --work $WT/work/thesis/bare --cuts 1M 4M 16M --per-family 50
# D: how much to read
for n in 0 1 2 4 6 8 12 16; do desk D-$n 4M 30 "camr:${APP/closest=6/closest=$n}"; done
# E: what each part adds
desk E-noroom 4M 30 "camr:${APP/asleep=lines/asleep=skip}"
desk E-nohop 4M 30 "camr:${APP/hop=2/hop=0}"
desk E-noreplies 4M 30 "camr:${APP/follow=3/follow=0}"
desk E-whole 4M 30 "camr:${${APP/asleep=lines/asleep=words}/read=lines/read=moments}"
desk E-dense 4M 30 "camr:${APP/finder=words/finder=dense}"
desk E-newest 4M 30 "$BASE,latest=1"
desk E-adapter 4M 30 "$BASE,adapter=reading-v1"
for m in qwen3-1.7b qwen3-8b; do
  run E-tell-$m $PY scripts/dev_ingest.py --dir $HAUL --model $m --cuts 4M --out $WT/work/memories/s4-$m --notes hot --disk-gb 1
  run E-read-$m $PY -m camr_engine.bench.desk --model $m --memory $WT/work/memories/s4-$m/4M.nosync --haul $HAUL --cut 4M --per-family 30 --records $R --variant "$BASE"
done
run E-notes $PY -m camr_engine.bench.local longhaul --contender engine:qwen3-4b --contender words:qwen3-4b --dir $HAUL --cuts 256K --memories $WT/work/thesis/notes-words --records $R
# C: Claude, with the money approved for it
run C-window $PY scripts/thesis_bench.py window --haul $HAUL --records $R --cuts 1M 4M --per-family 10
for c in 16M 4M 1M; do run C-ctx-$c $PY scripts/thesis_bench.py ctx --haul $HAUL --records $R --memory $MEM/$c.nosync --cut $c --per-family 50; done
# B: the long sitting
run B-soak $PY scripts/thesis_bench.py soak --haul $HAUL --records $R --memory $MEM/4M.nosync --cut 4M --work $WT/work/thesis/soak --minutes 120
# F and G
run F-keeping $PY scripts/thesis_workflows.py keeping --records $R --work $WT/work/thesis/scratch
run G-workflows $PY scripts/thesis_workflows.py workflows --records $R --work $WT/work/thesis/scratch
say "queue finished"
