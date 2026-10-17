"""Browser click-through for days 21 to 30: embed on another website, the designs list, print files, usage, account, owner billing.

Needs: the server running on port 8800 started with OWNER_EMAIL=owner@example.com and OWNER_PASSWORD=Owner-pass-for-dev-2026
(and REGISTER_LIMIT_PER_HOUR=50), Microsoft Edge, and `pip install websockets pillow`.
Run from the platform folder:  python tests/browser_embed_and_billing.py
It creates one "Embed Test Shop ..." in whatever database the server uses, and serves a small fake shop website on port 8899.
"""
import asyncio
import base64
import http.server
import io
import json
import os
import sys
import threading
import time
import uuid
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp import Browser

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
HOSTDIR = os.path.join(OUT, "host")
os.makedirs(HOSTDIR, exist_ok=True)
BASE = "http://localhost:8800"
OWNER = ("owner@example.com", "Owner-pass-for-dev-2026")
results = []
SET = "(sel,v)=>{const e=document.querySelector(sel);e.value=v;e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));}"


def check(name, ok, extra=""):
    results.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{extra}]" if extra else ""))


async def wait(b, expr, timeout=15.0):
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


def api(method, path, body=None):
    """fetch() inside the page, so the login cookie and the forgery header go along."""
    return ("(async()=>{const r=await fetch(%r,{method:%r,headers:{'X-Requested-With':'fetch','Content-Type':'application/json'},body:%s});"
            "let j=null;try{j=await r.json()}catch(e){};return {status:r.status,body:j}})()") % (path, method, json.dumps(json.dumps(body)) if body is not None else "undefined")


def serve():
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=HOSTDIR, **k)

        def log_message(self, *a):
            pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 8899), Quiet)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


HOST_PAGE = """<!doctype html><meta charset=utf-8><title>Fake shop</title>
<body style="font-family:sans-serif"><h1>Ahmedabad Gift Shop (test host)</h1>
<form><input type=hidden id=design_id name=design_id></form>
%(snippet)s
<script>window.__events=[];
// The snippet loads embed.js with "async", so PreviewPrint exists only after it has loaded; the DOM events work at any time.
document.addEventListener('previewprint:ready',e=>__events.push({t:'ready',d:e.detail}));
document.addEventListener('previewprint:design',e=>__events.push({t:'dom',id:e.detail.designId}));
window.addEventListener('load',()=>setTimeout(()=>PreviewPrint.on('design',d=>__events.push({t:'design',d})),200));</script>"""


async def main():
    tag = uuid.uuid4().hex[:5]
    email, password = f"embed-{tag}@example.com", "Browser-test-passphrase-9"
    srv = serve()
    async with Browser(1300, 900, port=9611) as s, Browser(1200, 800, port=9612) as o, Browser(1100, 900, port=9613) as h:
        # ---------------------------------------------------------- set up a shop with a published product
        await s.goto(f"{BASE}/account.html", wait=1.5)
        r = await s.js(api("POST", "/api/auth/register", {"business": f"Embed Test Shop {tag}", "name": "Asha", "email": email, "password": password}))
        check("register through the API", r["status"] == 200, r["body"] if r["status"] != 200 else "")
        tid, shop = r["body"]["tenant"]["id"], r["body"]["tenant"]["slug"]
        await o.goto(f"{BASE}/account.html", wait=1.5)
        await o.js(api("POST", "/api/auth/login", {"email": OWNER[0], "password": OWNER[1]}))
        await o.goto(f"{BASE}/owner.html", wait=2)
        check("owner approves the shop", (await o.js(api("POST", f"/api/owner/tenants/{tid}/status", {"status": "active"})))["status"] == 200)
        prod = await s.js(api("POST", "/api/seller/products", {"name": "Photo mug", "slug": "photo-mug", "template": "custom-printed-mug"}))
        pid = prod["body"]["id"]
        await s.js(api("POST", f"/api/seller/products/{pid}/publish", {"published": True}))
        # real size of the front print area, so the print file is tied to millimetres
        cfg = prod["body"]["config"]
        edit = {k: cfg[k] for k in ("name", "colors", "imprint_colors", "fonts", "zones", "defaults", "sample", "placeholder", "price")} | {"sizes": cfg.get("sizes", [])}
        edit["zones"][0]["print_w_mm"], edit["zones"][0]["print_h_mm"] = 90, 80
        check("seller saves the real print size", (await s.js(api("PUT", f"/api/seller/products/{pid}", edit)))["status"] == 200)

        # ---------------------------------------------------------- Day 21/22: the Embed page
        await s.goto(f"{BASE}/dashboard.html#/embed", wait=2.5)
        check("embed page shows a public key", await wait(s, "document.body.innerText.includes('pk_')"))
        check("no website allowed yet is explained", "blocked everywhere" in await s.js("document.body.innerText"))
        await setv(s, "#dm", "not a website\nlocalhost:8899")
        await s.js("document.querySelector('[data-act=save-domains]').click()")
        check("a bad website is refused with a message", await wait(s, "document.querySelector('#dm-err') && !document.querySelector('#dm-err').hidden && document.querySelector('#dm-err').innerText.includes('valid website')"))
        await setv(s, "#dm", "localhost:8899")
        await s.js("document.querySelector('[data-act=save-domains]').click()")
        check("saving the website works", await wait(s, "document.body.innerText.includes('1 website(s) allowed')"))
        check("the code snippet names the product and the key", await wait(s, "document.querySelector('#sn-code').textContent.includes('data-pp-product=\"photo-mug\"') && document.querySelector('#sn-code').textContent.includes('data-pp-key=\"pk_')"))
        await setv(s, "#sn-b", "Add to my order")
        snippet = await s.js("document.querySelector('#sn-code').textContent")
        check("button text appears in the snippet", 'data-pp-button="Add to my order"' in snippet)
        await s.js("document.querySelector('[data-act=new-secret]').click()")
        check("a new secret key is shown once", await wait(s, "document.querySelector('#new-secret') && document.querySelector('#new-secret').textContent.startsWith('sk_')"))
        secret = await s.js("document.querySelector('#new-secret').textContent")
        await s.shot(os.path.join(OUT, "e_embed_page.png"))
        await s.js("location.reload()"); await asyncio.sleep(3)
        check("after a reload the secret key is gone and only its start is listed", secret not in await s.js("document.body.innerText") and (secret[:10] in await s.js("document.body.innerText")))

        # ---------------------------------------------------------- Day 22/23: a different website embeds it
        open(os.path.join(HOSTDIR, "host.html"), "w", encoding="utf8").write(HOST_PAGE % {"snippet": snippet})
        await h.goto("http://localhost:8899/host.html", wait=5)
        check("the host page got a 'ready' message from the embedded customizer", await wait(h, "window.__events.some(e => e.t === 'ready')", 20))
        check("the iframe resized itself to the content", await h.js("parseInt(document.querySelector('iframe').style.height) > 500"))
        check("the button text from the snippet is used", await wait(h, "true") and (await h.frame_js("/embed/", "document.querySelector('#add').textContent")) == "Add to my order")
        check("the embedded page hides the seller line and picker", await h.frame_js("/embed/", "getComputedStyle(document.querySelector('#seller-line')).display") == "none")
        await h.frame_js("/embed/", "(()=>{const t=document.querySelector('textarea[data-f=text]')||document.querySelector('input[data-f=text]');t.value='Deep';t.dispatchEvent(new Event('input',{bubbles:true}));})()")
        await asyncio.sleep(1)
        await h.frame_js("/embed/", "document.querySelector('#add').click()")
        check("saving inside the iframe tells the host page", await wait(h, "window.__events.some(e => e.t === 'design')", 15))
        ev = await h.js("window.__events.find(e => e.t === 'design').d")
        check("the message carries a design id and preview address", ev and len(ev.get("designId", "")) == 12 and ev["previewUrl"].endswith(ev["designId"] + ".png") and ev["text"] == "Deep", str(ev))
        check("the hidden form field received the design id", await h.js("document.querySelector('#design_id').value") == ev["designId"])
        check("the DOM event fired on the container", await h.js("window.__events.some(e => e.t === 'dom')"))
        check("the saved note shows inside the iframe", await h.frame_js("/embed/", "!document.querySelector('#saved-note').hidden"))
        await h.shot(os.path.join(OUT, "e_host_page.png"))

        # a website that is NOT on the list cannot show it
        await h.goto("http://127.0.0.1:8899/host.html", wait=5)
        await asyncio.sleep(2)
        check("a website that is not allowed gets no customizer", await h.js("window.__events.length") == 0)
        blocked = await h.js("(()=>{try{return document.querySelector('iframe').contentDocument===null||document.querySelector('iframe').contentWindow.location.href==='about:blank'}catch(e){return true}})()")
        check("the browser refused to show the iframe", blocked)
        await h.shot(os.path.join(OUT, "e_host_blocked.png"))

        # ---------------------------------------------------------- Day 24: the Designs list
        await s.goto(f"{BASE}/dashboard.html#/designs", wait=2.5)
        check("the design appears in the list", await wait(s, "document.querySelector('.dc') && document.querySelector('.dc').innerText.includes('Deep')"))
        check("it is marked as coming from the shop's website", "Your website" in await s.js("document.querySelector('.dc').innerText"))
        await setv(s, "#d-q", "zzz-nothing")
        check("searching for something else shows no designs", await wait(s, "document.querySelector('#d-list').innerText.includes('No designs match')"))
        await setv(s, "#d-q", "deep")
        check("searching for the typed words finds it", await wait(s, "document.querySelectorAll('.dc').length === 1"))
        await s.shot(os.path.join(OUT, "e_designs.png"))

        # ---------------------------------------------------------- Day 25: print files
        did = ev["designId"]
        await s.goto(f"{BASE}/print.html?design={did}", wait=3)
        check("print page draws the area on a transparent background", await wait(s, "document.querySelectorAll('.checker canvas').length >= 1", 25))
        dims = await s.js("(()=>{const c=document.querySelector('.checker canvas');return [c.width,c.height]})()")
        check("the file is 300 dpi for 90 x 80 mm", dims == [1063, 945], str(dims))
        check("the real size is shown", "90 × 80 mm" in await s.js("document.body.innerText"))
        await s.js("""(()=>{const oc=URL.createObjectURL;URL.createObjectURL=b=>{window.__blob=b;return oc.call(URL,b)};
            HTMLAnchorElement.prototype.click=function(){window.__dl=this.download}})()""")
        await s.js("document.querySelector('#dl').click()")
        check("download starts", await wait(s, "!!(window.__dl && window.__blob)", 25))
        b64 = await s.js("""(async()=>{const buf=new Uint8Array(await window.__blob.arrayBuffer());let s='';for(let i=0;i<buf.length;i+=8192)s+=String.fromCharCode.apply(null,buf.subarray(i,i+8192));return btoa(s)})()""")
        zf = zipfile.ZipFile(io.BytesIO(base64.b64decode(b64)))
        names = zf.namelist()
        check("the zip is valid (checksums match)", zf.testzip() is None, str(names))
        check("it holds the area picture, the details and a readme", all(n in names for n in ("front.png", "design.json", "README.txt")), str(names))
        check("the file is named after the design", await s.js("window.__dl") == f"design-{did}.zip")
        from PIL import Image
        im = Image.open(io.BytesIO(zf.read("front.png"))).convert("RGBA")
        alpha = im.getchannel("A")
        check("the picture has transparent pixels and printed pixels", alpha.getextrema()[0] == 0 and alpha.getextrema()[1] == 255, str(alpha.getextrema()))
        check("the picture size matches", im.size == (1063, 945), str(im.size))
        meta = json.loads(zf.read("design.json"))
        check("design.json has the size and the text", meta["design_id"] == did and meta["areas"][0]["size_mm"] == [90, 80] and meta["areas"][0]["dpi"] == 300
              and any(l.get("text") == "Deep" for l in meta["areas"][0]["layers"]), str(meta)[:200])
        await asyncio.sleep(1)
        await s.shot(os.path.join(OUT, "e_print.png"))

        # ---------------------------------------------------------- Day 26/27: usage and plan
        await s.goto(f"{BASE}/dashboard.html#/usage", wait=2.5)
        stats = await s.js("document.querySelector('.stats').innerText")
        check("usage shows one design, a view and one export", "1\ndesigns saved" in stats and "1\nprint-file downloads" in stats, repr(stats))
        check("the pilot plan is shown with its included designs", "Pilot" in await s.js("document.body.innerText") and "100 designs included" in await s.js("document.body.innerText"))
        check("a bar chart is drawn for today", await s.js("document.querySelectorAll('.bar').length") == 1)
        await s.shot(os.path.join(OUT, "e_usage.png"))

        # ---------------------------------------------------------- Day 28: change password
        await s.goto(f"{BASE}/dashboard.html#/account", wait=2)
        await setv(s, "#pw-c", "totally-wrong-pass"); await setv(s, "#pw-n", "Another-long-passphrase-7")
        await s.js("document.querySelector('#pw').requestSubmit()")
        check("a wrong current password is explained", await wait(s, "document.querySelector('#pw-err').innerText.includes('not correct')"))
        await setv(s, "#pw-c", password); await setv(s, "#pw-n", "short")
        await s.js("document.querySelector('#pw').requestSubmit()")
        check("a weak new password is explained", await wait(s, "document.querySelector('#pw-err').innerText.includes('10 characters')"))
        await setv(s, "#pw-n", "Another-long-passphrase-7")
        await s.js("document.querySelector('#pw').requestSubmit()")
        check("the password changes", await wait(s, "document.querySelector('#toast').innerText.includes('Password changed')"))

        # ---------------------------------------------------------- Day 27: owner plans and invoices
        await o.goto(f"{BASE}/owner.html", wait=2.5)
        check("owner sees the shop in the billing table", await wait(o, f"document.querySelector('#billing').innerText.includes('Embed Test Shop {tag}')"))
        await o.js(f"""(()=>{{const tr=[...document.querySelectorAll('#billing tr')].find(r=>r.innerText.includes('Embed Test Shop {tag}'));
            tr.querySelector('[data-plan]').value='starter';tr.querySelector('[data-setup]').value='2000';tr.querySelector('[data-save-plan]').click()}})()""")
        check("saving a plan updates the total with GST", await wait(o, f"[...document.querySelectorAll('#billing tr')].find(r=>r.innerText.includes('Embed Test Shop {tag}'))?.innerText.includes('3,539')"), "999+2000 = 2999 + 18% = 3,538.82")
        csv = await o.js("(async()=>(await (await fetch(document.querySelector('#csv').href)).text()))()")
        check("the invoice CSV lists the shop", f"embed-test-shop-{tag}" in csv.lower() and "starter" in csv)
        await o.shot(os.path.join(OUT, "e_owner_billing.png"))

        # the shop sees the new plan
        await s.goto(f"{BASE}/dashboard.html#/usage", wait=2.5)
        check("the seller sees the plan the owner set", "Starter" in await s.js("document.body.innerText") and "3,539" in await s.js("document.body.innerText"))

        # ---------------------------------------------------------- the secret key works from outside, and a revoked one stops
        import urllib.error
        import urllib.request

        def call(key):
            req = urllib.request.Request(f"{BASE}/api/v1/designs", headers={"Authorization": f"Bearer {key}"})
            try:
                with urllib.request.urlopen(req) as r:
                    return r.status, json.load(r)
            except urllib.error.HTTPError as e:
                return e.code, None
        code, body = call(secret)
        check("the secret key lists the shop's designs", code == 200 and [d["id"] for d in body] == [did], str(code))
        await s.goto(f"{BASE}/dashboard.html#/embed", wait=2)
        await s.js("window.confirm = () => true")
        await s.js("document.querySelector('[data-act=revoke]').click()")
        check("revoking removes the key from the list", await wait(s, "document.body.innerText.includes('No secret keys yet')"))
        check("the revoked key no longer works", call(secret)[0] == 401)
    srv.shutdown()
    print(f"\n{sum(results)} of {len(results)} checks passed")
    sys.exit(0 if all(results) else 1)


asyncio.run(main())
