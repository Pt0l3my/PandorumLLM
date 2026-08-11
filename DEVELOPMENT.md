# PandorumLLM — Development Handoff

**Drop this into a new chat together with the current `fleet-panel.py`** (or the whole latest
zip) and work can continue with no ramp-up. It says what the project is, how it is built,
how a release is cut, and — most importantly — the traps that have already cost real
debugging time. **Read §5 before editing anything.**

**Current version:** v3.75 Beta (`v3.75 Beta` in the header).

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

**Version string.** `APP_VERSION` ("v3.75 Beta") + `APP_PATCH` (an int, 0 = none) are
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
> thinking-proxy for my SkyrimNet local llama.cpp fleet. Current version is **v3.75 Beta**.
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
