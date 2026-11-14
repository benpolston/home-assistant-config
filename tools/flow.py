"""Drive a HA config flow over REST.  python3 -I tools/flow.py <handler|flow_id> '<json step1>' ['<json step2>' ...]
A step may be {"next_step_id": "..."} for menu steps. Prints each response (secrets redacted)."""
import json, sys, os, urllib.request
T = open(os.path.join(os.path.dirname(__file__), "..", ".secrets", "ha_token")).read().strip()
B = "http://localhost:8123/api/config/config_entries/"
def req(m, p, d=None, base=B + "flow"):
    r = urllib.request.Request(base + p, method=m, data=json.dumps(d).encode() if d is not None else None,
        headers={"Authorization": "Bearer " + T, "Content-Type": "application/json"})
    try: return json.load(urllib.request.urlopen(r, timeout=120))
    except urllib.error.HTTPError as e: return {"http_error": e.code, "body": e.read().decode()[:400]}
def show(x):
    s = json.dumps(x); 
    for k in ("password", "token", "api_key"): pass
    keep = {k: x.get(k) for k in ("type", "flow_id", "step_id", "errors", "reason", "title", "menu_options", "description_placeholders", "http_error", "body") if k in x}
    if "data_schema" in x: keep["fields"] = [f.get("name") for f in x["data_schema"]]
    if "result" in x and isinstance(x["result"], dict): keep["entry_id"] = x["result"].get("entry_id")
    print(json.dumps(keep))
h = sys.argv[1]
base = B + ("options/flow" if h.startswith("options:") else "flow")
if h.startswith("options:"): h = h[8:]
if len(h) == 26 and h.isalnum() and h.isupper(): r = {"flow_id": h}
else: r = req("POST", "", {"handler": h, "show_advanced_options": True}, base); show(r)
for s in sys.argv[2:]:
    if "flow_id" not in r: break
    r = req("POST", "/" + r["flow_id"], json.loads(s), base); show(r)
