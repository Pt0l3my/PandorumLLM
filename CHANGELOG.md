# PandorumLLM — Full Version History

Every released version, newest first. Compiled from the changelog in `README.txt`,
which has had a paragraph appended on every release — so this is the real record,
not a reconstruction.

**Current version:** v3.76 Beta.

---

## v3.76 Beta
- **Every speculative decoding setting opens its own page in the Sampler Guide.**
  Each control on a server card shows the llama.cpp flag it writes, in blue, and
  clicking that flag opens the setting's explanation. The seven speculative ones were
  drawn the same blue and did nothing - four had pages by then and three had never
  been written. All seven have a page now, and the blue text behaves the way blue
  text behaves everywhere else on the card.
- **Four new pages cover the drafter's own dials**: minimum draft tokens, split
  probability, backend sampling, and the draft model's separate KV cache precision -
  including why quantizing a drafter's cache usually costs more than it saves.
- **The Sampler Guide now covers every repetition penalty llama.cpp offers.** It
  explained DRY and XTC but said nothing about the four classic ones, so anyone
  reaching for a repetition control had no way to choose between them. Repeat
  penalty, its shared look-back window, presence penalty and frequency penalty each
  have a page, with what they do differently from one another and from DRY.

## v3.75 patch44
- **The repository now states its own line endings.** The exact bytes of every file
  are part of what this project checks, but nothing told git that - so a copy taken
  with `git clone` was formatted according to whichever setting happened to be on the
  machine doing the copying. On a common Windows setup that hands back the wrong
  endings for the documentation and for one of the launcher scripts, and the panel's
  own checks then fail on files nobody had edited. Each rule mirrors one the checks
  already enforce, and a new check compares the two so they cannot drift apart.

## v3.75 patch43
- **The tags that ship off now reach an existing installation too.** A setting is
  only replaced on upgrade when it was left empty, which is right for a preference
  and wrong for a measurement: anyone who had ever adjusted their tag board kept the
  six broken emotions switched on. They are added to whatever the board already
  holds, once, so nothing chosen is lost and switching one back on afterwards sticks.

## v3.75 patch42
- **The tags that ship off are still on the board.** Six emotions - disgust,
  elation, longing, sadness, shame and determination - are switched off on a fresh
  install rather than removed. They appear on Allowed Tags like every other tag, and
  one click brings any of them back. The previous patch took them out of the list
  entirely, which also took away the switch; elation in particular has been judged
  harmful, then harmless, then harmful again over this project's life, and the tag
  most likely to need a human overrule was the one that had lost its control.
- **They are not offered to the tag injector or the mood reader.** The prompts are
  built from whatever the board still has switched on, so a model is never asked to
  choose a tag the panel would drop - it only gets one emotion per line and was
  spending it on these.
- **Switching an emotion off now stops NPC lines too.** The mood pass writes a
  finished control token into the line, and the wire gate leaves a line that already
  carries one alone - so a tag turned off on the board was honoured for the player's
  own lines and ignored for every character around them. The mood pass reads the same
  board now.

## v3.75 patch41
- **Five emotion tags are no longer used.** Disgust, longing, sadness and shame make
  Higgs speak the line as a different person entirely; elation keeps the speaker but
  loses them, at four times the loudness of a normal take. Each was measured on one
  short line with the engine deliberately left conditioned on another character's
  voice, so every tag faced the same pressure. The other sixteen emotions came back
  correct, amusement and pride among them as controls. The five are refused on the
  wire and are no longer listed in the prompts the tag injector and the mood reader
  are given - a tag the panel would refuse is not a tag worth asking a model to
  choose, and it was spending its one tag on them.
- **A character borrowing another's unique voice is called by their own name.** A
  voice sample whose filename carries a character's name identifies the sample, not
  whoever is speaking through it - and SkyrimNet lends those samples out. Every line
  spoken through a borrowed one wore the original owner's name, even when the words
  of the line itself said otherwise. The filename still answers when nothing else
  can, and still outranks timing.

## v3.75 patch40
- **A character's line is never named after the player.** The panel already refused
  a name that belongs to another voice sample, but it worked that out by looking at
  the samples characters have spoken through - and the player's own sample is
  deliberately kept out of that record. So the player's name was the one name the
  guard could not see, and SkyrimNet queues it as often as anyone's, because it
  writes the player's dialogue too. A line of Colette's arriving while a player line
  was queued was announced as the player's.
- **A queued line that could not have been this character's no longer silences the
  one who is speaking.** Chunks of a single utterance are held together by the
  character who just spoke, and that hold stands down whenever a new line is waiting
  - correctly, because a shared voice sample belongs to whoever spoke most recently.
  A waiting line whose character speaks through a *different* sample was never a
  claim on this one, and counting it left the true speaker unnamed: the line printed
  as its raw voice sample instead.
- **A take longer than the sample it was cloned from is recorded.** One line came
  back in the wrong voice after asking for 7.3 seconds of speech from a 5.6 second
  sample - the highest such ratio of that session, and the only line that went wrong.
  Whether that is the cause is not yet known, so the panel measures it rather than
  guessing: the terminal and the log now name any take that runs past its reference.

## v3.75 patch39
- **An NPC's thought waits for the line it belongs to.** A spoken chunk was only
  counted once its synthesis came back, so a chunk the panel was still waiting on
  left no trace at all - and a reply whose last chunk took more than three and a
  half seconds to make read as a reply that had finished. The thought then spoke
  over the ending it was supposed to follow. A chunk that has been asked for and
  not yet answered now counts as the reply still arriving, and the thought waits
  for it.
- **A thought is synthesized once.** The warm-up that starts on a reply's first
  chunk and the playback that follows it ask for the same audio, and neither
  could see a file the other was still writing - so both made it. The second take
  held the only speech engine while the reply's own next chunk waited behind it,
  which is the delay that made the thought early in the first place.
- **The next character waits for a thought that is still being spoken.** Thoughts
  play in the panel and dialogue plays in the game, and nothing joined the two:
  the next line began on top of the thought before it. A line now waits for the
  thought to finish, up to twelve seconds. The player's own voice is never held.
- **A character whose name is longer than 29 characters is finally heard.** The
  speaker of a request was read with a pattern that stopped at 29 characters, and
  a longer name did not fail loudly - it matched nothing, and the reply was filed
  as having no speaker at all. Four things hang off that name: the emotion tags
  the model wrote, the reply text the last-chunk decision compares against, the
  reply ring, and the thought itself. "Ertzebet the Librarian's Assistant" is 34
  characters, so she had no tags, no thought audio and no name in the identity
  ledger, and her thoughts appeared in the dashboard as a bare "thought:". The
  action a character chose was capped the same way.
- **The Providers and Options panels look like the Adjust panel.** They drew a
  flat grey outline where Adjust draws none, and sat flush under the bar where
  Adjust floats. Same glow, same corners, same spacing.
- **All on/off sits in the middle of the Providers panel** rather than against
  its left edge.

## v3.75 patch38
- **When a thought lands early, the log now says why.** A spoken chunk is judged
  the last one by matching how it ends against the reply the proxy already saw.
  That verdict was silent, so a thought firing after the first chunk looked the
  same whether the reply was missing, too old, or simply did not match - three
  different faults with one symptom. Each now names itself in the TTS
  calibration log, with both tails, and only while a thought is actually waiting.
- **The action a character chose is shown by default**, like thoughts.
- **Action parameters are written whole.** They had been cut at 60 characters,
  which removed the end of exactly the ones worth reading.

## v3.75 patch37
- **SkyrimNet's startup ping is Banned by default** - answered with silence and
  not announced. Speaking it cost 600-1100 ms of GPU for a word nobody wants to
  hear, and announcing it put a line in the terminal every time the game
  started.
- **An NPC's thought is shown by default.** It is the reason the line after it
  makes sense, and shipping the switch off meant the terminal looked broken to
  anyone who had not found the button.
- **Terminals start without the time column.** It is the same clock on every
  row and it costs the width where the line matters; the Timestamps button is
  still there for a session where the timing is the point.
- **Chunk size returns to 170 characters.** It had been lowered to 140 for a
  slightly earlier first chunk; more chunks per line also means more chunk
  boundaries for anything that waits on the last one, and thought placement
  went back to firing early in the same window.
- **One button turns every provider on or off** in a terminal's Providers
  panel, labelled from what is currently showing, and the providers now wrap
  into an even grid instead of a single row that ran off the right edge.

## v3.75 patch36
- **Player lines get their audio tags again.** PTI and PME hang off a server
  without a listener of their own - Live Network shows them as "Proxy" rather
  than a port - and the readiness check asked about that missing port, got
  "unknown" every time, and quietly sent every player line untagged while the
  server was serving perfectly. It now asks whether the SERVER is up, which is
  the thing that has to be.
- **Remote Access takes effect when you switch it.** The socket was bound once
  at startup, so turning Remote Access on did nothing until the panel was
  restarted - while the page printed the address to visit. The panel now listens
  on the network interface and decides per request: external addresses are
  refused outright, LAN addresses are refused while Remote Access is off, and
  allowed the moment it is on.
- **An install no longer reloads the page.** The fields an install fills are
  written straight from the state the page just fetched, so the folder paths and
  the model selection appear without discarding the terminal, the scroll
  position or anything half-typed.

## v3.75 patch35
- **Every setting on a server card is editable.** The card could grey a control
  out when another setting appeared to overrule it - and the reasoning behind
  one of those was simply wrong, which locked Model load mode on exactly the
  machines that needed it changed. The explanation stays; the lock is gone. The
  machine belongs to the person running it.
- **Installing or adopting Higgs reloads the page.** A repaint can rebuild the
  pane from current state, but not anything the page read once when it opened -
  which is why three rounds of more careful repainting still ended in CTRL+F5.
  An install is rare and deliberate, so it now just reloads.

## v3.75 patch34
- **Context checkpoints default to 0.** Each checkpoint is a rollback copy of a
  slot's context held in system memory, and llama.cpp keeps eight per slot by
  default - real RAM on a large model at a long context, and the last reason a
  model that should not have fitted appeared to fit and then ran slowly. This
  panel's own guide already said to set it to zero.
- **The fleet template states both cache zeros explicitly**, `--cache-ram 0` and
  `--ctx-checkpoints 0`, because an unstated zero is not a zero: the server
  falls back to its own defaults for whichever one is missing.
- **A default server launcher now closes every route into host memory** - no
  fitting across cards, no memory-mapped weights, no KV spill, no checkpoints -
  so a model that does not fit its card fails at launch instead of quietly
  borrowing system RAM.

## v3.75 patch33
- **Model load mode defaults to `dio`, and it is what keeps a model on its own
  card.** Memory-mapped weights stay host-resident, and llama.cpp will place
  them across whatever it can reach: measured on a three-card machine, one model
  landed on three GPUs plus system RAM under `auto` and on the single pinned
  card under `dio`. Every server card and the fleet template now ship with it.
- **The load mode control is always settable.** It had been greyed out on any
  card with every layer on the GPU, on the reasoning that it only affected load
  time - which is exactly the claim the measurement disproved. Its guidance
  moved into the hint beneath it, and the Sampler Guide page now explains that
  the flag decides where the weights end up, not just how fast they are read.
- **Installing or adopting Higgs repaints the TTS page immediately.** Both raise
  their own event now, and that repaint is not deferred for focus - the button
  that started the install holds focus and nothing ever takes it away, which is
  why adoption in particular left the page stale until a restart.

## v3.75 patch32
- **A server with no GPU chosen is given one.** A fresh install creates its
  slots unassigned, and an unassigned slot pinned nothing - so every server saw
  every card, whatever the launcher was otherwise doing. At the moment a
  launcher is written, a bare slot now takes the least-loaded card - the bigger
  card on a tie - the choice is written back so the card shows it, and the
  assignment is logged. Only a machine with no GPUs at all still writes an
  unpinned launcher, and says so.
- **The installed Higgs model is selected in the dropdown again.** The
  installer had begun storing the model's file name where the list matches full
  paths, so a freshly installed model sat beside a selector reading "(none
  selected)".
- **Clicking a detected IP address fills the field again**, and the suggestion
  chip is a single element rather than text wrapped in a second layer.
- **The TTS page repaints after an install even while a button holds focus.** A
  repaint deferred for focus now has a due date rather than waiting for a blur
  that never comes; it still yields to someone actually typing.

## v3.75 patch31
- **The GPU pin is written into the launcher that runs.** A server card stores
  its launcher text and the panel writes that text as it stands, editing only
  the flags inside the argument array - so a pin written as a template
  placeholder stayed a placeholder, and every card remained visible to every
  server. The pin is now imposed on the file at the moment it is written,
  whatever produced the text: a placeholder is replaced with the chosen card, a
  launcher without a pin gains one before the argument array, the line is never
  duplicated, and a slot with no card chosen writes no pin and says so in the
  log.
- **Installing or adopting Higgs fills every path it discovered** - the audio.cpp
  folder, the TTS models folder, the chosen model and the Sample Vault, which is
  created rather than only named - from one writer used by both routes, and the
  page is told to redraw so the fields match the banner above them.
- **Addresses on Proxy Setup respond to a click**, rather than showing a text
  caret over a field nobody types into by hand.

## v3.75 patch30
- **A server set to "Auto fit to VRAM: off" now says so to llama.cpp.** The flag
  was written only when the setting was on, and llama.cpp fits by default - so
  "off" meant nothing was written and the engine fitted anyway, redistributing a
  model across every card it could see and spilling the remainder into host
  memory. The setting now states both halves.
- **The fleet has its own launcher templates**, in `server-templates\`. Every
  one of them pins a single card, keeps every layer on it, turns fitting off,
  and reports how the server ended. The Launcher Creator keeps its own templates
  in `templates\` and is a separate feature: its files are no longer offered to
  server cards. They were read from one folder, which is how a template whose
  own header reads "no GPU pinning - for 1 PC / 1 GPU" reached a multi-GPU
  fleet, leaving every card visible to every server.
- **`server-templates\pinned-server.ps1`** ships as the fleet template: the GPU
  mask, all layers on the card, fitting off, unfiltered llama.cpp output for the
  VRAM report, and the exit line the panel reads.

## v3.75 patch29
- **Voice warm-up is removed.** It synthesised a whole discarded take on every
  speaker change to absorb the engine's carryover from the previous voice.
  Measured across 185 spoken lines, preparation cost 33 ms when the speaker was
  unchanged and 749 ms when it changed - 1459 ms from one NPC to another. The
  carryover it was built to fight went away with the reference samplers, so the
  cost bought nothing. Setting, control, ledger step, meter band and legend are
  all gone; there is no hidden switch left set.
- **The addresses on Proxy Setup are readable.** The previous patch cleared the
  blur from a class these fields do not use; this clears it from the one they
  do.
- **Saved Audio Folder shows a full path** rather than a bare folder name, so
  the field says where the files actually go.
- **Reverting TTS settings keeps the installed engine.** Where audio.cpp and its
  models live is something an install discovered, not a preference - wiping it
  left an installed engine unreachable and the page asking for a folder nobody
  had chosen by hand. Everything else still returns to its shipped value.
- **Recognition language defaults to Auto**, so a player speaking any language
  is transcribed as they speak rather than as English.
- **Server-card launchers report how they ended.** The exit line added in
  patch26 reached the two templates but not the builder every server card
  actually uses; it does now, carrying llama-server's exit code and holding the
  window open.

## v3.75 patch28
- **The TTS page follows an install without a browser refresh.** A repaint asked
  for while focus sat inside the pane was refused outright; it is now deferred -
  the very next render redraws from fresh state, whichever path asks for it.
- **The Dismiss button dismisses.** It hides a finished install banner and
  destroys nothing, so it no longer sits behind the confirmation gate meant for
  destructive actions - which had been bouncing every click.
- **Revert to default TTS settings** sits beside the TTS selector. It asks
  first, then returns every setting and path on the page to its shipped value
  and removes settings this build no longer has. Engines, models, voice
  samples, transcripts, saved audio and the calibration record are untouched.
- **New defaults:** saved audio lands in a `TTSaudio` folder beside the panel
  (blank still means a temporary folder; a bare name resolves beside the
  panel); the longest kept sample stays 10 seconds through an install; and long
  lines split at 140 characters instead of 170, so the first chunk of a long
  line reaches the engine about a fifth sooner - most dialogue is shorter and
  is untouched.
- **The Proxy Setup addresses are shown plainly** - the blur that needed a
  click per value to check a typo is gone, and the text is selectable.
- **The Permission Tree names what this build can do**, including clearing
  calibration data, reverting TTS settings, and reading a slot's own log to say
  why a launch ended.

## v3.75 patch27
- **Model load mode** replaces the old Disable mmap setting on every server card.
  Current llama.cpp folded `--no-mmap`, `--mlock` and `--direct-io` into a single
  `--load-mode` flag and warns on each of the old spellings - and warns again if
  an old one is combined with the new, so this replaces rather than adds. The
  setting offers exactly the values llama.cpp accepts (auto, none, mmap, mlock,
  mmap+mlock, dio) and defaults to auto, which is llama.cpp's own default.
- **The Sampler Guide has a Load mode page** explaining what each value does,
  what it replaced, and that with every layer on the GPU it affects load time
  rather than generation. The old Threads page no longer claims mmap, and every
  card setting's cross-reference was repointed with it.
- **Two flags you may still type by hand are labelled deprecated** in their
  hints - `--mlock` and `--defrag-thold` - with what to use instead.

## v3.75 patch26
- **The default launcher no longer restarts itself.** Its last line used to
  re-invoke the file, so a server that could not start looped instead of
  stopping - and each attempt replaced the console holding the reason before it
  could be read. A launch that ends now stays ended, and the window stays open
  with llama-server's output still on it.
- **It reports how it ended.** llama-server's exit code is carried through, and
  the launcher prints the one sentence the panel's log reader needs to tell a
  server that died from one still loading. llama.cpp never prints that sentence,
  so only the launcher can - and it never did, which is why the panel could not
  distinguish the two for generated launchers.
- **llama.cpp's output still reaches the log untouched**, which is what the
  panel parses for the VRAM report - weights, KV, compute buffers, the draft
  split. Both the server-card template and the Launcher Creator template carry
  the same ending.

## v3.75 patch25
- **A server that does not start now says why.** Fleet servers run in their own
  consoles, so unlike the speech server there is no process to watch - a launch
  that ended left a card that simply never turned green, with nothing to read.
  The panel now reads the slot's own log: if the port is shut and the log has
  stopped growing, the card carries what the server last managed to write, and
  says so differently when the model had finished loading before it went away.
- **A DFlash drafter is asked for what it can actually produce.** The panel used
  to send the drafter's trained block size as the draft depth, which the engine
  reduced on every launch, so the number in the launcher was never the number
  that ran. The depth is now computed the way llama.cpp computes it: a plain
  DFlash block reserves its first slot for a token already known and can draft
  one fewer than its size, while an anchor-first DSpark drafter fills the whole
  block. Block size and anchor behaviour are read from the drafter's own header,
  and DFlash is told from DSpark by the tensor it carries - never by filename,
  so a repack or a rename cannot move a drafter between the two.
- **A reduction the engine applies anyway is reported**, taken verbatim from the
  server's log rather than from anything a launcher claims about itself.

## v3.75 patch24
- **SenseVoice has its own band now.** Its inference is a second model on the
  same card, and it was invisible: folded in with a stored-transcript read, or
  off the line entirely on the learner thread. Every transcription is timed
  wherever it is called from, and appears by name on the timing line, on the
  graphic bar, and in the calibration terminal.
- **The bar draws what was actually spent.** It used to name its seven bands in
  its own code, so steps the panel had been measuring since patch17 - thought
  synthesis, the sample gate, the sample transcript, the identity note, the
  voice warm-up - could never appear on it however long they ran. The bands now
  come from the record, largest first, with `panel` as the remainder so they
  still sum to the wall.
- **The calibration terminal carries the spend.** Its per-line tree is written
  before the take, so it could not say where the time went; a `spent` line now
  follows the take in the same terminal.

## v3.75 patch23
- **Two samplers, and nothing that moves them.** The section is now **TTS
  Samplers**: temperature and top-k, set by hand, sent with every line. Boson's
  reference for this model is temperature 0.8 with top-k 50 and nothing else;
  audio.cpp documents repetition penalty as accepted-but-ignored for the Higgs
  family, and top-p and min-p only ever narrowed the distribution toward the
  degenerate repeat. A control that cannot help and can hurt is worse than no
  control, so those three are gone. The per-line token limit is not a sampler -
  the calibration above sets it.
- **Sampler Calibration is removed**, dropdown and automatic step alike. Nothing
  adjusts these values now; they are yours.
- **Steady Retry is removed.** A retry carries exactly the samplers the first
  attempt carried. Stepping them colder each attempt walked the engine toward
  greedy decoding, which is what produces an endless repeated-token take - the
  rescue was feeding the fault. The token cap still escalates on a retry, which
  is the part that was always sound.
- **A top-p arriving from SkyrimNet is dropped** rather than forwarded, since
  this engine has no use for it.
- **The terminal hover no longer blurs the provider name.** It was stacking
  three effects - a 7px glow, a 16px glow, and a drop-shadow filter over both -
  and the filter re-blurred pixels the glows had already blurred. One tight glow
  now.

## v3.75 patch22
- **The player tagger can now say nothing, and is told that is the usual
  answer.** The default prompt asked for the line back "with tags added", which
  presupposes markup on every line - and a flat test sentence duly came back
  marked as singing. The prompt now states that most lines need no tags, that a
  tag is added only when the words clearly call for one, and that in doubt the
  answer is no tag; neutral examples outnumber tagged ones, including the exact
  sentence that failed. A custom prompt is untouched, as always.
- **The tagger skips a server that is not serving.** It used to pay a full
  timeout on every player line before failing open when its slot was down -
  silent seconds attributed to nothing. It now asks the same cached probe the
  fleet cards use, skips instantly, says once which server and port it is
  waiting for, and announces when tagging resumes.

## v3.75 patch21
- **Boson's own sampler values are the defaults.** The reference example for
  higgs-tts-3-4b is temperature 0.8 with top-k 50 and nothing else sent. The
  panel now ships exactly that: top-p, min-p and repetition penalty are blank,
  so the engine's own defaults stand rather than being narrowed by values that
  were never part of the reference setup.
- **Top-K is a setting.** It sits with the other sampler controls, is carried
  from SkyrimNet when SkyrimNet sends one, and reaches the engine as an integer.
- **The retry no longer narrows the samplers.** It used to step each attempt
  colder - temperature down by a fifth per try, nucleus tighter, minimum
  probability higher - on the theory that a retry only needs to finish. That
  walks the sampler toward greedy decoding, and greedy decoding is how the
  degenerate repeat happens: a 27-second take caught in the field was one 40 ms
  frame repeated about 650 times, bit-identical, which is a distribution
  collapsed onto a single token. The rescue was feeding the fault it was meant
  to rescue. A retry now simply asks again. The old behaviour remains available
  behind its setting for anyone who wants it.
- **Installing or reinstalling Higgs restores these values**, overriding
  whatever the fields held - a number carried over from a tuning session is
  exactly what a reinstall is meant to undo - and the page refreshes itself when
  the install finishes.

## v3.75 patch20
- **The token-cap margin was pinned, not converged.** The estimator measures how
  much headroom its own misses actually need, and every session for weeks it
  asked for about 2.65 and was clamped to 1.60 - the ceiling never once stopped
  binding. Worse, the clamp made its own evidence: a line that hits an
  estimate-decided cap enters the record at cap/estimate, which IS the current
  headroom, so hundreds of censored lines entered at exactly 1.60 and held the
  statistic down where the clamp was satisfied. The per-line cap is already
  bounded by the guard, so the headroom now defers to that instead of
  pre-empting it, and what remains is a sanity stop against a corrupted fit.
  Expect noticeably fewer retries on the lines that were quietly hitting their
  cap and being rescued by the retry ladder.
- **Clear calibration data** (TTS Calibration). Forgets every measured line and
  every recorded cap-hit, on disk too, after a confirmation that says what is
  lost, what happens next, and what is left alone. A long run under a binding
  clamp leaves a record full of censored lines that cannot report what they
  truly needed; starting empty converges on the truth faster than unlearning
  does. Voice samples, the vault, transcripts, saved audio and every setting are
  untouched.

## v3.75 patch19
- **One line reaches the engine at a time.** Higgs keeps its reference prompt
  state in the model session, and nothing was serialising access to it - a
  dialogue line and a thought could be inside it together. The evidence was a
  hash-verified male reference returning a female voice, one take running 15.2
  seconds for 3.1 seconds of audio, and two reports interleaving mid-write in
  the log. Requests now queue for the engine, and the time spent waiting is
  reported on its own `queued:` line and recorded in the timing stream rather
  than being absorbed into synthesis.
- **Two lines in flight keep their own timings.** The take-and-waste record was
  a single shared dict, so concurrent lines overwrote each other's numbers.
- **An allocation refusal no longer escalates the token cap.** The AR prefill
  graph is sized from `max_tokens`, so raising the cap after a refusal asked the
  card for a larger buffer than the one it had just declined - in the field it
  climbed 271 to 406 to 609 and failed three times for it. The cap now holds.
- **The "not enough VRAM" advice is gone.** It fired on a card with 19 GB free,
  where a shorter reference or a smaller model would have changed nothing. The
  message now points at the measured card figures on the TTS-E01 line and says
  plainly that a refusal with ample free memory is not a shortage.

## v3.75 patch18
- **The timing report measures the take that played, not the retry ladder.** A
  line that failed once and succeeded once was reported as a single very slow
  synthesis: the realtime factor, the tokens-per-second and the stored record
  all read a number no individual take ever took. On a real session that made a
  75 tps take read as 43 tps, which is how a healthy engine came to look like a
  broken one. `server:` and the realtime factor now cover the successful attempt
  alone, and anything discarded before it appears on its own `discard:` line
  with the number of attempts - shown, never hidden.
- **Every line's numbers are also written machine-readably** to
  `tts-timing.csv`: characters, tokens, audio seconds, the take's own
  milliseconds, milliseconds wasted, attempts, prep, the server's own split when
  it offers one, and the reference sample's length in seconds and bytes
  alongside the transcript length. Six requests at one line length cannot
  separate a per-request cost from a per-token one; this accumulates the range
  needed to do it properly while you play.
- **A missing server-side split is stated rather than absorbed**, so the panel's
  single figure is never mistaken for the engine's own measurement.

## v3.75 patch17
- **The audio path explains itself.** audio.cpp is now started with `--log`, so
  the server writes what it loaded and what each allocation cost; before this it
  said almost nothing, and a session that ran out of memory left a log that
  could not say what was resident. The panel also writes its own launch banner
  first - every model with its family, size and path, the card it is pinned to,
  what is already resident there, and the exact argv - so a server that dies
  silently is still diagnosable from the panel's own log.
- **Failures carry codes.** TTS-E01 through E06 name the failure classes, they
  survive rewording, and they grep cleanly out of a log. The memory codes also
  report what was actually on the card when the allocation failed.
- **An allocation failure no longer loses the line.** "failed to allocate ...
  graph" is the card being momentarily full, not a bad request; the panel now
  waits briefly and asks again instead of dropping the line silently. The old
  advice to try a shorter reference voice is gone - it was not the cause.
- **Every step on the audio path books its own milliseconds.** Thought
  synthesis, the sample gate, voice warm-up, transcript reads and identity
  notes each appear by name in the timing line. They were previously swept into
  one residual called "panel", which is how a 2.6-second thought synthesis came
  to look like the panel being slow.
- **The recogniser picker stops offering speech models.** Higgs and the other
  TTS models are hidden from the SenseVoice dropdown, with a note saying how
  many were hidden; a current selection stays visible so it can be corrected.

## v3.75 patch16
- **The recogniser joins the verdict.** A take the duration check merely
  SUSPECTS of dropping its words is now transcribed and judged on them: a
  strict majority of the sent words must be heard, or the take is convicted
  and retried once - and a brief take that spoke everything is kept and said
  so. Verification runs only on suspect takes, never on the hot path, and
  only while the recogniser is co-hosted; without it the old log-line
  behaviour stands.
- **Performances pass unjudged.** "Ahh...", a lone sigh, a tagged murmur -
  lines that are a vocalisation rather than words - are exempt from both the
  runaway and the short verdicts, in both directions, and they no longer
  teach the pricing model: their length is legitimately unpredictable, and a
  recogniser hears no words in them because there are none.
- **Tag costs are learned.** What a rendered sigh or an authored ellipsis
  actually costs is now measured from the lines that carried them, clamped to
  a plausible range, with the shipped constants answering until enough tagged
  lines exist. An ellipsis is priced once, as a pause - it was previously
  also counted as characters, quietly double-charging every trailing "...".
- **One expectation everywhere.** The runaway verdict now runs on the same
  per-voice model as the token cap, so what a line is priced at and what it
  is judged against can never disagree.
- **The Meta tags dial is gone.** It chose whether the recogniser emitted
  markers the panel then stripped unconditionally - a control wired to
  nothing visible. Transcripts behave exactly as before; the vault now also
  keeps a small note of what the recogniser heard in each adopted sample.

## v3.75 patch15
- **Every voice prices its own lines.** The per-line token cap was one constant
  for every speaker and every length: a flat floor for short lines and a fixed
  rate per character beyond it. Measured against real takes that was too tight
  where it hurts and too loose where it costs - and a cap-hit is not a shortened
  line, it is an HTTP 500 with no audio at all, so the line is lost and retried.
  The panel now fits what a line actually costs from what that voicetype has
  actually cost: a shared per-character rate, which belongs to the model, plus
  each voice's own overhead - the lead-in breath, the codec warm-up, the pace of
  a read - which is most of a two-word line and vanishes in a long one. Short
  lines gain room, long lines lose it, so false failures fall and a runaway is
  stopped sooner. Sound effects, ellipses and authored pauses are priced by the
  same arithmetic that records them, so what the model learns and what it
  predicts can never drift apart. A voice nobody has heard yet uses the fitted
  constants shipped with this build and adapts from its own takes; a runaway is
  never allowed to teach it.

## v3.75 patch14
- **Reference transcripts are the default, and the installer supplies the
  recogniser.** The mode ships On - which costs nothing until a model exists -
  and the Higgs installer now also fetches SenseVoice-Small (about 254 MB, the
  exact GGUF audio.cpp's own sense_asr documentation names) into the models
  folder and points the field at it. A fetch that fails is logged and the
  install proceeds; nothing depends on it.
- **The page explains itself and guards the one easy mistake.** Every control
  in Reference Transcripts carries the same ? explanation the section title
  has, and picking the TTS model itself as the recogniser - the only gguf in a
  fresh folder - is named in red for what it is, since the server would refuse
  the entry and the panel would drop it at start.
- **Finishing an install refreshes the page it changed.** Folder paths, model
  dropdowns and settings written by the installer now appear the moment it
  completes, with no browser refresh.

## v3.75 patch13
- **Runaway Handling, a mode of its own** (TTS Backend Settings). The engine's
  stop is unreliable both ways - the same two words once came back as 27
  seconds of audio, once as a sigh with the words dropped, both as ordinary
  HTTP 200 - so the default mode now MEASURES: every take's audio is held
  against what its text should plausibly run, fitted to real sweeps and
  pricing what tags perform (a sigh, an authored pause). A runaway is asked
  once more and the take closer to its estimate speaks, with both on record; a
  short take is noted, never retried, until the rate is known. The threshold
  is a setting (1.7x by default). "Line Time Limit" remains as the alternate
  mode with the previous clock semantics, and the dropdown shows only the
  fields of the mode you chose. In detect mode the server clock is floored at
  30 seconds so the token cap, not the clock, is the bound.
- **The Sample Vault is the default home for voices.** The Higgs installer
  creates PandorumLLM\Sample Vault and writes it into the setting; blank now
  means that folder (a patch11 vault beside the logs keeps working until the
  setting says otherwise). Local Voice Clips are now an alternate SOURCE: a
  clip named after the voicetype is used instead of SkyrimNet's upload, still
  repaired into the vault - and when you edit that clip, the vault follows the
  moment its bytes change. SkyrimNet's per-session uploads never churn a vault
  entry once built. Each entry remembers the source bytes that made it.
- **Cached Voices defaults to 1024** - every speaker you meet stays encoded.

## v3.75 patch12
- **The server card reads as one design.** Every group boundary is now the same
  height with its divider line dead centre in the gap - whatever kind of row a
  group happens to end on. The Speculative Decoding section is built from the
  same anatomy as its neighbours: the same uppercase heading over the same
  divider, cells as tight as the generation cells above them, and every control
  naming the llama.cpp flag it writes in the same blue reference style as the
  rest of the card.
- **The built-in head is a chip, said once, in one voice.** When the model
  drafts for itself, a yellow "Built-in MTP head" chip sits beside the
  Speculative Decoding heading - and the note under the model dropdown that
  announced the head is the same chip in the same words, replacing the coloured
  prose line. The right-aligned type caption is gone: the drafter picker
  already names what drafts.

## v3.75 patch11
- **The repaired sample vault.** The first time a character speaks, their voice
  clip is read, rewritten with a header that says what the file actually holds,
  trimmed to an example rather than a performance, and kept in the panel's own
  folder under the voicetype's name. Every line after that speaks from the
  repaired copy. Clips whose header declares an impossible length - the fault
  that made a large part of a voice folder unplayable - are read for the audio
  they hold rather than the length they claim, so they simply work from then on.
  The originals are never touched, and a copy is written whole or not at all.
  Two rows in Audio Files set where the vault lives and how long a kept sample
  may run; the folder defaults to a place beside the panel's own files, so a
  blank setting is still a working one, and the behaviour can be turned off.
  Only the first repair is announced - after that the vault is simply where that
  voice lives, and the identity ledger records the copy's hash, which is what
  was actually sent to the engine.
- **The provider title glows again instead of blurring.** Hovering one in the
  proxy terminal set the text and its halo to the same colour, which leaves a
  glyph with no edge - the enclosed shapes in letters fill in and the whole
  title reads as smeared. The provider's colour now belongs to the halo and the
  text stays light, as every other glow on the page already did.

## v3.75 patch10
- **Reference Transcripts, a settings field of its own** (TTS page, above Audio
  Tags). A voice sample alone tells the engine how a character sounds; paired
  with what that sample says, it also tells it which sounds are the words -
  which is how cloning models are meant to be prompted, and it is worth most on
  short lines. Three modes: **Off** sends none; **Stored only** uses transcripts
  already known and loads no model at all, so it costs no VRAM; **On** co-hosts
  SenseVoice and learns the missing ones. With On, four controls that map to
  what audio.cpp's sense_asr family documents: the model file, recognition
  language, whether the engine emits its meta tags, and whether numbers come
  back as spoken words or digits. Chunking is deliberately absent - a voicetype
  sample is seconds long and takes one pass, which also means no VAD model is
  needed. **Clear transcripts** forgets the learned set, disk copy included.
- **Nothing waits for a transcript.** The speak path only reads what is already
  known; an unknown sample is learned in the background, so the line that first
  meets a voice goes out immediately and every line after it carries the
  transcript. A second model's inference never spends SkyrimNet's budget.
- **The synthesis timer measures synthesis.** The transcript lookup now sits
  above the timing wall rather than inside it, so a first line for a new voice
  is no longer reported as slower than it was.
- **The transcript store is meant to be read.** Each entry carries the
  voicetype beside its text in tts-ref-text.json, so a line can be corrected by
  hand - which beats any recogniser on Tamrielic names. A hand-written entry is
  authority and is never overwritten. The engine's `<|...|>` meta markers are
  stripped before anything is stored, whatever the engine was asked to emit.
- **A build that has never heard of SenseVoice still starts.** The start ladder
  gained a second rung: if the server exits with the ASR entry present, it is
  dropped and the server comes up without it, with a line in the terminal.

## v3.75 patch9
- **Speculative Decoding settings on the server card.** When a drafter is
  selected - a file or the model's own built-in MTP head - the card grows a
  segment with the llama.cpp speculative surface: draft tokens per step (max
  and min), the greedy acceptance threshold p-min, the split probability, and
  backend draft sampling as a three-way switch (server default / on / off,
  written as the bare `--spec-draft-backend-sampling` or its `--no-` form).
  File drafters additionally expose their own KV cache types (K and V); the
  built-in head rides the target model, so it carries no placement and no
  cache types of its own. DFlash and DSpark drafters keep the draft depth
  their header declares - a user value never breaks the block contract. Every
  value round-trips: a hand-edited launcher reads back into the same fields.
- **Qwen 3.8 support.** The Qwen 3.5/3.8 generation is its own reasoning
  category: thinking is a switch AND a depth at once. The Reasoning dial
  stays live, and beside it a "Reasoning effort" select (low / medium /
  xhigh, model default xhigh) writes `reasoning_effort` into the chat
  template kwargs - with Off outranking effort, because a depth for thinking
  that is not happening is noise. The multi-step MTP head Qwen 3.8 ships is
  found by the same nextn tensor scan the qwen35 generation shares, so
  selecting the built-in drafter simply works, and the new depth fields
  matter there: the head is trained for more than one step.

## v3.75 patch8
- **Ready for audio.cpp 0.6.** The 0.6 release dropped the Higgs
  reference-cache option, and the server exits outright on an option it does
  not know - so a start that dies at once now retries ONCE without session
  options and remembers the refusal for the rest of the panel run. Upgrading
  the engine costs three seconds on the first start, not a working server.
  Nothing changes on the builds that still accept the option.
- **Reference transcripts, learned once.** Point "ASR model for reference
  transcripts" (TTS page) at a SenseVoice-Small gguf and the panel co-hosts
  it beside the TTS model. Each voice sample is transcribed once - keyed on
  the file's hash, persisted across restarts in tts-ref-text.json - and every
  cloning request carries the transcript from then on: Higgs locks identity
  better when told what the reference says. No model set, or a transcription
  that fails, and lines go out exactly as before; nothing ever waits on it.
- **The Audio Cache.** Two buttons at the bottom of the Audio Files settings,
  glowing white under the cursor. "Audio Cache" opens a list of every
  character the panel has met - this run and earlier ones, because the
  pairings persist on disk and reload at start, with live learning always
  outranking yesterday's record - alphabetical, scrollable, with the
  voicetype, the sample file that speaks them, its presence on disk, and how
  many takes sit in the output folder. Click a name for their takes: every
  kept line with its creation time and size, newest first, with a Back button
  to the list. A take counts only when what follows the name is exactly a
  timestamp, so Urag's page never shows Urag gro-Shub's files. "Clear Audio
  Cache" forgets the learned pairings, on disk too, behind a confirm - the
  kept audio files are never touched.

## v3.75 patch7
- **The engine's conditioning is mirrored on every synthesis path.** The TTS
  engine keeps one session, and what it last spoke as is now tracked through
  one function that every path reports to - a voiced thought conditions the
  session exactly like a spoken line, and the warm-up's change detector sees
  both. Each identity-ledger block gains an "engine was:" line naming what the
  session had been conditioned on before that take, written only when it
  differs; a cold start shows nothing, by design. This is the line that settles
  a wrong-voice case in one read: a first-of-session take in the wrong voice
  with the correct bytes on record is the engine's own misrender, and a
  first-chunk fault right after another speaker is carryover.

## v3.75 patch6
- **What reaches the TTS engine is verified first.** Every reference passes a
  sample gate before synthesis. A file missing from disk is recovered from the
  panel's own copy of that voicetype, or the line is refused loudly - a dead
  path posted anyway leaves the engine cloning whoever it conditioned on last,
  behind a log that looks perfect. A path carrying ANOTHER voicetype's bytes -
  proven by hash, the wrong voice by arithmetic rather than by ear - speaks
  through the panel's copy or is refused the same way. Bytes that are merely
  new under a known voicetype are accepted with one alarm: a re-record is
  legitimate, and the ledger's hash says which it was. The gate's verdict is
  written into the identity ledger whenever it is anything but clean.
- **A voice warm-up probe, off by default.** With "Voice warm-up on speaker
  change" on (TTS page, beside the character-name field), a short discarded
  take on the new voice precedes the real one, absorbing the engine's
  session carryover from the previous speaker. It costs a second or two per
  speaker change and doubles as a measurement: if a first chunk in the wrong
  voice stops happening with it on, the carryover is proven on this hardware.

## v3.75 patch5
- **A spoken line is named by its own words first.** Every reply the proxy
  serves is remembered, four deep per character for two minutes, and a TTS
  chunk is matched into exactly one of them - a chunk held back by a deep TTS
  queue is late, not somebody else's. Timing rules run only where the words
  decide nothing.
- **The pairing queue hears Dialogue requests alone.** Every route used to
  push its character's name into the queue a TTS call consumes - GM, Combat,
  Charbio, a Meta pick - and no spoken line ever follows those, so the NEXT
  line took whatever was waiting. A non-Dialogue request still registers its
  character and its listener; it just makes no promise.
- **One utterance travels together.** Chunks of one line arrive back-to-back
  on one voicetype; once any chunk is named by its words, its short siblings
  inherit the same name instead of guessing. A live dialogue request ends the
  run - a shared voicetype takes the character who just spoke.
- **A unique voicetype is its own proof.** femaleuniquemirabelleervine IS
  Mirabelle Ervine: once that character has opened any prompt, the binding is
  permanent - no window, no queue, no ambiguity.
- **The Meta selector breaks ties.** Its [speaker]>[listener] pick, read
  loosely because the format is an LLM's promise, chooses among multiple
  waiting requests. It never names a line by itself.
- **A generic voicetype with no live evidence answers as itself.** The cache
  stopped answering: femaledarkelf handing one character's name to the next
  dark elf who spoke five seconds later is what it bought. The last-known name
  stays visible to the ledger and the one-voice guards.
- **The player is the one everyone talks to.** A name that appears as the
  listener under two different speakers and has never once spoken is the
  player - learned automatically, with the typed field still ranking first.
- **The wire is on record.** Every distinct generate_audio request shape is
  written to the identity ledger - top-level body keys and header names, no
  values - so "what else does SkyrimNet send" is answered from evidence.

## v3.75 patch4
- **Your character's name is a setting.** A field under the Player Tag Injector
  labels your own spoken lines and tells the tagger who "I" is. Typed, it is
  simply true and outranks anything read from a prompt; left empty, the panel
  reads it from SkyrimNet's party heading as before.
- **The player's name can no longer be learned wrong.** The rule that read a
  standalone "Think internally as <n>" request as the player's is gone:
  SkyrimNet sends NPC think tasks in exactly that shape, and one session's log
  shows the moment it named an NPC as the player and every player line wore her
  name from then on. One gate now takes the name - party heading only - it
  records where the name came from, and it refuses a name that already speaks
  through a voicetype, because a known character is not the player.
- **One character, one voice, on every rule.** Naming a voice from the words of
  its line (v3.74 patch183) gained the same guard the request queue has had: a
  name bound to one sample cannot be moved onto a second. And a line under 24
  characters names nobody - "Morning." matched the one kept reply that happened
  to contain it and put that character's name on a passing stranger's greeting.
- **The TTS identity ledger.** Every spoken line writes one block to
  `tts-identity.log`: the name, WHICH rule decided it, the voicetype, the
  sample path asked for and the one sent, the sample's own size and hash, what
  the other rules were holding, and the full line. A reference missing from
  disk is called missing instead of printed as a healthy filename - the engine
  keeps its previous session in that case and the line comes back in whoever
  spoke last, which no filename log could show. One character arriving on a
  second sample is alarmed in the TTS terminal the moment it happens.

## v3.75 patch3
- **Built-in MTP head is a picker choice.** A model that carries its own
  multi-token-prediction layers can be its own drafter: the Speculative
  decoding picker offers "Built-in MTP head", and the launcher receives
  `--spec-type draft-mtp` and nothing else - no draft file, no placement, no
  depth. A hand-written launcher already saying exactly that reads back onto
  the card as this choice, so the card's next write keeps it. Choosing it for
  a model without the head is called out in red under the picker.
- **A dialogue reply that opens with its thought is served dialogue-first.**
  SkyrimNet reads a reply front to back, and a leading `<internal_thought>`
  block left it nothing to speak. The proxy now serves the first dialogue
  segment first and places the thought immediately behind it - on streamed
  and unstreamed Dialogue replies alike, with the streamed rewrite proven
  byte-identical to the plain rule at every chunk size. Thought-only replies
  and thoughts arriving mid-reply keep the model's order, and the Proxy
  terminal and response payload show the reply as it was actually served.
- **Thoughts are shown and voiced whole.** The terminal row and the
  thought-audio pass carry the full thought text.
- **A per-launch VRAM report above each server card terminal.** Weights,
  drafter, projector, KV, RS, compute and MTP-context estimate, with GPU free
  at load, parsed from llama.cpp's own lines in the slot console log. A
  launch that exited before serving is called out in red rather than reported
  as loaded - the report does not trust the launcher's own STATUS line.
- **The port warning tells its two causes apart.** A held port that answers
  no HTTP names both possibilities - this server stuck or dying mid-load, or
  another process owning the port - and a parsed exit says which.

## v3.75 patch2
- **A speculative drafter is typed by what its tensors prove, not by the
  architecture it declares.** llama.cpp runs one implementation per `--spec-type`
  and identifies an MTP drafter by a single tensor -
  `blk.{block_count-1}.nextn.eh_proj.weight` - because heads of the qwen35
  generation (Qwen 3.5 / Qwen 3.8) declare the *family* architecture. The panel
  reads the same tensor the same way, so a qwen35 MTP head leaves the launcher as
  `draft-mtp`, a DFlash file with a Markov head as `draft-dspark`, and a whole
  small model of the same family as `draft-simple`. Every tensor name is read:
  the deciding one sits at the very end of the list.
- **A model that carries its own MTP head is labelled on its card.** The same
  tensor, inside a full model, means the model drafts for itself with no
  separate file (`--spec-type draft-mtp` alone); the card says
  `Built-in MTP head detected` under the model, with the detail on hover.
- **The Qwen 3.5/3.8 family is named** on the card rather than read as a
  generic Qwen 3 prefix, and the Sampler Guide's Spec type entry states all
  five draft types and where each comes from.
- **The launcher check flags an integer flag handed a fraction.** `--top-k` is
  a count; a value like `0.95` reads as `0` and turns the sampler off in
  silence - the check names the likely intended flag.

---

## v3.75 patch1
- **A version is placed by what KIND of build it is, not just its number.**
  Within one release the order is now the order such builds are made: the release
  itself, then any hotfix answering something it shipped with, then the patches
  that carry it forward. A hotfix and a patch of the same number are no longer
  read as the same build - comparing the tags as text had called them equal, so
  a patch could look like a build already installed. The header shows which kind
  a build is, `v3.75-p1 Beta` or `v3.75-h1 Beta`, and both short forms are read
  back the same way the full tags are.

---

## v3.75 hotfix1
- **Speculative decoding was loading a drafter and drafting nothing.** Current
  llama.cpp runs no speculation at all unless it is told which KIND to run:
  `--spec-type` defaults to none, and the only thing that fills it in
  automatically is a HuggingFace sidecar download - a draft model on disk infers
  nothing. A drafter named with `--model-draft` alone therefore loaded, held its
  VRAM and produced not one draft token, saying only `no implementations
  specified for speculative decoding` deep in the server log. The `ctx_other`
  line above it, which looks like the failure, is the memory-fitting pass and is
  harmless.
- **Every drafter now leaves with its type**, derived from the architecture the
  drafter itself declares: a Gemma 4 assistant head gets `draft-mtp`, a DFlash
  assistant `draft-dflash` with its own block size as the depth, an EAGLE-3 head
  `draft-eagle3`, and a whole small model of the same family `draft-simple`. The
  same full flag set goes to a generated launcher and a hand-written one alike,
  and a launcher that still names a drafter the old way is corrected in place -
  the type arrives, the dead flag goes, and everything written around it stays.
- **A head shipped beside a family is recognised as a drafter.** Gemma 4's MTP
  head declares `gemma4-assistant` and names its tensors like any other model,
  so nothing but that architecture could tell it apart from a small chat model;
  it now reads as a draft model, and the card names it for what it is rather
  than for the family it drafts for.
- **The line that looks like the failure is not one, and is no longer reported
  as one.** `Gemma4Assistant requires ctx_other to be set` comes from llama.cpp's
  memory fitting, which builds a throwaway probe context for the drafter before
  the target model exists; a head that must attach to the target - a Gemma 4
  assistant, a DFlash or EAGLE-3 head - can only throw there. llama.cpp catches
  it, says so in the message itself, and loads the drafter properly a moment
  later; the only thing skipped is the drafter's VRAM estimate. The panel raised
  it as an error, which sent the owner hunting a missing parameter that does not
  exist. Neither it nor the `[spec] failed to measure draft model memory` line
  that follows reaches the error log or the issue list now; the panel says once
  per session what they mean, and both stay in the server's own log where the
  load sequence can be read in context. Keeping them out of the error FILE alone
  was not enough - the issue list judges a line by its own words, and "failed" is
  in this one. A real load failure, a real out-of-memory and a real speculative
  context failure are all still errors, in both places.
- **A voice read a tag aloud, and cannot again.** Brelyna spoke
  "[prosody-expressive_low." because three things lined up: SkyrimNet's prompt
  asks the model for LOWERCASE tags while the panel only ever recognised the
  mod's own ALL-CAPS ones; the model wrote a full stop straight after a tag, so
  the sentence split fell through it; and what arrived had lost its closing
  bracket somewhere upstream. The panel is the last thing between the text and a
  voice, so it now reads a tag in any casing, survives a damaged one, and
  deletes anything merely tag-SHAPED - an unknown value, a bracketless
  fragment - rather than letting it be spoken. Text in brackets that is simply
  dialogue is untouched, as before.
- **A tag whose chunk carried no words waits for the words.** Such a chunk is no
  longer synthesized at all; its tags are held and colour the next chunk of that
  character's reply, which is where the model meant them. The field case now
  plays as one line: "Most of us here did..." delivered with the low
  expressiveness the model asked for, and nothing spoken in between.

---

## v3.75

Everything from the v3.74 patches, gathered into a release. The line that matters
most: local models moved, and the panel now reads what a model IS rather than what
it is called.

**New model families, read from the file itself**
- **Meta Muse Glimmer 30B** is supported end to end: the model, its DFlash
  speculative drafter and its perception encoder are each recognised, and the
  drafter is launched with the flags llama.cpp actually needs for it.
- Every server card now shows the **model architecture** it read out of the GGUF
  header - Gemma through Gemma 4, the Qwen 2 and 3 families, Llama with Mistral and
  NeMo, DeepSeek, GLM, Command-R, Phi, Granite, Nemotron and many more. A rename or
  a repack cannot fool it, and a family the panel has not been taught is reported
  under its own name rather than guessed at.
- Models whose thinking cannot be switched off are offered **reasoning strength**
  instead of a switch that would do nothing.

**Voiced NPC thoughts**
- An NPC's inner monologue can be spoken aloud, before or after the line, and now
  arrives whole rather than stopping at the first sentence. Click any spoken line
  in the terminal to hear it again, from any PC on the network.

**Emotion reaches the voice**
- The feelings the model writes into a reply are forwarded to Higgs as real control
  tokens, in reading order across the spoken chunks, so a reply that turns from
  cheerful to nervous is delivered that way.
- The Tag Limits board governs how often a character may use one, counted per reply
  rather than per chunk.

**Servers and launchers**
- A server card and its .ps1 launcher are now two views of one thing: every setting
  written into the file, every setting read back out of it.
- Two new provider pairs ship: **NarrativeEngine** (NE-Composer, NE-Director) and
  **AgencyEngine** (AE-Impulse, AE-Resolve). They appear in existing setups on the
  next start.
- TTS calibration is arithmetic now - no model call, no idle wait - and a failed
  voice line retries with more room and calmer sampling instead of repeating itself.

The per-patch account of all 190 patches behind this release follows below.

---

## v3.74 patch190
- **Emotion Chunk Placement is gone, and the model decides instead.** The
  setting chose between one assertion per reply and one assertion repeated
  through it - both of which threw away everything the model wrote after the
  first tag. A reply's feelings now reach the voice as the model wrote them:
  each spoken chunk takes the NEXT tag in reading order, so a reply that turns
  from cheerful to nervous to a whisper is delivered that way. When the model
  wrote fewer tags than the reply has chunks the last one holds, so a delivery
  never falls back to neutral half way through, and a reply with one feeling
  still carries it from start to finish.
- Unchanged, deliberately: sound tags are still never injected (SkyrimNet
  performs [chuckle] itself, and doubling it doubled the laugh), a line that
  already carries its own control token is left alone, emotions measured to
  break the voice are still refused, and the Tag Limits board still governs how
  often a character may use one.

---

## v3.74 patch189
- **The shipped default config had fallen four providers behind.** It still
  ended at SeverActions (1263), missing both plugin pairs - NE-Composer and
  NE-Director from patch150, AE-Impulse and AE-Resolve from patch180. Nothing
  was broken by it, because the seeder adds whatever a config lacks on load,
  but a file that contradicts the code is the shape every drift in this project
  has taken. It now states the same seventeen providers the seed table does,
  each with its mark, and the gate compares the two on every run so they cannot
  part again.

---

## v3.74 patch188
- **Model architecture, under the model picker.** Every GGUF declares the family
  llama.cpp will load it as, so the card now says which one it read: "Model
  architecture: Muse Glimmer (Meta) - 52 layers - 128k trained context". It comes
  from the header when the file is listed, never from its name, so a repack, a
  merge or a rename cannot move a model between families. Named so far: Muse
  Glimmer, Gemma through Gemma 4, the Qwen 2 and Qwen 3 families including their
  MoE and VL variants, Llama (with Mistral, NeMo and Yi, which share its
  architecture), Llama 4, Mistral 3, Pixtral, DeepSeek, GLM-4, Command-R and
  Cohere 2, Phi, OLMo, Granite, Nemotron, EXAONE, InternLM, MiniCPM, StableLM,
  Falcon, gpt-oss, Ling, Hunyuan, ERNIE, Jamba, Mamba, RWKV and more. An
  architecture the panel has not been taught is reported under its own name -
  an unseen Qwen falls back to its family, and nothing is ever guessed.
- **Reasoning adapts to the family.** Meta is explicit that Muse Glimmer's
  template opens the thinking channel unconditionally: `--reasoning on`, `off`
  and `reasoning_effort: none` all do nothing, and what a person actually
  controls is HOW MUCH, through the `reasoning_strength` template kwarg. When a
  model of that family is selected the card offers **Reasoning strength** - model
  default, low, medium, high, xhigh - writes it as
  `--chat-template-kwargs '{"reasoning_strength":"..."}'`, reads it back, and
  greys the on/off switch with the reason on hover rather than letting it lie.
  Families that CAN be switched off are untouched and still get the
  `enable_thinking` form. `--reasoning-budget` remains the hard cap for both.
- Both launcher writers now single-quote a JSON value, as the in-place editor
  always did, so a kwarg reads the same however it was written - and is read back
  the same way too.

---

## v3.74 patch187
- **A card change is an instruction, not a preference.** A setting was written
  into a hand-edited launcher only when the flag was already in the array or the
  value differed from the panel's shipped default - a rule meant to stop
  untouched defaults burying someone's tuning, which also meant that CHOOSING a
  default did nothing at all. Turning Reasoning back on wrote nothing, "on" being
  the default too, so the card said one thing and the file that ran said another.
  The setting the person just changed is now always written, whatever its value;
  settings they never touched are still left out, as before.
- **The launcher is the root; the cards are a view of it.** After the text is
  edited, the parameters are read back OUT of it - both for a launcher held in
  the Server Editor and one on disk - so the two can never describe different
  servers. Everything a person wrote around the flags stays untouched: only the
  `$llamaArgs` array is edited, and only the flags in question.
- The gate drives this through the endpoint the card actually posts to: Reasoning
  on writes `--reasoning on` into a hand-written launcher and the card reads back
  on; off writes both ways of saying it and the card reads back off; a dial set
  to its own default lands because it was touched; and the VRAM report, the
  `--jinja` line and the rest of the file are exactly as they were.

---

## v3.74 patch186
- **A card setting the launcher never heard.** A hand-edited launcher is edited
  in place, flag by flag, so that the parts a person wrote - VRAM reports, stamp
  parsing, sampler tables - survive a card change. The map of which flags a card
  owns held the model, the seventeen server parameters and the thinking switch,
  but NOT the two optional model pickers. Setting Speculative decoding or Vision
  to Disabled updated the card and left the file that actually ran loading the
  drafter or the projector: the card described something other than what started.
- **Both pickers now reach it.** A path names the flag, Disabled removes it, and
  swapping a DFlash assistant for a conventional drafter takes the speculative
  flags out with it (and the reverse). Everything a person wrote around the block
  - comments, sampler lines, the diagnostic pipeline - is untouched, as always:
  only the `$llamaArgs` array is edited, and only the flags in question. When a
  speculative drafter is on and the card has no GPU-layer opinion of its own, the
  launcher's own `--spec-draft-ngl` line is left exactly as written.
- **Proven across the whole card, not just the drafter.** The gate now sets every
  setting a server card owns to a NON-default value, writes them into a bare
  hand-edited launcher, and reads them back: model, vision, drafter, context, GPU
  layers, flash attention, both cache types, parallel, batch, ubatch, threads,
  n-predict, mmap, continuous batching, fit, reasoning budget, reasoning format,
  reasoning and context checkpoints. Any future setting that reaches only one
  side of that trip fails the run.

---

## v3.74 patch185
- **Muse Glimmer is recognised: the model, the drafter and the vision tower.**
  Meta's Muse Glimmer 30B ships its speculative drafter as a SEPARATE
  architecture - `dflash`, with ordinary tensor names and `block_size 16` - so
  the tensor scan that finds Gemma's MTP and EAGLE heads by name could never
  have found it, and the panel called the assistant a plain model. A file that
  names a drafting architecture in its own header is now taken at its word,
  which is the stronger fact: it is what llama.cpp reads too. `dflash`, `mtp`,
  `nextn`, `eagle` and `medusa` all count, by architecture or by an
  architecture-prefixed key.
- **A model that carries its own vision tower is still the model.** Muse
  Glimmer is image-text-to-text in one file; the header says how many text
  blocks it has, and a projector has none. The vision verdict is now only
  reached for files that are nothing else, so a one-file multimodal model can
  never be mistaken for an mmproj as more of them ship this way.
- **The speculative flags are injected, not `--model-draft`.** A DFlash
  assistant does not load as a small model of the same family: picking one now
  emits `--spec-draft-model`, `--spec-type draft-dflash`, `--spec-draft-n-max`
  taken from the drafter's own block size, and `--spec-draft-ngl` mirroring the
  server's own GPU-layer setting - the panel does not put the drafter on a card
  the user kept it off. A conventional drafter keeps `--model-draft` exactly as
  before. Both the generated launcher and a hand-written template are covered:
  a template that already speaks the speculative dialect is never handed a
  second drafter, and turning the drafter off strips every one of its flags.
- **The remembered verdicts are dropped.** Model kinds are cached by
  path+size+mtime, so an assistant already remembered as a plain model would
  have stayed one. The cache now records which rules produced it and is
  discarded when they change.

---

## v3.74 patch184
A sweep before the public update. No behaviour was added; dead weight was removed,
three live defects were fixed, and the gate learned to catch this class by itself.

- **Removed, not orphaned.** `next_id` in the provider repair path (creation moved
  out at patch151), the MOSS `_post_chunk` poster and its `TTS_MAX_NEW_TOKENS`
  ceiling, the JS `ttsSrvRunning` helper (PTI and PME are panel-called now), the
  retired LLM-Controlled mode's two prompts (`CAL_SYSTEM`,
  `TTS_AUTOCAL_DERIVE_SYSTEM` - `autocal_mode` has folded `llm` into `proxy` since
  patch88), and five constants nothing read: `TTS_FRAME_RATE`, `TTS_CHUNK_GAP_MS`,
  `TTS_MAX_WORKERS`, `GH_RELEASES`, `GH_API`. `SAMPLER_DEFAULTS` went with them -
  it was a second copy of the page's own default table.
- **The retry ceiling has a name.** `TTS_CAP_CEILING` replaces the bare 4096 the
  patch181 escalation stopped at, and it is the number the gate measures against.
- **Three live defects.** The fit tooltip promised "kept from N lines, at TIME"
  and read two settings nothing had ever written - every fit said "kept from ?
  lines"; both are now written where the fit is stored. The PTI/PME log family had
  a name (`PTIPME_LOG_GLOB`) that nothing used while the pruner repeated its
  literal. And the proxy has counted open requests per upstream on every forward
  since patch98 with no reader at all - that count now appears in the debug report,
  where a slow-fleet question starts.
- **The gate no longer takes a name for a pulse.** Four checks asserted that a
  constant, a prompt or a function EXISTED, each having lost its last caller
  patches earlier - true of a corpse, and one of them ("the list says which are not
  running") contradicted the check two lines above it. All four now pin the call.
  Three standing scans were added so this cannot recur: no JS function, no panel
  function or method, and no panel constant may be defined and never named. Each
  fails when its corpse is put back. The encoding rule also now covers every
  README.txt in the tree, not just the one at the root - `ps1-launchers/README.txt`
  had been LF since it was written.
- DEVELOPMENT.md carried two principles numbered 116; the stray is now 128, and
  the sweep's own lesson is 129.

---

## v3.74 patch183
- **A shared voice sample no longer swaps two characters' names.** The report
  was precise: Faralda and Saadia use the same sample, and when Faralda spoke
  her thought said Faralda and her action said Faralda - both carry the name
  the prompt gave - but the spoken line said Saadia. The reason: a voicetype
  learns ONE name, and when two characters share a sample the only thing
  separating them was the order their dialogue requests arrived, so an
  interleaved pair handed the spoken line the other one's name.
- **The line is now named by its own words.** Every reply is already kept
  under the name the prompt itself gave; the line about to be spoken is a
  piece of exactly one of them. That match names the voice and holds it for
  the rest of that line's chunks, outranking both the pending-name queue and
  the learned cache. A line that matches nothing, and a line both characters
  could have said, leave the older rules alone - a wrong name is worse than a
  voicetype - and the player's own voice is never named this way.
- Every reply's spoken text is now kept whether or not it carried a thought
  (one write, above the thought guard), so a thoughtless line can name its
  speaker too. The gate replays the field case end to end: the queue alone
  gives Faralda's line Saadia's name, the words give it back.

---

## v3.74 patch182
- **Max tokens: the card and the launcher are the final word.** SkyrimNet's
  request value no longer survives the proxy when the server has its own: a
  provider's n_predict override, else the launcher's --n-predict (or -n),
  overwrites the request's max_tokens on the way through - whatever the
  sampler-source setting says, because a server was configured for a reason
  and a request cannot un-configure it. The gate sends a 4096-token request
  through a card that says 800 and reads 800 out the other side.
- **The thought defer no longer waits on ghosts.** The field showed the real
  shape twice in one session: SkyrimNet ABANDONS a queued chunk (its estimate
  logs, its delivery never comes - 16:49 Luz, 16:57 Irileth), and the defer
  waited its full five-step ladder on a chunk that was never coming, firing
  15-17 s late; that is the "sometimes it never comes" experience. An
  unfinished reply now earns a defer only while chunks are ACTUALLY still
  arriving - quiet for 3.5 s stands the defer down and the chain fires on
  what really played - and the ladder is three steps, not five. The 16:49
  ghost replays at under six seconds with at most one defer; a genuinely
  slow final chunk still re-anchors and fires exactly as before.

---

## v3.74 patch181
- **A retry now differs from the attempt it retries.** The owner's 12:12 log
  showed the point exactly: three requests in a row with the identical token
  cap and byte-identical "steadier" samplers - a repeat, not a retry. The cap
  now grows half again per attempt (198 -> 297 -> 445, bounded at 4096) and
  the 🎯 line says so (`↺ retry cap → N`); the sampler ladder deepens per
  step - temperature ×0.8 per attempt, nucleus tighter by 0.05, min_p floor
  firmer by 0.03, repetition penalty off - always toward the stop token. The
  gate proves attempts two and three carry different, strictly cooler
  samplers, and flattening either ladder fails it.
- **The new provider marks are real everywhere.** 💥 and ⚖️ (and the NE pair's
  🎼 🎬) joined the slot card's emoji picker; a seeded default now CARRIES its
  shipped mark from birth; and an emoji-less factory provider - the AE pair
  created before this patch - heals to its mark on the next start, while a
  custom provider's empty choice is never touched.

---

## v3.74 patch180
- **The AgencyEngine pair: AE-Impulse and AE-Resolve.** Two real SN-based
  providers for the AgencyEngine SkyrimNet plugin (followers who START things):
  AE-Impulse serves the impulse decision - whether a companion raises
  something unprompted - and AE-Resolve the resolution judgement - whether a
  raised thing was answered or done. Seeded on the next two ports, 1266 and
  1267, plain non-thinking, utility priority, and deliberately riding the
  rails patch151 laid after the NarrativeEngine rollout stumbled:
  create_missing_default_providers runs inside load_config, so an EXISTING
  config receives both unallocated on the very next start - no button press -
  and the yaml generator already refuses panel-owned and port-0 entries, so
  once placed on a server they enter providers.yaml cleanly as the next two
  entries. The Providers page keeps them after every existing provider and
  before PTI/PME by construction (port order, panel-owned last).
- Both wear **rust (#b7410e)** in the one colour map the Providers page and
  the proxy terminal share, with the burst for Impulse and the scales for
  Resolve in both emoji maps. The gate runs the LOAD-path arrival on an
  existing config - the exact patch150 failure shape, now impossible to
  reintroduce silently - and dropping the seed pair or the rust each fails
  its own check.

---

## v3.74 patch179
- **A tag limit counts LLM responses - the round - not TTS chunks.** The
  owner's field log showed [Laughter (+2)] on one chunk and the countdown
  moving on the NEXT CHUNK of the same reply. The character's turn now
  advances once per reply: the first chunk of a fresh reply ticks it, later
  chunks of the same reply check without ticking, and a line with no fresh
  reply behind it (the player, or a race lost) still counts as its own turn.
  Reply membership is decided by one rule everywhere - a sliding window of
  the chunk found inside the reply text, immune to SkyrimNet's injected
  prefixes even on tiny chunks - shared by the turn counter, the thought
  chain filter and the defer.
- **Proven, not makeup.** The gate now walks the whole round: laughter spoken
  in reply 1, the WIRE strips the tag through the rest of that reply and the
  next two responses while the report counts 3-2-1, and reply 4 speaks it
  again. Forcing every chunk to be a new turn fails the run.
- **A multi-sentence thought arrives whole.** The owner's field wav held
  sentence 1 of 2 - 5.6 s of a 7.5 s thought - because audio.cpp ends a clip
  at a sentence's EOC on its own schedule. A thought is now synthesized one
  sentence per request (up to four) and the answers joined into one wav;
  cache key, echo, report and replay are unchanged. Removing the join fails
  the gate's stubbed two-sentence run.

---

## v3.74 patch178
- **The tag limit system is checkable at a glance.** Every TTS generation now
  reports, in its own block and only when there is something to say:
  `Banned Tags: [Determination], [Elation]` - the Allowed Tags board's
  clicked-off set - and `Tag Limits: [Laughter (2)]` - this character's live
  countdowns, where (2) means this turn and the next are still prohibited and
  (+2) means the limit was recorded on this very line. The countdown is
  computed from the same TAG_TURNS record the gate enforces with, so the row
  and the wire cannot disagree.
- **A limited tag can no longer pretend it fired.** The mood armer now skips
  (and consumes) a pair that is cooling, so neither the face nor the terminal
  shows an emotion the final gate was always going to strip - the exact
  "did the limit even work?" doubt this patch exists to end. Gate run walks
  the whole lifecycle: fresh (+2) on its own line, then (2), then (1), then
  free, and a cooling emotion refused outright.

---

## v3.74 patch177
- **RECONSTRUCTED ENTRY - the original record for this patch was lost to a
  context fault on my side; the code and its gate checks are the source.**
  Emotion Tag Ban: the Final-Off board's banned tags now govern the NPC mood
  armer too - a banned emotion is consumed from the completion's queue but
  never armed, and the wire gate receives the union of the board and this
  character's live cooldowns, so a ban holds everywhere a tag could travel.
  Tag Limit report: every spoken line's report block in the TTS terminal now
  states its gating in the open - `Banned Tags: [word], [word]` for the board,
  and `Tag Limits: [word (n)]` for turns remaining on cooling tags, with
  `[word (+N)]` marking a limit freshly started by this very line - so
  whether a limit fired is never a doubt again. Both painted as keyword rows
  by the terminal, both pinned and live-run in the gate.

---

## v3.74 patch176
- **The drilldown inversion, closed at the exact link the owner named.** The
  ActionEval drilldown is a SEPARATE LLM call that SkyrimNet posts only after
  stage 1's response returns - and leave() freed the card into precisely that
  gap: a queued normal (IntelEngine) took the GPU, and the high-priority
  stage 2 arrived to a busy card that nothing can preempt. The card now
  LINGERS held for HIGH_LINGER_S (2.5 s) after a high call leaves: the
  follow-up high lands inside the window and chains the hold; a window with
  no arrival releases the waiting normals; a card with no high traffic never
  lingers at all. The gate replays the field sequence move for move - normal
  queued during stage 1, held through the gap, drilldown owns the card, only
  the empty window releases - and zeroing the linger fails it.

---

## v3.74 patch175
- **Priority is per card, and now it holds.** The gate was already keyed by
  GPU - rt["gpu"] comes from the slot each provider lives under, so two cards
  never wait on each other - and the ActionEval drilldown arrives on
  ActionEval's own listener: same route, same priority 0, by construction.
  What the owner's field log exposed was patience: the 8 s wait cap was
  SHORTER than a real high call (ActionEval runs 16-17 s), so a normal
  provider like IntelEngine stopped waiting and barged onto the card
  mid-high - which is exactly the contention that stretched the drilldown to
  17 s. The cap is 30 s now: a normal yields to an active high for as long as
  the high realistically runs. A normal already mid-flight can never be
  preempted - llama offers no such thing - so refusing to start one against a
  high is the whole of what a gate can honestly do, and now it does all of it.
  Gate run: a normal waits behind an active high on its own card, another
  card is untouched, and the leave releases it at once.

---

## v3.74 patch174
- **The TTS terminal reads like the rest of the panel now.** Report groups
  stand apart - receipt (header, estimate, thought-delay) and the synthesis
  report each open on their own blank row, thought blocks were already
  blank-fenced - and the thought lines are written WHOLE: the (thought) header
  carries the full text, and the Thought voiced note is written in the
  proxy's own shape (plain waves, never the SAID pair, so the splicer still
  leaves it be).
- **Report rows wear the panel's own inks:** thinking's cyan for time and
  units, its gold for every number, the payload viewer's grape for the
  thought-delay row, magenta for wav and voice names, bold keyword heads -
  the same families as the Proxy terminal, the Thinking Content terminal and
  the prompt view. Two gate rules earned their keep on the way in: the
  backslash-in-RegExp-string rule and the []]-class rule both caught the
  first draft of the tinter.

---

## v3.74 patch173
- **The last half-second of overlap, closed.** The performed tag audio itself
  was never the gap - the laugh lives inside the measured wav - but the
  engine's hand-off between tag-performed chunks runs longer in-game than the
  0.30 s the chain allowed, and the fire kept landing just inside the last
  chunk. TH_CHUNK_GAP is 0.60 s now; the gate's burst run computes its
  expected fire from the constant, so the maths and the tests move together,
  and the thought-delay line in the TTS terminal itemizes the new figure on
  every reply.

---

## v3.74 patch172
- **After-mode timing restored to patch170 behaviour, with the 171 protections
  kept honest.** The owner's calterm named two matcher defects the defer made
  loud. First: `endswith` could not see past a SkyrimNet prefix inside a SHORT
  final chunk (*laughs* Hehe, Just a short walk.), so the final was never
  recognised - five defers, then a forced late fire. Second: final-chunk
  recognition accepted a 300-second-stale reply text, so a chunk racing its
  own completion matched the PREVIOUS reply forever. Recognition is by COMMON
  SUFFIX now - the true final chunk ends exactly as the reply ends, whatever
  was injected in front of it - and only a reply fresher than 25 s may claim
  anything; stale or unknown stands the defer down and the chain fires
  exactly as patch170 did. Replayed against both field cases: the 02:40
  short prefixed final anchors with zero defers, the 02:38 stale race fires
  on the chain, mid chunks and tiny single-chunk replies all classify
  correctly.

---

## v3.74 patch171
- **Emotion Chunk Placement (TTS > Audio Tags).** First Chunk (default): the
  reply's first chunk carries the emotion the LLM wrote, once. All Chunks:
  every chunk of the reply wears the SAME emotion, so the delivery holds
  through the whole reply. Random/most-appropriate is deliberately not offered:
  judging the right chunk would need a model call, and that engine is retired.
- **Sound tags are never injected again.** SkyrimNet performs [chuckle] itself
  as a spoken *laughs* prefix; injecting the token too doubled the laugh - the
  owner's field line said it twice. Emotions and styles only, and the erratic
  first-vs-second-chunk placement is gone with it: the parsed-reply window is
  20 s now, so a previous reply's leftover entry can no longer suppress the
  race wait and shove the tag onto chunk 2.
- **A sound-only chunk wears the sound's icon** (patch171 tier: after emotions
  and styles) - 😔 for a sigh, the laugh's own face for a chuckle - instead of
  the plain head.
- **The 01:55 thought race, won.** A pending armed by an early chunk could fire
  into the gap before the next chunk was even delivered; the reply's later
  chunks then found the queue empty and said nothing. A fire that was never
  FINAL-anchored now DEFERS in bounded 2 s steps while the reply is visibly
  still arriving, and the one true fire leaves after the final chunk
  re-anchors the chain - replayed in the gate against the exact field timing.
  Single-chunk replies fire exactly as before.
- **TTS terminal blocks write whole.** Thought synthesis logs from its own
  thread and its rows landed INSIDE a dialogue block; both report blocks now
  write under one lock, blank-separated, and the thought line keeps its grape
  colour. If thought audio is still inaudible in-game, the ARM/DEFER/FIRE
  lines plus the Saved row will now say exactly which stage went silent.

---

## v3.74 patch170
- **The armer never fired in the field - two placement truths, both fixed.**
  First, the mood capture lived INSIDE the thought function's early return, so
  it only ran when a thought happened to ride along; it now sits ABOVE the
  thought guard, and a tag-only reply with no thought at all fills the queue.
  Second, the owner's log showed the chunk beating the completion's parse by
  20 ms - the armer now waits a bounded moment (1.5 s) when NO fresh entry
  exists. An entry is written even when EMPTY, meaning "parsed, no tags", so
  untagged replies pass with no wait at all. Replayed against the exact field
  completion: [contentment] arms chunk 1, [chuckle] arms the laugh, a tag-only
  reply captures, the 300 ms race is won, and the untagged case is instant.

---

## v3.74 patch169
- **NPC emotions finally reach Higgs - the owner's finding, implemented.**
  There never was an NPC forwarding path: SkyrimNet strips the [enthusiasm]
  tags before its TTS requests, and nothing re-armed them, so the voice never
  heard what the completion said and the panel could at best paint a face.
  Now the completion's captured mood queue (patch168) becomes the real thing:
  each NPC chunk pops its next queued pair and wears it as a genuine
  <|emotion:...|> control token, injected one step before tts_apply_tags -
  so the SAME wire the player rides judges it: the ttsTags master switch, the
  final-off board, and this character's own ttsTagLimits cooldowns (a token
  that survives to the engine starts its cooldown, one that is gated costs
  nothing - identical semantics). Emotions in TTS_EMOTION_BLOCK are consumed
  but never injected, exactly as the alias pass refuses them; a line already
  carrying its own token is left alone. The face now simply reads the armed
  text - the patch168 stopgap fallback in say_line is gone, one popper, one
  gate. Full-circle gate run: a two-tag reply arms its two chunks in order,
  empty queue and own-token lines pass untouched, an open gate passes the
  token and a boarded-off gate strips it.

---

## v3.74 patch168
- **NPC faces, solved where they actually live.** The proof was in the owner's
  own estimate line: `proxy 5 ch` for "I do!" - SkyrimNet strips the
  [enthusiasm]-style tags BEFORE its TTS requests, so no text the TTS side ever
  sees can carry them. The completion is the only place they exist, and that is
  where they are read now: one mood queue per speaker, captured beside the
  thought in reading order; each spoken chunk pops the next entry, so a
  two-tag reply faces its two chunks. Emotions and styles face the row;
  sounds ([chuckle]) stay plain by the standing rule. Replayed verbatim
  against the field completion in this session.
- **The reply tree reconnected.** patch167 moved the header stamp to delivery,
  which broke the splicer's tuned "line lands just before its completion"
  anchor window - the real pre-167 splitter was the Before-hold widening the
  RECEIPT gap past the burst limit. Both truths now hold: the header is back
  at receipt where the anchor window expects it, and the burst gap absorbs a
  hold by reading the line's own `hold:` row - a held first chunk keeps its
  reply in one connected branch.

---

## v3.74 patch167
- **Faces, third and final source.** With audio.cpp the alias pass STRIPS
  recognised [enthusiasm]-style tags before synthesis, so the icon never saw
  them in the processed text at all. The face is now fed the RAW pre-alias
  line and reads SkyrimNet's lowercase [word] form directly - all four
  spellings (tokens, *directions*, wire brackets, raw brackets) draw from the
  one catalogue. Verified live against the exact field line.
- **The reply stays one burst.** The spoken-line header used to print at
  request RECEIPT; with the Before-hold in front of it, the stamp sat seconds
  early and pushed the next chunk past the burst gap - the dashboard then drew
  the reply's later chunks disconnected. The header now prints AT DELIVERY,
  the hold is shifted out of the measured wall (its own `hold:` row appears
  beside overhead), and a blank line separates blocks as before.
- **Thought blocks wear the dialogue's row shapes** - realtime, `server:`,
  `audio:` and `Saved` rows in the same columns the painter colours, with a
  blank row after the block.
- **Logs page:** `tts.log` files under the TTS category. The per-server slot
  buttons shipped in patch166 render at the right edge of the Server heading
  row - click a slot to filter, click again to clear.

---

## v3.74 patch166
- **NPC faces, the real regression found.** The LLM's [enthusiasm] / [chuckle]
  tags are rewritten by the alias pass into Higgs' on-wire form
  [EMOTION-ENTHUSIASM] - and the face chooser read only <|tokens|> (and, since
  patch165, *directions*), never that form, so every NPC row wore the plain
  head. The face now reads all three spellings from one catalogue; verified
  live in the gate. Sounds alone ([SFX-LAUGHTER]) still show the plain head by
  the standing rule - say the word to give them their own icons.
- **BEFORE really means before THIS reply.** The reply's first chunk often
  beats the completion's tail by milliseconds, so the thought it should front
  did not exist yet and slipped to mid-reply. The first chunk now waits a
  bounded moment (up to 3 s) for the streamed thought to land, then fronts it
  and holds as before.
- **Log > Files, as requested:** the ttscal / tts-server / ptipme session
  families rotate at five files like the dashboard always has; TTS and
  PTI / PME are their own categories; and the Server category grows one
  button per slot with saved files - click to filter to that server, click
  again to clear.

---

## v3.74 patch165
- **BEFORE-mode survives streaming and sequence switches.** The thought arrives
  at the END of a streamed completion; if the reply's first chunks already went
  out un-held (exactly the first reply after switching modes), playing it on
  arrival landed it mid-dialogue. A mid-reply thought is now DEFERRED - it
  stays fresh and the NEXT reply's first chunk fronts it - and any stale
  AFTER pendings are flushed the moment a before-mode thought is handled, so a
  sequence switch cannot leave an old timer to fire between chunks.
- **AFTER's extra half second trimmed** (chained tail pad removed, fallback pad
  0.5 -> 0.2), as requested now that the chain lands correctly.
- **NPC faces are back in the Proxy terminal.** NPC lines carry *stage
  directions* (*sighs*, *confused*), not Higgs control tokens; the face chooser
  read only tokens, so every NPC row wore the plain speaking head. Directions
  now translate through the same SkyrimNet-to-Higgs alias table the tag system
  uses: emotions decide the face, styles may, and sounds show their own icon -
  player and NPC rows draw from one catalogue.

---

## v3.74 patch164
- **The chain was dropping prefixed chunks - the owner's 19:30 log named it.**
  SkyrimNet injects vocalization prefixes (*sighs* Ahh, / *laughs* Hehe,) into
  a chunk at TTS time; the completion never contained them, so whole-text
  membership evicted those chunks from the reply trace and the thought fired at
  a partial sum (fires-in 4.1s where the reply had 12s of audio). Membership is
  now by the chunk's TAIL - model text, immune to anything injected in front.
  Replayed against the exact field numbers: both chunks counted, fire lands
  after the reply ends.
- **Thought synthesis now logs like dialogue** in the TTS terminal: its own
  header line, realtime/server timing, and the Saved row with the cache file
  and voice - the same shape as every spoken line.
- **The delay calculation prints between the two:** one line at arming -
  `thought delay <who>: 2 chunks, 12.0s audio + 0.45s start + 2x0.30s gap +
  0.4s pad -> plays in 13.0s` - so the period between dialogue and thought is
  never a mystery again.

---

## v3.74 patch163
- **The field log solved it: the reply's early chunks arrive BEFORE the streamed
  completion has yielded its thought**, so the thought-gated scheduler never saw
  them - and the "absolute" final-chunk anchor then discarded the playback
  backlog those chunks had piled up (synthesis runs 2-4x realtime, so the final
  chunk is delivered while earlier ones are still queued in-game). Two changes:
  every NPC chunk is now TRACED unconditionally at delivery (time, length,
  text), and when the thought lands with the recognised final chunk, the whole
  reply's playback is chained from that trace - early chunks included - with
  the fire at the chained end + pad. Replayed against the exact field timeline
  from the owner's logs: the fire lands after the last line ends, not inside it.
  The absolute anchor remains only as the fallback for an untraced reply.

---

## v3.74 patch162
- **The final chunk is recognised, not counted - the owner's design, verbatim.**
  The proxy has already seen the whole reply, so each TTS chunk is matched
  (tag-stripped, normalized) against the stored reply text; the chunk whose
  words END the reply is the final one, and it re-anchors the thought
  absolutely: that chunk's delivery + its own audio length + 0.5 s. The
  additive chunk chain remains only as the fallback for a reply the proxy
  never saw. This also closes the patch160 leftover where chunk extensions
  attached to the newest queue entry and the first thought kept only chunk 1.
  The ARM log now says `FINAL chunk` when recognition lands, so the terminal
  shows which rule timed each fire.
- BEFORE is unaffected by chunking: the thought is synthesized by the panel as
  ONE wav, so its hold already spans the full length + 0.5 s (patch161).
- Negative control: routing the final chunk to the newest pending again fails
  the recognition run.

---

## v3.74 patch161
- **Thought sequencing, stated as the owner's rule and matched to it.**
  AFTER (already exact since patch160): dialogue chunk delivered anchors the
  countdown; the thought is synthesized in the background WHILE dialogue plays;
  playback waits for the sum of the chunks' realtime lengths plus the gaps and
  pad; if synthesis outruns the period it still waits, and if it is slower the
  thought plays the moment it is ready - never earlier than the period.
  BEFORE now matches verbatim: the thought is made and played first, the
  dialogue is synthesized DURING the thought's playback, and the dialogue's
  first chunk is held until the thought's realtime length plus 0.5 s has
  passed (was 0.15 s), with the runaway cap raised 8 s -> 12 s so a long
  thought is honoured in full.
- Negative control: the old 0.15 s pad restored fails the rule check.

---

## v3.74 patch160
- **The thought race, found and fixed - all three symptoms were one bug.** A
  fast model produces the NEXT reply's thought while the CURRENT reply's chunks
  are still streaming. The old scheduler popped that fresh thought on chunk 2,
  cancelled the pending one and reset the chain: the first thought never played
  ("sometimes nothing"), the second fired mid-dialogue ("plays over the line",
  "right after the first chunk"), and slow or single-chunk replies never hit the
  race ("sometimes fine"). Pendings are a QUEUE now - one entry per reply, each
  chained after the end of the one before it, so a thought can never be erased
  and never fires before the room it belongs to has gone quiet. The gate plays
  the race itself: two thoughts landing mid-burst must both fire, in order.
- **Timing is never a guess again:** every arm and every fire writes one line to
  the TTS terminal - `thought ARM <who>: chunk 1.20s, fires in 3.4s, 2 pending`
  and `thought FIRE <who>: waited 3.4s` (or `synthesis failed, nothing to
  play`). If anything still lands wrong on your ears, that log says exactly
  which chunk fed the model and when the fire left.
- The per-chunk arithmetic is unchanged and is exactly the requested formula:
  each chunk contributes its true audio length plus the start latency and the
  engine gap, and the fire pad rides the end - anchored at delivery because the
  game sends no signal when playback actually begins.
- Negative control: restoring replace-semantics fails both the chain check and
  the race run.

---

## v3.74 patch159
- **AFTER-mode thoughts wait for the room to go quiet.** The scheduler modeled
  only the wav's own length; the game adds time around it - a delivery-to-
  audible start latency and an engine gap between the chunks of one reply - so
  the thought landed while the last line was still sounding. The model now
  carries both: `TH_START_LAT` 0.45s per re-anchor, `TH_CHUNK_GAP` 0.30s per
  chunk, `TH_FIRE_PAD` 0.20s at the end. A three-chunk reply fires ~1.6s later
  than before. The gate's burst run computes its expected fire time from these
  constants, so a future retune cannot stale it.
- **The echo is a shade now, and the boom sits in the chest.** Taps halved
  again to 0.055/0.026 (an eighth of the first cut), and the one-pole low-pass
  moved from ~140 Hz down to ~70 Hz with gain 1.8 over a 0.88 dry - measured
  60 Hz energy now 2.4x the 880 Hz reference (was 1.8x), peak well clear of
  clipping. The gate's bounds retuned to the new regime; restoring the old
  numbers fails them.
- Negative controls: the previous echo regime restored, and the chunk gap
  dropped from the scheduler model - each fail their own runs.

---

## v3.74 patch158
- **The empty Proxy terminal, the dead file viewer and the ReferenceError flood
  were one bug - mine.** The patch155 dead-code deletion sliced JS function to
  function, and two constants living between deleted functions went with them:
  `TTS_NEAR_DLG` and `TTS_BURST_GAP`. The terminal splicer threw on both, which
  emptied the Proxy terminal, killed the Files viewer's text field (same painter
  chain), and flooded the error log. Both constants are restored verbatim. The
  Python side had a top-level-name differ that caught exactly this class; the
  page now has its own, run by the gate on every build: every CAPS identifier
  the page code uses must be declared in the page, with strings and comments
  stripped in one left-to-right pass so prose cannot vouch for code. The scan
  immediately also caught (and fixed) a comment wedged between `const` and
  `TERM_FONTS`.
- **Speech Rate is gone, as requested.** The refit writes the stored fit itself
  now, so there is nothing to choose: the arithmetic uses the stored fit the
  moment a valid one exists and falls back to the measured rate otherwise.
  Refit Interval takes the cell, with the Algorithm button kept beneath it. Old
  configs shed the retired `ttsAutoCalUseFit` setting on load.
- Negative control: deleting `TTS_BURST_GAP` again fails both the named check
  and the wholesale scan.

---

## v3.74 patch157
- **Live Network boxes breathe:** the provider emoji now carries a 6px margin
  before the name - a margin because `.nb-t` is a flex row and throws a plain
  space away (the panel-icon branch always had one; the emoji branch never did).
- **The ? on Tag Limits is a proper badge now.** The round badge rule was scoped
  to titles only, so inside the button the ? rendered as bare text; the rule now
  dresses a `.qm` inside a button identically, hover glow included. The click
  that shows the tooltip immediately was already wired to every `.qm` - the
  badge just did not look like one, so nobody clicked it.
- One negative control each: the margin replaced by a throwaway space, and the
  button badge selector removed.

---

## v3.74 patch156
- **The exe is rebuilt from source.** The mingw-w64 cross toolchain
  (g++ 13.2, -O2 -municode -mwindows, fully static, stripped) is available on
  the build machine again, so PandorumLLM.exe now carries the corrected
  embedded copyright - "Source-visible license: personal use and modification
  only; no redistribution" - and version 3.74.0.0. launcher.cpp is unchanged;
  the binary shrinks from 664 KB to 216 KB purely from the newer toolchain and
  stripping. Byte-identical carry-forward resumes from THIS build. The gate now
  reads the string out of the binary itself and refuses an exe or an app.rc
  that still claims Apache. Note: built cross, not yet run on Windows here -
  give it one double-click before publishing.
- **A LICENSE ships, in both trees** - Source-Visible Personal Use: no
  redistribution, personal modification allowed, no trademark use, third-party
  components under their own licenses, no warranty. Drafted to match the terms
  the app.rc line already states; REVIEW THE WORDING before the public release,
  it is your legal text, not mine.
- Negative controls: a tree missing its LICENSE and an app.rc claiming Apache
  again each fail their own checks.

---

## v3.74 patch155
- **Pre-release sweep: safety and privacy first.** The LAN toggle promises a
  remote viewer "cannot see your IPs, paths, or GPU IDs" - and the redacted
  remote state was breaking that promise: it carried the ENTIRE hand-written
  launcher bodies (absolute paths, a pinned GPU serial, environment lines, log
  folders), the loaded-script source path, Creator template bodies, and eight
  unmasked path settings. All of it is stripped or masked now, and the release
  gate HUNTS the redacted state live on every build - a fixture config carrying
  everything the field one did must come out with zero path, serial, env-line,
  model-filename, IP or script-source hits. The toggle's promise is a gate
  check, not a sentence.
- **Every listener binds by one rule.** `listen_host()`: loopback unless a
  second PC is actually configured. The proxy and TTS wrapper bind the LAN only
  when a remote SkyrimNet IP is set - and rebind live if it changes - while the
  panel page binds the LAN only in LAN mode (that one takes a panel restart, and
  the toggle text now says so). Servers the panel spawns (llama defaults,
  audio.cpp, the TTS bat) default to 127.0.0.1: the proxy is the LAN face. The
  application-layer allowlists were already sound; the socket layer now sits
  under them.
- **Dead code out, whole.** Eight orphaned Python functions, five orphaned page
  functions, the stored calib port, the readerless quiet-gap clock, duplicate
  and unused imports, two dead locals, and a state key that silently overrode
  itself. A deletion mishap (constants living between dead functions) was caught
  by a top-level-name differ and restored in full; pyflakes is silent.
- Ship-tree scan: clean of personal identifiers. launcher-src/app.rc no longer
  claims "Apache-2.0 style open source" - its copyright line now matches the
  actual licence (the string inside the frozen exe updates on the next rebuild).
- Three negative controls - the launcher bodies riding to the remote again, the
  bind rule ignoring the second PC, the panel binding wide in local mode - each
  fail their own checks.

---

## v3.74 patch154
- **Server 2, part two: the setter now HEALS what earlier launches baked in.**
  patch153's fix stopped NEW stranding - but the launch-time editor writes its
  edited text back into the config, so every launch since the in-place editor
  arrived (patch48-50) had already saved `"-m", "path", $modelPath` into the
  stored launcher. The patch153 matcher consumed one value and re-inserted, so
  the baked stray survived every edit - same error, unchanged. The value group
  is now REPEATED: an edit consumes every consecutive value token (quoted or
  variable), so one launch under patch154 rewrites the pair clean and the config
  repairs itself. Verified live in the gate: the baked case heals to one clean
  pair, idempotently, with the neighbouring flags untouched - and against the
  field config with the stray simulated in, all three slots regenerate with zero
  stray positionals.
- To be clear on the earlier question: the card terminal (patch146) only shows
  the log - it made the early exit visible, it never touched the launcher. The
  editor that did is the launch-time `$llamaArgs` writer.
- One negative control - the repetition reverted to a single value - fails the
  healing run.

---

## v3.74 patch153
- **Server 2's launch failure, root-caused and fixed.** At every launch the panel
  edits the `$llamaArgs` array in a slot's launcher to match the card. The flag
  setter recognised only QUOTED values - and slot 2's hand-written launcher holds
  `"-m", $modelPath`. The setter removed the flag, re-inserted it with the quoted
  path, and left `$modelPath` behind as a stray positional: llama-server answered
  `error: invalid argument: <model path>`. Cards 1/3 escaped only because their
  launchers already held panel-quoted values. Reproduced from the field config,
  fixed - a PowerShell variable is a value now, replaced like any other - and the
  release gate runs both the variable case and the two-line orphan case live.
  Nothing on your end changed and nothing needed to: launch server 2 as before.
- **LLM Controlled retired.** The proxy algorithm is the one automatic mode; a
  config that still says `llm` keeps doing exactly what it did (the per-line ask
  had already converged to the same arithmetic) - verified by a live gate run.
  Gone with it: the fit job, its server picker, thinking switch and budget, the
  idle wait and quiet-gap clock, the LLM sampler reader, and every dead default.
  The calib job survives for the manual diagnose tool alone.
- **Server cards:** auto-names read `Server 1:` - no brackets - and labels the
  old namer wrote are retitled in place on load; the first three rows breathe;
  the section rules sit centered in the gap (16px above and below).
- **? marks are buttons now.** Tag Limits wears one too; clicking any ? shows its
  explanation in a positioned bubble instead of pressing the button beneath it -
  the click chain answers the ? before the button dispatch.
- **The card terminal is a steady box:** fixed 170px, text flows and autoscrolls
  within it for the whole launch, no resizing, no vanishing.
- Four negative controls - the llm option restored, the ? check sliding after the
  dispatch, the variable-value fix reverted (caught by the live run), the label
  migration dropped - each fail their own checks.

---

## v3.74 patch152
- **An AFTER thought waits for the WHOLE reply.** SkyrimNet splits one Dialogue
  completion into several TTS chunks, and the old timer armed on the first
  chunk's audio length - which is exactly the field photo: the thought landed
  after "Important?" while the rest of the reply was still speaking. The
  scheduler is now burst-aware: each chunk of a reply extends a per-speaker
  modeled playback end (in-game playback is sequential while requests pipeline
  ahead of it: end = max(end, now) + this chunk's seconds) and re-arms the ONE
  pending timer, so the thought fires once, ~0.35s after the LAST chunk's audio
  ends - never between chunks. The synthesis is warmed in the background on the
  first chunk, so the fire itself is a cache hit and a broadcast.
- BEFORE-mode was already whole-reply correct (it fires on the first chunk and
  holds that chunk's delivery) and is untouched. A new reply from the same
  speaker while a thought is still pending replaces it.
- The release gate now plays a three-chunk burst against the real scheduler and
  measures where the fire lands; two negative controls - chunks no longer
  extending the end, later chunks no longer re-arming - are both caught by that
  run's timing.

---

## v3.74 patch151
- **The thought note no longer masquerades as a response.** The "Thought voiced"
  line carried wave marks, and a waved line is SPOKEN as far as the dashboard
  splicer is concerned - so the note was inserted under the nearest record (an
  ActionEval, in the field photo) as a response row. The note is now a plain
  note, quoted, no waves; the splicer leaves it where it belongs.
- **The echo, retuned again:** taps at a quarter of the original (0.105/0.05)
  and the boom doubled (0.76). The gate's echo run now measures AT the tap,
  clear of the boom's brief decay, so tap strength and bass are told apart -
  silenced, halved and reverted taps all land outside its window.
- **A shipped default arrives on the next start.** The additive creator (used by
  the Restore button's seeder rather than copied into it) now also runs on every
  config load: anything in the factory list that is missing entirely - the
  NarrativeEngine pair, for one - is created unallocated, idempotently, without
  a button press. This is why NE-Composer and NE-Director had not appeared.
- **providers.yaml carries real SN providers only.** The panel-owned PTI/PME
  rows - proxy-internal, port 0 - were being exported as `:0` endpoints.
  The generator now skips anything panel-owned or portless; regenerate once and
  the two bogus entries disappear. (The `api_key: "1234"` on every entry is a
  deliberate placeholder: SkyrimNet requires a non-empty key and the proxy does
  not check it; the provider ports 1251+ were always correct.)
- Four negative controls - the wave marks returning, the load-time pass removed,
  the yaml filter dropped, the echo gains reverted - each fail their own checks.

---

## v3.74 patch150
- **The NarrativeEngine pair: NE-Composer and NE-Director.** Two real SN-based
  providers for the NarrativeEngine SkyrimNet plugin, seeded on the next two
  ports (1264 and 1265), plain non-thinking, utility priority. Existing configs
  receive them **unallocated on the next start** - the seeder creates only what
  is missing and touches nothing else - and fresh installs carry them on the
  utility server. Drag them onto a server like any provider; once placed and
  enabled they enter providers.yaml as the next two entries, ports and all.
- On the Providers page they sit exactly where asked by construction: rows sort
  by port with the panel-owned PTI/PME forced last, so 1264/1265 land after
  every existing provider and before the proxy-based pair. Both wear a bright
  grey (#cbd5e1) - clearly brighter than Meta's slate - with the score 🎼 and
  clapper 🎬 marks in both emoji maps.
- The release gate seeds a live config and asserts both arrive unallocated on
  the right ports; three negative controls - the seed pair dropped, the grey
  dropped, one emoji map losing the pair - each fail their own checks.

---

## v3.74 patch149
- **The inner-monologue echo, retuned.** The taps are half as prominent (0.42/0.20
  down to 0.21/0.10), and a **low boom** now sits under the voice: a true one-pole
  low-pass (~140 Hz) per channel mixed back in, so the thought carries weight in
  the chest instead of ringing in the room. Measured live in the release gate: the
  halved tap still carries after the dry note ends, a 60 Hz tone comes through
  clearly louder than an 880 Hz one, and nothing clips.
- **Thoughts click from the second PC.** /api/tts-thought joins the short remote
  allowlist deliberately: a read-only viewer on the game PC can click a thought,
  the host synthesizes it, and the replay reaches every open page - that viewer's
  speakers included. It writes only a cached wav in the TTS spool and broadcasts a
  replay id; everything else stays host-only.
- Three negative controls - the boom silenced, the taps back at full strength
  (caught by the run's bounded window), the remote allowance dropped - each fail
  their own checks.

---

## v3.74 patch148
- **The thought click works.** patch147's handler read a variable named `t` that
  the click chain actually calls `el`, so every press threw a ReferenceError
  before the request was even made - exactly the `t is not defined` in the error
  log, at the moment of each click. The handler now reads the element the chain
  provides. (Spoken-line replays never touched that path, which is why they kept
  working.)
- **Thought Audio is a setting.** A new section on the TTS page, after Player
  Tag System: **NPC thought Audio** (off by default), and - once armed - a
  **Sequence** select beside it: **Before NPC dialogue line** (default) or
  **After NPC dialogue line**. Armed, the NPC's freshest thought (remembered as
  the reply lands, whatever the terminal display setting says - hearing and
  showing are separate) is voiced automatically with the inner-monologue echo
  and broadcast to every open page. BEFORE holds the spoken line's delivery
  until the thought has had its playtime (capped at 8s); AFTER follows the
  line's own measured length. A thought is voiced once, for its own line, and
  stale thoughts are refused.
- Three negative controls - the free variable returning, the capture sliding
  back under the display gate, the delivery hold removed - each fail their own
  checks.

---

## v3.74 patch147
- **Thoughts can be voiced.** A thought line in the Proxy terminal is now a
  button like a spoken line: clicking it synthesizes the text in the character's
  own voice - the panel remembers each speaker's last working reference sample as
  they speak - and bakes in an **inner-monologue echo** (two decaying taps at
  ~130/260 ms, channel-aligned, clip-safe) so it sounds like the inside of a
  head. Stage directions (*sighs*) are removed before the engine reads it.
- The result is cached by content (the same thought synthesizes once and replays
  after), rides the same event stream as any replay - every open page plays it,
  the game PC's included - and the line pulses while it synthesizes. Needs the
  audio.cpp engine; a character must have spoken at least one line first, and the
  panel says so plainly otherwise.
- The release gate runs the echo LIVE on a synthetic wav: the first tap must
  carry real energy after the dry note ends, and nothing may clip.
- Three negative controls - the taps silenced, the reference never remembered,
  the click losing its speaker - each fail their own checks.

---

## v3.74 patch146
- **Server card launches and stops now behave like the TTS buttons.** Pressing
  Launch turns the button into a disabled "Launching Server..." and Stop into
  "Shutting Down..." - each stays down for the whole phase, and the phase ends
  only where the state confirms it: the slot actually serving for a launch,
  nothing running for a stop.
- **The card's small terminal lives through the transition.** It opens on the
  press and is fed every 1.5s from the slot's own newest console log (a new
  /api/slot-log endpoint, ANSI-stripped, reading the same file the speed reader
  trusts), auto-scrolled to the tail. A state repaint rebuilding the cards
  re-shows and refills it immediately, so it cannot blink away mid-launch; when
  the phase ends it closes, and the Terminal button still shows the real console
  window on demand.
- Three negative controls - the phase never ending, the poll dropped, the
  endpoint reading another slot's log - each fail their own checks.

---

## v3.74 patch145
- **The face is the feeling.** A dialogue row's icon now always follows the
  line's emotion tag: an emotion outside the icon map shows the plain face
  rather than letting anything stand in for it, a style (whisper, shout) may
  front the line only when no emotion is named, and a sound effect never does -
  a sigh is something the voice does, not something the character feels.
- **The payload hover is light, not paint.** Hovering a provider record in the
  Proxy terminal now glows the glyphs - accent text-shadow with a soft
  drop-shadow for the emoji - instead of painting a rectangular background
  behind them. At rest the text stays exactly the text.
- **The tag-limit stepper grew a quarter.** The < and > arrows (and the number
  between them) went from 13px to 16px with matching padding, on both the Player
  and NPC Audio Tag boards.
- **A wrapped line folds between words.** Terminal rows explicitly keep whole
  words together (`overflow-wrap:normal; word-break:normal`), and the realtime
  reading after a spoken line - brackets, bolt and number - is one unbreakable
  unit that moves to the next row whole, never split in the middle.
- Three negative controls - a sound effect sneaking back into the face chooser,
  the hover regaining its painted rectangle, the reading losing its one-unit
  wrap - each fail their own checks.

---

## v3.74 patch144
- (Ledger note: the wrap-restore release shipped tagged patch143; the delivery
  message called it 142. The artifacts were consistent throughout - only the
  narration was off by one.)
- **The asymmetric shell.** Field measurement on the current page: record rows
  37px, dialogue rows 22px - records alone carry one extra em, on a page whose
  markup provably contains no break character. So the shell stops arguing with
  the mechanism and removes its room to exist: dialogue, thought and branch rows
  (the wavy/tree/arrow lines) keep `pre-wrap` growth - they have been tight in
  the field for weeks and are the only rows that legitimately wrap - while every
  RECORD row wears `.one`: a hard `height:1.5em` with **no overflow clip**, so
  its glow halo renders whole and nothing a browser invents inside it can move
  the terminal's rhythm.
- **The door scrubs every break-capable character now**, not only CR: line and
  paragraph separators (U+2028/U+2029), vertical tab, form feed and NEL die with
  it; trailing spaces and tabs are stripped per line so nothing can hang or wrap
  blind; and the file's final empty line no longer paints a phantom row at the
  tail's foot.
- Three negative controls - the exotic-character scrub dropped, the record cap
  dropped, the trailing-empty pop dropped - each fail their own checks, the
  behaviour runs included.

---

## v3.74 patch143
- **The second break source, and the last: trailing spaces.** Record lines end in
  a run of column padding, plus the spaces left where the payload marker is
  stripped - and under pre-wrap the browser wraps a trailing preserved-space run
  onto an invisible second line. Records grew; spoken lines, composed in the page
  without padding, never did. This is why the CR fix (patch140) was necessary but
  not sufficient - two independent break sources, one hard, one soft - and why
  patch141's clip appeared to fix everything: it masked both. The painter now
  strips trailing whitespace per line right after the CR scrub; trailing runs
  have no display value in a terminal row. Measured on the reporting screenshot:
  records 37-38px against spoken 20-25px, a delta of exactly one wrapped line.
- The poisoned-tail gate run now feeds padded and tab-tailed lines too, and
  asserts no row ends in whitespace - so both break sources stay dead on every
  future release.
- One negative control - the strip removed - fails the run.

---

## v3.74 patch142
- **Wrapping returns - without reopening the hole.** patch141's clip-proof rows
  cut long lines off at the window's edge and, it turned out, sliced every glow
  and pulse at the row boundary (an overflow clip cuts text-shadows too, which is
  what made the effects look like smeared backgrounds). The row shell is now
  `min-height:1.5em` + `pre-wrap`, no fixed height and no clip: wrapped dialogue
  hangs under itself again with the tree connector stretching the full row, and
  every glow renders whole. The safety holds by construction elsewhere: a row's
  content comes from a split on LF with the CR scrubbed at the door, so no break
  character can exist inside one - and the poisoned-tail gate run now asserts NO
  break character anywhere in the painted markup, making wrapping the only way a
  row can ever grow.
- **"Insert TTS" is "Dialogue Text"** in the Adjust/Options panels, at all four
  places it appears and in its on/off label. The setting and act keep their
  internal names, so saved configs are untouched.
- Two negative controls - the CR scrub removed (caught by the strengthened run),
  the clip sneaking back - each fail their own checks.

---

## v3.74 patch141
- **The terminal renderer, rebuilt from the ground up, at the owner's order.**
  Every terminal row is now a fixed 1.5em box: `white-space:pre`, overflow hidden,
  one uniform height. A second line inside a row is **impossible by construction**
  - whatever the bytes carry (CRLF, bare CR, a smuggled newline), whatever glyphs
  or markup sit inside, the row cannot stand taller. Long lines scroll sideways
  like a real terminal instead of wrapping. The gate proves it by feeding the
  painter a deliberately poisoned tail and asserting one clip-proof row per line.
- The arrival animation and its row-marking machinery left with the rebuild - a
  fixed-height row needs no ceremony, and less machinery is the point. The CR
  scrub from patch140 stays as a belt under the shell.
- Everything above the rows is unchanged: colours, the spoken-line splice, tree
  glyphs, stamps, payload click, replay click, Copy raw tail.
- Two negative controls - the clip removed, the fixed height removed - each fail
  the shell check.

---

## v3.74 patch140
- **The fifteen-patch spacing bug was one character.** The log is written on
  Windows, so every file line ends in CR+LF. The page splits the tail on LF,
  leaving a carriage return on the end of every FILE line; when innerHTML parses
  it, that CR becomes a newline - and inside a pre-wrap row div, a trailing
  newline renders a second, empty line. **Every file-sourced row stood two lines
  tall.** Spliced rows (the spoken lines) are composed in the page without a CR,
  which is why they alone were ever tight - the exact split visible in every
  screenshot since this began. The painter now scrubs CR before anything else
  looks, for every terminal. Verified against the user's own uploaded log in
  BINARY (12 lines, 12 CRLF) and by a gate run that feeds the painter real CRLF
  and asserts CR-free single-line rows.
- Why it survived so long: every inspection of the log - the author's and the
  gate's - used text-mode reads, and universal newlines silently hid the CR. The
  client-side spacing systems of patches 124-135 happened to mask it whenever
  they ran (they filtered blank-ish lines); the revert re-exposed it; the mark-
  cell work never touched it.
- One negative control - the scrub removed - fails both the string check and the
  behaviour run.

---

## v3.74 patch139
- **The record rows finally stand at the spoken rows' height - by copying the
  winner.** On a current page, record rows measured 44px against 27px for spoken
  rows on the same screen, and the only difference between them was the mark cell:
  the spoken rows' `moodic` cell is a plain inline-block that every field
  screenshot ever sent proves tight, while the record cell carried the height cap
  and top-alignment of patches 127 and 131 - each of which measured TALLER in the
  field than the plain box. The record cell is now styled byte-for-byte like the
  spoken one: no height, no line-height, no vertical-align. The field measurement
  outranks the spec argument, three times over. (And no - the arrival animation is
  opacity and transform only; it never touched layout.)
- **Server cards: the header splits in two.** The first row is title, rename and
  the close symbol - nothing else, so no pill can ever push the close anywhere.
  Port and HTTP status sit in a second row beneath, and the port wears the pill's
  own capsule shape in quiet grey. The capsule got its own class after nearly
  colliding with the provider rows' existing `portchip`.
- Three negative controls - clever sizing creeping back onto the mark cell, the
  port sliding back into the title row, the capsule losing its grey - each fail
  their own checks.

---

## v3.74 patch138
- **The page follows the Higgs install.** The installer saved the folder paths and
  announced the change, but a state event only refreshed terminals and queues - the
  TTS pane sat on its old inputs until a hand reload. A state event now re-pulls
  /api/state itself and repaints the TTS pane, so the paths appear the moment the
  install finishes. Editing is respected: a field holding the keyboard is never
  stomped by the repaint.
- **The requested defaults, out of the box** (existing saved settings are the
  user's and are not touched): Audio Tags **pass to the engine**; PME Frequency
  **5**; Sampler Calibration **Automatic**; SkyrimNet Ping **No**; Who translates
  for SkyrimNet **the Proxy** - and that option now reads **"The Proxy"** instead
  of "The panel", in the select and the guide alike. Every drifted fallback copy
  of these defaults (server and client) was moved with the one in DEF_SETTINGS.
- Gate fixtures that silently leaned on shipped defaults now pin what they test:
  the ping-with-silence run pins Yes, the own-wrapper .bat rules pin ttsWrapMode
  off - a behaviour test rides its own settings, not whatever ships this week.
- Three negative controls - the repull no longer fetching, the tags default
  sliding back off, the focus guard dropped - each fail their own checks.

---

## v3.74 patch137
- **The card's first row holds its shape.** Title, rename, port, HTTP status and
  the close symbol stay on one line always: the header row no longer wraps, and it
  is the TITLE that gives way - ellipsised - never the close pushed onto a second
  row. Automatic names now read `Server (N): <gpu>`, numbered across the fleet,
  with the gpu part clamped to fit.
- **A version badge, bottom-right of every page.** It names the release the PAGE
  is running, and adds the panel's release beside it if they differ. This settles
  at a glance the question behind the entire spacing saga: whether the JS on
  screen is the JS that shipped. **A tab with no badge at all is running an old
  page** - close it and open a fresh one. Note also: `PandorumLLM.exe` is still
  the patch111 build; until a new exe is built, start the panel with
  `python fleet-panel.py` (or the bat) so the current page is what gets served.
- **Replay plays on every open page - the game PC included.** A click on a spoken
  line now asks the panel to broadcast the replay id over the event stream; every
  connected page (the host's, and a LAN remote view open on the SkyrimNet PC)
  plays it through its own speakers, pulsing the line where visible. The POST is
  host-scope - a read-only viewer cannot trigger it - and if the broadcast cannot
  be placed, the clicking page falls back to playing locally so the click never
  goes silent.
- On the Proxy terminal spacing: the client has been fully reverted since
  patch136 - patch124 was the first patch to alter spacing, and no spacing code
  from 124-135 remains. The writer emits no blank lines (single `\n` per record,
  verified), so a screen showing wide gaps is a tab running an old page; the badge
  now makes that visible instead of arguable.
- Four negative controls - the header allowed to wrap, the broadcast dropped to a
  local click, the badge never drawn, the clamp removed - each fail their own
  checks.

---

## v3.74 patch136
- **The spacing experiment is closed, at the owner's call.** The Proxy terminal is
  back to one uniform measure: every row - records, branches, spoken lines - wears
  the same block and the same short breath below; a blank line in the file stands
  no taller than a text row. All spacing machinery is gone together: the classifier,
  the spacer, the Row Spacing setting, its select in Adjust, the change-handler, and
  every drifted copy of its default. fixTree stays - correcting a tee to a turn is
  content, not spacing. (For the record, the mechanism behind "no change" was found
  and fixed in patch135 - a tab running old page JS - but simple and uniform is a
  perfectly good place to stop, and it is the owner's terminal.)
- **Replay reaches a two-PC setup.** /api/tts-audio is on the remote read-only
  allowlist: open the panel in a browser on the SkyrimNet PC (LAN mode, same address
  SkyrimNet already uses) and clicking a spoken line plays it on THAT machine's
  speakers - which is exactly where TTS audio normally lands. The panel cannot push
  audio into SkyrimNet's own in-game stream: SkyrimNet pulls each line's audio as
  the response to its own request and offers no play-this endpoint, so the browser
  on that PC is the faithful route.
- **The stepper matches the navigation buttons.** The < and > stand as tall as the
  number between them, accent-glow at rest, brighter glow under the pointer.
- Three negative controls - a branch marking sneaking back into the rows, the
  replay endpoint off the remote allowlist, the hover glow lost - each fail their
  own checks.

---

## v3.74 patch135
- **The spacing case, closed from the user's own files - and a self-healing fix.**
  The uploaded log has NO blank lines, the saved Row Spacing is 0, and the current
  pipeline renders that exact feed perfectly flat under those settings - proven by
  running the panel's real transform chain on the real file. The gaps on screen can
  therefore only come from a browser tab still running an OLD page's JS: the page
  is served no-store, but a terminal tab left open across panel updates never
  reloads, and every fix since has been reaching the server and not that tab. The
  page is now stamped with its release tag, /api/state names the release serving
  it, and a tab that sees a newer panel reloads itself exactly once. After
  installing this patch, hard-reload each open panel tab one last time
  (Ctrl+F5) - from then on, tabs keep themselves current. To see the bundle
  rhythm, set Row Spacing to "1 row" (the saved "0" now means truly flat).
- **Why the dashboard log has no dialogue lines: by design.** The file holds
  records and thoughts; the spoken lines live in the TTS log and are spliced in by
  the page (terminal and Log tab both), stamped with the moment they were spoken.
  One fact, one home - the dashboard file never duplicates the TTS log.
- **Click a spoken line to replay it.** In the TTS and Proxy terminals, hovering a
  spoken line breathes a slight glow; clicking pulses it and plays the audio. The
  wav say_line names is the one already kept in the worker's out-directory, so the
  replay window is exactly the keep window - once prune() rotates a file out, the
  endpoint says so honestly. One line plays at a time; the pulse ends with the
  audio, on error too.
- **The tag-limit stepper.** In limit mode, clicking a tag now opens a small
  < N > popover anchored under the chip - the page-navigation buttons at half
  size - stepping by one, clamped 0..99, instead of cycling blind. The green count
  badge stays on the chip's corner. The popover lives outside the grid so the
  repaint cannot take it down, re-anchors after each step, and closes on Save,
  Reset, leaving the mode, or clicking anywhere else.
- Five negative controls - the handshake never firing, the marker never written,
  the endpoint serving any path, the popover dying with the repaint, the pulse
  never released on error - each fail their own checks.

---

## v3.74 patch134
- **The spacing mystery, actually closed - and an apology owed.** `termRowGap`
  defaulted to 0, and at 0 the spacing function returned the raw file VERBATIM -
  including the blank lines the log itself writes. Every rhythm rebuilt across
  patches 124-133 was therefore skipped entirely on a default config; what was on
  screen the whole time was the file's own incidental blanks. Two changes: the
  normalization (strip the file's blanks) now happens at EVERY gap value - 0 means
  truly flat, 1+ means the bundle rhythm - and the default is 1, so the designed
  rhythm is what a default install shows. If you ever saved Row Spacing as "None"
  yourself, set it to "1 row" in Adjust to see the rhythm.
- **A "Copy raw tail" button** in the Adjust panel copies the terminal's feed
  exactly as the file holds it, before any client-side shaping - so the next report
  of anything odd can carry data instead of another round of theory.
- **Tag Limits, both boards.** Beside "Player Audio Tags" and "Allowed Tags" sits a
  Tag Limits button: while lit (accent glow), clicking a tag cycles its limit
  through 1/2/3/4/5/8/10/none, shown as a badge riding the chip; Save and Reset
  populate to its right (Reset returns to the default: no limits). A limited tag,
  once actually spoken, is held from the SAME character for that many of their own
  turns - the player counts player turns, an NPC counts that NPC's - enforced at
  the wire beside the Allowed Tags gate, so the source of the tag does not matter.
  Only a tag that truly reached the engine starts a cooldown; a warm-up ping
  neither spends a turn nor starts one; cooldowns live in memory, so a restart
  forgives them, which is correct for a conversation-scale rule. Two tables:
  `ttsTagLimitsPlayer` and `ttsTagLimits`, WORD:N pairs, unknown words ignored.
- Six negative controls - the default back to 0, gap-0 returning the raw file, the
  cooldown clock made global, a spoken tag never starting its cooldown, the player
  board's limit mode removed - each fail their own checks, the first two by
  behaviour runs.

---

## v3.74 patch133
- **The terminal rhythm, settled by running the real pipeline.** Instead of another
  CSS theory, the actual transform chain (hide -> splice -> space -> tree -> stamps)
  was run under node on a faithful raw feed, and two structural defects fell out in
  plain text with no CSS involved: adjacent bundles stacked TWO blank runs back to
  back, and a lone spoken row (the arrow-marked kind that hangs off no reply - the
  player's own lines) was invisible to the branch test, so it broke its bundle in
  half and took plain-row spacing. One classifier now defines a response row for
  every consumer - tree tee, turn, the lone arrow, the spoken wave - the spacing and
  the row classes read the same one, and a blank run is never laid on top of another:
  blanks can only exist at bundle edges, singly, by construction. The gate RUNS both:
  the row classes and a nine-row scene (adjacent bundles share one blank; a lone
  spoken row is bundled and aired; plain runs carry no blanks at all).
- **The Audio group's buttons toggle now.** Prosody words are offered lowercase while
  the stored set is uppercase, and every comparison was case-sensitive - the click
  saved and nothing dimmed, and the built-in prompts never dropped the word either.
  One case everywhere: the board dims through an uppercase compare, and the tagger
  prompt, its worked examples, and the answer cleaner all fold case before looking.
- **A separator line stands above the Player Audio Tags title** - a quiet 1px rule
  where one block ends and the next begins.
- **The Allowed Tags board hides under Strip.** With Audio Tags set to strip,
  nothing passes to the engine anyway, so the gate's buttons would be dead weight -
  the board renders only in Pass mode.
- Five negative controls - the blank runs stacking again, the lone arrow dropped
  from the classifier, the board back to case-sensitive dimming, the separator
  removed, the board shown under Strip - each fail their own checks, the first two
  caught by the behaviour runs rather than by strings.

---

## v3.74 patch132
- **Allowed Tags: a final gate on the wire to Higgs.** Under the Audio Tags field, a
  second button board in the same boxed-group shape as the player board - every tag
  the engine understands, lit while allowed, dimmed once blocked. A blocked tag never
  reaches the TTS, whoever wrote it: SkyrimNet's own NPC lines, the player tagger, or
  an alias spelling like [angry]. A blocked sound effect takes its onomatopoeia with
  it - a first cut gated only the control tokens and left the "Ahem," behind, spoken,
  for an effect the user had turned off; both tag writers (inline and sentence-level)
  now read the gate before anything is written, with a backstop on raw <|...|> tokens
  arriving in the text itself. One setting (`ttsTagsFinalOff`), read by the same
  parser as the player board with its own key; unknown words ignored.
- **The two boards are independent by design**: Player Audio Tags decides what the
  models are ASKED for; Allowed Tags decides what the engine is SENT. The ? on the
  title says so, and notes that in Strip mode the gate is idle because nothing
  passes anyway.
- Four negative controls - the inline writer's gate removed (the onomatopoeia leak),
  the backstop door bypassed, the speech path not passing the setting, the board
  dropped from the page - each fail their own checks. (The sentence-level writer's
  gate has no independent control: with the backstop in place its removal is not
  observable in output, which is the defence working as designed.)

---

## v3.74 patch131
- **The plain-row height, third episode, closed at the actual mechanism.** patch127
  blamed the colour emoji and fixed the mark cell's HEIGHT; patch129 found the
  maximized view's own line-height override and removed it - and the plain rows
  still stood at ~2.4em while bundle rows sat correctly at 1.3em (pixel-measured:
  40px against 21px on the same screen, so the 1.3 rhythm itself was provably in
  force). The remaining grower was the mark cell's ALIGNMENT: a baseline-aligned
  inline-block exports its internal baseline to the row, and with a colour emoji
  inside, that baseline rides ~2.4em of internal line - a fixed height changes
  nothing about what baseline alignment exports. The cell is now
  `vertical-align:top`, so it contributes exactly its own 1.25em and the row is
  1.3em like every other. Spoken and thought rows were never affected because their
  emoji are plain inline text, which line-height bounds - which is also why every
  earlier fix looked right in the bundle and wrong above it.
- One negative control - the alignment removed - fails its check.

---

## v3.74 patch130
- **The Proxy Algorithm is the standard, and it now does the whole job.** Default
  calibration method is `proxy` (was off). Every N lines (default 12) it refits
  itself by least squares over the measured record and writes the same stored fit
  the LLM path writes - no model, no server, no idle wait, no quiet gap, run inline
  on the line that makes it due, so it can never contend with speech. With Sampler
  Calibration on, the same tick takes at most ONE bounded arithmetic step: steadier
  (temperature -0.07 floor 0.5, top_p -0.02 floor 0.85, repetition 1.0) when >=8%
  of the last window's lines ran past end-of-content; one notch back towards
  SkyrimNet's own values after a clean 40-line window; never twice on the same
  window (the lines must postdate the last change); every change logged with the
  numbers that drove it. The LLM refit and the model-read sampler diagnosis remain
  as the LLM Controlled option, unchanged.
- **Efficiency: the record is read from memory.** The per-line cap used to re-read
  and re-parse the whole measure file for every spoken line; a warm in-memory copy
  is refreshed only when a line was actually appended (a generation counter says
  so). The file remains the truth across restarts.
- **The headroom is a percentile, not the single worst outlier.** h = p95 of the
  scored miss ratios x 1.10 pad, clamped [1.08, 1.60] (was worst x pad, clamped
  [1.05, 2.5] - one censored freak used to inflate every cap for 120 lines, and 2.5
  was the pinned-bug era's smell, not a margin). The worst miss is still reported in
  the facts and the feed sentence names both.
- **UI**: the method menu names "Proxy Algorithm (standard)"; the Refit Interval
  slider now appears in Proxy mode too (one shared block, defined once - the
  duplicate-id sweep caught the second copy); Sampler Calibration reads Manual /
  Automatic, shows the model cell only when a model will read the record, and its
  tooltip explains both runners.
- **"Audio Tags" is now titled "Player Audio Tags".**
- Six negative controls - worst ruling again, the append not staling the cache, the
  proxy tick not deriving, the sampler switch ignored, the same window stepped
  twice, the rename reverted - each fail their own checks.

---

## v3.74 patch129
- **Why the row tightening never showed: the Proxy Terminal page is the MAXIMIZED
  view, and it carried its own line-height.** `.tmax .tail` set `line-height:1.6`,
  so every rhythm change made to `pre.tail` since patch125 landed everywhere except
  the terminal actually being read. Verified against the reported pixels: the plain
  row pitch equals 1.6em times the display scaling, exactly. The override is
  removed - the maximized view keeps its layout rules (flex, height) and inherits
  the one rhythm (1.3 line, 3px breath on plain rows, tight bundles, 1.9em bundle
  edges) that the embedded view already had. The full text pipeline was also run
  against a faithfully rebuilt raw feed under node: transform and row classes are
  correct - the fault was this one CSS line.
- One negative control - the override restored - fails both its checks.

---

## v3.74 patch128
- **The speed-test regression, root-caused: idle was not silence.** The calibration
  jobs' idle wait let a fit, diagnosis or sampler calibration START in the sub-second
  gap between back-to-back lines, and those calls run 20-116 seconds on a card speech
  may share - the observed 4-5.5x realtime falling to 2-4x during a test. A background
  job now needs a real QUIET GAP: 2.5 seconds of speech silence, stamped when each
  line ends, on top of the existing idle checks. A stream of test lines never opens
  that gap, so the fit waits its two minutes, skips with its usual honest note, and
  stays due - the test is never shared with a calibration. Nothing changed in the
  per-line speech path itself; the base-v3.74 diff shows its additions are
  milliseconds of arithmetic and logging.
- **Speed is a number on the page now.** Each measure row records the wall seconds
  the line took to MAKE alongside the audio seconds it produced, and Monitoring gains
  two boxes: **speed** (median realtime factor of the last 24 lines) and **retries**
  (lines in that window that ran past end-of-content and were regenerated - each
  retry roughly halves that line's realtime on the spot). If the factor dips again,
  the boxes say whether it is retries, contention, or clocks.
- **GPU Clock Hold** (TTS Server field, off by default). Between lines the card drops
  to an idle power state and the first tokens of the next line are spent climbing
  back out - a real cost on short lines. On: when the TTS server starts, the card's
  own maximum graphics clock is read and locked (`nvidia-smi -lgc max,max`), and
  released (`-rgc`) when the server stops or the panel exits, every exit path.
  Needs the panel run as administrator (said plainly in the feed when it is not),
  and costs idle watts while held - both are why it is your switch.
- Five negative controls - the gap requirement removed, the wall not stored, the
  admin gate removed, the exit release removed, the boxes never drawn - each fail
  their own checks, the first caught by a behaviour run.

---

## v3.74 patch127
- **The spacing complaints were the emoji all along.** A colour emoji stands taller
  than the 1.3 line, so every row carrying one grew to the glyph's own height while
  the bolt rows stayed at 1.3em - patch125's tightening moved everything EXCEPT the
  rows it was aimed at, and the bundle's blank rows then read short beside them. The
  mark cell now has a fixed height (the glyph may overflow it visually, which is
  fine), so a row's height is the row's own.
- **The requested rhythm, exactly:** plain rows keep a short breath (3px) below them;
  a bundle's rows sit tight against each other (branch rows are marked `tb` by the
  row wrapper and carry no breath); and the bundle's edges get the longest air (the
  inserted blank rows, now 1.9em). The branch connector joins the same 1.3em rhythm
  instead of standing at 1.6em.
- The gate runs the row classifier under node - a plain row is a `tline`, a branch
  row a `tline tb` - and a behaviour run that cannot RUN now fails instead of
  skipping: the first version of this check died on a typo inside its own try/except
  and reported itself as "node not available".
- Four negative controls - the height cap removed, the connector back at 1.6em, the
  breath removed, the classifier disabled - each fail their own checks.

---

## v3.74 patch126
- **The built-in wording is a field of its own.** In the PTI and PME prompt editors,
  the "Built in:" section is a read-only, scrollable field with a copy control in its
  top-right corner - one click takes the whole wording (clipboard API on localhost, a
  hidden textarea over plain LAN http where the API is absent), and the corner answers
  with a check so the click is seen to land. No more dragging a selection through a
  grey paragraph.
- **The Custom Prompt Active chip stands beside the Audio Tags title**, inside the
  title's own label, instead of wrapping underneath it.
- **Each tag group is titled above a bordered field of its own** - "Emotion" and
  "Audio" over input-styled boxes that hold buttons instead of text.
- One escape-depth catch: the check mark the copy corner answers with was written as a
  single-backslash escape, which Python resolves before the page ships - every other
  page string writes the double form so the JS escape survives. Made consistent, and
  the gate's own pattern is built with `chr(92)` so its depth cannot lie either.
- Three negative controls - the grey paragraph restored, the chip pushed outside the
  label, the group boxes flattened - each fail their own checks.

---

## v3.74 patch125
- **Plain rows sit tighter by default** (terminal line-height 1.5 -> 1.3), while the
  blank rows the group spacing inserts are taller (1.75em) - so the air around a
  spoken bundle stays as it was and everything else closes up.
- **Tree elbows tell the truth.** A branch is drawn as a tee only when another branch
  hangs beneath it; a single child, and the last child of any group, is a turn. The
  written glyphs cannot know what the page splices beneath them later, so the shape
  is settled in the painter, after the splice, from what is actually on the next row.
  The gate RUNS this: one child -> turn; three -> tee, tee, turn.
- **The action bolt sits in the same fixed 2-character cell as every other mark**, so
  action rows start where spoken rows start instead of two pixels left of them.
- **"Hunter [Hunter]" is Hunter.** Generic NPCs arrive with a bracketed role - [Bandit],
  [Bandit Chief] - between the name and the headings the actor patterns anchor on, and
  a pattern that did not expect it matched nothing, so the record said "someone". The
  role is consumed and never captured, in all three actor patterns.
- **Audio Tags as buttons.** In Player Tag System, every tag the built-in PTI and PME
  prompts offer is a small lit chip, grouped Emotion / Audio. Click one and it dims:
  the word leaves the built-in tagger prompt, the built-in mood prompt where it
  appears, the worked example that taught it, and the answer filters - a model that
  uses it anyway is not kept, and a mood reading naming it is skipped as a choice, not
  logged as noise. Click again to restore. Stored as one setting (`ttsTagsOff`),
  unknown words ignored. Only the built-in prompts are edited: a custom prompt is the
  user's own text - the {words} placeholder still expands to the full vocabulary, and
  a yellow "Custom Prompt Active" chip beside the Audio Tags title (with the ? tooltip
  carrying the explanation, no grey paragraph) says these buttons have no effect until
  it is cleared. The prompt editor's "built-in wording" shows the prompt as it
  currently reads, clicked-off tags and all.
- The dead `_tag_allowed` allowlist - defined by patch115's refactor, called by
  nothing since - is deleted whole.
- Six negative controls - the role brackets removed, the prompt ignoring the set, the
  cleaner keeping an off tag, every branch a tee, the yellow chip downgraded, the rows
  loosened - each fail their own checks.

---

## v3.74 patch124
- **Air goes around what was said, not between every record.** In the Proxy terminal,
  a record with output hanging under it - thoughts, spoken lines, actions - gets the
  gap before it and after its last branch; plain records sit tight against each other.
  The gap size is still your Row Spacing setting, 0 still means none anywhere, and the
  spacing runs after the spoken lines are spliced in, so a record whose only output is
  speech still gets its air.
- **Quitting runs the same TTS stop the Stop button runs.** That is the whole fix:
  the button stops the handled process AND kills whatever owns the TTS port - which is
  what catches a server a previous panel run started - while the exit path only did
  the first half. patch123 then wrote a SECOND port-independent discovery instead of
  calling the one that existed, and its PowerShell quoting emitted rows no parser
  matched, so it found nothing in the field on its first day. That sweep is deleted
  whole; `full_exit` now calls `stop_tts_server` + `_kill_port_owner`, exactly as the
  button does, and does it BEFORE the fleet's own -Stop - a closing console gives the
  handler about five seconds and -Stop can eat all of them.
- The port kill falls back from `pwsh` to Windows PowerShell, so quitting does not
  depend on PowerShell 7 being installed.
- **Ctrl+C and the console's X both quit properly now.** KeyboardInterrupt used to
  fall through with no cleanup at all; it runs `full_exit` now, and a registered
  console control handler (reference kept - a collected callback is a crash) runs the
  same on the window's X, logoff and shutdown.
- The gate RUNS the new spacing under node - two plain records tight, air around the
  spoken group - rather than only reading it.
- Four negative controls - every row padded again, the exit stopping the handle only,
  the fleet stopped first again, Ctrl+C back to a silent pass - each fail their own
  checks.

---

## v3.74 patch123
- **The TTS server dies with the panel, whichever panel run started it.** Quitting
  stopped only the process THIS run held a handle to - restart the panel under a
  running TTS server and the handle is gone, so the fleet's discovery-based -Stop
  killed the LLM servers while the TTS server survived with a model pinned in VRAM.
  The exit now also sweeps: any audio.cpp server carrying the panel's own
  `audiocpp-server.json` on its command line is panel-started by construction,
  whichever run wrote it, and is stopped by pid as a process tree (`taskkill /T`).
  A server launched by the user's own means never matches and is never touched. The
  handled stop uses the tree kill too, and a remembered pid without a live handle is
  stopped rather than skipped.
- **Thinking controls titled like everything else.** In both calibration rows the
  switch sits under a white "Thinking" title and the slider under "Thinking Budget" -
  three titled columns (Server / Thinking / Thinking Budget), title above control,
  tooltips carried on the titles.
- **The Monitoring block no longer blinks.** Two causes: every state tick rebuilt the
  pane and the boxes, bars and chips sat EMPTY until the async fetches landed - the
  pane is now seeded synchronously from what was last known before any fetch; and the
  refreshers rewrote innerHTML with identical content every tick, which repaints as a
  flicker - everything goes through one setChanged() that writes only when the
  content differs (boxes, chips, pickers' legend, meter keys).
- **The player's name, third source.** These prompts carry no "## <name>'s Party"
  heading at all - but SkyrimNet's standalone thought prompt is the player's own
  ("You are Maxxor ... Think internally as Maxxor"), while an NPC's thought rides
  inside a dialogue reply. The proxy learns the player from that prompt when the
  speaker and the think-as name AGREE, keeps the party heading and the honest
  say-when-unnamed fallback, and now TELLS PTI and PME who the player is: "The line
  is spoken by the player, Maxxor." under the tagger's prompt, "The player is
  Maxxor." under the mood reader's. The Proxy terminal's spoken lines carry the name
  the moment it is learned.
- Six negative controls - the orphan sweep removed, the pid-only stop skipped, the
  switch title dropped, the change guard removed, the seed removed, the agreement
  requirement dropped - each fail their own checks. (The seed control first surfaced
  as a gate CRASH rather than a FAIL: a check built on `.index` of a string that a
  mutation removes raises instead of failing. It uses `.find` now.)

---

## v3.74 patch122
- **The terminal reads as it used to.** patch121's mark cell and click wrap addressed
  the mark as token 2 - which it only is BEHIND a timestamp. With Hide Stamps on, the
  stamp is stripped, the TITLE landed in the mark's 2-character cell, and "Dialogue"
  wrapped two letters to a row. The mark is found by what a stamp IS now (starts "["
  and carries ":", which a port token never does), so the cell, the button and the
  columns hold with stamps on or off.
- **New records slide in rather than snapping.** Both row painters - the record
  terminal and the spoken-lines one - know which rows are new by the count before the
  repaint, and those rows arrive with a short fade-and-rise. Scroll position and the
  stick-to-bottom behaviour are unchanged.
- **The Monitoring bars glide.** The segments have carried `transition: width .35s`
  since they were built - written on every repaint and never once seen, because
  `innerHTML` replaced the elements each tick and a transition only runs on an element
  that survives. Same segment set: widths are now updated in place and ease to their
  new values; a different set builds fresh once.
- Four negative controls - the mark addressed by position again, one painter's marking
  removed, the bar rebuilt every tick, the slide-in removed - each fail their own
  checks.

---

## v3.74 patch121
- **The terminal button is the text it always was.** No dotted underline, no glow at
  rest - the emoji and title look exactly as before, and the button shows itself under
  the hand as an accent pill behind them. Nothing about the glyphs is restyled.
- **The rows hold their columns.** Two fixes: every record's mark now sits in one
  fixed 2-character cell (emoji advance by different widths in a monospace line, and
  the whole row after a narrow one wandered left - the Calibrate line's dial was the
  visible case), and the provider-name column widened 13 -> 15 so "TTS Calibration"
  fits it rather than pushing its own lines two characters right. Lines from before
  this patch keep the old widths in the current session's file; the next session is
  uniform.
- **The TTS Calibration record wears the panel's own glowing mark**, the same
  PandorumLLM icon PTI and PME lines carry, instead of a ruler emoji.
- **The opened record is colour-coded** like the viewer the layout was drawn from:
  request keys in salmon, numbers green, punctuation dim - and the prompt string is
  laid out as REAL lines, with ## headings and **bold** runs lit, instead of one
  endless escaped line. The reply pane tints [TAGS] gold and <internal_thought>
  blocks in the terminals' own grape, with the reasoning under it dimmed grape. Every
  chunk is escaped before it is tinted; the tag scanner is a plain walker, because
  "not a ]" has no backslash-free regex spelling and this page bans backslashes in
  built RegExps.
- Five negative controls - the underline restored, the mark cell removed, the emoji
  back on the fit, the name column back to 13, the request pane back to plain escape -
  each fail their own checks.

---

## v3.74 patch120
- **"LLM fit" is called the TTS Calibration everywhere** - the monitoring box, the
  per-line working in the calibration feed ("TTS-calibrated"), the Proxy speech-rate
  menu option, the fallback note ("no TTS calibration derived yet"), the Proxy-terminal
  record name, and the feed lines the derive writes. It is the same thing the section
  is named after: the cps and lead-in a model fits once from this machine's measured
  lines. Setting keys are untouched, so existing configs carry over.
- **The thinking budget is the user's, per calibration.** A slider (500 - 10000) sits
  beside each Thinking switch - one on the TTS Calibration row, one on the Sampler
  Calibration row - in the same row, inside the card, with its value beside it. Dimmed
  and disabled when thinking is off, never hidden, so the row does not move. Both
  default to 2000. Diagnose reads the same record the sampler calibration reads, so it
  spends the sampler calibration's budget. The "Answer now." message still fires when a
  budget runs out.
- **The monitoring boxes explain themselves.** Every tooltip now says what its figure
  means and what follows from it: headroom as the safety margin every cap is multiplied
  by (with the percentage it grants), worst line as the estimator's worst
  under-prediction of real speech, pad as the fixed 10% over it, scored lines as the
  only lines that can grade the estimator (floor- and guard-decided lines say nothing
  about it), runaways as capped lines whose true length is unknown - what they COST is
  the cap's business, how OFTEN they happen is the samplers' - and the TTS calibration
  box as the model-fitted rate, kept only when it beats the panel's own least squares.
- Four negative controls - the calls cut off from the slider, the slider hidden instead
  of dimmed, the old name restored on a box, a tooltip reduced to naming its figure -
  each fail their own checks.

---

## v3.74 patch119
- **A terminal record can be OPENED.** In the Proxy terminal, the emoji and provider
  title of every generation are a button now (dotted underline, accent glow under the
  hand); clicking opens the request as it was actually sent and the reply as it came,
  side by side over the page - REQUEST PAYLOAD | RESPONSE PAYLOAD, with the provider
  chip, server port, a Streaming chip where it streamed, the duration and the
  timestamp in the header, and the model's reasoning under the reply when there was
  any. The pairs live in an 80-entry ring, **in memory only** - prompts are the
  player's game and are not written to any file the session leaves behind. A line
  older than the ring answers honestly that it is gone. Covers SkyrimNet's traffic
  and the panel's own calls (fit, diagnosis, sampler calibration) alike.
- **Why the LLM fit was "not a usable fit" every time:** the fit job's card has
  Thinking ON, and the call gave the model a flat `max_tokens: 60` - which a thinking
  model spends entirely inside its reasoning block, so the visible answer was empty
  and the parse had nothing to read. Panel jobs now carry a **512-token reasoning
  budget** with the ceiling raised to hold both halves; when the budget runs out the
  "Answer now." message (already wired) fires and the JSON follows. A budget is never
  sent with a grammar (HTTP 500), and 0 is never sent at all (it means "stop NOW" and
  answers a stub - patch38/97). The fit's visible answer also grew 60 -> 120 tokens
  for fences and a sentence.
- **An unusable fit answer says WHICH way it was unusable**, in the calibration feed,
  under the line that refused it: "the whole answer went to reasoning (~N chars)", or
  "the server answered nothing", or the first 160 characters of what it did say. "Not
  a usable fit" was the same words for three different faults, and only the text can
  say which fix is due.
- `--line`, the border colour nine CSS rules already asked for, finally exists.
- Five negative controls - the flat ceiling restored, a budget sent with a grammar,
  the mute refusal restored, the payload ring written to disk, the id left visible -
  each fail their own checks.

---

## v3.74 patch118
Ran the day's calibration logs through the arithmetic instead of reading them: the floor
decided 99 caps, the guard 81, the estimate 67. **The fit the user calibrates was not
consulted for 73% of lines** - which is exactly "LLM fits don't really adjust the token
limits any more". Three faults, each of them arithmetic outranking the measurement:

- **The flat 128-token floor swallowed every short line.** 128 tokens is ~5 seconds of
  audio; a 42-character line's whole working band was floor 128 to guard 147, so a fit
  moving cps 16 -> 17.5 moved nothing. The floor is now **half the guard** - the same
  tokens-per-character the user already owns - between a 48-token warm-up minimum (~2 s:
  the lead-in breath and the codec start) and the old 128 as its ceiling, so no line's
  floor is ever higher than it was. A 42-ch line's band is 74..147 now and the estimate
  decides it; a 10-ch runaway burns 48 tokens, not 128.
- **A runaway on a floor-decided line was scored as the estimator's miss.** Successes
  are only scored where the estimate decided the cap (that rule shipped long ago);
  failures were scored always - and 128 over a 17-token estimate is 7.4 of arithmetic,
  not of evidence. That single line pinned the headroom at its 2.50 maximum for a whole
  session, which raised every cap toward the guard, which raised what the next runaway
  cost. Failures now record WHO decided their cap and are scored by the same rule as
  successes. Where the estimate WAS in charge, cap/est is the current headroom by
  construction - the honest reading "est x headroom was not enough" - so the headroom
  moves one pad step at a time instead of pinning. Legacy failure rows carry no bound
  and are counted as runaways but not scored, which retires the poisoned 7.44 without
  deleting the record.
- **The model was marked on rows it never saw.** The derive prompt sent the last 24
  measured lines, then `tts_fit_mae` judged the offer against all of them. It is shown
  the last 120 now (~4 KB), the same population within reason, and the least-squares
  hint and refusal bar are unchanged - they were right.
- The calibration feed prints each line's own floor, and the Algorithm text describes
  the scaled floor from the live constants.
- Replayed the uploaded session through the new arithmetic: headroom settles at ~1.26
  instead of pinned 2.50, and "42 ch, est 69 -> 128 (floor)" becomes "-> 86 (estimate)".
- Five negative controls - the flat floor back in the cap, the flat floor back in the
  guard, every failure scored again, the bound no longer recorded, the 24-line taste
  restored - each fail their own checks.

---

## v3.74 patch117
- **The headroom reading is a row of boxes, not a sentence.** One figure per box, lit
  with the accent the way a Live Network box is, centred in the card and wrapping to a
  second row rather than running off it: *headroom*, *worst line*, *pad*, *scored lines*,
  *runaways*, *LLM fit*, *last attempt* (with its timestamp under it). Before eight
  scored lines it says *seed* and *n / 8* instead of a worst line that has not been seen
  yet. Each box carries the explanation it used to bury in the sentence as its tooltip.
- **The numbers travel as numbers.** `tts_headroom_facts` answers `h`, `worst`, `pad`,
  `n`, `need`, `censored` and `seed`, and builds the sentence the record prints from that
  same dict - so the boxes on the page and the line in the terminal cannot drift. Nothing
  on the page parses a sentence to find a number in it, and `tts_autocal_headroom` is now
  two lines over the same facts rather than a second copy of the rule.
- The seed threshold is a named constant (`AUTOCAL_HEAD_MIN_N`) instead of an 8 typed
  into the wording, and the box that holds a sentence a model wrote escapes it.
- Four negative controls - the sentence sent instead of the figures, the row set to
  nowrap and left-packed, the accent taken off the edge, the escaping removed - each fail
  their own checks.

---

## v3.74 patch116
- **The headroom reading is 14px**, one size up from the 13px it was. 26px was twice it
  and read as a headline over the bars rather than the caption it is.
- **Steady Retry sits with the samplers**, in the chips' own row, not beside their title -
  it is the other thing that decides what a request carries.
- **The player's name in the Proxy Terminal.** It is read from a `## <name>'s Party`
  heading in a dialogue request, and that read was capped at the first 256 KB of the
  body. The stock prompt puts the heading about 17 KB in; a long memory block pushes it
  past any fixed window, and then the name is never learned at all - so every spoken line
  said "Player" while the thought under a reply, which is named from that request's own
  "You are ..." line, read correctly. Two names, two sources, and only one of them could
  fail. The whole body is searched now, until it is found once, and any possessive on the
  party matches rather than that one full heading.
- **And when it still cannot be read, it says so.** One line in the panel log, once:
  that the player's line is going out unnamed, and the headings the last dialogue request
  actually used. A silent fallback is what made this look like it worked. If the message
  appears with headings that name the player some other way, that wording is what the
  next patch matches on - measured, not guessed.
- **The gate can no longer skip itself.** `re.search` answers a Match or None, and `A and
  B` over two of them answers None as soon as one misses - which this gate reads as SKIP.
  One check written that way ran green while testing nothing. Every check on a match is
  coerced to a bool, and a rule over the gate's own source refuses any that is not.
- Five negative controls - the fixed 256 KB window restored, the narrow heading restored,
  the silent fallback restored, 26px restored, and an unguarded match written into the
  gate - each fail their own checks.

---

## v3.74 patch115
- **The section is TTS Calibration**, the menu in it chooses the **TTS Calibration
  Method**, the bars and their reading sit under **Monitoring**, and the record is the
  **TTS Calibration Terminal** with a **Hide/Show Terminal** button.
- **Fixed mode is now a number you set.** A *Token per character* slider (1 - 25) with
  **Reset to Higgs Default** beside it, which puts back 3.5 - Higgs' own natural rate
  doubled. Fixed mode is nothing but this number (chars x tok/char, floored at the
  lead-in), and every other mode still stays under it as the runaway guard, so the
  Algorithm text quotes what is set rather than a constant. Outside 1 - 25 it is
  refused, not obeyed: a 0 would cap every line at the floor.
- **Settings are passed into that arithmetic, never read by it.** `load_config` fills
  defaults and SAVES, so a config read from inside a per-line guard would write the
  config file from the hot path - and did, until the gate's own cleanliness check
  caught a `fleet-config.json` appearing in the tree.
- **SkyrimNet's Own Settings is gone.** Whatever arrives with a line is always
  forwarded; your values (Manual) or the model's (LLM Controlled) overwrite it. The
  switch that could drop it only meant the engine's own default arrived instead, unseen.
- **All four sampler chips read.** They were fed REQUEST field names - `temperature`,
  `repetition_penalty` - and asked by chip name - `temp`, `rep`. Two of the four names
  happen to be identical, which is exactly the two that filled in while the line under
  the bars, which goes through `TTS_SAMP_FIELD`, had all four. One answer now
  (`tts_samp_now`), used by the facts AND by the meter tick, so the chips repaint with
  the bars instead of waiting for a diagnosis to be asked for.
- **Steady Retry** moved onto the Samplers line. **The headroom reading is 26px**, twice
  what it was, and the order under Monitoring is title, reading, then the line that
  reading was taken from - it was pinned to the far right of the title before.
- **Algorithm is a button**, in the speech-rate menu's own row, with no title or question
  mark above it; `ttsBtnCell` had no other caller and is gone.
- **The Diagnose section is one button**, between Hide/Show Terminal and Copy. Show data
  went with it, and so did the data block only that button could write
  (`cal_facts_text`, 52 lines) and the endpoint's loud branch.
- Six negative controls - the guard reading config again, an unclamped tok/char, the
  chips re-keyed by field name, the samplers dropped from the tick, the headroom put
  back above its title, the Reset button removed - each fail their own checks.

---

## v3.74 patch114
- **Measured on the glass, not reasoned about.** The screenshot says the server menu's
  box starts 9px below the setting menu's, and that the accent switch ends at x=678
  with the T of *Thinking* starting at x=679 - a flex `gap:10px` reading as zero. Two
  patches asked politely for both; this one removes the freedom.
- **The row's height is SET, not discovered.** `#dpane-tts .calrow .row` is 32px in
  every cell. Anything in a cell that comes out taller than the control re-centres that
  control inside it, which is exactly how the switch label's line box pushed the server
  menu down while its title stayed put. A row that cannot change height cannot move the
  menu in it, whatever the cell turns out to hold. The switch cell states `height:32px`
  too, rather than finding one.
- **The word stands clear of the switch by a margin** - `.swlab .sw { margin-right:14px }`
  - which applies whatever the label's `display` computes to. The flex `gap` it replaces
  does not, and that is why 10px arrived as 0px twice.
- Three negative controls - the row's height removed, the margin swapped back for a gap,
  the switch cell's height removed - each fail their own checks.

---

## v3.74 patch113
- **A width written against `select` never reached the box on screen.** Every
  `<select>` on this page is replaced at runtime by a `.selwrap` stand-in that
  carries the select's *classes* - and nothing else, not its inline style. patch112's
  caps and heights therefore sat on a hidden element while the stand-in sized itself
  to its own longest line: 546px of model name, which rode the Thinking switch and the
  Prompt button clean out of the card. The rules name the class both wear now
  (`.calsel`, `.setsel`, `.srvsel`), the way `.pctl` already did.
- **The server menu is 300px**, fixed, with the whole name in the opened list and dots
  where the closed box runs short. The setting menu fills its 250px cell exactly. The
  proxy speech-rate menu takes the same 300px, so the second column keeps one edge.
- **The Thinking switch sits inside the card**, and its cell is a flex box rather than
  an inline one: an inline-flex switch on a line of its own carries the line box's
  descender space with it, which made that cell taller than the setting cell beside it
  and dropped the server menu ~9px below the menu it lines up with. Both controls are
  32px in a 32px line now, so the two menus share a top edge - with the Server title
  where it was.
- **The Prompt buttons are gone**, from both rows. With them went the dialog branch
  they were the only way into, and the three prompt texts the endpoint sent for it -
  `deriveSystem`, `diagSystem`, `calSystem` - which nothing reads any more. The prompts
  themselves are untouched; they are still what gets sent. `ttsBtnCell` lost the `what`
  it can no longer be asked, and the Algorithm button under Proxy Algorithm stays.
- Four negative controls - the width written against `select` again, the switch back in
  an inline box, a menu sized inline, the dropped payload restored - each fail their
  own checks.

---

## v3.74 patch112
- **The calibration rows are fixed columns and a spring, not a middle cell that
  grows.** The server + thinking cell was `flex:1 1`, so every spare pixel the card
  had went into the server menu - which read as a fault, not a feature - and rode
  the Prompt cell out to the card's edge. Nothing in the row grows now: the setting
  cell is a fixed 250px, the server menu is capped at 320px, and one spring between
  the last setting and the Prompt button takes the surplus and collapses first when
  the card narrows. The row cannot overflow the card, whatever the model file is
  called. The proxy speech-rate menu takes the same cap, so the second column keeps
  one edge across modes as well as rows.
- **One height for every control in the row.** A select and a `.stop` button do not
  share one by default - the button carries borders the select does not - so both
  are pinned to `32px, border-box`. The thinking switch centres on that same line
  with its word held clear of the switch (`gap:10px`), and a name past the menu's
  cap ends in dots, with the whole name still in the opened list.
- **The setting menus fit their cells exactly.** The page-wide `select {
  min-width:260px }` floor was shoving a 260px control through a 250px cell, so the
  rows' columns never shared an edge. `min-width:0` inline frees the menus in these
  rows; every other select keeps the floor.
- **The Refit Interval slider sits UNDER its title**, in the title's own block,
  rather than beside it in a cell where it read as one more column of the row above.
- The row's rules live in a `.calrow` class the page carries once - where one height
  rule reaches every control - rather than in the function's inline style, and
  `ttsCalRow` lost the third cell that has carried nothing since patch111.
- Three negative controls - the menu regrown, the cells' shrink removed, the slider
  put back beside its title - each fail their own checks.

---

## v3.74 patch111
- **The Refit Interval is back under the Automatic Calibration menu**, as a setting
  of its own rather than a cell in the row. Its slider gets its old width back.
- **The menus were never going to line up: they were different controls.** The
  server picker wore `.tsel`, which trims the padding to `5px 26px 5px 9px` where the
  base select uses `7px 30px 7px 10px` - shorter, and sitting higher than the setting
  menu beside it. It is a plain select now, keeping only the `jobsrv` class the fill
  logic finds it by, so both cells are the same control at the same size.
- Both rows are now the same three cells - setting, server + thinking, Prompt - so
  Automatic Calibration and Sampler Calibration line up with each other as well as
  within themselves.
- **The thinking switch reads like a provider slot's**: `Thinking`, capitalised, and
  `.swlab` is `nowrap` so a narrow cell can no longer break the word onto a line under
  the switch, where it read as a caption rather than the switch's own label.
- **One reading, not three.** "no LLM fit kept yet" and "no fit has been attempted
  yet" are gone; `headroomLine()` puts the headroom, the fit under it and the last
  attempt in one sentence above the bars - the place the numbers they describe end
  up. The locals that built the old lines went with them.
- Titles are bold at the size they already had.
- 2127 checks.

---

## v3.74 patch110
- **One row per setting, whatever the choice brings with it.** `ttsCalRow` had a
  fixed `0 0 300px` middle cell and `flex-wrap:wrap`, so the server picker could not
  fit beside a 250px setting and dropped to a line of its own - where it stopped
  reading as part of the setting it belongs to. The row is `nowrap` now and every
  cell may shrink (`min-width:0`), including the `<select>` itself, which is the
  thing that refused to.
- LLM Controlled reads across: choice, server + thinking switch, refit interval,
  Prompt. Proxy Algorithm: choice, speech rate menu, Algorithm. Fixed: the choice
  alone. Sampler Calibration takes the same shape - choice, server + thinking,
  Prompt - with the cells empty under Manual.
- The refit interval and the speech rate menu moved INTO their rows rather than
  sitting under them, and the slider shrank to suit (`1 1 90px`, capped at 150).
- Readings moved the other way, under the row via `ttsCalNote`: the fit that was
  kept, the attempt that was made, the warning when no server is picked. They
  report; they do not set, and they were the reason the row had nowhere to go.
- **"Model" is "Server"**, matching the wired-server box on the same page.
- A negative control caught one of these checks passing when it should not have -
  it read the neighbourhood rather than the call, so removing the interval from the
  row left it green. It reads the call now.
- 2115 checks.

---

## v3.74 patch109
- **The calibration area is laid out like the Player Tag System rows**, with the same
  pieces in the same order: a titled setting, the model that carries it out with its
  thinking switch, and the button that shows what will be sent. `ttsCalRow` is that
  shape, used by both settings; `ttsJobCell` is the picker as a CELL rather than a
  full-width row, and the old `ttsJobRow` is removed rather than left orphaned.
- **Automatic Calibration**: Fixed / Proxy Algorithm / LLM Controlled. LLM Controlled
  brings the model, its thinking switch and a Prompt button; Proxy Algorithm brings
  the Algorithm button alone; Fixed brings neither. Proxy keeps its Speech Rate menu
  (measured here, or the LLM fit), LLM keeps its refit interval.
- **Sampler Calibration**: Manual / LLM Controlled, with the model cell and Prompt
  button filled only under LLM Controlled. The samplers themselves show under it
  either way - Manual means you move them, not that they stop being sent - and
  SkyrimNet pass-through and Steady Retry sit with them. The switch became a menu, so
  it saves as a field and its click handler is gone.
- **The headroom reading** moved out of the mode row to directly above the bars it
  explains, under a separator of its own, in white with a soft glow (`.headnow`)
  rather than as one more grey caption three settings away from its picture.
- **The grey explanation paragraphs are gone.** Every setting carries a white title
  with a `?` that explains it on hover, including what each menu choice does, and
  rules separate the groups of rows. The gate holds the absence as firmly as the
  presence: no `line-height:1.7` hint paragraph may return to either block.
- 2109 checks.

---

## v3.74 patch108
- **One calibration section.** The old TTS Calibration and Speech sampling sections
  fold into Automatic calibration, as asked. Order on the page: the calibration
  modes and fit, the failure-reading model picker directly below the fit picker
  (thinking switches beside each dropdown, as before), the sampler field, then
  Diagnose directly above the record it reads from and writes to.
- **The Auto Calibration button is a switch now: `Automatic sampler calibration`.**
  One switch, per the request: ON shows the sampler settings and makes the every-N
  automatic run also read the failures and change them - after the speech-rate fit,
  in the same idle window (a different failure-reading server gets its own idle
  wait). OFF hides the settings and stops the automation. **Stored sampler values
  keep applying to every line either way** - a display switch must not strip the
  user's settings from requests - and the page says so beside the switch. Ships
  OFF: automation is opted into.
- `autocal_sampler_run` is the one implementation - the old `api_tts_autocal_run`
  endpoint, the button, the Calibrate button and `api_tts_calibrate` are all gone.
  The diagnosis precedes the change by construction now (one function, DIAG then
  CAL), so the refuse-before-diagnosis guard and the disabled button had nothing
  left to guard. Sampler calibration still refuses to act when nothing has failed,
  still applies inside `cal_apply`'s bounds, and every way out writes one line to
  the calibration feed - the automatic caller has no page to show an error on.
- Pass-through of SkyrimNet's speech settings moved into the sampler field with the
  rest of the sampler controls.
- 2089 checks.

---

## v3.74 patch107
- **The cause, found by reading and explaining every prior symptom.** `renderTts`
  skips when `ttsPaneSig()` is unchanged, and the signature covered everything about
  the pane except `higgsInstall` and `higgsFound`. Pressing Install changed only
  those - signature identical, render declined. The poll (patch103-105) then found
  no row and asked `renderCurrent()` for it, which called `renderTts()` without
  force - declined again, every 700ms, forever. A refresh drew it because an empty
  pane always draws; the row then updated through `higgsPaint`'s direct writes until
  the next thing that removed it. Every one of patches 101-106 funnelled into that
  declining render.
- The signature now carries the SHAPE of both rows: running, done, error, warn,
  engine, model; adoptable, exe, model count. `pct` and `step` are deliberately
  excluded - they move every second and belong to `higgsPaint`'s in-place writes;
  in the signature they would turn the whole pane over once a second for two
  numbers, and the gate holds both the inclusion and the exclusion.
- The press also draws with `renderTts(true)`, so a future signature omission
  cannot swallow the running row a second time.
- Patches 101-106 stand: the missing state event, the gated reload, the mortal
  loop, the flag a dead loop kept, the silent unpack and the unmeasured-phase bar
  were all real - and all invisible behind this.
- 2076 checks.

---

## v3.74 patch106
- **The display was telling the truth; the installer had stopped talking.** Named
  precisely - it hangs at the press, and at "Unpacking ...zip into fast\", and is
  fine everywhere else - the two stalls line up exactly with the two stretches that
  report nothing. Four patches went into the page. The page was right.
- `_hi_unzip` ran silent from the first entry to the last. The CUDA archive takes
  long enough on a Windows disk with a scanner in the way to look like a dead panel.
  It now reports once a second - percent, files, MB - on the same cadence as the
  download and for the same reason, with a percentage of its own by uncompressed
  bytes. The bar restarts at 0 for it: unpacking is a phase, not a continuation of
  the download that preceded it.
- **A bar frozen at 0 is the same picture as a bar that has stopped.** From the press
  until the first download quotes a percentage - asking github for the release,
  clearing the engine folder - there is genuinely nothing to count. That now draws a
  moving striped bar (`higgsBarHtml`, one place, used by the row and by the live
  write) instead of an empty one.
- **Pressing Install draws the running row at once**, from what the page already
  knows, instead of waiting for a round trip to tell it something it asked for. That
  first phase has no number to report, so the old order left the Install button
  sitting there as though the press had done nothing.
- 2068 checks.

---

## v3.74 patch105
- **Two ways the loop could stop and never restart - both structural, both removed.**
  Four patches have each fixed a real fault and left the symptom; this one stops
  arguing about which mechanism fails and removes the ways any failure becomes
  permanent.
- **A bad tick was the last tick.** The reschedule sat at the bottom of the tick, so
  anything that threw on the way - and every version since patch103 could ask for a
  page redraw mid-tick - skipped it. It is in a `finally` now, and the whole tick is
  wrapped in a `catch` that traces and carries on. Nothing a tick does can end it
  except the install having stopped.
- **A dead loop held the place for good.** `window.__higgsT` was a bare flag: the
  loop set it, died, and left it set - so `load()`'s restart, added in patch103,
  found the flag and returned without starting anything. Only a page refresh cleared
  it, which is exactly the reported workaround. It is `__higgsBeat`, a timestamp
  renewed every tick; a claim older than three seconds is taken over.
- **The write could be going to a node nobody can see.** `getElementById` returns one
  node and cannot say whether it is still in the document - a pane rebuilt between
  the lookup and the write leaves a detached twin, and writing to that twin looks
  identical to not writing. `higgsPaint()` finds every `[data-higgs]` node fresh each
  tick, writes all of them, and reports how many were really on screen; none on
  screen asks for the pane through `renderCurrent()`.
- "(nothing new for Ns)" now appears from three seconds rather than five, so the
  liveness reading is visible sooner.
- 2055 checks.

---

## v3.74 patch104
- **The display stops; the install does not.** Three patches have chased this by
  reasoning about which mechanism failed - the event, the gate, the loop - and each
  time the fix addressed a real fault that was not the one being reported. This one
  stops relying on the mechanism being right.
- The poll still writes `higgs-step` and `higgs-bar` directly, as the quick path, but
  no longer depends on it. Every two seconds it redraws the whole pane through
  `renderCurrent()` - the same call a tab change makes, which is the one path that has
  worked throughout - and immediately rather than on the beat when the row cannot be
  found. A node addressed by id can be missing, stale, or the second copy of itself,
  and all three look identical from outside: the numbers stop.
- **A latent way the loop could still die.** patch103 ended it on any answer whose
  `running` was falsy - which includes an error body, a 403, or a panel without the
  endpoint, none of which mean the install finished. It now ends only on an answer
  that actually carries a `running` flag saying so.
- **The reading that was missing.** `HIGGS_INSTALL` records when it last changed and
  the endpoint returns `idle`, computed server-side off one clock. The step line shows
  "(nothing new for Ns)" past five seconds. If those seconds count up, the page is
  asking and the installer is quiet; if they sit still, the page has stopped asking.
  Three rounds went by without a way to tell those two apart.
- `higgsStepText()` composes that line once, for both the row and the poll.
- 2050 checks.

---

## v3.74 patch103
- **The bar ran for a few seconds after each refresh, then stopped.** patch102 gave
  the install its own poll, and then had that poll stop itself the moment
  `getElementById` came back empty for its two nodes. The TTS pane redraws on its own
  a few seconds after every page load - `ttsLoadModels` resolves and calls
  `renderTts()`, and during a 5 GB download into the model folder that scan is slow
  enough to be seconds - from a `state` that predates the install. One tick with the
  row absent and the loop was gone until the page was refreshed by hand. Exactly the
  reported shape: several seconds of movement, then nothing.
- The loop now ends for ONE reason: the install stopped. A missing row is a missed
  tick, not a reason to give up - and when the row is missing while an install runs,
  it asks for the redraw itself, through `renderCurrent()` so the one focus guard
  still applies rather than a second copy of it.
- `load()` restarts the loop whenever the state says an install is running. Starting
  it only from the row that draws it made the row and the loop depend on each other;
  now the thing that is known to run - a state load, which a refresh or a tab change
  performs - puts it back.
- `setInterval` replaced by a self-rescheduling `setTimeout`, so a slow answer cannot
  overlap the next ask, and the claim that stops a second loop starting is a flag
  rather than a timer handle nothing else can accidentally clear.
- 2038 checks.

---

## v3.74 patch102
- **The install bar still did not move, and patch101 was only half the answer.**
  Announcing the step was necessary; what the page does with an announcement is the
  other half. Every SSE event lands in `liveRefresh` → `queueLoad`, and a queued
  reload runs only when `uiBusy()` comes back empty - it re-queues itself otherwise.
  During an install something is always busy, so the reload was put off indefinitely
  and `state.higgsInstall` never reached the page. The terminal below kept scrolling
  because it has its own tail feed, and switching tabs "fixed" it because a tab
  change calls `load()` straight out, past the gate. **A progress bar cannot be
  gated on the panel being idle - being busy is the condition it exists to report.**
- `/api/higgs-progress`: one small GET that answers `HIGGS_INSTALL` and nothing else.
  No config read, no locks, host-only - a remote viewer cannot install, so it cannot
  watch one either.
- The running row carries `higgs-step` and `higgs-bar` ids and starts its own poll:
  every 0.7s it writes the step text and the bar width in place. No render, no
  queue, nothing to wait on. The timer is single (idempotent across redraws) and
  stops both when the install ends and when the row leaves the screen. When running
  goes false it reloads the state once, which is what turns the row into the
  finished, failed or cancelled one.
- Patch101's `state` event is kept: it costs nothing and other views of the same
  data are correct because of it.
- 2033 checks.

---

## v3.74 patch101
- **The Higgs install bar sat still while the install ran.** `_hi_log` wrote the
  step into `HIGGS_INSTALL` and called `TTSW.log`, which raises a `tail` event - that
  carries the terminals and nothing else. The bar and the step line above them are
  drawn from `state.higgsInstall`, which only arrives with a `state` event, so they
  showed whatever the page last loaded. Switching tabs or refreshing looked like a
  fix because both reload the state.
- An install step now raises both events. No throttle: the only caller that repeats
  is the download loop, which already limits itself to one line a second, and the
  notify is skipped entirely unless an install is actually running.
- **The switch under Speech sampling had no name** - only a sentence beside it that
  read as a description of nothing in particular. It is `Steady retry`: with it on,
  a retried line drops to a calmer sampler (temperature x0.8 with a floor of 0.1,
  `repetition_penalty` 1.0, `top_p` capped at 0.9) so the second attempt aims to
  finish rather than to perform. The player hears the retry, not the attempt that
  failed. Behaviour unchanged - it just says what it is now.
- 2019 checks.

---

## v3.74 patch100
- **The `<|channel>thought` leak is solved, from the config that was captured.**
  Slot 1 had `reasonfmt: "none"` — the server card dial Reasoning format, written
  into that launcher as `--reasoning-format none`. llama.cpp documents `none` as
  leaving thoughts unparsed in `message.content`; the other two servers were on
  `deepseek`, which puts them in `reasoning_content`, and were clean. The
  hand-written launcher used for the direct comparison carries no such flag, which
  is why the same model was clean when called directly. Deleting the config reset
  the dial to `auto` and the symptom went with it. Not corrupted - set.
- `PARAM_CAUTION`: a dial value can now carry a caution, keyed by VALUE rather than
  by setting, drawn as a ⚠ beside the dial standing on it. `reasonfmt: none` is the
  first: it says the thinking arrives as text and TTS will speak it, and what to use
  instead. The dial is not changed or restricted - reading a model raw is a
  legitimate thing to want.
- **The refit lost its place on every restart.** `AUTOCAL_GEN` counted from zero
  each time the panel came up, so with a long interval and a panel restarted often
  the fit could be due forever and never arrive: the lines had been spoken,
  measured and kept, and the one thing counting them had forgotten. It is now seeded
  once per run from `autocal_lines_since()` - the measurement log and the timestamp
  of the last attempt, both of which already survive a restart. No new per-line
  write.
- The interval is counted TO rather than by modulus. A running total tested with `%`
  skips a whole interval whenever the total is nudged - by the seed, or by moving
  the slider - and a decline now leaves the count due on the next line instead of
  costing another full interval.
- **"no LLM fit derived yet" was one sentence for three different problems**: never
  tried, could not run, and tried every N lines and refused every time for
  predicting worse than the panel's own least-squares fit. `autocal_note()` records
  what the last ATTEMPT came to, in the settings, on every path out of the fit; the
  page prints it under the refit row. The old line now reads "no LLM fit kept yet".
- Correction to patch99: the thinking that stopped working was provider Thinking
  switches left off after the config was reset, not the orphaned launcher line that
  patch99 reasoned from. The change itself stands on its own - asserting
  `enable_thinking: true` is right whatever the server default is - but the
  diagnosis attached to it was wrong, and gotcha 73 says so now.
- 2012 checks.

---

## v3.74 patch99
- **Patch97 reverted, whole.** It stopped the panel restating "do not think" to a
  server whose launcher already said `--reasoning off`, on a theory about Gemma 4's
  template branch that was never confirmed and fixed nothing - the fault went away
  when the config was deleted, so the cause was a persisted setting that is still
  unidentified. The OFF arm says it all three ways again, whatever the launcher
  says, exactly as patch38 through patch96 did. Both narrations went back with it.
- **Thinking ON does something now.** The ON arm only *removed* the off instruction
  and left the rest to the server. Absent is not "on" - it is "whatever that server
  defaults to", and the default is false in two cases: a launcher started
  `--reasoning off`, and a launcher carrying the Reasoning dial's own patch96 line,
  `--chat-template-kwargs '{"enable_thinking":false}'`.
- That line is written when the dial is set to off and removed only when it is set
  back to on, so a card whose setting was lost - a fresh config, an imported
  launcher - leaves it behind with nothing reading it. `parse_ps1_reasoning` looks
  at `--reasoning` alone, so the panel saw a server that could think, showed no
  warning, sent nothing, and the switch did nothing at all. That is the shape of
  "thinking stopped working entirely".
- Thinking ON now sends `enable_thinking: true` in the chat template kwarg, at the
  top level, and as `reasoning.enabled` - the same three forms the OFF arm writes.
  Checked against llama.cpp build 10219 (c629da565): a kwarg on the request
  overrides both `opt.chat_template_kwargs` from the command line and `--reasoning`,
  so this is the one place that can make the switch mean what it says. A `false`
  arriving from the client is overwritten rather than dropped.
- Two older checks encoded the old rule - "enable_thinking is present only when
  thinking is off" - and read the value on both arms now. One of them caught me
  writing the new check inverted.
- Still open: which persisted setting produced the `<|channel>thought` leak. Nothing
  in the config that was captured explains it, and it has not recurred since the
  reset.
- 1990 checks.

---

## v3.74 patch98
- **The automatic refit stopped running after a fresh config, and said nothing.**
  `autocal_tick` reads `ttsAutoCalPort`; with nothing stored it returned in
  silence. The picker hid that: it fills itself from the live servers and the fill
  read `sel.value || settings[key]`, so from the second refresh onward it displayed
  the first server whether or not one had ever been saved. The refit slider posts
  `ttsAutoCalEvery` on its own and does not save the picker, so setting an interval
  did not store one either. Diagnose and Auto Calibration kept working because they
  send the port from the page; only the automatic path reads the setting.
- The picker now fills from the store, never from itself, and offers
  `- pick a server -` until one is chosen. A stored port that is not among the live
  servers shows as unset without being erased - an unset picker saves nothing.
- The LLM block warns "no server picked - the refit cannot run" beside the interval,
  and `jobPort()` answers that question on the page by the same fall-back rule
  `tts_job_port` uses.
- A refit that is DUE and cannot run now writes the reason to the calibration feed:
  no server picked, or one already in flight. `autocal_derive`'s two guards - server
  not up, too few lines measured - logged nothing at all on the automatic path, so
  every way out of it writes exactly one record now, and the gate counts them.
- **The panel's own model calls appear in the Proxy terminal.** The fit, Diagnose,
  Calibrate and both halves of Auto Calibration called `_chat` straight: a server
  went busy for ten seconds with nothing in the record to say who asked. One wrapper,
  `panel_chat`, now carries all five through the same `PROXY.report` the proxy and
  PTI/PME use - tokens, prompt and decode speed, time - and they count in the server
  statistics, because the server did the work.
- `diag_route` takes a job name: Speech Fit, Diagnose, Calibrate, each with its own
  mark and its own id so a fit and a calibration are two records rather than one.
  Titles are 13 characters or fewer, which is what `proxy_line_text` pads the name
  column to. An unnamed job still reads as the diagnosis it used to be.
- No gate is held for them: PTI and PME hold one because they sit in front of a
  player waiting to hear a line, while these are asked after the idle wait finds a
  gap or by someone pressing a button.
- 1984 checks.

---

## v3.74 patch97
- **Server 1 spoke its scaffolding: `<|channel>thought` opened every Prosopon line.**
  Root cause, read against llama.cpp build 10219 (c629da565): the panel restated
  "do not think" inside every request to a server whose launcher already says
  `--reasoning off`. Gemma 4's template renders the no-think turn itself by
  prefilling an empty closed `<|channel>thought` / `<channel|>` pair into the
  prompt - and an `enable_thinking` key that is PRESENT takes a different template
  branch than one that is ABSENT. The restatement cost the prefill, the model wrote
  the ritual into its answer as text, and with reasoning off nothing server-side
  strips it, so TTS spoke "channel thought channel". A direct call - same launcher,
  no restatement - was clean, which pinned it to the request side.
- `apply_route_shape` now leaves a request EXACTLY as the client sent it when the
  route's server was launched with reasoning off: no kwarg, no top-level field, no
  `reasoning.enabled`, not even an empty `chat_template_kwargs` object. The launcher
  said it once; saying it twice was the bug. Injection is unchanged where it is
  needed - reasoning on or auto at the launcher with Thinking off on the provider -
  and a route missing `serverReasoning` degrades to injecting, never to silence.
  Slot pinning and Server Side sampler overrides still apply either way.
- Both narrations updated to match: the proxy listen line now reads "(reasoning off
  on the server: requests pass exactly as sent)" and the provider card's warning
  tooltip says the same instead of describing the old three-field send.
- Not the calibration or auto-sampler thinking toggles, and not a corrupted config:
  every one of those settings was off and `fleet-config.json` was clean. The
  injection has shipped since patch38; what changed lately was the slot 1 model -
  Versi-StyleTune's plain Gemma format had nothing to leak, Prosopon's Gemma 4
  channel format does.
- Standing caution, on purpose (gotcha 73): the patch96 dial line
  `--chat-template-kwargs '{"enable_thinking":false}'` makes the key PRESENT for
  every client of that server, direct calls included - the same broken branch. Do
  not write it for a Gemma 4 model; slot1.ps1 does not carry it today. Whether the
  dial should stop offering it, or write it per-template, is a scope call left
  open.
- 1949 checks.

---

## v3.74 patch96
- **The Reasoning dial writes the launcher too, as asked.** I was wrong that there was
  nothing to put there: llama.cpp has `--chat-template-kwargs`, which takes a JSON
  object and sets the default template kwargs for every request. Checked against
  `common/arg.cpp` - it logs that setting `enable_thinking` this way is deprecated and
  honours it regardless, and some models honour only that.
- Reasoning off now writes a second line beside `--reasoning off`, in the same
  paragraph rather than at the end of the array:
  `"--chat-template-kwargs", '{"enable_thinking":false}',`
- Single-quoted, because a JSON value cannot sit inside a double-quoted PowerShell
  string. `ps1_set_flag` matches the two quotings separately so it can still find,
  change and remove the line, and gained an `after=` argument so a new flag lands beside
  the one it belongs with.
- Turning Reasoning back on removes that line. A `--chat-template-kwargs` set for
  someone else's reasons is left alone - the dial only writes and removes the one it
  wrote. `CTK_FLAG`/`CTK_NO_THINK` are one constant pair, used by the generator and the
  in-place editor, so a fresh launcher and an edited one agree.
- Toggling it repeatedly leaves the file the same size.
- 1933 checks.

---

## v3.74 patch95
- **Visibility for patch94, which had none.** `enable_thinking` is a per-request field,
  not a launcher flag: `--reasoning off` is the only part of it a .ps1 can carry, so
  nothing further appears there however the dial is set. Verified against a real
  launcher - `slot_reasoning` reads `"--reasoning", "off"` correctly and is not fooled
  by `"--reasoning-format", "none"` on the line below it - and the route it produces
  does force `thinking` off for a provider whose own switch is on.
- The proxy now says so where it can be seen: `listening :1251 -> Dialogue  (reasoning
  off on the server: requests carry enable_thinking=false)`.
- The warning triangle already on the provider card now says what the panel actually
  sends, rather than only that the toggle cannot engage.
- 1924 checks.

---

## v3.74 patch94
- **Thinking off is now said three ways on every request:**
  `chat_template_kwargs.enable_thinking`, top-level `enable_thinking`, and
  `reasoning: {"enabled": false}` - the form SkyrimNet itself sends. Builds disagree
  about which they honour and none of them mind an extra. Still NOT
  `reasoning_budget_tokens: 0`, which means "stop thinking NOW" and returns a stub from
  any model that always opens a reasoning block. The thinking-on arm clears all three,
  so none can linger from a caller.
- **A server card set to Reasoning off now silences the request too.** `--reasoning off`
  tells the server; some models ignore it and only honour the per-request field. A slot
  set to off forces `thinking` off for every route on it - provider or panel - so the
  flag and the request cannot disagree about the same server. `slot_reasoning` caches
  against the launcher file's mtime, because that file sits on the PTI hot path.
- **The panel's two TTS jobs are chosen separately.** Fitting the speech rate and
  reading the failures are different questions, so each has its own server and its own
  thinking switch (`tts_job_port` / `tts_job_think`, `fit` and `calib`). Thinking is off
  by default for both: these are short questions with a strict answer shape, and a
  reasoning block in front of the answer is the commonest way one comes back unusable.
  An empty job borrows the other's server, so setting one picker still works.
- One row function draws both pickers and one handler serves both switches.
- 1922 checks.

---

## v3.74 patch93
- **The safety margin is not a setting any more.** No box, no `ttsAutoCalMargin`, and
  nothing reads one - so a value left in an old config cannot pin it either. It is
  learned, always. Three faults in how it was learned, all found in a real session:
- **1. It scored itself on lines where it was never in charge.** A short line is covered
  by the 128-token floor whatever the estimate said - `"Oh, great."` was estimated at 14
  tokens and used 34, a 2.44x "miss" that cost nothing and could not have. Only rows
  whose cap the estimate actually settled (`bound == "estimate"`) are scored now.
- **2. The record was made of survivors.** A line that ran past its cap produced no fit
  row at all, so the worst miss was computed from lines that finished - and read lowest
  exactly where lines were being lost. A runaway is now entered as `cap / est`: it
  needed *at least* that much. Losing a line widens the headroom, which is the direction
  that stops losing lines.
- **3. The model kept fitting a zero lead-in.** Ten fits running returned `lead 0.0`,
  which is physically wrong - there is a breath before the first word - and it is what
  made every short line read as a huge miss. `tts_measure_ols` now fits the same lines
  by least squares; that answer is given to the model as a starting point and used as
  the bar its reply must clear. A fit that predicts this machine worse than plain
  arithmetic (`tts_fit_mae`) is refused, not clamped, and the record says by how much.
- Measurements carry `bound` and `cap`; failures carry the `est` they missed. Without
  those two fields none of the above is computable.
- 1903 checks.

---

## v3.74 patch92
- **The per-line model call is gone.** LLM mode now differs from Proxy in exactly one
  thing - where the speech rate comes from - and a model is asked for that rate
  periodically, never for a line. Measured on identical input the per-line answer
  varied 14% with no new information in it, cost 351 ms median, and agreed with the
  fitted rate anyway. `TTS_AUTOCAL_LLM_SYSTEM` and `tts_autocal_llm_user` are deleted;
  `tts_auto_cap` no longer contains a `_chat` call at all, and the gate holds that.
- **The fit waits for an idle server.** `PROXY.busy(port)` is a count, not a guess: the
  panel forwards every request itself, so it increments on the way in and decrements on
  the same `finally` that already releases the GPU gate. `autocal_wait_idle` requires
  that count AND `TTSW._inflight` to be zero *before* calling - a call in flight cannot
  be taken back, which is exactly why the waiting is in front of it. If the server stays
  busy for ~2 minutes the fit is skipped, says so in the record, and the next tick tries
  again.
- **Auto Calibration**, one button beside the sampler chips: read the failures, say what
  they show, then change the settings they point at. Both model calls wait for a quiet
  server; values outside their bounds are refused rather than clamped; and it declines
  to run when nothing has failed yet, because there would be nothing to read and
  changing settings would be guessing.
- **The diagnosis now knows what moves the odds.** `DIAG_SYSTEM` states plainly that the
  token limit cannot change how often a line fails to stop - only what it costs - and
  points at `top_p 1.0` truncating nothing, `repetition_penalty` pushing away from the
  wind-down tokens, and chunk length. `cal_facts` carries the failure rate per sampler
  configuration and the sampler in force.
- **One server picker** for the page. There were three - the manual block's, LLM mode's,
  and the one Auto Calibration would have added - and all three always meant the same
  server.
- 1889 checks.

---

## v3.74 patch91
- **Speech sampling, on the TTS page, as chips.** temperature, top_p, min_p and
  repetition_penalty, drawn and edited exactly like a provider card's: accent and bold
  when set here, green when SkyrimNet's own value is passing through, dim when neither.
  One palette (`PSAMP_EMO`) serves both pages; its unused twin `SAMP_EMO` is deleted.
  Bounds come from `CAL_KNOBS`, the table that already held them.
- **The reason this matters, from the field test:** both runaways were short lines
  ending in a full stop, and one was the identical line that had just succeeded twelve
  times in the same minute. That is a draw inside the sampler, not a property of the
  text. The token cap only decides what a failure costs; the sampler decides how often
  there is one.
- **Every line now records the sampler it was spoken under** - `tts_measure_row` for
  lines that finished, `eoc_record` for lines that did not - and
  `tts_sampler_board` joins them into a failure rate per configuration, worst first, in
  the data block. Until now the sampler was the one variable never written down, so the
  question could not be answered at all. The comment claiming the engine would not
  accept sampling predated pass-through and is gone with it.
- **A retry no longer repeats the settings that just failed.** `tts_samplers(st,
  attempt)` is one rule for what a request carries: SkyrimNet's values, then anything
  set here, then - on attempt 2+ - cooler, `repetition_penalty` 1.0, nucleus truncated
  to 0.9. A retry only has to finish, and the retry is the take the player hears.
  Switchable, because it is the user's setting.
- **Fix: a runaway was recorded against the wrong cap.** Both the record and the line
  printed used `acpp_token_cap()` - the fixed guard - instead of the cap the request
  actually carried, so the field test showed "cap 227" for requests sent with 128. The
  record a calibration reads was holding a number no request ever used.
- The bars name the sampler each line was spoken under and mark retries; the
  calculation feed records it beside the cap. Scoring counts first attempts only - a
  retry runs a profile it was not chosen for.
- 1865 checks.

---

## v3.74 patch90
- **Fix: patch89 drew no bars at all.** Splitting the meter in two renamed
  `tts-meter-bar` to `-time` and `-tok`, and the early return at the top of
  `refreshTtsMeter` kept the old name. `$()` returning null is not an error, so it
  returned before painting on every tick: both bars empty, nothing logged, nothing
  thrown. My regression, in the patch that was meant to add the second bar.
- **The gate now cross-checks every `$("literal")` in the page against every
  `id="literal"` it creates**, allowing for ids finished by concatenation. Run against
  patch89 it names `tts-meter-bar` and nothing else. A second check confirms the meter
  guards on an id that exists and that `paintMeter` calls `paintMeterBar` for both
  views - markup is not paint, and patch89 had every element and drew into none of
  them.
- **Derive now is gone**, with its click handler, its endpoint
  (`/api/tts-autocal-derive`) and its route. Fitting is automatic in LLM mode on the
  slider, so a button doing the same thing by hand was a second way to do one thing.
  `autocal_tick` is the only caller of `autocal_derive` now.
- **Proxy mode no longer offers a server picker.** It asks nothing of a model by
  definition; the values it can read are made by LLM mode. One picker remains, in the
  one mode that talks to a model.
- 1837 checks.

---

## v3.74 patch89
- **Both bars at once.** Time above, tokens below, a rule between them, each with its
  own legend. The Time/Tokens toggle and its setting are gone - the two answer
  different questions and reading one asks the other.
- **Four modes became three: Off, Proxy, LLM.** `algo` was the proxy arithmetic and
  `median` was that same arithmetic reading an LLM-fitted rate - which is Proxy with a
  switch, not a mode. Both normalise to `proxy`, and `median` additionally implies the
  switch, so a config written by patch85-88 keeps doing exactly what it did. The page
  carries the same mapping and the gate checks the two agree.
- **Proxy can use what an LLM fitted** (`ttsAutoCalUseFit`): calibrate once with a
  model - run LLM for a while, or press Derive now - then switch to Proxy and have the
  arithmetic read those values instead of the raw measured median. Proxy still asks
  nothing of a model per line; that is the whole of what Proxy means, and the gate
  holds it.
- **LLM mode refits itself** every N lines, N on a 5-250 slider. The fit runs on its
  own thread - the line just spoken must never wait for a model - one at a time, and
  only when a server is picked. `autocal_derive` is one implementation called by both
  the button and the timer.
- The slider is driven from the input chain (label follows the drag) and the change
  chain (written once, on release). A range reaches neither the click chain nor, while
  dragging, the change chain - the same trap buttons fell into.
- Three faults the gate caught in this patch's own work: the server picker written out
  twice (now one `autoCalSrvRow`), a `data-act` left on the slider with no handler
  behind it, and a feed check still expecting the retired mode name.
- 1829 checks.

---

## v3.74 patch88
- **The flicker had a cause: `renderTts()` rebuilt the whole pane on every live tick.**
  That replaced the terminal element several times a minute - its text blanked until
  the next fetch, the height it had been dragged to reset, and the page flickered. The
  pane now carries a signature of everything it is drawn from and is redrawn only when
  that changes; the live parts (the feed, the bar) update in place. `ttsDiagLast` is
  deliberately outside the signature - it lands in the feed, and signing it would
  redraw the pane under the reader.
- **One terminal, one record.** The page kept its history twice: a log file AND a
  buffer inside the browser. Neither could show the other's lines in the right place
  and the buffer died on reload. Every line - per-line calculations, the data block,
  the diagnosis, and what a calibration changed - is written server-side to
  `<session>_ttscal.log`, and the page only tails it. `calTermText`, `calTermLine` and
  `ttsDiagLines` are gone; the data block is formatted where the data lives
  (`cal_facts_text`).
- The terminal starts **hidden** behind Show the record, remembered in settings, with
  its own Copy button.
- **Algorithm and Prompts open over the page** as a modal with Copy, using the existing
  `showModal` rather than a second overlay.
- **A live bar for where the last line went.** Time view: player tags, mood, token
  estimate, panel, then generate, codec, http + wav - panel work in warm colours,
  engine work in cool. Tokens view: used, headroom left unused, and the distance to
  the runaway guard. Each band is named with its value above the bar, click one and it
  explains itself, and the widths transition rather than jump. Fed by `/api/tts-meter`
  from the same numbers the spoken-line report prints.
- Fixed on the way: a lone CR introduced into the source (the encoding gate caught it),
  and three checks that had been asserting the browser buffer - the very design that
  caused the flicker they were written to guard against.
- 1787 checks.

---

## v3.74 patch87
- **Answered plainly: the token cap is a stop-loss, not a target.** Lowering the margin
  from 1.35 to 1.25 lowered the cap from ~160 to ~140 and changed nothing about the
  audio, because the engine stops when it emits its own end-of-content token - the cap
  never shortens a line. It decides two things only: what a runaway costs before the
  retry, and whether a line that genuinely needed more is cut off and generated again.
  A tighter cap is therefore not a better one, and no cap can reduce how OFTEN the
  model misses its stop token - chunk size and end punctuation are the levers on that,
  both already counted by the manual record.
- **So the headroom is learned, not typed.** `margin` is now `headroom` and defaults to
  `auto`: every measurement records the bare estimate that was in force, the fit is
  actual/estimated, and auto headroom is the worst miss this machine has produced x
  1.10, clamped 1.05-2.5, seeded at 1.35 until 8 fitted lines exist. A number typed in
  is still the user's and is obeyed exactly.
- **Every calculation is shown.** A feed of its own, `<session>_autocal.log`, painted
  by the same painter as the Proxy terminal in a new terminal on the TTS page: the
  record line carries mode, characters, pause seconds, estimate and cap, with the
  working as branches beneath - how the estimate was made, where the headroom came
  from, and which bound (estimate, floor or guard) decided the final number.
- **Algorithm and Prompts buttons**, read-only with Copy. The algorithm text is
  generated FROM the live constants, so it cannot drift from the code; the prompts
  returned are the same objects that are sent.
- **The spoken-line report itemises the panel's own time**: `prep: 291 ms (player tags
  274 + mood 6 + token estimate 12 + panel 9)`. The per-line LLM estimate runs inside
  the request builder, so it sat in the synthesis clock - it is taken out and named,
  the same fault patch86 fixed for the tagger. Each line also reports its fit: tokens
  used against tokens estimated, with the worst miss so far.
- Gate: two sections sandboxed - `tts_auto_cap` writes a log now, and the info endpoint
  loads config, so the gate was dirtying the tree it judges.
- 1762 checks.

---

## v3.74 patch86
- **The 25% "realtime regression" was an accounting fault, measured from the A/B logs:**
  base v3.74 overhead 7-15 ms per line; patch84 overhead 251-630 ms - and the patch84
  session shows 17 player-tagger calls at 0.27-0.60 s each, one per test line, that
  base does not have. The wall clock started at the top of the worker, so the tagger's
  model call (and every other panel step) was billed to "overhead (http + wav)" and
  read as the transport slowing down. GPU throughput was identical (~100 tps); the
  small server-time growth tracks the extra audio tokens the tags legitimately add.
- **The wall now splits at the POST.** Realtime is audio over SYNTHESIS - exactly what
  it measured before the tagger existed - and everything before the request is a
  `prep:` line with its biggest cost named: `prep: 285 ms (player tags 274 + panel 11)`.
  Recomputed over the patch84 test data, synthesis realtime is 3.9-4.1x - inside the
  4-5.5x band, matching base within noise.
- **A repeated line is tagged for free.** The tagger keeps its last 32 answers keyed by
  server, scene and line; SkyrimNet's TTS test repeats one line a dozen times and play
  repeats short barks. A hit costs nothing and logs `(cached)`. Failures are not
  cached - they retry.
- **The hot path parses no config files.** `load_config_cached()` answers from memory
  behind an mtime+size check, so an edit in the UI is seen on the very next line and a
  spoken line costs one stat instead of several full JSON parses. The signature is
  taken AFTER the load, because loading can itself save filled defaults.
- **The measurement record appends.** patch85 rewrote the whole 500-row list per line -
  O(n) on the hot path, growing with play. It is one appended JSONL line now, compacted
  every 128th append; the patch85 list is folded in and retired on first compaction.
- Third `cfg or load_config()` falsy trap fixed, in the tagger (gotcha 37).
- 1740 checks.

---

## v3.74 patch85
- **Answered first: the calibration record was not broken.** It records overrun EVENTS
  only, and exactly one had happened since it began - the session in hand shows twelve
  clean generations and none. What starved the diagnosis was that nothing recorded the
  lines that went RIGHT. Now every successful line is measured - characters, tags,
  pause seconds, spoken seconds - into `tts-measure.json` (500 kept), and the manual
  Diagnose sees it: `Measured lines: N, median X chars/s` joins the data block.
- **Automatic calibration, three ways, all inside the guard.** A new mode on the TTS
  page turns the measurements into a per-line token cap: `algo` (median measured
  chars-per-second, seed 15 until five lines exist, no LLM), `llm` (one small question
  per line against a chosen server, 3 s budget, algorithm fallback on any failure at
  all), `median` (Derive asks an LLM once to fit `{cps, lead}`; the proxy then applies
  it by arithmetic alone). Off is byte-identical to before. No mode ever exceeds the
  3.5 tok/char runaway guard or sinks below the 128-token lead-in floor; pause tags
  buy their silence; a fit outside 6-30 chars/s is refused, not kept. Each capped line
  logs what was chosen and why to the TTS terminal.
- A drifted copy caught by the gate itself: the new pause reader briefly declared a
  second `TTS_PAUSE_RX` beside the splicer's; the one existing pattern serves both.
- Two falsy-cfg traps fixed on the way (`cfg or load_config()` treats a caller's
  empty dict as absent - gotcha 37): one in the new code, one pre-existing in
  `live_llm_servers`, found when it silently loaded and SAVED a config into the gate
  tree.
- The overrun record's blind spot closed: a line failing all three attempts recorded
  attempts one and two and raised past the recorder on the third; the final failure
  is written now, unsettled.
- 1729 checks.

---

## v3.74 patch84
- **The two stages of an action pick read as one branch.** SkyrimNet first picks a
  broad category, then drills into it with a second prompt. The terminal showed them
  as two unrelated rows - and named the drilldown's actor `someone`, because that
  prompt names the character differently and the actor pattern only knew the main
  shape.
- Now the category row stays open and the drilldown closes the branch with the pick
  and its parameters, both under the character's real name:
  `|- ⚡ Serana > SNBaka_Expression` then `L- ⚡ Serana > Express (mood: surprised)`.
- The drilldown's record line wears the provider title with a drill mark
  (`ActionEval⤷`) - same colour, and `hasRecord` owns both shapes, so hiding the
  provider hides its drilldowns with it.
- The stage is read off the REQUEST, which introduces itself ("from a specific action
  category" / "A broader category was already identified"). It cannot be read off the
  reply: the prompt's own rule - a category answer must carry an `intent` parameter -
  is routinely ignored by the models, and param-less direct actions exist. Parse what
  models actually write.
- A drilldown answering `None` is written, because it closes a branch a category row
  opened; a main `None` stays silent as before.
- `action_row()` is the pure formatter and the gate holds it still: fixtures shaped
  like the real prompts pin the actor names, the stage detection, and both row shapes
  exactly. `action_line()` now returns the row it wrote, not just the action name.
- 1715 checks.

---

## v3.74 patch83
- Fix: **the Proxy terminal froze the moment an action row appeared** - patch82's fix
  was real, and underneath it sat a second patch73 fault with the same face.
  `ReferenceError: MG is not defined`: `MG` and `CY` are consts *inside* `paintThink`
  and `paintSpoken`, and the action-row block patch73 added to `paintTail` read them
  across scopes. The throw rejected the async refresh silently, `innerHTML` was never
  assigned, and every later paint died on the same line.
- Proven from the field before the fix: the session's `error_5.log` shows the first
  `MG is not defined` at 23:44:37 - the same second the first action line entered the
  dashboard tail. The freeze and its cause, timestamped to each other.
- The palette is one module-scope pair now, `SPK_MAG` and `SPK_CY`; both painters
  alias it and the action row reads it directly. One definition, nowhere to drift.
- Also: **`[]]` is an empty class in JavaScript.** It matches nothing, so `portRx`,
  `timeRx` and the `[type]` alternative of the launcher highlighter had never matched
  at all. A `]` outside a class is already the literal - all three are written bare
  now and fire for the first time: grey ports, cyan thinking stamps, highlighted
  `[type]` in the .ps1 editor.
- The gate gained a served-script sweep (node): it fails on a call to an undefined
  function or an ALL-CAPS constant read outside its scope. Run against patch73 it
  names exactly `refreshTails`, `MG` and `CY`; against patch82, `MG` and `CY`;
  against this patch, nothing. Two companions: no `RegExp` built from a string
  carrying a backslash, and no `[]]` class-closer anywhere in the page script.
- 1706 checks.

---

## v3.74 patch82
- Fix: **the Proxy and Split View terminals never updated.**
  `Invalid regular expression: /s(?:PTI|PME)s+[/: Unterminated character class` - thrown
  by `paintTail` on every paint, so `innerHTML` was never assigned.
- A backslash in the page script crosses **two** string layers: the Python literal that
  holds the page, and the JavaScript literal inside it. `"\\s"` therefore arrived as a
  bare `s` and `"\\["` as an unterminated character class. The pattern had been malformed
  since the filter was written, and it only ran when PTI or PME was off - which is the
  default, so it looked like the terminal breaking on its own.
- The filter uses **no regex at all** now. `hasRecord(line, title)` finds a record line
  with `indexOf`, which cannot be mangled by escaping and needs no escaper for a title
  holding a metacharacter - `rxEscape`, which existed only to feed those patterns, is
  gone with them.
- Found by rendering the real page in a browser and painting a real tail, which took one
  run. Three patches before it went into causes found by reading: a regex rebuilt per
  line, a second copy of the same, a row-joining rule. All three were real faults and
  none of them was this.
- 1709 checks.

---

## v3.74 patch81
- Fix: **the terminal was never stopping.** Everything after the first spliced spoken
  line was being joined onto the same row - `... (1.40x)Meta [1237] ...` - and that row
  then ran off to the right, past the edge of the pane. Nothing was missing; it was all
  on one line nobody could see.
- `joinLines` decided **per row** whether to add a newline: a spoken line was emitted
  without one, because the element it produces is block-level and breaks the row itself.
  When that assumption held it was invisible, and when it failed the row never broke.
  Sniffing the HTML to decide was the fragile part, so the decision is gone: every row is
  wrapped in a block of its own and there are no newlines between rows at all.
- An empty row keeps a minimum height, so the spacing the log was written with survives -
  including the blank rows the Row spacing setting adds.
- Two rounds were spent on the wrong cause before this. The report was "the terminal
  stops", the regex-per-line faults found on the way were real and worth fixing, and
  neither was this. The paste of the actual terminal contents is what showed it - the
  run-together is visible in the text and was never visible in the code.
- 1706 checks. Two negative controls, both caught.

---

## v3.74 patch80
- Fix: **the Proxy terminal ran for a few minutes and then stopped; Split View never
  started.** patch79 fixed the provider filter and missed its twin. `panelProvHidden`
  compiled two regexes for **every line** - and PTI and PME are off by default, so it ran
  for everybody whether or not a setting had ever been touched. The cost grows with the
  log, which is exactly the shape of the report: fine at first, gone later, and never
  working in Split View because that paints two panes.
- It is a matcher built once per refresh now, and when nothing is hidden the text is
  returned without a pass over it at all.
- Fix: the dashboard token painter compiled its splitter once per line as well. One
  pattern.
- The check for this is now positional rather than textual: every `RegExp` in the matcher
  must be constructed **before** the closure that runs per line. Rewriting the body to
  build one inside fails it - the first version of that check passed, because it was
  matching a brace that the rewrite happened not to use.
- 1703 checks. Three negative controls, all caught.

---

## v3.74 patch79
- Fix: **the Proxy and Split View terminals stopped showing anything.** patch73's provider
  filter built a fresh `RegExp` for every provider on every line, so a tail of a few
  thousand lines constructed tens of thousands of them on each refresh and the terminal
  could not keep up. One pattern is built per refresh now, outside the loop.
- Fix: **`refreshTails()` never existed.** It was called from the provider picker and the
  row-spacing control since patch73; the function is `refreshTail(which)`. Found by
  sweeping the page script for calls to names nothing declares - the Python side has had
  that check since patch43 and the JavaScript side had none.
- Fix: **pressing Diagnose cleared the terminal and showed nothing.** The handler called
  `load()` when the answer came back, which re-renders the pane and therefore replaces the
  terminal element. It no longer does, and the text is held outside the element as well,
  so a re-render for any other reason puts it back.
- Change: the calibration terminal resizes from its **bottom right** corner.
- Add: a running indicator while Diagnose or Calibrate is waiting - a chat against a cold
  model takes a while, and a button that looks idle is a button somebody presses twice.
- 1699 checks.

**Not in this patch, and next:** the two-column TTS page, the Thinking toggle for the
diagnosis server, and showing the two prompts.

---

## v3.74 patch78
- Change: **TTS Diagnostics, EOC Calibration and Diagnosis are one section - TTS
  Calibration** - sharing one terminal, which can be dragged larger from its bottom left
  corner. CSS only offers a bottom-right handle, so the wrapper is laid out right-to-left
  and the text put back the other way inside it.
- Change: **calibration is a decision, not a sweep.** It no longer speaks a test line at
  several chunk sizes. It hands the diagnosis and the data to the same server and asks
  what to change; whatever comes back is applied. The sweep measured one variable by
  spending minutes of speech, and the record already holds the same evidence from real
  play.
- **Diagnose must run first.** Calibration acts on what it found, and asking a model to
  choose settings with no diagnosis in front of it is asking it to guess. The button is
  disabled until one exists and the endpoint refuses regardless of the button.
- A returned value is applied only **inside its bounds**, and refused rather than clamped
  when outside: silently moving a number would report a setting nobody chose. Five knobs -
  chunk size, line time limit, temperature, top_p, repetition penalty - the last three
  applied as request overrides that win over SkyrimNet's own, because they were chosen
  against this machine's record.
- Change: the server list is **cards that could answer** - enabled, with a model selected -
  rather than only those currently serving. A card is a standing choice; a fleet restart
  should not empty the list. Each one's state is shown beside it.
- 1693 checks, up from 1706 - the sweep and its checks are gone. Five negative controls,
  all caught, including clamping a value instead of refusing it.

---

## v3.74 patch77
- Add: **Diagnosis**, under EOC Calibration. A dropdown of the user's own server cards,
  a Diagnose button and the written answer. What is sent: SkyrimNet's observed settings,
  whether they are being passed on, the chunk size and line time limit, the overrun
  record grouped by chunk size, and the rows from the last sweep - because none of those
  means much without the others.
- Only a server reporting **serving** is offered. One that is loading or wedged would
  fail after the wait rather than before it, which is the wrong end of a long sweep to
  discover it. An empty list says so rather than offering nothing silently.
- The panel speaks to it on an ordinary route - the same shape every provider uses, so
  it obeys the same thinking rule and invents no sampler of its own. The facts are
  bounded at 6000 characters, so a long record cannot fill a context and lose the
  question.
- The model is told to **say when the data supports no conclusion** rather than produce
  one. A diagnosis that always recommends something is worse than none.
- 1706 checks, up from 1690. Four negative controls, all caught.

---

## v3.74 patch76
- Add: **EOC Calibration**, in the TTS Diagnostics section. An editable line, a list of
  chunk sizes and a number of runs; it speaks the line at each size and reports overruns,
  a rate, and seconds per line, then names the size with the lowest rate.
- It speaks through `tts_acpp_speak` - the same path a game line takes, retry and cap
  included - and splits with `tts_chunks`, because a calibration on a different path
  would measure a different thing.
- The report gives a **rate**, not a raw count: a smaller chunk size speaks more lines
  from the same text, so counts are not comparable and would favour the largest size
  every time. When nothing fails it says so rather than naming a winner from noise.
- Fix: **the seed was displayed wrong.** SkyrimNet sends `701521338218674266`; the panel
  showed `701521338218674300`, because JavaScript holds 53 bits of integer and that is
  64. It travels as text now. A wrong seed is worse than none when the reason to read it
  is to pin it - which is what makes an overrun reproducible.
- Sizes outside 40-400 are refused rather than silently clamped: a calibration that
  quietly measured something other than what was asked for would be worse than an error.
- 1690 checks, up from 1676. Four negative controls, all caught - two of which passed on
  the first attempt, because both checks were reading a variable name rather than the
  arithmetic behind it.

---

## v3.74 patch75
- Fix: **the pass-through setting had no control.** patch74 added `ttsPassThrough`, wired
  it into the request and reported it in the diagnostics as "passed to the engine: yes" -
  and never put a switch anywhere, so it could be read and not changed.
- It is a `select` in the TTS Diagnostics section, beside the sentence explaining what it
  does, rather than three sections away. It could not have been a fieldset row: a list in
  that table is a FILE EXTENSION filter, so `["on", "off"]` would have drawn a file
  picker - which is what an earlier attempt at a two-value row would have done had it
  survived to ship.
- 1676 checks, up from 1672.

**Where the recent additions live**, since they are spread across two pages:
- TTS page: `TTS Backend Settings` (Chunk Size, Line Time Limit) between Audio Files and
  Ports & Naming, and `TTS Diagnostics` at the foot.
- Terminals page, Proxy terminal: `Providers` beside Options, and `Row spacing` inside
  Adjust.

---

## v3.74 patch74
- Fix: **SkyrimNet's TTS sliders were doing nothing.** It sends its whole Chatterbox
  parameter set with every spoken line - the panel received all of it, read the text and
  the reference, and discarded the rest before calling audio.cpp. A temperature set on
  that page reached nothing and the engine used its own defaults.
- The positions are matched against a rendered page rather than guessed: Pace 0.35,
  Top P 1.00, Min P 0.05, Temperature 0.80, Repetition Penalty 1.20, Expressiveness 0.50,
  Seed -1, and the seed actually drawn - which changes every line, and is why a retry
  after an overrun almost always succeeds.
- `temperature`, `top_p`, `min_p` and `repetition_penalty` are forwarded; the request path
  ignores a name it does not know, so a value is either honoured or dropped and never
  fatal. Pace and expressiveness have no counterpart and are observed only. On by
  default: these are the user's own settings and discarding them is what made them inert.
- Position is all a Gradio call gives, so every value is range-checked and a call of
  another shape produces nothing rather than nonsense. A boolean is not read as a number,
  which in Python it otherwise would be.
- Add: **TTS Diagnostics**, a section of its own on the TTS page. What SkyrimNet is
  asking for, whether it is being passed on, the panel settings that bear on it, and the
  overrun record grouped by chunk size and by whether the line ended on punctuation. Read
  only, with a Refresh - it answers a different question from the settings above it.
- 1672 checks, up from 1645. Five negative controls, all caught, including shifting one
  index by two.

---

## v3.74 patch73
- Add: **Providers**, a button on the Proxy terminal. Every provider is drawn by its own
  mark and lit in the accent colour when its lines are shown; clicking one drops its
  record lines from the terminal. Stored as the providers turned OFF, so one added later
  appears without anybody having to go and enable it. Titles are regex-escaped, since a
  provider may legitimately be called something with a bracket in it.
- Add: **Row spacing** in Adjust - none, one, two or three blank rows between records -
  on the Proxy terminal only, because the others are prose rather than records. A blank
  row never gains more blank rows. It is a `select`, so it is read on **change**: a button
  belongs in the click chain and a select does not, which this project has paid for once
  already.
- Change: an action line reads as who and what - the character in magenta, as a speaker
  is, and the action in cyan, as a tag is.
- 1645 checks, up from 1627.

---

## v3.74 patch72
- Add: **every argument SkyrimNet sends with a spoken line is recorded**, once per
  request, in `panel.log` - `[tts] fields: [0] 'en-us' [1] 'a line...' [2] 0.8 [3]
  dict{orig_name,path} [4] 50 [5] true`.
- `tts_pick_fields` reads two of those arguments - the text and the reference - and
  discards the rest unread. If SkyrimNet exposes TTS settings of its own, that list is
  where their values are, and nothing in the panel would ever have shown them. A Gradio
  call is positional, so the only way to learn what is in it is to look.
- The reference is summarised by its keys rather than printed: it carries a file path and
  sometimes base64 audio, and neither belongs in a log line. Positions are kept for empty
  arguments so the indices mean something.
- This matters because the two paths into audio.cpp behave differently, and both are now
  established: the CONFIG validates and exits on an unknown key (patch69), while the
  REQUEST ignores one (patch60 sent three token-cap spellings and the server never
  complained). Per-request parameters may therefore work where config-level ones could
  not - but only for names that exist, which is what this is for.
- 1627 checks, up from 1619. Four negative controls, all caught.

---

## v3.74 patch71
- Removed: **the TTS backend sampling controls.** audio.cpp validates its session option
  list and exits on anything not on it; `reference_cache_slots` is the only name this
  family takes. Temperature, top-k, top-p, repetition penalty, sampling rate and max audio
  tokens are gone, along with the Settings Owner choice, the refused-option learner and
  `acpp_sampling`. patch68 tried to set them, patch69 made the attempt survivable - an
  engine that will not be told is not a setting, and a control that cannot reach anything
  is worse than no control.
- Add: **Chunk Size**, the one lever the panel still owns. Every token generated is
  another chance to pass over end-of-content, so a shorter chunk overruns less often and
  costs less when it does. 170 by default, exactly what was hardcoded, clamped to 40-400.
- Change: **the EOC record measures what can be varied.** Each event now carries the chunk
  size in force, whether the line ended on punctuation, and how many performance tags it
  carried - and the summary groups by chunk size, bands the failures by length, and counts
  open endings apart. Recording a sampling figure nobody can change made every group
  identical and said nothing.
- 1619 checks. Four negative controls, all caught - including putting a sampling option
  back into the server config, which is the thing that stopped the server starting.

**Next:** EOC Diagnostics - the test prompt, the data view, the attached server for a
written report, and Calibrate, which now has a real thing to sweep.

---

## v3.74 patch70
- Fix: **changing the model on a server card did not reach a hand-written launcher.**
  The samplers and runtimes did, because they are `SERVER_PARAMS` rows and the edit set is
  built from that table - and the model is not in it, since `build_param_launcher` writes
  it itself. It was therefore never in the set of flags an in-place edit writes.
- The model is also usually reached through a variable: `"-m", $modelPath`, with the rest
  of the launcher printing `$modelPath` in its own report. `ps1_set_path` rewrites the
  **assignment** rather than the flag, so everything else reading that variable still
  agrees with what is loaded. A launcher that names the file directly is edited directly.
- Add: **Actions**, in the terminal Options panel, off by default. ActionEval answers
  under a json_schema - `{"ACTION": "bathe"}` - and its prompt names the actor in a
  profile heading rather than the way a dialogue prompt does. The line reads
  `Serana > bathe`, under a mark of its own.
- The actor is read but **not fed to the speaker queue**. That queue pairs a voice with a
  spoken line, and an action produces no speech - putting this name in it would land it on
  somebody else's voice, which is the bug patch53 fixed.
- `"None"` is not reported. It is the schema's way of saying nothing was chosen and by far
  the commonest answer; a line per turn saying so would bury the ones that matter.
- 1634 checks, up from 1619. Five negative controls, all caught.

---

## v3.74 patch69
- Fix: **the TTS server would not start on patch68.** `audiocpp_server failed: unknown
  Higgs TTS session option: higgs_audio_tts.temperature`. audio.cpp VALIDATES its session
  options and exits on one it does not recognise - patch68 was built on the assumption
  that an unknown key would be ignored, which is what an unknown key on the REQUEST does
  and is not what the config does.
- Add: **Settings Owner** - `SN Side` or `Proxy Side` - defaulting to SN Side, which
  writes nothing but `reference_cache_slots` and is exactly the behaviour that worked
  before patch68. Only Proxy Side hands the backend to the panel.
- Add: **the panel learns a refused option from the server's own words.** The failure
  names the offender, so a start that dies is read back, the name is remembered in
  `ttsAcppBadOpts`, and the start is retried once without it. Guessing a replacement name
  is what caused this; asking the server is not. A wrong name now costs a second rather
  than a working server, and it is never sent again.
- Add: **Sampling Rate**, 8000-48000, defaulting to the engine's own 24000.
- 1619 checks, up from 1610. Five negative controls, all caught - including reinstating
  the exact breakage, which fails the check that SkyrimNet's side is left alone.

---

## v3.74 patch68
- Add: **TTS Backend Settings** on the TTS page - temperature, top-k, top-p, repetition
  penalty and max audio tokens per line, written into audio.cpp's `session_options`
  beside `reference_cache_slots`. Namespaced by the `ttsAcppFamily` setting rather than a
  literal, so a build that renames the family keeps working.
- This is the first change that addresses the CAUSE. A missed end-of-content token is a
  sampling accident: the model passes over EOC and then has nothing telling it to stop.
  Temperature decides how often that happens. patch60 and patch67 both changed a ceiling,
  which only decides what each occurrence costs.
- Defaults are the model card's own for voice cloning - temperature 0.8, top_k 50,
  max_new_tokens 1024 - so out of the box nothing changes. Values are clamped, so a typo
  is corrected rather than handed to a server that would refuse it or babble.
- Add: **a persistent record.** Every overrun appends to `eoc-events.json` - the line, its
  length, the cap, what it cost, which attempt, and the sampling in force - and the file
  survives restarts. `eoc_summary()` groups by those settings, commonest first, so two
  temperatures can be compared without arithmetic. Written atomically, and failure to
  write is swallowed: a diagnostic must never break the line it describes.
- 1610 checks, up from 1581. Five negative controls, all caught.

**Not yet built, and next:** the EOC Diagnostics block itself - test prompt, a view of the
collected data, a server to attach for the written report, and Calibrate. All three need
data that did not exist until this patch and cannot be back-filled, which is why the
record ships first.

---

## v3.74 patch67
- Fix: **an overrun cost eighteen seconds because the request-level cap is ignored.**
  patch60 sent `max_new_tokens` and the failed line still ran 18.15s - against
  `busy_timeout_ms: 20000`, which the panel writes into audio.cpp's own `server.json` and
  which was the only bound actually stopping it. The token cap was never biting.
- Change: that timeout is a setting - **Line Time Limit**, on the TTS page - defaulting
  to **9000 ms** rather than the 20000 that was hardcoded. The longest chunk the panel
  sends is 170 characters, about 15 seconds of speech, and Higgs generates well above
  realtime when it is behaving: the slowest good line in the logs took 4.6s. Nine seconds
  leaves room for a legitimate long line and takes half the cost off a runaway. Clamped
  to 2-60 seconds, so a typo cannot make the server unusable.
- Change: the cap is now sent as `max_new_tokens`, `max_tokens` **and**
  `session_options["higgs_audio_tts.max_new_tokens"]`. A build that reads none of them
  ignores all three, which is exactly why the timeout is the bound that has to work - but
  if any name is right, the cost drops further.
- Change: a failed attempt is **timed**, and says so - `18.2s lost (cap 128 tokens, server
  limit 9000)`. Which bound bit is now readable instead of inferred, which is how this
  took two patches.
- 1581 checks, up from 1568. Four negative controls, all caught.

---

## v3.74 patch66
- Change: **all twenty-one emotions are offered again.** patch55 cut the list to the
  fourteen SkyrimNet's template named at the time; the template now lists every one Higgs
  has. That matters beyond parity - without anger, fear and disgust an aggressive line
  cannot be labelled at all, which is what produced the mislabelled examples in both
  versions of that file.
- Change: **prosody is written bare** - `[speed_slow]`, `[pause]`, `[pitch_high]` - rather
  than `PROSODY-SPEED_SLOW`, because that is how SkyrimNet's template teaches it. Both
  forms translate; only one of them matches what the dialogue models are being shown, and
  the point of the notation change in patch56 was that a marked-up player line and a
  marked-up NPC line should be indistinguishable. Emotions, styles and sounds keep their
  prefix, as the template writes them.
- Change: the placement rule follows the template - an emotion, style or prosody tag at
  the start of the sentence it applies to; a sound or a pause exactly where it happens.
- The engine side needed nothing. Every one of the template's tags already translates,
  in both the prefixed and the bare form, and `[pause]` mid-line becomes
  `<|prosody:pause|>` - a LEADING pause is dropped on purpose, since silence before the
  first word does nothing.
- 1568 checks, up from 1544. Three negative controls, all caught.

---

## v3.74 patch65
- Add: **tags with no Higgs counterpart are named when they are removed.** SkyrimNet's
  chatterbox vocabulary is wider in places - `[sarcastic]`, `[gasp]`, `[groan]`,
  `[shush]`, `[narration]` have nowhere to go. They were dropped so they would not be
  read aloud, which is right, and silently, which meant a model spending words on a tag
  that never arrives looked exactly like a tag that worked.
- Add: a check that **every tag in SkyrimNet's chatterbox list either translates or is
  dropped** - eighteen of them, asserted one by one. One falling through would be spoken
  aloud as words in the middle of a line.
- No translation change was needed. The panel already maps the whole chatterbox
  vocabulary onto Higgs: `[angry]` to `<|emotion:anger|>`, `[chuckle]` to
  `<|sfx:laughter|>Hehe,`, `[clear throat]` to `<|sfx:cough|>Ahem,`, and so on.
- 1544 checks, up from 1521.

---

## v3.74 patch64
- Add: **the raw incoming line is recorded**, in `panel.log`, before `tts_normalize`,
  before the tagger and before `tts_apply_tags` - `[tts] in: ...`, truncated at 200
  characters.
- This exists because the previous patch answered the wrong question. NPC lines were
  arriving without their performance tags, the terminal shows only the PROCESSED line,
  and a tag stripped by the panel is indistinguishable there from one that was never
  sent. The whole path has since been traced - `tts_pick_fields` takes the field
  untouched, `tts_normalize` only collapses whitespace and punctuates, and
  `tts_apply_tags` translates correctly when given the real reply - so nothing here
  removes them while Audio Tags is on. The one thing missing was evidence of what
  arrives, and that is now written down.
- 1521 checks, up from 1519.

---

## v3.74 patch63
- Add: **a line about to lose its performance tags says so.** `Audio Tags` defaults to
  "Strip them - speak the words only", and `tts_player_tag` sets `keep_tags = True` for
  the line it marked up itself - deliberately, so a tag the panel arranged is not thrown
  away by a different setting. The result is that the player is heard with feeling while
  every NPC line arrives flat, and nothing anywhere says why. The TTS terminal now reports
  `2 performance tags removed - Audio Tags is set to strip them (TTS page)`.
- The count uses `TTS_CAPS_RX`, so it counts tags and not brackets: a line that says
  `Meet me at [the mill] tonight` reports none.
- The translator is undamaged and this patch does not change it. Given the reported NPC
  line it produces `<|emotion:sadness|>...<|sfx:sigh|>Ahh, ...` with the setting on, and
  the bare words with it off. **Nothing regressed - the switch was off.**
- The default is left alone. Turning it on because the panel now asks SkyrimNet's models
  for these tags would be deriving one setting from another, which is gotcha 36.
- 1519 checks, up from 1510. Three negative controls, all caught.

---

## v3.74 patch62
- Change: **the Options panel blurs what is behind it** - `backdrop-filter: blur(2px)`,
  with the `-webkit-` form for older engines. It hangs over the terminal, so what is
  behind it is log text, and the flat `var(--pan)` fill read as a hole punched in the
  feed.
- The fill becomes `rgba(4, 6, 9, .55)`. An opaque background leaves `backdrop-filter`
  nothing to work through, so the blur would have had no visible effect at all - the same
  translucency the Adjust popovers already use, at 4px.
- One rule, so it applies to the Proxy terminal's panel and to both split panes' at once.
- 1510 checks, up from 1506. Three negative controls, all caught - including making the
  fill opaque again, which leaves the declaration in place and the effect invisible.

---

## v3.74 patch61
- Change: **each split pane has its own Options button**, in the top right of that pane's
  own terminal, exactly where the Proxy terminal has it. Timestamps and Insert TTS move
  inside it, along with PTI Output, PME Output and Thoughts.
- It appears only while that pane is showing the **Proxy** feed and goes when the pane is
  switched to something else - everything behind it is a proxy-feed thing: the spliced
  spoken line, the tagger's answer, an NPC's thought. Timestamps travels with it and
  carries that pane's own kind, `splitd` or `splitt`, so the two panes keep separate
  settings.
- A pane whose Options menu is open when it is switched away has the menu closed with the
  button; leaving it open would have left a panel hanging under a button that is no
  longer there.
- The single Options panel patch59 put on the split view's outer bar is removed. It
  switched things for "these terminals" when the switches belong to whichever pane is
  showing the feed.
- 1506 checks, up from 1498. Three negative controls, all caught.

---

## v3.74 patch60
- Fix: **an overrun cost nineteen seconds.** Higgs sometimes runs past its own
  end-of-content token; that is upstream, it is sampled, and the retry usually succeeds.
  What the panel controls is what the failure costs - and it was sending no length limit
  at all, so a runaway generated until audio.cpp's own default. Measured from the log: a
  4.2 second line took 19.01 seconds, 0.22x realtime.
- Each request now carries `max_new_tokens` sized to the line: 3.5 tokens per character
  with a floor of 128. Higgs emits about 25 audio tokens per second and speech runs at
  about 15 characters per second, so a line needs roughly 2.3 tokens per character -
  measured exactly on the failing line, 46 characters and 104 tokens. The cap is therefore
  about **half again more than any real line needs** and cannot truncate one, while
  turning a 19 second runaway into roughly 6.
- The retry also recognises an overrun reported as `EOC` rather than `max_tokens`, since
  a capped run may word it differently.
- Two things this does not do, and should be said plainly: it does not stop the model
  overrunning, and a build that does not know `max_new_tokens` will ignore the field and
  nothing will change. The timing in the TTS terminal says which happened within one line.
- 1498 checks, up from 1490. Four negative controls, all caught.

---

## v3.74 patch59
- Fix: **the tagger put every tag at the end of the line.** The compressed prompt said
  "put each where it starts - not all at the front", and the model read the second half
  and answered `if you say so. [PROSODY-SPEED_SLOW]`. It now says what SkyrimNet's own
  prompt says: an EMOTION or STYLE tag goes at the START of the sentence it applies to,
  never at the end of the line; an SFX or PROSODY tag goes exactly where it happens.
- Add: `PROSODY-PAUSE` and `PROSODY-LONG_PAUSE`. They were held back as "not a writer's
  decision", which is backwards - a beat is placed, not felt - and the engine renders
  both. Every audio tag Higgs has is now offered: 22.
- Fix: **a thought was labelled `thought:` instead of the character.** It read the name
  off the shared pending-name queue, which a spoken line arriving in between can empty.
  `note_speaker` returns the name it found, and the reply is attributed to the character
  whose request produced it - no queue involved.
- Fix: **no gap after the colon on a switched-on button.** The button is a flex row and a
  flex item trims the whitespace at its own end, so `Insert TTS: ` lost its space the
  moment the value became a `<span>`, while `Timestamps: Off` - one text node - kept it.
  A non-breaking space instead.
- Change: **PME counts NPC lines globally.** The tagger no longer resets the count. In a
  back-and-forth the reset landed before the count reached N, so any setting above 1 read
  the scene almost never - which was flagged when it was built and is now removed.
  `every=3` over nine lines: `..Y..Y..Y`.
- Change: the split view terminal gains its own Options button with the same switches,
  and moves to the end of the row after PTI / PME.
- 1490 checks, up from 1487.

---

## v3.74 patch58
- Change: **the thought is placed above the spoken lines, not below.** It was written the
  moment the reply landed, and `spliceTts` then inserted the spoken lines directly under
  the dialogue completion - on top of it. The splice now steps past any thought already
  hanging off that reply. The character thought it before they opened their mouth, and it
  reads that way round.
- Fix: **a wrapped thought had nothing joining its rows.** It was drawn with the closing
  elbow, whose upright stops at its own row by design - correct for the last branch, and
  it was the last branch only because it was in the wrong place. Now that the spoken lines
  follow it, a thought is always a mid branch, and its upright carries down through every
  wrapped row and on to the lines below. `thought_lines` cannot produce an end elbow at
  all, which the gate checks.
- Change: a thought is painted **grape** with a faint glow rather than the gold of speech,
  so an interior line is distinguishable from a spoken one at a glance.
- Change: server card group headings are **white**, separated by the same gradient rule
  the TTS page draws between its blocks rather than a flat border.
- 1487 checks, up from 1477. Four negative controls, all caught.

---

## v3.74 patch57
- Add: **Thoughts**, in the terminal Options panel, off by default. SkyrimNet asks each
  character to end a reply with `<internal_thought>...</internal_thought>` - "put the
  thought last, after and below your spoken line" - and it is never spoken, so it never
  reaches the TTS record. The reply on its way through the proxy is the only place to
  catch it.
- Written the moment the reply lands, so it sits **above** the spoken line Insert TTS
  splices in afterwards - which is where a thought belongs, since the character had it
  before they opened their mouth. Same branch glyphs as every other line the panel adds,
  under a thought bubble rather than a spoken mark, with the tag itself stripped.
- The proxy now keeps the reply text as well as the reasoning. It kept only
  `delta.reasoning_content` from a stream and threw the content away; both arms hand the
  reply to `report` now.
- The speaker name is **peeked at, never consumed** - the spoken line still needs it, and
  taking it here would have put the next character's name on this one. That is one of the
  negative controls.
- 1477 checks, up from 1460. Four negative controls, all caught.

---

## v3.74 patch56
- Change: **PTI and PME use SkyrimNet's categorised notation.** Tags are offered and
  answered as `KIND-NAME` - `[EMOTION-SURPRISE]`, `[SFX-LAUGHTER]`, `[STYLE-WHISPERING]`,
  `[PROSODY-PITCH_LOW]` - instead of the panel's own shorthand `[sad]`, `[laugh]`,
  `[whisper]`. A player's line came back marked up in one notation while every NPC line
  around it used another; they are the same now, and `TTS_CAPS_RX` already read this form,
  so one matcher covers both.
- Every tag now states its kind, which is the point of the change: the model can no longer
  read an emotion as a sound. The worked examples are rewritten in the same notation -
  `[SFX-LAUGHTER] Haha! [EMOTION-CONTENTMENT] Of course you would say that.`
- `_build_offer` no longer picks the shortest alias per tag; the name comes straight from
  `TTS_TAGS` with its kind. Answers are matched case-insensitively and normalised to
  upper case, so `[emotion-contentment]` is accepted and stored as
  `[EMOTION-CONTENTMENT]`. PME accepts a bare `contentment` too and returns it in the same
  form.
- **This costs prompt length**: 908 characters to 1209, because `EMOTION-CONTEMPLATION`
  is four times the size of `sad`. Still well under the 1994 it was two patches ago, but
  it is a real 33% back.
- 1460 checks. Twenty-three of them pinned the old notation and were rewritten rather than
  loosened; one - "taking the shortest accepted spelling of each" - was deleted, because
  the mechanism it tested no longer exists.

---

## v3.74 patch55
- Change: **PTI and PME are offered fourteen emotions, not twenty-one.** The list is the
  one in SkyrimNet's own Voice Performance Tags prompt - affection, arousal, awe,
  confusion, contemplation, contentment, enthusiasm, helplessness, longing, pride, relief,
  sadness, shame, surprise - because those are what its dialogue models are taught to
  write and what comes back sounding like something. All fourteen map onto real Higgs tag
  names, so nothing is asked for that the engine cannot render.
- Dropped from what the panel asks for: anger, amusement, bitterness, determination,
  disgust, elation, fear. The prompt is 908 characters, from 975.
- **What the panel ACCEPTS is untouched.** `tts_apply_tags` still translates every tag
  SkyrimNet writes into an NPC line, including the seven above - narrowing what we ask
  for must not narrow what we take, or dialogue quietly loses its delivery. The gate
  checks `[EMOTION-ANGER]` and `[EMOTION-DETERMINATION]` still reach the engine.
- One switch does all of it: `_EMOTION_OFFER` filters `_build_offer`, so the tagger
  prompt, the reader prompt, PTI's answer validation and PME's vocabulary all narrow
  together and cannot disagree.
- 1467 checks, up from 1440. Three negative controls, all caught.

---

## v3.74 patch54
- Change: **the server card lays its parameters out in labelled groups**, with a rule
  above each - GPU, Context and cache, Batching and concurrency, CPU, Generation - in the
  order `PARAM_GROUP_ORDER` gives, which is the order the launcher writes them in. A
  heading on the card therefore names a block of flags you can find in the `.ps1`.
- The order comes from that table rather than from the position of a row in
  `SERVER_PARAMS`, because the two do not agree: `fit` is a GPU flag and sits among the
  batching ones. The gate asserts every parameter lands in a group, so a new one cannot
  quietly go missing from the card.
- Removed a duplicate `PARAM_GROUP_ORDER`. There was already one, with Model, Server and
  Logging in it; the second one I added silently won by being defined later. The gate now
  asserts it is stated once.
- Change: **Timestamps, Insert TTS, PTI Output and PME Output move behind one Options
  button** in the Proxy terminal, in a panel of their own beside Adjust. Opening either
  closes the other.
- 1440 checks, up from 1414. Four negative controls, all caught.

---

## v3.74 patch53
- Fix: **two NPCs speaking in quick succession swapped names.** Pending speaker names were
  consumed newest-first, but spoken lines arrive in the order their dialogue was
  generated - so the first line took the second character's name and vice versa. It is a
  queue, not a stack. Measured: Azeeda's request then Serana's, lines in that order, each
  keeping its own name.
- Change: the cache figure appears **only for a provider with Cache switched on**. It was
  printed on every line, so `cache ?` sat beside providers that had never asked for a slot
  and read as a fault rather than as a setting nobody turned on.
- Change: in the Proxy terminal the figures are green and the word `cache`, the slash and
  the percent are white - the reading is the numbers, the rest is the label.
- 1414 checks. Four negative controls, all caught.

---

## v3.74 patch52
- Fix: **providers with Thinking OFF answered with a single `.`** - Vision, ActionEval and
  Memory, while every provider with Thinking ON answered normally. patch38 replaced
  `chat_template_kwargs.enable_thinking: false` with a per-request
  `reasoning_budget_tokens: 0`, because llama.cpp calls the first deprecated and points at
  the second. But a budget of 0 does not mean "do not think", it means **stop thinking
  now**: a model that always opens a reasoning block is forced shut on its first token and
  answers with a stub. The budget is gone; the kwarg is back.
- That one substitution cost three patches. It crashed the grammar providers with
  `Unexpected empty grammar stack` (patch44 worked around it), and it produced this. It
  was shipped on the strength of a changelog entry rather than a test against the model
  actually in use. Deprecated and working beats current and broken.
- The grammar special case added in patch44 is removed with it - there is no longer a
  forced end-of-thinking token for a grammar to trip over.
- 1411 checks. Two negative controls: reinstating the budget fails five, and removing the
  kwarg that replaces it fails four.

---

## v3.74 patch51
- Fix: **a character named with a role after it was never recognised.** SkyrimNet writes
  `You are Azeeda [hunter], a Female Redguard in Skyrim.` and `SPEAKER_RX` allowed only
  letters, apostrophes, spaces and hyphens in a name - the `[` stopped the match dead, no
  name was learned, and the line was spoken as `Femalecommoner`. The role tag is now
  matched and discarded. Verified against the real prompt: `Azeeda`, and
  `Iris the Elder [merchant]` reads as `Iris the Elder`.
- Removed: `--slot-prompt-similarity 0`, added by the Cache switches in patch46. It went
  in on a reading of the docs that said automatic slot selection would override an
  explicit `id_slot`. It does not - an explicit slot is honoured first and similarity is
  the **fallback** - so all the flag achieved was switching off the mechanism that still
  works when a build ignores `id_slot` on the OpenAI-compatible endpoint. Measured on the
  user's server with two slots open and the flag set: `cache 0/384 0%` on every call.
  The pin is sent per request; nothing is launched into any more.
- The gate refused a second change in the same patch, correctly. Reading the player's
  name from `You are speaking to X` looks free - the line is right there - but that names
  the **listener**, and in an NPC-to-NPC exchange it puts another NPC's name on the
  player. There was already a check forbidding exactly that.
- 1410 checks, up from 1407.

---

## v3.74 patch50
- Fix: **a server card change never reached the launcher in the Server Editor.** That
  launcher lives in `params["custom"]`, and `regen_slot_script` wrote it back verbatim
  whenever it was set - so a card edit updated the parameters in the config and was then
  overwritten by the untouched original, every time. The cards now edit the flags inside
  that text with the same writer patch48 added for launchers on disk: only the
  `$llamaArgs` array, only flags already there or deliberately changed, nothing else in
  the file touched. The text in the editor, the parameters on the cards and the file that
  actually launches are three views of one thing.
- patch48 never reached this path because the file it writes lives *inside*
  `generated-launchers/`, so `slot_owns_script` said the panel owned it - true of the
  file, false of its contents.
- Fix: **a `$modelPath` the panel could not follow dropped every card change in silence.**
  `regen_slot_script` returns early when no model is named in the parameters, which is
  right when it has to build a launcher from nothing and wrong when one already exists
  and only needs a flag changed. The guard now applies only to the building case.
- 1407 checks, up from 1400, including a full round trip: paste a launcher into the
  editor, change two values on the card, and assert the editor text, the file on disk and
  the card values all agree - with the launcher's own machinery and a flag named in a
  comment untouched.

---

## v3.74 patch49
- Fix: **an in-place launcher edit was made and then not saved** when the server was
  launched from the panel. patch48 gave `regen_slot_script` a second return shape -
  a path for a generated launcher, `{"changed": [...]}` for one edited in place - and the
  launch path still read "is it a dict" as "did it fail". Only a dict carrying `error` is
  a failure. This is the other half of why a server card change did not reach a
  hand-written `.ps1`.
- Add: **Context checkpoints** on the server card, `--ctx-checkpoints`, 0 to 64,
  defaulting to llama.cpp's own 8. It was written as `0` by the No-cache switch and
  nowhere else, so there was no way to have both a cache and checkpoints. The switch no
  longer writes it, so the dial is the only thing that does.
- Change: **a refused speaker pairing now says why.** A spoken line labelled with its
  voicetype instead of a character can mean two different things - the name was already
  bound to another voicetype, or no dialogue request arrived within the window - and
  both looked identical in a log. They now read
  `voice femalecommoner: not naming it Serana - that name already belongs to serana` and
  `voice malenord: no character named it - no dialogue request arrived within 15s`.
- 1400 checks, up from 1391.

---

## v3.74 patch48
- Change: **a launcher the panel did not write is now edited in place, not replaced.**
  `regen_slot_script` rendered a slot's parameters into a fresh file under
  `generated-launchers/` and repointed the slot at it. On a hand-written launcher that
  silently swaps hundreds of lines of machinery - a VRAM report, a sampler chain table,
  stamp parsing, an n-predict backstop that reads its own source - for a bare flag list.
  The panel could already read those launchers (`parse_launcher_params` follows
  `$variables` back to where they were set); it just had no writer that was not a
  regenerator.
- Only the `$llamaArgs` array is touched, so a flag named in a comment or a `Write-Host`
  is never mistaken for an argument. The first version the panel ever sees is copied to
  `ps1-launchers/<name>.ps1.before-panel`.
- Only three kinds of flag are written: one already in the array, one whose value differs
  from the shipped default (the only sign a person chose it), and
  `--slot-prompt-similarity`, which exists solely for the Cache switches. A launcher that
  names no `--threads` is not asking for the panel's default of 8.
- **A parameter the card has no opinion on is never deleted.** The first version of this
  removed `--no-cont-batching` from a launcher that wanted it, because the card had no
  value for it and absent read as off. Absent now means leave it alone.
- Three defects in the writer, each found by running it rather than reading it: removing
  a bare switch swallowed the following flag's name and orphaned its value; appending
  after a comma-less last element produced invalid PowerShell; and a trailing comma
  splats a null argument to the server. The array is normalised after every edit.
- 1391 checks, up from 1377.

---

## v3.74 patch47
- Add: **a cache figure on every Proxy line and in the PTI/PME record.** Whether caching
  is working was not answerable from the panel, and reassurance is not an answer. The
  line now ends `cache 258/270 96%`, or `cache 0/270 0%` when nothing was reused, or
  `cache ?` when the build reported no such figure. Those are three different situations
  and conflating the last two hides the one worth chasing. Read under whichever of the
  four names llama.cpp has used for it.
- Fix: **`voice femalecommoner is Serana`.** A spoken line with no dialogue request behind
  it took whatever name was pending, and Serana's was, because she had just spoken. One
  character has one voice: a name already bound to another voicetype is no longer
  available, and the line falls back to its voicetype rather than wearing somebody else's
  name. Measured: Serana pairs to `serana`, is then refused for `femalecommoner`, and
  `femalecommoner` takes Ysolda when Ysolda actually speaks - with `serana` undisturbed.
- 1377 checks, up from 1360.

---

## v3.74 patch46
- Add: **a Cache switch on the provider card.** llama-server keeps one KV cache per slot,
  in VRAM, and picks a slot by longest common prefix. Two callers whose prompts share
  nothing - the tagger and Meta - clear each other out of a single slot and prefill from
  scratch every time. There is no cache to turn on; what the switch does is give a
  provider a slot nobody else can evict.
- **How many slots exist stays yours.** `--parallel` and `--ctx-size` are set on the
  server card and are never rewritten: opening another slot divides the context and costs
  VRAM, so it is a decision for whoever is paying for it. The switch pins within what was
  opened. Slot 0 is left for everything unpinned, so two slots pin one provider, three
  pin two, and one pins nothing at all.
- A provider that asks for a slot when none is free is left unpinned and **says so on its
  card** - `no slot free - Parallel slots is 2` - rather than being sent an `id_slot` that
  does not exist. Its hover names the setting to raise and the number to raise it to.
- The only flag the switch adds is `--slot-prompt-similarity 0`, and only when something
  is actually pinned: automatic slot selection hands a request to whichever slot looks
  similar, which is precisely what a pin is for overriding.
- Slots are numbered by provider id, not by position in the list. A number that moved when
  a provider was added or dragged would send a request to a cache belonging to somebody
  else.
- `--ctx-size` is the total and llama-server divides it between the slots the server
  opened, so the card shows what each is left with - `slot 2 - 3413 tok/slot` - and the
  hover does the arithmetic before the switch is thrown.
- 1360 checks, up from 1335. Five negative controls, all caught, including rewriting
  `--parallel` from the switch, which is the version of this that was built first.

---

## v3.74 patch45
- Change: **the tagger's prompt is 49% of its former length** - 1994 characters down to
  975, 37 lines down to 14. Every instruction it made is still made:
  - "return the line back word for word, add nothing" - kept, in one sentence
  - how far a tag reaches and where to put it - kept, in one sentence
  - both tag kinds, what each is for, and that either may be left out - kept
  - the whole vocabulary - untouched, 21 emotion words and 20 audio words
  - what goes wrong if tags are piled at the front - now said by the worked example
    rather than by a paragraph, which is how this model was persuaded of it in the first
    place
- Six examples become three, each carrying something the prose no longer says: a second
  tag taking over mid-line (`[laugh] Haha! [amusement] ...`), an audible noise at the
  pause it falls in, and a line that comes back untouched. The split-line example is the
  one that changed this model's behaviour where instructions did not, and the gate now
  names it specifically so it cannot be the one dropped for length next time.
- 373 of the remaining 975 characters are the two word lists, which cannot be cut without
  taking tags away from the engine. The gate asserts every tag Higgs accepts still appears
  in the prompt, so a future trim cannot quietly remove one.
- 1335 checks, up from 1331. Four negative controls, all caught - including padding the
  prompt back out, which fails the length check, and shortening the emotion list, which
  fails seventeen.

---

## v3.74 patch44
- Fix: **ActionEval and Diary failed with HTTP 500 - `Unexpected empty grammar stack
  after accepting piece`.** Introduced in patch38. A grammar constrains output from the
  very first token; `reasoning_budget_tokens: 0` forces the reasoning block shut, and
  llama.cpp then accepts its end-of-thinking token after the grammar has already
  completed. Only the two grammar-carrying providers were affected - Diary, whose rail
  this panel injects, and ActionEval, which sends its own schema - which is exactly the
  pattern reported. A grammar-bound request now has thinking turned off by the template
  kwarg alone, which is what those providers had before the budget existed. Recognised
  from the route's own rail and from `grammar`, `json_schema` or `response_format` in the
  caller's body.
- Fix: **a shared voicetype wore the name of the first character who used it, for the
  whole session.** `femalecommoner` and `maleguard` are used by dozens of NPCs, and the
  pairing was cached and never revisited. A fresh dialogue request now wins; the cached
  name is the fallback for a spoken line with no request behind it. Measured: Brelyna
  Maryon, held while nothing newer arrives, then Ysolda once she speaks.
- Change: turning PTI or PME off hides their lines from the Proxy and PTI/PME terminals.
  Those terminals tail a file, so switching a feature off stopped new lines and left every
  earlier one on screen.
- 1331 checks, up from 1315. Five negative controls. Two passed on the first attempt -
  nothing at all covered the grammar guard, which was the whole point of the patch, so
  the check for it is behavioural across five request shapes.

---

## v3.74 patch43
- Fix: **the player's lines were never spoken and the PTI / PME terminal was empty.** One
  cause. patch38 replaced `_chat`'s `port` argument with a route object but left
  `ptipme_log("PTI", port, ...)` naming the old variable, so the tagger raised
  `NameError: name 'port' is not defined` *after* the model had answered - which is why
  the request reached the LLM and the dashboard line was written, but the PTI/PME
  terminal never was. The exception then propagated into `_run_inner` and killed the
  line: `TTS failed: name 'port' is not defined`, every time the speaker was the player.
  Same mistake in `mood_evaluate`. Both now pass `rt["server"]`.
- Worth noting the sequence: before patch42 this exception escaped the worker and hung
  the handler for 120 seconds. patch42's `try` is what turned a hang into a visible
  error in the log, which is how it was found.
- Add: **a scope-aware undefined-name sweep over the whole module.** A `NameError` only
  appears when the line actually runs, and this one sat in a branch that only the player
  speaking reaches. Nothing may read a name no enclosing scope binds. The sweep is
  checked against a probe that must be caught and a closure that must not, and the
  module-level set is built from the module **body only** - collecting names assigned
  inside other functions is how `port` looked defined on the first attempt.
- Fix: the sweep immediately found a second one. **The MOSS-TTS arm has never worked.**
  It resolves the reference, announces the line, then reads `secs`, `gen_s`, `dec_s`,
  `over`, `body` and `out` - all computed only in the audio.cpp arm, which returns before
  reaching it - and never calls `_post_chunk` at all, so nothing is ever generated. It
  predates this session; the same hit appears on the patch33 tree. Reconstructing it
  blind would be guesswork, so it now fails with a plain message naming what is missing
  rather than a `NameError` about the last variable it happens to touch.
- 1315 checks, up from 1311. Two negative controls, both caught - reinstating the exact
  `port` reference is one of them.

---

## v3.74 patch42
- Fix: **speech stalled for up to two minutes and often timed out.** patch37 moved the
  startup-ping test to the top of `_run_inner` so the probe would stop reaching the
  tagger - correct - but its `return` landed **above** the `try` whose `finally` sets
  `ev["done"]`. The ping was answered and the worker exited, and the request handler
  waiting on that event was never released; it sat for `TTS_RESULT_WAIT_S`, 120 seconds.
  SkyrimNet sends the probe at startup, so it waited on its own ping and every line
  behind it queued. Measured before: 90 seconds between the tagger finishing and the
  first audio. After: the handler is released in 0.002s.
- The same `return` was not the only way past that `finally`. Everything from the ping
  test to the engine call - the tagger, the mood reader, the tag translator - sat
  **outside** the `try`, so anything raising in any of them left the handler waiting too.
  The whole body is inside it now.
- Add: a check that would have caught it. Structural - nothing may return before the
  `try`, and each of those four steps must sit after it - and behavioural: the worker is
  driven down the ping path and down a raising path, and the event must be set both
  times. Reinstating the exact regression fails four checks.
- Add: **Reasoning** on the server card - `on`, `auto` or `off`, defaulting to `on`. It
  was written into every generated launcher as `on` unconditionally. That is still the
  default and still the sane choice, since a provider decides for itself; `off` refuses
  reasoning for every provider on that server whatever its Thinking switch says, and the
  provider card already warns about that combination.
- Two gate faults found by their own negative controls: a missing `SERVER_PARAMS` row
  made three checks raise `IndexError` and take the run down instead of failing, and the
  new worker test let PME's settle thread outlive the redirect it was given, so the
  thread wrote `fleet-config.json` into the tree 1.6 seconds later and the trailing sweep
  blamed the run. Both fixed.
- 1311 checks, up from 1289. Three negative controls, all caught.

---

## v3.74 patch41
- Change: **the reasoning budget message applies to every provider with Thinking on**,
  not just the two the panel calls itself. `reasoning_budget_message` moves into
  `apply_route_shape`, so a routed provider gets it as well; the wording lives in one
  place as `REASON_BUDGET_MSG`. It is `setdefault`, so a caller that sent its own wording
  keeps it, and it is inert unless a budget is actually set - on the server card or per
  request - so it costs nothing on a provider left unrestricted.
- Fix: **a provider with Thinking off must not carry a budget message.** Its budget is 0,
  which is exhausted at once, so the message would be forced into the reasoning block
  immediately and "Answer now." would appear in the output of a provider that was told
  not to think at all. Explicitly stripped on that arm.
- Change: `reasoning_format` is no longer forced on every panel request. The server card
  has owned that flag since patch40, and forcing `deepseek` per request would have been
  the same silent countermand the hardcoded `temperature: 0` was. Thinking content is
  still separated either way - `reasoning_content` when the server reports it,
  `_split_think` for an inline block.
- 1289 checks, up from 1281. Five negative controls, all caught - including removing the
  strip, which puts the message back into a non-thinking provider's output.

---

## v3.74 patch40
- Add: **Reasoning budget** and **Reasoning format** on the server card, written into the
  generated launcher as `--reasoning-budget` and `--reasoning-format`. Both are rows in
  `SERVER_PARAMS`, which is the one table the card, the launcher writer and the
  cross-reference chip all read - a control added anywhere else would be a control that
  never reaches a launcher. Budget is an `int`, so the card draws a number box with a
  slider beside it; format is a `sel`, so it draws a dropdown.
- The budget reaches -1 and defaults to it, which is llama.cpp's unrestricted, so an
  untouched server behaves exactly as before. The format offers all four values the flag
  accepts - `auto`, `deepseek`, `deepseek-legacy`, `none` - defaulting to `auto`.
- The server is still launched `--reasoning on`. Whether a given provider reasons is its
  own Thinking switch, which since patch38 sends a per-request budget of 0 when it is off
  - that is how one server reasons for some callers and not others.
- Change: the guide's budget entry said `N = -1 or 0 or more`, from when that was all the
  flag took. It takes a real token budget above 0 now, and the entry says so. The format
  entry listed three values; there are four.
- Fix: **the accent glow on the PTI and PME boxes was gone.** `netBox` builds its ring as
  `col + "3d"` - a hex with an alpha suffix - so `var(--acc)` arrived as `var(--acc)3d`,
  which is invalid, and the browser dropped the ring and the glow with it. `accHex()`
  reads the theme's computed `--acc`, validates it as `#RRGGBB` and falls back if a theme
  ever holds something else.
- Fix: **no gap between the mark and the title.** `.nb-t` is a flex row, so the whitespace
  text node between the image and the name collapsed to nothing. The mark carries its own
  margin now, which fixes it everywhere it is drawn rather than in the one place it was
  noticed.
- 1281 checks, up from 1257. Six negative controls, all caught.

---

## v3.74 patch39
- Fix: **the PandorumLLM mark was drawn as a raw character** in the provider page title,
  the Live Network box and the stats row - a lozenge rather than the icon. The mark is
  stored on the record as a character because a config file cannot hold an image, and
  the terminal painter already substituted it; nothing else did. `provMark()` does it in
  one place now, and every site that draws a provider goes through it.
- Change: the icon is 20px on the provider page, up from the 15 the card was drawing.
- Change: PTI and PME show **Proxy** where a routed provider shows its port, in the Live
  Network box and on the provider row. They have no port and the bare `:` said nothing.
- Change: the wired and parked provider boxes were two identical copies of the same
  markup; `provNetBox()` is the one copy, which is also what makes the Proxy label
  impossible to apply in one place and forget in the other.
- Change: PTI and PME sort to the end of the provider list. They have no port to sort by,
  so they were landing in the middle of it.
- 1257 checks, up from 1247. Five negative controls, all caught.

---

## v3.74 patch38
- Change: **PTI and PME are providers.** They carry a provider record, wire to a slot by
  drag and drop in Live Network, and take their server, Thinking switch, priority and
  sampler overrides from the card like everything else. `ttsPlayerTagsSrv` and
  `ttsMoodSrv` are deleted; their value is spent once on the initial wiring so an
  existing setup survives the upgrade, and after that the wiring is the only thing that
  names a server. Two places naming one server is two places that can disagree.
- Two things differ from a routed provider, and both follow from the panel being the
  caller rather than SkyrimNet: **no listener is bound** - binding `0.0.0.0` for
  something only ever reached in-process buys two LAN sockets for nothing, so the card
  reads `panel-called` where a port would be - and **Sampler Source is Server Side
  permanently** with no detect switch, because there is no other side to take values
  from. Accent left edge, and the PandorumLLM icon in place of the emoji picker.
- Fix: **a provider's sampler overrides never reached PTI or PME.** The proxy applied
  them; `_chat` did a different half of the same job and applied none. One
  `apply_route_shape` now, used by both. The gate reimplements what the proxy did inline
  before the extraction and asserts a routed request comes out byte-identical across
  thinking on/off and both sampler sides - that is the check protecting Meta.
- Fix: **`_chat` forced `temperature: 0` on every call**, overruling whatever the server
  was launched with and saying so nowhere. Removed. The same value ships as an override
  on the PTI card, so the behaviour is unchanged but it is visible and can be cleared.
- Change: Thinking off now sends `reasoning_budget_tokens: 0` at the **top level** of the
  body, which is the mechanism current llama.cpp points at - setting `enable_thinking`
  through `chat_template_kwargs` is deprecated and warns on recent builds. b9982 is what
  made a client-supplied budget actually reach the sampling layer; before it the server
  wrote its own defaults first and the body-copy loop skipped the request's value. The
  kwarg and the top-level `enable_thinking` still ride along for older builds.
- Change: priority comes from the card's 0/1/2 dial through `route_gate_key`, replacing
  the Priority Over Providers switches added in patch37. One dial, not two.
- Removed: `proxy_log_line`. They call the same `report()` a routed provider does, so
  they fold into the stats page as well as the terminal.
- Removed settings: `ttsPlayerTagsSrv`, `ttsMoodSrv`, `ttsPlayerTagsThinking`,
  `ttsMoodThinking`, `ttsPtiPriority`, `ttsPmePriority`.
- 1247 checks, up from 1194. Seven negative controls; three passed on the first attempt
  because the checks were weaker than the code - the listener guard was masked by the
  record having no port at all, the Server Side force was masked by the record being
  corrected on load, and nothing asserted the proxy actually *called* the shared shape
  rather than only that the shape worked. All three tightened.

---

## v3.74 patch37
- Fix: **PME could name three feelings and PTI would be shown one.** The reader's answer
  was checked against the *display* list - the one preferred spelling per tag that the
  prompt happens to print - so a line naming a feeling in any other spelling was thrown
  away whole. `angry`, `disgusted`, `elation`, `sadness` are all rendered correctly by
  `tts_apply_tags` and were all refused here. The vocabulary now comes from the same two
  tables the tag translator uses (`MOOD_SPELLING`), normalised to one spelling on the way
  in so the hint PTI sees still reads the same way.
- The measured case was different again and worth stating plainly: the model answered
  `contempt`, which Higgs has no tag for in any spelling, so that line was correctly
  refused - and **silently**, which is why it looked like truncation. A refused word is
  now named in the TTS terminal.
- Fix: **the startup ping was being tagged as though the player had said it.** The probe
  was recognised only after `tts_player_tag` had already marked it up and
  `mood_note_line` had already recorded it as a spoken turn, producing
  `[sound_ping] ping.` It is settled at the door now, by one shared `tts_is_ping`, before
  the tagger, the mood reader, the spoken record and either engine arm - and a probe never
  reaches any of them whatever the mode is set to.
- Change: **Answer SkyrimNet startup ping locally** is now **SkyrimNet Ping**, with a
  hover explanation and three options: **Yes** (silence, no GPU, said in the terminal),
  **No** (spoken like any line, for testing the engine at all), **Banned** (silence and
  nothing said). The page and the panel take the set from one table each and the gate
  holds them equal.
- Add: **Priority Over Providers**, one per feature, off by default. PTI and PME do not
  route through the proxy, so the priority a provider carries has nothing to say about
  them; with this on they hold the existing `GpuGate` for the card their server sits on,
  which is the footing a priority-0 provider already has. It does not interrupt a request
  already in flight and nothing waits beyond `GATE_MAX_WAIT_S`. Measured: a provider on
  the same card waits for the length of the call, one on another card waits nothing.
- The routing table and the gate now derive "which card is this slot on" from one
  `slot_gpu_key`. Two derivations would have meant the hold marking one key while the
  waiters watched another - a gate that appears to work.
- Change: **Chat History** ships at 25, moved once from the 8 it shipped with, on the same
  terms as PME Frequency in patch36.
- Change: the TTS page's setting titles are white and 14px against the 12px dim field
  labels under them. At the same size and colour they read as one more caption in a long
  column.
- The note beside `TTS_EMOTION_BLOCK` still explained itself in terms of the Pitch Guard,
  which patch33 removed. Corrected to say what actually happened.
- 1194 checks, up from 1123. Eight negative controls; four of them passed on the first
  attempt and the checks they defeated were the weak ones - a hold taken with an empty
  argument still contains the words `with _GateHeld(`.

---

## v3.74 patch36
- Change: the dividing rule in the Player Tag System moves **below** the Player Tag
  Injector Server. It was splitting the tagger's own block in two; it now closes that
  block and separates it from the mood reader, which is what a rule there is for. PME
  keeps its own rule above its server picker, where the same reasoning puts it.
- Add: a **TTS Server** heading over the Model and Build choices. They sat under no
  heading at all, directly after the Player Tag System, and read as part of it.
- Change: **Folders & Model** is now **Folder Paths**, **Voice** is **Audio Files** (both
  engines), and **Install** is **Installation**.
- Change: **Build (both are installed; switching only needs a restart)** is now
  **Audio.cpp Build**, with the explanation on the hover mark beside the title rather than
  as a paragraph under the control - the same treatment every other setting on the page
  has. The paragraph is removed, not duplicated, and the hover carries what it said plus
  what each build actually is. The options are named **Balanced** and **Fast**, nothing
  more.
- The install row's opening markup was written out five times identically, so renaming it
  meant five edits and one to miss. `HIGGS_SECT` now, stated once.
- Change: **PME Frequency defaults to 3** rather than 1. `DEF_SETTINGS` only fills a key
  that is *missing*, so a config written by patch35 keeps the 1 it shipped with and would
  never have seen the new default; it is moved once, and only from that exact value, so a
  1 chosen deliberately afterwards stays.
- 1101 checks, up from 1078 - 1123 with jsdom. Two of the new ones were caught by their
  own negative control: the rule-placement check passed when a *second* rule was added
  rather than the first moved, and the heading-order check used `.index()` and took the
  whole run down instead of reporting the absence, which is the trap DEVELOPMENT section 8
  had just been given a note about.

---

## v3.74 patch35
- Add: **PME Frequency**, beside Activation on the TTS page. A slider from 1 to 20 saying
  how many NPC lines pass between scene readings - 1 is every line, 5 is every fifth.
  Counted where a line **settles**, not where a piece of one arrives: a reply comes in
  several parts and only the last survives the generation guard, so counting arrivals
  would have run the frequency down several times over one line.
- A PTI completion restarts the count, as asked, and only once a reply has actually come
  back - a server that is down consumed no reading. Note the consequence: in a
  back-and-forth conversation the reset lands before the count reaches anything above 1,
  so a high setting means the scene is rarely read. It earns its keep when NPCs talk
  among themselves. The slider's own text says so.
- Change: **the Player Tag Output switch is now two switches**, `PTI Output` and
  `PME Output`. The PTI line repeats the player's line, which is already spliced in
  beside it, so it was the half worth hiding - and hiding it used to take the mood
  reading with it. A config written by an older build carries its single value onto both,
  so nothing changes until the new button is pressed.
- The button, its setting and its label come from one table (`TAG_OUT_BTNS`), so a button
  cannot be lit from one setting while toggling another. The old handler open-coded what
  `termToggle` does and left out the repaint, so a switch took effect only when something
  else happened to refresh the terminal; both now go through it.
- Change: **PTI and PME answers hang off the line that produced them**, on the same
  `|-` / `L-` branch the spliced spoken lines use, the last row closing the tree. The
  glyphs are stated on both sides - the panel writes them, the page draws its own - and
  the gate holds the two equal, since different glyphs would put the two kinds of branch
  in different columns.
- Fix: **the prompt speed column read `?` on every call the panel made.** `_chat` threw
  away the reply's `usage` and `timings` blocks, so there was nothing to put there -
  prompt processing cannot be timed from outside, only the server knows it. Both token
  figures were `len(text) // 4` estimates as well. Real counts and both speeds are read
  from `timings` now, falling back to `usage` for counts and to wall time for the
  generation rate. A figure the server did not report stays absent and prints `?` rather
  than being invented.
- Fix: **the Proxy line layout was written out twice and the two copies had drifted.**
  The provider copy filled the prompt-speed column; the panel's copy had `"?"` hardcoded
  in it. One `proxy_line_text` now, used by both, with a check that a panel line and a
  provider line put `tok` and `tps` at the same offsets.
- Removed: `_chat`'s `want_reasoning` switch. Every caller passed it, so the string-only
  return was dead.
- 1078 checks, up from 1037 - 1100 with jsdom installed, which the browser harness needs.
  Eight of the new ones were confirmed by reverting each fix in turn and watching them
  fail, including a cross-wired output button caught in the browser harness.

---

## v3.74 patch34
- Fix: **a reference voice with a broken length field was handed over unrepaired.** 160 of
  the user's voicetype WAVs carry `data` at the canonical offset 36 and then declare its
  size as `0xFFFFFFFF` - a streaming writer that never went back to patch the header once
  it knew the length. `tts_ref_canonical`'s cheap trust check tested **where** the data
  chunk sat and not **what size it claimed**, so every one of those files was called
  canonical and passed straight to audio.cpp, which refuses them with `failed to read WAV
  data chunk`. `tts_wav_normalize` already repaired them correctly - `wave` reads such a
  file without complaint and `readframes` returns only the bytes actually present - so
  nothing needed writing but the condition. The standalone repair script HANDOVER 2.4 was
  holding is no longer needed: uploads and Local Voice Clips are both mended in place on
  first use, once.
- Change: the header test is now one predicate, `tts_wav_head_ok(head, size)`, which asks
  whether a 44-byte header describes exactly the bytes that follow it - both declared
  lengths, not the layout. `TTS_WAV_HEAD` names the 44.
- Change: a reference that is not a WAV at all returns immediately instead of being read
  whole on every line to be handed back untouched.
- Fix: **the gate poisoned its own next run.** Importing `fleet-panel.py` wrote
  `__pycache__` into the tree, and the junk sweep that forbids it runs *before* that
  import - so the run passed, dirtied the tree, and the next run failed on `absent:
  __pycache__` blaming the tree for what the gate itself had left. `sys.dont_write_bytecode`
  is set before the import.
- Add: a sweep at the **end** of the gate for the same seven junk paths, which is what
  holds the above. It caught the new reference check writing `logs\panel.log` and
  `fleet-config.json` into the tree under test, through `panel_log` - held aside for the
  duration now, and the announcement is asserted rather than discarded.
- Change: the reference checks are behavioural rather than text matches. A WAV is built,
  both length fields are broken, and the file must come back canonical, be left alone when
  it already is, and not be rewritten twice. Verified to fail with the old condition
  restored.
- 1037 checks, up from 1025.

---

## v3.74 patch33
- **The Pitch Guard is removed.** It was built on a wrong conclusion. Higgs was never
  discarding the voice sample: a sweep across four references, judged by ear, found every
  take to be the right speaker throughout - elated ones simply higher in pitch and energy,
  plain ones flatter. Pitch and low-band energy both move with emotion, exactly as they
  should, and reading that as a change of speaker was a mistake. The guard could only ever
  have thrown away good audio.
- Fix: **an emotion tag was being applied to the whole line**, so a line opening with a
  laugh was delivered as though every word were part of it. Tags apply per sentence, which
  the prompt never said - it told the model an emotion tag "colours the whole line, so it
  goes at the very start". It now explains that a tag reaches from where it sits until the
  next one, and to put a calmer tag on the following sentence when only the opening is
  loud:

      "Haha, of course you would say that."
      ->  [laugh] Haha! [amusement] Of course you would say that.

  which reaches the engine as `<|sfx:laughter|>Hehe, Haha! <|emotion:amusement|>Of course
  you would say that.` - the energy on the laugh, the rest spoken normally.

## v3.74 patch32
- Fix: **a stray horizontal mark beside a wrapped dialogue line.** The tree's elbow was
  positioned at 50% of the branch, and since patch20 the branch is as tall as the whole
  row - so on a line that wrapped onto two rows, 50% landed exactly on the boundary
  between them. It is now pinned to a fixed half-row and always falls on the first.
  (The patch20 edit that should have done this was in a script that aborted before
  writing, so it never shipped.)
- Change: **PTI and PME answers appear as branches**, the same as spoken dialogue.
- Change: **each feeling PME names gets its own row**, so a reading with three is three
  branches rather than one long line.
- Change: the **PTI / PME terminal is painted by the same code as the Thinking Content
  terminal** - separators, timestamps and ports read identically, because they are the
  same kind of record. `--- INPUT ---` and `--- OUTPUT ---` glow in the accent colour.

## v3.74 patch31
- Change: the **PTI / PME terminal shows only what was sent and what came back** - the
  literal prompt under `--- INPUT ---`, the model's answer under `--- OUTPUT ---`, and
  nothing else. The working that led to the answer is stripped: with Thinking on, a
  reasoning preamble or a `<think>` block was appearing there alongside the answer, and
  the reasoning already has a terminal of its own.

## v3.74 patch30
- Fix: **the mood reading was being thrown away before it reached the tag injector.** The
  prompt asks for `1. [word] (NN%): reason` and shows an example in that shape, but models
  answer `1. amusement (85%): reason` often enough - and the parser required the square
  brackets, so a perfectly good reading was discarded and PTI ran with no context at all.
- Brackets are now optional. A score in parentheses is still required, so ordinary prose
  is not mistaken for an answer, and a feeling that is not on the offered list is still
  dropped.
- The reading is stored in one shape whatever shape it arrived in, so what PTI is shown
  always reads the same way - and the reason survives whether it was written after a
  colon, a dash, or nothing at all.

## v3.74 patch29
- Fix: **Thinking was on for the tag injector and the mood reader whatever the switch
  said.** The flag to turn it off was being sent at the top level of the request, where
  it is ignored; the template reads it from `chat_template_kwargs`, which is where the
  proxy has always put it. It now goes in both places.
- That also explains the second symptom: a tagging call that reasons takes twenty seconds
  rather than a tenth of one, and since each spoken line runs in its own thread, one still
  reasoning would overlap the next line - so the tag appeared to arrive after the speech
  rather than before it. The order in the code was always tag first, then speak.
- The TTS terminal now shows the tag and **how long it took**, above the line it belongs
  to, so the sequence is visible in one place rather than split across two terminals.

## v3.74 patch28
- Add: an **audio.cpp report** button on the TTS page. It reads the session's own logs and
  produces something that can be pasted straight into an upstream issue - versions, model,
  device, what the server said about the machine, how many lines were spoken, how many ran
  past the end, how many needed regenerating, median and worst generation time, the lines
  that went wrong, and the `audiocpp_cli` command to reproduce them with no panel involved.
- Fix: **the Pitch Guard was firing on takes that were fine.** In one session it refused
  the same reference at both 0.4x and 2.3x, which cannot both be a speaker swap. Checked
  against a proper implementation over eighteen real clips, the panel's stdlib pitch
  measurement lands within a semitone on fifteen and picks a subharmonic on three.
- The estimator is better for it - decimating to 12 kHz rather than 6, and taking the
  shortest strong correlation rather than the largest, since autocorrelation peaks at
  every multiple of the period. That fixed one of the four bad readings.
- But one clip in six is still read an octave out, so **the guard is now OFF by default**
  and the page says why. Every judgement it makes is recorded with the actual figures and
  appears in the report, so a wrong refusal can be looked at rather than argued about.
- The retry message now names the frequencies rather than only the ratio.

## v3.74 patch27
- Change: the tag injector is now asked for **the whole line back with tags placed in
  it**, rather than for a list of tags. A tag list can only ever be prepended; a noise
  belongs where it actually happens:

      "Excuse me. Dusty in here."   ->   Excuse me. [cough] Dusty in here.

  which reaches the engine as `Excuse me. <|sfx:cough|>Ahem, Dusty in here.` - the cough
  in the pause, not before the first word.
- The examples now show the input line and the marked-up line, so the format being asked
  for is the format being demonstrated.
- **A reply whose words differ from the line is refused outright.** The player typed that
  line and a model quietly rewording it would be putting words in their mouth. Tags are
  stripped, the remaining words compared, and anything that does not match is thrown away
  - the line is then spoken exactly as typed. Tags we never offered are dropped, and only
  the first of each kind is kept.

## v3.74 patch26
- Change: the tagger is now shown **two kinds of tag rather than four** - an *emotion
  tag* and an *audio tag*, at most one of each per chunk. Higgs has four tag families,
  but sfx, style and prosody are all "something you can hear" from a writer's point of
  view; splitting them made the model weigh four separate decisions and answer only the
  first.
- The prompt explains each kind rather than listing words: an **emotion tag** is what the
  speaker feels and colours the whole line; an **audio tag** is something you would
  actually hear - a noise they make, how the voice is produced, or how fast or high it is.
  It states which goes first, and that either may be left out.
- The examples now cover each case explicitly: emotion alone, both together, audio alone,
  and neither.
- The same 41 tags are available; only how they are grouped and explained has changed.

## v3.74 patch25
- Fix: the tag injector reliably answered with **one feeling and never a sound**, which
  was the prompt's fault, not the model's. It listed the vocabulary, gave no worked
  examples, and said *"fewer is better, and none at all is a perfectly good answer"* -
  which is an instruction to stop at one.
- The prompt now says what each group is **for** (a Feeling is what the speaker feels, a
  Sound is something audible they do while speaking), states that the groups combine, and
  shows seven worked examples - most of them with two tags:
  `"Keep your voice down, they will hear us."  ->  [fear] [whisper]`
- It ends by asking directly for a Sound, Delivery or Pacing tag whenever the line calls
  for one, rather than discouraging it.
- The mood reader gets a finished worked answer for the same reason.
- A gate check fails if any example uses a word the tagger is not allowed to answer -
  teaching it a tag that would then be rejected is worse than no example.

## v3.74 patch24
- **Elation is back.** It was blocked in patch22 on measured evidence, but the Pitch Guard
  added in patch23 catches a take in the wrong voice whichever tag caused it - which is the
  same fault treated at its source. The blocking mechanism stays for a tag that ever earns
  it; the list is empty.
- Change: **all 41 usable Higgs tags are now offered** - 21 feelings, 9 sounds, 3 delivery
  styles and 8 pacing controls, up from 16. `pause` and `long_pause` are left out
  deliberately: they are punctuation rather than performance.
- The list is **built from the tag tables** rather than written by hand. A hand-written
  one drifted immediately - eleven of the words in it were not accepted by the engine at
  all. The shortest accepted spelling of each tag wins, so `angry` rather than `anger`.
- Fix: a canonical tag name could not be written as itself. `[EMOTION-AFFECTION]` worked
  while `[affection]` was left in the line as literal text and read aloud - and eleven
  emotions had no other spelling. Every canonical name is now an alias for itself, and the
  matcher accepts the underscores that prosody names carry.
- Change: the tagger may now take **one word from each group** rather than one feeling and
  one sound, so `[happy] [laugh] [whisper] [slowly]` is a valid answer. Higgs stacks one
  per family and drops the rest, so a second word from the same group is dropped here too.

## v3.74 patch23
- Add: a **Pitch Guard**. Higgs intermittently discards the voice sample and speaks in its
  own default voice, measurably at three to four times the reference pitch. The panel now
  measures the reference once, measures each take, and if the two are more than 1.8x apart
  it throws the take away and asks again - up to three times, then keeps the last rather
  than losing the line. Costs a few milliseconds; entirely stdlib, no numpy.
- Fix: **thinking was capped at 600 tokens for the mood reader and 320 for the tagger**,
  hardcoded by me in patch18. That is why the reasoning kept stopping around 500 with no
  answer after it. Both are now sliders on the TTS page, 100 to 10000, shown only when
  Thinking is on.
- Add: `reasoning_format: deepseek` and `reasoning_budget_message: "Answer now."` are sent
  with every thinking request. **These are llama-server flags first** - a build that does
  not accept them per request ignores them, so if reasoning still arrives mixed into the
  answer, add `--reasoning-format deepseek` to that server's launcher.
- Fix: when reasoning is not separated by the server it arrives inside the reply as a
  `<think>` block, and the answer parser was reading the model's working as its answer.
  It is now split out. An unclosed block means the budget ran out mid-thought, which is
  treated as no answer rather than a garbled one.

## v3.74 patch22
- Change: **elation is no longer sent to Higgs**, whoever asked for it. The same short
  line was generated four times with and four times without `<|emotion:elation|>` against
  two references, one at 83 Hz and one at 200 Hz. All eight elation takes came back in a
  different voice - and all landed between 265 and 381 Hz **regardless of the reference**,
  which is the model dropping the speaker rather than shifting it. Around half of all
  calls also failed outright with "reached max_tokens before EOC". The tag is stripped at
  the point a control token is written, so every spelling of it is covered, and `happy` is
  gone from what the tagger may choose.
- Fix: a tag written in the wrong case - `[ANGRY]` rather than `[angry]` - matched nothing
  and was **spoken aloud, brackets and all**. Alias matching is case-insensitive now.
  Unrecognised brackets are still left alone, so ordinary dialogue is unaffected.
- Add: a **PTI / PME Terminal**, showing what each was asked and what it answered - the
  prompt, the line, and the reply in full. The Proxy terminal shows that they ran and what
  they cost; this shows why they answered as they did, which is the only way to tell a bad
  prompt from a bad model. Available in Split View as well.

## v3.74 patch21
- Add: every spoken line now records **which reference clip** it was given -
  `voice: playervoice.wav` - or `(none)` if none went out.
- Why: a generated line was measured at a median pitch of **264 Hz against the sample's
  77 Hz**, and it was wrong from its very first frame rather than drifting partway. That
  rules out the model losing its conditioning mid-generation and points at the wrong
  reference going out, or none at all. Without the filename in the log there is no way to
  tell a wrong file from a right file badly used.

## v3.74 patch20
- Fix: the TTS server's lines never appeared in the fleet terminal because **launching the
  fleet replaces that terminal's whole contents** with the server's own launch log,
  throwing away anything announced from the panel. It now forgets the last state when that
  happens, so the next pass says where the TTS server stands.
- Fix: a wrapped dialogue line broke the tree - the branch was one row tall while the row
  was two. The branch now reaches the bottom of however many rows the text folds to, while
  a closing branch still stops at its own elbow.
- Add: **Prompt Edit** for both the tag injector and the mood reader, between the setting
  and its Thinking switch. Empty means the built-in wording, which is shown beside the box
  so it can be copied or compared.
- Add: **Player Tag Output** in the Proxy terminal toolbar - shows what PTI and PME
  actually answered, on a branch under their own line. With Thinking on, only the final
  answer is shown, not the reasoning.
- Change: the mood reader's prompt asks for a **Final Answer** section in a numbered shape,
  which gives a reasoning model somewhere to put its working and somewhere separate to put
  the answer. The parser takes the last such section, since reasoning tends to quote the
  instruction.
- Change: a line that fails with *"reached max_tokens before EOC"* is **tried once more**.
  That is the model failing to stop rather than a bad request, and it is sampled - the same
  line usually succeeds on a second attempt. Two lines were lost to this in one session.
- Change: titles on the TTS page read white; a rule separates each setting from the server
  it uses; the panel's mark in the terminal is the actual icon at a readable size.

## v3.74 patch19
- Fix: the TTS server's starting and stopping lines were written into the **Proxy**
  terminal. They belong in the fleet stack terminal - the one behind the terminal emblem
  beside the launch buttons, which is where every other server reports. Moved.
- Add: **PTI** and **PME** report in the Proxy terminal in the same shape a provider does
  - tokens in and out, rate, and how long it took - so you can see them run and what they
  cost. With Thinking on, their reasoning appears in the Thinking Content terminal, the
  same way a provider's does.
- They carry the PandorumLLM mark rather than an emoji, lit in the accent colour, because
  these are calls the panel makes rather than anything routed through it.
- Change: the Thinking switch sits beside its setting rather than out at the right margin.
- Change: the section is called **Player Tag System**.

## v3.74 patch18
- Add: **Thinking** for the Player Tag Injector, beside its own setting - as the mood
  reader already had. Turning it on also gives the model room to reason; twelve tokens
  would not have been enough.
- Renamed, since the old labels described the mechanism rather than the thing:
  *Inject Player Tags* becomes **Player Tag Injector**, *Tagged by* becomes **Player Tag
  Injector Server**, *Read by* becomes **Player Mood Evaluation Server**, *Conversation
  read* becomes **Chat History**, *Feelings offered* becomes **Emotion Tag Count**, and
  *While speech is being made* becomes **Activation**, reading *After NPC text arrival* or
  *After TTS completion*. The "(Higgs only)" suffixes are gone - the settings only appear
  on Higgs anyway.
- Change: the explanations are **tooltips on the titles** rather than paragraphs under
  every control. A title carries a question mark and glows white when pointed at. The page
  was becoming prose to read past.
- Change: section headings are **banded** rather than separated by a hairline, and the
  player-voice settings have one of their own.

## v3.74 patch17
- Fix: the two tagging features required a **running** server, which had it backwards -
  settings are arranged before the fleet is launched, not after. A server counts when it
  is **set up with a language model on it**; the list marks the ones that are not running
  rather than hiding them. A server that is off simply answers nothing, which the tag path
  already treats as no tag.
- Change: more room between the rows on the TTS page, so each setting reads as one thing.

## v3.74 patch16
- Change: **Inject Player Tags** and **Player Mood Evaluation** are dimmed until a server
  is running with a language model loaded. Hovering says why. They were previously
  settable with nothing able to answer, which meant turning them on and finding out later
  that nothing happened.
- A **vision projector** and an **MTP draft** both load and both show as serving, but
  neither will answer a chat request - so neither is offered. Each slot now reports what
  kind of model it holds, read from the file once and remembered; the check costs about
  0.01 ms on a state read.

## v3.74 patch15
- Change: **mood evaluation now reads what was spoken, not a dialogue prompt.** Every line
  that reaches TTS is one turn, already carrying the speaker's name - so there is nothing
  to search, nothing to strip, and SkyrimNet's own history length no longer governs how
  far back the panel can see. It also works for someone using the panel for speech alone,
  with no fleet behind it.
- The proxy hook, the streaming-content capture and the prompt-extraction code are gone
  rather than adapted. Less code, and one fewer thing that has to be routed through the
  proxy for the feature to work.
- A reply that arrives in several pieces is read **once**, after the last piece, rather
  than once per piece.
- Confirmed: with nothing having passed through the proxy, names fall back to the
  voicetype (`Femaleyoungeager`) and `Player`, and nothing errors. Once a dialogue prompt
  does pass through, the same lines read `Serana` and `Maxxor`.

## v3.74 patch14
- Fix: **a tag the panel asked for was being stripped before it reached the engine.**
  `Audio Tags` defaults to *Strip them*, and the injected tag went through that same
  filter - so on a default install the whole player-tag feature did nothing at all. That
  setting governs tags **SkyrimNet** wrote; a tag we asked for deliberately is now always
  kept, and the page says so.
- Change: the tagger may return **one feeling and one sound** rather than one tag in
  total. Higgs accepts both - `[angry] [sighs]` becomes
  `<|emotion:anger|><|sfx:sigh|>` - and they answer different questions: how the line was
  said, and what the speaker did while saying it. Extra tags beyond one of each are
  dropped, and the feeling is placed first.
- Change: **mood evaluation names feelings only.** It was being offered sounds and
  delivery too, which it has no way to judge - a sigh or a whisper is in the line, and the
  tagger reads the line. Its answer is held to the same list.

## v3.74 patch13
- Add: **Player Mood Evaluation** on the TTS page. After each NPC line, a model of your
  choosing reads the exchange and names up to five feelings the player's reply might
  carry, with a likelihood and a few words of reason. That reading is offered to the tag
  process as background.
- It runs **after** the NPC has spoken, in the gap while the player is still reading, so
  it costs nothing at the moment the player types. Nothing waits on it: if the player is
  quick, the tag goes out with whatever reading was there before.
- Adjustable on the fly: turns of history read (1-250), feelings offered (1-5), thinking
  on or off, and whether to stand aside while speech is being generated - for anyone
  running this on the same card as TTS.
- **The framing matters more than the feature.** A hint saying "the player is angry" will
  pull a small model toward that tag whatever was actually typed. So nothing states what
  the player feels: the reading is presented as what the exchange *might invite*, marked
  plainly as NOT what the player said, and the tagger is told the line itself decides -
  with NONE still available.
- Only the dialogue provider triggers a reading; Meta, Vision and ActionEval are
  classifiers and their output is not conversation. The character sheet in the system
  prompt is dropped and private thoughts are stripped, so a 40 KB request contributes only
  its turns.

## v3.74 patch12
- Add: **Inject Player Tags** on the TTS page, Higgs only. The player types their line, so
  nothing has tagged it - every NPC around them is delivered with feeling and they are read
  flat. With this on, a fleet model of your choosing is asked for one tag before the line
  goes to the engine.
- The prompt is **81 tokens**, so on a small model the whole round trip is a few tens of
  milliseconds rather than the seconds a full dialogue prompt would cost.
- The server list offers only servers that are **up with a model loaded**, and says so when
  none is. Pick the smallest: the work is tiny and should not compete with dialogue.
- Everything fails to "no tag": a server that is down, a slow answer, a reply that is not
  one of the words offered. The line is spoken plainly rather than delayed.
- A line you tagged yourself is left alone. Typing `[angry] Get out of my way` has always
  worked and still does, with this off or on.

## v3.74 patch11
- The gate can no longer pass a check that tested nothing. Every check that examines a
  region of source now goes through `seg()`, which refuses a slice whose anchors are the
  wrong way round, whose start anchor also matches a longer name, or which came back
  suspiciously short. Previously such a slice returned an **empty string**, and a
  "must NOT contain" check is satisfied by an empty string - so a broken check did not
  fail, it passed.
- 140 slices converted. Eight anchors were ambiguous, and one check was found to be
  **passing on a slice that had run wild**: "the audio.cpp arm keeps a named copy" was
  matching one of fourteen occurrences of its anchor, and the named copy is in fact saved
  in shared code used by both engines. The check now says so.
- Checks that police code read it with comments and docstrings stripped, so a comment
  explaining why a symbol must not be used no longer counts as using it.
- Added a section in which the gate tests its own helpers - each failure mode above is
  proved to raise rather than pass.

## v3.74 patch10
- Add: the welcome message offers **TTS only for now** in the bottom left, which goes
  straight to the TTS page. Speech does not need the fleet - if someone's language models
  come from elsewhere, they should not be walked through setting up servers they will
  never run.
- The message now says the two halves can be used apart, rather than assuming everyone
  wants both.
- The new button is lit blue rather than accent, so it reads as a second path rather than
  competing with the main way in.

## v3.74 patch9
- Add: hovering the mood icon on a spoken line says what it stands for - *amusement*,
  *whispering*, *laughter*. A line with no tag says so rather than staying silent about it.
- The labels are built from `TTS_MOOD` and injected into the page, so the tooltip cannot
  drift from the icon the log actually chose. An icon shared by several tags lists them
  both rather than picking one and being wrong half the time.

## v3.74 patch8
- Fix: **the terminal never wrapped.** Wrapping was opt-in through a class `pre.tail` is
  never given, so any long line left the window on the right instead of continuing on the
  next row. It wraps now, like a log viewer should.
- Fix: spoken lines are laid out with flexbox rather than a computed indent. Counting
  terminal columns and applying them as `ch` could never work - an emoji is not a whole
  number of `ch` - which is why two attempts at this failed. The head now keeps its natural
  width whatever it contains, and the text wraps underneath itself.
- Removed `termCols`, which existed only to serve that arithmetic.

## v3.74 patch7
- Withdrawn: the "(waiting behind N)" note added in patch6. Measured across a real session,
  SkyrimNet sends the next chunk about 0.11s **after** it already has the previous chunk's
  audio - the requests never overlap, so nothing ever queued and the note could never have
  appeared. The explanation in patch6 was wrong.
- Fix: the Proxy terminal was still a column out. `U+FE0F`, the variation selector, takes
  no column of its own but makes the character before it render wide; it was being counted
  as one. Every line whose icon carries one - the plain speaking head, and the wave markers
  - sat a column too far right.
- Add: the TTS server writes **starting**, **stopped** and **stopped while starting** into
  the fleet log, so the Proxy terminal shows its life the way it shows the LLM servers.

## v3.74 patch6
- Add: a spoken line that arrived while others were still being generated says
  **(waiting behind N)**. SkyrimNet sends a long reply as several chunks at once and the
  panel forwards them all immediately, but audio.cpp serves one request at a time - the
  config carries `"threads": 1` - so the second and later chunks queue there. Their text
  appeared instantly while the speed figure arrived much later, which looked like the
  panel stalling on everything after the first sentence.
- The count is released in a `finally`, so a request that fails does not leave the queue
  looking permanently occupied.

## v3.74 patch5
- Add: audio.cpp reports `x-audiocpp-audio-duration-ms` and the panel only noted that the
  header existed. It now reads it and compares it with the length of the WAV actually
  received. If they disagree the terminal says so - that separates the model generating
  too much from a file coming back padded, which look identical from outside.
- Fix: the header list was logged on every line rather than once a session.

## v3.74 patch4
- Fix: every spoken line in the Proxy terminal had a blank row under it, which threw the
  alignment out. The check for "is this line a block" looked for `display:block` in the
  first 20 characters of the markup - it begins at character 26, so it never matched once.
  A class is used now, matched from the start.
- Fix: Terminate did not turn red for a running TTS server, only for running LLM servers.
  It stops both, so it lights for both.
- Change: audio.cpp writes one log per panel session, named like the fleet logs, and the
  TTS Server terminal shows this run rather than everything since the folder was made. A
  single `tts-server.log` from before the change is still read.
- Add: when a line produces far more audio than its words can account for - one measured
  case gave 56.5s for 24 words - the terminal says so. It looks like the panel stalling,
  and it is the model continuing past the end of the sentence.

## v3.74 patch3
- Fix: the Build choice added in patch2 described the wrong hardware. It said the profiles
  differ by GPU architecture; they do not. The release ships the same three names -
  portable, balance, fast - for the **CPU-only** builds too, where GPU architecture would
  mean nothing, so they are the host CPU instruction baseline. The GPU requirement is the
  same for both and comes from the prebuilt CUDA runtime: compute capability 7.5, an RTX
  20-series card or newer.

## v3.74 patch2
- Add: the installer fetches **both** the balanced and fast CUDA builds, and the TTS page
  offers a **Build** choice between them. Switching needs a restart, not another install.
- The two differ in the **CPU** instructions they were built against, not the GPU: the
  same three profile names are used for the CPU-only builds, where GPU architecture would
  mean nothing. The GPU floor is the same either way - compute capability 7.5, so RTX
  20-series or newer - and is set by the prebuilt CUDA runtime. Since the GPU does the
  work on a TTS path, expect little or no difference; balanced stays the default.
- Each build unpacks into its own subfolder while the shared CUDA runtime stays at the
  root, so the DLLs are not duplicated; the server is started with the root on `PATH` so a
  profile executable can still resolve them.
- The fast build is optional: a release that ships without one still installs, and the
  choice is only shown when both are really on disk.

## v3.74 patch1
- Fix: the TTS page buttons and the header **Launch TTS** button kept separate state, so
  starting from one left the other showing the old thing. They share one flag now, and one
  function repaints both.
- Fix: the TTS page never repainted during a start or stop, which is what left its buttons
  stuck until a refresh. The test `curDsub === "tts"` has been dead since TTS became its
  own tab in v3.73 patch1 - three of them.
- Fix: during a stop the header read "TTS running..." because the last reported state was
  checked before the action in flight. The action wins now.
- Change: the TTS GPU list reads like Live Network - device number, board partner, card.
- Add: **TTS Server (audio.cpp)** as a terminal feed, so the engine's own output can be
  read in Split View beside anything else.
- Change: the remote tail guard is an allowlist rather than "everything except kind=file".
  A feed added later that took a caller-supplied path would otherwise have been reachable
  from remote by default.

## v3.74

Everything from the v3.73 patches, with two changes that prompted the release.

**The Higgs installer no longer trusts what it finds**
- It kept whatever was already in its folder if an `audiocpp_server.exe` was there, which
  adopted a CPU-only build a user had unpacked by hand - the real engine never arrived and
  the settings pointed at the wrong one. Marking our own installs was not enough either: a
  marker still vouched for a folder antivirus had since gutted. **The engine folder is now
  cleared and reinstalled every time.** It is a couple of hundred MB; the 5 GB model is
  still kept when whole and resumed when not.
- A finished install also sets **Who translates for SkyrimNet** to *The panel*, and fills
  the proxy and server ports if blank. Leaving that pointing at a wrapper the user does not
  have produces silence with nothing to explain it.
- A settings write that fails after a good download is reported in amber rather than passed
  off as success. An outright failure is red, under the button.

**The GPU row said something untrue**
- Leaving it unpinned was labelled "no pin - every visible card is offered". The server
  config carries `"device": 0`, so unpinned means the **first** card and nothing else. On
  one card that is correct and nothing needed doing - but the label gave no way to know
  that, so people reasonably assumed they had missed a step. It now reads
  "Automatic - <your card> (your only card)", or names which card will be taken when there
  are several, with a warning that it may be the one already running your dialogue model.

**Step 7 says it is manual**
- It carries `ok: () => false` - nothing can ever satisfy it but the tick - so it sat red
  indefinitely for anyone who did not realise. It now shows a pulsing
  **Manual step - click the tick**.

## v3.73 patch11
- Fix: the installer adopted **any** `audiocpp_server.exe` already sitting in its folder
  and skipped the download - so a CPU-only build unpacked there by hand meant the real
  engine never arrived, and the settings pointed at the wrong one. It now records the
  release it installed in `.pandorum-engine.json` and only skips when that matches;
  anything else is cleared and replaced. A folder that cannot be cleared stops the install
  with a reason rather than continuing.
- Fix: a finished install now also sets **Who translates for SkyrimNet** to *The panel*,
  and fills the proxy and server ports if they are blank. An install that leaves the
  wrapper pointing at software the user does not have produces silence.
- Fix: a settings write that failed after a good download reported plain success. It is now
  shown in amber under the button; an outright failure is shown in red, as before.
- Add: step 7 of the Main Guide carries a pulsing **Manual step - click the tick** note.
  Nothing can ever detect it, so it sat red indefinitely for anyone who did not realise.

## v3.73 patch10
- Change: the **Timestamps** and **Insert TTS** buttons read `Timestamps: On` /
  `Insert TTS: Off`, with On in the same blue glow as Remote Access and Fullscreen in the
  header - so a switch looks the same wherever it appears. Timestamps still reports the
  terminal it belongs to, including the copy in the outer bar in full-window Split View.

## v3.73 patch9
- Removed the Model Source selector added in patch8. Loading from safetensors works, but
  the engine caps `weight_type` at q8_0 for this family, so it could not do the one thing
  it was wanted for. The TTS page is back to picking a GGUF from the models folder.

## v3.73 patch8
- Add: **Model Source** on the TTS page - a ready-made GGUF, or the original safetensors
  folder. GGUF keeps the model picker and Rescan exactly as before.
- Add: with safetensors selected, a **Weight Type** list applied as the weights load:
  native, BF16, FP16, FP32, Q8_0. Changing it needs a restart, not a conversion.
- The list is what the engine accepts and no more. Asked for anything smaller it answers
  "weight_type currently supports only native, f32, f16, bf16, and q8_0", so the k-quants
  the converter offers are deliberately absent - offering them would be offering a failure.

## v3.73 patch7
- Fix: the startup diagnosis added in patch6 read a blind 8KB tail of a log that spans
  every run, so it reported a **previous** failure after the cause had been fixed. The
  position the current run starts at is recorded when the server spawns, and only that
  part is read.
- Fix: **Stop** on the TTS page was disabled during startup - exactly when you want it, if
  a model is taking minutes or is never going to answer. It is now only dead while a stop
  is already running.
- Add: an **Installed** badge beside Install Higgs v3 when the engine and a model are
  present and selected.

## v3.73 patch6
- Fix: a TTS server that died while loading left the panel on "waiting for it to answer"
  for ever - it was watching the port, and a server that dies never opens one. The process
  is now polled, reaped, and its log read to say why.
- Add: two hints for GGUFs that will not load. A **tensor-only** build says it needs its
  sidecars (config.json, tokenizer, chat template) in the same folder; a GGUF written by
  **another converter** says audio.cpp cannot read its tensor metadata.
- Fix: downloading a log prompted "leave site?". The link was a plain `<a href>`, which
  counts as a navigation and armed the close-page guard. It carries `download` now.

## v3.73 patch5
- Fix: "session start" was written with `log_error`, which **created an error log on every
  clean run** - so there was always an error file, containing only a banner. It goes in the
  ordinary log now; the error log writes its own header naming the version when a real error
  first arrives. A clean session leaves no error file at all.
- Audited the other 21 `log_error` calls: all describe something that actually failed, so
  none were changed. The IP-allowlist rejections stay errors deliberately - they are the
  usual explanation when SkyrimNet cannot reach the panel. A gate check now fails if a
  `log_error` call does not describe a failure.
- Add: **Clear All** in Log > Errors. Empties the collected issues and this session's error
  log, asks first, host-only. It also clears the record of which server-log lines have
  already been scraped, so a line that has been cleared can be seen again.

## v3.73 patch4
- Fix: a slow state read was logged with `log_error`, which writes to the error log **and
  raises a UI issue** - so a timing observation looked like a fault. There is now a
  `log_warn` level: panel.log, tagged, no issue raised. The slow model-folder scan was the
  same and is demoted too.
- The error log is for things that failed. A gate check fails if any timing observation is
  logged as an error.

## v3.73 patch3
- Fix: `/api/state` took ~750ms, of which ~710ms was port probing. Probes are already run
  in parallel, but the priming pass and the read disagreed about which ports: priming used
  the slot's **stored** port while the read used the one **parsed from the launcher
  script**, and the TTS port was never primed at all. Any port they disagreed on fell
  through to a serial probe costing a full 350ms timeout each.
  Both now resolve ports identically. Four dead ports went from 1401ms to 352ms in test.
- Fix: priming skipped batches of fewer than two ports, so a single uncached port was
  always probed serially.

## v3.73 patch2
- Fix: long lines in the Permissions tree ran across into the next column. SVG text does
  not wrap, so they are now broken at word boundaries and the box is sized to whatever the
  columns came to.
- Change: the TTS page is divided into headed sections - TTS, Install, Folders & Model,
  Voice, Ports & Naming, Audio Tags - each separated by a rule.
- Change: **Install Higgs v3** is bigger and lit in the accent colour.

## v3.73 patch1
- Change: **TTS is its own tab**, under Server, rather than a sub-tab of Proxy. The TTS
  Terminal stays with the other terminals.
- Change: spoken lines are shown in the Proxy terminal by default.
- Change: the install button reads **Install Higgs v3**.

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
