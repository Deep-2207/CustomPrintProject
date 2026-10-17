"""Rules that need the product: checking a shopper's design, and checking a seller's edit to a product."""
from __future__ import annotations

import json
import re
import unicodedata

from fastapi import HTTPException

from .config import ALLOWED_FONTS, BASE, RESERVED_SLUGS, UPLOADS
from .schemas import SellerProductEdit

HEX = re.compile(r"#[0-9a-fA-F]{6}")
CONTROL = re.compile(r"[\x00-\x09\x0b-\x1f\x7f<>`\\{}]")   # strips control chars but keeps newline
MAX_STICKERS_PER_ZONE = 10
# These ids come from JSON files in static/, the single source of truth shared with the browser.
STICKER_IDS = {s["id"] for s in json.loads((BASE / "static" / "stickers.json").read_text(encoding="utf8"))}
TEXT_STYLE_IDS = {s["id"] for s in json.loads((BASE / "static" / "text-styles.json").read_text(encoding="utf8"))}
TEMPLATE_MESHES = {"band": {"band_outer"}, "mug": {"mug_outer"}}   # printable mesh of each built-in shape (see static/js/templates.js)


def clean_text(s: str, limit: int = 1000) -> str:
    raw = str(s).replace("\r\n", "\n").replace("\r", "\n")
    return CONTROL.sub("", raw)[:limit].strip()


def three_name(name: str) -> str:
    """How three.js names an object: spaces become underscores and reserved characters are dropped."""
    return re.sub(r"[\[\].:/]", "", re.sub(r"\s", "_", name or ""))


def slugify(text: str, max_len: int = 40) -> str:
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:max_len].strip("-")
    return t if len(t) >= 3 else (t + "-shop").strip("-")


def slug_problem(slug: str) -> str | None:
    if slug in RESERVED_SLUGS:
        return "That name is reserved. Please choose another."
    return None


# ---------------------------------------------------------------- shopper designs
def validate_design(prod: dict, d) -> list[dict]:
    """Returns the cleaned layers, or raises 422 listing every problem."""
    zones = {z["id"]: z for z in prod["zones"]}
    if not HEX.fullmatch(d.body_color) or (d.imprint_color and not HEX.fullmatch(d.imprint_color)):
        raise HTTPException(400, "Invalid colour")
    if d.size and d.size not in [s["id"] for s in prod.get("sizes", [])]:
        raise HTTPException(400, "Invalid size")
    errors, clean = [], []
    for i, l in enumerate(d.layers):
        z = zones.get(l.get("zone"))
        if not z:
            errors.append(f"Layer {i + 1}: unknown zone")
            continue
        kind = l.get("type")
        try:
            if kind == "text":
                text = clean_text(l.get("text", ""))
                chars = len(text.replace("\n", ""))           # line breaks are free; letters count
                lines = text.count("\n") + 1 if text else 0
                if chars > z["max_chars"]:
                    errors.append(f"{z['label']}: {chars} characters, limit is {z['max_chars']}")
                    continue
                if lines > z.get("max_lines", 1):
                    errors.append(f"{z['label']}: {lines} lines, limit is {z.get('max_lines', 1)}")
                    continue
                if l.get("font") not in prod["fonts"]:
                    errors.append(f"{z['label']}: font not allowed")
                    continue
                tpl = l.get("template") or "plain"
                if tpl not in TEXT_STYLE_IDS:
                    errors.append(f"{z['label']}: unknown text style")
                    continue
                clean.append({"zone": l["zone"], "type": "text", "font": l["font"], "template": tpl, "text": text,
                              "color": l.get("color") if HEX.fullmatch(str(l.get("color", ""))) else "",
                              "x": float(l.get("x", .5)), "y": float(l.get("y", .5)), "size": float(l.get("size", .5)), "rot": float(l.get("rot", 0))})
            elif kind == "image":
                if not z.get("allow_images", True):
                    errors.append(f"{z['label']}: images are not allowed here")
                    continue
                uid = str(l.get("upload_id", ""))
                if not re.fullmatch(r"[0-9a-f]{32}", uid) or not list(UPLOADS.glob(uid + ".*")):
                    errors.append(f"{z['label']}: image not found, upload it again")
                    continue
                clean.append({"zone": l["zone"], "type": "image", "upload_id": uid, "x": float(l.get("x", .5)), "y": float(l.get("y", .5)),
                              "scale": float(l.get("scale", .5)), "rot": float(l.get("rot", 0))})
            elif kind == "sticker":
                if not z.get("allow_stickers", True):
                    errors.append(f"{z['label']}: stickers are not allowed here")
                    continue
                if l.get("sticker") not in STICKER_IDS:
                    errors.append(f"{z['label']}: unknown sticker")
                    continue
                if sum(1 for c in clean if c["zone"] == l["zone"] and c["type"] == "sticker") >= MAX_STICKERS_PER_ZONE:
                    errors.append(f"{z['label']}: at most {MAX_STICKERS_PER_ZONE} stickers")
                    continue
                clean.append({"zone": l["zone"], "type": "sticker", "sticker": l["sticker"], "x": float(l.get("x", .5)), "y": float(l.get("y", .5)),
                              "scale": float(l.get("scale", .35)), "rot": float(l.get("rot", 0))})
            else:
                errors.append(f"Layer {i + 1}: unknown type")
        except (TypeError, ValueError):
            errors.append(f"Layer {i + 1}: a number is not valid")
    if errors:
        raise HTTPException(422, {"errors": errors})
    return clean


# ---------------------------------------------------------------- seller product edits
def merge_seller_edit(current: dict, edit: SellerProductEdit, model_meshes: set[str] | None) -> dict:
    """Applies a seller's edit to a product config and returns the new config, or raises 422 listing every problem.

    Sellers change colours, fonts, print areas, defaults and texts. They do not change the 3D model, the
    sizes' geometry or the built-in demos: those stay as they are in `current`.
    """
    errors: list[str] = []
    cfg = dict(current)
    cfg["name"] = edit.name.strip()

    colors = []
    for c in edit.colors:
        name, hx = clean_text(c.get("name", ""), 30), str(c.get("hex", ""))
        if not name or not HEX.fullmatch(hx):
            errors.append("Each colour needs a name and a colour like #1d6fe8.")
            break
        colors.append({"name": name, "hex": hx.lower()})
    if not colors:
        errors.append("Add at least one product colour.")
    if len({c["hex"] for c in colors}) != len(colors):
        errors.append("Two colours are the same. Remove one.")
    cfg["colors"] = colors

    imps = []
    for c in edit.imprint_colors:
        name, hx = clean_text(c.get("name", ""), 30), str(c.get("hex", ""))
        if not name or not (hx == "" or HEX.fullmatch(hx)):
            errors.append("Each text colour needs a name and a colour like #111111 (or none).")
            break
        imps.append({"name": name, "hex": hx.lower()})
    cfg["imprint_colors"] = imps

    fonts = [f for f in edit.fonts if f in ALLOWED_FONTS]
    if not fonts or len(fonts) != len(set(fonts)) or len(fonts) != len(edit.fonts):
        errors.append("Choose at least one font from the list.")
    cfg["fonts"] = fonts or current.get("fonts", ["Arial"])

    # Sizes: the shape numbers belong to the template; a seller can only rename a size.
    labels = {str(s.get("id")): clean_text(s.get("label", ""), 30) for s in edit.sizes}
    cfg["sizes"] = [{**s, "label": labels.get(str(s["id"])) or s["label"]} for s in current.get("sizes", [])]

    # Print areas
    seen, zones = set(), []
    allowed = model_meshes
    for z in edit.zones:
        if z.id in seen:
            errors.append(f"Two print areas share the id '{z.id}'.")
        seen.add(z.id)
        if z.u1 - z.u0 < 0.02 or z.y1 - z.y0 < 0.02:
            errors.append(f"'{z.label}': the print area is too small.")
        if allowed is not None and three_name(z.mesh) not in {three_name(m) for m in allowed}:
            errors.append(f"'{z.label}': the 3D model has no part called '{z.mesh}'.")
        zd = z.model_dump()
        zd["label"] = clean_text(zd["label"], 60) or z.id
        zones.append(zd)
    cfg["zones"] = zones
    cfg["body_meshes"] = sorted({z["mesh"] for z in zones}) or current.get("body_meshes", [])

    # Defaults must refer to things that exist
    d = dict(edit.defaults or {})
    hexes = {c["hex"] for c in colors}
    if d.get("bodyColor") and str(d["bodyColor"]).lower() not in hexes:
        errors.append("The starting colour must be one of the product colours.")
    if d.get("tpl") and d["tpl"] not in TEXT_STYLE_IDS:
        errors.append("Unknown starting text style.")
    try:
        ts = float(d.get("textSize", 0.45))
        if not 0.2 <= ts <= 0.8:
            errors.append("The starting text size must be between 20% and 80%.")
    except (TypeError, ValueError):
        errors.append("The starting text size must be a number.")
        ts = 0.45
    if d.get("font") and d["font"] not in cfg["fonts"]:
        errors.append("The starting font must be one of the chosen fonts.")
    cfg["defaults"] = {k: d[k] for k in ("bodyColor", "tpl", "font") if d.get(k)} | {"textSize": ts}

    cfg["sample"] = clean_text(edit.sample, 100)
    cfg["placeholder"] = clean_text(edit.placeholder, 100)
    p = edit.price or {}
    try:
        base = float(p.get("base", 0))
        if not 0 <= base <= 1_000_000:
            raise ValueError
    except (TypeError, ValueError):
        errors.append("The price must be a number.")
        base = 0.0
    cfg["price"] = {"base": base, "currency": "INR"}

    if errors:
        raise HTTPException(422, {"errors": list(dict.fromkeys(errors))})
    return cfg
