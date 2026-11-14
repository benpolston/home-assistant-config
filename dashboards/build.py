"""Builds both dashboards as JSON (source of truth in git). Push with tools/push_dashboards.
Screenshots for review: ~/.cache/ha-shot/shoot name=/dashboard-home/home@390x844@2 ..."""
import json, os
D = os.path.dirname(os.path.abspath(__file__))

# ---------- helpers ----------
def tile(e, **kw): return {"type": "tile", "entity": e, **kw}
def heading(t, icon=None, badges=None, style=None):
    c = {"type": "heading", "heading": t}
    if icon: c["icon"] = icon
    if badges: c["badges"] = badges
    if style: c["heading_style"] = style
    return c
def hbadge(e, **kw): return {"type": "entity", "entity": e, "show_state": True, "show_icon": True, **kw}
def act(e, service, name, icon, color=None, **kw):
    c = {"type": "tile", "entity": e, "name": name, "icon": icon, "hide_state": True,
         "tap_action": {"action": "perform-action", "perform_action": service, "target": {"entity_id": e}},
         "icon_tap_action": {"action": "perform-action", "perform_action": service, "target": {"entity_id": e}}, **kw}
    if color: c["color"] = color
    return c
def run(script, name, icon, color=None, **kw): return act(script, "script.turn_on", name, icon, color, **kw)
def scene(s, name, icon, color=None, **kw): return act(s, "scene.turn_on", name, icon, color, **kw)
def when(entity, *, state=None, state_not=None):
    c = {"condition": "state", "entity": entity}
    if state is not None: c["state"] = state
    if state_not is not None: c["state_not"] = state_not
    return [c]
def available(e): return when(e, state_not="unavailable")

def baby_button(sensor, log_script, undo_script, name, icon, color, **kw):
    log = {"action": "perform-action", "perform_action": log_script}
    undo = {"action": "perform-action", "perform_action": undo_script,
            "confirmation": {"text": f"Undo the last {name.lower()} entry?"}}
    return {"type": "tile", "entity": sensor, "name": name, "icon": icon, "color": color,
            "state_content": ["state", "at"],   # "2 h 15 min ago · 1:25 AM"
            "tap_action": log, "icon_tap_action": log, "hold_action": undo, **kw}
FED = ("sensor.baby_since_last_feed", "script.baby_log_feed", "script.baby_undo_feed", "Fed", "mdi:baby-bottle-outline", "pink")
DIAPER = ("sensor.baby_since_last_diaper", "script.baby_log_diaper", "script.baby_undo_diaper", "Diaper",
          "mdi:human-baby-changing-table", "light-blue")
FULL = {"grid_options": {"columns": 12}}
AGENDA = {"type": "markdown", "content":
          "{% set a = (state_attr('sensor.next_event_today', 'agenda') or [])[:8] %}"
          "{% for l in a %}{% set p = l.split(' · ', 1) %}**{{ p[0] }}** · {{ p[1] }}  \n{% else %}Nothing on the calendar{% endfor %}",
          **{"grid_options": {"columns": 12}}}
WEATHER_ALERTS = {"type": "markdown", "grid_options": {"columns": 12},
    "visibility": when("sensor.weather_alert_level", state_not=["none", "unknown", "unavailable"]),
    "content": "{% for a in state_attr('sensor.weather_alerts', 'alerts') or [] %}"
               "{% set e = as_datetime(a.ends) if a.ends else none %}"
               "{{ '🚨' if a.tier == 'critical' else '⚠️' if a.tier == 'warning' else '🌦️' }} **{{ a.event }}**"
               "{{ (' · until ' ~ as_local(e).strftime('%a %-I:%M %p')) if e else '' }}  \n{% endfor %}"
               "[NWS details](https://forecast.weather.gov/MapClick.php?lat={{ '%.4f' % state_attr('zone.home','latitude') }}"
               "&lon={{ '%.4f' % state_attr('zone.home','longitude') }})"}
CALENDARS = ["calendar.primary", "calendar.holidays_in_united_states", "calendar.good_to_know", "calendar.birthdays"]

QUARTER = {"grid_options": {"columns": 3, "rows": 2}, "vertical": True}
THIRD = {"grid_options": {"columns": 4, "rows": 2}, "vertical": True}
toggle = [{"type": "toggle"}]
bright = [{"type": "light-brightness"}]

SCENES = [
    ("scene.living_room_relax", "Relax", "mdi:sofa", "amber"),
    ("scene.living_room_bright", "Bright", "mdi:white-balance-sunny", "yellow"),
    ("scene.movie_mode", "Movie", "mdi:movie-open", "red"),
    ("scene.gaming_mode", "Gaming", "mdi:controller", "purple"),
]
playing = when("sensor.living_room_jellyfin_state", state_not="idle")

# Status chips at the top of each view (conditional ones only appear when relevant)
def status_badges():
    return [
        {"type": "entity", "entity": "person.resident_1", "show_name": True, "name": "Resident 1", "show_state": True, "show_icon": True},
        {"type": "entity", "entity": "person.resident_2", "show_name": True, "name": "Resident 2", "show_state": True, "show_icon": True},
        {"type": "entity", "entity": "sensor.system_problems", "name": "System problems", "show_name": True,
         "show_state": True, "show_icon": True, "color": "red", "visibility": when("sensor.system_problems", state_not=["0", "unknown", "unavailable"])},
        {"type": "entity", "entity": "sensor.weather_alerts", "name": "Weather", "show_name": True, "show_state": True,
         "show_icon": True, "color": "red", "icon": "mdi:alert", "visibility": when("sensor.weather_alert_level", state=["warning", "critical"])},
        {"type": "entity", "entity": "sensor.weather_alerts", "name": "Weather", "show_name": True, "show_state": True,
         "show_icon": True, "color": "orange", "visibility": when("sensor.weather_alert_level", state=["advisory", "watch"])},
        {"type": "entity", "entity": "sensor.next_event_today", "name": "Next", "show_name": True, "show_state": True,
         "show_icon": True, "color": "blue", "visibility": when("sensor.next_event_today", state_not=["none", "unknown", "unavailable"])},
        {"type": "entity", "entity": "sensor.baby_countdown", "name": "Baby", "show_name": True, "show_state": True,
         "show_icon": True, "color": "pink"},
        {"type": "entity", "entity": "weather.home", "show_state": True, "show_icon": True, "state_content": ["state", "temperature"]},
        {"type": "entity", "entity": "sensor.system_monitor_processor_temperature", "name": "CPU", "show_name": True,
         "show_state": True, "show_icon": True, "color": "teal"},
        {"type": "entity", "entity": "binary_sensor.jellyfin_web", "name": "Jellyfin", "show_name": True,
         "show_state": True, "show_icon": True},
        {"type": "entity", "entity": "input_boolean.movie_mode_active", "name": "Movie mode", "show_name": True,
         "show_state": False, "show_icon": True, "color": "red", "visibility": when("input_boolean.movie_mode_active", state="on")},
        {"type": "entity", "entity": "input_boolean.guest_mode", "name": "Guest mode", "show_name": True,
         "show_state": False, "show_icon": True, "color": "pink", "visibility": when("input_boolean.guest_mode", state="on")},
        {"type": "entity", "entity": "switch.living_room_heater", "name": "Heater on", "show_name": True,
         "show_state": False, "show_icon": True, "color": "deep-orange", "visibility": when("switch.living_room_heater", state="on")},
    ]

now_playing_card = {"type": "media-control", "entity": "media_player.samsung_smart_tv", "name": "Now playing",
                    "visibility": when("media_player.samsung_smart_tv", state=["playing", "paused"])}

# ---------- phone dashboard ----------
main = {"title": "Home", "views": [{
  "title": "Home", "path": "home", "icon": "mdi:home", "type": "sections", "max_columns": 3,
  "badges": status_badges(),
  "sections": [
    {"type": "grid", "cards": [
      {"type": "weather-forecast", "entity": "weather.home", "name": "Home", "forecast_type": "daily",
       "show_current": True, "show_forecast": True, **FULL},
      now_playing_card,
      WEATHER_ALERTS,
    ]},
    {"type": "grid", "cards": [
      heading("Calendar", "mdi:calendar"),
      {"type": "calendar", "entities": CALENDARS, "initial_view": "listWeek", **FULL},
      tile("input_boolean.calendar_evening_reminders", name="Evening reminder for tomorrow", features=toggle, **FULL),
      tile("input_text.calendar_reminder_skip", name="Never remind about", icon="mdi:calendar-remove", **FULL),
    ]},
    {"type": "grid", "cards": [
      heading("Living Room", "mdi:sofa", badges=[hbadge("light.living_room", name="Lights")]),
      *[scene(e, n, i, c, **QUARTER) for e, n, i, c in SCENES],
      tile("light.living_room", name="All living room lights", features=bright, **FULL),
      tile("light.living_room_overheads", name="Overheads", features=toggle, grid_options={"columns": 6}),
      tile("light.living_room_ceiling_strip", name="Ceiling strips", features=toggle, grid_options={"columns": 6}),
      tile("light.living_room_tv_strip", name="TV strip", grid_options={"columns": 12}),
    ]},
    {"type": "grid", "cards": [
      heading("TVs", "mdi:television"),
      {"type": "media-control", "entity": "media_player.samsung_tv", "name": "Living room TV"},
      tile("media_player.vizio_tv", name="Bedroom TV", icon="mdi:television", grid_options={"columns": 6}),
      run("script.tvs_off", "All TVs off", "mdi:television-off", "blue-grey", grid_options={"columns": 6}),
    ]},
    {"type": "grid", "cards": [
      heading("Comfort", "mdi:thermometer"),
      tile("switch.living_room_fan", name="Fan", icon="mdi:fan", color="cyan", features=toggle, grid_options={"columns": 6}),
      tile("switch.living_room_heater", name="Heater", icon="mdi:radiator", color="deep-orange", features=toggle,
           grid_options={"columns": 6}),
      tile("input_number.heater_max_hours", name="Heater auto-off after", icon="mdi:timer-alert-outline",
           features=[{"type": "numeric-input", "style": "buttons"}], **FULL),
      tile("switch.power_strip_spare", name="Spare outlet", icon="mdi:power-socket-us", **FULL),
    ]},
    {"type": "grid", "cards": [
      heading("Office", "mdi:desk"),
      tile("light.office_bulb", name="Office light", features=bright, **FULL),
      tile("binary_sensor.gaming_pc_online", name="Gaming PC", icon="mdi:desktop-tower", **FULL),
      run("script.gaming_pc_on", "Wake PC", "mdi:power", "green", grid_options={"columns": 6}),
      run("script.gaming_pc_sleep", "Sleep PC", "mdi:power-sleep", "indigo", grid_options={"columns": 6}),
    ]},
    {"type": "grid", "cards": [
      heading("Morning & night", "mdi:theme-light-dark"),
      run("script.good_morning", "Good Morning", "mdi:weather-sunny", "amber",
          grid_options={"columns": 6, "rows": 2}, vertical=True),
      run("script.goodnight", "Goodnight", "mdi:weather-night", "indigo",
          grid_options={"columns": 6, "rows": 2}, vertical=True),
    ]},
    {"type": "grid", "cards": [
      heading("Baby", "mdi:baby-face-outline"),
      tile("sensor.baby_countdown", name="Due date", icon="mdi:baby-carriage", color="pink",
           state_content=["state", "pregnancy_week"], **FULL),
      baby_button(*FED, grid_options={"columns": 6, "rows": 2}, vertical=True),
      baby_button(*DIAPER, grid_options={"columns": 6, "rows": 2}, vertical=True),
      tile("counter.baby_feeds_today", name="Feeds today", color="pink", grid_options={"columns": 6}),
      tile("counter.baby_diapers_today", name="Diapers today", color="light-blue", grid_options={"columns": 6}),
      tile("input_boolean.baby_feed_reminders", name="Feeding reminders", features=toggle, **FULL),
      tile("input_number.baby_feed_interval_hours", name="Remind after", icon="mdi:timer-sand",
           features=[{"type": "numeric-input", "style": "buttons"}], **FULL,
           visibility=when("input_boolean.baby_feed_reminders", state="on")),
      {"type": "tile", "entity": "script.baby_reset", "name": "Reset tracker", "icon": "mdi:restart",
       "hide_state": True, "color": "grey", **FULL,
       "tap_action": {"action": "perform-action", "perform_action": "script.baby_reset",
                      "confirmation": {"text": "Clear all feed and diaper times and today's counts?"}},
       "icon_tap_action": {"action": "perform-action", "perform_action": "script.baby_reset",
                           "confirmation": {"text": "Clear all feed and diaper times and today's counts?"}}},
    ]},
    {"type": "grid", "cards": [
      heading("Family", "mdi:account-group"),
      tile("person.resident_1", name="Resident 1", grid_options={"columns": 6}),
      tile("person.resident_2", name="Resident 2", grid_options={"columns": 6}),
      tile("input_boolean.guest_mode", name="Guest staying", color="pink", features=toggle, **FULL),
      tile("sensor.resident_1_phone_battery_level", name="Resident 1 phone", grid_options={"columns": 6},
           visibility=available("sensor.resident_1_phone_battery_level")),
      tile("sensor.resident_2_phone_battery_level", name="Resident 2 phone", grid_options={"columns": 6},
           visibility=available("sensor.resident_2_phone_battery_level")),
    ]},
    {"type": "grid", "cards": [
      heading("Media server", "mdi:server", badges=[hbadge("binary_sensor.jellyfin_web", name="Jellyfin")]),
      tile("sensor.system_monitor_processor_use", name="CPU", color="blue",
           features=[{"type": "trend-graph", "hours_to_show": 24}], grid_options={"columns": 6}),
      tile("sensor.system_monitor_processor_temperature", name="CPU temp", color="teal",
           features=[{"type": "trend-graph", "hours_to_show": 24}], grid_options={"columns": 6}),
      tile("sensor.system_monitor_memory_usage", name="Memory", color="purple",
           features=[{"type": "trend-graph", "hours_to_show": 24}], **FULL),
      tile("sensor.system_monitor_disk_usage", name="System disk", color="green",
           features=[{"type": "bar-gauge"}], grid_options={"columns": 6}),
      tile("sensor.system_monitor_disk_usage_mnt_media1", name="Media disk", color="green",
           features=[{"type": "bar-gauge"}], grid_options={"columns": 6}),
    ]},
  ]}]}

# ---------- tablet dashboard (Galaxy Tab A8, landscape ~1280x800) ----------
BIG = {"grid_options": {"columns": 3, "rows": 2}, "vertical": True}
BIG2 = {"grid_options": {"columns": 6, "rows": 2}, "vertical": True}   # quarter-width in a 2-column (24-col) section
tablet = {"title": "Tablet", "views": [{
  "title": "Home", "path": "home", "type": "sections", "max_columns": 4, "dense_section_placement": True,
  "badges": status_badges(),
  "sections": [
    {"type": "grid", "column_span": 1, "cards": [
      {"type": "clock", "clock_size": "large", "show_seconds": False, **FULL},
      {"type": "weather-forecast", "entity": "weather.home", "name": "Home", "forecast_type": "daily",
       "show_current": True, "show_forecast": True, **FULL},
      now_playing_card,
      AGENDA,
    ]},
    {"type": "grid", "column_span": 2, "cards": [
      heading("Scenes", "mdi:palette"),
      *[scene(e, n, i, c, **BIG2) for e, n, i, c in SCENES],
      heading("Lights & comfort", "mdi:lightbulb-group"),
      tile("light.living_room", name="Living room", features=bright, grid_options={"columns": 12, "rows": 2}),
      tile("light.office_bulb", name="Office", features=bright, grid_options={"columns": 12, "rows": 2}),
      tile("switch.living_room_fan", name="Fan", icon="mdi:fan", color="cyan", **BIG2),
      tile("switch.living_room_heater", name="Heater", icon="mdi:radiator", color="deep-orange", **BIG2),
      tile("media_player.samsung_tv", name="Living room TV", icon="mdi:television", color="blue",
           tap_action={"action": "toggle"}, icon_tap_action={"action": "toggle"}, **BIG2),
      tile("input_boolean.guest_mode", name="Guest staying", color="pink", **BIG2),
      heading("Quick actions", "mdi:gesture-tap"),
      run("script.good_morning", "Good Morning", "mdi:weather-sunny", "amber", **BIG2),
      run("script.goodnight", "Goodnight", "mdi:weather-night", "indigo", **BIG2),
      baby_button(*FED, **BIG2),
      baby_button(*DIAPER, **BIG2),
    ]},
  ]}]}

for name, cfg in (("main", main), ("tablet", tablet)):
    json.dump(cfg, open(os.path.join(D, f"{name}.json"), "w"), indent=1)
print("ok")
