"""Browser click-through checks. Needs: the server running on port 8800, Microsoft Edge, and `pip install websockets`.
Run from the platform folder:  python tests/browser_signup_and_mobile.py
The sign-up test adds one lead named "E2E Test Shop"; delete it afterwards (the admin page lists leads)."""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp import Browser

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")   # screenshots land here (git-ignored)
os.makedirs(OUT, exist_ok=True)
BASE = "http://localhost:8800"
results = []
def check(name, ok, extra=""):
    results.append(ok); print(("PASS " if ok else "FAIL ") + name + (f"  [{extra}]" if extra else ""))

FILL = """(v)=>{for(const [k,val] of Object.entries(v)){const e=document.querySelector('#'+k);e.value=val;e.dispatchEvent(new Event('input',{bubbles:true}));}}"""
SUBMIT = "document.querySelector('#lead').requestSubmit()"

async def main():
    async with Browser(1150, 900) as b:
        await b.goto(f"{BASE}/")
        # empty submit
        await b.js(SUBMIT); await asyncio.sleep(0.5)
        check("empty form shows a message", "shop name" in (await b.js("document.querySelector('#msg').textContent")))
        # bad phone
        await b.js(f"({FILL})({{business:'E2E Test Shop',name:'Tester',phone:'abc'}})"); await b.js(SUBMIT); await asyncio.sleep(0.5)
        check("bad phone is rejected on the page", "phone" in (await b.js("document.querySelector('#msg').textContent")).lower())
        check("bad field is highlighted", await b.js("document.querySelector('#phone').classList.contains('bad')"))
        # bad email
        await b.js(f"({FILL})({{phone:'+91 98765 43210',email:'nope'}})"); await b.js(SUBMIT); await asyncio.sleep(0.5)
        check("bad email is rejected on the page", "email" in (await b.js("document.querySelector('#msg').textContent")).lower())
        # valid
        await b.js(f"({FILL})({{email:'tester@example.com',sells:'mugs <b>x</b>'}})"); await b.js(SUBMIT); await asyncio.sleep(2)
        check("thank-you shown after a valid sign-up", await b.js("!document.querySelector('#thanks').hidden && document.querySelector('#lead').hidden"))
        await b.shot(os.path.join(OUT, "e_thanks.png"))

        # admin list
        await b.goto(f"{BASE}/admin.html", wait=2)
        await b.js("(()=>{const k=document.querySelector('#key');k.value='change-me';})()")
        await b.js("document.querySelector('#loadLeads').click()"); await asyncio.sleep(1.5)
        txt = await b.js("document.querySelector('#leads').innerText")
        check("admin lists the sign-up", "E2E Test Shop" in txt)
        check("typed markup is shown as plain text, not run", await b.js("document.querySelector('#leads b')") is None and "<b>x</b>" in txt)
        await b.js("document.querySelector('#key').value='wrong'"); await b.js("document.querySelector('#loadLeads').click()"); await asyncio.sleep(1)
        check("wrong admin key is refused", "admin key" in (await b.js("document.querySelector('#leadMsg').textContent")).lower())

    # phone-width layouts
    async with Browser(390, 844, port=9444) as m:
        for name, url in (("land", f"{BASE}/"), ("mug", f"{BASE}/s/ahmedabad-gifts/custom-printed-mug"), ("band", f"{BASE}/?product=custom-embossed-wristband")):
            await m.goto(url)
            sw = await m.js("document.documentElement.scrollWidth")
            check(f"no sideways scrolling on a phone: {name}", sw <= 392, f"scrollWidth={sw}")
            await m.shot(os.path.join(OUT, f"m_{name}.png"))
    print(f"\n{sum(results)}/{len(results)} checks passed")

asyncio.run(main())
