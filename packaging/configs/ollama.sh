# CAMR with Ollama. Ollama runs the model; CAMR adds memory as words. Two doors to the same memory (~/.camr/default):

# 1. The ollama CLI, through CAMR's Ollama pairing (it speaks Ollama's own API):
camr ollama &                                   # listens on 127.0.0.1:11435, forwards to Ollama on 11434
OLLAMA_HOST=127.0.0.1:11435 ollama run qwen3:4b

# 2. Any OpenAI client, through CAMR's OpenAI-compatible endpoint:
camr serve --backend ollama &                   # listens on 127.0.0.1:11436/v1, forwards to Ollama's /v1
export OPENAI_BASE_URL=http://127.0.0.1:11436/v1 OPENAI_API_KEY=camr
