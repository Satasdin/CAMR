#!/bin/sh
# The agent use case on the three proof lives (seed 1): every quiz question as an errand with tools, on the last day,
# for the 1.7B alone, the old CAMR and camr. Run it detached:  nohup caffeinate -i scripts/errands.sh >> work/errands.log 2>&1 &
set -e
cd "$(dirname "$0")/.."
for persona in student farmer developer; do
  for contender in bare camr camr; do
    .venv/bin/python -I -m camr_engine.ruler errands --persona "$persona" --seed 1 --contender "$contender" 2>&1 | grep -v -i warning
  done
done
echo "errands finished $(date)"
