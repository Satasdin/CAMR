#!/bin/zsh
# phase2b: CAMR Personal with whole notes at 512 tokens and the tightened profile extractor.
setopt pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH=$PWD CAMR_BENCH_TMP=~/.cache/camr-bench/tmp-p2b CAMR_BENCH_STORES=~/.cache/camr-bench/stores-p2b
PY=${PY:-python}
mkdir -p $CAMR_BENCH_TMP
F=(grep --line-buffered -E "wrote|scale [0-9]+[kM]: \{|Traceback|Error|error|Killed")
for n in 1000 10000 100000; do
  echo "BUILD $n $(date +%H:%M:%S)"
  $PY -u scripts/engine_bench.py scale --notes $n --phase build --out $CAMR_BENCH_TMP/build-$n.json 2>&1 | grep -E "Traceback|Error" || true
done
export CAMR_BENCH_OUT=$PWD/results/bench/phase2/phase2b
echo "RUN camr,a8,lme $(date +%H:%M:%S)"
$PY -u scripts/engine_bench.py run --only camr,a8,lme --fresh 2>&1 | $F || true
echo "CONTEXTS $(date +%H:%M:%S)"
CAMR_BENCH_OUT=$PWD/results/bench $PY -u scripts/engine_bench.py contexts --label phase2b 2>&1 | $F || true
echo "SCALE QUERY $(date +%H:%M:%S) load: $(uptime | sed 's/.*averages: //')"
$PY -u scripts/engine_bench.py run --only scale 2>&1 | $F || true
$PY -u scripts/engine_bench.py report 2>&1 | $F || true
echo "PHASE2B DONE $(date +%H:%M:%S)"
