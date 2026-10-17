# Project status

Plan: SRS v2, 30 working days of about 1 hour. Updated at the end of every working session.

**Days 1 to 30 finished.** Overall build: about 77% (the 10 modules weighted equally). Schedule: 30 of 30 days done.
What exists: a seller signs up, is approved, sets up products (or uploads a 3D model), marks print areas, shares a link or embeds the customizer
on their own website, receives designs with print-ready files, and sees usage and an estimated invoice. The owner approves shops, sets plans, and downloads invoices.
What is **not** proven yet: the Docker image has never been built or run (the Docker engine was not running here), and no real seller has used it.
The next real step is not more code: it is the pilot (`docs/PILOT_KIT.md`).

## Module completion

| ID | Module | Done | What exists | Still to do |
| --- | --- | --- | --- | --- |
| M1 | Tenants and onboarding | 85% | Seller registration, shop link names, owner approval, pending / active / suspended, `pilot-shop` command for done-for-you setup | Email verification, inviting staff |
| M2 | Authentication and roles | 80% | Login, logout, scrypt passwords, server-side sessions, roles (owner, shop admin, staff), login and sign-up limits, forged-request header, **change password (ends other logins), `reset-password` command** | Emailed password reset, staff invites, two-step login |
| M3 | Customizer engine | 88% | 3D viewer, multi-line text, 8 text styles, 13 stickers, logos, colours, fonts, drag positioning, limits and validation, demo mode; built-in shapes and sellers' own 3D models | Inside and continuous messages, 2D fallback |
| M4 | Template library | 90% | Wristband and mug templates; product picker; per-product defaults | Real print sizes confirmed with a seller |
| M5 | Product and model setup | 88% | Create from a template or a 3D model; product editor; model upload with report; visual print-area editor; **real print size in mm per area** | Delete or replace a model, resizing options for own models |
| M6 | Embed and public API | 90% | **Public key, allowed websites (enforced by the browser with `frame-ancestors`), iframe page, `embed.js` loader, design id handed back (DOM event, form field, callback), your own order reference, secret-key API (`/api/v1`), key create / revoke / replace, docs** | Webhooks, a JavaScript SDK, browser (CORS) API |
| M7 | Artwork and print files | 85% | Image upload checks, originals kept, low-resolution warning, **print-file export: transparent PNG per print area at 300 dpi, relief map for emboss / deboss, customer originals, `design.json`, one .zip** | CMYK / PDF output, bleed and crop marks |
| M8 | Seller dashboard | 92% | Products, new product, editor, 3D models, **designs list (search, filter, paging), embed page, usage and plan page, account page**, owner screen | Staff invites, delete a model |
| M9 | Plans, usage, invoicing | 75% | **Daily counters (views, designs, exports) in India time, plans in `config.PLANS`, monthly estimate with GST, setup fee until paid, CSV invoices for the owner and for each seller, per-shop hourly cap on designs** | PDF invoices, online payment, enforcing plan limits, seller-chosen plans |
| M10 | Plugins (Shopify, WooCommerce) | 0% | Not planned before the first paying sellers | Later |
| - | Landing page and lead capture | 100% for v1 | Landing page, sign-up form, rate limit, spam trap, owner list, outbox log, optional email | Real brand name, Gujarati copy |

## Day log (days 21 to 30)

| Day | Goal | Result |
| --- | --- | --- |
| 21 | API keys and allowed websites | Done: migration `0002`; a public key per shop; a list of allowed websites (cleaned and validated, wildcards one level only); secret keys shown once and stored as a hash, up to 3, revocable; dashboard page |
| 22 | Embed code | Done: `/embed/<key>/<product>` served with a `frame-ancestors` header naming only the allowed websites; `embed.js` loader (resizes the frame); snippet generator in the dashboard. Tested with a second website on another port: the listed one shows it, an unlisted one is refused by the browser |
| 23 | Design id back to the host page | Done: messages to the host page only if it is on the list; `previewprint:design` DOM event, `data-pp-input` form field, `PreviewPrint.on`; `data-pp-ref` order reference saved with the design |
| 24 | Designs list | Done: search (words typed, order reference, design id, product), product filter, 20 per page, preview, source (share link / your website / your own test); `/api/v1/designs` for servers |
| 25 | Print-file export | Done: `/print.html?design=ID` draws each print area with the same code as the 3D preview; .zip with PNGs, relief maps, originals, `design.json`, README. Verified: valid zip, 1063 x 945 px for 90 x 80 mm at 300 dpi, transparent background |
| 26 | Usage events and page | Done: counters per shop and day; usage page with monthly numbers, plan meter and a per-day chart |
| 27 | Plan settings and invoice CSV | Done: three plans (edit in `config.py`), setup fee, GST; owner screen to set a shop's plan; CSV for all shops (owner) and for one shop (admin); spreadsheet-formula-safe |
| 28 | Security pass | Done: security headers on every answer, content policy with no inline scripts (the old admin page was fixed), password change, admin-key header crash fixed, picture pixel cap, preview-size cap, per-shop hourly design cap (stops a script running up a bill through a public key), key-guessing slowed, production start-up guard |
| 29 | Docker deploy, HTTPS, backups | Written: `platform/deploy/` (compose with PostgreSQL and Caddy, `.env.example`, `backup.sh`, `restore.sh`), health check, `docs/DEPLOY.md`. **Not built or run: needs a test on a throw-away server** |
| 30 | Pilot kit | Done: `docs/PILOT_KIT.md` (goals, who to approach, offer, onboarding checklist, WhatsApp messages in English and Gujarati, agreement, feedback form, support table), `docs/EMBED_AND_API.md` |

Earlier days (1 to 20): see git history. Days 11 to 20 built the database, accounts, isolation, dashboard, product editor, 3D model upload and the print-area editor.

## Tests
- `python -m pytest`: 113 tests, passing on SQLite and on PostgreSQL 16 (45 of them new for days 21 to 30). Removing a shop filter (designs, API, embed) was tried on purpose: the tests fail, then pass again once restored.
- Browser click-through scripts in `platform/tests/`: shopper side 15 of 15, seller journey 44 of 44, sign-up and phone layouts 11 of 11, **embed, designs, print files, usage, password and owner billing 49 of 49**.
- Not covered: the Docker image and Caddy (not run), email sending, a real phone, a real printer (print files were checked as files, not printed), more than one server process.

## Known issues and notes
- **Docker image never built here.** Do a first deploy on a spare server (`docs/DEPLOY.md`) before a seller depends on it. Restore a backup once to prove it works.
- Brand name "PreviewPrint" is a placeholder (landing page header and footer).
- The old file `platform/data/platform.db` (before day 11) is unused and can be deleted.
- No emailed password reset or email verification: use `python -m app.manage reset-password`.
- Rate limits and the per-shop design cap are kept in memory: they reset when the server restarts and are per process.
- A shop's public key is visible in its web page. Anyone can call the embed endpoints with it. The allowed-websites list stops other sites **showing** the customizer, not scripts calling it. The hourly cap (default 600 designs a shop, `TENANT_DESIGNS_PER_HOUR`) limits the damage; invoices are estimates the owner reviews.
- "Views" count every time a customer's browser loads a product (reloads and bots count); only "designs" are charged.
- Days are counted in India time (UTC+5:30). Months use the same calendar.
- The designs search looks at a shop's newest 2000 designs.
- Print files are drawn in the seller's browser (needs WebGL). They are RGB PNG, not CMYK or PDF, and have no bleed or crop marks. Check with your printer what they need.
- Anyone with a design link can view that design; this is intended. Seller 3D models and customer pictures are public by their random file address.
- Sellers' own 3D models show text on the mesh's flat UV map; a model with overlapping or mirrored UVs repeats the print. The print-area editor's map view shows this.
- Mug print area (115 degrees wide, 72% of the height) is a placeholder; confirm the real size with your first seller. Plan prices are placeholders too.
- Built-in products are refreshed when `SEED_VERSION` goes up; sellers' own copies are never changed.
- Browsers cache JS files; press Ctrl+F5 if a page looks old.
- Days 3 to 30 are not committed yet.

## Next
1. Commit, then try the deploy on a throw-away server (`docs/DEPLOY.md`).
2. Replace the placeholder brand name, confirm the mug's real printable size, and get one real 3D model.
3. Start the pilot with 3 to 5 Ahmedabad sellers (`docs/PILOT_KIT.md`). What they say decides what to build next (M10 plugins, PDF/CMYK print files, emailed password reset).
