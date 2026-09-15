# PandorumLLM — Development Handoff

**Drop this into a new chat together with the current `fleet-panel.py`** (or the whole latest
zip) and work can continue with no ramp-up. It says what the project is, how it is built,
how a release is cut, and — most importantly — the traps that have already cost real
debugging time. **Read §5 before editing anything.**

**Current version:** v3.80 Beta (`v3.76-p24 Beta` in the header).

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

**Version string.** `APP_VERSION` ("v3.80 Beta") + `APP_PATCH` (an int, 0 = none) are
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

### The 17 files that ship

```
LICENSE                      source-visible, no-redistribution licence
PandorumLLM.exe              MinGW launcher (double-click entry point)
PandorumLLM.ico
README.txt                   user-facing, carries the per-version changelog
StartPandorumLLM.bat         plain-text way in when an antivirus blocks the exe
fleet-config.default.json    seed config; runtime config is fleet-config.json
fleet-panel.py               THE monolith — ~27,700 lines
force-stop.bat               last resort; kills only processes from its own folder
launch-llm-fleet.ps1
launcher-template.ps1        GPU-pinned base template
launcher-src/                launcher.cpp, app.manifest, app.rc, PandorumLLM.ico
ps1-launchers/README.txt
server-templates/pinned-server.ps1  server template: one card, pinned, no fitting
templates/single-gpu.ps1     GPU-agnostic template
```

**Repo-only, never in the release zip:** `gate.py`, `.gitattributes`, and
`gate-tools/` - `page-sandbox.js` (the shared window), `render-check.js` (the page
draws), `ref-check.js` (what the painters produced), `paint-diff.js` (one painter,
two builds, a corpus, diffed byte for byte), `term-diff.js` (one whole TERMINAL
over a real feed - the acceptance differ for painter migrations, and the gate runs
it: see section 8) and `entity-diff.js` (the entity resolver's answers - ready
set and probes - between two builds; the gate runs it with a moved-palette
control).

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
  (`_ver_tuple`: `v3.75-beta` → `(3,75,0)`, `v3.75-beta-patch5` → `(3,75,5)`). States:
  behind (pulsing yellow +
  "Update available!"), current, ahead, unknown.
- **Profiles** — one JSON file each in `profiles\`. Anything left inside the config from
  before is migrated out on first save/load/delete.

---

- **The action branch (Proxy terminal)** — an action pick is two requests: category,
  then drilldown. `note_actor` knows both prompt shapes; `is_action_drill` reads the
  stage off the request's own introduction — the reply cannot carry it, since the
  intent rule is routinely ignored and param-less direct actions exist. `action_row`
  is the pure formatter: a category row stays open (├─), a drilldown row closes the
  branch (└─) and carries the parameters, and a drilldown's record title wears
  `DRILL_MARK` — `hasRecord` owns that shape, so the provider filter hides both
  together.

- **Automatic TTS calibration (`tts_auto_cap`)** — every successful line is recorded
  (`tts-measure.json`: chars, tags, pause seconds, spoken seconds); the overrun record
  keeps only the failures. Four modes for the per-line token cap: `off` (the fixed
  3.5 tok/char runaway guard, byte-identical to before), `algo` (median measured
  chars-per-second, seed 15 until five lines exist), `llm` (one small question per
  line, 3 s budget, algo fallback on any failure), `median` (an LLM fits
  `{cps, lead}` once via Derive; the proxy applies it by arithmetic). Invariants the
  gate holds: no mode ever exceeds the runaway guard or sinks below the lead-in
  floor, pause tags buy their silence, and a fit outside 6–30 chars/s is refused.

- **The auto-cap headroom (`tts_autocal_headroom`)** — the cap is a stop-loss: the
  engine stops at its own EOC token, so the cap cannot shorten a line and cannot
  reduce EOC failures (chunk size and end punctuation do that — the manual record
  counts both). Below the real need it converts good lines into retries, which is
  slower. So each measurement records the bare estimate in force (`est`), the fit is
  `tok/est`, and `auto` headroom is the worst observed miss × 1.10, clamped 1.05–2.5,
  seeded at 1.35 until 8 fitted lines exist. A hand-typed number is the user's and is
  obeyed. `autocal_algorithm_text()` is written FROM the constants so the explanation
  cannot drift from the code, and the Prompts button returns the same objects that
  are sent.

- **Auto-calibration modes (`autocal_mode` / `autocal_use_fit`)** — off / proxy /
  llm. `algo` and `median` were the same arithmetic with and without an LLM-fitted
  rate, so both normalise to `proxy` and `median` additionally implies
  `ttsAutoCalUseFit` — a saved setting must never quietly come to mean something
  else. The page has the same mapping in `autoCalMode`, and the gate checks the two
  agree. LLM mode refits every N lines (`autocal_every`, 5–250) on a background
  thread via `autocal_derive`, which the button also calls — one implementation, one
  set of bounds. Proxy never starts a model call, by definition.

- **Speech sampling (`tts_samplers`)** — ONE rule for what a request carries:
  SkyrimNet's observed values (when pass-through is on), then anything set on the TTS
  page, then — on attempt 2+ — the steadier retry profile (temp x0.8, rep 1.0,
  top_p <=0.9), switchable. `TTS_SAMP_LAST` publishes what was sent so both records
  keep it: `tts_measure_row` for lines that finished, `eoc_record` for lines that did
  not. `tts_sampler_board` joins the two into a failure rate per configuration,
  counting **first attempts only** — a retry runs a profile it was not chosen for.
  The cap bounds the COST of a runaway; the sampler is the only lever on its
  FREQUENCY, and it was the one thing never recorded.

- **Idle-gating a background model call (`autocal_wait_idle`)** — `PROXY.busy(port)`
  is a COUNT, not a guess: the panel forwards every request itself, so it increments
  on the way in and decrements on the same `finally` that releases the GPU gate. The
  fit waits for that count and `TTSW._inflight` to be zero *before* it calls, because
  a call in flight cannot be taken back; if the server stays busy for ~2 minutes it
  gives up and the next tick tries again. Auto Calibration waits the same way before
  each of its two calls.

- **Learned headroom (`tts_autocal_fit` / `tts_autocal_headroom`)** — no setting, no
  override. Three corrections found in the field: (1) score only rows whose
  `bound == "estimate"`, since a floor-covered short line never tested the estimate
  and its 2.4x 'miss' cost nothing; (2) a runaway is a CENSORED observation entered as
  `cap/est`, because the fit record otherwise contains survivors only and reads low
  exactly where lines are being lost; (3) `tts_measure_ols` fits the same lines by
  least squares — it is the hint given to the model and the bar its answer must clear
  (`tts_fit_mae`), because ten model fits running returned `lead 0.0`, which is
  physically wrong and made every short line read as a huge miss.

- **Saying "do not think" (`apply_route_shape`)** — three fields, sent together,
  to every server whatever its launcher says:
  `chat_template_kwargs.enable_thinking`, top-level `enable_thinking`, and
  `reasoning.enabled` (the form SkyrimNet sends). Builds disagree about which they
  honour; none mind an extra. Still NOT `reasoning_budget_tokens: 0` — see gotcha on
  patch38. The ON arm is symmetric since patch99: it ASSERTS `enable_thinking: true`
  rather than merely removing the false, because absent means "whatever that server
  defaults to" and the default is false both under `--reasoning off` and under the
  Reasoning dial's own launcher line (gotcha 73). `slot_reasoning`
  (mtime-cached, the launcher file is on the PTI hot path) lets a server card set to
  `--reasoning off` force the request side off, overruling a provider or the
  panel. Panel TTS jobs pick their server and thinking per job: `tts_job_port` /
  `tts_job_think` with `fit` and `calib`, each falling back to the other's server so
  one picker still works — and `jobPort()` answers the same question on the page, so
  the picker cannot promise a server the panel would not ask (gotcha 74).

- **TTS page layout (`ttsTitle`, `ttsCalRow`, `ttsJobCell`, `ttsBtnCell`)** — one
  shape for a setting row: titled setting, the server that carries it out with its
  thinking switch, whatever else that choice brings, then the button that shows what
  it sends. The row is `nowrap` with `min-width:0` on every cell — a fixed-width
  middle cell wraps the moment the content is wider than the guess, and a control on
  its own line stops reading as part of its setting. Readings go UNDER the row
  (`ttsCalNote`), never in it. Explanations live in the
  title tooltip, never as grey paragraphs between controls; `.tsplit` separates
  groups; a measurement the section exists to produce gets `.headnow` (white, lit)
  and sits beside the picture it explains (patch109).

- **Sampler auto-calibration (`autocal_sampler_run`, `ttsSampAutoCal`)** — the
  second half of the automatic run, taken every N lines after the fit when the one
  switch is on. The switch shows the sampler settings AND enables the automation;
  off hides and stops both — stored values keep applying regardless, and the gate
  holds that `cal_overrides` never reads the switch. Diagnosis precedes the change
  by construction; every refusal writes one line to the feed (patch108).

- **Cautions on dial values (`PARAM_CAUTION`)** — keyed by VALUE, not by setting,
  and sent to the card in `paramDefs` so the rule lives in one place. A ⚠ appears
  beside a dial only while it stands on that value, with the consequence in its
  title. First entry: `reasonfmt: none`, which leaves the model's thinking in the
  visible answer for TTS to speak (gotcha 73). A caution never restricts the dial.

- **The panel's own model jobs (`panel_chat`, `PANEL_JOBS`)** — three questions the
  panel asks a server itself: `fit` (Speech Fit, refits the speech rate), `diag`
  (Diagnose, reads the failures) and `calib` (Calibrate, chooses the settings). All
  five call sites go through `panel_chat`, which builds the route with
  `diag_route(..., job=)` and reports through the same `PROXY.report` the proxy and
  PTI/PME use — so each appears in the Proxy terminal as a generation and counts in
  the server statistics. Titles are 13 characters or fewer (`proxy_line_text` pads
  the name column) and the ids differ so a fit and a calibration do not merge. No
  gate is held: these are asked after `autocal_wait_idle` finds a gap, or by someone
  pressing a button and waiting for the answer.

- **`--chat-template-kwargs` (the Reasoning dial's second line)** — llama.cpp takes
  a JSON object here and uses it as the default template kwargs for every request. It
  logs that setting `enable_thinking` this way is deprecated and honours it anyway;
  some models honour only this, which is why the dial writes both it and
  `--reasoning`. `CTK_FLAG`/`CTK_NO_THINK` are one constant pair shared by the
  generator and the in-place editor. The value is emitted **single-quoted** — a JSON
  string cannot sit inside a double-quoted PowerShell string — so `ps1_set_flag`
  matches the two quotings separately, and `after=` places a new flag beside the one
  it belongs with instead of at the end of the array.

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

**19. A cheap trust check must test the value, not where the value sits.**
`tts_ref_canonical` decided a reference voice was already canonical by finding `data` at
offset 36. 160 voicetype WAVs have `data` at offset 36 and then declare its size as
`0xFFFFFFFF` - a streaming writer that never went back to patch the header - so every one
of them was judged canonical and handed to audio.cpp, which refuses them with `failed to
read WAV data chunk`. The repair had existed the whole time; only the condition was blind.
A header check now asks whether the 44 bytes describe exactly the bytes that follow
(`tts_wav_head_ok`), and it is one predicate, not a copy per caller.

**20. The gate must not write into the tree it is judging.** Importing `fleet-panel.py`
left `__pycache__` behind, and the junk sweep that forbids it runs *before* that import -
so the run passed and the **next** one failed, blaming the tree. Worse, anything calling a
panel function inherits the panel's roots: `STACK` is the folder holding `fleet-panel.py`,
so one `panel_log()` inside a check writes `logs\panel.log` and `fleet-config.json` into
the tree under test. `sys.dont_write_bytecode` before the import, panel loggers held aside
around any check that calls into the panel, and **the same junk sweep repeated at the end
of the file** - which is what makes both stick.

**21. A format string written out twice does not stay the same twice.** The Proxy
terminal's one-line record existed in `PROXY.report` and again in `proxy_log_line`. They
looked identical and were not: the provider copy filled the prompt-speed column from
`timings`, the panel's copy had `"?"` written into that slot as a literal. Nobody was
going to notice by reading, because each copy was self-consistent. `proxy_line_text` is
the one shape now, and the gate asserts the layout string exists exactly once and that
both writers put `tok` and `tps` at the same offsets.

**22. Count where an event settles, not where it arrives.** A SkyrimNet reply reaches the
panel in several pieces and `mood_note_line` fires on each; only the last survives the
`_MOOD_GEN` guard. A frequency counter incremented on arrival would therefore run down
three or four times over one line and read the scene far more often than asked. The count
belongs *after* the guard, in `mood_due()`. Anything else keyed to "one NPC line" has the
same trap.

**23. A vocabulary check must use the vocabulary, not the printed list.** PME's answer
was held against `TAG_OFFER["Emotion"]` - the one preferred spelling per tag that the
prompt prints - while the tag translator accepts every alias in `TTS_ALIAS` plus every
raw Higgs name. A reader answering `angry` had the whole line discarded even though the
panel renders `angry` perfectly. Where two parts of the panel accept "the same" words,
they must read from the same table.

**24. Rejecting something silently makes it look like a different bug.** The same parser
dropped a line naming `contempt`, which Higgs genuinely has no tag for. The refusal was
right; the silence made a two-line reading look like a one-line one, and the reported
symptom was truncation. Anything discarded on the way to a model should say so.

**25. Recognise a special case at the door.** The startup ping was tested for after the
tagger had marked it up and the mood reader had recorded it, so `ping.` was tagged as
player dialogue and spoken back as `[sound_ping] ping.` The test itself was correct - it
was six statements too late. A line that is not dialogue should stop being treated as
dialogue at the first opportunity, not the last.

**26. A guard can be masked by a second thing that already prevents the fault.** Removing
the `PANEL_PROV_IDS` skip from `_desired` changed nothing, because those records carry no
port and `int("")` was already stopping the bind. Same with forcing Server Side in
`provider_route` - `ensure_panel_providers` corrects the record on load, so the route-level
force never ran in the test. Both guards are worth keeping, but a check that cannot reach
them is not a check. **Break the outer thing too, then see if the inner one holds.**

**27. Testing that a shared function works is not testing that anyone calls it.**
Replacing `apply_route_shape(d, rt)` in the proxy handler with `pass` left the gate green:
every check was on the function, none on the call site. Extractions need both.

**28. A CSS variable cannot go where a string is concatenated.** `netBox` builds its ring
colour as `col + "3d"`, appending hex alpha. Passing `var(--acc)` produced `var(--acc)3d`,
which is invalid, so the browser discarded the whole `box-shadow` - ring and glow together,
silently. Read the computed value when a colour has to be pasted into a larger string.

**29. Whitespace between elements is not a gap inside a flex row.** The mark and the
title were separated by `+ " " +` and the space collapsed to nothing, because `.nb-t` is
`display:flex`. Space between flex children is `gap` or a margin on one of them.

**30. An early return above a `try` skips its `finally`.** `_run_inner` releases the
waiting request handler in `finally: ev["done"].set()`. The ping answer was added as a
`return` *before* that `try`, so a probe was answered and the handler was never told - it
waited out `TTS_RESULT_WAIT_S`, 120 seconds, and SkyrimNet queued everything behind its
own startup ping. **When a function's contract is "the caller is waiting on an event you
must set", every statement belongs inside the try, not just the risky-looking ones.**
Anything that raised in the tagger or the tag translator had the same effect.

**31. A stub has to outlive the thread it stubs.** The gate check for the above drives
`_run_inner` with `CONFIG` pointed at a temp folder. `mood_note_line` schedules a thread
that wakes `MOOD_SETTLE` seconds later and calls `load_config()` - by which time the
`finally` had put `CONFIG` back, so the thread wrote into the tree under test and the
trailing sweep blamed the run. Stub the scheduler, not just the destination.

**32. Changing a signature is not finished until every reader of the old argument is
gone.** `_chat(port, ...)` became `_chat(rt, ...)`, and `ptipme_log("PTI", port, ...)` two
lines below kept the name. Python binds names at run time, so it compiled, imported,
passed 1311 checks and only failed when the player spoke. **A static undefined-name sweep
over the module is now a gate check** - and when you write one, build the module-level set
from the module BODY only: collecting names assigned inside other functions makes every
local of every function look like a global, which is how `port` passed on the first try.

**33. A mechanism that FORCES a token cannot be combined with one that CONSTRAINS
tokens.** `reasoning_budget_tokens: 0` makes llama.cpp inject an end-of-thinking token;
a grammar decides which tokens are legal. Put together, the forced token arrives after
the grammar has completed and the server answers HTTP 500. Anything that injects into
the stream has to ask first whether the stream is constrained - `grammar`, `json_schema`
or `response_format`, on the route or in the caller's body.

**34. A cache with no expiry is a guess that becomes permanent.** A voicetype was paired
with the first character heard using it and never revisited, so every commoner after the
first wore the first one's name. Where the evidence keeps arriving, the newest evidence
should win and the cache should be the fallback, not the answer.

**38. Reading a file is not permission to rewrite it.** The panel parsed hand-written
launchers into the server cards and, when a card changed, generated a replacement - which
threw away everything in the original that was not a flag. If a file is mostly somebody
else's work, the writer has to be as narrow as the reader was wide: touch one array, write
only what was already there or was deliberately changed, and keep the original.

**47. A negative instruction gets obeyed as written and not as meant.** "Put each where
it starts - not all at the front" was compressed from a paragraph, and the model took the
clause it could act on: it stopped putting tags at the front and put them at the end
instead. State the positive placement first and rule out the failure explicitly.

**60. Re-rendering a pane destroys anything written into it.** The calibration output
was appended to an element inside the TTS pane, and the handler called `load()` when
the answer arrived - which rebuilds `pane.innerHTML` and takes the element with it. It
looked exactly like the request returning nothing. **Text that accumulates has to live
outside the element that shows it.**

**63. "It stopped appearing" can mean "it went somewhere you cannot see".** The Proxy
terminal was reported as stopping; it was in fact joining every row after the first
spoken line onto one row that ran off to the right. Two patches went into performance
faults that were real and were not this. **Ask for the contents, not the symptom** -
the run-together was plain in a paste of the terminal and invisible in the source.

**65. A backslash in the page script crosses TWO string layers.** The page is a Python
literal containing JavaScript literals, so `"\\\\s"` in this file reaches the browser as
`s`. A pattern written that way is not slightly wrong, it is a SyntaxError at run time,
and the function holding it stops dead. **Prefer indexOf to a pattern in page code**,
and when a pattern is unavoidable, write its specials as character classes - `[ ]`,
`[[]` - which need no backslash at all.

**66. Render the page before theorising about it.** Four patches went into this: three
causes found by reading the source, all real, none of them the fault. Running the page
in jsdom and painting one real tail printed the exception verbatim on the first
attempt. **When a symptom is 'the UI does nothing', get the exception first** - there
almost always is one, and everything reasoned without it is a guess.

**67. A const in one painter is a ReferenceError in the next.** Page functions share a
file, not a scope: `MG` lived inside `paintThink`, and the action row in `paintTail`
that read it threw on the first action line and on every paint after it - inside an
async refresh, so the freeze was silent. The palette the painters share is module-scope
now (`SPK_MAG`, `SPK_CY`), and the gate runs a served-script sweep that fails on any
name called or read where it is not defined. Run against patch73 it names
`refreshTails`, `MG` and `CY`, and nothing else.

**68. `[]]` is an empty class in JavaScript.** POSIX and Python read `[]]` as a class
holding `]`; JavaScript closes the class immediately - `[]` matches *nothing* - and the
`]` becomes a literal. `portRx`, `timeRx` and the highlighter's `[type]` alternative
had never matched anything at all. A `]` outside a class is already the literal: write
it bare. The gate rejects `[]]` and `[^]]` in the page script outright.

**69. The wall must split at the POST.** A `t0` at the top of a worker bills every
feature added later to the transport: the player tagger's 0.3 s model call showed up
as `overhead (http + wav)` and read as a 25% realtime regression, hunted as such.
Realtime means synthesis - clock from the request going out - and everything before
it is `prep`, printed with its biggest cost named. A timing figure that quietly
absorbs new work will misattribute every future feature too; the gate now holds the
split.

**70. A pane rebuilt on a timer destroys everything inside it.** `renderTts()` ran
on every live tick and replaced `pane.innerHTML`, so the terminal element was new
several times a minute: its text blanked until the next fetch, its dragged height
reset, and the page flickered. A pane that holds anything stateful - a terminal, a
resize handle, a scroll position - needs a signature of what it is drawn from and a
redraw only when that changes, with the live parts (`refreshCalTail`,
`refreshTtsMeter`) updating in place. Exclude from the signature anything the pane
does not draw, or a value that changes constantly will redraw it anyway.

**71. Two records of one thing cannot be ordered.** The TTS page kept its history in
a browser buffer AND a log file; neither could show the other's lines in the right
place, and the buffer died on reload. Everything is written server-side to one feed
now and the page only tails it - which also means a formatter (`cal_facts_text`)
lives where the data does rather than in the page.

**72. A guard naming a stale id switches a feature off in silence.** Splitting the
meter into two bars renamed `tts-meter-bar` to `-time`/`-tok`, and the early return
at the top of `refreshTtsMeter` kept the old name: it returned before painting, both
bars stayed empty, and nothing threw - `$()` returning null is not an error. The gate
now cross-checks every `$("literal")` in the page against every `id="literal"` it
creates, allowing for ids finished by concatenation. **Renaming an element means
grepping for its old id, not just for its markup.**

**128. A symptom can have two sufficient causes; killing one proves nothing
about the other.** The double-height rows had a hard break (a carriage return)
AND a soft one (a trailing space run wrapping under pre-wrap). Fixing the CR was
correct and changed nothing visible, which read as failure; the clip then masked
both, which read as success; removing the clip resurfaced the survivor. When a
fix is verified at the mechanism level yet the symptom persists, do not retract
the fix - go hunting for the second cause, and poison the test with both
(patch143).

**134. A dependency's DEFAULT can change under you, and silence is the
symptom.** llama.cpp stopped inferring a speculative type from a local draft
file; `--model-draft` kept being accepted, the drafter kept loading, and it
drafted nothing - the only evidence was decode speed and one trace line. When a
tool takes a thing and does not complain, that is not proof it uses it. Check
the flags a new build actually acts on, not the ones it still parses (v3.75
hotfix1).

**133. A control that cannot do anything must say so, not sit there.** Muse
Glimmer ignores --reasoning entirely; leaving the switch live would have let
someone set it, watch the flag appear in the launcher, and get no change in
behaviour - the worst kind of working. The card greys what the chosen model
ignores, gives the reason on hover, and offers the dial that family DOES answer
to beside it. Adapt the controls to what was loaded, and never let a dial
pretend (patch188).

**132. A rule that protects the untouched must not silence the touched.**
"Write it only if it differs from the default" was a good rule for settings
nobody had chosen and a silent failure for the person choosing one: setting a
dial TO the default is still setting it. Where a guard exists to keep quiet
about what nobody asked for, it needs to know what was asked for - the endpoint
already knew, since a card posts the one key it changed (patch187).

**131. Two ways to say the same thing need a round trip, not two writers.**
The cards write flags into a launcher and read them back out of it; the reader
knew about the vision and drafter pickers and the writer did not, so one
direction worked for patches while the other silently did nothing. Where a
setting has two representations, test the LOOP over the whole surface - set it,
write it, read it back - because a missing pair is invisible from either end
alone (patch186).

**130. Identify a file by what its own header declares, before what it is
built from.** Gemma's drafters were found by tensor name, so the same scan was
asked to find Meta's - but a DFlash assistant has ordinary tensor names and says
`dflash` in its architecture field. The header is both cheaper and stronger: it
is what the runtime itself reads to decide how to load the file. Reach for the
declaration first and the construction second (patch185).

**129. A check that pins a NAME can outlive the thing it names.** Four gate
checks asserted that a constant, a prompt or a function existed - and each one
had lost its last caller patches earlier, so the check was true of a corpse and
read as a feature under test. Pin the CALL, not the definition; and let the gate
prove the absence of what was removed, not the presence of what remains. The
sweep that found them added the scan that would have: no function, method or
constant may be defined and never named (patch184).

**127. Identify a thing by what it CARRIES, not by what it arrived on.**
A voicetype is a channel, and two characters can share one; the pending-name
queue only ordered them, so a shared sample wore whichever name came first.
The spoken words belong to exactly one reply, and the panel already held every
reply under the name the prompt gave. When a label is ambiguous, look for
content the panel already owns that only one candidate could have produced -
and when even that is ambiguous, say nothing rather than guess (patch183).

**126. A "turn" is the unit the OWNER counts.** The tag limit said N turns
and ticked per TTS chunk; the owner counts LLM responses. When a limit,
timer or budget names a unit, find the thing the user would point at and
count exactly that - and derive it from data the panel already holds
(reply membership), never from a new protocol (patch179).

**125. A priority is a property of a SEQUENCE, not a call.** Two-stage
work - ActionEval and its drilldown - releases the card between its own
stages, and a queued normal will take that gap every time. Holding the card
briefly after a high call leaves (the linger) is what makes the stage pair
behave as one high unit without the panel having to know any provider's
protocol (patch176).

**124. Forward at the source, judge at the one gate.** The NPC's emotion
tags exist in exactly one place - the completion - because SkyrimNet strips
them before TTS. The fix that finally made Higgs HEAR them was not a new
pipeline: capture where the data exists, inject one step before the gate
everything already rides, and let the same switch, board and cooldowns judge
player and NPC alike (patch169).

**123. A deletion differ must cover every language in the file.** The Python
half of the patch155 sweep had a top-level-name differ; the JS half did not,
and two constants between dead functions died with them - an empty terminal,
a dead viewer, a flood of rejections. The page now carries the same guarantee
the module does: used CAPS identifiers must be declared, verified by the gate
with strings and comments stripped in one pass (patch158).

**122. What a binary claims about itself is shippable text - gate it.** The
exe's embedded copyright said "Apache-2.0 style open source" over a
no-redistribution licence for four months, because a string compiled into a
resource is invisible to every text search of the tree. The gate now decodes
the version resource out of the shipped binary and the .rc that builds it, so
the claim and the LICENSE cannot drift apart again (patch156).

**121. A privacy promise in the UI is a testable claim.** "Cannot see your
IPs, paths, or GPU IDs" was a sentence in a confirm dialog while the remote
state carried whole launcher scripts. The redaction is now verified the way it
should be: build a state from a config holding everything real ones hold,
redact it, and hunt the result for every leak class - as a live gate run, so
the promise cannot silently rot again. And bind sockets by one rule, written
once: loopback unless the LAN is actually needed (patch155).

**120. A fix that stops new damage must also heal the damage already saved.**
The launch-time editor writes its output back into the config, so yesterday's
bug is in today's input: stopping the stranding was not enough while every
stored launcher still carried the stray. The repaired matcher consumes every
consecutive value token, making each edit heal what a past edit broke - and the
gate's run covers the baked case, not only the pristine one (patch154).

**119. An editor that cannot read a value must not half-edit the pair.** The
flag setter knew quoted values only; met with `"-m", $modelPath` it removed the
flag, re-inserted it quoted, and left the variable behind as a stray positional
llama-server rejected by full path. Either recognise the value token - quoted OR
variable - and replace it whole, or leave the pair untouched. And when a feature
retires (LLM Controlled, patch153), it goes with its servers, switches, pickers,
clocks and defaults in one motion - the mode mapper absorbs old configs so
nothing a user saved changes behaviour (patch153).

**118. Schedule against the modeled stream, not the observed request.** One
reply arrives as several requests that pipeline ahead of sequential playback, so
"after the reply" cannot be read off any single request - it has to be modeled:
every chunk extends end = max(end, now) + seconds and re-arms one timer. The
timing itself is then testable: feed a burst, measure where the fire lands
(patch152).

**117. A handler is tested by pressing it, not by parsing it.** The thought
click shipped with a free variable that no syntax check could catch - the page
parsed clean, the gate passed, and the first real press threw. The browser
error log named the line; the debug trace showed the press with no request
after it. A click path needs at least one negative control that walks the
chain's real variable names (patch148).

**116. When growth is legitimate for only one row kind, cap the other kind -
not the mechanism you cannot name.** After the markup was proven break-free and
the rhythm still moved, the fix stopped chasing the browser's reason and removed
its room: rows that may wrap keep their freedom, rows that never legitimately
wrap get a fixed height with no clip. A cap on the right subset is a guarantee
that does not depend on naming the cause - and it is checkable forever
(patch144).

**115. An overflow clip cuts shadows, not just text.** The clip that made rows
two-line-proof also sliced every text-shadow at the row's edge, turning clean
glows into smeared bands - and clipped the wrapped text the terminal needed.
When a guarantee and a visual share one property, split them: keep the guarantee
where it is cheap (no break characters can reach a row, proven by a poisoned
input) and let the box breathe (patch142).

**114. When trust is spent, make the failure impossible, not unlikely.** After
enough rounds of "fixed" and "still broken", the next patch cannot be another
correct-looking cause - it has to be a construction under which the symptom
cannot exist at all, plus a test that feeds the construction poison and watches
it hold. A fixed-height, non-wrapping, overflow-hidden row cannot be two lines
tall no matter what the pipeline hands it; that property is checkable forever
and does not depend on any diagnosis being right (patch141).

**113. Inspect the bytes the CONSUMER sees, not the ones your tools default
to.** A carriage return broke a terminal's layout for fifteen patches while every
read of the file - text-mode Python, grep, harness fixtures joined with LF -
silently normalised it away. The browser was handed CRLF; every instrument was
handed LF; both told the truth. When a rendering mystery survives the logic,
open the input in binary and hand the test the same bytes the field gets
(patch140).

**112. When one variant is proven in the field, copy it byte for byte.** Two
mark cells held the same kind of glyph; one sat tight in every screenshot the user
ever sent, the other grew its row through three patches of spec-correct fixes.
The end of that road was not a fourth theory - it was making the failing cell
identical to the proven one and deleting every clever property. A working sibling
is worth more than a correct argument (patch139).

**111. A behaviour test pins the settings it tests.** Changing five shipped
defaults broke ten gate checks, and two of them were behaviour runs that had been
riding the defaults without saying so - the ping-silence run and the wrapper .bat
rules both meant "under THIS mode" and wrote "under whatever ships". A fixture
that inherits a default is a check on the default, not on the behaviour; pin the
mode in the fixture and the two concerns stop failing each other (patch138).

**110. Make the invisible arguable thing visible.** Weeks of "no change" reports
could not be settled because the one relevant fact - which page version a given tab
was running - was invisible to both sides. A permanent version badge on the page
turns that from an argument into a glance, and its very absence on an old page is
itself the answer. When two honest parties keep disagreeing about behaviour, stop
debating the behaviour and instrument the disagreement (patch137).

**109. When the owner calls an experiment over, close it completely.** Reverting
means removing the feature, its setting, its UI, its handlers and every drifted
copy of its default in one motion - a knob that no longer drives anything is worse
than no knob, and a half-revert leaves the next reader two systems to reconcile.
The root cause can be found AND the simple design can still win; those are separate
questions, and the second belongs to whoever pays for the settings (patch136).

**108. Ship a version handshake: a tab outlives every deploy.** A single-page
panel is updated by restarting the server, but the page already open never asks for
the new one - no-store headers only govern the NEXT load. Five patches of fixes
reached the server while the user's terminal tab kept week-old JS, and both sides
were telling the truth. The page carries the release tag that built it, the state
feed carries the release serving it, and a mismatch reloads the tab once. Proving
the fault needed the user's own files: the feed rendered flat under the current
code, so the code on their screen could not be current (patch135).

**107. Before debugging what code produces, prove the code RUNS on the user's
config.** Five patches refined a rhythm that a default setting switched off at the
front door: gap 0 returned the input verbatim, so every improvement was invisible
and every "no change" report was literally true. Two rules: normalization must not
hide behind the knob it serves (strip the file's noise at every setting, size the
air by the setting), and a feature's default must exercise the feature - "off by
default" plus "returns raw input when off" equals shipping dead code to everyone
who never finds the knob (patch134).

**106. When a rhythm keeps looking wrong, run the pipeline, not another theory.**
Four patches of CSS reasoning each fixed something plausible; running the actual
transform chain under node on a faithful feed exposed the real faults in ten
minutes, in plain text: stacked blank runs between adjacent bundles, and a row kind
(the lone spoken arrow) one classifier had never heard of. Two rules fell out: every
consumer of a classification must read ONE classifier, and an inserted structure
(blank runs) must be idempotent - never emitted onto its own kind. And when a set is
compared across representations, fold case at every boundary once - a lowercase
prosody word met an uppercase stored set at four different comparison sites, and all
four had to agree (patch133).

**105. A baseline-aligned inline-block exports its internal baseline; a fixed
height does not change what it exports.** The mark cell was given height and
line-height and the row still grew to the emoji inside it, across two more patches -
because the row asks a baseline-aligned box where its baseline is, not how tall it
is. `vertical-align:top` makes the box contribute its own height and nothing else.
Corollary for the whole saga (patches 125, 127, 129, 131): when a layout fix
"doesn't take", measure pixels FIRST and locate which element actually sets the
distance - three plausible mechanisms were fixed before the real one (patch131).

**104. A margin set by the maximum is set by your worst outlier.** The headroom
was worst-miss x pad: one censored freak line raised every cap for the next 120
lines, and the 2.5 clamp existed to contain a statistic that should not have needed
containing. A percentile with the same pad covers the misses that recur and lets the
freak be what it is - reported, not ruling. The same patch made the arithmetic the
standard: work that is free, inline and contention-proof should be the default, and
the model kept for what only a model can read (patch130).

**103. Style the view the user is actually reading.** Three patches tuned
`pre.tail`'s rhythm while the Proxy Terminal page - the maximized view - carried its
own `line-height` override and never inherited any of it. When a change refuses to
appear, list every rule that matches the REAL element in the REAL mode (maximized,
split, embedded) before touching the shared one again; the user's pixels are data,
and here they matched the override times display scaling exactly (patch129).

**102. Idle is an instant; a background job needs silence.** The calibration wait
checked that nothing was in flight and fired - into the sub-second gap between
back-to-back lines, where its 20-116 second model call then overlapped every line
that followed on a shared card. A guard that samples a moment answers "is it quiet
NOW", which is the wrong question for work that runs long; require a measured gap
since the last activity ended, and stamp that clock where the activity ends, success
and failure alike (patch128).

**101. A line's height belongs to its tallest glyph, and colour emoji are tall.**
Tightening line-height moved every row except the ones carrying colour emoji - their
line boxes were already grown to the glyph (~1.6-1.9em), which is why "reduce the
spacing" appeared not to work twice. Put variable-height glyphs in a fixed-height cell
(the visual may overflow; the layout must not listen), then set the rhythm with row
margins you own. And a behaviour check that cannot RUN must fail, not skip: a typo
inside its own try/except reported itself as "node not available" (patch127).

**100. Before writing a discovery, find the one the working button already uses.**
The TTS page's Stop button worked where quitting failed, and the difference was one
call: the button also killed whatever owned the TTS port. patch123 answered the quit
fault by writing a NEW discovery (a command-line sweep) beside the existing one - a
second copy of a rule, drifted on its first day, its PowerShell quoting emitting rows
no parser matched. When one path works and another does not, diff the two paths before
writing anything; the fix is usually to call what the working one calls (patch124).

**98. Cleanup that needs a remembered handle dies with the process that remembered
it.** The panel stopped the TTS server through the Popen handle its own run created;
restart the panel and the server is an orphan every later quit walks past - while the
fleet's -Stop, which DISCOVERS its servers, kept working across restarts. Anything a
program must be able to clean up after a restart needs a discovery path (here: the
panel's own config filename on the process command line), not a handle. And kill
process TREES on Windows; terminate() reaches one process only (patch123).

**99. A gate check must be able to FAIL - `.index` on a string a mutation removes
raises instead.** The negative control for the render seed crashed the gate rather
than failing one check, and a crash filtered through grep read as a pass. `.find`
with a `>= 0` guard fails cleanly; a check expression must never be able to raise
(patch123).

**97. A CSS transition on an element that is rebuilt every tick runs never.** The
meter segments carried `transition: width .35s` from the day they were written, and
`innerHTML` on each repaint replaced them before a single ease could play - the
animation was declared on every frame and seen on none. Where values change often,
keep the elements and move their styles; rebuild only when the STRUCTURE changes. The
same identity rule caught the terminal in this patch: token 2 is the mark only behind
a stamp, so with stamps hidden the title inherited the mark's 2ch cell - find a thing
by what it is, never by where it usually sits (patch122).

**96. In a monospace terminal, an emoji is not one character.** Different marks
advance by different widths, so every column after the mark wandered with it - and a
`%-13s` name field silently mis-sized the moment a 15-character name arrived, moving
only ITS lines. Give variable-width glyphs a fixed cell (`inline-block; width:2ch`)
and size a fixed-width column to the longest thing that will ever sit in it, checked
by the gate, not by eye (patch121).

**94. A thinking model with a flat max_tokens spends it all thinking.** The ceiling
bounds the whole generation, and the reasoning block comes first - so a 60-token
ceiling on a Thinking-ON card was consumed before the first visible character, and the
"unusable answer" was really an empty one. Where thinking is allowed, budget it
(`reasoning_budget_tokens` > 0, never 0, never with a grammar) and raise the ceiling by
the same amount, so both halves have room and the budget message can force the answer
out (patch119).

**95. A refusal must say what it refused.** "The answer was not a usable fit" covered a
model that thought its budget away, a server that answered nothing, and an answer with
the wrong numbers - three faults, three different fixes, one sentence. The refusing code
is the only place that holds the refused text; print its head there, or the diagnosis
happens by upload and guesswork a day later (patch119).

**92. Before tuning an estimator, count how often it is consulted.** A day's logs said
the floor decided 99 caps, the guard 81, the estimate 67 - the carefully-fitted number
was outranked by its own clamps on 73% of lines, so improving the fit could not have
changed anything. The bounds are part of the estimator: a flat floor of ~5 seconds of
audio under one-second lines WAS the estimate, whatever the fit said. Scale the clamp
with the thing it clamps (the floor is half the guard now), and read the bound
distribution before touching the model or the prompt (patch118).

**93. A filter applied to successes must be applied to failures, or the failures rule
the statistic.** Only estimate-decided lines were scored - but only on the success
path; a runaway held at the floor entered as cap/est off a line the estimate never
touched, and one 128/17 = 7.4 pinned the headroom at maximum for a session. The
asymmetry was invisible because failures are rare and each one large. Score both sides
by the same rule, and record with every failure the fact the rule needs (who decided
its cap) at the moment it happens - it cannot be reconstructed later (patch118).

**91. Send figures, not sentences, and build the sentence from the figures.** The
headroom reading was composed server-side into one line - four numbers and two outcomes
in prose - and the page printed it whole. A reader has to start at the beginning to find
the number they want, and anything that wanted to draw it differently would have had to
parse English back into numbers. `tts_headroom_facts` answers the figures; the wording is
built from that same dict in the same function, so the boxes and the record cannot say
different things. Where a display and a log describe one reading, one of them must be
derived from the other, never written twice (patch117).

**89. A check that can evaluate to None does not fail - it SKIPs, and tests nothing.**
`re.search` answers a Match or None, and `A and B` over two Matches answers the second;
one miss and the whole expression is None, which this gate's `check()` treats as "not
run". It reported green while asserting nothing, and only a negative control found it.
Coerce a match to `bool()`, and where a class of mistake is that quiet, write a rule over
the gate's own source so it cannot be made twice (patch116).

**90. A window into a document is a guess about how long the document is.** The player's
name was read from the first 256 KB of a dialogue request because the heading sits about
17 KB in - true of the stock prompt, false as soon as the memory block grows, and the
failure is silent because there is a reasonable-looking fallback ("Player"). Search the
whole thing when the answer is wanted once, and when a lookup fails, SAY what was there
instead: the next fix needs the wording the prompt actually used, and only the prompt
has it (patch116).

**87. Two dictionaries only meet if something maps their keys.** The sampler chips
asked by `temp` and `rep`; the answer was built in request field names, `temperature`
and `repetition_penalty`. `top_p` and `min_p` are spelled the same in both, so half the
row filled in and half read "-" - and the half that worked hid the fault for as long as
it did. Where two namings exist there is already a map (`TTS_SAMP_FIELD`): build the
answer through it, in ONE function both callers use, rather than handing a raw dict to a
reader that names things differently. And a reading that is always wanted rides the tick
that is always running - the chips were waiting on a diagnosis nobody had asked for
(patch115).

**88. A function on the per-line path must be handed its settings, never read them.**
`load_config` fills defaults and saves, so `acpp_token_cap` reading the config to find
the user's tokens-per-character would have written the config file from inside the
speech loop - and, in a test, into any tree that merely imported the module. Settings
are a parameter; with none in hand the constant is the answer (patch115).

**86. Set the height of a row that must line up with another; do not discover it.**
Two controls share a top edge only while their rows are the same height, and a row
that finds its own height is at the mercy of the tallest thing anyone puts in a cell -
a switch label's line box came out 9px taller than the menu beside it and re-centred
the menu, twice. And space two things with a margin on one of them, not with a flex
`gap`: the margin applies whatever the container's `display` computes to, while the
gap silently does nothing if the box is not flex or grid. Where a measurement and a
rule disagree, the measurement is the fact - take the pixels off the screenshot rather
than reasoning about the cascade (patch114).

**85. Style what is on the screen, not what is in the markup.** Every `<select>`
here is swapped at runtime for a `.selwrap` stand-in that inherits the select's
CLASSES and nothing else - so a width set on `select`, or inline on the select, lands
on a hidden element and the visible box falls back to its own longest line. Two
patches' worth of caps did nothing for that reason. Before writing a rule for a
control, check whether the control is still the thing being drawn; where a stand-in
exists, name the class both wear, as `.pctl select, .pctl .selwrap` already did
(patch113).

**84. A cell that grows to fill turns free space into a fault.** The calibration
server menu sat in a `flex:1 1` cell of a `nowrap` row: every spare pixel the card
had went into the menu, which read as broken rather than generous - and rode
everything after it out to the card's edge. A control with a natural size gets a cap
and `flex:0 1`; the surplus goes into one spring (`flex:1 1 0; min-width:0`) put
where empty space belongs. And a page-wide `select { min-width:260px }` outranks a
cell's wish to shrink - the escape is `min-width:0` inline on the control itself,
not another wrapper (patch112).

**83. Two controls line up only if they are the same control.** The calibration
server picker and the setting menu beside it looked like the same widget and were
not: `.tsel` trims a select to `5px 26px 5px 9px` against the base `7px 30px 7px
10px`, so it stood shorter and higher, and no amount of flex tuning was going to fix
a padding difference. **When two things must align, check they are the same class
before touching the layout around them.** Same patch, same family: a `.swlab` in a
narrow flex cell wraps its word under its switch, where it reads as a caption — the
label needs `nowrap`, not a wider cell (patch111).

**82. A signature-gated render is blind to whatever the signature omits.**
`renderTts` redraws only when `ttsPaneSig()` changes, and the sig listed everything
the pane shows except the Higgs install - so the Install press changed nothing it
compared, the render declined, and every later fix (five patches: events, gates,
loops, node lookups) fed a render that kept declining. The tell was there from the
start: **"a refresh fixes it" plus "the code that draws it looks right" means the
draw is being SKIPPED, not failing** - go read the skip condition before the drawing
code. Rules: when a pane gains a new data source, its signature gains it the same
patch; fast-moving fields (pct, step) stay OUT of the sig and are written in place,
or the pane churns once a second; and anything drawn from a skippable render keeps a
`force` path for the moment its data is first created (patch107).

**81. Before fixing the display, check that anything is being said.** The Higgs
install "froze" in two places and four patches went into the page - the event, the
idle gate, the loop, the node lookup - each a real fault, none of them the reported
one. The two stalls were the two stretches where the installer reported nothing at
all: the pre-download phase (no percentage exists yet) and the whole of `_hi_unzip`
(silent from first entry to last). The display was correct throughout. **A stalled
readout is a claim about the WRITER first and the reader second** — grep for what
writes the field before touching what draws it. Two corollaries, same patch: a long
step must report on a cadence, not once at its start; and a bar with nothing to count
must LOOK different from a bar at zero, or "working" and "stopped" are the same
picture (patch106).

**80. A "one instance" flag with no expiry is a lock a dead process holds.** The
install poll set `window.__higgsT = true` to stop a second loop starting. A tick
threw, the reschedule at the bottom of the tick never ran, and the flag stayed set —
so every restart path, including the one added specifically to recover from this,
looked at the flag and did nothing. Only a page reload cleared it. **Two rules:** put
the reschedule in a `finally` so no failure can be the last iteration, and make the
claim a TIMESTAMP renewed each tick so a stale one can be taken over. Related, same
patch: `getElementById` returns one node and cannot tell you it has been detached —
writing to a leftover twin is indistinguishable from not writing, so find every match
by attribute, write them all, and count how many were `isConnected` (patch105).

**79. When two patches in a row miss, add the reading that tells them apart.** The
install display stopped while the install ran, and three fixes each corrected a real
fault that turned out not to be the reported one — because nothing on screen
distinguished "the page has stopped asking" from "the installer is between steps".
`HIGGS_INSTALL` now stamps every change, the endpoint returns `idle` computed off the
server clock alone, and the step line shows it: seconds counting up mean the page is
alive. **A second failing guess is the signal to stop guessing and instrument.**
Related: prefer the path already known to work — the display is redrawn whole every
two seconds through `renderCurrent()`, the call a tab change makes, with the direct
node write kept only as the quick path (patch104).

**78. A poll that gives up when it cannot find its node gives up for good.** The
install poll stopped itself the first tick `getElementById` came back empty — and the
TTS pane redraws itself seconds after every page load (`ttsLoadModels` resolves and
calls `renderTts()`) from a `state` older than the install, so the row vanished for
one tick and the loop was gone until a manual refresh. **A missing node is a missed
tick, not an ending.** Stop on the CONDITION the loop is about (here: the install is
no longer running), redraw what is missing rather than surrendering to it, and have
the loop restarted by something that is known to run — `load()` — so it cannot be
lost. Self-rescheduling `setTimeout` over `setInterval`: a slow answer then cannot
overlap the next one (patch103).

**77. A progress display must not be gated on the panel being idle.** Every SSE
event becomes a QUEUED reload, and `queueLoad` runs `load()` only once `uiBusy()` is
empty — otherwise it re-queues. That is right for a save that would fight a field
being typed into, and wrong for anything reporting work in progress: during an
install something is always busy, so the Higgs bar never got a reload and only a tab
change (which calls `load()` directly) moved it. Announcing harder does not help — a
progress display needs a path that does not pass through the idle gate at all: a
small endpoint of its own, a short timer, and writes into named nodes rather than a
re-render (`/api/higgs-progress`, `higgsPoll`, patch102). **Ask what happens to the
event after it arrives, not only whether it was sent.**

**76. Two views of one thing need one announcement each.** The panel refreshes on
server-sent events, and `sse_notify` takes a KIND: `tail` reloads the terminals,
`state` reloads `/api/state`. The Higgs installer logged every step through
`TTSW.log`, which raises `tail` — so the terminal scrolled through a 5 GB download
while the progress bar above it, drawn from `state.higgsInstall`, never moved.
Switching tabs "fixed" it because a tab change reloads the state, which is the tell:
**when a refresh or a tab change fixes a stale display, the data got there and the
event did not.** Before adding a field to `/api/state` for something a worker thread
updates, check that the worker raises `state` and not only `tail` (patch101).

**75. A counter that starts at zero on every run measures the run, not the work.**
The automatic refit fired every N spoken lines, counted in memory from panel start.
Lines spoken before a restart had been measured, written to a store that survives a
restart, and used by the fit — and then not counted towards the next one, so a long
interval plus a panel restarted often left the fit due forever. Seed from the record
that outlives the process (`autocal_lines_since`), and count TO the interval rather
than testing a running total with `%`, which skips a whole interval every time the
total is nudged. Related: **one sentence for three outcomes is a broken instrument**
— "no LLM fit derived yet" meant never tried, could not run, and refused every time,
and only the last of those is working as designed (patch100).

**74. A `<select>` that fills itself shows a value nobody stored.** The TTS job
pickers are filled from the live servers on every refresh, and the fill read
`sel.value || settings[key]` — so once the browser had defaulted to the first option,
that option became the "stored" value on the next pass and the page displayed a
server the config had never held. The buttons pass the port from the page and kept
working; the automatic refit reads the SETTING and declined every time, silently, for
as long as the config was fresh. Two halves to the rule: **fill from the store, never
from the widget**, and **an unset control must look unset** — hence the `- pick a
server -` option. Sibling of gotcha 55: a control that cannot reach anything is worse
than no control, and one that looks set while reaching nothing is worse still
(patch98).

**73. Removing a "false" is not asserting a "true", and a theory is not a
diagnosis.** Gemma 4 opened every spoken line with `<|channel>thought`. I theorised
that restating `enable_thinking: false` in a request to a server already started
`--reasoning off` took a different template branch than leaving it absent, and
shipped patch97 on it. **It was never confirmed and it fixed nothing.** The real
cause was one dial: that slot had `reasonfmt: "none"`, so its launcher carried
`--reasoning-format none`, which llama.cpp documents as leaving thoughts unparsed in
`message.content` — the other two servers were on `deepseek` and were clean, and the
hand-written launcher used for the direct comparison had no such flag. It was in the
config the whole time and I read past it, because I had a mechanism in mind before I
had a cause. **Read the settings that differ between the working and broken case
BEFORE reaching for a theory about the ones that do not.** The second lesson, from
the same patch and verified against llama.cpp build 10219: the thinking-ON arm
only *popped* `enable_thinking`, leaving the server's own default to decide — and
that default is false on anything started `--reasoning off` **or** carrying the
Reasoning dial's patch96 line, `--chat-template-kwargs '{"enable_thinking":false}'`.
Only a dial set back to `on` removes that line, so a card whose setting was lost
orphans it in the launcher; `parse_ps1_reasoning` reads `--reasoning` alone, so the
panel saw a thinking-capable server, showed no ⚠, sent nothing, and the switch did
nothing at all. A request kwarg overrides both, so patch99 says `true` outright.
**Where a switch exists, the request states the value — never the absence of the
other one.** (That reasoning was sound but its trigger was not: the thinking that
had stopped was provider switches left off after the config reset. Ship a theory as
a theory — a fix that cannot be shown to work on the reported fault belongs in the
changelog as a hypothesis, not a repair.)

**64. A layout that works by assumption fails silently.** Emitting no newline after a
row because that row's element "is block-level" is correct until something changes it,
and then there is no error - just two rows on one line. Where every case must behave
the same, make them the same rather than testing which case you are in.

**62. When you find a fault in one function, grep for its shape.** `provHidden` and
`panelProvHidden` were written the same day, in the same style, with the same per-line
RegExp construction. Fixing one and shipping cost another round, and the one left
behind was the worse of the two because it ran by default. **A bug found by reading is
rarely the only instance of itself.**

**61. A regex built inside a loop is built every time round it.** The provider filter
compiled one pattern per provider per LINE; a few thousand lines of tail meant tens of
thousands of compilations per refresh and the terminal appeared to stop. Build the
pattern where the data does not change.

**59. A number from a model is input, not a decision.** Calibration asks a server for
settings and applies them - so every value is bounded, and one outside its range is
REFUSED rather than clamped. Clamping would report a setting nobody chose, and the
user would read it back as the model's judgement. **Validate at the boundary, and
prefer refusing to correcting** when the correction would be invisible.

**58. JavaScript holds 53 bits of integer.** An int64 seed read off SkyrimNet's call
reached the page rounded - 701521338218674266 shown as ...674300 - and a seed that is
nearly right is useless, because the only reason to read one is to reproduce a result
with it. **Anything wider than 2^53 crosses to the browser as text.**

**57. A setting is not shipped until it has a control.** `ttsPassThrough` was added,
wired into every request and reported in the diagnostics - and had no switch, so it
could be read and not changed. **Adding a key to DEF_SETTINGS is half the work**; the
gate now checks that this one has a control, and the same check is worth adding for
any setting a user is expected to touch.

**56. A proxy that reads two fields discards the rest, and nobody notices.**
SkyrimNet sent its whole TTS parameter set with every line; `tts_pick_fields` took the
text and the reference and the other twenty-eight arguments went nowhere. The sliders
on its page therefore did nothing, and the panel showed no sign of it either way.
**When standing between two programs, log the whole of what arrives at least once** -
the shape of the call is the interface, and reading only what you expected hides it.

**55. A control that cannot reach anything is worse than no control.** Three patches
went into sampling settings the speech engine refuses to accept - one to add them, one
to survive them, one to take them out. **Confirm the thing on the other end will take
a setting before building a way to change it**, and when it will not, delete the
control rather than leaving it on the page looking as though it does something.

**54. A table-driven writer only writes what is in the table.** Every sampler and
runtime reached a hand-written launcher because they are `SERVER_PARAMS` rows; the
model never did, because the launcher builder writes it separately and it was never
added to the edit set. **When a writer is built from a table, list what the table does
NOT contain** - that list is where the silent gaps are.

**53. "Unknown fields are ignored" is a property of ONE endpoint, not of a program.**
audio.cpp ignores an unknown key in a REQUEST and refuses to start on an unknown key in
its CONFIG. patch60 established the first and patch68 assumed the second, which took the
speech server down entirely. When writing into something whose schema is not documented,
either send nothing by default or read the refusal back - the server named the option it
would not take, which is better information than any guess.

**52. Find which bound is actually binding before tuning one.** An overrun was capped at
128 tokens and still took 18.15 seconds, because the request field is ignored and the real
limit was `busy_timeout_ms: 20000` - a constant the panel itself writes into the speech
server's config, three functions away from the retry that was being tuned. **A number that
matches the observed cost is the bound; one that does not is decoration.** 18.15 against 20
should have been read on the first patch.

**51. Log the input, not only the output.** Every TTS record showed the PROCESSED line,
so "the panel removed the tag" and "the tag never arrived" produced identical evidence and
two patches were spent guessing between them. Where a pipeline transforms something, the
thing as it arrived has to be written down somewhere, or the first question anyone asks
cannot be answered.

**50. An override that is right for one caller makes the setting invisible for the rest.**
`keep_tags` is forced on for the line PTI tagged, which is correct on its own terms - but
it means the player is always heard with feeling while every NPC line obeys a switch that
defaults to off. The asymmetry reads as a bug in the translator, and three separate
investigations went that way. **Where one path bypasses a setting, the paths that do not
have to say so.**

**49. When a fault is upstream, control what it COSTS.** Higgs running past its own
end-of-content token cannot be fixed here and has been chased three times. What could be
fixed in a few lines is the price: with no `max_new_tokens` a runaway generated to the
engine default and burned nineteen seconds on a four-second line. Sizing the cap to the
text turns the same failure into a second or two. **Ask what the failure costs before
asking how to prevent it.**

**48. Whitespace at the end of a flex item is trimmed.** `"Insert TTS: " + <span>On</span>`
lost its gap because the text node is an anonymous flex item and its trailing space goes;
`"Timestamps: Off"`, a single node, kept it. Use a non-breaking space when a label and its
value are separate elements.

**46. A closing elbow is a claim about position, not decoration.** The thought line was
drawn with the end glyph, whose upright deliberately stops at its own row - so a thought
long enough to wrap had nothing joining its rows. It was the last branch only because it
was being placed after the spoken lines; fixing the ORDER made it a mid branch, and the
tree drew itself correctly with no change to the CSS. When a glyph looks wrong, check
what it is asserting about its neighbours before changing how it is drawn.

**45. Narrowing what you ASK FOR is not narrowing what you ACCEPT.** The emotion list
offered to PTI and PME was cut to the fourteen SkyrimNet teaches, but `tts_apply_tags`
still has to translate all twenty-one, because SkyrimNet writes tags into NPC lines the
panel never requested. One filter on `_build_offer`, none on `TTS_ALIAS`. A gate check
sends `[EMOTION-ANGER]` through the translator to prove it.

**44. Matching two streams in time means matching them in the same ORDER.** Speaker names
arrive from the proxy in the order the dialogue was generated and spoken lines arrive in
that same order, so the pairing has to be first-in-first-out. Consuming the newest pending
name looked equivalent - both are "within the window" - and swapped the names of any two
characters who spoke close together.

**43. "Deprecated" is not "broken", and "current" is not "works here".** llama.cpp calls
`chat_template_kwargs.enable_thinking` deprecated and offers `reasoning_budget_tokens`
instead. The replacement stops thinking rather than preventing it, so a model that always
opens a reasoning block was cut off on its first token and answered with a full stop -
and the forced end token crashed every grammar provider. **A mechanism swap has to be
tested against the model in use, not accepted from a changelog.** Three patches were spent
on symptoms of this one substitution before it was reverted.

**42. A flag added to make a feature work can be the thing stopping it.**
`--slot-prompt-similarity 0` was added so automatic slot selection could not override an
explicit `id_slot`. It cannot anyway - the explicit slot is checked first - so the flag
only disabled the fallback that works when a build ignores `id_slot`. **When a fix is
"and also turn this off", check what the thing being turned off was doing for you.**

**41. Two editors over one thing must write through the same code, or they are two
things.** The server cards edited `params`; the Server Editor held the launcher text in
`params["custom"]`; the writer preferred the text. Every card change was therefore
recorded and immediately discarded. When a value has two ways in, there must be exactly
one way out, and a round-trip check that drives both.

**40. Giving a function a second return shape breaks every caller that tested the first
by type.** `regen_slot_script` returned a path, or a dict on error; patch48 made it also
return a dict on success. `if not isinstance(r, dict)` had meant "it worked" and silently
became "it was a generated launcher". When a return type widens, grep every caller - and
prefer testing for the failure marker over testing the type.

**39. In an edit-in-place writer, "no value" must never mean "delete".** A bare switch
absent from the card read as off and was removed from a launcher that wanted it. Absent
means the card has no opinion; only an explicit off is a request to remove.

**37. "Absent" and "zero" are different answers and a display must not merge them.** The
cached-token count is reported by llama.cpp under four different names across builds, and
some report none at all. Printing `0` for a build that said nothing would send someone
looking for a broken cache when the truth is that the panel cannot see one. `cache ?` and
`cache 0/270 0%` point at different problems.

**36. Deriving a capacity setting from a feature switch is countermanding the user.**
The first version of per-provider caching rewrote `--parallel` to whatever the switches
needed. It works, and it is the same mistake as the hardcoded `temperature: 0`: opening
another KV slot divides the context and costs VRAM, and that is a decision for whoever is
paying for it. Pin within what the user opened, say plainly when there is no room, and
add only the flag that has no meaning outside the feature - here `-sps 0`.

**35. An index derived from list order is a wrong answer waiting for a reorder.** KV
slots are pinned per provider by number; assigning them by position in `slot["providers"]`
would have moved every number the first time a provider was added or dragged, and each
moved number sends a request to a cache belonging to someone else. Sort by id.

**136. A record written on COMPLETION cannot answer "is this still coming?"**
`CHUNK_TRACE` gets its entry when a chunk's synthesis returns, so "the reply is still
arriving" was decided from returned chunks alone - and a request the panel was still
holding open left no mark anywhere in the process. A slow chunk was therefore
indistinguishable from no chunk: one field line spent 12.7 s inside a single request,
the 3.5 s quiet window shut while it was in flight, and the thought spoke 3.0 s before
that chunk was delivered. Ask what the evidence is ABSENT from, not only what it is
present in. Corollary: a bounded retry ladder is right for a guess and wrong for a
fact - three defers bounded a chunk that might never come, but a request known to be
open should wait on the clock instead, and the old bound fired into the reply.

**137. A cache keyed on a file that exists cannot see a file being written.**
`tts_thought_make` was "cached by content" via `os.path.isfile`, which is true only
AFTER the wav lands. The warm-up thread and the fire that followed it asked for the
same id a few seconds apart, both saw no file, and both synthesised - on a single-slot
speech engine, so the duplicate take held the slot while the reply's own next chunk
queued behind it. That queue is what lengthened the request that closed the window in
gotcha 136: the amplifier and the fault were the same bug seen twice. A cache whose
key is an artefact needs a lock over the PRODUCTION of that artefact, not only over
reading it.

**138. Two subsystems that make sound must know about each other.** Thoughts play in
the panel, dialogue plays in the game, and neither had any idea the other was
speaking - so the next character's first line started on top of the thought before it.
There was already a mechanism for exactly this (the BEFORE rule holds the HTTP response
until the thought's playtime has passed); it simply had never been pointed at the turn
boundary. Look for the lever that already exists before inventing one.

**177. A checked-in contract that only one tool knows is half a contract.** The
gate has enforced exact line endings per file type since section 6 was written, and
the repository had no `.gitattributes` at all - so git formatted every checkout from
whatever `core.autocrlf` was set to locally. With the common Windows default of
`true`, a fresh clone gets CRLF for the `.md` files and for `launch-llm-fleet.ps1`,
both of which the gate requires to be LF: the encoding section fails on files nobody
touched. It stayed invisible because the owner works from the release zip, not a
checkout, so the one path that breaks was the one path never taken. When a rule is
enforced by your own tooling, ask which OTHER tool also gets a vote - and make the
two cross-check each other rather than merely agreeing today.

**175. Fixing an over-eager check by narrowing its INPUT turns it off.** patch1
measured every attachment on `embedding_length` and flagged plain drafters llama.cpp
accepts. patch3 narrowed it to `embedding_length_out` - which exists only on a
standalone head, so a whole model carrying nextn tensors reported 0, 0 meant silence,
and the warning disappeared for the commonest case. Twice wrong in opposite
directions because both patches asked "which field", when the question was "does this
file attach at all". The panel had known that since patch2, in `_spec_kind`; the check
was simply never asking it.

**193. A harness the gate never executes is a green light soldered on.**
`term-diff.js` shipped in patch23 with an absolute require path into the working
directory of the session that wrote it, and no exit code - it ran for exactly one
container and could never say no, while being named the acceptance test for a whole
workstream. A presence check cannot catch this: the file was present throughout, and
its encoding checks passed. The gate now RUNS the differ - self against self must
report identical and exit 0 on every terminal, and a build with one colour moved
must report DIFFERENT and exit 1 - and pins every `gate-tools/` require to a
relative path. (v3.76 patch24)

**194. A text-mode read of a CRLF file plus a binary write strips every line ending
in it.** Python's text mode folds `\r\n` to `\n` on read; edit strings written with
`\r\n` then never match (count 0), and if any edit DOES land, writing the folded
string back re-encodes the whole file bare-LF - a one-character diff request becomes a
two-thousand-line one. The count-asserted `rep()` abort is the only thing that catches
the first failure before the second happens. Read `rb` and decode, always; the edit
discipline in section 7 assumes it. (v3.76 patch25)

**195. A key scan over a nested table reads the interiors as keys, and a row splitter
that matches into the next row consumes its first bytes.** The SHOW coverage check
found `sign`/`value`/`sep` - one element's internal part inks - as undeclared
elements, and a `findall` whose pattern ended at the next row's indent returned two
rows of five. Strip nested `{...}` before scanning keys, and split rows by their
START positions, slicing between them, so nothing is consumed twice or attributed to
the wrong row. (v3.76 patch25)

**196. The page is a Python string first, and every tool between your fingers and
the file eats a backslash.** A JS character class written `[^\]]` for the embedded
page arrived as `[^\\\\]]` after one shell heredoc - which JS reads as *anything,
twice-bracketed* and matches nothing - while looking right in every intermediate
view. The stamp silently stopped matching and the payload hook swallowed the line
head; only the byte-differ caught it. Patterns in the page stay backslash-free
(the patch1 rule), and edit scripts touching them are index-spliced, never
escape-matched. (v3.76 patch26)

**333. A setting for a choice that no longer exists.** audio.cpp shipped
portable/balance/fast build profiles through 0.6 and dropped them at 0.7, moving
to one archive per CUDA line - the shape llama.cpp already used. The panel kept
a chooser, a stored `ttsAcppProfile`, a per-profile search with subfolder
fallbacks, and a `profiles` field in the engine payload, all describing builds
that cannot be downloaded. `ACPP_MIN_VER` is 0.7 now and every piece of it is
gone. Removing the control is not enough on its own: the stored key, the handler,
the payload field and the search each had to go too, or the next reader finds
half a feature and reasonably assumes the other half is missing by mistake.

**334. Deleting a feature leaves prose behind.** Two blocks of comments still
explained the profile choice - which archive went in which subfolder, why "fast"
was not required - describing a table that had already been deleted at an
earlier patch. The manual-install steps were worse than stale: they told people
to download `audiocpp-windows-cuda-balance.zip`, an archive that has not existed
since 0.6. Wrong instructions are a bug with no stack trace. When a feature
goes, grep for its vocabulary, not just its identifiers.

**342. Take the engine at its word instead of holding a table.** DramaBox loaded
after patch105 and still refused every line: "unknown DramaBox request option:
temperature". The owner remembered seeing it on another voice, and the patch103
logs carry "unknown DotTTS request option: temperature" - two families refusing
the same option that Higgs wants. A capability table per family is exactly what
went stale for years with `reference_cache_slots`. The error NAMES the option, so
the panel now reads its own refusal, remembers it for that model, and asks again
without it. Only the first line to a fussy model costs the extra round trip;
every line after goes out correct the first time. Nothing in the code names a
family or an option, so a future release changing either needs no patch.

**343. A gate run that writes into the tree it is checking is not a check.** The
p106 runtime called the real sender, which read settings - and reading them
unstubbed wrote `fleet-config.json` and a `logs/` folder into the tree, which the
tree's own file checks then reported as unexpected. Stub what the code under test
touches, and give it a scratch folder. The standing rule is "leaves no trace";
this run had to be taught it twice.

**553. A PARSER THAT LEARNS A FORM MUST STILL ASK WHOSE REPLY IT IS.** p186
taught `action_row` SkyrimNet's ACTION line and called it for every record;
Combat and Dialogue carry that same line as their embedded action, GM carries
one too, and each grew a second row. The form tells you a reply HAS an action;
only the title tells you the reply IS one. `ACTION_TITLES` names the
providers whose whole answer is an action; nobody else gets the row. (p187)

**569. A GUARD ON A BUTTON IS ALSO A GUARD ON THE ENDPOINT.** The updater's
button disables while its server is up; the endpoint refuses too, because a
page can be stale, a second browser can be open, and a request can be sent
from anywhere. And each guard reads its own server only - the llama.cpp
updater cannot be blocked by the TTS server, nor the audio.cpp updater by
the fleet - because a guard that over-reaches teaches people to disable it.
The rule came from the owner's own self-test: a held DLL is refused both
ways. (p195)

**568. WHEN THREE LEGS CAN PRODUCE ONE PICTURE, INSTRUMENT ALL THREE.** The
Proxy terminal showed spoken lines alone; the server had the records, the
endpoint returned them on the same files, the splicer kept them - and on
that one refresh the page got an error, an empty text or filtered everything,
with nothing recording which. The root cause could not be found from the
logs, and that was the finding. A failed request is now filed with its
error, an empty answer is filed with what arrived, the server audits a fat
tail with no record row, and a filter that removes everything says so. Any
view that can show nothing must record why it shows nothing. (p194)

**567. BEFORE MAKING A STORE, FIND THE ONE THAT EXISTS.** p189 made
`logs\tts-audio` so the terminal could replay lines after a restart; the
Saved Audio Folder had kept every take with a readable name since patch8,
capped per character. The terminal needed a map from audio id to take, not a
folder. Ask what already keeps the thing before keeping it again. (p194)

**566. A DASHBOARD ROW WITH A REFERENCE IS A CHIP.** The written spoken rows
(p190) carried `⟨dlg:pid⟩`; the dashboard painter turns a reference on its
own rows into a "Request" chip under the row. They needed none: they sit under
their record. A marker means what its reader makes of it, and the two readers
of the two logs make different things of the same marker. (p193)

**565. REMOVE AND INSERT IN ONE BOTTOM-UP PASS.** p190 removed matched written
rows in one loop and inserted voiced lines in a second, at indices computed
before the removals - voiced lines under a Meta record, a lone player line
inside a Dialogue box, that box's rows then boxed with the player. Any edit
to a list at precomputed positions must proceed from the highest index down
and do everything for one position before moving up. (p193)

**564. NEVER CLOSE A HANDLE ANOTHER THREAD IS WAITING ON.** The p192 watcher probe
called CloseHandle from the probe thread while the watcher thread sat in a
synchronous ReadDirectoryChangesW on that handle. On Windows that call does
not reliably return; the probe hung, the request hung, the page froze. A
thread that waits on a handle must be the one to close it: flag it, wake it
(a touch in the folder), let it close its own handle and return. (p193)

**563. ONE HUNG REQUEST FROZE THE WHOLE PAGE.** post() counts calls in flight
and uiBusy() refuses every redraw while one is out - right for a save that
must not be overdrawn, fatal for a call that never answers: the launcher
buttons, the allocator, the terminals, the stats and the creator all stood
still until a browser refresh, and the owner read it as five regressions.
No request may be able to hold the page: every call is abandoned after a
bound and answers as an error; anything long-running runs aside and is
polled. The gate proves both with a fetch that never resolves. (p193)

**562. A MECHANISM THE GATE CANNOT RUN NEEDS A PROBE THE OWNER CAN.** The
watcher, the busy probe and the DLL swap have never executed anywhere but the
owner's machine; every gate check on them was a pin on their text. The
self-test runs them there against scratch objects and writes a report the
gate can read back as a fixture. Rules that made it safe: scratch for
everything it writes (its own folder, GGUFs, DLL copy, config copy), read-only
for anything real (nvidia-smi's query, PowerShell's version), a refusal while
a scan or an update runs, and a watcher handle it can close so its thread
ends and its folder can be removed. A probe that changes state is not a
probe. (p192)

**560. THE FAULTS THAT MATTER RETURN QUIETLY.** Twelve patches, and not one of
the real faults threw: a reference one short (p179), a speaker read as a
bracket (p183), rows without ids (p184), a parser returning "" (p186), a tail
without its figures (p188), a tail without its lines (p190). The error log
recorded what raised; the panel's failures were things that returned empty.
The `audit` source files a finding at the moment a silent empty appears -
where a reference is written, where a row is written, where a parser yields
nothing, where a terminal has records and no lines. Check the invariant at
the write, not the exception at the catch. (p191)

**561. THE NUMBERS YOU COMPUTE BY HAND BELONG IN THE PANEL.** Every report from
the owner was answered by the same forensic scripts: references against
records, rows against ids, spoken against voiced, first-try rate, EOC bounds.
`/api/diagnose` is those scripts, one button, one copyable text. It would have
refuted p181's duplicate-request story on the spot. (p191)

**559. THE RECORD SAYS WHAT WAS SAID.** For eleven patches the spoken rows in a
box came only from the TTS log - a second file, a second reader, a second
tail, and every mismatch between the two (p183's depth, p186's filter, p189's
midnight) emptied the box. The reply text is in the record from the moment it
is kept; the sentences are written under it then, and the TTS line, when it
comes, REPLACES its written twin (same words, an audio id on the voiced one)
rather than being the only source. Show what you know; let the other file
improve it. (p190)

**558. A CLOCK CROSSES MIDNIGHT; A CAP DOES NOT.** The deep TTS tail kept lines
"since" the dashboard's first stamp by HH:MM:SS. Read across the previous
session's file (p189), the first stamp was 22:30 and every line of the 05:36
session read as older - no spoken line anywhere, the owner's "massive
regression". Depth wanted a count, never a clock: both files' relevant lines,
newest N. Any comparison of wall-clock stamps across two files or two days is
wrong on the day it matters. (p190)

**556. "LOADED ON FIRST USE" MEANS FIRST USE BY EVERY READER.** The name-to-sample
ledger was loaded from disk on first use - inside the TTS request path. The
thought voice read the same map and never loaded it, so after a restart the
first click said "no voice learned" with 155 names on disk. A lazily loaded
store must be loaded by every path that reads it, or loaded at boot. (p189)

**557. WHAT ONE TAIL REMEMBERS ACROSS A RESTART, THE OTHER MUST TOO.** The
dashboard tail has shown the previous run's lines above a seam since p153; the
deep TTS read of p186 stopped at this run's file. Two logs joined by reference
(gotcha 552) must also be read to the same depth in SESSIONS. (p189)

**555. A FILTER MUST KEEP WHAT THE READER READS, NOT WHAT THE READER IS
NAMED FOR.** p186's deep TTS tail kept "the spoken lines" - the SAID marker -
and the splicer reads, for each spoken line, the `⚡ Nx realtime` and
`hold:` lines that follow it. Every row lost its realtime figure for one
build. Before filtering a log for a consumer, list every line the consumer
touches, not the one it is about. (p188)

**554. NORMALISE THE MODEL'S SHAPE BEFORE YOU FORMAT IT.** The selector answered
`\`Serana>Maxxor\``, `Illia>Maxxor`, `Thovasi Githrano [Witch]>[player]`,
`[Thovasi Githrano [Witch]>player` and `0` in one session, and the row copied
whatever it got; "no one speaks next" carried no arrow and the painter split
it at an arrow anyway. Take each side to a NAME first - quotes and backticks
off, the wrapping brackets off by balance so a name's own stay, "player" to
the player's name - then write one shape. A painter that splits on a token
must first ask whether the token is there. (p187)

**552. TWO TAILS, TWO CLOCKS.** The dashboard tail is 400 lines and spans, in a
quiet scene, twenty minutes; the TTS tail is 400 lines and spans four, because
the TTS log writes five lines around every spoken one. The splicer joined the
two by reference and found nothing for any record older than the shorter tail
- the box kept its thought (written into the dashboard) and lost its speech
(read from the TTS tail). The owner's Aranea case: two sentences voiced,
referenced, and gone from the screen five minutes later. Two logs joined by
reference must be read to the SAME depth in time, not the same depth in lines:
the TTS tail is now asked "since" the dashboard tail's first stamp. (p186)

**551. A LOG FROM THE LAST SESSION IS QUIET BY DEFINITION.** p178 recorded a
launch fault when a slot's log had stopped growing and its port did not
answer; at start-up every slot's log is the previous session's, old and
silent, and its server is gone. Fourteen "launch did not finish" errors in one
session's error log, all at the start-up second. A stall is only a stall for a
log written after `PANEL_T0`. Any rule that reads "has stopped changing" needs
"and was ours to begin with". (p186)

**550. THE OTHER SIDE'S FORMAT MOVES.** `action_row` parsed the strict-schema
JSON SkyrimNet's action providers answered in at p14; by p185 they answer
`ACTION: Name PARAMS: {...}` - the same line the dialogue replies carry as an
embedded action, which the panel already parsed elsewhere. Nothing broke
loudly: the row builder returned "" and the switch on the bar did nothing for
a whole session. A parser of another program's output is a claim about that
program's current build; when a feature goes silent, read a real reply before
reading the parser. (p186)

**549. A FALSE IN YOUR OWN PROOF IS THE BUG.** The p184 proof printed
"dashboard line wears the id: False" and I wrote it off as the harness not
capturing the log writer. It was the code: the `elif` I had inserted took the
marker block under it, and for one build no record row carried its id - the
title click fell through to the provider link, and the references, right at
last, had no row to hang on. The proof had said so. When your own check
returns false, the check is not what you fix first. (p185)

**548. WHEN A LINE NAMES A THING, READ THE NAME FROM WHAT IS LEFT.** The
splicer read a spoken line's speaker as the last `word:` on the line. p179 put
a reference `⟨dlg:5298⟩` at the end of every line, and from then on every
speaker was "⟨dlg", every burst was one speaker's, and Isran's lines rode
under Durak's record because they came within six seconds of his. A reader
that scans a line must scan the line with the annotation taken off - `refTake`
existed for exactly that and was called two lines earlier. (p184)

**547. THE GHOST WAS MINE.** p179 reserved a record id before a speech stream's
first word and fed the ledger under it; report() then ran `pid = None` - patch8,
"bound on every path" - a moment before pay_add read the parameter, so every
speech record was written one id past the one its chunks had named. p181 saw
the gap, saw an entry left open, and wrote a story about SkyrimNet sending each
request twice and dropping one. Two facts refuted it and I read past both: the
panel log had no dropped-connection line, and llama-server's task count
equalled the record count. The owner's p183 log made it plain - 117 of 191
references one id short of their record. A gap in the ids was a gap in MY
code; check what the code does with the number before blaming the network.
Gotcha 542's mechanism was real for a stream that truly aborts; its story of
duplicates is withdrawn. (p184)

**546. TWO LETTERS ARE CONTAINED EVERYWHERE.** "Ha!", "Oh!", "Hm." normalise to
two letters, and two letters are inside some word of every reply. The
containment rule that placed a forty-letter chunk deterministically placed a
two-letter one arbitrarily, and behind it the old ten-letter window guess
placed the rest. The owner's p181 log: thirteen such chunks on the wrong
reply. A chunk is one of a reply's SENTENCES - split as SkyrimNet splits, never
at an ellipsis, each stage direction its own, runs of neighbours counted too -
and equality with a sentence is asked first; containment only of a chunk long
enough to be nowhere by accident; and behind the ledger, nothing: a line it
cannot place carries no reference. A guess is worse than a blank. (p183)

**545. A CACHE OUTLIVES THE RULE THAT FILLED IT.** p181 taught `arch_family` to
name an unknown architecture from its string, and the dropdown still showed
Spark with no family: the family sits in the ledger record, written by the
rule of the day it was read, and nothing re-read it. Derive what a rule can
derive at READ time (`arch_family(arch)` in `list_models`), keep in the cache
only what costs a file read. (p183)

**544. "NO RULE" HAS TWO SPELLINGS.** `ustText(s, base)` was meant to paint every
word the vocabulary did not claim in `base`. It tested `paintTok(tk) === esc(tk)`
- the bare answer - but paintTok's last fallback answers a plain word in the
pane's text ink, `tint25(SD.text, tk)`, which is the same "I know nothing about
this" said in a span. Only whitespace runs came back bare, so the base ink
reached the spaces between words and never a word: the embedded action read
white with invisible cyan gaps, since p168, on every row that used a base.
When a function has two ways of saying "no verdict", a caller that tests one
of them has half a rule. (p182)

**543. NOTHING OVERFLOWS IF EVERYTHING MAY WRAP.** `segFit` (p175) measured
each row's `scrollWidth` against the box and scaled the box when a row was
wider - and `.tail .tl` was `white-space:pre-wrap`, so no row was ever wider
than its box; gotcha 526 recorded it as "written, wired, never firing" without
saying why. The fix is a decision about which rows are prose: a record row is
columns and must not wrap, so it is `white-space:pre`, overflows, and the box
scales; a spoken line wraps as it should. A measurement needs something that
can exceed the measure. (p182)

**542. A GHOST IN THE LEDGER TAKES WHAT IT CONTAINS.** SkyrimNet sent the
Dialogue request twice (the owner's "duplicated responses") and dropped one.
The dropped stream escaped the write handler as `ConnectionResetError`, which
`except (ConnectionAbortedError, BrokenPipeError)` did not catch, so no record
was written - and the ledger entry opened for it stayed open with half the
reply fed in, forever, because only closed entries expire. Every exchange
left one. Then a chunk voiced out of order - a stage direction after the line
that follows it - was found "before the cursor" in the real reply and "after
the cursor" in the ghost, and went to the ghost. Two rules: a stream that ends
without a record aborts its entry (a `finally` on the stream), and placement
asks which reply CONTAINS the words, unspoken occurrences first, oldest reply
first - the cursor picks the occurrence within a reply, never the reply. (p181)

**541. A NAME THE TABLE DOES NOT KNOW IS STILL A NAME.** `arch_family` returned
"" for any architecture outside `MODEL_ARCH_NAMES` and its prefix list, so the
owner's Spark model - read correctly, architecture printed on the card - had a
blank family in the menu. The string the file carries is a name; space and case
it (`spark2_5` -> Spark 2.5) and say it. A table is a courtesy for the reader,
not a gate on what exists. (p181)

**540. THE PROXY IS A PROXY.** The owner reverted to the official 3.76 and his
spoken lines and combat calls came back; he asked what the patches did to
provider calls. On the wire, everything the official did not: p149's
`ThinkStripStream` rebuilt EVERY content delta of every reasoning-off provider
without `id`, `object`, `created`, `model` or `finish_reason`; the
leading-thought reorder had grown from Dialogue to Combat; non-stream bodies
were re-serialised; and the socket stayed open until the panel's own
record-keeping finished, which had grown patch by patch. A proxy forwards
bytes and sets parameters. It does not reshape the reply, and it does not make
the caller wait for its bookkeeping. Every rewrite is now a named switch, off,
and the record is written after the close. (p180)

**539. A HANDLER THAT DIES IN SILENCE WAS NEVER THERE.** `_QuietServer.handle_error`
was `pass` - written for the dropped-socket noise Windows makes, it swallowed
every failure a provider server ever had. When the owner said combat requests
"never arrived", the log could not tell "not sent" from "arrived and died".
Silence the noise by exception type; record everything else with the port. A
failure inside the proxy answers 502 with its reason, so the caller sees a
reply and the log sees a line. (p180)

**538. A BOX PAINTER PAINTS BOXES; A LINE IN NO BOX MUST STILL BE PAINTED.**
`joinLines` returned `groups.map(...)` - only the boxes. Lines outside any box
were never emitted; that was invisible while the tree rule boxed the seam, and
the moment p179 unboxed it everywhere it vanished everywhere. Walk the lines,
emit a box where one starts and the line itself where none does. (p180)

**537. THE CLOCK CANNOT PLACE WHAT A QUEUE DELIVERS.** The Proxy terminal hung a
spoken line under "the latest speech row within three seconds", measured from
real logs in patch-era 20 when SkyrimNet fired TTS on the final token.
SkyrimNet now queues its speech: one reply's sentences arrive over ten to
thirty seconds, and a sentence is voiced as it STREAMS - before the record
line exists. The owner's screenshot had three lines standing alone above the
call that produced them. Only the words can place a chunk, and only if the
reply is known from its first word: the record id is reserved when the stream
opens (`pay_reserve`), the text is fed as it leaves (`speech_live_feed`), and a
chunk is looked for at or after where the reply's previous chunk ended
(`speech_place`/`speech_consume`). The splicer hangs any named line under its
record; the clock is left for lines that name nothing. (p179)

**536. A TEN-LETTER WINDOW IS NOT A MATCH.** `_th_member` placed a chunk in a
reply if ANY ten-character window of it appeared there - written so an
injected prefix could not defeat it. It also made "two replies contain these
words" the common case, and the rule that two answers name nothing then wrote
no reference at all. Strip the tags and stage asterisks from both sides and
look for the whole chunk; a prefix that survives that is a real difference,
not noise. The old matcher stays only behind the ledger, for a chunk the
ledger has never seen. (p179)

**535. PARTIAL IS NOT A READING.** Windows extends a file being copied to its
full length at once and fills it behind; a header read that overtakes the copy
gets zeros, which parse as empty keys with value 0 and raise nothing.
`gguf_meta` returned the partial dict, `general.architecture` - the first key -
came back true, and `_facts_complete` called the record complete because an
arch was present. The owner's test.gguf was remembered as a complete "other"
for the rest of the session, and every fix before this one moved the stat or
the fingerprint without asking whether the read itself had finished. A real
header has no empty key; one ends the read and the reader says `_hdrDone`
false, which the facts reader treats as a failed read. Ask the reader whether
it finished before believing what it returned. (p178)

**534. THE THING YOU COMPARE IS THE THING YOU CAN SEE CHANGE.** The models push
compared the SET OF NAMES and the menu-open answer returned `added` - a count.
A file re-read from unreadable to "Qwen 3.5, 65 layers" has the same name and
the same count, so both said "nothing changed" and the page kept its stale row
until a restart. The owner reported this five times; each fix moved the
trigger and none looked at what the trigger compared. A digest of the whole
list, or nothing. (p178)

**533. A GUARD ON THE WRONG ELEMENT IS NO GUARD.** `window.__menuOpen` was set
by a listener for a native `<select>` under the pointer. The model picker is a
custom `.selwrap` around a hidden select; the pointer lands on `.selbtn`, so
the guard never held for the one menu that mattered and the "models" push
rebuilt the cards under it. The wrap now holds the guard itself, and an open
picker is refreshed in place from `paramEditor(s)` rather than rebuilt. When a
guard is reported not to hold, find the element that actually receives the
event before touching the guard. (p178)

**532. A FILE THE GATE IS TOLD TO IGNORE IS A FILE THE GATE CANNOT SEE.**
tts-model-kinds.json was exempted from the repo/release drift check as a
"runtime cache", and the trace watch only named files that APPEARED during a
run - a file already in the tree when the run began could grow forever
unseen. It did, for thirty-odd patches: every run appended ~12 records for its
temporary .gguf files, the file was tracked (it was missing from .gitignore,
its sibling model-kinds.json was not), shipped, and listed in the release
manifest. By patch174 the shipped copy was 888 records, none real; the p176
tree 1036 records, 817 KB. Nothing was ever wrong in isolation - the exemption
was reasonable, the watch was reasonable - and the sum was a release that
delivered the developer's scratch over the user's own file on every update,
while the start-up install check dutifully reported the panel's own cache as
"changed". Found by diffing two trees, not by any check. Every exemption is a
blind spot; the fix removed this one rather than widening it: the ledger is
absent from every tree and the sweep insists, so the drift check has nothing
to skip and the watch has something to name. (p177)

**531. ONE RULE, NOT THIRTY-SEVEN RESTORES.** Sections redirected `_KIND["file"]`
to a temp file and put it back, thirty-seven times, and not one of them did the
same for `_TKIND` - which is how the TTS ledger leaked while the LLM ledger
stayed clean. The fix is not a thirty-eighth restore: both stores point into
the run's scratch root from the moment the panel module is imported, BEFORE
the pristine snapshot every section returns to is taken, so nothing can point
them back at the tree and no section has to remember anything. The p12 check
that pinned the store to `_KIND_FILE` was retold to pin it to the path it HELD.
When the same discipline has to be repeated at every site, the discipline is
the bug. (p177)

**530. A HELPER MUST BE DECLARED WHERE ITS CALLERS CAN SEE IT - AND "IT PARSES"
DOES NOT PROVE IT IS.** ustText and paintTok were written inside paintRow at
p168; the embedded-action and action branches call ustText from the callback
OUTSIDE paintRow. That is not a syntax error, it is a scope error, and nothing
failed until a record actually carried an embedded action - at which point
joinLines threw "ustText is not defined", paintTail died, and EVERY terminal
went blank during ordinary use. Eight patches between writing it and the owner
hitting it.

Two things let it through. node --check proves a file parses, not that a name
resolves - a reference to an out-of-scope name is perfectly valid JavaScript
until it runs. And the gate had a run for the embedded row's PIECES (treeLead
splitting it into branch, icon, label, content) and no run that PAINTED one
through joinLines, so the only path that touches the bug was never taken.
A check that exercises the parts and not the whole cannot see a wiring fault
between them. There is now a run that paints a record carrying an embedded
action, end to end.

**527. GOTCHA 526, THREE MORE TIMES IN ONE PATCH.** p174 shipped "half a change
is no change" as a lesson and p175 found three more of them in the same
report. The Folder Settings titles were emitted correctly and every rule that
styled them began with #dpane-tts, so on the page that mattered the title
stayed grey and the ? printed as a character. segFit was written, wired into
both painters, and never scaled anything, because a display:table box under
max-width:100% is CLIPPED and a clipped element's scrollWidth is its clipped
width - "does it fit" was always yes. The menu guard was placed on one of the
ten callers that redraw the cards, and a scan moves state too, which redrew
them through another. In each case the half a reader can see was done and the
half that makes it work was not, and the gate passed all three, because both
halves compile and neither is wrong on its own.

The owner had to report the Folder Settings page FOUR times. When a thing has
been reported more than once, the question is not "what did I write" but "what
reaches the screen" - and the honest way to answer that is to render it, not to
read the source again.

**528. Chained drop-shadows compound.** Each filter haloes the RESULT of the one
before it - the halo of the halo - so three at full colour read as a solid bar,
and halving every radius changed nothing visible, because the compounding made
the width, not the radii. And a 0.5px border draws as 1px; the core cannot go
below a pixel. One halo on a 1px core is the whole answer.

**529. The panel knew how to tell and nothing asked it to look.** list_models
checks the folder fingerprint on every call and rescans the instant it has
moved - and is called only when a page opens or a tab is entered, so a copy
that finished sat unnoticed until something incidental asked, minutes later.
The owner read that as a slow timer; it was the ABSENCE of a trigger. Opening
a model menu is the reader saying "show me the models", and that is when to
ask. A capability with no trigger is indistinguishable from no capability.

**524. A RECORD DESCRIBES THE FILE IT WAS READ FROM.** p172 gave each model
record the file's size and mtime so a change could be noticed - and stamped them
AFTER the read. A 22GB model read while it was still arriving failed, and then
the record took the finished file's size. Every later lookup compared that
against the finished file, found them equal, and called the failure current: an
entry wearing the identity of a file it had never seen, which could not go stale
for the rest of the session. The owner reported it as "the failed scan stays
that way no matter what I do". The stat taken BEFORE the read is the one that
belongs in the record. When a record carries evidence, the evidence must be of
the thing it describes, taken when it was described.

**525. A folder's mtime does not move while a file inside it grows.** The scan
fingerprint was the directory's mtime and its .gguf count - both unchanged
throughout a long copy and both unchanged when it finished, so the walk that
would have re-read the file never ran. The files' own sizes and mtimes are in it
now. A fingerprint has to include the thing you want to notice changing.

**526. Half a change is no change.** p170 put "Title\tdescription" into
SET_FIELDS, the form the TTS page has used since p41 - and never taught the
Folder Settings renderer to split on the tab, so the page printed the whole
string and looked exactly as it had. The owner reported it as "not implemented
at all", which was fair. Changing the data without changing the reader is not a
partial improvement; it is a regression with extra text in it.

**523. ASK THE UNIFIED SOURCE FIRST - BEFORE WRITING ANYTHING.** The owner's
standing rule, and it is a procedure, not a preference: when working on a
terminal, the payload card, or anything that shows what they show, the first
question is whether the change belongs in PAINT, ELEM or SHOW rather than at the
site. Not "can I make this look right here" but "where is this kind of thing
decided".

It is earned. The provider's weight was DECLARED in ELEM at p172 - and only
drawSegs read it, so the four terminals it paints went bold and the Proxy
terminal, painted by paintTok, did not. The declaration was right; one painter
simply never asked. The same day, the payload card was found carrying its own
#8b93a3 for a dimmed field and its own #c07ffb for reasoning - the two colours
PAINT already names as dim and think - so a change to either would have moved
five terminals and left that card behind.

Gated: no painter and no payload surface may carry a literal colour, and each
must be seen READING the table rather than merely avoiding a literal. The
second half matters - a surface that hard-codes nothing and asks nothing is
still outside the system.

Surfaces this covers today: the five terminals and their split panes, the
payload card, and anything drawn from an entity - a provider, a model, a
speaker. When a new surface shows one of those, it joins this list rather than
growing its own palette.

**520. AN IDENTITY THAT INCLUDES WHAT CHANGES IS A LEDGER THAT ONLY GROWS.** The
model ledger keyed each record by path + size + mtime, so a file that changed
did not update its record - it made a second one, and the first stayed for ever.
A 22GB copy in progress passes through several sizes and mtimes; a
delete-and-repaste makes another. The owner found two records of one test file
and asked for the obvious thing: one entry per file, rescan when anything but
the name changes, and drop the entry when the file is gone. The PATH is the
identity now and the file's shape lives inside the record, where a change is
noticed by comparing rather than by accumulating.

**521. A reader that learns nothing still fills in every field.** _facts_complete
asked whether the 33 keys were present. They always are - the reader writes all
33 whatever it finds - so a file it could not parse was recorded with an empty
arch and zero blocks, marked complete, and never retried. This is gotcha 512's
shape from the inside: an unreadable file answers with a full set of defaults.
Completeness now asks whether the record SAYS anything. That alone would have
surfaced the owner's file on the second scan.

**522. What is on screen is not what is in the DOM.** Both terminal panes live
in the page, one display:none. A cross-terminal chip found its anchor in the
hidden pane, scrolled it, flashed it and returned - correct code, invisible
effect. It worked while the other pane had never been painted and stopped as
soon as it had, which is why it read as a regression rather than a hole. Before
treating an element as somewhere the reader can be taken, ask whether they can
see it.

**518. If one side already knows, FORWARD it - do not make the other side ask.**
A model dropped into the folder mid-session was scanned, filed and written into
model-kinds.json, and the panel said nothing about it, so every menu built from
that list kept the list it was built with and only a restart ever showed the
file. p170 answered by polling from the page every few seconds; the owner's
correction was better and simpler - the scan knows the moment the set changes,
and the page has had a push channel since the beginning. The scan announces,
and only on a real change, so a scan that finds nothing is silent. Reach for
the push before the poll: the poll is what you build when you have forgotten
that the other side already knew.

**519. Two glows are two lines.** The segment border was an outer shadow plus an
inset one - two bands with the box's own edge between them. At full weight they
overlapped and read as one; thinned at p167 and again at p168 they stopped
meeting, and the owner's screenshot showed exactly two faint lines. A single
hairline border on a layer ABOVE the box, blurred, spreads the same distance
either way from where the edge actually is. When an effect is meant to be one
thing, draw it once.

**516. A REPAINTED TERMINAL DISCARDS EVERY ANSWER THE READER GAVE IT.** Two
controls the owner reported as dead had the same cause and it is p169's, one
patch on. The Show fold's click always worked - it unhid the body and renamed
the label - and the terminal replaces its whole innerHTML on the next poll, so a
second later the row was rebuilt hidden with the label back to Show. Worse, its
id was the line's INDEX in that paint, so the state could not have been
remembered even if something had tried: an index names a position, and the
position moves. Keyed by the line it heads, per feed, remembered in a Set,
re-applied on every paint.

Anything the reader changes in a repainted tree needs somewhere outside the tree
to live. The pattern is now used three times - open folds, fresh boxes, model
lists - and it is the same shape each time.

**517. A link that names a terminal has to OPEN that terminal.** The [Thinking]
chip looked for an anchor that only exists while the target terminal is being
PAINTED, and only the terminal on view is painted - so clicked from the Proxy
terminal it always searched for something absent and fell through to "the log
has scrolled past it". The code said "there is no pane to switch to", which is
true of split view and of nothing else. The owner's read was right: it never
worked. It also had a special arm for one kind and refused every other, which is
the tell that the general case was never built.

**515. An arrival animation on a wholly-repainted element animates everything,
every time.** The terminals repaint by replacing innerHTML, so every .tseg was a
brand-new element on every poll and every one restarted the half-second fade -
the whole terminal flashed when a single line landed. The owner read it exactly
right from the symptom alone. An animation belongs on the thing that is new, not
on the thing that is redrawn: boxes are keyed by the line they open with, the
set is kept per feed, and the first paint seeds it without animating, because
switching to a terminal is not an arrival. Before animating anything in a
repainted tree, ask what "new" means to the DOM - it is rarely what it means to
the reader.

**513. THE BRANCH IS DRAWN, NOT TYPED - and three faults hung off not knowing
it.** The owner reported the embedded action row three times across p164, p165
and p167: its tree mark was the wrong colour, it did not connect to the row
above, its icon gap differed, and its content wrapped back to the margin. I
tinted the chain emoji twice and the tree glyph once, and none of it could have
worked: a spoken line's tree character is REPLACED by a .tbr/.tbrend span with
border-left, a triple glow and height:100%, and that height is what carries the
line into the next row. The connection is geometry. No colour applied to a
character can produce it.

The real cause was one thing: the row was written as a special case BESIDE the
spoken-line painter instead of going through it, so it missed all three of that
painter's pieces at once - the drawn branch, the fixed 2ch icon cell, and the
two-cell flex that hangs a wrapped line under its own text. Three symptoms, one
cause, and I chased the symptoms because each looked like a colour problem.
When a row differs from its neighbour in several unrelated-looking ways, ask
whether it is built by the same code, before adjusting any of them.

**514. A base colour is a fallback, not a verdict.** An extending row's content
was one flat ink, so a number or a quoted phrase inside it read as prose while
the same token on a record row was coloured by the shared table. ustText() runs
the content through the same splitter and the same paintTok every record row
uses, and only the tokens paintTok knows nothing about keep the row's base
colour. The owner put the hierarchy exactly: base beneath, vocabulary above.

**511. One boundary rule for three different feeds is one rule too few.** The
segment boxes grouped on blank lines everywhere except the Proxy terminal - and
the Thinking family's records CONTAIN blank lines, because the model writes
paragraphs. One NE-Director record came out as a dozen boxes, none of which held
the header, so none could take a provider colour either: one wrong boundary
produced two visible faults. Each feed marks its records differently and each
mark is already authored - tree characters on the Proxy terminal, a rule line
and a port-carrying header in the Thinking family, the writer's own separator in
the TTS feed. 856 lines of thinking log now make 14 boxes instead of dozens.

**512. A box is only as wide as its widest line, indent included.** With a
record's branches each in their own box (p164), a box holding one indented child
began at the window edge, because the indent is part of the line. Returning to
one box per record (the owner's second thought) makes the question moot - the
box starts where the record starts. Worth remembering when a wrapper hugs
content: leading whitespace is content.

**508. A landmark that ships OFF is not a landmark.** p164 read a record's
provider from between the timestamp's bracket and the port's - and termStampsOff
lists dashboard by default, so there IS no timestamp and every row in the
owner's terminal glowed accent. The port bracket is four digits and is always
present; the name is what stands before it. Before anchoring on a piece of a
line, check whether a setting can remove it.

**509. One painter returned before the change reached it.** paintTail hands
thinking, ptipme and ttscal to paintThink and RETURNS - so the segment boxes,
added at joinLines, never touched three of the five terminals. The same shape as
gotcha 502: a change made at one surface, in a file where five surfaces are
served by two painters. When adding to a terminal, follow every path out of
paintTail before believing it is done.

**510. A feed that does not rotate cannot carry forward.** p153 gave the
rotating logs their last session; tts.log was one accumulating file, so a
restart brought last session's ROWS back with their spoken lines missing - which
the owner reasonably read as the Proxy terminal having stopped showing dialogue.
It rotates now, four kept beside the current one, like every other feed. A
carry-forward rule and a file-naming rule that disagree produce a terminal that
is half-remembered.

**507. A regex written into a page string is not the regex you wrote.** The
provider glow was matched with new RegExp("...\\s*...") built in the PAGE
string; by the time the browser read it one backslash had gone and the class had
become the letter s. It parsed, it ran, and every glow fell silently back to
accent - the worst shape of failure, because nothing complains. The match is
done by index now, between the stamp's bracket and the port's. In a page
assembled from Python strings, prefer indexOf and slice to any pattern that
depends on a backslash surviving two layers of quoting.

**506. Anchor by name, never by adjacency.** Every gate failure in p163 was the
same fault, five times: an anchor that meant "the thing next to X" rather than
"the thing called X". _a108 took THE LAST FUNCTION BEFORE const TL_FOLD_CHARS -
which stopped being joinLines the moment segGroups was inserted above it, so the
driver renamed the wrong function and left joinLines undefined. Another runtime
sliced the literal signature 'function joinLines(lines, fn)', which grew a third
argument. Two drivers assembled the painter from slices that no longer carried
the tables it reads. And the slice I added to fix one of them overlapped a slice
already there, declaring SAID_MARK_25 twice.

None of these were wrong when written; each was made wrong by something arriving
beside it. An anchor naming what it wants survives a neighbour; an anchor naming
a position does not. Same family as p159's cut-to-the-next-def and p162's
"  tts:" landing inside ELEM.num - and in a file where every patch inserts
something, adjacency is the least stable thing to point at.

**504. A boundary written by sixteen callers is not a boundary.** Asked to draw
a box around each log segment, the obvious separators were both wrong: timestamps
split one report into three (its lines are stamped as each is computed, spanning
several milliseconds), and the blank line was written by hand at sixteen call
sites - a convention, not a fact the panel held, so a new report that forgot
merged silently into its neighbour. segment_open() owns it now: written exactly
once, never twice running, never missing, and gated at log("") appearing twice in
the whole file. The page then groups on a boundary the writer AUTHORED. Where a
structure must be read, have the writer state it rather than the reader infer it.

**505. The Proxy terminal already stated its parent/child relation.** Grouping a
row with its branches needed no new marks: fixTree normalises the tree characters
after splicing, so a line carrying them IS a child. The grouping reads that.
Before inventing a structure, look for the one already authored.

**502. A TERMINAL ELEMENT IS DECLARED, OR IT DOES NOT EXIST.** Five line kinds
were added to terminals between p150 and p158 - the embedded action row, the run
seam, the arrival line, the queue-wait line, the held-back notice - and every
one was coloured WHERE IT WAS WRITTEN: a raw .seamline class, an inline
#e8ecf2, or nothing at all. PAINT and ELEM exist for exactly this: one entry per
element holding its recognition source AND its base ink, so a rule and its
colour cannot live in different places. Five elements outside them are five
second sources of truth, and the next person to change the accent finds one of
them. The owner asked whether the terminal work had respected the unified
structure; it had not, and I would not have checked unasked.

Declared now, read from the table, and GATED: every whole-line case in the
painter must take its ink from ELEM or PAINT, which is the check that would have
caught p153 and p156 on the day they were written. When adding a line kind to a
terminal: name the ink in PAINT if it is new, declare the element in ELEM with
its shape beside its ink, and have the painter read it. Never colour at the
site.

**501. A key that groups is not a key that links.** DEFAULT_PROVIDER_SEED was a
dict keyed by server port, and every path that walks it PARKS what it finds -
the fresh-config seeder at "providers start unallocated", and
create_missing_default_providers for a config that already exists. Nothing has
ever shipped attached. But the shape reads as an attachment, and it was read as
one: adding the Relationships provider I told the owner it was "on the 1238
server". His correction: "We don't ship Providers linked to anything, that's
manually done by the user on Live Network page. Always ship providers, GPUs and
servers unlinked by default." The code was right; the name was a lie. Renamed to
DEFAULT_PROVIDERS_BY_EXPECTED_PORT - the port a provider is EXPECTED to be
placed on, never where it is put. When a structure's shape suggests a
relationship its behaviour does not have, the shape is the defect.

**498. A pick that outlived its model took the server down.** The owner's
error log: "context type MTP requested but model doesn't contain MTP layers",
server exits, twice. The panel's own cache says mtpHead=False for that model -
it never claimed the head existed. A @builtin-mtp draft pick had been made for
a model that DID have one and survived the switch, because the option is kept
whenever it is already selected (a pick nobody can see cannot be corrected) and
the misfit warning explicitly skipped it. Both halves fixed: the card warns, and
the launcher refuses to emit a flag the model cannot honour. Note for whoever
reads this next: llama.cpp contradicts itself here -
common_speculative_types_from_gguf types a drafter from one tensor, while
llama_init_from_model also demands router_layer < 0, so a file can pass the
first test and fail the second.

**499. The same tag, asked for in one spelling.** The mood arm skipped a line
that already carried a FORMED <|...|> token - but the player tagger returns the
bracket form, [EMOTION-CONTEMPLATION], which has not been translated when the
arm runs. The line read as untagged, a mood was injected, and the bracket was
translated afterwards: *contemplation* *contemplation* in the owner's log. A
guard that asks "is this already done?" must recognise every spelling the thing
is written in, not the one the guard's author had in mind.

**500. The instrument answered on its first session.** p158's arrival log
settled in one reading what five sessions of inference could not: Brelyna's
reply completed at 09:21:19 and no sn-tts arrival exists until 09:22:39, a
page-click. SkyrimNet never asked for the speech. The panel forwarded the reply,
wrote the row and the thought, and was never called. Instrument before
theorising - the fifth theory is worth less than the first measurement.

**495. THE PANEL DOES NOT PAPER OVER WHAT COMES IN.** The owner, stating the
architecture in his own words: "This panel is not going to be able to deal with
external mistakes... If the LLM generates something like '...' on its own
despite instruction not telling it to, then it's something the user needs to
solve with the model or prompt, that's how it should be fixed." Named
exceptions: the TTS calibration, and thought audio and its control - the
panel's own work rather than compensation for someone else's. A silent skip
leaves the reader a missing line and no reason for it; the panel's own faults
are the panel's to fix, and the rest it REPORTS.

**496. A fix that does not fix is a cost, not a safety net.** The voice-prime
ladder - a gate, a primer that spoke "Right, then." to warm a switched voice, a
strip that took the tags off the first chunk, a carry that moved them to the
next line - was built across patches 31 to 54 against tag drift. The owner ran
all of it on the hardware it was built for and reports it helped nothing. It
cost ~1.5s on every speaker switch, the tags off exactly the openers that carry
the performance, and - when a strip left a chunk wordless - the line itself,
dropped in silence. Removed whole, and the gate sections that pinned it retold
as records of the removal so nothing rebuilds it without meeting the reason.

**497. Words are not the only utterance.** tts_wordless stripped every token and
asked whether letters remained, so a chunk carrying only <|sfx:laughter|> read
as nothing to say - while the translator two hundred lines above it emits that
bare token and says "the engine performs it itself". Nine sounds need no words.
The owner caught it: "some audio tags carry only a description and no actual
spoken line". Two halves of the panel disagreed about what an utterance is and
nothing checked. The rule went entirely under gotcha 495; the lesson stands.

**491. Serial is not ordered.** The owner saw a reply's last chunk logged before
its second-to-last, and asked how that was possible when synthesis is serial.
audio.cpp IS serial - its trace lines are contiguous per session, ~800-1100ms
each - but the panel handed it a raced queue. _QuietServer threads every
request, and prep before the POST runs 5ms on one chunk and 970ms on its
sibling (a tag-performed line needs a voice prime), so whichever finished prep
first reached audio.cpp first and audio.cpp faithfully honoured that order. The
audio was right in game because SkyrimNet plays in ITS order; only the panel's
record was wrong. The order was never corrupted - it was never established.

**492. A queue of those already waiting is not order.** The first fix sorted
whoever had reached the engine, which let a 20ms-prep chunk take the turn before
its 970ms sibling had even queued: the same race, one step later. The place has
to be reserved when the request declares it will speak, before prep. Proven
against the owner's own numbers.

**493. The clock was measuring somebody else's turn.** With concurrent posts,
"server ms" included waiting in audio.cpp's accept backlog: 3608ms recorded for
~1000ms of work. That number feeds tts-measure.jsonl, the learned
characters-per-second, the chunk cap, the lead and the thought-firing model - so
the panel had been teaching itself that synthesis is two to three times slower
than it is. Serialising in the panel does not make anything slower; it moves the
wait to where it can be seen, counted and reported.

**494. The panel could say what it finished and never what it was asked.**
Five sessions went into inferring whether SkyrimNet had requested a line that
never played, because a request that arrives and dies leaves no trace. Every
speech request now writes one line the moment it ENTERS - sequence, origin,
peer, the text - before any decision. Origins are named at all four doors:
SkyrimNet, the thought timer, the page's replay, the primer.

**489. Ask whether the source CAN answer before deciding what its answer means.**
The thinking label was wrong three times over three patches, and every attempt
reached for something the server said. p143 gated the trained label on
props.thinks. p155 found supports_thinking absent from /props and substituted
supports_reasoning_effort and supports_preserve_reasoning - which answer
different questions, so the label flipped to "no switch" the moment a server
started, exactly as the owner then reported: "running or not running the server
shouldn't change any labels." The truth is in llama.cpp's source:
common_chat_templates_support_enable_thinking() decides a request's
enable_thinking and is printed as a trace line, and is never serialised into
/props at all. The server cannot answer this question. Only a build that
publishes supports_thinking has said anything; otherwise the file's own reading
stands, running or not. Three wrong answers, all from treating a source as
authoritative without asking whether it holds the fact.

**490. Two saves cannot share one scratch name.** save_config wrote
CONFIG + "." + pid + ".tmp" - one name per PROCESS. Two saves at once wrote the
same path; the first rename consumed it and the second answered WinError 2,
"cannot find the file specified", losing the settings the reader had just
changed. Eight times across four days in the owner's panel.log, silent from the
page's side. A name per CALL and one rename at a time: 200 saves from eight
threads now pass without a refusal.

**487. A silent absence is not an answer - gotcha 4 from the other side.** The
owner reported combat lines never appearing, twice, across two patches. They had
been spoken, named and linked the whole time: running the splice against the
owner's OWN dashboard.log and tts.log placed 52 spoken lines, both of Brelyna's
under their Combat row. The splice was not running, because Insert TTS was off -
the code's default is "on", but config migration only adds MISSING keys, so a
config made when that default was "off" keeps it for ever. Two lessons. A
default changed in DEF_SETTINGS does not reach a config that already has the
key. And a terminal that withholds content must SAY so: the switch stays the
reader's to set - a setting they chose is theirs - but the terminal now prints
one line naming the toggle when spoken lines exist and are not being shown.

**488. Read the request, not the shape of it.** p154 was asked to change the
embedded action row's emoji and label colour. It also removed the parameters,
because "only write: Embedded action: <action>" read as a specification of the
whole row rather than of the part that was changing. The description is what the
row is FOR. Restored, with the label plain and the description in the cyan the
terminal already gives an action.

**484. A field that is not sent is not a "no".** The owner reported the thinking
label misreading models - Eclipse Phoenix has a switchable template and the card
said "no switch". The cache was right (reasonTmpl=switch), the file was right,
and slot 3's own server log said "init: chat template, thinking = 1". The tell
was that EVERY card said it, whatever the model: the panel asked /props for
chat_template_caps.supports_thinking, and jinja::caps.to_map() - read from
common/jinja/caps.h and caps.cpp - publishes nine keys, none of them that one.
An absent field returned nothing, nothing became False, and False was printed as
a verdict. Three states now: the server said yes, the server said no, the server
did not say - and silence yields to the file, as it does before a server runs.
A lookup that cannot fail loudly will fail quietly in the reader's favour.

**485. A tag the engine consumed is still a tag the model wrote.** Tags at the
head of a chunk become engine parameters and leave the text; one in the middle
cannot be applied and stays. So the terminal showed *contemplation* and not the
[emotion-contentment] that opened the same reply. The face already came from the
raw text; the words do now too, while the engine still receives the processed
text untouched.

**486. The payloads outlive the run, and that is a change of footing.** The
store carried a note: "in memory only: prompts are the player's game and do not
belong in a file the session leaves behind." The owner asked for them to survive
a restart, so they are written - one file per run, beside the logs, previous
run's loaded at start. The note was replaced rather than deleted, because the
reason it existed is still true: a full request carries the character card and
the whole system prompt, not just a line of dialogue. Named in the changelog so
nobody meets it by surprise.

**482. What is shown is not what is said.** The owner heard NPCs speak the
realtime ratio of their own thoughts. Clicking a thought in the terminal posts
el2.textContent - the RENDERED line - back to be spoken, and p148 had begun
writing "(4.09x)" onto that line. So the annotation was read aloud; and because
the text no longer matched, it hashed to a new audio id and re-synthesised on
every click, which is why one thought appears three times in the log with three
different ratios. The owner's first-time lines are clean; only the re-voicings
carry it. Any text a page sends back to be acted on must be stripped of what
the page added for the reader.

**483. A synonym is not the thing.** TTS_TAG_WORDS rewrote each tag as a
stage direction - "thoughtful" for [emotion-contemplation] - so a reader could
see at a glance that the tag survived. It reads well until the owner compared
the terminal with the payload and found a word the model never emitted. The
shape stays; the word is now the tag's own: *contentment* *speed slow*
*humming* ... *contemplation*. A display that renames its subject cannot be
used to check the subject.

**479. Half a pixel is a design defect.** The owner saw toggle knobs sitting
high on some provider cards and centred on others, and proposed one standard
toggle. Every toggle already came from swToggle - the markup WAS one standard.
The geometry was not: top:50% of a 21px track is 10.5px, and a browser rounds
that one way at one y position and the other way at the next. 38x20 with a 14px
knob at top:3px leaves nothing to round. When two instances of one component
differ, look for arithmetic that does not land on a pixel before looking for a
second implementation.

**480. A tooltip written twice is the second one.** paintVersion set a title
saying whether the panel was up to date; paintChrome then overwrote it, two
lines later, with the file path, build hash, size and mtime. So the control a
reader hovers to ask "am I current?" answered with a developer's build line. The
answer comes first now and the build detail follows it - both, in the order that
serves the reader.

**481. The terminal refused to remember on purpose.** api_tail took only files
written since PANEL_START and printed "waiting for this session" for anything
older - a patch-era decision to stop a stale screen looking un-cleared. The cost
was that every restart wiped the terminals. Each run still writes its own file,
so nothing grows without end; the reader is simply shown the previous run's tail
above this run's, under a rule. The file changed, the terminal did not.

**476. A variable declared ON an element is not in scope for a cousin.**
--selface is set on .sellist and .selbtn (p114, "one surface, named once"). The
p146 search field read background:var(--selface) while being neither, so it
resolved to nothing and the Model label showed through it. The field joins that
declaration rather than repeating the colour - the rule was right, the field was
simply outside it.

**477. min-width is not width.** The menu carried min-width:100%, so it was AT
LEAST the bar's width and grew to the longest model name, overhanging the bar it
belongs to. Pinned to the bar now, with rows ellipsising inside it.

**478. The boot screen repainted a still picture.** bootWatch ran every 120ms
and painted from state.ready - but nothing refreshed state while it ran: the one
load() before it was the only fetch. So the steps sat frozen and then jumped
from "19 of 142" straight to ready, whenever some unrelated event happened to
reload. It asks a door of its own now, four times a second, one request in
flight. /api/state is far too heavy for that rate, which is why the door exists
at all: a screen that reports progress must ask for progress.

**472. I read my own parsing bug as a defect in the panel - twice.** Told the
kinds cache "should refresh every launch", I claimed first that p126's widening
had left entries stale (it had not: every entry carried reasonTmpl) and then
that the completeness list held 17 of 33 fields and had drifted (it did not: it
holds all 33, and my "17" came from cutting the tuple at the first ")", which
landed inside a comment reading "(p115)"). Both diagnoses came from a derived
artifact - a census, a truncated grep - instead of the source. The owner pushed
back twice and was right twice. The p149 stamp bump those claims justified was
unnecessary: harmless, one rescan, fixing nothing. When a fact about the code
can be checked against the code, check it there.

**473. A model dropped into the folder is noticed now.** The list cache held for
300 seconds regardless, so a new file appeared up to five minutes late. Each
folder now carries a fingerprint - its own mtime and .gguf count - and a
different fingerprint means rescan whatever the timer says. It costs a walk and
a stat per directory, 0.02ms on a two-folder tree, so it can be asked on every
poll. Opening a model menu, and entering the Servers or TTS page, ask it.

**474. The scan reports its progress into the boot registry, which is wrong for
a dropdown.** list_models writes "%d of %d read" into the readiness step at
every file - right at boot, and a rewrite of a finished step when a menu asks.
The menu path scans quietly.

**475. A read that keeps failing is left alone, and says why.** An entry whose
read did not finish is re-read, up to five attempts, then reported and not
retried: the file, the attempt count, every field still missing, and the cause
in the reader's own words ("ValueError: header ends after 4 bytes"). The count
lives in the entry so it survives a restart, and the identity key carries size
and mtime, so replacing the file clears it by itself. Both failure shapes count:
an exception and a short return.

**469. An offset computed before an edit is a lie after it.** Removing the
Higgs guide page: I took the function's start and end offsets, then ran edits
that inserted text EARLIER in the file, then cut at the stale offsets - and
sliced step 2 of the audio.cpp tab mid-word. The render proof caught it, not
my reading. Rule: destructive slices go first, on fresh offsets, or recompute
after every edit. The panel edits were restarted from the p149 file in order.

**470. The embedded action reads back as its own branch.** SkyrimNet's embedded
action evaluation lets the dialogue model choose an action in the same reply as
its line - a final ACTION: Name PARAMS: {...} after the speech and the thought.
It is SkyrimNet's to execute and the proxy forwards the reply untouched; the
terminal now reads it back as a closing branch under the reply, "Embedded
action: who > Name (params)", on the same switch as the chosen-action branch.

**471. The guide helper is written only when it changes.** The guide tab polls
every three seconds and rebuilt its boxes each time - dropping the hover tip and
restarting the pulse the owner had just triggered. Same rule as the updater
dialog: build once, write on change. And the boxes' tasks are one bullet line
each, centred, as the owner drew them.

**466. Combat never spoke, and the terminal was innocent.** The owner: combat
lines rarely arrive in-game, only thoughts. The ledger said it in its own words -
"no live evidence - the voicetype stands" - beside cache, pin and run all naming
Brelyna. SPEAKER_TEXT_MIN refused any chunk under 24 characters, and a combat
line is one short sentence by design, voiced first-sentence-alone by SkyrimNet:
"Bandits!" is seven. Unnamed, the panel treated it as another speaker, switched
voices, and primed for 1.5s - 2.2s for a one-word line in the place speech is
needed fastest. Then the splicer anchored only /dialogue/ rows, and three proxy
branches each tested title == "Dialogue" alone, so a Combat reply was never
registered, never streamed through the reorder, never anchored. The chain from
a length gate to a silent companion. Fixed at the root: a short chunk claims the
single newest reply it belongs to and nothing older; one SPEECH_TITLES set read
by every branch and the splicer.

**467. Reasoning in content is reasoning.** llama.cpp's parsers extract a
thinking block only when thinking is ON (chat.cpp: extract_reasoning &&
inputs.enable_thinking). A model that reasons with the switch off keeps its
<think> block in content - the owner's Shruti payload shows it - and the proxy
forwarded that block to SkyrimNet as a memory query. A two-state stream strips
it, tags split across deltas included, keeps it as the reasoning it is, and the
observation "thinking: trained" now needs two facts: the switch was sent (three
ways, plus reasoning_effort "none" as llama.cpp's README names it), reasoning
came back. Whether the template had a switch is a detail, not a gate - a
finetune with no switch has nothing more to deliver.

**468. The stamp, again.** p126 widened reasoning detection and did not bump
_KIND_RULES, so no file read before it was ever re-read: zero effort entries and
most LFM files silent in the owner's cache four weeks later. Gotcha 401's lesson,
repeated at p126, found at p148, bumped at p149.

**462. A search field belongs to the menu, not the bar.** p146 built it into
the picker's wrap as a sibling of the bar, so the wrap's row layout put it
BESIDE the bar, squeezing it, always visible, in the bar's colours - the owner
drew an arrow to where it belonged. It is positioned above the bar now,
displayed only while the menu is open, wearing the menu's dark surface and
black glow, with a plain white stroked glass, and focus lands in it when the
menu opens.

**463. One marker, two spellings.** The terminal attaches a line's realtime
ratio by finding the SAID marker - U+3030 followed by the U+FE0F selector - in
tts.log. Spoken lines carried both; the thought line was logged with a bare
U+3030. So no thought ever showed its ratio, though the TTS log recorded one
for every thought. One character.

**464. A spoken line cannot precede the reply that produced it.** The splice
anchored each burst to the dialogue row with the smallest time gap - which could
be the NEXT row when a line began just before it landed - and grouped by
speaker; both reorder, and the owner saw 2, 1, 3. The rule that cannot: under
the latest reply completed before the speech started, in log order. Proven with
a line spoken 0.3s before the next reply landed.

**465. Three findings from the owner's logs, all mine.** The kinds cache was
never re-read after p126 widened reasoning detection - the stamp is still
376p125 - so every model read before p126 kept its old verdict: no effort
entries, Muse Glimmer and most LFM files still silent; gotcha 401's lesson,
repeated one patch later. (A "duplicate --reasoning flag" I reported here was my own grep
matching llama.cpp's deprecation message - "Use --reasoning on / --reasoning off
instead" - not the launch line; the launcher emits one. Corrected at p149.) And
llama.cpp's parsers extract reasoning
only when thinking is ON (extract_reasoning && inputs.enable_thinking, in
chat.cpp), so a model that reasons anyway keeps its <think> block in content -
which the proxy passed to SkyrimNet untouched as a memory query. p149.

**460. A guide falls behind the moment it is prose.** The main guide's step 1
still told the reader to find a llama.cpp folder and set three required paths,
patches after the install became one button and two of the three paths became
presets. The TTS guide's Higgs page carried the whole audio.cpp install, patches
after that became a button too, and named its tabs for models while the backend
now runs eight packs. Every number and path a guide states is now projected -
the version floor from ACPP_MIN_VER, the folders from the settings - and the
compatible-models list is generated from the pack table the panel runs, so a
pack added to the panel appears in the guide without anyone remembering to. The
DRY-range lesson again: derived cannot drift.

**461. A step's target is brought into view, not centred.** flashTargets
scrolled to block:"center", which snapped the Servers page to the middle of its
cards when the reader had been at the top. "nearest" moves nothing that is
already visible and still brings a deep target up.

**458. A search field above every model picker.** A long models folder made
the menu a scroll. The field is built into the picker's own wrap, above the bar,
so it is the bar's width by construction and wears the bar's surface, radius,
type and glow - nothing to keep in step. Typing narrows the rows to names
containing the text and the menu shrinks to what remains, whatever height was
dragged before; Enter takes the first match; choosing or closing clears it. The
model pickers only - the class they already carry says which.

**459. Two ways to choose a row, one function.** Enter in the field first
synthesised a pointer event to reuse the click handler - which jsdom exposed
as fragile (no PointerEvent there) and which was the wrong shape anyway. selPick
is the one place a row is chosen from; the pointer and the key both call it.

**455. One rule, not 49 restores.** The review counted 51 sections replacing
fp.log_dir and 2 restoring it; the true leak was 5 sections, the rest restoring
under names the count did not match. Either way the fix is the same: section()
snapshots the panel module on its first call and puts back every replaced
attribute at each boundary, reporting how many. Nine boundaries restore
something now - the five old leaks and four sections that patch for themselves.

**456. A leak that is fixed exposes whoever was living on it.** The moment
boundaries restored the module, four sections began writing logs and config into
the tree: one whose section() call sat mid-block, one logging through the
previous section's captured panel_log, one with 33,000 characters of calls
before its own patch, one reading the config through a leaked CONFIG. None had
been caught because the leak had been hiding them. The trace-watch names the
section at the boundary where the trace appears and clears it, so one run names
every culprit; a named culprit is a FAIL even though the tree ends clean.

**457. The silent deaths are not memory.** One run in roughly ten ends with no
verdict and nothing on stderr, at varying points, and once after printing its
verdict. Measured under a sampler: the cgroup limit is unlimited and every
python and node process together peaks at 400 MB on a 4 GB box. With
faulthandler and a signal handler armed, a run still died with nothing on
stderr - so it was killed from outside. Found by experiment: a background
process started with nohup, parent 1, its own process group, is KILLED when the
sandbox force-stops a tool call for exceeding its time limit, and likewise when
the session sits idle between turns. Every silent death sits in one of those
two moments. Not the gate, not the panel, not memory. The rule: a gate run must
start and finish within one turn, in calls that never approach the limit; a run
that straddles a turn boundary is a run that will be rerun.

**452. A lift that changes nothing is proved by the bytes.** The Sampler Guide's
entries and card renderers lived inside renderParams(), so the only way to show
a card was to render the whole page, and the [--flag] buttons had to leave the
page to show one. Lifted to module scope, with the page and the new popover
drawing through one pgCardHtml. The proof of a safe lift is byte-identity of
the page before and after - and it was not identical: four cards differed.

**453. The four DRY entries had been blank since patch131.** They were written in
the info-card shape (range/how) but placed in the sampler array, so the page
drew them as sampler cards - the description showed, but the range line, the
summary line and the lo/hi band were empty. "1.0 - 4.0, default 1.75" was never shown. A renderer that
picks the card by its SHAPE draws them correctly, which is how a refactor meant
to change nothing surfaced a fault nobody had reported. 49 of 53 cards
byte-identical; the 4 that changed are the 4 that were wrong.

**454. A gate SKIP is a run that did not happen.** 22 jsdom behaviour tests went
SKIP for one hidden path (/tmp/node_modules/jsdom, three lines from the one I
had just fixed) and the run said PASSED; I read the last line and the counts
and called it verified. The verdict block had listed them as "not run, not
passed" the whole time. The gate resolves jsdom through one finder now, and an
unexpected SKIP is a FAIL, so a one-line reading cannot miss it. And the
fixtures my pre-gate identity step used - lost with the disk - were in the
owner's own uploads; they live in the durable folder now.

**448. No file can say a model disobeys its switch.** The owner's LFM retest,
with --jinja now emitted: reasoning off, the template switch sent three ways, and
the model reasoned anyway. p116 had concluded the switch was failing; it was the
model. The GGUF can say a switch EXISTS; whether the model obeys it is training,
not structure, and no tensor carries it. So the panel records the one thing it
can know for certain - three facts on one reply: the server reported the switch
supported, the request carried enable_thinking:false, and reasoning came back.
"Thinking: trained", written on the file with the date, forgotten if the file
changes. Nothing is inferred from a reply's length - the owner pointed out a
thousand-token SkyrimNet reply is a normal reply - and a model that reasons
with no markers is invisible and stays unlabelled. Either the panel knows, or it
says nothing.

**449. The proxy had been discarding the evidence.** reasoning_content was kept
only when the route's thinking was ON - so with thinking off, the case in which
it matters, the reasoning was dropped and the payload view showed a normal reply.
Recorded always now.

**450. A tooltip is not an essay.** The "no switch" chip cited a field capture and
a token count; the draft mismatch cited a GGML assertion. Each is one or two
sentences now, and the Sampler Guide is where the levers are explained - the
owner's rule: the panel offers the education, the tooltip does not deliver it.

**451. The container restarted mid-ritual and the working disk was gone.** Both
build trees, every work folder, the extractor, and patch143's finished zips - all
on the ephemeral disk. Only /mnt/user-data/outputs survived, and it held every
build through patch142, byte-verified, so everything was rebuilt from there and
patch143 re-applied edit by edit. Whether the restart was a dropped connection
and a retry (the owner's reading) or memory pressure from two gate runs I had
started in parallel to save time (mine) cannot be told from inside; the
protections are the same either way and are in force: one gate run at a time,
deliverables copied to the durable folder the moment they are packaged, and
nothing that matters kept only on the ephemeral disk. Two gate runs had also
died silently that day with no traceback; that stays an open fact, not a theory.

**446. The patch123 deadlock, as a class.** panel_log -> log_dir -> load_config
took _KIND_LOCK while _KIND_LOCK was held: found once by a hang on the owner's
machine. The shape is general - any function holding a non-reentrant lock and
reaching, through any chain of calls, a function that takes the same lock - and
it is a call-graph question, so the gate walks the graph from every with-LOCK
block. Clean on the real panel; the planted p123 shape is found. Beside it, a
dynamic probe: every one of the 23 locks held in turn while the three logging
entry points are called, each with a deadline, because the static walk is
name-level and coarse and a probe proves the path that actually hung.

**447. A regex said five; the parser said sixteen.** Duplicate check messages,
counted from the gate's own AST. A failure listing names a check by its message,
so a shared one could not be located, and a retold pin sharing a message with a
live one could shadow it. Each later occurrence now carries its section. And the
three functions defined twice were all deliberate wrappers - the first captured
into a name before the second replaced it - so the rule became "a redefinition
captures what it replaces", not "no redefinitions".

**442. The gate reformed, after a review of the whole stack.** Four weaknesses,
each found by counting rather than remembering: 44 checks that could abort the
entire run on a missing needle (`before()` now, and a guard so none creep back);
runtimes that made temp directories where they pleased and left 134,000 of them
when killed (one scratch root per run, removed at exit AND on the signals that
skip exit); 41 whole-file checks with needles short enough to match a comment
that merely mentioned the name (`defined()` requires the definition; prose
needles lengthened to the line they mean); and no guard at all against an
invented name (an AST pass: every Name loaded that nothing binds, with its
line - a textual version matched 180 words inside strings and was thrown away).
A mechanical `.index()` conversion mangled three chained comparisons into
`bool < int`; a sweep for `before()` in a numeric comparison caught them.

**443. Six of 26 mechanical conversions changed a check's meaning.** "NAME in
py" sometimes meant "this is defined" and sometimes "this is used" -
`disk_usage` is `shutil.disk_usage`, not a definition. A regex cannot know
which. Each was restored to the form it meant, individually, after an edit
that aborted at its third needle had written nothing at all.

**444. A silence is a stated choice, or it is a hole.** 122 `except Exception:
pass` blocks; 17 said why. Most silence best-effort file work, where silence is
right. A ratchet: the count of unexplained ones may only fall, so every new one
carries its reason.

**445. The error system did not know about the features built since it.**
`log_error` writes the session error file and the issue record the Log page
shows. The updater wrote only to update.log; a boot step that failed wrote only
to panel.log. A failed update or a failed start was invisible in the one place
a reader looks. The updater's failures now carry stable codes (UPD-E01..E10, the
TTS path's shape) and reach the record; a boot step that throws is an error; the
helper's verdict of failure - written while no panel was running - is recorded
by the first panel to serve it, once.

**439. The updater is finished.** Five trials on the owner's machine. The update
itself worked from the first; every fault after that was in the surface - the
plan dialog, a tree rebuilt under the pointer, a stage inferred from a failed
poll, a result that vanished before it could be read - and each was caught by
his trial rather than by the gate, which is the wrong order. What is checked
now, as runtimes: element identity across ticks, zero style writes while idle,
nine failure outcomes landing on their rows, his exact timeline replayed, and a
real swap that changes the exe. The chain of custody is unchanged from patch127:
the archive is proved in memory, the helper proves it again from its own side,
every file is hashed as it lands, and the confinement to the PandorumLLM folder
has no configurable exception.

**440. A remote viewer is shown what the host knows, and can do nothing with
it.** The check door is host-only, so a viewer never receives updInfo; the
host's cached verdict rides on the state as a state and a tag - the url,
archive and checksum stay behind. The viewer gets the host's colour, green or
yellow, and no "Click to Update", no pulse, no pointer cursor, and a click that
does nothing. The Permission Tree names both halves.

**441. One rollback, the latest.** A backup is the version an update replaced,
so only the newest rolls the CURRENT install back - the ones before it roll back
to versions that are no longer installed. They stacked, one folder per update,
for ever. The helper's clearing stage now removes every backup but this
attempt's, on success only: a failed swap has just restored from this attempt's
backup, and nothing older is worth deciding about then.

**437. Read the launcher before designing around it.** I built a rename-aside for
`PandorumLLM.exe` on the belief that a running launcher holds its file. The
launcher EXITS the moment it has opened the browser - `return 0` - so while the
panel runs nothing holds the exe at all. The guard was for a case that does not
occur, and it was worse than useless: it renamed EVERY file the helper wrote to
`.old` and never removed them, so each update left `fleet-panel.py.old` and
friends in the owner's folder. Overwrite in place; rename aside only if a file
genuinely refuses; remember what was renamed.

**438. The helper is the right party to clear up, and it is a stage.** Deleting
the old needs no new panel instance: the helper watched the previous panel
close, wrote the new files, and has just confirmed the new panel answering. It
clears what it renamed aside, any `.old` an earlier attempt left, and its own
staging folder - and records `cleared` as its last step, so the dialog's eighth
row rests on a fact like the other seven. One catch found by running it: the
helper was started WITH the staging folder as its working directory, and Windows
will not remove a process's current directory, so it steps out first. The
panel's start-time tidy remains as the fallback for a file that was still held.

Proven from the container with an update that changes the exe - the case the
owner's four trials never exercised, because the exe had not changed between the
builds tested.

**435. A stage inferred from silence is a stage invented.** The owner's third
trial: the update completed in four seconds, and the dialog sat at "Closing the
panel" while the header beside it already read the new version. The apply loop
was waiting to SEE the panel go away before it would believe it had come back -
"swapping" was marked when a poll failed - and a four-second swap fell between two
one-second polls, so the inference never fired. The owner asked whether the UI
was timer-based. It was worse: a stage was marked because the page could not
reach the panel, which corresponds to no recorded fact at all.

While the panel is down the page cannot know anything, so it must not claim to.
The helper writes each fact to a file the moment it is true - verified, panel
closed, backed up, wrote, started - and the returning panel serves it. The page
asks one question, once a second: is a panel answering, and is its file THIS
attempt's? Every row is marked from that file, and each note names the fact the
mark rests on. The poll interval is how often it asks; nothing is decided by
time.

**436. A door that did not exist yesterday is not a failure today.** The verdict
door exists from patch137. The owner's dummy downgrades to v3.76-beta, which
serves a 404 for it - and the loop was about to report a FAILED update on a
successful swap. For a release too old to serve the file, the version it serves
is the proof - which is exactly what the header had been showing all along.

**433. The launcher's second job is wrong mid-update.** PandorumLLM.exe starts
fleet-panel.py hidden and then opens a browser tab on the port - the reason it
exists for a cold start. The helper restarted the exe after the swap, so the
owner ended up with two panel tabs: the one that asked for the update and was
waiting to reconnect, and the one the launcher opened. The helper starts the
panel the way the exe would - pythonw, no console - and leaves the browser
alone.

**434. A result that vanishes was never reported.** The apply loop reloaded the
page the instant the panel answered again, and the whole update disappeared
without a word - the owner had to infer success from the version number. The
helper now leaves a verdict at every exit it can take (the panel it was talking
to has gone by then; a file is the only channel), the returning panel serves it,
and the dialog stays: each stage marked, a failure landed on ITS row with its
reason, and a line saying what was achieved. Done reloads. The version-mismatch
reload had to be held too, or it would have yanked the page away first.

Nine outcomes are rendered by the gate - five panel-side failures, two helper
failures, the page never seeing the panel return, and success - each checked
for which row it lands on and what the verdict says.

**431. A test build that cannot be told from its predecessor will be mistaken for
it.** Every update-test dummy was zipped under the same name and its header read
`v3.76-p74 Beta` - a version that does not exist, produced by pushing a patch
number into a template meant for real builds. The owner ran a patch134 dummy
after patch135 had shipped, and reported patch134's two faults - the two-press
stop at "staged" and the pulsing glow - as still present. They were absent from
the build he had been handed; nothing on screen or on disk said so. The dummy's
header now reads `v3.74-updatetest from v3.76-beta-patchNNN`, the zip carries the
parent's number, and a FROM.txt sits beside it. That the faults were already
fixed does not make this his mistake: a fixture that is indistinguishable from
its previous version is a fixture designed to be confused.

**432. Silence during a check reads as an answer.** GitHub took 15-20 seconds to
reply on the owner's machine, and for that whole time the version button said
nothing - so it read as "no update", and then changed its mind. It says
"Checking for updates" now, and clicked in that state it says so, with the
linked name and one OK, instead of opening a plan it does not yet have. And the
header button's HTML was rewritten on every state refresh whether or not it had
changed - restarting its own hover fade under the pointer. Compare, then write,
there too.

**427. The first update on Windows worked; the owner's update.log proves it.**
Staged at 12:31:40, applied at 12:32:56, the exe started and answered in 13
seconds. The 76 second gap between the first two was him pressing Update a second
time - the two-press design was mine, and it was wrong: the plan dialog showed the
file and its checksum BEFORE the first press, so that press was already the
confirmation. Stopping at "staged" read as the process having died. One pass now.

**428. A guard against leaving must not fire on a reload the panel started.** The
beforeunload handler exists so closing the tab by accident asks first. It also
fired on both reloads the panel performs itself - after an update, and when the
served version no longer matches the page - and each became the browser's "this
page is asking you to confirm that you want to leave". Found while the owner was
looking at a different fault (the welcome greeting opening on top of the launch
view, from `load().then(maybeWelcome)`), which is now ordered after the panel is
up. Two faults, one symptom report.

**429. Writing a value that has not changed is still a write.** patch134 stopped
rebuilding the dialog's tree, and the glow STILL pulsed under the pointer,
because the painter set style.display on every button every tick - to the value
it already held. Touching the inline style restarts the hover transition. The
same discipline the text already had (compare, then write) now covers every
style too; ten idle ticks write nothing.

**430. A windowless process's children still open windows.** The helper runs
with CREATE_NO_WINDOW and asks `tasklist` every half second whether the panel has
gone - and each `tasklist` opened its own console for an instant. Those were the
"terminals popping up for a flash second". The flag goes on the child too.

**425. A view rebuilt every tick cannot be clicked.** patch133 made the update
dialog "self-rendering" by replacing its whole HTML every half second. Three
symptoms, one cause: the hovered button was destroyed and recreated, so its glow
pulsed; it was destroyed BETWEEN mousedown and mouseup, so no click event ever
fired; and update.log stayed unwritten because no press ever reached the panel.
The owner's panel.log showed five sessions of the dummy and not one [update]
line. He named the correct pattern himself - "its own graphical UI, like other
graphical solutions we have" - and it was already in the file: `higgsPaint` finds
elements by a data attribute and writes their text and width. It never rebuilds
the tree. The dialog does that now. A render test that rebuilds and reads cannot
see this fault; the gate's run checks element IDENTITY across ticks.

**426. The whole process belongs in the one dialog.** Pressing Apply tore the plan
down and opened a different modal for the restart, so the download was watched in
one window and the swap in another. The apply and restart phases are stage lines
in the same list now - closing, swapping, back, or stuck with the log to read.

This was the second consecutive dummy that could not complete a trial because of
the surface in front of the updater, not the updater - which had been proven end
to end from the container twice. A fault in the surface costs the owner a whole
trial each time, which makes it the worse place to keep failing.

**421. I matched the wrong component and called the instruction done.** Asked
to give the panel updater the layout of the llama.cpp/audio.cpp one, I copied
the PROGRESS ROW - running, failed, done - and reported it matched. What the
owner meant, and showed, was the PLAN dialog: "Install latest", the installed
version, the offered version, file and size, the sha256 line in green, Update / Cancel. He
had to send a screenshot of each to make the difference undeniable. Two different
things share the word "updater"; I picked the one nearer to hand.

**422. A dialog drawn from a snapshot shows the snapshot for ever.** Pressing
"Download and check" posted, then redrew - BEFORE the state had changed - so it
redrew the same thing, and the owner had to close and reopen to see anything. He
named the fault himself: "the solution was to create a graphical UI that
self-renders", which this project has done several times before. The dialog
redraws from fresh state on a tick now, for as long as it is open.

**423. A refusal three steps in read as a failure of step one.** The message was
"carries no file manifest" - emitted AFTER the archive had been downloaded and
its checksum verified. The dialog showed no tick for the stage that passed, so
the owner read a manifest refusal as "the SHA check still fails". Each stage is
its own line now. And, verified against the real release from here: the checksum
path worked the entire time.

**424. A test that can only reach a refusal proves nothing.** The owner's real
releases are made by hand, with no manifest and no helper inside, so requiring
both meant the updater could NEVER install one of them - and the update-test
dummy could only ever be watched refusing. Both are optional now, at no cost to
the guarantee: the archive is proved against the published checksum, every byte
written comes out of it, and every written file is re-hashed against the bytes
taken from it. Proven end to end against the real v3.76-beta from this
container: v3.74-updatetest became v3.76-beta, 16 files backed up, 3 written, 14
already identical.

**418. I wrote a rule for the filenames I generate, not the ones that exist.**
The updater looked for a checksum ending `.sha256.txt` - which is what
`make-manifest`-era builds produce - while the repo's own releases publish
`...zip.sha256` and, older still, `...-sha256.zip`. So the newest release read as
"publishes no checksum", and the older shape would have had its CHECKSUM chosen
as the archive, since that name ends in .zip. Both were visible on the releases
page the whole time; I never looked, because the rule matched what I had been
making.

**419. A failure cached is a failure repeated.** Three faults sat on top of that
one, and they are the same three this session keeps producing: the fetch error
was swallowed so the reason was lost; the empty result was cached for SIX HOURS,
so the owner could not retry; and the message reported a fact about the release
when the truth was a fact about the panel. The cache itself is sound - GitHub
rate-limits, and I hit it myself from this container - but caching an answer that
failed to arrive is indefensible and was never intended. It fell out of storing
the whole result regardless of what was in it.

**420. A test fixture that is hand-made is a test of the wrong thing.** The
update-test dummy was built by hand twice; both times the owner ran a trial
against an updater two patches behind and found a bug that was already fixed. It
is generated now, from whatever tree it is pointed at, differing from its parent
by the version tag alone.

**415. I checked one file and called it settled.** Asked where the sampler chain
was, I found it in `templates/single-gpu.ps1`, reported that it was there and
that nothing was wrong. The owner pushed back - three server slots, three
templates, did I actually read them - and the truth was that
`build_param_launcher`, which writes what his servers really run, emitted no
`--samplers` at all. One file agreeing with my expectation ended the search.

**416. --jinja was never emitted, and it silently disabled a whole feature.**
llama.cpp computes `template_supports_thinking = params_base.use_jinja && ...`,
so with no `--jinja` the server sets `enable_thinking` false whatever the
template says. Every reasoning control the panel offers - `--reasoning`,
`--reasoning-budget`, `enable_thinking` inside `--chat-template-kwargs` - was
being sent to a server that could not act on any of it. This was found while
looking for something else, and it likely explains the Shruti-Soft capture that
patch116 attributed to the model's training.

**417. The information I said was missing was already being collected.** For the
per-generation sampler report I looked at `pay_add`, saw only the merged request,
and told the owner the panel could not distinguish "SkyrimNet sent this" from
"the panel forced it" without new recording. He pointed at the provider's own
"Show SkyrimNet sampler values" switch: the proxy observes the incoming values a
layer above, BEFORE the merge. What was needed was to carry them onto the record,
not to invent a way to capture them.

The override list is still read by comparing the request before and after
`apply_route_shape` rather than by consulting the settings that were meant to
apply - a setting says what SHOULD happen, and the two differ whenever a rule
declines to fire.

**413. A staging list will not stay in step by being remembered.** patch129
shipped an `update-helper.py` two fixes behind the repo's, because the staging
step copies a NAMED LIST of files and the helper - added to that list at patch127
- was left out of the pass after. The code was right in the repo the whole time.
A panel updated into patch129 would have had no manifest installed and reported
itself changed for ever.

The fix is not a better memory. A file that the release ships and the repo keeps
has exactly one correct state - identical - so the gate compares them, and that
check needs no list maintained to keep working. Runtime caches are named as
exceptions once, in one place.

**414. It was found by RUNNING the update, not by reading it.** Every gate check
passed; the drift was between two trees, which no single-tree check could see.
The v3.74 test build the owner suggested is what surfaced it - and it surfaced it
on the last step, where the updated panel checked itself and said "changed".

**411. "I wrapped the ones I noticed" is not a fix.** patch126 made GGUF arrays
readable, so a value that had always been a number could arrive as a per-layer
list. Six reads were wrapped in `gguf_one_number`; SEVEN were left raw. `int()` of
a list raises, one raise killed the folder scan entirely, and the owner had no
model list for three patches. The line it actually died on - `blocks` - sat
outside the record my sweep was reading, so even the sweep I wrote to find them
was too narrow. When a change makes a whole CLASS of value possible, every reader
of that class has to be found, not the ones that come to mind.

**412. The launch view earned itself immediately.** That exception had been
thrown on every start since patch126 and was swallowed: the owner saw an empty
list and no reason. The first thing the readiness screen ever did was put the
error on the page in yellow, which is how the cause was found in one screenshot
rather than another round of guessing.

**408. "Nothing there" and "not looked yet" are different answers, and a panel
that cannot tell them apart will pick the wrong one.** The owner's model list
never loaded - not slowly, NEVER - and the menu said "not in models folder" under
files that were sitting right there. Three faults stacked:

- `/api/models` scanned inside the request, and `list_models` is single-flight
  behind a lock, so the request did not merely take ten seconds: it BLOCKED on
  the warm-up already scanning. The door reads a result now, in 0.4ms.
- a failed fetch was permanent, because `loadModels` only runs on a tab SWITCH -
  one failure meant an empty list for as long as he stayed on the page.
- and the message asserted absence, which is the fault this whole series keeps
  returning to: stating something the panel does not know.

Any one alone would have been survivable. What connects them is that nothing in
the panel could say "still working", so every early render had to invent an
explanation for missing data and picked a wrong one.

**409. A readiness registry is the fix for a class of lie, not a loading
screen.** Seven boot steps declare themselves BEFORE any of them starts, so a
step that never runs is visible as waiting rather than simply absent. A step that
throws is marked failed - a progress display that leaves a dead step saying
"working" is worse than none. `done` settles on success OR failure, and there is
a hard limit besides, because a panel that hides behind its own loading screen
over one broken step is worse than one that opens and says so. The visible screen
is the small half; the useful half is that consumers can now ASK instead of
guessing.

**410. Measure before blaming the change you just made.** The obvious suspect was
patch126's array reading. Benchmarked over 139 files with 150k-token
vocabularies: 9.83s before, 9.92s after. It was not the cause, and the real one
was three layers away.

**405. Verifying once proves nothing about later.** The owner asked that the
download never be let out of sight - that no swap be possible even during the
update. Holding a handle is not what delivers that; RE-CHECKING AT EVERY POINT OF
USE is. The archive is hashed in memory before it reaches the disk, hashed again
by the apply step about to open it, and hashed a third time by the helper from
its own side. Each file is proved from the archive before it is written and again
once it is on disk, because what matters is what ended UP there. The manifest and
the helper both come out of the verified archive rather than the folder, so the
step with the most power places the least trust in where it is standing.

Proven, not asserted: a staged archive altered after verification is caught and
discarded; a file that does not match the manifest is caught after
`fleet-panel.py` has ALREADY been replaced, and every file is put back. The
install ends where it began, never halfway.

**406. Four invented names in one feature.** `uuid` (not imported), `PANEL_PORT`
(the name is `PORT`), `/api/ping` (no such door - the reconnect loop would never
have seen the panel return), and a log line announcing a shutdown that the code
did not perform, which would have made the helper wait sixty seconds and abandon
every update. All four found by reading the code that had to answer, none by it
failing on the owner's machine. The lesson has not changed since gotcha 376; the
frequency has not either.

**407. A helper is a script, deliberately.** It can be read before it runs, it
adds no binary for a scanner to judge, and it ships inside each release so
nothing has to keep it current. An `Updater.exe` whose job is to download files
and overwrite executables is the textbook shape of a dropper - and this project
already declines to submit its one binary to scanners. It also refuses to act
without a live panel that asked for it, so it is not a general file replacer
sitting in the folder.

**402. Reading from the file is not the same as reading enough of it.** The owner
asked why Muse Glimmer and LFM2 showed no thinking label, and whether the panel
was reporting from a hard-coded table. It was not - it was reading the file and
finding nothing, twice over. Numeric ARRAYS were skipped wholesale, and several
architectures state `attention.head_count_kv` once per layer rather than once per
model, so Gemma 4 and LFM2 reported no kv heads at all: no GQA chip, and a
silently missing field in the pairing rule for exactly those families. And the
reasoning detector knew only `<think>` and `enable_thinking`, while templates
agree on neither - the switch is plain `thinking` on some, the opener may be a
harmony channel, and `reasoning_effort` is a third thing again, a LEVEL rather
than a switch. "The panel reads the file" is not a defence when the reading is
narrower than the thing being read.

**403. It needed styling, not a renderer.** Guide entries were one unbroken block
and I assumed the text was escaped. `pgLink` already copies markup through
untouched - they were shapeless because nothing had ever given them a shape, not
because they could not have one. Five minutes of CSS, after considering a
renderer rewrite.

**404. An unreferenced door is dead code even when it is half of something
good.** The panel updater's fetch, worker and door were written and verified, and
then withdrawn from this patch: nothing called them yet, and a door nobody knocks
on is the thing this project deletes on sight. It is worth more built complete in
its own session than shipped as scaffolding - especially this one, where a
mistake costs a machine that will not start.

**401. A wrong value is not a missing one, and they need different mechanisms.**
patch122 fixed float decoding and I told the owner the cache would refresh itself
"because `ropeBase` sits in `_KIND_FIELDS`". That rule drops an entry that is
MISSING a field. His entries had it - present and wrong - so 120 of 139 went on
holding 1315859240 for 1000000000.0, and only came to light because he sent the
file again. A value whose MEANING changed is what `_KIND_RULES` is for, and the
comment on the line that defines it says exactly that. Both mechanisms already
existed and were already documented; I reached for the wrong one and then
reported the problem as handled.

The reporting is the worse half. Saying "this refreshes automatically" without
running it against a cache in the affected state turned a fixable oversight into
a claim the owner had to disprove himself.

**398. When a number cannot answer, ask a different question.** Two projectors
sat with no family because width 5120 belongs to both Mistral and Qwen in the
owner's tree. The pairing rule was not too strict - it was being asked something
the number cannot decide, and no amount of extra numeric fields would have helped
because a projector states only one. What decides it is where the file LIVES: he
keeps a projector in the folder of the models it serves, which is his own
statement about what goes with what. The tiebreak answers only when one family is
strictly nearest, and names "folder" among its reasons so the answer can be
judged.

**399. For a file that is nothing but a mechanism, the mechanism is the truest
label available.** A drafting head whose parent cannot be found now reads
"DFlash drafter" rather than nothing - and only a PART may do this. A language
model labelled by its mechanism would be the category error patch118 removed; a
head labelled by its mechanism is simply what it is.

**400. A backslash does not survive two nestings.** `pairFolderOf` lives in JS
inside a triple-quoted Python string. A `/\\/g` regex written there was eaten
twice - Python read the escape, then the page string read it again - producing an
invalid regex AND a SyntaxWarning on the whole PAGE constant from `d:\models` in
an adjacent comment. Built from `String.fromCharCode(92)` instead, and no Windows
paths in comments inside PAGE.

**397. A load path does not log.** patch122 added a `panel_log` line to
`_kind_map`. `_kind_map` is called from inside `with _KIND_LOCK:`, and
`panel_log` reaches `log_dir()` -> `load_config()` - disk work that on a first
load can come back round to a model read wanting that same lock. `threading.Lock`
is not reentrant, so it is a DEADLOCK, not a slow path: the owner's panel never
reported a port and would not start at all. His cache had 139 entries all made
stale by the same patch, which is exactly the state that takes the branch. The
load leaves a note in `_KIND_SAY` now, and `_kind_say_flush()` says it after the
scan with no lock held.

Two things made this shippable when it should not have been. The check was
written against `_kind_map` called DIRECTLY, never through the lock its only
caller holds - so the test exercised a path that does not exist in production.
And a fresh container has no stale cache to trip the branch, so the panel booted
here every time. **Before adding a call to a function, read who calls IT** - the
lock was two frames up and one grep away.

**393. A float read as an integer is wrong in a way nothing notices.** GGUF type
6 is FLOAT32 and 12 is FLOAT64; both were decoded with `int.from_bytes`, so
`ropeBase` held 1315859240 - the bit pattern of 1000000000.0 - across 120 of the
owner's 139 models. Nothing consumed the field yet, which is exactly why it
survived: the number was stable, plausible and never checked. Every float key
read from here on would have inherited it. Found only because he asked why a file
had not changed.

**394. A record that is correctly unchanged looks exactly like one that is
stuck.** The owner watched `model-kinds.json` for two patches and could not tell
which. He was right to ask and the file was right not to change - a patch that
alters how something is DRAWN touches no stored fact. The panel now says on every
load how many remembered models are current, or how many must be re-read and
which fact they predate.

**395. A part is smaller than the whole it serves.** Pairing required every
shared field to agree, including feed-forward - and a drafting head's is smaller
than its parent's by construction: 19968 against 28672 on the owner's Muse
Glimmer. So the rule ruled out the correct family every time, and the heads sat
with no label while the rule looked strict and principled. What a part and its
parent must share is the shape of the state passing between them - residual
width, vocabulary, attention geometry - not the size of the work each does.

**396. One mark for a mechanism, another for a relationship.** Collapsing
"MTP drafter", "DFlash" and "DSpark" into one mark was right; collapsing that
mark with the built-in case was not, because a 27B chat model then read as though
it were itself a drafter. A file that IS a head wears MTP as its role; a model
that HAS one wears built-in MTP as a feature. The type suffixes on the names -
"[draft model]", "[vision projector]" - went at the same time: the labels say it,
and saying it twice cost width in the menu whose width was the running complaint.

**390. Three marks for one fact.** MTP, MTP drafter, DFlash and DSpark were four
labels for a thing a reader needs to know once: this file predicts ahead. Which
mechanism it uses is not news at the point of choosing a model, and what actually
distinguishes the two FILES - a model carrying a head versus a head on its own -
was already said by the role beside it. One mark, and the role carries the rest.

**391. A part states only what it needs to.** A vision projector carries one
number, `embdOut` - the width it projects into, which must equal its parent's
embedding width. No vocabulary, no layers, no feed-forward. The two-field pairing
rule therefore silenced all eighteen of the owner's projectors, and "needs more
evidence" became "can never be answered". A rule written for one kind of part has
to be checked against the others before it is called safe: a projector is paired
on that one field, and only when exactly one family in the folder has that width.

**392. Read the cache before believing the complaint - and before dismissing
it.** The owner said "a lot of models still have no family labels". The cache
said 118 of 139 had one. Both were true: the 21 without were 18 projectors, one
Flux and two DFlash heads, and the projectors were a real fault sitting inside a
number that looked reassuring.

**386. A fallback answer is an answer nobody checked.** `_model_kind_read` ended
with `return "main"`, so anything not recognised as vision or draft became a
language model by default - and the owner's Flux diffusion model was offered as
something to load into llama.cpp. A language model DECLARES its layers and its
trained context; those are the figures the card already prints, and a file that
cannot fill that line is not one. The test is asked LAST, so a projector or a
head - which declare neither either - cannot fall through to it.

**387. "Which family" and "what role" are different questions and want different
slots.** A file that serves no purpose for a language model belongs to no family
and says `other` where a family would go; a vision or draft file whose family
cannot be read says NOTHING there, which is a different claim - it has one, and
the panel cannot see which.

**388. One matching number is not evidence.** Pairing a drafter to its parent by
embedding width alone would have attached a Muse Glimmer DFlash head to a Gemma
4: in the owner's own 139 files, three of seven widths are shared between
families, and 5376 is one of them. `pairSuggest` judges on every field both sides
state - width, vocab, key and value lengths, kv heads, feed-forward - refuses
below two shared fields, treats a silent parent as a rule-out rather than
agreement, and yields NOTHING when two candidates survive. Two is not a near
miss; it is a question the file cannot answer. And what it produces is marked
with a tilde in its own colour, because a suggestion that looks like a reading is
worse than no suggestion.

**389. A `const` used above its declaration is a ReferenceError, not a default.**
The family slot read `mk` on the line before `const mk` - which would have thrown
at render time and blanked the card, not quietly defaulted.

**382. The cache already held every answer.** The owner sent his own
`model-kinds.json` and every one of four faults was visible in it: sixteen main
models carrying `spec=draft-mtp`, `dflash-draft` filed as `kind=main`, `lfm2moe`
with an empty `family`, `clip` uniformly empty. Detection was never the problem -
four USES of correctly recorded facts were wrong. When labels look wrong, read
the record before touching the reader.

**383. `spec` answers "what would this draft LIKE", not "is this a drafter".**
A main model with a built-in MTP head reports `draft-mtp` because that is what it
would do if used as one. Printing it as a role labelled sixteen language models
"MTP drafter" beside their own LLM label. It is now said only of `kind ==
"draft"`.

**384. A membership test on a name that carries suffixes must allow for them.**
`DRAFT_ARCHS` holds `dflash`; the owner's header said `dflash-draft`; so a DFlash
drafter was offered as a language model, with a dense label to match. The same
one-suffix assumption left `lfm2moe` and every future `-moe` variant with no
family.

**385. One fault, one mark.** patch118 added a warning tag to the row while the
option's own text already ended with the emoji, so a mismatched model wore two -
in the menu whose width was the complaint that started the whole thread.

**379. A function named for one job is not a function for a similar job.**
`arch_label` describes a FILE - it deliberately appends "assistant (MTP
drafter)", "(MoE)", and for llama a note that the family also covers Mistral and
NeMo. Every one of those is correct for its purpose and wrong for a label whose
whole job is the family, because the type is stated after the name and does not
want saying twice. `arch_family` is a separate function with the narrower job.
Read what a function RETURNS before reusing it, not just what it is called.

**380. A part is not a model.** Dense, MoE and hybrid describe how a model is
built, and the panel was saying them of drafting heads and projectors too - so an
assistant head shipped beside an MoE parent was labelled "dense", which is true
of the file and false about the pair it belongs to. Those words are now said only
of `kind == "main"`.

**381. The tensors cannot separate Mistral from Llama; the header can.**
llama.cpp reports architecture `llama` for Mistral, NeMo and Yi alike, so no
tensor scan will ever tell them apart. `general.name` is a header field and does,
and is read like any other - it is not a guess from the filename. Where it says
nothing recognisable, the family stands.

**376. FOUR invented field names in one series.** `st` in a scope that had none,
`srv.serving` and `srv.running` where the field is `srv.state`, `tokens` where the
record stores `tok`, and now `m.label` for `m.archLabel` plus `kind === "mmproj"`
where the values are main/vision/draft. Each one rendered something plausible
rather than failing: no architecture ever appeared, and every vision projector
was labelled LLM. The panel knew all of it. Read the writer before naming the
field - and put a RUNTIME on the values, because a textual check passes just as
happily on a name that does not exist.

**377. A role is what a thing IS; a feature is what it carries.** The server-card
role was exclusive, so a 27B language model with an MTP head was labelled MTP and
stopped being a language model. Labels that answer different questions must not
compete for one slot.

**378. The primer is in the template, so it can be removed.** Liquid AI say of
LFM2.5-2.6B that it "adds a `<think>` tag directly in the chat template when
starting an assistant answer" - which is why `enable_thinking` did nothing in the
owner's capture: there is no switch to honour and the prompt primes it every
turn. The panel writes a copy of that template with the opening tag removed and
passes `--jinja --chat-template-file`; the GGUF is never touched, and `--jinja`
must come first or llama.cpp accepts only the names of its built-ins. It removes
the invitation, not the training - so it reports what it changed rather than
promising a result, writes nothing for a template that never primed, and is off
by default.

**372. A label keyed on an architecture is a guess wearing a fact's clothes.**
The card said "Trained reasoning" for every `lfm2` file, so an LFM2.5-1.2B-Instruct
with no thinking mode wore it too. Whether a model was TRAINED to reason cannot
be read from a file - no tensor, no header key - and the owner's rule applies: if
it cannot be determined, do not state it. The list is gone.

**373. A substring is not a parse.** Replacing it with "does the template mention
`<think>`" reintroduced the same fault in a new costume: LFM2.5-1.2B-Instruct's
template mentions the tag in a `keep_past_thinking` option that preserves blocks
from earlier turns. What separates priming from housekeeping is WHERE the tag is
written, so only a `<think>` after the last `add_generation_prompt` counts.

**374. Ask the program that already knows.** llama-server publishes
`chat_template_caps` at `/props` - the verdict of its own Jinja parser, including
`supports_thinking`, which it reports false when `--jinja` is off whatever the
template says. No file can know that. So the panel reads the header for every
model in the folder and asks `/props` for the one a server has LOADED, and the
server's answer replaces the guess rather than sitting beside it. Two answers to
one question is how a card starts lying.

**375. /props cannot be a launch-time survey.** It describes the loaded model, so
asking it about 500 files would mean loading 500 models. Measured instead: the
header read is 27ms for 500 models and cached on `path|size|mtime` for ever;
`/props` is 1.5ms and asked only of a port already serving. Different scopes, not
different speeds.

**370. "Make A match B" names which one moves.** The owner asked three times for
the menu field to be as dark as the menu. patch114 finally made them equal - by
lightening the MENU, the half he had not asked about. Matching two values is not
the instruction; the instruction says which value is correct. Read the direction,
not just the relation.

**371. Ask the file, not the name.** patch107 knew `lfm2` was hybrid and asserted
that its KV cache would be small. The file says it outright: a hybrid names its
convolution layers `blk.N.shortconv.*` and its attention layers `blk.N.attn_*`,
so counting the distinct block numbers on each side gives "3 of 16 layers
attend" - the actual reason the cache is small, stated as a number. It also
works for any file built that way, named or not, so a future architecture with
the same layout needs no code. Stacked expert tensors (`ffn_gate_exps`) are read
the same way. What CANNOT be read this way is reasoning: that is a training
property, not a structural one, which is why that chip still says so in words.

**367. A value written in two places is a value that drifts.** The closed field
and the open list each held their own copy of the menu colour. Every patch that
touched it changed one and left the other, so the owner had to ask three times
for the same thing - and each time the answer was "fixed" while still visibly
wrong. The colour is one custom property now, named once and read twice. When a
request has to be made more than once, stop fixing the symptom and look for the
duplicate.

**368. Two things that look alike are not one thing.** patch111 gave the proxy
MOSS the audio.cpp pack's name, reasoning that it was one model reached two ways.
It is not: the proxy path launches NOTHING - the panel translates SkyrimNet's
Gradio protocol to a moss-tts-server the owner runs - and that server loads
MOSS-TTS Delay, the 8B baseline OpenMOSS train beside the Local one, while the
pack here is the small 1.5 build. The owner noticed because the sizes did not
agree. A shared name is a claim about identity; check it before making it.

**369. A stated figure and a measured one must not look alike.** The proxy's
weight cannot be measured from this side, so the panel reads the publisher's own
file listing and sums the weight files - a reading. Until that listing is read,
a stated fallback stands, and it wears a tilde so the two are never confused.
A runtime figure from the server itself would beat both and should replace them
when one is available.

**365. An empty catch is a fault you will never be told about.** The size labels
were fetched when the TTS pane drew, then `load()` and `renderTts()` were called
inside `.catch(function () {})`. Whatever went wrong in that chain went wrong in
silence, and the labels appeared only after a TTS was selected and forced a fresh
render. Work that must happen before a page is useful does not belong in a
best-effort callback attached to that page: the listings are read at LAUNCH now,
in the background job that already does the slow first-run work, and the page
asks for nothing. The door it used to ask through is deleted rather than left
standing.

**366. An exception is a thing to keep in step for ever.** patch111 gave the TTS
chooser a darker field while every other menu kept the old one, because that one
menu sits alone on a wide pane. The owner then asked for the standard menus to
match - so the colour moved onto `.selbtn` itself and the special case went. A
style that is right for one control is usually right for the rest; making it an
exception buys a difference someone has to maintain.

**362. A harness that does not use the real function tests nothing.** patch111
passed each option's label markup through `data-html` and escaped it with the
page's `esc()`, which escapes `&`, `<` and `>` and NOT quotes - so
`class="tslname"` closed the attribute and every row in the menu rendered empty.
It passed here because the harness had defined its own stricter `esc`. Pull the
real one out of the page, or the test is about a function that does not exist.

**363. Markup does not travel through an attribute; values do.** The fix is not
a quote-escaper. An option now carries `kind:value` pairs and the component that
draws them builds the spans as TEXT, so nothing in a model name can break a row.
The component owning the drawing is also what makes it safe.

**364. Two readings of one fact are two chances to be wrong.** The new start
button first read `srv.serving` and `srv.running` - neither is a field, so it was
false for ever and would have shown a start triangle over a running server. The
header button had the right test all along: `String(srv.state || "") ===
"serving"`. Copy the reading that is already correct rather than inventing a
second one, and check the field names against what the server actually sends.

**360. THE STANDING RULE: fix it, or replace it. Never cover it.** When the
owner reports something broken there are exactly two acceptable answers - the
thing remains and is fixed, or the thing is deleted and replaced by something
that works. Whichever is cleaner. What is never acceptable is leaving the broken
part live and putting a correction on top of it: the fault still fires, only its
last layer is hidden, and it reappears at the edges - during a transition, on a
state nobody styled, on the next browser. This is not a rule about CSS. It
applies to a function whose result is patched by its caller, a setting that is
overridden rather than removed, a code path kept "just in case" beside its
replacement, and a check that is excused rather than corrected.

The gate enforces the CSS-shaped case: no rule may exist whose only content is
switching off a property another rule still applies. The rest is discipline, and
this entry is where it is written down.

Twice in three patches I broke it. patch110 "fixed" a focus ring by cancelling
it - and the cancel did nothing at all, because the `button` rule already sets
`box-shadow:none !important`, so no ring was ever applied. The reported fault
survived untouched. The sweep then found `.dryok { box-shadow:none }`, another
cancel for an effect that was never applied. Both removed.

**361. Look for the component before building one.** patch109 built a bespoke
dropdown because a native `<option>` cannot carry a coloured label - which is
true, and is exactly why `enhanceSelects` already replaced every select on the
page with a `.selwrap` stand-in that has its own button, list, caret and hover.
Two components then existed for one job, and the second inherited none of the
first's fixes. The whole of it is deleted; the shared stand-in gained ONE
capability instead - an option may carry `data-html` - so every dropdown in the
panel can hold a label. Grep for the behaviour, not the name: `.selwrap` did not
answer to "dropdown", "ddwrap" or "customSelect".

**356. A button on the change chain never speaks.** The new TTS chooser was
built in patch109 and its handlers were written beside the old select's, in the
CHANGE listener. A select fires change; a button fires click. The control did
nothing at all - not subtly wrong, entirely dead - and it is the standing gotcha
about buttons belonging to the click chain, made again. When a control's type
changes, its handler moves chain.

**357. Read through the element that carries the action, never the one that was
clicked.** The chooser's head holds spans, so clicking the visible title is a
click on a span with no `data-act`. `ev.target.dataset` finds nothing there;
`e.target.closest("[data-act]")` finds the head. The click chain already did this
correctly - the change chain does not, which is another reason a button does not
belong on it.

**358. An allowlist is what a half-blind check needs.** The orphan sweep matched
only `d.act === "X"`, the change chain, so eight click-chain handlers had to be
excused by name - and an act that moved between chains looked orphaned while
being perfectly handled. Matching both forms removed the allowlist entirely and
put those eight back under the check. When a guard needs a list of exceptions,
suspect the guard.

**359. A focus ring is a rectangle.** `.txt:focus` draws a box-shadow, which is
right around an input and wrong around a title - the owner saw a rectangle where
he expected the letters to glow. The head refuses the ring and takes a
text-shadow on its own text instead.

**352. A native option renders text and nothing else.** Asked for a blue WIP
label and a green size beside each TTS title, the honest first answer was that a
`<select>` cannot hold either - which is why "not downloaded" had always tinted
the WHOLE row amber. The control is a listbox now: a button for the head, a
`role="listbox"` for the list, a `role="option"` per row. Say what a control
cannot do before building on it.

**353. The data was already there; I looked in the wrong place.** I said the
panel had no per-model sizes, having read the static `TTS_PACKS` table where each
pack carries one `gb` string. The owner pushed back, and he was right:
`tts_repo_files()` already returns every .gguf for a pack with its exact size in
bytes, cached for fifteen minutes to fill the download chooser. The range is
computed from that, so the figures are real files rather than a number typed into
a table that goes stale the day a quant is added. Before saying data does not
exist, look for who else already needed it.

**354. Marked by absence, not by presence.** `TTS_SETTLED` lists the finished
packs and everything else carries WIP. Named the other way round, a pack added
tomorrow would pass as finished because nobody remembered to mark it. The list
that is easy to forget should be the one that fails safe.

**355. A page being drawn must not reach for the network.** `tts_size_range()`
reads the cache and returns "" when it is cold; the fetch lives behind
`/api/tts-sizes`, which the page calls once when the dropdown is first opened.
The state path is polled - anything slow on it is slow for ever.

**350. A hard box is a promise about content, and content broke it.** `.tl.one`
is a fixed 1.5em row, assigned on the rule that "a RECORD has no business being
more than one line tall". True of a timing row; false of the banned-tag list,
which runs past six hundred characters. A line needing three rows still got one
and the next line painted over it. The fix is not to let records wrap - that
would cost the row rhythm the terminal depends on - but to make the promise TRUE:
anything past `TL_FOLD_CHARS` folds at its label, so the row really is one line
tall until someone asks for the rest.

**351. The comment tripped the check that the code passed.** The clip rules
forbid `overflow` inside the `.tail .tl` span because a clip slices the glow
halo. After removing the property, the gate still failed - the word survived in
the comment explaining WHY it had been removed. A textual guard reads prose too;
say it without saying the word.

**347. There is no lfm2 flag; there are lfm2 CONSEQUENCES.** Asked to support a
family properly, the reflex is to look for its parameters. llama.cpp has none:
all 433 arguments in `common/arg.cpp` were read and not one keys on recurrent,
hybrid, mamba or ssm. What a hybrid model needs is the general controls that
decide how its memory is laid out - and comparing llama.cpp's flag list against
the card found two missing that bear directly on it: `--kv-unified` /
`--no-kv-unified` and `--kv-unified-per-slot`. Both are fleet questions - how the
cache is shared across parallel slots - and they matter most where only some
layers attend. Diff the upstream argument list against the card; do not guess
which flags exist.

**348. A negatable flag cannot go through the value path.** `--kv-unified` and
`--no-kv-unified` are both bare, so the generic emitter would have written
`--kv-unified engine default`. Three states, two flags, and the third writes
nothing so the engine's own default stands.

**349. Inserted into a loop above the line that defines what it reads.** The
first draft of that handling sat before `v = _ngtpl.get(k) or gv(k)`, so it used
the PREVIOUS parameter's value: on and off both wrote nothing and no error was
raised. Same family as gotchas 300 and 318 - check what is defined where before
inserting into a span, not only what the span looks like.

**344. A model card is not the last word on what a model does.** Asked to
support an LFM2.5 fine-tune, the owner said it seemed to reason; its card says
nothing about reasoning at all, and I nearly took the card's silence as an
answer. Liquid AI's own material settles it - they ship an LFM2.5 Thinking
variant that writes `<think>` blocks, and the traces went in during MIDtraining,
so a fine-tune inherits the habit whatever its own card mentions. His field
capture then closed it: `enable_thinking` sent all three ways, reasoning disabled
on the provider, 2207 tokens of `<think>` returned for a one-line answer. An
owner watching the thing run is better evidence than a README.

**345. Support was mostly already there; what was missing was the card saying
so.** `lfm2` was in the architecture table, `_THINK_RX` strips a reasoning block
by SHAPE rather than by family - so an untaught architecture still cannot leak
into dialogue - and all four reasoning controls were already on the card. The
work was two chips: why the KV cache is small for the context (only some layers
attend; the rest shows as Recurrent state), and that the Thinking switch may do
nothing here. Before adding machinery, check what already covers the case.

**346. The lever that works is not the one that reads as "off".** For a family
that reasons by training, `enable_thinking` is ignored and a reasoning budget of
ZERO is worse than useless - patch38 measured that a model which always opens a
reasoning block is forced shut on its first token and answers with a stub. The
working control is a small POSITIVE budget with a budget message. The card now
says which control to reach for and which value not to use, because that pairing
is not guessable and cost this project a patch to learn once already.

**342. Ask the engine what it will not take; do not keep a list.** patch105 got
DramaBox loading and it then refused every line: HTTP 500, "unknown DramaBox
request option: temperature". The patch103 logs carry "unknown DotTTS request
option: temperature" as well - two families refusing an option that Higgs
requires, so it cannot be dropped for everyone. A table of what each family
accepts is precisely what went stale for years with `reference_cache_slots`. The
engine names the option in its own error, so the panel reads the name, remembers
it against THAT model, and asks again without it - one extra round trip on the
first line to a fussy model and none after. Nothing in the code names DramaBox,
DotTTS or temperature.

**343. A learned retry needs three guards or it is a loop.** It retries only for
an option the request actually carried, only once per option, and at most six
times in all. Without the first, a refusal naming something else retries for
ever; without the second, an engine that repeats itself does the same; without
the third, an engine that refuses everything hangs the line.

**338. A recovery that only fires inside three seconds is no recovery for a
large model.** The panel wrote `reference_cache_slots` on every start; 0.6
dropped it from Higgs and 0.7 knows it for no family, so the server refused and
a retry dropped session options. That retry only fires if the process dies
within three seconds of spawning - true of a 1.3 GB pack, false of DramaBox at
18 GB, which reads weights far longer than that before it parses the option. So
one pack never started at all, twice over. A field session settled the wider
question: every server that reached "listening" had ZERO session options and
every start carrying one was refused. The option is gone, and with it the rung
that dropped it and the "Cached Voices" setting that fed it - a control that did
nothing whatever it was set to.

**339. A guard with no lead-in starves the short line.** Tokens per character
measured 3.80 at p90 under 20 characters and 1.53 over 160, because a line costs
something before it costs anything per character - 1096 field lines fit
`15 + 1.66 x chars`. A purely proportional guard cannot fit both ends. The guard
is lead-in plus rate now, and may WIDEN on what this machine has actually been
measured to need - never narrow, never below twelve observations, so the user's
tokens-per-character still sets the shape and is not countermanded.

**340. The record stores `tok`, not `tokens`.** Reading a field that is not
there returns 0 for every row, so a measurement-driven widening would have
silently never happened with every textual check still passing. Read the writer
before naming the field.

**341. A cap on each marker is not a cap on the line.** `[pause Ns]` was clamped
to ten seconds per marker, so one oversized tag was cut correctly while four
ordinary ones passed untouched and asked for thirty-four seconds of silence
between sentences. MOSS is the only dialect that renders these literally, which
is why it looked like a MOSS fault and was not one. The budget is now spent
across the line: earlier markers keep their length, later ones take what is left,
and one with nothing left is dropped.

**336. `what` outlives the install; `running` does not.** One install record
serves both installers and `what` says whose it is. The TTS row tested only that,
so after a llama.cpp update FINISHED it went on announcing one - hiding the
audio.cpp verdict and the chosen model until the record was dismissed on the
other page. Folder Setup's own row has always read `mine && g.running`; the two
never agreed, and the sentence on screen said "is running" while the test did
not. When two views share a record, they need the same test, and the test should
say what the words say.

**337. A note that has been read should not need dismissing.** A finished
install's note is cleared when the reader leaves the page it sits on; Dismiss
stays for anyone who wants it gone sooner. This is not tidiness: the record is
shared, so a lingering note left the OTHER installer's page explaining itself
instead of showing its own verdict. Only a finished note clears, only from the
page that owns it, and re-selecting the same tab is not leaving it.

**333. When an upstream shape goes, the setting for it goes too.** audio.cpp
shipped portable/balance/fast build profiles through 0.6 and dropped them at
0.7, moving to one archive per CUDA line - the shape `LLAMA_LINES` already
described. The panel kept a chooser, a stored `ttsAcppProfile`, a resolver, a
profile-aware exe finder, a subfolder search, a save-list entry and a click
handler for a control that would no longer be drawn. `ACPP_MIN_VER` is `(0, 7)`
now and all of it is gone. A 0.6 install is still FOUND - telling someone
"nothing there" about a folder that plainly has the binary helps nobody - and
the version verdict is what turns it away, with the minimum shown.

**334. Prose goes stale more quietly than code.** Removing the profiles left the
manual-install instructions telling people to download
`audiocpp-windows-cuda-balance.zip`, an archive 0.7 does not publish, plus a
block of comments describing a per-profile asset table that had already been
deleted and a UI note explaining a choice that no longer existed. None of it
would ever fail a check. Grep the words, not only the identifiers.

**335. I inserted the same gate section twice.** The p103 block went in, an
edit to one of its checks was applied to a re-inserted copy, and the file
carried two. Both passed, so nothing complained; deleting the wrong one then
took a runtime with it. A section is applied ONCE - check the count before
editing a block that was just written, the same discipline `rep()` enforces
everywhere else.

**332. A message that has to be rationed should not be there.** A refused write
raised a modal, throttled to one a second because it was already known to repeat.
A remote view polls, so it arrived faster than anyone could dismiss it and the
page could not be used. Patch101 opened the one door that was spamming it, which
treats the instance and not the cause: there are ninety-odd host-only endpoints
and any of them can do this again. The owner's answer was the right one - delete
the dialogue. The caller is still told through `__refused` so nothing acts on a
refused write, the refusal is traced, and the viewer already knows where it
stands: the host-only tabs are not drawn for them and the header carries a badge.
The throttle was the tell. Rationing a message is an admission that it fires more
often than a person should be asked to care about.

**329. The display rule wanted uppercase; the prompt asks for lowercase.**
`tts_tags_display` turns a tag into a stage direction, and its bracket rule was
`\[([A-Z]+)-([A-Z_]+)\]`. SkyrimNet's prompt asks the dialogue model for the
LOWERCASE form, so `[emotion-amusement]` - the form that actually arrives -
matched nothing and was printed raw in front of every spoken line for many
patches. The engine was always handed the right control token; only the reader
saw markup, which is why it looked like a TTS fault and was not one. When a rule
names a case, check which case the thing it reads is written in.

**330. A thought is not speech and carries no mood.** The dialogue model is
asked for an emotion tag on what a character SAYS, and it sometimes tags what
the character thinks as well. Stripped at `thought_lines`, the one place
thoughts are cut out of a reply, so the terminal row and the thought-audio pass
both get clean text from a single edit.

**331. A new door needs to be told who may knock.** `/api/slot-logs` was added
at patch97 and never put on `REMOTE_READ_OK` - and `/api/slot-log` had never
been on it either. A read-only remote viewer was therefore refused on every
beat, and since patch100 made the beat 400ms that is a warning three times a
second which no amount of clicking OK can clear. Both are reads of a log the
panel already serves remotely through its tail feeds, and neither takes a path
from the caller. The same omission as the compSeen set: a door was added and
nobody asked who was allowed through it.

**326. A free figure is not an allocation and must not wear an allocation's
chip.** "Free at load" and "Free before drafter" were drawn in the list of
allocated buffers, carrying the destination chip that means THIS LANDED HERE -
so the card read "free VRAM ... -> VRAM", which says nothing. The figures are
worth having; the list of allocations is not where they belong. Both went to the
allocator log, under a headroom line. The row existed for many patches and was
only ever wrong once it started appearing.

**327. A second launch path meant a second press that was not a press.** The
header Launch button posts to `/api/launch-stack`, not through the per-slot
press, and only the press cleared a card's report. So a relaunched server kept
the previous run's figures - and since that report was marked `final`, the beat
had no reason to ask about it again. It looked like the report was slow; it was
not asking at all. The fleet press now clears every card, and a sweep every
twentieth beat asks about final slots anyway, so a launch by any path nobody
told the panel about is still noticed within eight seconds.

**328. A watcher must beat faster than the thing it watches.** A load writes its
buffers over a few seconds and the report was polled every 1.5s, so the owner saw
the weights and then everything at once, with nothing in between. 400ms shows the
buffers arriving. It costs nothing to look more often here because one request
carries the whole fleet and the asking stops dead when every log is final.

**322. A phase marker is not a boundary between buffers.** The compute dedupe
was keyed on `(buffer, device, phase, value)`, so a drafter that re-reserved
after the clip marker had its two reserves filed under different phases and
counted twice - 92.50 MiB on the card, 44.50 on the host. The owner relaunched
the same server with vision OFF and the drafter still reserved 92.50 twice on
its own, which settled it in one run. The key is now `(buffer, device, value)`:
an identical figure on the same device in one launch is one buffer, wherever it
falls. The field fixture's 455.02 was carrying that double count too, and is now
362.52.

**323. The log had been saying it all along.** "Free at load" never appeared
because it matched `GPU free VRAM:`, which this build does not print - while
`llama_prepare_model_devices: using device ... - N MiB free` sat in every log,
read only to detect the zero case. It appears TWICE: before anything loads, and
again when the drafter's turn comes. The owner's 5090 showed 681 MiB at that
second point on a launch whose drafter then died, and nothing on the card said
so. Read what the log offers, not only what was first looked for.

**324. Compare what you WROTE, not what came back.** The row pulse was gated on
`vv.innerHTML !== vhtml` - a round trip through the HTML parser, whose output
need not be byte-identical to its input. Since the report began repainting every
beat, any such difference meant a value pulsing for ever on a server that
finished minutes ago. The comparison is now against a value stored by the panel.
The repeat could not be reproduced here, so this is a guard on the mechanism
rather than a diagnosis of it.

**325. Equal specificity means the later rule wins.** `.pgrpfold.shut` and
`.pgrpfold:hover` both weigh two classes, and `.shut` was written afterwards - so
hovering a COLLAPSED heading left the text dim while the arrow, which had its own
rule, lit alone. The hover rule now names `.shut` explicitly and is written after
it. When two rules tie, order decides, and order is easy to change by accident.

**319. Thirteen patches, one leaked set.** Patch86 kept the compute-dedupe
bookkeeping in `out["compSeen"]` - a `set`, which `json` cannot write. The
moment a log grew its first compute line the door raised WHILE writing the
answer: connection closed, nothing sent, browser reports "NetworkError when
attempting to fetch resource". That is why every card stopped exactly at the
weights row (the last thing read before that line), why a 1.5 GB model reaching
its compute line in three seconds showed nothing at all, why a refresh lost
everything, and why polling rules, merging, `final`, backlogs and batching all
changed nothing - every one of them was downstream of an answer that was never
sent. The owner said from the start that it had worked several patches ago. It
had: up to patch85.

**320. The gate tested what the reader RETURNED, never whether it could be
SENT.** A report carrying a set satisfied every check for thirteen patches while
no browser could receive it. Any value that crosses a door must be proved
writable, not merely correct: the sendability run now serialises a report at
three stages of a load and pushes both doors' whole answers through
`json.dumps`. A returned object and a delivered one are different claims.

**321. Scratch state does not belong in the thing being returned.** `compSeen`
was the reader's own working set, put in the report because that object was
already to hand. A report is what the panel promises to send; a local is a
local. The comment now says so where the local is declared.

**316. The request was never made: a listen backlog of five.** Six patches went
into why the allocation report stopped filling in - parsing, settle rules,
merging, provenance - and the answer was that the browser could not open the
connection. `socketserver` defaults `request_queue_size` to 5, and the panel's
Handler inherited it along with HTTP/1.0, so every poll opens a new connection.
The owner launches his whole fleet from one button and the panel allows twenty
servers; a poll per slot, plus a 250ms ticker and three 600ms tickers, is a
burst well past five every beat, and the OS refuses the rest. "NetworkError when
attempting to fetch resource" was the only honest description anything gave, and
it took making the door speak (patch96) to see it.

**317. Cost per server must not scale with servers.** The fix is not a bigger
backlog alone: twenty servers polled individually is twenty connections in the
same instant however deep the queue. One request now carries the whole fleet,
naming only the slots whose logs are not yet final - so a fleet that has
finished loading asks for nothing, and one server costs the same as twenty. The
per-slot launch interval went with it; it duplicated the shared beat.

**318. Gotcha 300 caught the same hands twice in one patch.** Replacing
everything between two anchors takes what sits between them. The first slice ate
the `vramAnswered` and `vramWhy` declarations; the second ate
`setInterval(vramOwnTick, 1500)` - the heartbeat itself, which would have left
the report never updating at all. Both were caught by the gate rather than by
reading. Replace a named function, never a span between two names.

**314. A door that can answer with nothing will, and nobody will know.**
`api_slot_log` returned `{"report": None}` when its glob found no file, and the
client returned early without recording an answer - so "the panel said nothing"
and "the panel was never asked" produced the identical card: old figures, and an
"answered" clock climbing for ever. Every path out now carries a `why`, the
client records the answer before judging whether it was useful, and a request
that fails outright says so. Five rounds of this fault were spent proposing
causes; every one of them would have been visible in a single line had the door
been able to speak.

**315. There is one timing rule left, and it compares two clocks.** For 180
seconds after a launch press the door accepts only a log whose session header is
at or after the press - a PowerShell local timestamp against the panel's epoch
clock. Any skew between them rejects every log for those 180 seconds. It is now
the only remaining place where time decides anything, it names itself when it
fires, and the proper repair is to match on a launch identity written into the
header rather than on a timestamp at all.

**312. The log says when it is finished; stop inferring it.** Four rules were
tried for when the allocation report may stop polling - state name, sameness,
readiness, then nothing at all - and every one was an attempt to infer from
outside a fact the text states plainly. llama.cpp writes every buffer line
before its end-of-load marker: verified across twelve field logs, the closest by
24 lines, the failed launch included. So `final` is now read off the text, and
the poll stops on that and on nothing else. Model size, disk speed and how far
behind the log runs stop mattering, because none of them are consulted.

**313. Allocations only grow, so merge - never install.** A reply was replacing
the cached report wholesale, which made every poll a race: one reading taken
mid-write could undo a complete one. Within a launch the known set can only
grow; a reading with fewer rows is a short reading, not a change in the truth.
Replies are merged, sizes keep the larger value, flags latch on, and a new
launch is told apart by its session stamp - identity, not elapsed time. The
owner asked why any of this depended on timing. It should not have, and the
answer was in the log all along.

**310. Draftless speculation was drawn inside the drafter's block.** n-gram
speculation needs no draft model - that is what draftless means, and llama.cpp
mixes `ngram-mod` with `draft-mtp` precisely because they are independent. The
rows sat inside `if (drafting9)`, so they appeared only when a drafter was
already chosen: the one case where they are optional. Second time these rows
have been in the wrong place, the first being their position at patch83; a block
written by hand inherits nothing and must be checked against its own meaning.

**311. When three explanations have failed, ship the measurement that tells
them apart.** The report has now stuck three times. Each round produced a
plausible cause, a fix, and no change on the owner's machine - and every
screenshot looked the same whether the poll was dead, the requests were not
returning, or the panel was answering with a short report. A short report now
says when the panel last ANSWERED: frozen means the beat is not running,
climbing means it is and nothing comes back, small and steady means the panel is
replying and the fault is what it reads. Recorded on the reply, never on the
request, because a request that never returns must not look like one that was
never sent.

**308. Three rules, three frozen cards: delete the rule.** When to stop polling
the allocation report was decided by state name (patch92), by sameness
(patch88), and by readiness (patch93). Each was defensible and each left a card
half-read, because every one was a guess about when a log has finished being
written - which cannot be known from outside the writer. The tick now asks for
every slot on every beat and stops for nothing: three slots at 1.5s is two small
requests a second to a local process reading a 36 KB file, less than the page
already spends on its own status polls. A cheap thing done unconditionally needs
no rule, and a rule that must be right about timing will eventually be wrong.

**309. Do not aim an inline box by hand three times; let the row centre it.**
`font-size` (patch90), `transform` with `transform-origin` (patch91),
`vertical-align:middle` (patch92) - each was an attempt to place the fold arrow
against text metrics I could not see rendered. `vertical-align:middle` aligns to
half the x-height, which is not the optical centre of an uppercase heading with
letter-spacing. The heading is a flex row with `align-items:center` now; the
arrow carries only its rotation.

**306. "Ready" arrives in the same sweep as the last buffers.** The patch88
rule stopped asking once the log said `ready` and the figures had stopped
changing - but a report read a moment before the sweep finished can be BOTH ready
and short, so the rule settled on a half-filled report. Nothing is finished until
the rows the loader owes have actually arrived: weights, KV and compute, or an
exit.

**307. When everything measurable is right, add a measurement.** Three cards
froze half read. The parser read all three logs perfectly, the door served them
correctly under a fresh and a stale watermark, the interval was proved to
register, and the buttons updated from the same loop as the report - so the door
was being asked. Every explanation left was about something invisible: which file
the panel actually opened. The report now names its source and the age of that
file, and the card shows it while the report is short. Guessing again would have
been the fourth wrong theory in a row; the honest move was to make the panel say.

**303. A guessed state name broke three cards three different ways.** The
patch88 tick asked for a report only while `status.state === "serving"`. It reads
`"loading"` for the whole of a load and `"down"` after an exit - so a slot
loading with no report yet was never asked at all, one that caught a single tick
froze there, and one that DIED was never asked again, its failure never reaching
the card although the reader had parsed it correctly. The condition was the
defect. The tick asks unconditionally now and stops only when a report is
finished and unchanged: one cheap exchange for a quiet slot, and no string to be
wrong about.

**304. Two symptoms that look like three bugs can be one line.** Blank, frozen
and silent-on-failure read as three separate faults, and the temptation was to
fix each where it showed. Parsing all three logs first proved the reader was
right every time - which located the fault at delivery and made it one line.

**305. If you cannot measure it, do not build on it.** Twice I sized the fold
arrow with CSS against font metrics I could not see rendered, and twice it moved
the heading. An SVG is exactly as wide and as tall as it declares, sits on
`vertical-align:middle`, and rotates for state. When the medium is unmeasurable
from here, change the medium.

**301. To make a glyph bigger, scale it - do not enlarge its font.** Raising
the fold arrow to `font-size:30px` grew its line box and pushed the heading row
with it, and the `1.1em` width scaled along with the font so the gap widened
too: the arrow ended up high, left, and surrounded by space. `transform:scale()`
changes what is drawn and no metric at all, so the heading keeps the size and
baseline it has everywhere else.

**302. A new overlay wears the panel's clothes, not its own.** The DRY panel
arrived with `#12161d` and a `1px solid #3a4356` border - lighter than the card
behind it, with the brightest edge on the page. The panel's own surface is
`var(--bg)` and its language is glow, not outline. And the gate had already
written that rule down: nothing at rest may draw a zero-blur ring, which caught
the black ring I reached for first.

**298. A section built by hand misses everything the loop gains.** Speculative
Decoding and Draftless speculation were the only sections that would not fold,
and the owner read the cause straight off the symptom: they are written at the
end of the card rather than produced by the group loop, so they never received
the heading that folds. Twice now these two have missed something the other
sections had - patch83 was the position, this is the heading. They call
`pgrpHead` now, so what is added there reaches all of them.

**299. Per type AND per instance.** The fold was keyed by group alone, so
collapsing CPU on one server collapsed it on every server. Reasoned that "do I
care about CPU settings" is a fact about the setting - which is true of the
question and false of the use: the cards are read side by side, and a fold that
follows the group everywhere makes comparison impossible. Keyed by card and
group.

**300. Wrapping a block is not the same as returning around it.** Making the
drafting rows fold with an early `return h` would have taken the draftless block
with them, because that one is drawn afterwards in the same function. The guard
wraps its own rows. A slice moved during the swap also carried a closing brace
with it and put `drFile9` out of scope - the render check caught it, which is
what that check exists for.

**295. A chip that stands for a family should open the family.** The provider
DRY chip set `--dry-multiplier` and nothing else - the switch, with the three
dials that shape it unreachable from the panel. It now opens a small panel
carrying all four, each naming the flag it writes, blank meaning the field is
left out of the request.

**296. A panel with an OK button must also commit on the way out.** Filling in
four fields and losing them to a stray click elsewhere is worse than having no
button at all. OK, Enter and a click away all commit; only Escape discards. And
a field nobody touched is not written, so opening the panel and closing it
changes nothing.

**297. Fold by not drawing, not by hiding.** A collapsed group whose rows are
still in the document leaves the card exactly as long as it was; the point was
the length. The renderer returns before the rows when a group is shut.

**291. A live view needs a tick of its own, not a ride on someone else's.**
The allocation report was refreshed from two places and both were conditional:
`renderSlots` returns early when the page is not in view, a field has focus, or
a parameter is being adjusted - and its tick is the last line of that function -
while the launch interval was stopped by `slotBusyClear`, which fires when the
server answers its port. llama-server binds that port at 0.2s against a twelve
second load, so the report could be frozen on weights alone with every source of
refresh already gone. Patch87 then repainted that stale half faithfully for
ever, which is how a fix made the symptom worse. Its own heartbeat, as the TTS
status row got at patch61.

**292. Do not stop polling because nothing changed; stop when the source says
it is finished.** Buffers arrive in bursts with quiet between them, so sameness
alone is indistinguishable from a slow disk - that IS the frozen report. The log
says `ready` or `exited` when loading is over; only then does an unchanged report
mean there is nothing more coming.

**293. An empty measurement is not a measurement of zero.** `nvidia-smi` returns
no per-process memory for a GeForce card in WDDM mode - the list is empty whether
or not anything is running. The allocator log recorded "0 MiB in use by all
processes" beside a loaded 25 GB model, which reads as an empty card. It now says
the driver does not report it. A comparison against a number that was never taken
is worse than no comparison.

**294. I argued from the working half and was wrong.** Told the report vanished
while the buttons survived, I reasoned that the shared mechanism must be sound
and the difference must be a single missing call. The buttons survive because
`ctlApply` is called from more places, not because one call was enough. The owner
had suggested the report be made its own live UI two patches earlier; that was
the right answer and I talked past it twice.

**289. Two nodes, one pattern, one of them adopted a round-trip late.** The
allocation report flashed once at the end of a launch and vanished, while the
buttons on the same card survived every rebuild. Both are their own nodes
adopted from a placeholder; the difference was timing. `ctlApply` runs
synchronously after a render, so the buttons are home before the next rebuild.
The report was re-homed only when a POST came back, leaving its node orphaned
for a round-trip - and a rebuild arriving first discarded it. The last report is
already cached, so `vramApply(sid, null)` repaints it with no network at all;
that call now sits beside `ctlApply` where it always belonged.

**290. When a live node vanishes, ask who re-adopts it and WHEN.** The instinct
here was to rebuild the whole card as a patched live UI - a large change to a
mechanism that was already correct. The buttons proved the mechanism works: one
missing synchronous call was the entire fault. A symptom shared by two components
where only one misbehaves is pointing at the difference between them, not at the
design they share.

**286. The engine reports what it ASKED for; only the driver knows where it
landed.** Two servers on one card reported 30.9 + 1.76 GiB of a 31.8 GiB card,
and no amount of arguing about the parser could settle it, because llama.cpp
prints allocation requests, not residency. The allocator log now writes both:
the claimed total from the log, and `nvidia-smi`'s per-process resident figures
for the same card, with the difference stated. When a report and reality
disagree, add the measurement rather than the explanation.

**287. A repeated line with an IDENTICAL figure is one buffer, twice.** The
owner's log carries `CUDA0 compute buffer size = 104.50 MiB` at lines 382 and
395, and the reader summed both - Compute read 408 MiB where 303 MiB was
allocated. Patch85 tried to fix this by making a later figure REPLACE an earlier
one and broke a real session where three graphs each reserve on the same device.
The narrow rule is the right one: same figure, same device, same phase, count
once; a different figure is a different buffer.

**288. A gate check that reads one field is not a check on the row.** The
patch85 header check asserted the label and never looked at the class - so
`row("hdr", text, "vhdr")` passed the gate while the card printed the word
"vhdr" where the value belongs. The row signature is `(k, lab, val, cls, dest)`.
Check the shape, not the one field you were thinking about.

**283. Name the buffer that failed, do not infer it from bookkeeping.** The OOM
marker went to the next CORE row still awaiting a value, so a failed SWA cache -
not a core row - was reported as Compute. True about what the report was
expecting, false about the machine. The failing buffer, its size and its kind are
all in the log; read them.

**284. A failure need not mention memory to BE one.** A drafter loading into a
full card died with "invalid vector subscript", which reads like a corrupt file.
llama.cpp had already printed `using device CUDA0 ... - 0 MiB free` before it.
When that line is followed by a load failure, the panel says the card was full,
because nothing else will.

**285. I changed a measured case to fix a guessed one, and had to undo it.**
An owner reported VRAM climbing 100-300 MiB after launch. I inferred llama.cpp
was re-reserving its compute buffer and made a repeat on one device REPLACE the
earlier figure - which broke a real field session where main, drafter and vision
graphs each reserve on the same device and all are held. No log in hand shows a
re-reserve at all, and the climb happens after the lines this reader parses.
Reverted, with the reasoning left in the code. Measure before concluding applies
to explanations as much as to fixes.

**281. Markup that RESEMBLES the card is worse than markup that differs.** The
draftless rows were built with `<label>` and a plain `<span>` instead of the
card's `plab`/`pctl` shape, so they rendered white where every other label is
dim, with an inert `[--flag]` where every other one is a link, and with selects
wider than the numbers beside them. Close enough to look intentional, which is
what made it hard to see. Reach for the existing helper.

**282. A helper declared inside a block serves only that block.** `SPEC_GUIDE`
and the link builder lived inside the drafting section, so nothing else could
reach them - which is why the draftless rows got a hand-written imitation
instead. Both are module-level now and both halves of speculative decoding use
one of each. Same shape as gotcha 255: the same job in two places is done well
in one of them.

**278. A block written by hand cannot be positioned by a table.** The n-gram
rows had to sit under Speculative Decoding, and two attempts to place them by
group name failed - because that block is emitted directly at the end of the
card, not through `PARAM_GROUP_ORDER`. They are drawn there by hand too. The
group name they still carry orders their section in the LAUNCHER, which is a
different question with the same word for it.

**279. Anything the card writes, the parser must read.** `--spec-type` carries
the drafter's type and the n-gram type in one comma-separated value, and each
n-gram method spells its size options differently. Until `parse_launcher_params`
knew both, a hand-edited launcher silently lost the whole draftless block. The
round-trip check found it, which is what it is for.

**280. A fixture that flips every dropdown to on/off assumes every dropdown has
two options.** Ours no longer do. The round-trip check now picks a value the
list actually offers, which makes it a real test for every multi-option setting
rather than only for switches - and it states its three exclusions and why each
one cannot travel.

**276. Show the one fact that decides, as a verdict.** The chooser printed the
sha256 as a grey line. It is the only thing standing between the panel and
unpacking an executable it cannot identify, so it is green with a tick when the
publisher states one and red with a cross when they do not - and in the second
case the install button is not offered at all. The wording is careful: nothing
has been downloaded yet, so the tick means "the download will be checked against
this", not "a file has passed".

**277. Read the flag names; do not infer them.** `--spec-type` takes a
COMMA-SEPARATED list and mixes a draft-based type with a draftless one, which is
what lets n-gram speculation run beside an MTP head - two `--spec-type` flags
would be whichever the parser saw last, not a mixture. And the n-gram size
options are named per implementation upstream
(`--spec-ngram-simple-size-n`, `--spec-ngram-map-k4v-size-n`, ...): the generic
`--spec-ngram-size-n` I first wrote does not exist. One row on the card, the
right flag on the wire.

**274. A default is what you get when you have NOT said.** patch79 gave five
folders defaults under the panel's own directory and put them back on every
config read - correct for a new install, and for anyone upgrading it replaced
the paths they had chosen, the first time the panel loaded. The two behaviours
had been conflated because the four TTS folders, which the panel has genuinely
owned since patch56, are put back that way. Those were always the panel's; these
were the user's first. Before adding a default to an existing setting, ask what
it does to a config that already has a value.

**275. When a setting is lost, look for it in the things that used it.** A slot
names its model and its launcher by full path, so a folder replaced by patch79
can be read back off the slots. Only a folder every slot agrees on is used - one
guess from disagreeing evidence is worse than none - and the recovery only
reaches as far as the evidence does: `logDir` and `yamlOutDir` are referenced by
nothing else and cannot be recovered.

**271. A feature that moves the user's files is built plan-first.** The sort
reports every move - the file, where it would go, and which cards name it -
before anything is touched, and the button that runs it says files are moved
rather than copied. Two refusals matter as much as the moves: a header that does
not say what a model is leaves the file alone, because sorting on a guess moves
a file for a reason nobody can check afterwards; and a destination that is
occupied is skipped and reported rather than overwritten.

**272. Move the file and re-point the card in ONE operation.** A slot naming a
path that no longer exists is a server that will not start, and the panel is the
only thing holding both halves. The apply rewrites `model`, `vision` and `draft`
from the same plan that named them.

**273. `arch_label` is prose, not an identifier.** The first version of the
sorter built folder names from it and produced
`LLM/LlamafamilyalsoMistralNeMoYiandmostfinetunesofthem`. The architecture
itself - `gemma4`, `qwen3` - is the short name the file uses for itself, and is
what a folder should be called.

**268. A lock is only meaningful if something honours it.** Nine folders now
default under the panel's own directory and are put back if a config is edited
by hand - but `tts_fix_dirs` skips any the user has unlocked. Without that skip
the padlock would be a picture: the field would open, the edit would save, and
the next config read would undo it.

**269. A config READ must not make directories.** `tts_fix_dirs` created every
folder it fixed, which was tolerable for four TTS folders and became nine empty
directories for anyone who merely started the panel - and tripped the gate's
own no-trace rule. Creation belongs to whatever first writes into the folder,
and every one of those already did it.

**270. `\uD83D\uDD12` is not an emoji in a Python string.** Python parses it as
a lone surrogate while reading the page source, and a lone surrogate is half a
character - broken in the browser, and unencodable on the way there. Astral
characters go through `String.fromCodePoint`. The extractor caught this; the
browser would have shown a box.

**265. A failure the user cannot act on is half a failure.** An install that
could not download said so and stopped. The way round it is the address it was
fetching from - open it, take the file, point the panel at the folder - so both
failure rows now carry that address, click-to-copy, for the thing that actually
failed rather than one address for all three.

**266. `min-width` below the natural width equalises nothing.** The two status
headings were given `min-width:66px` to make them match; both render wider than
that, so the property never engaged and each stayed as wide as its own text.
92px clears the wider one. A width meant to equalise must exceed every item it
is equalising.

**267. Two settings pointing at one folder is one setting.** `ttsVoiceDir` and
`ttsSampleDir` both defaulted to `PandorumLLM\Sample Vault` and were shown as
"Local Voice Clips" and "Sample Vault" - two names and two fields for one
directory. Merged. The cost was eighteen gate failures, all of them fixtures
that had been written around the distinction; the distinction was the bug.

**262. HTTPS says who sent the bytes; only a digest says they are the right
bytes.** The panel downloads executables and unpacks them into a folder it then
runs from, and had no content check of any kind. Every archive is now hashed and
compared against the sha256 its publisher states - github per asset, hugging
face as the LFS oid - and a mismatch deletes the file rather than unpacking it.

**263. A redirect is an address you did not choose.** The starting URLs were
always built from constants in this file, but `urlopen` follows a redirect
anywhere, and an asset URL comes out of a remote answer. Fetches and redirects
are now both restricted to a named host list, over https only - a host on the
list reached over plain http is still an unauthenticated stranger, and
`github.com.evil.net` is not `github.com`.

**264. Install inside your own folder unless told otherwise.** `llama_exe`
fell back to a hard-coded `C:\llama.cpp-cuda` when nothing was configured, and
the installer refused to run at all. Unset now means `PandorumLLM\llama.cpp`,
which the installer creates and records; a path the user chose is untouched.

**260. Invalidate a cache at the moment you KNOW it is wrong.** The status
labels cache for a minute, which is what makes them cheap enough to draw on a
tick - and an install is the one event guaranteed to change what they report.
Nothing cleared them, so a finished update showed the old verdict until the
minute happened to lapse. The completion handler now stales both and asks again
at once. A cache without an invalidation point is a delay with extra steps.

**261. Green should mean one thing.** Both status labels used green letters for
a good verdict and coloured letters for every other state, so "good" had to be
read rather than seen. A good verdict now carries a green FILL and nothing else
does - which only works because it is the single state that gets it.

**258. Before building a second painter, check why the first one missed.** The
llama.cpp update bar moved while the words above it sat on "starting...". The
obvious reading is that the row needs its own live node, as the TTS status line
did at patch61. It did not: `higgsPaint` updates every element carrying
`data-higgs`, `higgsBarHtml` writes that attribute itself, and the step line
simply had not been tagged. One attribute. A second painter for the same job is
how the poorer implementation ends up carrying the bug (gotcha 255).

**259. A completion handler must redraw the page the row is actually on.** The
poll ended with `if (curTab === "tts") renderTts(true)`. llama.cpp updates from
Folder Setup, so its finished row never replaced the running one - the bar would
have sat there after a successful install. Whichever page holds the row is the
page to redraw.

**256. "Latest" is a marker, not a promise of binaries.** llama.cpp tags
version releases - v0.3.0 - whose only assets are a 7-byte `nightly-tag.txt` and
the source archives, while every Windows build lives in the bNNNNN releases
beneath. The updater asked for `releases/latest`, found no build, and reported
that truthfully - which was not the answer to the question anyone was asking.
Both engines walk the release list now until they find one that actually carries
the build for the chosen CUDA line.

**257. Record what you fetched, not what it was filed under.** A release tagged
v0.3.0 whose every binary says b10628 is a b10628 install. The version now comes
from the archive's own name, for both engines - with one trap handled, since
`cuda-13.3` in a filename is a CUDA line and the only thing in these names that
looks like a version without being one.

**254. "Is it installed" is a question for the disk.** The Install/Update button
read `llamaVersion`, which is only written when the PANEL installs llama.cpp -
so every hand-placed copy, which is most of them, read as nothing installed. The
state now carries `llamaHave` from `os.path.isfile`. Whenever a label describes
the world, check the world; the panel's record of what it did is a different
fact and answers a different question.

**255. The same job in two places will be done well in one of them.** audio.cpp
had a four-step version ladder since patch50 - subprocess, changelog, version
resource, shipped README. llama.cpp had one inline subprocess and three regexes,
the first of which matched the 0 that a git-less build prints. It has the ladder
now. When two callers ask the same question, the poorer one is where the bug
will be.

**252. A zero that came from a failed read is not a value.** `llama-server`
built without git information prints "version: 0"; the panel wrapped it as "b0"
and showed it as a build number. A parse that finds nothing must say so - the
dialog reads "installed, build unknown" now, and prefers the version the panel
itself recorded at install.

**253. A dialog and the page behind it must not say the same thing twice.**
The CUDA descriptions were printed on Folder Setup AND in the chooser, and a
"Check for update" button sat beside the installer asking the question the
chooser now answers as it opens. Both are gone from the page, along with the
function and the element that served the button - the third time this patch run
that removing a feature meant removing four things, not one.

**250. A `<button>` does not inherit font-family.** The page has been set in
Plus Jakarta Sans since it was written, and every button on it was in whatever
face the browser chose - because unlike almost every other element, form
controls do not inherit the font. One `font-family:inherit` on the button rule
fixed the whole panel, not the one dialog that made it noticeable.

**251. Two wide glows on short bold text make a box.** The chosen CUDA line was
lit with `0 0 6px` and `0 0 16px` of the same colour; at that spread the blur
from neighbouring glyphs merges and the result is a filled rectangle rather than
lit letters. One tight shadow follows the letterforms. If a glow looks like a
highlight, it is too wide, not too weak.

**248. When upstream changes shape, delete the old shape rather than teaching
it the new one.** audio.cpp 0.7 retired the balance/fast profile builds for one
archive per CUDA line - the scheme llama.cpp already used and patch48 already
had a picker for. The fix was not a second table but the SAME table and the SAME
picker, given two arguments so it can say which half of a release it wants.
`HIGGS_ENGINE_ASSETS` is gone, not extended: an asset table hunting for builds
that no longer exist is a table that can only fail.

**249. A failure that lists what it DID find is worth more than one that
retries.** The install said "release v0.7.0 carries no balanced build (needs win
+ cuda + balance). It has: ..." and named every asset. That message is what made
this a ten-minute diagnosis instead of a guess - the panel refused to unpack
something it could not identify, and showed its working.

**245. A removed feature must leave no half of itself running.** Adoption -
"use the files already on disk" - became pointless once the folders were the
panel's own, the model was picked from disk and a stale choice was cleared. It
was removed as a button, a client handler, a server door, and the `adoptable`
flag that fed it. Leaving any one of those would have been a path nothing could
reach and nothing would test.

**246. One class loses to a later rule with the same specificity.** The picker's
buttons carried `.ttsdl` and `.ttscx` with their own hover glows, and both
glowed white: `.stop:hover` sets its own shadow and appears later in the same
sheet, so a single class ties and loses. Written `.stop.ttsdl:hover` they win on
specificity. A style that "does nothing" is usually losing a tie, not missing.

**247. A delete-string that ends at `\r` orphans the `\n`.** Removing three
blocks this patch left two bare line feeds in a CRLF-only file, which the gate
caught immediately. Cut whole lines - `\r\n` and all - or the file ends up
mixed.

**243. Deleting a wall of prose deletes what was load-bearing in it.**
Replacing the install confirmation with the file list took the ENGINE
confirmation with it - "Update audio.cpp" would have downloaded without asking -
and took the origin disclosure and the "nothing about your setup is sent" line
as well. The gate's patch47 pins caught all of it. The engine has a short
question of its own again, and the list says where its files come from. When a
long text is replaced by a better UI, read the text for the facts it was
carrying before it goes.

**244. Clear a leftover only when nothing else can be true.** A model belonging
to another TTS is cleared when the chosen TTS has nothing on disk, because then
it is not a choice but a remnant - and it appeared beside the verdict as
"selected instead", reading like a decision the panel had made. But when a
correct model DOES exist, a wrong selection stands: the page argues in red and
the decision stays the user's.

**241. A second screen for one state will drift, and nobody will notice.**
`higgsInstallRow` had an `f.adoptable` arm that RETURNED before the two-line
report - a whole alternative UI written before patch50, with its own wording and
its own buttons. Choosing a TTS whose model was not downloaded landed in it, so
the labels vanished, the engine looked unrecognised, and the row claimed
"audio.cpp and a TTS model are already installed here" without having checked
either. Every improvement since patch50 had been made to the other shape.
Adoption is a BUTTON on the ordinary row now. One state, one shape.

**242. A function called from two places cannot borrow the caller's locals.**
Folding adoption in, I read `f` inside `ttsStatBody` where it is defined in
`higgsInstallRow`. The tick calls `ttsStatBody` directly, so that would have
thrown and taken the whole status row down with it. The node harness caught it;
the browser would have caught it louder.

**239. `\b` does not fire beside an underscore.** The quant parser read every
one of `higgs-audio-v3-tts-4b-q8_0.gguf`, `model-Q4_K_M.gguf` and the rest as
"no quant", because an underscore IS a word character and `\b` looks for a
change between word and non-word. These filenames are made of underscores. The
boundary that was meant is "not a letter or digit", written out as
`(?:^|[^a-z0-9])`.

**240. A progress word must be driven by a flag, not written into an element.**
Rescan wrote "scanning" into `#tts-mdl` and relied on a later repaint to replace
it - so a scan whose repaint did not land sat on that word for good, exactly as
the status row did before patch61. The flag is what the tick reads now, and a
scan that FAILS clears it too. Anything that says "working" needs something that
says when it stopped.

**237. Store per-thing settings under the thing, not as special cases.** Tag
boards, tag limits, the chosen model and both taggers all belong to ONE TTS.
Handling that with rules ("if the engine reads no tags, turn PTI off") loses the
user's setting the moment it fires. `TTS_PER_FAM` names the set once; choosing a
TTS saves the outgoing one and restores the incoming one, and a TTS that
performs nothing merely HOLDS the taggers off - the remembered values are never
written over, so coming back restores what the user chose rather than a default.

**238. Search the settings you were handed, not the ones on disk.** The
auto-pick first called `load_config()`, so a models folder changed in the same
save would have been searched as it used to be - and it created a default config
as a side effect, which the gate's no-trace rule caught. It takes the settings
being synced now.

**236. An empty frame is not an empty statement.** A tag group with nothing in
it was drawn as an empty bordered box, which reads as a control that failed to
load rather than a fact about the engine. It is a label alone now, with no box
around it. The same reasoning gave the populated boxes a dark glow instead of
the grey outline - that outline was the only hard border on the page, so it
looked like something from another screen.

**234. Answer the question that was asked, and name the rest.** With no model
on disk for the chosen pack, `tts_model_verdict` fell back to describing
whatever file was SELECTED - so the dropdown said Moss was "not downloaded"
while the line beneath it reported on a Fish file. Both statements were true and
together they read as a contradiction. The line answers about the PACK now
("not present - 7.5 GB to download") and carries the wrongly-selected file as a
separate, labelled fact. A second fact presented in the place of the first is
worse than no second fact.

**235. Never print an internal value where a person will read it.** The launch
dialog said "it reads as audiocpp" - the `general.architecture` string, which
EVERY audio.cpp package declares identically. True, and it told the reader
nothing at all. It says "That is a Fish Audio S2 Pro model, but Moss TTS v1.5
Local GGUF is selected". If a value is the same for every case, it cannot be the
thing you show to distinguish cases.

**231. A quantisation is what the QUANTISED tensors say.** The quant was read
as the dominant ggml type by element count, so two `q8_0` files in the field
reported F32 - small models whose full-precision norms and embeddings hold more
elements than their weights. Every quantised model keeps some tensors in float;
they are not what it IS. The pool is now the quantised types, floats answer only
when nothing is quantised, and the full type mix is recorded so the verdict can
be checked instead of believed.

**232. An id set in script is an id the page cannot find.** The wrong-model
dialog was built with `createElement` and `box.id = "..."`, and the gate's own
rule - no element looked up by an id nothing creates - failed it. The rule is
right: the markup is where ids live. Built with `insertAdjacentHTML` instead.

**233. Do not invent a setting name.** The recogniser guard was wired to
`ttsRefTranscribe` and `ttsRefMode`. Neither exists. The real one is
`ttsAsrMode`, and it has THREE values, of which only `on` loads a model - so
the guard would have nagged about a recogniser that was never going to be
loaded. A key that matches nothing fails silently and reads as working.

**228. "It accepts anything" is not the same as "it knows our words".** patch54
gave Fish and DramaBox the whole 43-word vocabulary because Fish documents
free-form cues and DramaBox reads prose. Both true, and neither means the sets
are equivalent: Fish publishes 51 emotion markers of its own, and exactly SEVEN
of our twenty-one appear in that list verbatim. Each engine now gets what its
own documentation shows, and where a published word means the same thing as
ours, ours is translated into it - thirteen of twenty-one. The other eight go as
our own word, because bitterness is not scorn and determination is not
confidence, and translating them would be inventing the agreement I had already
claimed once.

**229. A pack model always carries the key, so no key is a NO.** Every one of
the eight packs is an audio.cpp GGUF package and every audio.cpp package stamps
`audiocpp.model_spec.family`. Its absence is therefore a definite negative
rather than an unknown, which makes the identification ladder complete: family
key, then the declared architecture (an `ltx` quant says `ltx`), then a
safetensors folder's `config.json`, then - rarely - nothing. And a verdict never
blocks a launch: the server starts with whatever model the user selected, so a
hand-converted file that lost its key is called unrecognised and still runs.

**230. A line drawn into a pane dies with the pane.** The TTS status row was
rendered once and re-rendered only on success; a failed ask left "checking..."
on screen with nothing behind it, until the user navigated away and back. It is
its own node on a tick now, the way the allocation report is - it animates while
waiting, counts failed asks, says so after a few, and retries by itself.

**226. Match a DECLARED answer exactly; match a guess loosely.** The pack arch
hints are substring-matched, which is right for a bare `general.architecture`
where a family name can sit inside a longer one. Applied to
`audiocpp.model_spec.family` - the engine's own precise answer - it read
`moss_tts_nano` as the MOSS-Local pack and would have loaded the wrong model.
Found by running the owner's own 61-record file through the classifier, which is
worth more than any fixture: real data contains the cases nobody thinks to
invent.

**227. "Not asked yet" and "no" must not render the same.** The TTS page said
"audio.cpp: not installed" and "TTS model: not present" before its first status
request had returned, because an unset state fell through to the same branch as
a genuine absence. It says "checking..." now. A state that is merely unknown
must never borrow the words of a state that is known to be bad - the user acts
on the words.

**225. A parameter is not proven by existing - read the launcher it writes.**
patch51 added `--swa-full` as an on/off row and checked that the row existed,
that it had a group, and that its help text read correctly. All true, and every
launch on the owner's machine failed with `error: invalid argument: off`:
llama.cpp takes that flag with NO value, the panel keeps bare switches in an
explicit `bare` set, and the new row was never named there. The gate now
composes the launcher for EVERY on/off row and reads what came out - bare
switches absent when off, written alone when on, never beside a value. A row
that reaches llama-server must be checked the way llama-server reads it.

**223. Two answers to one question will disagree, and the user sees both.**
The TTS dropdown said "not downloaded" directly above an installation line
saying "present". Presence stat-ed each pack's own install path; the verdict
searched the whole folder - the p53 correction applied to one of the two callers
and not the other. Both ask `list_tts_models` now. Whenever a fact is shown
twice on one page, it must be computed once.

**224. A record belongs in the book whose questions it can answer.** Audio.cpp
models were being filed in `model-kinds.json` beside language models, where
"which family, which quantisation, why does it read that way" had nowhere to go.
They have `tts-model-kinds.json` now - same reader, same rules, same one-record-
per-line format, routed by what the file turned out to be. The rules stamp was
bumped so audio models already filed in the old book are re-read into the new
one rather than stranded.

**221. "I do not recognise this" and "this is something else" are different
answers, and only one of them is a shrug.** Files declaring `vibevoice`,
`voxcpm2` or `confucius4_tts` were painted plain, because `tts_model_family`
turned any family outside `TTS_PACKS` into `""` - the same value it returns for
a file with no header at all. But those files answered clearly, and the answer
was "not the one you selected". A declared family is now returned whatever it
is, so it paints red; plain is reserved for silence. Never collapse a definite
negative into a missing value.

**222. When a user has to open a file to help you, that file is a user
interface.** `model-kinds.json` was one 40,000-character line and carried no
reason for any verdict. It is now one sorted record per line, and every entry
says why the TTS pages read it as they did - "declares audio.cpp family
vibevoice", or "architecture audiocpp with no family key". A diagnostic nobody
can read is a diagnostic that does not exist.

**218. When every file answers the same, you are asking the wrong question.**
Three patches chased "present, but it calls itself audiocpp" - and the message
was accurate the whole time. EVERY audio.cpp GGUF writes
`general.architecture` = `audiocpp`; the family it really is lives in
`audiocpp.model_spec.family`, which LocalAI's own docs call the only reliable
signal for an audio.cpp model. Matching on the architecture made Higgs,
SenseVoice and Fish indistinguishable: nothing matched, nothing coloured, and a
model sitting in the folder could not be found. The tell was there in the
symptom - when a discriminator returns the same value for everything, it is not
discriminating.

**219. Fix the question in every place that asks it.** patch56 first corrected
only the SEARCH inside `tts_model_verdict`; the verdict computed immediately
after it still read the architecture, so a found Higgs file STILL reported
"audiocpp". One function now answers for both halves. A second way of asking
the same question is a second place to be wrong, and the gate pins its absence.

**220. A path the panel owns is not a setting.** Every "the panel cannot see my
models" fault traced back to a folder pointing somewhere the installer never
wrote. The four TTS folders - `audio.cpp`, `Models\TTS`, `TTSaudio`,
`Sample Vault` - are now created by the panel and rewritten on every config
read. They are still SHOWN, because a user should be able to see where their
files are, and locked, because it was never a choice.

**216. What the model can do is not what YOUR PATH to it can do.** patch54
gave Chatterbox `[laugh]` and `[cough]` on the strength of Resemble's own
README, which documents paralinguistic tags for the Turbo and Nano checkpoints.
But we reach Chatterbox through audio.cpp, and audio.cpp says of its own
integration that it "exposes voice cloning and voice conversion rather than a
separate tag-control interface" - so the bracket would have arrived as text and
been read aloud, the exact fault the whole tag table exists to prevent. Read the
docs of the thing you actually call, not only the docs of the thing it wraps.

**217. The engine's own default beats the model card's when you run through
that engine.** Fish's SDK publishes temperature 0.7; audio.cpp's `fish_audio`
integration documents 0.8 / top-k 30 / top-p 0.8 and is what actually reads the
value - and exposes a top-k the SDK page says does not exist. Sending nothing is
better than sending a number borrowed from a runtime we do not use. The same
reading changed Higgs: audio.cpp ships top-k **30**, not Boson's client 50,
because "the narrower default is less prone to premature EOC" - which is a fault
this panel has on short lines.

**214. Normalise once, emit per engine.** Four engines write a performed tag
four different ways - Higgs' control tokens, Fish's free-form brackets,
DramaBox's stage directions outside quotes, MOSS's pause marker - but all of
them need the SAME hard part first: aliases resolved, damaged tags repaired,
sentence-level tags hoisted, and the sweep that guarantees nothing tag-shaped
survives as words. So the pipeline produces one canonical token stream and a
single emitter writes it whichever way the pack declares. A ninth engine is a
table entry, not a branch through the tagger.

**215. A capability is not a preference, but it belongs in the same place.**
`tags_off` was already the one seam the prompts, the answer filters and the wire
gate all read. Feeding "what this engine cannot perform" into it made all three
engine-aware without any of them learning what an engine is - and the tagger
stops being asked for tags that would only be deleted (867 characters of prompt
instead of 1716 for an engine that performs none).

**212. "Is it there" is a question for the FOLDER, not for a path.** The TTS
model check looked at the one path an install would have written, so a
SenseVoice file sitting in the Higgs folder answered for Higgs - and answered
honestly, since that file declares the generic architecture `audiocpp`. The
message was right; reading that file at all was the fault. Detection now walks
the models folder and asks each `.gguf` what it is, through the same
`path|size|mtime` cache the LLM side uses. A selected file wins when it fits,
so a deliberate choice is never overridden.

**213. A hard-coded list of names needs a new entry for every thing you add,
and nobody remembers.** The ASR picker hid TTS models with the regex
`/higgs|vibevoice|indextts|fish-audio|voxcpm/i` - which knew nothing of the six
TTS added at patch49 and would have offered every one of them as a recogniser.
It reads what files declare now. The same rule that governs the LLM side: a
name is evidence only when nothing was declared, and can never override a
header that spoke.

**211. A contract checked per family will not cover the family added
tomorrow; check it per ENTRY.** The tag layer was proven for three dialects,
which said nothing about whether every pack names one of them or behaves once
it does. The gate now walks `TTS_PACKS` itself and asks each entry the same
question - is every tag either translated into something this engine performs,
or removed - so a ninth TTS is checked the day it lands rather than the day it
reads a tag aloud. The universal invariant is the useful one: a tag is never
handed over as text, because text is spoken.

**209. Report what a model IS; only offer what is genuinely a choice.** A
sliding window is trained into a model and llama.cpp only reads
`attention.sliding_window` for architectures that implement windowing - so an
override would either do nothing or impose an attention pattern the model was
never trained under. The window is therefore a label (`SWA Meta: 4096`) beside
the MTP chip, both read from the file. The one real choice is `--swa-full`,
which resizes the second KV cache llama.cpp builds for the windowed layers
WITHOUT changing what they attend to - off saves the memory, on buys back
prompt-cache reuse and context shifting.

**210. A colour that is always on is a colour nobody reads.** Host memory was
going to be red, but a pinned embedding table is how a healthy launch looks -
every Gemma launch would have shown red. Red is now reserved for actual
spillage (`offloaded X/Y` with X < Y, or weights in a plain CPU buffer), which
also surfaced a latent parser bug: `CPU_Mapped` matched neither host test, so
mmapped weights in system memory were counted as VRAM - hiding the exact fault
the report exists to show.

**207. A second definition wearing the same name silently replaces the first.**
patch50 added a `_ver_tuple()` for audio.cpp's `release-0.6.1` numbering without
noticing the panel already had `_ver_tuple()` for its OWN releases, which
understands hotfixes and patches. Python read the file top to bottom, the later
definition won, and the app's version ordering quietly broke - no error, no
warning. The gate's runtime check caught it in one run because it exercises the
behaviour rather than the text. Two different questions get two different names:
`_ver_tuple` for the panel, `_acpp_ver` for the engine.

**208. One badge cannot answer for two things.** "Installed" covered the engine
and the model at once, so a TTS whose gguf had never been downloaded still read
as installed. Each half now answers its own question - the engine by version
against a floor and the newest release, the model by what its own tensors say -
and each gets the button that fixes it. The model check reads the architecture
the file declares, so a renamed gguf cannot pass as another family.

**206. Markup is a dialect, not a capability flag.** Three are in play: Higgs
reads the panel's control tokens, MOSS reads one `[pause Ns]` marker of its
own, everything else reads neither - and a token a model does not know is
SPOKEN, not ignored. A boolean "does it take tags" collapsed the second case
into the third and would have cost MOSS-TTS-Local its pause marker the moment
it ran on audio.cpp instead of its own server. The dialect belongs to the
MODEL, so it lives in the pack and the runtime is irrelevant. Where a model has
tags of its own but no mapping from SkyrimNet's vocabulary exists - OmniVoice -
the honest dialect is "none": guessing puts unknown tokens in the text, and
those get read aloud.

**205. The two llama.cpp CUDA lines are a hardware fact, not a preference.**
CUDA 13 dropped pre-Turing outright - NVIDIA's 13.x notes say "Dropped support
for pre-Turing architectures (Maxwell, Volta, and Pascal)" - so a GTX 10-series
or P40 can only run the 12.4 build; and the 12.4 build is compiled against 12.4
while Blackwell needs 12.8+, so an RTX 50-series can only run the 13.3 one.
Neither can be dropped. Each line also needs TWO archives, because llama.cpp
publishes the CUDA runtime DLLs separately and a binary without its matching
cudart will not start. The updater unpacks over the folder rather than clearing
it: people keep launchers and scripts beside the binaries.

**204. A second model on the same engine is a table entry, not a branch.**
Fish Audio S2 Pro runs on the same audio.cpp as Higgs, so everything that
differs - repo, gguf path, folder, download size, disk requirement, licence,
reference samplers, and whether the model reads the panel's control tokens -
lives in one `TTS_PACKS` entry keyed on audio.cpp's own family string, which
the config already stored as `ttsAcppFamily`. The installer, the selector, the
confirm dialog and the tag layer all read the pack, so nothing branches on
"which TTS" twice. Note the tag rule is a real property of the model, not a
preference: Fish knows only `<|speaker:N|>` turn markers, and a control token
a model does not know is SPOKEN, not ignored.

**203. A persistent node is only as alive as the renderer that re-homes it.**
The p44/p45 rows survive card rebuilds by being swapped into a placeholder the
card emits - but the loop doing the swapping had lived in `renderSetup` since
p40, a page that never draws those cards. The allocation report survived only
because `renderSlots` happens to poll every slot, which re-homes it as a side
effect; the control row has no poll and simply vanished. Re-homing belongs in
the renderer that MAKES the placeholders, and adoption must never be gated on
`isConnected` - look for a live placeholder on every call and no-op when there
is none, so no caller can be too early or too late.

**202. An end anchor searched from zero can land before the start and duplicate
everything between.** A splice `t[:a] + new + t[b:]` with `b = t.index(marker)`
found a marker 6,000 lines BEFORE `a` - the span [b..a] then existed twice, and
the gate ran five hundred checks two times each. An end index must always be
searched from the start index: `t.index(marker, a)`. The count-asserted `rep()`
helper cannot save an index splice; only the anchored search can.

**201. A turn gate that answers to a browser event holds every turn hostage to
playback.** The patch34 queue released on the page's `tts-played` report -
correct, complete, and exactly why the field slowed: every Dialogue completion
inherited the previous thought's full playback plus its reporting. A pipeline
gate may wait on the pipeline's own clocks; the moment it waits on a viewer,
the viewer's pace becomes the pipeline's. Reverted in patch37.

**200. A guard on one rung guards one rung.** The patch40 rule - a player name
never attaches to another voicetype - lived inside the queue-pairing branch, and
the resolver has five ways to produce a name. The pin, the run-carry and the Meta
pick each answered before the guarded branch was reached, so three NPC lines were
named after the player with the guard standing right there. A rule about the
ANSWER must be asked wherever an answer is produced, which means one predicate
with one spelling, called at every rung - not a check written into whichever
branch happened to misbehave first. (v3.76 patch36)

**199. A fallback that always engages IS the primary path.** The voice-prime kick
declines a held speaker lock rather than wait - and its only caller called it from
inside that lock, so the non-reentrant acquire failed on every kick ever made.
Nothing crashed, nothing warned: the strip rung it falls back to worked perfectly,
which is why four field strips and zero primes was the entire signal. When a
callee declines under a lock, audit every call site's lock state; and when a
fallback's log line appears while the feature's own never does, the fallback is
not falling back - it is all there is. (v3.76 patch35)

**198. A blade proven sharp can still be mounted before the thing it cuts exists.**
Patch31's tag-strip was tested by feeding it tokenised text - every case exact -
and shipped ninety lines upstream of the translator that creates those tokens, so
in the field it cut air. Behavioural proofs of a function are not proofs of its
position; when order is the behaviour, pin the order (three source indexes,
ascending), and let the pin's prose avoid the function names it indexes against -
a comment naming the anchor moves the anchor (the glob docstring, twice now).
(v3.76 patch33)

**197. A pattern that can never match is invisible to a byte-differ.** The first
spelling of the tag shape ended `[]]` - an empty class, which matches nothing - so
the `[pause Ns]` branch was dead on arrival; every corpus line painted identically
because no corpus line carries a pause tag. The gate's own source-level ban (`[]]`
nowhere in the page) was the only referee. Acceptance against real output proves
what the output exercises; the source rules guard the rest. (v3.76 patch27)

**192. A corpus you assembled is a fixture; a corpus the panel assembled is
evidence.** patch23 changes only spliced lines, which no logged session produced -
all five terminal corpora showed zero difference, which reads exactly like a change
that does not work. Hand-building the spliced bodies produced zero too, because the
builder was wrong. Feeding the real `tts.log` to `ttsSpokenLines` and taking what IT
returned showed 29 of 30. The rule: when a corpus needs assembling, assemble it with
the function that assembles it in production, or the test is of the assembler.

**191. A timestamp is full of colons, and so is every rule that looks for one.**
`paintSpoken` found the speaker by `bare.indexOf(":")`, which lands inside
`[20:17:17.69]`, so `c > sp` was false and the entire head-tinting branch was skipped
whenever timestamps are SHOWN - no magenta on the name, and no fixed 2ch cell for the
mood icon, which is the only thing making names line up. The comment beside it records
fixing exactly this from the other direction ("matching on the LAST colon swallowed
the timestamp, which is full of them"), so the trap was known and the first-colon case
was still left open. `termStampsOff` ships with `tts` in it, so the default hid it.
That is gotcha 185 in a second place: a DISPLAY setting deciding something structural.
When a rule scans a line, scan from past the stamp - `TSTAMP_RX` exists for this and
takes the trailing space with it.

**190. "Shared" has three meanings, and only one of them can drift.** An element in
more than one terminal must have one source. An element in the terminals ONE painter
serves is *family*-scoped - shared among those, deliberately absent elsewhere, and
another terminal painting the same text differently is not a bug but a different
element. An element in one painter is *local*. `PAINT.num` reads like a panel-wide
entry and is family: it reaches Thinking, PTI/PME and Calibration because `markAt` is
called only from `paintThink`, while TTS paints durations gold and Proxy paints its
own, both correctly. Pushing coral into those two would unify two things that were
never one. Measured from five real terminal logs: 13 elements appear in more than one
terminal and only 3 were painted differently - so the drift was a tenth the size the
colour count suggested.

**189. The moment you are modelling may be one nobody thought to report.** The panel
predicted when a thought stops sounding, from the WAV's length, and held the next turn
against the guess - while `au.onended` fired in the page at the real moment and was
used to remove a CSS class. Two sessions had gone into tuning the prediction. Before
modelling anything, ask which side actually observes it: the browser plays the thought,
so the browser knows. The rule generalises - the panel cannot see the GAME's playback
and never will, but it had been treating its own audio as equally unknowable.

**188. A migration is only safe if you can see that nothing moved.** Stage 3 takes
four painters off text they re-derive meaning from, and every move is a chance to
silently change what a terminal shows. `render-check.js` cannot see that: it asks
whether something threw. `gate-tools/paint-diff.js` runs one painter over a corpus of
REAL log lines against two builds and diffs the markup byte for byte - and it was
proved by tampering, not by trusting a zero: changing one hex digit of `PAINT.think`
moved 21 of 721 lines and the differ named them. Build the differ before the first
migration, run every migration through it, and take the corpus from logs the panel
actually wrote rather than fixtures, because a line the painter never sees proves
nothing about the ones it does.

**187. A duration comes from a clock that cannot go backwards.** One `/api/state`
in the owner's log took **24,213,754ms** - six and three quarter hours, all of it
charged to one folder scan - because the machine slept mid-request and `time.time()`
counted the sleep. The scan was fine; the measurement was not, and it raised a
slow-request warning, which is the kind a reader learns to ignore. Elapsed time taken
inside a single call is `time.monotonic()`. The age of a STORED timestamp is not:
its other end is a wall-clock value written somewhere else, and a monotonic reading
compared against one is a number with no meaning. The two kinds look identical in a
grep, which is why the gate check is scoped per function - a global name check calls
every `t0` in the file the same variable, and the first version of it buried the two
real faults among false ones.

**186. Two actions on one element is one action, and not the one you wrote.**
The click dispatcher walks up from the target and takes the first `data-act` it
finds, so an element carrying one INSIDE another silently replaces it. patch16
wrapped the provider name in a `gotoProv` link; in the Proxy terminal that name is
already the payload hook, so the payload click became a jump to Live Network. It
degraded rather than broke: `MARK.provs` is empty until routing loads, so the first
clicks worked and later ones did not, which reads like a runtime fault rather than a
markup one. The glow can be unconditional; the action cannot. `nestedAct()` in the
harness now walks the markup as a stack and fails on any action inside another.

**185. A DISPLAY setting must never decide whether a LINK exists.** The heading hook
was located between the stamp segment and the port segment, and `termStampsOff`
ships with the Thinking terminal in its list - `stripStamps` removes the stamp before
any painter sees the line, so there was no left edge, the region could not be found,
and every heading fell through to a chip. The port is the only edge that has to be
there. Worth noting how nearly the diagnosis was thrown away: the first test of it
appeared to disprove the theory, because `paintTail` reads that setting internally
and both cases were stripped. A fixture that does not reproduce the condition is not
evidence against it.

**184. A table nothing ever fills makes the branch that reads it invisible, not
absent.** `MARK.provs` was declared `{}` and never assigned once, so `markAt`'s
provider branch never matched in its life and the `dashColor` call beneath it was
unreachable - yet both read as working code, and the three faults inside them could
not show. It had no `markEdge` call, so a provider named `Vision` would have matched
inside `Visionary`; it walked an object's keys, whose order is not length order, so
`NE` could have answered for `NE-Director`; and it prepended the emoji
unconditionally. Dead code does not stay correct while it waits - it stops being
checked. Where a table is read in one place and filled in another, pin the filling,
not just the reading.

The same patch nearly shipped a fourth fault of its own. That third one looked like
it needed a guard against doubling the emoji, so one was written and pinned - and the
negative control that removed the guard **passed the gate**. `markAt` is reached from
`paintThink` alone, and no writer it serves puts an emoji before a title, so the guard
could not fire; the check standing over it only read the source for its text, and the
harness assertion beside it tested a Proxy record, which never passes through `markAt`
and so could not have failed either. A guard that cannot fire is not protection, and a
check that only reads the source is not evidence that it is. When a negative control
passes, the control is not what is wrong.

**183. Before adding a store, look at what the existing one is nearly holding.**
The plan for the speech producer was a `who -> pid` note written at report time and
read at `say_line`. That is a second store keyed the same way as `REPLY_RING`, which
already holds every reply four deep for two minutes and already has a matcher that
places a spoken chunk inside one - and the two would have disagreed the first time a
TTS voicetype and a prompt name did. The ring only lacked one field. Adding it moved
the entry from a 2-tuple to a 3-tuple, which reached exactly one unpack site because
every other reader indexes `[0]` and `[1]`; that site was fixed rather than left to
raise. The matcher's own rule came free: exactly one record answers, or none does.

**182. A label that names the RECORD says nothing to the person reading it.**
The reference chip took its text from the kind of thing it pointed at, so every
reference to a call read `Dialogue` - which named neither the provider that made it,
nor the terminal the chip opened, nor the payload window that actually appeared. It
sat immediately after the provider name on a Thinking heading, in the column a label
occupies, and "Dialogue" is itself a SkyrimNet provider name, so it read as *this
call came from Dialogue*. The owner reported it as a wrong provider label and he was
reading it correctly. A hook should be the word already in the line that means the
thing - the provider on a thinking heading, `PTI` or `PME` on a tag one - and a chip
kept only for a reference that leaves the terminal, where no word can carry it.

**181. Three displays of one number are three chances to disagree.** How many
tokens the reasoning cost was shown on the proxy record, on the Thinking header and
in the payload modal, and each worked it out for itself. The modal preferred
llama.cpp's reported `reasoning_tokens` and measured the text only when it was
absent; the other two always measured, and printed a tilde even when the exact
figure was sitting one line above them in `met`. The two measurements then disagreed
with the modal's at every fourth length, because Python's `round` breaks a tie to
even and JavaScript's `Math.round` breaks it up. `think_tokens()` answers once and
returns `(n, exact)` - the pair, so no consumer has to judge for itself whether the
number can be trusted. A display that re-derives a value it was handed is a second
record of one thing.

**180. A cache that is not told a new fact goes on answering with silence.**
hotfix2 added `embd` to a remembered model verdict and patch3 added `embdOut`.
Neither bumped `_KIND_RULES`, which was the only thing that invalidated an entry, so
every file listed before hotfix2 kept a verdict with no width in it - 118 of the
owner's 128. `model_fit` then read 0 for the drafter's width and returned "" under
its own "an unknown is not a fault" rule, and the bad-match warning could not fire on
any file he had not re-quantised since. For three releases it read as a check that
was too narrow. It was a check that was never handed a number. The stamp covers a
verdict whose MEANING changed; a verdict that has gained a new FACT is a different
failure and now has its own mechanism - `_KIND_FIELDS` is named beside the stamp, an
entry that cannot answer for every field is dropped one by one, and the gate pins the
list against what `_model_facts_read` actually produces.

**179. An id that names a record must name the TERMINAL it lives in.** One
painter draws the Thinking, PTI/PME and TTS Calibration feeds and had no argument
saying which, so all three minted `ref-dlg-1236` for the same call - three elements,
one id, in one page. `getElementById` answers with whichever the markup happens to
put first, so the jump landed correctly by accident and the PTI/PME reference patch8
shipped could never be landed on at all. Nothing throws, nothing looks wrong, and one
markup reorder changes the behaviour. Scope the id by the pane as well as the record,
and build that name in ONE function both the painter and the jump call.

**178. A mark that is written and never read is a mark PRINTED ON THE SCREEN.**
patch6 introduced the typed reference, patch7 put a second one on every proxy record
that carried reasoning, patch8 added two more producers - and exactly one painter ever
learned to strip it. The Proxy terminal showed `⟨think:1236⟩` as literal text at
the end of every such line from patch7 to patch10, while the release notes described
the click-through as a feature. Every check those three patches ran asked whether the
mark was WRITTEN; the writer end was pinned six ways and the reader end not once.
A transport has two ends. A check on one proves nothing about the other, and the
half that is missing is the half nobody wrote a check for.

**176. A page cannot answer a question it was never given the facts for.** The picker
had `embd` and `embdOut` but not `spec`, so even a correct client-side rule could not
have distinguished an MTP drafter from a plain one. Check that a decision's inputs
actually reach the place making it before concluding the logic is at fault.

**173. A guard fired correctly on input that was wrong.** The rule that an NPC
voicetype must never wear the player's name is right, and it fired on
`player_thoughts` - which IS the player. The fault was never in the guard; it was that
`PLAYER_VOICES` listed one of the player's voicetypes and SkyrimNet sends two. When a
correct rule produces an absurd result, suspect what it was told before you touch what
it does.

**174. An error message that names the wrong remedy is worse than a vague one.** A
KV-cache exhaustion and a weights exhaustion are both "cudaMalloc failed", and the
generic advice - lower the GPU layers - is exactly wrong for the first, where the
weights already fit. Split a cause whenever the FIX differs, not whenever the words
differ.

**171. Both halves of an exchange can already exist and still not know each
other.** PTI and PME call `PROXY.report` and write their own record one line later -
the proxy had the id the whole time and simply never returned it. Adding the link was
one `return`, two arguments and a format string; the reason it had never been done was
that nobody had asked the question "can these two point at each other", not that it
was hard.

**172. A value bound inside a branch is not bound at the return.** `pid` was assigned
only when a request had been carried, so adding `return pid` at the end of `report`
raised `UnboundLocalError` on every call that had nothing to record - a path that runs
constantly. Initialise to None where the function begins, not where the happy path
does.

**169. Two marks on one line make their order load-bearing.** The proxy record
already ended in its payload id, matched by a pattern anchored at the end of the
line. Appending a second mark past it would have matched nothing and silently taken
the payload button away - the record would still have looked right. The reference is
written BEFORE the id, so stripping the id leaves the reference where its own matcher
looks. The gate proves it both ways: the shipped order works, and the reversed order
fails, so the ordering is tested rather than assumed.

**170. A reference is only followable if the thing it names has a name.** Pointing at
a record is half the work; landing on it is the other half. The Thinking terminal now
tags the block it painted with the id it carried, which is what makes "scroll here and
flash" possible at all - and the flash is not decoration. A terminal is a wall of
text, and dropping someone into the middle of one without saying where is not an
answer to "which call was it".

**167. A painter can see what a line looks like and never what it refers to.**
Four terminals each re-derived meaning from finished text, which is why the same term
meant different things in different windows - and why no terminal could point at
another's record at all. `MARK` unified the vocabulary the guesses were made with and
could not remove the guessing; only carrying the reference does that. It is written
by whoever knows what the thing is, stripped by whoever paints it, and the id is
stable across terminals so two windows holding it are the same record seen twice.

**168. Two ways to show one record will drift.** The reference chip and the proxy
terminal both open a dialogue payload. Copying the modal into the new path would have
left two versions of the same view to maintain, and one of them would have been the
one nobody updated - so the branch was extracted into `proxyPayloadOpen` first and
both callers share it. The gate section that pinned the old branch was retold against
the extracted function rather than deleted.

**165. Ownership held only in memory is ownership lost at every restart.**
`stop_tts_server` deliberately stops only a server the panel launched, and knew that
from a handle it kept in RAM. Restart the panel and its own server became
indistinguishable from a stranger's - still running, still on its port, and Terminate
walked past it. The stop path even had a branch for "a pid with no handle"; what was
missing was any way to LEARN the pid again. If a decision depends on "did we do
this", the answer has to outlive the process that made it.

**166. Adopting on partial evidence is worse than not adopting.** A pid alone proves
nothing - operating systems reuse them, and a busy machine reuses them quickly. The
note is only honoured when the pid is alive AND the executable behind it is the one
that was launched AND the port it claimed still answers. Where the executable cannot
be read, the panel declines rather than assumes: failing to stop your own server is
an inconvenience, and killing somebody else's is not.

**164. The last line of a crash is not the reason for it.** A process that dies
keeps printing for a moment, so `slot_launch_fault` quoting the final line reported
"resolve_fused_ops: resolving fused Gated Delta Net support:" while
`GGML_ASSERT(ggml_can_mul_mat(a, b))` - the whole diagnosis - sat one line above it,
unread, for as long as the feature has existed. Search the TAIL for a cause and fall
back to the last line, never the other way round.

**162. The field that decides a pairing is not always the field with the
obvious name.** A vision projector's `clip.vision.embedding_length` is the vision
tower's internal width - 1152 on a Gemma 4 projector - and comparing it to a text
model's `embedding_length` compares two unrelated numbers. What llama.cpp compares is
`clip.vision.projection_dim`, which its own error message spells out: *mismatch
between text model (n_embd = 2560) and mmproj (n_embd = 1536)*. Read the error the
engine actually raises and find the field it names, rather than the field whose name
matches.

**163. A compatibility rule needs to know what KIND of thing it is judging.** One
width test was applied to everything that attaches. It is right for an MTP or
assistant head, which hands a vector back, and wrong for a plain `draft-simple`
model, which needs a compatible vocabulary and no particular width at all - so the
check invented a fault for drafters llama.cpp would have accepted. A false warning is
not the safe side of this trade: it teaches people to ignore the colour, and then the
true warning goes unread too.

**159. The report existed; the useful half of it was discarded.** Browser errors
were captured all along - `error_4.log` held the ReferenceError from the second it
happened. What it held was `key is not defined @ :7129`: a line number in a page that
is generated fresh, naming nothing. The browser had `optFor > paramEditor >
renderSlots` on the error object and the handler dropped it. Before adding a
mechanism, check whether one exists and is throwing away the part that matters.

**160. A record nobody is told about is not a report.** That entry sat in the log for
three releases while the page looked simply empty. Nothing on screen suggested a log
worth opening, and the person seeing the fault had no reason to go looking. A fault
that reaches the user has to be visible where the user is.

**161. A map is a single point of failure for everything in it.** `state.slots.map(...)`
built every card in one expression, so one card's throw meant the assignment never
happened and the page rendered its heading and nothing else. Anything drawn per-item
from live data gets its own guard, or the worst item decides what the whole view
shows.

**157. A page that PARSES can be broken everywhere that matters.** `const bad =
(key !== "model")` sat inside `optFor(m, wantKey, cur2)`. There is no `key` in that
scope, so every server card threw while being drawn - and the Servers page showed its
heading, its slot count and an empty history table, which looks like a page that
rendered. `node --check` passed, every textual pin passed, and it shipped three times.
A static scope check does not catch it either: written function-scoped it sees a
`const key` in a sibling block and calls the name visible, which is what mine did
until it was tested against the real bug. The only thing that finds this is RUNNING
the render, so the gate now does - gate-tools/render-check.js loads the served page
in a sandbox and draws the cards, the parameter editor, the buttons and the thinking
painter against a test server.

**158. Two faults on one line, and fixing the loud one leaves the quiet one.** The
same statement also read `chosen`, a `const` declared 42 lines BELOW the function
that reads it - a temporal dead zone that throws exactly the same ReferenceError.
Renaming `key` to `wantKey` alone would have moved the failure, not removed it. When
a line is wrong, check every name on it, not the one the console happened to reach
first.

**155. Reading what a prompt IMPLIES when it also says the thing outright.**
The player's name was taken from `## <Name>'s Party` - true when present, and absent
whenever the player travels alone, which is most of the time. The same prompt names
the player five separate ways, one of them the words "the player character". The
panel spent a minute to seven counting how many characters had addressed him while
the answer sat in the text of the very first request. When a source is unreliable,
re-read what you are parsing before building machinery to compensate for it.

**156. A line placed in a branch that restores its own state does nothing twice
over.** `paintCast` was wired into the peer view, which saves `state`, swaps in the
remote panel's, renders, and restores in a `finally`. So it ran only when someone
opened the Host page, taught the painters a DIFFERENT machine's cast, and discarded
it - while the local panel, which refreshes constantly, never called it at all. The
gate proved the data was produced and survived redaction, which is exactly why the
fault looked like a server problem for a whole release.

**154. A control the plumbing already supports can still be missing a body.**
`--reasoning-budget-message` was in the flag help table and had its own Sampler Guide
page; every stage between the card and the launcher iterates SERVER_PARAMS and would
have carried it untouched. What did not exist was a way to TYPE it, because the
renderer had two named branches - toggle and dropdown - and an else that assumed a
number, so a string parameter would have drawn a spinner with a range popover around
a sentence. When adding a parameter of a kind that has never existed, check the
renderer's final else before assuming the pipeline is generic.

**152. Two files can be compatible on the check that is made and fatal on the one
that is not.** A gemma4 assistant drafter and a 26B-A4B model share a 262144-token
vocabulary, which is what llama.cpp compares, so the pair is accepted - and then dies
at graph build on `GGML_ASSERT(ggml_can_mul_mat)`, naming neither file. The number
that mattered was in the header all along: the head declares
`embedding_length_out = 5376` and the host is `embedding_length = 2816`. When a
downstream component asserts on a shape, find the field that shape comes from and
compare it upstream, where there is still a UI to say it in.

**153. A phase that only ends on success never ends on failure.** The Launch button
cleared itself when the slot reached `serving` - the one outcome that proves a launch
worked. Every other outcome left the flag set, and because it lives in the page, only
a reload cleared it. Write the ending condition for the failure path at the same time
as the success path, and put a clock under both: a state machine with one exit has
one bug waiting in it.

**150. A value learned once and never revisited is a guess with tenure.** The
player's name was write-once. One session read `You are speaking to someone` from two
different speakers, cleared the two-speaker bar, and called the player *someone* for
37 spoken lines - past a party heading and past every line the player actually said,
because the first answer was the only answer the code could hold. Anything inferred
needs to carry HOW it was learned, and a stronger source has to be able to replace a
weaker one. Ranking the sources costs a dict; not ranking them cost two hours of
wrong names.

**151. An ordering objection is not a content objection.** Pairing the player's voice
with a waiting dialogue request was correctly rejected - the player speaks BEFORE the
next request, so the queue holds the previous character. That reasoning is about
arrival order, and it was quietly taken to mean the pairing itself was unusable. It
is not: matching the spoken WORDS against a kept reply reaches the same conclusion
and cannot be fooled by order at all. When a rule is rejected, note which property
killed it, or the whole approach gets thrown away with it.

**149. "Only fill it if it is empty" is right for a preference and wrong for a
measurement.** The config merge replaces a setting on upgrade only when the stored
value is `""`. That protects a user's choices, which is what it is for - but six
emotions had been measured to break the cloned voice, and a board with any value at
all kept them enabled. The people it failed were precisely the ones who had used the
feature enough to customise it. Facts and preferences upgrade differently: a fact is
ADDED to what is there, behind a one-time flag, so nothing chosen is lost and the
user can still overrule it afterwards.

**147. Shipping something off is not the same as taking it away, and the
difference is the switch.** patch41 subtracted six emotions from the offer, which
removed them from the board along with the tag - no way to see them, no way to put
one back. DEVELOPMENT.md already had the law (never let an explanation disable an
input) and it still happened, because "block it" and "default it off" sound like the
same instruction. They are not: one is a decision the user can revisit, the other is
a decision made for them. Elation is the proof - blocked, unblocked, blocked, and now
off-by-default across four reversals. The entry most likely to be wrong is the one
that most needs its switch.

**148. A stage that writes the FINISHED form bypasses every gate downstream of it.**
The NPC mood pass emits a complete `<|emotion:x|>` token, and `tts_apply_tags` returns
a line that already carries one untouched - deliberately, so a line's own tags are not
double-processed. The consequence was invisible for a long time: the Allowed Tags
board was honoured for the player, whose tags arrive as `[EMOTION-X]` brackets and go
through the gate, and silently ignored for every NPC. When two producers feed one
consumer, check that both are actually passing through it, not just the one you were
looking at.

**144. A knob that exists and is empty is not a safeguard, it is a note to
self.** `TTS_EMOTION_BLOCK` was wired into three code paths and held `frozenset()`
for its whole life, with a comment explaining that the mechanism stays "if a tag is
ever found to be reliably destructive". A tag had been - the owner reported wrong
voices for months - and nobody ran the fifteen-second test that would have named it.
Twelve untested tokens, one short line each, thirteen minutes: four produce a
different speaker and a fifth destroys the level. The cost of not measuring was
paid one bad line at a time for far longer than the measurement took.

**145. Block the input, never try to hear the output.** The same sweep put through
zero-crossing rate and RMS puts the four wrong-speaker takes squarely inside the
spread of the correct ones - nothing separates them acoustically. That is the THIRD
time this project has confirmed it: the Pitch Guard (patch33) and the pitch-based
detector before it both measured feeling rather than identity. A wrong voice is not
detectable from the wave; it is preventable from the token.

**146. Rank hypotheses by what discriminates, not by what you can measure.** The
wrong-voiced line was the highest audio-to-reference ratio of forty-five takes -
a real, striking, quantifiable outlier, and completely irrelevant. The A/B killed
it in one run: the LONGEST take came back correct and a short one came back wrong.
The measurable correlate was a coincidence riding along with the actual cause, and
a diagnostic had already been shipped to collect more of it. Design the experiment
that separates the candidates before building anything that assumes one of them.

**141. A guard built from one table is blind to whatever that table excludes.**
The queue rule refused a name already bound to another voicetype by inverting
`_spk_voices` - sound, except the player branch of `speaker_for_voice_ex` returns
before `_spk_voices` is ever written. The player was therefore the single name the
guard could not see, and it is the name queued most often, because SkyrimNet writes
the player's dialogue too. Ask what a lookup table cannot contain, not only what it
does.

**142. A rule that stands down for "any" competitor stands down for competitors that
cannot compete.** The utterance run yields while a dialogue request is waiting,
because a shared sample belongs to whoever spoke most recently. But "waiting" counted
every queued name, including ones that demonstrably speak through a different sample
and so could never claim this one. Refusing them one at a time was not enough: the
run had already been silenced by their mere presence, and the line fell through to
printing its raw voicetype. Eligibility, not existence.

**143. A check can pass because a rule is unreachable rather than because it is
right.** Two speaker sections cleared `_spk_recent` and `_spk_voices` and left
`_spk_run` set, so the second ran inside the first's utterance run. Invisible for as
long as the run rule could not fire there - and the moment patch40 let it, the check
failed and looked like a regression in the panel. Reset every store a section
touches, or the gate is testing the leftovers.

**140. A pattern that caps a name is a silent data loss, not a validation.**
`SPEAKER_RX` bounded a character's name at 29 characters. A longer one did not
truncate and did not warn - it failed to match, `note_speaker` returned `""`, and four
stores guarded by `if who:` were skipped: the mood queue, `REPLY_FULL`, `REPLY_RING`
and `THOUGHT_FRESH`. One character lost her emotion tags, her thought audio, her
last-chunk matching and her name in the ledger, and the only visible trace was a
dashboard row reading `thought:` with no name in front of it. Bound a capture by what
it must not cross - here a comma, a full stop or a newline, which the character class
already did - not by a length guessed from the names that happened to be in front of
you. Corollary: when several regexes share a magic number, they share the bug; there
were five.

**139. A build that behaves is not the same as a build that is correct.** patch11 was
reported good and patch38 bad, with byte-identical thought code - `tts_thought_fire`,
`tts_thought_after_chunk` and `tts_chunk_trace` all diffed clean. The difference was
the TTS calibration store: warm (lead 1.02 s, headroom 1.46, 86 scored lines) meant no
chunk ever took 3.5 s and the latent fault never fired; near-cold (lead 0.32 s,
headroom 1.28, 17 scored lines) produced 6 runaway retries in 16 chunks and it fired
twice in one minute. Diff the code before believing a regression, and check the STATE
the two runs started from.
---

**135. An architecture string says what family a file belongs to - the tensors say
what it can DO.** llama.cpp types an MTP drafter by one tensor,
`blk.{block_count-1}.nextn.eh_proj.weight` (`common_speculative_types_from_gguf`),
because qwen35-generation heads declare the family architecture, not a drafter one.
The architecture-only rule sent `--spec-type draft-simple` beside a one-layer head
file and llama-server tried to load it as a 65-layer model, dying between `local
path` and the fit step with nothing in the console. Corollary: a tensor scan capped
at the first N names walks straight past the tensor that matters - it sits at the
END of the list. The same tensor inside a full model means the model drafts for
ITSELF (`--spec-type draft-mtp`, no draft file), which the card now states.


### The terminal record - design, not yet built

Every terminal currently receives a finished STRING and re-derives meaning from it.
The Proxy terminal knows a word is a speaker because it built the line; the Thinking
terminal receives raw model output and can only guess. `MARK` (patch1) unified the
vocabulary those guesses are made with - it did not remove the guessing.

What replaces it is a record emitted where the panel already KNOWS what a thing is:

```
{ src: "dialogue", id: 1236, port: 1238, text: "..." }
```

- **src** - what kind of thing this is: dialogue, thinking, tts, pti, pme, action.
- **id** - stable across terminals. The Proxy record for call 1236 and the Thinking
  content produced for it carry the SAME id.
- everything else the producer knows: port, speaker, provider, timings.

The transport already exists in miniature. A spoken line carries its audio id as
`⟪eid⟫` and a proxy record carries its payload id as `⟦pid⟧`, both appended by the
writer and stripped by the painter. That is the same idea applied to one field; the
record generalises it.

What it buys, and what makes it worth doing:

- **Navigation.** Clicking `Dialogue` in the Thinking terminal jumps to that call in
  the Proxy terminal and flashes it. Impossible today - nothing connects the two.
- **No terminal guesses.** A speaker is a speaker because the producer said so.
- **A new terminal inherits every rule** rather than growing its own tokenizer,
  which is how four of them drifted apart in the first place.

Order of work, so no stage leaves a half-wired system:

1. The record and its transport - one writer, one parser, one registry of what has
   been seen and where it sits.
2. One producer (the proxy's dialogue record) and one consumer (the Thinking
   terminal's reference), proving a jump end to end.
3. The remaining producers, then the painters migrated one at a time - each is a
   chance to silently change what a terminal SHOWS, so each needs its own
   before/after.

Stage 1 landed in patch6, the reciprocal jump in patch7, and PTI/PME in patch8: the
mark, the reader, the registry, and one producer (the thinking block) with one
consumer (its Dialogue chip) proving the jump.

**patch11 found the half of stage 1 that had never been built.** The Proxy terminal
was a *producer* of references and never a *reader* of them, so the mark patch7 put on
every record carrying reasoning was printed as text for four releases - see gotcha 178.
The same patch found that one painter serving three feeds named every landing place
identically - gotcha 179. Both are fixed, and both are now proved by a harness that
reads what a painter PRODUCED rather than what its source says:
`gate-tools/ref-check.js`.

Where stage 2 stands:

- **Action** - done in patch11. `action_line` takes the `pid` `PROXY.report` already
  had and the branch carries `⟨dlg:pid⟩`, so it opens the request that chose it.
- **Speech** - not started, and it is its own patch. A spoken line has no path to its
  dialogue call: `say_line` is in the TTS worker, nowhere near `PROXY.report`. The
  cheap route is a `who -> pid` note written at report time and read at say_line.
  It also puts a THIRD mark on that line, and the order is load-bearing again -
  `aidRx` is unanchored and `REF_RX` is anchored at the end, so `⟪ eid ⟫` must
  come first and the reference reader must run before the audio id is stripped.
- **The TTS terminal does not go through `paintThink`** - it has its own branch at
  `which === "tts"` - so it needs the reader added there explicitly, exactly as the
  dashboard arm did in patch11.

Stage 3, the painter migration, is unchanged and still the risky half. `paintSpoken`'s
`⟪ eid ⟫` replay handling is a second transport doing the same job; folding it in
would leave one mechanism, but it is user-visible and works, so it is a deliberate
piece of work rather than a rider on something else.

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

1. Bump `APP_PATCH` and `APP_RELEASE_TAG` (read the current values first — they
   have silently stuck before). `APP_VERSION` moves only at a version boundary.
2. `README.txt`: bump the version line, append a plain-language changelog paragraph.
3. `app.rc` (4 places) and `app.manifest` (1) — LF-only files.
4. Rebuild the exe (version boundaries only). The command lives in `BUILD.md` and
   only there - this file once carried its own copy, which omitted `-s` and
   `-std=c++17`: the exact fault BUILD.md records, fixed in one file and left
   standing in the other. One source.
5. Stage a clean copy, strip runtime folders, **run the gate**, zip folder-rooted, sha256.
6. **Hand over four files and nothing else:** the release zip, the repo zip, and one
   `-sha256.zip` beside each holding a single `.sha256` line in `sha256sum` format.
   `CHANGELOG.md` and `DEVELOPMENT.md` ship *inside* the repo zip - a loose copy
   beside it is a second copy that can disagree with the first.

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
- **Page-script scope:** a node sweep over the *served* script - after Python has eaten
  its escape layer - fails on a call to an undefined function or a constant read outside
  its scope, on a `RegExp` built from a string carrying a backslash, and on the `[]]`
  class-closer. The patch73 freeze family, all four forms.
- **Duplication:** the side-step rule must exist in exactly one place; no duplicate JS
  functions, no orphans, no duplicate element ids, no duplicate step lists.
- **Visual invariants:** nothing at rest draws a border or a hard ring; rest and hover have
  matching shadow layer counts; CSS braces balance.
- **Behaviour, in a real browser (jsdom):** menus open, effects stand aside, dropdowns work
  and announce once, no control sits blank, the folder warning appears *and clears*.
- **What a painter produced:** a reference-bearing line is put through the real
  `paintTail` and the markup that comes back is read - the chip is there, the mark is
  not, the payload button beside it still opens, and two feeds of one call are two
  elements. Textual pins cannot see any of this: a mark nothing reads still parses.
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

**The gate is run twice.** A check that passes only on a clean tree, or only on a dirty
one, is not a check - and the gate is the likeliest thing to have dirtied it. The junk
sweep runs at the top **and** at the bottom for that reason.

**A check must fail, not raise.** `_seg.index(x)` inside a `check()` argument throws
when `x` is absent, and the traceback takes the whole run down before the verdict is
printed - so a missing thing reads as a broken gate rather than as the failure it is.
Use `.find()` and compare, or put the lookup inside `seg()`, which reports properly.

**A check that verifies a function *exists* is not a check.** The redaction test passed for
several versions while filenames leaked, because it confirmed the masking function was
present rather than that it worked.

---

## 9. Testing

- `node --check` on the extracted `<script>` block catches JS syntax errors.
- **Extracting the page is a solved problem** - `gate.py` does it in a dozen lines
  around the `PAGE` literal: exec the literal, substitute `__TSKINDS__` and
  `__MOODS__`, split on `<script>`, write one file. Every harness takes that file as
  an argument. Do not write a second extractor.
- **`gate-tools/page-sandbox.js`** is the one window and element stub. Two harnesses
  use it: `render-check.js` proves the page loads and every card and terminal DRAWS,
  and `ref-check.js` reads what a painter actually produced. A harness that grows its
  own stub is how four painters drifted apart in the first place.
- **jsdom** loads the real page against the running panel. `fetchstub.js` must set
  `Content-Length` or POSTs arrive with empty bodies. It is **not** installed in a
  fresh container and the gate looks for it at `/tmp/node_modules/jsdom`: without it
  the `behaviour (jsdom)` section reports 22 SKIPs and the repo tree totals **3,154**
  ok; with it, **3,176**. Both are correct for their condition - a count that changes
  between sessions is that, not a change in the tree. It is not the render check,
  which uses bare node and has always run.
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
- **An unprimed voice switch strips first-chunk tags rather than holding** (owner,
  patch31): "losing on tag is a smaller issue than added latency". The primer runs
  in parallel off the Meta selection; the ladder never waits; in-flight counts as
  unprimed. Default ON. The Calibration-ledger mirror of prime/strip rows is
  deferred until the ledger renderer is next opened - not blind-patched.
- **A dashboard-painted fragment's bare number reads the pane's green value part**
  (patch27): one declaration per element per pane; the parts rule answers scalar
  readers with `.value`. No corpus line reaches it. Flip `SHOW.dashboard.num` to
  change.
- **Counted figures drop the tilde** (owner, patch25): "if it's been counted then it's a
  counted result, not an estimation". The Proxy record's `(~N)` keeps the sign only for
  estimates; shipped as its own content patch (patch29), never inside a byte-identity
  migration.
- Windows-only in practice: `llama-server.exe` is hardcoded in ~12 places, and the launchers
  are PowerShell with Windows-only VRAM reporting. The panel itself is portable.

---

## 12. Starting the next chat

> This is **PandorumLLM** — a single-file stdlib-Python browser control panel + embedded
> thinking-proxy for my SkyrimNet local llama.cpp fleet. Current version is **v3.80 Beta**.
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

**An `!important` declaration overrides an animation.** `button { box-shadow:none
!important }` silently killed the guide highlight on every button - the class was applied,
the keyframes ran, nothing appeared. Buttons here are glowing text, so effects aimed at them
must animate `text-shadow`; `#launchBtn` also carries `filter:none !important`, ruling out
the drop-shadow variant. **Check what the target's own rules suppress before choosing a
property to animate.**

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

### Engines

`ttsEngine` selects **moss** (default) or **audiocpp**. The **Gradio front is shared and
engine-neutral** - upload, HEAD caching, event ids, both SSE shapes, the path jail, the
allowlist, the body cap. Only the upstream call branches.

| | moss | audiocpp |
|---|---|---|
| route | `POST /tts` | `POST /v1/audio/speech` |
| body | `text`, `max_new_tokens`, `reference_wav_b64` | `model`, `input`, `voice_ref`, `reference_text` |
| reference | base64, per chunk | **a local file path** |
| chunking | `tts_chunks`, 4-way concurrent | the server's own `text_chunk_size` |
| joining | `tts_wav_join` | one request, one file |

The path passthrough works because the panel **starts** audio.cpp, so they are always on
one machine. audio.cpp also serializes requests per model, so client-side concurrency
would have bought nothing - hence `busy_timeout_ms`, or a slow line stalls every line after
it. `lazy_load` is deliberately off: the Start button waits on `/health`, and with lazy
loading that would answer before the model existed.

`tts_acpp_config()` writes `server.json` on every start - the panel owns that file. The GPU
is pinned with `CUDA_VISIBLE_DEVICES` and `"device": 0` rather than an index, because after
masking the chosen card **is** index 0, the same trap as `--main-gpu 0`.

**An error handler that throws destroys the evidence.** `load()`'s catch assigned through
an unguarded `$("sub")`; when that element did not exist yet the handler threw and the real
failure was replaced by `can't access property "textContent"`. Gated: no catch block may
assign through an unguarded `$()`.

**The served file and the kept file are different files.** `/gradio_api/file=` is jailed to
the wrapper's temp folder, so a generated line must be served from there; `tts_save_named()`
writes a second, readable copy into `ttsOutDir`. That folder belongs to the user and is
never pruned - the temp copy is.

**Do not invent a timing split.** The MOSS server reports generate and decode seconds;
audio.cpp's headers are undocumented, so `_num_or()` tries the plausible names and the
breakdown is only printed when one answers. Otherwise the wall time is shown as a single
honest figure.

**Use a regex LITERAL in the page, never `new RegExp("...")`.** The PAGE string eats one
backslash and the JS string literal eats another, so `"\\\\["` arrives as a character class
rather than an escaped bracket - the pattern compiles, matches the wrong thing, and looks
fine in the source. Caught by printing `rx.source` from inside jsdom. In the Python source
a literal needs `\\\\[` so the PAGE value is `\\[`; writing `\\[` also raises a
SyntaxWarning, which the gate now treats as a failure.

**Pairing the spoken line to its reply, measured not assumed.** A spoken line is logged
0.2-0.5s BEFORE its dialogue completion: SkyrimNet fires TTS on the final token, llama.cpp
writes its timing line afterwards. And a streamed reply yields SEVERAL spoken lines seconds
apart, so matching each on its own timestamp scatters them among the Meta and Vision calls
in between. Group consecutive lines (<=5s apart) into a burst and attach the burst where it
starts. Both facts came from real uploaded logs, and both were the opposite of my first
guess.

**Two tag vocabularies, no selector.** SkyrimNet writes `[angry]` / `[sigh]`; the custom
prompt writes `[EMOTION-ANGER]`. Lowercase words versus uppercase `FAMILY-VALUE` cannot
collide, so both are accepted at once and neither engine choice needs a setting. Two traps
found building it: the MOSS `[pause` matcher swallows a bare `[pause]`, so the alias pass
must run **first**; and deleting every unrecognised bracket eats dialogue like
`[see the note]` - only tags known to have no counterpart are removed.

**Three tag rules that are invisible until they are wrong** (measured by
`cleanestpoison/higgs3-tts-skyrimnet`, Apache-2.0): a bare `<|sfx:x|>` is **inert** without
onomatopoeia abutting it; emotion/style/speed/pitch are **sentence-level** and must sit at a
sentence start; and `<|prosody:long_pause|>` on a line **edge** runs the decoder to its cap
with no end-of-clip, which audio.cpp answers with an error and no audio - repeated hits can
take the engine down. All three now enforced in `tts_apply_tags`.

**Match a third party's release assets on words, not names.** `releases/latest`
means the version is never pinned, but the filename convention is not ours: exact
names broke the moment a build hash appeared, and a prefix would break on any
reordering. Required words, excluded words, preferred words with fallbacks - and the
profile is a preference, because any Windows CUDA build beats failing. A mismatch
must print the real asset list.

**The installer is the panel's largest privilege**, so it is fenced: host-only, one
explicit confirmation naming both sources and sizes, cancellable, resumable, free space
checked first, and everything narrated into the TTS terminal. `_hi_unzip` **refuses**
traversal and absolute-path entries rather than sanitising them - stripping `..` and then
extracting quietly flattens a hostile archive into the folder instead of rejecting it,
which is the trap the first version fell into.

**"You are speaking to X" names the LISTENER, not the player.** SkyrimNet generates
NPC-to-NPC dialogue, so when Serana addresses Brelyna that line holds Brelyna - and the
player's own voice took her name. `## <Name>'s Party's Active Quests` is the reliable
marker: the party is always the player's. It sits ~17 KB in, so it needs a wider scan than
the speaker does, but only until found once.

**The character's name is in the dialogue prompt, not the voice sample.** SkyrimNet's
system message opens `You are Serana, a Female Nord in Skyrim`, and the proxy already
carries that request - so `note_speaker()` reads the name from the first 4 KB, keeps only
the name, and never parses the body. `speaker_for_voice()` then learns voicetype -> name
and **consumes** the request it paired with: without that, a second voicetype asked inside
the same window inherited the same name, and since pairings are cached one wrong guess
would have stuck. Heuristic, and honest about it - it assumes one turn at a time.

**The upload filename is the voicetype**, not a temp name: `femalenord.wav`,
`malecommoner.wav`, `serana.wav`. That makes it a safe key for substituting a better
reference, which is what `ttsVoiceDir` does - SkyrimNet resamples every reference to
16 kHz first, including its own 44.1 kHz voice-samples, and Higgs runs at 24 kHz. Split
the name on **both** separators; `os.path.basename` ignores `\\` off Windows.

**SkyrimNet strips `<`, `|` and `>` from every line.** Higgs' native `<|family:value|>`
therefore CANNOT reach the panel - watching for it passes through nothing while looking
correct. The dialogue model is prompted to write `[EMOTION-FEAR]`, SkyrimNet's Chatterbox
allow-list lets it through, and `tts_apply_tags` translates. Chatterbox specifically:
it is the only backend with an audio-tag feature, at the cost of a 16000 Hz reference
against Zonos' 22050 Hz. Prior art: `cleanestpoison/higgs3-tts-skyrimnet`.

**Each engine gets only its own markers.** Higgs uses `<|family:name|>`; MOSS-TTS v1.5 uses
`[pause 3.2s]` and nothing else. `tts_apply_tags(text, keep, engine)` strips the other
engine's shapes in both directions, because an unknown marker is read aloud rather than
ignored. Pause length is clamped - a dialogue model asked for a pause will eventually ask
for a very long one.

**Higgs inline tags: pass through, never invent.** Higgs acts on `<|emotion:...|>`,
`<|style:...|>`, `<|prosody:...|>`, `<|sfx:...|>`. Only the dialogue model knows the mood,
so the panel's whole job is to decide whether those tags survive - `ttsTags`, audio.cpp
only, off by default. Two rules from Boson: an unrecognised tag is **read aloud**, so
anything not in the catalogue is stripped either way; and a tag must sit flush against its
word, so `tts_apply_tags` closes the space a language model will always leave.

**An anchor that is a PREFIX of a longer name matches the wrong thing.** Three times now:
`renderTts` found `renderTtsGuide`; `let svg` found the local inside `li()`;
`def tts_engine` found `def tts_engine_label`, which sits earlier, so the slice ran
backwards and silently tested nothing. Anchor on something that cannot be a prefix - add
the opening paren, the assignment, the closing quote.

**A setting that filters someone else\'s input must not filter your own.** The injected
player tag passed through `tts_apply_tags(..., keep=ttsTags=="on")` - and `ttsTags`
defaults to "off", so on a stock install the tag was computed, logged, and then thrown
away. Audio Tags governs tags SkyrimNet wrote; anything the panel adds itself sets
`keep_tags = True` regardless.

**Ask for the artefact, not a description of it.** The tagger returned a list of tags,
which the panel could only prepend - so a cough always landed before the first word. Asking
for the LINE BACK with tags placed in it puts the noise at the pause where it belongs. The
cost is that the model now holds the player's words, so `_clean_tagged()` compares them and
refuses any reply that changed them.

**Editing by slicing to a landmark deletes everything in between.** Replacing
`tts_player_tag` by slicing from its `def` to `def tts_apply_tags` destroyed eleven
functions and three module-level names sitting between them. `seg()` guards the GATE
against this; the edit scripts had no such guard. Replace ONE function - from its `def` to
the next `def` - and check the symbol list against the last packaged build afterwards.

**Four choices got one answer; two choices get two.** Higgs has four tag families, and
offering them as four groups made the model weigh four decisions per line and answer the
first. Collapsing sfx, style and prosody into a single "audio tag" - one emotion, one
audio - matches how a writer thinks about a line and is what the model can actually hold.
The vocabulary did not change, only the shape of the question.

**A prompt that says "fewer is better" gets fewer.** The tagger was offered 41 words in
four groups and reliably answered with exactly one feeling - because the instruction said
fewer was better and gave no example of a multi-tag answer. Listing a vocabulary is not
the same as showing what a good answer looks like: worked examples changed the behaviour,
the word list did not.

**A vocabulary list must be built from the table that judges it.** `TAG_OFFER` was typed
out by hand and eleven of its words were not accepted by `tts_apply_tags` at all - the
prompt offered them and the parser then rejected every answer using one. It is generated
from `TTS_ALIAS` and `TTS_TAGS` now, so the offer cannot outrun what the engine takes.

**Emotion moves the same numbers that identity does.** Two days of analysis concluded
Higgs was discarding the speaker, on the evidence that elated takes rose to 265-381 Hz and
lost their low-band energy. Both are true, and both are simply what an excited delivery
looks like - the listener confirmed every take was the right voice. Pitch and spectral tilt
cannot separate "this speaker, excited" from "a different speaker", and no threshold over
them ever will. Ask the person with ears before building the detector.

**A percentage is relative to something that may have changed.** The tree elbow sat at
`top:50%` from when the branch was one row tall. Making the branch full-height in patch20
silently moved it onto the row boundary of any wrapped line. When an element's height
becomes dynamic, every percentage inside it needs re-reading.

**Parse what models actually write, not only what you asked for.** PME was asked for
`1. [word] (NN%)`, was shown an example in that form, and answered `1. amusement (85%)`
anyway - and the strict parser dropped the lot, so PTI silently ran with no context. When
a format is requested, accept the near misses too; require only the part that
disambiguates, which here is the score.

**`enable_thinking` goes inside `chat_template_kwargs`.** At the top level of the request
it is silently ignored and the model reasons anyway. The proxy has always done this
correctly; `_chat()` did not, so both tagging features reasoned however their switch was
set - twenty seconds instead of a tenth of one, which then overlapped the next spoken line
and looked like a scheduling bug.

**Validate a measurement before acting on it.** The Pitch Guard shipped on six hand-picked
clips and looked fine; over eighteen it read four an octave out, and in the field it refused
good takes at 0.4x and 2.3x against the SAME reference - which cannot both be a speaker
swap. A guard that regenerates audio needs its measurement checked against a reference
implementation across everything available, not the examples that motivated it.

**A failure you can measure is a failure you can refuse.** Higgs drops the speaker
intermittently, so the take is simply asked for again - `wav_f0()` is pure stdlib
autocorrelation on a decimated signal, a few milliseconds a line, and the reference pitch
is cached by path+size+mtime. No DSP, no pitch shifting: rejection is honest where
correction would be a guess.

**When it fails, it lands on the SAME pitch whatever the reference was.** Eight bad takes
across an 83 Hz reference and a 200 Hz one all came back at 265-381 Hz. A tag that shifted
pitch would scale each reference differently; landing in one absolute band means the
speaker conditioning was discarded and the model used its own default voice. That is what
`TTS_EMOTION_BLOCK` exists for, and how to judge any future tag that misbehaves - measure
the absolute band, not the ratio.

**Wrong from frame one is a different fault from drifting.** A line came back at 264 Hz
median against a 77 Hz sample - and the pitch was already 270 Hz in the first 40 ms frame.
A model losing its conditioning would start right and wander; this started wrong, which
means the reference itself. Measure the pitch track before theorising about the model.

**A button belongs in the click chain.** The TTS page has two `d.act` chains - one on
`change` for the selects, one on `click` for the buttons. A button action added to the
change chain silently never fires.

**`stackSet()` replaces everything.** Launching the fleet calls it with the server's own
log, so anything the client had announced into that terminal is gone. Client-side lines
have to be re-announced after it.

**There are two terminals and they are fed differently.** The Proxy terminal tails
`<session>_dashboard.log` on disk; the fleet stack terminal behind the emblem is
client-side and fed by `stackAdd()` from JS. "Put it in the fleet terminal" meant the
second, and writing to the log file put it in the first.

**A setting is arranged before the thing it configures is running.** Gating the tagging
features on a *serving* server meant you could not configure them until after launching,
which is the wrong way round. The test is "set up and capable" - `scriptExists` plus a
model that is not vision or draft - and the list marks what is not running.

**"A model is loaded" is not "a model that can answer this".** A vision projector and an
MTP draft both load, both report serving, and neither will answer a chat request.
`model_kind()` already classified them for the model picker; slots now carry the result so
the TTS page can refuse to offer them. Anything that sends a prompt to a chosen server
should filter on kind, not on state alone.

**The spoken record is a better history than the prompt.** Mood evaluation first read the
dialogue request's `messages` - which meant stripping a 40 KB character sheet, stripping
`<internal_thought>`, and only working when the LLM went through the proxy. Every line that
reaches TTS is already one turn, already named. `TTS_TURNS` replaced the whole prompt path
and deleted the proxy hook with it.

**A hint about the player is a suggestion to the tagger, not information.** Mood
evaluation predicts what the player MIGHT feel before they have typed anything - so stated
as "the player is angry (60%)" it would pull a small model to `[angry]` regardless of the
line. It is therefore framed as what the exchange *might invite*, marked "NOT what the
player said", with NONE explicitly still available. If this feature ever tags badly, the
wording of that injection is the first thing to look at, not the model.

**The words a line CARRIES are not the words behind an icon.** `TTS_MOOD` is keyed on the
canonical name ("anger") for choosing an emoji; what a line may actually contain is a
`TTS_ALIAS` key or a `TTS_TAGS` name ("angry"). Building the player-tag vocabulary from
`TTS_MOOD` accepted `[whispering]` and rejected `[angry]`, because the two tables agree on
some words and not others. `TAG_OFFER` is now the single list, used to build the prompt AND
to validate the reply.

**A gate check must never be able to pass without testing anything.** Slicing with
`text[text.index(A):text.index(B)]` returns an EMPTY STRING when B precedes A - and
`"x" not in ""` is True, so every negative check on a broken slice passed silently. All
140 slices now go through `seg()`, which raises `GateBug` on backwards anchors, on a start
anchor that matches more than one place, on a missing anchor, and on a slice too short to
be real. `code_only()` strips comments and docstrings for checks that police code. The
gate has a section that tests these helpers against each failure mode. Converting them
exposed one check that had been passing on a slice spanning a third of the file.

**A gate check that greps source will match its own explanation.** Four times now: a check
for `new RegExp(` matched the comment saying not to use it; one for `(local clip)` matched
the note about removing it; one for `data-act="termStamps"` counted the `querySelectorAll`
that syncs those buttons; one for `log_error(` matched the docstring telling you to use
`log_warn`. Match what only a real occurrence has - the opening quote of a call, an element
rather than a substring - or strip comments first.

**Two views of one thing need one flag.** The TTS page and the header button each kept
their own - `ttsBusy` and `__ttsLaunching` - so each showed a state the other did not know
about. And moving TTS to its own tab left three live tests for `curDsub === "tts"` that can
never be true, so the page stopped repainting mid-action and its buttons stuck. **When a
pane moves, grep for what addressed it.**

**A label that describes the wrong behaviour is worse than no label.** The unpinned GPU
choice read "every visible card is offered" while `server.json` carried `"device": 0` - the
first card only. A single-GPU owner read it, concluded nothing needed setting, and was
right by accident. State what the code does, and check the two against each other.

**SkyrimNet does NOT send a reply\'s chunks in parallel.** Measured over a whole session:
the next chunk arrives ~0.11s after the previous chunk\'s audio was returned, every time.
So nothing queues, and a "waiting behind N" note - added in patch6 on the assumption that
it did - could never fire. Measure the arrival times before explaining a delay.

**Do not align emoji with `ch` arithmetic - use flexbox.** Terminal columns and CSS `ch`
are different units, and an emoji is not a whole number of either. Two attempts at
computing an indent failed for this reason before the layout was changed to two flex cells:
head at `flex:0 0 auto`, body at `flex:1 1 auto; min-width:0`. The browser measures what
the browser renders.

**`pre` does not wrap by default.** `pre.tail` had a `.wrap` variant that nothing ever
applied, so every terminal ran long lines off the right edge for as long as it has existed.

**U+FE0F takes no column but widens what precedes it.** Counting it as 1 put every line
whose icon carries a variation selector a column too far right.

**audio.cpp serves one request at a time.** `server.json` carries `"threads": 1`, and the
panel fires every chunk of a reply concurrently - so chunks 2..n queue AT THE SERVER. The
spoken line is logged on arrival and the speed on completion, so a queued chunk showed its
text instantly and its figure much later. That is a queue, not a stall, and it now says so.
Raising `threads` is untested and the model session may not be safe to share.

**Do not sniff markup by a fixed prefix length.** `html.slice(0, 20)` was checked for
`display:block`, which begins at character 26 of `<span style="display:block...`. It never
matched once, so a newline was appended after every spoken line and each got a blank row.
Mark the thing you mean - a class - and match it from position 0.

**portable / balance / fast are CPU baselines, not GPU ones.** The release ships the same
three names for the CPU-only builds, where CUDA architecture is meaningless - which
disproves the obvious reading. The GPU floor is fixed by the prebuilt CUDA runtime at CC
7.5 (RTX 20-series) regardless of profile. I labelled the panel with the wrong hardware
until a user pointed at the asset list.

**Two engine builds, one runtime.** The profile zips hold only the executables; the CUDA
DLLs are ~700 MB and shipped once. So each profile unpacks to `audio.cpp/<profile>/` while
the runtime stays flat at the root, and the server is spawned with the root on `PATH` -
duplicating the DLLs per profile would have been simpler and cost most of a gigabyte.
`find_acpp_exe` takes the profile and caches on `(root, profile)`; keying on root alone
would have returned the previous build after a switch.

**And "did we put it there" is not the same as "is it still intact".** The marker survived
antivirus gutting an install, so it vouched for a folder with its DLLs gone. For anything
cheap enough to fetch again, reinstalling beats any amount of cleverness about what is
already present - the engine is ~200 MB, a wrong one costs someone an afternoon.

**"Is the output already there" is not the same as "did we put it there".** The installer
skipped its download whenever any `audiocpp_server.exe` was in its folder - which adopted a
CPU-only build a user had unpacked by hand, installed nothing, and pointed the settings at
it. Write a marker naming the release, and only skip on a match.

**Higgs on audio.cpp has no path below q8_0.** Load-time `weight_type` refuses anything
smaller, and the only published GGUFs for the family are bf16 and q8_0 - the same ceiling.
The converter accepts `--type q4_k` generically, but that says nothing about whether this
family's runtime can execute it. A source-selector UI was built and then removed in
patch8/9 for exactly this reason: it worked, and bought nothing.

**audio.cpp quantises at LOAD, from safetensors.** `--session-option
higgs_audio_tts.weight_type=...` accepts native, f32, f16, bf16, q8_0 - and says so
verbatim when refused. The k-quants `audiocpp_gguf` accepts are NOT available this way,
which is likely why only bf16 and q8_0 are published for this family. Measured with two
CLI calls; guessing either way would have been wrong.

**A log that spans every run cannot be diagnosed by its tail.** `tts_diagnose` read the
last 8KB and matched a failure from a previous start, so a fixed problem kept being
reported. Record the file size when the server spawns and read only from there.

**Watching a port cannot detect a process that never opens one.** A TTS server dying
during model load left the panel on "waiting for it to answer" for ever. `tts_server_status`
polls the process as well, reaps it, and reads the server log for a reason - the diagnosis
helper already existed but only ran on a failed generate.

**The error log is for things that failed.** `log_error()` also calls `_record_issue()`,
which surfaces the message in the UI - so logging an observation that way tells the user
something is broken when nothing is. `log_warn()` writes to panel.log, tagged, and raises
nothing. Gated: no timing observation may go through `log_error`.

**A cache only helps if it is keyed on what the reader asks for.** `prime_slot_status`
probed slots in parallel using `slot["port"]`; `api_state` then read `parse_ps1_port(script)
or slot["port"]`. Any launcher that set its own port meant the primed entry was never hit,
and the read paid a full 350ms timeout - serially, per port. `state_probe_ports()` is now
the single answer to "which ports", used by both.

**A split pane shows a FEED but IS a pane.** `paintTail` is given the feed name, so a
per-terminal setting keyed on the pane never matched - the left pane showing the proxy asked
about "dashboard" while its button toggled "splitd". Pass the pane explicitly.

**The page must load nothing from a third party.** It pulled Plus Jakarta Sans from
`fonts.googleapis.com` on every open - a request carrying the operator's IP and referer
to Google, from a panel documented as LAN-only, which also needed the internet to look
right. Removed; the family stays declared so a local install is honoured and the stack
falls through to Segoe UI. Gated: every `<link>` in the head must be self-served.

**Exempting an endpoint from CFG_LOCK removes a guarantee it was relying on.** After
`NO_CFG_LOCK`, two presses of Launch TTS could each pass the checks and start a server.
Give each process-managing endpoint its OWN non-blocking lock: still no double-start,
still no waiting on the other one.

**A disabled button emits no pointer events.** The fleet button lost its hover arcs the
moment it was running, because running disabled it. Mark busy with a class and refuse the
click in the handler instead. And **an id-keyed CSS rule will not match a second button** -
every `#launchBtn` rule had to be widened before `#launchTtsBtn` looked like a launch
button at all, including the `position:relative` its arc overlay depends on.

**One slow request must not hold CFG_LOCK.** The POST dispatch serialized every mutating
endpoint, so a fleet launch blocked the TTS launch for its whole run. `NO_CFG_LOCK` names
the process-management endpoints, which take the lock themselves for the moment they need
it.

**pythonw.exe has no console, and that is not free.** `python.exe` started with
`CREATE_NO_WINDOW` still had one - hidden - and every console child inherited it. Switching
to `pythonw` in patch16 removed it entirely, so each `pwsh`/`nvidia-smi` call allocated a
fresh VISIBLE console. **Every `subprocess` call passes `**NOWIN`**; relying on an
inherited hidden console is what broke.

**The launcher must not look like a dropper.** v3.72 was flagged
`Trojan:Win32/Wacatac.B!ml` because the exe relaunched itself with `runas` and `SW_HIDE`
before starting Python hidden. That is the shape of a dropper, and it bought nothing - the
panel binds high ports and writes only in its own folder, and `app.manifest` has always
said `asInvoker`. Removed. **Anything added to launcher.cpp should be weighed against how
it reads to a classifier**, because the project is unsigned by choice (§9) and has nothing
else to lean on. `StartPandorumLLM.bat` exists so a block on the exe is never fatal.

**Gradio is a transport, not a contract.** Zonos and Chatterbox both reach the wrapper
through SkyrimNet's `GradioTTSInterface`, but their argument arrays differ - `fields[1]`
and `fields[3]` are right for Zonos and land on a flag for Chatterbox. `tts_pick_fields()`
keeps the proven positions when they hold and otherwise finds the reference as the only
dict with a `path`, and the text as the longest string that is not a language tag.

**Read the other process's log before reporting its failure.** A crashed audio.cpp closes
the socket; the panel sees `WinError 10054` and nothing else, while `tts-server.log` names
the cause one line earlier. `tts_diagnose()` reads the last 8 KB and translates known
signatures. The single-architecture CUDA build alone caused three unrecognisable failures
in one session.

**A cache in front of the upload means fixing the upload fixes nobody.** SkyrimNet HEADs
`/gradio_api/file=<path>` and skips the multipart entirely on a 200, so a reference stored
by an older build is never re-sent. `tts_ref_canonical()` therefore checks the 44-byte
header at use time and repairs in place. **When a fix lives at the write path, ask what
happens to everything already written.**

**Normalise the reference at the upload, not per engine.** SkyrimNet's samples are FFmpeg
output carrying extra RIFF chunks. moss-tts-server rejected them with 400; audio.cpp with
`failed to read WAV data chunk`. Same fault, two parsers, so `save_upload` normalises once
and every engine gets a canonical file. The CLI smoke tests passed only because those
references were soundfile-written and already clean - **test with a real SkyrimNet upload
before concluding a reference path works.**

**Model selection.** `ttsAcppModelsDir` is a root; `list_tts_models()` walks it three deep
and returns both shapes audio.cpp accepts - a `.gguf` **file**, or a **folder** with
`config.json` plus `model.safetensors[.index.json]`. Confirmed by test: `--model` pointed at
a `.gguf` gives the same `--inspect` output as its containing folder, so the panel names the
file and ambiguity disappears.

**A folder holding both loads the GGUF, silently.** `--inspect` on a folder containing bf16
safetensors *and* a q8 gguf reports `weights=1` pointing at the gguf, with no warning. Such
folders are marked `shadowed`, disabled in the dropdown, and refused at start. `--weight` is
a disambiguator *within* one resolved model, not a way to choose between models.

**A display cap must never feed the data path.** The thought row was trimmed to 400
characters for the terminal, and the same trimmed string went on to the thought-audio
pass - so the voice read "...the heat buil" and stopped mid-word. The trim looked like
formatting; it was data loss. Anything cut for display is cut at the last moment, on a
copy, and never stored back.

**An edit script is source code and earns the same escape-depth respect as the page.**
Two new flavors in one patch. A backslash at the end of a line *inside a triple-quoted
edit literal* is a line continuation inside the string: the two source lines splice into
one, the panel still parses, and every later anchor quoting them as two lines counts
zero. And a repair that replaced "from this rep to the print" swallowed the write-back
sitting between them - the reps ran in memory, the script printed success, the file
never changed. Anchors bound exactly what they mean to replace, and a repaired script
is re-read before it is re-run.

**A heuristic is only as safe as its test's ability to FAIL.** patch123 named the
player from a standalone think request, guarded by an agreement test: the speaker and
the think-as name must match. The test passed for the player - and when SkyrimNet began
sending NPC think tasks in the identical shape, it passed for those too, because it was
never able to fail for them. A safety test that cannot fail for the counterexample
class is a tautology. When upstream owns the input shape, prefer refusals over
inference: "a name already bound to a voicetype is never the player" cannot be walked
into by a prompt change (patch4).

**No config I/O on a per-line path - and the gate's no-trace check is the tripwire.**
The typed player name was first read with `load_config_cached()` inside the naming
lookup: one parse per spoken line, and on a tree with no config it CREATED one, which
the "gate leaves the tree as it found it" sweep caught. Same family as gotcha 37. A
per-line lookup reads a slot; the slot is refreshed where a cfg is already in hand -
the speak path and the settings save.

**An anomaly detector must know the system's designed motions.** A first cut alarmed
"voice X was A and is now B" - but a shared voicetype changing hands is patch116's
design working, and that alarm would have cried wolf on every commoner in the game. It
also wrote through TTSW.log from inside the naming lock's caller, which is how the gate
found it: the alarm path loaded a config the run never granted. The contradiction worth
shouting about is one NAME on two samples, and only that one ships.

**Timing is a guess; content is a fact.** Every naming failure in the field came from a
timing rule - a pairing window, a pin lifetime, a sticky cache - because timing encodes
"probably" and the queue does not care. The reply's own words are per-turn unique above
a couple of dozen characters, the proxy served them itself, and a chunk that arrives
ninety seconds late still matches the right reply. When a correlation can be made by
content, every timing rule behind it is demoted to tie-breaking.

**A fixture must be shaped like the field.** Two patch5 gate runs failed on their first
pass because the invented names - "GateYsolda5", a speaker called "A" - never matched
SPEAKER_RX, so the machinery under test was never reached and the run measured the
fixture, not the panel. A replay's inputs go through the same parsers the field's do;
if the parser would refuse them in production, the fixture is wrong, not the parser.

**Enforcement fails closed; detection only watches.** patch4 built the instrument - the
missing-sample alarm - and the line still went out on a dead path, leaving the engine
to improvise in whoever it conditioned on last, behind a perfect-looking log. An alarm
beside a fault that proceeds anyway documents the damage; the gate that refuses or
recovers PREVENTS it. Detection first is right for an unproven fault; once the fault
class is real, the alarm graduates to a gate.

**A corroborator is judged by its own ledger before it is trusted more.** The Meta
selector's pick was wired as a tie-breaker only, and one session's ledger showed it
lagging a full turn on every populated line - Mirabelle when Tolfdir spoke, Tolfdir
when Onmund spoke. It never fired, because ties never happened; had it been made
authoritative, that session carries three wrong names. The rank a signal deserves is
read off its recorded disagreements, not its description.

**Instruments exist to be surprised by.** The leading theory for the wrong-voice fault
was session carryover, and the whole detection stack was built around proving it. The
first field capture then showed a FIRST-of-session take - correct bytes on record, no
previous request in existence - coming back in the wrong voice: carryover cannot
explain a cold start, so the theory fell to its own instrument. The evidence was only
decisive because the input side was already hash-proven; had the reference not been
fingerprinted, "SkyrimNet sent the wrong sample" would have been unfalsifiable.

**Mirrored state is maintained where the state changes, not where it is convenient.**
The engine-conditioning record was first written only by the dialogue path, because
that is where the warm-up lived - but a voiced thought conditions the engine's one
session exactly the same way, so the record went stale on every thought and the change
detector missed real changes. State that mirrors another process is updated at every
site that changes the real thing, through one function, or it is fiction with a delay.

**A comment describing a fix is worse than no fix.** The TTS start's exit-detection
carried a comment saying a refused session option "is read back, remembered and the
start retried without it - once" - and the code below it returned an error. The retry
had never existed. Nobody rechecks a mechanism the source says is already there, so
the gap survived until 0.6 made it load-bearing; patch8 wrote the retry the comment
had been describing, and the gate now pins the CALL, not the prose.

**Anchors match file bytes, not source bytes.** A JS string inside the panel's Python
carries \\u2026 on disk - two backslashes - because the Python layer eats one. An edit
anchored on the SOURCE spelling (one backslash) counts zero and aborts. Same law as
gotcha 137, recurring: before anchoring into embedded-language regions, print the
line's repr and copy THAT. The count-assert turned the mistake into a no-op instead
of a corruption, which is the pattern working as designed.

**A new parameter named like an existing local is silently the wrong thing.** The
drafter-params argument was added as `p` to a function whose body already used `p` for
the path; the assignment shadowed the argument on line one and every read below it saw
a string where a dict was meant. The syntax was valid, the parse clean - only running
the flow showed it. Smoke-test the flow, not just the parse, and name new arguments
past the function's own vocabulary.

**When escaping depth compounds, stop escaping and compose.** Repairing a gate section
whose pins quote code that itself quotes JSON put four quoting layers in one string;
two surgery attempts miscounted backslashes, and the second corrupted the working gate.
The recovery that held: rebuild from the pristine tree and write the section wholesale
with the hard literals composed from chr() - a file that never contains the ambiguity
cannot miscount it. Same family as gotcha 137, one turn deeper.

**A segment rendered after a loop cannot use the loop's locals.** The card's new
section referenced `tight`, a per-iteration const of the parameter loop above it;
outside the loop it is a ReferenceError and the whole card stops rendering. What a
block can see is decided by where it RUNS, not by what it sits near in the file.

**A second model's inference does not belong in front of a line.** The transcript
fetch was written straight onto the speak path, one line below the timer opening -
so a first line for a new voice both waited on an ASR round trip and reported that
wait as synthesis. It was the timing-wall gotcha again, in a feature added long after
the rule was written. The fix was not only moving the call above the wall: work that
has to happen once per voice belongs BEHIND the line, in a background worker, with
the live path reading only what is already known.

**A shape that a person is expected to edit must say what its rows are.** The
transcript store was keyed by content hash with a bare string beside it - unreadable,
so unfixable, so in practice write-only. Writing the voicetype beside the text costs
nothing and turns the file into the thing that actually solves the hard case: proper
nouns no recogniser will ever get right. Any store meant to be corrected needs a
human-legible key beside its machine one.

**Strip what the tool adds, whatever the tool was told.** SenseVoice reports language,
emotion and events as inline markers, and the option that suppresses them is a
request field the panel might not always control. Since a marker inside a reference
transcript asserts the sample SAYS it, the strip is unconditional in the panel - the
setting only decides whether the engine bothers emitting them.

**Repair the input once, or handle the fault forever.** The broken voice clips were
worked around at every point that touched them - a runtime repair here, a refusal
there, a note in the log somewhere else - because each site only saw its own symptom.
Reading them once into a corrected copy and using that copy retires the whole class:
the engine reads it, a recogniser could read it, the hash is stable across sessions,
and no downstream code needs to know the fault ever existed. A fault that survives in
the data will be met again by every consumer of that data.

**Text and its own halo in one colour is a blur, not a glow.** The provider title set
color and text-shadow to the same variable, so the glyph had no edge against its own
light and the enclosed shapes filled in. Every glow on the page that reads correctly
keeps a light glyph against a coloured halo. A glow needs two values, and the one that
carries the identity belongs to the halo.

**A flag whose expression cannot be false is not a flag.** The adoption verdict was
first written as an or-chain ending in `or True` - always set, so every line for an
adopted voice would have reported news. Whether something is NEW is a question about
the state before the call, and it has to be asked before the call, not reconstructed
from its return value afterwards.

**A section that imitates a component drifts from it; a section that IS the component
cannot.** The Speculative Decoding block was first built as a bold full-width row with
hand-set spacing - close enough to pass a glance, and different in weight, case,
margins and divider from every real group heading two patches later. Rebuilding it ON
the .pgrp component made every future heading change apply to it for free. If a thing
should look like the others, make it out of the others.

**A variable margin cannot be centred against.** The divider sat off-centre because
the gap above it was whichever bottom margin the previous row happened to carry -
tight rows 4px, plain 15, stacked 30 - while the gap below was a constant. No single
margin on the heading fixes that; the cell BEFORE a heading has to surrender its
margin (`:has(+ .pgrp)`) so the heading owns the entire gap and can split it evenly.

**A dead control dressed as a live one is a small lie.** The new flag references reuse
the blue .pref style whose cursor promises a click that opens the Sampler Guide - but
these flags have no guide page. Keeping the look and the pointer cursor would have
taught the eye a click that does nothing; cursor:default keeps the vocabulary and
drops the false promise.

**An expectation that collapses with a setting condemns everything it measures.** The
first runaway detector based its expected duration on the auto-cal estimator, whose
estimate is 0.0 with calibration off - so the expectation fell to its floor and every
long take became a runaway, a retry storm shipped as a safety feature. The unit run
printed the symptom (`exp 0.8s` for a 65-character line) and passing tests hid it,
because no test asked the one question that mattered: is a LEGITIMATE long take left
alone? Derive an expectation from the artifact itself - here, the text - never from a
knob that can be off.

**Validate a detector by replaying every real take you have.** The threshold and the
short-side ratio were not argued into place: all 78 takes from the tag sweep were
replayed through the final detector, plus the field cases - the true runaway flagged,
the sigh-with-words-dropped flagged, one borderline short logged, zero false runaways.
A detector tuned on fixtures alone is an opinion; one replayed over the corpus is a
measurement.

**Escape depth compounds in every carrier, heredocs included.** A quoted heredoc
passes backslashes through literally, so the gate's WAV fixture wrote the TEXT
backslash-x-zero-zero instead of two zero bytes - four times the frames, every
duration wrong, every verdict inverted. Same law as gotchas 137 and the patch9
composition rule, third venue: when bytes matter, compose them (`bytes(2)`), never
spell them through a quoting layer.

**A default is every place that falls back, not just the settings table.** Turning
the transcript mode On required three `or "off"` fallbacks to become `or "on"` as
well as the DEF entry - a config object that never mentions the key reaches the
function fallbacks, and one left behind would have made "default on" true in the
table and false in behaviour. The gate now counts the fallbacks.

**The only file in the folder will be picked.** The recogniser field lists every
gguf in the models folder, and on a fresh install that list is exactly one entry:
the 4B TTS model - which the user duly picked, co-hosting it as an ASR family the
server must refuse. A picker whose wrong choice is the LIKELIEST choice needs the
mistake named inline, in red, at the moment it is made.

**Do not perform surgery on the surgeon.** A quote-collision broke the edit script,
and patching the edit script with a second script compounded the ambiguity until
the fix was less legible than the fault. The recovery that held, again: throw the
patcher away and rewrite it clean, with line-splices where giant string anchors
would carry quoting risk. Editing tools are cattle, not pets.

**Train and predict must share one function, or they will drift.** The first fit
trained on raw character counts while predicting from spoken ones, so nineteen
characters of `<|emotion:sadness|>` were priced as if the speaker read them aloud.
The second fit fixed that and still failed, because the predictor added an allowance
for a performed sigh that the residual never subtracted. Both were invisible in the
code and obvious the moment real takes were fed in - the spread refused to shrink.
The fix was structural rather than careful: one `tts_voice_extra()` used by the
predictor AND written into the record, so the two arithmetics are the same arithmetic.

**A learned model must be told what not to learn from.** One 27.5-second runaway in a
78-take corpus is enough to lift a fitted intercept until every later cap is inflated -
the failure teaching the system to expect failure. Rows whose residual is far past what
the fit already expects are dropped before fitting, and the exclusion is a gate check,
because it is the kind of thing that would silently stop working.

**Guessed constants are wrong in BOTH directions at once.** A flat floor plus a fixed
per-character rate was 17% over the observed maximum on a 13-character line and 88%
over on a 43-character one. It read as "conservative", and it was - conservatively
losing short lines to cap-hits while conservatively letting runaways burn twice as
long as needed. An average is not a safety margin; the spread has to be measured.

**A charset cannot tell an order from a moan.** The first non-lexical rule was a
set of breathy letters, and "Run. Now." is spelled entirely inside it - a two-word
command classified as a vocalisation. Shape had to join the letters: a performance
word is breathy letters WITH a stretch (a doubled letter), which keeps "Ahh" and
"Mmm" out of judgement and keeps orders in. The unit fixture that caught it stays.

**At exactly half, the majority test acquits the guilty.** `hit >= len/2` let a
two-word line whose transcript held only the sigh pass as spoken - one word of two
is half, and half was enough. The conviction this feature exists for was the case
the threshold could not reach. Strict majority (`hit*2 > len`) convicts it, and the
one-word guard still refuses to convict on a single word.

**An ellipsis was priced twice.** The dots stayed in the character count AND earned
a pause allowance, so every trailing "..." was quietly double-charged. One
decomposition function - spoken characters with dot-runs removed, counts for what
is performed - now feeds pricing, fitting, recording and exemption alike; the
previous two fixes of this family (raw-vs-spoken length, unsubtracted allowances)
were the same disease in different organs.

**Co-occurrence is not causation, and a device line settles it.** Two TTS failures sat
within twenty seconds of two LLM OOMs, so they were reported as VRAM contention between
the fleet and the speech server. The first line of the TTS server log says
`found 1 CUDA devices` - the pinning was working and the two workloads could not see
each other. The same session then produced a second wrong cause (a duplicated model in
the ASR slot) that a single screenshot disproved. Both guesses were reachable only
because the logs could not answer the question directly. The lesson is not "guess
better", it is that a diagnosis attempted on absent evidence should be a request for
evidence instead.

**A residual bucket will fill up with the thing you most needed to see.** "panel" was
everything in prep that was not the tag injector or the mood pass, and it quietly
contained inline thought synthesis - 2.6 seconds on one line, 10 milliseconds on the
next, reported identically. Any timing report with an unlabelled remainder is a report
that will eventually mislead. Name the steps; let the remainder be the small one.

**We were not filtering the server's output - it simply had nothing to say.** The
instinct on finding an uninformative log is to look for what is discarding lines. Here
stdout and stderr went straight to the file and audio.cpp is just quiet by default,
with `--log` documented one line deep in the README. Check what the tool CAN say before
auditing your own handling of what it did say.

**Fix the ruler before you change what it measures.** Six patches of TTS work were
judged against a `server:` figure that summed every failed attempt into one synthesis.
On the session that prompted the complaint, 38% of all reported server time was takes
that were thrown away, and the line that read 43 tps had actually run at 75. Every
conclusion drawn from that number - including "TTS got slower" - was drawn from a
measurement of the ladder rather than of the engine. When a metric and a memory
disagree by 2-3x, suspect the metric first.

**An intercept extrapolated from a narrow window is not a measurement.** A fixed
per-request cost of 499ms was derived by fitting six points spanning 77-99 tokens and
extending the line back to zero. The slope was reasonably constrained; the intercept was
barely constrained at all, and it was then attributed to reference encoding on no
evidence beyond plausibility. Reported as a fact, it nearly cost a voice-quality setting
change. State the window a fit came from, and do not extrapolate a per-unit model past
the range that produced it.

**Do not perform surgery on the surgeon - the gate is no exception.** An interrupted
build left three copies of the same new gate section in the working file. Unpicking them
by hand would have meant editing a file whose state was already unknown; recopying the
gate from the clean staged tree and inserting once took one command and left nothing to
verify. The same rule that applies to a broken edit script applies to a broken edit.

**A stateful engine needs a lock, and this one advertised its state in its own docs.**
audio.cpp says the Higgs integration "keeps the reference prompt state in the model
session". The panel sent concurrent requests to it for months. The wrong-voice reports
chased pitch, emotion tags, sample cross-wiring and identity resolution for two days
across several patches - and the identity ledger was right every time, because the panel
always sent the correct file. Nobody asked whether two correct files could be in the
engine at once. When a component documents that it holds state, serialise it before
investigating anything downstream of it.

**A retry that escalates must know what it is escalating.** The cap ladder was written
for a model that failed to stop, where a bigger budget genuinely helps. Applied to an
allocation refusal it asked the card for a larger buffer than the one just declined,
three times, each worse than the last. A retry policy belongs to a failure MODE, not to
the act of failing.

**An error message that names a cause is a claim, and it can be wrong for years.**
"not enough VRAM - try a shorter reference voice, a smaller model, or another card"
fired on a card with 19 GB free. It sent the owner hunting for memory that was already
there, and it sent this session's diagnosis down two dead ends before the probe added in
patch17 printed the actual figures beside it. Prefer messages that report what was
measured over messages that explain what it means.

**A clamp that always binds is not a clamp, it is the value.** `AUTOCAL_HEAD_MAX = 1.60`
read as a safety rail; in practice the fit asked for more than 1.60 in every session on
record, so the learned margin was decorative. The tell was in the log the whole time -
the same "headroom 1.60" line beside a p95 that kept moving. A learned parameter that
never changes is not converged, it is pinned, and a bound that is never slack should be
audited as a hard-coded value.

**A censored observation entered at the current headroom closes the loop on itself.**
A line hitting an estimate-decided cap enters the fit at cap/est, which by construction
IS the headroom in force. Under a binding clamp that means every failure votes for
exactly the value that caused it - 452 of 1124 scored lines at precisely 1.60 - and the
statistic that would justify raising the margin is computed from data the margin
truncated. Feedback that manufactures its own evidence cannot be diagnosed from inside
the loop; it needs the bound removed and the record cleared.

**Escape depth, fourth venue: JS inside a Python string.** A dialogue body written with
backslash-n produced real newlines and an unterminated JS literal, because the page
script is a Python string literal and the escape is consumed one layer down. The gate's
node --check caught it. Same law as the heredoc and the chr() composition rules:
compose the character (`String.fromCharCode(10)`), never spell it through a quoting
layer.

**The mitigation was the cause.** Every countermeasure built for the repeated-token
failure - runaway detection, the token model, take verification, the cap ladder - treated
it as something the engine did TO us. It was something the panel asked for: the retry
stepped the samplers colder on each attempt, and the third attempt at temperature 0.32
with min_p 0.08 is near-greedy decoding, which is the textbook way to make an
autoregressive model repeat itself forever. The measurement that should have ended this
days earlier was already in hand: a bit-identical 40 ms loop means the distribution has
collapsed to one token, and a collapsed distribution has a cause. Reading "the sampler
did this" off that observation needed no new instrumentation, only the question "what
narrows a distribution?" - which points straight at the code that narrows it on purpose.

**Check the reference implementation's defaults before tuning around them.** Boson's own
example is temperature 0.8, top_k 50, nothing else. The panel was sending top_p, min_p
and repetition_penalty - none of which appear in the reference setup, one of which
(repetition_penalty) audio.cpp documents as accepted-but-unconsumed for this family. Four
of the five sampler controls existed to solve a problem the fifth was creating.

**A default that only applies to fresh installs is not a default.** The reference
samplers are written by the installer over whatever the fields already hold, because the
users who most need them are the ones who have been tuning to escape the fault. A
reinstall exists to undo a tuning session, so it has to overwrite.

**A prompt that presupposes output gets output.** "Return it word for word with tags
added" reads as an instruction to add tags, whatever an "optional" clause says two lines
later - and a model given a flat sentence invented a singing style to satisfy it. The
family of this gotcha is already on record ("fewer is better" gets fewer); its general
form is that the FRAME outweighs the qualifier. State the null action as the default,
and let the examples show it by majority.

**Fail-open still costs the timeout.** The tagger failed open correctly when its server
was down - and paid two seconds per player line to do it, attributed to nothing. A
fallback that is reached by timing out is a stall wearing a safety label. Check
liveness with the probe that already exists before paying for the call, and say once
what is being skipped, or the feature silently becomes the cost.

**Three hard-coded copies of one key set, and the newest member reached only two of
them.** top_k was added to TTS_SAMP_KEYS in patch21 and did not appear on the page,
because the chip renderer carried its own ["temp","top_p","min_p","rep"] and the sampler
board carried a third copy in _samp_key. The gate check pinned the map, which passed. A
constant that enumerates a set must be the ONLY enumeration of it: the page is now handed
the keys (sampKeys) and the board iterates TTS_SAMP_KEYS. When adding to a set, grep for
its members as literals, not for the constant's name.

**Removing a feature means removing what asserted it.** Deleting autocal_sampler_arith
broke eight gate sites, two of them seg() boundaries that merely NAMED the function.
Boundaries chosen as "the next def" silently couple unrelated checks to a function's
existence; the retells that followed were mechanical, but they were only findable because
the gate crashed loudly rather than skipping.

**A hover effect should light text, not soften it.** .plpay:hover stacked a 7px
text-shadow, a 16px text-shadow and a drop-shadow FILTER. The filter operates on the
already-composited glyphs, so it blurs pixels the shadows blurred - the result reads as
out of focus rather than lit. One shadow, tight radius. Filters and text-shadows do not
add, they compound.

**A display that enumerates its own categories cannot show a new one.** The meter bar
listed seven band names in meterSegs. The spend ledger had been measuring five more since
patch17, and every one of them was drawn as nothing - not wrong, not zero, simply absent,
with `panel` silently absorbing the time. This is the third instance this week of the
same shape (the sampler chips, the sampler board, this bar): a set enumerated in two
places diverges the moment one grows. The rule that came out of it: a view renders the
KEYS OF THE DATA, and only the ordering is written by hand.

**Instrumentation has to be attached where the work happens, not where it is convenient.**
SenseVoice was wrapped in a `transcript` step that also covered a dictionary read, and
its learner path ran on a background thread that no per-line ledger watched. Timing the
one function every caller goes through - and doing it in a `finally` - put it on the
board from all three call sites at once.

**A clamp in someone else's log is a bug in our output.** llama.cpp printed
"requested draft size exceeds the trained block size 16 -- clamping to 15" on every
launch, and it was read for a year as an engine quirk. It was the panel sending
block_size as the depth. The rule is in llama.cpp's source in one line - a DFlash block
is [id_last, mask x (block_size-1)], so slot zero is not draftable - and reading it took
minutes. When a tool corrects our input every single time, the tool is not being
awkward; the input is wrong.

**The same limit has two answers, so a constant would have been wrong.** DSpark drafters
sampling from an anchor fill the whole block; plain DFlash cannot. Hard-coding
block_size-1 would have quietly under-drafted every DSpark model. The ceiling had to be
derived from the drafter's own metadata and its tensor scan, which is also why it is
computed and not typed in.

**An abort leaves the file untouched, which is the point - and the trap.** The first p25
edit aborted on a bad anchor, taking a metadata-key addition with it. The ceiling
function was re-added under a working anchor; the key was not, so the function read a
key that gguf_meta never captured. Nothing failed - the default simply always applied.
After an aborted multi-edit, re-verify EVERY change it carried, not the one being
retried.

**A parser that expects a sentence nobody writes is a contract with one signatory.**
slot_vram_report has always keyed "exited" off the exact string "Server process exited
before it became ready". llama.cpp never emits it; the shipped launcher template never
emitted it either. The flag could therefore only ever be false for generated launchers,
and no test noticed because the check merely read a dict key that was correctly present
and correctly False. When a reader depends on a producer, gate BOTH ends together - the
producing template and the consuming parser - or the pair drifts silently.

**A retry loop with no exit check destroys its own evidence.** The template ended with
`& "<SELF_PATH>"`, an unconditional self-invocation. A server failing at load restarted
forever, and every restart replaced the console holding the error. The symptom reported
downstream was "sometimes it does not launch" - which is what an unreadable, repeating
failure looks like from outside. A supervisor that cannot tell success from failure is
not a supervisor.

**Untestable code earns extra scepticism, not extra confidence.** There is no PowerShell
in this build environment, so the launcher body cannot be executed here. That is a reason
to keep the file MINIMAL and to push logic into the panel where it can be run - not a
reason to port hundreds of lines of someone else's parser into it on faith.

**Read the upstream option table before writing an option set.** The first draft of the
Load mode values was guessed - mmap/read/mlock/dio - and llama.cpp actually accepts
auto/none/mmap/mlock/mmap+mlock/dio. A select offering a value the parser rejects is a
setting that fails only on the user's machine, at launch, with a message they did not
ask for. The values, their order and the default all came out of arg.cpp in the end, and
took one fetch.

**Renaming a reference target silently orphans everything pointing at it.** The guide
page "Threads / mmap / fit" was renamed once mmap moved out of it, and two card settings
still named the old title - their [--flag] chips would have opened nothing, with no
error anywhere. The gate now walks every card setting's guide reference and fails if the
page does not exist, which is a check that should have existed from the day the
cross-reference feature shipped.

**Deprecated upstream is not automatically wrong here.** --chat-template-kwargs is
deprecated in llama.cpp and is deliberately still written, because some models honour
only the template kwarg; the panel writes it AND --reasoning for that reason, and the
code says so at the constant. An audit that removes every deprecated flag on sight would
have broken those models. Check why a thing is there before removing it for being old.

**A guard that skips work must leave a debt, not a hole.** stateRepull declined to
repaint while focus sat inside the TTS pane - reasonable, typing must not be clobbered -
but the decline was FINAL: the fresh state was fetched and then never shown, because the
drawn-signature matched itself forever after. Focus sits on the Install button the user
just pressed, so the one moment the page most needed to repaint was the one moment the
guard always fired. The fix is one line: a deferred repaint clears the drawn signature,
so whoever renders next renders fresh. (gotcha: defer means OWED.)

**One confirm gate for two verbs, and the harmless verb paid for the harmful one.** The
install endpoint required confirm for everything, then branched on action. Dismiss - hide
a banner - bounced with "not confirmed" on every click, and the client, which never read
the reply, repainted the same banner. Check destructive-ness per action, and answer the
harmless ones first.

**"Default" also means what an install writes.** DEF_SETTINGS said 10 seconds; the
installer wrote 4 over it (patch18); the owner read the page and saw 4 and called it the
default, correctly. Every writer of a value is part of its default, and they must agree
- the gate now pins both writers to 10.

**A remainder band hides whatever is not measured, and the owner will find it before
the bar does.** "panel" is defined as prep minus everything ledgered, so the warm-up -
which wrapped only its HTTP call in a spend_step while the surrounding work fell through
- showed up as several hundred unexplained milliseconds. The answer came from the timing
CSV in three lines of arithmetic: split every line by whether the speaker changed, and
the medians were 33 ms against 749 ms. Group the measurement by the thing you suspect;
do not stare at totals.

**A fix outlives the fault it was built for.** The warm-up existed to absorb session
carryover between voices. The sampler root cause removed the carryover, and the warm-up
kept charging for it - a fix nobody re-examined because it was off by default in the
shipped config and quietly on in the owner's.

**Slicing to "the next def" is the rule I already had, and I broke it.** Deleting
tts_warmup_needed by cutting from its header to the following def swallowed _WIRE_SEEN,
a module constant that happened to sit between them. Nothing failed at import; the gate's
orphan scan caught it. Delete a function by its own span, then diff the symbol list.

**Fix the class the element actually uses.** patch28 cleared filter:blur from .uuid; the
address inputs are .hb. The change passed its gate because the gate pinned the rule I
edited, not the rendered field. When a fix is about something VISIBLE, pin the element
that renders, not the stylesheet line.

**"Bare switch" is only safe when the engine-side default is off.** --fit was grouped
with --no-cont-batching as a flag that is present or absent. --no-cont-batching defaults
off upstream, so absent means off and the shorthand holds; --fit defaults ON, so absent
means ON and the card lied. This is the third instance of the same law in this project
(enable_thinking, cfg-or-load_config, now --fit): ABSENT IS NOT OFF. Before treating a
dial as present-or-absent, read the upstream default.

**One folder for two audiences is a bug waiting for a fleet.** Server cards and the
Launcher Creator shared templates\, so a file whose first line reads "TEMPLATE_NAME:
Single GPU (no GPU pinning) - for 1 PC / 1 GPU" was listed for a three-card server. It
even documented its own unsuitability, in the dropdown, and was still selectable. The
folder is the contract: server-templates\ files pin a card, templates\ files may do
anything. Separate the folders, not the naming.

**Two independent faults produced one symptom, and either alone would have been
survivable.** No pin meant every GPU was visible; fit-on meant llama.cpp used them all.
With the pin but no fit fix, one card would have been used and over-committed; with the
fit fix but no pin, layers would have stayed put on whichever card llama.cpp chose
first. The owner reported one behaviour, and it took both fixes. When a symptom has a
clean single-cause story, check whether it needs two.

**A placeholder is a contract with a specific substituting function - check its list.**
patch30 shipped a template pinning with <GPU_UUID>. render_launcher_lines implements
<GPU_ID>, <MODEL_PATH>, <MMPROJ_PATH>, <DRAFT_PATH>, <TITLE>, <SELF_PATH>, <SELF_NAME>,
<PORT> and <LLAMA_EXE> - and nothing else. An unknown placeholder does not error; it
survives into the output as literal text, which CUDA then ignores, which looks exactly
like no pin at all. The gate had checked that the TEMPLATE contained a pin line, which
it did. Pin the RENDERED result, not the source.

**And the template was never rendered anyway.** Server cards do not call
render_launcher_lines - that is the Launcher Creator's path. A card stores template text
as `custom` and write_slot_launcher writes it verbatim, with ps1_set_flag editing only
entries inside $llamaArgs. Anything outside the array - an env line, a Write-Host - is
untouchable by that mechanism. A value that MUST be right cannot live where only an
optional editor can reach it: ps1_force_gpu_pin now rewrites the bytes on the way to
disk.

**Two fixes for one symptom, and the first one worked.** patch30's --fit fix did land -
"fitting params to device memory" is absent from all three of the owner's new logs - but
the models still spread, because the pin fix did not. A partially-fixed symptom looks
identical to an unfixed one from outside, so say which half is proven: the fit half was
provable from the log the owner already had.

**A warning nobody reads is not a fix, and the log proved the code right and the ship
wrong.** patch31's enforcement worked exactly as written: ten lines of "server N has no
GPU chosen - its launcher pins nothing". Every one was correct, none helped. When the
correct behaviour on missing input is known and safe - assign the least-loaded card -
DO it and log the decision; reserve warnings for cases with no safe default. The fleet
still spread for one more patch because the code chose to be right instead of useful.

**Store the value in the shape its consumer matches.** The model dropdown compares
option.path === settings value, full path against full path. The installer began storing
basename - correct-looking, wrong shape - and the symptom was "(none selected)" beside a
successfully installed model. The adopt route stored the full path all along, which is
why only fresh installs showed it.

**A button holds focus until something takes it away.** The patch28 fix deferred a
focus-blocked repaint until "the next render" - which never came, because clicking
Install focuses a button and buttons do not blur themselves. Deferral needs a due date;
the due date yields to INPUT/TEXTAREA/SELECT so typing is never clobbered.

**The owner's conjecture was right and was dismissed twice. Investigate it instead.**
He said --load-mode was causing models to spread; the reply was that load-mode cannot
change which devices are VISIBLE. True, and irrelevant - he was describing ALLOCATION,
not visibility, and mmap governs allocation. He then ran the experiment: auto spreads,
--no-mmap fixes it, dio fixes it. Three data points beat a mechanism argument. When
someone who is watching the machine says "it is X", the cost of testing X is minutes and
the cost of dismissing it was three patches.

**A wrong comment became a disabled control.** The OFF map in the card renderer both
explains why a setting is irrelevant AND sets `disabled` on it. A patch27 comment claimed
load mode "only affects load time, not generation", so every fully-offloaded card greyed
out the one control that fixed the fleet. Anything that disables input on the strength of
an assumption needs that assumption to be measured, not reasoned.

**Focus deferral must not cover events the user just triggered.** Two patches tried to
make a focus-deferred repaint eventually fire (clear the signature, then a timer). Both
missed that ADOPTION never runs the install poller, so the SSE repaint was the only route
and it was the deferred one. An install completing is not "someone might be typing" - it
gets its own event and repaints unconditionally.

**When the documentation and the default disagree, the default is the bug.** The Sampler
Guide has said for many patches that --cache-ram and --ctx-checkpoints must both be set
to zero for a GPU-only cache, "and the zeros must be explicit". The panel shipped
--cache-ram 0 and --ctx-checkpoints 8. Nobody compared the guide against the table. A
guide that states a correct value is a test waiting to be written; the gate now pins the
default it prescribes.

**Diff against the known-good artifact, flag by flag, before theorising.** The owner had
a launcher that behaved correctly and one that did not. Four host-memory routes existed -
fitting, mmap, KV spill, checkpoints - and they were closed one per patch across p30,
p33 and p34 because each round asked "what could cause this" instead of "what differs".
The full diff was available from the first message that contained both files.

**A symptom with several independent causes reappears identically after each partial
fix.** Three times the report was "no change", and three times something HAD changed -
just not enough to alter the observable. Where multiple causes are plausible, enumerate
and close them together, or state explicitly which half is proven and which remains.

**Never let an explanation disable an input.** The OFF map served two purposes - saying
why a setting is being overruled, and setting `disabled` on it. The first is helpful and
can be wrong harmlessly; the second is destructive when wrong. A claim in a comment
became a locked control, and the owner had to hand-edit launchers to apply the fix that
control existed to apply. UI that removes agency needs a much higher standard of evidence
than UI that offers advice.

**Repainting cannot fix what is read once at load.** Three patches tried to make a
focus-deferred repaint eventually fire, each correct about the previous failure and each
still ending in CTRL+F5. The honest read is that the repaint path was never the whole
story, and an install is rare, deliberate and already disruptive - a page reload is
allowed. Prefer the certain, blunt mechanism for rare events; save the careful one for
the hot path.

**A summary is not the conversation.** This session lost an exchange to compaction, and
the reply to it - patch34 - existed in the tree while the request that produced it did
not. Before assuming an unfamiliar tree state is corruption, check whether it is simply
work whose provenance was dropped: the version line, the CHANGELOG entry and the shipped
zips all agreed, and they were the record.

**A readiness check must ask about the thing that can be down.** PTI and PME are
panel-called: they have a server but no listener, and provider_route says so - "Proxy",
no port. The gate probed rt["port"], which is empty for exactly those two, so
slot_status("") answered "unknown" forever and the tagger failed open on every player
line. The failure was silent BECAUSE it was designed to fail open. When a guard exists to
skip work safely, its inputs need a test of their own; a guard that always fires is
indistinguishable from a feature that is off.

**A switch that needs a restart is not a switch.** Remote Access bound the socket at
startup, so flipping it changed nothing while the page printed the LAN address to visit.
The bind was defence-in-depth over client_scope, which is consulted PER REQUEST and
already denies external addresses outright and LAN addresses while the switch is off.
Keeping the weaker, static lock cost the stronger, dynamic one its effect. If a control
implies immediacy, the enforcement point has to be one that is consulted at use time.

**Reverting is allowed to be the answer.** patch35 reloaded the page after an install
because four repaint attempts had failed. It worked, and it threw away the terminal, the
scroll position and any half-typed field to deliver four strings. The owner rejected it
and was right: the fix was to write those four fields directly after the repaint. When a
solution is disproportionate to the problem, that is evidence the problem was framed
wrongly.

**An off-by-default display switch is a bug report waiting to happen.** ttsThoughtOut
shipped off, and a session went into "NPC thoughts are broken" before the owner found the
button. This is the second time in one session that a display default produced a fault
report - PTI Output and PME Output are the same shape. If a feature exists because it is
useful, its display default should be the useful one; save "off by default" for things
that cost something to show.

**Read the identifiers out of the source before writing a list of them.** The stamps
default was first written as "dashboard,thinking,tts,ptipme,split" - and the real kinds
are splitd and splitt, with ttscal besides. A name nothing matches fails silently: that
terminal simply keeps its timestamps and nobody knows why. The gate now compares the
default against the set of tail ids scraped from the page, both directions, so an
invented name and a missed terminal each fail.

**Thought timing has not been touched this session.** The owner reported thoughts landing
after the first chunk again and asked for a revert; the newest patch marker anywhere in
the arming block is patch182, well before patch26. The cause is therefore adjacent -
chunking, or last-chunk detection - and reverting something that was never changed would
have been a wasted patch. Check provenance before reverting.

**When a function is right and the symptom persists, instrument its INPUTS.** Fed the
owner's own logged strings, tts_chunk_is_last returns True on the real final chunk - so
the suffix rule is sound and something about REPLY_FULL is not. Three candidates share
one symptom: no kept reply, a stale one, or one whose text does not match. Guessing
between them is what the last two rounds did; the verdict now names itself, and the next
log answers it. Prefer a patch that ENDS the guessing over a patch that guesses better.

**A diagnostic must not have side effects a predicate did not have.** _th_why called
calterm_log, which creates the log directory and reads the config - so a pure test of the
predicate began writing files into the tree, and the gate's own "leaves no trace" check
caught it. The explanation is now written only when a thought is actually waiting on this
speaker, which is both the only time it is useful and side-effect-free everywhere else.

**Display switches, again.** ttsActionOut shipped off for the same reason ttsThoughtOut
did, and would have produced the same bug report eventually. Both are now on. The rule
worth keeping: a switch that only decides whether to SHOW something already computed
should default to showing it.

### Still open

- **The launcher template's VRAM REPORT prints "STATUS: loaded" over a dead launch.**
  The panel's card report reads llama.cpp's own lines instead and says "exited during
  load"; the template's line itself still lies and stays unfixed.
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

---

## 14. Thought audio: the turn queue (built in 34, reverted in 37)

The thought-audio feature does something SkyrimNet has no concept of, through a door
built for dialogue. Every symptom the owner reported - overlap into the next speaker,
overlap between chunks, "impossible to get right by timing" - follows from that one
fact rather than from any of them being separately fixable. This is the agreed design
and the measurements that settled it. It replaces the timing model rather than tuning
it.

### 14.1 What the panel can and cannot observe

| | |
|---|---|
| **Exact** | when the panel handed a WAV to SkyrimNet, and that WAV's duration - the panel made it |
| **Exact** | when the panel's own thought audio finished - the browser plays it, `au.onended` fires |
| **Unknowable** | when SkyrimNet *starts* playing a delivered WAV |

Everything today leans on the third. `_hold_s` is a capped guess; the `after` timer
models WAV length plus start latency plus an inter-chunk gap, re-armed per chunk. It
cannot come right, and no amount of tuning changes that - it is predicting a device
the panel cannot see.

### 14.2 Measurements taken from the owner's p16 session

- **The LLM door tolerates 59.2 s.** 126 completions, median 1.28 s, p90 11.92 s,
  max 59.20 s, no abandonment anywhere in the logs. Waiting is expected there - it is
  a generation.
- **The TTS door has only been pushed to 4.4 s.** `final_ms` max 4360, p95 3038 over
  583 requests. `TTS_FLOOR_CAP_S = 12.0` is an assumption inherited from the old hold,
  never measured. **Hold at the LLM door, never at the TTS door.**
- **A reply becomes 2-4 TTS chunks.** The panel counts them itself, by matching each
  arriving chunk against the reply it already holds (`_th_member`, `tts_chunk_is_last`).
  It does not need to know SkyrimNet's splitting rule and must not try to infer one.
- **Request arrival is NOT a playback-end signal.** The gap between the last TTS chunk
  and the next Dialogue call runs from **-3.8 s to +117 s**. It was considered as a way
  to remove the last estimate; the spread rules it out.
- **SkyrimNet pipelines TTS requests.** Consecutive chunks of one reply arrive a median
  0.77 s *before* the previous one would have finished. `ahead = self._inflight - 1`
  exists for that reason.

### 14.3 The design - BUILT in patch34, REVERTED in patch37

**REVERTED in patch37.** The queue worked exactly as designed - and the design
gated whole turns on playback (see gotcha 201). The pre-34 after-timer engine
came back; the delay field remains, feeding it.

`after` only. The before/after dropdown becomes a **delay** field.

1. A **bundle** is a Dialogue job's reply plus every TTS chunk matched into it, closed
   by `tts_chunk_is_last`.
2. When the last chunk's WAV is handed over, wait `duration + delay`, then play the
   thought.
3. `au.onended` posts back to the panel. A fact, not an estimate.
4. The **next Dialogue completion is held** until that arrives. SkyrimNet cannot
   request TTS for text it has not been given, so one held response gates the whole
   turn's audio.

Why it works where timing does not: SkyrimNet may request as far ahead as it likes,
but it can only PLAY what it has received. Releasing one turn at a time makes delivery
order the playback order without needing to observe playback at all.

**One estimate survives** - delivery-to-audible latency, the delay field. Under the
queue, being late costs nothing: there is no next turn to collide with, because it is
held. Being early clips the tail of the same NPC's own sentence. The failure is
asymmetric, so **bias the estimate late** - ship 0.75 s rather than the 0.45 s that
`TH_START_LAT` has carried, which was tuned under a design where late collided with the
next speaker and was squeezed from both sides.

**Why not `before`:** there the estimate gates the next turn, so late costs a stall and
early costs an overlap - squeezed from both sides again. `after` puts the panel's own
audio last, where `onended` makes the gate exact.

### 14.4 What this deletes - DELETED in patch34

`TH_AFTER`, the re-arming timers, `CHUNK_TRACE`'s defer ladder, `TH_FIRE_PAD`,
`TH_CHUNK_GAP`, `tts_floor_set`'s predicted duration, `_hold_s` and its cap, and the
`ttsThoughtSeq` branch. All of it exists to model a boundary the queue makes explicit.

### 14.5 Ruled out, with reasons - do not revisit without new evidence

- **Joining thought and speech into one WAV.** SkyrimNet lip-syncs what it plays, and
  the thought must not move the NPC's mouth. Thought audio is panel-side today
  (`sse_notify("replay", …)`), which is *why* it has no lipsync - the game never sees it.
- **Telling SkyrimNet not to lip-sync, or marking the audio.** The contract is Gradio's:
  the last exchange hands over raw WAV bytes and nothing else. There is no field.
- **Merging `<eid>` into the reference grammar.** They point at different things - a
  file on disk versus a record the proxy holds - with different minting authorities and
  lifetimes. The forced write order (audio id first, reference last) is the only cost
  and it is pinned by a gate check.
- **A queue at the TTS door.** Wrong door: narrow, unmeasured headroom, and it cannot
  see playback start.
- **Gating on the Meta call.** Meta fires several times per turn, interleaved with
  ActionEval; telling a turn boundary from a mid-turn evaluation is unsolved and
  unnecessary once the gate is the Dialogue job.

### 14.6 Three things got established the hard way

- **`said` in the identity ledger is the TTS request text**, not the LLM reply. Reading
  it as the reply led to "SkyrimNet does not split at all", which is wrong.
- **`sent` is the sample path**, not the text. Reading field names instead of the writer
  (`tts_identity_note`) produced two wrong answers about chunking before the third
  attempt read the twelve lines that settled it.
- **The panel already knows how a reply was split** and always did. It holds the reply
  and matches chunks into it. The question "what is SkyrimNet's chunking rule" never
  needed answering.

### 14.7 Sfx tags are not a scheduling problem

SkyrimNet strips `<`, `|` and `>`, so the model writes `[LAUGHTER]` and the panel
rewrites it to `<|sfx:laughter|>` - injecting the onomatopoeia (`Haha`, `Haah`) itself,
because a bare tag performs nothing. That word is in the text sent to the engine, so it
is in the WAV, so it is in the measured duration. The gate reads the finished file;
nothing about sfx is estimated.

It does mean the audio says a syllable the in-game subtitle does not show, since the
subtitle carries the model's original text. That is a content question, not a timing
one, and is open.

### 14.8 Build order

1. **Report `au.onended` back and hold the next Dialogue response on it.**
   **DONE in patch20**, half of it: the page now reports, and the floor the BEFORE
   hold already waits on is brought in by the real end instead of the predicted one.
   The predicted floor stays as the ceiling, so a closed or throttled page loses
   nothing. Holding the DIALOGUE response rather than the TTS one landed in patch34,
   and was reverted in patch37 - the held Dialogue slowed every turn; the floor
   at the TTS door is the rule again.
2. **Collapse to `after` only**, replace the dropdown with the delay field, delete
   14.4. **DONE in patch34** - the play-first precondition waived by the owner.
   The delay field survives the patch37 revert.

---

## 15. The unified presentation system (patch24-patch29)

One vocabulary, one set of declarations, two resolvers, a reporter that cannot
be ignored, and two differs that referee every move. Built across six patches,
each proven byte-identical against the p16 session logs before it shipped.

**ELEM** - one entry per element: the recognition SOURCE beside the base ink.
Anchors are derived per read mode (`elemRx`; `RXTOK` for whole-token forms,
`MARK.rx` filled by the same loop), never written twice. Where a terminal
genuinely accepts a different set, that difference is a NAMED form in the one
entry - `tok:` for the Proxy arm's foldings, `tts:` for the report-row number,
`short:` for the record line's parenthesised figure, `loose:` for the head
stamp - instead of an unlabelled local. Exactly two stamp spellings exist in
the page and the gate counts them.

**SHOW** - exhaustive, five panes by every element. A hex is the ink; `null`
is a decision not to mark; `ENTITY` says the ink arrives on the record; a
PARTS object carries named sub-inks, and `inkOf` answers a scalar reader with
`.value`/`.unit`, so one declaration serves the Proxy arm's decomposition and
a TTS-family fragment on the same pane. A missing key is not a default - it is
a fault, from both vectors: `showAudit` at page load, and the draw-time seam.

**LINE** - whole-line shapes per pane, first match wins, and the ORDER is
load-bearing: an error inside a spoken line is a spoken line. `trim` is part
of the declaration where the painter always trimmed. Rendering stays in the
painter; LINE only decides.

**The resolvers.** Occurrence: `markAt` walks the stream with the derived
rules; precedence is the written order - a character beats a provider beats a
shape that merely looks like one. Entity: `paintProvs` fills the READY SET
once per routing change - title, id, emoji, ink - plus the exact-key
`MARK.provIx`; `entInk` is the public face (drilldown-strip, set hit,
derivation fallback - the hash is LIVE in the field and stays for a name the
set has never met); `dashColor` is internal, pinned at exactly three
references. Painters take the ink OFF the record, never per painted token.

**The reporter.** `paintFault(level, pane, element, failure, sample)` - the
reference is an FNV-1a hash, stable across sessions; one report per reference;
fire-and-forget to `/api/paint-fault`, which lands on the existing
`log_warn`/`log_error` split and never raises an issue by a side path. A fault
that reaches the screen wears `.unset`: dotted, colourless, the reference on
hover - because every real ink in these terminals is a deliberate choice and a
failure wearing one is invisible.

**The differs.** `gate-tools/term-diff.js` paints one whole terminal from a
real feed in two builds and compares bytes - the acceptance test for every
painter migration, and the gate runs it against itself with a moved-colour
control. `gate-tools/entity-diff.js` snapshots the ready set and the
resolver's probe answers between two builds; a build from before the resolver
answers through the derivation itself, which made the patch27-vs-patch28 run
the consolidation proof. Corpus law throughout: only what the corpus
exercises is folded; unexercised tolerances survive as NAMED forms, and what
no corpus can referee is guarded at the source - the `[]]` ban, the
backslash-free page rule, the two-stamp count.

**The build, one line each.** patch24: the differ itself proven (it shipped
unable to say no). patch25: ELEM/SHOW/LINE, both resolvers' tables, the
reporter, the Proxy arm migrated. patch26: pane-aware `drawSegs`, the think
family migrated, no legacy path - a pane-less call crashes loudly. patch27:
the spoken family and `rtTint`, the parts rule, `TSTAMP_RX` derived. patch28:
`entInk`, six askers, the entity differ. patch29: a counted figure wears no
tilde (the one content patch; the reader was ready since patch13).

**Deliberately NOT unified.** `*starred*` emphasis and the separator ink stay
painter-local in `paintThink` (line-level choices, not elements); the white
asterisks around a tag stay in `paintSpoken`; `pidRx` stays in the Proxy arm
(layout, not recognition); respPretty keeps its private gold (section 11);
LINE's order arrays ARE its declaration - a four-state line audit waits for a
second consumer. Standing behaviour deltas live in section 11.
