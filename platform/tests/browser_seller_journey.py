"""Browser click-through of the whole seller journey (days 12 to 20).

Needs: the server running on port 8800 started with OWNER_EMAIL=owner@example.com and
OWNER_PASSWORD=Owner-pass-for-dev-2026, Microsoft Edge, and `pip install websockets`.
Run from the platform folder:  python tests/browser_seller_journey.py
It creates one test shop ("Browser Test Shop ...") in whatever database the server uses.
"""
import asyncio
import os
import sys
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp import Browser

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)
SAMPLE = os.path.join(HERE, "..", "samples", "sample-bottle.glb")
BASE = "http://localhost:8800"
OWNER = ("owner@example.com", "Owner-pass-for-dev-2026")
results = []

SET = "(sel,v)=>{const e=document.querySelector(sel);e.value=v;e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));}"


def check(name, ok, extra=""):
    results.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{extra}]" if extra else ""))


async def wait(b, expr, timeout=12.0):
    end = time.time() + timeout
    while time.time() < end:
        try:
            if await b.js(expr):
                return True
        except Exception:
            pass
        await asyncio.sleep(0.25)
    return False


async def setv(b, sel, value):
    await b.js(f"({SET})({sel!r}, {value!r})")


async def main():
    tag = uuid.uuid4().hex[:5]
    email = f"seller-{tag}@example.com"
    password = "Browser-test-passphrase-9"

    async with Browser(1300, 900, port=9601) as s, Browser(1200, 800, port=9602) as o:
        # ---------------------------------------------------------- Day 12: register
        await s.goto(f"{BASE}/account.html#register", wait=2)
        await setv(s, "#r-business", f"Browser Test Shop {tag}")
        await setv(s, "#r-name", "Asha Patel")
        await setv(s, "#r-email", email)
        await setv(s, "#r-pass", "short")
        await s.js("document.querySelector('#register').requestSubmit()")
        await asyncio.sleep(1)
        check("weak password shows a message and stays on the page", "10 characters" in (await s.js("document.querySelector('#r-err').innerText")) and "account.html" in await s.js("location.href"))
        slug = await s.js("document.querySelector('#r-slug').value")
        check("shop link name is suggested from the business name", slug.startswith("browser-test-shop"), slug)
        await setv(s, "#r-pass", password)
        await s.js("document.querySelector('#register').requestSubmit()")
        check("registering lands on the dashboard", await wait(s, "location.pathname === '/dashboard.html'"))
        await asyncio.sleep(1.5)
        check("pending banner is shown", await wait(s, "document.querySelector('#banner').innerText.includes('waiting for approval')"))
        check("shop name appears in the sidebar", f"Browser Test Shop {tag}" in await s.js("document.querySelector('#who-shop').innerText"))
        await s.js("location.hash = '#/new'"); await asyncio.sleep(1.2)
        check("pending shop cannot create products (button disabled)", await s.js("document.querySelector('#np .btn').disabled"))

        # ---------------------------------------------------------- Day 15: owner approves
        await o.goto(f"{BASE}/account.html", wait=2)
        await setv(o, "#l-email", OWNER[0]); await setv(o, "#l-pass", OWNER[1])
        await o.js("document.querySelector('#login').requestSubmit()")
        check("owner login goes to the owner page", await wait(o, "location.pathname === '/owner.html'"))
        await asyncio.sleep(1.5)
        check("owner sees the new shop waiting", await wait(o, f"document.querySelector('#tenants').innerText.includes('Browser Test Shop {tag}')"))
        await o.js(f"[...document.querySelectorAll('#tenants tr')].find(r => r.innerText.includes('Browser Test Shop {tag}')).querySelector('[data-set=active]').click()")
        check("approved shop leaves the waiting list", await wait(o, f"!document.querySelector('#tenants').innerText.includes('Browser Test Shop {tag}')"))
        await o.shot(os.path.join(OUT, "j_owner.png"))

        # ---------------------------------------------------------- Day 16: create a product from a template
        await s.goto(f"{BASE}/dashboard.html#/products", wait=2)
        check("approved: no pending banner", await s.js("document.querySelector('#banner').innerText.trim() === ''"))
        await s.js("location.hash = '#/new'"); await asyncio.sleep(1.2)
        await s.js("document.querySelector('input[name=src][value=\"t:custom-printed-mug\"]').click()")
        await setv(s, "#np-name", "Photo Mug")
        check("link name follows the product name", await s.js("document.querySelector('#np-slug').value") == "photo-mug")
        await s.js("document.querySelector('#np').requestSubmit()")
        check("product created and editor opens", await wait(s, "location.hash.startsWith('#/product/')"))
        await asyncio.sleep(1.5)
        pid = int((await s.js("location.hash")).split("/")[-1])
        check("editor shows both mug print areas", await s.js("document.querySelectorAll('.zone').length") == 2)
        await s.shot(os.path.join(OUT, "j_editor.png"), full=True)

        # ---------------------------------------------------------- Day 17: edit and save
        await setv(s, "#e-name", "Photo Mug Deluxe")
        await s.js("document.querySelector('[data-act=add-colors]').click()"); await asyncio.sleep(0.4)
        await s.js("""(()=>{const rows=[...document.querySelectorAll('[data-list=colors][data-k=name]')];const last=rows[rows.length-1];last.value='Sage';last.dispatchEvent(new Event('input',{bubbles:true}));
                       const hx=[...document.querySelectorAll('[data-list=colors][data-k=hex]')].pop();hx.value='#9caf88';hx.dispatchEvent(new Event('input',{bubbles:true}));})()""")
        await s.js(f"({SET})('[data-z=\"0\"][data-k=max_chars]', '20')")
        await s.js("document.querySelector('[data-act=save]').click()")
        check("Save shows a confirmation", await wait(s, "document.querySelector('#toast').innerText === 'Saved'"))
        saved = await s.js(f"fetch('/api/seller/products/{pid}').then(r=>r.json()).then(j=>({{name:j.name,colors:j.config.colors.length,max:j.config.zones[0].max_chars}}))")
        check("changes were stored", saved == {"name": "Photo Mug Deluxe", "colors": 9, "max": 20}, str(saved))
        # a bad edit is explained, not lost
        await s.js("document.querySelector('[data-act=del-colors][data-i=\"0\"]').click()")
        for _ in range(8):
            await s.js("document.querySelector('[data-act=del-colors]').click()")
            await asyncio.sleep(0.15)
        await s.js("document.querySelector('[data-act=save]').click()")
        check("saving with no colours shows a clear message", await wait(s, "document.querySelector('#ed-err').innerText.toLowerCase().includes('at least one')"))
        await s.goto(f"{BASE}/dashboard.html#/product/{pid}", wait=2)     # discard the bad edit

        # ---------------------------------------------------------- publish, then shop from the link
        await s.js("document.querySelector('[data-act=publish]').click()")
        check("Publish switches the product to Published", await wait(s, "document.querySelector('#state').innerText === 'Published'"))
        await s.goto(f"{BASE}/s/{slug}/photo-mug", wait=4)
        check("shopper link opens the customizer", await s.js("typeof cz !== 'undefined' && cz.meshes.size > 0"))
        check("seller's change (20 letters) applies for shoppers", "/ 20" in await s.js("document.querySelector('#c-front').innerText"))
        await s.js(f"({SET})('#t-front', 'Deep\\nPatel')"); await asyncio.sleep(0.8)
        await s.js("document.querySelector('#add').click()")
        check("shopper can save a design on the seller's product", await wait(s, "!document.querySelector('#share').hidden"))
        await s.shot(os.path.join(OUT, "j_share.png"))

        # ---------------------------------------------------------- Day 18: upload a 3D model
        await s.goto(f"{BASE}/dashboard.html#/models", wait=2)
        await s.set_files("#file", [os.path.abspath(SAMPLE)])
        check("model upload shows its report", await wait(s, "document.querySelector('#view').innerText.includes('Bottle Body')"))
        check("report lists the parts and says they can be printed", "Yes" in await s.js("document.querySelector('#view').innerText"))
        # a bad file is explained
        bad = os.path.join(OUT, "not-a-model.glb"); open(bad, "wb").write(b"this is not a model")
        await s.set_files("#file", [bad]); await asyncio.sleep(1.5)
        check("a bad file is refused with a message", await wait(s, "!document.querySelector('#up-err').hidden"))
        await s.shot(os.path.join(OUT, "j_models.png"), full=True)

        # ---------------------------------------------------------- new product from the model
        await s.goto(f"{BASE}/dashboard.html#/new", wait=2)
        await s.js("document.querySelector('input[name=src][value^=\"m:\"]').click()")
        await setv(s, "#np-name", "Bottle")
        await s.js("document.querySelector('#np').requestSubmit()")
        check("product from the model is created", await wait(s, "location.hash.startsWith('#/product/')"))
        await asyncio.sleep(1.5)
        bid = int((await s.js("location.hash")).split("/")[-1])
        check("new model product starts without print areas", "No print areas yet" in await s.js("document.querySelector('#view').innerText"))

        # ---------------------------------------------------------- Days 19 and 20: the print-area editor
        await s.goto(f"{BASE}/zone-editor.html?product={bid}", wait=3)
        check("editor loads the 3D model and lists its parts", await wait(s, "window.ze && ze.parts.length >= 2"))
        names = await s.js("ze.parts.map(p => p.name)")
        check("parts are named the way three.js names them", "Bottle_Body" in names and "Cap" in names, str(names))
        await s.js("document.querySelector('[data-part=\"Bottle_Body\"]').click()")
        await s.js("document.querySelector('#add').click()")
        check("adding a print area selects it for adjusting", await wait(s, "!document.querySelector('#adjust').hidden && ze.draft.zones.length === 1"))
        a0 = await s.js("ze.draft.zones[0].aspect")
        check("surface shape was measured from the model (about 2 for this bottle)", 1.6 < a0 < 2.4, f"{a0:.2f}")
        for k, v in (("u0", 20), ("u1", 80), ("y0", 30), ("y1", 70)):
            await s.js(f"({SET})('#z-{k}', '{v}')")
        await asyncio.sleep(0.5)
        z = await s.js("ze.draft.zones[0]")
        check("sliders move the print area", (z["u0"], z["u1"], z["y0"], z["y1"]) == (0.2, 0.8, 0.3, 0.7), str((z["u0"], z["u1"], z["y0"], z["y1"])))
        await s.js(f"({SET})('#z-u0', '95')")      # drag the left edge past the right edge
        z = await s.js("ze.draft.zones[0]")
        check("an area cannot be dragged smaller than a minimum", z["u1"] - z["u0"] >= 0.039, f"{z['u0']:.2f}-{z['u1']:.2f}")
        await s.js(f"({SET})('#z-u0', '20')"); await s.js(f"({SET})('#z-u1', '80')")
        await s.js(f"({SET})('#z-label', 'Label')")
        await s.js(f"({SET})('#sample', 'BOTTLE 500ML')"); await asyncio.sleep(0.8)
        await s.shot(os.path.join(OUT, "j_zone_editor.png"))
        check("unsaved changes are flagged", "Unsaved" in await s.js("document.querySelector('#dirty').innerText"))
        await s.js("document.querySelector('#save').click()")
        check("saving print areas confirms", await wait(s, "document.querySelector('#toast').innerText === 'Saved'"))
        check("the unsaved flag clears", await s.js("document.querySelector('#dirty').innerText") == "")
        await s.goto(f"{BASE}/zone-editor.html?product={bid}", wait=3)
        check("print areas persist after reloading the editor", await wait(s, "window.ze && ze.draft.zones.length === 1 && ze.draft.zones[0].label === 'Label'"))

        # ---------------------------------------------------------- publish the bottle and shop from the link
        await s.goto(f"{BASE}/dashboard.html#/product/{bid}", wait=2)
        await s.js("document.querySelector('[data-act=publish]').click()")
        check("bottle product publishes", await wait(s, "document.querySelector('#state').innerText === 'Published'"))
        await s.goto(f"{BASE}/s/{slug}/bottle", wait=5)
        check("shoppers get the 3D bottle with its print area", await s.js("cz.meshes.size >= 1 && cz.product.zones.length === 1"))
        await s.js(f"({SET})('#t-area-1', 'Fresh\\nWater')"); await asyncio.sleep(1.0)
        await s.shot(os.path.join(OUT, "j_bottle.png"))

        # ---------------------------------------------------------- phone width
        await s.resize(390, 844)
        for name, url in (("products", f"{BASE}/dashboard.html#/products"), ("editor", f"{BASE}/dashboard.html#/product/{pid}"),
                          ("models", f"{BASE}/dashboard.html#/models"), ("zone editor", f"{BASE}/zone-editor.html?product={bid}"),
                          ("login", f"{BASE}/account.html")):
            await s.goto(url, wait=3.5)
            sw = await s.js("document.documentElement.scrollWidth")
            check(f"no sideways scrolling on a phone: {name}", sw <= 392, f"scrollWidth={sw}")
            if name in ("editor", "zone editor"):
                await s.shot(os.path.join(OUT, f"j_phone_{name.replace(' ', '_')}.png"))
        await s.resize(1300, 900)

        # ---------------------------------------------------------- logging out
        await s.goto(f"{BASE}/dashboard.html", wait=2)
        await s.js("document.querySelector('#logout').click()")
        check("logging out returns to the login page", await wait(s, "location.pathname === '/account.html'"))
        await s.goto(f"{BASE}/dashboard.html", wait=2)
        check("dashboard is closed to logged-out visitors", await wait(s, "location.pathname === '/account.html'"))

    print(f"\n{sum(results)}/{len(results)} checks passed")
    return all(results)


sys.exit(0 if asyncio.run(main()) else 1)
