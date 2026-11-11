#!/bin/zsh
S=${0:a:h}
Q4=~/.ollama/models/blobs/sha256-85e4a5b7b8ef0e48af0e8658f5aaab9c2324c76c1641493f4d1e25fce54b18b9
Q17=~/.ollama/models/blobs/sha256-3d0b790534fe4b79525fc3692950408dca41171676ed7e21db57af5c65ef6ab6
run() {
  label=$1; shift
  pkill -f "llama-server.*--port 8091"; sleep 3
  llama-server -m $Q4 -a qwen3-4b-instruct --jinja -c 65536 -np 2 --port 8091 --slot-save-path $S/vault/.burrow/kv "$@" > $S/server-$label.log 2>&1 &
  for i in $(seq 1 90); do curl -s localhost:8091/health | grep -q ok && break; sleep 1; done
  python3 -I $S/bench.py 8091 $label $S/r-$label.json > $S/out-$label.txt 2>&1
  echo "done $label"
}
run baseline2
run ngram-simple --spec-type ngram-simple
run ngram-map-k --spec-type ngram-map-k
run ngram-mod --spec-type ngram-mod
run draft-1.7b --spec-type draft-simple -md $Q17 --spec-draft-n-max 8
run q8kv -fa on -ctk q8_0 -ctv q8_0
#!/bin/zsh
S=${0:a:h}
Q4=~/.ollama/models/blobs/sha256-85e4a5b7b8ef0e48af0e8658f5aaab9c2324c76c1641493f4d1e25fce54b18b9
run() {
  label=$1; benchflags=$2; shift 2
  pkill -f "llama-server.*--port 8091"; sleep 3
  llama-server -m $Q4 -a qwen3-4b-instruct --jinja -c 65536 -np 2 --port 8091 --slot-save-path $S/vault/.burrow/kv "$@" > $S/server-$label.log 2>&1 &
  for i in $(seq 1 90); do curl -s localhost:8091/health | grep -q ok && break; sleep 1; done
  python3 -I $S/bench.py 8091 $label $S/r-$label.json ${=benchflags} > $S/out-$label.txt 2>&1
  echo "done $label"
}
run baseline3 ""
run lookup-vault "" --spec-type ngram-cache -lcs $S/vault-lookup.bin
run ngram-simple-n4 "" --spec-type ngram-simple --spec-ngram-simple-size-n 4 --spec-ngram-simple-size-m 16
run ngram-map-k-n4 "" --spec-type ngram-map-k --spec-ngram-map-k-size-n 4 --spec-ngram-map-k-size-m 16
run plain-baseline "--plain"
run plain-ngram-simple-n4 "--plain" --spec-type ngram-simple --spec-ngram-simple-size-n 4 --spec-ngram-simple-size-m 16
pkill -f "llama-server.*--port 8091"
#!/bin/zsh
while pgrep -f "chain.sh" > /dev/null; do sleep 15; done
Q4=~/.ollama/models/blobs/sha256-85e4a5b7b8ef0e48af0e8658f5aaab9c2324c76c1641493f4d1e25fce54b18b9
Q17=~/.ollama/models/blobs/sha256-3d0b790534fe4b79525fc3692950408dca41171676ed7e21db57af5c65ef6ab6
run() {
  label=$1; shift
  pkill -f "llama-server.*--port 8091"; sleep 5
  llama-server -m $Q4 -a qwen3-4b-instruct --jinja -c 49152 -np 2 --port 8091 --slot-save-path $SCRATCH/vault/.burrow/kv -fa on -ctk q8_0 -ctv q8_0 "$@" > $SCRATCH/server-$label.log 2>&1 &
  for i in $(seq 1 120); do curl -s localhost:8091/health | grep -q ok && break; sleep 1; done
  python3 -I $SCRATCH/bench.py 8091 $label $SCRATCH/r-$label.json > $SCRATCH/out-$label.txt 2>&1
  echo "done $label $(sysctl -n vm.swapusage)"
}
run q8kv-48k
run draft-1.7b-48k --spec-type draft-simple -md $Q17 --spec-draft-n-max 8 -ctkd q8_0 -ctvd q8_0
pkill -f "llama-server.*--port 8091"
