# Project status

Plan: SRS v2, 30 working days of about 1 hour. Updated at the end of every day.

**Day 4 of 30 finished.** Overall build: about 22% (the 10 modules weighted equally). Schedule: 4 of 30 days done (13%).

## Module completion

| ID | Module | Done | What exists | Still to do (day) |
| --- | --- | --- | --- | --- |
| M1 | Tenants and onboarding | 0% | Nothing yet | Sellers table (11), register (12), approval (15) |
| M2 | Authentication and roles | 5% | One shared admin key | Login, hashed passwords, roles (12) |
| M3 | Customizer engine | 80% | 3D viewer, multi-line text, 8 text style templates, 13 stickers, logo layers, colours, fonts, drag positioning, character and line limits, validation, reset | Inside and continuous messages, 2D fallback, polish (6, 7) |
| M4 | Template library | 70% | Wristband and mug templates built from code; both products in the database | Product picker (5), per-template defaults (6) |
| M5 | Product and model setup | 25% | JSON product definition, GLB upload with checks | Product form (17), model report (18), zone editor (19, 20) |
| M6 | Embed and public API | 20% | Design save and load API, shareable link page `/s/<seller>/<product>`, WhatsApp share | API keys and allowed domains (21), embed snippet (22), return design ID to host page (23) |
| M7 | Artwork and print files | 25% | Image upload checks, originals kept, low-resolution warning | Print-ready file export (25) |
| M8 | Seller dashboard | 0% | Nothing yet | Shell (15), products (16), designs list (24) |
| M9 | Plans, usage, invoicing | 0% | Nothing yet | Usage events and report (26, 27) |
| M10 | Plugins (Shopify, WooCommerce) | 0% | Not planned before the first paying sellers | Later |

## Day log

| Day | Goal | Result |
| --- | --- | --- |
| 1 | Git, README, clean start | Done: `.gitignore`, venv and data untracked, README, clean-start test passed |
| 2 | Template registry | Done: `static/js/templates.js`; wristband built through the registry |
| 3 | Mug template | Done: cup, handle on the back, print area on the front; mug product seeded (`custom-printed-mug`) |
| 3b | Mug redesign (your feedback) | Done: two fixed print rectangles (front and back, either side of the handle) with a dashed guide; handle on the viewer's left; text and logos clipped to the rectangle |
| 3c | Names on several lines and stickers (your feedback) | Done: Enter makes a new line (mug allows 4 lines, 60 letters); 13 one-colour stickers (`static/stickers.json`) added under the text box, each resizable and draggable; server checks lines, sticker ids and counts |
| 3d | Text style templates (your feedback) | Done: "Text style" gallery under the message box shows the customer's own text in 8 ready-made styles (plain, bubble sticker, ribbon banner, round badge, retro shadow, script, stamp, pop colour); styles live in `static/js/textstyles.js`, ids in `static/text-styles.json`; server checks the style id |
| 4 | Shareable link page | Done: `/s/<seller>/<product>` page, save and share design, copy link and WhatsApp button; camera now fits tall products |

## Known issues and notes
- The `seller` in a share link is only a label until real seller accounts exist (day 11 to 13).
- The share link opens the design by its ID; anyone with the link can view it. This is intended for now.
- Mug: handle is on the viewer's left, so the visible side is the FRONT area; Back turns the mug and shows the BACK area (handle on the right). The dashed guide shows on screen only, never in the saved preview. Print area size (115 degrees wide, 72% of the height) is a placeholder; confirm the real size with your first seller.
- Mug designs saved before this change used a single `print` area and no longer open.
- Browsers cache the JS files; after an update press Ctrl+F5 if the page looks old.
- Days 1 and 2 are committed; days 3 and 4 are not committed yet.
- Not yet tested in a real browser: the Save and share button, Copy link, and the WhatsApp link (the API behind them was tested).

## Next
Day 5: product picker that switches between wristband and mug on one page.
