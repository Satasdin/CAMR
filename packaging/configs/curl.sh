# CAMR's OpenAI-compatible endpoint, from curl. Start it first:  camr serve --backend ollama
CAMR=http://127.0.0.1:11436

# the models the backend has
curl -s $CAMR/v1/models

# tell it something (the exchange is remembered once the answer ends)
curl -s $CAMR/v1/chat/completions -H 'Content-Type: application/json' -d '{
  "model": "qwen3:4b",
  "messages": [{"role": "user", "content": "The client picked terracotta, #C2410C, as the main colour."}]
}'

# ask about it later, streaming: notes from memory go in just before the question
curl -sN $CAMR/v1/chat/completions -H 'Content-Type: application/json' -d '{
  "model": "qwen3:4b", "stream": true,
  "messages": [{"role": "user", "content": "What main colour did the client pick?"}]
}'

# one request without memory: nothing recalled, nothing remembered
curl -s $CAMR/v1/chat/completions -H 'Content-Type: application/json' -H 'X-CAMR-Memory: off' -d '{
  "model": "qwen3:4b", "messages": [{"role": "user", "content": "Hello"}]
}'

# what each request cost: recall_ms, added_ms, first_byte_ms, tokens
curl -s $CAMR/camr_engine/metrics
