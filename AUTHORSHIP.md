# Authorship

PandorumLLM is the original work of **Pt0l3my**: its code, and also its ideas, features, workflows and
designs, which were conceived, built and first published here.

## My position

I do not consent to PandorumLLM's ideas, features or designs being copied into, re-implemented in or
integrated into other applications, whether or not any of its code is copied, and whether or not
credit is given. "Inspired by", "ideas, not code" and "credit where it's due" are not permission.

If you build tools for SkyrimNet, build your own ideas. If people want something PandorumLLM does,
point them to PandorumLLM. If you want to cooperate, ask me first.

The terms that bind everyone who uses PandorumLLM are in [LICENSE](LICENSE): sections 3 (no derivative
or competing works) and 4 (names and identity).

## First published here

The public repository's commit and release history is the dated record. Where a version is given, it is
the earliest version the changelog names; "by" means the work shipped no later than that version. Early
releases were numbered as versions of their own (v1.5, v2.31); later ones as patches of a version (v3.80
patch63). This list is not complete.

### The proxy and routing

| Work | Version |
|---|---|
| **The thinking proxy.** One listener per SkyrimNet provider port, each job forwarded to the server its provider sits on, reasoning harvested apart from the reply, a thinking switch per provider. Built on my own earlier SkyrimNet-Proxy.py. | before v1.4 |
| **The GPU priority gate.** Providers ranked High, Normal or Low; high-priority work holds lower tiers on the same GPU, so in-game lines go ahead of background jobs. | by v2.16 |
| **Per-port provider slots.** Each provider's layout, its sample values detected from what SkyrimNet actually sends, sampler overrides adjusted on the fly while the server runs, and live thinking and cache switches. | by v2.31 |
| **The Diary grammar rail.** A GBNF grammar held on SkyrimNet's Diary job. | by v1.8 |
| **Reply length from speech.** A dialogue reply's token cap calibrated from measured TTS speech rate. | by v3.74 patch92 |
| **SkyrimNet YAML.** SkyrimNet's provider configuration written from the panel's own routing. | by v2.43 |

### Live Network

| Work | Version |
|---|---|
| **The map.** GPU, server and SkyrimNet provider drawn as one network, each link coloured by its status (dashed red where a listener isn't live). | v1.0 |
| **Colour by GPU.** Every chain coloured after its GPU, and that colour carried down to each server and provider, repeated as a bar on each box. | v1.3; v2.52 |
| **Wiring by drag.** Drag a provider onto a server, or a server onto a GPU, and it takes effect at once; drop a box anywhere else to detach it; a server takes any number of providers. | v1.5; v2.54; v3.76 patch39 |
| **The live model on each server.** Each server box shows its model, coloured by whether it is serving. | by v2.3 |
| **The one place wiring happens.** Live Network as the first tab, with the PC's GPUs at its head (switched on and off there), so GPUs, servers and providers are managed in one view. | v2.51; v2.66 |
| **Click tracing.** Click any box and its whole chain lights up, from GPU to provider. | v2.50 |
| **Every action reported,** with its priority. | v2.55 |
| **Links into it.** An allocation line, or a provider's name anywhere in the panel, opens Live Network with that server or provider lit up. | v2.78; v2.79; v3.76 patch16 |
| **The read-only view.** The same map for a remote viewer, with model file names hidden. | v2.29; v3.65 |
| **Host and client.** Point the panel at another PC's panel and the Client tab draws that machine's Live Network. | v3.68 |
| **The panel's own providers** (PTI, PME) placed by drag and drop like any other. | v3.74 patch38 |

### Terminals and views

| Work | Version |
|---|---|
| **The Proxy terminal.** One bracketed record per request, its own response lines beneath it, token counts, speed and time on every row; which providers and which outputs are shown is yours to choose. | early |
| **The Thinking terminal.** Each model's reasoning, live, as requests are answered. | by v2.2 |
| **The Split View terminal.** | by v2.4 |
| **Full Window and normal views for the terminals,** and the panel's full-screen mode. | v1.3 |
| **UST (Unified Source Terminals).** One colour language for names, spoken lines, tags and numbers across every terminal, the payload viewer and the JEV view. | |
| **The payload viewer for llama.cpp,** with each request's reasoning content beside its reply. | by v3.74 patch174 |
| **Per-job statistics,** including the time each job spends queued; the Server Statistics page. | by v2.31 |

### Servers, launchers and models

| Work | Version |
|---|---|
| **The Launcher Creator and its editor.** | by v1.1 |
| **The Launcher Inspector.** | by v2.13 |
| **Server cards that write their own launcher.** Switch a runtime option or change a number, and the panel rebuilds the server's launch template there and then. | |
| **Launch and terminate the whole fleet with one click,** colour-coded launcher buttons, and a status indicator that counts running servers by colour. | |
| **GPU detection and pinning.** Each card found and named after its maker, its UUID hidden until clicked, and each server kept on the card you choose. | by v2.0 |
| **The allocator.** Each server card shows where every part of its model went at launch (weights, drafter, projector, KV cache, recurrent state, compute buffers and MTP context), on which device, and whether it loaded, read from llama.cpp's own log; the allocator log checks each launch's allocations against what the driver reports as actually resident, and says so when they disagree. | by v3.74 patch48; card v3.75 patch3; log v3.76 patch86 |
| **Model labels by tensor.** A model's kind (dense, MoE, hybrid, decision, encoder and more) read from the model file itself and shown as labels. | |
| **Every downloader and updater,** with their screens and SHA-256 checks. | |
| **The Hub's LLM page.** Models on Hugging Face built on chosen bases, found by tag and kind, each row with its architecture, LM head and tie_word_embeddings read from its own config and tensor names and flagged red when they disagree; the model tree laid out as Hugging Face's; a card with the README, a tensor check, and the GGUFs with their fit, an output-layer check from the header and a SHA-256-checked download. | v3.91 patch3 |
| **The Hub's integrity read,** after the owner's quantization tools: a stale tie flag told from a broken head, short and missing shards, an Integrity column; the card's reading of every tensor header - the head compared row by row with the embeddings, the Gemma 4 convert keys, the attention geometry, the tensor families and a quantization plan for the HB16 head; a GGUF's head and embedding types and head_count_kv. Customize Columns, the Recently uploaded sort, the card in its own frame with its styles and videos, the model tree as Hugging Face lays it out, and server cards that fill the row. | v3.91 patch4 |
| **The nine-tab layout:** Server with Host, Client and Launcher File, JEV Diagnostics a Host page; Settings with Folder Settings, Backend Engines - each engine's installer on its own page, audio.cpp's with its own download record - Permissions and Customization; every guide under User Guide; the Main Guide and every message naming the new places; the Hub's tables sized to their content. | v3.91 patch5 |
| **Hub > LLM's deeper search:** models built on a base through other models found by the base's architecture and size, a tie settled by the models each names; imatrix and static GGUF columns from a model's quantization repos; base, kind, GGUF size range and architecture as labels under a name; the Hub's lists in fields that scroll; the model tree's elbows below the names; the audio.cpp Folder on Folder Settings. | v3.91 patch6 |
| **Tensor Parallelism per server:** a server card's model cut across its own GPU and pooled ones with shares by memory bandwidth, what -sm tensor needs held and the owner's values given back, a build, architecture or fit that cannot run it refusing Start and the fleet launcher holding that server, the pool dashed in Live Network; every card link opening its own Sampler Guide entry; Run on CPU's RAM pre-check; a multi-file download told once, as one bundle, with a quant of the running repo joining it. | v3.91 patch7 |
| **Tensor Parallelism measured per GPU:** a share beside each pooled GPU with its percent; the allocator report drawn as a window per GPU of the pool, a cut buffer by the card's share and each card's total measured before the launch and once serving, with what else loaded there named; Hub > LLM drawing every row and reading a row as it comes into view, column lines on both Hub lists, "+N" listing every GGUF repo of its kind, a model tree that shows names whole and scrolls sideways. | v3.91 patch8 |
| **The public release of the v3.91 cycle:** lists that keep their place when their page is drawn again, a batch of read rows redrawing only those rows; one TTS engine, audio.cpp; locked folders read-only on every page; a Hub search that judges a model by what it weighs, not by its label, searches English models, and leaves out - and counts - a model that is not intact. | v3.95 |

### Decision models and JEV

| Work | Version |
|---|---|
| **Native decision models for SkyrimNet.** Detected from the model's own header and labelled DECISION; SkyrimNet's typed decisions passed to llama.cpp's own `/v1/systemone`; a server too old for them answers with a request to update. | v3.80 patch58 |
| **The Decision Models page.** A catalog of decision models llama.cpp runs directly, downloaded with SHA-256 checks, a check that the installed llama.cpp can serve them, and a step-by-step Guide. | v3.80 patch58–59 |
| **The decision-model scan.** Daily, and on demand, the curated collection is read and new models join the list with their size, licence and languages. | v3.80 patch60 |
| **Decisions on the Proxy terminal.** One row per decision with its tokens, speed and time; each answer on its own line in SkyrimNet's own words (a coded option as its description); names in UST colours. | v3.80 patch59–61 |
| **Model kinds, read from the file.** Encoder, embedding, reranker, encoder-decoder, diffusion and decision type labelled on every model; a server card warns when its model cannot write text and names the providers that would fail on it; Decision Models shows each model's kind. | v3.80 patch63 |
| **llama.cpp's errors in plain words,** on the error cards and the Proxy terminal, where a refused decision stands as a red row with its payload. | v3.80 patch63 |
| **The JEV view.** A decision's JEV label opens its questions, every option with its token count from the server's own tokenizer, the passes llama.cpp took and the answer with its likeliest options; Request and JEV switch the one record back and forth. Painted in UST colours. | v3.80 patch63–64 |
| **Passes from the server's own log.** Each pass a decision took, read while it was answered: its tokens and time, and each batch of it, drawn as a tree; a lev choice's row shows its passes. | v3.80 patch63; v3.80 patch65 |
| **JEV Diagnostics.** A refused pass and why, and real risks only: a pass near the context, an encoder near its micro-batch, Kev past its batch; a warning shows on the decision's JEV label. | v3.80 patch64–65 |
| **Names and the player from decisions.** Every name in a decision's state, its recent dialogue and its last exchange joins the cast; the player's name is read from a decision too. | v3.80 patch63–64 |
| **Target selection diagnostics.** Every target decision - who answers the player, who speaks next and to whom - set against the cues SkyrimNet sent with it: the crosshair, a name in the line, the last exchange, proximity, a reply owed and whether the one owing it can speak. Kept per session and shown as two cards, Player Target Selector and NPC Target Selector, with a drawer tab per model: Input vs Outcome, and five groups from Followed the cues to Failed to respond, each category drawn as its pattern and opening on its decisions and their exchange. | v3.91 patch1 |
| **The diagnostics report.** One Markdown report per selector for prompt work: what it shows, what to look at and what to do, the figures per model, the decision prompt word for word, and every case for review with its cues, its answer and its exchange. | v3.91 patch1 |

### TTS

| Work | Version |
|---|---|
| **The TTS updater and downloader,** with SHA checks. | |
| **Automatic NPC voice allocation by ID,** shown in the terminals. | |
| **The Sample Vault.** | by v3.75 patch11 |
| **TTS backend settings and EOC handling.** | |
| **TTS calibration and monitoring.** | |
| **Audio tags chosen by clicking boxes on a graphic, and banned for a number of rounds.** | |
| **The player tag system, PTI and PME.** | |
| **Thought audio** for SkyrimNet's NPC thoughts and the player's own. | |
| **The TTS GPU clock hold.** | |
| **TTS on the CPU,** one switch, with the processor named and the GPU menus greyed; the allocation lines naming the card by pin number, maker and name. | v3.91 patch3 |

### Song Generator

| Work | Version |
|---|---|
| **The song vault with its built-in player.** | by v3.80 patch1 |
| **The voice extractor and converter,** picking an NPC's voice by ID and placing it into the songs SkyrimNet requests. | by v3.80 patch1 |

### Setup, guides and access

| Work | Version |
|---|---|
| **The Sampler Guide,** written for SkyrimNet's jobs, cross-referenced with the runtimes, samplers and sampler chain across the panel's pages. | by v2.31 |
| **The step-by-step User Guide,** and the graphic guides for TTS, the Song Generator and decision models. | by v2.49 |
| **The dual-PC setup with its client bridge.** | by v1.9 |
| **Five client panels, controlled from the host.** Up to five PCs registered by address, each with a flap on Live Network > Client and Server > Client showing that PC's own Live Network, Servers, Server Editor and Server Statistics; Client Settings to link and detach a client's Live Network boxes and use its server cards, each working only once that PC trusts its host. | v3.91 patch2 |
| **Remote Access,** and its Permission Tree. | by v2.17; by v2.23 |
| **Profiles of the whole setup.** One profile holds every GPU's state, every server (its GPU, name, port and parameters), every provider on each server and those not yet placed, and both PCs' addresses; saving or loading one switches the whole fleet layout in a step. | v1.5 |
| **The Helper.** An interactive setup flowchart. | v1.3 |
| **The Recommended Setup helper,** pairing servers to GPUs by size. | v1.4 |
| **The Log page.** The panel's logs as cards, the error records, a diagnostics dump, and a self-test that checks the panel's own workings on your PC in a scratch folder, saves its report for copying and files any panel fault under Log > Errors. | by v2.9; dump by v3.72 patch26; self-test by v3.76 patch192 |
| **Customization.** Eleven theme presets with live previews, custom colours for each part of the interface, your own colours saved as a preset, and switchable effects. | v1.9; v2.76; v3.72 patch1 |
