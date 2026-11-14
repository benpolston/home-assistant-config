# Source of truth for what Gemini/Assist (and the MCP server) can see. Edit KEEP, then:
#   sudo docker cp tools/assist_exposure.py homeassistant:/tmp/ && sudo docker exec homeassistant python /tmp/assist_exposure.py "$(cat .secrets/ha_token)" dry|apply
# "apply" un-exposes everything not in KEEP and turns off auto-exposing new entities.
import asyncio, aiohttp, json, sys
KEEP = """
light.living_room light.living_room_overheads light.living_room_gu10_1 light.living_room_gu10_2 light.living_room_gu10_3
light.living_room_gu10_4 light.living_room_ceiling_strip light.living_room_tv_strip light.office_bulb
switch.living_room_fan switch.power_strip_spare switch.gaming_pc binary_sensor.gaming_pc_online
scene.movie_mode scene.gaming_mode scene.living_room_relax scene.living_room_bright
script.goodnight script.good_morning script.tvs_off script.tv_strip_video_mode script.baby_log_feed script.baby_log_diaper
media_player.samsung_tv media_player.vizio_tv media_player.samsung_smart_tv
input_boolean.guest_mode
todo.shopping_list todo.to_do_list
counter.baby_feeds_today counter.baby_diapers_today sensor.baby_since_last_feed sensor.baby_since_last_diaper
input_datetime.baby_due_date sensor.baby_countdown
sensor.next_event_today calendar.primary weather.home sensor.weather_alerts person.resident_1 person.resident_2
sensor.jellyfin_now_playing binary_sensor.jellyfin_web
sensor.system_monitor_processor_temperature sensor.system_monitor_disk_usage sensor.system_monitor_disk_usage_mnt_media1
sensor.system_monitor_memory_usage sensor.system_monitor_processor_use
""".split()
async def main():
    tok, apply = sys.argv[1], sys.argv[2] == 'apply'
    async with aiohttp.ClientSession() as s, s.ws_connect("http://localhost:8123/api/websocket") as ws:
        await ws.receive_json(); await ws.send_json({"type":"auth","access_token":tok}); await ws.receive_json()
        await ws.send_json({"id":1,"type":"homeassistant/expose_entity/list"}); r=await ws.receive_json()
        cur={e for e,v in r["result"]["exposed_entities"].items() if v.get("conversation")}
        await ws.send_json({"id":2,"type":"get_states"}); states={x["entity_id"] for x in (await ws.receive_json())["result"]}
        missing=[e for e in KEEP if e not in states]
        remove=sorted(cur-set(KEEP)); add=sorted(set(KEEP)-cur)
        print("currently exposed:",len(cur)," keep:",len(KEEP)," remove:",len(remove)," add:",add, " missing:",missing)
        if apply:
            await ws.send_json({"id":3,"type":"homeassistant/expose_entity","assistants":["conversation"],"entity_ids":remove,"should_expose":False}); print("unexpose", (await ws.receive_json())["success"])
            await ws.send_json({"id":4,"type":"homeassistant/expose_entity","assistants":["conversation"],"entity_ids":list(KEEP),"should_expose":True}); print("expose", (await ws.receive_json())["success"])
            await ws.send_json({"id":5,"type":"homeassistant/expose_new_entities/set","assistant":"conversation","expose_new":False}); print("expose_new off", (await ws.receive_json())["success"])
            await ws.send_json({"id":6,"type":"homeassistant/expose_entity/list"}); r=await ws.receive_json()
            print("now exposed:",len({e for e,v in r["result"]["exposed_entities"].items() if v.get("conversation")}))
asyncio.run(main())
