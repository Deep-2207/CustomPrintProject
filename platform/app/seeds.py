"""Built-in (platform) products. Sellers clone these from the dashboard to make their own.

Bump SEED_VERSION when a definition below changes: on start-up the platform copy is refreshed.
Sellers' own copies are never touched.
"""
from __future__ import annotations

from typing import Any

SEED: dict[str, Any] = {
    "slug": "custom-embossed-wristband",
    "name": "Custom Embossed Wristbands",
    "model": {"type": "template", "template": "band", "url": None},
    "sizes": [{"id": "1/2", "label": '1/2"', "mm": 12.7}, {"id": "3/4", "label": '3/4"', "mm": 19}, {"id": "1", "label": '1"', "mm": 25.4}],
    "colors": [{"name": n, "hex": h} for n, h in [("Blue", "#1d6fe8"), ("Cyan", "#1fb5e8"), ("Black", "#1b1b1b"), ("Red", "#d62828"),
                                                  ("Green", "#2a9d3f"), ("Yellow", "#facc15"), ("Orange", "#f97316"), ("Purple", "#7e3ff2"), ("White", "#f4f4f4")]],
    "imprint_colors": [{"name": n, "hex": h} for n, h in [("None", ""), ("White", "#ffffff"), ("Black", "#111111"), ("Gold", "#d4a017"), ("Silver", "#c0c6cc")]],
    "fonts": ["Arial", "Impact", "Georgia", "Courier New", "Trebuchet MS"],
    "zones": [
        {"id": "front", "label": "Front message", "mesh": "band_outer", "style": "emboss", "max_chars": 28, "allow_images": True, "u0": 0.0, "u1": 0.5},
        {"id": "back", "label": "Back message", "mesh": "band_outer", "style": "emboss", "max_chars": 28, "allow_images": True, "u0": 0.5, "u1": 1.0},
    ],
    "body_meshes": ["band_outer"],
    "price": {"base": 16.0, "currency": "INR"},
    # What a fresh customizer starts with, the hint text, and ready-made examples for demos.
    "defaults": {"bodyColor": "#1fb5e8", "tpl": "plain", "textSize": 0.45},
    "sample": "TEAM 2026",
    "placeholder": "e.g. TEAM SPIRIT 2026",
    "demos": [
        {"name": "Team spirit", "body_color": "#1d6fe8", "zones": {"front": {"text": "TEAM SPIRIT 2026"}, "back": {"text": "NEVER GIVE UP"}}},
        {"name": "Charity run", "body_color": "#d62828", "imprint_color": "#ffffff", "zones": {"front": {"text": "RUN FOR LIFE"}, "back": {"text": "5K - AHMEDABAD"}}},
        {"name": "Event pass", "body_color": "#1b1b1b", "imprint_color": "#d4a017", "zones": {"front": {"text": "VIP ACCESS"}, "back": {"text": "ALL NIGHT LONG"}}},
    ],
}


MUG_SEED: dict[str, Any] = {
    "slug": "custom-printed-mug",
    "name": "Custom Printed Mugs",
    "model": {"type": "template", "template": "mug", "url": None},
    # height / radius in millimetres drive the 3D shape (see static/js/templates.js)
    "sizes": [{"id": "11oz", "label": "11 oz (325 ml)", "mm": 95, "radius": 41}, {"id": "15oz", "label": "15 oz (440 ml)", "mm": 110, "radius": 44}],
    "colors": [{"name": n, "hex": h} for n, h in [("White", "#f4f4f4"), ("Black", "#1b1b1b"), ("Red", "#d62828"), ("Blue", "#1d6fe8"),
                                                  ("Green", "#2a9d3f"), ("Yellow", "#facc15"), ("Orange", "#f97316"), ("Pink", "#ec4899")]],
    "imprint_colors": [{"name": n, "hex": h} for n, h in [("Auto", ""), ("Black", "#111111"), ("White", "#ffffff"), ("Gold", "#d4a017"), ("Red", "#d62828")]],
    "fonts": ["Arial", "Impact", "Georgia", "Courier New", "Trebuchet MS"],
    # Two fixed print rectangles, one each side of the handle. With the handle on the viewer's left the
    # visible side is the FRONT; turn the mug and the BACK area faces you. y0/y1 = top/bottom of the area.
    "zones": [
        {"id": "front", "label": "Front print area", "mesh": "mug_outer", "style": "print", "max_chars": 60, "max_lines": 4, "allow_images": True,
         "u0": 0.09, "u1": 0.41, "y0": 0.14, "y1": 0.86, "guide": True},
        {"id": "back", "label": "Back print area", "mesh": "mug_outer", "style": "print", "max_chars": 60, "max_lines": 4, "allow_images": True,
         "u0": 0.59, "u1": 0.91, "y0": 0.14, "y1": 0.86, "guide": True},
    ],
    "body_meshes": ["mug_outer"],
    "price": {"base": 250.0, "currency": "INR"},
    "defaults": {"bodyColor": "#f4f4f4", "tpl": "bubble", "textSize": 0.6},
    "sample": "Your\nName",
    "placeholder": "Type a name or message. Press Enter for a new line",
    "demos": [
        {"name": "World's best dad", "body_color": "#f4f4f4",
         "zones": {"front": {"text": "WORLD'S\nBEST\nDAD", "tpl": "bubble"}, "back": {"text": "Since\n1985", "tpl": "script"}}},
        {"name": "Name gift", "body_color": "#1b1b1b",
         "zones": {"front": {"text": "Deep\nPatel", "tpl": "script", "color": "#ffd166",
                             "stickers": [{"id": "star", "x": 0.14, "y": 0.18, "scale": 0.16}, {"id": "star", "x": 0.86, "y": 0.82, "scale": 0.16}]}}},
        {"name": "Team mug", "body_color": "#1d6fe8",
         "zones": {"front": {"text": "TEAM\nAHMEDABAD", "tpl": "badge"}, "back": {"text": "Work hard\nDrink chai", "tpl": "shadow"}}},
        {"name": "Mr & Mrs", "body_color": "#ec4899",
         "zones": {"front": {"text": "Mr &\nMrs Patel", "tpl": "shadow",
                             "stickers": [{"id": "heart", "x": 0.12, "y": 0.2, "scale": 0.18}, {"id": "heart", "x": 0.88, "y": 0.8, "scale": 0.18}]}}},
    ],
}

SEED_VERSION = 2   # bump when a built-in product definition above changes
SEEDS = [SEED, MUG_SEED]
for _p in SEEDS:
    _p["seed_version"] = SEED_VERSION
