"""Screenshot HA dashboards headlessly. Run inside mcr.microsoft.com/playwright/python with --network host.
Usage: python shot.py <out_dir> <name>=<path>@<WxH>[@dpr] ...   (token from env HA_TOKEN)"""
import json, os, sys, time
from playwright.sync_api import sync_playwright

TOKEN = os.environ["HA_TOKEN"]
BASE = "http://localhost:8123"
tokens = json.dumps({"hassUrl": BASE, "clientId": BASE + "/", "expires": 9999999999999,
                     "refresh_token": "", "access_token": TOKEN, "expires_in": 1800, "token_type": "Bearer"})
out = sys.argv[1]
with sync_playwright() as p:
    b = p.chromium.launch()
    for spec in sys.argv[2:]:
        name, rest = spec.split("=", 1)
        parts = rest.split("@")
        path, (w, h) = parts[0], map(int, parts[1].split("x"))
        dpr = float(parts[2]) if len(parts) > 2 else 1
        ctx = b.new_context(viewport={"width": w, "height": h}, device_scale_factor=dpr, color_scheme="dark")
        ctx.add_init_script(f"window.localStorage.setItem('hassTokens', {json.dumps(tokens)});")
        if "tablet" in name:  # the tablet uses Profile → "Always hide the sidebar"
            ctx.add_init_script("window.localStorage.setItem('dockedSidebar', JSON.stringify('always_hidden'));")
        page = ctx.new_page()
        page.goto(BASE + path, wait_until="networkidle", timeout=60000)
        time.sleep(4)  # let cards/graphs render
        page.screenshot(path=f"{out}/{name}.png", full_page=True)
        errs = page.locator("hui-error-card, hui-warning").count()
        print(f"{name}: saved ({w}x{h}@{dpr}) error/warning cards: {errs}")
        ctx.close()
    b.close()
