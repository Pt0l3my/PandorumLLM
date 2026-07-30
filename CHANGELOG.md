# PandorumLLM — Full Version History

Every released version, newest first. Compiled from the changelog in `README.txt`,
which has had a paragraph appended on every release — so this is the real record,
not a reconstruction.

**Current version:** v3.73 Beta.

---

## v3.73

Everything from the v3.72 patch series, plus the pre-release sweep below.

**Safety and privacy**
- Removed the Google Fonts link. The page pulled a webfont from `fonts.googleapis.com` on
  every load, telling a third party the IP and referer of a panel documented as LAN-only,
  and needing the internet to look right. The family is still declared, so a local install
  is used; otherwise it falls through to Segoe UI. The page now loads nothing external.
- `NO_CFG_LOCK` (patch43) removed the serialization that launching and starting TTS had
  been relying on, so a second press could have started a second server. Each now has its
  own lock, tried without blocking, so neither can double-start and neither waits on the
  other.
- The remote comment on `/api/tail` claimed dashboard and thinking only; it has always
  allowed tts as well. Corrected, and it now states plainly that those feeds carry content
  - reasoning, dialogue, character names - not only numbers.

**Permissions tree**
- Added the one-click installer and the audio.cpp update check to the host column, both of
  which reach the internet.
- Removed the claim that filenames are stripped for remote readers: the Saved line is a
  bare filename by design since patch13. Full paths are still masked.
- Added an explicit line saying terminal text reaches a remote reader.

**Duplication**
- The spoken line and the saved line were each written once per engine arm. Now one
  `say_line` and one `saved_line`, called from both.
- Two identical patterns for a rendered control token, one of them inline. Now one
  `TTS_TOKEN_RX`.

## v3.72 patch47
- Fix: pressing Terminate while TTS was starting left the button reading "Starting TTS..."
  for good. Nothing said the process had gone, so the flag was never cleared. The panel
  already reports whether it holds a TTS process; the button uses that.
- Fix: patch46 pushed the right pane's bar down a row, which left its Timestamps orphaned
  below the Adjust that belongs with it. In full window the right pane's controls now move
  into the outer bar, which is where its **Adjust already went** - the pattern was there and
  I had not followed it.

## v3.72 patch46
- Fix: in full window, Split View's buttons overlapped on the right. There are **two**
  chromes there - an outer bar carrying Full Window / Normal Size, and one per pane
  carrying Timestamps and Adjust - and in full window both are absolutely positioned at the
  top, so the right pane's right-aligned buttons landed underneath the outer ones. The pane
  bars now sit below it. Making the bar wrap in patch44 could not have helped: they are
  different elements, not one row.

## v3.72 patch45
- Fix: neither launch button lifted on hover. The crackle rides on the arc effect, which is
  off by default since patch32, so hover now has its own rule and is always there.
- Fix: Terminate did stop the TTS server - it always has - but the button had no state for
  it, so it kept reading "TTS running..." while the model unloaded. It now says
  **Stopping TTS...** and glows like the fleet button does.
- Fix: per-terminal timestamps did not work in Split View. A pane paints the FEED it shows,
  and the button toggles the PANE, so the two names never matched. `paintTail` is now told
  which pane it is drawing into.

## v3.72 patch44
- Fix: a long spoken line wrapped back to column zero and cut through the branch. It now
  hangs under the dialogue, indented to just past the speaker's name. The indent is measured
  in terminal columns rather than characters, since an emoji occupies two cells.
- Fix: in a narrow Split View pane the Timestamps and Normal Size buttons sat on top of each
  other. The bar wraps now and no button can be squeezed away.
- Fix: Timestamps toggled every terminal at once. It is remembered per terminal, and each
  button carries the terminal it belongs to.

## v3.72 patch43
- Change: the TTS tab is no longer labelled Alpha.
- Fix: **Launch TTS** had no lit or running glow. Every launch style was keyed on
  `#launchBtn` alone, so none of them matched the second button - including the one that
  gives it an arc overlay at all.
- Fix: **Launch LLM** lost its hover crackle once servers were running. A disabled button
  emits no pointer events; both buttons are now marked busy instead, with the click
  refused in the handler.
- Fix: starting one server blocked the other button. Every mutating request was
  serialized on the config lock, and a launch holds it for seconds. Launching, TTS and the
  installer now run unlocked - anything of theirs that needs the config takes the lock
  itself.
- Change: the TTS page carries less prose; the install hint reads "1 click install into the
  PandorumLLM directory"; the version report is yellow throughout.

## v3.72 patch42
- Change: **Launch** is now **Launch LLM**, and **Launch TTS** sits beside it - same arcs,
  same loading and running glows, driven by whether the TTS server is answering. Pressing
  it with nothing configured says what is missing and opens the TTS page. Stopping stays on
  the TTS page.
- Change: the setting is now **TTS** rather than TTS engine, and names the voice - "Higgs
  Audio v3 (4B) - runs on audio.cpp" - so the engine follows from the choice. Still stored
  against the engine, so no existing config needs migrating.
- Change: the branch glow is a three-layer shadow.
- Fix: the mood icons did not line up, since emoji widths differ. Each sits in a fixed cell
  now, and the plain one carries a variation selector or it renders narrow.
- Change: the audio.cpp version check no longer mentions that it could not determine the
  installed version. It states it where it knows, and otherwise just reports the newest
  release.

## v3.72 patch41
- Fix: the player's line could carry another character's name. It was taken from
  `You are speaking to ...`, which names the **listener** - so when one NPC addressed
  another, the player's own voice took that NPC's name. The player is now named from
  `## <Name>'s Party's Active Quests`, which is always the player whoever is speaking,
  and falls back to "Player" rather than borrowing a name.
- Change: a spoken line is headed by an icon for how it is meant to sound - an angry face,
  a laugh, a whisper - rather than one mask for everything. Every emotion, style and sound
  effect has one; a line with no tags gets a speaking head.
- Change: a spoken line is now recognised by the markers around what was said rather than
  by its icon, since the icon varies.
- Change: the version check also reads the server's own startup output, which the panel
  already captures.

## v3.72 patch40
- Change: a spoken line that hangs off nothing now starts in the same column as one that
  hangs off a reply - the arrow is indented like the branch and takes its width.
- Change: the branch glow is a two-layer shadow rather than one, so it reads more clearly.
- Change: the version check tries four things in order, since the README turned out to
  carry no version: the tag recorded at install, a **running server's** `/health` or
  `/v1/models`, the file's own Windows version resource, then a version in any README or
  CHANGELOG shipped beside it. If none answer it reports nothing rather than guessing.

## v3.72 patch39
- Fix: the branch is now **drawn** rather than typed. A stretched box glyph overlapped the
  row below it and the glow doubled up where they met; an inline-block exactly one row
  tall touches the next and no more.
- Fix: the player's spoken lines took an NPC's name, and NPCs got the player's marker.
  The player speaks BEFORE the next dialogue request, so their voice was pairing with the
  previous turn's character. The player is now named from the same prompt line - `You are
  speaking to Maxxor` - and never enters the learned map. The pairing window is also
  tightened from 45s to 15s.
- Fix: the version check reported nothing for an install the panel did not perform. It now
  reads a version out of the README the release archives carry, and records it when an
  existing install is adopted.

## v3.72 patch38
- Add: the terminal names the **character** rather than the voicetype - Serana, not
  Femaleyoungeager - and saved files are named the same way. SkyrimNet's dialogue prompt
  opens with `You are Serana, a Female Nord in Skyrim`, and the proxy is already carrying
  that request, so no extra model call is needed and nothing leaves the machine. Only the
  name is kept, never the prompt, and only the first 4 KB is scanned.
- The pairing is **learned**: a TTS call arriving shortly after a dialogue request pairs
  that voicetype with that name, and the request is consumed so a second voice in the same
  window cannot inherit it. A learned pairing is never relearned. It is a heuristic - it
  assumes one turn at a time, which is how SkyrimNet works - and falls back to the
  voicetype when it has learned nothing.

## v3.72 patch37
- Change: a spoken line that hangs off nothing - the player's own speech, which no reply
  produced - gets a glowing arrow rather than a branch.
- Fix: a turn's chunks are grouped by speaker as well as by time. Grouping on the gap
  alone merged the player's line with the NPC reply 3.7s later, so each speaker now gets
  its own branch under the reply.
- Change: the branch glyph is stretched to the row height, so consecutive ones meet
  instead of leaving a gap - the terminal runs line-height 1.6 and a box character fills
  only part of the row.

## v3.72 patch36
- Change: inserted spoken lines are drawn as a channel tree hanging off the completion
  above - the glyph after the timestamp, indented, in the accent colour with a glow, and
  the last chunk of a turn closing it with a corner.
- Add: the audio.cpp release tag is recorded when the panel installs it, so **Check for
  update** has something to compare. The binary reports no version of its own, which is
  why the check found nothing.
- Add: an install already on disk is detected. If the server and a model are in the
  panel's own folders but the settings are not pointing at them - after installing by
  hand, or after a config save that failed at the last step - the page offers **Use it**
  instead of asking for four paths.

## v3.72 patch35
- Fix: turning timestamps off also removed the TTS insertions. The splice places lines by
  timestamp, and the stamps were being stripped first, so it had nothing to match on.
- Add: an inserted line begins with a bold purple arrow, so it is obviously not part of
  the fleet log. The marker survives hiding the timestamps.
- Add: each Split View pane chooses its own feed - **Proxy**, **Thinking Content** or
  **TTS**. The choice is remembered.
- Fix: Insert TTS appeared on both split panes regardless of what they showed. It is now
  only on a pane showing the proxy.

## v3.72 patch34
- Fix: a streamed reply produces several spoken lines a second or so apart, and matching
  each on its own timestamp scattered them between the Meta and Vision calls that landed
  in between. Consecutive spoken lines within 5s are now treated as one turn and placed
  together, under the dialogue completion nearest where the turn STARTS.
- Fix: the terminals showed the previous run's fleet log until a new launch created a new
  one. Only a log written during this session of the panel is shown; before the first
  launch it says so.
- Fix: the space between the mask and the speaker name was being trimmed away.

## v3.72 patch33
- Fix: spoken lines in the Proxy terminal piled onto one old completion in **reverse**
  order. Measured from real logs, a spoken line lands 0.2-0.5s **before** its dialogue
  completion - SkyrimNet fires TTS on the final token and llama.cpp writes its timing line
  a moment later - so the match was the wrong way round. Each line is now placed under the
  completion that follows it, and several on one completion stay in time order.
- Fix: the speaker was mis-coloured. `(local clip)` in the name broke the parse, and the
  parse itself matched to the last colon, which swallowed the timestamp. The suffix is
  gone from the spoken line - it appears on the Saved line as `[local clip]` - and the
  speaker is now read between the mask and the first colon after it.
- Change: the TTS log starts empty each session, as the fleet logs already do.

## v3.72 patch32
- Change: the launch-button arc is **off** by default. The guide step highlights the button
  instead, so nothing depends on it.
- Fix: a tag ran into the word after it in the terminal - `*laughs*Hehe`. The display now
  spaces them; the engine still receives them flush, which Boson require for the tag to
  take effect.
- Fix: a line spliced into the Proxy terminal was left unpainted. The spoken-line painter
  is now shared, so it looks the same in both places.
- Fix: the spliced line was pinned under the newest completion and stayed at the bottom.
  TTS log lines are now stamped, and each spoken line is paired to the **dialogue**
  completion at or before its time - the newest completion is usually a Meta call that
  landed in between. Several lines can be placed at once, each in flow.

## v3.72 patch31
- Fix: console windows popped up on launch and twice on exit. patch16 switched the panel
  to `pythonw.exe` so nothing had to be started hidden - but `python.exe` with
  `CREATE_NO_WINDOW` still HAD a console, just hidden, and child processes inherited it
  silently. `pythonw` has none, so every `pwsh` and `nvidia-smi` call allocated a fresh
  visible one. All nine spawns now suppress it explicitly rather than relying on
  inheriting somebody else's hidden console.
- Change: the spoken line in the TTS terminal is gold rather than the theme accent.
- Add: a **Timestamps** button on every terminal, hiding the leading `[20:45:12.86]`.
- Add: an **Insert TTS** button on the Proxy and Split View terminals, which places the
  newest spoken line and its speed under the newest dialogue completion.

## v3.72 patch30
- Fix: a successful install said nothing. The row had branches for running and failed but
  not for finished, so it fell back to the same Install button - a completed install looked
  exactly like one that had never been pressed. It now names the model and engine folder,
  points at Start TTS, and can be dismissed.
- Change: pressing Install again skips an engine that is already unpacked, so retrying
  after a failure costs only the part that did not finish.
- Change: the failure message says that anything downloaded is kept and trying again
  resumes.

## v3.72 patch29
- Fix: saving the config could fail with `[WinError 5] Access is denied` on the atomic
  rename. Anything holding a handle for an instant causes it - an antivirus scan or the
  search indexer, both of which are busy right after the installer writes several
  gigabytes into that folder. The write now retries for about two seconds before giving
  up, and never leaves a `.tmp` behind.
- Change: if that last step still fails, the installer reports what **was** installed and
  the four values to set by hand, rather than reporting a failed install. The download is
  complete by then and nothing is lost.

## v3.72 patch28
- Change: engine assets are matched on the **words** a filename contains rather than a
  prefix. `win` not `windows`, so a `win64` archive matches; the CPU profile is a
  preference with fallbacks (`balance`, then `portable`, then `fast`, then anything)
  rather than a requirement; and the shared runtime is optional, since a future release
  may fold it into the build. The release fetched is always `latest`, so the version was
  never pinned - only the naming was, and now much less so.
- A rename that still defeats it fails with the release's real asset list, so it can be
  installed by hand from the same message.

## v3.72 patch27
- Fix: the Higgs installer could not find the engine. audio.cpp's profile archives carry
  the build's commit hash - `audiocpp-windows-cuda-balance-27d87ba.zip` - while the shared
  runtime does not, and the installer asked for exact filenames. It now matches by prefix,
  so a new build's hash cannot break it.
- Change: when an asset really is absent, the error lists what the release does carry
  rather than only what was wanted.

## v3.72 patch26
- Fix: the "Panel is NOT elevated" banner showed for everyone. It dated from when the
  launcher relaunched itself as administrator; patch15 removed that, so the panel is
  never elevated and does not need to be - it binds high ports, writes only in its own
  folder, and signals only processes it started. Banner, its styling and the matching
  console warning all removed. `is_admin()` stays in the diagnostics dump.

## v3.72 patch25
- Add: **Local Voice Clips** on the TTS page. Drop a `.wav` named after the voicetype -
  `femalenord.wav`, `malecommoner.wav`, `serana.wav` - and it is used instead of the
  upload. SkyrimNet resamples every reference to 16 kHz before sending it, including the
  44.1 kHz files in its own voice-samples folder; Higgs runs at 24 kHz and has room for
  far more. The terminal marks a line that used one. Idea and naming scheme from
  `cleanestpoison/higgs3-tts-skyrimnet`.
- `.wav` only: the reference implementation accepts six formats because it has FFmpeg,
  and this panel is stdlib-only.

## v3.72 patch24
- Change: audio tags read as stage directions in the terminal - `*sniffs*`, `*afraid*`,
  `*whispering*`, `*long pause*` - rather than raw identifiers. All 43 have a word.
- Change: the spoken line is colour coded. Speaker in magenta, the dialogue itself
  highlighted, tag words in cyan between white stars.

## v3.72 patch23
- Change: the TTS terminal shows audio tags inline in `[FAMILY-VALUE]` form, in cyan, so
  you can see at a glance whether a tag survived SkyrimNet and reached the engine. The
  line still goes to Higgs in its native `<|family:value|>` form; only the display differs.
- Add: the TTS terminal is painted rather than dumped as plain text, with every part of a
  line escaped, since it carries NPC dialogue.

## v3.72 patch22
- Add: SkyrimNet's own tag vocabularies are translated too - `[angry]`, `[sigh]`,
  `[whispering]`, `[laugh]`, `[pause]` and the rest - so its **stock** prompt works with
  Higgs without being edited. No engine selector needed: the two forms cannot collide,
  since Higgs' are uppercase `FAMILY-VALUE` and SkyrimNet's are lowercase words.
- Tags with no Higgs counterpart - `[shush]`, `[groan]`, `[gasp]`, `[advertisement]`,
  `[narration]` - are named and removed rather than guessed at.
- Anything else in square brackets is **left alone**. A line may legitimately contain
  `[see the note]`, and deleting it loses meaning where speaking a stray tag does not.
- A recognised tag is removed even with tags switched off, so it is never read aloud.

## v3.72 patch21
- Add: **Cached Voices** on the TTS page, written into `server.json` as
  `reference_cache_slots`. The engine's default is **one**, so with a conversation
  alternating speakers practically every line re-encoded its reference. Default 64,
  clamped to 1-1024; raise it if you use many custom-voiced NPCs.

## v3.72 patch20
- Add: **Install Higgs v3 for me** on the TTS page. Downloads the audio.cpp engine from
  its GitHub release and the Q8 model from Hugging Face into `PandorumLLM\audio.cpp` and
  `PandorumLLM\Models\TTS\Higgs-v3-4b`, unpacks them, and selects them on the page.
  The manual route is unchanged and the guide still documents it.
- One confirmation before anything is fetched, naming both sources, both sizes, the GPU
  requirement and the disk needed. Host-only, refused without that confirmation, and
  stoppable - a part-finished download is kept, so starting again resumes.
- Archive entries that would land outside the target folder, or name an absolute path,
  are **refused** rather than flattened into it.

## v3.72 patch19
- Fix: a line ending in a sound effect lost its full stop. The text is punctuated before
  tags are rewritten, and a trailing `[SFX-LAUGHTER]` then appends its onomatopoeia after
  it - leaving the spoken text unpunctuated, which invites the model to keep talking.
  Punctuation is now checked again after rewriting, ignoring the tags themselves.

## v3.72 patch18
- Fix: audio tag handling rewritten against rules measured by
  `cleanestpoison/higgs3-tts-skyrimnet`, each of which silently spoiled the feature:
  - **Sound effects need onomatopoeia** immediately after the token, in the spelling the
    model was trained on. A bare `<|sfx:sigh|>` does nothing at all; it now becomes
    `<|sfx:sigh|>Ahh,`.
  - **Emotion, style and speed/pitch prosody are sentence-level.** Written mid-line they
    are moved to the front of their sentence rather than emitted where they were typed.
  - **A pause with no speech on one side is dropped.** `<|prosody:long_pause|>` at the
    start or end of a line makes the decoder run to its token cap without ending the
    clip - audio.cpp then fails the request with no audio, and repeated hits have been
    seen to take the engine down.
- Fix: the sound-effect list was wrong. `breath` and `throat_clearing` are not tags;
  `crying`, `screaming`, `burping`, `humming` and `sneeze` were missing.
- Add: `EMOTION_FEAR`, `EMOTION FEAR` and `EMOTIONFEAR` are accepted alongside
  `EMOTION-FEAR`, and competing tags are deduped rather than stacked.

## v3.72 patch17
- Fix: Audio Tags watched for a shape that can never arrive. SkyrimNet strips angle
  brackets and pipes from every line, so Higgs' native `<|emotion:fear|>` is destroyed
  before it leaves the mod. What survives is `[EMOTION-FEAR]`, and the panel now
  translates that - which is the entire point of the feature.
- Change: the Higgs guide no longer recommends Zonos outright. Zonos sends a 22050 Hz
  reference and clones better; Chatterbox sends 16000 Hz but is the only backend with an
  audio-tag list. The guide states the trade-off and the three SkyrimNet steps tags need.

## v3.72 patch16
- Change: the launcher no longer opens sockets. It used to probe five candidate ports to
  find the panel; it now reads `panel-port.txt`, which the panel already writes and the
  .bat already reads. A small unsigned binary doing port scans reads as reconnaissance.
- Change: `pythonw.exe` is preferred, so nothing has to be started with
  `CREATE_NO_WINDOW`. Telling Windows to hide a process is worth avoiding when unsigned.
- Change: the version resource declares InternalName, OriginalFilename, a real copyright
  and a Comments field pointing at the source; the manifest declares supported Windows
  versions and DPI awareness. Thin metadata is itself a heuristic signal.
- The binary now imports two notable functions in total: `CreateProcessW` to start the
  panel and `ShellExecuteW` to open the browser.

## v3.72 patch15
- Fix: Windows Defender reported `Trojan:Win32/Wacatac.B!ml` on the launcher for some
  users. The exe relaunched **itself, elevated and hidden**, then started Python hidden
  from there - which is what droppers do, and how the ML classifier read it. The panel has
  never needed administrator rights: it binds high ports and writes only inside its own
  folder, and the manifest has always said `asInvoker`. The elevation was a leftover from
  an older design and is gone. One less UAC prompt as well.
- Add: **StartPandorumLLM.bat** is back. It does what the exe does, in plain readable text,
  so an antivirus block on the exe can never leave anyone with no way in.

## v3.72 patch14
- Change: "Inline control tags" is now **Audio Tags**, and it applies to both engines.
  MOSS-TTS v1.5 has its own marker - `[pause 3.2s]` - so each engine keeps what it
  understands and drops the other's. A runaway pause is clamped to 10 seconds.
- Change: the audio.cpp update result is coloured as the llama.cpp one is - green when
  current, amber when behind or unknown, red on error.
- Change: the TTS settings have room between them, with a rule separating groups.

## v3.72 patch13
- Change: the terminal's Saved line shows the filename only. The folder is a setting, so
  printing it on every line was noise. Both engines.
- Add: **Inline control tags** for audio.cpp. Higgs acts on `<|emotion:...|>`,
  `<|style:...|>`, `<|prosody:...|>` and `<|sfx:...|>` written into the line. Off by
  default; the panel adds none of its own, only decides whether the ones your dialogue
  model wrote reach Higgs. Unrecognised tags are always removed - the model reads aloud
  what it does not know. The space after a tag is closed, which Boson document as
  necessary for the tag to take effect.

## v3.72 patch12
- Add: the TTS terminal announces starting, ready, listening and stopping, in the shape the
  reference wrapper used - naming the engine, the model and the card. The reference wrapper
  never reported stopping at all; this does.
- Add: the audio.cpp folder now gets what the llama.cpp folder has - a warning when no
  `audiocpp_server.exe` is found in it or below it, the releases address as a copyable
  block, and the update check beside it.
- Fix: a guide block flashed an outline *and* pulsed. The outline rule no longer applies to
  the pulsing blocks.

## v3.72 patch11
- Change: the guide keeps one **TTS Guide** tab, with **Higgs v3** and **MOSS-TTS** as pages
  inside it rather than two more tabs across the top.
- Add: copyable blocks carry a copy icon, and pulse in the accent colour when clicked. The
  icon is an SVG, and it is excluded from what reaches the clipboard.

## v3.72 patch10
- Change: the audio.cpp server is chosen by **folder**, as llama.cpp already is. The panel
  finds `audiocpp_server.exe` in it or below it - flat for a prebuilt, nested for a source
  build. Naming an executable directly is no longer offered.
- Fix: a path picker opened on a stale or unreachable path answered "not a folder" and gave
  up. It now falls back to the drive list.
- Add: **Check audio.cpp version** - the newest release tag, and the installed one where the
  binary will report it. Same terms as the llama.cpp check: only when pressed.
- Change: "Wrapper Port" is now **Proxy TTS Port** - the wrapper is optional, the port is not.
- Add: the User Guide's TTS page splits into **TTS: MOSS** and **TTS: Higgs v3**, the latter
  with the release link, both model download commands, and a default model folder.
- Change: the crash hint no longer assumes you built from source - the prebuilt CUDA package
  covers RTX 20xx and newer.

## v3.72 patch9
- Change: the audio.cpp terminal now shows the full breakdown. The server sends no timing
  headers under any name tried, so the request itself is timed: `server:` is the round trip
  with audio tokens and tokens per second, `overhead:` is what the panel spent around it.
  If a future build does send timings, its own split is used instead.
- Add: unrecognised `x-*` response headers are logged once, so audio.cpp's real timing
  header names can be found rather than guessed at.

## v3.72 patch8
- Add: **Saved Audio Folder** on the TTS page, for both engines. Generated lines are kept
  there as `<Speaker>_<YYYYMMDD_HHMMSS>.wav`, the same scheme the reference wrapper used,
  with a numeric suffix if two land in the same second. Blank keeps the old behaviour.
  Nothing in that folder is ever deleted by the panel.
- Change: the terminal shows the reference wrapper's breakdown again - generate, codec and
  overhead with audio tokens and tokens per second. On audio.cpp the split is shown only
  when the server reports its own timings; otherwise the total is shown honestly as one
  figure rather than a guess.

## v3.72 patch7
- Fix: a failed state load reported the wrong error. `load()`'s catch wrote through an
  unguarded `$("sub")`, so when that element did not exist the handler threw and replaced
  the real failure with a TypeError. Guarded, and the original error is now traced.
- Add: the gate rejects any catch block that assigns through an unguarded `$()` - an error
  handler that throws destroys the evidence.

## v3.72 patch6
- Fix: Chatterbox sent its reference voice to the wrong place. The wrapper read the text
  and the voice from fixed positions in the Gradio call, which is right for Zonos and
  wrong for every other engine using the same interface. Positions are kept where they
  hold and the fields are found by shape where they do not.
- Add: when the audio.cpp server crashes, the panel reads the tail of `tts-server.log`
  and says what happened. A dropped connection reads as `WinError 10054` and explains
  nothing; the server's own log names the cause one line earlier.

## v3.72 patch5
- Fix: patch4 normalised uploads but did not fix anyone who had already used the panel.
  SkyrimNet HEADs the reference path first and skips the upload on a 200, so a file
  cached by an earlier build was never re-sent and never normalised - the failure
  survived the fix. A stale reference is now checked (44 bytes) and repaired in place on
  first use. No need to clear the temp folder by hand.

## v3.72 patch4
- Fix: audio.cpp answered every real request with `failed to read WAV data chunk`.
  SkyrimNet's reference voices come from FFmpeg with extra RIFF chunks; the MOSS path
  normalised them, the audio.cpp path was given the raw file. Normalisation moved to
  `save_upload`, so the stored reference is canonical for every engine.

## v3.72 patch3
- Change: the audio.cpp model is chosen from a scanned list, as LLM models already are.
  Set a TTS models folder and pick from a dropdown; the scan finds both shapes audio.cpp
  loads - a `.gguf` file, or a folder holding `config.json` and `model.safetensors`.
- Fix: a safetensors folder with a `.gguf` beside it is marked unavailable and refused at
  start. audio.cpp resolves the gguf and ignores the safetensors **silently**, so picking
  "safetensors" there would have loaded something else with no indication.
- Change: a selected model may be a file or a folder, since pointing `path` at a `.gguf`
  works and removes the ambiguity entirely.

## v3.72 patch2
- Add: a TTS engine selector. **audio.cpp** joins MOSS - one server binary and a model
  folder, no python, no venv, no wrapper script. The panel writes its `server.json`,
  starts it with the GPU masked by UUID, and talks to `/v1/audio/speech`.
- Change: on the audio.cpp path the reference voice is passed as a **file path**, so
  nothing is base64'd per request. Chunking, concurrency and WAV stitching are also gone -
  the server does its own chunking and serializes requests, so all three were doing nothing.
- Change: the Gradio front is untouched. Upload, HEAD caching, event ids, the SSE shapes,
  the path jail, the client allowlist and the body cap are engine-neutral and shared.
- Add: a folder picker on the TTS page, since an audio.cpp model is a directory.

## v3.72 patch1
- Add: Customization > Effects - a switch for the lightning on the Launch button. On by
  default. Guarded inside `arcFire`, so every path that draws it is covered by one check;
  the button still changes colour and still shows the running count with it off.
- Change: with the lightning off, the Main Guide's launch step highlights the button. That
  step passes no selector to `helperGo` because the arc was meant to do the pointing, so
  with it off nothing pointed.
- Fix: the guide highlight was invisible on **every** button, not just this one. `guideHL`
  animates `box-shadow`, and `button { box-shadow:none !important }` overrides it - an
  `!important` declaration beats an animation. Buttons now get a text-shadow variant,
  which is what `lbDemo` and `btnPulse` already use on the same element.

## v3.72
- Fix: the proxy read whatever body length a caller claimed. Capped like the TTS listener;
  an oversized claim is refused with 413 rather than allocated. Both bind 0.0.0.0, so the
  cap belonged on both.
- Fix: uploaded reference voices were never pruned. Kept to the newest 32 alongside the
  generated audio; SkyrimNet re-uploads if its check comes back 404.
- Consolidates v3.71 and its patches.

## v3.71 patch7
- Fix: Terminate still showed nothing on the TTS page. `queueLoad` defers every reload
  while a write is in flight and Terminate is one long write, so the state event arrived
  and the reload was postponed until it finished - by which point the server was already
  stopped. `terminateAll` now marks the pane itself, as the Stop button does, and clears
  it in a `finally`.
- Change: one phrase for the state. It read "stopping" from the button and "shutting down"
  from the reported flag; both now say shutting down.

## v3.71 patch6
- Fix: patch5's shutting-down state could never appear. `stop_tts_server` waited for the
  process to exit before returning, so the port was already released and the status went
  straight to down - and the wait blocked the very response that would have reported it.
  Stop and Terminate now terminate on a thread, announce the change before blocking, and
  report `stopping` until the process is gone. The exit path still waits.
- Fix: Start was pressable mid-shutdown, racing the terminate. Both buttons are now
  disabled between running and stopped.

## v3.71 patch5
- Add: the TTS terminal has the Adjust menu the other three have - text scaling, size and
  font. It was left out because `tts` was never registered as a scale kind.
- Change: the kind list is now one tuple in Python, injected into the page, instead of a
  copy in each. `api_settings` filtered against the Python copy, so a kind the page knew
  about was dropped on save with no error. A `tts` scale setting now round-trips.
- Add: a server holding its port but no longer answering reads as **shutting down** rather
  than jumping straight to stopped, and Stop is disabled while it does.

## v3.71 patch4
- Fix: patch3's redraw was in the wrong place and changed nothing. `liveRefresh` runs
  *before* `queueLoad` fetches, so the pane was redrawn faithfully with the state it already
  had. Moved to `renderCurrent`, which `load()` calls once fresh state has arrived - it fell
  through to `renderRouting`, which returns unless Proxy Setup is open, so nothing redrew.
- Add: the gate drives the pane in jsdom through an actual state change rather than checking
  that a redraw call exists somewhere. The structural check passed while the bug was live.

## v3.71 patch3
- Fix: the TTS page did not follow the server's state. Terminate stopped it, but the pill
  still read ready and Start stayed disabled until the page was reloaded. Three causes, all
  fixed: `liveRefresh` never redrew the pane, the status watcher tracked only fleet slots so
  the TTS port changing produced no event, and stopping left the cached status saying
  "serving". Starting and stopping now announce themselves and drop the cache.
- Change: the pane stands aside while a field on it has focus, as the YAML pane does.

## v3.71 patch2
- Fix: the Permission Tree still described three terminals and said nothing about TTS at
  all. It now names the TTS terminal a remote viewer can see, lists TTS setup among the
  host-only powers, and includes TTS [Alpha] among the pages withheld from remote.
- Add: the gate checks the tree's claims against the code enforcing them - the terminals it
  names against the terminal list, and every page it calls withheld against either
  `data-hostonly` or a scope redirect. Section 8 specified this check; it had never been written.
- Change: `showDsub` refuses Proxy Setup at the click for a remote viewer, as it already did
  for SkyrimNet YAML and TTS. It was previously corrected only on the next refresh.

## v3.71 patch1
- Fix: closing the last browser tab shut the LLM fleet down but left a panel-started TTS
  server running, holding the model in VRAM with nothing able to reach it. `full_exit` now
  stops it and closes the TTS listener alongside the proxy's. Terminate does the same.
- Change: only a server the panel started is stopped. In launcher mode the server belongs
  to the user's own launcher and must outlive the panel, so it is left alone.

## v3.71
- Fix: the embedded TTS listener did not filter clients by IP. It binds 0.0.0.0 for 2-PC
  mode, so anyone on the LAN could upload a file or spend GPU time on it while the proxy
  beside it refused them. It now applies the same allowlist the proxy does.
- Fix: the TTS listener read whatever body length a caller claimed. Capped at 32 MB; a
  larger claim is refused with 413 rather than allocated.
- Fix: generated audio accumulated in the temp folder for as long as the game ran. Pruned
  to the newest 24, mirroring how the panel prunes its own logs.
- Fix: starting the TTS server leaked a file handle per press - the child holds its own
  duplicate, and the parent's copy was never closed on the success path.
- Consolidates v3.70 and its patches.

## v3.70 patch7
- Add: User Guide > TTS Guide. Eight-step setup from scratch, the two modes explained, and
  a troubleshooting section. States plainly that the support is experimental and built
  against one specific MOSS-TTS build (sammcj/openmoss), so a different TTS server will not
  work even if it also loads a GGUF.
- Change: `showUgSub` iterates one list instead of naming each pane and button, so a fourth
  guide is a single entry rather than four more lines.

## v3.70 patch6
- Fix: Start gave no feedback. The server does not bind its port until the model has loaded,
  so status still read "down" straight after the press and the button sprang back to
  "Start TTS" as though nothing had happened. It now reads "Launching...", stays disabled,
  and the state line says it is waiting for the server to answer. Times out at three
  minutes pointing at `tts-server.log`.

## v3.70 patch5
- Add: Start/Stop for the TTS server on the TTS page, so with the panel acting as wrapper
  there is nothing left to run by hand. Pins the GPU by UUID in the child environment,
  passes `--main-gpu 0` after masking, and writes the server's output to `tts-server.log`.
- Add: a readiness line covering both halves - server up on its port, panel answering on
  the wrapper port - and a pill that only reads ready when both are true.
- Change: start is a no-op when the port is already serving, so pressing it twice or
  starting alongside a hand-run launcher cannot produce a second server.

## v3.70 patch4
- Fix: the embedded wrapper handed the uploaded reference voice to moss-tts-server as-is and
  was answered 400. The reference wrapper round-trips it through soundfile first, which
  strips stray RIFF chunks and rewrites a clean header; the same is now done with `wave`,
  downmixing to mono without `audioop` (removed in 3.13).
- Fix: an upstream failure logged only "HTTP Error 400: Bad Request", discarding the server's
  own explanation. The response body and the URL are now included.
- Fix: "Recomputing voice" was printed both when a voice was computed and when no reference
  resolved at all. The second case now says so and names the path it tried.

## v3.70 patch3
- Fix: with the panel acting as the wrapper, the generated launcher still started a wrapper
  too and collided on the port every run. It now writes a server-only launcher in that mode
  and says so, since the model still has to be hosted somewhere.

## v3.70 patch2
- Add: the panel can be the TTS wrapper itself. It answers SkyrimNet's Gradio protocol on
  the wrapper port and translates to moss-tts-server's JSON, so no separate wrapper process
  or venv is needed. Stdlib only - `http.server`, `urllib`, `wave`, `base64`.
- Change: **off by default.** While on, voices depend on the panel running; the launcher
  route is unchanged and remains the default.
- Add: the startup ping is answered locally by default - returns silence, never reaches the
  GPU. Compared after normalisation, since the trailing full stop makes it arrive as "ping.".
- Fix (new code): `/gradio_api/file=` takes a caller-supplied absolute path and the listener
  binds 0.0.0.0, so it serves only files inside its own folder; uploads are sanitised into it.

## v3.70 patch1
- Add: the header, the startup banner and the generated launcher all carry the patch number
  and build hash, so a build can be identified from any of them. Every v3.70 build reported
  the same string, which made "is the fix installed?" unanswerable.
- Add: the terminal source line shows when the feed last refreshed, so a stalled live tail is
  visible without waiting for new content.

## v3.70
- Add: Proxy > TTS [Alpha]. Settings for a TTS server/wrapper pair (binary, model, ports,
  python, wrapper script) plus a GPU pinned by UUID, and a generator that writes
  `start-tts.bat` into the launcher folder.
- Add: fourth terminal beside Proxy/Thinking/Split tailing `tts.log`. Served as a fixed
  `api_tail` kind rather than `kind=file`, so it stays readable on remote with paths masked.
- Fix: the generated launcher exports `MOSS_TTS_URL` from the configured server port. Without
  it the wrapper fell back to a hardcoded 1240 and changing the port broke the pair.
- Fix: a serial-shaped GPU tag on a server survived `redact_state` and reached remote viewers.
  Masked in both slots and routing; a plain name tag and `gpuId` are untouched, so the remote
  Live Network graph still draws.
- Add: file picking for the TTS paths. The existing folder browser takes an optional
  extension filter and lists matching files; `Choose file` sits beside each path field.
- Add: `Import from a launcher` reads the paths straight out of an existing .bat/.cmd/.ps1
  and fills all six fields. Classifies by extension, not variable name, and returns only the
  fields it recognised - never the file contents.
- Fix: the TTS terminal did not stream. `sse_notify("tail")` only fires from `report()`,
  which runs when the panel writes the proxy/thinking logs itself - nothing tells it that
  `tts.log`, written by a separate process, has moved. `status_watch_loop` now stats it once
  a second (only while an SSE client is connected) and notifies through the same path.
  Server-status polling keeps its original 3s cadence.
- Fix: the TTS terminal only updated when the page was reloaded or the tab re-entered.
  The terminal-to-feed mapping existed in both `showTsub` and `liveRefresh` and only the
  first was updated; both now call one `refreshCurTerm()`.
- Fix: `Write start-tts.bat` wrote to `outputDir` rather than `launcherDir`. outputDir is
  seeded with a default and only mirrors launcherDir on save, so on a config where the two
  disagree the file landed in a folder Folder Settings never showed. launcherDir now wins.
- Fix: the launcher folder viewer only listed `.ps1`, so the `start-tts.bat` the panel had
  just written was invisible from inside the panel. Viewer now lists both; the sweep and the
  Server Editor list stay `.ps1`-only, since a .bat is not a server launcher.
- Add: `gate.py` - the release gate from DEVELOPMENT.md section 8 as a runnable script
  (115 checks: encoding, version agreement, redaction, remote boundary, duplication, visual
  invariants, generated .bat rules, jsdom behaviour).

## v3.69 patch1-5
- Change: header markers evenly spaced; Fullscreen visible to remote viewers (it only
  affects the screen of whoever presses it), Remote Access and Profiles stay host-only.
- Add: addresses blurred until clicked, and re-blurred on clicking away, on Proxy Setup and
  Permissions > Remote Access. Reuses the existing click-to-reveal blur.
- Change: provider switch renamed to Show SkyrimNet sampler values.
- Fix: a remote reader of a log feed no longer receives file paths. Stripped on the host
  before sending, not hidden in the page; fails closed if masking throws.

## v3.69
- Add: Fullscreen marker in the header, using the browser's own full screen.
- Consolidates v3.68 and its thirteen patches.

## v3.68
- Add: host/client Live Network. Point Proxy Setup at another panel's address and the Client
  tab draws the same page from that machine's state. Pull, not push: it reads the read-only
  remote view the client already serves, on its own thread with a two second limit.
- Add: providers can be switched off again; a power button per provider card, green on, red
  off. A provider switched off keeps its port shut, which is what lets a second PC serve it.
- Add: the version in the header is a button - green on the newest release, pulsing yellow
  with Update available! when GitHub has a newer one. Tags compared as numbers.
- Change: install path and slot count left the header for the Servers page and Folder
  Settings; Remote Access, Profiles and the refresh interval state themselves in the header.
- Fix: SeverActions had a scroll in one emoji table and a wrench in a later one.
- Remembered across restarts: Remote Access, auto refresh, the launcher loaded into a server,
  the Server Editor's lock state, the profile in use and the Observer's recording state.

## v3.67
- Fix: the port probe used connect_ex on a socket with a timeout, which on Windows waits out
  the whole timeout and answers WSAEWOULDBLOCK instead of reporting a refusal. Every check
  cost its full timeout; connect() reports at once.
- Fix: identifying a .gguf opens it. That was done for every model on every scan and held
  only thirty seconds, so a folder of large models cost 25s repeatedly and server cards sat
  on "Model could not be loaded". Now indexed per file, held five minutes, warmed at startup.
- Add: every step of a state read is timed with the remainder named, in the debug report and
  in the error log for anything over half a second.
- Add: the panel says which file it is running - path, hash, size and date.
- Change: full window terminals cover the page; controls hide until the mouse moves and float
  over the text; each terminal has its own Adjust menu.

## v3.66
- Fix: the per-tab live-refresh rule existed in two drifted copies. One liveRefresh() now,
  copy count gated at build.
- Fix: a state event repainted only the server slots, so provider cards never updated live.
- Add: every event carries a sequence number echoed by the heartbeat; a dead stream is caught
  within about five seconds and the connection rebuilt.
- Change: provider colours match SkyrimNet's chips everywhere at once.

## v3.65

model filenames no longer reach a remote viewer.

- You were right, and it mattered: the server boxes in Live Network showed the
  gguf filename to anyone on the read-only view. The masking covered the copy of
  the model path kept beside each server, but a card carries its own copy under
  its parameters, and that is the one Live Network draws from - so the name was
  masked in one place and printed in another.
- The model, vision projector and draft paths on a card are all masked now. The
  numbers beside them - context size, layers, batch - are settings rather than
  names and stay visible, since they are what makes the graph worth looking at.
- This also means the Permission Tree was claiming something the code did not do.
  It said filenames are stripped; for the past several versions they were not.
  Checking that a claim on that page is true is the whole reason it is checked at
  build time, and this one slipped through because nothing tested the parameters.
  The build now feeds a fully populated server through the masking and fails if a
  filename, a path or a card serial survives anywhere in what a viewer receives.

## v3.64

sweep the launcher folder before you trust what is in it.

- Folder Settings has a Sweep launcher folder button. It reads every .ps1 there and
  reports anything that does not belong in a file whose only job is to start
  llama-server: running text as code, hidden or encoded commands, fetching things
  off the internet, loading code into memory, changing Windows Defender, making
  itself run at startup, editing the registry, reading credentials, deleting files
  in bulk, launching another program to run code, or hiding its own window. Each
  finding names the line and shows what was seen.
- Said plainly on the page and worth repeating: a clean sweep means nothing
  alarming was found, NOT that a file is safe. PowerShell can be written to hide
  what it does, and anyone setting out to get past a list of words will manage it.
  This catches mistakes and the obvious. Only run launchers you wrote or trust.
- Checked against both of the real launchers in use, which come back clean, and
  against a file that downloads and runs code, which does not.

## v3.63

the Permission Tree says what the app actually does now.

- That page is what someone reads to decide whether to trust the remote view, so a
  claim on it that is out of date is worse than no claim at all. Three had drifted
  since it was written.
- Added to the read-only side: Proxy Setup, SkyrimNet YAML and Provider Statistics
  are not offered there, and the statistics endpoint is not answered at all - a
  viewer cannot reach the figures even by asking directly. Also stated plainly that
  providers and their allocation are visible but read-only, which they always were.
- Added to the host side: saving, loading and deleting profiles, which are now files
  in the profiles folder, and Provider Statistics with its monitoring switch.
- The setup flow is called the Main Guide, not the Helper, and sampler parameters
  can now be reset as well as edited. Both said correctly.
- Every claim on the remote side was checked against the code that enforces it
  rather than taken on trust.

## v3.62

two real faults from the code sweep, and a privacy pass.

- The guide's side note never eased its shadow. Two rules set a transition on it and
  the later one replaced the earlier outright rather than adding to it, so only the
  opacity was animated and the shadow snapped. Both are named in the rule that wins.
- Hint text ignored every theme. A hardcoded grey in a later rule was beating the
  theme's own colour, so on a light theme the hints stayed dark-theme grey. The
  theme colour wins now, and hints follow the theme like everything else.
- A comment describing the step list had been pasted a second time above the step
  descriptions, where it described nothing. Removed.
- Left alone deliberately: seven further cases of a rule setting a property twice.
  In each the later rule is a deliberate override and the earlier value is simply
  unused - removing them changes nothing on screen and risks more than it gains.
Privacy:
- Swept every shipped file for machine names, model names, IP addresses, GPU serial
  numbers, personal folder paths, credentials and email addresses. Nothing personal
  is in the release.
- One change from it: working out which network card would be used was done by
  asking the system for a route to Google's DNS server. Nothing was ever sent - a
  datagram connect only asks the question - but naming a real third party's address
  reads like an outbound call to anyone auditing the file, which cuts against the
  promise that there are none. It now asks about an address reserved for
  documentation that is never routed anywhere. Same answer, nobody else's address.

## v3.61

one button for clearing forced sampler values, not two.

- Beside Restore default providers there is now Reset all sampler parameters. It
  clears every value forced on every provider and nothing else - names, ports,
  priorities, thinking and sampler sources are all left alone, and each parameter
  falls back to whatever SkyrimNet or the server sends. It says how many providers
  carry forced values and asks before clearing, and does nothing if none do.
- The per-provider button added in the last version has been taken out again: each
  slot already carries Revert Params, which does exactly that job, and a second
  button beside it was only duplication.

## v3.60

clearing forced sampler values, one provider or all of them.

- Each provider carries a Reset sampler parameters button at the right of its
  heading. It clears every value forced on that provider and nothing else - the
  name, port, priority, thinking and sampler source are all left as they are, and
  each parameter falls back to whatever SkyrimNet or the server sends.
- Beside Restore default providers there is now Reset all sampler parameters,
  which does the same for every provider at once. It says how many carry forced
  values and asks before clearing them, and does nothing if none do.
- Both are host-only, so a read-only viewer is not offered them.

## v3.59

Restore really restores, the picker keeps its choice, and the arcs behave.

- Restore default providers put back a provider's name, priority and thinking, but
  left everything else exactly as it was: forced sampler values, which side decides
  the sampling, the detect switch and the icon all survived. A restored provider is
  now the provider the app ships - nothing forced, sampling decided server side,
  detect off, and its own icon back.
- Choosing a launcher in the Server Editor loaded it, but the list was rebuilt with
  nothing marked, so it fell back to its placeholder on the next redraw and looked
  as though the choice had been lost. It remembers which one you picked.
- The Launch button's arcs are drawn outside the button, and were passing in front
  of the fleet terminal button beside it, cutting into its glow. That button now
  sits on its own layer, so the arcs pass behind it and its light stays whole.

## v3.58

statistics stay host-side, and typing no longer freezes the animations.

- Reverted: a read-only viewer cannot ask the panel for the statistics again, and
  the Provider Statistics page is not offered in that view at all. If it happened
  to be showing when the view opened, it moves to the providers list.
- The animations stopped whenever a text field had focus. That guard was added to
  stop effects disturbing an open menu, and a focused field was swept in with it -
  but the effects only ever draw inside their own button and cannot reach a field,
  and what actually protects something being typed into is the separate guard that
  holds a redraw back. The guard still stands the effects down for an open menu, a
  dropdown, a slider or a dialog, which is what it was for.

## v3.57

a remote viewer can see the statistics that are already being kept.

- Monitoring was never off. A read-only viewer was not allowed to ask for the
  figures at all, so the page received nothing and its header fell back to saying
  monitoring was off - while the host had it on the whole time and was recording
  normally.
- Reading the figures changes nothing on the host, so a viewer may now ask for
  them. Resetting them still cannot be done remotely, and the Monitoring and
  Reset buttons are no longer shown there; a viewer sees whether monitoring is on
  instead of two buttons that would only be refused.

## v3.56

a viewer stays put, and every sampler value has somewhere to come from.

- The read-only view sent a viewer to the terminals on every refresh, not just
  when it opened - so any new terminal row dragged them off whatever they were
  reading. That is why it happened whenever a model generated something. A viewer
  is placed there once now, and moved only if they are somewhere they cannot be.
- The buttons across the top have more room between them.
- A provider only ever showed what SkyrimNet put in the request. Anything the
  request leaves out - min_p and DRY among them - is decided by the server itself,
  so those stayed blank however many requests went through. The server's own
  values, which the panel already reads out of the server log, now fill those in.
  A value that came in on the request still reads green; one taken from the
  server reads plain, so the two are not confused; and one that nobody states
  stays grey.

## v3.55

the launch count keeps up, and a read-only view says so.

- The count beside Running was worked out only when the button changed state, so
  it froze at whatever it was the moment the first server answered - hence 1/3
  while three were up. It is worked out on every pass now and the label follows
  as each server arrives, with the fleet terminal noting the progress rather than
  declaring a failure the moment the first one lands.
Remote view:
- Proxy Setup and SkyrimNet YAML are host business and are no longer offered. If
  one of them was showing when the view opened, it moves to the terminal instead.
  Provider Statistics stays available.
- Every refusal now says the same thing once, wherever it came from. Some actions
  refused silently before - changing a sampler value, or moving a box in Live
  Network - so they simply appeared to do nothing.
- Still to do: the page can still jump back to what it was showing after a refused
  action. That is the calling code redrawing on failure rather than the refusal
  itself, and it needs the callers gone through one at a time. Say if it is
  getting in the way and I will take that next.

## v3.54

the reasoning flags are known, and the rest of that launcher checks out.

- --reasoning-budget-message and --reasoning-format are real llama-server options
  and are now recognised, along with a few others in the same family that had not
  come up yet: --chat-template-file, --special, --poll, --slots, --no-warmup and
  --override-kv.
- Every value the panel takes off that launcher was checked against the file
  itself rather than trusted: model, vision projector, draft model, port, context,
  layers, batch and micro-batch, parallel slots, threads, generation cap, flash
  attention, auto-fit, mmap and continuous batching. All correct, thinking read as
  on, and nothing in the file is unrecognised any more.

## v3.53

profiles are files, the button counts, and only drafters look right.

Profiles:
- A profile is a file of its own in a profiles folder beside the panel, so one can
  be copied, kept or handed to someone else without carrying the whole config.
  Anything already stored inside the config is moved out the first time a profile
  is saved, loaded or deleted, so nothing is lost.
Launch button:
- The arcs were dim because the whole button was dimmed while it worked, and the
  arcs are drawn inside it. Only the letters are dimmed now, so it still reads as
  busy while the arcs keep their full light and hold it.
- It says how many servers came up out of how many were meant to - Running (3/3),
  or (2/3) if one did not start. A server counts as expected once it has a model
  to load and a provider pointed at it. The same is written to the fleet terminal
  when the count settles.
Server cards and Launcher Creator:
- Only a real draft model reads as suitable in the speculative decoding picker.
  An ordinary model shows red there now, the same as a projector does.

## v3.52

Launch stops asking for a step you have already covered.

- The rule about the side step standing in for the two yaml steps was written out
  in a fourth place I had not found: the check behind the Launch button. That
  copy let it stand in for only one of the two, so Launch went on asking for the
  other even while the guide and the completion check both said it was done.
- Every place that asks now goes through the one rule. There is a single
  statement of it in the file and nothing else spells it out.
- Worth saying plainly: this is the third version in a row where the same fault
  came back somewhere else. Each time it was another copy of a rule that should
  only have been written once. The build now counts them, so a fifth copy cannot
  appear quietly.

## v3.51

the Gamemaster moves up, the button reacts, and sampler values arrive live.

Recommended Setup:
- The Gamemaster writes for the player too, so it takes the large model alongside
  the talking providers - but at normal priority, behind the ones a person is
  waiting on directly and ahead of Meta.
- Charbio, IntelEngine and SeverActions start with thinking on, since all three
  reason before they answer.
Launch button:
- While the fleet is coming up, every arc is drawn at full strength.
- Once it is running, the arcs hold their light for their whole life rather than
  fading in and out. Both are said with a class on the button, so the drawing
  code itself is untouched.
Provider slots:
- The proxy learns a provider's sampler values from the request it has just
  carried, but nothing told the page, so those numbers only appeared once
  something else caused a redraw. It says so now, and only when the numbers have
  actually changed, so a busy fleet does not flood the page with announcements.

## v3.50

the recommendation sets priorities, and the font list is honest.

Recommended Setup:
- It now sets each provider's priority as well as its place. The ones a person is
  waiting on - Dialogue, Combat, the translator and the assistant - go to the
  front. Meta drops to the back when it has ended up sharing a card with them, so
  it cannot get in their way; on a card of its own it stays in the middle.
Terminal fonts:
- Nothing can be done to make those fonts line up, and it is worth saying plainly
  why. The terminals line their columns up with spaces, which only works when
  every character is the same width. Plus Jakarta Sans and Inter vary their
  widths, so the columns cannot hold whatever else is changed.
- The picker now says so before you choose: the five fixed-width fonts are marked
  in green, and the rest are marked in amber and say the columns will not line
  up. They are all still there to choose - the terminals just read better in one
  of the first five.

## v3.49

the guide agreed with itself, and the graphs answer properly.

Main Guide:
- There were two lists of what each step requires: the steps, and a second copy
  used by the completion check that claimed to mirror them. It had drifted - two
  of its entries were from a step list that no longer exists - so the guide and
  the check disagreed. The copy is gone; there is one list and the check asks it.
- That is why the side step went green while the yaml step was still being asked
  for: the box colour and the requirement behind it were reading different rules.
  Both read the same one now, stated in a single place.
- The guide keeps itself honest while it is open. Servers come up a few seconds
  after Launch and nothing was asking again, so the launched step only turned
  green if something else happened to redraw the page.
Provider Statistics:
- The graphs asked for their hover notes with a title inside the drawing, which
  is the browser's own box - a different thing from the attribute the panel lifts
  off everything else, which is why those alone were still the old style. They
  ask the same way as the rest of the panel now.
- Clicking an emoji reports how fast prefill and decode ran, in tokens per
  second, alongside how long each took.
- That panel draws no line, and carries the same soft dark glow as everything
  else.

## v3.48

Recommended Setup places providers by what they do.

- It used to sort providers into three priority tiers and spread them about. It
  now reasons the way you described. Vision needs a server that actually has a
  vision projector loaded, so that pairing is made first and is not negotiable.
  Dialogue, Combat, the translator and the assistant all produce words a person
  reads, so they take the largest model, and that model takes the strongest card.
  Meta is short and constant, so it goes to the smallest model. Everything else
  is utility work nobody is waiting on, and goes to the next largest model, which
  by then is on a different card.
- Servers are ranked by the size of the model file they are pointed at, and the
  biggest gets the strongest card. The summary says what went where and why.
Launcher Creator:
- Its model pickers still chose vision files by looking for "mmproj" in the name.
  They use what the panel reads out of each file now, and mark which files belong
  in which picker, exactly as the server cards do.
Main Guide:
- The side step about setting providers up by hand was attached to Live Network.
  It belongs to the two yaml steps and is attached to those, by name rather than
  by position, so inserting a step cannot move it again.

## v3.47

a launcher that names its model through a variable is read properly.

- Your launcher sets $modelPath at the top and writes "-m", $modelPath further
  down. The panel only ever looked for a path written out at the flag itself, so
  it found no model and the server had nothing to load. Any value a launcher sets
  up first and refers to later is now followed back to where it was set, for
  every flag rather than the model alone.
- Four flags it uses were unrecognised and are now known: --no-mmproj,
  --cache-reuse, --no-context-shift and --swa-full. Validate reports nothing
  unrecognised in your launcher now, and the card reads its model, port, context,
  layers, batching, threads, generation cap and every switch correctly.
- The folder warning cleared only if you typed the path. Choosing a folder with
  the picker goes down a different route, which redrew the fields and wired them
  up again but never asked about them. Both routes re-check now, and so does
  simply opening the Folder Settings page.

## v3.46

fewer notes, and the yaml one says where the file goes.

- Gone from Proxy Setup: the paragraph about where GPUs, servers and providers
  live, and the line about what the addresses do to the proxy.
- Gone from Launcher Creator: the note about which template to pick for one card
  or several, and the note about clicking samplers.
- The SkyrimNet YAML note has moved off the button row to the bottom of the
  panel, where the rest of the explanation is, and now spells out the whole path
  the file belongs at, starting from the modlist folder. The password and the
  path are picked out in blue with a soft blue glow, so the two things you
  actually need to read are the two things that stand out.

## v3.45

Restore default providers repairs, rather than duplicates.

- The button rebuilt the provider list on each server from the factory list, but
  it never looked at the providers sitting unallocated. Those survived untouched,
  so every press left you with the originals plus a fresh set attached to servers
  - the same names, the same ports, twice over.
- It now finds each provider wherever it already is, allocated or not, matches it
  to its factory entry by port, and puts its name and settings back in place. It
  is left exactly where it was: this repairs providers, it does not reorganise
  them, and nothing is attached to a server on your behalf. Only a default that
  has gone missing entirely is recreated, and it arrives unallocated.
- Providers you added yourself are not touched.
- Checked by pressing it twice: thirteen providers before, thirteen after, none
  allocated, no port appearing more than once.

## v3.44

blank dropdowns, tidier IP list, and the model field says it is required.

- The Size and Font dropdowns came up empty until clicked. Those two are filled
  with their choices after they are put on the page, so the replacement control
  was drawn from a list that was still empty, and only a click made it look
  again. Every control is now brought back into step whenever the page changes -
  except one that is open, which must not be rebuilt under your hand.
- The detected addresses disappear once you take one. They are a list of choices;
  after the choice is made they are only noise.
- The Model field on a server card carries the same Mandatory marker the required
  folders do, since a server cannot run without one.

## v3.43

a folder warning clears as soon as the folder is right.

- Saving a path redraws the fields, which throws away the elements the check was
  listening to, and nothing asked again afterwards - so whatever message was on
  screen stayed there until the page was reloaded, even once the folder held
  exactly what it was complaining about.
- Every folder is now re-checked the moment a path is saved, and the fields are
  listened to again after the redraw. The check also runs when a field is left or
  Enter is pressed, not only while typing.
- Checked by pointing the models folder at an empty one and then at one holding a
  model: the warning appears and then clears on its own.

## v3.42

the hover glow is quicker, and no longer flickers.

- You were right that a border was coming back on top of the glow. A shadow can
  only fade into another one that has the same number of layers: at rest a field
  had one, and on hover it had two - a soft glow with a hard ring added in front
  of it. The extra layer cannot be faded in, so it appeared outright partway
  through, which is the thickening and thinning you saw, and that ring is the
  line itself.
- Hover and focus are a single glow now, matching rest layer for layer, so the
  light simply grows and fades with nothing appearing on top of it.
- Twice as quick: half a second instead of a whole one, on both the fields and
  the dropdowns.
- The build now checks that a resting state and its hover state have the same
  number of shadow layers, so a mismatch that would flicker cannot ship.

## v3.41

the lines you were seeing were not borders at all.

- Last version removed every border and I told you the page was clean. It was, of
  borders - but what you were looking at was a one-pixel ring drawn as a shadow,
  which is a different property entirely and my check never looked at it. A ring
  of no offset and no blur is a line whatever it is called and whatever colour it
  is given, black included.
- Every one of those was listed, and at rest none of them carry a ring now: cards,
  server cards, panels, log panes, fields, the editor, the theme swatches and the
  dropdowns are all left with the soft dark halo alone.
- Hover, focus and open states keep their ring, since that is what tells you a
  thing is live under your hand. Buttons, switches, table header rows and the
  guide's status boxes are untouched, as are the flashes that mark an error or a
  jump - in those the ring is the whole point of the effect.
- My first attempt at this rewrote the stylesheet while reading it and corrupted
  several rules; it was thrown away and done again in one pass. The keyframes it
  had damaged were restored from before the change.

## v3.40

no lines left, except where you asked for them.

- Every border in the panel was listed first, then dealt with one at a time
  rather than swept away by a blanket rule.
- Fields that had a line - the inline editor, the token box, the guide's value
  pills, the error text box - now carry a dark ring and a soft dark halo instead.
  The dropdowns carry the same at rest. Hover and focus are written in their own
  rules and were not touched, so reaching for any of them still lights it up.
- Chips, badges, table rows, the code gutter and the banner simply lost the line;
  nothing took its place.
- Left as they were, by your list: buttons, the header row of a table, and the
  toggle switches. Three more were left alone on judgement, and are worth a look:
  the small triangle on a dropdown is drawn out of borders and would vanish
  entirely; the dotted underline marking a reference in the guide is what shows
  it can be clicked; and the coloured bar down the left of the SkyrimNet and
  fleet notes marks which is which rather than framing anything. Say the word on
  any of the three and they go.
- Checked by walking every element on the page and reading what it actually
  draws: nothing outside that list draws a line.

## v3.39

the grey line was mine, and the widths are measured now.

- The line around an open dropdown was not the browser's after all - it was a
  one-pixel light ring I drew myself as a shadow when building the replacement,
  and my own check looked only for a border, so a ring drawn as a shadow went
  straight past it. The list now carries the same quiet dark glow the cards use
  and nothing else. The check looks for a hard ring however it is drawn.
- The widths were wrong because I gave every stand-in a 260 pixel minimum, which
  overrode the narrower widths the rules had already worked out for particular
  fields - the provider icon dropdown among them. Each stand-in now takes the
  width its own select was given, read from that field before it is tucked away,
  so nothing is imposed on it.

## v3.38

the new dropdowns look right, and the guide arrows point properly.

- I built the replacement dropdown out of a button, which was the wrong element
  for this panel. Buttons here are deliberately transparent and glow on hover,
  and that is set with !important, so the control could never carry a field
  background however it was styled - hence no background, a stray outline and the
  wrong hover. It is built from a plain element now and takes the styling as
  written: field background, no frame anywhere, the field's own quiet glow.
- The widths were wrong because the rules that size these fields are written
  against the classes the select carries, and the stand-in did not carry them.
  It does now, so each dropdown is the width it was before.
Main Guide:
- The rows of the guide alternate direction, but an arrow was always drawn from
  the right edge of one box to the left edge of the next. On the second row,
  which runs right to left, that meant starting past the box it was leaving and
  ending past the one it pointed at. Each arrow now leaves by whichever edge
  faces the next box.

## v3.37

the grey frame on open dropdowns is gone.

- You asked three times and I explained twice that the frame around an open
  dropdown is drawn by the browser and cannot be styled. That was true, and it
  was the wrong answer: the way to be rid of it is to stop using the browser's
  dropdown, which is what this version does.
- Every dropdown in the panel now opens a list the page draws itself, with no
  frame, the same background as everything else, and the colours already used to
  mark which model files fit a picker carried through onto each line.
- The real select is still there behind it, hidden, holding the value and still
  announcing every change - so everything already written against those
  dropdowns carries on working untouched. Checked by using one: the value
  changes, exactly one change is announced, and the label follows.
- While a list is open the animated effects stand aside and the page will not
  redraw, the same courtesy the menus already get.

## v3.36

Validate works, and the folder button is back where it was.

- The Validate button did nothing because its handler was put in the wrong place -
  among the listeners that watch for errors rather than the one that handles button
  presses. It sits with the other editor buttons now, and the report appears below
  the editor when pressed.
- Last version added an Open folder button to the llama.cpp row to even up the box
  lengths. That was wrong twice over: the button had nothing behind it, since the
  folder viewer lists files by extension and there is no listing defined for a
  folder of executables, so pressing it only ever raised "This folder has no
  viewer". The exception was there for a reason and it is back. The row now holds
  the space open instead, so the boxes still line up, and any folder without a
  viewer is handled the same way without further thought.

## v3.35

an even row, and a launcher you can read before choosing a model.

Folder Settings:
- The llama.cpp box was longer than the others because its row was the only one
  without an Open folder button, so the box stretched into the space the other
  rows give up. It is a folder like the rest, and being able to open it to check
  llama-server.exe is really there is useful, so it has the same button now and
  the boxes line up by themselves rather than by a measurement.
Server Editor:
- A server with no model chosen yet showed nothing but a message telling you to
  go and choose one. Every other setting was already decided, so there was a
  launcher worth reading. It is shown now, with the model line reading <no model
  chosen yet> and a note above saying it is a preview. Nothing is saved and
  nothing is launched from it.

## v3.34

reading a .gguf properly, and pickers that show what fits.

The fault you caught:
- Last version claimed to identify a drafter by its contents. It did not. A .gguf
  header holds the tokenizer as a list of a few hundred thousand strings, and the
  reader stepped over only the first four thousand of them - a limit put there to
  avoid a long loop. That left it stranded in the middle of the list, so every
  tensor name after it was read as nonsense and nothing was ever found. The one
  case that appeared to work was matching on the filename, exactly what it was
  meant to replace.
- An array of any length is now stepped over by seeking past it, so the position
  is right whatever the vocabulary size. Tested against a header holding two
  hundred thousand tokenizer entries: a drafter with an ordinary filename is
  recognised, in a tenth of a second.
Models:
- A vision projector is recognised by its tensors as well, so one named nothing
  in particular is still known for what it is.
- Each picker now shows which files belong in it: green where the file fits, red
  where it does not, with what it actually is in brackets. A plain model offered
  as a drafter counts as fitting, since that is a normal thing to do. The two
  optional pickers say so underneath as well when the choice does not fit.

## v3.33

Validate, and a launcher read properly.

Server Editor:
- A Validate button, with a report below the editor. It reads every flag the way
  the panel will and says what it made of each: shown on the server card and with
  what value, understood and handed to llama-server unchanged, or not recognised.
  Sampling flags are listed apart, because the proxy sets sampling per request, so
  whatever a launcher says there is only a default and cannot stop a server.
Fixed, both found by reading your launcher:
- "--fit", "off" was turning auto-fit ON. Three settings are switches, and the
  parser treated them as present-or-absent, so spelling out "off" after one was
  read as the switch being there at all. An explicit off is now honoured.
- A draft model given as --spec-draft-model was not picked up: only the older
  --model-draft was known. Both are read now, and -md as well.
Models:
- A drafter can be recognised by what it is built from rather than what it is
  called. The panel reads the tensor names in a .gguf and treats one carrying
  multi-token-prediction tensors as a drafter, whatever its filename says. Names
  are still consulted, but only when the file itself says nothing.

## v3.32

the Debug tab watches the app run.

- Log > Debug Report records what the page actually does, in order, with the time
  each thing happened: what you pressed, which menu opened, every call to the
  server and how long it took, each redraw - and, just as important, everything
  that was held back and the reason for it. An effect standing down because a menu
  is open, a redraw refused because a parameter is being adjusted, a reload put
  off because a save has not come back yet.
- That last part is the point. Nearly everything that has gone wrong here was
  something happening at a moment it should have waited, so a line saying an
  effect stood down, and why, is worth more than a line saying it ran.
- The two guards that decide when to hold back now state their reason rather than
  answering yes or no, which is where those explanations come from.
- Recording is off by default and costs nothing while off. It keeps the last six
  hundred entries. Copy and Save put a short description of this build and setup
  at the top, so a trace you send says what it came from.

## v3.31

a debug report you can hand over.

- Log has a third tab, Debug Report. It writes about forty lines describing this
  build and this setup: the panel version and python, whether each folder is set
  and holds what it should, one or two PC mode and whether the IPs are filled in,
  the graphics cards by name and whether each is enabled, and for each server its
  port, what kind of model it is pointed at, whether it is on a card, whether its
  launcher was built, whether it is running, how many providers it has, and only
  those settings that differ from the default. Then the errors recorded this
  session, by kind, with the last twenty.
- It is written to be shared. There are no folder paths, no IP addresses, no
  graphics card serial numbers and no model filenames in it: a folder is reported
  as set or not, and a model as what kind of model it is. What matters in a bug
  report is the shape of a setup, not its contents.
- Copy puts it on the clipboard; Save writes it to a file. It is short enough to
  read before you send it.

## v3.30

the guide knows its steps by name.

- Adding a step last version moved every step after it, and seven places in the
  guide recognised a step by its position rather than by what it is. That is why
  step seven ran the Launch demonstration and jumped to Proxy Setup - it was
  reaching for the step that used to sit there. Each step now has a name of its
  own and the code asks for it by name, so inserting one can never point that
  code at the wrong step again.
- Step four no longer completes when the server is pointed at a vision projector
  or a draft model. A file the panel has not scanned still counts as usable, so
  an unusual path is never held against a server.
- The warning about the wrong kind of model appears the moment you choose it. The
  cards deliberately refuse to redraw while the pointer rests on a parameter, so
  sliders do not jump about - but choosing a model is a deliberate change, and
  the pointer is necessarily on that cell at the time, so it was waiting for
  something else to force a redraw. A change you made is now drawn at once.

## v3.29

a step for setting a server up, and the panel knows what a model is.

Main Guide:
- A step of its own between detecting the GPUs and wiring Live Network: get one
  server set up with a model. One is enough - any other servers can sit without a
  model until you want them.
- While adding it I found the list of explanations already had one entry more than
  there were steps: a leftover line about picking a model sat between the GPU step
  and Live Network, so every step from the fourth onward has been showing the
  explanation belonging to the step before it. That leftover is exactly the step
  being added back, so it has returned to its place and the two lists line up
  again - which also repairs steps five to eight.
Models:
- Every model file ends in .gguf, so nothing in the name reliably separates a chat
  model from a vision projector or a draft model. The panel now reads the header
  of each file, which states what it is, and only falls back to the name when the
  header says nothing useful. A file that cannot be read is never rejected.
- The model list marks projectors and draft models, and choosing one as the model
  a server runs says so plainly and points at the right dropdown instead.

## v3.28

the folder is down to what it needs.

- Four files are gone. StartPandorumLLM.bat only repeated what the exe
  does. stop-llm-stack.bat asked for administrator rights to stop a fleet
  that never runs with them - a leftover from an older design - and the
  script behind it was a second copy of shutdown logic that
  launch-llm-fleet.ps1 already does, and that the panel's Exit already
  uses. Two picture files were referenced by nothing, and a developer
  test file was being shipped to users by mistake.
- One batch file remains: force-stop.bat, for when the panel will not
  open or will not answer. It stops only what was started from its own
  folder, so a llama-server you run yourself elsewhere is untouched, and
  it needs no administrator rights.
- remove-windows-block.bat is gone too. The panel now clears Windows'
  downloaded-from-internet mark from its own folder when it starts, so
  SmartScreen only ever has to be answered once and there is no separate
  tool to run.

## v3.27

the fade away waits too, and switches stop flicking back.

- Holding back new effects was only half of it. The bolts already drawn were
  still being taken away on their own timers, and removing something from the
  page closes an open dropdown just as surely as adding something. A bolt now
  waits until you are finished before it disappears.
- A switch could still flick back and forth. The server announces every saved
  change, and the page reloaded on that announcement without checking whether
  anything was in progress: the switch showed its new position, the announcement
  arrived before the save had been read back, and the page drew the old position
  before drawing the new one. The reload now waits its turn instead.
- A ticked box holding focus no longer holds the whole page still - only typing
  does.
- The switch knob is centred by construction, but the track's inner shadow sat a
  pixel low, darkening its top edge and making a centred knob look high. The
  shadow is even now.

## v3.26

decoration is purely visual now.

- The animated effects were changing the page on their own timers regardless of
  what you were doing - bolts being added to the Launch button and taken away
  again, the terminal glyph being rewritten, several times a second. Any change
  to the page while a dropdown is open is enough for the browser to close it, so
  a menu could be dismissed by an effect that had nothing to do with it.
- Every animated effect now asks one question before it draws: with a menu open,
  a dropdown in use, a field focused or a dialog up, it skips its turn and
  changes nothing. Nothing an effect draws can be clicked either.
- Checked by opening a menu and firing the effects ten times: nothing was added
  to the page and the menu stayed open.

## v3.25

menus open again.

- My fault, and a bad one. Tidying away an unused variable in v3.23 removed the
  whole line it was written on, and three variables that are still very much in
  use were declared on that same line. Closing a menu therefore threw an error,
  and because opening a menu closes the others first, the error stopped the menu
  from ever opening. Every drop-out menu in the header was affected.
- The declaration is restored and all three menus are confirmed opening again.
- The build now loads the finished page in a real browser engine, presses each
  menu, and refuses to package if anything throws or a menu fails to open. A
  break of this kind cannot be shipped again without being noticed.
Switches:
- The knob sat a fixed distance from the top of its track, so it only looked
  centred at one exact track height. It is centred on the track itself now.

## v3.24

generated launchers are grouped by subject.

- A generated launcher listed every flag in one long run. That run was held
  together by line continuations, and a continued line cannot carry a comment, so
  there was no way to label anything within it.
- The flags are gathered into a named list instead, which needs no continuations
  and can be commented. Each group is headed: model files, server, GPU, context
  and cache, batching and concurrency, CPU, generation, logging. The command
  itself is one line at the end that hands the list to llama-server.
- The panel reads the same flag and value pairs out of it as before, so model,
  port and thinking detection are unchanged.

## v3.23

nothing is altered under the pointer any more.

- Hover notes worked by taking the title attribute off an element and every parent
  of it the moment the pointer arrived, then putting them all back as it left.
  Changing attributes under the pointer is enough for the browser to dismiss a
  dropdown you are in the middle of using - which is why a menu closed itself
  while you were clicking through it. The note text is now moved off title once,
  when an element is drawn, so nothing on the page is touched while you interact
  with it.
Server Editor:
- The editor could come up empty. It filled the text box it had found before
  asking the server for the launcher, and with auto refresh running the page was
  often redrawn while it waited - so it filled a box that was no longer on screen.
  It now looks the box up again after the answer arrives.

## v3.22

warnings sit under the box they are about.

Folder Settings:
- A folder warning was being added to the block of extra material that follows a
  field, so the llama.cpp one appeared below the update-check panel rather than
  below its own box. Each warning is now placed directly beneath the box it
  refers to, ahead of anything else.
User Guide:
- The Setup Helper heading is a fifth larger, with the buttons set clear of it.
Customization:
- Theme Presets is a fifth larger, and the two explanatory lines are gone.

## v3.21

auto refresh stays out of your way.

- You found it: the refresh redrew the page on a timer regardless of what was
  happening. Flicking a switch showed it on straight away, the refresh then drew
  the state the server still had - off, because the save had not landed yet - and
  the save landing drew it on again. That is the on, off, on you saw, and the same
  cause behind menus closing and edits being interrupted.
- Every write is now counted while it is in the air, and a refresh is skipped
  while one is outstanding, or while a menu or dialog is open, a field is being
  typed in, a slider is being used, or something is being dragged. It simply
  catches up on the next tick, so nothing is lost.
Server cards:
- The slider panel sits on the middle of its value box rather than its right edge.
Proxy:
- The green note about entering both IPs is gone.

## v3.20

the models and launcher folders are checked too.

- Only the llama.cpp folder was ever checked - the folder check looked for
  llama-server.exe and nothing else, so the other two had nothing to report no
  matter what you pointed them at.
- The models folder now warns in red when it holds no .gguf files. It looks a
  couple of levels down as well, since models are usually filed in a folder of
  their own, and stops at the first one it finds rather than reading the whole
  drive.
- The launcher folder warns in yellow when it holds no .ps1 launchers yet, which
  is a normal state before you have made any rather than a mistake.

## v3.19

the Permission Tree lines up.

- Text in each box sits on the middle of that box both ways. It had been placed a
  fixed distance in from the top-left corner, so it drifted with the size of the
  box it was in.
- The joining lines meet each box on its own centre. The two outer branches were
  drawn thirty units to the side of the boxes they connect, which is why they ran
  into the corners rather than the middle.

## v3.18

everything in a row sits on the middle of it.

- Rows were lining up on the baseline of their text, and a second rule then
  re-centred only the buttons and fields inside them. So a control sat centred
  while the label beside it sat on the baseline, and the two disagreed by however
  much their sizes differed - which is why some pages looked right and others did
  not.
- Every row centres now, and the rule that singled out controls is gone. The
  three places that asked for baseline of their own - the statistics header,
  server cards and provider slots - follow the same rule as everything else, so
  there is one behaviour across the whole interface.

## v3.17

folder paths save themselves.

Folder Settings:
- There is no Save settings button. A path is saved when you leave the field or
  press enter, and only if it actually changed. The warning about an unsaved path
  and the first-run line telling you to press save are both gone with it.
Launcher:
- The base template view in the Creator can be dragged taller instead of sitting
  at a fixed height.
Permissions:
- The Permission Tree's frame carries no glow of its own.

## v3.16

your llama.cpp build number is read correctly now.

- Check for update could fetch the newest release but never your own build, so it
  always fell back to asking you to compare by eye. llama-server reports itself as
  "version: 10107 (commit)", while the code was only looking for "build: 10107" or
  a "b10107" tag - neither of which it ever prints. All three forms are accepted
  now, so the comparison works.
- llama-server is also asked from its own folder, since on Windows it needs the
  CUDA libraries sitting beside it in order to start and answer at all.
Folder Settings:
- The note about closing the last browser tab is gone, as is the line beside Save
  settings. The button itself is unchanged.

## v3.15

button rows line up with the page.

- A row of buttons sitting straight on a page was lining up by the edge of the
  first button rather than by its text, so it sat sixteen pixels - one button's
  padding - to the right of everything else on that page. It is pulled back by
  exactly that, on every page. Rows inside a panel are untouched, since there a
  button should line up with the panel it is in.
- The Permissions page has no heading or description above its two buttons.

## v3.14

the highlight grows out of the glow already there.

- Highlighting something that already had a glow took that glow away for the two
  seconds it ran and handed it back at the end, which is the snap out and back.
  An animation replaces a property outright rather than adding to it, so the
  amber was arriving instead of the resting glow rather than on top of it.
- Each thing that has a resting glow now names it, and the highlight lays the
  amber over that name. The resting glow stays put the whole time while the amber
  rises and falls on top, so it grows out of what was there and settles back into
  it. Anything with no resting glow contributes nothing, so it behaves as before.

## v3.13

the symbol is part of the heading now, not a separate piece.

- You were right that the two were in different places. The symbol carried a glow
  of its own with no easing on it, while the words eased over about a seventh of a
  second - so on hover the symbol always arrived first. They were two effects on
  two elements pretending to be one.
- A heading is now lit as a single thing: one glow, applied to the whole heading,
  covering the symbol and the words together. Nothing targets the symbol on its
  own any more, so the two cannot differ or fall out of step.
- The small drop and lift on the symbol was a transform I had added to steady the
  highlight. Making and unmaking that layer nudged the heading. It is gone; the
  same steadying is asked for in a way that moves nothing.

## v3.12

the highlight is a glow, with no border in it.

- The highlight was drawing a solid ring. A shadow with no blur is a border
  however it is written, and mine began with one - which is the orange outline
  that appeared around everything it touched. Both glows now blur, with no ring
  at all.
- A heading's glow follows the letters and the symbol rather than boxing them, so
  steps three and four no longer draw a rectangle around the title.
- That glow is applied to the heading as a finished picture rather than making the
  browser redraw the artwork on every frame, which is what made the symbol
  shimmer. The symbol and title still light as one, since it is one glow on one
  element.

## v3.11

the guide highlight rebuilt from scratch.

Why it kept breaking:
- The highlight had grown into six rules pulling in different directions - one for
  words, one for edges, one that recoloured a symbol, each with its own timing.
  Every fix to one of them broke another, because they were separate effects
  being asked to look like a single one.
The rebuild:
- All of it is gone, replaced by one rule. The highlight is drawn around whatever
  a step points at and touches nothing inside it, so a folder field, a panel and
  a heading all light exactly the same way. Nothing is recoloured, so no text in a
  field can light up by accident, and no artwork is redrawn, so nothing shimmers.
- A heading's symbol and title can no longer fall out of step with each other,
  because they are lit as one element rather than as two effects.
The headings:
- PC GPUs and Live Network were built differently - different symbol sizes, and a
  vertical nudge on each symbol that does nothing in a row layout. Both now use
  one shared shape: symbol and title on one line, evenly spaced, same size.

## v3.10

the field text stops glowing, the symbols glow again.

- The symbol highlight works by recolouring, and it was being applied to every
  step target - so a highlighted text field had its own text recoloured, which is
  the glowing text in the box. It now only goes to the two headings that actually
  have a symbol, and only if one is found there.
- Those symbols carry a real glow again, not just a colour. The glow is switched
  on and off rather than eased, because a filter that changes over time is what
  re-draws the artwork every frame and makes it shimmer; switched once at each
  end there is nothing to shimmer, and the colour easing either side carries the
  softness.

## v3.09

step 1 lights the field again, not the words in it.

- Splitting the highlight in v3.03 into one version for words and one for edges
  left the edge version matching only a field sitting inside the highlighted
  element. Step 1 points straight at the folder fields themselves, so they fell
  through to the words version and lit their own text instead of their edge.
- The edge version now matches the element itself as well as one inside it, and a
  field lit that way no longer glows its text at the same time. Panels and fields
  take an edge; the two headings still light their words and symbol.

## v3.08

no more shimmer on the highlighted symbol.

- The flicker was never about where the glow was applied - it was the glow itself.
  A filter that changes over time makes the browser re-draw the artwork on every
  frame, and fine strokes land on slightly different pixels each time. Moving it
  from the heading to the symbol in v3.03, and fixing its timing in v3.07, left
  that untouched.
- Both symbols take their colour from the heading they sit in, so the highlight
  now simply changes that colour and eases it back. A colour change needs no
  redraw, so there is nothing left to shimmer, and the symbol still keeps step
  with the words.

## v3.07

the symbol highlight finally keeps step with the words.

- The glow on a heading's symbol vanished rather than fading, and arrived out of
  step with the words. Two causes. The fade was declared on the same class as the
  glow, so taking the class away took the fade with it and the glow simply
  switched off. And the timings did not match: the words rise to a peak at one
  second and are gone by two, while the symbol reached full in seven tenths and
  only started leaving at two.
- The fade now lives on the heading itself, so it survives the class being
  removed, and the symbol's glow is held for exactly one second. Both reach full
  together and clear together.
Live Network:
- The hover glow on a box is much softer.

## v3.06

a slight glow, text centred by construction.

- The provider colour is a faint outline and a soft halo rather than the solid
  ring and wide glow of the last version.
- Their text is centred by giving the box equal padding above and below and
  letting its height follow the text, instead of fixing a height and asking the
  browser to centre within it. Nothing is computed, so nothing can drift.
- The drop area shows no glow while dragging.

## v3.05

provider colours written onto the boxes themselves.

- The colour each provider is given has been reaching the box correctly for
  several versions, but the glow built from it kept losing somewhere among the
  rules that also style those boxes. It is now written straight onto the box, so
  nothing can outrank it. Hovering still brightens it.
- The port sits in the row rather than being placed by hand, so the name and the
  port share the middle of the box instead of drifting to the top.
- The drop area's glow while dragging was far too strong. It is a quiet edge now.

## v3.04

the white dropdown list explained, provider colours back.

Fixes:
- The list that drops out of a dropdown was white with a grey frame. That list is
  drawn by the browser rather than by the page, and it follows the system theme
  unless the page says which it prefers. The page never did, so it was being
  drawn light no matter how the options themselves were coloured. It now declares
  a dark preference, which the browser applies to its own controls.
- Provider boxes name their own glow rather than inheriting it, so the colour
  each provider is given in the terminals shows on its box again, and their text
  sits on the middle of the box rather than near the top.
- The dashed outline around the drop area while dragging is gone, replaced by a
  glow like everything else.

## v3.03

the flickering symbol, properly this time.

- Highlighting a heading made its symbol shimmer while the words were fine. The
  cause was animating a filter on the element that holds them both: doing that
  forces everything inside it to be redrawn on every frame, and fine vector
  strokes land slightly differently each time, which is the flicker. Matching the
  keyframe values in v2.91 cured an abrupt jump but never this.
- Nothing animates a filter over a symbol any more. Words glow through their own
  shadow, fields and panels through an edge, and the symbol eases between two
  fixed states with a transition - drawn once rather than every frame.
- The Live Network status pane has no border, just the usual black glow.

## v3.02

provider boxes pinned thin, slider panels fade out.

Live Network:
- Provider boxes have a set height rather than one worked out from the text
  inside them. Trimming their padding never quite settled it because the line the
  text sits on was deciding the height; it is fixed at 24 pixels now.
- Their colour reads properly again: the glow is wider and no longer pulled in
  behind the edge of the box.
Server cards:
- The slider panel fades out quickly after half a second instead of blinking off.
Fields:
- No dropdown declares a border of its own any more.

## v3.01

notes keep out of the way, and two stubborn borders finally go.

Fixes:
- Hover notes were closing dropdowns. On arriving at an element the code strips
  the title off it and every parent, so the browser does not draw its own box on
  top - and changing the page like that while a dropdown is open is enough to
  dismiss it. Nothing is touched now while anything is open: a drop-out panel, a
  slider, the guide's side note, a dialog, or a dropdown you are choosing from.
  A note already waiting is dropped if something opens, and opening a panel takes
  down a note already showing.
- The border on the provider slots really was still there, sitting after the glow
  in the same rule, which is why passes that only looked at the glow kept missing
  it. The Permission Tree's frame was a style written onto the drawing itself, so
  no stylesheet change could ever have removed it. Both are gone, replaced by the
  same soft glow as everything else.

## v3.00

dropdowns behave, preset glow restored.

Fixes:
- Opening a dropdown turned it white. A blend mode applies to the whole control,
  and the list the browser draws is part of that control, so asking the closed
  label to invert against the panel behind it inverted the open list as well.
  Only text can follow a backdrop, so every dropdown now keeps one fixed
  background - the same one everywhere in the app, for the control and its list
  alike - and takes text chosen to contrast with it, exactly like the text boxes.
- The glow on the theme presets had gone. Preset cards are cards inside a card,
  and the rule that flattens a nested panel came later in the stylesheet at equal
  weight, so it won and stripped them. Presets are now exempt.

## v2.99

glows without the hard edge.

- What still looked like a border on the provider slots was the glow itself. It
  began with a solid one pixel ring at zero spread, which is a border by another
  name. That ring is gone from the provider slots and the permission tree; only
  the soft part remains.
- Boxes in the Permission Tree are edged by a glow in their own colour instead of
  a line - green for host, blue for remote, red for denied.
- Statistics: the heading is gone and the monitoring and reset controls sit at the
  left in its place.

## v2.98

colour pickers follow the theme, fields pick readable ink.

Fixes:
- Choosing a preset in Customization left the swatches under Custom Colors
  showing the previous theme's colours. Applying a theme only set the underlying
  values; the pickers are ordinary colour inputs and had to be told as well.
  They now update the moment a preset is chosen.
Pop-up menus:
- Dropdowns on a see-through panel invert against what shows through, like the
  buttons beside them, including the closed dropdown and not only its list. The
  list itself keeps a solid pair of colours, since the system draws it.
- Text boxes keep their own background, so their text is chosen to contrast with
  that instead: the actual background is measured and light or dark ink picked to
  suit. A pale theme will no longer leave pale text on a pale field.

## v2.97

black glow everywhere borders used to be.

Panels:
- Server cards, provider slots and log file cards carry the black glow. They had
  been flattened by the rule that strips outlines from a panel inside a panel.
- The launcher editor, the guide's status pane and the permission tree have no
  borders; the first two carry the glow instead.
Live Network:
- Box colours are back as a glow rather than an outline, and a server that is not
  allocated to a GPU falls back to the black glow like everything else.
- Provider boxes are thinner again.

## v2.96

panels get their backgrounds back, with a black glow.

Appearance:
- The see-through panels are reverted. Every panel has its background again and
  is set off by a black glow rather than an accent one.
- A panel sitting inside another has no outline of its own, and neither does the
  strip that carries Add server or Add template.
Pop-up menus:
- The tint is darker while still letting the interface show through.
- Buttons on those menus invert against whatever shows through behind them, so
  they read as dark over a bright patch and light over a dark one.

## v2.95

panels lose their fill, and some lost styling comes back.

Appearance:
- Panels across every page no longer have a filled background. They are marked by
  a faint accent outline and a soft glow instead: Live Network, server cards,
  provider slots, the Launcher creator and inspector, and every other page that
  builds from the same panel.
- The Permission Tree's boxes have no border, just a faint edge in their own
  colour - green for host, blue for remote, red for denied.
Repair:
- The swirling glow on the logo had stopped because the animation behind it was
  gone. Tidying away one unused animation in v2.91 used a pattern that ran on
  past its target and removed 3.7 thousand characters: the brand glow, the whole
  stylesheet for the YAML editor, and the rule that blurs sensitive values on
  screen. All of it is restored. The build now refuses to package if anything
  asks for an animation that does not exist, which is what would have caught it.

## v2.94

one keypress, one step - and sliders on demand.

Fixes:
- Tapping an arrow key moved a slider twice. The continuous motion began on the
  very first frame of the press, so even a sixty millisecond tap got the single
  step plus one or two more from the ramp. Context length was the only one that
  behaved because its own ramp waits half a second. Every slider now waits three
  tenths of a second before it starts running, so a tap is exactly one step and
  holding still speeds up as before.
Server > Servers:
- The slider is no longer squeezed into the row. It drops out of a panel beneath
  the value box when you point at either, and waits a second after you leave so
  you can reach it. It is wider than it was, which makes it easier to aim.
Elsewhere:
- Pop-up panels blur at four pixels rather than six.

## v2.93

pop-up panels you can actually see through.

- The blur had been doing its job all along. At eighteen pixels it smeared the
  text behind into a smooth haze, which is what looked like a gradient rather
  than like glass, and the pale tint of the last version made that worse.
- The tint is dark again, as originally asked, and transparent enough that what
  sits behind survives it. The blur is down to six pixels, which softens what is
  behind instead of erasing it, so you can see the interface through the panel
  rather than a wash of colour.

## v2.92

the pop-up panels are frosted for real this time.

- Every attempt so far tinted the panels dark. On a near-black page that can
  never look translucent: a 42% dark tint over the background lands on RGB
  15,18,23, while an ordinary solid panel is 22,26,34 - a couple of points
  apart. The blur was working the whole time; there was simply nothing to give
  the layer away.
- The panels now use a light scrim instead, which is how frosted glass is done
  on a dark interface. It lifts wherever it sits and shifts with whatever is
  underneath, so text and cards show through it.
- Where a browser cannot frost at all, the panels fall back to a solid
  background rather than a washed-out film over sharp text.

## v2.91

the flashing symbol explained, and the glass finally looks like glass.

Fixes:
- The symbol beside a highlighted heading flashed instead of glowing. A list of
  filters only animates smoothly when every step of the animation has the same
  number of entries in it; this one went from one glow, to two, back to one, so
  the browser could not blend between them and jumped halfway through. The text
  never showed it because its own glow was blending smoothly and hid the jump.
  Every step now carries the same number, and the symbol's own glow stands down
  while the highlight runs, so both move as one.
- The frosted panels were being darkened as well as blurred, which made whatever
  sat behind them harder to see rather than easier - so they read as solid. They
  are lighter and more transparent now, with a stronger blur and no darkening, so
  the interface genuinely shows through.
- Pop-up panels have no border.
- The Profiles and auto refresh panels now hang from their own button rather than
  from whatever happened to be positioned above them.
User Guide:
- The manual-providers note fades away instead of vanishing, and waits two
  seconds rather than three.

## v2.90

quitting really does leave nothing behind.

Fixes:
- After quitting, a shell was often still running and kept a hold on the
  PandorumLLM folder, so it could not be deleted. Each server runs in its own
  shell window opened with -NoExit, so the window outlives the server inside it.
  Stopping the fleet only reaches windows whose port is still listening, which
  means a server that had already crashed or been stopped left its window behind.
  Quitting now also closes any leftover window, matched by the install folder in
  its command line so nothing else you have open is touched, and it reports how
  many it closed.
- Opening the terminal background menu again straight after choosing from it
  could fail. It opened on the click while every other menu opens on the press,
  and mixing the two lets one half of a press open a menu and the other half
  close it. Every menu now opens on the press.

## v2.89

the guide path is exact, and the side note waits for you.

User Guide > Main Guide:
- Each row of steps now starts directly beneath the step that ended the row
  above it and runs back the other way. Both the column and the row are pinned
  now; previously only the column was set and the browser chose the row, which
  could push a step onto a fresh line and leave a gap.
- The manual-providers note is joined by a single line from whichever of the two
  steps you are pointing at, rather than a line to each.
- It stays up for three seconds after you move off the step, so there is time to
  reach it and press its button, and it stays as long as you are on it.

## v2.88

the guide snakes, menus behave, panels look like glass.

User Guide > Main Guide:
- The steps now run left to right, then the next row runs back right to left,
  and so on. Each row begins under the end of the one above it, so the path
  never leaps across the whole width when the window changes size.
- The manual-providers note has left the layout. It appears while the pointer
  rests on step 5 or step 6 - the two steps it bypasses - with its arrows drawn
  to them, and stays while you move onto it.
Menus:
- Opening one drop-out menu now closes any other that is open. All of them close
  through one place, so this holds for Profiles, auto refresh, PC GPUs and the
  terminal background alike.
- The frosted panels really are frosted now. Blurring a flat background looks
  exactly like not blurring it, which is why they seemed unchanged; they now
  darken what is behind them as well as blurring it, and carry a faint light
  edge, so they read as glass over any part of the interface.

## v2.87

the setup diagram is part of the page now.

User Guide > Main Guide:
- The step boxes were one large drawing laid over the interface. That is why the
  buttons inside them would not glow and why they kept their size when you
  zoomed the browser while everything around them shrank. They are ordinary page
  elements now, like the boxes in Live Network: they zoom with the rest of the
  interface, reflow to the window width, and their skip and confirm controls
  glow on hover and pulse when pressed like every other button.
- Only the connectors between boxes are still drawn, and those are measured from
  the boxes' real positions after layout, so they follow the boxes wherever they
  end up - including when a narrow window pushes a step onto the next line. They
  redraw when the window is resized.
- A line still leaves each box in that box's colour, and the manual-providers
  branch still hangs below the row it belongs to.

## v2.86

frosted panels, a tidier terminal toolbar.

User Guide:
- The symbol beside a highlighted heading now glows as strongly as the words. It
  was getting only the shape glow while the text got that plus a text glow, so it
  barely registered.
Proxy > Dashboard:
- The text scaling toggle is now "Default text size", which puts a manually set
  size back to the shipped one. It is greyed out while Auto is chosen.
- The line of text describing the current scaling mode is gone; the chosen mode
  is marked with a green glow on Auto or Manual instead.
- The background switch is now "Terminal background color", a menu that drops
  out with Midnight and Black to choose from, each glowing under the pointer and
  the current one marked in green.
Throughout:
- Hover descriptions and every drop-out menu sit on smoked glass: a dark
  translucent panel with the page blurred behind it.

## v2.85

highlights glow the words, arcs run both sides.

User Guide:
- Jumping to a step now glows the heading and its symbol themselves rather than
  drawing a box around them. The old highlight used a box shadow, which follows
  the element's rectangle; this one follows the shape of the letters and the
  drawn symbol.
- The skip, confirm and undo marks in each step's corner glow when you hover
  them.
- Step 7 no longer highlights anything. It simply plays the Launch button's own
  effect, which the competing highlight had been cutting short.
Launch button:
- Arcs now jump along the bottom of the word as well as the top.
Provider > Providers:
- Sampler values no longer carry a permanent glow; they light up under the
  pointer only.

## v2.84

the guide points at the right things.

User Guide:
- A connector now takes the colour of the box it leaves rather than the one it
  arrives at, so a completed step's outgoing line is green.
- Step 3 highlights the PC GPUs heading and its symbol, and step 4 the Live
  Network heading, instead of outlining the whole panel.
- Step 7 shows you the Launch button working: it lights up and throws arcs
  immediately, holds for two seconds, then eases back over the last one. Nothing
  is launched.
- The skip, confirm and undo controls in each step's corner are drawn marks now,
  with no emoji left in the diagram.
Provider > Providers:
- Sampler values have no box around them. They are plain text carrying a glow in
  their own state colour, brighter under the pointer.
Tabs:
- Server Setup is now Server, Provider Setup is Provider, and Folder Setup is
  Folder Settings.

## v2.83

rows share a baseline, which is what "aligned" actually means.

The alignment change:
- Items in a row now sit on a shared baseline instead of a shared centre. Centring
  is geometrically correct but it is not what the eye reads as aligned: a 12px
  port label centred beside an 18px title ends up floating about 2.4 pixels above
  that title's baseline, which is exactly the gap visible in the screenshots.
  Sharing a baseline removes it. Buttons, switches and input fields have no
  meaningful baseline, so those stay centred, and the one row that forced its own
  centring inline no longer does.
Folder Setup:
- The exit-on-close setting is gone. Closing the last browser tab always shuts
  PandorumLLM and every server it started.
User Guide:
- A connector takes the colour of the box it points at, so a line and its step
  always agree.
- The status marks inside each step are drawn symbols now - a tick, a cross, or a
  skip arrow - each with a faint glow in that step's own colour.
Page arrows:
- The glow is drawn on the arrow stroke itself rather than as a shadow behind the
  button, so nothing sits in front of it.

## v2.82

the row alignment cause found - it was the emoji font.

The fix:
- An emoji dropped into a run of text is drawn from a different font, and that
  font stands much taller than the text one. The line it sits on grows to make
  room for it, and the words are pushed down inside that taller line - so any
  label containing an emoji sat lower than a plain one beside it, no matter how
  the boxes were aligned. That is why this survived several attempts: the boxes
  were lining up correctly all along, the letters inside one of them were not.
  The emoji font is now re-declared with the text font's proportions, so a line
  with an emoji is exactly as tall as a line without, everywhere in the app.
Live Network:
- The hover glow is the box's own colour, brighter, rather than switching to the
  accent.
- Provider boxes are slimmer, and the port sits in from the right edge by
  exactly as much as the name sits in from the left.
Server Setup > Servers:
- The port is plain text, with a glow only while you hover it or type in it.

## v2.81

dragging holds its place, one highlight everywhere.

Live Network:
- The hover glow is back. Moving each box's colour into an inline style had
  quietly overridden the hover rule, since an inline style outranks a
  stylesheet one. The colour is now passed as a variable and the stylesheet
  owns the shadow again.
- Picking up a box no longer makes the drop box below jump up into the gap. The
  space it came from is held open until you let go.
- Dropping a box where nothing would change simply puts it back, with no reload.
- A server can no longer be dropped into a provider box.
Row alignment:
- Every item sharing a row now gets the same box height and centres its own text
  inside it. Before, each item's box was scaled to its own font size, so a large
  title and a small chip could centre their boxes without their letters lining
  up - and a taller glyph such as an emoji could stretch its box past its
  neighbours. Font size and glyph metrics no longer come into it.
User Guide:
- The arrowheads between steps are 40% smaller.
- Every jump from a step now highlights the same way: one second easing in, one
  second easing out. Some used to flash and vanish.
Server Setup > Servers:
- The port has no box around it, just the glow the other fields use, and sits
  level with the server name.

## v2.80

one top edge, and indentation that means something.

Layout:
- The tab column and the page beside it now start on the same line. Both sit
  twelve pixels below the header, and the subtab buttons carry the same padding
  as the tab buttons, so the two rows of text line up rather than merely their
  boxes. The rule is written down beside the values so it stays that way.
- Indentation now shows depth. Subtab buttons sit at the page's left edge and
  everything belonging to them starts twenty-six pixels further in, so the
  further down the hierarchy something is, the further right it begins. It used
  to be the other way around.

## v2.79

the row alignment bug found, provider names become links.

The alignment fix:
- Provider names sat off the line from the port and status beside them. The
  emoji was part of the title text, and emoji glyphs are taller than letters, so
  they stretched that line box and pushed the words down inside it. Centring the
  boxes could never fix that. The emoji now has a line box of its own and every
  text item in a row centres its own contents, so glyph metrics cannot throw a
  row out of line again.
Provider Setup > Providers:
- Provider names and their symbols are links. Pressing one opens Live Network
  and lights up that provider with everything joined to it, glowing in that
  provider's own colour.
Live Network:
- The PC GPUs symbol glows with its heading, and each card keeps its name,
  memory and driver id on one line.
User Guide:
- The hover highlight touches only the outline of a step box. The skip and tick
  controls glow when you hover them, pulse when pressed, and a completed step
  keeps a steady green glow.
Server Setup > Servers:
- The last launched line is gone. A port change is still reported on the card.
Elsewhere:
- Profiles, auto refresh and the page arrows are 20% larger, and nothing sits
  over the arrows' glow any more.

## v2.78

rows line up, GPUs tuck away, models report their state.

Fixes:
- Row contents really are centred on one line now. Matching the boxes was not
  enough: a large heading has a tall line box, so its text rode high against
  smaller neighbours beside it. Row children now share a line height, which is
  what was actually throwing them off.
Live Network:
- PC GPUs is a heading you press. The card list is hidden by default and drops
  out of it, with Detect GPUs inside, closing when you click away.
- Boxes have no outlines. Their colour is carried as a soft glow instead.
Server Setup > Servers:
- The allocation line is now a link. Pressing it opens Live Network and lights
  up that server and everything joined to it.
- The model line under each card is gone, since the dropdown says the same
  thing. Instead the three model pickers colour themselves: green once a model
  is loaded, amber while it is being applied, and red with a triple pulse if the
  launcher could not be written, staying red until you choose another. Either
  outcome is written to the fleet terminal.
Elsewhere:
- The page arrows have no background, just a glowing symbol.
- The User Guide hover highlight is much subtler.

## v2.77

page history arrows and a restore for the servers.

New:
- Two arrows sit in the bottom left corner, always in view. They walk back and
  forward through the pages you have visited, the way a browser does: going back
  and then opening something new drops whatever was ahead. They dim when there
  is nowhere to go.
- Server Setup has a "Restore default servers" button under the subtabs. It
  rebuilds the shipped servers with their default parameters and launchers.
  Providers are not lost with their slot - they move to the unallocated row so
  you can put them back where you want.
Appearance:
- The terminal symbol has a black screen with softly glowing green contents, a
  faint green halo, and the rolling character is now as large as the prompt.
- Toggle switches carry a faint accent halo at rest that brightens under the
  pointer. Switched off, the track is black with a blurred edge.
- Hover descriptions wait a second and a half before appearing.

## v2.76

your own colour presets, and everything back in line.

Customization:
- "Save as preset" stores the colours you have set under a name of your own.
  Saved presets sit beside the shipped ones with a small cross in the corner:
  hovering it glows red, and clicking pulses the whole preset red once before it
  fades away over a second and is removed.
Fixes:
- Context size stepping no longer fights itself. A tap now applies its whole
  1024 step when you release the key, and the 128 creep only starts after half a
  second of holding - previously the tap jumped 1024 and the creep immediately
  began nudging off that value.
- Buttons, titles, status text and notes sharing a row are centred on the same
  line again. Changing the heading and button sizes had left them staggered.
Appearance:
- The buttons along the top are 20% larger and the terminal symbol 25%.
- The version no longer sits in a pill.
- In Provider Setup, the port number has no box around it and sits level with
  the provider name and its symbol.
- Server Management and Provider Management are now Server Setup and Provider
  Setup, each on a single line.

## v2.75

fleet terminal on demand, provider colours, context-size stepping.

New:
- A terminal button sits beside Terminate. The fleet stack terminal no longer
  appears on its own when you launch; it opens only when you press that button.
  The character beside the prompt rolls through digits and symbols while you
  hover the button or while the terminal is open.
Live Network:
- Provider boxes are outlined in the colour that provider is given in the
  terminals, so a name reads the same in both places, and the trace glow follows
  that colour too.
Server Management > Servers:
- Holding an arrow key now moves from the outset instead of pausing for a second
  before the wind-up begins.
- Context size steps in whole 1024s. If the value is off that grid, the first
  press lands it on the nearest multiple in that direction. Held, it creeps in
  128s - one every half second at first, one every tenth of a second after five.
  Other settings are unchanged.
Appearance:
- Page headings and subtab labels are 15% larger.
- The off state of a toggle matches a text field, with a subtle inset texture.

## v2.74

sliders that wind up, instant theme selection.

Server Management > Servers:
- Every slider now moves one unit at a time. Tap an arrow key for a single step;
  hold it and after a second it winds up, gaining one percent of that slider's
  range per second and settling at five percent per second. A context size
  slider therefore crawls at first and ends up moving thousands per second,
  while a small setting stays controllable throughout.
Customization:
- The chosen preset is marked with an accent glow rather than a border, and the
  marker moves the instant you click. It used to wait for the save and a full
  reload before catching up.
User Guide:
- The step boxes light up as you pass over them.
- The skip and tick controls inside the boxes have no box or border of their own
  any more, just their symbol.
Folder Setup:
- The buttons have no emoji. Copy keeps its symbol.

## v2.73

the slider flicker traced to the background refresh.

Fix:
- Adjusting a slider with the arrow keys no longer flickers or bounces back to
  the old number. The page only paused its background refresh while a field had
  keyboard focus - but driving a slider by hovering focuses nothing, so the
  refresh kept rebuilding the card underneath. Rebuilding swapped the slider out,
  which is the flicker, and repainted the last value the server had sent, which
  is the bounce. The card now also holds still while the pointer is over a row or
  a save is still on its way, and catches up once you move away.
Live Network:
- Provider boxes are shorter and their port number sits centred. GPU and server
  boxes are untouched, since they carry a second line.
- Recommended setup uses the filled wand with sparkles.

## v2.72

smooth slider edits and a glow that lets go.

Live Network:
- The box rows are back exactly as they were. Only the PC GPUs heading moved: it
  now lines up with the Live Network title above it, because the GPU panel's own
  padding had been indenting it.
Server Management > Servers:
- Adjusting a value with the arrow keys no longer flickers, lag or snap back to
  the previous number. Every keypress was saving and rebuilding the whole page:
  the rebuild was the flicker, the status fetch was the delay, and two replies
  landing out of order was the value jumping. Keypresses are now gathered up and
  saved once you pause, and the card holds still while you are working in it.
Fields, everywhere:
- The accent glow lets go as soon as you are finished with a field, instead of
  hanging on until you click somewhere else. Pressing Enter on an unchanged
  value, or picking the same option again, produces no change event at all, so
  the field kept focus and stayed lit; both cases release it now. Sliders are
  left alone so dragging still works.

## v2.71

cyan arcs, working slider keys, tighter switch rows.

Launch button:
- The bolts are cyan against the accent-coloured label, and they keep arcing on
  their own while servers are running, not only while you hover.
Fixes:
- Slider arrow keys work from the row your pointer is over, which is what you
  would expect when the slider only appears on hover. Previously the keys only
  reached a slider that already had focus, so hovering and pressing an arrow did
  nothing. All four arrows work, the value box follows, and the value stops at
  each end of its range.
- The rows below Disable mmap are visibly tighter. The markup was already
  correct - the gap was being halved from 15px to 8px on rows 34px tall, which
  was too small to notice. Those rows are now half height as well as half gap.
- Terminate keeps its stop symbol while it reads "Working..." and afterwards. It
  was rewriting itself as plain text, which discarded the symbol and brought the
  old emoji back with it.
- The "drag the bottom-right corner to resize" hover message is gone from the
  launch terminal and the yaml status pane.
Live Network:
- Rows start at the left edge, in line with the panel title and its symbol.
- Provider boxes are shorter and their port sits centred.
Elsewhere:
- Toggle knobs are darker again.

## v2.70

distinct symbols and even Live Network boxes.

Symbols:
- Terminate carries a stop square instead of a power glyph, so it no longer
  looks like a smaller Exit button. Its symbol is red, and it now lights up
  along with the label rather than staying flat while the text glowed.
- Live Network uses a drawn hierarchy symbol in place of the web emoji, matched
  to the GPU symbol in size and colour.
- Recommended setup uses a wand instead of the sparkle emoji.
- The GPU symbol gained the little lip at the top of its bracket, so it reads as
  an IO shield seen from the side.
Live Network:
- GPU boxes are all as wide as the widest GPU name, server boxes as wide as the
  longest server title, and providers likewise. Names are no longer clipped and
  each row stays square, whatever the cards are called.
Welcome message:
- The button reads "Take me to the user guide".

## v2.69

real lightning on the Launch button.

Launch button:
- The arcs are drawn now, not faked with shadows. Each letter sits in its own
  span with a transparent canvas over the label, and bolts are plotted as jagged
  paths jumping between two randomly chosen letters - first to fourth, fourth to
  fifth, and so on. Hovering throws a steady scatter of thin bolts; pressing
  throws a short burst of longer, brighter ones.
Fixes:
- The rows below Disable mmap really are at half spacing now. A row's margin is
  the space beneath it, so Disable mmap itself had to carry the tighter spacing
  for the gap under it to close; previously only the rows after it did.
- Clicking into a dropdown or text box no longer stacks a second, wider accent
  glow on top of the hover one. Focus now holds exactly the hover glow and keeps
  it until you click away, whether or not you actually change the value.
Appearance:
- The GPU symbol on the Live Network panel is twice the size.
- Toggle knobs are dark grey rather than pearl white.
- The manual-providers text is centred in its box in the guide.

## v2.68

Launch button fixed, drawn symbols, fields that warm to the touch.

Fixes:
- The Launch button kept its filled background. A separate rule was forcing it
  with a higher priority than the change that stripped every other button; it is
  overridden properly now, so Launch is glowing accent text like the rest.
- Its letters jittered on hover. The arc effect was animating the spacing
  between characters, which reflowed the text on every frame. The spacing is
  fixed now and only the glow crackles.
Symbols:
- Terminate carries a drawn power symbol instead of the red emoji.
- The PC GPUs heading carries a drawn graphics-card symbol, in the same colour
  as the rest of the interface, and Detect GPUs has no emoji.
Live Network:
- The GPU enable switches sit at the front of each row.
- The explanatory grey notes are gone from the panel and the GPU list.
Server Management > Servers:
- Half spacing again on the switch rows below Disable mmap.
Fields:
- Hovering a dropdown or text box warms its glow to the accent colour over a
  second. The accent holds while you are picking or typing, then cools back to
  black over a second once you are done.

## v2.67

electric Launch button, glowing tabs, working slider keys.

Navigation:
- Subtabs lose their pills, like the buttons did. The page you are on is marked
  by an accent glow on its label instead of a grey fill, for both the tab list
  and the subtab rows.
Launch and Terminate:
- Launch carries a steady accent glow. Hovering it throws short electric arcs
  between the letters; pressing it throws longer ones.
- Terminate glows red while anything is serving and pulses when you hover it.
  Once the last server stops, the red fades away over about a second rather
  than cutting out.
Fixes:
- Clicking a button pulsed twice. The pulse ended at no glow and then snapped
  back to the hover glow, which read as a second flash; it now settles on the
  hover glow.
- Sliders really do take the arrow keys now. Each row was a label wrapping two
  inputs, so clicking the slider was forwarded elsewhere and it could never hold
  focus. Rows are plain elements now, the slider takes all four arrow keys, the
  value box takes left and right as well as up and down, and the two stay in
  step whichever one you are using.
- The flag link beside each setting matches its title size.
- The auto refresh dropdown is only as wide as its text.
User Guide:
- The manual-providers branch leaves the bottom of step 5 and enters the bottom
  of step 6 at mirrored positions, meeting the box edges instead of running
  underneath them.

## v2.66

buttons become glowing text.

Throughout:
- Buttons no longer have a background or a border. They are their label, which
  lights up when you hover it and pulses once when pressed. Each one glows in
  the colour its background used to be: Launch green, the accent colour for
  primary actions, red for the remove crosses, and a soft white for everything
  that used to be grey.
- The tab list and the subtab rows keep their shape, because they still have to
  show which page you are on.
Live Network:
- The GPU enable and disable buttons are switches now, lined up down the right
  of the panel whatever the card names are.
Server Management > Servers:
- Half the spacing on everything below the Context size row; the three model
  pickers keep the wider gap.
- Sliders take keyboard input. Tab to one and the arrow keys move it, with the
  value box updating as you go.

## v2.65

the reason the server card spacing never changed.

The important fix:
- A stray closing brace had been sitting in the stylesheet since v2.57, left
  behind when an animation block was removed. Everything after it - 212 rules -
  was being thrown away by the browser, including every layout rule for the
  server card parameters. That is why the rows stayed cramped no matter how
  much the spacing was increased. The brace is gone, so those rules apply now,
  and the packaging check refuses to build if the stylesheet is ever unbalanced
  again.
Server Management > Servers:
- Parameter rows are properly spaced and no longer collide.
- Value boxes and dropdowns are the same width and end flush with the right edge
  of the card. The hidden slider used to reserve its width to the right of each
  value box, which is what pushed the numbers out of line with the dropdowns.
Appearance:
- Toggle knobs are pearl-like, with a soft dark halo.
- Dropdown and text field glow is black by default, in every theme. It is still
  the "dropdown menu glow" colour in Customization if you want it tinted.
- On Folder Setup the switch now follows its label rather than leading it.
User Guide:
- The manual-providers branch leaves the bottom of step 5, runs beneath both
  boxes and rises into step 6. It now reads "I manually set up providers in
  SkyrimNet UI".

## v2.64

card rows spaced and aligned, two popup bugs fixed.

Fixes:
- Hovering the flag beside a greyed-out setting produced two tooltips at once.
  Only the hovered element had its title suppressed, so the browser still drew
  its own box for the row behind it. The whole chain is suppressed now.
- The Profiles panel opened off the right edge of the window. It now grows
  leftwards from the word, like the auto refresh panel.
- Profiles sometimes needed two clicks. The panel opened on click, and a
  background refresh landing mid-click could replace the header and swallow the
  gesture. Both header panels now open on press instead.
Server Management > Servers:
- Twice the spacing between parameter rows.
- Value boxes, dropdowns and switches all sit flush with the right edge of the
  card, so they line up down the column.
- Flash attention and both KV cache types are back to a compact width, all three
  identical.
- Model, Vision (mmproj) and Speculative decoding put their dropdown on its own
  line under the title, so long model names have the full width.
- GPU layers accepts up to 999 again.

## v2.63

server cards rebuilt, header controls slimmed, new theme colour.

Server Management > Servers:
- Every setting is now one row: name and flag on the left, control on the right,
  all lined up down the card. Vision (mmproj) and Speculative decoding no longer
  wrap their flag onto a second line.
- Sliders are hidden until you hover the row, so the cards read as plain values.
  The value box sits to the left of its slider.
- Flash attention and both KV cache types now use the full-width dropdown the
  other settings use, instead of a box barely wider than its arrow.
- GPU layers is capped at 99, the generation cap accepts -2 (fill the context),
  and the KV cache types now offer the full llama.cpp set: f32, f16, bf16, q8_0,
  q5_1, q5_0, q4_1, q4_0 and iq4_nl.
- The grey sampler note at the bottom of each card is gone.
Header:
- Profiles is now the word itself, glowing blue on hover; the button is gone.
- The auto refresh clock is a drawn symbol that opens the interval dropdown when
  clicked, rather than sitting open all the time.
Customization:
- New "dropdown menu glow" colour. Dropdowns and text fields have no border at
  all now, only that glow, and it starts out matching each theme's accent.
Elsewhere:
- Switches use the accent colour.
- Main tab labels have a soft text shadow.
- In Live Network, the line from a server down to its provider box now lights up
  with the rest of the chain when you click any box in it.
- Provider emoji dropdowns align their emoji left like every other dropdown.
- Proxy sits above Launcher in the tab list.

## v2.62

instant linking, conditional settings, consistent terminal controls.

Live Network:
- Dragging a box now takes effect immediately. The redraw used to wait on a full
  status refresh, which probes every server port, so a link took a couple of
  seconds to appear. The box now settles where you dropped it at once and the
  field is locked until the change is stored, so nothing can be moved twice.
- The boxes no longer carry status words like Unallocated or idle; the lines
  between them already show what is linked to what.
Server Management > Servers:
- Three times the spacing between runtime settings.
- "Vision model (mmproj)" is now "Vision (mmproj)", and both it and Speculative
  decoding have Sampler Guide links like the other settings.
- Settings the rest of the configuration makes pointless are now shown greyed
  out and cannot be changed, with the reason on hover. With every layer on the
  GPU, CPU threads and Disable mmap are inactive; with flash attention off, the
  KV cache types are inactive; with a single parallel slot, Disable cont
  batching is inactive; and with auto fit on, GPU layers is inactive.
Proxy > Dashboard:
- All three terminal views now carry the same controls in the same place,
  directly above the terminal, in two rows: scaling mode on the first, size and
  font on the second. Previously the single terminals had them at the top of the
  page and only split view had them above the terminals.
- The size and font dropdowns are much narrower, and the size dropdown only
  appears in manual mode.
- "Text Size" is now "Text Scaling".
Elsewhere:
- Dropdowns draw their own arrow so the spacing matches on both sides.
- Switches take their on colour from the active theme, so they turn green under
  OpenRouter and follow whatever accent a custom theme sets.
- Hovering the PandorumLLM title says what it needed to say all along.

## v2.61

switch toggles, roomier server cards, borderless popups.

Throughout:
- Every on/off setting is now a sliding switch instead of a tick box or a
  two-item dropdown. That covers Thinking and Detect SN sampler parameters on
  providers, Disable mmap, Disable cont batching and Auto fit to VRAM on server
  cards, and the exit-on-close setting in Folder Setup. Settings with more than
  two choices, such as Flash attention and the KV cache types, stay dropdowns.
- Tooltips and dialogs have lost their outlines and rely on their shadow.
Server Management > Servers:
- Noticeably more space between one runtime setting and the next, so the rows no
  longer run together.
Provider Management > Providers:
- Restore default providers has moved here from Live Network.
- The Priority and Sampler Source labels are gone; the controls speak for
  themselves.
- Sampler Source now sits before the Thinking switch.

## v2.60

launcher picker, profiles panel, tighter provider rows.

Server Management > Server Editor:
- The path box and Open launcher file button are replaced by a dropdown listing
  the .ps1 files in the launcher folder you set in Folder Setup. Picking one
  loads it into the selected server.
Proxy > Proxy Setup:
- Detect IP address has moved up beside the 1 PC / 2 PC buttons, set apart from
  them.
Profiles:
- Now a single Profiles button in the top bar. Clicking it opens a small panel
  holding the profile dropdown and Save, New and Delete. Save overwrites the
  selected profile, New stores the current setup under a name you choose, and
  Delete asks for confirmation first. Clicking anywhere outside closes it.
Provider Management > Providers:
- The duplicate emoji between the emoji dropdown and the name is gone; the
  dropdown already shows it.
- Priority and Sampler Source dropdowns are only as wide as their text.
- Editing a sampler value no longer flashes a tick; the chip simply comes back
  showing the new value.

## v2.59

working update check, softer surfaces, sentence-case buttons.

Folder Setup:
- "Check for update" now really checks. It asks github.com for the newest
  llama.cpp release, reads your own build number from llama-server.exe, and
  answers in colour: green when you are current, amber when a newer build is
  out, red if it could not reach GitHub.
  This is the only outbound request the app makes and it happens only when you
  press that button. The SAFETY & TRUST section has been corrected to say so.
- "Path set" now appears only under the folder you actually changed.
Server Management > Servers:
- More vertical space between the rows of controls, and more room between each
  label and its flag link.
- While a model is being applied the card says "Loading model..." in amber; if
  the launcher could not be written it says "Model could not be loaded" in red.
  Previously this window showed a confusing "file missing" warning.
User Guide:
- The "I manually set up providers in SN UI" branch curves cleanly out of step 5
  and into step 6 instead of doubling back on itself.
Appearance:
- Panels, cards and popups no longer have outlines.
- Dropdowns and text fields use a soft glow instead of a border, which brightens
  when focused.
- Buttons other than the tab and subtab rows use sentence case, so only the
  first word is capitalised. Product names and acronyms keep their capitals.

## v2.58

readable buttons, styled tooltips, tidier Folder Setup.

Fixes:
- Several Server Editor buttons showed "??" where an emoji should have been. The
  padlock, save, folder and revert icons are gone; those buttons now read as
  plain words, which render on every font.
- The Server Editor text area showed a white box before a launcher was loaded.
  It now keeps the panel's dark background whether it holds anything or not.
- Open Launcher File is disabled while the editor is in Inspector Mode.
User Guide:
- The "I manually set up providers in SN UI" branch now leaves step 5 and
  arrows into step 6, matching the two steps it completes.
- Step 1 highlights both mandatory folders - llama.cpp and Models - instead of
  only the first.
Folder Setup:
- "Path set" now appears under the folder it belongs to and clears itself after
  three seconds, rather than as one message at the bottom of the page.
- A Check for Updates button sits beside Copy. It opens the llama.cpp releases
  page in your browser; the panel still makes no outbound calls of its own.
Throughout:
- Buttons have more space between their leading symbol and the label.
- Hover tooltips are drawn by the app instead of the browser, so they match the
  rest of the interface and use the same typeface.
- More space between the rows of controls inside a server card.

## v2.57

sampler values are yours to set, with a switch for which side wins.

Provider Management > Providers:
- Sampler values can be edited at any time. The restriction that made you wait
  for a first request is gone.
- New "Sampler Source" dropdown per provider. On Server Side, the values set
  here are what reaches the model on every request. On SkyrimNet Side, whatever
  SkyrimNet sends passes straight through and your values are kept for later.
- New "Detect SN Sampler Parameters" toggle. With it on, each value shows what
  SkyrimNet sent in brackets beside your own, e.g. temp 0.8 (0.85), so you can
  see both at a glance.
Layout:
- The rounded subtab buttons are 20% smaller, and the row now starts level with
  the top of the first main tab button.

## v2.56

Server Editor, more runtime settings, guide cross-links.

Server Management > Server Editor (was Server Inspector):
- The launcher is now editable. It opens locked in Inspector Mode; the padlock
  switches to Editor Mode, with undo and redo.
- Save keeps your text exactly as written and reads the parameters back out of
  it, so the server cards keep showing what will actually run.
- Open Launcher File loads an existing .ps1 into a server the same way.
- Revert steps back to the launcher in place before the last save or load, and
  Revert to Default discards hand edits and rebuilds from the parameters.
- If the model a launcher points at is not in your models folder, the editor
  says "Model not found, select a model".
Server cards:
- Added a vision model picker and a speculative decoding picker, both defaulting
  to Disabled.
- Added --no-mmap, --no-cont-batching and --fit.
- Every setting now shows its flag beside the label, e.g. [--ctx-size]. Hovering
  makes it glow and clicking opens that entry in the Sampler Guide.
- Servers always launch at log level 4; it is not shown on the card, only in the
  Server Editor.
User Guide:
- "I manually set up providers in SN UI" now completes step 5 and step 6 rather
  than 6 and 7.
- Reset Steps no longer clears step 3: whether GPUs are detected is a fact about
  the machine, so that step always reflects reality.
- The buttons at the top sit next to the title instead of spread across the row.
Folder Setup:
- The PS1 Launcher Folder is no longer marked mandatory.

## v2.55

provider edits apply immediately, Live Network reports what you do.

Fixes:
- Provider changes did not appear to do anything. Every provider handler still
  refreshed the old Proxy Setup pane, which after the tab rework only draws the
  IP card - so emoji, name, port, priority and sampler edits all silently failed
  to repaint. They now refresh whichever page you are on.
- That is also why a sampler chip turned into a tick and stayed there. It now
  returns to a normal chip as soon as the value is saved or you press Escape.
- Server cards took seconds to show a newly picked model, because the redraw
  waited on a full state fetch that probes every server port. The card now
  updates instantly and reconciles with the server afterwards.
Live Network:
- Only one link line runs from a server to its drop box, drawn straight down the
  centre of the server box, and only once the box holds something.
- All provider boxes are the same width and sit centred in the drop box.
- The status field below the network now reports what you did as you do it:
  "<GPU> <- <Server>" when a server is allocated, "<Server> <- <Provider>
  (Priority 1 - Normal)" when a provider is dropped in, detachments, GPUs being
  enabled or disabled, and the full list of cards found after a GPU detection.
Provider slots:
- Sampler values cannot be overridden until the proxy has actually seen a
  request for that provider. Attempting it early pulses the value red and
  explains why in a small note beside it, rather than a dialog.
- The priority dropdown is labelled and reads "0 - High", "1 - Normal",
  "2 - Low". The chosen emoji now shows beside the provider name straight away,
  and the controls have more space between them.
Other:
- The PS1 Launcher Folder is back on the Folder Setup page and now doubles as
  the Launcher Creator output folder.
- The profiles dropdown is narrower with a gap before the buttons.
- The server Launch button no longer carries an emoji.

## v2.54

provider editing fixed, Live Network handling smoothed out.

Fixes:
- Changing a provider's emoji (or name, port or sampler overrides) failed with
  "unknown provider" whenever that provider was unallocated. Both provider
  endpoints only looked inside servers; they now see parked providers too.
- Picking a model left the server card stale, with Launch still greyed out. The
  redraw was being skipped because the dropdown still had focus.
- The connection glow juddered at each peak. It animated a box shadow and the
  line thickness; it now pulses opacity alone, which the browser composites
  smoothly.
- Recommended Setup appeared to hang: it repainted the old Proxy Setup pane
  rather than Live Network. It now shows "Working..." while it runs and redraws
  the network as soon as it finishes.
Live Network:
- Dropping a box anywhere that is not a valid target now detaches it, so you can
  simply drag a provider out of a server or a server away from its GPU. A
  detached server keeps its providers.
- Boxes size themselves to their text, up to a limit, with anything longer
  ending in an ellipsis so it stays inside the box.
- The grey captions above the rows are gone, as is the empty "nothing detached"
  placeholder - unallocated providers simply sit in their row.
Server cards:
- The Flash attention and KV cache dropdowns are now compact and sit beside
  their labels instead of stretching across the card.
- More space above the Launch row, and Add Slot is now "Add Server" with a
  wider gap above it.
User Guide:
- The step list drops from nine to seven. Wiring is now one "Live Network
  complete" step covering the GPU link, the model and the providers, and the
  obsolete ".ps1 launcher" prompt is gone. The "I manually set up providers in
  SN UI" bypass now runs from providers.yaml generated to Servers launched.

## v2.53

Live Network dragging fixed, and the boxes tidied up.

Fixes:
- Nothing could actually be dragged in Live Network. The HTML5 drag-and-drop
  rewrite never fired, so dragging now uses pointer events - the same method the
  old graph used. Boxes follow the cursor, the zone under it lights up, and a
  click without moving still traces the connections.
- Recommended Setup did nothing once everything started unallocated: it only
  looked at providers already inside a server. It now sees parked providers and
  places them, so it sets up a fresh install in one press.
- Enabling or disabling a GPU now redraws Live Network immediately instead of
  needing a page refresh.
Changes:
- Providers are always on. The enable/disable button is gone - if SkyrimNet
  never calls a provider, the proxy simply never sees a request for it.
- Live Network boxes are a fixed width per row, so a long model or GPU name no
  longer stretches them. Text that does not fit ends in an ellipsis, and the
  port no longer overlaps the title.
- Boxes carry their colour as an outline only, the left colour bar is gone, and
  the link lines now inherit the colour of the chain they belong to.
- More vertical space between the GPU, server and provider rows.
- The "not routed" label was dropped from unallocated provider boxes.
- Servers always launch with reasoning enabled; each provider's own thinking
  setting decides what it sends. The per-server Reasoning dropdown is gone.
- Parameter value boxes no longer show up/down spinner arrows.
- The Launch buttons lost the rocket; other button emoji are unchanged.
- The Add Slot button no longer sits inside a grey panel.
- Provider cards on the Providers page are no longer draggable.

## v2.52

Live Network wiring fixed, Server Inspector added.

Fixes:
- Live Network could not link anything. Server boxes were not draggable and GPUs
  were not drop targets, so with everything starting unallocated there was
  nothing to drag and no way to put a server on a GPU at all. Servers now drag
  onto GPUs, providers drop into any server, and either can be dragged to the
  Unallocated row to detach. None of it needs a model to be chosen first.
- The Providers page went empty in v2.51, because it only listed providers that
  were inside a server and every provider had just been parked. Unallocated
  providers are listed again, marked as such.
- Choosing a model now refreshes Live Network, so the server box shows it.
New:
- Server Management > Server Inspector shows the launcher a server compiles to,
  with syntax highlighting and line numbers, generated live from its parameters
  so you can read it before ever launching.
Changes:
- Live Network boxes carry their GPU's colour again, down the chain from GPU to
  server to provider, with the colour repeated as a bar on each box.
- The logo glow returns to the softer v2.46 swirl, now double-ended: two glow
  points opposite each other orbiting the logo and title.
- Server Management > Servers: the Server Slots heading is gone, Stop only
  appears once a server is running, and Launch shows a spinner and "Running..."
  like the fleet Launch button.
- Server card contents wrap properly instead of overlapping, and the parameter
  grid uses narrower columns so it fits inside a card.

## v2.51

Live Network becomes the one place wiring happens.

- Live Network is now the first tab, and the PC GPU panel sits at the top of it,
  so GPUs, servers and providers are all managed in one view.
- Allocation is done only by connecting boxes in Live Network. The GPU dropdown
  on server cards and the server dropdown on provider cards are gone - both
  pages still show what something is allocated to, they just no longer change it.
- Nothing is wired until you wire it. A fresh install starts with every server
  off-GPU and every provider parked in the Unallocated row, and an existing
  setup is moved to that state once so the wiring is rebuilt in one place.
- Thinking now starts off on every provider. Enable reasoning on the server, then
  each provider's own thinking setting decides what it sends.
- Profiles moved out of the individual pages and into the top bar beside the auto
  refresh control. One profile now covers the whole setup - wiring, server
  parameters and settings - instead of separate ones per page.
- Server Management > Servers shows servers as cards side by side, without the
  GPU selector or the down / disabled state chips.
- The logo and title rays are sharper and less bloomed: four hard-edged spikes
  sweeping a quarter turn rather than a soft halo.

## v2.50

Live Network rebuilt to read top-down, with drag-to-allocate and click tracing.

- The diagram now flows downwards instead of sideways: GPUs along the top, the
  servers running on them underneath, and each server's providers below it.
  Everything is centred in the field.
- A server that is allocated to a GPU gets a dark drop area directly beneath it.
  Drag provider boxes into it and they stack vertically, and the area grows to
  fit them.
- Providers that belong to no server sit side by side in an Unallocated row along
  the bottom. Drag one down there to detach it - an unallocated provider gets no
  proxy port and is left out of providers.yaml until you allocate it again.
- Hovering a box highlights it, the box being dragged dims, and the drop area you
  are over lights up.
- Clicking traces the wiring: a provider lights up its server and GPU, a server
  lights up its GPU and all of its providers, and a GPU lights up every server on
  it and all of their providers. The connecting lines light up too. The glow
  fades in over half a second, pulses for six seconds, then fades away over one.
- Connection lines are measured from the real box positions, so they stay correct
  when the layout wraps or the window is resized.

## v2.49

servers and providers reworked; launcher files retired.

Servers now launch from parameters, not .ps1 files:
- Each server carries its own runtime parameters - model, context size, GPU
  layers, flash attention, KV cache types, parallel slots, batch sizes, threads,
  generation cap and reasoning - set with dropdowns, sliders and value boxes on
  the server card.
- Saving a parameter rewrites a hidden launcher for that server, and launching
  regenerates it first, so a server can never start with stale flags. Your
  existing .ps1 for a slot is imported as its starting parameters, so nothing
  you had configured is lost.
- The launcher dropdown and launcher path are gone from the server cards. A
  server now shows "Unallocated" in grey, or "Allocated to <GPU>" in green.
- Sampler values stay per provider and are injected into every request, so each
  provider remains adjustable while the server is running.
New tab layout:
- "Servers" is now "Server Management", with the Servers subtab holding the GPU
  panel above the server slots, and Server Statistics beside it.
- New "Provider Management" tab: every provider in one flat stack showing which
  server it is allocated to, with a dropdown to move it, plus Provider
  Statistics.
- New "Live Network" tab holding the wiring diagram.
- Proxy > Proxy Setup now holds only the PC IP addresses.
- "Helper" is now "User Guide", with a Main Guide subtab and the Sampler Guide
  moved in from the Launcher tab. The Launcher tab keeps Creator and Inspector;
  its Getting Started guide has been removed.
- Folder Setup: the models folder is now the second path, and both launcher
  folders are gone along with the launcher system.
- The main guide steps and the first-run welcome message were rewritten for the
  new layout.

## v2.48

bigger subtabs, per-terminal fonts, resizable panes, log categories.

Navigation:
- The rounded subtab buttons across the top of each page are 30% larger.
Proxy > Dashboard:
- Each terminal now has its own Font dropdown, with 16 choices including the
  current Cascadia Code and the font the rest of the app uses. Split View gets a
  separate dropdown per pane, and every terminal remembers its own font. All the
  fonts are ones already installed on your PC, so nothing is downloaded.
- Full Window now stretches the terminal all the way down the browser window.
  Previously the Split View panes stayed capped at about three quarters height.
  Text size is unchanged by this.
Resizable panes:
- The fleet launch terminal at the top, the Yaml File Handler status window and
  the Generated Preview can all be resized by dragging their bottom-right corner.
Servers > Statistics:
- Charts now use the same typeface as the rest of the app instead of a monospace
  one.
Log > Files:
- Log files are now grouped into categories - Error, Server, Thinking, Dashboard,
  Panel and Other - each with a count, inside the same Log Files panel.
Internal:
- Removed four dead declarations that were no longer referenced anywhere
  (an old console spawner, a superseded filename shortener, and two constants
  replaced by newer ones). No behaviour change.

## v2.47

timestamps, provider colours and timings, per-terminal scaling, sampler guide ranges.

Launch terminal:
- Every line in the fleet status terminal is now timestamped, with the
  [HH:MM:SS] stamp shown in blue. Lines added while the fleet comes up are
  stamped as they arrive.
Servers > Statistics > Provider Statistics:
- Bars now use each provider's own colour - the same colour that provider has
  in the terminals and elsewhere in the app - instead of a generic palette.
- Clicking a provider emoji under the Generation time chart opens a small
  readout showing that provider's generation, prefill and decode times.
- A little more vertical space between the emoji row and the chart.
Proxy > Dashboard:
- Split View now keeps text size, Auto/Manual mode and Text Scaling on/off
  separately for each of the two terminals, each with its own controls.
- The grey "source:" line now sits on top of the terminal instead of pushing it
  down, so the two Split View terminals stay aligned whether or not a source
  line is present. It is hidden entirely in Remote Access view.
Top bar:
- The title and icon glow is now a swivelling set of short sunlight rays that
  rotate around the centre.
Launcher > Sampler Guide:
- Every sampler and runtime flag now shows its usable value range rather than a
  single stock value, so nothing reads as a recommended default. For example
  --n-gpu-layers N with the range shown; use-case notes are unchanged.
- Where a description mentions another sampler, that name is now a blue link:
  hover it for a glow, click it to jump to that entry, which flashes to show
  where you landed.

## v2.46

brand animation, launch terminal, and per-terminal text scaling.

Top bar:
- The PandorumLLM title and icon now use a slow swirling glow (an orbiting light)
  instead of a pulse.
Proxy > Proxy Setup:
- In the PandorumLLM PC row, the Set IP Address button now sits directly beside
  the IP field, with Detect IP Address after it.
Launch:
- The status terminal now appears the moment you press Launch, opening with the
  "=== PandorumLLM <version> - launch stack ===" header while the servers spin up.
Proxy > Dashboard terminals:
- Full Window now scales the text with the window: the font grows by the same
  proportion the terminal is enlarged over its normal width (capped at 3x).
- Text-size scaling now persists per terminal view (Proxy / Thinking / Split
  each keep their own Auto/Manual, size and On/Off) instead of sharing one
  setting across all three.
- The grey "source:" log-file line is now a fixed single line, so the two panes
  in Split View stay vertically aligned (hover it to see the full path).
Remote Access view:
- The SkyrimNet YAML subtab is now hidden.
Proxy > SkyrimNet YAML (Yaml File Handler):
- Removed the green tick that appeared beside the Generate button.
- The status window under the buttons now timestamps each line, e.g. [14:07:22].

## v2.45

YAML tab cleanup + fleet status animation + statistics polish.

SkyrimNet YAML tab (now "Yaml File Handler"):
- Removed the Custom Spaces panel; the feedback line now sits directly under
  the action buttons.
- "Create providers.yaml" is now "Create providers.yaml File".
- "Open Yaml Folder" now opens the folder in Windows Explorer (native), not the
  in-app viewer.
- Generated providers now use an identical id and name per entry, e.g.
  Dialogue-1251-PandorumLLM for both. Regeneration recognizes this new naming
  as well as the previous id style, so old files clean up correctly.
Top bar + fleet status:
- The PandorumLLM title and icon now have a soft animated glow.
- The status light pulses while launching (yellow) and holds a steady glow when
  all servers are up (green). Pressing Terminate shows a pulsing red while
  shutting down, then goes to unlit grey once everything has stopped.
- While servers are running the Launch button reads "Running..." with a spinning
  indicator and is disabled; it returns to "Launch" once nothing is running.
Statistics:
- Server and provider charts now omit any entry with no data (no zero bars).
- Provider charts show just the provider emoji on the axis; hover any emoji to
  see the provider name and a subtle glow.

## v2.44

Remote Access IP fix + Getting Started subtab + a deeper runtime guide.

- The Remote Access address now uses the PandorumLLM PC IP you set in Proxy
  Setup (not an auto-detected/VPN adapter), so "Open from another PC at ..."
  shows the right address. The address is styled blue with a soft glow.
- The Remote Access "ON ..." status line is now green, and the extra
  "Remote access is ON and active now ..." note was removed.
- The "Getting started: create a .ps1 launcher!" walkthrough moved out of the
  Sampler Guide into its own "Getting Started" subtab under Launcher. The
  Sampler Guide keeps its intro text, now under a proper heading.
- Expanded the runtime reference: KV cache is split into KV cache (offload) and
  a new KV cache quantization entry (q8_0 / q4_0, needs flash attention);
  Concurrency (--parallel / --no-cont-batching) now explains why parallel is
  biased to 1; and Prompt batching (--batch-size / --ubatch-size) is its own
  entry. Each has its own description and cross-references the related knobs.

## v2.43

SkyrimNet YAML gets its own subtab + a VS Code style editor, plus IP/Helper fixes.

- Helper Step 2 is now PC-mode aware: 1 PC Setup only needs this PandorumLLM
  PC's IP; 2 PC Setup needs both this PC and the remote gaming PC. Step 2 shows
  incomplete (red) in 2 PC mode until the remote IP is set.
- Removed the "Set Same As PandorumLLM PC" button from Proxy Setup's PC IP
  Addresses (and its code).
- SkyrimNet YAML moved out of Proxy Setup into its own "SkyrimNet YAML" subtab
  under Proxy; the field emoji changed to a file emoji.
- New editor in that subtab, modelled on the Launcher Creator: an editable,
  persistent Base YAML (Save / Reset To Builtin) plus addable/removable Custom
  Spaces (your own provider blocks), all shown in a VS Code style editor with
  YAML syntax colouring, line numbers and the Dark+ colour scheme. A read-only
  Generated Preview shows the final Providers.yaml (base + spaces + the
  auto-generated PandorumLLM providers).

## v2.42

Folder Setup feedback + a consistent Title Case pass.

- The in-app folder picker ("Set Folder Path") now saves the chosen path
  immediately and shows a green "Path set" confirmation.
- Editing any path field shows a yellow "Path modified - click Save
  Settings" reminder until you save.
- Saving via Save Settings shows the same green "Path set" confirmation.
- Every button label and form field title is now Title Case (every word
  capitalized) so the UI reads consistently - previously some were
  sentence case (Save settings) and some Title Case (Open Folder). The
  Sampler Guide glossary keeps its own technical naming (Top-p, Min-p,
  XTC, etc.), and literal names (llama.cpp, providers.yaml, mmproj) are
  left as-is.

## v2.41

launcher templates now use --n-gpu-layers 99 (was 999). Both the

base and custom Launcher Creator templates, and the Sampler Guide note,
now agree on 99 - a number at or above any realistic model's layer
count, so every layer still offloads to the GPU (full offload) for the
models you would actually run. (999 also works and additionally covers
100B+ models with more than 99 layers, but 99 is the simpler, more
familiar value.)

## v2.40

terminal scaling and Statistics charts. Auto text scaling now

measures the longest line actually on screen and sizes the font so it
spans the terminal side to side, instead of assuming a fixed column
count - so the Proxy terminal fills its width, and the Thinking-context
terminal scales exactly the same way. Full Window now shows text at
full (100%) scale rather than halving it. The Servers > Statistics
graphs were rebuilt as upward vertical bar charts: bars grow up from a
baseline and scale with the graph width, each bar is labelled with just
the model name (with the .gguf extension dropped, no server title),
there is a numeric value axis down the left and the model / provider
names along the bottom, each bar prints its value on top, and both axes
have faint dashed gridlines. Switching to the Provider statistics
sub-tab now fetches fresh figures first and then fills the pane, the
same as the Server sub-tab.

## v2.39

interface polish. The Helper page highlight now rings the exact

element it points to - a field, a button, or every server row - instead
of tinting the whole card behind it; the "No .ps1 launcher yet?" prompt
moved to sit just above the assign-launchers step; the Getting Started
guide title now reads "Getting started: create a .ps1 launcher!"; the
guide's GPU-layers note now shows 999 to match the launcher templates
(999 is a sentinel meaning offload every layer - llama.cpp caps it to
the model's real layer count, so it just means "all of them" for any
model size); and the Remote Access toggle no longer claims a restart is
needed - it takes effect immediately, and now shows green text when on
and yellow when off instead of a popup. Also fixed a bug where the
Remote Access panel fetched its status with the wrong request method,
so the on/off buttons and address never refreshed.

## v2.38

two changes. The launcher scan now goes into subfolders. It

turned out .ps1 files were only found at the top level of a folder,
while models were found recursively - so a launcher tucked in a
subfolder of your launcher/models folder was invisible on the Servers
page even though the model beside it showed up. Launcher folders (the
ps1 launcher folder, the output folder and the archive) are now
scanned a few levels deep, matching how models are scanned; the
models folder itself is still scanned at its top level only, so large
model trees stay fast. And the Proxy terminals now default to manual
text scaling at 12 px (they were auto before) - existing setups still
on the old default switch over automatically, while any size you had
chosen yourself is kept.

## v2.37

fixes the Servers page not refreshing on navigation. The

Servers tab was the only tab that did not re-render when you clicked
onto it, so after changing folders the launcher dropdown kept showing
its previous contents until some other refresh happened. It now
re-renders when you open it, the same as every other tab - so a
launcher .ps1 you just made visible (including one found in your
models folder) shows up as soon as you switch to the Servers tab.

## v2.36

launcher/model discovery + guide polish. The app now scans

BOTH your launcher folder and your models folder for launchers AND
models, so if you keep a .ps1 and a .gguf together in one folder,
both show up no matter which folder field you set it in (the Servers
launcher dropdown was previously blind to .ps1 files sitting in the
models folder). Launcher Creator's Validate now checks the port: it
errors on anything that is not a whole number from 1 to 65535, and
warns on system/privileged ports (1-1023) and on the dynamic range
Windows uses for itself (49152-65535), steering you to 1024-49151.
On the Sampler Guide Getting Started, step 1 now has a click-to-copy
Hugging Face roleplay-models link, step 3 links straight to the
Launcher Creator, and the Connect-SkyrimNet and Launch steps were
reordered to match the Setup Helper. And in Folder Setup the
llama.cpp releases link is now click-to-copy as well.

## v2.35

small UI clarity fixes. On Proxy Setup, the 1 PC / 2 PC

feedback message now shows directly under the card title instead of
on the first IP address row. On the Setup Helper, step 1 is renamed
'Set folder paths' (it now goes green once your llama.cpp, launcher
and models folders are all set, and its how-to text lists all three).
And Folder Setup now marks the llama.cpp, ps1 launcher and models
folders with a 'Mandatory' badge so it is clear which paths are
required.

## v2.34

two fixes. Changing the ps1 launcher folder in Folder Setup

now fully switches to that folder everywhere - the Servers launcher
dropdown used to keep showing launchers from a previously-set folder
because the folder was added to a list instead of replacing it; it
now replaces cleanly, the same way the models folder already did, so
launcher and model choices stay in sync across the app when you
change folders. And the Launcher Creator's Validate no longer warns
about the vision (mmproj) and MTP drafter placeholders when those
are set to Disabled, nor notes the window title: those placeholders
only appeared in the template's header comment (documentation), and
the title is always filled with the template's own name at create
time. Validation now checks only real argument lines, so a genuinely
unfilled model, port or mmproj line is still caught. The vision and
drafter dropdowns now read 'Disabled' instead of a dash.

## v2.33

Launcher Creator and Sampler Guide polish. In the Creator,

switching a template's base launcher now keeps the samplers and
field choices you already made (they are re-applied onto the new
base instead of being wiped), and each editable template gained a
[Reset] button that clears its samplers and fields back to that base
template's defaults. On the Sampler Guide, the Getting Started steps
were rewritten to follow a model from Hugging Face through folder
setup, launcher creation and launch, and the steps that line up with
the Setup Helper now link straight to the matching Helper step
(clicking jumps to the Helper and highlights it). The sampler and
runtime cards were rewritten to be neutral definitions of what each
knob does and how it works - with the gauges and the in-Skyrim NPC
notes kept, and roleplay ranges suggested - rather than describing
one particular set of launchers.

## v2.32

two changes. Each Statistics chart now appears only once

it has data and then fills in live, so the page starts clean and
grows as generations happen (the charts stay stacked as rows, one
chart per metric with a bar per model inside). And the Log tab was
split into two sub-tabs: [Files] (the existing log-file list) and a
new [Errors] view. Errors lists this session's errors and warnings
as rows - each with a type tag, a one-line title and the related
text quoted in its own field (capped at 250 words so no row can
balloon) - most recent first. A row at the top shows the session
error total plus a per-type and per-level breakdown that grows as
new types appear. A 'show most recent' dropdown (10/25/50/100/250,
default 50) sets how many are kept, a 'per page' dropdown
(10/20/30/40/50, default 10) sets page size, and a [<] [1] [2] ...
[>] pager walks the pages. Collection is in-memory and session-only
(cleared on restart or by Clear Logs), so it adds no disk writes.

## v2.31

UI improvements across the Servers, Proxy and Dashboard

pages. First, four fixes on the Servers and Proxy pages. (1) On
the Server Slots page, assigning a launcher to a server now updates
that server's status line immediately - it changes from "(disabled
- no launcher assigned)" to the assigned launcher path right away
instead of only on the next refresh, so you get instant confirmation
the assignment took. (2) In the Launcher Creator, the Base launcher
preview labels its two persistent templates "Single GPU" and "Multi
GPU" in green, instead of printing the .ps1 file path for one and a
short name for the other - the two now read consistently. (3) the
shipped template set is confirmed to be exactly those two persistent
base templates plus one editable example launcher (seeded at first
run), with no stray or leftover templates; the last internal
placeholder name left over from the early versions was renamed out. (4) On Proxy
Setup, the "PC IP Addresses" confirmation is now live. After you
press "Set IP address" it reads "set: <the IP>", and the moment you
edit or clear that field it switches to a reminder to press "Set IP
address" again to save - the old behaviour left a stale "set" note
sitting next to an address you had already started changing.

And on the Proxy Dashboard, the terminals gained text-size
controls that apply to all three views (Proxy Terminal, Thinking
Content, and Split View). A new Auto / Manual toggle sits above
the terminals. Manual lets you pick an exact size from 8 to 24 px
from a dropdown; Auto sizes the text to fit the terminal width on
its own and re-fits whenever the window changes. The mode and the
chosen size are remembered between sessions, and a short note
("Auto text scaling" / "Manual text scaling") confirms which is
active. "Full Window" scales the terminal text to about half the fitted
size so it does not become oversized on a large monitor (Manual is
always there if you want it larger), and when the window gets too
narrow the log lines wrap instead of running off the edge.
While a terminal is maximized the normal size controls are
hidden, so Full Window also carries its own "Text scaling"
On/Off button: On keeps the auto-fit / manual sizing, Off holds
the terminal at a fixed size and stops it resizing with the
window.

Servers also gains a new "Parameters" sub-tab: a visual guide to
the settings that shape how your local models talk in SkyrimNet.
It explains each sampler (temperature, top-p, min-p, top-k and the
DRY penalty) with a little gauge showing where the fleet default
sits between calm and wild, plus the runtime and hardware flags
(context size, GPU layers, flash attention, the no-RAM-cache
convention, the draft/MTP model, the vision projector and GPU
pinning) and a note on the proxy-side thinking and Diary-grammar
behaviour - each with what it does, how it works and what to
expect when playing AI Skyrim. The guide covers each
sampler (temperature, top-p, min-p, top-k, DRY and the N-sigma
sampler) with what it does, how it works, what to expect in
Skyrim and how your own servers set it, plus a section on the
adaptive and newer samplers (dynamic temperature, typical, XTC,
adaptive-p - the adaptive min-p - and Mirostat), the sampler
chain, the runtime and reasoning flags, speculative decoding and
per-server profiles (dialogue, reasoning, meta and TTS) built from
the fleet's own launchers. And in the Launcher Creator, every
template now has clickable sampler cards (including the newer
adaptive ones) plus a sampler-chain dropdown with a Disabled
option; toggling a card or picking a chain rebuilds the sampler
settings in the template text into neat titled sections in the
.ps1 style, keeping any values you edited by hand. The base
templates now seed the full llama.cpp sampler chain by default so
your chosen params take effect both server- and SkyrimNet-side,
and on Proxy Setup every provider exposes each of the chain's
sampler params as a clickable value you can override per provider.
Samplers that clash by function are guarded too: Adaptive-P must
be the sole final truncator (only a mild Min-p may precede it), so
trying to enable it alongside Top-p, Top-k, Typical, N-sigma or XTC
(or vice versa) is blocked - the clicked card flashes red and a
note explains why and which sampler(s) to remove first. For a
template you have hand-edited, a [Validate] button scans the whole
launcher text and reports errors, incompatible or duplicate
flags, samplers set but missing from the --samplers chain (so they
have no effect), unfilled placeholders and structural problems,
graded as errors, warnings and notes. Separately, every
confirmation and message pop-up - Terminate, Exit, Launch,
delete/restore, save-profile and all error notices - now uses
PandorumLLM's own in-app dialog styled to match the panel, with
Enter/Escape support, instead of the browser's native alert boxes. The launcher tools
also moved into their own main [Launcher] tab (Creator, Inspector
and the renamed Sampler Guide), separate from [Servers], and the
Sampler Guide now opens with a Getting Started walkthrough that
takes you from setting folders and creating a launcher to running
the .ps1 with llama.cpp and launching a live server from the app.
The graphical Setup Helper gained a sub-step branching off the
"launchers assigned" box - "No .ps1 launcher yet?" - that jumps
straight to that Getting Started guide and highlights it.
The Servers tab gained a [Statistics] sub-tab with two views,
[Server Statistics] and [Provider Statistics], that graph live
performance and usage as stacked per-metric bar charts (one chart
per metric, one bar per server or provider). Server view covers
prefill/decode speed, response time, total and thinking-token
usage, generations, times loaded, accumulated queue time, cached
tokens, cache time saved, MTP draft acceptance/size and errors;
Provider view covers average generation time, input/output/thinking
tokens and errors. Figures use running incremental averages
(mean += (value - mean) / count) and simple totals, so nothing is
accumulated per request and memory stays flat - the whole feature
is a few arithmetic operations per generation piggy-backed on the
proxy, a small aggregates fetch only while the tab is open, and no
disk writes (session-only, cleared on restart). A [Monitoring:
On/Off] button pauses or resumes collection and a [Reset stats]
button clears the figures.

## v2.30

internal cleanup only - no change to how anything works. The

panel's source file had grown a large duplicated block: two copies of
the proxy manager, the settings / provider / recommend handlers and
about a dozen other functions, of which Python only ever ran the
second copy. That stale first copy - roughly 736 lines - is now
removed, and with it the long-standing trap where a fix had to be
applied to both copies or it silently did nothing. A few other dead
leftovers went too: the old update-check stub (the update check itself
was already taken out back in v2.18), a duplicate of the path-masking
helper, and an unused older allowed-folders check that a newer one had
replaced. Every function that stayed is byte-for-byte the copy that
was already in use, so the running behaviour is identical - this is
purely a size and maintainability fix (the file drops from about 5,600
to about 4,870 lines).

## v2.29

two changes. Each provider (including custom/added ones) now

gets a Revert params button that appears whenever it has forced
overrides - one click clears them all, so every param falls back to
whatever SkyrimNet / the server sends. And the remote Live Network
graph now looks the same as on the host: the GPU-to-server lines are
drawn and every line is coloured by GPU, instead of the GPU links
being missing and the server-to-provider links showing grey. This
was because the internal GPU key was being masked on the remote view,
breaking the graph's GPU/server matching; that key is not
host-identifying (the GPU uuid and index are still masked), so it is
now kept. Model titles remain shown as dots on remote, as before.

## v2.28

per-provider sampler monitoring and control. The proxy already

knows which provider each request belongs to (each provider has its
own port), so it now reads the sampler values SkyrimNet actually
sends for each provider and shows them per-provider on the Proxy
Setup page - so Dialogue, GM, Combat etc. now display their own real
values instead of one shared server number. Each value is also a
control: click a provider's chip to force an override, and the proxy
injects your value into every request for that provider (leaving the
others untouched); clear it (empty) to fall back to whatever
SkyrimNet sends. A forced value is shown in the accent colour and
marked "(forced)". The server-level launcher defaults are still shown
once per server in the header for reference.

## v2.27

two fixes. On the remote read-only view, the Live Network

buttons (Recommended Setup, Restore Default Providers) and the
profiles dropdown are now hidden - the graph itself still shows.
And the sampler parameter chips were corrected: they are a property
of the SERVER (its launcher .ps1 flags), not of each provider, so
they are now shown once per server and read from that server's
launcher rather than from the last request in the shared log. That
last-request reading is why every provider on a server looked
identical and often wrong - the server log records per-request
values with no way to tell which provider sent them, so it could
never be a reliable per-provider source. Server-level launcher flags
are the correct source and now drive the display.

## v2.26

two fixes. The Live Network graph (the GPU - server -

provider link lines) is now clearly kept on the remote read-only
view. And in Folder Setup, paths you type or paste are no longer
wiped when you use the folder picker for a different field: a
re-render now preserves any unsaved edits in the other boxes, so you
can mix pasting and picking and then Save settings once, and every
path sticks.

## v2.25

fixed the real cause of "2 PC Setup" reverting to 1-PC. The

setting was being saved as the text "False" instead of a true/false
value, which the interface then read as 1-PC on the next refresh -
so any later action (a GPU enable/disable, a theme change, or just a
background refresh) appeared to snap it back. It is now stored
correctly as a real boolean and stays put. Existing configs that
were already saved with the text value are repaired automatically on
load. Also added a lock so simultaneous actions can no longer
overwrite each other's saved settings.

## v2.24

two fixes. In 2-PC mode, pressing "Set IP address" or "Set

same as PandorumLLM PC" no longer makes the Remote PC row vanish or
snap back to 1-PC - an IP action now preserves your 1-PC/2-PC choice.
And in the Launcher Creator, toggling the Wrap button no longer
halves the editor's height: the code box now keeps a stable size (and
can be resized by dragging its bottom edge) whether wrap is on or off.

## v2.23

fixes. The "Pick a folder" window now has a Drives button in

the bottom-left to jump straight back to the PC root (drive list),
and the window itself can be resized by dragging its bottom-right
corner. Choosing "2 PC Setup" now correctly shows the Remote PC
(SkyrimNet PC) row straight away - previously only the confirmation
text appeared. Button icon/text spacing was audited across the UI
to ensure every icon has a space before its label.

v2.23 (cont.): widened the Permissions > Permission Tree so the
bullet text in each column has room and no longer runs into the
next column. Hardened the "2 PC Setup" button so the Remote PC row
appears the instant it is pressed (the row's visibility is now set
directly and immediately, not left to a re-render).

v2.23 (cont.): "2 PC Setup" no longer auto-fills or auto-detects
this PC's IP address - you enter both IPs manually and press Set for
each, as intended. Also fixed 2-PC not sticking: selecting it now
persists across page reloads and no longer occasionally snaps back
to 1-PC on its own (a background refresh could briefly overwrite the
choice before it committed; the panel now keeps your selection).

## v2.22

UI polish + templates. The in-app folder picker now uses

proper SVG icons for drives and folders (no more "??"), and its
list can be dragged taller from the bottom-right corner. On a
remote (read-only) PC the IP Addresses, PC GPUs and SkyrimNet yaml
panels are now hidden entirely rather than shown masked, and the
"read-only remote view" badge uses a real eye icon. The Permission
Tree was updated to reflect this. The Permissions "Settings"
sub-tab is renamed "Remote Access". In the Launcher Creator, the
"GPU (server pin)" dropdown is hidden when a single-GPU template is
selected (it has no card to pin). And the Base Launcher card now
has two persistent base plates with [Default] and [GPU pin]
buttons: Default is the GPU-agnostic single-GPU template (simplest,
for one-GPU PCs); GPU pin is for multi-GPU / dedicated inference
PCs and pins each server to a specific card. A short explanation of
each is shown when you switch between them.

## v2.21

UI + fixes. The Permissions tab now sits between

Customization and Helper. On the Permissions > Settings page,
Remote access is controlled by [On] / [Off] buttons next to the
title (On opens the read-only LAN view, Off removes it). The
in-app folder picker no longer shows broken "??" glyphs next to
drives. Picking a folder now saves it and refreshes immediately,
so a wrong llama.cpp folder (missing the server .exe) is flagged
right away instead of only after a reload. "1 PC Setup" is now the
default. The "Restore Default Providers" button moved to its
correct place - Proxy Setup > Live Network, next to Recommended
Setup (it was mistakenly showing on each server row). The Helper
"Check Completion Status" now includes the "yaml delivered to
SkyrimNet" step and correctly counts steps you skipped (e.g. a
skipped providers.yaml step no longer shows as outstanding).

## v2.20

added a second built-in launcher template, "Single GPU (no

GPU pinning)", for people with one PC and one GPU - it is identical
to the default template but omits the GPU-ID pinning line, so
llama.cpp just uses the only card. Pick it from the template
dropdown in the Launcher Creator; a hint there explains which
template suits your setup (single-GPU vs multi-GPU / separate
inference PC). The original template is now labelled to make clear
it pins the card by GPU ID. Also added a Safety & Trust section
(above) and every release now ships with a SHA-256 checksum you
can verify.

## v2.19

folder handling reworked so the app can't read or write

anything outside the folders you configure. The old "open in
Windows Explorer" behaviour and the pop-up folder/file picker
dialog are both gone, replaced by in-app views:
 - Setting a path (llama.cpp / launcher / models / yaml / log /
   output folders) now uses an in-app folder picker that shows
   ONLY folders - never files - so it can never surface an
   executable while you browse.
 - The "Open Folder" button now opens an in-app list that shows
   ONLY the relevant files for that folder (.gguf for models, .ps1
   for launchers, .log for logs, .yaml for the yaml folder) - never
   anything else, never an executable.
 - "Open Folder" was removed entirely for the llama.cpp folder, so
   its executables are never listed at all.
Under the hood, every path the app is asked to read, write, or open
is now checked against your configured folders (resolved to defeat
"..\" tricks and symlinks); anything pointing outside is refused,
and opening executable file types is refused outright. These file
views are host-only - a read-only remote viewer can't use them.

## v2.18

removed the online llama.cpp update check and the "open

releases page" web link. PandorumLLM no longer contacts GitHub or
any external site on its own - it makes no outbound internet calls
at all now. In Folder Setup, under the llama.cpp path, the two
buttons are replaced by the releases address shown as plain grey
text you can select or Copy, then paste into your own browser to
check for newer builds. (The panel still talks to your local model
servers and forwards SkyrimNet's requests to them - that is its
job - but it never phones home.)

## v2.17

remote-access safety + Permissions tab. The panel now has a

real two-state access model, enforced by the server on every
request (not by hiding buttons):
 - This PC (localhost): full control, exactly as before. Solo users
   see no change - no password, no prompts.
 - Same-LAN remote PC (opt-in): READ-ONLY. Can watch every terminal,
   full-window, set its own colours/wrap, and see the fleet status -
   but cannot launch, edit, write, or touch folders, and never sees
   real IPs, paths, GPU IDs or filenames (they are stripped out of
   the data server-side, not just blurred in the browser).
 - Outside/unknown: rejected outright.
Remote access is OFF by default (localhost only). Turn it on in the
new Permissions > Settings tab; it takes effect on the next launch
and shows the address to open from another PC. Permissions > Permission
Tree shows a diagram of exactly what each machine can do. Always-on
hardening was also added for every user: an Origin/Host guard that
blocks malicious web pages and DNS-rebinding from poking the panel,
and request size limits. SkyrimNet connects to the model servers
directly and is unaffected by any of this. No password is required -
the read-only wall is the boundary, and it is enforced server-side.

## v2.16

Restore Default Providers now only resets the shipped

default providers to their original state (title, port, priority,
thinking, and which server they belong on) and re-adds any that
were removed - it no longer deletes the custom providers you added,
which are kept exactly as they are. The confirmation prompt and
button tooltip were updated to match.

## v2.15

added (custom) providers can be removed again, while the

shipped default providers stay protected. Providers you add now
carry a "custom" flag and show a small x remove button; the
defaults have no remove button and the backend refuses to delete
them (use Disable, or Restore Default Providers to reset). Existing
configs are migrated automatically - any provider that isn't part
of the shipped default set is marked custom and becomes removable.

## v2.14

welcome pop-up cleaned up - removed the broken waving-hand

glyph (it rendered as "??"), dropped the "Thrilled to have you
here" opener, and corrected the description: PandorumLLM is a
control panel for the thinking proxy that powers SkyrimNet's AI
dialogue, with llama.cpp as the inference backend the proxy uses
(not a "llama.cpp fleet"). The Helper status log is taller (300px)
and can be dragged taller from its bottom-right corner. And Helper
step 2 is renamed from "both PC IPs set" to "IP addresses set".

## v2.13

five additions. (1) Both the Launcher Creator editors and

the Launcher Inspector now have a Wrap on/off toggle button at the
top-right above the text - off keeps the horizontal-scroll code
view, on wraps long lines. (2) On first launch a friendly welcome
pop-up greets you and offers to jump straight to the Helper page
(it only shows once). (3) The Helper page has a new [Check
Completion Status] button that inspects what is actually
done/registered and prints a checklist summary into the status
log, including a note that providers.yaml PLACEMENT into your
Modlist is manual and cannot be verified by the panel. (4) In
Proxy Setup you can no longer delete providers - the remove (x)
button is gone - but you can still disable/enable any of them. (5)
A new [Restore Default Providers] button sits next to [Recommended
Setup]; it resets every server's provider list to the shipped
defaults and deletes any custom providers, after a confirmation
prompt warning that custom providers will be removed.

## v2.12

fixed the Launcher Creator model / vision / MTP drafter

dropdowns coming up empty. The model list was fetched only once and
an empty result was cached as "already loaded", so if the Creator
was ever opened before the models folder was set (e.g. right after
an install), the dropdowns stayed empty until a full page reload -
even though models showed up everywhere else. Now an empty list is
treated as not-yet-loaded and re-fetched when you revisit the
Creator, the list is refreshed automatically when you change the
models folder in Folder Setup, and the dropdowns render safely with
a "set the models folder" hint when nothing is found instead of
silently blanking.

## v2.11

in the Launcher Creator, the --mmproj and --model-draft

lines are now conditional. When vision or MTP drafter is set to "-"
(the default, including the first time you open the page after an
install), the corresponding line is absent from the editor and
from any launcher you create - so a server won't refuse to start
over an empty <MMPROJ_PATH>/<DRAFT_PATH>. Selecting an actual model
injects the line back in, right after --model, with the real path;
switching back to "-" removes it again, with no duplicates on
re-select. The persistent Base template still carries both lines as
the reference format.

## v2.10

fixed the version label - the UI had been stuck showing

v2.6 because the version constant stopped getting bumped at v2.7,
so v2.8 and v2.9 only updated the exe's file-properties version,
not the string the page shows. It now reads v2.10 and the
packaging bump is verified so it can't silently drift again. The
emblem is also finally visible: the browser icon URL carried a
cache-bust tag frozen at v25 since v2.5, so every emblem change
from v2.6 onward was masked by the cached old icon. The tag is now
tied to the version, so the clipped-P emblem loads (a hard refresh
still helps the very first time). And the Log file cards now keep
View and Download stacked on their own line beneath the filename
for every card, instead of sliding up next to short names.

## v2.9

the emblem uses the older larger P (touches top and bottom of

the deltoid) but the bowl's overflow past the upper-right edge is
now clipped to the inner diamond, so that edge reads as a clean
straight diagonal instead of a bump. Baked into the exe and
favicon. The Log page files render as stacked card BLOCKS in a grid
(filename with View/Download on top, size and dates below each) -
not the flat one-line rows from before. The Split View Terminal
gained its own Full Window button, matching the other two
terminals (it expands both feeds side by side to fill the screen).
The three terminal sub-tab buttons (Proxy Terminal / Thinking
Content Terminal / Split View Terminal) are now grey with white
text like the rest - previously they were lime-green with dark
text because they carried no button class (this is the set the
screenshot flagged; the Generate providers.yaml button was already
fixed). And Reset steps now forces EVERY step back to red -
including the ones that were genuinely done, not just the skipped
ones. Each step un-forces itself the moment you click through to
it (or you can re-tick it), and Revert reset restores the whole
prior state as before.

## v2.8

the emblem's P is enlarged to the maximum that fits inside

the inner deltoid - taller stem and a wider bowl, computed against
the rhombus edges so nothing crosses them. The Launcher Creator's
vision and MTP drafter dropdowns drop the "Disabled" option; the
"-" (empty) entry is the default and still removes the line on
Create. The terminal background swap now works on all three
terminals: two hardcoded CSS id-rules (#tail-dashboard and
#tail-thinking) were forcing pure black at a higher specificity
than the toggle class, so Proxy Terminal and Thinking Content were
stuck black - those rules are gone and the midnight/black toggle
governs every terminal. Clicking 1 PC Setup now actually hides the
Remote PC row: the show/hide logic lived at the tail of the click
handler (so it only fired on the next click and raced the repaint)
and now runs inside renderRouting, every time the pane is drawn.
And the Generate providers.yaml button is restyled grey with white
text to match the other buttons (the three terminal buttons were
already grey).

## v2.7

the Logs page is restored to the original inspector design

(the v0.1/v2.3 one) - a LOG FILES list where each file has a View
button that tails its contents into a viewer below, plus a
Download link. Per your screenshot the files are now stacked as
full-width cards (name, size, created, last-edit, View, Download)
one per row instead of the wrapped grid. The later chip/filter/
pagination Logs rewrite is gone. The emblem's P is redrawn smaller
so it sits fully inside the inner deltoid with clearance on every
side - no part of the letter crosses the diamond edges.

## v2.6

the Thinking colorizer is rewritten from scratch. The old

version injected color spans and then let later rules (quotes,
provider names) run over the already-injected markup - so the
span's own style="color:#..." got matched and re-wrapped, dumping
literal "color:#e0c23c"> text into the terminal. The new painter
tokenizes each line ONCE over the raw text and escapes every piece
exactly once, so spans can never be re-processed. Verified against
your exact screenshot line: separators/[time] cyan, provider emoji
+ name in its dashboard color (single span), (~N tok est) magenta,
*starred* inner text cyan, "quoted" text golden, and zero escaped
markup leaks (spans balanced 5/5). Each terminal now has a
Background button to swap between "midnight" (the split-view blue-
black you liked) and pure black; the choice persists. The Logs
page keeps the SkyrimNet styling but stacks the file cards in a
full-width vertical list, and clicking any file opens an inspector
showing its contents (last 200 KB) with a Close button. 1 PC Setup
now reads the IP correctly (detect-ip returns a list - the old
code read a singular field that was always undefined, hence the
false "could not detect" error) and hides the Remote PC row since
both addresses are the same machine; 2 PC Setup restores it. The
emblem is simplified to just an uppercase P inside the deltoid,
touching top and bottom, no wings or tail.

## v2.5

hotfix + layout correction. v2.4's Logs rewrite accidentally

deleted the DASH_PAL color palette that both terminal painters
depend on - every tail refresh died with a ReferenceError, which
is why the Dashboard, Thinking and Split terminals all went blank
(error_2.log caught it precisely). The palette is restored and the
test harness now exercises dashColor with real agent names so a
missing palette can never pass again. The terminal layout is now
as you meant it: [Dashboard] and [Proxy Setup] stay as the two
sub-tabs, and INSIDE Dashboard sit three inner buttons - Proxy
Terminal, Thinking Content Terminal, Split View Terminal (the
split pane was also rescued from being accidentally nested inside
the thinking pane, which kept it invisible). PC IP Addresses
gained [1 PC Setup] (detects this PC and sets BOTH addresses to it
- yes, one machine running SkyrimNet and PandorumLLM together
works exactly like that) and [2 PC Setup] (sets this PC, then
golden-highlights the remote field for you). Pressing Set with an
empty field now answers "No IP address was entered" instead of
saving nothing. The new emblem is cache-busted (?v=25) so browsers
drop the old favicon; if Windows Explorer still shows the old exe
icon, that is the Windows icon cache - it refreshes on its own or
with a sign-out, the file itself already carries the new emblem.

## v2.4

new emblem - a closer homage to the classic winged-diamond

sigil with a bold P as the central figure (drawn original, since
the actual game mark is trademarked); baked into exe, favicon and
header. The Logs page is reorganized SkyrimNet-style: LOG FILES
cards with sizes, timestamps and Download buttons (server logs,
dashboard/thinking captures, panel and error logs), clickable
ERROR/WARN/INFO count chips, a filter bar with level and page-size
selectors plus live search, paginated LOG ENTRIES, Refresh and
Clear Logs. Creator vision and MTP drafter dropdowns start empty
and offer Disabled instead of N/A - empty or Disabled both drop
the line on Create. The GPU blur toggle finally works: the blurred
spans now sit above the editor textarea (they were physically
unreachable before - clicks landed on the textarea layer). The
Thinking colorizer no longer colors Label: text; only *starred*
text is cyan, and quoted text - double or guarded single quotes -
renders golden. Thinking Content moved off the main stack: the
Proxy page now has Proxy Terminal, Thinking Content Terminal,
Split View Terminal (both feeds side by side, independently
painted and scroll-held) and Proxy Setup. The folder picker was
rebuilt a fourth time: the pwsh process now launches with normal
window rights (hidden style instead of no-window), shows an
activated near-invisible owner window at screen center, and keeps
the AttachThreadInput foreground ticks - the strongest legitimate
combination Windows allows.

## v2.3

yaml providers are named <Function>-<port>-PandorumLLM

(e.g. Dialogue-1251-PandorumLLM). Auto-refresh now repaints the
Proxy Setup pane too, and assigning a launcher re-renders it
immediately. Helper boxes deep-link: clicking a step jumps to the
exact field and flashes it with a Discord-style golden highlight.
Reset steps snapshots the clearable flags (yaml generated /
delivered / manual ticks / skips) before clearing them, and the
new Revert reset button restores that snapshot; steps that mirror
real infrastructure (IPs set, GPUs enabled, launchers assigned)
stay green by design - resetting those would mean deleting real
config. Launch history now records the GGUF for launchers that use
a $modelPath variable (the E2B style) - the fleet script gained
the same fallback the panel already had. The Thinking colorizer
keeps every symbol white: only the text between *stars* and
line-starting Label: text turns cyan. Live Network server nodes
show their selected GGUF - green when serving, yellow when
selected but down. And PandorumLLM has a new emblem: an original
white winged sigil in the Skyrim spirit, transparent background,
shipped as ico/svg/png and baked into the exe.

## v2.2

the launcher editor converts the legacy hardcoded

llama-server.exe path to your Folder Setup path (old saved content
included), and the default template's port line is a real <PORT>
placeholder with tolerant matching, so the port field finally
lands. GPU UUIDs stay blurred until clicked - click again to
re-blur. The editor has a proper draggable scrollbar. The three custom
templates were removed per request (the multi-template machinery
stays for the future). The llama.cpp path field checks itself as
you type and shows a red "llama-server.exe not found in this
folder" when wrong. Selecting a launcher still adopts its port,
now with a yellow "server port changed X >> Y" notice on the slot.
Dashboard delay units render as "1604 ms" - green number, white
unit, space between. Full Window terminals scale their font with
the window height. The Thinking terminal is fully colorized: agent
names get their dashboard colors AND emojis injected, separators,
[time], leading bullets, *emphasis* and "Label:" fields are cyan,
(~N tok est) is magenta, [port] stays dim. SeverActions is
globally a scroll emoji now (one-time migration included). Both
terminals hold your scroll position during auto-refresh unless you
are already at the bottom. Helper step 7 is a manual green tick -
there is no reliable way to auto-confirm delivery. Launch history
shows the GGUF model name under each launcher path (recorded by
the fleet script at spawn).

## v2.1

the custom templates are now truly generic - every brand, GPU

model, quant name, model name, fleet reference and log-tag was
swept (only neutral engineering terms like "imatrix" remain), and
llama-server.exe is no longer assumed at C:\llama.cpp-cuda: all
templates use <LLAMA_EXE>, filled from your Folder Setup llama.cpp
path at create time and shown live in the editor. Dropdowns are
WYSIWYG now: picking a model, mmproj, drafter, GPU pin or typing a
port rewrites the actual launcher lines in the editor instantly
(N/A restores the placeholder so the line is dropped on Create),
with previous values tracked so re-edits replace cleanly.

## v2.0

SmartScreen - the warning appears because the exe is unsigned

and the zip carries Windows' downloaded-from-internet mark. Two
fix: right-click the ZIP before extracting > Properties > Unblock,
and the mark never reaches the files at all. If you forget, clicking
More info > Run anyway teaches SmartScreen permanently on that
machine, and the panel clears the mark from its own folder on every
start, so it only ever has to be answered once. The
exe now carries full version metadata (publisher, description) so
the dialog at least names it properly. Grammar-rail and reasoning
badges only appear when a provider's thinking box is actually
checked - unchecked providers stay clean. All buttons, inputs,
dropdowns and sub-tabs now use Plus Jakarta Sans (code areas stay
monospace). Pandorum leads the theme presets; OpenRouter remains
the default. Launcher Creator: every template card has a template
dropdown (PandorumLLM default plus a set of custom example
templates built from real production launchers - paths, GPU pins,
ports and model names parametrized, every calculation and harness
intact), a GPU (server pin) dropdown listing
detected cards (writes CUDA_VISIBLE_DEVICES; N/A removes the line),
and a port field. GPU UUIDs are blurred in the editor and Inspector
at all times - screenshot-safe while the real value stays in the
file.

## v1.9

the Helper has a bridge step - "I manually set up providers

in SN UI" - sitting under the second row with its own arrows from
step 6 to step 8; press its green check to mark it done and steps
6 and 7 turn green with it (Reset steps clears it too). A new
Customization tab offers eleven theme presets with live previews
(OpenRouter, the original Pandorum blue, Dragonborn, Parchment,
Silver-Blood, Stormcloak, Imperial, Terminal, Dwemer, Nightingale,
Aurora) plus per-element color pickers that apply live and persist
as a Custom theme. Terminals intentionally stay dark so log colors
keep their contrast. The whole UI now uses Plus Jakarta Sans
(loaded from Google Fonts, falling back to Inter/Segoe offline);
terminals use a brighter, larger coding font - they stay monospace
because the dashboard columns are space-aligned and a proportional
font would break them. Folder Setup captions are white and bigger.

## v1.8

reasoning state is now read from the launcher ps1 itself

(authoritative; the log banner is only a fallback), so every server
gets a correct amber badge - server 2's launcher simply never
mentioned it in its banner. Diary answered: its GBNF grammar rail
constrains output from the first token, so thinking can never
appear there even when enabled - it now wears a puzzle-piece badge
explaining that. The folder/file picker uses AttachThreadInput to
take the foreground (the canonical Windows fix). Setup is now
Folder Setup; the yaml card is SkyrimNet yaml with an Open yaml
Folder button. Profiles appear on the Servers page too. Top-right:
a clock with an auto-refresh dropdown (Off/1s/5s/10s). The header
carries the PandorumLLM icon, and a fleet status dot lives next to
Launch: black = not running, pulsing yellow = launching, orange =
partial, green = all serving; the launch log gets a green line per
server as it comes up and a final "fleet ready" confirmation.

## v1.7

server-to-GPU drag works (the drop sent the wrong parameter

name to the edit API - "unknown slot" was the tell). Sampler chips
are finally faithful: values are paired to names by column position
in the harness table, so a blank penalties column can no longer
shift everything left or leak a timestamp into temp. Providers on a
server whose launcher runs reasoning OFF now show an amber warning
next to the thinking checkbox - the per-request thinking switch can
only engage on servers launched with --reasoning on (that is why
only the 1238 crew could think). The accent lime is deeper and
greener to match OpenRouter's button.

## v1.6

Recommended Setup no longer demands the yaml or the IPs - the

only functional requirement left is a detected GPU and at least one
provider; the Launch button remains the single place that reminds
you of unfinished Helper steps. Saving a profile now auto-selects
it in the dropdown. The Dashboard tab is now called Proxy, and the
inner Dashboard Terminal is simply Dashboard. Dashboard log colors:
all numeric values green, thinking-token estimates (~N) magenta,
words and separators white, timestamps cyan, ports dim, agents in
their own colors. The whole UI wears an OpenRouter-inspired skin:
near-black neutral background, lime accent on Launch, green stats,
Inter/Segoe typography with tabular numerals.

## v1.5

IMPORTANT - press Ctrl+F5 once after upgrading. The panel now

sends no-cache headers and shows a warning banner if your browser is
displaying an outdated cached UI (that cache was behind the ghost
budget box, vanished Helper button/skips, and re-glitched size
buttons). The live server windows no longer spam
System.Collections.Hashtable (a PowerShell splatting typo in the log
composer - the srv log files themselves were already correct). The
Live Network is interactive: drag a provider onto a server, or a
server onto a GPU, to relink them - changes apply instantly through
the same APIs as the cards. Recommended Setup feedback now survives
the page re-render (that is why it looked like it did nothing), and
a Profiles dropdown with Save/Delete sits next to it - each profile
snapshots the whole Proxy Setup (GPU enables, server-GPU pairing,
provider layout, both IPs). Sampler chips only show values actually
read from each server's log now - "-" until the first log exists.
The MO2/drop-in button is gone; the Generate message and Helper
step 7 spell out the real destination:
<Modlist>\overwrite\SKSE\Plugins\SkyrimNet\config\Providers.yaml
(or use [Create Providers.yaml] and pick that folder). Every Helper
step now prints a plain-language how-to in the terminal below.

## v1.4

thinking is now genuinely controlled per provider - the proxy

injects chat_template_kwargs.enable_thinking=false into every
request of a provider whose [thinking] box is off (and strips it
when on), exactly like the original SkyrimNet proxy. Leave your
launcher's --reasoning flags as they are; the toggle works live
with no restarts. The thinking-budget box was removed (that value
lives in the ps1 and needs a server restart anyway). Sampler chips
are honest now: green = value read from the launcher ps1 (parsed
only from the $llamaArgs block, single or double quotes), cyan =
live value read from the running server's log, yellow "-" = not
set anywhere visible. Server srv logs are captured by composing
PowerShell's information records (transcripts write every
Write-Host fragment on its own line - that was the shredded-log
cause), so the file finally matches the live window, colors intact
in the window. Dashboard terminal now colors bracketed timestamps,
ports, tps and seconds too. The Full/Normal window buttons work
(they were static HTML with unexpanded code in v1.3 - sorry).
Recommended Setup also pairs launcher-assigned servers to GPUs by
size and priority, reports with a tick, and surfaces any failure
instead of dying silently. Helper steps each have a skip button
(dashed border when skipped) plus a Reset-steps button. Launcher
Creator and Inspector both use VS Code-style PowerShell coloring;
the Creator edits through a live highlight overlay. The panel is
plain HTTP on your LAN - browsers note "not secure" because there
is no TLS certificate; nothing leaves your wired network.

## v1.3

the zip now contains a PandorumLLM folder (extract to C:\ and

you get C:\PandorumLLM - do not extract INTO an existing install or
it will nest). Server ports now always follow the assigned launcher
ps1 (manual port edits are refused while a launcher is assigned).
Folder/file pickers fight much harder to appear in front of the
browser. Set-IP, yaml, and Recommended Setup actions all confirm
with a green tick; changing the panel IP after generating warns you
to regenerate. Generating providers.yaml now REQUIRES the panel IP
(no more silent fallback to a VPN adapter address). The MO2 button
is now "Compress as drop-in file": the zip starts at overwrite\...
- drop its CONTENT into your Modlist root folder. Thinking is off
by default for all providers, and each provider has a thinking
budget box (injected per request; 0 also disables thinking via the
chat template - no server restart needed). Sampler chips (temp,
top_p, min_p, top_k, dry) sit on every provider: yellow = launcher
uses the base default, green = set in the ps1; click to edit - the
value is written into the launcher file itself, so restart that
server to apply. Server terminal logs are captured via transcript
now, so harness lines stay composed instead of one word per row.
Dashboard terminal is colorized (agents, times, ports); Thinking
Content stays white. Both terminals have a Full Window toggle. The
Live Network graph is color-coded per GPU chain and vertically
centered. New Helper tab: an interactive setup flowchart - boxes
turn green as you complete steps, click a box to jump to that
setting, with a log terminal underneath; Launch warns if setup
steps are incomplete. A separate TTS starter script is no longer
included.

## v1.2

fixed a config-migration bug (a stray reference left every

config load crashing once GPUs were detected - it killed the state
API, the UI, and even the handoff that lets a new launch replace the
old one, which is why relaunching reported no ports answering).
Structural guarantees added: startup can no longer die silently
(any failure writes logs\STARTUP-CRASH.log and shows a message
box); every response carries an X-App header so a stuck instance is
recognized even when its API is broken - it gets a handoff request
and, failing that, is force-closed before the new panel claims the
port; config saves are atomic with torn-read retry. Launch is also
snappier: the web server binds within ~1 second and the page loads
immediately while GPU detection and proxy listeners initialize in
the background; the exe polls faster and opens the browser sooner.

## v1.1

Proxy Setup blank-page fixed (the Live Network graph read a

status field the routing payload never had - caught by the built-in
browser error reporter, see error_N.log). Folder/file pickers now
force themselves in front of the browser. Assigning a launcher to a
slot auto-adopts the launcher's port. Launcher Creator dropdowns
edit the params live: picking a model/vision/drafter rewrites its
line in the editor, N/A removes it, and the title follows into the
header.

## v1.0

port probing is bind-truth based (transparent proxies, phantom

answerers and Windows reserved ranges can no longer fake "taken" or
"free"), and PORTERROR.log now reports per-port WHY, including the
netsh excludedportrange check for Hyper-V/WSL reservations. Proxy
Setup gained a Live Network card: an SVG map of GPU >> server >> SN
provider with status-colored lines (dashed red = listener not live).
GPUs and providers have Enable/Disable - disabled items leave the
map, pairing dropdowns, listeners and yaml generation. [Recommended
Setup] auto-pairs enabled providers by hierarchy (high tier on the
biggest GPU's first server, low tier beside it, utility spread over
the remaining GPUs) - requires both IPs set, detected enabled GPUs,
and a generated providers.yaml.

## v0.8

panel ports: 50607 -> 50617 -> 50627 -> 50637 -> 50647 (first free wins;

a running PandorumLLM on one of them hands off gracefully; foreign
occupants are simply skipped). The check runs first thing, kill-free,
and fails inside 5 seconds: if all five are taken you get a message
box plus logs\PORTERROR.log with exact netstat + edit instructions
(the candidate list sits on one clearly marked line at the top of
fleet-panel.py). panel-port.txt records the port actually chosen. UI is now push-updated over SSE
(no periodic refresh): user actions, proxy traffic, and server
status changes render immediately. Server ports show RED with a
warning when the port is busy or collides with another slot /
provider / the panel. Proxy Setup gained a SkyrimNet Providers card:
Add reads your current Providers.yaml, Generate appends
PandorumLLM-<Agent>-<port> providers (endpoint = PandorumLLM PC IP,
all passwords: 1234) below your entries with a persistent green tick
on success, Create writes Providers.yaml to the output folder from
Setup, and Create as MO2 mod packs it as
SKSE\Plugins\SkyrimNet\config\Providers.yaml. Fresh installs
scaffold ps1-launchers\, logs\, models\ and providerYAML\ inside
the PandorumLLM folder and default the paths there; llama.cpp path
shows a placeholder until set.
