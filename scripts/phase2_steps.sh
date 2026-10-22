#!/bin/zsh
# Phase 2 bench, one change at a time (flags over CAMR Personal's config, which has every Phase 2 flag on).
#   scripts/phase2_steps.sh stores step0 step1 step2 step3 b512 b768 c384 c512 final contexts k60
#   python scripts/phase2_compare.py      # -> results/bench/phase2/README.md
setopt pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH=$PWD CAMR_BENCH_TMP=~/.cache/camr-bench/tmp-p2 CAMR_BENCH_STORES=~/.cache/camr-bench/stores-p2
PY=${PY:-python}
OFF='"dated_context": false, "time_filter": false, "entity_gate_skip_time": false, "profile": false, "aggregate": false, "slot_gate": false'
run_step() {  # name flags-json
  export CAMR_BENCH_OUT=$PWD/results/bench/phase2/$1
  echo "STEP $1 start $(date +%H:%M:%S) flags $2"
  $PY -u scripts/engine_bench.py run --only camr,a8,lme,scale --flags "$2" 2>&1 | grep --line-buffered -E "scale [0-9]+k: \{|Traceback|Error|error|Killed" || true
  $PY -u scripts/engine_bench.py report 2>&1 | grep -E "wrote|Traceback|Error" || true
  echo "STEP $1 done $(date +%H:%M:%S)"
}
for s in "$@"; do
  case $s in
    stores)  # the needle stores as CAMR Personal now writes them (profile notes on); every step then only queries
      for n in 1000 10000 100000; do
        echo "BUILD $n $(date +%H:%M:%S)"
        $PY -u scripts/engine_bench.py scale --notes $n --phase build --out ~/.cache/camr-bench/tmp-p2/build-$n.json 2>&1 | grep -E "Traceback|Error|short of" || true
        cat ~/.cache/camr-bench/tmp-p2/build-$n.json; echo
      done ;;
    step0) run_step step0-before "{$OFF}" ;;
    step1) run_step step1-dates "{$OFF, \"dated_context\": true, \"time_filter\": true}" ;;
    step2) run_step step2-profile "{$OFF, \"dated_context\": true, \"time_filter\": true, \"profile\": true, \"entity_gate_skip_time\": true}" ;;
    step3) run_step step3-aggregate "{$OFF, \"dated_context\": true, \"time_filter\": true, \"profile\": true, \"entity_gate_skip_time\": true, \"aggregate\": true}" ;;
    final) run_step step5-final "{}" ;;
    contexts)  # the exact contexts of the Phase 2 read path, for the reader bench
      CAMR_BENCH_OUT=$PWD/results/bench $PY -u scripts/engine_bench.py contexts --label phase2 2>&1 | grep -E "wrote|Traceback|Error" || true ;;
    k60)  # 60-token chunks on a stratified slice (new vectors needed); compared with step 3 on the same slice
      export CAMR_BENCH_QIDS=$(cat results/bench/phase2/chunk60-qids.txt)
      K60='{"slot_gate": false, "compress": "none", "chunk_tokens": 60}'
      echo "EMBED k60 $(date +%H:%M:%S)"
      $PY -u scripts/engine_bench.py embed --scales 1000 --flags "$K60" 2>&1 | grep -E "done:|Traceback|Error" || true
      export CAMR_BENCH_OUT=$PWD/results/bench/phase2/chunk60-384
      $PY -u scripts/engine_bench.py run --only lme --fresh --flags "$K60" 2>&1 | grep -E "Traceback|Error" || true
      unset CAMR_BENCH_QIDS
      echo "STEP chunk60-384 done $(date +%H:%M:%S)" ;;
    b512) run_step budget-512 "{\"slot_gate\": false, \"token_budget\": 512}" ;;
    b768) run_step budget-768 "{\"slot_gate\": false, \"token_budget\": 768}" ;;
    c384) run_step compress-384 "{\"slot_gate\": false, \"compress\": \"sentences\"}" ;;
    c512) run_step compress-512 "{\"slot_gate\": false, \"compress\": \"sentences\", \"token_budget\": 512}" ;;
  esac
done
echo "ALL STEPS EXIT $?"
