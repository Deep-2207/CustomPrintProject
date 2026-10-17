"""Tiny Edge driver over the DevTools protocol (test tooling only, not part of the project)."""
import asyncio, json, os, subprocess, tempfile, time, urllib.request
import websockets

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"


class Browser:
    def __init__(self, w=1200, h=900, port=9333):
        self.port = port
        self.ud = tempfile.mkdtemp(prefix="edge-cdp-")
        self.proc = subprocess.Popen([EDGE, "--headless=new", f"--remote-debugging-port={port}", f"--user-data-dir={self.ud}",
                                      "--enable-unsafe-swiftshader", "--use-angle=swiftshader", "--ignore-gpu-blocklist",
                                      f"--window-size={w},{h}", "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(60):
            try:
                tabs = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json"))
                self.ws_url = next(t["webSocketDebuggerUrl"] for t in tabs if t["type"] == "page")
                break
            except Exception:
                time.sleep(0.5)
        else:
            raise RuntimeError("Edge did not start")
        self.w, self.h = w, h
        self.id = 0

    async def __aenter__(self):
        self.ws = await websockets.connect(self.ws_url, max_size=50_000_000)
        await self.send("Page.enable"); await self.send("Runtime.enable"); await self.send("DOM.enable")
        await self.send("Emulation.setDeviceMetricsOverride", width=self.w, height=self.h, deviceScaleFactor=1, mobile=False)
        return self

    async def __aexit__(self, *a):
        await self.ws.close(); self.proc.kill()

    async def send(self, method, **params):
        self.id += 1
        mid = self.id
        await self.ws.send(json.dumps({"id": mid, "method": method, "params": params}))
        while True:
            msg = json.loads(await self.ws.recv())
            if msg.get("id") == mid:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})

    async def goto(self, url, wait=4.0):
        await self.send("Page.navigate", url=url)
        await asyncio.sleep(wait)

    async def js(self, expr):
        r = await self.send("Runtime.evaluate", expression=expr, awaitPromise=True, returnByValue=True)
        if "exceptionDetails" in r:
            raise RuntimeError(r["exceptionDetails"].get("exception", {}).get("description", str(r["exceptionDetails"])))
        return r["result"].get("value")

    async def shot(self, path, full=False):
        r = await self.send("Page.captureScreenshot", format="png", captureBeyondViewport=full)
        import base64
        open(path, "wb").write(base64.b64decode(r["data"]))

    async def set_files(self, selector, paths):
        doc = await self.send("DOM.getDocument", depth=-1)
        node = await self.send("DOM.querySelector", nodeId=doc["root"]["nodeId"], selector=selector)
        await self.send("DOM.setFileInputFiles", files=paths, nodeId=node["nodeId"])
