# PandorumLLM — Development Handoff

**Drop this into a new chat together with the current `fleet-panel.py`** (or the whole latest
zip) and work can continue with no ramp-up. It says what the project is, how it is built,
how a release is cut, and — most importantly — the traps that have already cost real
debugging time. **Read §5 before editing anything.**

**Current version:** v3.65 Beta.

---

## 1. What it is

A **single-file, stdlib-only Python browser control panel** (no pip dependencies) that runs
on Windows and drives a local **llama.cpp inference fleet**, plus an embedded
**thinking-proxy** for **SkyrimNet** (an AI-driven Skyrim NPC dialogue mod).

- The **panel** serves a browser UI + JSON API on a dynamic port (written to `panel-port.txt`).
- The **proxy** opens one listener **per provider**, forwards each request to the right
  upstream llama.cpp **server**, and can inspect and rewrite it (thinking toggle, grammar
  injection, per-provider sampler capture and override).
- SkyrimNet points its provider URLs at the proxy's **provider ports (1251–1263)**; the proxy
  forwards to the **server ports (1236 / 1237 / 1238)**.

Distributed **source-visible** with a **SHA-256 per release**. No code signing.

---

## 2. Where things live

- **Installed:** `C:\PandorumLLM\`
- **Models:** wherever the user points; llama.cpp at e.g. `C:\llama.cpp-cuda`
- **Releases:** `PandorumLLM-vX.Y-Beta.zip` + `.sha256.txt`, folder-rooted (top-level
  `PandorumLLM/` inside the zip).

### The 14 files that ship

```
PandorumLLM.exe              MinGW launcher (double-click entry point)
PandorumLLM.ico
README.txt                   user-facing, carries the per-version changelog
fleet-config.default.json    seed config; runtime config is fleet-config.json
fleet-panel.py               THE monolith — ~10k lines
force-stop.bat               last resort; kills only processes from its own folder
launch-llm-fleet.ps1
launcher-template.ps1        GPU-pinned base template
launcher-src/                launcher.cpp, app.manifest, app.rc, PandorumLLM.ico
ps1-launchers/README.txt
templates/single-gpu.ps1     GPU-agnostic template
```

**Runtime-created, never shipped and never committed:** `fleet-config.json`,
`panel-port.txt`, `profiles/`, `logs/`, `models/`, `providerYAML/`, `generated-launchers/`.

---

## 3. Architecture

Two HTTP layers, both stdlib `ThreadingHTTPServer`:

1. **Panel** (`class Handler`): serves the PAGE string on `GET /`, JSON on `POST /api/*`
   via a `routes` dict. Some endpoints (`/api/state`, `/api/stats`, `/api/models`,
   `/api/logs`, `/api/launch`, …) are handled **inline in the dispatcher**, not through
   `routes` — a checker that only reads `routes` will report them as missing. They aren't.
2. **Proxy** (`class ProxyManager` + `_mk_handler`): `PROXY.sync()` reads the config and
   reopens a listener per enabled provider port.

**Config flow:** `load_config()` (fresh read each call) → mutate → `save_config()` (atomic
`os.replace`, fires an SSE `state` event). All config-mutating POSTs run under `CFG_LOCK`.

**Frontend data source:** the UI reads providers from **`state.routing`**, not `state.slots`.
`routing` is built separately and carries `samplers`, `obsSamplers`, `srvSamplers`,
`samplerOverrides`, per-provider `stats`. **Add per-provider display data to the routing
construction, not to `build()`.**

---

## 4. Subsystems worth knowing

- **Model identification (`model_kind`)** — reads the GGUF header and the first 400 tensor
  names. `mtp.*` / `nextn.*` / `eagle.*` → draft; `v.*` / `mm.*` / `vision_model` /
  `resampler.*` → vision; otherwise main. Filename is only a fallback. Every model picker
  colours by this: green if the file belongs there, red if not.
- **Launcher parsing (`parse_launcher_params`)** — classifies every flag. Follows PowerShell
  **variables**: `$modelPath = "…"` then `"-m", $modelPath` resolves correctly. Bare switches
  honour explicit values (`"--fit", "off"` reads as off, not as present).
- **Launcher validation (`validate_launcher`)** — reports each flag as card-setting,
  understood passthrough, sampling default, or NOT RECOGNISED.
- **Launcher sweep (`sweep_launcher`)** — 11 rules for things that don't belong in a file
  whose only job is to start llama-server. **A clean sweep means nothing alarming was found,
  not that a file is safe** — PowerShell obfuscates past any word list. The UI says so and
  the gate enforces the wording.
- **Debug observer** — `traceOn` / `trace(kind, what, why)`, 16 watch points, off by default.
  Records what the page *declined* to do and why, which is where most bugs live.
- **Profiles** — one JSON file each in `profiles\`. Anything left inside the config from
  before is migrated out on first save/load/delete.

---

## 5. Gotchas — read before editing

**1. Duplicated logic is the recurring fault in this codebase.** It has caused more
regressions than everything else combined. The canonical case: the rule "the manual side
step stands in for both yaml steps" was written out in **four** places; each fix corrected
the copies that were visible and missed one, over three consecutive versions. Related: a
second list of step requirements had silently drifted from `HELPER_STEPS`.
**Before fixing a rule, grep for every place that states it, and make them share one.**
The gate now counts several of these.

**2. Escaping inside the PAGE string is brutal.** The UI is one giant Python triple-quoted
string, so Python and JS escaping collide:
- `"\\n"` becomes a JS newline → SyntaxError. Use `String.fromCharCode(10)`; likewise
  `34`=`"`, `39`=`'`, `92`=`\`.
- `&` in any SVG/XML text must be `&amp;`.
- `\/` throws a SyntaxWarning — write `\\/`.
- **Prefer `str_replace` per item** over python heredocs for lines with escaped quotes or
  emoji. A heredoc that asserts before writing leaves the file *untouched* if any assert
  fails — a partial batch means none of it applied.

**3. Anchors drift.** Re-grep before assuming a line still reads as it did.

**4. Emoji render as `??` on some systems.** SVG icons always render. There is a packaging
guard that fails the build if an emoji sits directly against an alphanumeric.

**5. A ring drawn as a shadow is a border.** `box-shadow: 0 0 0 1px <colour>` looks exactly
like a border and is invisible to any check that only reads `border`. Cost two versions.
Nothing at rest may carry a zero-blur ring; hover/focus/open states may.

**6. A shadow only animates into one with the same layer count.** Rest with one layer and
hover with two makes the extra layer appear outright mid-transition — reads as flicker.

**7. Effects must not touch the page while it is in use.** `fxQuiet()` returns a *reason
string* (falsy when safe) for an open menu, dropdown, slider or dialog. It deliberately does
**not** stand down for a focused field — a field is protected by the separate redraw guard,
and pausing the animations for it was a bug.

**8. Two copies of a path.** A server keeps its model in `slots[].model` *and*
`slots[].params.model`; the UI draws from the second. Masking only the first leaked model
filenames to remote viewers for several versions. **If you mask something, mask every copy.**

**9. Booleans in the settings catch-all.** `_HANDLED_KEYS` are excluded from the
stringifying catch-all. **Add any new boolean/object setting to it** or `false` becomes the
string `"False"`, which JS reads as truthy.

**10. Uploads at `/mnt/user-data/uploads/` are replaced every turn.** Read them fresh.

---

## 6. Encoding (enforced by the gate)

| file | rule |
|---|---|
| `*.py` | UTF-8 **no BOM**, **CRLF** |
| `*.ps1` | UTF-8 **with BOM**, CRLF (except `launch-llm-fleet.ps1`: BOM + LF) |
| `*.bat` | no BOM, CRLF, **no carets**, balanced quotes |
| `README.txt` | CRLF, no BOM |
| `app.rc` / `app.manifest` | LF only, no BOM |

Read bytes → decode `utf-8-sig` → normalise LF → **assert counts before mutating** → write CRLF.

---

## 7. Release recipe

1. Bump `APP_VERSION` (read the current value first — it has silently stuck before).
2. `README.txt`: bump the version line, append a plain-language changelog paragraph.
3. `app.rc` (4 places) and `app.manifest` (1) — LF-only files.
4. Rebuild the exe:
   ```
   cd launcher-src && x86_64-w64-mingw32-windres app.rc -O coff -o app.o \
     && x86_64-w64-mingw32-g++ -O2 -municode -mwindows launcher.cpp app.o \
        -o ../PandorumLLM.exe -lws2_32 -static -static-libgcc -static-libstdc++ \
     && rm -f app.o
   ```
5. Stage a clean copy, strip runtime folders, **run the gate**, zip folder-rooted, sha256.

---

## 8. The gate

It runs on the staging copy and **blocks packaging**. Beyond encoding and file-set checks it
enforces, roughly in order of how much grief each has caused:

- **Privacy:** a fully-populated server pushed through `redact_state`, failing if a model
  name, projector, draft, path, IP or GPU serial survives — and confirming `gpuId` is *not*
  masked, since masking it breaks the remote network graph. Plus a scan of every shipped file
  for machine names, GPU serials, emails, personal paths and third-party IPs.
- **Remote boundary:** no mutating endpoint may appear in `REMOTE_READ_OK`; every claim the
  Permission Tree makes is checked against the code that enforces it.
- **Duplication:** the side-step rule must exist in exactly one place; no duplicate JS
  functions, no orphans, no duplicate element ids, no duplicate step lists.
- **Visual invariants:** nothing at rest draws a border or a hard ring; rest and hover have
  matching shadow layer counts; CSS braces balance.
- **Behaviour, in a real browser (jsdom):** menus open, effects stand aside, dropdowns work
  and announce once, no control sits blank, the folder warning appears *and clears*.
- **Parsing:** every launcher the user has shared runs through the validator and must come
  back with nothing unrecognised; a variable-named model resolves; `--fit off` reads as off.
- **The sweep:** real launchers pass; download-and-run, `-EncodedCommand`, Defender changes,
  `schtasks` and remote fetch are all caught.

**A check that verifies a function *exists* is not a check.** The redaction test passed for
several versions while filenames leaked, because it confirmed the masking function was
present rather than that it worked.

---

## 9. Testing

- `node --check` on the extracted `<script>` block catches JS syntax errors.
- **jsdom** loads the real page against the running panel. `fetchstub.js` must set
  `Content-Length` or POSTs arrive with empty bodies.
- **Fire the right event.** Several handlers listen for `click`, not `pointerdown`; testing
  with the wrong one has made working features look broken more than once.
- Isolated-function testing: extract one JS function by brace counting and `eval` it with
  minimal stubs. **Do not `eval` the whole page** — the interval loop hangs.

---

## 10. Security model

- **Host** (localhost) → full control. **Remote** (same-LAN, opt-in) → read-only, redacted.
  **External** → rejected (link-local counts as external).
- `networkMode` defaults to `"localhost"` — **remote is off until deliberately enabled**.
- **No password.** The read-only wall is the boundary. What a viewer can see: terminals
  (including generated dialogue), provider names/ports/allocation, the network graph, fleet
  status. What they cannot: IPs, paths, model filenames, GPU serials, the statistics
  endpoint, Proxy Setup, SkyrimNet YAML, Provider Statistics.
- `origin_host_ok()` guards CSRF / DNS-rebinding. **Zero outbound calls** — the only external
  string is a URL shown as text to copy. Interface detection uses a route lookup against a
  reserved documentation address; nothing is sent.
- Every `subprocess` call uses an argument list. **No `shell=True` anywhere** — keep it that way.

---

## 11. Standing decisions

- No-caching launcher block: `--flash-attn on` / `--cache-ram 0` / `--ctx-checkpoints 0`.
- Terminals align columns with spaces, so **only fixed-width fonts hold them**; the picker
  marks the rest rather than hiding them.
- Recommended Setup places providers by **what they do**: Vision needs a server with a
  projector; Dialogue/Combat/UT/AI-Assistant take the largest model on the strongest card at
  priority 0; GM joins them at priority 1; Meta takes the smallest and drops to 2 if it shares
  a card with the talkers; everything else takes the second model, off the strongest card.
- Restore default providers **repairs in place** — it never reorganises, never allocates, and
  never duplicates. It resets names, icons, priority, thinking, sampler source, detect and
  forced values.
- Windows-only in practice: `llama-server.exe` is hardcoded in ~12 places, and the launchers
  are PowerShell with Windows-only VRAM reporting. The panel itself is portable.

---

## 12. Starting the next chat

> This is **PandorumLLM** — a single-file stdlib-Python browser control panel + embedded
> thinking-proxy for my SkyrimNet local llama.cpp fleet. Current version is **v3.65 Beta**.
> I'm attaching `DEVELOPMENT.md` and the current `fleet-panel.py`. Read the Gotchas section
> first. I want to: **<your change>**.

Then attach this file and `fleet-panel.py` (or the whole release zip if the change touches
the launcher, templates or README). Keep one bug or feature per chat where practical, and
re-cut a release with §7 when done.
