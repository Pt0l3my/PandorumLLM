PandorumLLM v3.75 Beta - local LLM stack for SkyrimNet, all in one folder
============================================================


================================================================
SAFETY & TRUST
================================================================

PandorumLLM is a free, open-source, solo-built tool for the SkyrimNet
community. Please read this before running it.

WHAT IT DOES TO PROTECT YOU
 - Runs entirely on your own machine. No phone-home, no telemetry,
   nothing is sent about you or your setup. The single exception is
   the "Check for update" button under the llama.cpp path in Folder
   Setup: pressing it asks github.com for the newest llama.cpp
   release number, and nothing else. Never press it and PandorumLLM
   makes no outbound internet calls at all.
 - File access is contained: it can only read or write inside the
   folders you configure (llama.cpp / launcher / models / yaml /
   log / output). Paths that try to escape those folders (via "..\"
   or symlinks) are refused, and opening executable file types is
   refused outright.
 - Remote access is OFF by default. When you enable it, it is
   same-LAN only and READ-ONLY - other PCs can watch the terminals
   and fleet status but cannot change anything, and your IPs, paths,
   GPU IDs and filenames are stripped out before the data ever
   leaves this PC.
 - It blocks other web pages from sending commands to the panel in
   the background (Origin/Host checks; also stops DNS-rebinding).
 - No account, no login, no cloud, no payment - there is nothing
   for anyone to steal.
 - SkyrimNet talks to your model servers directly and is unaffected
   by any of the above.

WHAT I CANNOT PROMISE (please read honestly)
 - It is UNSIGNED. Windows SmartScreen will warn you when you run
   it ("unknown publisher"). This is expected for indie/community
   tools and does not by itself mean anything is wrong - but it
   also means Windows cannot vouch for the file for you.
 - It is a solo-built BETA. It has not been audited by a security
   team, and no software is ever completely risk-free.
 - A PC that is already compromised (existing malware/keylogger)
   is beyond what any application can protect against.

HOW TO VERIFY IT IS REALLY MINE AND UNTAMPERED
 - It is OPEN SOURCE - read exactly what it does. That is the real
   guarantee here, stronger than a signature on a black box.
 - BUILD IT YOURSELF if you would rather not trust my files - the
   launcher .exe source is included (launcher-src/), and the app
   itself is plain Python you can run directly.
 - Every release has a published SHA-256 checksum. Hash your
   download and compare it to the value on the release page - if it
   matches, it is my file, unmodified. On Windows:
       certutil -hashfile PandorumLLM-vX.Y-Beta.zip SHA256

BY USING PANDORUMLLM YOU ACKNOWLEDGE THESE POINTS AND ACCEPT THE
RISKS OF RUNNING COMMUNITY-MADE SOFTWARE. It is provided as-is,
without warranty of any kind; you use it at your own risk and take
responsibility for doing so.

Extract this zip into any folder, e.g. C:\PandorumLLM\ (all paths
are relative to the folder, so it can live or move anywhere)
Safe to extract over an existing copy: fleet-config.json,
fleet-history.json, logs\ and the ps1-launchers\ archive are not in
the zip and survive. Old configs are migrated automatically (new
"settings" and "creatorSlots" sections are added on first run).

  PandorumLLM.exe            <- double-click: THE way to start it.
                                Custom icon, one UAC prompt. Always
                                overwrites a running panel (old panel
                                process is killed, LLM servers are
                                left untouched), then opens the page
                                only once the new instance answers.
                                Unsigned exe: SmartScreen may warn on
                                first run (More info -> Run anyway).
  launcher-src\              exe source (launcher.cpp, MinGW build)
  force-stop.bat             <- last resort only: stops everything this
                                folder started, when the panel will not
                                open or will not answer. Normally you
                                use Exit in the panel instead.
  fleet-panel.py             the PandorumLLM panel (http://localhost:50607/)
  launch-llm-fleet.ps1       config-driven fleet spawner
  launcher-template.ps1      Base template for the Launcher Creator
  templates\                 extra Creator base templates
  fleet-config.default.json  seed config (copied to fleet-config.json)
  ps1-launchers\             auto-populated launcher archive
  logs\                      created on demand (path editable in Setup)

Panel tabs (vertical): Servers | Dashboard | Thinking Content |
Setup | Log. Servers has sub-tabs Server Slots | Launcher Creator |
Launcher Inspector; Dashboard has sub-tabs Dashboard Terminal |
Setup (the SN routing editor).

THE THINKING PROXY IS NOW BUILT IN (ported from SkyrimNet-Proxy.py):
PandorumLLM itself listens on every SN provider port (Dialogue 1251,
GM 1252, ...) and forwards each into the server slot the provider
sits in - including the Diary GBNF grammar rail, the GPU priority
gate (keyed on each slot's editable "gpu" tag; slots sharing a tag
gate against each other), and reasoning harvesting into the
Thinking Content tab (per-provider "thinking" toggle). Listeners
come up with the panel and re-bind live when routing changes.
Dashboard > Proxy Setup - hierarchy: GPU >> server >> server port >>
SN provider port. GPUs are auto-detected via nvidia-smi at every
launch ([Detect GPUs] re-runs it), with the AIB brand read from the
PCI subsystem vendor (ASUS/ZOTAC/MSI/... - unknown vendors show the
raw id) and the full UUID blurred until clicked; assign each server to a GPU with
its dropdown - servers auto-name themselves after their detected
brand and model (numbered when a card hosts several) until
you rename them manually - priority gating is per GPU, so servers sharing a card
gate against each other. Every provider card has an emoji picker
(shown in the dashboard/thinking logs), title, 4-digit port,
priority (0 high blocks lower tiers on the same GPU for up to 8s,
1 normal, 2 low) and the thinking toggle.
Drag a provider card onto another server slot to
re-route it; edit titles, 4-digit ports, and thinking per provider;
add/remove providers and slots. PC IP Addresses card: detect/set
the PandorumLLM PC IP (what SkyrimNet should point at) and the
Remote (SkyrimNet) PC IP - once a Remote IP is set, provider ports
only accept connections from those two machines + localhost. Priority tiers and the Diary
grammar flag are seeded in fleet-config.json (editable there).
The old launch-thinking-proxy.bat is gone from the stack; the
original SkyrimNet-Proxy.py on disk is untouched but would collide
on ports if run alongside the panel.

Header buttons: [Launch] re-syncs the embedded proxy listeners and
starts every ENABLED slot (minimized, tee'd logs). [Terminate]
stops all LLM servers, panel stays up. [Exit] shuts down the panel
AND all servers. Closing the last browser tab prompts (the
browser's generic leave dialog - custom text isn't allowed by
browsers, and a refresh triggers it too) and then does the same as
[Exit]; a crashed browser is detected within ~2.5 minutes. This
behavior can be turned off with the "exit when the last tab closes"
checkbox in [Setup] - recommended if you watch the panel from the
gaming PC and close that tab mid-session. Restarting via the
exe or bat now ALWAYS overwrites a stale panel (running servers are
left untouched). [Terminal] on a running
slot restores its minimized window to the foreground. Green PP/TG t/s readouts are parsed from
the standard llama-server timing lines in each server's log.

Setup: llama.cpp folder (with update check against the llama.cpp
GitHub releases + button to the releases page), ps1 launcher folder,
Base template file, launcher output folder, log folder, models
folder. Every path row has [Find Folder] / [Find File] (native folder/file picker - the
dialog opens on the machine running the panel, so use it locally,
not from a remote browser) and [Open Folder] (Explorer).

Launcher Creator: a persistent read-only Base template plus 1-20
editable templates (title, line-numbered param editor, mandatory
model pick, vision/mmproj or N/A, MTP drafter or N/A). [Create
launcher] writes a .ps1 into the output folder; <MODEL_PATH> etc.
placeholders are substituted, lines whose placeholder is N/A are
dropped, and the trailing self-invoke line points at the new file.

Log tab: rotating logs in the log folder - per server slot
srv_<slotid>_1..5.log (oldest reused at 5), dashboard/thinking kept
to the last 5 sessions, plus error_1..20.log (oldest reused at 20)
which inherits errors from every slot log, the proxy, the fleet and
the panel itself. All viewable and downloadable with size/dates.

What does NOT live here: your llama.cpp launchers, any TTS engine,
and your model weights - each kept in its own folder.

v0.7 ships release-generic: fresh installs start with empty paths
(the Setup tab shows a first-run banner), three unnamed server
slots, and the 13 SkyrimNet providers parked on server 1 ready to
be dragged onto servers. Existing fleet-config.json files are
untouched by upgrades.

v0.8: panel ports: 50607 -> 50617 -> 50627 -> 50637 -> 50647 (first free wins;
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

v1.0: port probing is bind-truth based (transparent proxies, phantom
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

v1.1: Proxy Setup blank-page fixed (the Live Network graph read a
status field the routing payload never had - caught by the built-in
browser error reporter, see error_N.log). Folder/file pickers now
force themselves in front of the browser. Assigning a launcher to a
slot auto-adopts the launcher's port. Launcher Creator dropdowns
edit the params live: picking a model/vision/drafter rewrites its
line in the editor, N/A removes it, and the title follows into the
header.

v1.2: fixed a config-migration bug (a stray reference left every
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

v1.3: the zip now contains a PandorumLLM folder (extract to C:\ and
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

v1.4: thinking is now genuinely controlled per provider - the proxy
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

v1.5: IMPORTANT - press Ctrl+F5 once after upgrading. The panel now
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

v1.6: Recommended Setup no longer demands the yaml or the IPs - the
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

v1.7: server-to-GPU drag works (the drop sent the wrong parameter
name to the edit API - "unknown slot" was the tell). Sampler chips
are finally faithful: values are paired to names by column position
in the harness table, so a blank penalties column can no longer
shift everything left or leak a timestamp into temp. Providers on a
server whose launcher runs reasoning OFF now show an amber warning
next to the thinking checkbox - the per-request thinking switch can
only engage on servers launched with --reasoning on (that is why
only the 1238 crew could think). The accent lime is deeper and
greener to match OpenRouter's button.

v1.8: reasoning state is now read from the launcher ps1 itself
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

v1.9: the Helper has a bridge step - "I manually set up providers
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

v2.0: SmartScreen - the warning appears because the exe is unsigned
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

v2.1: the custom templates are now truly generic - every brand, GPU
model, quant name, model name, fleet reference and log-tag was
swept (only neutral engineering terms like "imatrix" remain), and
llama-server.exe is no longer assumed at C:\llama.cpp-cuda: all
templates use <LLAMA_EXE>, filled from your Folder Setup llama.cpp
path at create time and shown live in the editor. Dropdowns are
WYSIWYG now: picking a model, mmproj, drafter, GPU pin or typing a
port rewrites the actual launcher lines in the editor instantly
(N/A restores the placeholder so the line is dropped on Create),
with previous values tracked so re-edits replace cleanly.

v2.2: the launcher editor converts the legacy hardcoded
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

v2.3: yaml providers are named <Function>-<port>-PandorumLLM
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

v2.4: new emblem - a closer homage to the classic winged-diamond
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

v2.5: hotfix + layout correction. v2.4's Logs rewrite accidentally
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

v2.6: the Thinking colorizer is rewritten from scratch. The old
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

v2.7: the Logs page is restored to the original inspector design
(the v0.1/v2.3 one) - a LOG FILES list where each file has a View
button that tails its contents into a viewer below, plus a
Download link. Per your screenshot the files are now stacked as
full-width cards (name, size, created, last-edit, View, Download)
one per row instead of the wrapped grid. The later chip/filter/
pagination Logs rewrite is gone. The emblem's P is redrawn smaller
so it sits fully inside the inner deltoid with clearance on every
side - no part of the letter crosses the diamond edges.

v2.8: the emblem's P is enlarged to the maximum that fits inside
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

v2.9: the emblem uses the older larger P (touches top and bottom of
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

v2.10: fixed the version label - the UI had been stuck showing
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

v2.11: in the Launcher Creator, the --mmproj and --model-draft
lines are now conditional. When vision or MTP drafter is set to "-"
(the default, including the first time you open the page after an
install), the corresponding line is absent from the editor and
from any launcher you create - so a server won't refuse to start
over an empty <MMPROJ_PATH>/<DRAFT_PATH>. Selecting an actual model
injects the line back in, right after --model, with the real path;
switching back to "-" removes it again, with no duplicates on
re-select. The persistent Base template still carries both lines as
the reference format.

v2.12: fixed the Launcher Creator model / vision / MTP drafter
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

v2.13: five additions. (1) Both the Launcher Creator editors and
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

v2.14: welcome pop-up cleaned up - removed the broken waving-hand
glyph (it rendered as "??"), dropped the "Thrilled to have you
here" opener, and corrected the description: PandorumLLM is a
control panel for the thinking proxy that powers SkyrimNet's AI
dialogue, with llama.cpp as the inference backend the proxy uses
(not a "llama.cpp fleet"). The Helper status log is taller (300px)
and can be dragged taller from its bottom-right corner. And Helper
step 2 is renamed from "both PC IPs set" to "IP addresses set".

v2.15: added (custom) providers can be removed again, while the
shipped default providers stay protected. Providers you add now
carry a "custom" flag and show a small x remove button; the
defaults have no remove button and the backend refuses to delete
them (use Disable, or Restore Default Providers to reset). Existing
configs are migrated automatically - any provider that isn't part
of the shipped default set is marked custom and becomes removable.

v2.16: Restore Default Providers now only resets the shipped
default providers to their original state (title, port, priority,
thinking, and which server they belong on) and re-adds any that
were removed - it no longer deletes the custom providers you added,
which are kept exactly as they are. The confirmation prompt and
button tooltip were updated to match.

v2.17: remote-access safety + Permissions tab. The panel now has a
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

v2.18: removed the online llama.cpp update check and the "open
releases page" web link. PandorumLLM no longer contacts GitHub or
any external site on its own - it makes no outbound internet calls
at all now. In Folder Setup, under the llama.cpp path, the two
buttons are replaced by the releases address shown as plain grey
text you can select or Copy, then paste into your own browser to
check for newer builds. (The panel still talks to your local model
servers and forwards SkyrimNet's requests to them - that is its
job - but it never phones home.)

v2.19: folder handling reworked so the app can't read or write
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

v2.20: added a second built-in launcher template, "Single GPU (no
GPU pinning)", for people with one PC and one GPU - it is identical
to the default template but omits the GPU-ID pinning line, so
llama.cpp just uses the only card. Pick it from the template
dropdown in the Launcher Creator; a hint there explains which
template suits your setup (single-GPU vs multi-GPU / separate
inference PC). The original template is now labelled to make clear
it pins the card by GPU ID. Also added a Safety & Trust section
(above) and every release now ships with a SHA-256 checksum you
can verify.

v2.21: UI + fixes. The Permissions tab now sits between
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

v2.22: UI polish + templates. The in-app folder picker now uses
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

v2.23: fixes. The "Pick a folder" window now has a Drives button in
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

v2.24: two fixes. In 2-PC mode, pressing "Set IP address" or "Set
same as PandorumLLM PC" no longer makes the Remote PC row vanish or
snap back to 1-PC - an IP action now preserves your 1-PC/2-PC choice.
And in the Launcher Creator, toggling the Wrap button no longer
halves the editor's height: the code box now keeps a stable size (and
can be resized by dragging its bottom edge) whether wrap is on or off.

v2.25: fixed the real cause of "2 PC Setup" reverting to 1-PC. The
setting was being saved as the text "False" instead of a true/false
value, which the interface then read as 1-PC on the next refresh -
so any later action (a GPU enable/disable, a theme change, or just a
background refresh) appeared to snap it back. It is now stored
correctly as a real boolean and stays put. Existing configs that
were already saved with the text value are repaired automatically on
load. Also added a lock so simultaneous actions can no longer
overwrite each other's saved settings.

v2.26: two fixes. The Live Network graph (the GPU - server -
provider link lines) is now clearly kept on the remote read-only
view. And in Folder Setup, paths you type or paste are no longer
wiped when you use the folder picker for a different field: a
re-render now preserves any unsaved edits in the other boxes, so you
can mix pasting and picking and then Save settings once, and every
path sticks.

v2.27: two fixes. On the remote read-only view, the Live Network
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

v2.28: per-provider sampler monitoring and control. The proxy already
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

v2.29: two changes. Each provider (including custom/added ones) now
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

v2.30: internal cleanup only - no change to how anything works. The
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

v2.31: UI improvements across the Servers, Proxy and Dashboard
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

v2.32: two changes. Each Statistics chart now appears only once
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

v2.33: Launcher Creator and Sampler Guide polish. In the Creator,
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

v2.34: two fixes. Changing the ps1 launcher folder in Folder Setup
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

v2.35: small UI clarity fixes. On Proxy Setup, the 1 PC / 2 PC
feedback message now shows directly under the card title instead of
on the first IP address row. On the Setup Helper, step 1 is renamed
'Set folder paths' (it now goes green once your llama.cpp, launcher
and models folders are all set, and its how-to text lists all three).
And Folder Setup now marks the llama.cpp, ps1 launcher and models
folders with a 'Mandatory' badge so it is clear which paths are
required.

v2.36: launcher/model discovery + guide polish. The app now scans
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

v2.37: fixes the Servers page not refreshing on navigation. The
Servers tab was the only tab that did not re-render when you clicked
onto it, so after changing folders the launcher dropdown kept showing
its previous contents until some other refresh happened. It now
re-renders when you open it, the same as every other tab - so a
launcher .ps1 you just made visible (including one found in your
models folder) shows up as soon as you switch to the Servers tab.

v2.38: two changes. The launcher scan now goes into subfolders. It
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

v2.39: interface polish. The Helper page highlight now rings the exact
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

v2.40: terminal scaling and Statistics charts. Auto text scaling now
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

v2.41: launcher templates now use --n-gpu-layers 99 (was 999). Both the
base and custom Launcher Creator templates, and the Sampler Guide note,
now agree on 99 - a number at or above any realistic model's layer
count, so every layer still offloads to the GPU (full offload) for the
models you would actually run. (999 also works and additionally covers
100B+ models with more than 99 layers, but 99 is the simpler, more
familiar value.)

v2.42: Folder Setup feedback + a consistent Title Case pass.
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

v2.43: SkyrimNet YAML gets its own subtab + a VS Code style editor, plus IP/Helper fixes.
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

v2.44: Remote Access IP fix + Getting Started subtab + a deeper runtime guide.
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

v2.45: YAML tab cleanup + fleet status animation + statistics polish.
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

v2.46: brand animation, launch terminal, and per-terminal text scaling.
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

v2.47: timestamps, provider colours and timings, per-terminal scaling, sampler guide ranges.
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

v2.48: bigger subtabs, per-terminal fonts, resizable panes, log categories.
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

v2.49: servers and providers reworked; launcher files retired.
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

v2.50: Live Network rebuilt to read top-down, with drag-to-allocate and click tracing.
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

v2.51: Live Network becomes the one place wiring happens.
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

v2.52: Live Network wiring fixed, Server Inspector added.
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

v2.53: Live Network dragging fixed, and the boxes tidied up.
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

v2.54: provider editing fixed, Live Network handling smoothed out.
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

v2.55: provider edits apply immediately, Live Network reports what you do.
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

v2.56: Server Editor, more runtime settings, guide cross-links.
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

v2.57: sampler values are yours to set, with a switch for which side wins.
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

v2.58: readable buttons, styled tooltips, tidier Folder Setup.
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

v2.59: working update check, softer surfaces, sentence-case buttons.
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

v2.60: launcher picker, profiles panel, tighter provider rows.
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

v2.61: switch toggles, roomier server cards, borderless popups.
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

v2.62: instant linking, conditional settings, consistent terminal controls.
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

v2.63: server cards rebuilt, header controls slimmed, new theme colour.
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

v2.64: card rows spaced and aligned, two popup bugs fixed.
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

v2.65: the reason the server card spacing never changed.
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

v2.66: buttons become glowing text.
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

v2.67: electric Launch button, glowing tabs, working slider keys.
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

v2.68: Launch button fixed, drawn symbols, fields that warm to the touch.
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

v2.69: real lightning on the Launch button.
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

v2.70: distinct symbols and even Live Network boxes.
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

v2.71: cyan arcs, working slider keys, tighter switch rows.
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

v2.72: smooth slider edits and a glow that lets go.
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

v2.73: the slider flicker traced to the background refresh.
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

v2.74: sliders that wind up, instant theme selection.
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

v2.75: fleet terminal on demand, provider colours, context-size stepping.
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

v2.76: your own colour presets, and everything back in line.
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

v2.77: page history arrows and a restore for the servers.
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

v2.78: rows line up, GPUs tuck away, models report their state.
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

v2.79: the row alignment bug found, provider names become links.
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

v2.80: one top edge, and indentation that means something.
Layout:
- The tab column and the page beside it now start on the same line. Both sit
  twelve pixels below the header, and the subtab buttons carry the same padding
  as the tab buttons, so the two rows of text line up rather than merely their
  boxes. The rule is written down beside the values so it stays that way.
- Indentation now shows depth. Subtab buttons sit at the page's left edge and
  everything belonging to them starts twenty-six pixels further in, so the
  further down the hierarchy something is, the further right it begins. It used
  to be the other way around.

v2.81: dragging holds its place, one highlight everywhere.
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

v2.82: the row alignment cause found - it was the emoji font.
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

v2.83: rows share a baseline, which is what "aligned" actually means.
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

v2.84: the guide points at the right things.
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

v2.85: highlights glow the words, arcs run both sides.
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

v2.86: frosted panels, a tidier terminal toolbar.
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

v2.87: the setup diagram is part of the page now.
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

v2.88: the guide snakes, menus behave, panels look like glass.
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

v2.89: the guide path is exact, and the side note waits for you.
User Guide > Main Guide:
- Each row of steps now starts directly beneath the step that ended the row
  above it and runs back the other way. Both the column and the row are pinned
  now; previously only the column was set and the browser chose the row, which
  could push a step onto a fresh line and leave a gap.
- The manual-providers note is joined by a single line from whichever of the two
  steps you are pointing at, rather than a line to each.
- It stays up for three seconds after you move off the step, so there is time to
  reach it and press its button, and it stays as long as you are on it.

v2.90: quitting really does leave nothing behind.
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

v2.91: the flashing symbol explained, and the glass finally looks like glass.
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

v2.92: the pop-up panels are frosted for real this time.
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

v2.93: pop-up panels you can actually see through.
- The blur had been doing its job all along. At eighteen pixels it smeared the
  text behind into a smooth haze, which is what looked like a gradient rather
  than like glass, and the pale tint of the last version made that worse.
- The tint is dark again, as originally asked, and transparent enough that what
  sits behind survives it. The blur is down to six pixels, which softens what is
  behind instead of erasing it, so you can see the interface through the panel
  rather than a wash of colour.

v2.94: one keypress, one step - and sliders on demand.
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

v2.95: panels lose their fill, and some lost styling comes back.
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

v2.96: panels get their backgrounds back, with a black glow.
Appearance:
- The see-through panels are reverted. Every panel has its background again and
  is set off by a black glow rather than an accent one.
- A panel sitting inside another has no outline of its own, and neither does the
  strip that carries Add server or Add template.
Pop-up menus:
- The tint is darker while still letting the interface show through.
- Buttons on those menus invert against whatever shows through behind them, so
  they read as dark over a bright patch and light over a dark one.

v2.97: black glow everywhere borders used to be.
Panels:
- Server cards, provider slots and log file cards carry the black glow. They had
  been flattened by the rule that strips outlines from a panel inside a panel.
- The launcher editor, the guide's status pane and the permission tree have no
  borders; the first two carry the glow instead.
Live Network:
- Box colours are back as a glow rather than an outline, and a server that is not
  allocated to a GPU falls back to the black glow like everything else.
- Provider boxes are thinner again.

v2.98: colour pickers follow the theme, fields pick readable ink.
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

v2.99: glows without the hard edge.
- What still looked like a border on the provider slots was the glow itself. It
  began with a solid one pixel ring at zero spread, which is a border by another
  name. That ring is gone from the provider slots and the permission tree; only
  the soft part remains.
- Boxes in the Permission Tree are edged by a glow in their own colour instead of
  a line - green for host, blue for remote, red for denied.
- Statistics: the heading is gone and the monitoring and reset controls sit at the
  left in its place.

v3.00: dropdowns behave, preset glow restored.
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

v3.01: notes keep out of the way, and two stubborn borders finally go.
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

v3.02: provider boxes pinned thin, slider panels fade out.
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

v3.03: the flickering symbol, properly this time.
- Highlighting a heading made its symbol shimmer while the words were fine. The
  cause was animating a filter on the element that holds them both: doing that
  forces everything inside it to be redrawn on every frame, and fine vector
  strokes land slightly differently each time, which is the flicker. Matching the
  keyframe values in v2.91 cured an abrupt jump but never this.
- Nothing animates a filter over a symbol any more. Words glow through their own
  shadow, fields and panels through an edge, and the symbol eases between two
  fixed states with a transition - drawn once rather than every frame.
- The Live Network status pane has no border, just the usual black glow.

v3.04: the white dropdown list explained, provider colours back.
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

v3.05: provider colours written onto the boxes themselves.
- The colour each provider is given has been reaching the box correctly for
  several versions, but the glow built from it kept losing somewhere among the
  rules that also style those boxes. It is now written straight onto the box, so
  nothing can outrank it. Hovering still brightens it.
- The port sits in the row rather than being placed by hand, so the name and the
  port share the middle of the box instead of drifting to the top.
- The drop area's glow while dragging was far too strong. It is a quiet edge now.

v3.06: a slight glow, text centred by construction.
- The provider colour is a faint outline and a soft halo rather than the solid
  ring and wide glow of the last version.
- Their text is centred by giving the box equal padding above and below and
  letting its height follow the text, instead of fixing a height and asking the
  browser to centre within it. Nothing is computed, so nothing can drift.
- The drop area shows no glow while dragging.

v3.07: the symbol highlight finally keeps step with the words.
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

v3.08: no more shimmer on the highlighted symbol.
- The flicker was never about where the glow was applied - it was the glow itself.
  A filter that changes over time makes the browser re-draw the artwork on every
  frame, and fine strokes land on slightly different pixels each time. Moving it
  from the heading to the symbol in v3.03, and fixing its timing in v3.07, left
  that untouched.
- Both symbols take their colour from the heading they sit in, so the highlight
  now simply changes that colour and eases it back. A colour change needs no
  redraw, so there is nothing left to shimmer, and the symbol still keeps step
  with the words.

v3.09: step 1 lights the field again, not the words in it.
- Splitting the highlight in v3.03 into one version for words and one for edges
  left the edge version matching only a field sitting inside the highlighted
  element. Step 1 points straight at the folder fields themselves, so they fell
  through to the words version and lit their own text instead of their edge.
- The edge version now matches the element itself as well as one inside it, and a
  field lit that way no longer glows its text at the same time. Panels and fields
  take an edge; the two headings still light their words and symbol.

v3.10: the field text stops glowing, the symbols glow again.
- The symbol highlight works by recolouring, and it was being applied to every
  step target - so a highlighted text field had its own text recoloured, which is
  the glowing text in the box. It now only goes to the two headings that actually
  have a symbol, and only if one is found there.
- Those symbols carry a real glow again, not just a colour. The glow is switched
  on and off rather than eased, because a filter that changes over time is what
  re-draws the artwork every frame and makes it shimmer; switched once at each
  end there is nothing to shimmer, and the colour easing either side carries the
  softness.

v3.11: the guide highlight rebuilt from scratch.
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

v3.12: the highlight is a glow, with no border in it.
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

v3.13: the symbol is part of the heading now, not a separate piece.
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

v3.14: the highlight grows out of the glow already there.
- Highlighting something that already had a glow took that glow away for the two
  seconds it ran and handed it back at the end, which is the snap out and back.
  An animation replaces a property outright rather than adding to it, so the
  amber was arriving instead of the resting glow rather than on top of it.
- Each thing that has a resting glow now names it, and the highlight lays the
  amber over that name. The resting glow stays put the whole time while the amber
  rises and falls on top, so it grows out of what was there and settles back into
  it. Anything with no resting glow contributes nothing, so it behaves as before.

v3.15: button rows line up with the page.
- A row of buttons sitting straight on a page was lining up by the edge of the
  first button rather than by its text, so it sat sixteen pixels - one button's
  padding - to the right of everything else on that page. It is pulled back by
  exactly that, on every page. Rows inside a panel are untouched, since there a
  button should line up with the panel it is in.
- The Permissions page has no heading or description above its two buttons.

v3.16: your llama.cpp build number is read correctly now.
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

v3.17: folder paths save themselves.
Folder Settings:
- There is no Save settings button. A path is saved when you leave the field or
  press enter, and only if it actually changed. The warning about an unsaved path
  and the first-run line telling you to press save are both gone with it.
Launcher:
- The base template view in the Creator can be dragged taller instead of sitting
  at a fixed height.
Permissions:
- The Permission Tree's frame carries no glow of its own.

v3.18: everything in a row sits on the middle of it.
- Rows were lining up on the baseline of their text, and a second rule then
  re-centred only the buttons and fields inside them. So a control sat centred
  while the label beside it sat on the baseline, and the two disagreed by however
  much their sizes differed - which is why some pages looked right and others did
  not.
- Every row centres now, and the rule that singled out controls is gone. The
  three places that asked for baseline of their own - the statistics header,
  server cards and provider slots - follow the same rule as everything else, so
  there is one behaviour across the whole interface.

v3.19: the Permission Tree lines up.
- Text in each box sits on the middle of that box both ways. It had been placed a
  fixed distance in from the top-left corner, so it drifted with the size of the
  box it was in.
- The joining lines meet each box on its own centre. The two outer branches were
  drawn thirty units to the side of the boxes they connect, which is why they ran
  into the corners rather than the middle.

v3.20: the models and launcher folders are checked too.
- Only the llama.cpp folder was ever checked - the folder check looked for
  llama-server.exe and nothing else, so the other two had nothing to report no
  matter what you pointed them at.
- The models folder now warns in red when it holds no .gguf files. It looks a
  couple of levels down as well, since models are usually filed in a folder of
  their own, and stops at the first one it finds rather than reading the whole
  drive.
- The launcher folder warns in yellow when it holds no .ps1 launchers yet, which
  is a normal state before you have made any rather than a mistake.

v3.21: auto refresh stays out of your way.
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

v3.22: warnings sit under the box they are about.
Folder Settings:
- A folder warning was being added to the block of extra material that follows a
  field, so the llama.cpp one appeared below the update-check panel rather than
  below its own box. Each warning is now placed directly beneath the box it
  refers to, ahead of anything else.
User Guide:
- The Setup Helper heading is a fifth larger, with the buttons set clear of it.
Customization:
- Theme Presets is a fifth larger, and the two explanatory lines are gone.

v3.23: nothing is altered under the pointer any more.
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

v3.24: generated launchers are grouped by subject.
- A generated launcher listed every flag in one long run. That run was held
  together by line continuations, and a continued line cannot carry a comment, so
  there was no way to label anything within it.
- The flags are gathered into a named list instead, which needs no continuations
  and can be commented. Each group is headed: model files, server, GPU, context
  and cache, batching and concurrency, CPU, generation, logging. The command
  itself is one line at the end that hands the list to llama-server.
- The panel reads the same flag and value pairs out of it as before, so model,
  port and thinking detection are unchanged.

v3.25: menus open again.
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

v3.26: decoration is purely visual now.
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

v3.27: the fade away waits too, and switches stop flicking back.
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

v3.28: the folder is down to what it needs.
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

v3.29: a step for setting a server up, and the panel knows what a model is.
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

v3.30: the guide knows its steps by name.
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

v3.31: a debug report you can hand over.
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

v3.32: the Debug tab watches the app run.
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

v3.33: Validate, and a launcher read properly.
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

v3.34: reading a .gguf properly, and pickers that show what fits.
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

v3.35: an even row, and a launcher you can read before choosing a model.
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

v3.36: Validate works, and the folder button is back where it was.
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

v3.37: the grey frame on open dropdowns is gone.
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

v3.38: the new dropdowns look right, and the guide arrows point properly.
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

v3.39: the grey line was mine, and the widths are measured now.
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

v3.40: no lines left, except where you asked for them.
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

v3.41: the lines you were seeing were not borders at all.
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

v3.42: the hover glow is quicker, and no longer flickers.
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

v3.43: a folder warning clears as soon as the folder is right.
- Saving a path redraws the fields, which throws away the elements the check was
  listening to, and nothing asked again afterwards - so whatever message was on
  screen stayed there until the page was reloaded, even once the folder held
  exactly what it was complaining about.
- Every folder is now re-checked the moment a path is saved, and the fields are
  listened to again after the redraw. The check also runs when a field is left or
  Enter is pressed, not only while typing.
- Checked by pointing the models folder at an empty one and then at one holding a
  model: the warning appears and then clears on its own.

v3.44: blank dropdowns, tidier IP list, and the model field says it is required.
- The Size and Font dropdowns came up empty until clicked. Those two are filled
  with their choices after they are put on the page, so the replacement control
  was drawn from a list that was still empty, and only a click made it look
  again. Every control is now brought back into step whenever the page changes -
  except one that is open, which must not be rebuilt under your hand.
- The detected addresses disappear once you take one. They are a list of choices;
  after the choice is made they are only noise.
- The Model field on a server card carries the same Mandatory marker the required
  folders do, since a server cannot run without one.

v3.45: Restore default providers repairs, rather than duplicates.
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

v3.46: fewer notes, and the yaml one says where the file goes.
- Gone from Proxy Setup: the paragraph about where GPUs, servers and providers
  live, and the line about what the addresses do to the proxy.
- Gone from Launcher Creator: the note about which template to pick for one card
  or several, and the note about clicking samplers.
- The SkyrimNet YAML note has moved off the button row to the bottom of the
  panel, where the rest of the explanation is, and now spells out the whole path
  the file belongs at, starting from the modlist folder. The password and the
  path are picked out in blue with a soft blue glow, so the two things you
  actually need to read are the two things that stand out.

v3.47: a launcher that names its model through a variable is read properly.
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

v3.48: Recommended Setup places providers by what they do.
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

v3.49: the guide agreed with itself, and the graphs answer properly.
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

v3.50: the recommendation sets priorities, and the font list is honest.
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

v3.51: the Gamemaster moves up, the button reacts, and sampler values arrive live.
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

v3.52: Launch stops asking for a step you have already covered.
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

v3.53: profiles are files, the button counts, and only drafters look right.
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

v3.54: the reasoning flags are known, and the rest of that launcher checks out.
- --reasoning-budget-message and --reasoning-format are real llama-server options
  and are now recognised, along with a few others in the same family that had not
  come up yet: --chat-template-file, --special, --poll, --slots, --no-warmup and
  --override-kv.
- Every value the panel takes off that launcher was checked against the file
  itself rather than trusted: model, vision projector, draft model, port, context,
  layers, batch and micro-batch, parallel slots, threads, generation cap, flash
  attention, auto-fit, mmap and continuous batching. All correct, thinking read as
  on, and nothing in the file is unrecognised any more.

v3.55: the launch count keeps up, and a read-only view says so.
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

v3.56: a viewer stays put, and every sampler value has somewhere to come from.
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

v3.57: a remote viewer can see the statistics that are already being kept.
- Monitoring was never off. A read-only viewer was not allowed to ask for the
  figures at all, so the page received nothing and its header fell back to saying
  monitoring was off - while the host had it on the whole time and was recording
  normally.
- Reading the figures changes nothing on the host, so a viewer may now ask for
  them. Resetting them still cannot be done remotely, and the Monitoring and
  Reset buttons are no longer shown there; a viewer sees whether monitoring is on
  instead of two buttons that would only be refused.

v3.58: statistics stay host-side, and typing no longer freezes the animations.
- Reverted: a read-only viewer cannot ask the panel for the statistics again, and
  the Provider Statistics page is not offered in that view at all. If it happened
  to be showing when the view opened, it moves to the providers list.
- The animations stopped whenever a text field had focus. That guard was added to
  stop effects disturbing an open menu, and a focused field was swept in with it -
  but the effects only ever draw inside their own button and cannot reach a field,
  and what actually protects something being typed into is the separate guard that
  holds a redraw back. The guard still stands the effects down for an open menu, a
  dropdown, a slider or a dialog, which is what it was for.

v3.59: Restore really restores, the picker keeps its choice, and the arcs behave.
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

v3.60: clearing forced sampler values, one provider or all of them.
- Each provider carries a Reset sampler parameters button at the right of its
  heading. It clears every value forced on that provider and nothing else - the
  name, port, priority, thinking and sampler source are all left as they are, and
  each parameter falls back to whatever SkyrimNet or the server sends.
- Beside Restore default providers there is now Reset all sampler parameters,
  which does the same for every provider at once. It says how many carry forced
  values and asks before clearing them, and does nothing if none do.
- Both are host-only, so a read-only viewer is not offered them.

v3.61: one button for clearing forced sampler values, not two.
- Beside Restore default providers there is now Reset all sampler parameters. It
  clears every value forced on every provider and nothing else - names, ports,
  priorities, thinking and sampler sources are all left alone, and each parameter
  falls back to whatever SkyrimNet or the server sends. It says how many providers
  carry forced values and asks before clearing, and does nothing if none do.
- The per-provider button added in the last version has been taken out again: each
  slot already carries Revert Params, which does exactly that job, and a second
  button beside it was only duplication.

v3.62: two real faults from the code sweep, and a privacy pass.
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

v3.63: the Permission Tree says what the app actually does now.
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

v3.64: sweep the launcher folder before you trust what is in it.
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

v3.65: model filenames no longer reach a remote viewer.
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

v3.66: live updates repaired - one refresh rule, a self-healing stream, SkyrimNet colors.
- Fix: the page's only live driver was the event stream, and the per-tab refresh rule
  was written twice (event handler and auto-refresh tick) with drifted copies. One
  liveRefresh() now; the build counts the copies so a second cannot reappear.
- Fix: a state event repainted only the server slots, so Provider cards never updated
  live. Every event now repaints whichever page is open; the do-not-redraw-while-typing
  guards moved inside the renderers themselves, one home each.
- Add: every event carries a sequence number and the 5-second heartbeat echoes it. A
  silently dead stream is noticed within about five seconds; the page catches up and
  rebuilds the connection, and notes the gap in Log > Observer.
- Change: the source-file line sits above each terminal instead of inside it, on all
  three terminal views.
- Change: provider colors now match the chips SkyrimNet itself shows for the same
  roles, everywhere at once - terminal lines, statistics bars, provider rows (new
  colored accent) and the Live Network glow. Titles SkyrimNet does not know get vivid
  colors from the hash palette; grey no longer appears.
- Note: the Server Inspector repaints only on your own actions, never under a live
  event, so the editor cannot be redrawn while in use.

v3.67: full-window terminals go edge to edge, controls appear only when the mouse moves.
- Change: Full Window now covers the whole page, terminal text up to the top edge.
- Add: in Full Window every button, dropdown and the source line is hidden (not
  removed) until the mouse moves or a key is pressed; 2.5 seconds of stillness hides
  them again. A control that holds focus - an open font picker, a field being used -
  keeps the row visible. One mechanism serves all three terminal views.
- Add: Escape leaves Full Window, since the exit button is hidden most of the time.

v3.67 hotfix1: the terminal's priority-wait marker now reads +8013ms instead of
held 8013ms. No other change; page reload not required.

v3.67 hotfix2: Full Window's hidden controls actually hide. Clicking the Full Window
button left it focused, and a focused button counted as "in use", so the hide never
engaged. Buttons no longer hold the controls visible (only open dropdowns and fields
do), the toggle drops its own focus, and the frame padding is gone - terminal text
reaches the true top edge. Covered by a runtime test that enters Full Window with the
button still focused.

v3.67 hotfix3: the priority-queue wait in the terminal reads +2922 ms with the number
in green, matching the other timing figures. Lines written by earlier builds (+2922ms,
one token) are recolored the same way.

v3.67 hotfix4: Full Window controls float over the terminal instead of pushing it
down. Waking the mouse now shows only two buttons - Adjust and Normal Size; Adjust
reveals the font, size and source controls, and stays as set until Full Window is
left. The priority-wait marker is recolored: + and ms in plain text, only the number
in green.

v3.67 hotfix5: the terminal chrome is the same in both views - a slim bar with the
source line, Adjust and Full window, and a settings panel that Adjust floats OVER the
terminal instead of pushing it. Terminals take the freed height in normal view too.
Fixes Full Window's unclickable, washed-out buttons: the stacked overlay strips were
painting over and swallowing clicks meant for the bar; overlays no longer catch the
pointer except on their own controls, and the grey gradient strip is gone.

v3.67 hotfix6: an open Adjust menu now stays put - the Full Window idle hide leaves it
alone until it is closed with the button or by clicking anywhere outside it, in both
views, through the same outside-click gate every other drop-out panel uses. The menu
background is translucent with a 2px blur of the terminal beneath.

v3.67 hotfix7: the Adjust menu is a compact card only as wide as its controls, hanging
directly under the Adjust button and aligned to the terminal's right edge, instead of
a strip across the whole width. In Split view each terminal has its own Adjust button
opening its own menu. Everything else about the menu (persistence, outside-click
close, translucency) is unchanged.

v3.67 hotfix8: in Split view's Full Window, the right terminal's Adjust no longer
lands on top of Normal Size. A stand-in Adjust sits beside Normal Size and opens the
right terminal's menu in its usual place at that terminal's right edge; the column's
own button steps aside in Full Window and returns in normal view.

v3.67 hotfix9: the floating page-navigation arrows (bottom-left) now follow the Full
Window idle hide - gone with the rest of the chrome after 2.5 s of stillness, back on
any mouse move or key, and always back on leaving Full Window.

v3.67 hotfix10: the panel no longer resolves its own hostname on every api call. The
origin check did a fresh name lookup per request, and on Windows machines without a
default gateway that lookup can stall for seconds - which is why panels with a busy
proxy took half a minute to first draw the server cards, and the debug report took
four. Literal localhost or LAN addresses now skip resolution entirely and the address
list is cached for a minute. Verified by a gate that counts resolutions across twenty
api calls: zero.

v3.67 hotfix11: the version everywhere - header, logs, debug report, page-cache check -
now carries the hotfix number (v3.67-hf11 Beta), so a report always says exactly which
build produced it. The Server Editor's launcher picker mirrors the launcher actually
saved on the server instead of a session variable, so it survives restarts; a saved
hand-edit outside the launcher folder shows as a "(current, hand-edited)" entry. And
the panel now times itself: an /api/state call over half a second writes a line to the
error log naming the slow phase, and the debug report ends with a timing breakdown of
its own build - so the next slow-startup report will name the culprit instead of us
guessing at it.

v3.67 hotfix12: the panel now says which file it is running. The startup banner, the
debug report and the tooltip on the version in the header all carry the full path of
fleet-panel.py, a short hash of its contents, its size and when it was last modified.
Replacing a file is not the same as running it: an older instance still holding the
port serves the old code to the browser, and there was no way to tell. If startup
displaces a running instance of a different version, it now says so.

v3.67 hotfix13: server cards are quick again. Checking whether a server is up used
socket.create_connection and urlopen, and both run the name resolver even for
127.0.0.1 - about a second each on a machine with no default gateway, so three
servers cost three seconds on every state read and the debug report took over four.
The probe now uses a plain socket and speaks /health over the same connection, with a
short cache so a burst of refreshes probes once. The same report is now built in about
a millisecond.
Also remembered across restarts: the launcher you loaded into a server (the picked
file is copied into generated-launchers, so its origin is now stored alongside and the
picker shows it), whether the Server Editor was left Locked or Open, and which profile
is loaded - its name is shown beside Profiles in the header.

v3.67 hotfix14: the whole state build is now traced, and the probes stop dominating
it. Every step that reads the disk or the network is timed - launcher folder scan,
model folder scan, template scan, launcher parsing, log parsing, config reads, address
lookups and the port probes - and whatever time is left over is reported as
everything-else, so a slow call is never unexplained. The breakdown appears in the
debug report and in the error log for any state read over half a second.
On this machine a closed server port is dropped rather than refused, so each probe sat
out its full timeout. Probes now run for all servers at once with a 0.35s loopback
limit, so three unreachable servers cost 0.35s instead of three seconds.
Also: the Observer is remembered - if it was recording when you left, it starts
recording again on the next run.

v3.67 hotfix15: the wait before servers show as ready was the model list. Identifying
a .gguf means opening it and reading its header, that was done for every model on
every scan, and the result was only held for thirty seconds - so a folder of large
models cost that read again and again, and the server cards sat on "Model could not be
loaded" until it finished. Each file's kind is now remembered in model-kinds.json,
keyed to the file's size and date so a changed or new model is still re-read, the scan
is held for five minutes, and the first scan runs in the background at startup instead
of under the first page load. A scan over a second says so in the error log.
Also: report internals now cover folder checks and model header reads, and the logs
and providers.yaml folders no longer report "nothing expected found in it" - they are
written to, not read from, so existing is all they need to be.

v3.67 hotfix16: Live Network is now the start page in fact as well as in the sidebar -
the nav item was selected at startup while the Servers page was the one on screen.
The model scan is also single-flight: the startup warm-up and the first page load used
to scan at the same moment and read every model header twice (25s and 10s in the same
second on a 68 model folder). The second caller now waits for the first and takes its
result. The listen backlog is raised from the default of five, since a browser opens
several connections at once and a second tab or a remote viewer doubles that.

v3.67 hotfix17: the debug report gains a port behaviour section. It connects to a
known-closed port, to the panel's own port and to each configured server port, and
says what each one did and how long it took. A closed port refuses at once; one that
neither answers nor refuses is being intercepted, and the report says so - worth
knowing before llama-server tries to bind the same port.
Observer: a click that closes nothing no longer writes a line (those entries were
most of a trace and pushed the useful ones out), and moving between pages is now
recorded, so a trace shows where you were.

v3.68: consolidates v3.66 and v3.67 with their seventeen hotfixes, and closes out the
slow-start work.
- Fix: checking whether a server was up used connect_ex on a socket with a timeout.
  On Windows that does not report a refusal - it waits out the whole timeout and
  answers WSAEWOULDBLOCK - so every check cost its full timeout even though nothing
  was wrong with the machine. It now uses connect, which reports a refusal at once.
  The port behaviour section of the debug report was reading the same false answer.
- Fix: Remote Access was written to the config but not among the known settings, so
  it was dropped on the next read and came back Off every start. It is remembered.
- Add: the header states Remote Access - On or Off beside Profiles, On in blue.
- Live updates: one refresh rule shared by the event stream, the auto-refresh tick
  and a heartbeat fallback that notices a dead stream within about five seconds.
  Every event repaints the page in view, so provider cards no longer need a reload.
- Start-up: model kinds are read once per file and remembered, folder scans are
  single-flight and warmed in the background, address lookups are cached, and every
  step of a state read is timed with the remainder named. A debug report that took
  four seconds now takes about five milliseconds.
- Terminals: full window covers the page, its controls hide until the mouse moves and
  float over the text instead of pushing it, each terminal has its own Adjust menu,
  and the source line sits above the text.
- Memory: the launcher loaded into a server, the Server Editor's Locked or Open
  state, the profile in use and the Observer's recording state all survive a restart.
- Colours: providers use the same colours SkyrimNet shows, everywhere at once.

v3.68 patch1: the header states more at a glance. The loaded profile's name glows
blue beside Profiles, and the auto refresh interval appears next to the clock as
- 1s, - 5s or - 10s, also in blue, with nothing shown when it is off. Remote Access,
the profile name and the refresh interval all share one glow rule.

v3.68 patch2: the three header markers read the same way - Remote Access-On,
Profiles-desk, and the refresh interval as -5s beside the clock. One separator, no
stray spaces, no dot.
Also: the auto refresh interval is remembered and starts again on the next run.

v3.68 patch3: a small space each side of the dash in the header markers - Remote
Access - On, Profiles - p1, and - 5s beside the clock, whose own padding provides the
space on its left so the gap matches the other two.

v3.68 patch4: the header is tidier and the version now tells you something.
- Change: the path and slot count have left the header. The slot count sits on the
  Servers page beside Restore default servers; the install path is at the foot of
  Folder Settings.
- Add: the version is a button. It glows a faint green when you are on the newest
  release, and pulses yellow with Update! beneath it when GitHub has a newer one.
  Clicking it asks before opening the releases page in a new tab.
- Note: this adds a second outbound request - a plain read of the public releases
  page on github.com, once per session and cached for six hours. Nothing about your
  setup is sent, it is host-only like every other command, and the panel works
  normally when it cannot be reached.
- Change: Remote Access, Profiles and the refresh interval are clickable across the
  whole marker, value included. Remote Access opens the Live Network page, where the
  setting lives - it does not toggle from the header.
- Change: a little less space between the clock and its interval.

v3.68 patch5: the update check compared release tags as text, so any tag that was not
an exact match counted as newer - it announced v3.67-beta-hotfix9 as an update to
v3.68. Tags are now read as numbers (version, then patch or hotfix number) and
compared properly; a build newer than the newest release says so rather than nagging.
The label reads Update available! and is centred under the version.
Fix: SeverActions was listed with a scroll in one emoji table and a wrench in a later
one, and the later table won. Both say scroll.
Change: the Remote Access marker opens Permissions > Remote Access, and all three
header markers glow blue on hover.

v3.68 patch6: providers can be switched off again. The flag was still honoured by the
proxy and the yaml writer, but every config read stamped it back on, so nothing could
hold it. A provider switched off keeps its port shut, which is what lets a second PC
serve that provider instead without two machines listening on the same port. The row
dims when off, the setting survives a restart and rides along in profiles, and
Restore default providers puts it back on with the rest of the shipped values.

v3.68 patch7: the provider On/Off switch is now a power symbol at the right-hand end
of the provider row, vertically centred, the same glyph as the Exit button at twice
the size. It glows green while the provider is served by this panel and red while it
is off, and says which in its tooltip.

v3.68 patch8: the provider power button sat on a line of its own. The provider row is
a wrapping flex box whose sampler chips take a full line, so no flex child could ever
sit beside both lines. The button is now pinned to the card itself - right edge, true
vertical middle - and the card reserves room for it.

v3.68 patch9: the provider power button did nothing. It was wired to the handler the
row's dropdowns and switches use, which listens for a change event and reads the
element's value - a button raises neither. It has its own click action now, and its
tooltip reads Provider state - Enabled or Provider state - Disabled.

v3.68 patch10: a disabled provider fades its whole card, not just the row of fields
inside it - the name, port and allocation line dim with the rest. The power button
stays at full strength so it can still be read and pressed.

v3.68 patch11: first step towards a second AI machine. Live Network now has Host and
Client tabs. Give the Client tab the address of another PandorumLLM panel on your LAN
and this one shows that machine's cards, servers and enabled providers as Client GPU1,
Client Server1 and so on.
Nothing is sent to the client and nothing new is exposed by it: this panel reads the
ordinary read-only remote view the client already serves, so the client simply needs
Remote Access switched on. The read happens on its own thread every five seconds with
a two second limit, so a client that is switched off cannot slow this panel down - the
Client tab just says it is not reachable. The client's address is masked for anyone
viewing this panel remotely, and a client running a different version is called out.
Launching, editing and everything else still happens on the machine that owns the
GPUs; this is a view, not a remote control.

v3.68 patch12: Live Network > Client is now the Host page itself, drawn from the
client's state - the same cards, servers, providers and lines, just the other
machine's. Only one of the two is on the page at a time, since the graph uses fixed
element ids. The client view is look-only: host controls are hidden and nothing in it
responds to clicks.
The client's address moved to Proxy > Proxy Setup, beside the other addresses.
There is no client mode to switch on. A client is simply a panel with Remote Access
on; this one reads what it already publishes to any remote viewer.

v3.68 patch13: a Full Window marker sits beside Remote Access in the header and puts
the whole panel on the screen, the same as pressing F11. It reads On in blue while
full screen and follows the browser, so leaving with Escape updates it too. This is
the browser window, not the terminal's own full window view, and it works for a
remote viewer as well since it only affects that person's screen.

v3.69: consolidates v3.68 and its thirteen patches.
- Add: a second AI machine can be watched from this one. Put its address in Proxy >
  Proxy Setup and Live Network gains Host and Client tabs, the Client tab being the
  same page drawn from that machine's data. There is no client mode to switch on: a
  client is a panel with Remote Access on, and this one reads what it already shows
  any remote viewer. Nothing is sent to it and nothing is controlled from here. The
  read runs on its own thread with a two second limit, so a client that is off cannot
  slow this panel down, and the client's address is masked for remote viewers.
- Add: providers can be switched off again, with a power button at the right of each
  provider card - green for on, red for off, and the card fades when off. A provider
  switched off keeps its port shut, which is what lets a second PC serve it instead.
- Add: the version in the header is a button. It glows green on the newest release,
  pulses yellow with Update available! when GitHub has a newer one, and asks before
  opening the releases page in a new tab. Release tags are compared as numbers.
- Add: Fullscreen, Remote Access, Profiles and the refresh interval all state
  themselves in the header and are clickable across the whole marker.
- Change: the install path and slot count left the header - the count sits on the
  Servers page, the path at the foot of Folder Settings.
- Fix: SeverActions had a scroll in one emoji table and a wrench in a later one.
- Remembered across restarts: Remote Access, the auto refresh interval, the launcher
  loaded into a server, the Server Editor's Locked or Open state, the profile in use
  and the Observer's recording state.

v3.69 patch1: the header markers are spaced evenly. The gap was set on the header row,
but Remote Access, Fullscreen and Profiles sit inside one span of their own, so it
only ever applied between that span and the clock. The group now carries the same gap.
Fix: the whole marker group was marked host-only, so a remote viewer lost Fullscreen
as well - and that one only affects the screen of whoever presses it. Host-only now
sits on Remote Access and Profiles, the two that change something shared.

v3.69 patch2: addresses are blurred until you ask for them. On Proxy > Proxy Setup
that covers the panel and remote IP fields, the green line that repeats what was set,
the detected addresses offered as chips and the client panel address; on Permissions >
Remote Access it covers the URL for opening the panel from another PC. Click any of
them to reveal, and a field clears its own blur while you type in it. This uses the
same click-to-reveal blur already used for GPU serial numbers, so there is one rule
for it rather than two.

v3.69 patch3: a revealed address covers itself again as soon as you click elsewhere,
and revealing one hides any other that was open, so at most one is ever readable. A
field you are typing in keeps its reveal until it loses focus. This applies to every
blurred value, GPU serial numbers included.

v3.69 patch4: the provider switch labelled Detect SN sampler parameters now reads
Show SkyrimNet sampler values, which is what it does. Nothing else changed - the
setting itself and its saved name are the same.

v3.69 patch5: groundwork for the TTS work. A remote reader of a log feed no longer
receives file paths - they are stripped on the host before the text is sent, not
hidden in the page, so the rule holds however the feed is read. Drive-letter and UNC
paths both go; dialogue lines and timing figures are untouched, and if the masker ever
fails it hides the line rather than handing it over. Settings for a TTS server and
wrapper pair are seeded but not yet used by any page.
v3.70: text-to-speech gets its own page. Proxy > TTS [Alpha] holds the settings for a
TTS server and its wrapper - the server binary, the model, the ports, the python and
the wrapper script - and pins the card by UUID so a reboot or a reseated card cannot
move it. Press Write start-tts.bat and the panel builds the launcher for you, in the
launcher folder alongside the others. The launcher starts the server, waits until it
answers, then starts the wrapper with its output mirrored into logs\tts.log, and it
carries the handful of details that are easy to get wrong: the card re-indexes to 0
once it has been isolated, python needs -X utf8 and -u or the log arrives empty and
then in lumps, and the colour codes are stripped from the copy the panel reads. It
also points the wrapper at whichever server port you set, so changing that port moves
both halves rather than only one. A fourth terminal sits beside Proxy, Thinking and
Split and shows that log live; a remote viewer can read it too, with any file paths
stripped out on the host before it is sent. The wrapper itself stays yours - the panel
writes launchers, not wrappers - and no voice traffic passes through the panel, so
speech keeps working whether or not the panel is running.

You should not have to hunt for any of those paths. Each one has a Choose file button
that opens the same picker used elsewhere, showing only the right type of file, and if
you already have a working TTS launcher there is an Import from a launcher button that
reads all six settings out of it in one go - it only takes the paths and ports, nothing
else is read from the file.

Also fixed: the TTS terminal did not update on its own - you had to leave the page and
come back. The panel writes its own proxy and thinking logs, so it always knew when those
changed, but the TTS log is written by a separate program and nothing announced it. The
panel now checks that file once a second while you are watching, and lines appear as they
are written, like the other three.

Also fixed: Write start-tts.bat could write into a different folder from the one shown
as your PS1 Launcher Folder. It now always writes where Folder Settings says.

Also fixed: the launcher folder viewer showed only .ps1 files, so the start-tts.bat the
panel had just written could not be seen from inside the panel. There is now an Open
launcher folder button on the TTS page as well.

Also fixed: a GPU serial written into a server's card could still be read by someone
viewing the panel from another PC. It is now hidden like the other serials, while the
Live Network graph keeps drawing exactly as before.

v3.70 patch1: builds can now be told apart. The version in the header, the line printed
at startup and the comment at the top of a generated launcher all carry the patch number
and a short build hash, so you can always check which build is actually running rather
than guessing from the release name. The terminal also shows the time of its last refresh
beside the source name, so a feed that has stopped updating is visible straight away
instead of looking like a quiet log.

v3.70 patch2: the panel can now do the translating itself. Under Proxy then TTS [Alpha]
there is a choice of who answers SkyrimNet - your own wrapper, as before, or the panel.
Choosing the panel means there is no second program to install, no python environment and
no launcher to run by hand; point SkyrimNet's TTS endpoint at the panel and that is all.
The trade is that voices then depend on the panel running, so it is off unless you pick it,
and your existing setup is untouched either way. The startup ping SkyrimNet sends is
answered locally by default, returning a moment of silence rather than spending a second of
graphics card time generating the word "ping".

v3.70 patch3: when the panel is doing the translating, the launcher it writes now starts
only the TTS server. Before it also tried to start a wrapper, which could not work because
the panel was already answering on that port. The model still needs hosting, so the server
half remains and the launcher says plainly that the panel is handling the rest.

v3.70 patch4: the panel as wrapper now sends the reference voice in the same form the
standalone wrapper always did. It was passing the uploaded file straight through, and the
TTS server rejected it; the file is now rewritten cleanly first. When the server does refuse
something, its own explanation is written to the log instead of a bare "Bad Request", and a
line that finds no reference voice at all says so rather than reporting that it computed one.

v3.70 patch5: one button. With the panel doing the translating, the only thing still
started by hand was the TTS server itself, so there is now a Start button on the TTS page
that runs it with the right card, the right flags and its output kept in a log. A line
beside it says whether both halves are up, and the state only reads ready when the server
is answering and the panel is listening. Pressing Start when something is already serving
does nothing rather than starting a second one, so it is safe next to a launcher you may
still be running yourself.

v3.70 patch6: the Start button now says what it is doing. The TTS server does not open its
port until the model has finished loading, so for the first several seconds nothing looked
different and the button appeared to have done nothing at all. It now reads Launching while
that happens, cannot be pressed again, and the line beside it explains that it is waiting
for the server to answer. If three minutes pass without one, it says so and points at the
server log rather than waiting forever.

v3.70 patch7: there is now a TTS Guide under User Guide. It walks through setting the whole
thing up from nothing in eight steps, explains the difference between letting the panel do
the translating and keeping your own wrapper, and lists what to check when it does not work.
It also says plainly what the TTS support is: experimental, and written against one specific
build of MOSS-TTS rather than TTS servers in general, so a different one will not work here
even if it looks similar. The voices SkyrimNet already supports by itself need none of it.

v3.71: a review pass over the new text-to-speech code, and four fixes from it. The panel's
TTS listener accepts connections from the network so a second PC can reach it, but it was
not checking who was calling - it now applies the same address filter the proxy has always
used, so a machine the proxy would turn away is turned away here too. It also no longer
trusts a caller's claim about how large a request is, refusing anything oversized instead
of setting aside room for it. Generated speech files were piling up in a temporary folder
for as long as the game ran and are now kept to the most recent two dozen, and starting the
TTS server no longer leaves a file handle behind each time. Everything from v3.70 and its
patches is included.

v3.71 patch1: closing the browser now shuts the TTS server down as well. The panel already
stopped the language model servers when the last tab closed, but a TTS server it had started
was left running and kept the voice model sitting in graphics memory even though nothing
could reach it any more. It is now stopped along with everything else, and the Terminate
button does the same. A TTS server you started yourself from a launcher is deliberately left
alone, since in that arrangement it is meant to keep working without the panel.

v3.71 patch2: the Permissions page was out of date. It still described three terminals when
there are four, and made no mention of the TTS page at all - so it understated what someone
viewing from another PC can see and left out which TTS controls are yours alone. It now
matches what the app actually does, and the release checks compare its claims against the
code that enforces them, so it cannot quietly fall behind again. Opening Proxy Setup from a
remote view is also refused immediately now rather than a moment later.

v3.71 patch3: the TTS page now keeps up with the server. Pressing Terminate did stop it, but
the page carried on showing it as ready with the Start button greyed out until you reloaded.
The page refreshes itself along with everything else now, the panel watches the TTS server
the same way it watches the language model servers, and starting or stopping announces the
change straight away instead of leaving the page to notice. As on the other pages, it holds
still while you are typing in a field so nothing is lost mid-edit.

v3.71 patch4: the previous attempt at keeping the TTS page in step with the server did not
work. The page was being redrawn, but a moment too early - before the new information had
arrived - so it redrew itself exactly as it already was. It now redraws at the point the
fresh status comes in, which is where the rest of the app does it, and the release checks
drive the page through a real change rather than merely confirming the code contains an
instruction to redraw.

v3.71 patch5: the TTS terminal now has the same Adjust menu as the others, so its text
size and font can be set independently and the setting is remembered - previously it
borrowed the dashboard terminal's and had no controls of its own. Stopping the TTS server
also shows a shutting down state while the server is closing, instead of appearing to be
already stopped a moment before it is.

v3.71 patch6: stopping the TTS server now shows what it is doing. The previous attempt
could not work: the panel waited for the server to close before answering the page at all,
so by the time anything could be displayed it was already finished. Stopping now happens in
the background and the page is told immediately, so it reads shutting down for as long as
the model takes to unload and only then stopped. Neither button can be pressed during that
gap, so a restart cannot collide with a shutdown still in progress.

v3.71 patch7: pressing Terminate now shows the TTS server shutting down as it happens. The
panel deliberately holds off refreshing a page while a change is still being saved, and
Terminate counts as one for as long as it runs, so the page waited and only found out once
everything had already stopped. The TTS page is now told directly by the button that pressed
it. The wording is also consistent - it says shutting down whether you stopped the server
from its own button or from Terminate.

v3.72: a sweep over the whole project, and two things from it. The proxy accepted a claim
about how large an incoming request was and set aside room for it; like the TTS side it now
refuses anything absurd instead. Reference voice samples were also being kept indefinitely
in a temporary folder and are now trimmed to the most recent few dozen, which costs nothing
since they are sent again if they are needed. Everything from v3.71 and its patches is
included.

v3.72 patch1: the lightning that plays across the Launch button can now be switched off,
under Customization in a new Effects section. It stays on unless you turn it off. The button
itself is unchanged either way - it still changes colour as servers come up and still shows
how many are running; only the animation stops.

With the lightning switched off, the Main Guide's launch step now lights the button up so
you can still see where to look - it relied on the lightning to do that before. This also
fixes the guide highlight on buttons generally: it was drawn as a glow around a box, and
buttons here are glowing text with no box at all, so it never showed on any of them.

v3.72 patch2: there is now a choice of TTS engine. Alongside the existing MOSS setup you
can pick audio.cpp, which needs only a server program and a model folder - no python
installation, no separate wrapper script, and nothing to start by hand. The panel writes
the server's configuration itself, starts it on whichever card you pinned, and hands it the
reference voice as a file on disk rather than re-sending the audio with every line. Which
engine you use changes nothing about how SkyrimNet talks to the panel.

v3.72 patch3: choosing a TTS model now works the same way as choosing a language model.
Point the panel at a folder of TTS models and pick one from a list, rather than typing a
path. Both kinds are found - single model files and the folders that hold a model split
across several files. If a folder contains both, the panel says so and will not let you
pick the one that would be quietly ignored, which is what happens otherwise.

v3.72 patch4: fixes text-to-speech failing on every line when using the audio.cpp engine.
The voice sample SkyrimNet sends carries some extra information inside the audio file that
not every program will read past, so it is now tidied as soon as it arrives rather than
only for one of the engines. Nothing needs reconfiguring.

v3.72 patch5: the previous fix only applied to voice samples sent after updating. SkyrimNet
checks whether it has already sent a sample and skips it if so, which meant anyone who had
used the panel before kept hitting the same error. Existing samples are now repaired the
first time they are used, so nothing has to be cleared out by hand.

v3.72 patch6: the Chatterbox voice option now works through the panel. It uses the same
connection style as Zonos but arranges its request differently, and the panel was reading
the wrong parts of it, so the voice sample never arrived. Separately, when the speech
server stops unexpectedly the panel now reads that server's own log and tells you what went
wrong, instead of only reporting that the connection closed.

v3.72 patch7: when the panel briefly could not be reached, the message shown was about the
wrong thing entirely - the code that displays the warning could itself fail and hide what
had actually gone wrong. Fixed, and the real reason is now recorded.

v3.72 patch8: you can now choose where spoken lines are saved, and they are named after the
speaker and the time rather than a long string of random characters. Leave the setting blank
and nothing changes. The panel never deletes anything from a folder you choose. The terminal
also shows the fuller timing breakdown again - how long generation took, how long the audio
encoding took, and what was left over.

v3.72 patch9: the TTS terminal now shows how long the speech server took and how much time
was spent around it, together with the speed figures, rather than a single total. Where a
server reports its own internal timings those are used instead.

v3.72 patch10: setting up audio.cpp is simpler. You point the panel at the folder you
unzipped it into and it finds the program itself, the same way it already handles llama.cpp.
There is a button to check whether a newer audio.cpp has been released. The TTS section of
the User Guide now has a page for Higgs, with the download links and commands, and the port
setting is called Proxy TTS Port since a wrapper is no longer always involved.

v3.72 patch11: the TTS part of the User Guide now has a page for each engine inside it,
rather than spreading across the top of the screen. Anything you can copy shows a small copy
symbol and flashes when you click it, so it is clear the text went to the clipboard.

v3.72 patch12: the TTS terminal now tells you what is happening - which engine and model are
loading, which graphics card they are on, when they are ready, where to point SkyrimNet, and
when the server stops. The audio.cpp folder setting also warns if the program is not in it,
shows the download address for newer versions, and can check for one. Copying from a guide
now shows a single glow rather than a glow and an outline together.

v3.72 patch13: the terminal now shows just the file name when a line is saved, since you
chose the folder yourself. There is also a new setting for the Higgs engine: it can act on
emotion, style, pause and sound-effect markers written into a line of dialogue, if your
language model is set up to write them. It is off by default and the panel never adds any
of its own.

v3.72 patch14: the tag setting is now called Audio Tags and works for both engines - MOSS
understands a pause marker of its own, so each engine is given only the markers it knows.
The audio.cpp version check is colour coded like the llama.cpp one, and the TTS settings are
spaced out so the different groups are easier to tell apart at a glance.

v3.72 patch15: some people saw Windows Defender report a threat in the launcher. It was a
false alarm, but an understandable one: the program used to restart itself with
administrator rights and no window, which is a pattern unwanted software uses. It never
needed those rights, so it no longer asks for them - which also means one less permission
prompt each time you start it. StartPandorumLLM.bat is also back in the folder. It starts
the panel exactly as the program does, is plain text you can read, and gives you a way in
if security software ever blocks the program itself.

If your antivirus still objects, please report it to Microsoft as a false positive at
microsoft.com/en-us/wdsi/filesubmission - it is checked by a person and usually corrected
within a few days, for everyone rather than just you.

v3.72 patch16: more work on the false alarm some antivirus software reported. The launcher
no longer opens any network connections - it used to check several ports to find the panel,
and now simply reads the small file the panel writes with the port it chose. It also starts
Python in a way that needs no hidden window, and carries fuller version details. All told
the program now uses exactly two notable Windows functions: one to start the panel and one
to open your browser.

v3.72 patch17: the audio tag feature now works. It was looking for markers in a form
SkyrimNet removes from every line before sending it, so nothing would ever have come
through. The dialogue model writes them in a form that survives, and the panel converts.
The guide explains the three things SkyrimNet needs set up for tags to arrive, and is
honest that the backend which supports them clones voices slightly less well than the one
that does not.

v3.72 patch18: audio tags now follow the rules the model actually needs. Sound effects only
work when a written-out sound follows them immediately, so that is added. Emotion and style
colour a whole sentence and have to sit at its start, so they are moved there. And a pause
written at the very beginning or end of a line is removed - left in, it can make the speech
engine run on until it gives up, returning nothing and sometimes stopping altogether. The
list of available sound effects was also wrong and has been corrected.

v3.72 patch19: a line that ended with a sound effect could be sent to the speech engine
without a full stop, which can make it run on past the end of the line. Fixed.

v3.72 patch20: there is now a one-click install for the Higgs speech engine. It asks first,
telling you exactly what it will download, from where, how large it is and what your
graphics card needs to be, and it only proceeds if you say yes. Everything lands inside the
PandorumLLM folder and the settings are filled in for you. You can stop it part way and
start again later without losing what was already downloaded. Installing by hand still
works exactly as before and the guide still describes it.

v3.72 patch21: the speech engine keeps recently used voices prepared so it does not have to
work them out again. It only kept one, which meant nearly every line of a conversation
redid that work. It now keeps 64, and you can change the number on the TTS page if you use
a lot of custom voices.

v3.72 patch22: SkyrimNet's own performance markers now work with Higgs as well. Its normal
setup writes things like [angry] or [sigh] into a line, and those are converted to what
Higgs understands - so you can use SkyrimNet exactly as it comes, with no prompt to edit.
Markers Higgs has no equivalent for are removed rather than spoken. Ordinary square
brackets in dialogue are left untouched.

v3.72 patch23: the TTS terminal now highlights performance tags in cyan, written the way
your dialogue model wrote them. If you see them there, they made it through; if the line is
plain, they were never written or were removed before reaching the panel.

v3.72 patch24: spoken lines in the TTS terminal now read like a script - the speaker in
magenta, the line itself picked out, and performance directions shown as *sighs* or
*whispering* rather than as codes.

v3.72 patch25: you can now give the panel a folder of voice clips of your own. Name a .wav
after the voice type - femalenord.wav, or a character name - and it is used in place of the
one SkyrimNet sends. This matters because SkyrimNet reduces the quality of every voice
sample before sending it, and the Higgs engine can make use of far more detail than
survives that. The terminal says when a line used one of your clips.

v3.72 patch26: removes the orange warning saying the panel is not running as administrator.
It no longer needs to be - that changed when the launcher stopped asking for administrator
rights - so the warning was telling everybody about a problem that no longer exists.

v3.72 patch27: fixes the one-click Higgs install failing to find the speech engine. The
files it downloads have a code in their names that changes with each build, and the
installer was looking for fixed names. It now recognises them whatever the code is.

v3.72 patch28: the one-click Higgs install is more tolerant of how the speech engine names
its downloads. It always takes the newest release, and now recognises the right file by the
words in its name rather than an exact match, so a change of naming will not stop it
working. If it ever cannot find one, it lists what the release does contain.

v3.72 patch29: fixes an "Access is denied" error when saving settings. Windows briefly locks
files while antivirus or search indexing looks at them, which is most likely just after a
large download, and the panel gave up at the first refusal. It now waits and tries again.
If it still cannot save after the Higgs install, it tells you what was installed and which
four settings to fill in - the download itself is finished and nothing is lost.

v3.72 patch30: installing Higgs now tells you when it has finished, naming what was
installed and where, instead of quietly returning the page to how it looked before.
Pressing Install again after a problem no longer re-downloads anything already in place.

v3.72 patch31: fixes black console windows appearing when servers start and when you quit.
The dialogue in the TTS terminal is now gold. Every terminal has a Timestamps button to
hide the time at the start of each line, and the Proxy and Split View terminals have an
Insert TTS button that shows the spoken line, and how fast it was produced, directly under
the reply that produced it.

v3.72 patch32: the lightning on the Launch button is now off unless you turn it on. In the
terminals, performance directions like *laughs* no longer run into the next word, spoken
lines inserted into the Proxy terminal are coloured the same as in the TTS terminal, and
each one now sits directly beneath the reply that produced it rather than at the bottom of
the list.

v3.72 patch33: spoken lines shown in the Proxy terminal now sit in the right place. They
were being grouped under one old reply and listed backwards. The speaker name is coloured
correctly, and the note about a local voice clip has moved to the line that reports the
saved file. The speech log also starts fresh each time you start the panel.

v3.72 patch34: when a reply is spoken in several pieces, they now appear together beneath
the reply that produced them rather than scattered between the other work the panel was
doing. The terminals also no longer show the previous session's log while waiting for a new
one to start.

v3.72 patch35: hiding timestamps no longer hides the spoken lines along with them, and each
spoken line now starts with a purple arrow so it stands out from the rest of the log. In
Split View each half can be set to show the Proxy, the Thinking Content or the TTS log,
and the Insert TTS button only appears on a half that is showing the Proxy.

v3.72 patch36: spoken lines in the Proxy terminal now hang off the reply that produced them
as a small branching tree, in the accent colour, with the last piece closing the branch. The
panel also remembers which version of the speech engine it installed, so it can tell you
when a newer one is out, and it notices an installation that is already present on disk -
offering to use it rather than asking you to fill in the paths.

v3.72 patch37: your own spoken lines now show a glowing arrow rather than a branch, since
they are not produced by a reply. Each speaker gets its own branch, and the branch lines
join up without gaps.

v3.72 patch38: spoken lines now show who is actually speaking - Serana rather than
Femaleyoungeager - and saved audio files are named after the character too. The panel works
this out from the request it is already passing to your language model, which states who the
character is; it keeps only the name, never the conversation, and nothing is sent anywhere.
Where it has not learned a name yet it shows the voice type as before.

v3.72 patch39: your own spoken lines were being labelled with a companion's name, and
companions were being marked as yours. Both are fixed - your name is read from the same
place, so your lines now show it. The branch lines in the terminal no longer overlap where
they meet. The speech engine version is also found for installations the panel did not
perform itself.

v3.72 patch40: your own spoken lines now line up with the others, and the branch lines glow
a little more. The speech engine version is looked for in more places, including asking the
running server directly - though if it genuinely does not report one, the panel says so
rather than making a number up.

v3.72 patch41: your own spoken lines were sometimes labelled with a companion's name. The
panel was reading the name of whoever was being spoken TO, which is not always you. It now
reads it from the party, which is always yours. Spoken lines also show a small face or
symbol for how they are meant to sound rather than the same mask every time.

v3.72 patch42: the Launch button is now Launch LLM, and a Launch TTS button sits next to it
which starts the speech server in the same way. The setting for choosing speech now names
the voice rather than the software behind it. Faces in the terminal line up properly, the
branch lines glow a little more, and the version check no longer points out when it cannot
tell which version you have.

v3.72 patch43: the TTS section is no longer marked Alpha. The Launch TTS button now lights
up and glows like the Launch LLM one, both keep their glow when you hover over them even
while busy, and you can start one while the other is still starting. The TTS page has been
tidied of explanatory text.

v3.72 patch44: a long spoken line now continues underneath itself rather than wrapping back
across the branch beside it. In Split View the buttons no longer overlap in a narrow pane,
and the Timestamps button affects only the terminal it sits in.

v3.72 patch45: both launch buttons brighten when you point at them again. Terminate now
visibly shows the speech server stopping rather than appearing to ignore it. And in Split
View the Timestamps button really does affect only its own half.

v3.72 patch46: in Split View at full window, the buttons on the right no longer sit on top
of each other.

v3.72 patch47: stopping the speech server while it was still starting no longer leaves the
button stuck. In Split View at full window the right terminal's buttons now sit together in
the top bar rather than on a row of their own.

v3.73: everything from the v3.72 patches, gathered up. The headline is Higgs Audio v3
speech: a one-click install, voices named after the characters speaking them, performance
tags the dialogue model can write, and spoken lines shown in the terminal beside the reply
that produced them. There are separate Launch LLM and Launch TTS buttons, and the panel no
longer loads anything from the internet just to draw its own interface.

v3.73 patch1: TTS now has its own entry in the menu on the left, under Server, instead of
being tucked inside Proxy. Spoken lines appear in the Proxy terminal without having to turn
them on first.

v3.73 patch2: text in the Permissions diagram no longer runs across into the next column.
The TTS page is split into labelled sections so it is easier to find your way around, and
the install button is larger.

v3.73 patch3: the panel was spending about three quarters of a second checking whether
servers were running, most of it waiting on ports it had already meant to check in the
background. It now checks them all at once, as intended.

v3.73 patch4: notes about something being slow no longer appear in the error log or raise a
problem in the panel. Nothing had failed - they are observations, and they now go in the
ordinary log marked as warnings.

v3.73 patch5: a session with no problems no longer leaves an error log behind - it was
writing one every time just to record that the panel had started. Log > Errors now has a
Clear All button.

v3.73 patch6: if the speech server stops while loading a model, the panel now says so and
explains what went wrong instead of waiting indefinitely. Downloading a log no longer asks
whether you want to leave the page.

v3.73 patch7: the explanation shown when the speech server fails to start now describes the
attempt you just made rather than an earlier one. Stop works while it is starting, and the
TTS page shows an Installed badge once Higgs is set up.

v3.73 patch8: you can now point the TTS page at the original model files instead of a
prepared one, and choose the precision to load them at - full, half, or a smaller Q8. That
means trying a lighter setup without downloading or converting anything.

v3.73 patch9: removes the model source choice added in the last patch. It could not offer
anything smaller than the Q8 you already have, so it was complication without benefit.

v3.73 patch10: the Timestamps and Insert TTS buttons now say whether they are on or off,
the same way the Remote Access and Fullscreen indicators do.

v3.73 patch11: fixes the Higgs installer skipping the download when another copy of
audio.cpp was already in its folder - it now replaces anything that is not the version it
means to install. Finishing an install also sets the SkyrimNet translation option, and a
problem part-way through is shown on the page rather than only in the log. Step 7 of the
guide now says that it is a manual step.

v3.74: the one-click Higgs install now replaces the speech engine every time rather than
keeping whatever it finds, so a copy downloaded by hand - or one damaged by antivirus -
cannot be picked up by mistake. Finishing an install also sets the SkyrimNet translation
option for you. Step 7 of the guide now says that it needs a manual tick, which several
people had reasonably taken for a fault.

Also in v3.74: the GPU setting on the TTS page now tells you which card will be used when
you have not chosen one, rather than implying that all of them are available.

v3.74 patch1: the Start and Stop buttons on the TTS page and the Launch TTS button at the
top now always agree, and neither gets stuck. The GPU list on the TTS page shows the same
detail as Live Network, and audio.cpp's own output can be watched in Split View.

v3.74 patch2: the Higgs install now brings down two versions of the speech engine, and you
can switch between them on the TTS page. They differ in the processor instructions they
were built for, not the graphics card, so expect little difference - the balanced one is
the default and works everywhere.

v3.74 patch4: spoken lines in the Proxy terminal no longer leave a blank row that pushed
everything out of line. Terminate now lights up for a running speech server too. The speech
engine keeps a separate log per session, and if a line takes far longer to speak than its
length suggests, the terminal explains why.

v3.74 patch6: when a reply is long enough to be spoken in several pieces, the later pieces
now say they are waiting their turn. The speech engine handles one at a time, so they
queue - the text appeared straight away while the sound came later, which looked like a
fault rather than a queue.

v3.74 patch7: spoken lines in the Proxy terminal now line up exactly, and the speech server
reports starting and stopping there alongside the language servers.

v3.74 patch8: long lines in the terminals now continue on the next row instead of running
off the right-hand side, and spoken lines line up properly under the speaker.

v3.74 patch9: hover the little face beside a spoken line and the panel tells you which
emotion it represents.

v3.74 patch10: the first-run welcome now offers to take you straight to speech setup if
that is all you want - the panel can give SkyrimNet voices whether or not its language
models come from here.

v3.74 patch12: your own spoken lines can now be given a feeling. NPC lines arrive with
performance tags because the model that wrote them added those; a line you typed has none,
so it is read flat. Turn on Inject Player Tags and one of your running models will suggest
a single tag before the line is spoken. You can also just write one yourself.

v3.74 patch13: adds Player Mood Evaluation. After a character speaks to you, a model reads
how the conversation is going and notes what your reply might carry. That reading is passed
to the tagging step as background - it is never treated as what you actually said. It runs
while you are still reading, so it does not delay anything.

v3.74 patch14: fixes player tags being discarded before they reached the speech engine on
a default install. A tagged player line can now carry both a feeling and a sound, and the
mood reading suggests feelings only.

v3.74 patch15: the mood reading now follows the conversation as it is spoken rather than
reading it out of a prompt. That is quicker, it is not limited by SkyrimNet's own history
setting, and it works even if you use the panel only for speech.

v3.74 patch16: the two tagging features are greyed out until you have a server running
with a language model, and hovering over them explains why. A vision or draft model does
not count - neither can answer the kind of question these ask.

v3.74 patch17: you can now set up the tagging features before launching the fleet - a
server counts as soon as it has a language model assigned, and the list tells you which
are not running yet. The TTS page is also a little more spaced out.

v3.74 patch18: the TTS page is tidier. Settings are grouped under coloured headings, the
explanations appear when you hover over a setting's name instead of filling the page, and
both tagging features now have their own Thinking switch beside them.

v3.74 patch19: the tagging features now report in the Proxy terminal alongside the servers,
so you can see them working and how fast they are. The speech server's own starting and
stopping messages have moved to the fleet terminal, where the other servers report.

v3.74 patch20: a spoken line that wraps onto two rows no longer breaks the little tree
beside it. The speech server now reports in the fleet terminal as intended. You can edit
the instructions sent to the tagging models, see what they answered, and a line the speech
model fails to finish is tried once more instead of being lost.

v3.74 patch21: the TTS log now names the voice clip used for each line, so if a character
comes out sounding wrong you can see which sample was actually sent.

v3.74 patch22: the "elated" emotion is no longer sent to the speech engine. Testing showed
it reliably produced the wrong voice - a different speaker entirely, not just a brighter
delivery - and often failed outright. A new PTI / PME terminal shows exactly what the
tagging models were asked and what they replied.

v3.74 patch23: when the speech engine produces a line in the wrong voice, the panel now
notices and asks for it again rather than passing it on. The two tagging features have a
thinking budget you can set - previously they were cut off part way through reasoning.

v3.74 patch24: the full set of Higgs voice tags is available again, including the elated
one - the pitch check added last patch catches a wrong voice regardless of which tag caused
it. Tags can now also be written by their proper names, which previously ended up spoken
aloud.

v3.74 patch25: the tagging model now gets worked examples rather than just a word list, so
your lines can pick up a laugh, a whisper or a sigh alongside the feeling instead of
stopping at one tag.

v3.74 patch26: the tagging model is now told about two kinds of tag - one for the feeling
and one for what you would actually hear - rather than four overlapping groups, with an
explanation and examples of each.

v3.74 patch27: a sound tag is now placed where it belongs in your line rather than at the
front - a cough falls at the pause, not before the first word. If the model changes your
wording in any way, the whole reply is discarded and the line is spoken exactly as you
typed it.

v3.74 patch28: adds an audio.cpp report button that gathers everything an upstream
maintainer would need about a speech failure. The pitch check is off by default - testing
showed it rejects about one good take in six.

v3.74 patch29: fixes the Thinking switch being ignored for the two tagging features, which
made them far slower than intended and made the tag appear after the line was spoken rather
than before.

v3.74 patch30: fixes the mood reading never reaching the tagging step. It was being
discarded whenever the model wrote its answer without square brackets, which was most of
the time.

v3.74 patch31: the PTI / PME terminal now shows just the prompt that was sent and the
answer that came back, without the model's reasoning mixed in.

v3.74 patch32: fixes a stray mark beside dialogue lines that wrap onto two rows, and gives
the PTI / PME terminal the same colours as the thinking terminal.

v3.74 patch33: a laugh at the start of a line no longer makes the whole line sound like a
laugh - the tagging model now places each tag where its feeling begins. The pitch check has
been removed; testing showed the speech engine was never losing your voice sample.

v3.74 patch34: fixes voice clips that the speech engine refused to read. Some WAV files
- including a great many of Skyrim's own voicetype samples - record the wrong length
inside themselves, which most players never notice because ordinary media players read
past it. The panel already knew how to repair that, but its check for whether a file
needed repairing looked in the wrong place and passed those files straight through.
Any such clip is now mended the first time it is used, in place, once.

v3.74 patch35: the mood reader can now run less often. A new PME Frequency setting
beside Activation says how many NPC lines go by between readings, from every one up to
every twentieth. The single Player Tag Output button is now two - one for the tagger
and one for the mood reader - so you can hide the tagger's echo of your own line while
keeping the reading. Both answers now hang off the line that produced them on a proper
branch, the way spoken lines already do. The prompt speed column, which read "?" for
every one of these calls, now shows the real figure the server reports, along with
exact token counts rather than an estimate.

v3.74 patch36: tidies the TTS page. Sections are named for what they hold - Folder
Paths, Audio Files, Installation, and a new TTS Server heading over the model and build
choices, which previously sat under nothing. The build choice is now called Audio.cpp
Build, its two options are simply Fast and Balanced, and the paragraph explaining the
difference has moved into the hover mark beside the title like every other setting on
the page. The dividing rule in the Player Tag System now sits below the tagger's server
picker, where it separates the tagger from the mood reader instead of splitting the
tagger in half. PME Frequency now starts at 3 rather than 1.

v3.74 patch37: fixes the mood reader losing half its answer. It could name several
feelings but only those spelled exactly the way the panel lists them survived, so a
reading of two feelings often reached the tagger as one - and when a feeling was
dropped, nothing said so. Every spelling the panel understands is now kept, and
anything refused is named in the terminal. SkyrimNet's startup ping is no longer
handed to the tagger as though you had said it; it is recognised before anything else
looks at the line, and the setting is now called SkyrimNet Ping with a third option,
Banned, that deals with it in complete silence. Both tagging features gained a
Priority Over Providers switch, which makes requests to other models on the same card
wait while the tagger runs. Chat History now starts at 25, and the setting titles on
the TTS page are white and a size larger.

v3.74 patch38: the tagger and the mood reader are now providers. They appear in Live
Network like any other, and you choose which server answers them by dragging their box
onto it - the server pickers on the TTS page are gone, along with their Thinking and
priority switches, because those live on the provider card now with everyone else's.
This also means the sampler values you set on a provider finally reach them; they never
did before, and the panel was quietly forcing one of its own. The TTS page keeps the
on/off switch, and it is the same switch as the power button on the card.

v3.74 patch39: tidies how the tagger and the mood reader are drawn. Their boxes showed
a bare colon where other providers show a port; they now read Proxy. The PandorumLLM
icon appears in place of the plain shape that was showing in their titles, and it is
larger on the provider page. They sit at the end of the provider list rather than in
the middle of it.

v3.74 patch40: server cards gain two reasoning settings - a Reasoning budget with a
slider and a Reasoning format dropdown - which are written into the launcher the panel
generates, with the usual cross-reference to the Sampler Guide beside each. Whether a
particular provider actually reasons is still its own Thinking switch. Also restores
the accent glow on the tagger and mood reader boxes in Live Network, and puts the gap
back between their icon and their name.

v3.74 patch41: any provider with Thinking on is now told what to do when its reasoning
budget runs out - it is asked to answer now - rather than only the two the panel calls
itself. A provider with Thinking off never carries that message, since its budget is
zero and it would be spoken straight away. The reasoning format is left to the server
card instead of being forced on every panel request.

v3.74 patch42: fixes speech taking half a minute or more to start, or timing out. The
startup ping SkyrimNet sends was answered correctly but the reply was never handed back
to the waiting request, so SkyrimNet sat on its own probe for two minutes and every
line behind it queued. Anything that failed while preparing a line did the same. Server
cards also gain a Reasoning dial - on, auto or off - which was previously written into
every launcher as on with no way to change it.

v3.74 patch43: fixes your own spoken lines failing while everyone else's worked, and the
empty PTI / PME terminal. Both were one mistake: the tagger still named a variable that
had been replaced, so it crashed after the model had already answered - the answer never
reached the terminal and your line was never spoken. The panel now refuses to build if
any function reads a name nothing defines.

v3.74 patch44: fixes the Action Eval and Diary providers failing with server errors.
Those two are the ones whose replies follow a fixed shape, and the panel had begun
sending them an instruction that cut a reply short before that shape was complete. Also:
a shared voicetype no longer wears the name of the first character who used it, so
commoners and guards are named correctly, and switching the tagger or the mood reader
off now hides their lines from the Proxy terminal instead of only stopping new ones.

v3.74 patch45: the tagger's instructions are less than half as long. Every rule it used
to spell out is still made, but by the shortest wording or by a worked example instead
of a paragraph. Nothing was dropped from the list of tags it may use.

v3.74 patch46: provider cards gain a Cache switch. A provider with it on gets a slice of
the server's video memory reserved for its own prompt, so the part that never changes is
worked out once and reused instead of being recalculated every time. How many slices a
server has is still yours to set - Parallel slots on the server card - and one is always
kept for everything that is not cached, so two slots cache one provider and three cache
two. A provider that asks when none is free says so on its card and tells you what to
raise. Context size is shared out between the slices, so the card shows what each is
left with.

v3.74 patch47: every line in the Proxy terminal now ends with how much of that prompt
the server did not have to work out again - `cache 258/270 96%` when it reused almost
all of it, `cache 0/270 0%` when it reused none, and `cache ?` when the server does not
report the figure at all. Those are three different situations and only two of them are
worth chasing. Also: a character's name can no longer be borrowed by a second voice, so
one NPC's name stops appearing on another's lines.

v3.74 patch48: if a server runs a launcher you wrote yourself, the panel now edits that
file in place instead of quietly replacing it with one of its own. Only the argument
list is touched, and only the settings you changed or that were already there - the
rest of your script is left exactly as it was, and a copy of the version before the
panel first touched it is kept in ps1-launchers.

v3.74 patch49: an edit to your own launcher was being made and then not remembered when
the server was launched from the panel - fixed. Server cards gain a Context checkpoints
slider. And when a spoken line ends up labelled with its voice file rather than the
character's name, the log now says which of the two reasons it was.

v3.74 patch50: the server cards and the launcher in the Server Editor are one thing at
last. A launcher pasted or loaded into the editor was written back exactly as it came,
so anything changed on a card was recorded and then overwritten by the original. The
cards now edit the flags inside that text, leaving the rest of it alone, and the file
that launches is the text you can see.

v3.74 patch51: characters whose name is written with a role after it - Azeeda [hunter] -
were never recognised, so every one of them spoke under the name of its voice file.
Fixed. The Cache switches also stop adding a flag that was doing more harm than good.

v3.74 patch52: providers with Thinking switched off were answering with a single full
stop. Turning thinking off was being done by telling the model to stop thinking
immediately rather than not to start, so it was cut off on its first word and had
nothing left to say. Reverted to the method used before patch38.

v3.74 patch53: two characters speaking one after the other could end up wearing each
other's names - the panel was matching the newest pending name rather than the oldest,
while lines are spoken in the order they were written. The cache figure in the Proxy
terminal now appears only for providers that have caching switched on.

v3.74 patch54: server cards lay their settings out in labelled groups with a rule
between them - GPU, context, batching, CPU, generation - in the same order the launcher
writes them, so a heading on the card names a block you can find in the .ps1. The
Proxy terminal's switches move behind a single Options button.

v3.74 patch55: the tagger and the mood reader are now offered the fourteen emotions
SkyrimNet's own voice prompt teaches its characters to use, rather than every one the
speech engine will accept. Tags written by SkyrimNet itself are unaffected - an NPC
line still speaks with whatever it was given.

v3.74 patch56: the tagger and the mood reader now write tags the same way SkyrimNet
does - [EMOTION-SURPRISE], [SFX-LAUGHTER], [STYLE-WHISPERING] - instead of the panel's
own shorthand. A marked-up player line is now indistinguishable from a marked-up NPC
line, and every tag says which kind it is.

v3.74 patch57: a new Thoughts switch, in the Proxy terminal's Options. SkyrimNet asks
its characters to end a reply with their private reasoning, which is never spoken - it
now appears on its own line above what they said, under a thought bubble.

v3.74 patch58: the thought now sits above the spoken lines rather than below them, in
grape with a faint glow so it reads as interior rather than said aloud, and its branch
carries down through a thought long enough to wrap. Server card group headings are
white, with the same rule the TTS page draws between its blocks.

v3.74 patch59: the tagger was putting every tag at the end of the line; it is now told
plainly that a felt tag goes at the start of its sentence and a heard one goes where it
happens. Pause tags are offered as well. A thought carries the name of the character
whose reply it came from. The split view terminal gains the same Options button, and
sits last in the row. The mood reader counts NPC lines globally again.

v3.74 patch60: when the speech model fails to stop at the end of a line it no longer
costs twenty seconds. Each line is now sent with a length limit of about twice what it
needs, so a runaway is cut off in a second or two and the retry happens almost at once.
The model still occasionally overruns - that is the speech engine, not the panel - but
it is no longer something you wait through.

v3.74 patch61: in split view, each pane now has its own Options button in its top right
corner, with Timestamps and Insert TTS inside it. It appears only while that pane is
showing the Proxy feed, and goes when the pane is switched to something else.

v3.74 patch62: the Options menu is now slightly see-through with a soft blur behind it,
so the log underneath reads as depth rather than as a hole in the terminal.

v3.74 patch63: when a line arrives carrying performance tags and Audio Tags is set to
strip them, the TTS terminal now says so and names the setting. Your own lines were
always spoken with feeling because the tagger overrides that setting for the line it
marked up, so NPC lines arriving flat looked like a fault rather than a switch.

v3.74 patch64: the panel now records each spoken line exactly as SkyrimNet sent it,
before anything here touches it. Whether a performance tag was removed by the panel or
never arrived was not answerable before - the terminal only ever showed the line after
processing, so the two looked the same.

v3.74 patch65: some of the tags SkyrimNet can ask a character for have no equivalent in
this speech engine and are removed so they are not read out. The TTS terminal now names
them, so a tag the model spent words on but that never arrives is visible.

v3.74 patch66: the tagger and the mood reader are offered every emotion the speech
engine has again - anger, fear and disgust among them - and pace and pitch are now
written the same way SkyrimNet writes them, so a marked-up player line and a marked-up
NPC line are indistinguishable.

v3.74 patch67: a line that runs away now costs about nine seconds instead of eighteen.
The speech server ignores the length limit sent with each request, so the limit that
actually stops it is the server's own - which was fixed at twenty seconds inside the
panel and is now a setting on the TTS page, defaulting to nine.

v3.74 patch68: a TTS Backend Settings block on the TTS page - temperature, top-k,
top-p, repetition penalty and the audio token ceiling. Temperature is the one that
decides how OFTEN a line runs away; everything before this only decided what it cost.
Every overrun is now also written to eoc-events.json with the settings in force at the
time, and that file survives restarts - it is what a calibration will be measured
against.

v3.74 patch69: fixes the TTS server refusing to start on patch68. The speech engine
checks the options it is given and stops if it does not recognise one, so the panel now
sends none of them unless you hand it the backend - a new Settings Owner choice, SN Side
or Proxy Side. If the server ever does refuse a name, the panel reads that name out of
the refusal and starts again without it. Sampling Rate joins the backend settings.

v3.74 patch70: changing the model on a server card now reaches a launcher you wrote
yourself, including one that names the file through a variable. And a new Actions switch
shows what the action evaluator picked for a character - Serana > bathe - in the Proxy
terminal.

v3.74 patch71: the speech engine will not accept sampling settings from the panel, so
those controls are removed rather than left there looking useful. What remains is the
one thing the panel can change - how much text it hands over at once - and the record
of overruns now measures against that.

v3.74 patch72: SkyrimNet sends more with each spoken line than the panel reads - a list
of arguments of which two are used and the rest were discarded unseen. Any speech
setting SkyrimNet has of its own is in that list, so the panel now writes the whole of
it down once per line. Values are never printed for the voice reference.

v3.74 patch73: the Proxy terminal gains a Providers button - each provider shown by its
own mark, lit when its lines are being shown and dark when they are not - and a Row
spacing choice in Adjust for blank rows between one record and the next. An action line
now reads with the character in magenta and the action in cyan.

v3.74 patch74: the sliders on SkyrimNet's own TTS page were doing nothing. It sends them
with every line and the panel was throwing them away before calling the speech engine.
Temperature, Top P, Min P and Repetition Penalty are now passed on. A new TTS
Diagnostics section shows what SkyrimNet is asking for beside what has actually gone
wrong.

v3.74 patch75: the choice of whether SkyrimNet's speech settings are passed to the
engine now has a control, in the TTS Diagnostics section beside the explanation of what
it does. It was a setting with no way to change it.

v3.74 patch76: EOC Calibration. Give it a line and a few chunk sizes and it speaks the
line at each of them, counts how often generation runs past its own end, and names the
size that held up best. It speaks through the same path a game line takes, so the
numbers mean the same thing. Also fixes the seed being shown wrong - it is larger than
a browser can hold as a number.

v3.74 patch77: a Diagnosis section under the calibration. Pick one of your own servers -
only those actually up with a model are offered - and it is handed the observed
settings, the overrun record and the last sweep, and asked what it makes of them.

v3.74 patch78: TTS Diagnostics, EOC Calibration and Diagnosis become one section, TTS
Calibration, with one terminal shared between them that can be dragged larger from its
bottom left corner. Diagnose asks one of your servers what the collected data shows;
Calibrate then asks the same server what to change and applies whatever comes back
within its bounds. Diagnose has to run first.

v3.74 patch79: fixes the Proxy and Split View terminals falling behind or going blank,
the calibration terminal clearing itself when Diagnose was pressed, and moves its resize
handle to the bottom right. Diagnose and Calibrate now show that they are working.

v3.74 patch80: the Proxy terminal working for a few minutes and then stopping, and Split
View never working at all, were the same fault as patch79 fixed - in a second place
that runs for everybody by default rather than only when a setting is changed.

v3.74 patch81: the terminal was not stopping - everything after the first spoken line
was being joined onto the same row, which then ran off to the right where nobody could
see it. Every row is now its own block and there is no case left where one can be
joined to the next.

v3.74 patch82: the Proxy and Split View terminals work again. The filter that decides
which lines to show was built from a text pattern that arrived damaged, so painting the
terminal failed every time and it simply never updated. It matches by hand now, with no
pattern to be damaged.

v3.74 patch83: the terminal that patch82 brought back froze again the moment an action
row appeared - the lines that show which action a character chose. Colouring those rows
asked for colour names that live inside a different painter, and the browser stops a
paint at the first name it cannot find, so from that line on nothing updated. The names
live in one shared place now that every painter can see. Three colour rules that had
never worked a day also start working: port numbers in the terminals, the [hh:mm:ss]
stamps in the thinking view, and [type] names in the launcher editor - all three were
written with a bracket form that JavaScript quietly reads as a class that matches
nothing.

v3.74 patch84: choosing what a character does is really two questions - first a broad
category, then the exact action inside it - and the terminal used to show them as two
unrelated rows, with the second one blamed on 'someone'. They read as one branch now:
the category row stays open, the follow-up closes it with the chosen action and its
details, both under the character's real name, and the follow-up's record wears the
provider's name with a small drill arrow, so hiding a provider in the filter hides
its drilldowns with it.

v3.74 patch85: every spoken line is now measured - characters in, seconds out - and
an automatic calibration can turn that into a per-line token allowance, chosen on the
TTS page: a plain algorithm using the measured speech rate, a model asked before each
line (the algorithm stands in whenever it cannot answer within three seconds), or a
model-fitted median the panel then applies by arithmetic alone. Every mode stays
inside the runaway guard and the lead-in floor, and Off leaves everything exactly as
it was. The manual Diagnose and Calibrate remain and now see the measured lines too -
the record used to hold only the failures, which is why a diagnosis kept answering
that there was not enough data.

v3.74 patch86: the realtime figure had been swallowing the panel's own preparation -
above all the player line tagger's model call, a quarter to half a second - and
billing it as 'overhead (http + wav)', which read as the transport slowing down by a
quarter. Realtime now measures synthesis alone, exactly what it measured before the
tagger existed, and the preparation is shown on its own line with the tagger named.
The tagger also remembers its last 32 answers, so a repeated line - the TTS test
repeats one a dozen times, and play repeats short barks - is tagged for free. The
config file is parsed once per change instead of several times per spoken line, and
the measurement record appends one line instead of rewriting itself each time.

v3.74 patch87: the automatic calibration now shows its work. Every calculation is
written to its own terminal on the TTS page, coloured like the Proxy terminal, with
the estimate, the headroom and the bound that decided the final number. Two buttons
beside it show the exact arithmetic and the exact prompts, read-only, with a copy
button. The spoken-line report also itemises everything the panel spent before the
engine was asked - player tags, mood, the token estimate, and the rest.

Also in patch87: the 'margin' setting is now called headroom and defaults to auto.
A token cap is a stop-loss, not a target - the engine stops when it decides the line
is finished, so a smaller cap does not make speech shorter or faster; it only decides
what a runaway costs, and set below what a line really needed it turns a good line
into a failed one that has to be generated again. On auto, the headroom is worked out
from how wrong the estimate has actually been on this machine rather than from a
number typed in, and every spoken line now reports how close the estimate was.

v3.74 patch88: the TTS page had two terminals and the page was rebuilt every few
seconds, which wiped what they were showing and put them back to their default size -
the flickering. There is one terminal now, carrying the calculations, the data, the
diagnosis and every change a calibration made, in the order they happened; the page
is only redrawn when something it shows has actually changed, so the terminal keeps
its text, its scroll and the size you dragged it to. It starts hidden behind a Show
the record button, and that choice is remembered.

Also in patch88: Algorithm and Prompts now open over the page rather than filling a
terminal, each with a copy button. And the automatic calibration has a live bar
showing where the last spoken line actually went - the tag injector, the mood note,
the token estimate, the panel, then the engine's own generate, codec and transport -
colour-coded, with each band named and valued above it. A Tokens view shows the same
line as tokens used, headroom left unused, and the distance to the runaway guard.
Click a band and it explains what it is. It fills in as lines are spoken.

v3.74 patch89: both bars are shown at once now, time above and tokens below with a
line between them, so the two questions can be read together.

Also in patch89: the automatic calibration has three settings instead of four - Off,
Proxy and LLM. Proxy does the arithmetic here and asks no model at all; LLM asks one
for each line and refits itself as it goes, on a slider you set between every 5 and
every 250 lines. The old 'LLM-derived median' is not gone, it has become a choice
inside Proxy: run LLM for a while (or press Derive now), then switch to Proxy and
tell it to use the values the model fitted - calibrated by a model once, running
without one afterwards. Settings saved by earlier patches keep doing exactly what
they did.

v3.74 patch90: the bars are back. patch89 split the one bar into two and renamed its
pieces, but the check at the top of the code that fills them still asked for the old
name - so it gave up before drawing anything, and both bars stayed empty with nothing
reported anywhere. The panel now refuses to build if any part of the page looks for
something by a name nothing creates.

Also in patch90: the Derive now button is gone. Fitting is automatic in LLM mode on
the slider you set, so a button doing the same thing by hand was a second way to do
one thing. Proxy mode no longer offers a server to pick either - it asks nothing of a
model by definition, and the values it can read are made by LLM mode.

v3.74 patch91: a new Speech sampling section on the TTS page, with the same chips the
provider cards use - temperature, top_p, min_p and repetition penalty. Set one and it
is sent with every line, over whatever SkyrimNet sends; leave it empty and SkyrimNet's
own value passes through. This matters because the token cap only decides what a
failure costs, while the sampler decides how often there is one.

Every line spoken now records the sampler it was spoken under, whether it finished or
ran past the end, so the record can tell you the failure rate for each setting - shown
in the data block, worst first. That is the first time this question could be answered
at all: the sampler was never written down before.

Also in patch91: a retry no longer repeats the settings that just failed. It drops to
a steadier profile - cooler, no repetition penalty, nucleus truncated - because a
retry only has to finish, and the retry is the take you actually hear. There is a
switch for it. And a fault worth naming: when a runaway was recorded, the panel wrote
down the old fixed limit instead of the limit actually in force, so the record a
calibration reads held a number no request had ever used.

v3.74 patch92: nothing asks a model about a line any more. LLM mode now differs from
Proxy in one thing only - where the speech rate comes from - and the model is asked
for that rate periodically rather than for every line. Measured on the same sentence
spoken over and over, the per-line answer wandered by 14% with no new information in
it, cost about a third of a second each time, and agreed with the fitted rate anyway.

That fit now waits for a quiet server. It will not start while the chosen server has
anything open, or while a line is being spoken; if the server stays busy it gives up
and tries again after the next batch of lines. Once a fit is away it runs to the end -
which is why the waiting happens before it rather than around it.

And a new Auto Calibration button beside the sampler chips. It reads the failures on
the record, says what they show, and then changes the sampler settings they point at,
keeping only values inside their allowed range. It refuses to run when nothing has
failed yet, because there would be nothing to read and changing settings would be
guessing. The three server pickers on this page are now one.

v3.74 patch93: the safety margin is no longer something to type in. There is no box
for it and no setting behind it - the panel works it out, and three things it was
getting wrong are fixed.

It now only judges itself on lines where its estimate actually decided the limit. A
short line is covered by the minimum whatever the estimate said - one of yours was
estimated at 14 tokens and used 34 - and counting those was pushing the margin up on
the strength of lines where the estimate was never in charge.

A line that ran past its limit now counts too, as 'needed at least this much'. Before,
only lines that finished were counted, so the record was made of survivors and read
lower than the truth exactly where it mattered. Losing a line now widens the margin,
which is the direction that stops lines being lost.

And the panel now fits the measured lines itself, by least squares. That fit is given
to the model as a starting point and used to judge what comes back: an answer that
predicts your machine worse than plain arithmetic does is not kept. Ten fits in a row
had come back claiming there is no breath before the first word, when there plainly
is one.

v3.74 patch94: the panel gives a model two different TTS jobs - fitting the speech
rate, and reading the failures to choose sampler settings - and each now has its own
server and its own thinking switch. A small quick model can do the first while
something that reasons does the second. Thinking starts off for both: these are short
questions with a strict answer shape, and a reasoning block in front of the answer is
the commonest way one comes back unusable. Setting one and leaving the other empty
still works - the empty one borrows the server you picked.

Also in patch94: when thinking is off, the request now carries every form of saying
so - the chat template setting, the plain one some builds read instead, and the one
SkyrimNet itself sends. Builds disagree about which they honour and none of them mind
an extra. And a server card set to Reasoning off now silences the request as well as
the server: some models ignore the launcher flag and only honour the per-request
setting, so a provider asking to think on such a server no longer gets to.

v3.74 patch95: a note on where to look for the above. Turning Reasoning off on a
server card writes --reasoning off into the launcher, and that is the only part of it
a .ps1 can carry - the rest travels with each request, not with the command line, so
there is nothing further to see in the launcher no matter what is set. The Proxy
terminal now says so when it announces a provider on such a server, and the warning
triangle on the provider card explains what the panel is actually sending.

v3.74 patch96: and the launcher does carry it after all. llama.cpp has a server flag
for this - --chat-template-kwargs - so turning Reasoning off on a server card now
writes a second line into the reasoning paragraph beside --reasoning off:

v3.74 patch97: fixed dialogue lines that began with spoken "channel thought
channel" on Gemma 4 models such as Prosopon. When a server's launcher already
says --reasoning off, the panel no longer restates it inside every request:
Gemma 4's own chat template handles the no-think turn, and the restatement
made the model write its thinking markers into the answer, which TTS then
read aloud. Requests to such a server now pass through exactly as SkyrimNet
sent them - the same thing calling the server directly does. Servers whose
launcher leaves reasoning on or auto are unchanged: the per-provider Thinking
switch still turns it off per request there.

v3.74 patch98: the automatic refit runs again, and the panel's own model calls
are visible. The refit reads the server picked under Automatic calibration, and
that picker used to draw a server whether or not one had ever been saved - so
after a fresh config it showed a choice the panel did not have, and every refit
was skipped without a word. The picker now says "- pick a server -" until one is
chosen, the page warns beside the refit interval when there is none, and a refit
that is due but cannot run writes the reason into the calibration feed instead of
returning in silence. If your refits stopped, open Automatic calibration and
check that row. Separately, the fit, Diagnose and Calibrate now appear in the
Proxy terminal as ordinary generations - marked Speech Fit, Diagnose and
Calibrate, with their tokens, speed and time - and count in the server
statistics, because the server did the work.

v3.74 patch99: patch97 is reverted, and Thinking ON now actually says so.
Patch97 stopped the panel repeating "do not think" to a server whose launcher
already said --reasoning off. It did not fix what it was written for, so it is
gone and requests carry that instruction every way again, as they did up to
patch96. The real fault was on the other side: turning Thinking ON only REMOVED
the off instruction and left the rest to the server, and a server defaults to
not thinking if it was started with --reasoning off or if the Reasoning dial
ever wrote its --chat-template-kwargs line into that launcher. That line is only
removed by setting the dial back to on, so a card whose setting was lost - a
fresh config, an imported launcher - left it behind with nothing reading it,
no warning shown, and the Thinking switch doing nothing at all. Thinking ON now
sends enable_thinking=true, which overrides both the launcher flag and that
line. If your servers stopped thinking, this is the patch. Worth checking your
launcher for a stray --chat-template-kwargs line as well.

v3.74 patch100: the cause of the spoken "channel thought" is found, and the
automatic refit keeps its place across restarts. The server card dial Reasoning
format was on "none" for that server: llama.cpp leaves the model's thinking in
the visible answer at that setting instead of splitting it off, so a model that
writes thought markers hands them over as text and TTS reads them aloud. The
dial now carries a warning beside it whenever it stands on that value. Use auto
or deepseek unless you want the raw stream. Separately: the refit counted lines
from zero every time the panel started, so a long interval and a panel restarted
often could leave a fit due forever - lines measured before a restart now still
count. And the page shows what the LAST ATTEMPT came to, not only the last fit
that was kept: never tried, no server picked, the server stayed busy, or offered
and refused for predicting worse than the panel's own arithmetic all read the
same before, and read differently now.

v3.74 patch101: the Higgs install bar moves while it installs. The progress bar
and the step line above the TTS terminal were only redrawn when the whole page
state reloaded, which is why switching tabs or refreshing appeared to fix them -
the install was announcing itself to the terminal alone. Also: the unlabelled
switch under Speech sampling is now named Steady retry. It decides whether a
retried line drops to a calmer sampler - temperature down a fifth, repetition
penalty off, top_p capped at 0.9 - so a second attempt aims to finish rather
than to perform.

v3.74 patch102: the Higgs install bar really moves now. Patch101 made the panel
announce each step, which was necessary and not sufficient: the page turns an
announcement into a QUEUED reload, and a queued reload waits until nothing is
busy - during an install something always is, so it never landed. Switching tabs
appeared to fix it because a tab change reloads immediately, past that gate. The
bar and the step line now read a small endpoint of their own every 0.7s and write
themselves in place, with no page redraw and nothing to wait for. When the
install stops, the page reloads once to show what it came to.

v3.74 patch103: the install bar kept its own progress loop but threw it away the
first time it could not find the bar on screen - which happens a few seconds
after every page load, when the model list finishes scanning and redraws the
page from a state older than the install. That is why it ran for several seconds
after a refresh and then stopped for good. The loop now stops for one reason
only - the install stopping - draws the row again if it has gone missing, and is
restarted by every state load, so it cannot be lost.

v3.74 patch104: the install display is redrawn whole every couple of seconds, by
the same call a tab change makes - the one path that was always seen to work.
Writing the two nodes directly is kept as the quick path, but it is no longer
relied on: a node addressed by name can be the wrong one or missing, and every
such failure looks the same from the outside - the numbers stop. The step line
also reports how long the install has been silent, so a display that has stopped
asking can be told apart from an install that is simply between steps: if the
seconds are counting up, the page is alive and the installer is quiet.

v3.74 patch105: two ways the install display could stop and never start again,
both removed. A tick that failed - and a tick may redraw the page, which can fail
- skipped the line at the bottom that schedules the next one, so one bad tick was
the last. That line now runs whatever happens. And the flag that stops a second
loop starting was left set by the dead one, so every attempt to restart was
refused until the page was reloaded by hand; it carries a timestamp now, and a
loop that has not ticked for three seconds is replaced. The step and bar are also
written by attribute to every copy of the row that exists rather than to the one
a lookup by name happens to return, which can be a leftover off-screen copy -
indistinguishable, from the outside, from not writing at all.

v3.74 patch106: the install display was right and the installer was quiet. The two
places it appeared to hang are the two places nothing was being reported: from
pressing the button until the first download can quote a percentage, and the
whole unpacking step, which ran in complete silence and takes a while on a
Windows disk with a scanner in the way. Unpacking now reports itself once a
second with a percentage of its own, pressing Install draws the running row
immediately instead of after a round trip, and a phase with nothing to count -
asking github, clearing a folder - shows a moving striped bar rather than one
frozen at zero, which looked exactly like a bar that had stopped.

v3.74 patch107: the install display is fixed at the actual cause. The TTS page
skips redrawing when a signature of its contents has not changed, and that
signature did not include the installer at all - so pressing Install changed
nothing the page compared, the redraw was declined, and every later attempt to
show the row was declined the same way. A refresh drew it because an empty page
always draws. The signature now covers the install and the found-install rows;
the percentage and step line stay live through the direct writes, which have
worked all along once the row existed. The five earlier patches remain: each
fixed a real defect that this one was hiding behind.

v3.74 patch108: the calibration corner of the TTS page is one section. Automatic
calibration leads it; the model that reads the failures sits directly below the
fit model, each with its thinking switch beside the dropdown. The Speech sampling
block lives inside it behind one switch, Automatic sampler calibration: on shows
the sampler settings AND lets the every-N automatic run read the failure record
and change them; off hides the settings and stops the automation. Values already
set keep applying to every line either way - the switch governs the panel and
the automation, never your settings. The Auto Calibration and Calibrate buttons
are gone; their work is the second half of the automatic run. Diagnose remains,
placed directly above the record it reads from and writes to.

v3.74 patch109: the Automatic Calibration area is laid out like the Player Tag
System one. Each setting is a white title with a "?" that explains it on hover -
including what each choice in the menu does - followed by its menu, the model
that carries it out with its thinking switch, and the button that shows what
will be sent. Automatic Calibration reads Fixed, Proxy Algorithm or LLM
Controlled: LLM Controlled shows the model and a Prompt button, Proxy Algorithm
shows the Algorithm button, Fixed shows neither. Sampler Calibration below it
reads Manual or LLM Controlled, with the samplers under it either way - Manual
means you move them, not that they stop being sent. The headroom reading now
sits directly above the bars it explains, under a rule of its own, in lit white
rather than grey. The grey explanation paragraphs are gone; everything they said
is in the tooltips.

v3.74 patch110: each calibration setting keeps everything its choice brings with
it on one line. The middle cell had a fixed width, so the server picker could not
fit and dropped onto a row of its own, away from the setting it belongs to. The
row no longer wraps and every cell in it may shrink instead, the picker included.
LLM Controlled now reads across as: the choice, the server with its thinking
switch, the refit interval, then Prompt. Proxy Algorithm: the choice, the speech
rate menu, then Algorithm. Sampler Calibration is the same shape. The readings -
the fit that was kept, the attempt that was made - sit under the row rather than
in it, because they report rather than set. The picker is titled Server, not
Model, matching the wired-server box on the same page.

v3.74 patch111: the calibration rows line up. The server menu was drawn with a
trimmed padding that the setting menu beside it does not use, so it stood shorter
and a little higher than the control it is meant to match - it is the same
control now, and Automatic Calibration and Sampler Calibration are the same three
cells in the same sizes. The Refit Interval went back under its own menu. The
thinking switch is labelled and spaced like the one on a provider slot, and its
word can no longer break onto a line of its own. The two grey fit lines are gone:
what they said now joins the headroom reading above the bars, which is where the
numbers they describe end up. Titles are bold.

v3.74 patch112: the calibration rows hold their line. The server menu no longer
grows into whatever space the card has spare - it is capped, with the full name
in the opened list and dots when the closed box runs short - and a spring between
the settings and the Prompt button soaks up the surplus instead, so nothing rides
the card's edge any more. Every control in the row is the same height, the
thinking switch sits centred on that line with its word held clear of it, and the
setting menus fit their cells exactly instead of being pushed wide by the
page-wide select minimum. The Refit Interval slider moved under its title.

v3.74 patch113: the calibration rows, actually. Every dropdown on the page is
drawn by a stand-in element that copies the menu's classes and nothing else, so
patch112's widths were being set on something invisible while the stand-in sized
itself to the longest model name it held - which is what pushed the Thinking
switch and the Prompt button out past the card. The server menu is a fixed 300px
now, with the full name in the opened list and dots when the closed box runs
short, and the switch sits beside it inside the card, on the same line and at the
same height as the setting menu. The Prompt buttons are gone from both rows, and
with them the prompt-text view they opened; the Algorithm button under Proxy
Algorithm stays.

v3.74 patch114: the two menus in each calibration row now start on the same line
as each other, and the word Thinking stands clear of its switch. Both had been
asked for twice and arrived wrong twice: the row was finding its own height, so
the switch label - a little taller than the menu beside it - pushed that menu
down inside its own cell while the title above stayed where it was; and the space
before the word was written as a flex gap, which does nothing unless the box it
is on is a flex box. The row is a fixed 32px in every cell now, and the space is
a margin on the switch, which applies either way.

v3.74 patch115: the TTS Calibration page, renamed and rearranged. The section is
TTS Calibration, the menu picks the Calibration Method, the bars sit under
Monitoring with the headroom reading under the title at twice the size, and the
record is the TTS Calibration Terminal with Diagnose on its own button row. Fixed
mode is now a slider: how many tokens one character may cost, 1 to 25, with a
Reset to Higgs Default button that puts back 3.5. SkyrimNet's Own Settings is
gone - whatever arrives with a line is always passed on and then overwritten by
what you set, or by what the model sets. And all four sampler chips show a value
now: they were being handed the settings under their engine names while asking
for them under their short ones, so two of the four could never match.

v3.74 patch116: the headroom line is back to a caption size, one step up from
where it was; Steady Retry moved next to the sampler chips; and the player is
called by name in the Proxy Terminal. That last one: the name is read out of a
"## <name>'s Party" heading in a dialogue request, and the panel was only looking
at the first 256 KB of it. On the stock prompt the heading is well inside that; a
long memory block pushes it past, and then the name is never learned and every
spoken line says "Player" - while the thought under a reply, which takes its name
from a different line of the same request, reads correctly. The whole request is
searched now, and if the heading still is not there, the panel log says so once
and prints the headings the prompt did use.

v3.74 patch117: the headroom reading is now a row of small lit boxes instead of
one long sentence - headroom, worst line, pad, scored lines, runaways, the LLM
fit, and the last attempt with the time it was made. They sit centred under the
Monitoring title and wrap to a second row on a narrow window. Each box explains
itself on hover. Under eight scored lines it says seed, and how many of the eight
it has. The numbers are sent to the page as numbers now; the sentence the
terminal prints is built from those same numbers, so the two cannot disagree.

v3.74 patch118: the calibration actually calibrates again. Measured over a day's
logs, the fixed 128-token floor and the guard were deciding three caps out of
four, so the fitted speech rate barely mattered - and one runaway on a short,
floor-decided line was mis-scored as a 7.4x estimator miss, which pinned the
headroom at maximum and inflated every cap after it. The floor now scales with
the line (half the guard, never above the old 128, never below a 48-token
warm-up), failures are scored by the same rule as successes and record which
bound decided them, and the fit model is shown the same lines it is judged on.
In practice: short lines get caps near their real need, the fit decides mid-size
lines instead of the floor, runaways cost less, and the headroom settles around
1.3 instead of pinning at 2.5.

v3.74 patch119: every generation line in the Proxy terminal can be opened - click
the emoji and provider name and the request that was sent and the reply that came
back appear side by side over the page, with the reasoning under the reply when
there was any. The last 80 pairs are kept, in memory only; nothing is written to
disk. And the LLM fit works on a thinking card now: the fit call was giving the
model 60 tokens in total, which a thinking model spends entirely inside its
reasoning block, so the visible answer was always empty - the panel's own calls
now budget the thinking and keep room for the answer after it, and when a fit is
still refused, the calibration terminal prints what actually came back.

v3.74 patch120: what a model fits from your measured lines is called the TTS
Calibration now, everywhere - the box under Monitoring, the speech-rate menu, the
per-line working, the terminal record. Each calibration row also gained a slider
next to its Thinking switch: how many tokens that model may spend thinking, 500
to 10000, before it is told to answer. And every box under Monitoring explains
itself on hover - what the figure means, where it comes from, and what the panel
does with it.

v3.74 patch121: the clickable terminal records look like the terminal again - no
underline, no restyled text; the button appears as a soft accent pill only when
the mouse is over it. The rows line up: every record's emoji sits in a fixed-width
cell and the name column fits the longest name, so the ports and numbers share
their columns whatever the mark. The TTS Calibration record carries the glowing
PandorumLLM icon, like PTI and PME. And the opened request/reply window is colour
coded: JSON keys and values in their own colours, the prompt laid out as real
lines with its headings and bold runs lit, tags in gold and internal thoughts in
grape on the reply side.

v3.74 patch122: the Proxy terminal looks like itself again - patch121's fixed-width
mark cell assumed a timestamp at the start of every line, so with Hide Stamps on
the provider names fell into that little cell and wrapped two letters at a time.
The mark is recognised by what it is now, so the layout holds with stamps on or
off. And things move instead of snapping: a new terminal record fades and rises
into place, and the Monitoring bars ease their segments to new widths on every
spoken line rather than jumping.

v3.74 patch123: quitting the panel now closes the TTS server even when a panel
restart happened in between - servers running on the panel's own config file are
found and stopped as process trees, and only those; anything you started yourself
is never touched. The Thinking switch and its budget slider each sit under their
own white title in both calibration rows. The Monitoring block stops blinking on
refresh: the pane is seeded from the last known reading before any fetch, and
nothing rewrites content that has not changed. And the player's name is learned
from a third place - the player's own thought prompt - then handed to PTI and PME
so the tagger and the mood reader know who is speaking; spoken lines in the Proxy
terminal carry the name from the moment it is learned.

v3.74 patch124: the Proxy terminal breathes where something was said - a record
with thoughts, spoken lines or actions under it gets your row gap before and
after, and plain records sit tight. And quitting finally takes the TTS server
with it, every way out: the exit now runs exactly what the TTS page's Stop
button always ran - stop the process the panel started, then whatever owns the
TTS port - before the fleet shutdown, and both Ctrl+C and closing the console
window trigger it. Works on machines with only Windows PowerShell as well.

v3.74 patch125: the Proxy terminal reads tighter - plain rows close up while the
air around spoken bundles stays - the tree elbows are honest (a single branch is
a turn, not a tee), action rows line up with spoken rows, and generic NPCs like
"Hunter [Bandit]" are named Hunter instead of "someone". And under Player Tag
System there is a new Audio Tags board: every tag the built-in prompts offer as a
small lit button. Click one to turn it off - it leaves the built-in PTI and PME
prompts, their examples and their filters - and click it again to bring it back.
Custom prompts are never touched; a yellow chip says so when one is active.

v3.74 patch126: three finishes on those newest pieces. The built-in wording in
the prompt editors sits in its own read-only field with a copy button in the
corner; the yellow Custom Prompt Active chip stands beside the Audio Tags title
rather than under it; and each tag group - Emotion, Audio - is titled above a
bordered field of its own, like a text field that holds buttons.

v3.74 patch127: the Proxy terminal's row rhythm is finally what was asked for -
and the culprit was the emoji. A colour emoji is taller than the text line, so
every record row was quietly growing to the emoji's height while everything else
tightened. The mark cell now has a fixed height, plain rows keep a short breath
below them, a bundle's rows sit tight, and the air at a bundle's edges is the
longest spacing on the screen.

v3.74 patch128: the TTS speed regression is found and closed - the automatic
calibration could start its long model call in the split-second between two
spoken lines and then share the card with everything that followed. Background
jobs now wait for real silence, never for an instant. Monitoring shows two new
boxes, speed (median realtime factor) and retries, so the engine's pace is a
number you can watch. And a new GPU Clock Hold switch under TTS Server can lock
the card at its maximum clock while the server runs (needs administrator,
released on stop and on exit), so short lines stop paying the idle-clock ramp.

v3.74 patch129: the row spacing finally lands where you read it. The Proxy
Terminal page is the maximized view, and it had a line-height of its own that
quietly overrode every rhythm change of the last few patches. That override is
gone: one rhythm everywhere - tight plain rows with a short breath, bundles
close together, the longest air at a bundle's edges.

v3.74 patch130: the Proxy Algorithm is the standard calibration now, and it does
everything itself - refitting the speech rate by least squares every few lines
and stepping the samplers from the failure record, one bounded notch at a time,
each change logged with the numbers behind it. No model, no server, no waiting
for a quiet moment: arithmetic cannot contend with speech. The LLM method stays
as an option. The headroom is now a percentile rather than the single worst
line, the measured record is read from memory instead of re-parsed per line, and
the tag board is titled Player Audio Tags.

v3.74 patch131: the plain rows finally stand at the same height as everything
else. The last grower was the mark cell's alignment - a baseline-aligned cell
hands the row its internal, emoji-tall baseline however small the cell is
made, so the cell is now top-aligned and contributes only its own height.
Bundle rows were never affected, which is why each earlier fix looked right
below and wrong above.

v3.74 patch132: a second tag board, Allowed Tags, sits under the Audio Tags
setting - the final word on what reaches the engine. Every tag Higgs
understands is a button: click one off and it never gets sent, whether it
came from an NPC line, the player tagger, or an [angry]-style alias - and a
blocked sound effect takes its written-out sound with it. The Player Audio
Tags board still decides what the models are asked for; this one decides
what the engine is sent.

v3.74 patch133: the Proxy terminal rhythm was settled by running the panel's
own display pipeline outside the browser and reading what it produced: two
real faults, in text, not styling. Bundles that touched stacked their blank
rows double, and the player's own arrow-marked spoken lines did not count as
response rows at all, so they broke their bundle apart and spaced like plain
records. One shared classifier fixes both: blanks now exist only at bundle
edges, one run at a time. Also fixed: the Audio group's tag buttons toggle
(a case mismatch ate the click), a separator line sits above Player Audio
Tags, and the Allowed Tags board hides itself while Strip is selected.

v3.74 patch134: the terminal rhythm finally shows - the Row Spacing default
was None, and None rendered the raw log file untouched, blank lines and all,
so none of the spacing work ever ran on a default setup. The default is now
1 row, None means truly flat, and a Copy raw tail button in Adjust captures
the feed for any future report. And Tag Limits: on both tag boards, a Tag
Limits button lets you click any tag and choose how many of that character's
own turns must pass before the tag can be spoken again - the player by
player turns, each NPC by their own - with Save and Reset beside it. No
more NPCs laughing in every single line.

v3.74 patch135: the panel now notices its own updates - a page left open
across an update reloads itself once, so fixes reach every tab instead of
only freshly opened ones (hard-reload each open tab once after THIS update;
it is the last time that is ever needed). Spoken lines in the TTS and Proxy
terminals replay on click - a soft glow on hover, a pulse while the audio
plays - served from the same kept files the engine already writes. And the
tag-limit boxes open a small < N > stepper under the clicked tag instead of
cycling, with the green count badge kept right where it was.

v3.74 patch136: the Proxy terminal is back to plain, even spacing - one
uniform row height for everything, no special rules, and the Row Spacing
control is gone with them. Replaying a spoken line now works across a
two-PC setup: open the panel in a browser on the SkyrimNet machine and the
click plays there, on the speakers that normally carry the TTS. The tag
limit stepper's arrows are now full-size with the same accent glow as the
rest of the panel's buttons.

v3.74 patch137: server cards keep their first row - title, port, status and
the close stay on one line, long titles trim themselves, and automatic names
read Server (N): <gpu>. A small version badge sits in the page's corner
naming the page you are actually running - a tab with no badge is an old
page and wants closing. And clicking a spoken line now plays it on every
open panel page at once: host and the remote view on the game PC alike,
each through its own speakers.

v3.74 patch138: installing Higgs now shows its folder paths the moment the
install finishes - no page reload needed. And the panel ships tuned the way
it is meant to be played: audio tags pass to the engine, the mood reader
runs every 5th NPC line, sampler calibration is Automatic, the startup ping
is No, and the Proxy translates for SkyrimNet (the option is named The
Proxy now). Settings you have already saved stay exactly as you set them.

v3.74 patch139: the Proxy terminal's record rows now stand exactly as tall
as the dialogue rows - the record mark cell is styled identically to the
spoken rows' cell, the one that was always tight. And the server cards keep
their shape: the title row holds only the title, rename and close, while
the port - now a quiet grey capsule - and the HTTP status sit on their own
row beneath.

v3.74 patch140: the Proxy terminal spacing is fixed at the true root - a
single carriage return. Windows log lines end in CR+LF; the page kept the
CR and the browser turned it into a second, empty line inside every file
row, which is why records looked double-spaced while spoken lines sat
tight. The panel now scrubs it before painting, in every terminal. Rows of
every kind finally stand at one uniform height.

v3.74 patch141: the terminal rows were rebuilt from scratch. Every row is
now a fixed-height, single-line box - nothing that arrives in the log, and
nothing drawn inside a row, can make it taller. Long lines scroll sideways
like a real terminal. Records, branches and dialogue all stand at exactly
one uniform height, guaranteed by the shape of the row itself.

v3.74 patch142: long lines wrap again - dialogue hangs neatly under its own
first line with the tree connector reaching the full row - and the glow and
pulse effects render clean instead of being sliced at the row's edge. Rows
still cannot double up: nothing with a line break in it can reach a row in
the first place, and the release gate proves it with a poisoned feed. The
Adjust toggle formerly called Insert TTS is now Dialogue Text.

v3.74 patch143: the terminal row spacing is settled - the last grower was a
run of invisible trailing spaces on record lines that wrapped onto a hidden
second line. They are stripped as the feed arrives, wrapping and glow stay
exactly as patch142 restored them, and the release gate now proves both
break sources dead on every build.

v3.74 patch144: the terminal's rhythm is held by construction. Dialogue,
thoughts and branch lines wrap as before; every record row is a fixed
single line that nothing can stretch, with its glow intact. The page also
scrubs every invisible break character a log could carry and drops the
file's trailing blank, so no phantom rows remain anywhere.

v3.74 patch145: dialogue icons now show the character's emotion - a sound
effect like a sigh never stands in for a feeling. Hovering a provider
record glows the glyphs instead of painting a box behind them. The audio
tag stepper's arrows are a quarter larger. And wrapped dialogue folds
between words, with the realtime reading moving to the next row whole.

v3.74 patch146: launching or stopping a server from its card now reads like
the TTS buttons - Launching Server... and Shutting Down... stay pressed for
the whole phase - and the card's small terminal stays open from the press
until the server is up or fully gone, streaming the slot's own console log
the entire way.

v3.74 patch147: thought lines in the Proxy terminal can now be heard.
Click one and it is spoken in the character's own voice with an inner-
monologue echo, cached so a repeat click replays instantly, and played on
every open panel page - the game PC included. The character needs to have
spoken once so the panel knows their voice.

v3.74 patch148: clicking a thought line now actually plays it - the click
handler had a one-word bug that threw before asking for audio. And thought
voicing can run by itself: arm NPC thought Audio on the TTS page (a new
Thought Audio section after Player Tag System) and every NPC thought is
spoken automatically with the inner-monologue echo, either just before its
dialogue line or right after it - your choice in the Sequence menu.

v3.74 patch149: the thought echo is subtler and deeper - half the ring,
with a low bass boom underneath so it sounds like the inside of a head.
And thought lines can now be clicked from the remote panel window on the
second PC: the host generates the audio and it plays right there.

v3.74 patch150: two new providers for the NarrativeEngine SkyrimNet plugin
- NE-Composer and NE-Director - on ports 1264 and 1265. They appear on the
Providers page after the existing providers and before PTI/PME, in bright
grey, arrive unallocated in existing setups on the next start, and join
providers.yaml once placed on a server.

v3.74 patch151: the Thought voiced note now reads as a note instead of
being mistaken for a dialogue response; the thought echo is subtler still
with twice the bass; the two NarrativeEngine providers now appear by
themselves on the next panel start; and providers.yaml no longer contains
the two bogus :0 PTI/PME entries - regenerate it once after updating.

v3.74 patch152: with Sequence set to After, the NPC's thought now waits
for the entire dialogue reply - every spoken chunk of it - and plays only
once the last one has finished. Before-mode already respected the whole
reply and is unchanged.

v3.74 patch153: server 2 launches again - the panel's launch-time flag
editor now understands a PowerShell variable as a flag's value instead of
leaving it behind as a stray argument llama-server rejects. LLM Controlled
is retired (Proxy Algorithm is the automatic mode; old configs keep their
behaviour), server cards read Server 1: with roomier headers and centered
section rules, every ? mark now opens its explanation on click instead of
pressing the button under it, and the card terminal holds one steady size
through the whole launch.

v3.74 patch154: server 2 for real this time. patch153 stopped the launcher
editor from creating the stray argument, but your config already carried
one from earlier launches and the editor kept re-saving it. The editor now
cleans up the whole value list when it touches a flag, so the very next
launch repairs the stored launcher and the server comes up.

v3.74 patch155: a full pre-release sweep. The read-only LAN view now truly
hides your paths, GPU serials and launcher contents - verified by the
release gate on every build - and every listener stays on 127.0.0.1 unless
you have actually configured a second PC or switched LAN mode on. A pile of
dead code left over from retired features is gone.

v3.74 patch156: the launcher exe is rebuilt from source with its embedded
copyright matching the LICENSE that now ships in the release - source-
visible, personal use and modification only, no redistribution.

v3.74 patch157: provider boxes in Live Network put a space between the
emoji and the name, and the ? beside Tag Limits is a real click-for-help
badge like the others.

v3.74 patch158: the Proxy terminal and the Files viewer are back - two
constants lost in the patch155 cleanup are restored, and the release gate
now proves every name the page uses is declared. The Speech Rate menu is
gone: the stored fit is used automatically whenever a valid one exists,
and Refit Interval takes its place.

v3.74 patch159: thought audio in After mode now waits for the dialogue to
actually finish sounding - the timing model includes the game's own start
latency and the gap between chunks - and the thought voice itself carries
less echo with a deeper 60 Hz body.

v3.74 patch160: thought audio timing solved at the root - a second thought
arriving while a reply was still sounding used to erase the first and fire
early; thoughts now queue per reply and play in order, and the TTS
terminal logs every arm and fire so timing is visible.

v3.74 patch161: Before-mode now holds the dialogue for the thought's full
realtime length plus half a second, exactly as specified; After-mode
already followed the same rule since patch160.

v3.74 patch162: the thought now waits for the reply's FINAL dialogue
chunk - recognised from the reply text the proxy already saw - plus that
chunk's audio length and half a second, exactly as designed.

v3.74 patch163: thought audio now counts the dialogue chunks that were
spoken before the thought even existed - the whole reply's playback is
reconstructed from an always-on trace, so the thought waits for the real
end of the reply.

v3.74 patch164: thought timing counts every dialogue chunk - vocalization
prefixes no longer evict chunks from the reply - thought synthesis logs
like dialogue in the TTS terminal, and a delay line shows the exact
period calculated between the dialogue and the thought.

v3.74 patch165: Before-mode thoughts defer cleanly when they arrive
mid-reply (and sequence switches no longer strand old timers), After's
extra half second is trimmed, and NPC lines in the Proxy terminal wear
their Higgs emotion faces again.

v3.74 patch166: NPC lines wear their emotion faces again (the on-wire tag
form is read now), Before-mode thoughts front their own reply even when
the first chunk races the stream, and the Log page files TTS and PTI/PME
under their own headings with per-server filter buttons and a five-file
rotation for calculation logs.

v3.74 patch167: NPC emotion faces read the raw LLM tags at last, a held
first chunk no longer splits its reply apart on the dashboard, thought
blocks in the TTS terminal match the dialogue layout, and tts.log files
under the TTS category.

v3.74 patch168: NPC emotion faces are read from the completion itself -
the only place SkyrimNet leaves the tags - one queued face per chunk,
and a held first chunk no longer breaks its reply out of the dialogue
branch on the dashboard.

v3.74 patch169: NPC emotions are forwarded to Higgs at last - the tags the
LLM writes are read from the dialogue completion and armed onto each
spoken chunk as real control tokens, ruled by the same tag board and
per-character limits as the player's.

v3.74 patch170: the NPC emotion forwarding now actually fires - the tags
are captured from every dialogue reply (thought or no thought), and a
chunk that races the completion by milliseconds waits it out instead of
going unarmed.

v3.74 patch171: Emotion Chunk Placement chooses where the LLM's emotion
lands (first chunk or every chunk), sound tags are never doubled again,
sound-only lines wear the sound's icon, after-mode thoughts no longer
fire into the gap between chunks, and TTS terminal blocks never
interleave.

v3.74 patch172: after-mode thought timing is back to its best - short
prefixed final chunks are recognised again and a chunk racing its own
completion can no longer match the previous reply, so thoughts land
after the reply ends, without defer storms.

v3.74 patch173: the per-chunk gap the thought timer allows is doubled to
0.6 s - tag-performed lines hand between chunks more slowly - closing
the last half-second of overlap into the final chunk.

v3.74 patch174: the TTS terminal is tidied - blocks separated by blank
rows, thought lines written out in full and coloured, and every report
row's numbers, units and names inked in the same palette as the Proxy
and Thinking terminals.

v3.74 patch175: provider priority now holds for the full length of a
high call - normal providers no longer barge onto the same GPU after
eight seconds - and the ActionEval drilldown rides ActionEval's own
priority as it always structurally did.

v3.74 patch176: two-stage high-priority work (ActionEval and its
drilldown) now holds its GPU across the gap between the stages, so a
queued normal provider can no longer slip in between them.

v3.74 patch178: every TTS generation reports the banned tags and each
character's live tag-limit countdowns - (2) turns left, (+2) just
recorded - and a limited tag is refused before it can fake a face or a
log line.

v3.74 patch179: audio tag limits count LLM responses (the round), not
TTS chunks - proven end to end in the gate - and multi-sentence thought
audio is synthesized per sentence and joined, so the whole thought
plays back.

v3.74 patch180: two new providers for the AgencyEngine SkyrimNet plugin
- AE-Impulse and AE-Resolve - on ports 1266 and 1267, in rust on the
Providers page and in the proxy terminal. They arrive unallocated in
existing setups on the next start and join providers.yaml once placed
on a server.

v3.74 patch181: TTS retries escalate instead of repeating - the token
cap grows half again per attempt and the samplers cool further each
step - and the new provider emojis are pickable, carried by seeded
defaults, and healed onto existing emoji-less entries.

v3.74 patch182: the server card and ps1 launcher now have the final word
on max tokens over anything SkyrimNet sends, and after-mode thought
audio no longer stalls on chunks SkyrimNet abandoned - quiet replies
fire within seconds on what actually played.

v3.74 patch183: two characters sharing one voice sample no longer swap
names on spoken lines - the line is identified by the words it carries,
matched against the reply the character actually generated.

v3.74 patch184: a housekeeping pass before the public update - dead code
and unused constants removed, the fit tooltip's missing numbers written,
open request counts added to the debug report, and the self-check
hardened so nothing can sit in the panel unused again.

v3.74 patch185: support for Meta's Muse Glimmer - its DFlash assistant is
recognised as a draft model, a one-file multimodal model is no longer
mistaken for a vision projector, and choosing a DFlash drafter emits the
speculative flags llama.cpp needs instead of --model-draft.

v3.74 patch186: the Vision and Speculative decoding pickers now reach a
hand-edited launcher like every other server card setting - choosing
Disabled removes the flags from the file that runs, and every card
setting is proven to survive the trip out and back.

v3.74 patch187: a server card setting always reaches the launcher now,
even when the value chosen happens to be the default - and the card is
read back out of the launcher afterwards, so the file that runs and the
card that describes it cannot disagree.

v3.74 patch188: server cards now show the model architecture read from
the file's own header - Muse Glimmer, Gemma, Qwen, Llama/Mistral,
DeepSeek, GLM, Command-R and many more - and the reasoning controls
adapt to it: a model whose thinking cannot be switched off is offered
a reasoning strength instead.

v3.74 patch189: the shipped default configuration now lists the same
providers the panel seeds, including the NarrativeEngine and
AgencyEngine pairs.

v3.75 Beta: a release of everything the v3.74 patch line brought - Muse
Glimmer support, model architecture detection on every server card,
voiced NPC thoughts, emotion forwarded to the voice engine, and server
cards that stay in step with their launchers.

v3.74 patch190: the Emotion Chunk Placement setting is gone - a reply's
feelings now reach the voice exactly as the model wrote them, in reading
order across the spoken chunks.

v3.74 patch177: emotion tags can be banned outright - the Final-Off
board now rules the NPC mood armer as well as the wire - and every
spoken line's TTS report states its Banned Tags and Tag Limits
(remaining turns, and limits this line just started) in the open.

    # --- reasoning OFF (dialogue model) ---
    "--reasoning", "off",
    "--chat-template-kwargs", '{"enable_thinking":false}',

Turning Reasoning back on removes that line again. A --chat-template-kwargs you set
yourself for other reasons is left alone - the dial only ever writes and removes the
one it wrote. This is a server-side default for every request; the per-request fields
from patch94 still apply on top, per provider.
