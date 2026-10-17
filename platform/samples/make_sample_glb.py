"""Writes samples/sample-bottle.glb: a simple bottle (body + cap) with proper UV maps.

Use it to try the 3D model upload and the print-area editor without needing a model of your own.
    python samples/make_sample_glb.py
The part names are "Bottle Body" and "Cap".
"""
import json
import math
import struct
from pathlib import Path


def cylinder(radius, height, y0, segments=64, rings=1):
    """Open tube. u runs round the tube (0 to 1), v runs up (0 to 1). Returns positions, normals, uvs, indices."""
    pos, nor, uv, idx = [], [], [], []
    for r in range(rings + 1):
        v = r / rings
        y = y0 + v * height
        for s in range(segments + 1):
            u = s / segments
            a = u * 2 * math.pi + math.pi      # seam (u = 0 and 1) at the back; u = 0.5 faces +Z, the front
            x, z = math.sin(a), math.cos(a)
            pos += [radius * x, y, radius * z]
            nor += [x, 0.0, z]
            uv += [u, 1 - v]
    for r in range(rings):
        for s in range(segments):
            a = r * (segments + 1) + s
            b = a + segments + 1
            idx += [a, a + 1, b, b, a + 1, b + 1]      # counter-clockwise seen from outside = front face
    return pos, nor, uv, idx


def disc(radius, y, up=True, segments=48):
    pos, nor, uv, idx = [0.0, y, 0.0], [0.0, 1.0 if up else -1.0, 0.0], [0.5, 0.5], []
    for s in range(segments + 1):
        a = s / segments * 2 * math.pi
        pos += [radius * math.sin(a), y, radius * math.cos(a)]
        nor += [0.0, 1.0 if up else -1.0, 0.0]
        uv += [0.5 + 0.5 * math.sin(a), 0.5 + 0.5 * math.cos(a)]
    for s in range(1, segments + 1):
        idx += [0, s, s + 1] if up else [0, s + 1, s]
    return pos, nor, uv, idx


def merge(*parts):
    pos, nor, uv, idx = [], [], [], []
    for p, n, t, i in parts:
        base = len(pos) // 3
        pos += p; nor += n; uv += t; idx += [base + k for k in i]
    return pos, nor, uv, idx


def build() -> bytes:
    body = merge(cylinder(1.0, 3.2, 0.0), disc(1.0, 0.0, up=False), disc(1.0, 3.2, up=True))
    cap = merge(cylinder(0.45, 0.5, 3.2), disc(0.45, 3.7, up=True))
    chunks, views, accessors, meshes, nodes = bytearray(), [], [], [], []
    for name, (pos, nor, uv, idx) in (("Bottle Body", body), ("Cap", cap)):
        first = len(accessors)
        for data, fmt, target, ctype, typ, extra in (
            (pos, "f", 34962, 5126, "VEC3", {"min": [min(pos[i::3]) for i in range(3)], "max": [max(pos[i::3]) for i in range(3)]}),
            (nor, "f", 34962, 5126, "VEC3", {}),
            (uv, "f", 34962, 5126, "VEC2", {}),
            (idx, "H", 34963, 5123, "SCALAR", {}),
        ):
            raw = struct.pack(f"<{len(data)}{fmt}", *data)
            raw += b"\x00" * (-len(raw) % 4)
            views.append({"buffer": 0, "byteOffset": len(chunks), "byteLength": len(raw), "target": target})
            chunks += raw
            count = len(data) // {"VEC3": 3, "VEC2": 2, "SCALAR": 1}[typ]
            accessors.append({"bufferView": len(views) - 1, "componentType": ctype, "count": count, "type": typ, **extra})
        meshes.append({"name": name, "primitives": [{"attributes": {"POSITION": first, "NORMAL": first + 1, "TEXCOORD_0": first + 2}, "indices": first + 3, "material": 0}]})
        nodes.append({"name": name, "mesh": len(meshes) - 1})
    doc = {"asset": {"version": "2.0", "generator": "make_sample_glb.py"}, "scene": 0, "scenes": [{"nodes": list(range(len(nodes)))}], "nodes": nodes,
           "meshes": meshes, "materials": [{"name": "plain", "pbrMetallicRoughness": {"baseColorFactor": [0.9, 0.9, 0.9, 1], "metallicFactor": 0, "roughnessFactor": 0.5}}],
           "accessors": accessors, "bufferViews": views, "buffers": [{"byteLength": len(chunks)}]}
    js = json.dumps(doc, separators=(",", ":")).encode()
    js += b" " * (-len(js) % 4)
    bin_ = bytes(chunks)
    total = 12 + 8 + len(js) + 8 + len(bin_)
    return (b"glTF" + struct.pack("<II", 2, total) + struct.pack("<II", len(js), 0x4E4F534A) + js + struct.pack("<II", len(bin_), 0x004E4942) + bin_)


if __name__ == "__main__":
    out = Path(__file__).with_name("sample-bottle.glb")
    out.write_bytes(build())
    print(f"wrote {out} ({out.stat().st_size / 1024:.0f} KB)")
