"""A standard RAG pipeline built in n8n (Qdrant for the vectors, Ollama for the embedder and the model), run through
the Long Haul as CAMR is, so the two compare: how each works, how fast, how accurate. See README.md.

    python -m camr_engine.bench.rag_n8n longhaul --dir ../work/haul/s2 --cuts 2M [--k 8] [--budget 720]
"""
