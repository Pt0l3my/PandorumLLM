![PandorumLLM](https://github.com/user-attachments/assets/039c932c-d545-4a42-adb9-fe66f59756b5)

# PandorumLLM

**Control panel + proxy built for SkyrimNet — a reliable, local llama.cpp solution.**
Any models, any GPU setup, one or two PCs: link each GPU to its own server, then
allocate every Provider (job) to whichever server you want with simple drag & drop —
any configuration you can think of, launched with one click.
Setting up llama.cpp servers means no files, Python, API or C++ to mess with — every
option is a curated field to enter or a setting to toggle and choose.
No install — unzip the folder anywhere, double-click the exe, and the panel opens in
your browser. One Python file, no dependencies, no cloud, no accounts.

---

## 🔀 The proxy — one port per Provider

- **Per-Provider samplers, edited on the fly.** Force temperature, top-p, top-k,
  min-p or DRY for a single job mid-session — click a chip, set a value, done. Injected
  100% llama.cpp-compliant, cleared again just as fast.
- **Live values.** Chips show each Provider's settings actually in effect — from the
  request, from the server, or unknown.
- **Thinking on/off, on the fly.** Per Provider, mid-session, no API editing — and
  the thinking process streams live in its own terminal, colour-coded per job.
- **Job-specific rails**, like the Diary grammar guard, applied automatically.
- SkyrimNet simply points each provider at its port — the panel writes
  `Providers.yaml` for you, exactly where SkyrimNet expects it.

## 🚀 Servers & launchers

- **One-click launch** of every server, with a live tally (`Running… 3/3`).
- **Any GPU setup.** Multiple GPUs and servers, cards pinned by UUID so nothing
  silently swaps; one PC or two over your LAN.
- **No argument files to edit.** Launcher options — context, batch sizes, flash
  attention, caching and the rest — are toggles and fields in the UI, handled behind
  the scenes.
- **Launcher Creator.** Build and inspect llama.cpp launchers from a template — no
  PowerShell writing needed.
- **Server Editor.** Edit a server's launcher settings directly from the panel.
- **Bring your own `.ps1`.** Load existing launcher files onto servers — every
  parameter and model path is auto-detected and read (even paths held in variables),
  and models and settings are allocated automatically.
- **Recommended Setup** assigns every Provider to the best server for it, based on
  your models and GPUs.
- **Live network graph** — GPU → server → Provider drawn as lines; drag a job to
  re-route it, effective immediately.
- **Profiles** save and restore whole configurations.

## 📊 Monitoring

- **Per-server graphs**, one bar per model: prefill and decode speed (t/s), response
  time, token usage, thinking tokens, queue time, cache hits and time saved,
  speculative-decoding acceptance and draft size, generations, loads and errors.
- **Per-Provider graphs**: generation time, input / output / thinking tokens and
  errors — click a Provider's emoji for its generation, prefill and decode breakdown
  with tok/s.
- Three live terminal views — server output, proxy traffic and model thinking —
  colour-coded per Provider, with adjustable font and size.

## 🔒 Remote & safety

- **Remote view** from any other PC on your LAN — read-only, enforced server-side,
  with paths, addresses and hardware details redacted. Off-LAN access is rejected.
- **Launcher sweep** flags constructs that don't belong in a llama-server launcher —
  a mistake-catcher, not a guarantee.
- Open source, one readable file, zero cloud; every release ships with a SHA-256
  checksum.

## 📖 Guides

- **Main Guide** — step-by-step setup that checks its own progress and tells you
  what's left.
- **Sampler reference** tailored for SkyrimNet use — what each parameter does and
  where it matters.

## 🧾 Requirements

- **Windows** with [PowerShell 7](https://github.com/PowerShell/PowerShell) (`pwsh`)
- **[Python 3.9+](https://www.python.org/downloads/)** — standard library only,
  nothing to pip-install
- **[llama.cpp](https://github.com/ggml-org/llama.cpp)** — a CUDA build if you run
  NVIDIA cards
- **NVIDIA GPU(s)** with `nvidia-smi` on PATH — it ships with the
  [driver](https://www.nvidia.com/en-us/drivers/)
- **[SkyrimNet](https://github.com/MinLL/SkyrimNet-GamePlugin)** — the reason this
  exists

---

## Install

1. Download the latest release zip and extract it — anywhere works; `C:\` is the usual
   spot, giving `C:\PandorumLLM\`.
2. **Verify it first** (see below).
3. Run `PandorumLLM.exe`, or `python fleet-panel.py` if you'd rather see the console.
4. Open the panel, set your three folders in **Folder Settings**, and follow the **Main Guide**.

---

## Verify what you downloaded

Every release ships a SHA-256. Check it before you run anything:

```
certutil -hashfile PandorumLLM-v3.65-Beta.zip SHA256
```

Compare it against the `.sha256.txt` attached to the same release. If they don't match,
don't run it — and tell me where you got it from.

---

## Is it safe?

Read the source. That's the honest answer, and it's why the source is here.

**There's no code signing**, so Windows SmartScreen will warn you the first time. That
warning means "we don't know who wrote this", not "we found something wrong" — and it will
appear for any unsigned tool from an individual.

What the app does and doesn't do:

- **No automatic outbound connections.** It never phones home or sends telemetry. The one
  outbound request in the source is the **Check for update** button in Folder Settings,
  which asks github.com for the newest llama.cpp release tag — only when you press it, and
  nothing about your setup is sent.
- **It runs PowerShell** — that's the whole job. It launches the `.ps1` files in your
  launcher folder. **A launcher is a script, and running one runs whatever is in it.** There's
  a **Sweep launcher folder** button in Folder Settings that reads every `.ps1` there and
  flags anything that doesn't belong in a file whose only job is to start llama-server.
  A clean sweep means nothing alarming was found — not that a file is safe. Only run
  launchers you wrote or trust.
- **It only touches folders you point it at.** Path containment is enforced server-side.

### Remote access

Off by default. If you turn it on, another PC on the same network can open the panel
**read-only** — it can watch the terminals and the network graph, but changes nothing. IPs,
file paths, model filenames and GPU serial numbers are stripped before they leave the
machine.

**There's no password.** The read-only wall is the boundary. Worth knowing: a viewer can
read the live terminals, which include generated NPC dialogue. If you share a network with
people you'd rather not show that to, leave remote access off.

---

## Licence

**Use it, modify it for yourself, don't republish it.** See [LICENSE](LICENSE).

The source is here so you can read it before you run it. Being able to read it isn't
permission to repost it.

---

## Also here

- **[DEVELOPMENT.md](DEVELOPMENT.md)** — architecture, traps, and how a release is cut
- **README.txt** — the user-facing readme that ships in the zip

---

## Reporting something

Open an issue with the version number, what you did, and what happened. If the panel is
misbehaving in the browser, the **Log → Observer** tab records what the page did and what it
declined to do — start recording, reproduce it, and attach the export. It names no folders,
IP addresses or model files.
