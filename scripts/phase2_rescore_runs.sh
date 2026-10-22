#!/bin/zsh
# Re-score LongMemEval with the answer-survives rule: one run per configuration, two at a time.
setopt pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH=$PWD CAMR_BENCH_STORES=~/.cache/camr-bench/stores-p2
PY=${PY:-python}
OFF='"dated_context": false, "time_filter": false, "entity_gate_skip_time": false, "profile": false, "aggregate": false, "slot_gate": false, "compress": "none"'
one() {  # name flags
  CAMR_BENCH_TMP=~/.cache/camr-bench/tmp-rs-$1 CAMR_BENCH_OUT=$PWD/results/bench/phase2/rescore/$1 \
    $PY -u scripts/engine_bench.py run --only lme --fresh --flags "$2" 2>&1 | grep -E "Traceback|Error" || true
  echo "RESCORE $1 done $(date +%H:%M:%S)"
}
one baseline "{$OFF}" &
one step3-aggregate "{$OFF, \"dated_context\": true, \"time_filter\": true, \"profile\": true, \"entity_gate_skip_time\": true, \"aggregate\": true}" &
wait
one compress-384 '{"slot_gate": false, "compress": "sentences"}' &
one budget-512 '{"slot_gate": false, "compress": "none", "token_budget": 512}' &
wait
one compress-512 '{"slot_gate": false, "compress": "sentences", "token_budget": 512}' &
one budget-768 '{"slot_gate": false, "compress": "none", "token_budget": 768}' &
wait
one final '{}'
echo "RESCORE ALL DONE"
