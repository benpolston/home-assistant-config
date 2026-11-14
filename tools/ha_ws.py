"""Run HA WebSocket commands. Usage (host):
  sudo docker exec -i -e HA_TOKEN="$(cat .secrets/ha_token)" homeassistant python - < tools/ha_ws.py  <<< '...'
Simpler: tools/ws '<json list of commands>'  (see tools/ws). Each command is a dict without "id".
Prints one JSON result per command."""
import asyncio, json, os, sys, aiohttp
async def main(cmds):
    async with aiohttp.ClientSession() as s:
        async with s.ws_connect("http://127.0.0.1:8123/api/websocket", max_msg_size=0) as ws:
            await ws.receive_json()
            await ws.send_json({"type": "auth", "access_token": os.environ["HA_TOKEN"]})
            r = await ws.receive_json()
            if r["type"] != "auth_ok": sys.exit(f"auth failed: {r}")
            for i, c in enumerate(cmds, 1):
                await ws.send_json({"id": i, **c})
                while True:
                    m = await ws.receive_json()
                    if m.get("id") == i and m["type"] == "result": break
                print(json.dumps({"cmd": c.get("type"), "success": m["success"], "result": m.get("result"), "error": m.get("error")}))
asyncio.run(main(json.loads(os.environ["HA_CMDS"])))
