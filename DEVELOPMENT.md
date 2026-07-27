# PandorumLLM — Development Handoff

**Drop this into a new chat together with the current `fleet-panel.py`** (or the whole latest
zip) and work can continue with no ramp-up. It says what the project is, how it is built,
how a release is cut, and — most importantly — the traps that have already cost real
debugging time. **Read §5 before editing anything.**

**Current version:** v3.69 Beta patch5 (`v3.69-p5 Beta` in the header).

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

**Version string.** `APP_VERSION` ("v3.69 Beta") + `APP_PATCH` (an int, 0 = none) are
combined into `APP_VER_UI` — the single source feeding the header, console banner, error
log, launch log, debug report, `X-App` and the page-cache check. `APP_RELEASE_TAG` holds the
GitHub tag this build ships under and **must match the tag actually published**, because the
in-app update check compares against it.

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
- **Model kind cache (`model-kinds.json`)** — `model_kind` opens every `.gguf` to read its
  header; 68 models cost 25s per scan. Results are now cached by path+size+mtime, the scan
  is single-flight (`_MODELS_LOCK`), held 5 minutes, and warmed on a background thread at
  startup. A scan over a second logs itself. **Runtime state — gitignored.**
- **Live updates** — one SSE stream (`/api/events`) drives everything. `liveRefresh()` is the
  *single* per-tab refresh rule; the SSE handler, the auto-refresh tick and the heartbeat
  fallback all call it. Every event carries a sequence number echoed by the 5s heartbeat, so
  a silently dead stream is caught within ~5s and the EventSource rebuilt. `load()` →
  `paintChrome()` + `renderCurrent(force)`; the don't-redraw-a-focused-field guards live
  *inside* the renderers.
- **Self-timing** — 17 helpers are wrapped by phase (`port-probes`, `model-folder-scan`,
  `launcher-parse`, `address-lookup`, `folder-checks`, …). Any `/api/state` over 500ms writes
  a line naming the slow phase; the debug report ends with a full breakdown and an
  `everything-else` remainder, so a slow call is never unexplained. **Use this before
  guessing at performance.**
- **Provider enable/disable** — a provider switched off keeps its port shut (the proxy skips
  it, the yaml writer skips it). This is what lets a second PC serve that provider instead.
  Power button at the right of each provider card, green on / red off.
- **Host/client peer view** — Live Network has Host and Client tabs. Set another panel's
  address in Proxy Setup and the Client tab draws `netCard()` from *its* state. Pull, not
  push: the host reads the peer's ordinary read-only remote view, so no new endpoint and no
  inbound surface. Background thread, 5s interval, 2s timeout — **never on the request
  path**. There is no "client mode": a client is a panel with Remote Access on.
- **Update check** — the version in the header is a button. `api_app_update` asks GitHub for
  the newest release tag once per session, cached 6h, and compares it *numerically*
  (`_ver_tuple`: `v3.69-beta-patch5` → `(3,69,5)`). States: behind (pulsing yellow +
  "Update available!"), current, ahead, unknown.
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

**10. `connect_ex` on Windows lies about refusals.** On a socket with a timeout it does
**not** return `WSAECONNREFUSED` — it waits out the entire timeout and returns
`WSAEWOULDBLOCK` (10035). This produced a completely false diagnosis ("your machine is
filtering loopback, check your firewall") and three releases of wrong tuning. **Use
`connect()` and catch `ConnectionRefusedError`.**

**11. `socket.create_connection` and `urlopen` call `getaddrinfo` even for `127.0.0.1`.**
On a box with no default gateway that can cost ~1s per call. For loopback probes, use a raw
socket and speak HTTP over it.

**12. Nothing slow may sit on the request path.** Every multi-second stall in this project
traced to blocking work inside `/api/state` — a name lookup, a port probe, a model scan.
Background thread, short timeout, cached result, and the UI degrades to "not reachable".

**13. Masking belongs at the boundary, not in the page.** Filtering in the renderer still
ships the secret to the browser. `api_tail` takes the caller's scope and strips path-shaped
text before returning; a masker that throws must fail **closed** (return a placeholder), not
hand back the raw line.

**14. Flex `order:N` moves an item past full-width siblings.** A button ordered to the end
of a wrapping row landed on a row of its own. To sit beside content regardless of wrapping,
position it against the card (`position:absolute` + the card `position:relative`).

**15. `change` never fires for a `<button>`.** A button wired to a field handler that reads
`ev.target.value` silently does nothing. Give it its own click action.

**16. Uploads at `/mnt/user-data/uploads/` are replaced every turn.** Read them fresh.

**17. A containment check built from the thing it checks cannot fail.** The TTS launcher
write was gated with `_within(outd, _all_roots(cfg))` - but `_all_roots()` is built *from*
`outputDir`, so the test contained the folder it was testing and passed for every input,
including traversal out of the launcher folder. It read as a security control while
enforcing nothing. Reachability was the real control: the endpoint is absent from
`REMOTE_POST_OK`. **Before trusting a guard, feed it something that must fail.**

**18. Reading a CRLF file in text mode defeats any `\r\n` check.** Python's universal
newlines collapse `\r\n` to `\n` on read, so `open(p).read().split('\r\n')` returns one
element and every per-line assertion silently examines nothing - reporting a clean pass.
Hit twice in one session. **Open in binary for any line-ending or per-line gate.**

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

**Fixtures must use documentation-reserved values** - RFC 5737 addresses, an all-zero UUID,
a drive letter that exists nowhere. A fixture copied from a real machine puts that machine in
a public repository, and `gate.py` is committed. The gate checks its own source for this, and
reads **the file being run** rather than a name looked up in the tree.

**Never narrow a check to silence it.** The personal-data scan flagged the gate's own
fixtures on its first run; narrowing it to shipped files hid a real finding for eight
patches. If a check fires on the checker, fix the checker's data, not its scope.

**The Permission Tree is a claim about the code and drifts silently.** It named three
terminals for a build with four and omitted TTS entirely, because the section 8 check tying
its claims to enforcement had never been written. It exists now: terminals named vs
`showTsub`'s list, and every page called withheld vs `data-hostonly` **or** a scope redirect -
there are two enforcement mechanisms and a check that knows only one produces false failures.

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
- `origin_host_ok()` guards CSRF / DNS-rebinding. **No *automatic* outbound calls, but no
  longer zero.** Two exist, both host-only, both plain GETs of public pages with nothing
  about the setup sent: the llama.cpp update check (only when pressed) and the app version
  check (once per session, cached 6h). Interface detection uses a route lookup against
  `10.255.255.255` - a UDP `connect` that transmits nothing and never leaves the host. It is
  RFC 1918 broadcast space, **not** a documentation address; the mechanism is sound but do
  not repeat that description. **`README.md` still claims zero outbound
  connections and needs correcting.**
- **A peer address is host-identifying.** `peerAddr` is masked in `redact_state`, and log
  feeds have paths stripped for non-host readers.
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
> thinking-proxy for my SkyrimNet local llama.cpp fleet. Current version is **v3.69 Beta patch5**.
> I'm attaching `DEVELOPMENT.md` and the current `fleet-panel.py`. Read the Gotchas section
> first. I want to: **<your change>**.

Then attach this file and `fleet-panel.py` (or the whole release zip if the change touches
the launcher, templates or README). Keep one bug or feature per chat where practical, and
re-cut a release with §7 when done.

---

## 13. TTS [Alpha]

**The chain.** SkyrimNet -> a wrapper on :7860 -> `moss-tts-server.exe` on :1240 -> a GPU.
`moss-tts-server.exe` is a separate binary from the openmoss build (not llama-server) that
loads a GGUF and answers plain JSON. **The wrapper exists only to translate** between that
and the Gradio client protocol SkyrimNet's Zonos engine speaks.

**Zonos is a first-class SkyrimNet engine** - its own `ZonosInterface.cpp`, its own engine
type, its own preloading policy. So the wrapper is not bridging an *unsupported* engine; it
makes MOSS-TTS **impersonate a supported one**. That matters: the contract is fixed and
public (documented below), so anyone writing a replacement is implementing a known spec
rather than reverse-engineering. It also means a wrapper is only needed for backends
SkyrimNet cannot drive itself - engines it speaks to directly need none of this, which is
why the whole feature stays optional rather than foundational. *(Which engines those are is
not established by any log held here: a session only ever shows the one engine configured.)*

**Three options, in escalating cost. The alpha is 1.**

1. **The user's wrapper, our launcher and terminal.** What v3.70 ships. Nothing new runs and
   nothing new is written - the panel generates the launcher, tails the log, renders the
   terminal. No TTS traffic passes through the panel at any point.
2. **PandorumLLM ships a wrapper.** Still a separate process the user starts, just one we
   wrote - stdlib-only, no Gradio. For people who have no wrapper of their own.
3. **The panel becomes the wrapper.** The proxy speaks Gradio to SkyrimNet and MOSS's JSON to
   the server, with no separate process. **Set aside deliberately:** it puts the panel inside
   SkyrimNet's 15s TTS budget, and closing the panel would kill voices.

### What was built

`Proxy > TTS [Alpha]` - host-only, since it shows filesystem paths. Settings for the server
(binary, GGUF, port, GPU by UUID) and the wrapper (python, script, port), keys `ttsServerExe`,
`ttsModel`, `ttsServerPort`, `ttsGpuId`, `ttsPython`, `ttsWrapper`, `ttsWrapperPort`. Preview
renders the launcher; **Write start-tts.bat** saves it to the launcher folder
(`api_tts_launcher`, generator `tts_launcher_text`). Each path field has a **Choose file**
button, and **Import from a launcher** (`api_tts_import`) reads all six settings out of an
existing `.bat`/`.cmd`/`.ps1` - classifying by **extension, not variable name**, so it works
whatever the author called things, and returning only the recognised fields rather than the
file. `api_browse_dirs` gained an optional `exts` filter for this: it is the same host-only
endpoint that has always browsed the whole filesystem, because setting a path means reaching
somewhere not yet configured. **Split paths on `[\\/]`, not `os.path.basename`** - basename
does not treat a backslash as a separator off Windows, which silently mis-filed every path
and made the classifier untestable anywhere but Windows. A **fourth terminal** beside
Proxy/Thinking/Split tails `tts.log`.

The terminal is a **fixed `tts` kind in `api_tail`**, not `kind=file`. `kind=file` is 403'd
for remote sessions because it reads a caller-supplied path; a fixed kind resolves one known
name inside `log_dir()`, so it carries no path and stays readable on remote with
`_mask_paths_in` applied like the other three. **An externally-written log has no notifier.** `sse_notify("tail")` fires from
`PROXY.report()`, which only runs when the panel writes the proxy/thinking logs itself.
`tts.log` is written by another process, so `status_watch_loop` stats it every second
(guarded on `SSE_CLIENTS`, so idle when nobody is watching) via `tail_watch_sig()` and
notifies through the same path. Signature is **mtime plus size** - a same-second append can
leave mtime unchanged on Windows. Any future log the panel does not write itself needs the
same treatment.

The open terminal maps to its feed in **one** place, `refreshCurTerm()`, called by both
`showTsub` (on open) and `liveRefresh` (every tick) - a terminal wired only into the first
renders once and then goes stale until reload. It is
deliberately absent from `termScales`/`TS_KINDS`, so `tsForId()` and `maxKindForId()` fall
through to their `dashboard` defaults and it shares that terminal's font and size. **A
terminal kind is currently stated in ~14 places across two naming schemes** (`showTsub` uses
proxy/think/split, the scaling layer uses dashboard/thinking/splitd/splitt, `tKind()` bridges
them). Adding a fifth registered kind should collapse that to one table first - and note
`api_settings` filters `termScales` against a hardcoded tuple, so an unlisted kind is
**dropped on save with no error**.

### The protocol, confirmed

Five operations per line, not three. All confirmed against a real SkyrimNet log:

1. `POST /gradio_api/upload` (multipart) -> `["<abs path>"]`, a JSON array of one string
2. `HEAD /gradio_api/file=<abs path>` -> 200/404. **SkyrimNet skips re-uploading a voice it
   already sent** - 8 HEADs against 2 uploads over 5 generations. A wrapper that mishandles
   this gets the reference voice re-uploaded on every line.
3. `POST /gradio_api/call/generate_audio` -> `{"event_id":"<32 hex>"}`
4. `GET /gradio_api/call/generate_audio/<event_id>` -> SSE:
   - success: `event: complete` then `data: [{"path": ..., "url": ..., "size": null,
     "orig_name": ..., "mime_type": null, "is_stream": false, "meta": {"_type":
     "gradio.FileData"}}]`
   - failure: `event: error` then `data: {"error": null}`
   - **note the asymmetry**: `data` is an array on success, an object on error.
5. `GET /gradio_api/file=<abs path>` -> **the WAV bytes**. The SSE returns only a path.

SkyrimNet takes the `path` field and rebuilds the URL against its own configured endpoint; it
does not follow `url`. So `url` may be approximate, `path` must round-trip.

**Field order (29 positional), verified against the wrapper signature:** `model, text,
language, speaker_audio, prefix_audio, tone_happiness, tone_sadness, tone_disgust, tone_fear,
tone_surprise, tone_anger, tone_other, tone_neutral, vq_score, fmax, pitch_std, speaking_rate,
dnsmos_overall, denoise_speaker, cfg_scale, top_p, min_k, min_p, linear, confidence,
quadratic, seed, randomize_seed, unconditional_keys`.

The request body is **never logged** - only URLs. But SkyrimNet logs what it prepares in the
~50ms before the POST, which pins several fields: `text` and `language` from
`ZonosInterface.cpp:277/299`, `speaker_audio` from the upload that precedes it, and
`prefix_audio` from the second, smaller upload resolved immediately after. The ping is the
control case: one audio upload, not two.

### What the reference wrapper actually does

- **27 of the 29 parameters are accepted and discarded.** Only `text` and `speaker_audio` are
  used. Everything reaching moss-tts-server is `{"text", "max_new_tokens"}` plus
  `reference_wav_b64`. **Every sampler in SkyrimNet's Zonos panel is inert** - cfg_scale,
  top_p, seed, pitch_std, the eight tone values, all of it.
- **The wrapper appends the full stop.** `normalize_text()` adds `.` when text does not end in
  punctuation, so `ping` arrives as `ping.`. Any local ping answer must normalise before
  comparing, never test against the literal.
- Long text is split into ~170-char chunks, fired concurrently (max 4), stitched with 100ms
  of silence, written to a temp WAV whose path Gradio returns.
- Reply headers carry `X-MOSS-Generate-Seconds` / `X-MOSS-Decode-Seconds` /
  `X-MOSS-Audio-Frames`; `overhead = wall - generate - codec`, so overhead is purely wrapper
  work.
- It is **not** stdlib - numpy, requests, soundfile, gradio. A replacement could be
  (`http.server` + `urllib` + `wave` + `base64`), which is what keeps the no-dependencies rule
  available.

### Decisions - build, do not relitigate

- **Generate the launcher, not the wrapper.** A launcher is flags and substitution; a wrapper
  is a protocol translator, one per engine, that the panel cannot test.
- **The wrapper stays the user's own.** A shipped one can come later.
- **Do not proxy TTS traffic.** It adds a hop inside SkyrimNet's 15s timeout and makes voices
  depend on the panel running. Available later, opt-in, for users with no wrapper.
- **A shipped wrapper emits JSON stats beside the human log.** The panel must never regex its
  own prose: statistics would read `tts-stats.jsonl`, the terminal renders `tts.log`.

### Launcher traps, all mandatory

- `CUDA_VISIBLE_DEVICES=<uuid>` then **`--main-gpu 0`** - after masking, the chosen card
  re-indexes to 0. The classic mistake.
- **`-X utf8`**: into a pipe Python falls back to the locale code page (cp1252), which cannot
  encode the wrapper's emoji - it crashes on the first print. Plus
  `[Console]::OutputEncoding = UTF8` so PowerShell decodes it back.
- **`-u`**, or output block-buffers and the log looks dead.
- **cmd's `^` escapes only outside double quotes.** Inside a quoted `-Command` it reaches
  PowerShell as a stray token. The one caret the file needs is `2^>nul` inside `for /f`,
  which is outside quotes and required.
- **Export `MOSS_TTS_URL`.** The wrapper reads it from the environment and otherwise falls
  back to a hardcoded `127.0.0.1:1240`; without it, changing the server port moves the server
  while the wrapper keeps calling the old one.
- The log **must** live in the panel's `logs\` folder: `api_tail` joins a *name* to that
  folder.

**Both listeners bind `0.0.0.0`, so both must filter clients.** `ProxyManager` has always
applied `PROXY.allow` (built from `remoteIp`/`panelIp`); the TTS listener shipped without it,
which meant the panel refused a stranger on one port and served them on the next. It now
reuses the same allowlist rather than keeping a second one. Bodies are capped at 32 MB -
never allocate what a caller claims. **Any new listener inherits both requirements.**

**`queueLoad` defers every reload while a write is in flight** (`uiBusy` ->
`writesInFlight`), so a long-running POST hides all state change until it returns. Terminate
runs `run_fleet(["-Stop"])` and can take seconds; the SSE event fired at once and the reload
was postponed past it. **A caller that starts something long must mark the affected pane
itself** - `terminateAll` sets `ttsBusy` and clears it in a `finally`, exactly as the Stop
button does. No amount of server-side notifying fixes this.

**A synchronous stop cannot report itself.** `stop_tts_server` waited for the process to
exit before returning, which blocked the very response that would have told the page
anything was happening - and by the time it answered, the port was released and the status
read `down`. A state added for the gap could never appear. Stop and Terminate now terminate
on a thread, `sse_notify` **before** blocking, and report `stopping` until the process is
gone; only `full_exit` still waits, since the process is about to end anyway.

**Terminal scale kinds are one tuple.** `TERM_SCALE_KINDS` in Python drives `api_settings`
validation and is injected into the page as `__TSKINDS__`; `termScales`, `tsForId` and
`maxKindForId` derive from it rather than restating it. Before this, a kind the page knew
about but the Python tuple did not was **dropped on save with no error** - the fifth
terminal is why it finally got collapsed.

**Redraw from `renderCurrent`, not `liveRefresh`.** `liveRefresh` runs first and only
*queues* the state fetch; `load()` then fetches and calls `renderCurrent`. A pane redrawn
from `liveRefresh` renders with the state it already had - it looks correct in the source
and changes nothing on screen. `renderCurrent` falls through to `renderRouting`, which
returns unless Proxy Setup is open, so any other dashboard pane needs its own branch there.

**A pane that is not in `liveRefresh` shows yesterday.** `dpane-tts` was redrawn only by the
Start button's own poll, so a change from anywhere else - Terminate, exit, a crash - left it
claiming the server was up. Any pane showing live state needs an entry there **and** a
focused-field guard. The state itself needs a source too: `status_watch_loop` tracked only
`cfg["slots"]`, so the TTS port could come and go without producing an event.

**Stopping it.** `full_exit` (which the watchdog calls once the last browser client stops
heartbeating) stops the fleet, so a panel-started TTS server must go with it - otherwise it
holds the model in VRAM with nothing able to reach it. `stop_tts_server()` is the single
implementation, shared by exit, Terminate and the Stop button, and it stops **only what the
panel started** (`TTS_PROC["proc"]`), never whatever holds the port: in launcher mode the
server belongs to the user's script and must outlive the panel.

**Starting the server.** `api_tts_server` start/stop, reusing `slot_status()` (cached,
resolver-free - see gotcha 11) for readiness and `_kill_port_owner()` to stop. Spawned with
an argument list, no `shell=True`, `CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP`, stdout to
`tts-server.log`. Start is a no-op while the port already serves, so it cannot race a
hand-run launcher into a second server.

**Documented in-app** at User Guide > TTS Guide (`renderTtsGuide`), including that this
targets one specific MOSS-TTS build. The engine is hardcoded even though every path is not:
the `/tts` upstream route, the `max_new_tokens` / `reference_wav_b64` request fields, the
`X-MOSS-*` response headers and the `--no-webui` server flag all follow that build.

### Still open

- **`ttsWrapperPort` is not honoured.** The reference wrapper hardcodes `WRAP_PORT = 7860`.
  The launcher exports `WRAP_PORT`; making the field real needs one line in the wrapper:
  `WRAP_PORT = int(os.environ.get("WRAP_PORT", 7860))`.
- **The startup ping is intermittent.** It sometimes fails at Gradio's input handler before
  `generate_audio` runs (which is what the wrapper's stderr filter swallows), and sometimes
  succeeds and spends 600-1100ms of GPU generating the word "ping". Answering it locally would
  catch the expensive half; the failing half already costs nothing.
- Wrapper waste: the reference base64 is sent **once per chunk**, not once per request, so a
  four-chunk line sends it four times. Single-chunk lines are still decoded to numpy and
  re-encoded. Connection reuse **is** present (`Session` + pooled adapter). Overhead measures
  500ms cold and 269-351ms warm, against 600-1100ms of generation - not urgent.
- The reference wrapper writes a permanent WAV per generation to its samples folder,
  uncapped. The embedded one prunes to the newest 24 (`TtsWrapper.prune`), the same shape as
  `prune_keep_newest` for the panel's own logs - anything the panel writes per-request needs
  a bound or it grows for as long as the game runs.
