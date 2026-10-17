"""Browser click-through checks. Needs: the server running on port 8800, Microsoft Edge, and `pip install websockets`.
Run from the platform folder:  python tests/browser_flows.py
The sign-up test adds one lead named "E2E Test Shop"; delete it afterwards (the admin page lists leads)."""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp import Browser
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")   # screenshots land here (git-ignored)
os.makedirs(OUT, exist_ok=True)
BASE = "http://localhost:8800"

# a simple 600x600 logo with transparent corners
logo = os.path.join(OUT, "logo.png")
im = Image.new("RGBA", (600, 600), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
d.ellipse((20, 20, 580, 580), fill=(220, 30, 80, 255)); d.rectangle((200, 200, 400, 400), fill=(255, 255, 255, 255))
im.save(logo)

results = []
def check(name, ok, extra=""):
    results.append(ok); print(("PASS " if ok else "FAIL ") + name + (f"  [{extra}]" if extra else ""))

async def main():
    async with Browser(1150, 1000) as b:
        # ---- Day 8: demo presets ----
        await b.goto(f"{BASE}/?product=custom-printed-mug&demo=1")
        check("demo bar visible", await b.js("!document.querySelector('#demo').hidden"))
        check("mug starts with the bubble style", await b.js("cz.state.zones.front.tpl") == "bubble")
        await b.js("document.querySelector('[data-demo=\"0\"]').click()")
        await asyncio.sleep(1.2)
        txt = await b.js("cz.state.zones.front.text")
        check("preset 'World's best dad' loads text", txt == "WORLD'S\nBEST\nDAD", repr(txt))
        check("preset sets back text and style", await b.js("cz.state.zones.back.tpl") == "script")
        check("panel shows the preset text", await b.js("document.querySelector('#t-front').value") == "WORLD'S\nBEST\nDAD")
        await b.shot(os.path.join(OUT, "e_demo.png"))
        await b.js("document.querySelector('#spin').click()")
        check("auto-rotate switches on", await b.js("cz.controls.autoRotate") is True)

        # ---- Day 5: picker carries the text ----
        await b.goto(f"{BASE}/?product=custom-printed-mug")
        await b.js("(()=>{const t=document.querySelector('#t-front');t.value='Hello';t.dispatchEvent(new Event('input',{bubbles:true}));})()")
        await b.js("document.querySelector('#picker a:not(.on)').click()")
        await asyncio.sleep(4)
        url = await b.js("location.href")
        check("picker navigated to the wristband", "custom-embossed-wristband" in url, url)
        check("text carried to the wristband front", await b.js("cz.state.zones.front.text") == "Hello")
        check("wristband uses its own default colour", await b.js("cz.state.bodyColor") == "#1fb5e8")

        # ---- Day 7: logo upload on both products ----
        for slug, zone in (("custom-printed-mug", "front"), ("custom-embossed-wristband", "front")):
            await b.goto(f"{BASE}/?product={slug}")
            await b.set_files(f'[data-up="{zone}"]', [logo])
            await asyncio.sleep(2.5)
            has = await b.js(f"!!cz.state.zones.{zone}.image")
            check(f"logo uploaded on {slug}", has)
            await b.shot(os.path.join(OUT, f"e_logo_{slug}.png"))

        # ---- Day 4: share page save + link ----
        await b.goto(f"{BASE}/s/ahmedabad-gifts/custom-printed-mug")
        await b.js("(()=>{const t=document.querySelector('#t-front');t.value='Deep\\nPatel';t.dispatchEvent(new Event('input',{bubbles:true}));})()")
        await b.js("document.querySelector('#add').click()")
        await asyncio.sleep(3)
        shown = await b.js("!document.querySelector('#share').hidden")
        link = await b.js("document.querySelector('#share input').value")
        check("share box appears after Save and share", shown, link)
        wa = await b.js("document.querySelector('#share [data-wa]').href")
        check("WhatsApp link built", wa.startswith("https://wa.me/?text="))
        # open the shared link and confirm the design restores
        await b.goto(link)
        check("shared link restores the text", await b.js("cz.state.zones.front.text") == "Deep\nPatel")

        # ---- Day 3/4: back view link ----
        await b.goto(f"{BASE}/?product=custom-printed-mug&view=back")
        check("view=back param works", await b.js("cz.camera.position.z") < 0)

    print(f"\n{sum(results)}/{len(results)} checks passed")

asyncio.run(main())
