#!/bin/sh
# The 27B on this machine (Qwen3.8-27B-4bit, 16 GB) on the three held-out lives: alone, with CAMR v1, and reading
# CAMR v2's memory as words (its hybrid layers can't use the saved notes). The quiz is asked at week 12 only, the
# week every table compares, then the errands. The app is stopped first: the 27B needs the RAM.
#   nohup caffeinate -i scripts/big27b.sh >> work/big27b.log 2>&1 &
set -e
cd "$(dirname "$0")/.."
while ! grep -q "downloaded to" work/download-27b.log 2>/dev/null; do sleep 30; done
pkill -f "engram.app" || true
echo "--- starting $(date), load $(sysctl -n vm.loadavg)"
for persona in student farmer developer; do
  for c in bare-27b camr-27b camr2-words-27b; do
    .venv/bin/python -I -m engram.ruler run --persona "$persona" --seed 1 --contender "$c" --quiz-weeks 12 2>&1 | grep -v -i warning
  done
  for c in bare camr camr2-words; do
    .venv/bin/python -I -m engram.ruler errands --persona "$persona" --seed 1 --contender "$c" --reader 27b 2>&1 | grep -v -i warning
  done
done
echo "27b finished $(date)"
