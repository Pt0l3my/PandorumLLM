![PandorumLLM](https://github.com/user-attachments/assets/039c932c-d545-4a42-adb9-fe66f59756b5)

# PandorumLLM

**A browser control panel for a local llama.cpp fleet, built for SkyrimNet.**

One Python file, no dependencies, no cloud. It starts your servers, routes SkyrimNet's
providers to them, and shows you what the models are actually doing while you play.

---

## What it does

SkyrimNet needs a dozen or so providers — dialogue, combat, memory, vision and the rest —
and each one has to reach a running llama.cpp server. Doing that by hand means juggling
PowerShell launchers, ports, GPU assignments and a `Providers.yaml` you have to keep in
sync. PandorumLLM does the juggling.

- **Run several servers across several GPUs.** Cards are pinned by UUID, so a driver update
  or a reboot can't quietly swap which model lands on which card.
- **Build launchers without writing PowerShell.** Pick a model, set context and batch sizes,
  and the launcher is generated for you — or bring your own `.ps1` and the panel reads it,
  including model paths held in variables.
- **Route providers by dragging them.** A live network graph shows GPU → server → provider,
  and drops take effect immediately.
- **Watch it work.** Two live terminals: the proxy feed, and the models' reasoning as it's
  generated. Colour-coded per provider, scalable, in whichever font you like.
- **See where the time goes.** Per-provider generation, prefill and decode timings with
  tokens/second, input and output token counts, cache hits, queue time, and MTP acceptance
  rates if you're running speculative decoding.
- **Tune samplers per provider.** Read what SkyrimNet is actually sending, override any
  parameter for one provider, and clear it again in a click.
- **Generate `Providers.yaml`.** Built from your live setup and written where SkyrimNet
  wants it.
- **Follow the guide if you'd rather not think about it.** An eight-step setup flow that
  checks its own work and tells you what's left.

---

## Requirements

- **Windows** with PowerShell 7 (`pwsh`)
- **Python 3.9+** — stdlib only, nothing to install
- **llama.cpp** (a CUDA build, if you have NVIDIA cards)
- **NVIDIA GPU(s)** with `nvidia-smi` on PATH for detection
- **SkyrimNet**, if you want the reason this exists

---

## Install

1. Download the latest release zip and extract it to `C:\` — you'll get `C:\PandorumLLM\`.
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

- **No outbound connections.** It never phones home, checks for updates, or sends telemetry.
  The only external address anywhere in the source is a GitHub URL shown as text for you to
  copy if you want it.
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

- **[CHANGELOG.md](CHANGELOG.md)** — every released version, back to v0.8
- **[DEVELOPMENT.md](DEVELOPMENT.md)** — architecture, traps, and how a release is cut
- **README.txt** — the user-facing readme that ships in the zip

---

## Reporting something

Open an issue with the version number, what you did, and what happened. If the panel is
misbehaving in the browser, the **Log → Observer** tab records what the page did and what it
declined to do — start recording, reproduce it, and attach the export. It names no folders,
IP addresses or model files.
