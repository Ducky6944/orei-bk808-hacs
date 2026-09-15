# AGENTS.md

Guidance for any agent (or human) continuing work on this repository.
Read this before making changes — it encodes constraints that are not
obvious from the code alone.

## How to work on this repo (read first)

**Prefer the simple answer, and ask before you over-engineer.**

- **Ask a clarifying question before increasing complexity.** One good
  question ("should this be a toggle, just two fields, or a preset?") is
  worth an afternoon of build-then-revert. Do not spend a huge number of
  tokens to decide something the user can answer in one line.
- **Simple > clever.** If a two-line fix, deleting an unused option, or a
  single field does the job, do that. Do not add flags, wrappers, caches, or
  abstractions to solve a one-spot problem. YAGNI.
- **Prefer removing over adding.** Several real bugs here came from an
  over-designed UI (a checkbox that silently overwrote typed input). When in
  doubt, cut the moving part.
- **State the plan in a sentence or two and check it works**, rather than
  producing a long rationale. Short, concrete, verifiable — then stop.
- **Stop debating with yourself after 2–3 turns.** If you find yourself going
  back and forth on which path to take more than two or three times, ask the
  user what they think instead of endlessly deliberating. If they have no
  preference, that's fine — pick one and go.
- **Verify with the real device / live test when the bug is behaviour**,
  not just with unit stubs, before claiming a fix.

If you're about to write a paragraph explaining *why* a particular design is
reasonable, that's a signal to ask the user what they actually want instead.

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
  - `get input status`  -> `inactive[]`  (1 = powered on, 0 = off),
    plus `inname[]` (input port names).
  - `get output status` -> `allconnect[]` (1 = something connected, 0 = off),
    plus `name[]` (output port names).
  - `get video status`  -> `allsource[]` (routing: which input sits on each
    output), plus `allinputname[]` / `alloutputname[]`.
  - **Names live in different fields per blob.** To reliably read the user's
    configured port names you must accept **all** of: `allinputname`,
    `inname`, `name`, `alloutputname`. `config_flow._extract_names` does this;
    reuse it rather than assuming one field.
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
- **Reads are POSTs, not GETs.** Because of the sticky socket (see gotchas),
  the routing/blob state is read via `send_command(...)` (POST `/cgi-bin/instr`),
  wrapped by `_read_video_blob()`. GET is only a fallback. If you add a new
  state read, POST it.

## Conventions

- **Minimal diffs.** Change only what the task requires. Match the style
  and naming of neighbouring files before writing new code.
- **No comments unless asked.** Code comments only when a rule asked for
  them. Docstrings should be accurate and current — fix stale ones.
- **Non-blocking I/O in the event loop.** Any `read_bytes`, file, or sync
  network call inside `async` code must go through `asyncio.to_thread(...)`.
  (This caught two real bugs — see gotchas.)
- **Python < 3.12** compatibility for the HA runtime in `hacs.json`; CI runs
  on 3.11. Local dev/verified on 3.13.
- **Feature-flag / const resolution**: read from `const.py` (CEC tables,
  counts). Do not hardcode port numbers or CEC payloads inline — resolve via
  the const tables.
- **Entity naming**: build names from `coordinator.input_display_name(n)` /
  `coordinator.output_display_name(o)`. Do NOT hardcode "Input N" /
  "Output N".

## Lint & quality gates

Toolchain is **black** + **flake8** — the exact two CI runs in
`.github/workflows/tests.yml`. Install if missing with `pip install black flake8`.

- **black** (line length 88, its default; the project targets 88).
  Format with `python -m black custom_components/ tests/`.
- **flake8** is configured via **`.flake8`**: `max-line-length = 88`,
  `extend-ignore = E203, W503, W504`.
  Run `python -m flake8 custom_components/ tests/`.
- Both must pass before release; they mirror CI so a green local run equals
  a green CI run.
- **Stub-test before release.** Run the full gate:
  `python -m pytest tests/` + `python -m black --check custom_components/ tests/`
  + `python -m flake8 custom_components/ tests/` + `python -m compileall -q ...`.

## Release process

1. Run the full lint & quality gate (see above): `pytest` + `black --check`
   + `flake8` + `compileall`, all clean.
2. Bump `"version"` in `custom_components/orei_bk808/manifest.json` — **but
   only for code changes** that reach into `custom_components/`. Docs-only
   edits (README, AGENTS.md, release notes, workflow YAML) carry no bearing on
   the released integration: just commit, no version bump, no new tag or
   `gh release`. Keep `manifest.json`, the git tag, and the GitHub release
   version in lockstep at all times.
3. `git add -A && git commit -m "vX.Y.Z: <summary>"`.
4. `git tag vX.Y.Z`, `git push origin <branch> --follow-tags`
   (repo: `https://github.com/Ducky6944/orei-bk808-hacs.git`).
5. `gh release create vX.Y.Z --title "vX.Y.Z" --notes "..."`
   (auth: `gh auth login` or PAT; `git credential fill <<< "protocol=https\nhost=github.com\n"` to read the PAT).

## Known gotchas (all hit and fixed — do not regress)

- **STICKY SOCKET + GET/POST asymmetry (the #1 trap, caused the "device is
  unreachable" setup failure).** The BK808 is a sticky single-connection
  device: it latches the payload it last generated and keeps returning it
  **regardless of the `comhead` you ask for**. And the transport matters:
  a **GET** `/cgi-bin/query` serves the latched blob and does *not* re-latch,
  but a **POST** `/cgi-bin/instr` **re-latches** the device onto the requested
  `comhead`. Consequence: whatever your *first* call asks for becomes sticky
  for subsequent GETs.
  - This is why setup used to fail: the config flow ends by POSTing
    `get input status` / `get output status`, leaving the socket latched on a
    non-video blob; the coordinator then did a **GET** `get video status`,
    which stayed latched → never saw `allsource` → `UpdateFailed: All state
    queries failed` → `ConfigEntryNotReady: … unreachable`. **Fix:** read the
    state via **POST** — `coordinator._read_video_blob()` POSTs
    `get video status` first (reliable re-latch), only falling back to GET.
    Rule: **any read of the routing/blob state must POST, not GET.**
  - It is also why the *names* field differs per blob (`allinputname` vs
    `inname` vs `name`) — see the next bullet.
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
- **Cover bytes.** The bundled cover is read off the event loop via
  `asyncio.to_thread(_read_cover_sync)` in `media_player.py` and
  `asyncio.to_thread(_STATIC.read_bytes)` in `http_view.py`. A plain sync
  `read_bytes` in an async context works but blocks; keep the `to_thread`.
- **HOW THE MEDIA-PLAYER COVER ACTUALLY GETS TO THE CARD.** This is the one
  that bit us in v1.4.6 — read it carefully:
  The frontend media-control card does **not** load `media_image_url` as a
  plain `<img>`. It calls the server-side `media_player_proxy`
  (`/api/media_player_proxy/{entity_id}`), which runs
  `player.async_get_media_image()` and expects it to **return a
  `(bytes, content_type)` tuple**. Our `http_view` route
  (`/local/orei_bk808/cover.jpg`) is a *separate* direct-URL fallback, not the
  primary path. So if `async_get_media_image` ever returns a coroutine (see
  below), the card silently shows the placeholder and you get NO console
  error — just a blank cover.
- **Awaiting async helpers (the v1.4.6 regression).** `_get_cover_bytes()`
  became `async` in v1.4.6, but its call site in
  `async_get_media_image` was left as `cov = _get_cover_bytes()` — i.e. an
  **un-awaited coroutine**. A coroutine is never `None`, so the
  `if cov is None` guard passed, the coroutine was returned up to the proxy,
  and `data, content_type = <coroutine>` raised
  `TypeError: cannot unpack non-iterable coroutine object` → HTTP 500 →
  placeholder cover. **Rule:** whenever you turn a helper async, update every
  call site to `await`. Verify the cover with
  `result = await player.async_get_media_image(); assert isinstance(result, tuple)`.
- **`async def` for HA HTTP handlers.** If you add more `HomeAssistantView`
  handlers, they must be `async def` (a sync handler trips
  `AssertionError: Handler should be a coroutine or a callback`).
- **Config-flow name pre-fill trap.** `async_step_naming` *used to* have a
  `use_device_names` checkbox that defaulted to `True` whenever the device
  reported any name — silently discarding the user's typed names (and the
  sticky device sometimes returned name-less blobs, making it
  non-deterministic — "several attempts"). It then defaulted to `False`,
  which made the box "always look unchecked". **Final fix:** the checkbox is
  *gone*; the two text fields are always pre-filled with the device's names
  and are the single source of truth (do nothing → device names; edit →
  yours). If you add a toggle back, default it OFF and keep the text fields
  authoritative.
- **The BK808 is a sticky single-connection device** and the field names
  differ per response blob: names arrive as `allinputname`/`alloutputname`
  (video-status blob) *or* `inname` (input-status blob) *or* `name`
  (output-status blob). `config_flow._extract_names` accepts all three. Do
  **not** assume a single blob carries a given field.

## Verifying a behaviour fix against the real device

These bugs are all about a *living device*, so unit tests alone don't prove a
fix. Cheap, direct probes (no HA/hass needed) are the fastest way to confirm:

```python
# one-off: reach the matrix straight, print what each comhead actually returns
import asyncio, json, aiohttp, ssl
HOST = "192.168.1.100"                      # or the DNS name
cx = ssl.create_default_context(); cx.check_hostname = False; cx.verify_mode = ssl.CERT_NONE
async def post(s, ch):
    async with s.post(f"https://{HOST}/cgi-bin/instr", json={"comhead": ch, "language": 0},
                      headers={"Content-Type": "application/json", "Accept": "application/json"},
                      timeout=aiohttp.ClientTimeout(total=10)) as r: return json.loads(await r.text())
async def get(s, ch):
    async with s.get(f"https://{HOST}/cgi-bin/query", params={"comhead": ch},
                     timeout=aiohttp.ClientTimeout(total=10)) as r: return json.loads(await r.text())
async def main():
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=cx)) as s:
        # latches a NON-video blob, then check the video read recovers:
        await post(s, "get input status"); await post(s, "get output status")
        print("GET  video:", "allsource" in await get(s, "get video status"), "(may be False!)")
        print("POST video:", "allsource" in await post(s, "get video status"), "(should be True)")
asyncio.run(main())
```

If **GET video = False / POST video = True**, the sticky-latch bug is present
(or, after the v1.4.9 fix, that's exactly why the coordinator must POST).
The repo's `test_live_setup_recovers` is the same check through the real
coordinator (skipped by default — run with
`OROE_LIVE_HOST=<ip> python -m pytest -k live_setup -s`).

## Current state (v1.5.0 — ✅ verified working by user in Home Assistant)

- **v1.4.9 released** (tag `v1.4.9`): the two reported bugs —
  1. *Setup failed: "device is unreachable / All state queries failed".*
     Sticky-socket cause: the config flow ends on a POST that latches a non-video
     blob; the coordinator's GET read stayed latched and raised
     `ConfigEntryNotReady`. **Fix:** `coordinator._read_video_blob()` now POSTs
     `get video status` (reliable re-latch), GET only as a fallback.
  2. *Config naming checkbox always looked unchecked / ignored edits.*
     **Fix:** removed the `use_device_names` checkbox; the input/output text
     fields are pre-filled with the device names and are the sole source of
     truth. `_validate` reads names from any blob and falls back to POST.
  - Added cross-referencing comments between `_validate` and
    `_read_video_blob` so neither gets "cleaned up" into re-introducing the
    sticky-latch failure.
- **v1.5.0 (this):** docs + guard-rail comments only — added the "How to work
  on this repo", "Verifying a behaviour fix", and the interlock comments.
- **✅ VERIFIED BY THE USER.** Full setup → use in Home Assistant confirmed
  working (v1.4.9 fixes: setup failure, cover art, naming all good).
  If a repro ever comes back, start with the probes above and the
  `coordinator` / `http_view` trace in the HA logs before changing code.
