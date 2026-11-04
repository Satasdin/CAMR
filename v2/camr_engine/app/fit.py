"""What fits this Mac: a model's anatomy from its config.json, the RAM it needs at a context, and how fast it runs
here, from the speeds measured on this Mac.

RAM at a context is the weights (their files' bytes), the keys and values every attention layer keeps per token
(bf16), the fixed state of linear-attention layers, the working memory of reading the prompt, and, for a model that
reads tensor memory, the camr's RAM budget (the core and the hot shelf). A model measured on this Mac uses its
measured peak instead of the estimate. The verdict:
- ``won't run``: the RAM needed is past the GPU's limit (Metal's working set; a 27B at 32K tokens ran out there);
- ``slow``: it fits, but writes under 10 tokens a second or waits over 4 s for the first word on a 1K-token desk;
- ``fits``: otherwise, with ``tight`` set when under 1.5 GB would be left.

Speeds of an unmeasured model come from two constants fitted to this Mac's measured models: writing is bound by
memory bandwidth (bytes of weights read per token), reading the prompt by compute (parameters per token).
"""

from __future__ import annotations

import json
import math
import re
import statistics
from dataclasses import dataclass, field
from pathlib import Path

from camr_engine.swap import RAM_BYTES

KV_BYTES = 2  # bf16 keys and values
STATE_BYTES = 4  # float32 linear-attention state
PREFILL_STEP = 2048  # camr_engine.models.PREFILL_STEP: the prompt is read in steps this long
DESK_TOKENS = 1024  # the desk the speed verdict is judged on (an camr desk is about 600 tokens)
SLOW_DECODE_TPS = 10.0
SLOW_FIRST_WORD_S = 4.0
TIGHT_BYTES = 1_500_000_000
CAMR_RAM = RAM_BYTES  # the core and the hot shelf together
WORK_PER_VOCAB = 2.3  # bytes of working memory per vocabulary entry per prompt token read in one step (fitted)
CONTEXTS = (2048, 8192, 32768)

KINDS = {"full_attention": "kv", "attention": "kv", "global_attention": "kv", "sliding_attention": "sliding",
         "chunked_attention": "sliding", "local_attention": "sliding", "linear_attention": "linear",
         "mamba": "linear", "mamba2": "linear", "conv": "linear", "recurrent": "linear", "ssm": "linear"}


def text_config(cfg: dict) -> dict:
    """The language model's part of a config (multimodal configs nest it), with the quantization kept."""
    tc = dict(cfg.get("text_config") or cfg.get("llm_config") or cfg.get("language_config") or cfg)
    for k in ("quantization", "quantization_config", "tie_word_embeddings", "torch_dtype", "dtype"):
        if k not in tc and k in cfg:
            tc[k] = cfg[k]
    return tc


def _n(tc: dict, *names, default=None):
    for n in names:
        if tc.get(n) is not None:
            return tc[n]
    return default


def layer_kinds(tc: dict) -> list[str]:
    """One kind per layer: ``kv`` (keeps keys and values, so it can read saved tensor memory), ``sliding`` (keeps
    them for a window only), ``linear`` (linear attention or a state-space layer: a fixed state, no KV) or ``none``
    (no attention at all)."""
    n = int(_n(tc, "num_hidden_layers", "n_layer", "num_layers", default=0) or 0)
    types = tc.get("layer_types")
    if isinstance(types, list) and len(types) == n:
        return [KINDS.get(str(t).lower(), "kv") for t in types]
    pattern = tc.get("hybrid_override_pattern")
    if isinstance(pattern, str) and len(pattern) == n:
        return ["kv" if c == "*" else "linear" if c == "M" else "none" for c in pattern]
    if tc.get("full_attention_interval"):
        k = int(tc["full_attention_interval"])
        return ["kv" if (i + 1) % k == 0 else "linear" for i in range(n)]
    if tc.get("attn_layer_period"):
        p, o = int(tc["attn_layer_period"]), int(tc.get("attn_layer_offset", 0))
        return ["kv" if i % p == o else "linear" for i in range(n)]
    if tc.get("sliding_window_pattern") and tc.get("sliding_window"):
        p = int(tc["sliding_window_pattern"])
        return ["kv" if (i + 1) % p == 0 else "sliding" for i in range(n)]
    if tc.get("use_sliding_window") and tc.get("sliding_window"):
        return ["sliding"] * n
    return ["kv"] * n


def quant(cfg: dict, name: str = "") -> dict:
    """Bits, group size and mode of the weights, from the config, else from the name; bf16 when not quantized."""
    q = cfg.get("quantization") or cfg.get("quantization_config") or {}
    if isinstance(q, dict) and q.get("bits"):
        bits, group, mode = int(q["bits"]), int(q.get("group_size") or 64), q.get("mode") or "affine"
    else:
        m = re.search(r"(\d+)\s*-?bit", name, re.I)
        if m:
            bits, group, mode = int(m.group(1)), 64, "affine"
        else:
            dtype = str(cfg.get("torch_dtype") or cfg.get("dtype") or "bfloat16")
            bits, group, mode = (32 if "32" in dtype else 16), 0, dtype.replace("bfloat16", "bf16").replace(
                "float16", "fp16")
    if bits >= 16:
        label = "bf16" if bits == 16 and mode in ("bf16", "affine") else str(mode)
    else:
        label = f"{bits}-bit" + (f" {mode}" if mode not in ("affine", None) else "") + (f" g{group}" if group else "")
    return {"bits": bits, "group_size": group, "mode": mode, "label": label}


def bytes_per_param(q: dict) -> float:
    if q["bits"] >= 16:
        return q["bits"] / 8
    scales = 1 / 32 if "mxfp" in str(q["mode"]) else 4 / max(q["group_size"] or 64, 1)  # bf16 scale and bias
    return q["bits"] / 8 + scales


def _params(tc: dict, kinds: list[str]) -> tuple[float, float]:
    """Total and active (per token) parameters, worked out from the shapes."""
    h = int(_n(tc, "hidden_size", "d_model", "n_embd", default=0) or 0)
    if not h:
        return 0.0, 0.0
    heads = int(_n(tc, "num_attention_heads", "n_head", default=1) or 1)
    kvh = int(_n(tc, "num_key_value_heads", default=heads) or heads)
    hd = int(_n(tc, "head_dim", default=h // heads) or h // heads)
    inter = int(_n(tc, "intermediate_size", "ffn_hidden_size", default=4 * h) or 4 * h)
    vocab = int(_n(tc, "vocab_size", default=0) or 0)
    experts = int(_n(tc, "num_experts", "n_routed_experts", "num_local_experts", default=0) or 0)
    k = int(_n(tc, "num_experts_per_tok", "moe_top_k", default=0) or 0)
    moe_inter = int(_n(tc, "moe_intermediate_size", default=inter) or inter)
    shared = int(_n(tc, "shared_expert_intermediate_size", default=0) or 0) or (
        int(tc.get("n_shared_experts") or 0) * moe_inter)
    attn = h * heads * hd * 2 + 2 * h * kvh * hd
    total = active = 0.0
    for kind in kinds:
        a = attn if kind in ("kv", "sliding") else (4 * h * h if kind == "linear" else 0)
        if experts and k:
            total += a + 3 * h * (experts * moe_inter + shared)
            active += a + 3 * h * (k * moe_inter + shared)
        else:
            total += a + 3 * h * inter
            active += a + 3 * h * inter
    emb = vocab * h * (1 if tc.get("tie_word_embeddings", False) else 2)
    return total + emb, active + emb


def _kv_per_token(tc: dict) -> int:
    """Bytes of keys and values one attention layer keeps per token."""
    h = int(_n(tc, "hidden_size", "d_model", default=0) or 0)
    heads = int(_n(tc, "num_attention_heads", "n_head", default=1) or 1)
    if tc.get("kv_lora_rank"):  # multi-head latent attention, cached as full keys and values per head
        return heads * (int(tc.get("qk_nope_head_dim", 0)) + int(tc.get("qk_rope_head_dim", 0))
                        + int(tc.get("v_head_dim", 0))) * KV_BYTES
    kvh = int(_n(tc, "num_key_value_heads", default=heads) or heads)
    hd = int(_n(tc, "head_dim", default=h // heads if heads else 0) or 0)
    return 2 * kvh * hd * KV_BYTES


def _state_per_layer(tc: dict) -> int:
    """Bytes of the fixed state one linear-attention (or state-space) layer keeps, whatever the context."""
    if tc.get("linear_num_value_heads"):
        vh, kd, vd = (int(tc["linear_num_value_heads"]), int(tc.get("linear_key_head_dim", 128)),
                      int(tc.get("linear_value_head_dim", 128)))
        kh, conv = int(tc.get("linear_num_key_heads", vh)), int(tc.get("linear_conv_kernel_dim", 4))
        return vh * kd * vd * STATE_BYTES + (conv - 1) * (2 * kh * kd + vh * vd) * KV_BYTES
    if tc.get("mamba_num_heads") or tc.get("ssm_state_size") or tc.get("state_size"):
        heads = int(_n(tc, "mamba_num_heads", default=0) or 0)
        hd = int(_n(tc, "mamba_head_dim", default=0) or 0)
        n = int(_n(tc, "ssm_state_size", "state_size", default=128) or 128)
        h = int(_n(tc, "hidden_size", default=0) or 0)
        inner = heads * hd or 2 * h
        return inner * n * STATE_BYTES
    h = int(_n(tc, "hidden_size", default=0) or 0)
    return h * 128 * STATE_BYTES  # unknown layout: a hidden-wide state of 128


def _size_from_name(name: str) -> tuple[float | None, float | None]:
    """Parameters named in a repository name, as in ``Qwen3-30B-A3B``: (total, active), in billions."""
    m = re.search(r"(?<![\w.])(\d+(?:\.\d+)?)\s*([BM])(?:-A(\d+(?:\.\d+)?)([BM]))?(?![a-z])", name, re.I)
    if not m:
        return None, None
    scale = {"b": 1e9, "m": 1e6}
    total = float(m.group(1)) * scale[m.group(2).lower()]
    active = float(m.group(3)) * scale[m.group(4).lower()] if m.group(3) else None
    return total, active


@dataclass
class Anatomy:
    """What a model is, from its config: its layers and what each keeps."""

    layers: list[str]
    kv_per_token: int  # all KV-keeping layers together, per token
    sliding_per_token: int  # all sliding layers together, per token within their window
    window: int | None
    state_bytes: int  # all linear layers together
    params: float  # total
    active: float  # per token
    vocab: int
    quant: dict
    max_context: int | None
    family: str | None

    @property
    def memory_as(self) -> str:
        """``tensors`` when every attention layer keeps its keys and values, so saved notes can be laid on its desk;
        ``words`` otherwise (the memory is read to it as text)."""
        return "tensors" if self.layers and all(k == "kv" for k in self.layers) else "words"

    def to_dict(self) -> dict:
        return {"layers": self.layers, "kv_layers": self.layers.count("kv"),
                "linear_layers": self.layers.count("linear"), "sliding_layers": self.layers.count("sliding"),
                "kv_bytes_per_token": self.kv_per_token + self.sliding_per_token, "window": self.window,
                "state_bytes": self.state_bytes, "params": self.params, "active_params": self.active,
                "quant": self.quant, "memory_as": self.memory_as, "max_context": self.max_context,
                "family": self.family}


def anatomy(cfg: dict, name: str = "") -> Anatomy:
    tc = text_config(cfg)
    kinds = layer_kinds(tc)
    per_layer = _kv_per_token(tc)
    total, active = _params(tc, kinds)
    named, named_active = _size_from_name(name)
    if named and (not total or abs(math.log(named / total)) > math.log(1.6)):
        active = (named_active or named * (active / total if total else 1.0))
        total = named
    return Anatomy(kinds, per_layer * kinds.count("kv"), per_layer * kinds.count("sliding"),
                   int(tc["sliding_window"]) if tc.get("sliding_window") and "sliding" in kinds else None,
                   _state_per_layer(tc) * kinds.count("linear"), float(total), float(active),
                   int(_n(tc, "vocab_size", default=0) or 0), quant(cfg, name),
                   int(tc["max_position_embeddings"]) if tc.get("max_position_embeddings") else None,
                   tc.get("model_type") or cfg.get("model_type"))


# -- this Mac's measured speeds


@dataclass
class Measured:
    """One model's measured run on this Mac (``camr_engine.bench.throughput``): peak RAM, first word and writing speed
    by prompt length, and the token count where it ran out of GPU memory, if it did."""

    record: str
    points: list[dict]
    failed_at: int | None = None

    def _ok(self) -> list[dict]:
        return sorted((p for p in self.points if "first_word_s" in p), key=lambda p: p["tokens"])

    def decode_tps(self) -> float | None:
        ok = self._ok()
        return ok[0]["write_tok_s"] if ok else None

    def first_word_s(self, tokens: int = DESK_TOKENS) -> float | None:
        """At ``tokens``, interpolated on log scales between the two nearest measured lengths."""
        ok = [p for p in self._ok() if p.get("first_word_s")]
        if not ok:
            return None
        return _loglerp([(p["tokens"], p["first_word_s"]) for p in ok], tokens)

    def peak_bytes(self, tokens: int, kv_per_token: int) -> int | None:
        """Peak RAM at ``tokens``: linear between measured lengths; past the last, the last plus the keys and values
        of the extra tokens. None when that length ran out of GPU memory here."""
        if self.failed_at is not None and tokens >= self.failed_at:
            return None
        ok = [p for p in self._ok() if p.get("peak_gb")]
        if not ok:
            return None
        pts = [(p["tokens"], p["peak_gb"] * 1e9) for p in ok]
        if tokens <= pts[0][0]:
            return int(pts[0][1])
        for (t0, b0), (t1, b1) in zip(pts, pts[1:]):
            if tokens <= t1:
                return int(b0 + (b1 - b0) * (tokens - t0) / (t1 - t0))
        return int(pts[-1][1] + (tokens - pts[-1][0]) * kv_per_token)


def _loglerp(pts: list[tuple[float, float]], x: float) -> float:
    pts = sorted(pts)
    if len(pts) == 1:
        return pts[0][1] * x / pts[0][0]
    if x <= pts[0][0]:
        (x0, y0), (x1, y1) = pts[0], pts[1]
    elif x >= pts[-1][0]:
        (x0, y0), (x1, y1) = pts[-2], pts[-1]
    else:
        (x0, y0), (x1, y1) = next((a, b) for a, b in zip(pts, pts[1:]) if a[0] <= x <= b[0])
    f = (math.log(x) - math.log(x0)) / (math.log(x1) - math.log(x0))
    return math.exp(math.log(y0) + f * (math.log(y1) - math.log(y0)))


@dataclass
class Speeds:
    """This Mac's measured runs by repository (MLX) and Ollama name, and the two constants fitted to them."""

    mlx: dict[str, Measured] = field(default_factory=dict)
    ollama: dict[str, Measured] = field(default_factory=dict)
    bandwidth: float | None = None  # bytes of weights read per second while writing
    compute: float | None = None  # parameters times prompt tokens read per second
    records: list[str] = field(default_factory=list)

    @classmethod
    def load(cls, folder: Path, weights: dict[str, tuple[int, Anatomy]] | None = None) -> Speeds:
        """Read every ``throughput-*.json`` in ``folder`` (later records win), then fit the constants on the
        measured MLX models whose files and config are in ``weights`` (repo -> (weights bytes, anatomy))."""
        s = cls()
        for path in sorted(Path(folder).glob("throughput-*.json")):
            try:
                rec = json.loads(path.read_text())
            except (OSError, ValueError):
                continue
            name = f"{path.parent.name}/{path.name}"
            s.records.append(name)
            for m in (rec.get("mlx") or {}).values():
                if m.get("repo"):
                    s.mlx[m["repo"]] = _measured(name, m)
            for m in (rec.get("ollama") or {}).values():
                if m.get("name"):
                    s.ollama[m["name"]] = _measured(name, m)
        s.fit(weights or {})
        return s

    def fit(self, weights: dict[str, tuple[int, Anatomy]]) -> None:
        bw, cp = [], []
        for repo, m in self.mlx.items():
            if repo not in weights:
                continue
            size, a = weights[repo]
            ok = m._ok()
            if ok and size:
                bw.append(size * (a.active / a.params if a.params else 1.0) * ok[0]["write_tok_s"])
            long = [p for p in ok if p["tokens"] >= PREFILL_STEP]
            if long and a.active:
                cp.append(a.active * long[0]["read_tok_s"])
        self.bandwidth = statistics.median(bw) if bw else None
        self.compute = statistics.median(cp) if cp else None


def _measured(record: str, m: dict) -> Measured:
    points = m.get("points") or []
    failed = [p["tokens"] for p in points if p.get("error")]
    return Measured(record, points, min(failed) if failed else None)


# -- one model on this Mac


@dataclass
class Mac:
    """The limits a model is judged against."""

    ram_bytes: int | None
    gpu_limit_bytes: int | None
    other_bytes: int | None = None  # what other processes hold now


def judge(a: Anatomy, weights_bytes: int, context: int, mac: Mac, speeds: Speeds, *, measured: Measured | None = None,
          camr: bool = True) -> dict:
    """RAM needed at ``context``, the speed here, and the verdict, each marked measured or est."""
    ctx = min(context, a.max_context) if a.max_context else context
    kv = a.kv_per_token * ctx + a.sliding_per_token * min(ctx, a.window or ctx)
    work = int(min(ctx, PREFILL_STEP) * a.vocab * WORK_PER_VOCAB) if a.vocab else int(0.1 * weights_bytes)
    camr_bytes = CAMR_RAM if camr and a.memory_as == "tensors" else 0
    model_bytes = weights_bytes + kv + a.state_bytes + work
    source = "est."
    if measured is not None:
        peak = measured.peak_bytes(ctx, a.kv_per_token + a.sliding_per_token)
        if peak is not None:
            model_bytes, source = peak, "measured"
        elif measured.failed_at is not None and ctx >= measured.failed_at:
            source = "measured"
            model_bytes = max(model_bytes, (mac.gpu_limit_bytes or model_bytes) + 1)
    need = model_bytes + camr_bytes

    decode = first = None
    speed_source = None
    if measured is not None and measured.decode_tps():
        decode, first, speed_source = measured.decode_tps(), measured.first_word_s(DESK_TOKENS), "measured"
    elif speeds.bandwidth and weights_bytes:
        active_bytes = weights_bytes * (a.active / a.params if a.params else 1.0)
        decode = speeds.bandwidth / (active_bytes + a.kv_per_token * DESK_TOKENS)
        if speeds.compute and a.active:
            first = DESK_TOKENS * a.active / speeds.compute
        speed_source = "est."

    limit = mac.gpu_limit_bytes or (int(mac.ram_bytes * 0.74) if mac.ram_bytes else None)
    spare = limit - need if limit is not None else None
    if mac.ram_bytes and mac.other_bytes is not None:
        spare = min(spare, mac.ram_bytes - mac.other_bytes - need) if spare is not None else (
            mac.ram_bytes - mac.other_bytes - need)
    if limit is not None and need > limit:
        verdict, why = "wont_run", f"needs {need - limit} B past the GPU limit"
    elif (decode is not None and decode < SLOW_DECODE_TPS) or (first is not None and first > SLOW_FIRST_WORD_S):
        verdict, why = "slow", "under 10 tok/s" if decode is not None and decode < SLOW_DECODE_TPS else (
            f"over {SLOW_FIRST_WORD_S:g} s to the first word on a {DESK_TOKENS}-token desk")
    else:
        verdict, why = ("fits", "") if limit is not None else ("unknown", "the GPU limit could not be read")
    return {"context": ctx, "need_bytes": need, "source": source,
            "parts": {"weights": weights_bytes, "kv": kv, "state": a.state_bytes, "work": work if source == "est."
                      else max(0, model_bytes - weights_bytes - kv - a.state_bytes), "camr": camr_bytes},
            "limit_bytes": limit, "spare_bytes": spare, "tight": spare is not None and spare < TIGHT_BYTES,
            "decode_tps": round(decode, 1) if decode else None,
            "first_word_s": round(first, 3) if first else None, "speed_source": speed_source,
            "verdict": verdict, "why": why}
