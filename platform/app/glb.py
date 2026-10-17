"""Reads the structure of a binary glTF (.glb) file without any 3D library, and reports what a seller needs to know.

A GLB is: a 12-byte header, then chunks. The first chunk is JSON describing meshes, materials and accessors.
Everything is checked defensively: a seller's file is untrusted input.
"""
from __future__ import annotations

import json
import struct

from .config import HEAVY_TRIANGLES
from .validation import three_name

MAX_JSON_BYTES = 8 * 1024 * 1024


def inspect_glb(data: bytes) -> dict:
    """Returns {valid, errors, warnings, bytes, total_triangles, meshes:[{name, three_name, triangles, has_uv}], nodes}."""
    errors: list[str] = []
    warnings: list[str] = []
    report = {"valid": False, "bytes": len(data), "total_triangles": 0, "meshes": [], "nodes": [], "errors": errors, "warnings": warnings}

    if len(data) < 20 or data[:4] != b"glTF":
        errors.append("This is not a binary glTF (.glb) file.")
        return report
    version, length = struct.unpack_from("<II", data, 4)
    if version != 2:
        errors.append(f"Unsupported glTF version {version}; export as glTF 2.0.")
        return report
    if length != len(data):
        errors.append("The file is damaged (its length does not match).")
        return report
    clen, ctype = struct.unpack_from("<II", data, 12)
    if ctype != 0x4E4F534A or 20 + clen > len(data):          # "JSON"
        errors.append("The file is damaged (no readable description).")
        return report
    if clen > MAX_JSON_BYTES:
        errors.append("The model description is unusually large.")
        return report
    try:
        gltf = json.loads(data[20:20 + clen].decode("utf8").rstrip("\x00 "))
    except Exception:
        errors.append("The file is damaged (the description cannot be read).")
        return report
    if not isinstance(gltf, dict):
        errors.append("The file is damaged.")
        return report

    # Everything must be inside the file. A link to another address would make every shopper's browser fetch it.
    for kind in ("buffers", "images"):
        for item in gltf.get(kind) if isinstance(gltf.get(kind), list) else []:
            uri = item.get("uri") if isinstance(item, dict) else None
            if isinstance(uri, str) and not uri.startswith("data:"):
                errors.append("The model refers to files outside itself. Export it again as a single .glb with everything embedded.")
                break
        if errors:
            break
    # The shop viewer does not include these decoders, so a model that needs them could never be shown.
    unsupported = {"KHR_draco_mesh_compression", "EXT_meshopt_compression", "KHR_texture_basisu"}
    need = [e for e in (gltf.get("extensionsRequired") if isinstance(gltf.get("extensionsRequired"), list) else []) if e in unsupported]
    if need:
        errors.append("The model uses compression the viewer cannot read (" + ", ".join(need) + "). Export it without Draco, Meshopt or Basis compression.")
    if errors:
        return report

    accessors = gltf.get("accessors") if isinstance(gltf.get("accessors"), list) else []

    def count(idx) -> int:
        if isinstance(idx, int) and 0 <= idx < len(accessors) and isinstance(accessors[idx], dict):
            c = accessors[idx].get("count")
            return c if isinstance(c, int) and c >= 0 else 0
        return 0

    total = 0
    meshes = []
    for i, m in enumerate(gltf.get("meshes") if isinstance(gltf.get("meshes"), list) else []):
        if not isinstance(m, dict):
            continue
        tris, has_uv = 0, False
        for p in m.get("primitives") if isinstance(m.get("primitives"), list) else []:
            if not isinstance(p, dict):
                continue
            attrs = p.get("attributes") if isinstance(p.get("attributes"), dict) else {}
            n = count(p.get("indices")) if "indices" in p else count(attrs.get("POSITION"))
            if p.get("mode", 4) == 4:
                tris += n // 3
            has_uv = has_uv or "TEXCOORD_0" in attrs
        name = str(m.get("name") or f"mesh_{i}")[:80]
        meshes.append({"name": name, "three_name": three_name(name), "triangles": tris, "has_uv": has_uv})
        total += tris
    report["meshes"], report["total_triangles"] = meshes, total
    report["nodes"] = [three_name(str(n.get("name")))[:80] for n in gltf.get("nodes", []) if isinstance(n, dict) and n.get("name")][:500]

    if not meshes:
        errors.append("The file contains no 3D shapes.")
    if meshes and not any(m["has_uv"] for m in meshes):
        errors.append("None of the shapes has UV coordinates, so nothing can be printed on them. Ask your 3D artist to unwrap the model.")
    for m in meshes:
        if not m["has_uv"]:
            warnings.append(f"'{m['name']}' has no UV coordinates, so it cannot be a print area.")
    if total > HEAVY_TRIANGLES:
        warnings.append(f"Very heavy model ({total:,} triangles). It will load slowly on phones; try to stay under {HEAVY_TRIANGLES:,}.")
    if len(data) > 10 * 1024 * 1024:
        warnings.append("The file is over 10 MB. Smaller textures (for example 1024 px) and fewer polygons will make it load faster.")
    named = [m["three_name"] for m in meshes]
    if len(set(named)) != len(named):
        warnings.append("Two shapes have the same name. Give each printable shape its own name.")
    report["valid"] = not errors
    return report
