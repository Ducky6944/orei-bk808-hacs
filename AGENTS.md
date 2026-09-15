# AGENTS.md

Guidance for any agent (or human) continuing work on this repository.
Read this before making changes — it encodes constraints that are not
obvious from the code alone.

## What this project is

A HACS-ready Home Assistant custom integration for the **Orei BK808**, an
8×8 HDMI matrix switch (8 HDMI inputs × 8 HDMI outputs, with CEC and
per-port cover-art passthrough). It is *not* a full AV controller — the
device routes video signals but does not decode them — so we model it as
a matrix + a set of "media players" that expose which port is live.

## Repository layout

```
custom_components/orei_bk808/   # the integration (shipped to HA)
  __init__.py                    # async_setup / unload, service registration
  config_flow.py                 # HA config flow (user -> naming -> entry)
  coordinator.py                 # DataUpdateCoordinator: polls device, caches state
  media_player.py                # per-input/out "media player" proxies
  button.py select.py switch.py  # CEC buttons, routing selects, mute switches
  sensor.py remote.py            # routed-input sensor, per-port remotes
  http_view.py                   # serves cover bytes at /api/.../cover
  services.yaml                  # HA service definitions (user-facing)
  const.py                       # constants + CEC command tables
  strings.json                   # config-flow strings (per-locale root)
  translations/en.json           # English translations
  brand/ static/                 # brand icon, bundled cover assets
tests/                           # pytest test suite
  conftest.py                    # fixtures (sample_video_status, sample_cec_status)
  test_coordinator.py
  test_config_flow.py
  test_media_player.py
.github/workflows/tests.yml     # CI
hacs.json                        # HACS manifest
README.md                        # user-facing docs (rendered by HACS)
lovelace_dashboard.yaml          # optional template dashboard
pytest.ini                       # pytest config
```

Note: `custom_components/__init__.py` (the *namespace* package, one level
up) is **not** shipped and is not required — tests pass without it. Do not
re-add it.

## How the device works (API)

- Device sits on the LAN, speaks **HTTPS with a self-signed cert**.
  All calls must use `fingerprint="*"`.
- **Single sticky connection**: use ONE persistent `aiohttp.ClientSession`
  for the process life. It was verified that *sequential* requests over that
  single connection return correct bodies. Do not open a new session per call
  and do not reuse one connection for concurrent requests.
- **Read status**: `POST /cgi-bin/instr` body `{"comhead": "..."}`.
  - `get input status`  -> `inactive[]`  (1 = powered on, 0 = off)
  - `get output status` -> `allconnect[]` (1 = something connected, 0 = off)
  - video / CEC status read via the coordinator's existing poll.
- **Command**: `POST /cgi-bin/instr` body `{"comhead": "<command>"}`.

Key consequence: the device does **not** report "which video is playing" —
so `media_player.state` is limited to `"on"`/`"off"` derived from the
port-power/connection lists above. Do not claim playback detail we can't
read back.

## Coordinator pattern (custom_components/orei_bk808/coordinator.py)

- A `DataUpdateCoordinator` owns the single `aiohttp` session and the
  cached state (`_input_active`, `_output_connect`, video/CEC state).
- `input_is_on(n)` / `output_is_on(o)` expose the derived booleans to
  entities (1-indexed port numbers).
- `send_command(cmd)` is the single place that fires-and-forgets device
  commands, then requests a coordinator refresh.
- All reads go through the coordinator; entities must NOT open their own
  HTTP connections.

## Conventions

- **Minimal diffs.** Change only what the task requires. Match the style
  and naming of neighbouring files before writing new code.
- **No comments unless asked.** Code comments only when a rule asked for
  them. Docstrings should be accurate and current — fix stale ones.
- **Non-blocking I/O in the event loop.** Any `read_bytes`, file, or sync
  network call inside `async` code must go through `asyncio.to_thread(...)`.
  (This caught two real bugs — see gotchas.)
- **Stub-test before release.** Run `pytest` and confirm byte-compile clean
  before bumping the version.
- **Python < 3.12** compatibility for the HA runtime in `hacs.json`; CI runs
  on 3.11. Local dev/verified on 3.13.
- **Feature-flag / const resolution**: read from `const.py` (CEC tables,
  counts). Do not hardcode port numbers or CEC payloads inline — resolve via
  the const tables.
- **Entity naming**: build names from `coordinator.input_display_name(n)` /
  `coordinator.output_display_name(o)`. Do NOT hardcode "Input N" /
  "Output N".

## Release process

1. Confirm `pytest` green + `python -m compileall` clean.
2. Bump `"version"` in `custom_components/orei_bk808/manifest.json`.
3. `git add -A && git commit -m "vX.Y.Z: <summary>"`.
4. `git tag vX.Y.Z`, `git push origin <branch> --follow-tags`
   (repo: `https://github.com/Ducky6944/orei-bk808-hacs.git`).
5. `gh release create vX.Y.Z --title "vX.Y.Z" --notes "..."`
   (auth: `gh auth login` or PAT; `git credential fill <<< "protocol=https\nhost=github.com\n"` to read the PAT).

## Known gotchas (all hit and fixed — do not regress)

- **YAML `on` key.** In `services.yaml`, `on:` parses as boolean `True`
  under YAML 1.1. The field must be quoted: `"on":`. Symptom of a
  regression: `expected str at 'set_power.fields[True]'`.
- **`MediaPlayer.state` is a `cached_property`.** To report `on`/`off`,
  override with a `@property def state` (and `is_on`). Subclass property
  override is correct.
- **Config-flow result type.** `data_entry_flow.RESULT_TYPE_FORM` no longer
  exists — use the string literals `"form"` / `"create_entry"`.
- **`enable_custom_integrations` fixture.** Config-flow tests need this
  fixture (from `pytest-homeassistant-custom-component`) to clear the
  loader cache.
- **Cover bytes.** `async_get_media_image()` and the `http_view` handler
  both call `asyncio.to_thread(...)` to read bundled asset bytes. A plain
  sync call in async code blocks the loop / trips
  `AssertionError: Handler should be a coroutine or a callback`.
- **`async def` for HA HTTP handlers.** `http_view` handler must be
  `async def`, not a plain function.

## Current state (as of v1.4.6, in preparation)

- v1.4.6 changes are complete and green locally: media-player state now
  `"on"`/`"off"` from real port status; services.yaml `on` quoted;
  http_view + cover bytes made async; dead `_stop` handler removed;
  stale `test_connection` string removed; README + entity tables updated;
  `test_media_player.py` added; `pytest.ini` added.
- **Not yet done:** commit v1.4.6, tag `v1.4.6`, push, create the release.
