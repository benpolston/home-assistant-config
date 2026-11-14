# Home Assistant: local-first smart home

A self-hosted smart-home platform built on Home Assistant, running in Docker on a Linux home server. Everything is configuration-as-code: YAML packages, scenes, scripts and automations live in git, dashboards are generated from Python, and the voice assistant's entity access is managed by a script.

The project has three priorities: **local control** (the lights keep working when the internet is down), **a small attack surface** (no open ports, no public endpoints), and **good behavior on a shared network** (the voice assistant can't touch the space heater, and sensible things happen when nobody is home).

---

## Architecture

```
                         ┌───────────────────── Linux home server (Docker, host networking) ─────────────────────┐
                         │                                                                                       │
 Phones / tablet ──────► │  Tailscale Serve (HTTPS, tailnet only) ──► Home Assistant :8123                       │
 (on the tailnet)        │                                              │  ▲                                     │
                         │                                              │  │ MQTT (auth, localhost + LAN only)  │
 iPhone Home app / Siri ◄┼── HomeKit Bridge (LAN) ◄─────────────────────┤  │                                     │
                         │                                              │  Mosquitto ◄──── govee2mqtt ─────────┼──► Govee strips (LAN API)
 Voice (Assist) ────────►│  Gemini conversation agent ◄─ curated ───────┤                                        │
                         │                               entities (48)  │                                        │
                         │                                              ├──► Matter server (matter.js) ──────────┼──► Govee bulbs (Matter over Wi-Fi, IPv6)
                         │                                              │      ▲ radvd: private IPv6 prefix       │
                         │                                              ├──► Kasa outlets / bulb (local TP-Link) │
                         │                                              ├──► Samsung / Vizio TVs (LAN, WoL)      │
                         │                                              ├──► Jellyfin health + playback state    │
                         │                                              └──► Encrypted backups ─► local + off-site│
                         └───────────────────────────────────────────────────────────────────────────────────────┘
```

| Component | Role |
|---|---|
| **Home Assistant** (Docker, `network_mode: host`) | Core automation engine. Host networking for mDNS/SSDP discovery, Wake-on-LAN broadcasts and HomeKit. |
| **Mosquitto** | MQTT broker. Authentication required, no anonymous access, bound to localhost and the LAN interface only. |
| **govee2mqtt** | Bridges Govee light strips to MQTT, using the Govee LAN API where the device supports it. |
| **Matter server** (matterjs-server) | Matter controller for the Govee bulbs. Built from a pinned upstream commit (see troubleshooting). |
| **radvd** | Advertises a private (ULA) IPv6 prefix on the LAN. Matter needs IPv6 and the ISP provides none. |
| **HomeKit Bridge** | Exposes a curated set of lights, outlets and scenes to Apple Home and Siri. |
| **Gemini voice assistant** | HA Assist pipeline using Google Gemini for conversation, speech-to-text and text-to-speech, with local intents tried first. |
| **Tailscale Serve** | Remote access over the tailnet with HTTPS. No public exposure. |

### Repository layout

```
docker-compose.yml          the whole stack
config/
  configuration.yaml        thin: loads packages, scripts, scenes, automations
  packages/                 one file per feature (lights, homekit, weather alerts, system health, ...)
  automations/              lighting, media, presence, safety, server watchdog
  scenes/  scripts/         living-room looks and household routines
  secrets.example.yaml      template; the real secrets.yaml is never committed
dashboards/build.py         generates both Lovelace dashboards (phone + wall tablet) as JSON
tools/                      small CLIs: REST/WebSocket helpers, Assist exposure manager, dashboard push, screenshots
mosquitto/  radvd/          service configs
```

### Highlights

- **Packages, not one big file.** Each feature (weather alerts, system health, HomeKit, calendar) is self-contained with its helpers, templates, scripts and automations.
- **Weather alerts with tiers.** Polls the National Weather Service API for the home location (read from HA at runtime, never hard-coded). Critical alerts bypass silent mode, warnings are time-sensitive and get an "ended" follow-up, watches are quiet during quiet hours, advisories stay on the dashboard.
- **Self-monitoring.** Template `problem` sensors for the Govee bridge, Google connection, backups and the weather feed. A dashboard chip turns red, and a push notification is sent after a 30-minute grace period, plus one when the problem clears.
- **Media-aware lighting.** Jellyfin playback on the living-room TV snapshots the lights, dims for the movie, changes on pause and restores the previous look when playback stops.
- **Safety automations only turn things off.** The heater has a maximum runtime enforced by two triggers (a state trigger plus a 5-minute backstop that survives HA restarts).
- **Dashboards as code.** `dashboards/build.py` generates both dashboards; `tools/push_dashboards` deploys them over the WebSocket API.

---

## Security design

- **No port forwarding.** Nothing on the router is open to the internet. Remote access is through **Tailscale Serve** only (HTTPS, tailnet devices only, Funnel disabled). HA trusts the local proxy (`trusted_proxies: 127.0.0.1, ::1`) and has IP banning on after 5 failed logins.
- **Least exposure inside the LAN.** MQTT requires auth and listens only on localhost and the LAN address, not on the Tailscale or Docker interfaces. HomeKit advertises only on the LAN IP.
- **Secrets handling.** Credentials live in a gitignored `secrets.yaml` and a `.secrets/` directory (mode 700, env files for containers). `secrets.example.yaml` documents every key. Helper tools read the API token from disk at runtime, and the Wi-Fi/router credential tools prompt with hidden input and never write passwords into the repo. A `.gitignore` keeps runtime state (`.storage/`, databases, logs, backups, pairing data) out of version control. The repo is scanned with gitleaks.
- **Curated voice access (104 → 48 entities).** "Expose new entities" is off. `tools/assist_exposure.py` is the single source of truth for what the voice assistant (and the MCP server) can see: it un-exposes everything else and can be re-run idempotently. Clutter like per-segment strip controls and duplicate media players was removed, so the model gets a clean, unambiguous entity list.
- **The heater is hidden from voice control.** A misheard command or an LLM mistake shouldn't be able to turn on a space heater. It can be controlled manually (dashboard, HomeKit) and is still covered by the max-runtime auto-off and the "everyone away" shutdown.
- **Encrypted off-site backups.** HA's built-in backups run daily with encryption, keep 7 copies, and go both to local storage and to Google Drive. A cron job copies them out of the container volume with restrictive permissions. A health sensor alerts if no backup has succeeded in 50 hours.
- **Household schedule isn't hard-coded.** Quiet hours, reminder times and the morning reset are UI helpers (`input_datetime`), not literals in YAML.

---

## Local-first control: cloud → Matter / LAN migration

The Govee lights started out cloud-only: HA → govee2mqtt → Govee's cloud API → bulb. That meant:

- **Latency:** up to ~15 s from command to confirmed state.
- **Fragility:** an internet outage made every Govee light uncontrollable, and transient DNS failures dropped commands silently (govee2mqtt doesn't retry).
- **Workarounds everywhere:** the cloud ignores color sent to an off bulb, so scenes needed "power on, wait 2 s, apply look, verify, retry" helpers.

The migration:

| Device | Before | After | Latency |
|---|---|---|---|
| 4 ceiling bulbs (Govee H600D) | Cloud | **Matter over Wi-Fi** (local) | ~0.3–0.4 s |
| 2 ceiling light strips | Cloud | **Govee LAN API** (local) | ~0.3–0.5 s |
| TV backlight strip | Cloud | Cloud (no LAN/Matter support on this model) | — |

Entity IDs were kept identical through registry renames, so scenes, groups, automations, HomeKit and dashboards needed no changes. The cloud-era workarounds were then removed from the bulb paths (they caused new problems with Matter, see below) and kept only for the devices that still need them.

---

## Troubleshooting notes

### Matter pairing failed: no IPv6, then a missing VendorID

**Symptom:** The Govee app refused to start Matter setup ("An IPv6 network is required"). After that was fixed, pairing reached the secure session (PASE) and then aborted.

**Root cause:** Two separate problems.
1. The ISP provides no IPv6, and Matter over Wi-Fi requires it on the LAN.
2. The bulb firmware doesn't report `VendorID`/`ProductID` in its Basic Information cluster. python-matter-server aborts at `ReadCommissioningInfo`, and matter.js rejected the device attestation (`CertificationDeclarationFieldMismatch`). This is a known vendor issue.

**Fix:**
1. `radvd` on the server advertises a private RFC 4193 ULA prefix with `AdvDefaultLifetime 0`, so devices get IPv6 addresses on the LAN but never try to route to the internet through the server.
2. Swapped python-matter-server for matterjs-server (same WebSocket API) and built it from source at the first upstream commit that accepts such devices when test-net DCL is enabled. The compose file documents how to return to a published image once a release includes the fix. Commissioning also needed the right timing: start the controller's commission call first, then open the bulb's pairing window.

### The Govee outage

**Symptom:** Overnight, every Govee light showed "unavailable" and nothing could be controlled. Separately, an evening movie-mode test left some lights off with no error.

**Root cause:** The internet went down overnight, and all Govee control went through the cloud. The movie-mode failure was a transient DNS lookup failure for Govee's API, which govee2mqtt doesn't retry.

**Fix:** Short term, a `govee_ensure_power` script (verify the state and retry up to 3 times) and a scene "power assist" automation. Long term, the migration above: the bulbs and ceiling strips are now local and don't depend on the internet. A `problem_govee_bridge` health sensor alerts if the bridge or all its lights go unreachable.

### Dropped color commands on the Matter bulbs

**Symptom:** Scenes sometimes set the right brightness but not the right color. In Goodnight, a bulb would dim to 1% but stay white instead of purple, while HA showed purple.

**Root cause:** A bulb firmware quirk. The bulb sometimes accepts a color command, reports the new color back over Matter, and doesn't show it. Because the reported state is "correct", HA can't detect the failure. Separately, the Matter `ExecuteIfOff` option was 0, so color sent to an off bulb was ignored.

**What didn't work:** Re-sending the identical command (no-op from the bulb's view), multi-step "settle" loops that checked and re-sent (more commands meant more chances for the firmware to misbehave, including brief 100% flashes), and pre-coloring before dimming.

**Fix:** Set `ExecuteIfOff = 1` on the bulbs. Then one automation (`living_room_look_second_command`) sends exactly **one** follow-up command 0.5 s after any living-room scene, with the same brightness and a *barely different* color (e.g. 2700 K → 2800 K, hue 270° → 272°). The bulb sees a real change and applies it. The result has been reliable in every mode. Lesson: when the device's reported state can't be trusted, the fix has to change what you send, not add more verification.

---

## Running it

```bash
cp config/secrets.example.yaml config/secrets.yaml   # fill in values
mkdir -p .secrets && chmod 700 .secrets               # govee2mqtt.env etc.
docker compose up -d --build
python3 dashboards/build.py && tools/push_dashboards  # needs .secrets/ha_token
```

Entity IDs, device IDs, IP addresses and person names in this repo are placeholders (e.g. `person.resident_1`, `192.0.2.10`, `fd00:0:0:1::/64`).
