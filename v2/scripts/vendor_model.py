"""Make a downloaded glTF model fit for the vendored kit (camr_engine/agentic/vendor/models): every texture image is
taken out and the parts it painted get a plain colour, so no lettering, flag or logo of the source comes along, and
the binary is rebuilt with only the geometry that is used.

    .venv/bin/python -I scripts/vendor_model.py <downloaded.glb> <out.glb> [--colour 0.94]

Run with -I on a downloaded file. It reads only the GLB container (JSON + binary chunk); nothing in the file is run.
"""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path


def read_glb(data: bytes) -> tuple[dict, bytes]:
    if data[:4] != b"glTF" or struct.unpack("<I", data[4:8])[0] != 2:
        raise ValueError("not a glTF 2 binary")
    at, doc, binary = 12, None, b""
    while at < len(data):
        size, kind = struct.unpack("<II", data[at:at + 8])
        chunk = data[at + 8:at + 8 + size]
        if kind == 0x4E4F534A:  # JSON
            doc = json.loads(chunk)
        elif kind == 0x004E4942:  # BIN
            binary = chunk
        at += 8 + size
    if doc is None:
        raise ValueError("no JSON chunk")
    return doc, binary


def write_glb(doc: dict, binary: bytes) -> bytes:
    js = json.dumps(doc, separators=(",", ":")).encode()
    js += b" " * (-len(js) % 4)
    binary += b"\0" * (-len(binary) % 4)
    total = 12 + 8 + len(js) + (8 + len(binary) if binary else 0)
    out = struct.pack("<III", 0x46546C67, 2, total) + struct.pack("<II", len(js), 0x4E4F534A) + js
    if binary:
        out += struct.pack("<II", len(binary), 0x004E4942) + binary
    return out


def strip_markings(doc: dict, binary: bytes, colour: float = 0.94) -> tuple[dict, bytes, int]:
    """(doc, binary, textures removed): no images, textures or samplers; a textured material becomes plain
    ``colour`` grey-white; only the buffer views the geometry uses are kept, packed again."""
    removed = 0
    for m in doc.get("materials", []):
        pbr = m.setdefault("pbrMetallicRoughness", {})
        for key in ("baseColorTexture", "metallicRoughnessTexture"):
            if key in pbr:
                del pbr[key]
                pbr["baseColorFactor"] = [colour, colour, colour, 1]
                removed += 1
        for key in ("normalTexture", "occlusionTexture", "emissiveTexture"):
            if key in m:
                del m[key]
                removed += 1
        for ext in list((m.get("extensions") or {})):
            if any("Texture" in k for k in m["extensions"][ext]):
                del m["extensions"][ext]
    for key in ("images", "textures", "samplers"):
        doc.pop(key, None)
    for key in ("extensionsUsed", "extensionsRequired"):
        if key in doc:
            doc[key] = [e for e in doc[key] if "texture" not in e.lower()]
            if not doc[key]:
                del doc[key]
    used = sorted({a["bufferView"] for a in doc.get("accessors", []) if "bufferView" in a})
    new_index, packed, views = {}, bytearray(), []
    for old in used:
        v = dict(doc["bufferViews"][old])
        start = v.get("byteOffset", 0)
        piece = binary[start:start + v["byteLength"]]
        packed += b"\0" * (-len(packed) % 4)
        v["byteOffset"] = len(packed)
        v["buffer"] = 0
        packed += piece
        new_index[old] = len(views)
        views.append(v)
    for a in doc.get("accessors", []):
        if "bufferView" in a:
            a["bufferView"] = new_index[a["bufferView"]]
    doc["bufferViews"] = views
    doc["buffers"] = [{"byteLength": len(packed)}]
    return doc, bytes(packed), removed


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--colour", type=float, default=0.94)
    a = ap.parse_args(argv)
    doc, binary = read_glb(a.src.read_bytes())
    doc, binary, removed = strip_markings(doc, binary, a.colour)
    a.out.write_bytes(write_glb(doc, binary))
    print(f"{a.src.name}: {removed} textures taken out -> {a.out} ({a.out.stat().st_size:,} B)")


if __name__ == "__main__":
    main()
