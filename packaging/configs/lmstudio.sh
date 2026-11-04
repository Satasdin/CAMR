# CAMR with LM Studio. LM Studio runs the model; CAMR sits in front of its server and adds memory.
lms server start                                # LM Studio's OpenAI-compatible server, on 127.0.0.1:1234
lms ls                                          # the models you downloaded in LM Studio
lms load <model>                                # or load one in the LM Studio app
camr serve --backend lmstudio &                 # CAMR on 127.0.0.1:11436/v1, forwarding to 127.0.0.1:1234

# Then, in any client that used LM Studio's server, change only the base URL:
#   http://localhost:1234/v1   ->   http://127.0.0.1:11436/v1
# The model names stay LM Studio's own (curl http://127.0.0.1:11436/v1/models lists them).
export OPENAI_BASE_URL=http://127.0.0.1:11436/v1 OPENAI_API_KEY=lm-studio
