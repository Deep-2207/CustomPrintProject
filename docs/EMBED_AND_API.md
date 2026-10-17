# Embed and API guide (for a seller or their web developer)

Two ways to use the customizer on your own website, and one way to get the designs back to your server.

| You want | Use |
| --- | --- |
| Customers design the product on **your** website | The embed code (this page, part 1) |
| Your order system to know **which design** a customer made | The design id that the embed hands back (part 2) |
| Your server to **read** designs later (admin, packing slips, automation) | The API with a secret key (part 3) |
| Just share a link on WhatsApp or Instagram | No code needed: `https://YOUR-HOST/s/YOUR-SHOP/PRODUCT` |

## 1. Embed on your website

1. In the dashboard open **Embed on your site**.
2. Under **Allow your website**, list the website(s) that will show the customizer, one per line:
   `shop.example.com`, or `*.example.com` for every subdomain. While testing on your own computer add `localhost:3000` (use your port).
   Only the websites on this list can show it. Any other website sees an empty frame.
3. Pick a product. Copy the code. It looks like this:

```html
<div data-pp-product="photo-mug" data-pp-key="pk_xxxxxxxxxxxxxxxxxxxxxxxx" data-pp-input="#design_id"></div>
<script src="https://YOUR-HOST/embed.js" async></script>
```

4. Paste it where the customizer should appear. Add a hidden field to your order form so you receive the design id:

```html
<form action="/cart/add" method="post">
  <input type="hidden" id="design_id" name="design_id">
  ...
</form>
```

Optional attributes on the `div`:

| Attribute | Meaning |
| --- | --- |
| `data-pp-button="Add to my order"` | Text of the main button (max 40 characters) |
| `data-pp-ref="ORDER-1042"` | Your own reference. Saved with the design, searchable in the Designs list, and available from the API |
| `data-pp-design="a1b2c3d4e5f6"` | Open an earlier design for editing |
| `data-pp-input="#design_id"` | A form field (CSS selector) that receives the design id when the customer saves |
| `data-pp-height="720"` | Starting height in pixels (the frame then resizes itself) |

The public key (`pk_...`) is **not a secret**: it is meant to be in your web page. What protects you is the allowed-websites list.

## 2. Getting the design id back

When the customer presses the button, the design is saved and your page is told. Listen on the page:

```js
document.addEventListener('previewprint:design', e => {
  console.log(e.detail.designId);    // "a1b2c3d4e5f6"  (also written into data-pp-input)
  console.log(e.detail.previewUrl);  // picture of the finished product (PNG)
  console.log(e.detail.text);        // the words the customer typed
});
```

`previewprint:ready` fires when the customizer has loaded. `window.PreviewPrint.on('design', fn)` does the same once `embed.js` has loaded
(the snippet loads it with `async`, so use the DOM event if your code runs early).

Store `designId` with the order. Later, a design opens for editing at `https://YOUR-HOST/s/YOUR-SHOP/PRODUCT?design=DESIGN_ID`.

## 3. API for your server (secret key)

Create a secret key under **Embed on your site, API keys for your server**. It is shown **once**; copy it somewhere safe. A shop can have 3.
**Never put a secret key in a web page or an app.** If one leaks, revoke it in the dashboard (it stops working at once) and make a new one.

```bash
# newest designs first; limit up to 100; pass before=<design id> for the next page
curl "https://YOUR-HOST/api/v1/designs?limit=20" -H "Authorization: Bearer sk_..."

# one design, including every layer (text, fonts, sticker ids, positions)
curl "https://YOUR-HOST/api/v1/designs/DESIGN_ID" -H "Authorization: Bearer sk_..."

# the designs for one of your orders (the data-pp-ref you passed)
curl "https://YOUR-HOST/api/v1/designs?ref=ORDER-1042" -H "Authorization: Bearer sk_..."

# your published products
curl "https://YOUR-HOST/api/v1/products" -H "Authorization: Bearer sk_..."
```

A design looks like:

```json
{ "id": "a1b2c3d4e5f6", "product": "photo-mug", "created_at": "2026-10-17T07:09:50", "source": "embed", "ref": "ORDER-1042",
  "text": "Deep", "preview_url": "https://YOUR-HOST/files/designs/a1b2c3d4e5f6.png", "open_url": "https://YOUR-HOST/s/shop/photo-mug?design=a1b2c3d4e5f6" }
```

Limits: 120 calls per minute per key; repeated wrong keys are slowed down. A key only ever sees its own shop's designs.

**Print files** (the transparent PNG per print area at 300 dpi, plus the customer's original pictures) are downloaded from the dashboard:
**Designs, Print files, Download**. Set each print area's real width and height in millimetres in the product editor first.

## What the customer sees, and what is saved

Every design is checked on our server again (letters, lines, fonts, stickers, picture type and size), whatever the browser sent.
A design saved by you while testing your own products is marked "Your own test" and is not counted on your invoice.

## Troubleshooting

| Problem | Cause |
| --- | --- |
| Empty frame / "refused to connect" | Your website is not on the allowed list, or you typed `www.` but the page is on the bare domain (add both) |
| "This product is not available" | The product is not published, the key is wrong or was replaced, or the shop is not active |
| Works on `localhost` but not live | Add the live domain; use `https` |
| The design id field stays empty | The `data-pp-input` selector does not match the field, or the customer has not pressed the button |
| 401 from the API | Missing `Bearer`, a public key instead of a secret key, or a revoked key |
