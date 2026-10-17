# Project status

Plan: SRS v2, 30 working days of about 1 hour. Updated at the end of every working session.

**Days 1 to 10 finished.** Overall build: about 26% (the 10 modules weighted equally). Schedule: 10 of 30 days done (33%).
Ahead on the customizer; behind on seller accounts, which start on day 11.

## Module completion

| ID | Module | Done | What exists | Still to do (day) |
| --- | --- | --- | --- | --- |
| M1 | Tenants and onboarding | 0% | Nothing yet (the landing sign-up form only collects leads) | Sellers table (11), register (12), approval (15) |
| M2 | Authentication and roles | 5% | One shared admin key | Login, hashed passwords, roles (12) |
| M3 | Customizer engine | 85% | 3D viewer, multi-line text, 8 text styles, 13 stickers, logos, colours, fonts, drag positioning, limits and validation, reset, per-product defaults, demo examples, auto-rotate, download picture | Inside and continuous messages, 2D fallback, polish |
| M4 | Template library | 90% | Wristband and mug templates; product picker that keeps the typed text; per-product defaults and sample text | Real print sizes to confirm with a seller |
| M5 | Product and model setup | 25% | JSON product definition, GLB upload with checks, seed versioning for built-in products | Product form (17), model report (18), zone editor (19, 20) |
| M6 | Embed and public API | 25% | Design save and load API, shareable link page `/s/<seller>/<product>`, WhatsApp share, demo mode | API keys and allowed domains (21), embed snippet (22), return design ID to host page (23) |
| M7 | Artwork and print files | 30% | Image upload checks, originals kept, low-resolution warning, logos verified on both products | Print-ready file export (25) |
| M8 | Seller dashboard | 0% | Nothing yet (admin page lists sign-ups) | Shell (15), products (16), designs list (24) |
| M9 | Plans, usage, invoicing | 0% | Nothing yet | Usage events and report (26, 27) |
| M10 | Plugins (Shopify, WooCommerce) | 0% | Not planned before the first paying sellers | Later |
| - | Landing page and lead capture (outreach support) | 100% for v1 | Landing page with live demo, sign-up form, rate limit, spam trap, admin list, outbox log, optional email | Real brand name, Gujarati copy |

## Day log

| Day | Goal | Result |
| --- | --- | --- |
| 1 | Git, README, clean start | Done: `.gitignore`, venv and data untracked, README, clean-start test passed |
| 2 | Template registry | Done: `static/js/templates.js`; wristband built through the registry |
| 3 | Mug template | Done: cup, handle, two fixed print areas (front and back, either side of the handle) with a dashed guide |
| 3b to 3d | Your feedback on the mug | Done: names on several lines, 13 stickers, and 8 text style templates that show the customer's own text |
| 4 | Shareable link page | Done: `/s/<seller>/<product>`, save and share, copy link, WhatsApp |
| 5 | Product picker | Done: pills at the top switch between wristband and mug and carry the typed text across |
| 6 | Per-template defaults | Done: each product has its own starting colour, text style, size, hint text and sample text; built-in products update when `SEED_VERSION` is bumped |
| 7 | Logo upload on both templates | Done and verified by a browser test on the mug and the wristband |
| 8 | Demo mode | Done: `&demo=1` adds example buttons (4 for the mug, 3 for the wristband), auto-rotate and Download picture |
| 9 | Landing page | Done: hero, live demo tabs, benefits, how it works, sign-up form; no sideways scrolling at phone width |
| 10 | Sign-ups and demo video | Done: sign-ups saved, rate limited (5 per hour), spam trap, admin list, outbox log, optional email. The video itself is for you to record: see `docs/DEMO_SCRIPT.md` |

## Tests
Two browser click-through scripts in `platform/tests/` (see the README). Last run: 15 of 15 and 11 of 11 passed.
They cover demo examples, the product picker, logo upload, Save and share, the shared link, the sign-up form,
the admin list and phone-width layouts. There are no unit tests for the API yet (planned for day 14).

## Known issues and notes
- Brand name "PreviewPrint" is a placeholder (landing page header and footer).
- The `seller` in a share link is only a label until real seller accounts exist (days 11 to 13).
- Anyone with a design link can view that design; this is intended for now.
- Mug print area (115 degrees wide, 72% of the height) is a placeholder; confirm the real size with your first seller.
- Mug designs saved before day 3b no longer open (they used one area, now two). Test data only.
- The sign-up rate limit is kept in memory: it resets when the server restarts, and it is per server process.
- Built-in products are replaced when `SEED_VERSION` in `main.py` goes up; edits made to them in the admin page are lost then. Use a new slug for your own variants.
- Logos on the wristband are printed flat; only text and stickers are embossed.
- Text styles use fonts found on most Windows and Mac computers (Arial Black, Impact, Georgia). They may look a little different on some phones.
- The sign-up form promises only "we will contact you soon", not a response time.
- Browsers cache JS files; press Ctrl+F5 if a page looks old.
- Nothing from day 3 onward is committed yet (only days 1 and 2).

## Next
Day 11: move from SQLite to PostgreSQL with migrations (Alembic), and add tenants and users tables.
