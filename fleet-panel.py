# ================================================================
#  fleet-panel.py  -  PandorumLLM  v0.1 Beta
#  http://localhost:1235/   (LAN too: http://<this-pc-ip>:1235/)
#
#  The panel is now the ENTRY POINT: it launches nothing on start.
#  The [Launch stack] button starts the proxy dashboard + thinking
#  windows and every enabled server slot, all minimized, with their
#  console streams tee'd into the log folder - which feeds the
#  Dashboard / Thinking Content / Log tabs and the speed readouts.
#
#  Vertical tabs: Servers (Server Slots | Launcher Creator |
#  Launcher Inspector), Dashboard, Thinking Content, Setup, Log.
#
#  Still thin: Launch/Stop per slot routes through
#  launch-llm-fleet.ps1 (-Slot ... -Force / -Stop).
#
#  State: fleet-config.json (slots, settings, creator templates),
#  fleet-history.json (last 50 launches).
# ================================================================
import hashlib
import ctypes, glob, hashlib, hmac, ipaddress, json, os, re, secrets, shutil, socket, subprocess, sys, threading, time, traceback
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from urllib.request import urlopen, Request
from urllib.error import HTTPError

APP_NAME    = "PandorumLLM"
APP_VERSION = "v3.74 Beta"
APP_RELEASE_TAG = "v3.74-beta"            # the tag this build ships under
APP_PATCH = 0                                 # patch number; 0 = none
TERM_SCALE_KINDS = ("dashboard", "thinking", "splitd", "splitt", "tts")
TERM_SCALE_LEGACY = ("split",)                # older configs stored one "split" entry
_TTS_LANG_RX = re.compile(r"^[a-z]{2}(-[a-z]{2,4})?$", re.I)
TTS_FRAME_RATE = 12.5          # MOSS audio tokens per second of audio
TTS_ACPP_FRAME_RATE = 25.0     # Higgs Audio v3: 8 codebooks at 25 fps
TTS_SERVER_LOG_NAME = "tts-server.log"
TTS_LOG_NAME = "tts.log"                      # fixed name; the launcher writes it into log_dir()
APP_VER_UI = APP_VERSION.replace(" ", "-p%d " % APP_PATCH, 1) if APP_PATCH else APP_VERSION

def _build_id():
    """Identity of the file actually running: replacing a file is not the same as
    running it, and a stale instance on the port looks identical from the browser."""
    try:
        path = os.path.abspath(__file__)
    except Exception:
        path = "fleet-panel.py"
    try:
        with open(path, "rb") as f:
            blob = f.read()
        return {"path": path, "sha": hashlib.sha256(blob).hexdigest()[:12],
                "kb": len(blob) // 1024,
                "mtime": time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(path)))}
    except Exception:
        return {"path": path, "sha": "?", "kb": 0, "mtime": "?"}
BUILD_ID = _build_id()
TAKEOVER = []                                 # set when we displaced a running instance
PORT_CANDIDATES = [50607, 50617, 50627, 50637, 50647]   # edit these if they clash (valid ports: 1-65535)
PORT = PORT_CANDIDATES[0]                          # runtime value; set by choose_port()
MAX_SLOTS   = 20
MAX_TPL     = 20
STACK       = os.path.dirname(os.path.abspath(__file__))
CONFIG      = os.path.join(STACK, "fleet-config.json")
DEFAULT     = os.path.join(STACK, "fleet-config.default.json")
HISTORY     = os.path.join(STACK, "fleet-history.json")
ARCHIVE     = os.path.join(STACK, "ps1-launchers")
FLEET_PS1   = os.path.join(STACK, "launch-llm-fleet.ps1")
GH_RELEASES = "https://github.com/ggml-org/llama.cpp/releases"
GH_API      = ""  # update check removed - app no longer contacts GitHub

DEF_SETTINGS = {
    "llamacppPath": "",
    "launcherDir":  os.path.join(STACK, "ps1-launchers"),
    "templateFile": os.path.join(STACK, "launcher-template.ps1"),
    "onePC": True,
    "networkMode": "localhost",
    "peerAddr": "",
    "ttsServerExe": "", "ttsModel": "", "ttsServerPort": "1240", "ttsGpuId": "",
    "ttsPython": "", "ttsWrapper": "", "ttsWrapperPort": "7860",
    "ttsWrapMode": "off", "ttsAnswerPing": "on",
    "ttsEngine": "moss",                          # moss | audiocpp
    "ttsTags": "off",                             # inline control tags, audio.cpp only
    "ttsOutDir": "", "ttsVoiceDir": "",
    "termStamps": "on", "termInsTts": "on",
    "termStampsOff": "",                          # terminals hiding the time
    "splitSrcD": "dashboard", "splitSrcT": "thinking",
    "ttsAcppDir": "", "ttsAcppExe": "", "ttsAcppModelsDir": "", "ttsAcppModel": "", "ttsAcppModelId": "higgs",
    "ttsAcppFamily": "higgs_audio_tts", "ttsAcppRefSlots": "64",
    "ttsAcppVersion": "",                         # the release tag installed
    "launchArc": False,               # the guide step highlights instead
    "autoRefresh": 0,
    "srvEdOpen": False,
    "observerOn": False,
    "activeProfile": "",
    "outputDir":    os.path.join(STACK, "ps1-launchers"),
    "logDir":       os.path.join(STACK, "logs"),
    "modelsDir":    os.path.join(STACK, "models"),
    "yamlOutDir":   os.path.join(STACK, "providerYAML"),
    "panelIp":      "",
    "remoteIp":     "",
    "exitOnClose":  True,
    "termScaleMode": "manual",
    "termFontSize": 12,
    "termScaleOn": True,
    "termScales": {},
    "statsMonitoring": True,
}
ANSI_RX = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b\][^\x07]*\x07|[\x00-\x08\x0b\x0c\x0e-\x1f]")

# ---------------------------------------------------------------- config
def load_json(path, fallback):
    try:
        with open(path, encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception:
        return fallback

# Serializes every config read-modify-write so concurrent POSTs can't clobber
# each other's changes (a lost update - e.g. a GPU toggle overwriting a just-saved
# "2 PC" setting). All mutating endpoints run under this lock (see do_POST).
class _NullLock(object):
    """Stands in for CFG_LOCK where a request must not block the others."""

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


# Endpoints that start or stop a process rather than edit the config. They can run for
# several seconds, and nothing they do needs the config serialized - anything of theirs
# that does takes CFG_LOCK itself.
#
# They were relying on CFG_LOCK to stop a second request arriving mid-start, though, so
# each gets its OWN lock: still no double-start, and still no waiting on the other one.
# Tried without blocking, so a second press is told rather than queued.
NO_CFG_LOCK = frozenset(("/api/launch-stack", "/api/tts-server", "/api/higgs-install"))
_FLEET_LOCK = threading.Lock()
_TTSSRV_LOCK = threading.Lock()


CFG_LOCK = threading.RLock()

def save_config(cfg):
    """Write the config atomically, retrying a Windows lock rather than failing.

    os.replace answers WinError 5 when anything holds a handle on either file, even
    for an instant - an antivirus scan or the search indexer will do it, and both are
    busy right after the installer writes several gigabytes into this folder. The lock
    is transient, so back off briefly and try again; giving up on the first refusal
    loses the settings the user just changed.
    """
    tmp = CONFIG + "." + str(os.getpid()) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    last = None
    for attempt in range(8):                 # ~1.8s in total, then give up honestly
        try:
            os.replace(tmp, CONFIG)
            last = None
            break
        except PermissionError as e:         # WinError 5 / 32: someone holds a handle
            last = e
            time.sleep(0.05 * (attempt + 1))
        except OSError as e:
            last = e
            break
    if last is not None:
        try:
            os.remove(tmp)                   # do not leave .tmp files behind
        except OSError:
            pass
        raise last
    try:
        sse_notify("state")
    except NameError:
        pass

DEFAULT_PROVIDER_SEED = {
    1236: [("Dialogue", 1251, False, 0), ("GM", 1252, False, 0), ("Combat", 1253, False, 0), ("AI-Assistant", 1256, False, 0)],
    1237: [("Meta", 1254, False, 2), ("UT", 1255, False, 2)],
    1238: [("ActionEval", 1257, False, 1), ("Charbio", 1258, True, 1), ("Diary", 1259, False, 1),
           ("Memory", 1260, False, 1), ("Vision", 1261, False, 1), ("IntelEngine", 1262, True, 1), ("SeverActions", 1263, True, 1)],
}
DEFAULT_PROVIDER_GPUS = {}
DEFAULT_PROVIDER_PAIRS = {(nm, pp) for lst in DEFAULT_PROVIDER_SEED.values() for (nm, pp, _thk, _prio) in lst}

def is_default_provider(p):
    return (p.get("title"), int(p.get("port") or 0)) in DEFAULT_PROVIDER_PAIRS

def seed_default_providers(cfg):
    """Put the shipped providers back to their factory names and settings, in place.

    Every provider is found wherever it already is - attached to a server or sitting
    unallocated - and matched to its factory entry by port, which is what identifies it.
    Its name and settings are restored and it is left exactly where it was: this repairs
    providers, it does not reorganise them. Only a default that is missing entirely is
    created, and it arrives unallocated so nothing is silently attached to a server.
    Providers you added yourself are not touched at all.
    """
    factory = {}
    for port, entries in DEFAULT_PROVIDER_SEED.items():
        for (nm, pp, thk, prio) in entries:
            factory[pp] = (nm, thk, prio)
    everywhere = ([p for s in cfg.get("slots", []) for p in s.get("providers", []) or []]
                  + list(cfg.get("unallocatedProviders", []) or []))
    used = {p.get("id") for p in everywhere}
    def next_id():
        n = 1
        while ("prov%d" % n) in used:
            n += 1
        used.add("prov%d" % n)
        return "prov%d" % n
    seen = set()
    for p in everywhere:
        if p.get("custom"):
            continue                              # yours: left alone
        f = factory.get(int(p.get("port") or 0))
        if not f:
            continue                              # a default whose port was changed
        nm, thk, prio = f
        p["title"] = nm
        p["thinking"] = thk
        p["priority"] = prio
        p["diaryGrammar"] = (nm == "Diary")
        p["custom"] = False
        p["samplerOverrides"] = {}                # nothing forced
        p["samplerSource"] = "server"             # the shipped side
        p["detectSN"] = False
        p["emoji"] = DEFAULT_PROVIDER_EMOJI.get(nm, "")
        p["enabled"] = True                       # shipped state is on
        seen.add(int(p.get("port")))
    missing = [pp for pp in factory if pp not in seen]
    if missing:
        un = cfg.setdefault("unallocatedProviders", [])
        for pp in sorted(missing):
            nm, thk, prio = factory[pp]
            un.append({"id": next_id(), "title": nm, "port": pp, "thinking": thk,
                       "priority": prio, "diaryGrammar": nm == "Diary", "custom": False})
    return cfg

def load_config():
    cfg = load_json(CONFIG, None)
    if cfg is None and os.path.isfile(CONFIG):
        time.sleep(0.08)                       # torn read during a save - retry once
        cfg = load_json(CONFIG, None)
    if cfg is None:
        cfg = load_json(DEFAULT, None) or {}
    changed = False
    cfg.setdefault("launcherDirs", [])
    cfg.setdefault("slots", [])
    st = cfg.setdefault("settings", {})
    for k, v in DEF_SETTINGS.items():
        if k not in st or (st[k] == "" and v != "" and k != "llamacppPath"):
            st[k] = v
            changed = True
    # one-time: terminals now default to manual 12px (were auto 14px). Apply the new default
    # only to configs still sitting on the old default, so any custom size/mode is preserved.
    if not st.get("termScaleV12"):
        if st.get("termScaleMode", "auto") == "auto" and int(st.get("termFontSize", 14) or 14) == 14:
            st["termScaleMode"] = "manual"
            st["termFontSize"] = 12
        st["termScaleV12"] = True
        changed = True
    # repair booleans that may have been stored as strings by an older build
    for _bk in ("onePC", "devMode", "welcomeSeen", "termBlack", "termScaleOn"):
        if isinstance(st.get(_bk), str):
            st[_bk] = st[_bk].strip().lower() in ("1", "true", "on", "yes")
            changed = True
    cfg.setdefault("gpus", [])
    cfg.setdefault("unallocatedProviders", [])
    if not st.get("wiringV250"):
        # one-time move to the Live Network wiring model: existing links are parked so
        # every connection is (re)made in one place. Runs once, then never again.
        park = cfg["unallocatedProviders"]
        for _s in cfg.get("slots", []):
            for _p in (_s.get("providers") or []):
                _p["thinking"] = False
                park.append(_p)
            _s["providers"] = []
            _s["gpuId"] = ""
        st["wiringV250"] = True
        changed = True
    if not cfg.get("settings", {}).get("sevEmojiV2"):
        for s2 in cfg.get("slots", []):
            for p2 in s2.get("providers", []) or []:
                if p2.get("title") == "SeverActions":
                    p2["emoji"] = "📜"
                    changed = True
        cfg.setdefault("settings", {})["sevEmojiV2"] = True
        changed = True
    for s in cfg.get("slots", []):
        if s.get("script"):
            try:
                pp = parse_ps1_port(s["script"])
                if pp and 1000 <= pp <= 9999 and s.get("port") != pp:
                    s["port"] = pp
                    changed = True
            except Exception:
                pass
        s.setdefault("gpuId", "")
        s.setdefault("autoName", False)   # existing (already named) slots keep their names
        if "params" not in s:
            # migration: a slot's existing .ps1 becomes its parameter set, so the move
            # off launcher files loses nothing the user had already configured.
            seed = {"model": "", "vision": "N/A", "draft": "N/A", "content": ""}
            scr = s.get("script") or ""
            if scr and os.path.isfile(scr):
                try:
                    seed["content"] = open(scr, encoding="utf-8-sig").read()
                    mm = re.search(r'"(?:-m|--model)",\s*"([^"]+)"', seed["content"])
                    if mm:
                        seed["model"] = mm.group(1)
                    mv = re.search(r'"--mmproj",\s*"([^"]+)"', seed["content"])
                    if mv:
                        seed["vision"] = mv.group(1)
                    md = re.search(r'"--model-draft",\s*"([^"]+)"', seed["content"])
                    if md:
                        seed["draft"] = md.group(1)
                except Exception:
                    pass
            if not seed["content"]:
                seed["content"] = read_template(st)
            s["params"] = seed
            changed = True
        for p in s.get("providers", []) or []:
            p.setdefault("enabled", True)   # a disabled provider keeps its port shut; the
                                           # proxy and the yaml writer both honour this
            if "emoji" not in p:
                p["emoji"] = AGENT_EMOJI.get(p.get("title", ""), "")
                changed = True
    for g in cfg.get("gpus", []):
        g.setdefault("enabled", True)
    if not any("providers" in s for s in cfg.get("slots", [])):
        pid = 1
        park = cfg.setdefault("unallocatedProviders", [])
        for s in cfg.get("slots", []):
            s.setdefault("providers", [])
            s.setdefault("gpu", DEFAULT_PROVIDER_GPUS.get(int(s.get("port") or 0), s.get("id")))
            s["gpuId"] = ""                       # nothing is wired until Live Network says so
            for (nm, pp, _thk, prio) in DEFAULT_PROVIDER_SEED.get(int(s.get("port") or 0), []):
                # providers start unallocated, and with thinking off: the server enables
                # reasoning, then each provider overrides it for its own requests.
                park.append({"id": "prov%d" % pid, "title": nm, "port": pp,
                             "thinking": False, "priority": prio,
                             "diaryGrammar": nm == "Diary", "custom": False})
                pid += 1
        changed = True
    for s in cfg.get("slots", []):
        for p in s.get("providers", []) or []:
            if "custom" not in p:
                p["custom"] = not is_default_provider(p)
                changed = True
    if "creatorSlots" not in cfg:
        cfg["creatorSlots"] = [{"id": "tpl1", "title": "my launcher 1",
                                "content": read_template(st),
                                "model": "", "vision": "N/A", "draft": "N/A"}]
        changed = True
    if st.get("launcherDir") and cfg["launcherDirs"] != [st["launcherDir"]]:
        cfg["launcherDirs"] = [st["launcherDir"]]
        changed = True
    if changed or not os.path.isfile(CONFIG):
        save_config(cfg)
    return cfg

def read_named_template(name):
    safe = re.sub(r"[^a-zA-Z0-9_-]", "", str(name or ""))
    p = os.path.join(STACK, "templates", safe + ".ps1")
    try:
        return open(p, encoding="utf-8-sig").read()
    except Exception:
        return ""

def list_templates():
    out = [{"id": "", "name": "PandorumLLM default (pins GPU by ID - for multi-GPU / multi-PC)"}]
    d = os.path.join(STACK, "templates")
    try:
        for f in sorted(os.listdir(d)):
            if not f.endswith(".ps1"):
                continue
            nm = f[:-4]
            try:
                first = open(os.path.join(d, f), encoding="utf-8-sig").readline()
                m = re.search(r"TEMPLATE_NAME:\s*(.+)", first)
                disp = m.group(1).strip() if m else nm
            except Exception:
                disp = nm
            out.append({"id": nm, "name": disp})
    except Exception:
        pass
    return out

def read_template(settings=None):
    path = (settings or {}).get("templateFile") or DEF_SETTINGS["templateFile"]
    try:
        return open(path, encoding="utf-8-sig").read()
    except Exception:
        return "# template file not found: %s\n# fix the path in [Setup]\n" % path

def log_dir(cfg=None):
    d = ((cfg or load_config()).get("settings", {}) or {}).get("logDir") or DEF_SETTINGS["logDir"]
    os.makedirs(d, exist_ok=True)
    return d

def pick_rotating(ld, prefix, maxn):
    """srv_slot1_1.log ... _5.log style rotation: fill free indices first,
    then truncate-and-reuse the oldest."""
    rx = re.compile(re.escape(prefix) + r"(\d+)\.log$")
    found = {}
    for p in glob.glob(os.path.join(ld, prefix + "*.log")):
        m = rx.search(os.path.basename(p))
        if m: found[int(m.group(1))] = p
    for n in range(1, maxn + 1):
        if n not in found:
            return os.path.join(ld, "%s%d.log" % (prefix, n))
    return min(found.values(), key=os.path.getmtime)

def prune_keep_newest(ld, pattern, keep):
    files = sorted(glob.glob(os.path.join(ld, pattern)), key=os.path.getmtime, reverse=True)
    for p in files[keep:]:
        try: os.remove(p)
        except Exception: pass

ERR_FILE = [None]
ERR_RX = re.compile(r"\b(error|fail(?:ed|ure)?|fatal|exception|traceback|cuda error|out of memory|unreachable)\b", re.I)
WARN_RX = re.compile(r"\bwarn(?:ing)?\b", re.I)
# In-memory, session-only issue log for the Log > Errors tab. Capped list (most recent
# 250 rows kept for display); running counters below are the true session totals.
ERR_LOG = []
ERR_TOTAL = [0]
ERR_BY_TYPE = {}
ERR_BY_LEVEL = {}

def _classify_level(msg):
    low = str(msg).lower()
    if re.search(r"\b(error|fail|fatal|exception|traceback|cuda|out of memory|unreachable|refused|denied)\b", low):
        return "ERROR"
    if "warn" in low:
        return "WARN"
    return "ERROR"

def _record_issue(source, msg):
    try:
        m = str(msg).strip()
        mm = re.match(r"^\[[0-9:. -]+\]\s*(\[[^\]]+\]\s*)?(.*)$", m)
        if mm and mm.group(2):
            m = mm.group(2).strip()
        words = m.split()
        text = " ".join(words[:250]) + (" ..." if len(words) > 250 else "")
        if len(text) > 2500:
            text = text[:2500] + " ..."
        title = (m.split(chr(10))[0]).strip()
        if len(title) > 90:
            title = title[:88] + ".."
        typ = (str(source).split() or ["log"])[0].lower()
        lvl = _classify_level(m)
        ERR_LOG.append({"ts": time.strftime("%H:%M:%S"), "level": lvl, "type": typ,
                        "source": str(source), "title": title or "(no message)", "text": text})
        if len(ERR_LOG) > 250:
            del ERR_LOG[:len(ERR_LOG) - 250]
        ERR_TOTAL[0] += 1
        ERR_BY_TYPE[typ] = ERR_BY_TYPE.get(typ, 0) + 1
        ERR_BY_LEVEL[lvl] = ERR_BY_LEVEL.get(lvl, 0) + 1
    except Exception:
        pass

def api_errors_snapshot(remote=False):
    if remote:
        return {"total": ERR_TOTAL[0], "byType": {}, "byLevel": dict(ERR_BY_LEVEL), "errors": []}
    return {"total": ERR_TOTAL[0], "byType": dict(ERR_BY_TYPE), "byLevel": dict(ERR_BY_LEVEL),
            "errors": list(reversed(ERR_LOG))}
def api_errors_clear(body=None):
    """Empty the collected issues and this session's error log. Host-only."""
    n = ERR_TOTAL[0]
    del ERR_LOG[:]
    ERR_TOTAL[0] = 0
    ERR_BY_TYPE.clear()
    ERR_BY_LEVEL.clear()
    ERRTRACK.clear()          # or a line already scraped from a server log never returns
    path = ERR_FILE[0]
    if path:
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("=== %s %s error log - cleared %s ===\n"
                        % (APP_NAME, APP_VER_UI, time.strftime("%Y-%m-%d %H:%M:%S")))
        except OSError:
            pass
    panel_log("[panel] cleared %d issue(s)" % n)
    return {"ok": True, "cleared": n}


def log_error(source, msg, record=True):
    try:
        if ERR_FILE[0] is None:
            ld = log_dir()
            ERR_FILE[0] = pick_rotating(ld, "error_", 20)
            with open(ERR_FILE[0], "w", encoding="utf-8") as f:
                f.write("=== %s %s error log - session %s ===\n" % (APP_NAME, APP_VER_UI, time.strftime("%Y-%m-%d %H:%M:%S")))
        with open(ERR_FILE[0], "a", encoding="utf-8") as f:
            f.write("[%s] [%s] %s\n" % (time.strftime("%H:%M:%S"), source, str(msg).strip()[:500]))
    except Exception:
        pass
    if record:
        _record_issue(source, msg)

ERRTRACK = {}
def scan_slot_errors(slot_id, label, ld):
    files = sorted(glob.glob(os.path.join(ld, "srv_%s_*.log" % glob.escape(slot_id))),
                   key=os.path.getmtime, reverse=True)
    if not files: return
    path = files[0]
    st = ERRTRACK.setdefault(slot_id, {"path": "", "pos": 0})
    try:
        size = os.path.getsize(path)
        if st["path"] != path:
            st["path"], st["pos"] = path, max(0, size - 65536)
        if size <= st["pos"]:
            st["pos"] = min(st["pos"], size); return
        with open(path, "rb") as f:
            f.seek(st["pos"]); chunk = f.read(size - st["pos"])
        st["pos"] = size
        for line in ANSI_RX.sub("", chunk.decode("utf-8", errors="ignore")).splitlines():
            if line.startswith("==="):
                continue
            if ERR_RX.search(line):
                log_error("slot " + label, line)
            elif WARN_RX.search(line):
                _record_issue("slot " + label, line)
    except Exception:
        pass

def panel_log(msg):
    try:
        with open(os.path.join(log_dir(), "panel.log"), "a", encoding="utf-8") as f:
            f.write("[%s] %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))
    except Exception:
        pass
    print(msg)

def log_warn(source, msg):
    """Something worth noticing that did not fail.

    log_error() also raises a UI issue, so using it for an observation - a slow state
    read, say - tells the user something is broken when nothing is. A warning goes to
    panel.log, tagged, and raises nothing.
    """
    panel_log("[warn] [%s] %s" % (source, str(msg).strip()[:500]))


# ---------------------------------------------------------------- scanning
PORT_RX = [re.compile(r'"--port"\s*,\s*"(\d+)"'), re.compile(r'--port\s+(\d+)')]
def parse_ps1_model(path):
    try:
        txt = open(path, encoding="utf-8-sig").read()
    except Exception:
        return ""
    def leaf(p):
        # a launcher may be written on either kind of path, whatever we are running on
        return re.split(r"[\\/]", str(p).strip())[-1]
    m = (re.search(r'"-m",\s*"([^"]+\.gguf)"', txt) or re.search(r'"--model",\s*"([^"]+\.gguf)"', txt))
    if m:
        return leaf(m.group(1))
    # named through a variable instead - read it the same way the card does
    v = (parse_launcher_params(txt) or {}).get("model") or ""
    return leaf(v) if v else ""

SAMPLER_KEYS = [("temp", "--temp"), ("top_p", "--top-p"), ("min_p", "--min-p"),
                ("top_k", "--top-k"), ("n_sigma", "--top-n-sigma"), ("typ_p", "--typical"),
                ("xtc_p", "--xtc-probability"), ("xtc_t", "--xtc-threshold"),
                ("dry", "--dry-multiplier"), ("freq", "--frequency-penalty"), ("pres", "--presence-penalty")]
SAMPLER_DEFAULTS = {"temp": "0.8", "top_p": "0.95", "min_p": "0.05", "top_k": "40", "dry": "0", "n_sigma": "-1", "typ_p": "1.0", "xtc_p": "0", "xtc_t": "0.1", "freq": "0", "pres": "0"}

# Per-provider sampler fields the proxy observes in each request body and can override.
# Maps our short key -> the JSON field name llama.cpp / SkyrimNet uses in the request.
PROXY_SAMPLER_FIELDS = {"temp": "temperature", "top_p": "top_p", "min_p": "min_p",
                        "top_k": "top_k", "n_sigma": "top_n_sigma", "typ_p": "typical_p",
                        "xtc_p": "xtc_probability", "xtc_t": "xtc_threshold",
                        "dry": "dry_multiplier", "freq": "frequency_penalty", "pres": "presence_penalty"}
def _num_str(v):
    """normalize a numeric sampler value to a short display string."""
    try:
        f = float(v)
        return ("%g" % f)
    except Exception:
        return str(v)[:10]
def parse_ps1_samplers(path):
    out = {}
    try:
        txt = open(path, encoding="utf-8-sig").read()
    except Exception:
        return out
    m = re.search(r"llamaArgs\s*=\s*@\(", txt, re.I)
    if m:
        end = txt.find("\n)", m.end())
        region = txt[m.end():end if end > 0 else len(txt)]
    else:
        region = txt
    for key, flag in SAMPLER_KEYS:
        mm = re.search("[\"']%s[\"']\\s*,\\s*[\"']([^\"']+)[\"']" % re.escape(flag), region)
        if mm:
            out[key] = mm.group(1)
    return out

def _latest_srv_log(slot_id, ld):
    files = sorted(glob.glob(os.path.join(ld, "srv_%s_*.log" % slot_id)), key=os.path.getmtime)
    return files[-1] if files else None

SAMPLER_NAMES = ("penalties", "dry", "top_k", "top_p", "min_p", "temp", "temperature")

def parse_log_samplers(slot_id, ld):
    """live sampler values: pair the numbers row to the names row by column position."""
    try:
        f = _latest_srv_log(slot_id, ld)
        if not f:
            return {}
        with open(f, "rb") as fh:
            fh.seek(max(0, os.path.getsize(f) - 40000))
            tail = fh.read().decode("utf-8", "replace")
        i = tail.rfind("Sampler chain")
        if i < 0:
            return {}
        lines = tail[i:].split(chr(10))[1:4]
        name_line = num_line = None
        for j, ln in enumerate(lines):
            if sum(1 for n in SAMPLER_NAMES if n in ln) >= 3:
                name_line = ln
                num_line = lines[j + 1] if j + 1 < len(lines) else ""
                break
        if name_line is None:
            return {}
        npos = [(m.start(), m.group(0)) for m in re.finditer("|".join(SAMPLER_NAMES[:6]), name_line)]
        out = {}
        for m in re.finditer(r"[0-9]+(?:\.[0-9]+)?", num_line):
            p = m.start()
            best = min(npos, key=lambda nv: abs(nv[0] - p)) if npos else None
            if best:
                key = "temp" if best[1] == "temperature" else best[1]
                out[key] = m.group(0)
        out.pop("penalties", None)
        return out
    except Exception:
        return {}

def parse_ps1_reasoning(path):
    try:
        txt = open(path, encoding="utf-8-sig").read()
    except Exception:
        return ""
    m = re.search("[\"']--reasoning[\"']\\s*,\\s*[\"'](on|off)[\"']", txt, re.I)
    if m:
        return m.group(1).lower()
    m = re.search(r"--reasoning\s+(on|off)", txt, re.I)
    return m.group(1).lower() if m else ""

def parse_log_reasoning(slot_id, ld):
    """'on' / 'off' / '' from the launcher banner in the newest srv log."""
    try:
        f = _latest_srv_log(slot_id, ld)
        if not f:
            return ""
        head = open(f, "rb").read(4096).decode("utf-8", "replace")
        m = re.search(r"reasoning (ON|OFF)", head, re.I)
        return m.group(1).lower() if m else ""
    except Exception:
        return ""

def _profile_snapshot(cfg):
    """One profile now covers the whole setup - wiring, server parameters and settings -
    so there is no longer a separate notion of a server profile vs a provider profile."""
    return {"gpus": [{"id": g.get("id"), "enabled": g.get("enabled", True)} for g in cfg.get("gpus", [])],
            "slots": [{"id": s.get("id"), "gpuId": s.get("gpuId", ""), "label": s.get("label", ""),
                       "port": s.get("port"), "params": json.loads(json.dumps(s.get("params", {}) or {})),
                       "providers": json.loads(json.dumps(s.get("providers", []) or []))}
                      for s in cfg.get("slots", [])],
            "unallocatedProviders": json.loads(json.dumps(cfg.get("unallocatedProviders", []) or [])),
            "settings": {k: cfg.get("settings", {}).get(k, "") for k in ("panelIp", "remoteIp")}}

PROFILE_DIR = os.path.join(STACK, "profiles")

def _profile_file(name):
    safe = re.sub(r"[^A-Za-z0-9._ -]", "_", str(name)).strip()
    return os.path.join(PROFILE_DIR, safe + ".json") if safe else ""

def _profile_names():
    try:
        return sorted(f[:-5] for f in os.listdir(PROFILE_DIR) if f.lower().endswith(".json"))
    except Exception:
        return []

def _profiles_migrate(cfg):
    """Move any profile still living inside the config out into its own file, once."""
    old = cfg.get("profiles") or {}
    if not old:
        return False
    try:
        os.makedirs(PROFILE_DIR, exist_ok=True)
    except Exception:
        return False
    moved = 0
    for name, prof in old.items():
        p = _profile_file(name)
        if p and not os.path.exists(p):
            try:
                with open(p, "w", encoding="utf-8") as f:
                    json.dump(prof, f, indent=2)
                moved += 1
            except Exception:
                pass
    cfg["profiles"] = {}
    if moved:
        panel_log("[panel] moved %d profile(s) into %s" % (moved, PROFILE_DIR))
    return True

def _profile_read(name):
    p = _profile_file(name)
    if not p or not os.path.isfile(p):
        return None
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def api_profile_save(body):
    name = str(body.get("name", "")).strip()[:40]
    if not name:
        return {"error": "profile needs a name"}
    cfg = load_config()
    if _profiles_migrate(cfg):
        save_config(cfg)
    p = _profile_file(name)
    if not p:
        return {"error": "that name cannot be used for a file"}
    try:
        os.makedirs(PROFILE_DIR, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(_profile_snapshot(cfg), f, indent=2)
        cfg["settings"]["activeProfile"] = name
        save_config(cfg)
    except Exception as e:
        return {"error": "cannot write the profile: %s" % e}
    panel_log("[panel] profile saved: %s" % p)
    return {"ok": True, "profiles": _profile_names()}

def api_profile_load(body):
    name = str(body.get("name", "")).strip()
    cfg = load_config()
    if _profiles_migrate(cfg):
        save_config(cfg)
    prof = _profile_read(name)
    if not prof:
        return {"error": "unknown profile"}
    ge = {g["id"]: g.get("enabled", True) for g in prof.get("gpus", [])}
    for g in cfg.get("gpus", []):
        if g.get("id") in ge:
            g["enabled"] = ge[g.get("id")]
    ps = {s["id"]: s for s in prof.get("slots", [])}
    for s in cfg.get("slots", []):
        if s.get("id") in ps:
            s["gpuId"] = ps[s["id"]].get("gpuId", "")
            s["providers"] = json.loads(json.dumps(ps[s["id"]].get("providers", [])))
    for k, v in (prof.get("settings") or {}).items():
        if v:
            cfg["settings"][k] = v
    cfg["settings"]["activeProfile"] = name
    save_config(cfg)
    PROXY.sync()
    panel_log("[panel] profile loaded: %s" % name)
    return {"ok": True}

def api_profile_delete(body):
    name = str(body.get("name", "")).strip()
    cfg = load_config()
    if _profiles_migrate(cfg):
        save_config(cfg)
    p = _profile_file(name)
    if p and os.path.isfile(p):
        try:
            os.remove(p)
        except Exception as e:
            return {"error": "cannot delete the profile: %s" % e}
        panel_log("[panel] profile deleted: %s" % name)
        return {"ok": True, "profiles": _profile_names()}
    return {"error": "unknown profile"}

def api_helper_skip(body):
    cfg = load_config()
    try:
        step = int(body.get("step"))
    except Exception:
        return {"error": "bad step"}
    sk = cfg["settings"].setdefault("helperSkipped", [])
    if body.get("on"):
        if step not in sk:
            sk.append(step)
    else:
        cfg["settings"]["helperSkipped"] = [x for x in sk if x != step]
    save_config(cfg)
    return {"ok": True}

def _log_sources(cfg):
    ld = log_dir(cfg)
    out = []
    seen = set()
    for d in (ld, STACK):
        try:
            for f in sorted(os.listdir(d)):
                if not f.endswith(".log") or f in seen:
                    continue
                p = os.path.join(d, f)
                try:
                    st = os.stat(p)
                    out.append({"name": f, "size": st.st_size, "mtime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime)), "dir": d})
                    seen.add(f)
                except Exception:
                    pass
        except Exception:
            pass
    return out

def api_logs_meta(body):
    cfg = load_config()
    files = _log_sources(cfg)
    entries = []
    def add(path, deflevel):
        try:
            lines = open(path, encoding="utf-8", errors="replace").read().splitlines()[-500:]
        except Exception:
            return
        for ln in lines:
            if not ln.strip():
                continue
            lvl = deflevel
            low = ln.lower()
            if "error" in low or "fail" in low or "traceback" in low:
                lvl = "ERROR"
            elif "warn" in low:
                lvl = "WARN"
            m = re.match(r"\[([0-9: -]+)\]\s*(\[[^\]]+\])?\s*(.*)", ln)
            entries.append({"level": lvl, "time": (m.group(1) if m else ""), "tag": ((m.group(2) or "").strip("[]") if m else ""), "msg": (m.group(3) if m else ln)})
    err = os.path.join(STACK, "error_1.log")
    for f in sorted(os.listdir(STACK)):
        if f.startswith("error_") and f.endswith(".log"):
            err = os.path.join(STACK, f)
    add(err, "ERROR")
    add(os.path.join(STACK, "panel.log"), "INFO")
    entries.reverse()
    counts = {"ERROR": 0, "WARN": 0, "INFO": 0}
    for e in entries:
        counts[e["level"]] = counts.get(e["level"], 0) + 1
    return {"files": files, "entries": entries[:400], "counts": counts, "dir": log_dir(cfg)}

def api_log_read(body):
    name = os.path.basename(str(body.get("name", "")))
    cfg = load_config()
    cand = [os.path.join(log_dir(cfg), name), os.path.join(STACK, name)]
    for p in cand:
        if os.path.isfile(p):
            try:
                data = open(p, "rb").read()
                tail = data[-200000:]
                txt = tail.decode("utf-8", errors="replace")
                if len(data) > len(tail):
                    txt = "... (showing last 200 KB of %d KB) ...\n" % (len(data) // 1024) + txt
                return {"ok": True, "name": name, "text": txt}
            except Exception as e:
                return {"error": str(e)}
    return {"error": "not found"}

def api_logs_clear(body):
    ERR_LOG.clear(); ERR_TOTAL[0] = 0; ERR_BY_TYPE.clear(); ERR_BY_LEVEL.clear()
    n = 0
    for f in os.listdir(STACK):
        if f.startswith("error_") and f.endswith(".log"):
            try:
                open(os.path.join(STACK, f), "w").close()
                n += 1
            except Exception:
                pass
    return {"ok": True, "cleared": n}

def api_path_check(body):
    """Does a folder actually hold what the panel needs from it?"""
    p = str(body.get("path", "")).strip()
    kind = str(body.get("kind") or "llamacppPath")
    if not p or not os.path.isdir(p):
        return {"ok": False}
    if kind == "modelsDir":
        # models are often filed in per-model subfolders, so look a little way down,
        # but stop at the first hit and do not walk an entire drive
        try:
            root_depth = p.rstrip("\\/").count(os.sep)
            for root, dirs, files in os.walk(p):
                if any(f.lower().endswith(".gguf") for f in files):
                    return {"ok": True}
                if root.count(os.sep) - root_depth >= 2:
                    dirs[:] = []
        except Exception:
            pass
        return {"ok": False}
    if kind in ("logDir", "yamlOutDir", "outputDir"):
        return {"ok": True}          # written to, not read from: existing is all it needs
    if kind == "launcherDir":
        try:
            return {"ok": any(f.lower().endswith(".ps1") for f in os.listdir(p))}
        except Exception:
            return {"ok": False}
    if kind == "ttsAcppDir":
        exe = find_acpp_exe(p)
        return {"ok": bool(exe), "exe": exe}
    return {"ok": os.path.isfile(os.path.join(p, "llama-server.exe"))}

def debug_report():
    """A short account of this build and this machine's setup, meant to be shared.

    Deliberately narrow: enough to tell what is configured and what has gone wrong,
    with nothing in it that identifies you. No paths, no IP addresses, no GPU serial
    numbers, no model filenames - a folder is reported as set or not set, and a model
    as what kind of model it is. What matters for a bug report is the shape of the
    setup, not its contents.
    """
    cfg = load_config()
    st = cfg.get("settings", {}) or {}
    def folder(key, kind="llamacppPath"):
        p = (st.get(key) or "").strip()
        if not p:
            return "not set"
        return "ok" if api_path_check({"path": p, "kind": key}).get("ok") else "set, but nothing expected found in it"
    slots = cfg.get("slots", []) or []
    lines = []
    A = lines.append
    A("PandorumLLM %s debug report" % APP_VER_UI)
    A("generated %s" % time.strftime("%Y-%m-%d %H:%M:%S"))
    A("running file %s" % BUILD_ID.get("path", "?"))
    A("build %s, %s KB, modified %s" % (BUILD_ID.get("sha", "?"), BUILD_ID.get("kb", 0), BUILD_ID.get("mtime", "?")))
    A("")
    A("-- this machine ------------------------------------------------")
    A("  windows            : %s" % ("yes" if os.name == "nt" else "no (%s)" % sys.platform))
    A("  python             : %s" % sys.version.split()[0])
    A("  panel port         : %s" % PORT)
    # kept for diagnostics only. The panel has not asked for elevation since v3.72
    # patch15 and does not need it: high ports, its own folder, and it only signals
    # processes it started itself.
    A("  running elevated   : %s" % is_admin())
    A("")
    A("-- folders -----------------------------------------------------")
    for key, label in (("llamacppPath", "llama.cpp"), ("modelsDir", "models"),
                       ("launcherDir", "ps1 launchers"), ("logDir", "logs"),
                       ("yamlOutDir", "providers.yaml out")):
        A("  %-18s : %s" % (label, folder(key)))
    A("")
    A("-- setup -------------------------------------------------------")
    A("  mode               : %s" % ("1 PC" if st.get("onePC", True) else "2 PC"))
    A("  panel IP set       : %s" % bool((st.get("panelIp") or "").strip()))
    A("  remote IP set      : %s" % bool((st.get("remoteIp") or "").strip()))
    A("  yaml generated     : %s" % bool(st.get("yamlGenerated")))
    A("  theme              : %s" % (st.get("themeName") or "default"))
    A("")
    A("-- graphics cards ----------------------------------------------")
    gp = cfg.get("gpus", []) or []
    A("  detected           : %d" % len(gp))
    for i, g in enumerate(gp):
        A("    card %d           : %s, %s" % (i, g.get("name", "?"),
                                              "enabled" if g.get("enabled", True) else "disabled"))
    A("")
    A("-- servers -----------------------------------------------------")
    A("  configured         : %d" % len(slots))
    for s in slots:
        p = s.get("params", {}) or {}
        mdl = (p.get("model") or "").strip()
        kind = model_kind(mdl) if mdl and os.path.isfile(mdl) else ("set, file missing" if mdl else "none")
        A("    port %-6s      : model %s, on a GPU: %s, launcher built: %s, %s"
          % (s.get("port", "?"), kind, bool(s.get("gpuId")),
             bool(s.get("script")) and os.path.isfile(s.get("script") or ""),
             slot_status(s.get("port")).get("state", "?")))
        # only the runtime settings, and only where they differ from the default -
        # a list of defaults tells nobody anything and buries what does not
        d = param_defaults()
        changed = [(k, str(p.get(k))) for (k, _l, _ki, _dv, _o, _f, _r) in SERVER_PARAMS
                   if str(p.get(k, "")).strip() not in ("", str(d.get(k, "")))]
        if changed:
            A("        changed from default: " + ", ".join("%s=%s" % kv for kv in changed))
        if (p.get("vision") or "N/A") not in ("", "N/A", "Disabled"):
            A("        vision projector: yes")
        if (p.get("draft") or "N/A") not in ("", "N/A", "Disabled"):
            A("        draft model     : yes")
        if (p.get("custom") or "").strip():
            A("        launcher        : hand-edited")
        A("        providers       : %d" % len(s.get("providers", []) or []))
    A("")
    A("-- port behaviour ----------------------------------------------")
    A("  a closed port should refuse at once; waiting means something filtered it.")
    _ctl = _free_port()
    _rows = ([("control (closed)", _ctl)] if _ctl else []) + [("panel (listening)", PORT)]
    _rows += [("server " + str(x.get("port") or "?"), x.get("port")) for x in slots if x.get("port")]
    _odd = False
    for _lab, _pt in _rows:
        _v, _ms, _rc = _port_verdict(_pt)
        A("  %-18s : %s in %dms%s" % (_lab, _v, _ms, (" (code %d)" % _rc) if _rc > 0 else ""))
        if _v == "no answer":
            _odd = True
    if _odd:
        A("  a port that neither answers nor refuses is being intercepted - look at")
        A("  third-party antivirus or firewall, and at VPN or container filter drivers")
    A("")

    A("-- recent problems ---------------------------------------------")
    A("  total this session : %d" % ERR_TOTAL[0])
    for kind, count in sorted(ERR_BY_TYPE.items(), key=lambda x: -x[1]):
        A("    %-16s : %d" % (kind, count))
    recent = ERR_LOG[-20:]
    if not recent:
        A("  nothing recorded this session")
    for it in recent:
        A("  [%s] [%s] %s" % (it.get("ts", "?"), it.get("source", "?"), str(it.get("title", ""))[:150]))
    return "\n".join(lines) + "\n"

def api_debug_report(body):
    try:
        return {"ok": True, "text": debug_report()}
    except Exception as e:
        return {"error": "could not build the report (%s)" % e}

def api_helper_manual(body):
    cfg = load_config()
    cfg["settings"]["helperManualSN"] = bool(body.get("on"))
    save_config(cfg)
    return {"ok": True}

HELPER_FLAG_KEYS = ("helperSkipped", "helperManualSN", "yamlGenerated", "yamlGeneratedAt", "yamlGeneratedIp", "yamlDelivered", "helperForceReset")

def api_helper_revert(body):
    cfg = load_config()
    bak = cfg.get("settings", {}).get("helperResetBackup")
    if not isinstance(bak, dict):
        return {"error": "nothing to revert - no reset backup found"}
    for k in HELPER_FLAG_KEYS:
        if k in bak:
            cfg["settings"][k] = bak[k]
        else:
            cfg["settings"].pop(k, None)
    cfg["settings"].pop("helperResetBackup", None)
    save_config(cfg)
    return {"ok": True}

def api_helper_reset(body):
    cfg = load_config()
    st = cfg.setdefault("settings", {})
    st["helperResetBackup"] = {k: st[k] for k in HELPER_FLAG_KEYS if k in st}
    st["helperSkipped"] = []
    st["helperManualSN"] = False
    for k in ("yamlGenerated", "yamlGeneratedAt", "yamlGeneratedIp", "yamlDelivered"):
        st.pop(k, None)
    st["helperForceReset"] = [i for i in range(7) if i != 2]
    save_config(cfg)
    return {"ok": True}

def api_helper_unforce(body):
    cfg = load_config()
    st = cfg.setdefault("settings", {})
    fr = st.get("helperForceReset")
    if isinstance(fr, list):
        try:
            idx = int(body.get("step"))
        except Exception:
            return {"error": "bad step"}
        st["helperForceReset"] = [i for i in fr if i != idx]
        save_config(cfg)
    return {"ok": True}

def api_sampler_edit(body):
    cfg = load_config()
    s = next((x for x in cfg.get("slots", []) if x.get("id") == body.get("slot")), None)
    if not s or not s.get("script"):
        return {"error": "that server has no launcher assigned"}
    key = str(body.get("key", ""))
    flag = dict(SAMPLER_KEYS).get(key)
    if not flag:
        return {"error": "unknown sampler"}
    val = str(body.get("value", "")).strip()
    if val:
        try:
            float(val)
        except Exception:
            return {"error": "value must be a number"}
    path = s["script"]
    try:
        txt = open(path, encoding="utf-8-sig", newline="").read()
    except Exception as e:
        return {"error": "cannot read launcher: %s" % e}
    rx = re.compile(r'([ \t]*)"%s"\s*,\s*"[^"]*"\s*,?' % re.escape(flag))
    m = rx.search(txt)
    if val == "":
        if m:
            ls = txt.rfind(chr(10), 0, m.start()) + 1
            le = txt.find(chr(10), m.end())
            le = len(txt) if le < 0 else le + 1
            probe = txt[ls:le].strip().rstrip(",")
            if probe.startswith(chr(34) + flag) and probe.endswith(chr(34)):
                txt = txt[:ls] + txt[le:]
            else:
                txt = rx.sub(lambda mm: mm.group(1), txt, count=1)
    elif m:
        txt = rx.sub(lambda mm: '%s"%s", "%s",' % (mm.group(1), flag, val), txt, count=1)
    else:
        pm = re.search(r'([ \t]*)"--port"\s*,\s*"\d+"\s*,?', txt)
        if not pm:
            return {"error": "no --port pair found in the launcher to insert after"}
        eol = txt.find(chr(10), pm.end())
        eol = len(txt) if eol < 0 else eol
        nl = chr(13) + chr(10) if chr(13) + chr(10) in txt else chr(10)
        core = txt[:eol].rstrip(chr(13))
        rest = txt[eol + 1:] if eol < len(txt) and txt[eol] == chr(10) else txt[eol:]
        txt = core + nl + '%s"%s", "%s",' % (pm.group(1), flag, val) + nl + rest
    try:
        open(path, "w", encoding="utf-8-sig", newline="").write(txt)
    except Exception as e:
        return {"error": "cannot write launcher: %s" % e}
    panel_log("[panel] sampler %s -> %s in %s" % (flag, val or "(removed)", os.path.basename(path)))
    return {"ok": True, "note": "restart the server to apply"}
def parse_ps1_port(path):
    try:
        text = open(path, encoding="utf-8-sig", errors="ignore").read()
    except Exception:
        return None
    for rx in PORT_RX:
        m = rx.search(text)
        if m:
            return int(m.group(1))
    return None

def list_launchers(cfg):
    # Launcher folders (launcher dir, output dir, archive) are scanned RECURSIVELY (up to 3 levels
    # deep) so a .ps1 tucked in a subfolder is still found - matching how models are scanned. The
    # models folder is only a bonus source (a .ps1 kept next to the models), so it is scanned at its
    # top level only, since a models tree can be huge; keep launchers in a launcher folder for depth.
    seen, out = set(), []
    def add(root, files, src):
        for name in sorted(files, key=str.lower):
            low = name.lower()
            if not low.endswith(".ps1") or low in seen:
                continue
            seen.add(low)
            path = os.path.join(root, name)
            out.append({"path": path, "name": name,
                        "port": parse_ps1_port(path), "source": src})
    def scan_deep(base, src):
        if not base or not os.path.isdir(base):
            return
        for root, subdirs, files in os.walk(base):
            if root[len(base):].count(os.sep) > 3:
                subdirs[:] = []
                continue
            add(root, files, src)
    lds = [d for d in cfg.get("launcherDirs", []) if d]
    for d in lds:
        scan_deep(d, "primary")
    outd = cfg.get("settings", {}).get("outputDir")
    if outd and outd not in lds:
        scan_deep(outd, "output")
    scan_deep(ARCHIVE, "archive")
    mdl = cfg.get("settings", {}).get("modelsDir")
    if mdl and mdl not in lds and mdl != outd and os.path.isdir(mdl):
        try:
            add(mdl, os.listdir(mdl), "models")
        except OSError:
            pass
    return out

_models_cache = {"t": 0, "dir": "", "items": []}
PART_RX = re.compile(r"-(\d{5})-of-\d{5}\.gguf$", re.I)
def gguf_skip_array(f, SZ):
    """Move the file position past a GGUF array of any length.

    Strings are skipped by their stated length rather than read, so a tokenizer of a
    quarter of a million entries costs nothing and, crucially, leaves the position
    exactly where the next value begins.
    """
    et = int.from_bytes(f.read(4), "little")
    ln = int.from_bytes(f.read(8), "little")
    if et == 8:
        for _ in range(ln):
            sl = int.from_bytes(f.read(8), "little")
            f.seek(sl, 1)
    elif et == 9:
        for _ in range(ln):
            gguf_skip_array(f, SZ)
    else:
        f.seek(SZ.get(et, 4) * ln, 1)

GGUF_WANT = ("general.architecture", "clip.has_vision_encoder", "clip.has_audio_encoder")

def gguf_meta(path):
    """Read a few named values out of a GGUF header, without reading the weights.

    Returns {} for anything that is not a readable GGUF - a model is never rejected
    just because we could not inspect it.
    """
    out = {}
    try:
        with open(path, "rb") as f:
            if f.read(4) != b"GGUF":
                return out
            f.read(4)                                   # format version
            f.read(8)                                   # tensor count
            n = int.from_bytes(f.read(8), "little")
            if n > 4096:                                # not a header we understand
                return out
            def rd_str():
                ln = int.from_bytes(f.read(8), "little")
                if ln > (1 << 20):
                    raise ValueError("string too long")
                return f.read(ln).decode("utf-8", "replace")
            SZ = {0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4, 6: 4, 7: 1, 10: 8, 11: 8, 12: 8}
            for _ in range(n):
                k = rd_str()
                ty = int.from_bytes(f.read(4), "little")
                if ty == 8:
                    v = rd_str()
                elif ty == 7:
                    v = bool(f.read(1)[0])
                elif ty in SZ:
                    v = int.from_bytes(f.read(SZ[ty]), "little")
                elif ty == 9:                           # an array: step over all of it
                    gguf_skip_array(f, SZ)
                    v = None
                else:
                    break                               # unknown kind: stop, keep what we have
                if k in GGUF_WANT:
                    out[k] = v
    except Exception:
        pass
    return out

def gguf_tensor_hint(path):
    """Look at a GGUF's tensor names for a marker of what the file is.

    Only the names are read, never the weights, and only the first few hundred. A file
    that carries multi-token-prediction tensors is a drafter whatever it is called.
    """
    try:
        with open(path, "rb") as f:
            if f.read(4) != b"GGUF":
                return ""
            f.read(4)
            ntensor = int.from_bytes(f.read(8), "little")
            nkv = int.from_bytes(f.read(8), "little")
            if ntensor > 100000 or nkv > 4096:
                return ""
            def rd_str():
                ln = int.from_bytes(f.read(8), "little")
                if ln > (1 << 20):
                    raise ValueError("string too long")
                return f.read(ln).decode("utf-8", "replace")
            SZ = {0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4, 6: 4, 7: 1, 10: 8, 11: 8, 12: 8}
            for _ in range(nkv):                      # step over the header values
                rd_str()
                ty = int.from_bytes(f.read(4), "little")
                if ty == 8:
                    ln = int.from_bytes(f.read(8), "little")
                    f.seek(ln, 1)
                elif ty in SZ:
                    f.seek(SZ[ty], 1)
                elif ty == 9:
                    gguf_skip_array(f, SZ)
                else:
                    return ""
            for _ in range(min(ntensor, 400)):        # then the tensor names
                name = rd_str().lower()
                if "mtp" in name or "nextn" in name or "eagle" in name:
                    return "draft"
                if name.startswith("v.") or name.startswith("mm.") or "vision_model" in name \
                        or name.startswith("resampler.") or name.startswith("mmproj"):
                    return "vision"
                nd = int.from_bytes(f.read(4), "little")
                if nd > 8:
                    return ""
                f.read(8 * nd)                        # dimensions
                f.read(4)                             # type
                f.read(8)                             # offset
    except Exception:
        pass
    return ""

_KIND_FILE = os.path.join(STACK, "model-kinds.json")
_KIND = {"map": None, "dirty": False}
_KIND_LOCK = threading.Lock()
def _kind_map():
    if _KIND["map"] is None:
        try:
            with open(_KIND_FILE, encoding="utf-8") as f:
                _KIND["map"] = json.load(f) or {}
        except Exception:
            _KIND["map"] = {}
    return _KIND["map"]
def _kind_flush():
    with _KIND_LOCK:
        if not _KIND["dirty"]:
            return
        data = dict(_KIND["map"] or {})
        _KIND["dirty"] = False
    try:
        tmp = _KIND_FILE + ".%d.tmp" % os.getpid()
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(tmp, _KIND_FILE)
    except Exception:
        pass
def model_kind(path):
    """Cached in front of the header read: identifying a .gguf means opening it, and
    a models folder full of multi-gigabyte files turned that into tens of seconds on
    every scan. The key is path + size + mtime, so a changed file is re-read."""
    try:
        stt = os.stat(path)
        key = "%s|%d|%d" % (os.path.abspath(path).lower(), stt.st_size, int(stt.st_mtime))
    except Exception:
        return _model_kind_read(path)
    with _KIND_LOCK:
        hit = _kind_map().get(key)
    if hit:
        return hit
    val = _model_kind_read(path)
    with _KIND_LOCK:
        _kind_map()[key] = val
        _KIND["dirty"] = True
    return val

def _model_kind_read(path):
    """What a .gguf actually is: a chat model, a vision projector, or a draft model.

    The header is asked first. The name is only consulted when the header says nothing
    useful, because names are a convention and not a guarantee.
    """
    meta = gguf_meta(path)
    arch = str(meta.get("general.architecture") or "").lower()
    if arch == "clip" or meta.get("clip.has_vision_encoder") or meta.get("clip.has_audio_encoder"):
        return "vision"
    hint = gguf_tensor_hint(path)                 # what the file is built from
    if hint:
        return hint
    low = os.path.basename(path).lower()          # only then, what it is called
    if "mmproj" in low or "-vision" in low or low.startswith("vision"):
        return "vision"
    if "mtp" in re.split(r"[^a-z0-9]+", low) or "draft" in low or "eagle" in low:
        return "draft"
    return "main"

def list_models(cfg):
    d = cfg.get("settings", {}).get("modelsDir") or ""
    roots = []
    if d:
        roots.append(d)
    for x in cfg.get("launcherDirs", []):
        if x and x not in roots:
            roots.append(x)
    key = "|".join(roots)
    now = time.time()
    if _models_cache["dir"] == key and now - _models_cache["t"] < 300:
        return _models_cache["items"]
    _t_scan = time.time()
    items, seen = [], set()
    for base in roots:
        if not os.path.isdir(base):
            continue
        for root, dirs, files in os.walk(base):
            if root[len(base):].count(os.sep) > 3:
                dirs[:] = []
                continue
            for n in files:
                if not n.lower().endswith(".gguf"):
                    continue
                m = PART_RX.search(n)
                if m and m.group(1) != "00001":
                    continue
                full = os.path.join(root, n)
                if full.lower() in seen:
                    continue
                seen.add(full.lower())
                items.append({"path": full, "name": os.path.relpath(full, base),
                              "kind": model_kind(full)})
    items.sort(key=lambda x: x["name"].lower())
    _kind_flush()
    _took = (time.time() - _t_scan) * 1000
    if _took > 1000:
        # also an observation: the scan finished, it just took a while
        log_warn("panel", "model folder scan: %dms for %d models (headers are read once "
                          "per file and remembered in model-kinds.json)" % (_took, len(items)))
    _models_cache.update(t=now, dir=key, items=items)
    return items

# ---------------------------------------------------------------- status / speeds
_ST_CACHE = {}
_ST_LOCK = threading.Lock()
_ST_TTL = 1.2
_ST_WAIT = 0.35    # loopback: a live server accepts at once and a dead port refuses at
                   # once. Anything slower is a firewall/reservation dropping the SYN,
                   # and waiting a full second per server for that answer is pointless.
def _port_verdict(port, wait=1.5):
    """What a connection to a local port actually does. A closed port refuses at
    once (WSAECONNREFUSED); anything that waits out the clock is being filtered by
    something in the path, which is worth knowing before a server tries to bind it."""
    sk = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sk.settimeout(wait)
    t0 = time.time()
    try:
        sk.connect(("127.0.0.1", int(port)))
        return ("accepted", (time.time() - t0) * 1000, 0)
    except ConnectionRefusedError:
        return ("refused", (time.time() - t0) * 1000, 0)
    except socket.timeout:
        return ("no answer", (time.time() - t0) * 1000, -1)
    except OSError as e:
        return ("error", (time.time() - t0) * 1000, e.errno or -2)
    finally:
        try: sk.close()
        except Exception: pass

def _free_port():
    """A port nothing is listening on: bind it, note it, let it go."""
    sk = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sk.bind(("127.0.0.1", 0))
        return sk.getsockname()[1]
    except Exception:
        return 0
    finally:
        try: sk.close()
        except Exception: pass

_PATH_RX = re.compile("(?:[A-Za-z]:" + chr(92)*2 + "|" + chr(92)*4 + ")[^" + chr(92) + "s" + chr(34) + chr(39) + "<>|]*")
def _mask_paths_in(text):
    """Strip anything path-shaped from text bound for a remote reader. Uses the same
    masker as the state payload so there is one rule, not two."""
    try:
        return _PATH_RX.sub(lambda m: _mask_path(m.group(0)), text)
    except Exception:
        # a masker that fails must not hand back the unmasked text: fail closed
        return "(hidden - could not be masked for a remote reader)"

def _probe_slot(port):
    """One loopback probe, resolver-free. socket.create_connection() and urlopen()
    both call getaddrinfo even for a numeric address, and on a machine with no
    default gateway that costs about a second EACH - three servers meant three
    seconds on every state read. A raw socket skips it; /health is spoken over the
    same connection instead of opening a second one."""
    sk = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sk.settimeout(_ST_WAIT)
    try:
        sk.connect(("127.0.0.1", int(port)))       # connect(), not connect_ex: on
    except Exception:                              # Windows connect_ex sits out the
        try: sk.close()                            # timeout and answers WSAEWOULDBLOCK
        except Exception: pass                     # instead of reporting the refusal
        return {"state": "down"}
    try:
        sk.sendall(b"GET /health HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n")
        head = sk.recv(64).decode("latin-1", "replace")
        if not head.startswith("HTTP/"):
            return {"state": "wedged"}
        code = int(head.split(" ", 2)[1])
        if code == 503:
            return {"state": "loading", "http": code}
        return {"state": "serving", "http": code}
    except Exception:
        return {"state": "wedged"}
    finally:
        try: sk.close()
        except Exception: pass

def prime_slot_status(ports):
    """Probe every server at once. Serial probes cost N x the timeout on machines
    where a closed port is dropped rather than refused."""
    todo = []
    now = time.time()
    with _ST_LOCK:
        for p0 in ports:
            if not p0:
                continue
            hit = _ST_CACHE.get(int(p0))
            if not (hit and now - hit[0] < _ST_TTL):
                todo.append(int(p0))
    if not todo:
        return
    ths = [threading.Thread(target=slot_status, args=(x,), daemon=True) for x in todo]
    for t in ths:
        t.start()
    for t in ths:
        t.join(timeout=_ST_WAIT + 0.4)

def slot_status(port):
    if not port:
        return {"state": "unknown"}
    key = int(port)
    with _ST_LOCK:
        hit = _ST_CACHE.get(key)
        if hit and time.time() - hit[0] < _ST_TTL:
            return dict(hit[1])
    out = _probe_slot(key)
    with _ST_LOCK:
        _ST_CACHE[key] = (time.time(), dict(out))
    return dict(out)

NUM = r"([0-9]+(?:\.[0-9]+)?)"
PP_RX = [re.compile(r"prompt eval time[^\n]*?\(\s*" + NUM + r"\s*tokens per second", re.I),
         re.compile(r"prompt processing[^\n]*?" + NUM + r"\s*t/s", re.I)]
TG_RX = [re.compile(r"(?<!prompt )eval time[^\n]*?\(\s*" + NUM + r"\s*tokens per second", re.I),
         re.compile(r"token generation[^\n]*?" + NUM + r"\s*t/s", re.I)]
def speeds_for_slot(slot_id, ld):
    files = sorted(glob.glob(os.path.join(ld, "srv_%s_*.log" % glob.escape(slot_id))),
                   key=os.path.getmtime, reverse=True)
    if not files:
        return None
    try:
        with open(files[0], "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - 65536))
            text = ANSI_RX.sub("", f.read().decode("utf-8", errors="ignore"))
    except Exception:
        return None
    def avg(rxs):
        vals = []
        for rx in rxs:
            vals += [float(v) for v in rx.findall(text)]
        vals = vals[-5:]
        return round(sum(vals) / len(vals), 1) if vals else None
    pp, tg = avg(PP_RX), avg(TG_RX)
    if pp is None and tg is None:
        return None
    return {"pp": pp, "tg": tg}

def api_network_info(body=None):
    panel_ip = (load_config().get("settings", {}) or {}).get("panelIp") or ""
    host_ip = panel_ip or primary_lan_ip()
    return {
        "mode": net_mode(),
        "devMode": dev_mode(),
        "lanIp": host_ip,
        "port": PORT,
        "lanUrl": ("http://%s:%d/" % (host_ip, PORT)) if host_ip else "",
        "networkDown": network_is_down(),
        "usingPanelIp": bool(panel_ip),
    }

def api_state():
    cfg  = load_config()
    hist = load_json(HISTORY, []) or []
    ld   = log_dir(cfg)
    def build(s):
        script = s.get("script") or ""
        actual = (parse_ps1_port(script) if script else None) or s.get("port")
        st = slot_status(actual)
        spd = speeds_for_slot(s.get("id"), ld) if st["state"] in ("serving", "loading") else None
        scan_slot_errors(s.get("id"), s.get("label", "?"), ld)
        last = next((h for h in hist if h.get("slotId") == s.get("id")), None)
        return {**s, "actualPort": actual, "status": st, "speeds": spd, "lastLaunch": last,
                "model": (parse_ps1_model(script) if script else ""),
                "scriptExists": bool(script) and os.path.isfile(script),
                "gpuId": s.get("gpuId", ""), "gpu": s.get("gpu", ""),
                "params": {k: v for k, v in (s.get("params", {}) or {}).items() if k != "prevCustom"}}
    with ThreadPoolExecutor(max_workers=8) as ex:
        slots = list(ex.map(build, cfg.get("slots", [])))
    routing = [{"id": s.get("id"), "label": s.get("label"), "port": s.get("port"),
                "gpu": s.get("gpu", ""), "gpuId": s.get("gpuId", ""), "samplers": (parse_ps1_samplers(s["script"]) if s.get("script") else {}), "logSamplers": (parse_log_samplers(s.get("id"), log_dir(cfg)) if s.get("script") else {}), "reasoning": ((parse_ps1_reasoning(s["script"]) or parse_log_reasoning(s.get("id"), log_dir(cfg))) if s.get("script") else ""),
                "model": (parse_ps1_model(s["script"]) if s.get("script") else ""), "hasScript": bool(s.get("script")), "providers": [
                    {"diaryGrammar": p.get("diaryGrammar", False), **p, "stats": PROXY.stats.get(p.get("id")),
                     "obsSamplers": PROXY.observed.get(p.get("id")) or {},
                     "srvSamplers": (parse_log_samplers(s.get("id"), log_dir(cfg)) if s.get("script") else {}),
                     "samplerSource": (p.get("samplerSource") or "server"),
                     "detectSN": bool(p.get("detectSN")),
                     "samplerOverrides": {k: v for k, v in (p.get("samplerOverrides") or {}).items() if str(v).strip() != ""}} for p in (s.get("providers") or [])]}
               for s in cfg.get("slots", [])]
    return {"app": APP_NAME, "version": APP_VER_UI, "build": BUILD_ID, "stack": STACK,
            "paramDefs": [{"key": k, "label": lab, "kind": kind, "def": dv, "opt": o,
                           "flag": f, "ref": ref}
                          for (k, lab, kind, dv, o, f, ref) in SERVER_PARAMS],
            "elevated": is_admin(), "slots": slots, "settings": cfg.get("settings", {}),
            "creatorSlots": cfg.get("creatorSlots", []), "routing": routing,
            "unallocated": cfg.get("unallocatedProviders", []) or [],
            "gpus": cfg.get("gpus", []), "panelPort": PORT,
            "profiles": _profile_names(),
            "llamaOk": bool(cfg.get("settings", {}).get("llamacppPath"))
                       and os.path.isfile(os.path.join(cfg.get("settings", {}).get("llamacppPath", ""), "llama-server.exe")),
            "listening": sorted(PROXY._servers.keys()), "ttsWrap": TTSW.state(),
            "higgsInstall": dict(HIGGS_INSTALL),
            "higgsFound": higgs_present(cfg),
            "ttsServer": tts_server_status(cfg),
            "launchers": list_launchers(cfg), "history": hist[:50]}

def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False

# ---------------------------------------------------------------- fleet plumbing
# Windows: a console program spawned from a process that has NO console gets a brand
# new, VISIBLE one. python.exe started with CREATE_NO_WINDOW still had a console - just
# hidden - and children inherited it silently. pythonw.exe, preferred since v3.72
# patch16 so that nothing had to be started hidden, has no console at all, so every
# pwsh and nvidia-smi call began popping a window on screen. Suppress it explicitly on
# every child rather than relying on inheriting somebody else's hidden console.
NOWIN = {"creationflags": 0x08000000} if os.name == "nt" else {}   # CREATE_NO_WINDOW


def run_fleet(extra):
    cmd = ["pwsh", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", FLEET_PS1] + extra
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=300, **NOWIN)
        log = (p.stdout or "")
        if (p.stderr or "").strip():
            log += "\n" + p.stderr
        for ln in log.splitlines():
            if ERR_RX.search(ln):
                log_error("fleet", ln)
        return log.strip() or "(no output)"
    except subprocess.TimeoutExpired:
        return "ERROR: launch-llm-fleet.ps1 timed out"
    except FileNotFoundError:
        return "ERROR: pwsh not found on PATH"

def api_action(body, mode):
    sid = body.get("slot", "")
    args = ["-Slot", sid] + (["-Force"] if mode == "launch" else ["-Stop"])
    panel_log("[panel] %s %s" % (mode, sid))
    if mode == "launch":
        try:
            _cfg = load_config()
            _s = next((x for x in _cfg.get("slots", []) if x.get("id") == sid), None)
            if _s and (_s.get("params") or {}).get("model"):
                if not isinstance(regen_slot_script(_cfg, _s), dict):
                    save_config(_cfg)
            if _s:
                _up = (parse_ps1_port(_s.get("script") or "") if _s.get("script") else None) or _s.get("port")
                if _up: PROXY.note_load(_up)
        except Exception: pass
    out = {"log": run_fleet(args)}
    sse_notify("state")
    return out

def api_stats_reset(body):
    PROXY.sstats.clear(); PROXY.pstats.clear()
    return {"ok": True}

CLIENTS = {}
LIFE = {"ever": False, "empty_since": None, "exiting": False}
import queue as _queue
SSE_CLIENTS = set()
SSE_SEQ = {"n": 0}   # bumps on every notify; the heartbeat echoes it so the page can spot a dead stream
def sse_notify(kind, extra=None):
    SSE_SEQ["n"] += 1
    msg = json.dumps({"t": kind, "seq": SSE_SEQ["n"], **(extra or {})})
    for q in list(SSE_CLIENTS):
        try: q.put_nowait(msg)
        except Exception: pass

_status_sig = {"v": None}
_tail_sig = {"v": None, "path": None}

def tail_watch_sig(cfg=None):
    """Signature of a log the panel does NOT write itself.

    The proxy and thinking logs are written here, so report() can notify directly.
    tts.log is written by a separate process, so nothing tells the panel it moved and
    its terminal would sit still until some unrelated event happened to fire. mtime
    plus size, because a same-second append can leave mtime unchanged on Windows.
    """
    try:
        st = os.stat(os.path.join(log_dir(cfg), TTS_LOG_NAME))
        return (st.st_mtime_ns, st.st_size)
    except Exception:
        return None

def status_watch_loop():
    n = 0
    while True:
        time.sleep(1)
        n += 1
        try:
            if not SSE_CLIENTS:
                continue
            # one stat per second, and only while a page is actually watching
            sig = tail_watch_sig()
            if sig != _tail_sig["v"]:
                _tail_sig["v"] = sig
                sse_notify("tail")
            if n % 3:
                continue          # server status stays on its original 3s cadence
            cfg = load_config()
            sig = {}
            with ThreadPoolExecutor(max_workers=6) as ex:
                def one(s):
                    script = s.get("script") or ""
                    ap = (parse_ps1_port(script) if script else None) or s.get("port")
                    st = slot_status(ap)
                    return s.get("id"), "%s/%s" % (st.get("state"), st.get("http", ""))
                for k, v in ex.map(one, cfg.get("slots", [])):
                    sig[k] = v
            _cfgd = cfg.get("settings", {})
            if (_cfgd.get("ttsServerExe") or _cfgd.get("ttsAcppDir") or "").strip():
                _t = slot_status(tts_server_port(cfg))     # only when TTS is configured
                sig["_tts"] = "%s/%s" % (_t.get("state"), _t.get("http", ""))
                if _t.get("state") == "serving" and not TTS_PROC.get("said_ready"):
                    TTS_PROC["said_ready"] = True
                    TTSW.log("\u2705 %s ready for voice synthesis" % tts_engine_label(cfg))
                    TTSW.log("")
                elif _t.get("state") != "serving":
                    TTS_PROC["said_ready"] = False
            if sig != _status_sig["v"]:
                _status_sig["v"] = sig
                sse_notify("state")
        except Exception:
            pass

def sweep_launcher_shells():
    """Close any launcher shell left over after the servers have gone.

    Returns the number closed. Only shells whose command line mentions this
    install folder are touched, so nothing else the user is running is at risk.
    """
    try:
        root = STACK.replace("'", "''")
        ps = ("$me=$PID; $root='" + root + "'; $n=0; "
              "Get-CimInstance Win32_Process -Filter \"Name='pwsh.exe'\" -ErrorAction SilentlyContinue | "
              "Where-Object { $_.ProcessId -ne $me -and $_.CommandLine -and "
              "$_.CommandLine -like ('*' + $root + '*') } | "
              "ForEach-Object { $n++; Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }; "
              "Write-Output $n")
        p = subprocess.run(["pwsh", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
                           **NOWIN,
                           capture_output=True, text=True, timeout=30)
        try:
            return int((p.stdout or "0").strip().splitlines()[-1])
        except Exception:
            return 0
    except Exception as e:
        log_error("exit", e)
        return 0

def clear_download_mark():
    """Drop Windows' "came from the internet" mark from our own folder.

    It is what makes SmartScreen warn, and it lingers on every extracted file. Clearing
    it here means there is nothing extra for anyone to run. Ours only - nothing outside
    the install folder is touched.
    """
    if os.name != "nt":
        return
    try:
        for root, _dirs, files in os.walk(STACK):
            for f in files:
                try:
                    os.remove(os.path.join(root, f) + ":Zone.Identifier")
                except OSError:
                    pass
    except Exception:
        pass

def full_exit(reason, kill_servers=True):
    if LIFE["exiting"]: return
    LIFE["exiting"] = True
    panel_log("[panel] EXIT (%s)%s" % (reason, "" if kill_servers else " - servers left running"))
    if kill_servers:
        out = run_fleet(["-Stop"])
        panel_log(out)
        n = sweep_launcher_shells()          # -Stop misses shells with no live port
        if n:
            panel_log("[panel] closed %d leftover launcher window(s)" % n)
        try:
            # a TTS server the panel started is the panel's to clean up; left running it
            # holds the model in VRAM with nothing able to reach it
            stop_tts_server(reason)
        except Exception:
            pass
    try:
        for srv in list(PROXY._servers.values()):
            import threading as _th
            _th.Thread(target=srv.shutdown, daemon=True).start()
        if getattr(TTSW, "_srv", None):
            import threading as _th2
            _th2.Thread(target=TTSW._srv.shutdown, daemon=True).start()
    except Exception: pass
    time.sleep(0.5)
    os._exit(0)

def watchdog_loop():
    import threading
    while True:
        time.sleep(3)
        try:
            cfg_on = True                      # always shut the fleet down with the panel
            now = time.time()
            for uid in [u for u, ts in CLIENTS.items() if now - ts > 150]:
                CLIENTS.pop(uid, None)
            if CLIENTS:
                LIFE["ever"] = True
                LIFE["empty_since"] = None
            elif LIFE["ever"] and cfg_on:
                if LIFE["empty_since"] is None:
                    LIFE["empty_since"] = now
                elif now - LIFE["empty_since"] > 8:
                    threading.Thread(target=full_exit, args=("browser closed",), daemon=True).start()
                    return
        except Exception as e:
            log_error("watchdog", e)

def api_terminate(body):
    panel_log("[panel] terminate all servers")
    stop_tts_server("terminate button", wait=False)      # a panel-started TTS server counts as one
    return {"log": _stamp_log(run_fleet(["-Stop"]))}

def api_exit(body):
    import threading
    threading.Timer(0.6, full_exit, args=("exit button",)).start()
    return {"ok": True, "msg": "shutting down"}

def api_handoff(body):
    import threading
    threading.Timer(0.3, full_exit, args=("handoff to new instance", False)).start()
    return {"ok": True}

AIB_VENDORS = {0x1043: "ASUS", 0x19DA: "ZOTAC", 0x1462: "MSI", 0x1458: "GIGABYTE",
               0x3842: "EVGA", 0x196E: "PNY", 0x1569: "PALIT", 0x10B0: "GAINWARD",
               0x7377: "COLORFUL", 0x1B4C: "GALAX/KFA2", 0x1849: "ASROCK", 0x10DE: "NVIDIA FE"}
def brand_from_sub(sub):
    try:
        v = int(str(sub).strip(), 16)
    except Exception:
        return ""
    lo, hi = v & 0xFFFF, (v >> 16) & 0xFFFF
    if lo in AIB_VENDORS:
        return AIB_VENDORS[lo]
    if hi in AIB_VENDORS:
        return AIB_VENDORS[hi]
    return "sub 0x%04X" % lo if lo else ""

def gpu_short(g):
    name = (g.get("name") or "GPU").replace("NVIDIA GeForce ", "").replace("NVIDIA ", "")
    b = g.get("brand") or ""
    return (b + " " + name).strip()

def apply_auto_names(cfg):
    gpus = {g.get("id"): g for g in cfg.get("gpus", [])}
    per = {}
    for s in cfg.get("slots", []):
        if s.get("autoName") and s.get("gpuId") in gpus:
            per.setdefault(s["gpuId"], []).append(s)
    for gid, ss in per.items():
        base = gpu_short(gpus[gid]) + " server"
        for i, s in enumerate(ss):
            s["label"] = base + ((" %d" % (i + 1)) if len(ss) > 1 else "")

def api_gpu_edit(body):
    cfg = load_config()
    for g in cfg.get("gpus", []):
        if g.get("id") == body.get("id"):
            if "enabled" in body:
                g["enabled"] = bool(body["enabled"]) if not isinstance(body["enabled"], str) else body["enabled"].lower() in ("1", "true", "on")
            save_config(cfg); PROXY.sync()
            return {"ok": True}
    return {"error": "unknown GPU"}

def api_detect_gpus(body=None):
    try:
        p = subprocess.run(["nvidia-smi", "--query-gpu=index,name,uuid,memory.total,pci.sub_device_id",
                            "--format=csv,noheader"], capture_output=True, text=True,
                           timeout=15, **NOWIN)
        rows = [r.strip() for r in (p.stdout or "").splitlines() if r.strip()]
        if p.returncode != 0 or not rows:
            return {"error": "nvidia-smi returned nothing (%s)" % (p.stderr or "").strip()[:120]}
    except Exception as e:
        return {"error": "nvidia-smi failed: %s" % e}
    cfg = load_config()
    gl = cfg.setdefault("gpus", [])
    byu = {g.get("uuid"): g for g in gl}
    used = {g.get("id") for g in gl}
    for r in rows:
        parts = [x.strip() for x in r.split(",")]
        if len(parts) < 3:
            continue
        idx, name, uuid = parts[0], parts[1], parts[2]
        mem = parts[3] if len(parts) > 3 else ""
        sub = parts[4] if len(parts) > 4 else ""
        brand = brand_from_sub(sub)
        if uuid in byu:
            byu[uuid].update(index=idx, name=name, mem=mem, sub=sub, brand=brand)
        else:
            n = 0
            while "gpu%d" % n in used:
                n += 1
            used.add("gpu%d" % n)
            gl.append({"id": "gpu%d" % n, "uuid": uuid, "index": idx, "name": name,
                       "mem": mem, "sub": sub, "brand": brand})
    ids = {g["id"] for g in gl}
    for s in cfg.get("slots", []):   # auto-link by legacy gpu-name-substring tag
        if not s.get("gpuId") and s.get("gpu"):
            hits = [g for g in gl if s["gpu"].lower() in (g.get("name") or "").lower()]
            if len(hits) == 1:
                s["gpuId"] = hits[0]["id"]
    apply_auto_names(cfg)
    save_config(cfg)
    PROXY.sync()
    panel_log("[panel] GPUs detected: %s" % ", ".join(g["name"] for g in gl))
    return {"gpus": gl}

def api_open_file(body):
    cfg = load_config()
    path = os.path.abspath(body.get("path", ""))
    if not _within(path, _all_roots(cfg)):
        return {"error": "path outside the allowed folders"}
    if os.path.splitext(path)[1].lower() in _EXE_EXTS:
        return {"error": "refusing to open an executable file"}
    if not os.path.isfile(path):
        return {"error": "file not found"}
    try:
        os.startfile(path)
        return {"ok": True}
    except AttributeError:
        return {"error": "open-file is Windows-only"}
    except Exception as e:
        return {"error": str(e)}

YAML_DIRNAME = "providerYAML"
DEFAULT_BASE_YAML = """providers:
  - id: openrouter
    name: OpenRouter
    endpoint: https://openrouter.ai/api/v1/chat/completions
    api_key: ""
    use_sse: true
    use_structured_outputs: false
    reasoning: false
    provider_settings: ~
    provider_sorting: latency
    builtin: true
  - id: nanogpt
    name: NanoGPT
    endpoint: https://nano-gpt.com/api/v1/chat/completions
    api_key: ""
    use_sse: false
    use_structured_outputs: false
    reasoning: false
    provider_settings: ~
    provider_sorting: default
    builtin: true
  - id: nvidia
    name: Nvidia NIM
    endpoint: https://integrate.api.nvidia.com/v1/chat/completions
    api_key: ""
    use_sse: true
    use_structured_outputs: false
    reasoning: false
    provider_settings: ~
    provider_sorting: default
    builtin: true
  - id: chutes
    name: Chutes
    endpoint: https://llm.chutes.ai/v1/chat/completions
    api_key: ""
    use_sse: true
    use_structured_outputs: false
    reasoning: false
    provider_settings: ~
    provider_sorting: default
    builtin: true
"""

def _yaml_dir():
    d = os.path.join(STACK, YAML_DIRNAME)
    os.makedirs(d, exist_ok=True)
    return d

def _yaml_base_path():
    return os.path.join(_yaml_dir(), "Providers.base.yaml")

def _yaml_gen_path():
    return os.path.join(_yaml_dir(), "Providers.generated.yaml")

PANDO_BLOCK_RX = re.compile(r"(?ms)^([ \t]*)- id:[ \t]*(?:pandorumllm-[A-Za-z0-9._-]*|[A-Za-z0-9._-]*-PandorumLLM)\b.*?(?=^[ \t]*- id:|\Z)")

def api_yaml_load(body):
    content = str(body.get("content", ""))
    if not content.strip():
        return {"error": "empty file"}
    if len(content) > 2_000_000:
        return {"error": "file too large"}
    if "providers:" not in content:
        return {"error": "that does not look like a SkyrimNet yaml.yaml (no providers: key)"}
    with open(_yaml_base_path(), "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    n = len(re.findall(r"(?m)^\s*- id:", content))
    cfg = load_config()
    cfg["settings"]["yamlBase"] = "uploaded (%d providers)" % n
    save_config(cfg)
    panel_log("[panel] providers.yaml base uploaded: %d entries" % n)
    return {"ok": True, "count": n}

def api_yaml_generate(body):
    cfg = load_config()
    base = DEFAULT_BASE_YAML
    src = "builtin default"
    if os.path.isfile(_yaml_base_path()):
        base = open(_yaml_base_path(), encoding="utf-8-sig").read()
        src = cfg["settings"].get("yamlBase", "uploaded")
    base = PANDO_BLOCK_RX.sub("", base)   # regenerating: drop our old blocks
    m = re.search(r"(?m)^([ \t]*)- id:", base)
    ind = m.group(1) if m else "  "
    ip = cfg["settings"].get("panelIp") or ""
    warns = []
    if not ip:
        return {"error": "set the PandorumLLM PC IP in Proxy Setup first - the yaml providers must point at it"}
    provs = []
    for s in cfg.get("slots", []):
        for p in s.get("providers", []) or []:
            if p.get("enabled") is not False:
                provs.append(p)
    provs.sort(key=lambda p: int(p.get("port") or 0))
    if not provs:
        return {"error": "no SN providers configured in Proxy Setup"}
    live = set(PROXY._servers.keys())
    blocks = []
    for p in provs:
        title = re.sub(r"[^A-Za-z0-9]+", "", p.get("title") or "Agent") or "Agent"
        port = int(p.get("port") or 0)
        if port not in live:
            warns.append("port %d (%s) is not live on this PC - check for conflicts" % (port, p.get("title")))
        blocks.append(
            ind + "- id: %s-%d-PandorumLLM\n" % (title, port)
            + ind + "  name: %s-%d-PandorumLLM\n" % (title, port)
            + ind + "  endpoint: http://%s:%d/v1/chat/completions\n" % (ip, port)
            + ind + "  api_key: \"1234\"\n"
            + ind + "  use_sse: true\n"
            + ind + "  use_structured_outputs: false\n"
            + ind + "  reasoning: false\n"
            + ind + "  provider_settings: ~\n"
            + ind + "  provider_sorting: default\n"
            + ind + "  builtin: false\n")
    out = base.rstrip("\n") + "\n" + "".join(blocks)
    with open(_yaml_gen_path(), "w", encoding="utf-8", newline="\n") as f:
        f.write(out)
    cfg = load_config()
    cfg["settings"]["yamlGenerated"] = True
    cfg["settings"]["yamlGeneratedAt"] = time.strftime("%Y-%m-%d %H:%M:%S")
    cfg["settings"]["yamlGeneratedIp"] = ip
    save_config(cfg)
    panel_log("[panel] providers.yaml generated: %d PandorumLLM providers on %s (base: %s)" % (len(provs), ip, src))
    return {"ok": True, "count": len(provs), "ip": ip, "base": src, "warnings": warns}

def api_yaml_create(body):
    if not os.path.isfile(_yaml_gen_path()):
        return {"error": "generate providers.yaml first"}
    cfg = load_config()
    outd = cfg["settings"].get("yamlOutDir") or _yaml_dir()
    os.makedirs(outd, exist_ok=True)
    dest = os.path.join(outd, "Providers.yaml")
    shutil.copyfile(_yaml_gen_path(), dest)
    cfg["settings"]["yamlDelivered"] = True
    save_config(cfg)
    panel_log("[panel] providers.yaml written: %s" % dest)
    return {"ok": True, "path": dest}

def api_yaml_mo2(body):
    if not os.path.isfile(_yaml_gen_path()):
        return {"error": "generate providers.yaml first"}
    import zipfile
    cfg = load_config()
    outd = cfg["settings"].get("yamlOutDir") or _yaml_dir()
    os.makedirs(outd, exist_ok=True)
    dest = os.path.join(outd, "PandorumLLM-Providers-DropIn.zip")
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(_yaml_gen_path(), "overwrite/SKSE/Plugins/SkyrimNet/config/Providers.yaml")
    cfg["settings"]["yamlDelivered"] = True
    save_config(cfg)
    panel_log("[panel] drop-in providers zip written: %s" % dest)
    return {"ok": True, "path": dest}

DEFAULT_SPACE_YAML = ("  - id: my-custom-provider\n"
    "    name: My Custom Provider\n"
    "    endpoint: https://example.com/v1/chat/completions\n"
    "    api_key: \"\"\n"
    "    use_sse: true\n"
    "    use_structured_outputs: false\n"
    "    reasoning: false\n"
    "    provider_settings: ~\n"
    "    provider_sorting: default\n"
    "    builtin: false\n")

def _yaml_read_base():
    """Return (text, label, is_builtin) for the persistent base YAML."""
    bp = _yaml_base_path()
    if os.path.isfile(bp):
        try:
            txt = open(bp, encoding="utf-8-sig").read()
            lbl = load_config()["settings"].get("yamlBase", "custom base")
            return txt, lbl, False
        except Exception:
            pass
    return DEFAULT_BASE_YAML, "builtin default (fresh SkyrimNet skeleton)", True

def api_yaml_get(body):
    base, label, builtin = _yaml_read_base()
    gp = _yaml_gen_path()
    gen = ""
    if os.path.isfile(gp):
        try: gen = open(gp, encoding="utf-8-sig").read()
        except Exception: gen = ""
    spaces = load_config().get("yamlSpaces", [])
    return {"ok": True, "base": base, "baseLabel": label, "builtin": builtin,
            "spaces": spaces, "generated": gen}

def api_yaml_base_save(body):
    content = str(body.get("content", ""))
    if "providers:" not in content:
        return {"error": "the base must contain a 'providers:' key"}
    if len(content) > 2_000_000:
        return {"error": "file too large"}
    with open(_yaml_base_path(), "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    n = len(re.findall(r"(?m)^\s*- id:", content))
    cfg = load_config()
    cfg["settings"]["yamlBase"] = "edited base (%d providers)" % n
    save_config(cfg)
    panel_log("[panel] providers.yaml base edited: %d entries" % n)
    return {"ok": True, "count": n}

def api_yaml_base_reset(body):
    bp = _yaml_base_path()
    if os.path.isfile(bp):
        try: os.remove(bp)
        except Exception: pass
    cfg = load_config()
    cfg["settings"].pop("yamlBase", None)
    save_config(cfg)
    panel_log("[panel] providers.yaml base reset to builtin default")
    return {"ok": True}

def api_yaml_space_save(body):
    cfg = load_config()
    spaces = cfg.setdefault("yamlSpaces", [])
    sid = str(body.get("id") or "")
    name = (str(body.get("name") or "Custom space")).strip()[:80] or "Custom space"
    content = body.get("content", None)
    if content is None:
        content = DEFAULT_SPACE_YAML
    content = str(content)
    if len(content) > 2_000_000:
        return {"error": "space too large"}
    hit = None
    for s in spaces:
        if s.get("id") == sid:
            hit = s; break
    if hit is not None:
        hit["name"] = name; hit["content"] = content
    else:
        sid = "sp" + str(int(time.time() * 1000))
        spaces.append({"id": sid, "name": name, "content": content})
    save_config(cfg)
    return {"ok": True, "id": sid, "spaces": spaces}

def api_yaml_space_remove(body):
    cfg = load_config()
    sid = str(body.get("id") or "")
    cfg["yamlSpaces"] = [s for s in cfg.get("yamlSpaces", []) if s.get("id") != sid]
    save_config(cfg)
    return {"ok": True, "spaces": cfg["yamlSpaces"]}

def api_yaml_open_native(body):
    """Open the providers.yaml output folder in the OS file browser (Windows Explorer)."""
    cfg = load_config()
    outd = cfg["settings"].get("yamlOutDir") or _yaml_dir()
    try:
        os.makedirs(outd, exist_ok=True)
    except Exception:
        pass
    if not os.path.isdir(outd):
        return {"error": "folder not found: %s" % outd}
    try:
        os.startfile(outd)   # Windows: opens the folder in Explorer
        return {"ok": True, "path": outd}
    except AttributeError:
        try:
            subprocess.Popen(["xdg-open", outd])
            return {"ok": True, "path": outd}
        except Exception:
            return {"error": "cannot open a native file window on this OS"}
    except Exception as e:
        return {"error": str(e)}

def _within(child, roots):
    """True iff child resolves to inside one of roots. Windows-safe (normcase) and symlink-safe (realpath)."""
    try:
        c = os.path.normcase(os.path.realpath(child))
    except Exception:
        return False
    for root in roots:
        if not root:
            continue
        try:
            r = os.path.normcase(os.path.realpath(root))
        except Exception:
            continue
        if c == r or c.startswith(r + os.sep):
            return True
    return False

def _all_roots(cfg):
    """Every folder the app is legitimately allowed to touch."""
    st = cfg.get("settings", {})
    roots = list(cfg.get("launcherDirs", []))
    for k in ("llamacppPath", "modelsDir", "logDir", "outputDir", "yamlOutDir"):
        if st.get(k):
            roots.append(st[k])
    roots.append(ARCHIVE)
    try: roots.append(log_dir(cfg))
    except Exception: pass
    try: roots.append(_yaml_dir())
    except Exception: pass
    return [r for r in roots if r]

_EXE_EXTS = {".exe", ".com", ".bat", ".cmd", ".scr", ".msi", ".vbs", ".vbe", ".js", ".jse", ".wsf", ".wsh", ".msc", ".cpl", ".dll", ".sys", ".pif", ".reg"}

def _list_drives():
    if os.name == "nt":
        return [("%s:" + os.sep) % c for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if os.path.isdir(("%s:" + os.sep) % c)]
    return ["/"]

def api_browse_dirs(body):
    """Browser for SETTING paths. Host-only.

    Directories only by default. When "exts" is supplied it ALSO lists files with those
    extensions, because a path field naming a file cannot be filled from a folder list.
    Not containment-gated, deliberately: the purpose is to reach a location that is not
    yet configured, which is why the directory side was never gated either. Reachability
    is the control - this endpoint is host-only.
    """
    exts = body.get("exts") or []
    exts = [str(e).lower() for e in exts if str(e).startswith(".")][:8]
    path = str(body.get("path", "") or "").strip()
    if not path:
        return {"path": "", "parent": None, "dirs": [], "files": [], "drives": _list_drives()}
    path = os.path.abspath(path)
    if not os.path.isdir(path):
        return {"error": "not a folder"}
    dirs = []
    try:
        for name in sorted(os.listdir(path), key=str.lower):
            full = os.path.join(path, name)
            try:
                if os.path.isdir(full) and not os.path.islink(full):
                    dirs.append(name)
            except Exception:
                pass
    except PermissionError:
        return {"error": "access denied to this folder"}
    except Exception as e:
        return {"error": str(e)}
    files = []
    if exts:
        try:
            for name in sorted(os.listdir(path), key=str.lower):
                if os.path.splitext(name)[1].lower() not in exts:
                    continue
                full = os.path.join(path, name)
                try:
                    if os.path.isfile(full):
                        files.append({"name": name, "size": fmt_size(os.path.getsize(full))})
                except Exception:
                    pass
                if len(files) >= 500:
                    break
        except Exception:
            pass
    rest = os.path.splitdrive(path)[1]
    if rest in ("", os.sep, "/") or os.path.dirname(path.rstrip("\\/")) == path:
        parent = ""
    else:
        parent = os.path.dirname(path.rstrip("\\/"))
    return {"path": path, "parent": parent, "dirs": dirs, "drives": _list_drives(), "files": files}

FOLDER_VIEW_EXT = {"models": {".gguf"}, "launcher": {".ps1", ".bat"}, "yaml": {".yaml", ".yml"}, "log": {".log"}, "output": {".ps1", ".bat"}}

def api_folder_view(body):
    """List ONLY the relevant files (by extension) inside a configured folder, jailed to that folder. Host-only."""
    which = str(body.get("which", ""))
    exts = FOLDER_VIEW_EXT.get(which)
    if not exts:
        return {"error": "unknown folder"}
    cfg = load_config(); st = cfg.get("settings", {})
    if which == "models":
        roots = [st.get("modelsDir")]
    elif which == "launcher":
        roots = list(cfg.get("launcherDirs", []))
    elif which == "output":
        roots = [st.get("outputDir")]
    elif which == "yaml":
        roots = [st.get("yamlOutDir") or _yaml_dir()]
    elif which == "log":
        roots = [log_dir(cfg)]
    else:
        roots = []
    roots = [os.path.abspath(r) for r in roots if r and os.path.isdir(r)]
    if not roots:
        return {"error": "that folder is not set yet"}
    files = []; CAP = 2000
    for root in roots:
        for dp, dns, fns in os.walk(root):
            if not _within(dp, [root]):
                dns[:] = []; continue
            for fn in fns:
                if os.path.splitext(fn)[1].lower() in exts:
                    full = os.path.join(dp, fn)
                    try: sz = fmt_size(os.path.getsize(full))
                    except Exception: sz = "?"
                    files.append({"name": fn, "rel": os.path.relpath(full, root), "size": sz})
            if len(files) >= CAP: break
        if len(files) >= CAP: break
    files.sort(key=lambda f: f["rel"].lower())
    return {"which": which, "root": roots[0], "count": len(files), "capped": len(files) >= CAP, "files": files}

def api_client_error(body):
    log_error("browser", "%s @ %s:%s" % (body.get("msg", "?"), body.get("src", ""), body.get("line", "")))
    return {"ok": True}

def api_detect_ip(body):
    ips = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("192.0.2.1", 80))      # reserved, never routed: asks the OS which interface would be used; ips.append(s.getsockname()[0]); s.close()
    except Exception: pass
    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            if ip not in ips: ips.append(ip)
    except Exception: pass
    return {"ips": [i for i in ips if not i.startswith("127.")]}

def _stamp_log(text):
    """Prefix every line with [HH:MM:SS] for the fleet status terminal."""
    ts = _dt.datetime.now().strftime("[%H:%M:%S] ")
    return "\n".join((ts + ln) if ln.strip() else ln for ln in str(text).split("\n"))

def api_launch_stack(body):
    if not _FLEET_LOCK.acquire(blocking=False):
        return {"error": "a launch is already running"}
    try:
        return _api_launch_stack(body)
    finally:
        _FLEET_LOCK.release()


def _api_launch_stack(body):
    lines = [_stamp_log("=== %s %s - launch stack ===" % (APP_NAME, APP_VER_UI))]
    try:
        for _s in load_config().get("slots", []):
            if not _s.get("script"): continue
            _up = parse_ps1_port(_s.get("script") or "") or _s.get("port")
            if _up: PROXY.note_load(_up)
    except Exception: pass
    r = PROXY.sync()
    lines.append(_stamp_log("PROXY embedded listeners: %s" % (", ".join(str(x) for x in r["listening"]) or "none")))
    panel_log("[panel] launch stack")
    lines.append(_stamp_log(run_fleet([])))
    return {"log": "\n".join(lines)}

def api_show_terminal(body):
    cfg = load_config()
    s = next((x for x in cfg.get("slots", []) if x.get("id") == body.get("slot")), None)
    if not s or not s.get("script"):
        return {"error": "slot has no launcher assigned"}
    stem = re.sub(r"\.ps1$", "", os.path.basename(s["script"]), flags=re.I).replace("'", "''")
    ps = ("Add-Type -Namespace W -Name U -MemberDefinition "
          "'[DllImport(\"user32.dll\")] public static extern bool ShowWindow(IntPtr h,int c);"
          "[DllImport(\"user32.dll\")] public static extern bool SetForegroundWindow(IntPtr h);';"
          "$w = Get-Process | Where-Object { $_.MainWindowTitle -like '*| %s*' } | Select-Object -First 1;"
          "if ($w) { [W.U]::ShowWindow($w.MainWindowHandle,9) | Out-Null;"
          "[W.U]::SetForegroundWindow($w.MainWindowHandle) | Out-Null; 'restored' } else { 'window not found' }") % stem
    try:
        p = subprocess.run(["pwsh", "-NoProfile", "-Command", ps], **NOWIN,
                           capture_output=True, text=True, timeout=20)
        return {"log": (p.stdout or p.stderr or "").strip()}
    except Exception as e:
        return {"error": str(e)}

# ---------------------------------------------------------------- slots / settings
def api_assign(body):
    cfg = load_config()
    for s in cfg.get("slots", []):
        if s.get("id") == body.get("slot"):
            path = body.get("script", "") or ""
            if path and not os.path.isfile(path):
                return {"error": "file not found: " + path}
            s["script"] = path
            oldp = s.get("port")
            if path:
                pp = parse_ps1_port(path)
                if pp and 1000 <= pp <= 9999:
                    s["port"] = pp   # slot expectation follows the launcher
            save_config(cfg)
            PROXY.sync()
            return {"ok": True, "oldPort": oldp, "newPort": s.get("port")}
    return {"error": "unknown slot"}

def api_edit(body):
    cfg = load_config()
    for s in cfg.get("slots", []):
        if s.get("id") == body.get("slot"):
            if "label" in body:
                lab = str(body["label"]).strip()[:60]
                if not lab:
                    return {"error": "name can't be empty"}
                s["label"] = lab
                s["autoName"] = False
            if "port" in body:
                ps = str(body["port"]).strip()
                if not re.fullmatch(r"\d{4}", ps):
                    return {"error": "port has to be four numbers (1000-9999)"}
                s["port"] = int(ps)
            if "gpu" in body:
                s["gpu"] = str(body["gpu"]).strip()[:20] or s.get("gpu", "")
            if "gpuId" in body:
                gid = str(body["gpuId"]).strip()
                if gid and gid not in {g.get("id") for g in cfg.get("gpus", [])}:
                    return {"error": "unknown GPU"}
                s["gpuId"] = gid
                apply_auto_names(cfg)
            save_config(cfg)
            PROXY.sync()
            return {"ok": True}
    return {"error": "unknown slot"}

def api_add(body):
    cfg = load_config()
    slots = cfg.setdefault("slots", [])
    if len(slots) >= MAX_SLOTS:
        return {"error": "max %d slots" % MAX_SLOTS}
    used = {s.get("id") for s in slots}
    n = 1
    while "slot%d" % n in used:
        n += 1
    taken = {int(s.get("port") or 0) for s in slots}
    taken |= {int(p.get("port") or 0) for s in slots for p in s.get("providers", []) or []}
    taken.add(PORT)
    port = 1236
    while port in taken and port < 9999:
        port += 1
    slots.append({"id": "slot%d" % n, "label": "server %d" % n, "port": min(port, 9999),
                  "script": "", "gpu": "", "gpuId": "", "autoName": True, "providers": []})
    save_config(cfg)
    return {"ok": True}

def api_remove(body):
    cfg = load_config()
    slots = cfg.get("slots", [])
    if len(slots) <= 1:
        return {"error": "at least 1 slot is required"}
    keep = [s for s in slots if s.get("id") != body.get("slot")]
    if len(keep) == len(slots):
        return {"error": "unknown slot"}
    cfg["slots"] = keep
    save_config(cfg)
    return {"ok": True}

def api_settings(body):
    cfg = load_config()
    st = cfg.setdefault("settings", {})
    if "networkMode" in body:
        st["networkMode"] = "lan" if str(body["networkMode"]).lower() == "lan" else "localhost"
    if "devMode" in body:
        st["devMode"] = bool(body["devMode"])
    if "welcomeSeen" in body:
        st["welcomeSeen"] = bool(body["welcomeSeen"])
    if "termBlack" in body:
        st["termBlack"] = bool(body["termBlack"])
    if "termScaleMode" in body:
        st["termScaleMode"] = "manual" if str(body["termScaleMode"]).lower() == "manual" else "auto"
    if "termFontSize" in body:
        try:
            st["termFontSize"] = max(8, min(24, int(body["termFontSize"])))
        except Exception:
            pass
    if "termScaleOn" in body:
        st["termScaleOn"] = bool(body["termScaleOn"])
    if body.get("launcherDir"):
        st["outputDir"] = str(body["launcherDir"])     # one folder serves as both
    if "termScales" in body and isinstance(body["termScales"], dict):
        clean = {}
        for k in TERM_SCALE_KINDS + TERM_SCALE_LEGACY:
            d = body["termScales"].get(k)
            if isinstance(d, dict):
                try:
                    sz = max(8, min(24, int(d.get("size") or 12)))
                except Exception:
                    sz = 12
                fnt = str(d.get("font") or "")[:40]
                clean[k] = {
                    "mode": "auto" if str(d.get("mode")).lower() == "auto" else "manual",
                    "size": sz,
                    "on": bool(d.get("on", True)),
                    "font": fnt,
                }
        st["termScales"] = clean
    if "peerAddr" in body:
        st["peerAddr"] = str(body["peerAddr"]).strip()[:80]
    if "autoRefresh" in body:
        try:
            st["autoRefresh"] = max(0, min(3600, int(body["autoRefresh"])))
        except Exception:
            st["autoRefresh"] = 0
    if "srvEdOpen" in body:
        st["srvEdOpen"] = bool(body["srvEdOpen"])
    if "observerOn" in body:
        st["observerOn"] = bool(body["observerOn"])
    if "statsMonitoring" in body:
        st["statsMonitoring"] = bool(body["statsMonitoring"])
    if "onePC" in body:
        st["onePC"] = bool(body["onePC"])
    if "themeName" in body:
        st["themeName"] = str(body["themeName"])[:30]
    if "customThemes" in body and isinstance(body["customThemes"], dict):
        st["customThemes"] = {str(k)[:40]: {kk: str(vv)[:9] for kk, vv in (v or {}).items()}
                              for k, v in list(body["customThemes"].items())[:40]}
    if "themeVars" in body and isinstance(body["themeVars"], dict):
        _clean = {}
        for _k, _v in body["themeVars"].items():
            if _k in ("bg", "card", "edge", "txt", "dim", "acc", "ok", "warn", "err") and re.fullmatch(r"#[0-9a-fA-F]{6}", str(_v)):
                _clean[_k] = str(_v)
        st["themeVars"] = _clean
    _HANDLED_KEYS = ("onePC", "devMode", "welcomeSeen", "termBlack", "networkMode", "themeName", "themeVars", "termScaleMode", "termFontSize", "termScaleOn", "termScales", "statsMonitoring", "customThemes", "srvEdOpen", "observerOn", "autoRefresh", "peerAddr")
    for k in DEF_SETTINGS:
        if k not in body or k in _HANDLED_KEYS:
            continue
        if k in ("exitOnClose", "launchArc"):
            st[k] = bool(body[k]) if not isinstance(body[k], str) else body[k].lower() in ("1", "true", "on", "yes")
            continue
        v = str(body[k]).strip()
        if k in ("panelIp", "remoteIp") and v and not re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", v):
            return {"error": "%s must be an IPv4 address" % k}
        st[k] = v
    if st.get("launcherDir"):
        cfg["launcherDirs"] = [st["launcherDir"]]
    save_config(cfg)
    PROXY.sync()
    try:
        TTSW.sync()
    except Exception:
        pass
    return {"ok": True}

# ---------------------------------------------------------------- creator / inspector / logs
GEN_LAUNCHER_DIR = os.path.join(STACK, "generated-launchers")

def llama_exe(cfg):
    """Absolute path to llama-server.exe from the configured llama.cpp folder."""
    base = ((cfg.get("settings", {}) or {}).get("llamacppPath") or "C:\\llama.cpp-cuda").rstrip("\\/")
    return base + "\\llama-server.exe"

def render_launcher_lines(t, dest, llexe):
    """Substitute a launcher template with one parameter set.

    Shared by the Creator (which writes user-visible .ps1 files) and by server
    slots (which render a hidden launcher from their stored parameters), so the
    two can never drift apart.
    """
    vis_off = t.get("vision") in ("", "N/A", "Disabled", None)
    drf_off = t.get("draft") in ("", "N/A", "Disabled", None)
    out_lines = []
    for line in (t.get("content") or "").splitlines():
        # conditional flags: skip the whole line (placeholder OR already-resolved) when the dropdown is empty
        if ('"--mmproj"' in line or "<MMPROJ_PATH>" in line) and vis_off:
            continue
        if ('"--model-draft"' in line or "<DRAFT_PATH>" in line) and drf_off:
            continue
        if "<GPU_ID>" in line and t.get("gpu") in ("", "N/A", "Disabled", None):
            continue
        line = (line.replace("<MODEL_PATH>", t.get("model") or "")
                    .replace("<MMPROJ_PATH>", t.get("vision") or "")
                    .replace("<DRAFT_PATH>", t.get("draft") or "")
                    .replace("<TITLE>", t.get("title") or "")
                    .replace("<SELF_PATH>", dest)
                    .replace("<SELF_NAME>", os.path.basename(dest))
                    .replace("<GPU_ID>", t.get("gpu") or "")
                    .replace("<PORT>", str(t.get("port") or ""))
                    .replace("<LLAMA_EXE>", llexe)
                    .replace("C:\\llama.cpp-cuda\\llama-server.exe", llexe))
        out_lines.append(line)
    # if a model IS selected but its flag line is missing from the content, inject it after --model
    def _inject(flag, path):
        if any(('"%s"' % flag) in ln for ln in out_lines):
            return
        mi = next((i for i, ln in enumerate(out_lines) if '"--model"' in ln), None)
        entry = '    "%s", "%s",' % (flag, path)
        if mi is not None:
            out_lines.insert(mi + 1, entry)
        else:
            out_lines.append(entry)
    if not vis_off:
        _inject("--mmproj", t.get("vision"))
    if not drf_off:
        _inject("--model-draft", t.get("draft"))
    return out_lines

def _gpu_pin_value(cfg, gpu_id):
    """CUDA_VISIBLE_DEVICES value for a slot's GPU - UUID pinning, index as fallback."""
    for g in cfg.get("gpus", []):
        if g.get("id") == gpu_id:
            return g.get("uuid") or str(g.get("index", ""))
    return ""

# ITEM 9: the runtime parameter set a server launches with. Samplers are deliberately
# absent - llama.cpp CLI samplers are only defaults, and the proxy injects per-provider
# sampler values into every request, so each provider stays adjustable on the fly.
SERVER_PARAMS = [
    ("ctx",       "Context size",        "int",  "8192",  {"min": 512,  "max": 262144, "step": 512},  "--ctx-size",         "Context size"),
    ("ngl",       "GPU layers",          "int",  "99",    {"min": 0,    "max": 999,    "step": 1},    "--n-gpu-layers",     "GPU layers"),
    ("flash",     "Flash attention",     "sel",  "on",    {"opts": ["on", "off", "auto"]},            "--flash-attn",       "Flash attention"),
    ("cacheK",    "KV cache type (K)",   "sel",  "f16",   {"opts": ["f32", "f16", "bf16", "q8_0", "q5_1", "q5_0", "q4_1", "q4_0", "iq4_nl"]}, "--cache-type-k", "KV cache quantization"),
    ("cacheV",    "KV cache type (V)",   "sel",  "f16",   {"opts": ["f32", "f16", "bf16", "q8_0", "q5_1", "q5_0", "q4_1", "q4_0", "iq4_nl"]}, "--cache-type-v", "KV cache quantization"),
    ("parallel",  "Parallel slots",      "int",  "1",     {"min": 1,    "max": 16,     "step": 1},    "--parallel",         "Concurrency (parallel slots)"),
    ("batch",     "Batch size",          "int",  "2048",  {"min": 32,   "max": 16384,  "step": 32},   "--batch-size",       "Prompt batching"),
    ("ubatch",    "Micro-batch size",    "int",  "512",   {"min": 32,   "max": 4096,   "step": 32},   "--ubatch-size",      "Prompt batching"),
    ("threads",   "CPU threads",         "int",  "8",     {"min": 1,    "max": 128,    "step": 1},    "--threads",          "Threads / mmap / fit"),
    ("npredict",  "Generation cap",      "int",  "-1",    {"min": -2,   "max": 32768,  "step": 1},    "--n-predict",        "Generation cap"),
    ("nommap",    "Disable mmap",        "sel",  "off",   {"opts": ["off", "on"]},                    "--no-mmap",          "Threads / mmap / fit"),
    ("nocontbat", "Disable cont batching","sel", "off",   {"opts": ["off", "on"]},                    "--no-cont-batching", "Concurrency (parallel slots)"),
    ("fit",       "Auto fit to VRAM",    "sel",  "off",   {"opts": ["off", "on"]},                    "--fit",              "Threads / mmap / fit"),
]

# Which heading each parameter is written under in a generated launcher, and the order
# the headings appear in - broad setup first, then tuning, then output.
PARAM_GROUP = {
    "ctx": "Context and cache", "cacheK": "Context and cache", "cacheV": "Context and cache",
    "ngl": "GPU", "flash": "GPU", "fit": "GPU",
    "parallel": "Batching and concurrency", "batch": "Batching and concurrency",
    "ubatch": "Batching and concurrency", "nocontbat": "Batching and concurrency",
    "threads": "CPU", "nommap": "CPU",
    "npredict": "Generation",
}
PARAM_GROUP_ORDER = ["Model", "Server", "GPU", "Context and cache",
                     "Batching and concurrency", "CPU", "Generation", "Logging", "Other"]

def param_defaults():
    return {k: d for (k, _lab, _kind, d, _o, _f, _r) in SERVER_PARAMS}

def build_param_launcher(cfg, s, dest):
    """Compose a llama-server launcher from a slot's parameter set.

    Written in the same "--flag", "value" shape the rest of the panel parses, so
    port/model/sampler introspection keeps working against the generated file.
    """
    p = s.get("params") or {}
    d = param_defaults()
    def gv(k):
        v = str(p.get(k, "")).strip()
        return v if v != "" else d.get(k, "")
    q = lambda v: str(v).replace('"', '`"')
    title = s.get("label") or s.get("id") or "server"
    pin = _gpu_pin_value(cfg, s.get("gpuId") or "")
    L = []
    L.append("# " + "=" * 62)
    L.append("#  %s  -  generated by PandorumLLM from the server's parameters." % title)
    L.append("#  Do not edit by hand: it is rewritten on every launch.")
    L.append("# " + "=" * 62)
    L.append('$Host.UI.RawUI.WindowTitle = "%s"' % q(title))
    L.append("[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()")
    if pin:
        L.append('$env:CUDA_VISIBLE_DEVICES = "%s"' % q(pin))
    L.append("")
    args = [("Model", "--model", p.get("model") or "")]
    if (p.get("vision") or "N/A") not in ("", "N/A", "Disabled"):
        args.append(("Model", "--mmproj", p["vision"]))
    if (p.get("draft") or "N/A") not in ("", "N/A", "Disabled"):
        args.append(("Model", "--model-draft", p["draft"]))
    args += [("Server", "--port", str(s.get("port") or "")),
             ("Server", "--host", "0.0.0.0"),
             ("Server", "--alias", title)]
    bare = {"nommap", "nocontbat", "fit"}          # switches, not values
    for (k, _lab, kind, _dv, _o, flag, _ref) in SERVER_PARAMS:
        v = gv(k)
        if v == "":
            continue
        if k in bare:
            if v == "on":
                args.append((PARAM_GROUP.get(k, "Other"), flag, None))
            continue
        args.append((PARAM_GROUP.get(k, "Other"), flag, v))
    # reasoning is always enabled on the server - each provider then turns thinking
    # on or off for its own requests through the proxy
    args.append(("Generation", "--reasoning", "on"))
    args.append(("Logging", "-lv", "4"))          # verbose log level, kept out of the UI
    if str(p.get("noCache", "1")) in ("1", "true", "True"):
        args.append(("Context and cache", "--cache-ram", "0"))
        args.append(("Context and cache", "--ctx-checkpoints", "0"))
    # An array can be commented and needs no line continuations, so each group of flags
    # can be labelled. The panel reads the same "--flag", "value" pairs out of it.
    L.append("$llamaArgs = @(")
    for group in PARAM_GROUP_ORDER:
        rows = [(f, v) for (g, f, v) in args if g == group]
        if not rows:
            continue
        L.append("    # %s %s" % (group, "-" * max(4, 56 - len(group))))
        for flag, val in rows:
            L.append('    "%s"' % flag if val is None else '    "%s", "%s"' % (flag, q(val)))
        L.append("")
    while L and L[-1] == "":
        L.pop()
    L.append(")")
    L.append("")
    L.append('& "%s" @llamaArgs' % q(llama_exe(cfg)))
    L.append("")
    return "\n".join(L) + "\n"

def regen_slot_script(cfg, s):
    """Render a server slot's parameters into a generated launcher and point the
    slot at it. The .ps1 is an implementation detail: the UI edits parameters,
    and launch-llm-fleet.ps1 keeps launching a script path exactly as before."""
    p = s.get("params") or {}
    if not (p.get("model") or "").strip():
        return ""                                     # no model yet - nothing launchable
    try:
        os.makedirs(GEN_LAUNCHER_DIR, exist_ok=True)
    except Exception as e:
        return {"error": "cannot create %s (%s)" % (GEN_LAUNCHER_DIR, e)}
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", str(s.get("id") or "slot"))
    dest = os.path.join(GEN_LAUNCHER_DIR, safe + ".ps1")
    custom = (p.get("custom") or "").strip()
    try:
        with open(dest, "w", encoding="utf-8-sig", newline="\r\n") as f:
            f.write((custom + "\n") if custom else build_param_launcher(cfg, s, dest))
    except Exception as e:
        return {"error": "cannot write generated launcher: %s" % e}
    s["script"] = dest
    return dest

def api_slot_params(body):
    """Save a server slot's launch parameters and regenerate its hidden launcher."""
    cfg = load_config()
    sid = str(body.get("slot") or "")
    s = next((x for x in cfg.get("slots", []) if x.get("id") == sid), None)
    if not s:
        return {"error": "unknown server slot"}
    p = s.setdefault("params", {})
    for k in ["model", "vision", "draft", "noCache"] + [x[0] for x in SERVER_PARAMS]:
        if k in body:
            p[k] = str(body[k])
    r = regen_slot_script(cfg, s)
    save_config(cfg)
    if isinstance(r, dict) and r.get("error"):
        return r
    sse_notify("state")
    return {"ok": True, "script": s.get("script", ""), "params": p}

def parse_launcher_params(text):
    """Read a launcher back into the parameter set the server cards edit.

    Used when someone hand-edits the launcher or loads an existing .ps1, so the
    cards stay a faithful view of what will actually run.
    """
    out, bare = {}, {"nommap", "nocontbat", "fit"}
    # values a launcher sets up first and refers to later, e.g. $modelPath = "D:\\...gguf"
    vars_ = {}
    for vm in re.finditer(r'\$([A-Za-z_][A-Za-z0-9_]*)\s*=\s*"([^"]*)"', text):
        vars_.setdefault(vm.group(1), vm.group(2))
    def grab(flag):
        m = re.search(r'"%s"\s*,\s*"([^"]*)"' % re.escape(flag), text)
        if m:
            return m.group(1)
        # written as a variable instead: follow it back to where it was set
        m = re.search(r'"%s"\s*,\s*\$([A-Za-z_][A-Za-z0-9_]*)' % re.escape(flag), text)
        if m:
            return vars_.get(m.group(1))
        return None
    def present(flag):
        return re.search(r'"%s"' % re.escape(flag), text) is not None
    mm = grab("--model") or grab("-m")
    if mm:
        out["model"] = mm
    out["vision"] = grab("--mmproj") or "N/A"
    # a draft model is named by either flag depending on which llama.cpp is in use
    out["draft"] = grab("--model-draft") or grab("--spec-draft-model") or grab("-md") or "N/A"
    OFF = {"off", "false", "0", "no"}
    for (k, _lab, _kind, _dv, _o, flag, _ref) in SERVER_PARAMS:
        if k in bare:
            # these read as switches, but a launcher may still spell out on or off after
            # them - and "--fit", "off" plainly means off, not on
            v = grab(flag)
            if v is not None:
                out[k] = "off" if v.strip().lower() in OFF else "on"
            else:
                out[k] = "on" if present(flag) else "off"
        else:
            v = grab(flag)
            if v is not None:
                out[k] = v
    return out

# What the panel knows about a llama-server flag. Anything not named here is reported
# as unrecognised rather than quietly passed on, because a flag we cannot read is a flag
# the server cards cannot show you and the guide cannot reason about.
LAUNCH_FLAGS = {
    # shown and editable on the server card
    "-m": "the model", "--model": "the model",
    "--mmproj": "the vision projector", "--model-draft": "the draft model",
    "--spec-draft-model": "the draft model", "-md": "the draft model",
    "--port": "the port", "--host": "the listening address", "--alias": "the server name",
    # understood, passed straight to llama-server, not shown on the card
    "--main-gpu": "which card to prefer", "--split-mode": "how layers are split across cards",
    "--tensor-split": "how layers are split across cards", "--device": "which devices to use",
    "--reasoning": "whether the server emits thinking", "--reasoning-budget": "thinking budget",
    "--reasoning-budget-message": "what is said when the thinking budget runs out",
    "--reasoning-format": "how thinking is wrapped in the reply",
    "--chat-template-file": "chat template handling", "--special": "shows special tokens",
    "--poll": "how the worker waits", "--slots": "serves its slot state",
    "--no-warmup": "skips the warm-up pass", "--override-kv": "overrides a header value",

    "--cache-ram": "host cache size", "--ctx-checkpoints": "context checkpoints",
    "--spec-type": "the kind of speculative decoding",
    "--spec-draft-n-max": "speculative decoding depth",
    "--draft-max": "speculative decoding depth", "--draft-min": "speculative decoding depth",
    "-lv": "log verbosity", "--log-file": "where llama-server writes its own log",
    "--verbose": "log verbosity", "--no-webui": "turns off llama-server's own page",
    "--jinja": "chat template handling", "--chat-template": "chat template handling",
    "--api-key": "an api key", "--timeout": "request timeout", "--keep": "tokens kept",
    "--rope-scaling": "rope scaling", "--rope-freq-base": "rope scaling",
    "--rope-freq-scale": "rope scaling", "--yarn-ext-factor": "rope scaling",
    "--mlock": "locks weights in RAM", "--numa": "NUMA placement",
    "--no-mmproj": "no vision projector for this server",
    "--cache-reuse": "how much of a prompt may be reused",
    "--no-context-shift": "context shifting", "--swa-full": "sliding window attention",
    "--list-devices": "prints the devices and exits", "--props": "serves its own settings",

    "--threads-batch": "batch threads", "--defrag-thold": "kv defragmentation",
    "--slot-save-path": "where slots are saved", "--metrics": "prometheus metrics",
}
# Sampling belongs to the proxy: each provider sets its own per request, so whatever a
# launcher says here is only a default and cannot break a launch.
SAMPLER_FLAGS = {
    "--samplers", "--temp", "--temperature", "--top-k", "--top-p", "--min-p", "--typical",
    "--typ-p", "--top-n-sigma", "--xtc-probability", "--xtc-threshold", "--mirostat",
    "--mirostat-lr", "--mirostat-ent", "--dry-multiplier", "--dry-base",
    "--dry-allowed-length", "--dry-penalty-last-n", "--dry-sequence-breaker",
    "--repeat-penalty", "--repeat-last-n", "--frequency-penalty", "--presence-penalty",
    "--seed", "--ignore-eos", "--logit-bias", "--grammar", "--grammar-file", "--json-schema",
}

# What has no business in a launcher whose only job is to start llama-server. This
# catches mistakes and the obvious, not a determined attacker: PowerShell can be
# obfuscated past any list of words, so a clean sweep means "nothing alarming was
# found", never "this file is safe". The report says so.
SWEEP_RULES = [
    ("runs text as code", r"\bInvoke-Expression\b|\biex\b\s*[\(\$\"']|\bicm\b\s+-Script"),
    ("runs a hidden, encoded command", r"-Enc(?:odedCommand)?\b|\bFromBase64String\b"),
    ("fetches something off the internet", r"\bInvoke-WebRequest\b|\bInvoke-RestMethod\b|\bDownloadString\b"
                                           r"|\bDownloadFile\b|\bStart-BitsTransfer\b|\bNet\.WebClient\b"
                                           r"|\bcurl\b|\bwget\b|\bbitsadmin\b"),
    ("loads code into memory", r"\bReflection\.Assembly\b|\[Assembly\]::|\bAdd-Type\b\s+-TypeDefinition"),
    ("changes Windows Defender", r"\bAdd-MpPreference\b|\bSet-MpPreference\b|\bMpCmdRun\b"),
    ("makes itself run at startup", r"\bschtasks\b|\bNew-ScheduledTask|\bNew-Service\b"
                                    r"|CurrentVersion\\+Run|\bStartup\\+"),
    ("edits the registry", r"\bNew-ItemProperty\b|\bSet-ItemProperty\b\s+-Path\s+['\"]?HKLM|\breg\s+add\b"),
    ("reads or stores credentials", r"\bGet-Credential\b|\bConvertTo-SecureString\b|\bnet\s+user\b"),
    ("deletes files in bulk", r"\bRemove-Item\b[^\n]*-Recurse[^\n]*-Force|\bFormat-Volume\b|\bdel\s+/[sf]"),
    ("launches another program to run code", r"\bmshta\b|\brundll32\b|\bregsvr32\b|\bcertutil\b[^\n]*-decode"),
    ("hides its own window", r"-WindowStyle\s+Hidden|-NonInteractive[^\n]*-Enc"),
]

def sweep_launcher(text):
    """Read a launcher and report anything that does not belong in one."""
    found = []
    for why, pat in SWEEP_RULES:
        m = re.search(pat, text, re.I)
        if m:
            ln = text[:m.start()].count("\n") + 1
            found.append({"why": why, "at": ln, "saw": m.group(0)[:40]})
    starts = bool(re.search(r"llama-server(\.exe)?", text, re.I))
    return {"findings": found, "startsAServer": starts,
            "verdict": ("nothing alarming found" if not found else "look at this before using it")}

def sweep_launcher_dir(cfg):
    """Sweep every .ps1 in the launcher folder and remember what was found."""
    d = (cfg.get("settings", {}) or {}).get("launcherDir") or ""
    out = {}
    if not d or not os.path.isdir(d):
        return {"error": "set the launcher folder first"}
    for fn in sorted(os.listdir(d)):
        if not fn.lower().endswith(".ps1"):
            continue
        p = os.path.join(d, fn)
        try:
            with open(p, encoding="utf-8-sig", errors="replace") as f:
                txt = f.read()
        except Exception as e:
            out[fn] = {"error": str(e)[:80]}
            continue
        r = sweep_launcher(txt)
        r["hash"] = hashlib.sha256(txt.encode("utf-8", "replace")).hexdigest()[:16]
        out[fn] = r
    cfg.setdefault("settings", {})["launcherSweep"] = out
    return {"ok": True, "swept": len(out),
            "flagged": len([1 for v in out.values() if v.get("findings")])}

def api_sweep_launchers(body):
    cfg = load_config()
    r = sweep_launcher_dir(cfg)
    if r.get("error"):
        return r
    save_config(cfg)
    panel_log("[panel] swept %d launcher(s), %d flagged" % (r["swept"], r["flagged"]))
    return r

def validate_launcher(text):
    """Read a launcher the way the panel will and say what it made of every flag.

    Three outcomes per flag: shown on the card, understood and passed on, or not
    recognised. Sampling flags are called out separately because they are only defaults
    - the proxy sets sampling per request - so they can never stop a server starting.
    """
    card = {f for (_k, _l, _ki, _d, _o, f, _r) in SERVER_PARAMS}
    seen, unknown, sampler, applied, passed = [], [], [], [], []
    parsed = parse_launcher_params(text)
    for m in re.finditer(r'"(-{1,2}[A-Za-z][A-Za-z0-9-]*)"', text):
        flag = m.group(1)
        if flag in seen:
            continue
        seen.append(flag)
        if flag in card:
            key = next(k for (k, _l, _ki, _d, _o, f, _r) in SERVER_PARAMS if f == flag)
            applied.append((flag, "shown on the card as %s" % key, parsed.get(key)))
        elif flag in LAUNCH_FLAGS:
            passed.append((flag, LAUNCH_FLAGS[flag]))
        elif flag in SAMPLER_FLAGS:
            sampler.append(flag)
        else:
            unknown.append(flag)
    lines = []
    A = lines.append
    A("%d flags read" % len(seen))
    A("")
    if applied:
        A("shown on the server card (%d):" % len(applied))
        for f, note, val in applied:
            A("   %-22s %s%s" % (f, note, "" if val is None else "  ->  " + str(val)))
        A("")
    if passed:
        A("understood, handed to llama-server unchanged (%d):" % len(passed))
        for f, note in passed:
            A("   %-22s %s" % (f, note))
        A("")
    if sampler:
        A("sampling, only a default (%d): %s" % (len(sampler), ", ".join(sampler)))
        A("   the proxy sets sampling per request, so these cannot stop a server starting")
        A("")
    if unknown:
        A("NOT RECOGNISED (%d) - check these before launching:" % len(unknown))
        for f in unknown:
            A("   %s" % f)
        A("   the panel cannot show these on the card or reason about them. If llama-server")
        A("   accepts them the server will still start; if it does not, it will refuse.")
    else:
        A("every flag was recognised")
    for key, label in (("model", "model"), ("draft", "draft model"), ("vision", "vision projector")):
        v = parsed.get(key)
        if v and v != "N/A":
            A("")
            A("%s: %s" % (label, "file not found" if not os.path.isfile(v)
                                 else "reads as a %s model" % model_kind(v)))
    return "\n".join(lines) + "\n"

def api_validate_launcher(body):
    text = str(body.get("content") or "")
    if not text.strip():
        return {"error": "there is nothing in the editor to check"}
    try:
        return {"ok": True, "text": validate_launcher(text)}
    except Exception as e:
        return {"error": "could not read that launcher (%s)" % e}

def _slot_by_id(cfg, sid):
    return next((x for x in cfg.get("slots", []) if x.get("id") == str(sid or "")), None)

def api_slot_launcher_save(body):
    """Accept hand-edited launcher text: keep it verbatim and re-read the params from it."""
    cfg = load_config()
    s = _slot_by_id(cfg, body.get("slot"))
    if not s:
        return {"error": "unknown server"}
    text = str(body.get("content") or "")
    if not text.strip():
        return {"error": "the launcher is empty"}
    p = s.setdefault("params", {})
    p["prevCustom"] = p.get("custom", "")        # so Revert can step back one edit
    p["custom"] = text
    p.update(parse_launcher_params(text))
    try:
        os.makedirs(GEN_LAUNCHER_DIR, exist_ok=True)
        dest = os.path.join(GEN_LAUNCHER_DIR, re.sub(r"[^A-Za-z0-9._-]", "_", str(s.get("id"))) + ".ps1")
        with open(dest, "w", encoding="utf-8-sig", newline="\r\n") as f:
            f.write(text if text.endswith("\n") else text + "\n")
        s["script"] = dest
    except Exception as e:
        return {"error": "cannot write the launcher: %s" % e}
    save_config(cfg)
    sse_notify("state")
    return {"ok": True, "params": {k: v for k, v in p.items() if k not in ("custom", "prevCustom")}}

def api_slot_launcher_load(body):
    """Load an existing .ps1 from disk into a server."""
    cfg = load_config()
    s = _slot_by_id(cfg, body.get("slot"))
    if not s:
        return {"error": "unknown server"}
    path = str(body.get("path") or "").strip().strip('"')
    if not path:
        return {"error": "give the full path to a .ps1 launcher"}
    if not path.lower().endswith(".ps1"):
        return {"error": "that is not a .ps1 file"}
    if not os.path.isfile(path):
        return {"error": "no file at %s" % path}
    try:
        text = open(path, encoding="utf-8-sig").read()
    except Exception as e:
        return {"error": "cannot read that file: %s" % e}
    res = api_slot_launcher_save({"slot": s.get("id"), "content": text})
    if not (res or {}).get("error"):
        # the text is copied into generated-launchers, so without this the picked
        # file is forgotten and the picker can only show the generated copy
        cfg2 = load_config()
        s2 = _slot_by_id(cfg2, s.get("id"))
        if s2 is not None:
            s2["scriptSrc"] = path
            save_config(cfg2)
    return res

def api_slot_launcher_default(body):
    """Drop any hand-edited launcher and go back to one built from the parameters."""
    cfg = load_config()
    s = _slot_by_id(cfg, body.get("slot"))
    if not s:
        return {"error": "unknown server"}
    p = s.setdefault("params", {})
    p["prevCustom"] = p.get("custom", "")
    p["custom"] = ""
    r = regen_slot_script(cfg, s)
    save_config(cfg)
    sse_notify("state")
    if isinstance(r, dict) and r.get("error"):
        return r
    return {"ok": True}

def api_slot_launcher_revert(body):
    """Step back to the launcher that was in place before the last save or load."""
    cfg = load_config()
    s = _slot_by_id(cfg, body.get("slot"))
    if not s:
        return {"error": "unknown server"}
    p = s.setdefault("params", {})
    prev = p.get("prevCustom", "")
    if prev:
        return api_slot_launcher_save({"slot": s.get("id"), "content": prev})
    return api_slot_launcher_default({"slot": s.get("id")})

APP_REPO = "Pt0l3my/PandorumLLM"
_APP_UPD = {"t": 0.0, "res": None}
def _ver_tuple(tag):
    """v3.68-beta-patch4 -> (3, 68, 4); v3.67-beta-hotfix9 -> (3, 67, 9);
    v3.65-beta -> (3, 65, 0). Comparing the tags as text called an older release
    newer, because any difference at all counted as a difference."""
    t = str(tag or "").lower()
    m = re.search(r"v?([0-9]+)\.([0-9]+)", t)
    if not m:
        return None
    n = re.search(r"(?:patch|hotfix|hf|p)[ _-]*([0-9]+)", t)
    return (int(m.group(1)), int(m.group(2)), int(n.group(1)) if n else 0)

PEER = {"t": 0.0, "state": None, "err": "", "addr": "", "ver": ""}
_PEER_LOCK = threading.Lock()
def _peer_poll_once():
    """Read the other panel the way a browser would: its ordinary read-only remote
    view. Nothing new is exposed on either side. Runs on its own thread with a short
    timeout, because a client PC that is switched off must never slow this one down."""
    try:
        addr = str(((load_config().get("settings", {}) or {}).get("peerAddr") or "")).strip()
    except Exception:
        addr = ""
    if not addr:
        with _PEER_LOCK:
            PEER.update(state=None, err="", addr="", ver="")
        return
    url = addr if addr.startswith("http") else ("http://" + addr)
    try:
        rq = Request(url.rstrip("/") + "/api/state", headers={"User-Agent": "PandorumLLM"})
        data = json.loads(urlopen(rq, timeout=2.0).read().decode("utf-8"))
        with _PEER_LOCK:
            PEER.update(t=time.time(), state=data, err="", addr=addr,
                        ver=str(data.get("version") or ""))
    except Exception as e:
        with _PEER_LOCK:
            PEER.update(err=str(e)[:140], addr=addr)

def _peer_loop():
    while True:
        try:
            _peer_poll_once()
        except Exception:
            pass
        time.sleep(5)

def api_peer(body=None):
    with _PEER_LOCK:
        pr = dict(PEER)
    age = (time.time() - pr["t"]) if pr["t"] else None
    return {"addr": pr.get("addr", ""), "err": pr.get("err", ""),
            "age": round(age, 1) if age is not None else None,
            "fresh": bool(pr.get("state")) and age is not None and age < 20,
            "version": pr.get("ver", ""), "mine": APP_VER_UI,
            "state": pr.get("state")}

def api_app_update(body=None):
    """Ask GitHub for the newest PandorumLLM release tag.

    Outbound, and the second such call in the panel. Nothing about the setup is sent -
    it is a plain GET of a public release page. Answered from a 6 hour cache so opening
    the panel repeatedly does not repeat the request. See SAFETY & TRUST.
    """
    now = time.time()
    if _APP_UPD["res"] is not None and now - _APP_UPD["t"] < 21600:
        return dict(_APP_UPD["res"], cached=True)
    out = {"tag": "", "current": APP_RELEASE_TAG, "state": "unknown", "url": "https://github.com/%s/releases" % APP_REPO}
    try:
        rq = Request("https://api.github.com/repos/%s/releases/latest" % APP_REPO,
                     headers={"User-Agent": "PandorumLLM", "Accept": "application/vnd.github+json"})
        data = json.loads(urlopen(rq, timeout=10).read().decode("utf-8"))
        tag = str(data.get("tag_name") or "").strip()
        if tag:
            out["tag"] = tag
            out["url"] = str(data.get("html_url") or out["url"])
            mine, theirs = _ver_tuple(APP_RELEASE_TAG), _ver_tuple(tag)
            if mine and theirs:
                out["state"] = "behind" if theirs > mine else ("current" if theirs == mine else "ahead")
            else:
                out["state"] = "current" if tag.lower() == APP_RELEASE_TAG.lower() else "unknown"
    except Exception as e:
        out["note"] = str(e)[:120]
    _APP_UPD.update(t=now, res=dict(out))
    return out

def api_llama_update(body):
    """Ask GitHub for the newest llama.cpp release tag.

    This is the only outbound request PandorumLLM makes, it happens only when the
    button is pressed, and nothing about your setup is sent - see SAFETY & TRUST.
    """
    try:
        rq = Request("https://api.github.com/repos/ggml-org/llama.cpp/releases/latest",
                     headers={"User-Agent": "PandorumLLM", "Accept": "application/vnd.github+json"})
        data = json.loads(urlopen(rq, timeout=10).read().decode("utf-8"))
    except HTTPError as e:
        if e.code == 403:
            return {"error": "github.com refused the request (rate limit) - try again in a few minutes"}
        return {"error": "github.com returned HTTP %s" % e.code}
    except Exception as e:
        return {"error": "could not reach github.com (%s)" % e}
    tag = str(data.get("tag_name") or "").strip()
    if not tag:
        return {"error": "GitHub did not return a release tag"}
    local = ""
    try:
        exe = llama_exe(load_config())
        if os.path.isfile(exe):
            r = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=20,
                               **NOWIN,
                               cwd=os.path.dirname(exe) or None)
            out = (r.stdout or "") + (r.stderr or "")
            for pat in (r"version:\s*(\d+)",          # what llama.cpp prints today
                        r"build\s*[:=]?\s*(\d+)",     # older builds
                        r"\bb(\d{3,})\b"):            # a release tag, if it echoes one
                m = re.search(pat, out)
                if m:
                    local = m.group(1)
                    break
    except Exception:
        pass
    newest = re.sub(r"[^0-9]", "", tag)
    known = bool(local) and bool(newest)
    return {"ok": True, "latest": tag, "local": local,
            "upToDate": (known and int(local) >= int(newest)), "known": known}

def api_slot_launcher(body):
    """Return the launcher a server would run right now, compiled from its parameters."""
    cfg = load_config()
    sid = str(body.get("slot") or "")
    s = next((x for x in cfg.get("slots", []) if x.get("id") == sid), None)
    if not s:
        return {"error": "unknown server"}
    p = s.get("params") or {}
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", str(s.get("id") or "slot"))
    dest = os.path.join(GEN_LAUNCHER_DIR, safe + ".ps1")
    custom = (p.get("custom") or "").strip()
    if custom:
        return {"ok": True, "path": dest, "src": s.get("scriptSrc", ""), "custom": True, "content": custom}
    waiting = not (p.get("model") or "").strip()
    if waiting:
        # nothing is saved and nothing is launched from this: it is the launcher this
        # server will have, shown with the one thing still missing marked as such
        preview = dict(s)
        preview["params"] = dict(p, model="<no model chosen yet>")
        return {"ok": True, "path": dest, "src": s.get("scriptSrc", ""), "custom": False, "waiting": True,
                "content": build_param_launcher(cfg, preview, dest)}
    return {"ok": True, "path": dest, "src": s.get("scriptSrc", ""), "custom": False,
            "content": build_param_launcher(cfg, s, dest)}

def api_creator_save(body, create=False):
    cfg = load_config()
    tpls = cfg.setdefault("creatorSlots", [])
    t = next((x for x in tpls if x.get("id") == body.get("id")), None)
    if not t:
        return {"error": "unknown template"}
    _llexe = llama_exe(cfg)
    for k in ("title", "content", "model", "vision", "draft", "gpu", "template", "port"):
        if k in body:
            t[k] = str(body[k])
    t["title"] = (t.get("title") or "").strip()[:80] or t["id"]
    save_config(cfg)
    if not create:
        return {"ok": True}
    if not t.get("model") or not os.path.isfile(t["model"]):
        return {"error": "model path is mandatory - pick a model file"}
    name = re.sub(r"[^A-Za-z0-9._ -]", "_", t["title"]).strip().replace(" ", "-") or t["id"]
    outd = cfg.get("settings", {}).get("outputDir") or DEF_SETTINGS["outputDir"]
    os.makedirs(outd, exist_ok=True)
    dest = os.path.join(outd, name + ".ps1")
    if not _within(dest, [outd]):
        return {"error": "refusing to write outside the output folder"}
    if os.path.exists(dest):
        return {"error": "file already exists: " + dest + " (rename the template)"}
    out_lines = render_launcher_lines(t, dest, _llexe)
    with open(dest, "w", encoding="utf-8-sig", newline="\r\n") as f:
        f.write("\n".join(out_lines) + "\n")
    panel_log("[panel] created launcher %s" % dest)
    return {"ok": True, "path": dest}

def api_creator_add(body):
    cfg = load_config()
    tpls = cfg.setdefault("creatorSlots", [])
    if len(tpls) >= MAX_TPL:
        return {"error": "max %d templates" % MAX_TPL}
    used = {t.get("id") for t in tpls}
    n = 1
    while "tpl%d" % n in used:
        n += 1
    tpls.append({"id": "tpl%d" % n, "title": "my launcher %d" % n,
                 "content": read_template(cfg.get("settings", {})),
                 "model": "", "vision": "N/A", "draft": "N/A"})
    save_config(cfg)
    return {"ok": True}

def api_creator_remove(body):
    cfg = load_config()
    tpls = cfg.get("creatorSlots", [])
    if len(tpls) <= 1:
        return {"error": "at least 1 template is required"}
    keep = [t for t in tpls if t.get("id") != body.get("id")]
    if len(keep) == len(tpls):
        return {"error": "unknown template"}
    cfg["creatorSlots"] = keep
    save_config(cfg)
    return {"ok": True}

def tts_launcher_text(cfg=None):
    """Build the TTS launcher .bat from settings.

    Modelled line-for-line on the reference launcher that is known to work. Every
    comment below marks something that has already cost debugging time; none of it
    is decoration. Written as .bat, not .ps1, because this file is started by hand
    and a double-clicked .ps1 opens in an editor instead of running.
    """
    cfg = cfg or load_config()
    st = cfg.get("settings", {})
    # When the panel is the wrapper it already holds the wrapper port, so a launcher
    # that starts one too would collide. Server half only in that mode.
    panel_wraps = str(st.get("ttsWrapMode", "off")).lower() == "on"
    gid = st.get("ttsGpuId") or ""
    gpu = next((g for g in cfg.get("gpus", []) if g.get("id") == gid), None)
    uuid = (gpu or {}).get("uuid") or ""
    gname = (gpu or {}).get("name") or ""
    ld = log_dir(cfg)

    if uuid:
        mask = ('REM Isolate to one card by UUID, so a reboot or a reseated card cannot\n'
                'REM change which GPU this lands on. Child windows started with START inherit it.\n'
                'REM NOTE: after masking, the chosen card re-indexes to device 0 in-process, so the\n'
                'REM server flag below is --main-gpu 0 (NOT its physical index). Easy to get wrong.\n'
                'set CUDA_VISIBLE_DEVICES=' + uuid + '\n')
    else:
        mask = ('REM No GPU pinned in the panel, so every visible card is offered to the server.\n'
                'REM Pick one under Proxy then TTS to pin it by UUID.\n')

    L = []
    a = L.append
    a('@echo off')
    a('REM ' + APP_NAME + ' ' + APP_VER_UI + ' (build ' + str(BUILD_ID.get("sha", "?"))
      + ') - generated TTS launcher. Regenerating overwrites this file.')
    if panel_wraps:
        a('REM Starts the TTS server only - the panel is answering SkyrimNet itself, so')
        a('REM there is no wrapper to start here and nothing to mirror into a log.')
    else:
        a('REM Starts the TTS server, waits for it to answer, then starts the wrapper')
        a('REM and mirrors the wrapper output into a log the panel can render.')
    if gname:
        a('REM Card: ' + gname)
    a('')
    a('set SERVER=' + (st.get("ttsServerExe") or ""))
    a('set MODEL=' + (st.get("ttsModel") or ""))
    if not panel_wraps:
        a('set WRAPPER=' + (st.get("ttsWrapper") or ""))
        a('set PYTHON=' + (st.get("ttsPython") or ""))
    a('set PORT=' + (str(st.get("ttsServerPort") or "1240")))
    a('set WPORT=' + (str(st.get("ttsWrapperPort") or "7860")))
    a('')
    a('REM The log MUST sit in the panel log folder: the panel opens logs by name,')
    a('REM joined to that folder, never by an arbitrary path.')
    a('set LOGDIR=' + ld)
    a('set LOG=%LOGDIR%\\' + TTS_LOG_NAME)
    a('')
    for line in mask.rstrip('\n').split('\n'):
        a(line)
    a('')
    a('REM Fail loudly and stay open, rather than flashing a window and vanishing.')
    a('if not exist "%SERVER%"  ( echo [X] server not found: %SERVER%   & pause & exit /b 1 )')
    a('if not exist "%MODEL%"   ( echo [X] model not found: %MODEL%     & pause & exit /b 1 )')
    if not panel_wraps:
        a('if not exist "%WRAPPER%" ( echo [X] wrapper not found: %WRAPPER% & pause & exit /b 1 )')
        a('if not exist "%PYTHON%"  ( echo [X] python not found: %PYTHON%   & pause & exit /b 1 )')
    a('if not exist "%LOGDIR%"  ( echo [X] log folder not found: %LOGDIR% & pause & exit /b 1 )')
    a('')
    a('REM PowerShell 7 when present, Windows PowerShell otherwise. 7 writes UTF-8 without')
    a('REM a BOM and 5.1 with one; the panel reads either.')
    a('where pwsh >nul 2>&1 && (set PS=pwsh) || (set PS=powershell)')
    a('')
    a('echo Starting TTS server on port %PORT% ...')
    a('start "TTS Server (%PORT%)" cmd /k ""%SERVER%" --model "%MODEL%" --main-gpu 0 --host 0.0.0.0 --port %PORT% --no-webui"')
    a('')
    a('echo Waiting for the server to answer /health ...')
    a('set /a TRIES=0')
    a(':waitloop')
    a('set /a TRIES+=1')
    a('for /f %%C in (\'curl -s -o nul -w "%%{http_code}" http://localhost:%PORT%/health 2^>nul\') do set CODE=%%C')
    a('if "%CODE%"=="200" goto ready')
    a('if %TRIES% geq 90 ( echo [X] server did not answer within ~180s. & pause & exit /b 1 )')
    a('timeout /t 2 /nobreak >nul')
    a('goto waitloop')
    a('')
    a(':ready')
    a('echo Server ready.')
    a('')
    if panel_wraps:
        a('echo The panel is answering SkyrimNet on port %WPORT% itself, so no wrapper is')
        a('echo started here. Point the SkyrimNet TTS endpoint at this machine on %WPORT%.')
        a('echo Leave this window open: closing it stops the TTS server.')
        a('echo.')
        a('echo Server : http://localhost:%PORT%')
        a('timeout /t 5 /nobreak >nul')
        return '\r\n'.join(L) + '\r\n'
    a('')
    a('REM Start each run on a fresh log, so the panel is not showing yesterday lines.')
    a('del /q "%LOG%" >nul 2>&1')
    a('')
    a('REM The wrapper reads MOSS_TTS_URL from the environment and otherwise falls back')
    a('REM to a hardcoded 127.0.0.1:1240 - without this line, changing the server port')
    a('REM above moves the server while the wrapper keeps calling the old one.')
    a('set MOSS_TTS_URL=http://127.0.0.1:%PORT%/tts')
    a('REM Honoured only if the wrapper reads it; the reference wrapper hardcodes 7860.')
    a('set WRAP_PORT=%WPORT%')
    a('')
    a('echo Starting wrapper on port %WPORT%, logging to %LOG% ...')
    a('REM  -X utf8  : into a pipe Python falls back to the locale code page, which cannot')
    a('REM             encode the wrapper emoji - it crashes on the first print. This forces')
    a('REM             UTF-8; OutputEncoding below makes PowerShell decode it back.')
    a('REM  -u       : Python line-buffers to a console but block-buffers to a pipe. Without')
    a('REM             this the log sits empty and then arrives in 8KB lumps.')
    a('REM  2>&1     : keep errors in the same stream so a failure reaches the log too.')
    a('REM  The pipe inside -Command needs NO caret: cmd leaves | alone inside double quotes,')
    a('REM  and a caret there would reach PowerShell as a stray token.')
    a('REM  ForEach  : print the line to this window untouched, then write a copy with the')
    a('REM             ANSI colour codes stripped for the panel to read.')
    a('start "TTS Wrapper (%WPORT%)" %PS% -NoExit -NoProfile -Command "[Console]::OutputEncoding=[Text.Encoding]::UTF8; $e=[char]27; & \'%PYTHON%\' -X utf8 -u \'%WRAPPER%\' 2>&1 | ForEach-Object { $_; ($_ -replace ($e + \'\\[[0-9;]*m\'), \'\') | Out-File -FilePath \'%LOG%\' -Append -Encoding utf8 }"')
    a('')
    a('echo.')
    a('echo Server : http://localhost:%PORT%')
    a('echo Wrapper: http://localhost:%WPORT%   - point the SkyrimNet TTS endpoint here')
    a('echo Log    : %LOG%')
    a('echo Open it in the panel under Proxy then TTS Terminal.')
    a('timeout /t 5 /nobreak >nul')
    return '\r\n'.join(L) + '\r\n'


def api_tts_launcher(body):
    cfg = load_config()
    st = cfg.get("settings", {})
    missing = [lab for key, lab in (("ttsServerExe", "server binary"), ("ttsModel", "model"),
                                    ("ttsPython", "python"), ("ttsWrapper", "wrapper"))
               if not (st.get(key) or "").strip()]
    text = tts_launcher_text(cfg)
    if not body.get("save"):
        return {"content": text, "missing": missing}
    # launcherDir wins. It is the field the user edits in Folder Settings; outputDir is
    # SEEDED with a default and only overwritten when launcherDir is saved, so a config
    # where launcherDir was never saved leaves the two disagreeing and the file lands in
    # a folder the user was never shown.
    #
    # Deliberately NOT gated with _within(_all_roots()): _all_roots() is built FROM
    # outputDir, so that test would contain the folder it is testing and could never
    # fail - a containment check that enforces nothing. What keeps this endpoint safe is
    # reachability: it is absent from REMOTE_POST_OK, so a remote caller is refused by
    # the dispatcher, and the host choosing where its own launcher lands is the feature.
    outd = os.path.abspath(st.get("launcherDir") or st.get("outputDir") or "")
    if not (st.get("launcherDir") or st.get("outputDir")):
        return {"error": "set the PS1 Launcher Folder under Folder Settings first - the launcher is written there"}
    if not os.path.isdir(outd):
        return {"error": "launcher folder does not exist: %s" % outd}
    path = os.path.join(outd, "start-tts.bat")
    try:
        with open(path, "wb") as f:          # .bat: no BOM, CRLF (see the encoding table)
            f.write(text.encode("utf-8"))
    except Exception as e:
        return {"error": str(e)}
    panel_log("[panel] TTS launcher written: %s" % path)
    return {"content": text, "path": path, "missing": missing}


def api_tts_import(body):
    """Read a launcher (.bat/.cmd/.ps1) and pull the TTS paths out of it.

    Classifies by extension, not by variable name, so it works whichever names the
    author used. Returns ONLY the fields it recognised - never the file contents - so
    pointing it at the wrong file leaks nothing. Host-only.
    """
    path = os.path.abspath(str(body.get("path", "") or "").strip())
    if not os.path.isfile(path):
        return {"error": "no such file: %s" % path}
    if os.path.splitext(path)[1].lower() not in (".bat", ".cmd", ".ps1"):
        return {"error": "expected a .bat, .cmd or .ps1 launcher"}
    try:
        txt = open(path, encoding="utf-8-sig", errors="replace").read()
    except Exception as e:
        return {"error": str(e)}

    assigns = []
    for m in re.finditer(r"(?im)^\s*set\s+([A-Za-z_]\w*)\s*=\s*(.+?)\s*$", txt):
        assigns.append((m.group(1).upper(), m.group(2).strip().strip('"')))
    for m in re.finditer("(?im)^\\s*\\$([A-Za-z_]\\w*)\\s*=\\s*[\"']([^\"']+)", txt):
        assigns.append((m.group(1).upper(), m.group(2).strip()))

    out = {}
    for name, val in assigns:
        if not val or "%" in val or "$" in val:
            continue
        ext = os.path.splitext(val)[1].lower()
        # split on BOTH separators: os.path.basename does not treat "\\" as one off
        # Windows, so this classifier would silently mis-file every path elsewhere
        low = re.split(r"[\\/]", val)[-1].lower()
        if ext == ".gguf":
            out.setdefault("ttsModel", val)
        elif low.startswith("python") and ext == ".exe":
            out.setdefault("ttsPython", val)
        elif ext == ".py":
            out.setdefault("ttsWrapper", val)
        elif ext == ".exe":
            out.setdefault("ttsServerExe", val)
        elif val.isdigit() and 1000 <= int(val) <= 65535 and "PORT" in name:
            key = "ttsWrapperPort" if ("WRAP" in name or "GRADIO" in name) else "ttsServerPort"
            out.setdefault(key, val)

    if "ttsWrapperPort" not in out:
        m = re.search(r"(?:wrapper|gradio)[^\n]*?localhost:(\d{4,5})", txt, re.I) \
            or re.search(r"localhost:(\d{4,5})[^\n]*(?:wrapper|gradio|skyrimnet)", txt, re.I)
        if m:
            out["ttsWrapperPort"] = m.group(1)

    if not out:
        return {"error": "nothing recognisable in that file - expected set NAME=path lines"}
    cfg = load_config()
    st = cfg.setdefault("settings", {})
    for k, v in out.items():
        st[k] = v
    save_config(cfg)
    return {"found": out, "path": path}


# ---------------------------------------------------------------- embedded TTS wrapper
# The panel speaks the Gradio client protocol SkyrimNet's Zonos engine uses and
# translates it to moss-tts-server's plain JSON, so no separate wrapper process is
# needed. OFF by default: while it is on, voices depend on the panel running.
#
# Protocol (DEVELOPMENT.md section 13, confirmed against a real SkyrimNet log):
#   POST /gradio_api/upload                      -> ["<abs path>"]
#   HEAD /gradio_api/file=<abs path>             -> 200/404
#   POST /gradio_api/call/generate_audio         -> {"event_id": "<32 hex>"}
#   GET  /gradio_api/call/generate_audio/<id>    -> SSE complete|error
#   GET  /gradio_api/file=<abs path>             -> the WAV bytes
import array, base64, io, tempfile, uuid, wave as _wave
from urllib.parse import unquote

TTS_CHUNK_CHARS = 170        # chunk cap; longer utterances drift
TTS_CHUNK_GAP_MS = 100       # silence stitched between chunks
TTS_MAX_WORKERS = 4
TTS_MAX_NEW_TOKENS = 2048
TTS_RESULT_WAIT_S = 120.0


# Higgs Audio v3 inline control tags.
#
# The rules below are not guesses - they come from Boson's model card and from
# cleanestpoison/higgs3-tts-skyrimnet (Apache-2.0), whose wrapper measured the
# behaviour against a live engine. Three of them are non-obvious and each one
# silently ruins the feature if missed:
#
#   * SkyrimNet strips < | > from every line, so the native <|family:value|>
#     shape can never arrive. The dialogue model writes [EMOTION-FEAR] instead.
#   * emotion, style and the speed/pitch prosody tags are SENTENCE-LEVEL: they
#     colour a whole sentence and must sit at its start. Written mid-line they
#     are moved to the front of their sentence.
#   * sound effects are INLINE and must be followed immediately by onomatopoeia
#     with no space. A bare <|sfx:laughter|> does nothing at all, so the word is
#     injected here using the spellings the model was trained on.
#
# And one measured failure worth engineering against: <|prosody:long_pause|> at
# the very start or end of the engine input makes the decoder run to its token
# cap without ever emitting an end-of-clip, which audio.cpp answers with an
# error and no audio - repeated hits have been seen to take the engine down. A
# pause at a line edge means nothing anyway, so it is dropped.
TTS_TAGS = {
    "emotion": ("affection", "amusement", "anger", "arousal", "awe", "bitterness",
                "confusion", "contemplation", "contentment", "determination", "disgust",
                "elation", "enthusiasm", "fear", "helplessness", "longing", "pride",
                "relief", "sadness", "shame", "surprise"),
    "prosody": ("speed_very_slow", "speed_slow", "speed_fast", "speed_very_fast",
                "pitch_low", "pitch_high", "expressive_high", "expressive_low",
                "pause", "long_pause"),
    "style": ("singing", "shouting", "whispering"),
    "sfx": ("cough", "laughter", "crying", "screaming", "burping", "humming",
            "sigh", "sniff", "sneeze"),
}
# The model card's own spellings. A sound effect without one is inert.
TTS_ONOMATOPOEIA = {
    "cough": "Ahem", "laughter": "Hehe", "crying": "Sob", "screaming": "Aaah",
    "burping": "Burp", "humming": "Hmm", "sigh": "Ahh", "sniff": "Sff",
    "sneeze": "Achoo",
}
TTS_INLINE = {"prosody": {"pause", "long_pause"}, "sfx": set(TTS_TAGS["sfx"])}
TTS_ORDER = {"emotion": 0, "prosody": 1, "style": 2}

# Uppercase only, and the separator may be anything the mod left behind, so
# EMOTION-FEAR, EMOTION_FEAR, EMOTION FEAR and EMOTIONFEAR all land the same
# way. Caps matter: "emotion" and "style" are ordinary English words.
TTS_CAPS_RX = re.compile(
    r"\[?\s*(?<![A-Za-z0-9])(EMOTION|PROSODY|STYLE|SFX)((?:[ \t\-_]*[A-Z]+){1,3})(?![A-Za-z])\s*\]?")
TTS_TAG_ANY_RX = re.compile(r"<\|[^|>]{0,40}\|>")

# SkyrimNet's own tag vocabularies, mapped onto Higgs' where an equivalent exists.
# Two of them: the fixed list its Chatterbox branch teaches, and the looser set its
# other branch suggests ([sad], [whispers], [sighs], [pause]...). Accepting both costs
# nothing - they are lowercase single words, while Higgs' are uppercase FAMILY-VALUE,
# so nothing is ambiguous - and it means the stock prompt works without editing.
# Only clear equivalents are mapped. [advertisement], [narration], [shush], [groan]
# and [gasp] have no Higgs counterpart and are dropped rather than guessed at.
TTS_ALIAS = {
    "angry": ("emotion", "anger"), "anger": ("emotion", "anger"),
    "fear": ("emotion", "fear"), "afraid": ("emotion", "fear"),
    "surprised": ("emotion", "surprise"), "surprise": ("emotion", "surprise"),
    "happy": ("emotion", "elation"), "excited": ("emotion", "enthusiasm"),
    "sad": ("emotion", "sadness"), "disgusted": ("emotion", "disgust"),
    "proud": ("emotion", "pride"), "confused": ("emotion", "confusion"),
    "whispering": ("style", "whispering"), "whispers": ("style", "whispering"),
    "whisper": ("style", "whispering"),
    "shouting": ("style", "shouting"), "shouts": ("style", "shouting"),
    "shout": ("style", "shouting"), "singing": ("style", "singing"),
    "sings": ("style", "singing"),
    "laugh": ("sfx", "laughter"), "laughs": ("sfx", "laughter"),
    "laughter": ("sfx", "laughter"), "chuckle": ("sfx", "laughter"),
    "chuckles": ("sfx", "laughter"),
    "sigh": ("sfx", "sigh"), "sighs": ("sfx", "sigh"),
    "cough": ("sfx", "cough"), "coughs": ("sfx", "cough"),
    "clear throat": ("sfx", "cough"), "clears throat": ("sfx", "cough"),
    "crying": ("sfx", "crying"), "cries": ("sfx", "crying"),
    "sob": ("sfx", "crying"), "sobs": ("sfx", "crying"),
    "sniff": ("sfx", "sniff"), "sniffs": ("sfx", "sniff"),
    "sneeze": ("sfx", "sneeze"), "sneezes": ("sfx", "sneeze"),
    "screaming": ("sfx", "screaming"), "screams": ("sfx", "screaming"),
    "humming": ("sfx", "humming"), "hums": ("sfx", "humming"),
    "burp": ("sfx", "burping"), "burps": ("sfx", "burping"),
    "slowly": ("prosody", "speed_slow"), "quickly": ("prosody", "speed_fast"),
    "pause": ("prosody", "pause"), "long pause": ("prosody", "long_pause"),
    "dramatic": ("prosody", "expressive_high"),
    "dramatic tone": ("prosody", "expressive_high"),
    "monotone": ("prosody", "expressive_low"),
}
TTS_ALIAS_RX = re.compile(r"\[\s*([a-z][a-z ]{0,18})\s*\]")
# SkyrimNet tags with no Higgs counterpart. These are DELETED; anything else in square
# brackets is left alone, because a line may legitimately contain [something] and eating
# it loses meaning, while speaking one stray tag aloud does not.
TTS_ALIAS_DROP = frozenset((
    "advertisement", "narration", "shush", "groan", "gasp", "sarcastic",
    "clears throat" if False else "", "grunt", "grunts", "yawn", "yawns",
))
TTS_SENT_RX = re.compile(r"(?<=[.!?])\s+")
TTS_PAUSE_RX = re.compile(r"\[\s*pause\s+([0-9]+(?:\.[0-9]+)?)\s*s\s*\]", re.I)
TTS_PAUSE_ANY_RX = re.compile(r"\[\s*pause\b[^\]]{0,20}\]", re.I)
TTS_PAUSE_MAX_S = 10.0
_TTS_SQUASH = lambda v: re.sub(r"[^a-z0-9]", "", v.lower())
TTS_LOOKUP = {c: {_TTS_SQUASH(v): v for v in vals} for c, vals in TTS_TAGS.items()}
TTS_EDGE_PAUSE_RX = re.compile(
    r"[ \t]*(?:" + "|".join(re.escape("<|prosody:%s|>" % v)
                            for v in ("pause", "long_pause")) + r")[ \t]*")


def _tts_spoken(part):
    """Is there anything here the model would actually say?"""
    return any(ch.isalnum() for ch in TTS_TAG_ANY_RX.sub("", part))


def _tts_drop_edge_pauses(line):
    """Remove pause tokens with no speech on one side - see the note above."""
    def keep(m):
        if _tts_spoken(line[:m.start()]) and _tts_spoken(line[m.end():]):
            return m.group(0)
        return ""
    return TTS_EDGE_PAUSE_RX.sub(keep, line)


def _tts_sentence(sentence):
    """One sentence -> (text with inline tokens in place, sentence-level tags)."""
    out, level, pos = [], [], 0
    while True:
        m = TTS_CAPS_RX.search(sentence, pos)
        if m is None:
            break
        fam = m.group(1).lower()
        words = list(re.finditer(r"[A-Z]+", m.group(2)))
        value, end = None, m.end()
        for n in range(len(words), 0, -1):      # longest value wins
            key = _TTS_SQUASH("".join(w.group(0) for w in words[:n]))
            if key in TTS_LOOKUP[fam]:
                value, end = TTS_LOOKUP[fam][key], m.start(2) + words[n - 1].end()
                if sentence[end:end + 1] == "]":
                    end += 1                     # the bracket leaves with the tag
                break
        out.append(sentence[pos:m.start()])
        if value is None:
            pass                                 # unknown: dropped, never spoken
        elif fam == "sfx":
            word = TTS_ONOMATOPOEIA[value]
            rest = sentence[end:].lstrip()
            if rest[:len(word)].lower() == word.lower():
                out.append("<|sfx:%s|>" % value)         # it wrote its own
                end += len(sentence[end:]) - len(rest)
            else:
                piece = "<|sfx:%s|>%s" % (value, word)
                if rest and rest[0] not in ".,!?;:":
                    piece += ","
                out.append(piece)
        elif value in TTS_INLINE.get(fam, ()):
            out.append("<|%s:%s|>" % (fam, value))
        else:
            level.append((fam, value))           # colours the whole sentence
        pos = end
    out.append(sentence[pos:])
    return "".join(out), level


def _tts_render(tags):
    """One tag per competing group, in the model card's stacking order."""
    kept = {}
    for fam, value in tags:
        group = (fam, value.split("_")[0] if fam == "prosody" else "")
        kept.setdefault(group, (fam, value))
    ordered = sorted(kept.values(), key=lambda x: (TTS_ORDER.get(x[0], 9), x[1]))
    return "".join("<|%s:%s|>" % (f, v) for f, v in ordered)


def tts_apply_tags(text, keep, engine="audiocpp"):
    """Turn the mod's ALL-CAPS tags into Higgs control tokens, or remove them.

    MOSS understands one marker of its own, [pause 3.2s], and none of Higgs'.
    """
    text = str(text or "")
    higgs = keep and engine == "audiocpp"
    moss = keep and engine != "audiocpp"

    def pause(m):
        if not moss:
            return ""
        mm = TTS_PAUSE_RX.fullmatch(m.group(0))
        if not mm:
            return ""
        try:
            return "[pause %gs]" % min(max(float(mm.group(1)), 0.1), TTS_PAUSE_MAX_S)
        except Exception:
            return ""

    def alias(m):
        """SkyrimNet's own [angry] / [sigh] style, where Higgs has an equivalent.

        Unrecognised brackets are RETURNED UNCHANGED: dialogue can legitimately contain
        [something], and deleting it loses meaning. Only tags known to have no Higgs
        counterpart are removed.
        """
        word = " ".join(m.group(1).split()).lower()
        hit = TTS_ALIAS.get(word)
        if hit and higgs:
            return "[%s-%s]" % (hit[0].upper(), hit[1].upper())
        if hit or word in TTS_ALIAS_DROP:
            return ""              # a recognised tag we are not passing on: never spoken
        return m.group(0)          # anything else is dialogue, not markup

    # BEFORE the MOSS pause handling: that matcher takes [pause + anything, so it would
    # otherwise swallow a bare [pause] and delete it on the Higgs path. Runs whether or
    # not tags are on, because an unpassed tag must not be read aloud either.
    text = TTS_ALIAS_RX.sub(alias, text)
    text = TTS_PAUSE_ANY_RX.sub(pause, text)
    if not higgs:
        text = TTS_CAPS_RX.sub("", text)
        text = TTS_TAG_ANY_RX.sub("", text)
        return re.sub(r"\s{2,}", " ", text).strip()

    lines = []
    for line in text.split("\n"):
        carried, done = [], []
        for sentence in TTS_SENT_RX.split(line):
            body, level = _tts_sentence(sentence)
            body = body.strip()
            tags = carried + level
            if not body:
                carried = tags          # nothing to colour; hand them onward
                continue
            carried = []
            done.append(_tts_render(tags) + body)
        if carried and done:
            done[-1] = _tts_render(carried) + done[-1]
        lines.append(_tts_drop_edge_pauses(" ".join(done)))
    text = "\n".join(lines)
    text = TTS_TAG_ANY_RX.sub(
        lambda m: m.group(0) if re.fullmatch(
            r"<\|(emotion|prosody|style|sfx):[a-z_]+\|>", m.group(0)) else "", text)
    text = re.sub(r"\s+-\s+-\s+", " - ", text)   # a removed tag can leave " - - "
    text = re.sub(r"\s{2,}", " ", text).strip()
    # tts_normalize punctuated the line, but a tag can land after that full stop -
    # an sfx at the end brings its onomatopoeia with it and leaves the SPOKEN text
    # unpunctuated again, which is how a model is invited to keep talking.
    spoken = TTS_TAG_ANY_RX.sub("", text).strip()
    if spoken and spoken[-1] not in ".!?,;\"'":
        text += "."
    return text


# How each tag reads in the terminal. The point of the line is to answer one question
# at a glance - did the tag survive SkyrimNet and reach the engine - and *sniffs* says
# that faster than [SFX-SNIFF] does. Stage directions, not identifiers.
TTS_TAG_WORDS = {
    ("emotion", "affection"): "affectionate", ("emotion", "amusement"): "amused",
    ("emotion", "anger"): "angry", ("emotion", "arousal"): "aroused",
    ("emotion", "awe"): "awed", ("emotion", "bitterness"): "bitter",
    ("emotion", "confusion"): "confused", ("emotion", "contemplation"): "thoughtful",
    ("emotion", "contentment"): "content", ("emotion", "determination"): "determined",
    ("emotion", "disgust"): "disgusted", ("emotion", "elation"): "elated",
    ("emotion", "enthusiasm"): "enthusiastic", ("emotion", "fear"): "afraid",
    ("emotion", "helplessness"): "helpless", ("emotion", "longing"): "longing",
    ("emotion", "pride"): "proud", ("emotion", "relief"): "relieved",
    ("emotion", "sadness"): "sad", ("emotion", "shame"): "ashamed",
    ("emotion", "surprise"): "surprised",
    ("style", "whispering"): "whispering", ("style", "shouting"): "shouting",
    ("style", "singing"): "singing",
    ("prosody", "speed_very_slow"): "very slowly", ("prosody", "speed_slow"): "slowly",
    ("prosody", "speed_fast"): "quickly", ("prosody", "speed_very_fast"): "very quickly",
    ("prosody", "pitch_low"): "low", ("prosody", "pitch_high"): "high",
    ("prosody", "expressive_low"): "flat", ("prosody", "expressive_high"): "animated",
    ("prosody", "pause"): "pause", ("prosody", "long_pause"): "long pause",
    ("sfx", "cough"): "coughs", ("sfx", "laughter"): "laughs",
    ("sfx", "crying"): "cries", ("sfx", "screaming"): "screams",
    ("sfx", "burping"): "burps", ("sfx", "humming"): "hums",
    ("sfx", "sigh"): "sighs", ("sfx", "sniff"): "sniffs",
    ("sfx", "sneeze"): "sneezes",
}


# The line already says how it should be delivered, so show that rather than one mask
# for everything. Emotion wins over style, style over a sound effect - the emotion
# colours the whole sentence while a sound is one moment in it.
TTS_MOOD = {
    ("emotion", "anger"): "\U0001F620", ("emotion", "fear"): "\U0001F628",
    ("emotion", "sadness"): "\U0001F622", ("emotion", "elation"): "\U0001F604",
    ("emotion", "amusement"): "\U0001F60F", ("emotion", "surprise"): "\U0001F632",
    ("emotion", "disgust"): "\U0001F922", ("emotion", "affection"): "\U0001F60D",
    ("emotion", "pride"): "\U0001F60C", ("emotion", "contemplation"): "\U0001F914",
    ("emotion", "confusion"): "\U0001F615", ("emotion", "relief"): "\U0001F605",
    ("emotion", "shame"): "\U0001F633", ("emotion", "determination"): "\U0001F624",
    ("emotion", "enthusiasm"): "\U0001F929", ("emotion", "awe"): "\U0001F62E",
    ("emotion", "bitterness"): "\U0001F612", ("emotion", "helplessness"): "\U0001F629",
    ("emotion", "longing"): "\U0001F97A", ("emotion", "contentment"): "\U0001F60A",
    ("emotion", "arousal"): "\U0001F975",
    ("style", "whispering"): "\U0001F92B", ("style", "shouting"): "\U0001F4E3",
    ("style", "singing"): "\U0001F3B5",
    ("sfx", "laughter"): "\U0001F602", ("sfx", "sigh"): "\U0001F614",
    ("sfx", "cough"): "\U0001F637", ("sfx", "crying"): "\U0001F62D",
    ("sfx", "screaming"): "\U0001F631", ("sfx", "sniff"): "\U0001F927",
    ("sfx", "sneeze"): "\U0001F927", ("sfx", "humming"): "\U0001F3B6",
    ("sfx", "burping"): "\U0001F62C",
}
TTS_MOOD_PLAIN = "\U0001F5E3\uFE0F"    # a speaking head - the variation selector
                                       # forces emoji width, or it renders narrow
# The one pattern for a rendered control token. Defined here because this block sits
# above the tag catalogue; tts_tags_display had an identical copy inline.
TTS_TOKEN_RX = re.compile(r"<\|([a-z]+):([a-z_]+)\|>")


def tts_mood_icon(text):
    """An icon for how the line is meant to sound, from the tags it carries."""
    found = TTS_TOKEN_RX.findall(str(text or ""))
    for want in ("emotion", "style", "sfx"):
        for fam, val in found:
            if fam.lower() == want:
                hit = TTS_MOOD.get((fam.lower(), val.lower()))
                if hit:
                    return hit
    return TTS_MOOD_PLAIN


def tts_tags_display(text):
    """Rewrite Higgs control tokens as stage directions: <|sfx:sniff|> -> *sniffs*."""
    def one(m):
        fam, val = m.group(1), m.group(2)
        word = TTS_TAG_WORDS.get((fam, val)) or val.replace("_", " ")
        return "*%s* " % word          # a space for the reader; the engine got none
    out = TTS_TOKEN_RX.sub(one, str(text or ""))
    return re.sub(r" {2,}", " ", out).strip()


def tts_normalize(text):
    """Match the reference wrapper: collapse whitespace, end with punctuation.

    The trailing full stop is why SkyrimNet's `ping` arrives as `ping.` - any ping
    check must compare AFTER this, never against the literal.
    """
    text = " ".join(str(text or "").split())
    if text and text[-1] not in ".!?,;\"'":
        text += "."
    return text


def tts_chunks(text, maxc=TTS_CHUNK_CHARS):
    """Split on sentence boundaries, packing greedily up to maxc."""
    sentences = re.findall(r"[^.!?]+[.!?]+|\S[^.!?]*$", text)
    sentences = [s.strip() for s in sentences if s.strip()]
    pieces = []
    for s in sentences:
        if len(s) <= maxc:
            pieces.append(s)
            continue
        buf = ""
        for part in re.split(r"(?<=,)\s+", s):
            if len(part) > maxc:
                if buf:
                    pieces.append(buf.strip()); buf = ""
                line = ""
                for w in part.split():
                    if len(line) + len(w) + 1 > maxc:
                        pieces.append(line.strip()); line = w
                    else:
                        line = (line + " " + w).strip()
                if line:
                    pieces.append(line.strip())
            elif len(buf) + len(part) + 1 > maxc:
                pieces.append(buf.strip()); buf = part
            else:
                buf = (buf + " " + part).strip()
        if buf:
            pieces.append(buf.strip())
    out, cur = [], ""
    for p in pieces:
        if not cur:
            cur = p
        elif len(cur) + len(p) + 1 <= maxc:
            cur = cur + " " + p
        else:
            out.append(cur); cur = p
    if cur:
        out.append(cur)
    return out or [text]


def tts_wav_join(parts, gap_ms=TTS_CHUNK_GAP_MS):
    """Concatenate WAV blobs with a silence gap. Stdlib `wave` only.

    All parts come from one model, so the format is uniform; the first part's
    parameters win and any part that disagrees is skipped rather than producing
    a garbled join.
    """
    frames, params, gap = [], None, b""
    for raw in parts:
        if not raw:
            continue
        try:
            with _wave.open(io.BytesIO(raw), "rb") as w:
                p = w.getparams()
                data = w.readframes(w.getnframes())
        except Exception:
            continue
        if params is None:
            params = p
            gap = b"\x00" * int(p.framerate * gap_ms / 1000.0) * p.sampwidth * p.nchannels
        elif (p.framerate, p.sampwidth, p.nchannels) != (
                params.framerate, params.sampwidth, params.nchannels):
            continue
        elif frames:
            frames.append(gap)
        frames.append(data)
    if params is None:
        return None, 0, 0
    buf = io.BytesIO()
    with _wave.open(buf, "wb") as w:
        w.setnchannels(params.nchannels)
        w.setsampwidth(params.sampwidth)
        w.setframerate(params.framerate)
        w.writeframes(b"".join(frames))
    body = buf.getvalue()
    nframes = sum(len(f) for f in frames) // (params.sampwidth * params.nchannels)
    return body, params.framerate, nframes


def tts_wav_normalize(raw):
    """Re-encode a reference voice to a canonical mono PCM WAV.

    The reference wrapper round-trips it through soundfile before base64, which
    quietly strips any extra RIFF chunks the producer left behind and rewrites a
    clean header. Handing over the original bytes instead is the difference between
    that wrapper working and this one being answered with 400.
    """
    try:
        with _wave.open(io.BytesIO(raw), "rb") as w:
            nch, sw, fr = w.getnchannels(), w.getsampwidth(), w.getframerate()
            frames = w.readframes(w.getnframes())
    except Exception:
        return raw                      # not a WAV we can read: send it untouched
    if nch > 1 and sw == 2:             # downmix without audioop (gone in 3.13)
        a = array.array("h")
        a.frombytes(frames[:len(frames) - (len(frames) % (2 * nch))])
        mono = array.array("h", [int(sum(a[i:i + nch]) / nch) for i in range(0, len(a), nch)])
        frames, nch = mono.tobytes(), 1
    out = io.BytesIO()
    with _wave.open(out, "wb") as w:
        w.setnchannels(nch); w.setsampwidth(sw); w.setframerate(fr)
        w.writeframes(frames)
    return out.getvalue()


def tts_speaker_path(v):
    """Pull a filesystem path out of whatever shape the speaker_audio field arrives in.

    The request body is never logged by SkyrimNet, so the exact form is unconfirmed -
    Gradio FileData is a dict, but a bare string is equally plausible. Handle both
    rather than guess one.
    """
    if isinstance(v, str):
        return v or None
    if isinstance(v, dict):
        for k in ("path", "name", "orig_name"):
            if v.get(k):
                return str(v[k])
    return None


class TtsWrapper:
    """Gradio-facing listener. One per panel; bound only while enabled."""

    def __init__(self):
        self._srv = None
        self._port = None
        self._lock = threading.Lock()
        self._events = {}          # event_id -> {"done":Event, "path":str, "err":str}
        self._voice = {}           # md5 -> base64 of the reference wav
        self._dir = None

    # ---- storage: everything this listener reads or writes lives in one folder,
    # ---- because /gradio_api/file= takes an absolute path from the caller and the
    # ---- listener is reachable from the LAN.
    def dir(self):
        if not self._dir:
            d = os.path.join(tempfile.gettempdir(), "pandorum-tts")
            os.makedirs(d, exist_ok=True)
            self._dir = os.path.realpath(d)
        return self._dir

    def prune(self, keep=24, keep_voices=32):
        """Every generated line leaves a WAV behind, and every distinct reference voice
        leaves a folder. Without this the temp folder grows for as long as the game runs.
        Mirrors prune_keep_newest for the panel's own logs. Dropping a voice folder is
        safe: SkyrimNet re-uploads when its HEAD check comes back 404."""
        try:
            root = self.dir()
            files = [os.path.join(root, f) for f in os.listdir(root)
                     if f.startswith("out-") and f.endswith(".wav")]
            for p in sorted(files, key=os.path.getmtime, reverse=True)[keep:]:
                try: os.remove(p)
                except Exception: pass
            dirs = [os.path.join(root, d) for d in os.listdir(root)
                    if os.path.isdir(os.path.join(root, d))]
            for d in sorted(dirs, key=os.path.getmtime, reverse=True)[keep_voices:]:
                try: shutil.rmtree(d, ignore_errors=True)
                except Exception: pass
        except Exception:
            pass

    def owns(self, path):
        try:
            p = os.path.normcase(os.path.realpath(path))
        except Exception:
            return False
        r = os.path.normcase(self.dir())
        return p == r or p.startswith(r + os.sep)

    def upstream(self, cfg=None):
        st = (cfg or load_config()).get("settings", {})
        port = str(st.get("ttsServerPort") or "1240").strip() or "1240"
        return "http://127.0.0.1:%s/tts" % port

    # ---- lifecycle
    def sync(self):
        cfg = load_config()
        st = cfg.get("settings", {})
        on = str(st.get("ttsWrapMode", "off")).lower() == "on"
        try:
            port = int(str(st.get("ttsWrapperPort") or "7860").strip())
        except Exception:
            port = 7860
        with self._lock:
            if self._srv and (not on or port != self._port):
                try:
                    srv = self._srv
                    threading.Thread(target=srv.shutdown, daemon=True).start()
                    panel_log("[tts] closed listener :%d" % (self._port or 0))
                    self.log("\U0001F50C Proxy TTS listener closed on :%d" % (self._port or 0))
                except Exception:
                    pass
                self._srv, self._port = None, None
            if on and not self._srv:
                try:
                    srv = _QuietServer(("0.0.0.0", port), _mk_tts_handler(self))
                    self._srv, self._port = srv, port
                    threading.Thread(target=srv.serve_forever, daemon=True).start()
                    panel_log("[tts] listening :%d -> %s" % (port, self.upstream(cfg)))
                    self.log("\u2705 Proxy TTS ready for voice synthesis")
                    self.log("")
                    self.log("* Listening on http://0.0.0.0:%d  (point SkyrimNet here)" % port)
                    self.log("* Forwarding to %s" % self.upstream(cfg))
                    self.log("")
                except OSError as e:
                    panel_log("[tts] FAILED to bind :%d (%s)" % (port, e))
                    log_error("tts", "failed to bind :%d (%s) - another wrapper may hold it" % (port, e))
        return {"listening": self._port}

    def state(self):
        return {"on": bool(self._srv), "port": self._port}

    # ---- the human log the TTS terminal renders. Written here, so the panel can
    # ---- notify directly instead of waiting for the file watcher.
    def log(self, line):
        """Stamped, so the proxy terminal can put a spoken line beside the completion
        that produced it. The Timestamps button hides them again."""
        line = line.rstrip()
        if line:
            now = time.time()
            line = "[%s.%02d] %s" % (time.strftime("%H:%M:%S", time.localtime(now)),
                                     int((now % 1) * 100), line)
        try:
            with open(os.path.join(log_dir(), TTS_LOG_NAME), "a", encoding="utf-8") as f:
                f.write(line + "\n")
            sse_notify("tail")
        except Exception:
            pass

    # ---- protocol steps
    def save_upload(self, filename, data):
        """Store an uploaded reference voice, normalised.

        SkyrimNet's samples come from FFmpeg, which leaves extra RIFF chunks behind.
        moss-tts-server answered those with 400, and audio.cpp with
        "failed to read WAV data chunk" - the same fault seen twice through two
        different parsers. Normalising HERE fixes it once for every engine, rather
        than in whichever arm happened to notice: the file on disk is canonical, so
        both the base64 MOSS wants and the path audio.cpp wants are clean.
        """
        name = re.split(r"[\\/]", str(filename or "voice.wav"))[-1]
        name = re.sub(r"[^A-Za-z0-9._-]+", "_", name) or "voice.wav"
        sub = os.path.join(self.dir(), hashlib.md5(data).hexdigest())
        os.makedirs(sub, exist_ok=True)
        path = os.path.join(sub, name)
        clean = tts_wav_normalize(data) if data[:4] == b"RIFF" else data
        if clean is not data and len(clean) != len(data):
            panel_log("[tts] normalised %s: %d -> %d bytes" % (name, len(data), len(clean)))
        with open(path, "wb") as f:
            f.write(clean)
        return path

    def submit(self, fields):
        eid = uuid.uuid4().hex
        ev = {"done": threading.Event(), "path": "", "err": ""}
        with self._lock:
            self._events[eid] = ev
            for k in list(self._events)[:-40]:      # keep the last 40
                self._events.pop(k, None)
        text, ref = tts_pick_fields(fields)
        threading.Thread(target=self._run, args=(eid, text, ref), daemon=True).start()
        return eid

    def result(self, eid, timeout=TTS_RESULT_WAIT_S):
        with self._lock:
            ev = self._events.get(eid)
        if not ev:
            return {"err": "unknown event"}
        ev["done"].wait(timeout=timeout)
        if not ev["done"].is_set():
            return {"err": "timed out"}
        return {"path": ev["path"], "err": ev["err"]}

    def _ref_b64(self, path):
        if not path or not os.path.isfile(path):
            return None, False
        try:
            with open(path, "rb") as f:
                raw = f.read()
        except Exception:
            return None, False
        h = hashlib.md5(raw).hexdigest()
        with self._lock:
            hit = h in self._voice
            if hit:
                return self._voice[h], True
        b64 = base64.b64encode(tts_wav_normalize(raw)).decode("ascii")
        with self._lock:
            self._voice[h] = b64
            for k in list(self._voice)[:-16]:
                self._voice.pop(k, None)
        return b64, False

    def _post_chunk(self, url, text, ref_b64):
        body = {"text": text, "max_new_tokens": TTS_MAX_NEW_TOKENS}
        if ref_b64:
            body["reference_wav_b64"] = ref_b64
        req = _ureq.Request(url, data=json.dumps(body).encode("utf-8"),
                            headers={"Content-Type": "application/json"}, method="POST")
        try:
            r = _ureq.urlopen(req, timeout=120)
        except _uerr.HTTPError as e:
            detail = ""
            try:
                detail = e.read().decode("utf-8", "replace")[:400].strip()
            except Exception:
                pass
            raise RuntimeError("HTTP %s from %s%s" % (
                e.code, url, (" - " + detail) if detail else " (no detail returned)"))
        with r:
            raw = r.read()
            g = float(r.headers.get("X-MOSS-Generate-Seconds") or 0)
            d = float(r.headers.get("X-MOSS-Decode-Seconds") or 0)
        return raw, g, d

    def say_line(self, ref_path, processed, display=True):
        """The spoken line, once. Each engine arm wrote its own copy of this.

        display=False for MOSS: it is handed the text as it stands and has no Higgs
        tokens to turn back into stage directions.
        """
        self.log("%s %s: \u3030\uFE0F %s \u3030\uFE0F"
                 % (tts_mood_icon(processed), tts_speaker_label(ref_path),
                    tts_tags_display(processed) if display else processed))

    def saved_line(self, body, ref_path, cfg, out, local):
        """Keep a named copy and report it. Also written twice before."""
        kept = tts_save_named(body, tts_speaker_label(ref_path), cfg)
        self.log("\U0001F4BE Saved: %s (%.1f KB)%s"
                 % (os.path.basename(kept or out), len(body) / 1024.0,
                    "  [local clip]" if local else ""))

    def _run(self, eid, text, ref_path):
        ev = self._events.get(eid)
        t0 = time.time()
        cfg = load_config()
        st = cfg.get("settings", {})
        local = tts_local_sample(ref_path, cfg)
        if local:
            ref_path = local
        processed = tts_apply_tags(tts_normalize(text),
                                   str(st.get("ttsTags", "off")).lower() == "on",
                                   tts_engine(cfg))
        try:
            # SkyrimNet pings at startup with a silent reference. Answering it here costs
            # nothing; letting it through spends 600-1100ms of GPU saying "ping".
            if str(st.get("ttsAnswerPing", "on")).lower() == "on" and \
                    processed.rstrip(".!?").strip().lower() == "ping":
                out = self._silence()
                ev["path"] = out
                self.log("\U0001F50C Ping answered locally (no GPU)")
                return
            if tts_engine(cfg) == "audiocpp":
                self.say_line(ref_path, processed)
                self.log("")
                mid = st.get("ttsAcppModelId") or "higgs"
                base = "http://127.0.0.1:%d" % tts_server_port(cfg)
                _t_post = time.time()
                body, hdrs = tts_acpp_speak(base, mid, processed,
                                            tts_ref_canonical(ref_path) if ref_path else "")
                srv_s = time.time() - _t_post
                if not body:
                    raise RuntimeError("no audio returned by audio.cpp")
                out = os.path.join(self.dir(), "out-%s.wav" % eid)
                with open(out, "wb") as f:
                    f.write(body)
                self.prune()
                ev["path"] = out
                wall = time.time() - t0
                rate, nframes = 0, 0
                try:
                    with _wave.open(io.BytesIO(body), "rb") as w:
                        rate, nframes = w.getframerate(), w.getnframes()
                except Exception:
                    pass
                secs = (nframes / float(rate)) if rate else 0.0
                gen_s = _num_or(hdrs, ("x-audiocpp-generate-seconds", "x-generate-seconds",
                                       "x-inference-seconds", "x-higgs-generate-seconds"))
                dec_s = _num_or(hdrs, ("x-audiocpp-decode-seconds", "x-decode-seconds",
                                       "x-codec-seconds"))
                toks = secs * TTS_ACPP_FRAME_RATE
                self.log("\u26A1 %.2fx realtime (%.2fs \u2192 %.1fs audio)" % (
                    (secs / wall) if wall else 0.0, wall, secs))
                if gen_s or dec_s:      # the server told us; show its own split
                    self.log("   %-9s%6.0f ms   %7.1f audio tok   %7.1f tps"
                             % ("generate:", gen_s * 1000.0, toks, (toks / gen_s) if gen_s else 0.0))
                    self.log("   %-9s%6.0f ms   %7d samples     %7.0f tps"
                             % ("codec:", dec_s * 1000.0, nframes, (toks / dec_s) if dec_s else 0.0))
                else:                   # it did not, so split what WE can measure
                    self.log("   %-9s%6.0f ms   %7.1f audio tok   %7.1f tps"
                             % ("server:", srv_s * 1000.0, toks, (toks / srv_s) if srv_s else 0.0))
                    self.log("   %-9s%13d samples @ %d Hz" % ("audio:", nframes, rate))
                self.log("   %-9s%6.0f ms   (http + wav)"
                         % ("overhead:", max(0.0, (wall - (gen_s + dec_s or srv_s)) * 1000.0)))
                _unknown = [k for k in hdrs
                            if k.startswith("x-") and k not in ("x-request-id",)]
                if _unknown and not (gen_s or dec_s):
                    panel_log("[tts] audio.cpp response headers seen: %s" % ", ".join(sorted(_unknown)))
                self.saved_line(body, ref_path, cfg, out, local)
                self.log("")
                return

            ref_b64, cached = self._ref_b64(ref_path)
            if ref_b64 is None:
                self.log("\u26A0\uFE0F No reference voice resolved from %s" % (ref_path or "(none sent)"))
            else:
                self.log("\u267B\uFE0F Reused cached voice" if cached else "\U0001F195 Recomputing voice")
            self.log("")
            self.say_line(ref_path, processed, display=False)
            toks = secs * TTS_FRAME_RATE
            self.log("   %-9s%6.0f ms   %7.1f audio tok   %7.1f tps"
                     % ("generate:", gen_s * 1000.0, toks, (toks / gen_s) if gen_s else 0.0))
            self.log("   %-9s%6.0f ms   %7d samples     %7.0f tps"
                     % ("codec:", dec_s * 1000.0, nframes, (toks / dec_s) if dec_s else 0.0))
            self.log("   %-9s%6.0f ms   (http + wav)" % ("overhead:", over))
            self.saved_line(body, ref_path, cfg, out, local)
            self.log("")
        except Exception as e:
            # a crashed server just closes the socket; its own log says why
            hint = tts_diagnose(cfg, TTS_PROC.get("log_at")) if tts_engine(cfg) == "audiocpp" else ""
            ev["err"] = (str(e) + ((" - " + hint) if hint else ""))[:300]
            self.log("\u274C TTS failed: %s" % str(e)[:200])
            if hint:
                self.log("   \u2192 %s" % hint)
            log_error("tts", "generate failed: %s%s" % (e, (" - " + hint) if hint else ""))
        finally:
            ev["done"].set()

    def _silence(self, ms=120):
        out = os.path.join(self.dir(), "silence.wav")
        if not os.path.isfile(out):
            with _wave.open(out, "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000)
                w.writeframes(b"\x00" * int(24000 * ms / 1000.0) * 2)
        return out


# ---- learning an NPC's real name -------------------------------------------------
# The voice sample is named after the VOICETYPE - femaleyoungeager, malenord - not the
# character. The name is in the dialogue prompt the proxy already forwards, in the first
# line of the system message:
#
#   You are Serana, a Female Nord in Skyrim. You are speaking to Maxxor, ...
#
# So the proxy reads it out of a request it is already carrying: no extra model call and
# nothing leaves the machine. Only the name is kept - never the prompt.
#
# It then LEARNS the pairing. A TTS call arriving shortly after a dialogue request is
# almost certainly that character speaking, so voicetype -> name is remembered and used
# from then on, including out of order.
SPEAKER_RX = re.compile(rb"You are ([A-Z][A-Za-z' \-]{1,28}?), a ")
# The player is named by the PARTY, which is always theirs whoever is speaking:
#   ## Maxxor's Party's Active Quests
# NOT by "You are speaking to ...", which names the LISTENER - when one NPC addresses
# another, that line holds the other NPC and the player's own voice took their name.
PLAYER_RX = re.compile(rb"##\s+([A-Z][A-Za-z' \-]{1,28}?)'s Party's")
# The player's own voice must never learn an NPC's name. Their line is spoken when THEY
# speak, which is before the next dialogue request, so it would pair with the previous
# turn's character - which is exactly what happened.
PLAYER_VOICES = frozenset(("player", "playervoice", "playerdialogue"))
SPEAKER_SCAN = 4096            # the speaker sits in the first few hundred bytes
PLAYER_SCAN = 262144           # the party marker is much further in
SPEAKER_PAIR_S = 15.0          # a TTS call this soon after a request is that character
_spk_lock = threading.Lock()
_spk_recent = []               # [(when, name)], newest last
_spk_voices = {}               # voicetype -> name, learned
_spk_player = [""]             # the player's own name, from the same line


def note_speaker(body):
    """Remember the character named in a dialogue request. Cheap and best-effort."""
    if not body:
        return
    try:
        m = SPEAKER_RX.search(body[:SPEAKER_SCAN])
        if not m:
            return
        name = m.group(1).decode("utf-8", "replace").strip()
        if not name or name.lower() in ("speaking", "a", "an"):
            return
        # the party marker sits ~17 KB in, well past the speaker, so it needs a wider
        # look - but only until it is found once. A regex over 45 KB is microseconds;
        # it is JSON parsing that would have cost something.
        pm = None
        if not _spk_player[0]:
            pm = PLAYER_RX.search(body[:PLAYER_SCAN])
        with _spk_lock:
            _spk_recent.append((time.time(), name))
            del _spk_recent[:-12]
            if pm:
                _spk_player[0] = pm.group(1).decode("utf-8", "replace").strip()
    except Exception:
        pass


def speaker_for_voice(voicetype):
    """The character behind a voicetype, learned from what the proxy has carried."""
    key = str(voicetype or "").strip().lower()
    if not key:
        return ""
    if key in PLAYER_VOICES:
        # named by the prompt where it says so, otherwise just "Player". Never learned,
        # and never a name taken from a conversation.
        return _spk_player[0] or "Player"
    now = time.time()
    with _spk_lock:
        known = _spk_voices.get(key)
        if known:
            return known                         # already paired; never re-learn
        # CONSUME the request it pairs with. Without that, a second voicetype asked
        # inside the same window inherited the same name - and the pairing is cached,
        # so one wrong guess would stick.
        for idx in range(len(_spk_recent) - 1, -1, -1):
            when, name = _spk_recent[idx]
            if now - when <= SPEAKER_PAIR_S:
                _spk_voices[key] = name
                del _spk_recent[idx]
                panel_log("[tts] voice %s is %s" % (key, name))
                return name
        return ""


def tts_voice_name(path):
    if not path:
        return "Default Voice"
    n = re.split(r"[\\/]", str(path))[-1]
    if n.lower().endswith(".wav"):
        n = n[:-4]
    n = re.sub(r"([a-z])([A-Z])", r"\1 \2", n)
    return n.replace("_", " ").title() or "Default Voice"


def tts_speaker_label(path):
    """The character's name where the proxy has learned it, else the voicetype."""
    leaf = re.split(r"[\\/]", str(path or ""))[-1]
    return speaker_for_voice(os.path.splitext(leaf)[0]) or tts_voice_name(path)


def tts_parse_multipart(body, ctype):
    """Extract (filename, bytes) pairs. `cgi` was removed in 3.13, so parse by hand."""
    m = re.search(r"boundary=([^;]+)", ctype or "")
    if not m:
        return []
    bound = b"--" + m.group(1).strip().strip('"').encode("ascii", "replace")
    out = []
    for part in body.split(bound):
        if b"\r\n\r\n" not in part:
            continue
        head, data = part.split(b"\r\n\r\n", 1)
        if data.endswith(b"\r\n"):
            data = data[:-2]
        fn = re.search(rb'filename="([^"]*)"', head)
        if fn and data:
            out.append((fn.group(1).decode("utf-8", "replace"), data))
    return out


def _mk_tts_handler(mgr):
    class _T(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        MAX_BODY = 32 * 1024 * 1024      # a reference voice is ~250 KB

        def log_message(self, *a):
            pass

        def _allowed(self):
            """Same allowlist the proxy applies. Both listeners bind 0.0.0.0 for 2-PC
            mode, so without this anyone on the LAN could upload files and spend GPU
            time here while the proxy beside it refused them."""
            allow = getattr(PROXY, "allow", None)
            if allow is not None and self.client_address[0] not in allow:
                self.send_response(403)
                self.send_header("Content-Length", "0")
                self.send_header("Connection", "close")
                self.end_headers()
                log_error("tts", "rejected %s (not in IP allowlist)" % self.client_address[0])
                return False
            return True

        def _json(self, code, obj):
            body = json.dumps(obj).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _filepath(self):
            i = self.path.find("file=")
            return unquote(self.path[i + 5:]) if i >= 0 else ""

        def do_HEAD(self):
            if not self._allowed(): return
            p = self._filepath()
            ok = bool(p) and mgr.owns(p) and os.path.isfile(p)
            self.send_response(200 if ok else 404)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_GET(self):
            if not self._allowed(): return
            if "/gradio_api/file=" in self.path:
                p = self._filepath()
                # the listener is on 0.0.0.0 and the path comes from the caller, so
                # anything outside our own folder is refused rather than served
                if not (p and mgr.owns(p) and os.path.isfile(p)):
                    self.send_response(404); self.send_header("Content-Length", "0"); self.end_headers(); return
                with open(p, "rb") as f:
                    data = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "audio/wav")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            m = re.search(r"/gradio_api/call/generate_audio/([0-9a-f]+)", self.path)
            if m:
                r = mgr.result(m.group(1))
                if r.get("err") or not r.get("path"):
                    payload = "event: error\ndata: {\"error\": null}\n\n"
                else:
                    fd = [{"path": r["path"],
                           "url": "http://127.0.0.1:%s/gradio_api/file=%s" % (mgr._port, r["path"]),
                           "size": None, "orig_name": os.path.basename(r["path"]),
                           "mime_type": None, "is_stream": False,
                           "meta": {"_type": "gradio.FileData"}}]
                    payload = "event: complete\ndata: %s\n\n" % json.dumps(fd)
                body = payload.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_response(404); self.send_header("Content-Length", "0"); self.end_headers()

        def do_POST(self):
            if not self._allowed(): return
            try:
                n = int(self.headers.get("Content-Length") or 0)
            except Exception:
                n = 0
            if n > self.MAX_BODY:        # do not allocate whatever a caller claims
                self._json(413, {"error": "body too large"})
                return
            body = self.rfile.read(n) if n else b""
            if self.path.startswith("/gradio_api/upload"):
                files = tts_parse_multipart(body, self.headers.get("Content-Type") or "")
                if not files:
                    self._json(400, {"error": "no file"}); return
                paths = [mgr.save_upload(fn, data) for fn, data in files]
                self._json(200, paths)
                return
            if "/gradio_api/call/generate_audio" in self.path:
                try:
                    data = (json.loads(body.decode("utf-8")) or {}).get("data") or []
                except Exception:
                    data = []
                if not data:
                    self._json(400, {"error": "no data"}); return
                self._json(200, {"event_id": mgr.submit(data)})
                return
            self._json(404, {"error": "not found"})
    return _T


TTSW = TtsWrapper()


PANEL_START = time.time()      # a log older than this is a previous session
_tts_models_cache = {"t": 0.0, "dir": "", "items": []}


def list_tts_models(cfg=None):
    """Every model under the TTS models folder that audio.cpp can actually load.

    Two shapes, because audio.cpp accepts both:
      * a .gguf FILE - self-contained, its configs are embedded and extracted on load
      * a FOLDER of safetensors - config.json plus model.safetensors[.index.json]

    A folder holding both is listed only as its .gguf and marked, because audio.cpp
    resolves the GGUF and ignores the safetensors silently - selecting "safetensors"
    there would quietly load something else.

    Walks three levels like list_models() and does not read any headers, so this stays
    cheap even on a large folder.
    """
    cfg = cfg or load_config()
    base = (cfg.get("settings", {}).get("ttsAcppModelsDir") or "").strip()
    now = time.time()
    if _tts_models_cache["dir"] == base and now - _tts_models_cache["t"] < 120:
        return _tts_models_cache["items"]
    items = []
    if base and os.path.isdir(base):
        for root, dirs, files in os.walk(base):
            if root[len(base):].count(os.sep) > 3:
                dirs[:] = []
                continue
            ggufs = [n for n in files if n.lower().endswith(".gguf")]
            for n in sorted(ggufs):
                m = PART_RX.search(n)
                if m and m.group(1) != "00001":
                    continue                      # one entry per sharded set
                full = os.path.join(root, n)
                items.append({"path": full, "name": os.path.relpath(full, base),
                              "kind": "gguf", "shadows": len(ggufs) > 1})
            has_cfg = "config.json" in (x.lower() for x in files)
            has_st = any(x.lower() in ("model.safetensors", "model.safetensors.index.json")
                         for x in files)
            if has_cfg and has_st:
                rel = os.path.relpath(root, base)
                items.append({"path": root, "name": ("." if rel == "." else rel) + "  (safetensors)",
                              "kind": "safetensors", "shadowed": bool(ggufs)})
    items.sort(key=lambda x: x["name"].lower())
    _tts_models_cache.update(t=now, dir=base, items=items)
    return items


def api_tts_models(body):
    """Host-only: absent from REMOTE_POST_OK, and it discloses filesystem paths."""
    cfg = load_config()
    items = list_tts_models(cfg)
    return {"models": items, "dir": cfg.get("settings", {}).get("ttsAcppModelsDir") or "",
            "selected": cfg.get("settings", {}).get("ttsAcppModel") or ""}


TTS_HINTS = (
    ("no kernel image is available",
     "the server has no CUDA kernels for the card it is pinned to. The prebuilt "
     "CUDA package covers RTX 20xx and newer; a self-build needs "
     "-CudaArchitectures covering this card (a 3090 is 86-real)"),
    ("missing model file 'config'",
     "this .gguf carries no config of its own - it is a tensor-only build and needs its "
     "sidecar files (config.json, tokenizer, chat template) in the SAME folder. "
     "audio.cpp's own GGUFs embed them; ones built for another app often do not"),
    ("exact tensor shape metadata is invalid",
     "this .gguf was written by a different converter and audio.cpp cannot read its "
     "tensor metadata - use a GGUF built for audio.cpp"),
    ("missing model package file",
     "the model path points at the wrong place - select a model folder or .gguf, not the "
     "folder above it"),
    ("out of memory",
     "not enough VRAM - try a shorter reference voice, a smaller model, or another card"),
    ("failed to read WAV data chunk",
     "the reference voice is not a plain WAV the server can read"),
)


def _num_or(hdrs, names):
    """First of these headers that parses as a number, else 0.0.

    Which timing headers audio.cpp sends is not documented, so try the plausible
    spellings rather than assume one and silently report zero.
    """
    for n in names:
        v = (hdrs or {}).get(n)
        if v:
            try:
                return float(v)
            except Exception:
                pass
    return 0.0


ACPP_EXE_NAME = "audiocpp_server.exe"
ACPP_REPO = "0xShug0/audio.cpp"
_acpp_find = {"root": "", "t": 0.0, "exe": ""}


def find_acpp_exe(root):
    """Locate audiocpp_server.exe under a root folder.

    Same shape as the llama.cpp folder setting: the user names a FOLDER and the panel
    finds the binary. Naming the executable directly is not offered - a path field that
    accepts any .exe is a path field that will eventually be pointed at the wrong .exe.

    A prebuilt release unzips flat; a source build puts it under
    build/windows-cuda-release/bin. Four levels covers both without walking a whole drive.
    """
    root = (root or "").strip()
    if not root or not os.path.isdir(root):
        return ""
    now = time.time()
    if _acpp_find["root"] == root and now - _acpp_find["t"] < 30 and _acpp_find["exe"]:
        if os.path.isfile(_acpp_find["exe"]):
            return _acpp_find["exe"]
    hit = ""
    direct = os.path.join(root, ACPP_EXE_NAME)
    if os.path.isfile(direct):
        hit = direct
    else:
        for cur, dirs, files in os.walk(root):
            if cur[len(root):].count(os.sep) > 4:
                dirs[:] = []
                continue
            for f in files:
                if f.lower() == ACPP_EXE_NAME:
                    hit = os.path.join(cur, f)
                    break
            if hit:
                break
    _acpp_find.update(root=root, t=now, exe=hit)
    return hit


# ---------------------------------------------------------------- Higgs installer
# The panel downloading and unpacking executables is the largest thing it does on
# a user's behalf, so it is deliberately narrow: host only, never automatic, one
# explicit confirmation naming both sources, everything logged to the terminal as
# it happens, and cancellable. Nothing is sent anywhere - these are two public
# GETs and the panel says nothing about the machine it is running on.
# WORDS an asset must contain, not a filename or even a prefix. The release always
# fetched is "latest", so the version is never pinned - but the naming is not ours to
# rely on. Exact names broke the moment a build hash appeared
# (audiocpp-windows-cuda-balance-27d87ba.zip); a prefix would break on any reordering.
# Requiring the words survives both, and anything unrecognised is reported with the
# real asset list so it can be installed by hand.
#
# The runtime is OPTIONAL: it is shared across builds today, and a future release that
# folds it into the profile archive should not be treated as broken.
# (label, must contain, must NOT contain, preferred in order, required)
# "win" not "windows", so win64 matches too. The profile is a PREFERENCE, not a
# requirement: if the profile names ever change, any Windows CUDA build still beats
# failing outright.
HIGGS_ENGINE_ASSETS = (
    ("runtime", ("win", "cuda", "runtime"), (), (), False),
    ("CUDA build", ("win", "cuda"), ("runtime", "debug", "symbol", "cpu"),
     ("balance", "portable", "fast"), True),
)
HIGGS_GGUF_REPO = "audio-cpp/audio.cpp-gguf"
HIGGS_GGUF_PATH = "Higgs-Audio-v3-TTS-4B-GGUF/higgs-audio-v3-tts-4b-q8_0.gguf"
HIGGS_NEED_BYTES = 8 * 1024 * 1024 * 1024        # ~5.1 GB model plus room to unzip
HIGGS_INSTALL = {"running": False, "cancel": False, "step": "", "pct": 0.0,
                 "error": "", "done": False, "engine": "", "model": "",
                 "warn": ""}


def higgs_paths(cfg=None):
    root = STACK
    return {"engine": os.path.join(root, "audio.cpp"),
            "models": os.path.join(root, "Models", "TTS"),
            "model_dir": os.path.join(root, "Models", "TTS", "Higgs-v3-4b")}


def _hi_log(msg):
    HIGGS_INSTALL["step"] = msg
    TTSW.log(msg)


def _hi_get(url, headers=None):
    h = {"User-Agent": "PandorumLLM"}
    h.update(headers or {})
    return urlopen(Request(url, headers=h), timeout=30)


def _hi_download(url, dest, label):
    """Stream to disk with progress, resuming a part-file if one is there."""
    part = dest + ".part"
    have = os.path.getsize(part) if os.path.isfile(part) else 0
    headers = {"Range": "bytes=%d-" % have} if have else {}
    try:
        r = _hi_get(url, headers)
    except HTTPError as e:
        if have and e.code in (416, 200):        # server will not resume; start over
            have, r = 0, _hi_get(url)
        else:
            raise
    total = int(r.headers.get("Content-Length") or 0) + have
    mode = "ab" if have and r.status == 206 else "wb"
    if mode == "wb":
        have = 0
    done, last = have, 0.0
    with r, open(part, mode) as f:
        while True:
            if HIGGS_INSTALL["cancel"]:
                raise RuntimeError("cancelled")
            chunk = r.read(1024 * 512)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            if total and time.time() - last > 1.0:
                last = time.time()
                HIGGS_INSTALL["pct"] = 100.0 * done / total
                _hi_log("   %s  %.0f%%  (%.0f of %.0f MB)"
                        % (label, HIGGS_INSTALL["pct"], done / 1e6, total / 1e6))
    if total and done < total:
        raise RuntimeError("%s ended early (%d of %d bytes)" % (label, done, total))
    os.replace(part, dest)
    return dest


def _hi_unzip(src, dest):
    """Extract, refusing any entry that would land outside dest.

    A zip may name ..\\..\\windows\\system32 and a naive extractall will write it.
    """
    import zipfile
    dest = os.path.realpath(dest)
    os.makedirs(dest, exist_ok=True)
    with zipfile.ZipFile(src) as z:
        for info in z.infolist():
            name = info.filename.replace("\\", "/")
            if name.endswith("/"):
                continue
            # do NOT strip ".." and then extract: that quietly flattens a hostile
            # archive into the folder instead of refusing it. Resolve the name as
            # written and check where it actually lands.
            if name.startswith("/") or re.match(r"^[A-Za-z]:", name):
                raise RuntimeError("refusing an absolute path in the archive: %s"
                                   % info.filename)
            out = os.path.realpath(os.path.join(dest, name))
            if not (out == dest or out.startswith(dest + os.sep)):
                raise RuntimeError("refusing an archive entry outside the folder: %s"
                                   % info.filename)
            os.makedirs(os.path.dirname(out), exist_ok=True)
            with z.open(info) as fh, open(out, "wb") as f:
                shutil.copyfileobj(fh, f)


def _hi_free_bytes(path):
    try:
        return shutil.disk_usage(path).free
    except Exception:
        return None


def higgs_install_worker():
    cfg = load_config()
    paths = higgs_paths(cfg)
    tmp = os.path.join(STACK, "logs", "_higgs-download")
    try:
        os.makedirs(tmp, exist_ok=True)
        free = _hi_free_bytes(STACK)
        if free is not None and free < HIGGS_NEED_BYTES:
            raise RuntimeError("not enough disk space: %.1f GB free, about %.0f GB needed"
                               % (free / 1e9, HIGGS_NEED_BYTES / 1e9))
        TTSW.log("")
        _hi_log("\U0001F4E6 Installing Higgs Audio v3 into %s" % STACK)

        # ---- 1. the engine
        _hi_log("\U0001F50E Asking github.com for the newest audio.cpp release...")
        rel = json.loads(_hi_get("https://api.github.com/repos/%s/releases/latest"
                                 % ACPP_REPO).read().decode("utf-8"))
        tag = str(rel.get("tag_name") or "?")
        assets = [a for a in (rel.get("assets") or []) if a.get("name")]
        def pick(need, avoid, prefer):
            """Best .zip carrying every needed word and none of the avoided ones.
            Preference order first, then the shortest name."""
            hits = [a for a in assets
                    if a["name"].lower().endswith(".zip")
                    and all(w in a["name"].lower() for w in need)
                    and not any(w in a["name"].lower() for w in avoid)]
            def rank(a):
                low = a["name"].lower()
                for i, w in enumerate(prefer):
                    if w in low:
                        return (i, len(low))
                return (len(prefer), len(low))
            return sorted(hits, key=rank)[0] if hits else None
        chosen, missing = [], []
        for label, need, avoid, prefer, required in HIGGS_ENGINE_ASSETS:
            a = pick(need, avoid, prefer)
            if a:
                chosen.append(a)
            elif required:
                missing.append("%s (needs %s)" % (label, " + ".join(need)))
            else:
                _hi_log("   no %s in this release - continuing without it" % label)
        if missing:
            raise RuntimeError(
                "release %s carries no %s. It has: %s" %
                (tag, "; ".join(missing),
                 ", ".join(a["name"] for a in assets[:9]) or "no assets at all"))
        _hi_log("   found %s" % tag)
        os.makedirs(paths["engine"], exist_ok=True)
        # ALWAYS replace. A previous version kept whatever was here if an
        # audiocpp_server.exe existed, which adopted a CPU-only build someone had
        # unpacked by hand. Trusting our own marker instead still vouched for an install
        # that antivirus had since gutted - a complete-looking folder with its DLLs gone.
        # The engine is a couple of hundred MB; a wrong one costs far more than that in
        # someone else's afternoon. The 5 GB model is still kept and resumed separately.
        stamp = os.path.join(paths["engine"], ".pandorum-engine.json")
        if os.listdir(paths["engine"]):
            _hi_log("\U0001F5D1 Clearing %s - the engine is always installed fresh"
                    % paths["engine"])
            for n_ in os.listdir(paths["engine"]):
                victim = os.path.join(paths["engine"], n_)
                try:
                    shutil.rmtree(victim) if os.path.isdir(victim) else os.remove(victim)
                except OSError as e:
                    raise RuntimeError("could not clear %s: %s - close anything using it "
                                       "and try again" % (victim, e))
        for a in chosen:
            name = a["name"]
            zp = os.path.join(tmp, name)
            _hi_log("\u2B07 %s (%.0f MB)" % (name, (a.get("size") or 0) / 1e6))
            _hi_download(a["browser_download_url"], zp, name)
            _hi_log("\U0001F4C2 Unpacking %s" % name)
            _hi_unzip(zp, paths["engine"])
            try:
                os.remove(zp)
            except OSError:
                pass
        exe = find_acpp_exe(paths["engine"])
        if not exe:
            raise RuntimeError("unpacked, but no %s was found - the release layout may "
                               "have changed" % ACPP_EXE_NAME)
        try:                       # so a later run knows this one is ours, and which
            with open(stamp, "w", encoding="utf-8") as f:
                json.dump({"tag": tag, "when": time.strftime("%Y-%m-%d %H:%M:%S")}, f)
        except OSError:
            pass
        _hi_log("\u2705 Engine ready: %s" % exe)

        # ---- 2. the model
        os.makedirs(paths["model_dir"], exist_ok=True)
        gguf = os.path.join(paths["model_dir"], os.path.basename(HIGGS_GGUF_PATH))
        if os.path.isfile(gguf) and os.path.getsize(gguf) > 4e9:
            _hi_log("\u2705 Model already here: %s" % os.path.basename(gguf))
        else:
            url = ("https://huggingface.co/%s/resolve/main/%s?download=true"
                   % (HIGGS_GGUF_REPO, HIGGS_GGUF_PATH))
            _hi_log("\u2B07 %s (about 5.1 GB - this is the long part)"
                    % os.path.basename(HIGGS_GGUF_PATH))
            _hi_download(url, gguf, "model")
            _hi_log("\u2705 Model ready: %s" % os.path.basename(gguf))

        # ---- 3. point the panel at what was just installed
        #
        # Everything is on disk by now. If only this last step fails - a locked config
        # is the usual reason - the download is NOT wasted, so say what was installed
        # and where rather than reporting a failed install.
        try:
            with CFG_LOCK:
                c = load_config()
                st = c.setdefault("settings", {})
                st["ttsEngine"] = "audiocpp"
                st["ttsAcppDir"] = paths["engine"]
                st["ttsAcppModelsDir"] = paths["models"]
                st["ttsAcppModel"] = gguf
                st["ttsAcppVersion"] = tag        # audiocpp_server has no --version
                # the panel answers SkyrimNet itself - an install that leaves this
                # pointing at a wrapper the user does not have produces silence
                st["ttsWrapMode"] = "on"
                if not str(st.get("ttsWrapperPort") or "").strip():
                    st["ttsWrapperPort"] = "7860"
                if not str(st.get("ttsServerPort") or "").strip():
                    st["ttsServerPort"] = "1240"
                save_config(c)
        except Exception as e:
            HIGGS_INSTALL["done"] = True
            HIGGS_INSTALL["warn"] = ("downloaded and unpacked, but the settings could not "
                                     "be saved: %s" % str(e)[:160])
            _hi_log("\u2705 Downloaded and unpacked, but the settings could not be saved: %s"
                    % str(e)[:160])
            _hi_log("   Nothing is lost. Set these by hand on this page:")
            _hi_log("      TTS engine          audio.cpp")
            _hi_log("      audio.cpp Folder    %s" % paths["engine"])
            _hi_log("      TTS Models Folder   %s" % paths["models"])
            _hi_log("      Model               %s" % gguf)
            TTSW.log("")
            return
        _tts_models_cache["t"] = 0.0
        HIGGS_INSTALL.update(done=True, engine=paths["engine"],
                             model=os.path.basename(gguf))
        _hi_log("\U0001F389 Higgs Audio v3 is installed and selected. Press Start TTS.")
        TTSW.log("")
    except Exception as e:
        msg = "cancelled" if str(e) == "cancelled" else str(e)[:300]
        HIGGS_INSTALL["error"] = msg
        _hi_log("\u274C Install %s" % ("cancelled" if msg == "cancelled"
                                       else "failed: " + msg))
        if msg != "cancelled":
            log_error("tts", "higgs install failed: %s" % msg)
    finally:
        HIGGS_INSTALL["running"] = False
        HIGGS_INSTALL["cancel"] = False
        sse_notify("state")


def higgs_present(cfg=None):
    """What is already installed where the panel would put it.

    Someone may have installed by hand, or the settings may have been lost while the
    files survived - a config save failing at the last step did exactly that. Offering
    to adopt what is there beats making them fill in four paths.
    """
    cfg = cfg or load_config()
    paths = higgs_paths(cfg)
    st = cfg.get("settings", {})
    exe = find_acpp_exe(paths["engine"])
    models = []
    for root, dirs, files in os.walk(paths["models"]):
        if root[len(paths["models"]):].count(os.sep) > 3:
            dirs[:] = []
            continue
        for f in sorted(files):
            if f.lower().endswith(".gguf"):
                models.append(os.path.join(root, f))
    wired = bool((st.get("ttsAcppDir") or "").strip()
                 and (st.get("ttsAcppModel") or "").strip())
    return {"exe": exe, "models": models[:8], "wired": wired,
            "adoptable": bool(exe and models and not wired)}


def api_higgs_adopt(body=None):
    """Point the settings at an install that is already on disk. Host only."""
    found = higgs_present()
    if not (found["exe"] and found["models"]):
        return {"error": "nothing to adopt - no server and model under %s"
                         % higgs_paths()["engine"]}
    paths = higgs_paths()
    with CFG_LOCK:
        c = load_config()
        st = c.setdefault("settings", {})
        st["ttsEngine"] = "audiocpp"
        st["ttsAcppDir"] = paths["engine"]
        st["ttsAcppModelsDir"] = paths["models"]
        st["ttsAcppModel"] = found["models"][0]
        ver = acpp_local_version(c)              # from a README if there is one
        if ver:
            st["ttsAcppVersion"] = ver
        save_config(c)
    _tts_models_cache["t"] = 0.0
    TTSW.log("\u2705 Adopted the install already in %s" % paths["engine"])
    return {"ok": True, "model": os.path.basename(found["models"][0])}


def api_higgs_install(body):
    """Host only, and never without the confirmation the page shows first."""
    if str((body or {}).get("action", "")) == "cancel":
        if HIGGS_INSTALL["running"]:
            HIGGS_INSTALL["cancel"] = True
        return {"ok": True}
    if HIGGS_INSTALL["running"]:
        return {"error": "an install is already running"}
    if not (body or {}).get("confirm"):
        return {"error": "not confirmed"}
    if str((body or {}).get("action", "")) == "dismiss":
        HIGGS_INSTALL.update(done=False, error="", step="", warn="")
        return {"ok": True}
    HIGGS_INSTALL.update(running=True, cancel=False, step="", pct=0.0, error="",
                         done=False, engine="", model="", warn="")
    threading.Thread(target=higgs_install_worker, daemon=True).start()
    return {"ok": True}


ACPP_VER_RX = re.compile(r"release-\d+\.\d+(?:\.\d+)?|(?<![\w.])\d+\.\d+\.\d+(?![\w.])")


def acpp_local_version(cfg=None):
    """The installed audio.cpp version, by whatever means there is.

    audiocpp_server answers no --version, so this tries what might: the tag the panel
    recorded when IT installed, then a running server's own /health or /v1/models, then
    the file's Windows version resource, then a version in whatever the archive shipped
    beside it. Any of these may be absent - returning "" and saying so is better than
    inventing a number.
    """
    cfg = cfg or load_config()
    st = cfg.get("settings", {})
    tag = (st.get("ttsAcppVersion") or "").strip()
    if tag:
        return tag
    exe = find_acpp_exe(st.get("ttsAcppDir", ""))
    if not exe:
        return ""

    # 2. a running server may say. Only when it is actually up, and briefly.
    try:
        if slot_status(tts_server_port(cfg)).get("state") == "serving":
            base = "http://127.0.0.1:%d" % tts_server_port(cfg)
            for path in ("/health", "/v1/models"):
                try:
                    with urlopen(Request(base + path,
                                         headers={"User-Agent": "PandorumLLM"}),
                                 timeout=2) as r:
                        txt = r.read(8192).decode("utf-8", "replace")
                    for key in ("version", "build", "commit", "revision"):
                        m = re.search(r'"[^"]*%s[^"]*"\s*:\s*"([^"]{1,40})"' % key, txt, re.I)
                        if m and re.search(r"\d", m.group(1)):
                            return m.group(1)
                except Exception:
                    continue
    except Exception:
        pass

    # 3. the server's own startup output, which the panel already captures
    try:
        with open(os.path.join(log_dir(cfg), TTS_SERVER_LOG_NAME), "rb") as f:
            head = f.read(65536).decode("utf-8", "replace")
        for line in head.splitlines()[:120]:
            if re.search(r"version|build|audio\.cpp", line, re.I):
                m = ACPP_VER_RX.search(line)
                if m:
                    return m.group(0)
    except Exception:
        pass

    # 4. the file's own version resource, if the build carries one. PowerShell reads it
    # in one line; parsing PE resources in Python for a label is not worth it.
    try:
        ps = ("$v=(Get-Item -LiteralPath %s).VersionInfo; "
              "if ($v.FileVersion) { $v.FileVersion } elseif ($v.ProductVersion) "
              "{ $v.ProductVersion }" % json.dumps(exe))
        r = subprocess.run(["pwsh", "-NoProfile", "-Command", ps],
                           capture_output=True, text=True, timeout=12, **NOWIN)
        got = (r.stdout or "").strip().splitlines()
        if got and re.search(r"\d", got[0]) and got[0].strip("0. ") != "":
            return got[0].strip()
    except Exception:
        pass

    # 5. whatever the archive shipped alongside it
    for name in ("README.md", "README.txt", "VERSION", "version.txt", "CHANGELOG.md"):
        path = os.path.join(os.path.dirname(exe), name)
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                m = ACPP_VER_RX.search(f.read(8192))
            if m:
                return m.group(0)
        except OSError:
            continue
    return ""


def api_acpp_update(body=None):
    """Newest audio.cpp release, and the installed one if the binary will say.

    Same terms as the llama.cpp check: only when the button is pressed, a plain GET of a
    public release page, nothing about the setup is sent.
    """
    out = {"tag": "", "local": "", "url": "https://github.com/%s/releases" % ACPP_REPO}
    try:
        rq = Request("https://api.github.com/repos/%s/releases/latest" % ACPP_REPO,
                     headers={"User-Agent": "PandorumLLM", "Accept": "application/vnd.github+json"})
        data = json.loads(urlopen(rq, timeout=10).read().decode("utf-8"))
        out["tag"] = str(data.get("tag_name") or "").strip()
        out["url"] = str(data.get("html_url") or out["url"])
        out["published"] = str(data.get("published_at") or "")[:10]
    except HTTPError as e:
        return {"error": ("github.com refused the request (rate limit) - try again shortly"
                          if e.code == 403 else "github.com returned HTTP %s" % e.code)}
    except Exception as e:
        return {"error": "could not reach github.com (%s)" % str(e)[:80]}
    _cfg = load_config()
    _st = _cfg.get("settings", {})
    out["local"] = acpp_local_version(_cfg)      # recorded at install, or read on disk
    exe = find_acpp_exe(_st.get("ttsAcppDir", ""))
    if exe:
        out["exe"] = exe
        for flag in ("--version", "-v"):     # not documented; try, do not insist
            try:
                r = subprocess.run([exe, flag], capture_output=True, text=True, timeout=15,
                                   **NOWIN,
                                   cwd=os.path.dirname(exe) or None)
                m = re.search(r"\b\d+\.\d+(\.\d+)?\b", (r.stdout or "") + (r.stderr or ""))
                if m:
                    out["local"] = m.group(0)
                    break
            except Exception:
                pass
    return out


def tts_save_named(src_bytes, npc, cfg=None):
    """Keep a named copy of a generated line in the user's chosen folder.

    The served file has to stay in the wrapper's own temp folder because
    /gradio_api/file= is jailed to it - so this is a copy alongside, exactly as the
    reference wrapper did: a temp file to serve and a readable one to keep.

    Names match that wrapper too: <Npc>_<YYYYMMDD_HHMMSS>.wav. Nothing here is pruned;
    the folder is the user's, and deleting from it uninvited would be worse than growth.
    """
    out = (( cfg or load_config()).get("settings", {}).get("ttsOutDir") or "").strip()
    if not out:
        return ""
    try:
        os.makedirs(out, exist_ok=True)
        safe = re.sub(r"[^A-Za-z0-9_-]+", "_", str(npc or "voice")).strip("_") or "voice"
        path = os.path.join(out, "%s_%s.wav" % (safe, time.strftime("%Y%m%d_%H%M%S")))
        n = 1
        while os.path.exists(path):                # same second, same speaker
            path = os.path.join(out, "%s_%s-%d.wav"
                                % (safe, time.strftime("%Y%m%d_%H%M%S"), n))
            n += 1
        with open(path, "wb") as f:
            f.write(src_bytes)
        return path
    except Exception as e:
        log_error("tts", "could not save into the output folder %s: %s" % (out, e))
        return ""


def tts_diagnose(cfg=None, since=None):
    """Turn an audio.cpp crash into something a person can act on.

    A dropped connection reads as WinError 10054 on our side and says nothing. The
    server's own log usually says exactly what happened one line earlier, so read the
    tail of it and translate. Three separate failures this session were the same
    single-architecture CUDA build, each time unrecognisable from the panel's side.
    """
    try:
        path = os.path.join(log_dir(cfg or load_config()), TTS_SERVER_LOG_NAME)
        with open(path, "rb") as f:
            f.seek(0, 2)
            end = f.tell()
            # THIS run only. The log spans every start, so reading a blind tail reported
            # the previous failure again after the cause had been fixed.
            start = max(0, end - 8192) if since is None else min(max(0, since), end)
            f.seek(start)
            tail = f.read().decode("utf-8", "replace")
    except Exception:
        return ""
    for needle, hint in TTS_HINTS:
        if needle in tail:
            return hint
    return ""


def tts_pick_fields(fields):
    """Find the text and the reference voice in a Gradio call.

    SkyrimNet's Zonos and Chatterbox interfaces both speak Gradio but send different
    argument lists. Indexing by position is right for Zonos and silently wrong for
    anything else - it lands on a number or a flag and the reference never arrives.
    Keep the proven positions when they hold, and fall back to shape when they do not:
    the reference is the only dict carrying a "path", and the text is the longest string
    that is not a language tag.
    """
    text = fields[1] if len(fields) > 1 and isinstance(fields[1], str) else ""
    ref = None
    if len(fields) > 3 and isinstance(fields[3], dict) and fields[3].get("path"):
        ref = tts_speaker_path(fields[3])
        return text, ref
    for f in fields:                                  # another engine's argument list
        if isinstance(f, dict) and f.get("path"):
            ref = tts_speaker_path(f)
            break
    if not text or _TTS_LANG_RX.match(text.strip()):
        best = ""
        for f in fields:
            if isinstance(f, str) and not _TTS_LANG_RX.match(f.strip()) and len(f) > len(best):
                best = f
        text = best
    return text, ref


# ---- local reference clips ------------------------------------------------------
# SkyrimNet resamples every reference to 16 kHz before uploading it - including the
# 44.1 kHz files in its own voice-samples folder - which throws away everything above
# 8 kHz. Higgs runs at 24 kHz and has room for far more, so a clip read straight off
# disk clones noticeably better than the same clip round-tripped through the mod.
#
# The key is the upload's filename, which is the voicetype: femalenord.wav,
# malecommoner.wav, or a character name like serana.wav. Idea and naming scheme from
# cleanestpoison/higgs3-tts-skyrimnet (Apache-2.0).
#
# .wav only here. The reference implementation accepts six formats because it has
# FFmpeg; this panel is stdlib-only, and MOSS is handed the bytes rather than a path.
_voice_index = {"dir": "", "mtime": None, "map": {}}


def tts_voice_index(cfg=None):
    d = ((cfg or load_config()).get("settings", {}).get("ttsVoiceDir") or "").strip()
    if not d or not os.path.isdir(d):
        _voice_index.update(dir="", mtime=None, map={})
        return {}
    try:
        mt = os.stat(d).st_mtime
    except OSError:
        return {}
    if _voice_index["dir"] == d and _voice_index["mtime"] == mt:
        return _voice_index["map"]
    out = {}
    try:
        for n in sorted(os.listdir(d)):
            full = os.path.join(d, n)
            if os.path.isfile(full) and n.lower().endswith(".wav"):
                out[os.path.splitext(n)[0].lower()] = full
    except OSError:
        return _voice_index["map"]
    _voice_index.update(dir=d, mtime=mt, map=out)
    panel_log("[tts] local voices: %d clip(s) in %s" % (len(out), d))
    return out


def tts_local_sample(upload_path, cfg=None):
    """A local clip matching the upload's filename, or "" if there is none."""
    if not upload_path:
        return ""
    # split on BOTH separators: os.path.basename ignores "\\" off Windows, which is the
    # same trap api_tts_import hit in v3.71
    leaf = re.split(r"[\\/]", str(upload_path))[-1]
    stem = os.path.splitext(leaf)[0].lower()
    return tts_voice_index(cfg).get(stem, "")


def tts_ref_canonical(path):
    """Make sure a reference on disk is one a strict WAV reader can parse.

    Normalising at save_upload is not enough on its own: SkyrimNet HEADs the path first
    and skips the upload when it gets a 200, so a file cached by an older build is never
    re-sent and never re-normalised. Rewrite it in place the first time it is used.
    After that the check costs 44 bytes.
    """
    try:
        with open(path, "rb") as f:
            head = f.read(44)
        if len(head) >= 40 and head[:4] == b"RIFF" and head[36:40] == b"data":
            return path                      # canonical already
        with open(path, "rb") as f:
            data = f.read()
        clean = tts_wav_normalize(data)
        if clean and clean != data:
            with open(path, "wb") as f:
                f.write(clean)
            panel_log("[tts] rewrote a stale reference: %s (%d -> %d bytes)"
                      % (os.path.basename(path), len(data), len(clean)))
    except Exception as e:
        log_error("tts", "could not normalise the reference %s: %s" % (path, e))
    return path


def tts_engine_label(cfg=None):
    cfg = cfg or load_config()
    if tts_engine(cfg) != "audiocpp":
        return "MOSS-TTS"
    sel = (cfg.get("settings", {}).get("ttsAcppModel") or "").strip()
    return "audio.cpp" + ((" (" + re.split(r"[\\/]", sel)[-1] + ")") if sel else "")


def tts_gpu_label(cfg=None):
    """The card the server was pinned to, by name where we know it."""
    cfg = cfg or load_config()
    want = (cfg.get("settings", {}).get("ttsGpuId") or "").strip()
    for g in cfg.get("gpus", []) or []:
        if want and str(g.get("uuid", "")) == want:
            return str(g.get("name") or want)
    return want or "default device"


def tts_engine(cfg=None):
    return str((cfg or load_config()).get("settings", {}).get("ttsEngine", "moss")).lower()


def tts_acpp_config(cfg=None):
    """The server.json audio.cpp is started with.

    The panel owns this file - a user editing it by hand would be overwritten on the
    next Start, which is why the GPU is pinned by env instead of the "device" key:
    CUDA_VISIBLE_DEVICES masks to one card and that card is then index 0 in-process,
    exactly as --main-gpu 0 works for the llama.cpp fleet.

    lazy_load is left off deliberately. Eager loading means /health answering is a real
    readiness signal, which is what the Start button waits on; with lazy loading the
    server would report ok before the model existed.
    """
    cfg = cfg or load_config()
    st = cfg.get("settings", {})
    fam = (st.get("ttsAcppFamily") or "higgs_audio_tts")
    try:
        slots = max(1, min(int(str(st.get("ttsAcppRefSlots", "64")).strip() or 64), 1024))
    except Exception:
        slots = 64
    return json.dumps({
        "host": "0.0.0.0",
        "port": tts_server_port(cfg),
        "backend": "cuda",
        "device": 0,
        "threads": 1,
        "models": [{
            "id": (st.get("ttsAcppModelId") or "higgs"),
            "family": fam,
            "path": (st.get("ttsAcppModel") or "").replace("\\", "/"),
            "task": "tts",
            "mode": "offline",
            # SkyrimNet gives TTS about 15s. The server queues a second request behind
            # the first, so without a bound a slow line stalls every line after it.
            "busy_timeout_ms": 20000,
            # The engine keeps encoded references in a cache whose default size is ONE.
            # A conversation alternates speakers, so at one slot practically every line
            # re-encodes its reference. One entry per voice you actually meet.
            "session_options": {
                "%s.reference_cache_slots" % fam: slots,
            },
        }],
    }, indent=2)


def tts_acpp_speak(url_base, model_id, text, ref_path, ref_text=""):
    """POST /v1/audio/speech and return WAV bytes.

    voice_ref is a server-local PATH, not base64 - the Gradio front has already written
    the uploaded sample to disk, so it is passed straight through. That only holds while
    the panel and audio.cpp are on the same machine, which they are by construction: the
    panel starts the process.
    """
    body = {"model": model_id, "input": text}
    if ref_path:
        body["voice_ref"] = ref_path
        if ref_text:
            body["reference_text"] = ref_text
    req = _ureq.Request(url_base.rstrip("/") + "/v1/audio/speech",
                        data=json.dumps(body).encode("utf-8"),
                        headers={"Content-Type": "application/json"}, method="POST")
    try:
        r = _ureq.urlopen(req, timeout=120)
    except _uerr.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", "replace")[:400].strip()
        except Exception:
            pass
        raise RuntimeError("HTTP %s from %s%s" % (e.code, url_base,
                                                  (" - " + detail) if detail else ""))
    with r:
        data = r.read()
    return data, {k.lower(): v for k, v in r.getheaders()}


def tts_server_port(cfg=None):
    try:
        return int(str((cfg or load_config()).get("settings", {}).get("ttsServerPort") or "1240"))
    except Exception:
        return 1240


def tts_server_status(cfg=None):
    """Cached, resolver-free probe - same one the fleet slots use, so this costs no
    more on a state read than one more server would."""
    port = tts_server_port(cfg)
    out = dict(slot_status(port))
    out["port"] = port
    # A server that dies while loading never opens the port, and nothing here noticed -
    # the panel sat on "waiting for it to answer" for ever. Reap it and say why.
    proc = TTS_PROC.get("proc")
    if proc is not None and proc.poll() is not None and not TTS_PROC.get("stopping"):
        code = proc.returncode
        TTS_PROC["pid"], TTS_PROC["proc"] = None, None
        hint = tts_diagnose(cfg, TTS_PROC.get("log_at"))
        TTS_PROC["died"] = ("the server stopped while starting (exit %s)%s"
                            % (code, (" - " + hint) if hint else ""))
        log_error("tts", TTS_PROC["died"])
        TTSW.log("\u274C %s" % TTS_PROC["died"])
    out["pid"] = TTS_PROC.get("pid")
    out["stopping"] = bool(TTS_PROC.get("stopping"))
    out["died"] = TTS_PROC.get("died") or ""
    return out


TTS_PROC = {"pid": None, "proc": None, "stopping": False, "said_ready": False,
            "died": "", "log_at": None}


def stop_tts_server(reason="", wait=True):
    """Stop the TTS server IF THE PANEL STARTED IT.

    Deliberately not "whatever holds the port": with the panel acting only as launcher
    writer, the server belongs to the user's own launcher and must outlive the panel.
    The panel cleans up what it started, nothing else.

    wait=False terminates on a thread and reports "stopping" until the process is gone.
    Unloading a large model is not instant, and a synchronous stop blocks the very
    response that would have told the page anything was happening - so the shutdown was
    real but unobservable. The exit path still waits, since the process is about to end.
    """
    p = TTS_PROC.get("proc")
    pid = TTS_PROC.get("pid")
    if not p and not pid:
        return False
    TTS_PROC["stopping"] = True
    TTSW.log("")
    TTSW.log("\U0001F6D1 Stopping the TTS server%s..." % ((" - " + reason) if reason else ""))
    try:
        with _ST_LOCK:
            _ST_CACHE.pop(tts_server_port(), None)
        sse_notify("state")          # say so BEFORE blocking, not after
    except Exception:
        pass

    def _finish():
        try:
            if p and p.poll() is None:
                p.terminate()
                try: p.wait(timeout=6)
                except Exception: p.kill()
            panel_log("[tts] stopped the server (pid %s)%s" % (pid, (" - " + reason) if reason else ""))
        except Exception as e:
            log_error("tts", "could not stop the server: %s" % e)
        TTS_PROC["pid"], TTS_PROC["proc"] = None, None
        TTS_PROC["stopping"] = False
        TTSW.log("\u2705 TTS server stopped")
        TTSW.log("")
        try:
            with _ST_LOCK:
                _ST_CACHE.pop(tts_server_port(), None)
            sse_notify("state")
        except Exception:
            pass

    if wait:
        _finish()
    else:
        threading.Thread(target=_finish, daemon=True).start()
    return True


def api_tts_server(body):
    """Start or stop the TTS server. Host-only: absent from REMOTE_POST_OK."""
    if not _TTSSRV_LOCK.acquire(blocking=False):
        return {"error": "a TTS start or stop is already running"}
    try:
        return _api_tts_server(body)
    finally:
        _TTSSRV_LOCK.release()


def _api_tts_server(body):
    action = str(body.get("action", "")).lower()
    cfg = load_config()
    st = cfg.get("settings", {})
    port = tts_server_port(cfg)

    if action == "stop":
        stop_tts_server("stop button", wait=False)
        _kill_port_owner(port)        # also catches a server the panel did not start
        with _ST_LOCK:
            _ST_CACHE.pop(port, None)      # do not report a stale "serving"
        panel_log("[tts] stopped the server on :%d" % port)
        return {"ok": True, "status": tts_server_status(cfg)}

    if action != "start":
        return {"error": "unknown action"}

    cur = slot_status(port)
    if cur.get("state") in ("serving", "loading"):
        return {"ok": True, "already": True, "status": tts_server_status(cfg)}

    eng = tts_engine(cfg)
    if eng == "audiocpp":
        exe = find_acpp_exe(st.get("ttsAcppDir", "")) or (st.get("ttsAcppExe") or "").strip()
        model = (st.get("ttsAcppModel") or "").strip()
        if not exe or not os.path.isfile(exe):
            return {"error": "no %s found under %s" % (ACPP_EXE_NAME,
                              st.get("ttsAcppDir") or "(no folder set)")}
        if not model or not os.path.exists(model):
            # a .gguf is a FILE, a safetensors layout is a FOLDER - both are valid
            return {"error": "audio.cpp model not found: %s" % (model or "(not set)")}
        if os.path.isdir(model) and any(n.lower().endswith(".gguf") for n in os.listdir(model)):
            return {"error": "that folder holds a .gguf, which audio.cpp loads instead of the "
                             "safetensors - pick the .gguf itself, or move it out"}
    else:
        exe = (st.get("ttsServerExe") or "").strip()
        model = (st.get("ttsModel") or "").strip()
        if not exe or not os.path.isfile(exe):
            return {"error": "TTS server binary not found: %s" % (exe or "(not set)")}
        if not model or not os.path.isfile(model):
            return {"error": "TTS model not found: %s" % (model or "(not set)")}

    gid = st.get("ttsGpuId") or ""
    gpu = next((g for g in cfg.get("gpus", []) if g.get("id") == gid), None)
    uuid_ = (gpu or {}).get("uuid") or ""
    env = os.environ.copy()
    if uuid_:
        # after masking, the chosen card re-indexes to 0 in-process, so --main-gpu
        # stays 0 rather than the physical index. Same trap as the launcher.
        env["CUDA_VISIBLE_DEVICES"] = uuid_
    if eng == "audiocpp":
        # the panel owns server.json; it is rewritten on every start
        cfgp = os.path.join(log_dir(cfg), "audiocpp-server.json")
        try:
            with open(cfgp, "wb") as f:
                f.write(tts_acpp_config(cfg).encode("utf-8"))
        except Exception as e:
            return {"error": "cannot write the audio.cpp config: %s" % e}
        args = [exe, "--config", cfgp]
    else:
        args = [exe, "--model", model, "--main-gpu", "0", "--host", "0.0.0.0",
                "--port", str(port), "--no-webui"]

    try:
        logf = open(os.path.join(log_dir(cfg), TTS_SERVER_LOG_NAME), "ab")
    except Exception as e:
        return {"error": "cannot open the server log: %s" % e}
    flags = 0
    if os.name == "nt":       # no console window, and its own group so a Ctrl+C
        flags = 0x08000000 | 0x00000200   # in the panel's console does not reach it
    try:
        p = subprocess.Popen(args, env=env, stdout=logf, stderr=subprocess.STDOUT,
                             cwd=os.path.dirname(exe) or None, creationflags=flags)
    except Exception as e:
        try: logf.close()
        except Exception: pass
        return {"error": "could not start the server: %s" % e}
    try:
        logf.close()      # the child holds its own duplicate; keeping ours leaks a
    except Exception:     # handle on every start
        pass
    try:                       # where this run's output begins in the shared log
        TTS_PROC["log_at"] = os.path.getsize(os.path.join(log_dir(cfg), TTS_SERVER_LOG_NAME))
    except OSError:
        TTS_PROC["log_at"] = 0
    TTS_PROC["pid"], TTS_PROC["proc"], TTS_PROC["died"] = p.pid, p, ""
    with _ST_LOCK:
        _ST_CACHE.pop(port, None)
    panel_log("[tts] started %s on :%d (pid %d)" % (os.path.basename(exe), port, p.pid))
    TTSW.log("")
    TTSW.log("\U0001F680 Loading %s..." % tts_engine_label(cfg))
    TTSW.log("\U0001F527 Using device: cuda (%s)" % tts_gpu_label(cfg))
    TTSW.log("\u23F3 Waiting for the model to load - the first line is always the slowest")
    sse_notify("state")
    return {"ok": True, "started": True, "pid": p.pid, "status": tts_server_status(cfg)}


def api_launcher_content(body):
    cfg = load_config()
    path = os.path.abspath(body.get("path", ""))
    if not _within(path, _all_roots(cfg)):
        return {"error": "path outside the allowed folders"}
    try:
        return {"content": open(path, encoding="utf-8-sig", errors="replace").read(), "path": path}
    except Exception as e:
        return {"error": str(e)}

def fmt_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return ("%.1f %s" if unit != "B" else "%d %s") % (n, unit)
        n /= 1024.0

def api_logs():
    ld = log_dir()
    out = []
    for n in os.listdir(ld):
        p = os.path.join(ld, n)
        if not os.path.isfile(p):
            continue
        stt = os.stat(p)
        out.append({"name": n, "size": fmt_size(stt.st_size), "bytes": stt.st_size,
                    "created": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stt.st_ctime)),
                    "modified": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stt.st_mtime))})
    out.sort(key=lambda x: x["modified"], reverse=True)
    return {"dir": ld, "files": out}

def api_tail(body, scope="host"):
    ld = log_dir()
    kind = body.get("kind", "")
    if kind in ("dashboard", "thinking"):
        # Only THIS session's file. The fleet names its logs per launch, so before the
        # first launch the newest one belongs to the previous run - showing it looked
        # like the terminal had not cleared.
        files = sorted(glob.glob(os.path.join(ld, "*_%s.log" % kind)),
                       key=os.path.getmtime, reverse=True)
        path = None
        for f in files:
            if os.path.getmtime(f) >= PANEL_START - 2.0:
                path = f
                break
        if path is None and files:
            return {"text": "(waiting for this session - the last log is from a previous "
                            "run of the panel)", "file": ""}
    elif kind == "tts":
        # a fixed feed, NOT kind=file: one known name inside the log folder. It carries
        # no caller-supplied path, so the remote objection to kind=file does not apply,
        # and this stays readable on remote like the other three terminals.
        path = os.path.join(ld, TTS_LOG_NAME)
        if not os.path.isfile(path):
            path = None
    elif kind == "file":
        name = os.path.basename(body.get("name", ""))
        path = os.path.join(ld, name)
        if not os.path.isfile(path):
            path = None
    else:
        return {"error": "bad kind"}
    if not path:
        if kind == "tts":
            return {"text": "(no %s yet - run the TTS launcher; it writes into the panel log folder)" % TTS_LOG_NAME, "file": ""}
        return {"text": "(no log file yet - hit [Launch] first, or check the log folder in [Setup])", "file": ""}
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - 131072))
            text = ANSI_RX.sub("", f.read().decode("utf-8", errors="ignore"))
        lines = text.splitlines()[-400:]
        text = "\n".join(lines)
        if scope != "host":
            # decided at the boundary, not in the page: a remote reader must never be
            # sent a path, whichever program wrote the line
            text = _mask_paths_in(text)
        return {"text": text, "file": os.path.basename(path)}
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------- embedded SN proxy
# Ported from SkyrimNet-Proxy.py: per-provider listeners forwarding to the server
# slot each provider currently sits in. Keeps the Diary GBNF grammar rail, the
# GPU priority gate (keyed on each slot's editable "gpu" tag), reasoning_content
# harvesting (per-provider thinking toggle) and the dashboard/thinking log files.
import urllib.request as _ureq, urllib.error as _uerr, datetime as _dt

DIARY_GRAMMAR = r"""
root   ::= "{" space "\"importance_score\"" space ":" space number "," space "\"emotion\"" space ":" space string "," space "\"content\"" space ":" space string space "}"
number ::= ("0" | [1-9] [0-9]*) ("." [0-9]+)?
string ::= "\"" ( [^"\\\x00-\x1F] | "\\" (["\\bfnrt/] | "u" [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F]) )* "\""
space  ::= [ \t\n]*
"""
AGENT_EMOJI = {"Dialogue":"\U0001F4AC","GM":"\U0001F3B2","Combat":"\u2694\uFE0F","Meta":"\U0001F9EA",
               "UT":"\U0001F310","AI-Assistant":"\U0001F916","ActionEval":"\U0001F3C3","Charbio":"\U0001F3AD",
               "Diary":"\u270D\uFE0F","Memory":"\U0001F9E0","Vision":"\U0001F441\uFE0F",
               "IntelEngine":"\U0001F6F0\uFE0F","SeverActions":"\U0001F4DC"}
GATE_MAX_WAIT_S = 8.0
PROXY_MAX_BODY = 64 * 1024 * 1024   # far beyond any real prompt, but bounded

class GpuGate:
    def __init__(self):
        import threading
        self._cond = threading.Condition()
        self._active_high = {}
    def enter(self, gpu, is_high):
        if is_high:
            with self._cond:
                self._active_high[gpu] = self._active_high.get(gpu, 0) + 1
            return 0
        t0 = time.time(); deadline = t0 + GATE_MAX_WAIT_S
        with self._cond:
            while self._active_high.get(gpu, 0) > 0:
                rem = deadline - time.time()
                if rem <= 0: break
                self._cond.wait(timeout=rem)
        return round((time.time() - t0) * 1000)
    def leave(self, gpu, is_high):
        if not is_high: return
        with self._cond:
            self._active_high[gpu] = max(0, self._active_high.get(gpu, 0) - 1)
            if self._active_high[gpu] == 0: self._cond.notify_all()

def _stamp():
    return _dt.datetime.now().strftime("%H:%M:%S.%f")[:-4]

# ---- streaming statistics: O(1) memory. We keep only a running mean+count, or a
# running sum - never a list of samples. mean_new = mean + (x - mean)/n is the exact
# running average, so figures are correct without any per-request accumulation. ----
def _fold_mean(agg, key, x):
    if x is None: return
    try: x = float(x)
    except Exception: return
    n = agg.get(key + "N", 0) + 1
    agg[key] = agg.get(key, 0.0) + (x - agg.get(key, 0.0)) / n
    agg[key + "N"] = n

def _fold_sum(agg, key, x):
    if x is None: return
    try: agg[key] = agg.get(key, 0.0) + float(x)
    except Exception: pass

class ProxyManager:
    def __init__(self):
        import threading
        self._lock = threading.Lock()
        self._servers = {}      # port -> ThreadingHTTPServer
        self.routes = {}        # port -> route dict
        self.stats = {}         # provider id -> {"n":int,"last":str}
        self.observed = {}      # provider id -> {"temp":..,"top_p":..} last-seen request sampler params
        self.sstats = {}        # server port(str) -> running perf/usage aggregates (session, in-memory)
        self.pstats = {}        # provider id -> running perf/usage aggregates (session, in-memory)
        self.stats_on = True    # Monitoring toggle (settings.statsMonitoring)
        self.gate = GpuGate()
        self.allow = None
        self.session = time.strftime("%Y%m%d-%H%M%S")

    def _desired(self, cfg):
        out = {}
        gpu_ids = {g.get("id") for g in cfg.get("gpus", [])}
        for s in cfg.get("slots", []):
            up = (parse_ps1_port(s.get("script") or "") if s.get("script") else None) or s.get("port")
            for p in s.get("providers", []) or []:
                if p.get("enabled") is False:
                    continue
                try: lp = int(p.get("port"))
                except Exception: continue
                if not (1000 <= lp <= 9999) or lp in out or lp == PORT: continue
                gid = s.get("gpuId") or ""
                gkey = gid if gid in gpu_ids else (s.get("gpu") or s.get("id"))
                out[lp] = {"id": p.get("id"), "title": p.get("title") or "?",
                           "emoji": (p.get("emoji") or AGENT_EMOJI.get(p.get("title", ""), "\u2022")),
                           "thinking": bool(p.get("thinking")), "priority": int(p.get("priority", 1)),
                           "grammar": bool(p.get("diaryGrammar")), "gpu": gkey,
                           "overrides": {k: v for k, v in (p.get("samplerOverrides") or {}).items()
                                         if k in PROXY_SAMPLER_FIELDS and str(v).strip() != ""},
                           "sampSource": (p.get("samplerSource") or "server"),
                           "upstream": "http://127.0.0.1:%d" % int(up), "server": str(up)}
        return out

    def sync(self):
        cfg = load_config()
        want = self._desired(cfg)
        st = cfg.get("settings", {})
        self.stats_on = bool(st.get("statsMonitoring", True))
        allow = None
        if st.get("remoteIp"):
            allow = {"127.0.0.1", st["remoteIp"]}
            if st.get("panelIp"): allow.add(st["panelIp"])
        with self._lock:
            self.allow = allow
            self.routes = want
            for lp in [p for p in self._servers if p not in want]:
                try:
                    srv = self._servers.pop(lp)
                    import threading
                    threading.Thread(target=srv.shutdown, daemon=True).start()
                    panel_log("[proxy] closed listener :%d" % lp)
                except Exception: pass
            for lp in [p for p in want if p not in self._servers]:
                try:
                    srv = _QuietServer(("0.0.0.0", lp), _mk_handler(self, lp))
                    self._servers[lp] = srv
                    import threading
                    threading.Thread(target=srv.serve_forever, daemon=True).start()
                    panel_log("[proxy] listening :%d -> %s" % (lp, want[lp]["title"]))
                except OSError as e:
                    panel_log("[proxy] FAILED to bind :%d (%s)" % (lp, e))
                    log_error("proxy", "failed to bind :%d (%s)" % (lp, e))
        return {"listening": sorted(self._servers)}

    def report(self, rt, think, usage, timings, ms, wait_ms):
        inp = out = pf = dc = None
        if timings:
            inp, out = timings.get("prompt_n"), timings.get("predicted_n")
            pf, dc = timings.get("prompt_per_second"), timings.get("predicted_per_second")
        if inp is None and usage: inp = usage.get("prompt_tokens")
        if out is None and usage: out = usage.get("completion_tokens")
        tn = round(len(think) / 4) if think else 0
        emoji = rt.get("emoji") or "\u2022"
        line = ("[%s] %s %-13s [%s]  %6s / %5s %-8s tok  %5s / %3s tps  %8.3f sec  %s" % (
            _stamp(), emoji, rt["title"], rt["server"],
            inp if inp is not None else "?", out if out is not None else "?",
            ("(~%d)" % tn) if tn else "", ("%.0f" % float(pf)) if pf else "?",
            ("%.0f" % float(dc)) if dc else "?", ms / 1000.0,
            ("+%d ms" % wait_ms) if wait_ms > 0 else ""))
        ld = log_dir()
        try:
            with open(os.path.join(ld, "%s_dashboard.log" % self.session), "a", encoding="utf-8") as f:
                f.write(line.rstrip() + "\n")
            if think and think.strip():
                with open(os.path.join(ld, "%s_thinking.log" % self.session), "a", encoding="utf-8") as f:
                    f.write("\n%s\n[%s] %s [%s]  (~%d tok est)\n%s\n%s\n" % (
                        "=" * 70, _stamp(), rt["title"], rt["server"], tn, "=" * 70, think.strip()))
        except Exception: pass
        st = self.stats.setdefault(rt["id"], {"n": 0, "last": ""})
        st["n"] += 1
        st["last"] = _stamp()[:8]
        if self.stats_on:
            self._fold_request(rt, inp, out, pf, dc, tn, timings, ms, wait_ms)
        sse_notify("tail")

    def _fold_request(self, rt, inp, out, pf, dc, tn, timings, ms, wait_ms):
        now = time.time()
        sa = self.sstats.setdefault(str(rt["server"]), {"gens": 0, "errors": 0, "loads": 0})
        sa["gens"] += 1; sa["ts"] = now
        _fold_mean(sa, "pp", pf); _fold_mean(sa, "tg", dc); _fold_mean(sa, "resp", ms)
        tot = (inp or 0) + (out or 0)
        _fold_sum(sa, "tokTot", tot); _fold_mean(sa, "tokAvg", tot); sa["recentTok"] = tot
        _fold_sum(sa, "thinkTot", tn); _fold_mean(sa, "thinkAvg", tn)
        _fold_sum(sa, "queueTot", wait_ms)
        if timings:
            cached = timings.get("prompt_cached_n") or timings.get("cache_n") or timings.get("n_cached") or timings.get("cached_n") or 0
            if cached:
                _fold_sum(sa, "cacheTok", cached)
                if pf: _fold_sum(sa, "cacheSavedMs", (float(cached) / float(pf)) * 1000.0)
            dn = timings.get("draft_n"); da = timings.get("draft_n_accepted")
            if dn:
                _fold_mean(sa, "mtpAmt", dn)
                if da is not None: _fold_mean(sa, "mtpAcc", (float(da) / float(dn)) * 100.0)
        pa = self.pstats.setdefault(rt["id"], {"gens": 0, "errors": 0, "title": rt["title"], "emoji": rt.get("emoji", "\u2022")})
        pa["gens"] += 1; pa["ts"] = now; pa["title"] = rt["title"]
        _fold_mean(pa, "gen", ms); _fold_mean(pa, "in", inp); _fold_mean(pa, "out", out); _fold_mean(pa, "think", tn)
        if timings:
            # llama.cpp reports the two halves of a generation separately
            _fold_mean(pa, "pfMs", timings.get("prompt_ms"))
            _fold_mean(pa, "dcMs", timings.get("predicted_ms"))

    def note_error(self, rt, kind):
        if not self.stats_on: return
        sa = self.sstats.setdefault(str(rt["server"]), {"gens": 0, "errors": 0, "loads": 0})
        sa["errors"] = sa.get("errors", 0) + 1; sa["lastErr"] = kind
        pa = self.pstats.setdefault(rt["id"], {"gens": 0, "errors": 0, "title": rt["title"], "emoji": rt.get("emoji", "\u2022")})
        pa["errors"] = pa.get("errors", 0) + 1

    def note_load(self, server_port):
        if not self.stats_on: return
        sa = self.sstats.setdefault(str(server_port), {"gens": 0, "errors": 0, "loads": 0})
        sa["loads"] = sa.get("loads", 0) + 1

    def stats_snapshot(self, remote=False):
        cfg = load_config()
        slot_by_port = {}
        for s in cfg.get("slots", []):
            up = (parse_ps1_port(s.get("script") or "") if s.get("script") else None) or s.get("port")
            slot_by_port[str(up)] = {"label": s.get("label") or ("port " + str(up)),
                                     "model": (parse_ps1_model(s["script"]) if s.get("script") else "") or ""}
        servers = []
        for port, a in self.sstats.items():
            meta = slot_by_port.get(str(port), {"label": "port " + str(port), "model": ""})
            row = dict(a)
            row["port"] = port
            row["label"] = "server" if remote else meta["label"]
            row["model"] = "" if remote else meta["model"]
            servers.append(row)
        providers = []
        for pid, a in self.pstats.items():
            row = dict(a); row["id"] = pid
            if remote: row["title"] = "provider"
            providers.append(row)
        return {"monitoring": self.stats_on, "session": self.session, "servers": servers, "providers": providers}

PROXY = ProxyManager()

class _QuietServer(ThreadingHTTPServer):
    daemon_threads = True
    # socketserver defaults the listen backlog to 5. A browser opens several
    # connections at once (page, state, tail, the event stream) and a second tab or a
    # remote viewer doubles that, so the surplus was being dropped rather than queued.
    request_queue_size = 128
    def handle_error(self, request, client_address):
        pass  # dropped sockets (WinError 10054 etc.) are expected, not actionable

def _mk_handler(mgr, listen_port):
    class _P(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        def log_message(self, *a): pass
        def do_GET(self): self._proxy()
        def do_POST(self): self._proxy()
        def do_DELETE(self): self._proxy()

        def _forward(self, rt, body):
            req = _ureq.Request(rt["upstream"] + self.path, data=body, method=self.command)
            for k, v in self.headers.items():
                if k.lower() in ("host", "content-length", "connection", "accept-encoding"): continue
                req.add_header(k, v)
            req.add_header("Accept-Encoding", "identity")
            return _ureq.urlopen(req, timeout=600)

        def _send_head(self, resp, streaming):
            self.send_response(getattr(resp, "code", None) or resp.status)
            for k, v in resp.headers.items():
                if k.lower() in ("transfer-encoding", "content-length", "connection"): continue
                self.send_header(k, v)
            self.send_header("Connection", "close")
            if streaming: self.end_headers()

        def _proxy(self):
            rt = mgr.routes.get(listen_port)
            if not rt:
                self.send_response(503); self.end_headers(); return
            if mgr.allow is not None and self.client_address[0] not in mgr.allow:
                self.send_response(403); self.send_header("Connection", "close"); self.end_headers()
                log_error("proxy", "rejected %s on :%d (not in IP allowlist)" % (self.client_address[0], listen_port))
                return
            length = int(self.headers.get("Content-Length", 0) or 0)
            if length > PROXY_MAX_BODY:      # a chat request is kilobytes; never allocate
                self.send_response(413)      # whatever a caller claims
                self.send_header("Content-Length", "0"); self.end_headers()
                log_error("proxy", "refused a %d byte body on :%d" % (length, listen_port))
                return
            body = self.rfile.read(length) if length else None
            note_speaker(body)          # reads a name, keeps nothing else
            is_chat = wants_stream = False
            if self.command == "POST" and self.path.startswith("/v1/chat/completions") and body:
                is_chat = True
                try: wants_stream = bool(json.loads(body).get("stream"))
                except Exception: pass
            if is_chat and body:
                try:
                    d = json.loads(body)
                    ck = d.setdefault("chat_template_kwargs", {})
                    if not rt.get("thinking"):
                        ck["enable_thinking"] = False
                    else:
                        ck.pop("enable_thinking", None)
                        if not ck:
                            d.pop("chat_template_kwargs", None)
                    # observe the sampler params SkyrimNet sent for THIS provider (by its port)
                    seen = {}
                    for _k, _field in PROXY_SAMPLER_FIELDS.items():
                        if _field in d and d[_field] is not None:
                            seen[_k] = _num_str(d[_field])
                    if seen and mgr.observed.get(rt["id"]) != seen:
                        mgr.observed[rt["id"]] = seen
                        try:
                            sse_notify("state")      # tell the page: these are new numbers
                        except Exception:
                            pass
                    # Server Side: the panel's values are final. SkyrimNet Side: pass through.
                    ov = (rt.get("overrides") or {}) if rt.get("sampSource", "server") == "server" else {}
                    for _k, _val in ov.items():
                        _field = PROXY_SAMPLER_FIELDS.get(_k)
                        if not _field:
                            continue
                        try:
                            d[_field] = int(_val) if _k == "top_k" else float(_val)
                        except Exception:
                            continue
                    body = json.dumps(d).encode("utf-8")
                except Exception:
                    pass
            if is_chat and rt["grammar"] and body:
                try:
                    obj = json.loads(body)
                    if "grammar" not in obj and "response_format" not in obj:
                        obj["grammar"] = DIARY_GRAMMAR
                        body = json.dumps(obj).encode("utf-8")
                except Exception: pass
            is_high = rt["priority"] == 0
            gate_held = is_chat
            wait_ms = mgr.gate.enter(rt["gpu"], is_high) if gate_held else 0
            t0 = time.time()
            try:
                try:
                    resp = self._forward(rt, body)
                except _uerr.HTTPError as e:
                    resp = e
                except _uerr.URLError as e:
                    msg = json.dumps({"error": {"message": "upstream %s unreachable: %s" % (rt["upstream"], e.reason)}}).encode()
                    self.send_response(502); self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(msg))); self.send_header("Connection", "close")
                    self.end_headers(); self.wfile.write(msg)
                    panel_log("[proxy] %s upstream down - 502" % rt["title"])
                    log_error("proxy " + rt["title"], "upstream %s unreachable" % rt["upstream"])
                    mgr.note_error(rt, "unreachable")
                    return
                except (ConnectionResetError, ConnectionError, OSError):
                    return
                if not is_chat:
                    data = resp.read()
                    self._send_head(resp, streaming=False)
                    self.send_header("Content-Length", str(len(data))); self.end_headers()
                    self.wfile.write(data); return
                if wants_stream:
                    self._send_head(resp, streaming=True)
                    think, usage, timings = [], None, None
                    while True:
                        line = resp.readline()
                        if not line: break
                        try:
                            self.wfile.write(line); self.wfile.flush()
                        except (ConnectionAbortedError, BrokenPipeError): break
                        s = line.strip()
                        if not s.startswith(b"data: ") or s == b"data: [DONE]": continue
                        try: obj = json.loads(s[6:])
                        except Exception: continue
                        if "timings" in obj: timings = obj["timings"]
                        if obj.get("usage"): usage = obj["usage"]
                        ch = obj.get("choices") or []
                        if ch and rt["thinking"]:
                            d = ch[0].get("delta", {})
                            if d.get("reasoning_content"): think.append(d["reasoning_content"])
                    mgr.report(rt, "".join(think), usage, timings, round((time.time() - t0) * 1000), wait_ms)
                    return
                data = resp.read(); ms = round((time.time() - t0) * 1000)
                self._send_head(resp, streaming=False)
                self.send_header("Content-Length", str(len(data))); self.end_headers()
                self.wfile.write(data)
                try:
                    j = json.loads(data); msg = j["choices"][0]["message"]
                    mgr.report(rt, (msg.get("reasoning_content") or "") if rt["thinking"] else "",
                               j.get("usage"), j.get("timings"), ms, wait_ms)
                except Exception:
                    panel_log("[proxy] %s unparseable - passed through" % rt["title"])
                    log_error("proxy " + rt["title"], "unparseable non-stream body")
                    mgr.note_error(rt, "parse")
            finally:
                if gate_held:
                    mgr.gate.leave(rt["gpu"], is_high)
    return _P

def api_provider_add(body):
    cfg = load_config()
    s = next((x for x in cfg.get("slots", []) if x.get("id") == body.get("slot")), None)
    if not s: return {"error": "unknown slot"}
    used = {p.get("id") for sl in cfg["slots"] for p in sl.get("providers", []) or []}
    n = 1
    while "prov%d" % n in used: n += 1
    ports = {int(p.get("port") or 0) for sl in cfg["slots"] for p in sl.get("providers", []) or []}
    np = 1251
    while np in ports or np == PORT: np += 1
    s.setdefault("providers", []).append({"id": "prov%d" % n, "title": "provider %d" % n,
                                          "port": np, "thinking": True, "priority": 1, "diaryGrammar": False, "custom": True})
    save_config(cfg); PROXY.sync()
    return {"ok": True}

def api_restore_servers(body):
    """Rebuild the shipped server slots with their default parameters and launchers.

    Providers are not thrown away with their slot - they are moved to the
    unallocated row so nothing the user configured is lost.
    """
    cfg = load_config()
    try:
        seed = json.loads(open(DEFAULT, encoding="utf-8-sig").read())
    except Exception as e:
        return {"error": "cannot read the shipped defaults: %s" % e}
    park = cfg.setdefault("unallocatedProviders", [])
    for s in cfg.get("slots", []) or []:
        for p in (s.get("providers") or []):
            park.append(p)
    slots = json.loads(json.dumps(seed.get("slots", []) or []))
    for s in slots:
        s["providers"] = []
        s["gpuId"] = ""
        s["params"] = param_defaults()
    cfg["slots"] = slots
    for s in slots:
        try:
            regen_slot_script(cfg, s)
        except Exception:
            pass
    save_config(cfg)
    try:
        PROXY.sync()
    except Exception:
        pass
    sse_notify("state")
    return {"ok": True, "servers": len(slots), "parked": len(park)}

def api_provider_restore_defaults(body):
    cfg = load_config()
    seed_default_providers(cfg)
    save_config(cfg)
    try:
        PROXY.sync()
    except Exception:
        pass
    return {"ok": True}

def api_provider_remove(body):
    cfg = load_config()
    for s in cfg.get("slots", []):
        pr = s.get("providers", []) or []
        target = next((p for p in pr if p.get("id") == body.get("id")), None)
        if target is not None:
            if not target.get("custom") or is_default_provider(target):
                return {"error": "default providers cannot be removed - use Disable, or Restore Default Providers to reset"}
            s["providers"] = [p for p in pr if p.get("id") != body.get("id")]
            save_config(cfg); PROXY.sync()
            return {"ok": True}
    return {"error": "unknown provider"}

def api_provider_edit(body):
    cfg = load_config()
    allp = ([(s, p) for s in cfg.get("slots", []) for p in s.get("providers", []) or []]
            + [(None, p) for p in cfg.get("unallocatedProviders", []) or []])
    hit = next(((s, p) for s, p in allp if p.get("id") == body.get("id")), None)
    if not hit: return {"error": "unknown provider"}
    s, p = hit
    if "samplerSource" in body:
        p["samplerSource"] = "skyrimnet" if str(body["samplerSource"]) == "skyrimnet" else "server"
    if "detectSN" in body:
        p["detectSN"] = bool(body["detectSN"])
    if "title" in body:
        p["title"] = str(body["title"]).strip()[:40] or p["title"]
    if "port" in body:
        ps = str(body["port"]).strip()
        if not re.fullmatch(r"\d{4}", ps):
            return {"error": "port has to be four numbers (1000-9999)"}
        np = int(ps)
        if any(pp is not p and int(pp.get("port") or 0) == np for _, pp in allp) or np == PORT:
            return {"error": "port %d is already taken" % np}
        p["port"] = np
    if "enabled" in body:
        p["enabled"] = bool(body["enabled"]) if not isinstance(body["enabled"], str) else body["enabled"].lower() in ("1", "true", "on")
    if "thinking" in body:
        p["thinking"] = bool(body["thinking"]) if not isinstance(body["thinking"], str) else body["thinking"].lower() in ("1", "true", "on")
    if "priority" in body:
        try:
            pv = int(str(body["priority"]).strip())
        except Exception:
            return {"error": "priority must be 0, 1 or 2"}
        if pv not in (0, 1, 2):
            return {"error": "priority must be 0, 1 or 2"}
        p["priority"] = pv
    if "emoji" in body:
        p["emoji"] = str(body["emoji"]).strip()[:8]
    if "enabled" in body:
        p["enabled"] = bool(body["enabled"]) if not isinstance(body["enabled"], str) else body["enabled"].lower() in ("1", "true", "on")
    save_config(cfg); PROXY.sync()
    return {"ok": True}

def api_provider_move(body):
    cfg = load_config()
    prov = None
    for s in cfg.get("slots", []):
        pr = s.get("providers", []) or []
        for p in pr:
            if p.get("id") == body.get("id"):
                prov = p; pr.remove(p); break
        if prov: break
    if not prov:
        un = cfg.setdefault("unallocatedProviders", [])
        for p in list(un):
            if p.get("id") == body.get("id"):
                prov = p; un.remove(p); break
    if not prov: return {"error": "unknown provider"}
    if not str(body.get("toSlot") or ""):
        cfg.setdefault("unallocatedProviders", []).append(prov)
        save_config(cfg); PROXY.sync(); sse_notify("state")
        return {"ok": True, "unallocated": True}
    dst = next((x for x in cfg["slots"] if x.get("id") == body.get("toSlot")), None)
    if not dst: return {"error": "unknown target slot"}
    dst.setdefault("providers", []).append(prov)
    save_config(cfg); PROXY.sync()
    return {"ok": True}

def api_provider_sampler(body):
    """Set or clear a per-provider sampler override that the proxy injects into
    each request for that provider. Empty value removes the override (falls back
    to whatever SkyrimNet sends)."""
    cfg = load_config()
    allp = ([(s, p) for s in cfg.get("slots", []) for p in s.get("providers", []) or []]
            + [(None, p) for p in cfg.get("unallocatedProviders", []) or []])
    hit = next(((s, p) for s, p in allp if p.get("id") == body.get("id")), None)
    if not hit:
        return {"error": "unknown provider"}
    s, p = hit
    if body.get("clearAll"):
        p.pop("samplerOverrides", None)
        save_config(cfg); PROXY.sync()
        return {"ok": True}
    key = str(body.get("key") or "")
    if key not in PROXY_SAMPLER_FIELDS:
        return {"error": "unknown sampler"}
    val = str(body.get("value") or "").strip()
    ov = p.setdefault("samplerOverrides", {})
    if val == "":
        ov.pop(key, None)
    else:
        try:
            fv = float(val)
        except Exception:
            return {"error": "%s must be a number" % key}
        if fv < 0:
            return {"error": "%s cannot be negative" % key}
        ov[key] = str(int(fv)) if key == "top_k" else _num_str(fv)
    if not ov:
        p.pop("samplerOverrides", None)
    save_config(cfg); PROXY.sync()
    return {"ok": True}

def _mem_mib(g):
    m = re.search(r"([0-9]+)", str(g.get("mem") or "0"))
    return int(m.group(1)) if m else 0

# What each provider is actually for, which is what should decide where it runs.
# Anything not named here is treated as a utility provider.
# the icon each shipped provider arrives with
DEFAULT_PROVIDER_EMOJI = {
    "Dialogue": "\U0001F4AC", "GM": "\U0001F3B2", "Combat": "\u2694\uFE0F", "Meta": "\U0001F9EA",
    "UT": "\U0001F310", "AI-Assistant": "\U0001F916", "ActionEval": "\U0001F3C3",
    "Charbio": "\U0001F3AD", "Diary": "\u270D\uFE0F", "Memory": "\U0001F9E0",
    "Vision": "\U0001F441\uFE0F", "IntelEngine": "\U0001F6F0\uFE0F", "SeverActions": "\U0001F4DC"}
PROV_TALK = {"dialogue", "combat", "ut", "ai-assistant"}   # these speak to the player
PROV_NARRATE = {"gm"}                                       # writes for the player, but can wait
PROV_SMALL = {"meta"}                                       # short, frequent, wants speed
PROV_VISION = {"vision"}

def _model_bytes(s):
    p = ((s.get("params") or {}).get("model") or "").strip()
    try:
        return os.path.getsize(p) if p and os.path.isfile(p) else 0
    except Exception:
        return 0

def api_recommend(body):
    """Place providers by what they do, and servers by how big their model is.

    The reasoning, in the order it matters:
      - Vision needs a server that actually has a vision projector loaded; nothing
        else will do, so that pairing is made first and is not negotiable.
      - Dialogue, Combat, the translator and the assistant all produce words a person
        reads, so they want the largest model, and it wants the strongest card.
      - Meta is short and constant, so it goes to the smallest model.
      - Everything else is utility work nobody is waiting on, so it goes to the next
        largest model, which by then is on a different card.
    """
    cfg = load_config()
    gpus = [g for g in cfg.get("gpus", []) if g.get("enabled") is not False and g.get("uuid")]
    provs = ([p for s in cfg.get("slots", []) for p in s.get("providers", []) or []]
             + list(cfg.get("unallocatedProviders", []) or []))
    ranked = sorted([s for s in cfg.get("slots", []) if _model_bytes(s)],
                    key=_model_bytes, reverse=True)
    missing = []
    if not gpus:
        missing.append("at least one enabled, detected GPU (press Detect GPUs)")
    if not provs:
        missing.append("at least one provider")
    if not ranked:
        missing.append("at least one server with a model chosen")
    if missing:
        return {"error": "Recommended Setup needs: " + "; ".join(missing)}
    gpus.sort(key=_mem_mib, reverse=True)
    lines = []
    # the biggest model gets the strongest card, and so on down
    for i2, s in enumerate(ranked):
        want = gpus[min(i2, len(gpus) - 1)]["id"]
        if s.get("gpuId") != want:
            s["gpuId"] = want
            lines.append("%s -> %s" % (s.get("label"), gpus[min(i2, len(gpus) - 1)].get("name", "GPU")))
    biggest = ranked[0]
    second = ranked[1] if len(ranked) > 1 else ranked[0]
    smallest = ranked[-1]
    vision_srv = next((s for s in ranked
                       if ((s.get("params") or {}).get("vision") or "N/A") not in ("", "N/A", "Disabled")), None)
    park = cfg.setdefault("unallocatedProviders", [])
    def place(p, slot):
        for s in cfg.get("slots", []):
            lst = s.get("providers") or []
            if p in lst:
                if s is slot:
                    return False
                lst.remove(p)
                break
        else:
            if p in park:
                park.remove(p)
        slot.setdefault("providers", []).append(p)
        return True
    put = {}
    for p in provs:
        title = str(p.get("title", "")).strip().lower()
        if title in PROV_VISION and vision_srv is not None:
            slot, why, prio = vision_srv, "the only server with a vision projector", 1
        elif title in PROV_TALK:
            # a person is waiting on these, so they go first
            slot, why, prio = biggest, "speaks to the player - largest model, strongest card", 0
        elif title in PROV_NARRATE:
            # same model, since it writes too, but it need not cut ahead of the talkers
            slot, why, prio = biggest, "writes for the player - largest model, behind the talkers", 1
        elif title in PROV_SMALL:
            # short and constant: fine anywhere, but it must not get in the way of the
            # providers a person is waiting on if it ends up sharing their card
            shares = smallest.get("gpuId") and smallest.get("gpuId") == biggest.get("gpuId")
            prio = 2 if shares else 1
            why = ("short and constant - smallest model, kept behind the talking providers"
                   if shares else "short and constant - smallest model")
            slot = smallest
        else:
            slot, why, prio = second, "utility work - next largest model, off the strongest card", 1
        p["priority"] = prio
        if place(p, slot):
            put.setdefault((slot.get("label"), why), []).append(p.get("title", "?"))
    for (label, why), names in put.items():
        lines.append("%s <- %s  (%s)" % (label, ", ".join(names), why))
    if vision_srv is None and any(str(p.get("title", "")).lower() in PROV_VISION for p in provs):
        lines.append("Vision was left with the rest: no server has a vision projector loaded")
    apply_auto_names(cfg)
    save_config(cfg)
    PROXY.sync()
    panel_log("[panel] recommended setup applied")
    return {"ok": True, "summary": chr(10).join(lines)}

def net_mode():
    try:
        return (load_config().get("settings", {}) or {}).get("networkMode", "localhost")
    except Exception:
        return "localhost"

def dev_mode():
    try:
        return bool((load_config().get("settings", {}) or {}).get("devMode", False))
    except Exception:
        return False

def _ip_class(ip):
    """Classify a client IP: 'local' | 'lan' | 'external'."""
    if not ip:
        return "external"
    ip = ip.split("%", 1)[0]
    if ip in ("127.0.0.1", "::1", "localhost"):
        return "local"
    try:
        a = ipaddress.ip_address(ip)
    except Exception:
        return "external"
    if a.is_loopback:
        return "local"
    if a.is_private and not a.is_link_local:
        return "lan"
    return "external"

def client_scope(handler):
    """Return the access scope for a request: 'host' (full) | 'remote' (read-only) | None (deny)."""
    ipc = _ip_class(handler.client_address[0] if handler.client_address else "")
    if ipc == "local":
        return "host"
    if ipc == "lan":
        if net_mode() != "lan":
            return None                      # LAN reachable but owner hasn't opened it
        return "host" if dev_mode() else "remote"
    return None                              # external: always denied

# Endpoints a read-only remote viewer MAY call. Everything else is host-only.
REMOTE_READ_OK = {
    "/", "/index", "/index.html",
    "/api/state", "/api/events", "/api/heartbeat", "/api/bye",
    "/api/client-error", "/icon.ico", "/favicon.ico",
}
# /api/tail is allowed for remote for the FIXED feeds only - dashboard, thinking and
# tts - and never kind=file, which would read an arbitrary path. Checked in the dispatcher.
#
# Those feeds carry content, not only numbers: thinking holds the model's reasoning and
# tts holds spoken dialogue, including the player's own lines and character names. That is
# deliberate - a remote session is the operator's own second screen, bound to remoteIp -
# but it is worth knowing before handing out an address.

def _host_allowlist():
    hosts = {"localhost", "127.0.0.1", "[::1]"}
    try:
        hosts.add("localhost:%d" % PORT); hosts.add("127.0.0.1:%d" % PORT)
    except Exception:
        pass
    for ip in _local_ips():
        hosts.add(ip)
        try: hosts.add("%s:%d" % (ip, PORT))
        except Exception: pass
    return hosts

def origin_host_ok(handler):
    """Reject cross-origin / rebinding: Host header must be ours; Origin (if present) must match."""
    host = (handler.headers.get("Host") or "").strip().lower()
    hp0 = host.rsplit(":", 1)[0].strip("[]") if host else ""
    if hp0 in ("localhost", "127.0.0.1", "::1") or _ip_class(hp0) in ("local", "lan"):
        host = ""                             # literal own/LAN address: nothing to resolve
    if host and host not in _host_allowlist():
        # allow bare-IP hosts in private range (covers LAN access), reject public names
        hp = host.rsplit(":", 1)[0].strip("[]")
        if _ip_class(hp) == "external":
            return False
    origin = (handler.headers.get("Origin") or "").strip().lower()
    if origin:
        try:
            oh = origin.split("://", 1)[1]
        except Exception:
            return False
        ohost = oh.rsplit(":", 1)[0].strip("[]")
        if ohost not in ("localhost", "127.0.0.1", "::1") and _ip_class(ohost) == "external":
            return False
    return True

_LIPS = {"ips": None, "ts": 0.0}
_LIPS_LOCK = threading.Lock()
def _local_ips(force=False):
    # getaddrinfo(hostname) can stall for seconds on Windows boxes without a default
    # gateway (DNS -> LLMNR -> NetBIOS walk). It used to run on EVERY api call via the
    # origin check and taxed the whole panel; resolve at most once a minute instead.
    with _LIPS_LOCK:
        if not force and _LIPS["ips"] is not None and time.time() - _LIPS["ts"] < 60:
            return set(_LIPS["ips"])
    ips = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None):
            ip = info[4][0].split("%", 1)[0]
            if _ip_class(ip) in ("local", "lan"):
                ips.add(ip)
    except Exception:
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1)); ips.add(s.getsockname()[0]); s.close()
    except Exception:
        pass
    out = {i for i in ips if _ip_class(i) == "lan"}
    with _LIPS_LOCK:
        _LIPS["ips"] = set(out); _LIPS["ts"] = time.time()
    return out

def primary_lan_ip():
    ips = sorted(_local_ips())
    return ips[0] if ips else ""

def network_is_down():
    """Best-effort: True only if NO active non-loopback network is detected. Fails closed (returns False on doubt)."""
    try:
        if _local_ips():
            return False
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.4)
        try:
            s.connect(("192.0.2.1", 53))      # reserved, never routed: nothing is sent
            ip = s.getsockname()[0]
            s.close()
            if ip and ip != "0.0.0.0" and _ip_class(ip) != "local":
                return False
        except Exception:
            s.close()
            return True     # no route at all -> network down
    except Exception:
        return False        # doubt -> fail closed (treat as up)
    return True

# ---- server-side masking: real host identifiers never leave the machine for remote ----
_MASK = "\u2022\u2022\u2022\u2022"

def _mask_path(p):
    # fully hide - no basename leak (filenames can reveal model/setup identity)
    return _MASK if p else p

def _mask_ip(_v):
    return "\u2022\u2022\u2022.\u2022\u2022\u2022.\u2022.\u2022"

def _mask_uuid(v):
    if not v:
        return v
    s = str(v)
    return "GPU-\u2022\u2022\u2022\u2022" if s.upper().startswith("GPU-") else _MASK

def redact_state(st):
    """Deep-copy-lite redaction of a state dict for remote viewers: strip IPs, paths, UUIDs, filenames."""
    import copy
    st = copy.deepcopy(st)
    se = st.get("settings", {}) or {}
    for k in ("panelIp", "remoteIp", "yamlGeneratedIp"):
        if se.get(k):
            se[k] = _mask_ip(se[k])
    for k in ("llamacppPath", "modelsDir", "outputDir", "templateFile", "logDir", "yamlPath", "yamlDir", "mo2Path"):
        if se.get(k):
            se[k] = _mask_path(se[k])
    if se.get("peerAddr"):
        se["peerAddr"] = "***"
    se["_masked"] = True
    for g in st.get("gpus", []) or []:
        if g.get("uuid"): g["uuid"] = _mask_uuid(g["uuid"])
        if "index" in g: g["index"] = _MASK
    def _mask_gpu_tag(v):
        # slots carry a free-text gpu tag. Historically a name substring ("5090"),
        # but launcher-template.ps1 tells users to pin by UUID, so it often holds a
        # real serial. Mask only when it is serial-shaped: gpuId stays the graph key
        # and a plain name tag stays readable, so the remote graph is unaffected.
        return _mask_uuid(v) if isinstance(v, str) and v.upper().startswith("GPU-") else v
    def scrub_slot(s):
        if s.get("gpu"): s["gpu"] = _mask_gpu_tag(s["gpu"])
        for key in ("script",):
            if s.get(key): s[key] = _mask_path(s[key])
        if s.get("model"): s["model"] = _mask_path(s["model"])
        # The card carries its own copy of the model, projector and draft paths, and
        # Live Network draws the server boxes from those - so masking only the field
        # above left the filenames on screen for a remote viewer to read.
        pr = s.get("params") or {}
        for key in ("model", "vision", "draft"):
            if pr.get(key) and pr[key] not in ("N/A", "Disabled"):
                pr[key] = _mask_path(pr[key])
        for p in s.get("providers", []) or []:
            pass  # provider titles/ports are routing info, kept visible (masked of nothing host-identifying)
    for s in st.get("slots", []) or []:
        scrub_slot(s)
    for s in st.get("routing", []) or []:
        if s.get("model"): s["model"] = _mask_path(s["model"])
        if s.get("gpu"): s["gpu"] = _mask_gpu_tag(s["gpu"])
        # gpuId is an internal correspondence key (e.g. "g1"), not host-identifying - the real
        # secret is the GPU uuid (masked separately). Keep gpuId so the remote Live Network graph
        # draws the same GPU->server->provider lines and colours as the host.
    st["scope"] = "remote"
    return st

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send_response(self, code, message=None):
        super().send_response(code, message)
        self.send_header("X-App", "%s %s" % (APP_NAME, APP_VER_UI))

    def _send(self, code, ctype, payload, extra=None):
        data = payload if isinstance(payload, bytes) else payload.encode("utf-8", "replace")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        if "text/html" in str(ctype):
            self.send_header("Cache-Control", "no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        scope = client_scope(self)
        if scope is None:
            self.send_response(403); self.send_header("Connection", "close"); self.end_headers(); return
        self._scope = scope
        if self.path.startswith("/api/") and not origin_host_ok(self):
            self._send(403, "application/json", '{"error":"origin/host rejected"}'); return
        if scope == "remote":
            base = self.path.split("?", 1)[0]
            if base == "/api/tail":
                pass  # kind restricted below in dispatch
            elif base not in REMOTE_READ_OK:
                self._send(403, "application/json", '{"error":"read-only remote session"}'); return
        if self.path.startswith("/api/log-download"):
            if getattr(self, "_scope", "host") == "remote":
                self._send(403, "application/json", '{"error":"read-only remote session"}'); return
            try:
                q = parse_qs(urlparse(self.path).query)
                name = os.path.basename((q.get("f") or [""])[0])
                cfg = load_config()
                cand = [os.path.join(log_dir(cfg), name), os.path.join(STACK, name)]
                src = next(p for p in cand if os.path.isfile(p))
                data = open(src, "rb").read()
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Disposition", "attachment; filename=%s" % name)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            except Exception:
                self.send_response(404); self.end_headers()
            return
        if self.path.split("?")[0] in ("/icon.ico", "/favicon.ico"):
            try:
                ico = open(os.path.join(STACK, "PandorumLLM.ico"), "rb").read()
                self.send_response(200)
                self.send_header("Content-Type", "image/x-icon")
                self.send_header("Content-Length", str(len(ico)))
                self.send_header("Cache-Control", "max-age=86400")
                self.end_headers()
                self.wfile.write(ico)
            except Exception:
                self.send_response(404); self.end_headers()
            return
        u = urlparse(self.path)
        if u.path == "/api/events":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            q = _queue.Queue(maxsize=200)
            SSE_CLIENTS.add(q)
            try:
                self.wfile.write(b": hello\n\n"); self.wfile.flush()
                while True:
                    try:
                        msg = q.get(timeout=15)
                        self.wfile.write(("data: " + msg + "\n\n").encode("utf-8"))
                    except _queue.Empty:
                        self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
            except Exception:
                pass
            finally:
                SSE_CLIENTS.discard(q)
            return
        if u.path == "/" or u.path.startswith("/index"):
            self._send(200, "text/html; charset=utf-8", PAGE.replace("__UIV__", APP_VER_UI).replace("__TSKINDS__", json.dumps(list(TERM_SCALE_KINDS))))
        elif u.path == "/api/state":
            _st = api_state()
            if getattr(self, "_scope", "host") == "remote":
                _st = redact_state(_st)
            self._send(200, "application/json", json.dumps(_st))
        elif u.path == "/api/models":
            self._send(200, "application/json", json.dumps({"models": list_models(load_config())}))
        elif u.path == "/api/templates":
            self._send(200, "application/json", json.dumps({"templates": list_templates()}))
        elif u.path == "/api/template":
            cfg = load_config()
            q = parse_qs(u.query or "")
            nm = (q.get("name") or [""])[0]
            if nm:
                self._send(200, "application/json", json.dumps({"path": nm, "content": read_named_template(nm)}))
            else:
                self._send(200, "application/json", json.dumps(
                    {"path": cfg["settings"].get("templateFile", ""), "content": read_template(cfg["settings"])}))
        elif u.path == "/api/logs":
            self._send(200, "application/json", json.dumps(api_logs()))
        elif u.path == "/api/stats":
            self._send(200, "application/json", json.dumps(PROXY.stats_snapshot(getattr(self, "_scope", "host") == "remote")))
        elif u.path == "/api/errors":
            self._send(200, "application/json", json.dumps(api_errors_snapshot(getattr(self, "_scope", "host") == "remote")))
        elif u.path == "/api/log-download":
            name = os.path.basename(parse_qs(u.query).get("f", [""])[0])
            p = os.path.join(log_dir(), name)
            if name and os.path.isfile(p):
                self._send(200, "application/octet-stream", open(p, "rb").read(),
                           {"Content-Disposition": 'attachment; filename="%s"' % name})
            else:
                self._send(404, "text/plain", "not found")
        else:
            self._send(404, "text/plain", "not found")

    def do_POST(self):
        scope = client_scope(self)
        if scope is None:
            self.send_response(403); self.send_header("Connection", "close"); self.end_headers(); return
        self._scope = scope
        if not origin_host_ok(self):
            self._send(403, "application/json", '{"error":"origin/host rejected"}'); return
        n = int(self.headers.get("Content-Length", "0"))
        if n > 8 * 1024 * 1024:
            self._send(413, "application/json", '{"error":"payload too large"}'); return
        raw = self.rfile.read(n)
        if self.path in ("/api/heartbeat", "/api/bye"):
            uid = ""
            try: uid = json.loads(raw).get("uid", "")
            except Exception: uid = (raw or b"").decode("utf-8", "ignore").strip()
            if uid:
                if self.path == "/api/bye": CLIENTS.pop(uid, None)
                else: CLIENTS[uid] = time.time(); LIFE["ever"] = True
            self._send(200, "application/json", json.dumps({"ok": True, "seq": SSE_SEQ["n"]}))
            return
        try:
            body = json.loads(raw or b"{}")
        except Exception:
            self._send(400, "application/json", '{"error":"bad json"}')
            return
        routes = {
            "/api/assign": api_assign, "/api/edit": api_edit,
            "/api/add": api_add, "/api/remove": api_remove,
            "/api/settings": api_settings, "/api/tail": api_tail,
            "/api/tts-launcher": api_tts_launcher, "/api/tts-import": api_tts_import,
            "/api/tts-server": api_tts_server, "/api/tts-models": api_tts_models,
            "/api/acpp-update": api_acpp_update,
            "/api/higgs-install": api_higgs_install,
            "/api/higgs-adopt": api_higgs_adopt,
            "/api/launch-stack": api_launch_stack, "/api/show-terminal": api_show_terminal,
            "/api/creator-add": api_creator_add, "/api/creator-remove": api_creator_remove,
            "/api/launcher-content": api_launcher_content,
            "/api/provider-add": api_provider_add, "/api/provider-remove": api_provider_remove,
            "/api/provider-restore-defaults": api_provider_restore_defaults,
            "/api/restore-servers": api_restore_servers,
            "/api/provider-edit": api_provider_edit, "/api/provider-move": api_provider_move,            "/api/browse-dirs": api_browse_dirs, "/api/folder-view": api_folder_view,
            "/api/terminate": api_terminate, "/api/exit": api_exit,
            "/api/handoff": api_handoff, "/api/detect-ip": api_detect_ip,
            "/api/network-info": api_network_info,
            "/api/client-error": api_client_error,
            "/api/detect-gpus": api_detect_gpus, "/api/open-file": api_open_file,
            "/api/gpu-edit": api_gpu_edit, "/api/recommend": api_recommend,
            "/api/sampler-edit": api_sampler_edit,
            "/api/provider-sampler": api_provider_sampler,
            "/api/helper-skip": api_helper_skip, "/api/helper-reset": api_helper_reset,
            "/api/helper-manual": api_helper_manual,
            "/api/helper-revert": api_helper_revert,
            "/api/helper-unforce": api_helper_unforce,
            "/api/path-check": api_path_check,
            "/api/debug-report": api_debug_report,
            "/api/validate-launcher": api_validate_launcher,
            "/api/sweep-launchers": api_sweep_launchers,
            "/api/logs-meta": api_logs_meta,
            "/api/log-read": api_log_read,
            "/api/logs-clear": api_logs_clear,
            "/api/profile-save": api_profile_save, "/api/profile-load": api_profile_load, "/api/profile-delete": api_profile_delete,
            "/api/yaml-load": api_yaml_load, "/api/yaml-generate": api_yaml_generate,
            "/api/yaml-create": api_yaml_create, "/api/yaml-mo2": api_yaml_mo2,
            "/api/yaml-get": api_yaml_get, "/api/yaml-base-save": api_yaml_base_save,
            "/api/yaml-base-reset": api_yaml_base_reset,
            "/api/yaml-space-save": api_yaml_space_save, "/api/yaml-space-remove": api_yaml_space_remove,
            "/api/yaml-open-native": api_yaml_open_native,
            "/api/slot-params": api_slot_params, "/api/slot-launcher": api_slot_launcher,
            "/api/llama-update": api_llama_update, "/api/app-update": api_app_update, "/api/peer": api_peer,
            "/api/slot-launcher-save": api_slot_launcher_save, "/api/slot-launcher-load": api_slot_launcher_load,
            "/api/slot-launcher-default": api_slot_launcher_default, "/api/slot-launcher-revert": api_slot_launcher_revert,
            "/api/stats-reset": api_stats_reset,
            "/api/errors-clear": api_errors_clear,
        }
        REMOTE_POST_OK = {"/api/tail", "/api/client-error", "/api/heartbeat", "/api/bye"}
        if getattr(self, "_scope", "host") == "remote":
            if self.path not in REMOTE_POST_OK:
                self._send(403, "application/json", '{"error":"read-only remote session - this action is host-only"}'); return
            if self.path == "/api/tail" and str((body or {}).get("kind", "")) == "file":
                self._send(403, "application/json", '{"error":"read-only remote session"}'); return
        # Starting a server takes seconds and touches no config, so holding the lock for
        # it made the OTHER launch button wait on this one. Those two run unlocked.
        _lk = _NullLock() if self.path in NO_CFG_LOCK else CFG_LOCK
        try:
            with _lk:                 # serialize all mutating endpoints: no lost updates
                if self.path == "/api/tail":
                    out = api_tail(body, getattr(self, "_scope", "host"))
                elif self.path in routes:
                    out = routes[self.path](body)
                elif self.path == "/api/creator-save":
                    out = api_creator_save(body, create=False)
                elif self.path == "/api/creator-create":
                    out = api_creator_save(body, create=True)
                elif self.path == "/api/launch":
                    out = api_action(body, "launch")
                elif self.path == "/api/stop":
                    out = api_action(body, "stop")
                else:
                    out = {"error": "unknown endpoint"}
        except Exception as e:
            panel_log("[panel] ERROR %s %s" % (self.path, e))
            log_error("panel", "%s: %s" % (self.path, e))
            out = {"error": str(e)}
        self._send(200, "application/json", json.dumps(out))

# ---------------------------------------------------------------- page
PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>PandorumLLM</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<!-- No webfont link. This pulled Plus Jakarta Sans from fonts.googleapis.com on every
       page load, which told Google the IP and referer of a panel that is documented as
       running entirely on your LAN - and needed the internet to look right. The family is
       still declared in the CSS, so it is used if installed locally; otherwise the stack
       falls through to Segoe UI, which every Windows install has. -->
  <link rel="icon" href="/icon.ico?v=210">
  <style>
  :root { --bg:#0d0e10; --card:#151619; --edge:#26282d; --txt:#ececf1; --dim:#9aa0a8;
          --acc:#b5f320; --ok:#3fdd78; --warn:#eab308; --err:#ef4444; --selglow:#000000; }
  * { box-sizing:border-box; }
  @font-face {
    font-family: "EmojiMatched";
    src: local("Segoe UI Emoji"), local("Apple Color Emoji"), local("Noto Color Emoji"),
         local("Segoe UI Symbol");
    ascent-override: 100%;
    descent-override: 26%;
    line-gap-override: 0%;
  }
  :root { color-scheme: dark;
          /* an element with no resting glow contributes nothing to the highlight */
          --restglow:0 0 12px -2px rgba(0,0,0,.85); }
  body { background:var(--bg); color:var(--txt); margin:0;
         font:500 14px/1.55 "Plus Jakarta Sans",Inter,"Segoe UI Variable Text","Segoe UI",
              "EmojiMatched",system-ui,sans-serif;
         font-feature-settings:"tnum"; }
  header { display:flex; align-items:center; gap:14px; padding:14px 22px 10px; flex-wrap:wrap; }
  h1 { font-size:20px; margin:0; }
  .ver { color:var(--dim); font-size:12px; border:none; padding:2px 4px; white-space:nowrap; flex:0 0 auto; }
  .sub { color:var(--dim); font-size:12px; }
  .wrap { display:flex; align-items:flex-start; }
  /* the nav column and the page share one top edge, 12px below the wrap:
     nav = 8px padding + 4px button margin, page = 4px padding + 8px subtab margin.
     matching button padding then lines up the text, not just the boxes. */
  nav { width:170px; padding:8px 0 20px 14px; flex-shrink:0; }
  nav button { display:block; width:100%; text-align:left; margin:4px 0; background:transparent;
               text-shadow:0 1px 3px rgba(0,0,0,.7);
               border:1px solid transparent; color:var(--dim); border-radius:10px; padding:9px 12px;
               font-size:13.5px; font-weight:600; cursor:pointer; }
  nav button:hover { color:var(--txt); }
  nav button.on { background:var(--card); border-color:var(--edge); color:var(--txt); }
  main { flex:1; padding:4px 22px 30px 14px; min-width:0; }
  main > div { padding-left:26px; }
  main > div > .subtabs { margin-left:-26px; }
  main .row:not(.card .row):not(.subtabs) > button:first-child { margin-left:-16px; }
  .subtabs { display:flex; gap:8px; margin:8px 0 14px; flex-wrap:wrap; }
  button { word-spacing:3px; }
  .subtabs button { background:transparent; border:1px solid var(--edge); color:var(--dim);
                    border-radius:999px; padding:5.2px 14.6px; font-size:14.95px; font-weight:600; cursor:pointer; }
  .subtabs button.on { background:var(--card); color:var(--txt); border-color:var(--dim); }
  .stcard { background:var(--card); box-shadow:0 0 14px -2px rgba(0,0,0,.8); border:none; border-radius:12px; padding:12px 15px; margin-bottom:10px; }
  .stcard-h { font-weight:700; font-size:14px; margin-bottom:9px; display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
  .stcard-sub { font-weight:400; font-size:11.5px; color:var(--dim); }
  .stbar-row { display:flex; align-items:center; gap:10px; margin:5px 0; }
  .stbar-lbl { flex:0 0 200px; font-size:12px; color:var(--txt); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .stbar-track { flex:1 1 auto; height:16px; background:rgba(255,255,255,.05); border-radius:5px; overflow:hidden; min-width:50px; }
  .stbar-fill { height:100%; border-radius:5px; transition:width .4s ease; min-width:2px; }
  .stbar-val { flex:0 0 84px; text-align:right; font-size:12px; font-variant-numeric:tabular-nums; color:var(--txt); }
  .stempty { color:var(--dim); padding:26px; text-align:center; line-height:1.6; }
  .errstat { display:flex; flex-wrap:wrap; gap:8px; align-items:center; }
  .errstat-total { font-weight:700; font-size:14px; margin-right:6px; }
  .errchip { background:rgba(255,255,255,.06);  border-radius:999px; padding:3px 10px; font-size:12px; font-variant-numeric:tabular-nums; white-space:nowrap; }
  .errchip-ERROR { color:#ff8a8a; border-color:rgba(255,90,90,.4); }
  .errchip-WARN { color:#eab308; border-color:rgba(234,179,8,.4); }
  .errctrl select { background:#0d0f13; color:var(--fieldtxt, var(--txt)); border:none; border-radius:7px; padding:4px 8px; margin-left:4px; }
  .errrow { background:var(--card); box-shadow:0 0 14px -2px rgba(0,0,0,.8); border:none; border-radius:10px; padding:10px 12px; margin-bottom:8px; }
  .errrow-h { display:flex; align-items:center; gap:9px; margin-bottom:7px; flex-wrap:wrap; }
  .errrow-title { font-weight:600; font-size:13px; flex:1 1 auto; min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .errrow-time { color:var(--dim); font-size:11.5px; font-variant-numeric:tabular-nums; }
  .errrow-text { width:100%; box-sizing:border-box; background:var(--bg); color:var(--txt); box-shadow:0 0 12px -2px rgba(0,0,0,.85); border-radius:7px; padding:8px 10px; font-family:ui-monospace,Consolas,monospace; font-size:12px; line-height:1.5; min-height:42px; max-height:150px; resize:vertical; }
  .errpager { display:flex; gap:5px; justify-content:center; margin-top:12px; flex-wrap:wrap; }
  .errpg { background:transparent;  color:var(--txt); border-radius:7px; padding:4px 11px; font-size:12.5px; cursor:pointer; min-width:34px; }
  .errpg.on { background:var(--acc); color:#12161d; border-color:var(--acc); font-weight:700; }
  .errpg.dis { opacity:.4; cursor:default; }
  .errpg-gap { padding:4px 4px; color:var(--dim); align-self:center; }
  .card { background:var(--card);
         --restglow:0 0 14px -2px rgba(0,0,0,.8);
         box-shadow:var(--restglow);
         border:none; border-radius:12px;
          padding:14px 16px; margin-bottom:14px; }
  .row { display:flex; align-items:center; gap:10px; flex-wrap:wrap; }
  .label { font-size:18.4px; font-weight:600; }
  .chip { font-size:11px; padding:2px 8px; border-radius:999px;  color:var(--dim); }
  .chip.clickable { cursor:pointer; }
  .chip.clickable:hover { color:var(--txt); border-color:var(--dim); }
  .svr-row .chip { border:none !important; background:transparent !important; padding:2px 4px;
                   box-shadow:none; transition:box-shadow .16s, color .16s, text-shadow .16s; }
  .svr-row .chip:hover, .svr-row .chip:focus-within {
    color:var(--txt); text-shadow:0 0 10px var(--acc); }
  .chip.bad { color:var(--err); border-color:var(--err); font-weight:700; }
  .off { opacity:.42; }
  .pill { font-size:11px; padding:2px 10px; border-radius:999px; font-weight:600; }
  .pill.serving { background:#10321f; color:var(--ok); }
  .pill.loading { background:#3a2a12; color:var(--warn); }
  .pill.down    { background:#242833; color:var(--dim); }
  .pill.wedged  { background:#3a1414; color:var(--err); }
  .pill.unknown { background:#242833; color:var(--dim); }
  .spd { color:var(--ok); font-size:12px; font-weight:600; font-family:Consolas,monospace; }
  .path { font-family:"Cascadia Mono",Consolas,monospace; font-size:12px; color:var(--acc);
          word-break:break-all; margin:6px 0 2px; }
  .last { font-size:11px; color:var(--dim); margin-bottom:8px; }
  select, input.txt { background:#0d0f13; color:var(--fieldtxt, var(--txt)); border:none;
           border-radius:8px; padding:7px 10px; font-size:13px; max-width:100%; }
  /* the native arrow sits hard against the right edge, so draw our own and pad evenly */
  select { appearance:none; -webkit-appearance:none; -moz-appearance:none;
           padding:7px 30px 7px 10px;
           background-image:url("data:image/svg+xml;charset=UTF-8,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'%3E%3Cpath d='M1 1l4 4 4-4' fill='none' stroke='%238b93a3' stroke-width='1.6' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E");
           background-repeat:no-repeat; background-position:right 10px center; }
  select::-ms-expand { display:none; }
  select { min-width:260px; }
  select, input.edit, input.txt {
    border:none !important; border-radius:8px;
    --restglow:0 0 9px var(--selglow);
    box-shadow:var(--restglow); }
  select:focus, input.edit:focus, input.txt:focus { outline:none; }
  /* soften the glow where the browser can blend colours; the plain ring above is the fallback */
  select, input.edit, input.txt { transition:box-shadow .5s ease; }
  @supports (color: color-mix(in srgb, red 50%, transparent)) {
    select, input.edit, input.txt {
      --restglow:0 0 12px 2px color-mix(in srgb, var(--selglow) 70%, transparent);
      box-shadow:var(--restglow); }
    select:hover, input.edit:hover, input.txt:hover {
      box-shadow:0 0 13px 2px color-mix(in srgb, var(--acc) 55%, transparent); }
    /* focus holds exactly the hover glow until you click away */
    select:focus, input.edit:focus, input.txt:focus {
      box-shadow:0 0 15px 3px color-mix(in srgb, var(--acc) 70%, transparent); }
  }
  input.txt { width:100%; font-family:Consolas,monospace; font-size:12.5px; }
  button { background:var(--acc); color:#08131f; border:0; border-radius:8px;
           padding:7px 16px; font-size:13px; font-weight:600; cursor:pointer; }
  body.remoteview [data-hostonly] { display:none !important; }
  body.remoteview #pmsub-stats, body.remoteview #pmpane-stats { display:none !important; }
  body.remoteview #card-ips, body.remoteview #card-gpus, body.remoteview #card-yaml { display:none !important; }
  body.remoteview #dsub-setup, body.remoteview #dsub-yaml { display:none !important; }
  .pickrow { padding:7px 10px; border-radius:6px; cursor:pointer; }
  .pickrow:hover { background:#1b2028; }
  button.stop { background:#242833; color:var(--txt); border:1px solid var(--edge); }
  button.stop.on { background:#323845; border-color:var(--dim); color:#fff; }
  button:disabled { opacity:.5; cursor:wait; }
  button.icon { background:transparent; border:0; color:var(--dim); font-size:14px; padding:2px 4px; }
  button.icon:hover { color:var(--txt); }
  button.x { margin-left:auto; background:transparent; border:1px solid var(--edge);
             color:var(--dim); border-radius:8px; padding:2px 9px; font-size:12px; }
  button.x:hover { color:var(--err); border-color:var(--err); }
  button.go { background:#123726; color:var(--ok); border:1px solid #1d5c3f; }
  input.edit { background:#0d0f13; color:var(--fieldtxt, var(--txt)); box-shadow:0 0 12px -2px rgba(0,0,0,.85); border-radius:8px;
               padding:5px 8px; font-size:14px; min-width:70px; max-width:280px; }
  .addcard { text-align:center; background:none; border:none; padding:0; }
  .provs { display:flex; flex-direction:column; gap:8px; margin-top:10px; }
  .prov { display:flex; align-items:center; gap:9px; flex-wrap:wrap; background:#0d0f13;
          box-shadow:0 0 16px -1px rgba(0,0,0,.9); position:relative;
          border:none; border-radius:10px; padding:8px 52px 8px 10px; }
  .grip { color:#4a5162; letter-spacing:-2px; user-select:none; cursor:grab; padding:2px 4px; }
  .grip:active { cursor:grabbing; }
  .uuid { filter:blur(4px); cursor:pointer; user-select:none; transition:filter .15s; }
  .uuid.show { filter:none; user-select:text; }
  .dropzone.over { border-color:var(--acc); box-shadow:0 0 0 1px var(--acc) inset; }
  .mismatch { color:var(--warn); font-size:12px; }
  pre.log { background:#0d0f13; border:none;
            box-shadow:0 0 14px -2px rgba(0,0,0,.8); border-radius:8px;
            padding:8px 10px; font-size:11.5px; white-space:pre-wrap; color:var(--dim);
            max-height:170px; overflow:auto; margin:10px 0 0; display:none; }
  /* ---- Live Network: top-down layout, drop zones, trace glow ---- */
  .netwrap { position:relative; padding:16px 6px 8px; overflow-x:auto; }
  .netwrap.netbusy { pointer-events:none; opacity:.72; }
  .netlines { position:absolute; left:0; top:0; width:100%; height:100%; pointer-events:none; z-index:0; overflow:visible; }
  .netband { position:relative; z-index:1; display:flex; justify-content:center; align-items:flex-start;
             gap:20px; flex-wrap:wrap; }
  .netband + .netband { margin-top:64px; }
  .netcol { display:flex; flex-direction:column; align-items:center; gap:22px; }
  .netbox { position:relative; background:#12161d; border:none; border-radius:10px;
            padding:8px 12px; width:max-content; min-width:172px; box-sizing:border-box; cursor:grab;
            touch-action:none; user-select:none;
            transition:border-color .15s, box-shadow .15s, transform .1s; }
  .netbox.dragging { cursor:grabbing; }
  .netghost { flex:none; pointer-events:none; }
  .netbox { box-shadow:0 0 15px 0 var(--nbc, rgba(0,0,0,.85)); }
  .netbox.srv:not([style*="--nbc"]) { box-shadow:0 0 14px -2px rgba(0,0,0,.85); }
  .netbox:hover { box-shadow:0 0 0 1px var(--nbc, var(--acc)),
                              0 0 12px -2px var(--nbc, var(--acc)) !important; }
  .netbox .nb-t { font-weight:600; font-size:12.5px; color:#e8ecf2;
                  white-space:nowrap; overflow:hidden; text-overflow:ellipsis; padding-right:46px; }
  .netbox .nb-s { font-size:11px; color:var(--dim); margin-top:2px;
                  white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .netbox .nb-r { position:absolute; right:10px; top:9px; font-size:11px; color:var(--dim); }
  .netbox.prov { min-width:186px; padding:5px 12px; min-height:0; height:auto;
                 display:flex; align-items:center; justify-content:space-between; gap:10px; }
  .netbox.prov .nb-t { line-height:1.2; display:flex; align-items:center; flex:1 1 auto; }
  .netbox.prov .nb-t { font-size:12px; padding-right:0; }
  .netbox.prov .nb-r { position:static; right:auto; top:auto; transform:none;
                       flex:0 0 auto; line-height:1.2; }

  .netbox.dragging { opacity:.85; transform:scale(.97); box-shadow:0 0 0 1px var(--acc), 0 0 18px 2px var(--acc); }
  .netdrop { background:#0c0f14; box-shadow:0 0 14px -2px rgba(0,0,0,.8);
             border:none; border-radius:10px; padding:8px;
             min-width:252px; box-sizing:border-box; min-height:38px; display:flex; flex-direction:column; gap:8px;
             align-items:center; transition:border-color .15s, box-shadow .15s, background .15s; }
  .netdrop .nd-e { font-size:10.5px; color:#5b6479; text-align:center; padding:4px 2px; }
  .netdrop.over { border-color:var(--acc); background:#111823; box-shadow:0 0 15px rgba(77,163,255,.45) inset; }
  .netdock, .netdock.over { box-shadow:none !important; }
  .netdock { border:none; border-radius:12px; padding:4px; transition:box-shadow .15s; }
  .netdock.over { border-color:var(--acc); box-shadow:0 0 15px rgba(77,163,255,.45); }
  .netpark { width:100%; }
  .netpark.over { outline:none; border-radius:12px; box-shadow:none; }
  /* trace glow: ramps up over 0.5s, pulses for 6s, fades out over the last 1s */
  /* ramp in over 0.5s, pulse for 6s, fade over the last 1s - only opacity moves, so the
     browser composites it instead of repainting a shadow, which is what made it judder */
  @keyframes netGlow {
    0% { opacity:0 }   6.7% { opacity:1 }
    14.7% { opacity:.45 }  22.7% { opacity:1 }  30.7% { opacity:.45 }  38.7% { opacity:1 }
    46.7% { opacity:.45 }  54.7% { opacity:1 }  62.7% { opacity:.45 }  70.7% { opacity:1 }
    78.7% { opacity:.45 }  86.7% { opacity:1 }  100% { opacity:0 }
  }
  .netbox.trace::after { content:""; position:absolute; left:-2px; top:-2px; right:-2px; bottom:-2px;
    border-radius:12px; pointer-events:none; will-change:opacity;
    box-shadow:0 0 14px 3px currentColor;
    animation: netGlow 7.5s linear forwards; }
  .netbox.trace { color:var(--nbc, #b5f320); }
  .netline.trace { stroke:#b5f320 !important; will-change:opacity;
    filter:drop-shadow(0 0 5px rgba(181,243,32,.9));
    animation: netGlow 7.5s linear forwards; }
  .slotgrid .card > .row { flex-wrap:wrap; gap:10px 16px; align-items:center; margin-bottom:4px; }
  .slotgrid .card .label { width:auto; max-width:100%; overflow-wrap:anywhere; }
  .slotgrid .card .path, .slotgrid .card .last { word-break:break-word; white-space:normal; margin:2px 0 6px; }
  .slotgrid .card .spd, .slotgrid .card .mismatch { white-space:normal; }
  .slotgrid .pgrid { gap:0; }
  .slotgrid .pcell { margin-bottom:15px; }
  .slotgrid .pcell.ptight { margin-bottom:4px !important; min-height:22px; }
  .slotgrid .pcell.stack { margin-bottom:30px; }
  .slotgrid .pcell input.pnum { max-width:124px; }
  .slotgrid { display:grid; grid-template-columns:repeat(auto-fill,minmax(430px,1fr)); gap:14px; align-items:start; }
  .slotgrid > .card { margin:0; }
  .prov { gap:12px 14px !important; padding:12px 56px 12px 14px !important; }
  .prov .row, .prov > .row { align-items:center; }
  .prov .portchip { border:none !important; box-shadow:none !important; background:transparent;
                    padding:0 2px; color:var(--dim); }
  .prov .chip.clickable { cursor:pointer; }
  .pgrid { display:flex; flex-direction:column; gap:26px; margin-top:14px; }
  .pcell { display:flex; align-items:center; justify-content:space-between; gap:16px;
          min-height:34px; margin:0; }
  .plab { flex:1 1 auto; min-width:0; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .pctl { flex:0 0 auto; display:flex; align-items:center; justify-content:flex-end; gap:10px; }
  .pctl select, .pctl .selwrap { width:124px; min-width:0; }
  /* the slider stays in the layout but only shows while the row is hovered */
  .pctl { position:relative; }
  .rngpop { position:absolute; top:calc(100% + 6px); left:50%; transform:translateX(-50%);
            z-index:60; display:none;
            padding:9px 12px; border-radius:10px;
            background:rgba(4,6,9,.55); backdrop-filter:blur(4px) saturate(1.15);
            -webkit-backdrop-filter:blur(4px) saturate(1.15);
            box-shadow:0 10px 26px rgba(0,0,0,.55); }
  .rngpop { opacity:0; transition:opacity .18s ease; }
  .rngpop.on { display:block; }
  .rngpop.on.vis { opacity:1; }
  .pctl .prng { width:150px; flex:none; accent-color:var(--acc); display:block; }
  .pctl .prng:focus-visible { outline:2px solid var(--acc); outline-offset:2px; }
  /* the model pickers need the full width, so their control drops to its own line */
  .pcell.stack { display:block; }
  .pcell.stack .plab { display:block; white-space:normal; margin-bottom:8px; }
  .pcell.stack .pctl { display:block; }
  .pcell.stack .pctl select, .pcell.stack .pctl .selwrap { width:100%; }
  textarea.srved { background:#0d0f13 !important; color:var(--txt); border:none; box-shadow:0 0 14px -2px rgba(0,0,0,.8);
                   border-radius:8px; padding:10px 12px; box-sizing:border-box; resize:vertical; }
  textarea.srved[readonly] { border-color:var(--edge); color:#c9d1dc; }
  /* styled replacement for the browser's own tooltip */
  .uitip { position:fixed; z-index:200; max-width:340px; pointer-events:none;
           background:rgba(4,6,9,.55); backdrop-filter:blur(4px) saturate(1.15); -webkit-backdrop-filter:blur(4px) saturate(1.15); border:none; border-radius:9px;
           box-shadow:0 10px 26px rgba(0,0,0,.55);
           padding:8px 11px; font-size:12px; line-height:1.5; color:#e8ecf2;
           font-family:"Plus Jakarta Sans", Inter, "Segoe UI", system-ui, sans-serif;
           box-shadow:0 10px 26px rgba(0,0,0,.55); opacity:0; transition:opacity .12s; }
  .uitip.on { opacity:1; }
  .profwrap, .refwrap { position:relative; display:inline-flex; align-items:center; }
  .hdr-link, .hdr-ico { color:var(--dim); cursor:pointer; user-select:none;
                        transition:color .14s, text-shadow .14s, filter .14s; }
  .hdr-link { font-size:15.6px; font-weight:600; padding:3px 5px; }
  .hdr-note { color:var(--dim); font-size:15.6px; font-weight:600; padding:3px 5px;
              user-select:none; white-space:nowrap; }
  #ref-now { padding-left:0; margin-left:-4px; }   /* the clock already pads this side */
  #hdr-prof { display:flex; align-items:center; gap:24px; }   /* same gap as the row itself */
  .hdr-note[data-act] { cursor:pointer; }
  .hdr-note[data-act]:hover { color:#8cc6ff; text-shadow:0 0 9px rgba(77,163,255,.95); }
  .ver { display:inline-flex; flex-direction:column; align-items:center; line-height:1.05;
         cursor:pointer; user-select:none; border-radius:6px; }
  .ver .upd { font-size:9.5px; font-weight:700; letter-spacing:.3px; margin-top:1px;
              text-align:center; white-space:nowrap; }
  .ver.uptodate { color:#7ee081; text-shadow:0 0 5px rgba(126,224,129,.45); }
  .ver.behind { color:#e0c23c; text-shadow:0 0 9px rgba(224,194,60,.95);
                animation:verpulse 1.6s ease-in-out infinite; }
  @keyframes verpulse { 0%,100% { text-shadow:0 0 5px rgba(224,194,60,.55); }
                        50% { text-shadow:0 0 14px rgba(224,194,60,1); } }
  .peerview [data-hostonly] { display:none !important; }
  .peerview [data-act] { pointer-events:none; }
  .provoff { opacity:.5; transition:opacity .15s; }
  .provoff .provpow { opacity:2; }        /* the control itself stays readable */
  .provpow { position:absolute; right:12px; top:50%; transform:translateY(-50%);
             background:none !important; border:none !important; box-shadow:none !important;
             padding:2px 6px; font-size:26px; line-height:1; cursor:pointer; color:var(--ok);
             text-shadow:0 0 7px rgba(126,224,129,.85); transition:color .15s, text-shadow .15s; }
  .provpow.off { color:#ff5d5d; text-shadow:0 0 7px rgba(255,93,93,.85); }
  .provpow:hover { text-shadow:0 0 12px rgba(126,224,129,1); }
  .provpow.off:hover { text-shadow:0 0 12px rgba(255,93,93,1); }
  .blueglow { color:#8cc6ff; text-shadow:0 0 9px rgba(77,163,255,.95); }
  .hdr-ico { display:inline-flex; align-items:center; padding:4px 5px; }
  .hdr-ico svg { width:18px; height:18px; }
  .hdr-link:hover, .hdr-link.on { color:#8cc6ff; text-shadow:0 0 9px rgba(77,163,255,.95); }
  .hdr-ico:hover, .hdr-ico.on { color:#8cc6ff; filter:drop-shadow(0 0 6px rgba(77,163,255,.95)); }
  .refpop { position:absolute; top:calc(100% + 8px); right:0; z-index:150; display:none;
            align-items:center; gap:8px; white-space:nowrap;
            background:rgba(4,6,9,.55); backdrop-filter:blur(4px) saturate(1.15); -webkit-backdrop-filter:blur(4px) saturate(1.15); border-radius:12px; padding:10px 12px;
            box-shadow:0 14px 34px rgba(0,0,0,.6); }
  .refwrap.on .refpop { display:flex; }
  @supports not (backdrop-filter: blur(2px)) {
    .uitip, .profpop, .refpop, .gpupop, .bgpop { background:#161b24; }
  }
  #auto-ref { min-width:0; width:auto; }
  .profpop { position:absolute; top:calc(100% + 8px); right:0; z-index:150;
             display:flex; flex-direction:column; gap:10px; min-width:250px;
             background:rgba(4,6,9,.55); backdrop-filter:blur(4px) saturate(1.15); -webkit-backdrop-filter:blur(4px) saturate(1.15); border-radius:12px; padding:12px 14px;
             box-shadow:0 14px 34px rgba(0,0,0,.6); }
  .profpop select, .profpop .selwrap { min-width:0; width:100%; }
  .profpop .profbtns { display:flex; gap:8px; }
  .profpop .profbtns button { flex:1; }
  .sw { position:relative; display:inline-block; width:38px; height:21px; flex:none; vertical-align:middle; }
  .sw input { position:absolute; opacity:0; width:0; height:0; }
  .sw span { position:absolute; inset:0; border-radius:999px; cursor:pointer;
             transition:background .16s, box-shadow .16s; background:#000;
             box-shadow:inset 0 0 7px 3px #000, inset 0 0 2px rgba(0,0,0,.9); }
  .sw span::before { content:""; position:absolute; width:15px; height:15px; left:3px;
                     top:50%; transform:translateY(-50%);
                     border-radius:50%; transition:transform .16s;
                     background:radial-gradient(circle at 32% 28%, #6a7079 0%, #4d525a 38%, #34383e 68%, #212429 100%);
                     box-shadow:0 1px 2px rgba(0,0,0,.55), 0 0 6px 2px rgba(0,0,0,.45),
                                inset -1px -1px 2px rgba(0,0,0,.45), inset 1px 1px 2px rgba(255,255,255,.35); }
  .sw input:checked + span { background:var(--acc); }
  @supports (color: color-mix(in srgb, red 50%, transparent)) {
    .sw span { box-shadow:inset 0 0 7px 3px #000, inset 0 0 2px rgba(0,0,0,.9),
                          0 0 5px color-mix(in srgb, var(--acc) 28%, transparent); }
    .swlab:hover .sw span, .sw:hover span {
      box-shadow:inset 0 0 7px 3px #000, inset 0 0 2px rgba(0,0,0,.9),
                 0 0 11px 2px color-mix(in srgb, var(--acc) 72%, transparent); }
    .sw input:checked + span { box-shadow:0 0 6px color-mix(in srgb, var(--acc) 45%, transparent); }
    .swlab:hover .sw input:checked + span {
      box-shadow:0 0 13px 2px color-mix(in srgb, var(--acc) 85%, transparent); }
  }
  .sw input:checked + span::before { transform:translate(17px, -50%); }
  .sw input:disabled + span { opacity:.45; cursor:default; }
  .swlab { display:inline-flex; align-items:center; gap:8px; cursor:pointer; }
  .tsel { min-width:0 !important; width:auto; padding:5px 26px 5px 9px; background-position:right 8px center; }
  .tfont { max-width:170px; }
  .gputog { flex:none; display:flex; justify-content:flex-start; width:46px; }
  .gpuwrap { position:relative; display:inline-flex; align-items:center; }
  /* Both page headings are the same thing: a symbol and a title on one line. One class
     so they sit identically and behave as a single unit - which is what lets the guide
     light the pair with one rule instead of one per part. */
  .hdg { display:inline-flex; align-items:center; gap:9px;
         transition:color .18s ease, filter .18s ease;
         will-change:filter; }
  .hdg > svg { flex:0 0 auto; width:30px; height:22px; }
  .hdg > span { display:inline-flex; align-items:center; }

  /* The guide's highlight. It draws an outline and a halo AROUND whatever a step points
     at and touches nothing inside it, so the same rule serves a field, a panel or a
     heading. Nothing is recoloured and no artwork is redrawn, so there is nothing to
     fall out of step and nothing to shimmer. */
  @keyframes guideHL {
    0%   { box-shadow:var(--restglow), 0 0 0 0 rgba(250,166,26,0); }
    45%  { box-shadow:var(--restglow), 0 0 22px 5px rgba(250,166,26,.6); }
    100% { box-shadow:var(--restglow), 0 0 0 0 rgba(250,166,26,0); }
  }
  @keyframes guideShape {
    0%   { filter:drop-shadow(0 0 0 rgba(250,166,26,0)); }
    45%  { filter:drop-shadow(0 0 7px #faa61a); }
    100% { filter:drop-shadow(0 0 0 rgba(250,166,26,0)); }
  }
  .guidehl { animation:guideHL 2s ease-in-out 1; border-radius:9px; }
  .gcode { position:relative; cursor:pointer; font-family:Consolas,monospace;
           font-size:12.5px; line-height:1.6; white-space:pre-wrap; word-break:break-all;
           padding:9px 34px 9px 11px; margin:9px 0; border-radius:7px;
           background:rgba(255,255,255,.045); transition:background .14s; }
  .gcode:hover { background:rgba(255,255,255,.075); }
  .gcode .gcopy { position:absolute; top:8px; right:10px; color:var(--dim);
                  transition:color .14s; pointer-events:none; }
  .gcode:hover .gcopy { color:var(--acc); }
  @keyframes gcodePulse {
    0%   { box-shadow:0 0 0 0 rgba(0,0,0,0); }
    35%  { box-shadow:0 0 15px 3px var(--acc); }
    100% { box-shadow:0 0 0 0 rgba(0,0,0,0); }
  }
  .gcode.copied-flash { animation:gcodePulse .42s ease-out 1; }
  /* the TTS page is a long column of settings; without room they read as one blob */
  #dpane-tts .set > label { display:block; margin:20px 0 7px; font-weight:600; }
  #dpane-tts .set > label:first-of-type { margin-top:4px; }
  #dpane-tts .set > .row { margin-bottom:2px; }
  #dpane-tts .set > .hint { margin:7px 0 4px; line-height:1.7; }
  #dpane-tts .tgnote { margin:7px 0 4px !important; line-height:1.7; }
  #dpane-tts .tgroup { margin:24px 0 4px; padding-top:18px;
                       border-top:1px solid rgba(255,255,255,.07); }
  /* The branch under a spoken line. Drawn rather than typed: a stretched box glyph
     overlapped its neighbour and the glow doubled up at the join. An inline-block
     exactly one row tall meets the next one and no more. */
  .tail .tbr, .tail .tbrend { display:inline-block; position:relative;
                              width:2ch; height:1.6em; vertical-align:top; }
  .tail .tbr::before, .tail .tbrend::before { content:""; position:absolute;
                              left:.45ch; top:0; border-left:1.6px solid var(--acc);
                              box-shadow:0 0 4px var(--acc), 0 0 10px var(--acc), 0 0 20px var(--acc); }
  .tail .tbr::before    { height:100%; }        /* carries on to the next row */
  .tail .tbrend::before { height:50%; }         /* stops at the elbow */
  .tail .tbr::after, .tail .tbrend::after { content:""; position:absolute;
                              left:.45ch; top:50%; width:1.25ch;
                              border-top:1.6px solid var(--acc);
                              box-shadow:0 0 4px var(--acc), 0 0 10px var(--acc),
                                          0 0 20px var(--acc); }
  /* a section heading on the TTS page, with the rule that separates it from the last */
  #dpane-tts .tsect { margin:26px 0 10px; padding-top:16px; font-size:14px;
                      font-weight:700; letter-spacing:.4px; color:var(--txt);
                      border-top:1px solid rgba(255,255,255,.07); }
  #dpane-tts .tsect:first-child { margin-top:6px; padding-top:0; border-top:none; }
  /* the one step nothing can detect. Pulsing so it reads as waiting on you, not broken */
  .gmanual { margin-top:6px; font-size:11px; font-weight:700; letter-spacing:.04em;
             text-transform:uppercase; color:var(--ok); text-align:center;
             animation:gmanualPulse 1.9s ease-in-out infinite; }
  @keyframes gmanualPulse {
    0%, 100% { opacity:.62; text-shadow:0 0 4px rgba(181,243,32,.35); }
    50%      { opacity:1;   text-shadow:0 0 9px rgba(181,243,32,.95),
                                        0 0 18px rgba(181,243,32,.5); }
  }
  @media (prefers-reduced-motion: reduce) { .gmanual { animation:none; opacity:1; } }
  /* the one action on the page that does something big */
  .bigbtn { padding:9px 18px; font-size:14px; font-weight:700; letter-spacing:.3px;
            color:var(--acc); text-shadow:0 0 8px var(--acc), 0 0 18px var(--acc); }
  .bigbtn:hover { text-shadow:0 0 6px var(--acc), 0 0 16px var(--acc), 0 0 30px var(--acc); }
  .hdg.guidehl { animation:guideShape 2s ease-in-out 1; box-shadow:none; }
  /* Buttons are glowing text, not filled boxes: "button { box-shadow:none !important }"
     above, and an !important declaration overrides an animation - so the box-shadow
     highlight is invisible on any button. #launchBtn also carries filter:none !important,
     which rules out the drop-shadow variant too. Text-shadow is what actually shows,
     and it is what lbDemo and btnPulse already use on the same element. */
  @keyframes guideText {
    0%   { text-shadow:0 0 8px var(--bglow), 0 0 18px var(--bglow); }
    45%  { text-shadow:0 0 10px #faa61a, 0 0 26px #faa61a, 0 0 52px #faa61a; }
    100% { text-shadow:0 0 8px var(--bglow), 0 0 18px var(--bglow); }
  }
  button.guidehl, a.btnlink.guidehl { animation:guideText 2s ease-in-out 1; }
  .bgwrap, .profwrap, .refwrap { position:relative; display:inline-flex; align-items:center; }
  .bgpop { position:absolute; top:calc(100% + 8px); right:0; z-index:150; display:none;
           flex-direction:column; gap:4px; min-width:150px; padding:8px; border-radius:12px;
           background:rgba(4,6,9,.55); backdrop-filter:blur(4px) saturate(1.15); -webkit-backdrop-filter:blur(4px) saturate(1.15); box-shadow:0 14px 34px rgba(0,0,0,.6); }
  .bgwrap.on .bgpop { display:flex; }
  .bgopt { text-align:left; }
  .bgopt:hover { color:var(--acc); text-shadow:0 0 10px var(--acc); }
  .bgopt.on { color:var(--ok); text-shadow:0 0 9px var(--ok); }
  /* the chosen scaling mode is marked by a glow rather than a line of text */
  .tscale-btn:disabled { opacity:.35; }
  [id^="termscale-auto"].on, [id^="termscale-manual"].on {
    color:var(--ok); text-shadow:0 0 10px var(--ok); }
  .gputitle { cursor:pointer; user-select:none; }
  .gputitle:hover, .gputitle.on { color:var(--acc); filter:drop-shadow(0 0 6px var(--acc)); }

  .gpupop .row { flex-wrap:nowrap; white-space:nowrap; }
  .gpupop .uuid { margin-left:6px; }
  .gpupop { position:absolute; top:calc(100% + 14px); left:0; z-index:150; min-width:460px;
            background:rgba(4,6,9,.55); backdrop-filter:blur(4px) saturate(1.15); -webkit-backdrop-filter:blur(4px) saturate(1.15); border-radius:12px; padding:12px 14px; white-space:nowrap;
            box-shadow:0 14px 34px rgba(0,0,0,.6); }
  #card-gpus { padding-left:0; padding-right:0; background:transparent; margin-bottom:0; }
  .themecard { border:none !important; box-shadow:0 0 12px -2px rgba(0,0,0,.85); transition:box-shadow .12s; }
  .themecard:hover { box-shadow:0 0 0 1px var(--dim), 0 0 12px rgba(255,255,255,.14); }
  .themecard.on { box-shadow:0 0 0 2px var(--acc), 0 0 16px 2px var(--acc); }
  .themedel { position:absolute; right:6px; bottom:6px; color:var(--dim); cursor:pointer;
              line-height:0; padding:3px; transition:color .14s, filter .14s; }
  .themedel:hover { color:var(--err); filter:drop-shadow(0 0 7px var(--err)); }
  @keyframes themeGone {
    0%   { box-shadow:0 0 0 2px var(--err), 0 0 6px 1px var(--err); opacity:1; }
    22%  { box-shadow:0 0 0 3px var(--err), 0 0 26px 6px var(--err); opacity:1; }
    45%  { box-shadow:0 0 0 2px var(--err), 0 0 10px 2px var(--err); opacity:1; }
    100% { box-shadow:0 0 0 0 rgba(0,0,0,0), 0 0 0 0 rgba(0,0,0,0); opacity:0; transform:scale(.92); }
  }
  .themecard.themegone { animation:themeGone 1s ease-out forwards; pointer-events:none; }
  /* guide step boxes light up under the pointer */
  /* the setup diagram is ordinary page content: boxes are elements, only the
     connectors between them are drawn, and those are measured after layout */
  .gwrap { position:relative; margin-top:12px; }
  .glines { position:absolute; left:0; top:0; width:100%; height:100%;
            pointer-events:none; overflow:visible; z-index:0; }
  .ggrid { position:relative; z-index:1; display:grid; gap:44px 38px;
           grid-template-columns:repeat(auto-fill, minmax(196px, 1fr)); }
  .gstep { background:#12161d; border-radius:10px; padding:9px 12px 11px; cursor:pointer;
           box-shadow:0 0 0 2px currentColor; transition:box-shadow .14s, filter .14s; }
  .gstep.gok  { color:var(--ok); }
  .gstep.gbad { color:#ff5d5d; }
  .gstep.gskipped { box-shadow:0 0 0 2px currentColor; opacity:.85; }
  .gstep:hover { box-shadow:0 0 0 2px currentColor, 0 0 14px 1px currentColor; }
  .gstep .gtop { display:flex; align-items:center; gap:8px; }
  .gmarksvg { width:15px; height:15px; flex:none; }
  .gstep .gnum { font-size:13px; font-weight:600; }
  .gstep .glabel { color:var(--txt); font-size:12.5px; margin-top:4px; }
  .gbtn { margin-left:auto; color:var(--dim); line-height:0; padding:3px;
          border-radius:6px; transition:color .14s, filter .14s; }
  .gbtn svg { width:14px; height:14px; }
  .gbtn:hover { color:var(--acc); filter:drop-shadow(0 0 7px var(--acc)); }
  .gbtn.gdone { color:var(--ok); filter:drop-shadow(0 0 5px var(--ok)); }
  @keyframes gbtnPulse {
    0%   { filter:drop-shadow(0 0 3px var(--acc)); }
    40%  { filter:drop-shadow(0 0 16px var(--acc)); }
    100% { filter:drop-shadow(0 0 0 rgba(0,0,0,0)); } }
  .gbtn.gbtnpulse { animation:gbtnPulse .42s ease-out; }
  .gblines { position:absolute; left:0; top:0; width:100%; height:100%;
             pointer-events:none; overflow:visible; z-index:2;
             opacity:0; transition:opacity .5s ease; }
  .gbranch { position:absolute; z-index:3; display:none; align-items:center; gap:10px;
             background:rgba(8,10,14,.92); backdrop-filter:blur(10px);
             -webkit-backdrop-filter:blur(10px); border-radius:10px;
             padding:9px 12px; max-width:340px; color:var(--acc);
             box-shadow:0 0 0 2px currentColor, 0 10px 26px rgba(0,0,0,.6); transition:box-shadow .14s; }
  .gbranch { opacity:0; transition:box-shadow .14s, opacity .5s ease; }
  .gbranch.gshow { display:flex; }
  .gbranch.gshow.gvis { opacity:1; }
  .gbranch.gon { color:var(--ok); }
  .gbranch:hover { box-shadow:0 0 0 2px currentColor, 0 0 14px 1px currentColor; }
  .gbranch .gbtext { color:var(--txt); font-size:12px; }
  #navfly { position:fixed; left:14px; bottom:14px; z-index:180; display:flex; gap:8px; }
  .navfly-btn { background:none !important; background-color:transparent !important;
                border:none !important; box-shadow:none !important; backdrop-filter:none !important;
                color:var(--acc); padding:8px 11px; line-height:0; cursor:pointer; overflow:visible;
                transition:filter .14s, opacity .14s; }
  .navfly-btn::before, .navfly-btn::after { content:none !important; }
  #navfly, .navfly-btn, .navfly-btn svg { background:none !important; }
  .navfly-btn svg { width:18px; height:18px; overflow:visible; }
  .navfly-btn svg path { stroke:var(--acc); filter:drop-shadow(0 0 3px var(--acc));
                         transition:filter .14s, stroke-width .14s; }
  .navfly-btn:hover:not(:disabled) svg path {
    stroke-width:2.8; filter:drop-shadow(0 0 6px var(--acc)) drop-shadow(0 0 14px var(--acc)); }
  .navfly-btn:disabled { opacity:.3; cursor:default; }
  @keyframes navPulse {
    0%   { filter:drop-shadow(0 0 4px var(--acc)); }
    40%  { filter:drop-shadow(0 0 16px var(--acc)); }
    100% { filter:drop-shadow(0 0 3px var(--acc)); } }
  .navfly-btn.btnpulse svg path { animation:navPulse .4s ease-out; }
  #stackBtn { padding:5px 8px; }
  #stackBtn svg { filter:drop-shadow(0 0 3px rgba(94,232,141,.45)); transition:filter .16s; }
  #stackBtn:hover svg, #stackBtn.on svg { filter:drop-shadow(0 0 8px rgba(94,232,141,.95)); }
  .tlit { fill:#5ee88d; }
  .tlitstroke { stroke:#5ee88d; }
  #stackBtn.on { color:var(--acc); }
  /* everything sharing a row sits on the same centre line, whatever its size.
     the line-height reset matters: without it a large label's tall line box makes
     its text ride high against smaller neighbours even though the boxes centre. */
  header, .subtabs { align-items:center; }
  .row { align-items:center; }
  .row > * { line-height:1.25; }
  /* every row centres, so nothing needs singling out */
  .row > button, .row > select, .row > .selwrap, .row > input { display:inline-flex; align-items:center; }
  /* an emoji has taller metrics than text; on its own line box it cannot drag the
     words beside it off centre */
  .pemoji { display:inline-flex; align-items:center; line-height:1; margin-right:7px; }
  .ptitle { display:inline-flex; align-items:center; line-height:1.2; }
  header button { font-size:16.8px; padding:7px 11px; }
  header #stackBtn { padding:6px 9px; }
  header #stackBtn svg { width:21px; height:19px; }
  .msel.mok   { color:var(--ok); }
  .msel.mload { color:var(--warn); }
  .msel.mfail { color:var(--err); animation:mFail .6s ease-in-out 3; }
  @keyframes mFail {
    0%,100% { box-shadow:0 0 0 1px var(--err), 0 0 0 0 rgba(0,0,0,0); }
    50%     { box-shadow:0 0 0 1px var(--err), 0 0 15px 3px var(--err); } }
  .provlink { cursor:pointer; transition:color .14s, text-shadow .14s; }
  .provlink:hover { color:var(--pgl); text-shadow:0 0 10px var(--pgl); }
  .sampchip { border:none !important; background:transparent !important; padding:2px 5px;
              text-shadow:none; transition:text-shadow .16s; }
  .sampchip:hover { text-shadow:0 0 11px var(--sgl), 0 0 20px var(--sgl); }
  @keyframes lbDemo {
    0%   { text-shadow:0 0 18px var(--acc), 0 0 38px var(--acc); }
    66%  { text-shadow:0 0 18px var(--acc), 0 0 38px var(--acc); }
    100% { text-shadow:0 0 8px var(--acc), 0 0 18px var(--acc); } }
  #launchBtn.lbdemo, #launchTtsBtn.lbdemo { animation:lbDemo 3s linear forwards; }
  .alloclink { cursor:pointer; transition:text-shadow .14s; }
  .alloclink:hover { text-shadow:0 0 9px currentColor; }
  .gs-hlink { color: var(--acc); cursor: pointer; text-decoration: underline; text-underline-offset: 2px; white-space: nowrap; font-weight: 600; }
  .mand { display:inline-block; margin-left:8px; font-size:10px; font-weight:700; letter-spacing:.05em; color:var(--acc); background:rgba(181,243,32,.12);  border-radius:5px; padding:1px 6px; vertical-align:middle; text-transform:uppercase; }
  .gs-copy { color:var(--acc); cursor:pointer; text-decoration:underline; text-underline-offset:2px; font-weight:600; }
  /* the guide blocks pulse instead; an outline on top of that is two effects at once */
  .copied-flash:not(.gcode) { outline:2px solid var(--acc); outline-offset:2px; border-radius:6px; }
  .hb { filter: blur(3.5px); cursor: pointer; }
  input.hb:focus { filter: none; } .hb.show { filter: none; } .pswrap .pshl .hb { pointer-events: auto; position: relative; z-index: 2; }
  /* VS Code style YAML editor */
  .vsc-wrap { border:none; border-radius:6px; background:#1e1e1e; overflow:auto; max-height:460px; margin-top:8px; }
  .vsc-inner { display:flex; align-items:stretch; min-height:100%; width:max-content; min-width:100%; }
  .vsc-gutter { flex:0 0 auto; padding:10px 10px 10px 12px; text-align:right; color:#6e7681; background:#1e1e1e;
    font-family:'Consolas','Menlo','Courier New',monospace; font-size:13px; line-height:1.55; white-space:pre;
    user-select:none;  position:sticky; left:0; z-index:1; }
  .vsc-code { position:relative; flex:1 0 auto; min-width:0; }
  .vsc-hi, .vsc-ta { margin:0; padding:10px 14px; font-family:'Consolas','Menlo','Courier New',monospace; font-size:13px;
    line-height:1.55; white-space:pre; tab-size:2; -moz-tab-size:2; border:0; letter-spacing:0; }
  .vsc-hi { color:#d4d4d4; min-width:100%; box-sizing:border-box; display:block; }
  .vsc-ta { position:absolute; top:0; left:0; width:100%; height:100%; background:transparent; color:transparent;
    caret-color:#e6e6e6; resize:none; outline:none; overflow:hidden; box-sizing:border-box; white-space:pre; }
  .vsc-ta::selection { background:#264f78; color:transparent; }
  .vsc-ro .vsc-code { cursor:default; }
  .vt-com { color:#6a9955; } .vt-key { color:#9cdcfe; } .vt-str { color:#ce9178; }
  .vt-num { color:#b5cea8; } .vt-bool { color:#569cd6; } .vt-anc { color:#4ec9b0; } .vt-punct { color:#808080; }
  /* brand glow (title + icon) - short sunlight rays swivelling around the centre.
     4 rays at 90 deg apart rotated through 90 deg, so the loop is seamless. */
  /* four tight, hard-edged rays (0 blur = a spike, not a halo) sweeping a quarter turn */
  /* v2.46 soft swirl, now double-ended: two glow points opposite each other, orbiting */
  @keyframes brandRays {
    0%   { filter: drop-shadow( 3.5px 0 5px rgba(181,243,32,.75)) drop-shadow(-3.5px 0 5px rgba(181,243,32,.75)); }
    25%  { filter: drop-shadow(0  3.5px 5px rgba(181,243,32,.75)) drop-shadow(0 -3.5px 5px rgba(181,243,32,.75)); }
    50%  { filter: drop-shadow(-3.5px 0 5px rgba(181,243,32,.75)) drop-shadow( 3.5px 0 5px rgba(181,243,32,.75)); }
    75%  { filter: drop-shadow(0 -3.5px 5px rgba(181,243,32,.75)) drop-shadow(0  3.5px 5px rgba(181,243,32,.75)); }
    100% { filter: drop-shadow( 3.5px 0 5px rgba(181,243,32,.75)) drop-shadow(-3.5px 0 5px rgba(181,243,32,.75)); }
  }
  .card .card:not(.themecard), .card .stcard, .card .pg-card, #card-gpus { box-shadow:none; }
  .addcard { box-shadow:none; background:transparent; }
  #psub-tree-pane { border:none; box-shadow:none; background:transparent; }
  #psub-tree-pane .card, #psub-settings-pane .card { box-shadow:0 0 16px -1px rgba(0,0,0,.9); }
  .slotgrid .card { box-shadow:0 0 14px -2px rgba(0,0,0,.8); }
  .card .prov { box-shadow:0 0 16px -1px rgba(0,0,0,.9); }
  .card .logcard { box-shadow:0 0 14px -2px rgba(0,0,0,.8); }
  /* buttons on a see-through panel invert against whatever shows through, so they
     stay readable whether the interface behind them is light or dark */
  .profpop button, .refpop button, .bgpop button, .gpupop button, .rngpop button {
    mix-blend-mode:difference; color:#fff; }
  /* every dropdown in the app looks the same, wherever it sits: one background for the
     control and its list, with the text picked to contrast against it */
  select, select option, select optgroup {
    background:#0d0f13; color:var(--fieldtxt, var(--txt)); }
  .profpop select, .refpop select, .bgpop select, .gpupop select, .rngpop select,
  .profpop input, .refpop input, .gpupop input, .rngpop input {
    background:#0d0f13; color:var(--fieldtxt, var(--txt)); }
  .bluetag { color:#4da3ff; text-shadow:0 0 7px rgba(77,163,255,.45); }
  .chkmsg { margin-top:5px; }
  .tglyph { pointer-events:none; }
  .selwrap { position:relative; display:inline-flex; vertical-align:middle; }
  .selwrap > select { position:absolute; inset:0; width:100%; height:100%;
                      opacity:0; pointer-events:none; }
  .selbtn { position:relative; width:100%; box-sizing:border-box; text-align:left;
            padding:7px 30px 7px 12px; border:none; cursor:pointer; user-select:none;
            border-radius:8px; background:#0d0f13; color:var(--fieldtxt, var(--txt));
            font-size:13px; line-height:1.25; white-space:nowrap; overflow:hidden;
            text-overflow:ellipsis; transition:box-shadow .5s ease;
            --restglow:0 0 12px -2px rgba(0,0,0,.85);
            box-shadow:var(--restglow); }
  .selbtn::after { content:""; position:absolute; right:11px; top:50%; width:0; height:0;
                   transform:translateY(-40%); pointer-events:none;
                   border-left:4px solid transparent; border-right:4px solid transparent;
                   border-top:5px solid var(--dim); }
  .selwrap:hover .selbtn, .selwrap.on .selbtn {
            box-shadow:0 0 13px 2px color-mix(in srgb, var(--acc) 55%, transparent); }
  .selbtn.off { opacity:.45; cursor:default; }
  .sellist { position:absolute; top:calc(100% + 5px); left:0; min-width:100%;
             background:#0d0f13; border:none; border-radius:9px; padding:4px;
             box-shadow:0 10px 26px -6px rgba(0,0,0,.92), 0 0 16px -2px rgba(0,0,0,.85);
             z-index:80; max-height:46vh; overflow:auto; display:none; }
  .selwrap.on .sellist { display:block; }
  .selopt { padding:7px 11px; border-radius:6px; cursor:pointer; font-size:13px;
            white-space:nowrap; }
  .selopt:hover { background:rgba(255,255,255,.07); }
  .selopt.on { background:color-mix(in srgb, var(--acc) 18%, transparent); }
  .selopt.off { opacity:.4; cursor:default; }
  .setnote { min-height:1.1em; margin:4px 0 2px; font-size:12px; font-weight:600; }
  .pref { color:#4da3ff; cursor:pointer; font-size:inherit; margin-left:6px; transition:text-shadow .15s, color .15s; }
  .pref:hover { color:#8cc6ff; text-shadow:0 0 8px rgba(77,163,255,.95); }
  .pcell.pdim { opacity:.42; }
  .pcell.pdim, .pcell.pdim * { cursor:not-allowed; }
  .pcell input.pnum { width:124px; flex:none; text-align:left; -moz-appearance:textfield; appearance:textfield; }
  .pcell input.pnum::-webkit-outer-spin-button,
  .pcell input.pnum::-webkit-inner-spin-button { -webkit-appearance:none; margin:0; }
  .pcell input[type=range] { accent-color:var(--acc); }
  /* drag-resizable text panes (bottom-right corner) */
  pre.log.resizable { resize:both; overflow:auto; max-height:none; height:170px; min-height:60px; }
  .vsc-wrap { resize:both; }
  pre.tail.blackbg { background:#000 !important; }
  pre.tail { background:#0d0f13; border:none; box-shadow:0 0 14px -2px rgba(0,0,0,.8); border-radius:10px; padding:28px 12px 12px;
             font-family:Consolas,monospace; font-size:13px; line-height:1.5; white-space:pre-wrap; color:var(--txt);
             height:calc(100vh - 162px); overflow:auto; margin:0; }
  /* log-source line: overlays the top of the terminal so it never shifts the terminal box
     (split panes stay aligned whether or not a source line is present) */
  .tailbox { position:relative; }
  .tail-src { margin:0 0 6px; padding:4px 12px; line-height:17px; white-space:nowrap;
              overflow:hidden; text-overflow:ellipsis; background:#0d0f13; border-radius:8px; }
  .tail-src:empty { display:none; }
  body.remoteview .tail-src { display:none !important; }
  .ed { display:flex; background:#0d0f13; box-shadow:0 0 14px -2px rgba(0,0,0,.8); border:none; border-radius:10px; overflow:hidden; height:280px; resize:vertical; min-height:160px; }
  .ed pre.gut { margin:0; padding:10px 6px; text-align:right; color:#4a5162; background:#0a0c10;
                font:12.5px/1.5 Consolas,monospace; user-select:none; min-width:34px;
                height:100%; box-sizing:border-box; overflow:hidden; }
  .ed textarea { flex:1; background:transparent; color:var(--txt); border:0; outline:none;
                 padding:10px; font:12.5px/1.5 Consolas,monospace; height:100%; white-space:pre; }
  table { width:100%; border-collapse:collapse; font-size:12.5px; }
  th { text-align:left; color:var(--dim); font-weight:600; padding:6px 8px; border-bottom:1px solid var(--edge); }
  td { padding:6px 8px;  vertical-align:top; }
  td .p { font-family:Consolas,monospace; font-size:11px; color:var(--dim); word-break:break-all; }
  .set label { display:block; color:var(--dim); font-size:12px; margin:12px 0 4px; }
  h2 { font-size:15px; margin:20px 0 8px; }
  .hint { color:var(--dim); font-size:12px; }
  .logcardgrid { display:grid; grid-template-columns:repeat(auto-fill,minmax(240px,1fr)); gap:10px; margin-top:10px; }
  .logcard { background:#12161d; box-shadow:0 0 14px -2px rgba(0,0,0,.8); border:none; border-radius:10px; padding:11px 13px; }
  a.btnlink { background:#242833; color:var(--txt); border:1px solid var(--edge); border-radius:8px;
              padding:7px 14px; font-size:13px; font-weight:600; text-decoration:none; }
.hc { color: #6A9955; font-style: italic; } .hs { color: #CE9178; } .hv { color: #9CDCFE; }
.hk { color: #C586C0; } .hn { color: #B5CEA8; } .ht { color: #4EC9B0; } .hf { color: #DCDCAA; }
.pswrap { position: relative; flex: 1; display: flex; min-width: 0; height: 100%; }
.ed .gut, .pswrap textarea, .pswrap .pshl { font: 12.5px/1.5 Consolas, "Cascadia Mono", monospace; }
.pswrap textarea { flex: 1; position: relative; z-index: 1; background: transparent; color: transparent;
  caret-color: #e8ecf2; white-space: pre; overflow: scroll; padding: 8px 10px; box-sizing: border-box;
  scrollbar-width: auto; scrollbar-color: #3a4152 transparent; }
.pswrap textarea::-webkit-scrollbar { width: 13px; height: 13px; }
.pswrap textarea::-webkit-scrollbar-thumb { background: #3a4152; border-radius: 7px; border: 3px solid transparent; background-clip: content-box; }
.pswrap textarea::-webkit-scrollbar-thumb:hover { background: #4d5668; }
.pswrap .pshl { position: absolute; inset: 0; margin: 0; pointer-events: none; overflow: hidden;
  white-space: pre; color: #d4d4d4; background: transparent; padding: 8px 10px; box-sizing: border-box; }
.pswrap.wrap textarea { white-space: pre-wrap; overflow-wrap: anywhere; overflow-x: hidden; }
.pswrap.wrap .pshl { white-space: pre-wrap; overflow-wrap: anywhere; }
pre.tail.wrap { white-space: pre-wrap; overflow-wrap: anywhere; }
  .card { border-radius:12px; }
  button { border-radius:8px; }
  .go { background:var(--acc) !important; color:#111 !important; font-weight:600; border:none !important; }
  .go:hover { filter:brightness(1.08); }
  header button, nav button { background:#1a1b1e; }
  header .row > button, header .row > a.btnlink { margin-right:10px; }
  header button:hover, nav button:hover { background:#232529; }
  .tail, .log { font: 500 13.5px/1.6 "Cascadia Code", Consolas, monospace; color: #e8ecf2; }
  .hint { font-size: 13px; color: var(--dim); }
  .setup-lab { color: var(--txt); font-size: 14px; font-weight: 600; }
.tmax { position: fixed; inset: 0; z-index: 60; display: flex; flex-direction: column; background: var(--bg); padding: 0; }
/* Terminal chrome, both views: a slim always-there bar (source + Adjust + Full window)
   and a floating settings panel the Adjust button toggles OVER the terminal - never
   pushing it. Full Window adds edge-to-edge and the idle hide on top of the same parts. */
.tbar { display: flex; gap: 8px; align-items: center; margin-bottom: 6px;
            flex-wrap: wrap; row-gap: 4px; }
.tbar .tail-src { margin: 0; flex: 1 1 auto; min-width: 0; }
/* a narrow split pane has no room for four buttons in a row: let them wrap rather
   than overlap, and never let one be squeezed to nothing */
.tbar > button { flex: 0 0 auto; }
.tchrome { position: relative; }
.tpanel { display: none; position: absolute; top: 100%; left: auto; right: 0; z-index: 9;
          width: max-content; max-width: 100%; margin-top: 4px;
          background: rgba(13,16,22,.72); backdrop-filter: blur(2px);
          box-shadow: 0 0 14px -2px rgba(0,0,0,.85); border-radius: 10px; padding: 10px 12px 4px; }
.tchrome.adjopen .tpanel { display: block; }
.tmax .tchrome { position: absolute; top: 0; left: 0; right: 0; z-index: 9; padding: 6px 8px; pointer-events: none; }
.tmax .tchrome .tbar { margin-bottom: 0; }
.tmax .tbar > * , .tmax .tpanel { pointer-events: auto; }
.tmax .tchrome:not(.adjopen) .tbar .tail-src { visibility: hidden; }
.tmax .splitgrid > div { position: relative; }
.tmax .splitgrid .tchrome { z-index: 8; }
/* In full window the RIGHT pane's controls move into the outer bar, which is where its
   Adjust already went (#adjbtn-splitt is hidden). Both chromes are absolute at top:0, so
   leaving them in the pane put them underneath the outer ones. */
.tmax #tchrome-splitt .tbar > button { display: none; }
.tmaxonly { display: none; }
.tmax .tmaxonly { display: inline-block; }
.tmax #adjbtn-splitt { display: none; }
.tmax.hidechrome .tchrome { display: none; }
body.tmaxidle #navfly { display: none; }
.tmax .tail { border-radius: 0; }
.tmax .tailbox { flex: 1; min-height: 0; display: flex; flex-direction: column; }
.tmax .tail { flex: 1; height: auto; max-height: none; line-height: 1.6; }
  .tscale-btn { display: none; }
  .tmax .tscale-btn { display: inline-block; }
  .pg-intro { color:var(--dim); font-size:13px; line-height:1.6; margin:2px 0 14px; }
  .pg-intro b { color:var(--txt); }
  .pg-sec { font-size:15px; font-weight:700; color:var(--txt);  padding-bottom:6px; margin:24px 0 12px; }
  .pg-sub { color:var(--dim); font-weight:400; font-size:12px; margin-left:8px; }
  .pg-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(330px,1fr)); gap:12px; }
  .pg-card { background:var(--card); box-shadow:0 0 14px -2px rgba(0,0,0,.8); border:none; border-radius:12px; padding:14px 16px; }
  .pg-h { display:flex; align-items:center; gap:8px; flex-wrap:wrap; margin-bottom:8px; }
  .pg-name { font-size:16px; font-weight:700; color:var(--txt); }
  .pg-flag { font-family:Consolas,monospace; font-size:12px; background:#0d0f13;  color:var(--acc); border-radius:6px; padding:2px 7px; }
  .pg-def { font-size:11px; background:rgba(63,221,120,.12); color:var(--ok);  border-radius:999px; padding:2px 9px; font-weight:600; }
  .pg-what { font-size:13px; color:var(--txt); margin-bottom:10px; }
  .pg-gauge { position:relative; height:9px; border-radius:999px; background:linear-gradient(90deg,#3182ce,#38a169,#dd6b20); margin:8px 0 5px; }
  .pg-ref { color:#4da3ff; cursor:pointer; border-bottom:1px dotted rgba(77,163,255,.45); }
  .pg-ref:hover { text-shadow:0 0 7px rgba(77,163,255,.9); border-bottom-color:#4da3ff; }
  @keyframes pgHit { 0% { box-shadow:0 0 0 0 rgba(77,163,255,0); } 22% { box-shadow:0 0 0 3px rgba(77,163,255,.55); } 100% { box-shadow:0 0 0 0 rgba(77,163,255,0); } }
  .pg-hit { animation:pgHit 1.9s ease-out; border-color:#4da3ff !important; }
  .pg-lohi { display:flex; justify-content:space-between; font-size:10.5px; color:var(--dim); margin-bottom:11px; }
  .pg-how { font-size:12.5px; color:var(--dim); line-height:1.55; margin-bottom:10px; }
  .pg-sky { font-size:12.5px; line-height:1.55; background:rgba(181,243,32,.07); border-left:3px solid var(--acc); border-radius:0 8px 8px 0; padding:8px 11px; color:var(--txt); }
  .pg-sky b { color:var(--acc); font-weight:700; }
  .pg-fleet { font-size:12px; line-height:1.5; background:rgba(127,212,255,.08); border-left:3px solid #7fd4ff; border-radius:0 8px 8px 0; padding:7px 10px; margin-top:8px; color:var(--txt); }
  .pg-fleet b { color:#7fd4ff; font-weight:700; }
  .pg-chain { display:flex; flex-wrap:wrap; gap:6px; align-items:center; margin:2px 0 4px; }
  .pg-pill { font-family:Consolas,monospace; font-size:11.5px; background:#0d0f13; box-shadow:0 0 12px -2px rgba(0,0,0,.85); border-radius:999px; padding:3px 10px; color:var(--txt); }
  .pg-arrow { color:var(--dim); font-size:13px; }
  .pg-prof-h { display:flex; align-items:center; gap:9px; margin-bottom:4px; flex-wrap:wrap; }
  .pg-role { color:#0b0d11; font-size:11px; font-weight:700; border-radius:999px; padding:2px 11px; }
  .pg-kv { display:grid; grid-template-columns:max-content 1fr; gap:4px 12px; font-size:12px; margin-top:8px; }
  .pg-kv .k { color:var(--dim); }
  .pg-kv .v { color:var(--txt); font-family:Consolas,monospace; font-size:11.5px; }
  .sampcards { display:flex; flex-wrap:wrap; gap:6px; }
  .sampcard { font-size:12px; padding:4px 11px; border-radius:999px; background:#0d0f13;  color:var(--dim); cursor:pointer; font-family:inherit; line-height:1.3; }
  .sampcard:hover { border-color:var(--acc); color:var(--txt); }
  .sampcard.on { background:rgba(181,243,32,.14); border-color:var(--acc); color:var(--acc); font-weight:600; }
  .sampcard.reject { animation: sampReject .85s ease; }
  @keyframes sampReject { 0%,100% { background:#0d0f13; } 15%,45%,75% { background:var(--err); border-color:var(--err); color:#fff; } 30%,60% { background:#3a1414; border-color:var(--err); color:#fff; } }
#twrap-split.tmax .splitgrid { flex: 1; min-height: 0; }
#twrap-split.tmax .splitgrid > div { min-height: 0; }
#twrap-split.tmax .tail { max-height: none; height: auto; }
  .tail-cap { max-height: calc(100vh - 205px); }
  .tmax .tail-cap { max-height: none; }
.chip.clickable { cursor: pointer; }
#tail-thinking { color: #fff; }
  button, select, option, input, textarea { font-family: "Plus Jakarta Sans", Inter, "Segoe UI", system-ui, sans-serif; font-size: 13.5px; }
  .tail, .log, .pswrap textarea, .pswrap .pshl, .ed .gut { font-family: "Cascadia Code", Consolas, monospace !important; }
  @keyframes titleRays {
    0%   { text-shadow:  3px 0 7px rgba(181,243,32,.5), -3px 0 7px rgba(181,243,32,.5); }
    25%  { text-shadow: 0  3px 7px rgba(181,243,32,.5), 0 -3px 7px rgba(181,243,32,.5); }
    50%  { text-shadow: -3px 0 7px rgba(181,243,32,.5),  3px 0 7px rgba(181,243,32,.5); }
    75%  { text-shadow: 0 -3px 7px rgba(181,243,32,.5), 0  3px 7px rgba(181,243,32,.5); }
    100% { text-shadow:  3px 0 7px rgba(181,243,32,.5), -3px 0 7px rgba(181,243,32,.5); }
  }
  header img { animation: brandRays 9s linear infinite; }
  header h1 { animation: titleRays 9s linear infinite; }
  /* fleet status dot glows */
  @keyframes dotPulse { 0%,100% { filter: drop-shadow(0 0 2px var(--dg)); } 50% { filter: drop-shadow(0 0 10px var(--dg)); } }
  .fleet-dot-yellow { --dg:#eab308; animation: dotPulse 1.15s ease-in-out infinite; }
  .fleet-dot-red { --dg:#ef4444; animation: dotPulse 0.7s ease-in-out infinite; }
  .fleet-dot-green { filter: drop-shadow(0 0 5px #22c55e); }
  /* running button spinner */
  @keyframes spin360 { to { transform: rotate(360deg); } }
  .spin-emoji { display:inline-block; animation: spin360 1.9s linear infinite; }
  /* provider stat emoji hover */
  .stat-emoji { cursor:default; transition: filter .12s; }
  .stat-emoji:hover { filter: drop-shadow(0 0 4px rgba(181,243,32,.9)); }
  /* ---- buttons are glowing text rather than filled boxes ---- */
  button, a.btnlink {
    --bglow:var(--acc);
    background:transparent !important; border:none !important; box-shadow:none !important;
    color:var(--txt); padding:6px 9px; border-radius:6px; font-weight:600;
    transition:color .14s, text-shadow .14s; }
  button.stop, button.icon, a.btnlink { --bglow:#ffffff; }
  button.go, #launchBtn {
    --bglow:var(--acc);
    background:transparent !important; background-image:none !important;
    color:var(--acc) !important; border:none !important; filter:none !important; }
  button.x  { --bglow:var(--err); color:var(--dim); }
  button:hover:not(:disabled), a.btnlink:hover {
    color:var(--bglow); text-shadow:0 0 10px var(--bglow), 0 0 22px var(--bglow); }
  button:disabled { opacity:.4; cursor:default; text-shadow:none; }
  @keyframes btnPulse {
    0%   { text-shadow:0 0 10px var(--bglow), 0 0 22px var(--bglow); }
    35%  { text-shadow:0 0 22px var(--bglow), 0 0 44px var(--bglow); }
    100% { text-shadow:0 0 10px var(--bglow), 0 0 22px var(--bglow); } }
  button.btnpulse, a.btnlink.btnpulse { animation:btnPulse .38s ease-out; }
  button svg { transition:filter .14s; }
  button:hover:not(:disabled) svg { filter:drop-shadow(0 0 6px var(--bglow)); }
  #termBtn svg { color:var(--err); }
  #termBtn.livered svg { filter:drop-shadow(0 0 8px var(--err)); }
  #termBtn.livered:hover:not(:disabled) svg { filter:drop-shadow(0 0 14px var(--err)); }
  /* navigation keeps its shape - it has to show which tab is open */
  nav button, .subtabs button { background:transparent !important; border:none !important; }
  nav button { padding:9px 12px; white-space:nowrap; }
  .subtabs button { padding:9px 12px; }
  nav button.on, .subtabs button.on {
    color:var(--acc); text-shadow:0 0 10px var(--acc), 0 0 22px var(--acc); }
  nav button:hover, .subtabs button:hover { background:transparent !important; }
  /* ---- Launch: always lit, crackles on hover, throws longer arcs when pressed ---- */
  /* BOTH launch buttons. Keyed on the id alone, the TTS one had no arc overlay and no
     lit state - the rules simply never matched it. */
  #launchBtn, #launchTtsBtn { color:var(--acc);
                              text-shadow:0 0 8px var(--acc), 0 0 18px var(--acc);
                              letter-spacing:.4px; position:relative; }
  #launchBtn .alt, #launchTtsBtn .alt { position:relative; z-index:1; }
  /* the crackle rides on the arc effect, which is off by default - so the lift on
     hover is its own rule and always there */
  #launchBtn:hover, #launchTtsBtn:hover {
      text-shadow:0 0 6px var(--acc), 0 0 16px var(--acc), 0 0 30px var(--acc); }
  #launchBtn:hover .alt, #launchTtsBtn:hover .alt { opacity:1; }
  #termBtn { position:relative; z-index:3; }   /* its glow stays whole under the arcs */
  .arcsvg { position:absolute; left:0; top:0; width:100%; height:100%;
            overflow:visible; pointer-events:none; z-index:2; }
  /* Working, not off: dim the letters so it reads as busy, but leave the arcs alight.
     Dimming the button dimmed everything drawn inside it, arcs included. */
  #launchBtn.lbbusy, #launchTtsBtn.lbbusy { opacity:1; }
  #launchBtn.lbbusy .alt, #launchTtsBtn.lbbusy .alt { opacity:.4; }
  #launchBtn.lbbusy, #launchTtsBtn.lbbusy { cursor:default; }
  #launchBtn.lbload .arcbolt, #launchBtn.lbrun .arcbolt,
  #launchTtsBtn.lbload .arcbolt, #launchTtsBtn.lbrun .arcbolt {
            animation:none; opacity:1; stroke-width:2.2; filter:drop-shadow(0 0 7px #2ef2ff); }
  .arcbolt { pointer-events:none; fill:none; stroke:#2ef2ff; stroke-width:1.4; stroke-linecap:round;
             stroke-linejoin:round; filter:drop-shadow(0 0 4px #2ef2ff);
             animation:boltFade .17s linear forwards; }
  .arcbolt.strong { stroke-width:2.2; filter:drop-shadow(0 0 7px #2ef2ff);
                    animation:boltFade .3s linear forwards; }
  @keyframes boltFade { 0% { opacity:0 } 12% { opacity:1 } 55% { opacity:.9 } 100% { opacity:0 } }
  /* ---- Terminate: lit while anything is serving, fades out once it all stops ---- */
  #termBtn.livered { color:var(--err); text-shadow:0 0 9px var(--err), 0 0 20px var(--err); }
  @keyframes redPulse {
    0%,100% { text-shadow:0 0 8px var(--err), 0 0 16px var(--err); }
    50%     { text-shadow:0 0 20px var(--err), 0 0 38px var(--err); } }
  #termBtn.livered:hover:not(:disabled) { animation:redPulse 1.05s ease-in-out infinite; }
  @keyframes redFade {
    from { color:var(--err); text-shadow:0 0 9px var(--err), 0 0 20px var(--err); }
    to   { color:var(--txt); text-shadow:0 0 0 rgba(0,0,0,0), 0 0 0 rgba(0,0,0,0); } }
  #termBtn.fadered { animation:redFade 1.1s ease-out forwards; }
</style></head><body>
<header>
  <img src="/icon.ico?v=210" style="width:26px;height:26px;border-radius:6px" alt=""><h1 title="Pure awesomeness">PandorumLLM</h1><span class="ver" id="ver" data-act="verClick" role="button" tabindex="0"></span>
  <span id="fleet-dot" style="font-size:17px" title="fleet status: not running">⚫</span>
  <button class="go" id="launchBtn" data-hostonly onclick="launchStack(this)"><span class="alt">L</span><span class="alt">a</span><span class="alt">u</span><span class="alt">n</span><span class="alt">c</span><span class="alt">h</span><span class="alt"> </span><span class="alt">L</span><span class="alt">L</span><span class="alt">M</span><svg class="arcsvg" xmlns="http://www.w3.org/2000/svg"></svg></button>
  <button class="go" id="launchTtsBtn" data-hostonly onclick="launchTts(this)"><span class="alt">L</span><span class="alt">a</span><span class="alt">u</span><span class="alt">n</span><span class="alt">c</span><span class="alt">h</span><span class="alt"> </span><span class="alt">T</span><span class="alt">T</span><span class="alt">S</span><svg class="arcsvg" xmlns="http://www.w3.org/2000/svg"></svg></button>
  <button class="stop" id="stackBtn" data-hostonly data-act="stackToggle" title="Fleet server stack terminal"><svg viewBox="0 0 24 20" width="17" height="15" style="vertical-align:-3px"><rect x="1" y="1" width="22" height="18" rx="2.4" fill="#05070a"/><circle cx="19.4" cy="4.3" r="1.15" class="tlit"/><circle cx="15.8" cy="4.3" r="1.15" class="tlit"/><circle cx="12.2" cy="4.3" r="1.15" class="tlit"/><rect x="3.2" y="6.6" width="17.6" height="1.7" rx="0.85" class="tlit"/><path d="M4.4 10 8.4 12.9 4.4 15.8" fill="none" class="tlitstroke" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/><text class="tglyph tlit" x="16.4" y="15.9" font-size="8.6" font-family="Consolas,monospace" text-anchor="middle">_</text></svg></button><button class="stop" id="termBtn" data-hostonly onclick="terminateAll(this)"><svg viewBox="0 0 16 16" width="14" height="14" style="vertical-align:-2px;margin-right:6px"><path fill="currentColor" fill-rule="evenodd" d="M3.2 1.3h9.6c1.05 0 1.9.85 1.9 1.9v9.6c0 1.05-.85 1.9-1.9 1.9H3.2c-1.05 0-1.9-.85-1.9-1.9V3.2c0-1.05.85-1.9 1.9-1.9Zm2.6 4.5v4.4h4.4V5.8H5.8Z"/></svg>Terminate</button>
  <button class="stop" data-hostonly onclick="exitPanel(this)">&#9211; Exit</button>
  <span style="margin-left:auto;display:flex;align-items:center;gap:24px">
    <span style="display:contents"><span id="hdr-prof"></span></span>
    <span class="refwrap" id="refwrap">
      <span class="hdr-ico" data-act="refToggle" title="server UI auto refresh" role="button" tabindex="0">
        <svg viewBox="0 0 16 16" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="8" cy="8" r="6.4"/><path d="M8 4.4V8l2.5 1.7" stroke-linecap="round"/></svg>
      </span><span class="hdr-note" id="ref-now" data-act="refToggle" role="button" tabindex="0" title="server UI auto refresh"></span>
      <span class="refpop" id="refpop">
        <span class="hint" style="width:auto">Auto refresh</span>
        <select id="auto-ref" onchange="setAutoRef(this.value)" title="auto refresh interval">
          <option value="0">Off</option><option value="1">1s</option><option value="5">5s</option><option value="10">10s</option>
        </select>
      </span>
    </span>
  </span>
</header>
<pre class="log resizable" id="stacklog" style="margin:0 22px 8px;display:none"></pre>
<div class="wrap">
<nav>
  <button id="nav-network" class="on" onclick="showTab('network')">Live Network</button>
  <button id="nav-servers" onclick="showTab('servers')">Server</button>
  <button id="nav-tts" data-hostonly onclick="showTab('tts')">TTS</button>
  <button id="nav-provmgmt" onclick="showTab('provmgmt')">Provider</button>
  <button id="nav-dashboard" onclick="showTab('dashboard')">Proxy</button>
  <button id="nav-launcher" onclick="showTab('launcher')">Launcher</button>
  <button id="nav-setup" onclick="showTab('setup')">Folder Settings</button>
  <button id="nav-custom" onclick="showTab('custom')">Customization</button>
  <button id="nav-perms" onclick="showTab('perms')">Permissions</button>
  <button id="nav-helper" onclick="showTab('helper')">User Guide</button>
  <button id="nav-log" onclick="showTab('log')">Log</button>
</nav>
<main>
  <div id="tab-servers" style="display:none">
    <div class="subtabs">
      <button id="ssub-slots" class="on" onclick="showSsub('slots')">Servers</button>
      <button id="ssub-inspect" onclick="showSsub('inspect')">Server Editor</button>
      <button id="ssub-stats" onclick="showSsub('stats')">Server Statistics</button>
    </div>
    <div class="row" data-hostonly style="margin:-4px 0 10px">
      <span class="hint" id="slotcount" style="width:auto;margin-right:12px"></span>
      <button class="stop" data-act="restoreSrv" title="rebuild the shipped servers with their default parameters and launchers - any providers are moved to the unallocated row rather than removed">Restore default servers</button>
    </div>
    <div id="pane-slots"><div id="slots"></div>
      <h2>Launch History (last 50)</h2>
      <div class="card"><table><thead>
      <tr><th style="width:150px">Time</th><th style="width:150px">Slot</th><th style="width:60px">Port</th><th>Launcher</th></tr>
      </thead><tbody id="histbody"></tbody></table></div>
    </div>
    <div id="pane-inspect" style="display:none"></div>
    <div id="pane-stats" style="display:none">
      <div id="stats-header"></div>
      <div id="stpane-server"></div>
    </div>
  </div>
  <div id="tab-provmgmt" style="display:none">
    <div class="subtabs">
      <button id="pmsub-providers" class="on" onclick="showPmSub('providers')">Providers</button>
      <button id="pmsub-stats" onclick="showPmSub('stats')">Provider Statistics</button>
    </div>
    <div id="pmpane-providers"></div>
    <div id="pmpane-stats" style="display:none">
      <div id="pstats-header"></div>
      <div id="stpane-provider"></div>
    </div>
  </div>
  <div id="tab-network"></div>
  <div id="tab-launcher" style="display:none">
    <div class="subtabs">
      <button id="sub-creator" class="on" onclick="showSub('creator')">Creator</button>
      <button id="sub-inspector" onclick="showSub('inspector')">Inspector</button>

    </div>
    <div id="pane-creator" style="display:none"></div>
    <div id="pane-inspector" style="display:none"></div>
  </div>
  <div id="tab-dashboard" style="display:none">
    <div class="subtabs">
      <button id="dsub-term" class="on" onclick="showDsub('term')">Dashboard</button>
      <button id="dsub-setup" onclick="showDsub('setup')">Proxy Setup</button>
      <button id="dsub-yaml" data-hostonly onclick="showDsub('yaml')">SkyrimNet YAML</button>
    </div>
    <div id="dpane-term">
      <div class="row" style="gap:8px;margin-bottom:10px">
        <button id="tsub-proxy" class="stop on" onclick="showTsub('proxy')">Proxy Terminal</button>
        <button id="tsub-think" class="stop" onclick="showTsub('think')">Thinking Content Terminal</button>
        <button id="tsub-split" class="stop" onclick="showTsub('split')">Split View Terminal</button>
        <button id="tsub-tts" class="stop" onclick="showTsub('tts')">TTS Terminal</button>
        <span style="margin-left:auto"></span>
        <span class="bgwrap" id="bgwrap"><button class="stop" data-act="bgToggle" title="choose the terminal background">Terminal background color</button><span class="bgpop"><button class="stop bgopt" data-act="bgPick" data-v="0">Midnight</button><button class="stop bgopt" data-act="bgPick" data-v="1">Black</button></span></span>
      </div>
      <div id="tpane-proxy">
      <div id="twrap-dashboard"><div class="tchrome"><div class="tbar"><div class="hint tail-src" id="dash-src"></div><span style="margin-left:auto"></span><button class="stop" data-act="termStamps" data-kind="dashboard" title="show or hide the time on every line">Timestamps</button><button class="stop" data-act="termInsTts" title="show the spoken line under the newest dialogue completion">Insert TTS</button><button class="stop adjbtn" data-act="tmaxAdjust" title="show the font, size and source controls">Adjust</button><button class="stop" data-act="tailMax" data-kind="dashboard" id="tmaxbtn-dashboard">⛶ Full window</button></div><div class="tpanel"><div class="row" style="gap:8px;margin-bottom:6px;align-items:center;flex-wrap:wrap"><span class="hint" style="width:auto">Text Scaling:</span><button class="stop" data-act="termScaleMode" data-kind="dashboard" data-mode="auto" id="termscale-auto-dashboard">Auto</button><button class="stop" data-act="termScaleMode" data-kind="dashboard" data-mode="manual" id="termscale-manual-dashboard">Manual</button><button class="stop tscale-btn" data-act="termSizeReset" data-kind="dashboard" id="tscalebtn-dashboard">Default text size</button></div><div class="row" style="gap:8px;margin-bottom:6px;align-items:center;flex-wrap:wrap"><span id="termfs-wrap-dashboard" style="display:none;gap:8px;align-items:center"><span class="hint" style="width:auto">Size</span><select id="termfs-sel-dashboard" data-fskind="dashboard" class="tsel"></select></span><span class="hint" style="width:auto">Font</span><select id="termfont-sel-dashboard" data-fontkind="dashboard" class="tsel tfont"></select><span class="hint" id="termscale-msg-dashboard" style="margin-left:4px"></span></div></div></div><div class="tailbox"><pre class="tail" id="tail-dashboard"></pre></div></div>
      </div>
      <div id="tpane-think" style="display:none">
    <div id="twrap-thinking"><div class="tchrome"><div class="tbar"><div class="hint tail-src" id="think-src"></div><span style="margin-left:auto"></span><button class="stop" data-act="termStamps" data-kind="thinking" title="show or hide the time on every line">Timestamps</button><button class="stop adjbtn" data-act="tmaxAdjust" title="show the font, size and source controls">Adjust</button><button class="stop" data-act="tailMax" data-kind="thinking" id="tmaxbtn-thinking">⛶ Full window</button></div><div class="tpanel"><div class="row" style="gap:8px;margin-bottom:6px;align-items:center;flex-wrap:wrap"><span class="hint" style="width:auto">Text Scaling:</span><button class="stop" data-act="termScaleMode" data-kind="thinking" data-mode="auto" id="termscale-auto-thinking">Auto</button><button class="stop" data-act="termScaleMode" data-kind="thinking" data-mode="manual" id="termscale-manual-thinking">Manual</button><button class="stop tscale-btn" data-act="termSizeReset" data-kind="thinking" id="tscalebtn-thinking">Default text size</button></div><div class="row" style="gap:8px;margin-bottom:6px;align-items:center;flex-wrap:wrap"><span id="termfs-wrap-thinking" style="display:none;gap:8px;align-items:center"><span class="hint" style="width:auto">Size</span><select id="termfs-sel-thinking" data-fskind="thinking" class="tsel"></select></span><span class="hint" style="width:auto">Font</span><select id="termfont-sel-thinking" data-fontkind="thinking" class="tsel tfont"></select><span class="hint" id="termscale-msg-thinking" style="margin-left:4px"></span></div></div></div><div class="tailbox"><pre class="tail" id="tail-thinking"></pre></div></div>
      </div>
      <div id="tpane-split" style="display:none">
    <div id="twrap-split">
      <div class="tchrome"><div class="tbar" style="justify-content:flex-end"><button class="stop tmaxonly" data-act="termStamps" data-kind="splitt" title="show or hide the time on every line in the right terminal">Timestamps</button><button class="stop tmaxonly" id="splitins-t-max" data-act="termInsTts" title="show the spoken line under the newest dialogue completion">Insert TTS</button><button class="stop adjbtn tmaxonly" data-act="tmaxAdjust" data-tc="tchrome-splitt" title="font and size controls for the right terminal">Adjust</button><button class="stop" data-act="tailMax" data-kind="split" id="tmaxbtn-split">⛶ Full window</button></div></div>
      <div class="splitgrid" style="display:flex;gap:10px;align-items:stretch">
        <div style="flex:1;min-width:0;display:flex;flex-direction:column"><div class="tchrome"><div class="tbar"><select class="tsel" id="splitsel-d" data-act="splitFeed" data-side="d" title="which log this pane shows"></select><div class="hint tail-src" id="split-src-d"></div><span style="margin-left:auto"></span><button class="stop" data-act="termStamps" data-kind="splitd" title="show or hide the time on every line">Timestamps</button><button class="stop" id="splitins-d" data-act="termInsTts" title="show the spoken line under the newest dialogue completion">Insert TTS</button><button class="stop adjbtn" data-act="tmaxAdjust" title="show the font and size controls">Adjust</button></div><div class="tpanel"><div class="row" style="gap:8px;margin-bottom:6px;align-items:center;flex-wrap:wrap"><span class="hint" style="width:auto">Text Scaling:</span><button class="stop" data-act="termScaleMode" data-kind="splitd" data-mode="auto" id="termscale-auto-splitd">Auto</button><button class="stop" data-act="termScaleMode" data-kind="splitd" data-mode="manual" id="termscale-manual-splitd">Manual</button><button class="stop tscale-btn" data-act="termSizeReset" data-kind="splitd" id="tscalebtn-splitd">Default text size</button></div><div class="row" style="gap:8px;margin-bottom:6px;align-items:center;flex-wrap:wrap"><span id="termfs-wrap-splitd" style="display:none;gap:8px;align-items:center"><span class="hint" style="width:auto">Size</span><select id="termfs-sel-splitd" data-fskind="splitd" class="tsel"></select></span><span class="hint" style="width:auto">Font</span><select id="termfont-sel-splitd" data-fontkind="splitd" class="tsel tfont"></select><span class="hint" id="termscale-msg-splitd" style="margin-left:4px"></span></div></div></div><div class="tailbox" style="flex:1;min-height:0"><pre class="tail tail-cap" id="tail-splitd"></pre></div></div>
        <div style="flex:1;min-width:0;display:flex;flex-direction:column"><div class="tchrome" id="tchrome-splitt"><div class="tbar"><select class="tsel" id="splitsel-t" data-act="splitFeed" data-side="t" title="which log this pane shows"></select><div class="hint tail-src" id="split-src-t"></div><span style="margin-left:auto"></span><button class="stop" data-act="termStamps" data-kind="splitt" title="show or hide the time on every line">Timestamps</button><button class="stop" id="splitins-t" data-act="termInsTts" title="show the spoken line under the newest dialogue completion">Insert TTS</button><button class="stop adjbtn" id="adjbtn-splitt" data-act="tmaxAdjust" title="show the font and size controls">Adjust</button></div><div class="tpanel"><div class="row" style="gap:8px;margin-bottom:6px;align-items:center;flex-wrap:wrap"><span class="hint" style="width:auto">Text Scaling:</span><button class="stop" data-act="termScaleMode" data-kind="splitt" data-mode="auto" id="termscale-auto-splitt">Auto</button><button class="stop" data-act="termScaleMode" data-kind="splitt" data-mode="manual" id="termscale-manual-splitt">Manual</button><button class="stop tscale-btn" data-act="termSizeReset" data-kind="splitt" id="tscalebtn-splitt">Default text size</button></div><div class="row" style="gap:8px;margin-bottom:6px;align-items:center;flex-wrap:wrap"><span id="termfs-wrap-splitt" style="display:none;gap:8px;align-items:center"><span class="hint" style="width:auto">Size</span><select id="termfs-sel-splitt" data-fskind="splitt" class="tsel"></select></span><span class="hint" style="width:auto">Font</span><select id="termfont-sel-splitt" data-fontkind="splitt" class="tsel tfont"></select><span class="hint" id="termscale-msg-splitt" style="margin-left:4px"></span></div></div></div><div class="tailbox" style="flex:1;min-height:0"><pre class="tail tail-cap" id="tail-splitt"></pre></div></div>
      </div>
    </div>
      </div>
      <div id="tpane-tts" style="display:none">
    <div id="twrap-tts"><div class="tchrome"><div class="tbar"><div class="hint tail-src" id="tts-src"></div><span style="margin-left:auto"></span><button class="stop" data-act="termStamps" data-kind="tts" title="show or hide the time on every line">Timestamps</button><button class="stop adjbtn" data-act="tmaxAdjust" title="show the font, size and source controls">Adjust</button><button class="stop" data-act="tailMax" data-kind="tts" id="tmaxbtn-tts">&#9210; Full window</button></div><div class="tpanel"><div class="row" style="gap:8px;margin-bottom:6px;align-items:center;flex-wrap:wrap"><span class="hint" style="width:auto">Text Scaling:</span><button class="stop" data-act="termScaleMode" data-kind="tts" data-mode="auto" id="termscale-auto-tts">Auto</button><button class="stop" data-act="termScaleMode" data-kind="tts" data-mode="manual" id="termscale-manual-tts">Manual</button><button class="stop tscale-btn" data-act="termSizeReset" data-kind="tts" id="tscalebtn-tts">Default text size</button></div><div class="row" style="gap:8px;margin-bottom:6px;align-items:center;flex-wrap:wrap"><span id="termfs-wrap-tts" style="display:none;gap:8px;align-items:center"><span class="hint" style="width:auto">Size</span><select id="termfs-sel-tts" data-fskind="tts" class="tsel"></select></span><span class="hint" style="width:auto">Font</span><select id="termfont-sel-tts" data-fontkind="tts" class="tsel tfont"></select><span class="hint" id="termscale-msg-tts" style="margin-left:4px"></span></div></div></div><div class="tailbox"><pre class="tail" id="tail-tts"></pre></div></div>
      </div>
    </div>
    <div id="dpane-setup" style="display:none"></div>
    <div id="dpane-yaml" style="display:none"></div>
  </div>
  <div id="tab-tts" style="display:none">
    <div id="dpane-tts"></div>
  </div>
  <div id="tab-setup" style="display:none"></div>
  <div id="tab-custom" style="display:none"></div>
  <div id="tab-helper" style="display:none">
    <div class="subtabs">
      <button id="ugsub-main" class="on" onclick="showUgSub('main')">Main Guide</button>
      <button id="ugsub-params" onclick="showUgSub('params')">Sampler Guide</button>
      <button id="ugsub-tts" onclick="showUgSub('tts')">TTS Guide</button>
    </div>
    <div id="ugpane-main"></div>
    <div id="ugpane-params" style="display:none"></div>
    <div id="ugpane-tts" style="display:none"></div>
  </div>
  <div id="tab-log" style="display:none">
    <div class="subtabs">
      <button id="lsub-files" class="on" onclick="showLsub('files')">Files</button>
      <button id="lsub-errors" onclick="showLsub('errors')">Errors</button>
      <button id="lsub-debug" onclick="showLsub('debug')">Debug Report</button>
    </div>
    <div id="lpane-files"></div>
    <div id="lpane-errors" style="display:none"></div>
    <div id="lpane-debug" style="display:none"></div>
  </div>
  <div id="tab-perms" style="display:none"></div>
</main>
</div>
<div id="navfly" data-hostonly><button class="navfly-btn" data-act="navBack" title="previous page"><svg viewBox="0 0 16 16" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 3 5 8l5 5"/></svg></button><button class="navfly-btn" data-act="navFwd" title="next page"><svg viewBox="0 0 16 16" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 3l5 5-5 5"/></svg></button></div>
<script>
function reportable(m) {
  m = String(m || "");
  return m.indexOf("NetworkError when attempting") < 0 && m.indexOf("Failed to fetch") < 0;
}
window.addEventListener("error", function(e) { if (!reportable(e.message)) return; try { fetch("/api/client-error", { method: "POST", body: JSON.stringify({ msg: String(e.message || e.type), src: String(e.filename || ""), line: e.lineno || 0 }) }); } catch (x) {} });
window.addEventListener("unhandledrejection", function(e) { if (!reportable(e.reason)) return; try { fetch("/api/client-error", { method: "POST", body: JSON.stringify({ msg: "unhandledrejection: " + String(e.reason) }) }); } catch (x) {} });
const ICO = {
  copy: '<svg viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round" style="vertical-align:-1px"><rect x="5.6" y="5.6" width="8.2" height="8.8" rx="1.6"/><path d="M10.4 5.6V3.6A1.6 1.6 0 0 0 8.8 2H3.8A1.6 1.6 0 0 0 2.2 3.6v7A1.6 1.6 0 0 0 3.8 12h1.8"/></svg>',
  drive: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" style="vertical-align:-2px;flex:none"><rect x="3" y="5" width="18" height="14" rx="2" stroke="currentColor" stroke-width="1.7"/><circle cx="17" cy="12" r="1.3" fill="currentColor"/><path d="M6 9h6" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>',
  folder: '<svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor" style="vertical-align:-2px;flex:none"><path d="M10 4H4a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-8l-2-2z"/></svg>',
  file: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" style="vertical-align:-2px;flex:none"><path d="M6 2h8l4 4v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2z" stroke="currentColor" stroke-width="1.6"/><path d="M14 2v5h5" stroke="currentColor" stroke-width="1.6"/></svg>',
  eye: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" style="vertical-align:-2px;flex:none"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z" stroke="currentColor" stroke-width="1.7"/><circle cx="12" cy="12" r="2.6" stroke="currentColor" stroke-width="1.7"/></svg>',
};
let state = null, curTab = "network", curSub = "creator", curSsub = "slots", curPmSub = "providers", curUgSub = "main", statsData = null, statsTimer = null, curLsub = "files", errData = null, errRetain = 50, errPerPage = 10, errPage = 1, errTimer = null, models = null, tplBase = null;
const esc = s => String(s ?? "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
const $ = id => document.getElementById(id);

function portProblem(s) {
  if (s.status && s.status.state === "wedged")
    return "port already in use by another process - stop it or change the port";
  const mine = String(s.actualPort || s.port);
  let owners = 0;
  (state.slots || state.routing || []).forEach(x => { if (String(x.actualPort || x.port) === mine) owners++; });
  (state.routing || []).forEach(x => (x.providers || []).forEach(p => { if (String(p.port) === mine) owners++; }));
  if (String(state.panelPort) === mine) owners++;
  return owners > 1 ? "port collides with another slot / provider / the panel - change it" : "";
}
function pill(st) {
  const map = { serving:["serving","HTTP "+(st.http??"?")], loading:["loading","loading ("+(st.http??503)+")"],
                down:["down","down"], wedged:["wedged","port held, no HTTP"], unknown:["unknown","unknown"] };
  const [cls, txt] = map[st.state] || map.unknown;
  return '<span class="pill '+cls+'">'+txt+'</span>';
}
let curPsub = "tree";
function renderPerms() {
  const box = document.getElementById("tab-perms");
  if (!box) return;
  box.innerHTML =
    '<div class="subtabs">'
    + '<button id="psub-tree" class="'+(curPsub==="tree"?"on":"")+'" onclick="showPsub('+String.fromCharCode(39)+'tree'+String.fromCharCode(39)+')">Permission Tree</button>'
    + '<button id="psub-settings" class="'+(curPsub==="settings"?"on":"")+'" onclick="showPsub('+String.fromCharCode(39)+'settings'+String.fromCharCode(39)+')">Remote Access</button>'
    + '</div>'
    + '<div id="psub-tree-pane" style="display:'+(curPsub==="tree"?"":"none")+'">' + permTreeHtml() + '</div>'
    + '<div id="psub-settings-pane" style="display:'+(curPsub==="settings"?"":"none")+'">' + permSettingsHtml() + '</div>';
  if (curPsub === "settings") loadNetInfo();
}
function showPsub(s) {
  curPsub = s;
  ["tree","settings"].forEach(x => {
    const p = document.getElementById("psub-"+x+"-pane"), b = document.getElementById("psub-"+x);
    if (p) p.style.display = x === s ? "" : "none";
    if (b) b.classList.toggle("on", x === s);
  });
  if (s === "settings") loadNetInfo();
}
function permTreeHtml() {
  const C = { host:"#b5f320", remote:"#5aa9e6", deny:"#ef4444", line:"#3a3d44", box:"#12161d", txt:"#ececf1", dim:"#9aa0a8" };
  function node(x, y, w, h, stroke, title, sub) {
    // text sits on the middle of the box both ways. Where there are two lines they
    // straddle the middle; where there is one it sits on it, allowing for the fact that
    // a line of text hangs below its baseline.
    const cx = x + w / 2, cy = y + h / 2;
    return '<rect x="'+x+'" y="'+y+'" width="'+w+'" height="'+h+'" rx="10" fill="none" stroke="'+stroke
      + '" stroke-width="1" stroke-opacity=".3" style="filter:drop-shadow(0 0 5px '+stroke+')"/>'
      + '<text x="'+cx+'" y="'+(sub ? cy - 5 : cy + 5)+'" text-anchor="middle" fill="'+C.txt
      + '" font-size="15" font-weight="700">'+esc(title)+'</text>'
      + (sub ? '<text x="'+cx+'" y="'+(cy + 13)+'" text-anchor="middle" fill="'+C.dim
             + '" font-size="11.5">'+esc(sub)+'</text>' : '');
  }
  // SVG text does not wrap, so a long line ran straight into the next column. Break it
  // at word boundaries and report how tall it ended up, so the caller can advance.
  const LI_CHARS = 52, LI_STEP = 26, LI_WRAP = 16;
  function li(x, y, mark, label, col) {
    const words = String(label).split(" ");
    const rows = [];
    let cur = "";
    words.forEach(w => {
      if (cur && (cur + " " + w).length > LI_CHARS) { rows.push(cur); cur = w; }
      else { cur = cur ? (cur + " " + w) : w; }
    });
    if (cur) rows.push(cur);
    let out = "";        // not "svg": the outer builder uses that name
    rows.forEach((r, i) => {
      out += '<text x="' + (i ? x + 12 : x) + '" y="' + (y + i * LI_WRAP)
           + '" fill="' + col + '" font-size="12.5">'
           + (i ? "" : mark + " ")
           + '<tspan fill="' + C.dim + '">' + esc(r) + '</tspan></text>';
    });
    return { svg: out, h: LI_STEP + (rows.length - 1) * LI_WRAP };
  }
  const hostItems = ["Launch / Terminate / Exit the fleet",
                     "Create & edit launcher templates (.ps1)",
                     "Assign launchers, swap models",
                     "Edit sampler params, reset them, thinking source",
                     "Folder Settings, model folder, all file & log access",
                     "Generate providers.yaml, IP & GPU settings",
                     "Add / remove / restore providers",
                     "Save, load and delete profiles (files in profiles\\)",
                     "Provider Statistics, and turning monitoring on or off",
                     "TTS setup, writing its launcher, starting and stopping its server",
                     "One-click Higgs install: fetches audio.cpp and a model from the internet",
                     "Checking for a newer audio.cpp (asks github.com only when pressed)",
                     "Main Guide setup flow"];
  const remoteItems = ["View all terminals (Proxy / Thinking / Split / TTS)",
                       "Full-window, wrap, background colour",
                       "Live Network graph & fleet status",
                       "Providers and their allocation, read-only",
                       "Read-only - changes nothing on the host",
                       "Proxy Setup, SkyrimNet YAML, TTS and Provider Statistics are not offered",
                       "IP / GPU / yaml panels are hidden entirely",
                       "Any IPs and file paths are masked before being sent",
                       "Terminal TEXT is not: dialogue, reasoning and character names show",
                       "The statistics endpoint is not answered at all"];
  // The box is sized to whatever the columns came to, since a wrapped bullet adds a row
  // and a fixed height would clip the bottom of the longest column.
  let svg = '<svg viewBox="0 0 1180 __H__" width="100%" style="max-width:1180px;background:#0d0e10;border:none;border-radius:12px">';
  // root
  svg += node(470, 20, 240, 56, "#6b7280", "Incoming request", "which machine is it from?");
  // connectors
  svg += '<path d="M590 76 L590 100 M190 100 L990 100 M190 100 L190 130 M590 100 L590 130 M990 100 L990 130" stroke="'+C.line+'" stroke-width="2" fill="none"/>';
  // three branches
  svg += node(40, 130, 300, 64, C.host, "This PC (localhost)", "the AI PC running the panel");
  svg += node(440, 130, 300, 64, C.remote, "Same-LAN remote PC", "another PC on your network");
  svg += node(840, 130, 300, 64, C.deny, "Outside / unknown", "anything not on your LAN");
  // host branch
  svg += node(40, 230, 300, 40, C.host, "FULL CONTROL", "");
  let hy = 300;
  hostItems.forEach(it => { const r = li(48, hy, "\u2713", it, C.host); svg += r.svg; hy += r.h; });
  // remote branch
  svg += node(440, 230, 300, 40, C.remote, "READ-ONLY", "");
  let ry = 300;
  remoteItems.forEach(it => { const r = li(448, ry, "\u25CF", it, C.remote); svg += r.svg; ry += r.h; });
  // deny branch
  svg += node(840, 230, 300, 40, C.deny, "REJECTED", "");
  svg += li(848, 300, "\u2715", "Request refused at the door", C.deny).svg;
  svg += li(848, 326, "\u2715", "Also blocks malicious web pages", C.deny).svg;
  svg += li(848, 352, "\u2715", "and DNS-rebinding attempts", C.deny).svg;
  // connectors to leaves
  svg += '<path d="M190 194 L190 230 M590 194 L590 230 M990 194 L990 230" stroke="'+C.line+'" stroke-width="2" fill="none"/>';
  svg += '</svg>';
  svg = svg.replace("__H__", String(Math.max(650, hy + 20, ry + 20)));
  return svg
    + '<div class="hint" style="margin-top:12px;line-height:1.6">These rules are enforced by the panel itself on every request - not by hiding buttons in the browser - so a read-only remote session genuinely cannot perform host actions or read hidden values, even by crafting its own request.</div>';
}
function permSettingsHtml() {
  return '<div class="card">'
    + '<div class="row" style="gap:10px;align-items:center;flex-wrap:wrap"><b>Remote Access</b>'
    +   '<button id="netmode-on" class="stop" onclick="setNetMode(true)">On</button>'
    +   '<button id="netmode-off" class="stop" onclick="setNetMode(false)">Off</button>'
    +   '<span class="hint" id="netmode-state"></span></div>'
    + '<div class="hint" style="margin:10px 0 4px;line-height:1.6">By default the panel is reachable only from this PC. Turn this <b>On</b> to also open the read-only view from other PCs on your network. Other PCs can watch, but cannot change anything or see your IPs, paths, or GPU IDs. Turn it <b>Off</b> to remove that access.</div>'
    + '<div id="netmode-url" class="hint" style="margin-top:8px"></div>'
    + '<div id="netmode-note" style="margin-top:10px;line-height:1.5;font-weight:600"></div>'
    + '<div class="hint" style="margin-top:10px;line-height:1.6">Note: the first time you enable this, Windows may ask to allow PandorumLLM on private networks - click Allow (Private). SkyrimNet itself connects to the model servers directly and is unaffected by this setting.</div>'
    + '</div>';
}
async function loadNetInfo() {
  try {
    const r = await post("/api/network-info", {});
    window.__net = r;
    const bon = document.getElementById("netmode-on"), boff = document.getElementById("netmode-off"), st = document.getElementById("netmode-state"), url = document.getElementById("netmode-url");
    const on = r.mode === "lan";
    if (bon) bon.classList.toggle("on", on);
    if (boff) boff.classList.toggle("on", !on);
    if (st) st.innerHTML = on
      ? '<span style="color:var(--ok)">ON - other PCs on your LAN can open the read-only view</span>'
      : "OFF - only this PC can open the panel";
    if (url) url.innerHTML = (r.mode === "lan" && r.lanUrl)
      ? ('Open from another PC at: <b class="hb" style="color:#4da3ff;text-shadow:0 0 7px rgba(77,163,255,.6),0 0 2px rgba(77,163,255,.9)">' + esc(r.lanUrl) + '</b>')
      : "";
    const note = document.getElementById("netmode-note");
    if (note) note.innerHTML = on ? "" : '<span style="color:var(--warn)">Remote access is OFF - only this PC can open the panel.</span>';
  } catch (e) {}
}
async function setNetMode(on) {
  const cur = (window.__net && window.__net.mode) || "localhost";
  if ((cur === "lan") === on) { await loadNetInfo(); return; }   // already in that state
  if (on) {
    if (!await uiConfirm("Allow other PCs on your network to open the read-only view?" + String.fromCharCode(10) + String.fromCharCode(10)
      + "They will be able to watch the terminals and fleet status, but cannot change anything on this PC and cannot see your IPs, paths, or GPU IDs." + String.fromCharCode(10) + String.fromCharCode(10)
      + "This takes effect immediately - no restart needed.")) { await loadNetInfo(); return; }
  }
  const r = await post("/api/settings", { networkMode: on ? "lan" : "localhost" });
  if (r && r.error) { uiAlert(r.error); return; }
  await loadNetInfo();
}
// pages the user has been through, so the corner arrows can walk back and forward
let navHist = [], navAt = -1, navJump = false;
function navSync() {
  const b = document.querySelector('[data-act="navBack"]');
  const f = document.querySelector('[data-act="navFwd"]');
  if (b) b.disabled = navAt <= 0;
  if (f) f.disabled = navAt < 0 || navAt >= navHist.length - 1;
}
function navGo(step) {
  const i = navAt + step;
  if (i < 0 || i >= navHist.length) return;
  navAt = i;
  navJump = true;                                 // a jump is not a new visit
  showTab(navHist[i]);
  navJump = false;
  navSync();
}
function showTab(t) {
  trace("you", "opened " + t);
  if (!navJump && navHist[navAt] !== t) {
    navHist = navHist.slice(0, navAt + 1);        // a new visit drops anything ahead
    navHist.push(t);
    if (navHist.length > 60) navHist.shift();
    navAt = navHist.length - 1;
  }
  navSync();
  curTab = t;
  ["servers","tts","provmgmt","network","launcher","dashboard","setup","log","helper","custom","perms"].forEach(x => {
    $("tab-"+x).style.display = x === t ? "" : "none";
    $("nav-"+x).classList.toggle("on", x === t);
  });
  if (t === "servers") { loadModels().then(function() { showSsub(curSsub === "stats" ? "stats" : "slots"); }); }
  if (t === "provmgmt") showPmSub(curPmSub);
  if (t === "network") renderNetwork();
  if (t === "setup") { renderSetup(); wireLlamaCheck(); recheckPaths(); }
  guideWatch(t === "helper");
  if (t === "log") showLsub(curLsub);

  if (t === "helper") showUgSub(curUgSub);
  if (t === "custom") renderCustom();
  if (t === "perms") renderPerms();
  if (t === "setup") setTimeout(wireLlamaCheck, 60);

  if (t === "tts") { ttsModels = null; renderTts(); }
  if (t === "dashboard") showDsub(curDsub);
  if (t === "launcher") showSub(curSub === "inspector" ? "inspector" : "creator");
}
function showSub(s) {
  curSub = s;
  ["creator","inspector"].forEach(x => {
    $("pane-"+x).style.display = x === s ? "" : "none";
    $("sub-"+x).classList.toggle("on", x === s);
  });
  if (s === "creator") renderCreator();
  if (s === "inspector") renderInspector();
}
// ITEM 12: User Guide holds the step-by-step guide and the sampler reference
function showUgSub(s) {
  curUgSub = s;
  ["main", "params", "tts"].forEach(x => {          // one list, so another guide is one entry
    const p = $("ugpane-" + x), b = $("ugsub-" + x);
    if (p) p.style.display = x === s ? "" : "none";
    if (b) b.classList.toggle("on", x === s);
  });
  if (s === "params") renderParams();
  else if (s === "tts") renderTtsGuide();
  else renderHelper();
}
// generic click-to-copy for a code span, so a URL can be copied without the app
// ever making an outbound request of its own
function copyCode(el) {
  // textContent would include the icon's own node; take only the text that is the point
  let t = "";
  if (el) {
    el.childNodes.forEach(n => {
      if (n.nodeType === 3) t += n.nodeValue;
      else if (!(n.classList && n.classList.contains("gcopy"))) t += n.textContent || "";
    });
    t = t.trim() || el.textContent || "";
  }
  const flash = () => { el.classList.add("copied-flash"); setTimeout(() => el.classList.remove("copied-flash"), 1000); };
  if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(t).then(flash, flash);
  else flash();
}

function showSsub(s) {
  curSsub = s;
  $("pane-slots").style.display = s === "slots" ? "" : "none";
  $("pane-inspect").style.display = s === "inspect" ? "" : "none";
  $("pane-stats").style.display = s === "stats" ? "" : "none";
  $("ssub-slots").classList.toggle("on", s === "slots");
  $("ssub-inspect").classList.toggle("on", s === "inspect");
  $("ssub-stats").classList.toggle("on", s === "stats");
  if (s === "stats") renderStats();
  else if (s === "inspect") renderSrvInspector();
  else renderSlots();
}
// Server Editor: read-only by default, unlocked with the padlock. Saving re-reads the
// parameters out of the text, so the server cards stay a true view of what will run.
let srvEd = { hist: [], at: -1, locked: null };   // null = not yet taken from settings
function renderSrvInspector() {
  if (!state) return;
  const pane = $("pane-inspect");
  if (!pane) return;
  const opts = (state.slots || []).map(function(s) {
    return '<option value="' + esc(s.id) + '"' + (s.id === window.__srvInspId ? " selected" : "") + '>'
      + esc((s.label || s.id) + "  :" + s.port) + '</option>';
  }).join("");
  if (srvEd.locked === null) srvEd.locked = !((state.settings || {}).srvEdOpen);
  const lk = srvEd.locked;
  pane.innerHTML = '<div class="card"><div class="row" style="gap:8px;align-items:center">'
    + '<span class="hint" style="width:auto">Server</span>'
    + '<select id="srvinsp-sel" style="min-width:280px" data-act="srvInspSel">' + opts + '</select>'
    + '<button class="stop" data-act="srvEdLock" title="' + (lk ? "currently read-only - click to edit" : "editing enabled - click to lock") + '">'
    + (lk ? "[ Locked ]  Inspector Mode" : "[ Open ]  Editor Mode") + '</button>'
    + '<button class="stop" data-act="srvEdUndo" title="undo"' + (lk ? " disabled" : "") + '>\u21B6</button>'
    + '<button class="stop" data-act="srvEdRedo" title="redo"' + (lk ? " disabled" : "") + '>\u21B7</button>'
    + '<button class="stop" data-act="srvEdValidate" title="read every line the way the panel will, and say what it made of each">Validate</button>'
    + '<button class="stop" data-act="srvEdSave" title="save this launcher and re-read the parameters from it"' + (lk ? " disabled" : "") + '>Save</button>'
    + '<button class="stop" data-act="srvEdRevert" title="go back to the launcher in place before the last save or load">Revert</button>'
    + '<button class="stop" data-act="srvEdDefault" title="discard the hand-edited launcher and rebuild it from the parameters">Revert to default</button>'
    + '</div>'
    + '<div class="row" style="gap:8px;margin-top:8px;align-items:center">'
    + '<span class="hint" style="width:auto">Load launcher</span>'
    + '<select id="srvinsp-path-in" style="min-width:300px" data-act="srvEdOpen"' + (lk ? " disabled" : "") + '>'
    + '<option value="">&#8212; pick a .ps1 from your launcher folder &#8212;</option>'
    + (state.launchers || []).map(function(l) {
        const on = (window.__srvEdPath && window.__srvEdPath === l.path) ? " selected" : "";
        return '<option value="' + esc(l.path) + '"' + on + '>' + esc(l.name + (l.port ? "  :" + l.port : "")) + '</option>';
      }).join("")
    + '</select>'
    + '<span class="hint" id="srvinsp-path"></span></div>'
    + '<div class="hint" id="srvinsp-note" style="margin-top:6px"></div>'
    + '<textarea id="srvinsp-view" class="edit srved" spellcheck="false" style="width:100%;height:52vh;margin-top:10px;'
    + 'font-family:Consolas,monospace;font-size:12.5px;line-height:1.5;white-space:pre;overflow:auto"'
    + (lk ? " readonly" : "") + '></textarea>'
    + '<pre class="log" id="srvval" style="display:none;margin-top:10px;max-height:34vh;overflow:auto"></pre>'
    + '</div>';
  srvInspect();
}
async function srvInspect() {
  const sel = $("srvinsp-sel");
  if (!sel) return;
  if (!sel.value) { const v0 = $("srvinsp-view"); if (v0) v0.value = "(no servers configured)"; return; }
  window.__srvInspId = sel.value;
  const r = await post("/api/slot-launcher", { slot: sel.value });
  const view = $("srvinsp-view");                // look it up again: the pane may have
  if (!view) return;                             // been redrawn while we were waiting
  const path = $("srvinsp-path"), note = $("srvinsp-note");
  if (r.error) { view.value = r.error; if (path) path.textContent = ""; return; }
  if (path) path.textContent = r.path;
  // the picker mirrors the launcher actually saved on this server - not a session
  // variable - so it survives restarts. A saved path outside the launcher folder
  // (a hand-edit in generated-launchers) is shown as a synthetic "(current)" entry.
  const pick = r.src || r.path || "";        // the file the user chose, not the copy
  window.__srvEdPath = pick;
  const pin = $("srvinsp-path-in");
  if (pin && pick) {
    let has = false;
    for (const o of pin.options) if (o.value === pick) { has = true; break; }
    if (!has) {
      const o = document.createElement("option");
      o.value = pick;
      o.textContent = pick.split(String.fromCharCode(92)).pop()
        + (r.src ? "  (loaded" : "  (current") + (r.custom ? ", hand-edited)" : ")");
      pin.insertBefore(o, pin.options[1] || null);
    }
    pin.value = pick;
  }
  view.value = r.content || "";
  srvEd.hist = [view.value]; srvEd.at = 0;
  if (note) {
    const slot = (state.slots || []).filter(x => x.id === sel.value)[0];
    const mdl = (slot && slot.params) ? slot.params.model : "";
    const known = (models || []).some(function(m) { return (m.path || m) === mdl; });
    note.innerHTML = (r.custom
        ? '<span style="color:var(--warn)">hand-edited launcher in use - Revert to Default rebuilds it from the parameters</span>'
        : (r.waiting
            ? '<span style="color:var(--warn)">preview - the launcher this server will have once a model is chosen; nothing is saved or launched from it yet</span>'
            : 'built from this server' + String.fromCharCode(39) + 's parameters'))
      + ((mdl && !known) ? ' &middot; <span style="color:#ff5d5d">Model not found, select a model</span>' : '');
  }
}
function srvEdPush() {
  const view = $("srvinsp-view");
  if (!view) return;
  srvEd.hist = srvEd.hist.slice(0, srvEd.at + 1);
  srvEd.hist.push(view.value);
  if (srvEd.hist.length > 60) srvEd.hist.shift();
  srvEd.at = srvEd.hist.length - 1;
}
function srvEdStep(delta) {
  const view = $("srvinsp-view");
  const i = srvEd.at + delta;
  if (!view || i < 0 || i >= srvEd.hist.length) return;
  srvEd.at = i;
  view.value = srvEd.hist[i];
}
async function srvEdValidate() {
  const box = $("srvval"), view = $("srvinsp-view");
  if (!box || !view) return;
  box.style.display = "block";
  box.textContent = "reading...";
  const r = await post("/api/validate-launcher", { content: view.value });
  box.textContent = (r && r.error) ? r.error : ((r && r.text) || "(nothing came back)");
}
async function srvEdAction(act) {
  const sel = $("srvinsp-sel"), view = $("srvinsp-view");
  if (!sel || !sel.value) return;
  let r = null;
  if (act === "save") r = await post("/api/slot-launcher-save", { slot: sel.value, content: view.value });
  else if (act === "revert") r = await post("/api/slot-launcher-revert", { slot: sel.value });
  else if (act === "default") r = await post("/api/slot-launcher-default", { slot: sel.value });
  else if (act === "open") {
    const pin = $("srvinsp-path-in");
    r = await post("/api/slot-launcher-load", { slot: sel.value, path: pin ? pin.value : "" });
  }
  const note = $("srvinsp-note");
  if (r && r.error) { if (note) note.innerHTML = '<span style="color:#ff5d5d">' + esc(r.error) + '</span>'; return; }
  await load();
  renderSrvInspector();
}function showPmSub(s) {
  curPmSub = s;
  $("pmpane-providers").style.display = s === "providers" ? "" : "none";
  $("pmpane-stats").style.display = s === "stats" ? "" : "none";
  $("pmsub-providers").classList.toggle("on", s === "providers");
  $("pmsub-stats").classList.toggle("on", s === "stats");
  if (s === "stats") renderStats(); else renderProviders();
}
const STAT_COLORS = ["#3fdd78","#7fd4ff","#c084fc","#eab308","#f472b6","#38bdf8","#fb923c","#a3e635"];
const stColor = i => STAT_COLORS[i % STAT_COLORS.length];
function stNum(v) { return Math.round(v || 0).toLocaleString(); }
function stK(v) { v = v || 0; return v >= 1e6 ? (v / 1e6).toFixed(1) + "M" : v >= 1e3 ? (v / 1e3).toFixed(1) + "K" : Math.round(v).toString(); }
function stMs(v) { v = v || 0; return v >= 1000 ? (v / 1000).toFixed(1) + " s" : Math.round(v) + " ms"; }
function stTps(v) { return Math.round(v || 0) + " t/s"; }
function stPct(v) { return Math.round(v || 0) + "%"; }
function st1(v) { return (v || 0).toFixed(1); }
function modelBase(m) {
  if (!m) return "";
  m = String(m);
  const i = Math.max(m.lastIndexOf("/"), m.lastIndexOf(String.fromCharCode(92)));
  let b = i >= 0 ? m.slice(i + 1) : m;
  if (b.toLowerCase().slice(-5) === ".gguf") b = b.slice(0, -5);
  return b;
}
function niceTicks(maxV, want) {
  if (maxV <= 0) return { top: 1, step: 1 };
  const raw = maxV / want;
  const pow = Math.pow(10, Math.floor(Math.log10(raw)));
  const n = raw / pow;
  const step = (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * pow;
  return { top: Math.ceil(maxV / step) * step, step: step };
}
function statChart(items, fmt, opt) {
  opt = opt || {};
  // vertical bars grow UP from a baseline; numeric scale + dashed gridlines on the Y axis,
  // category (model / provider) labels on the X axis, value printed on top of each bar.
  const VW = 640, VH = 210, mL = 54, mR = 14, mT = 26, mB = 42;
  const PW = VW - mL - mR, PH = VH - mT - mB, x0 = mL, yB = VH - mB;
  const maxV = Math.max(0, ...items.map(x => x.value || 0));
  const nt = niceTicks(maxV, 4), top = nt.top || 1;
  const EOL = String.fromCharCode(8230);
  let g = '<svg viewBox="0 0 ' + VW + ' ' + VH + '" style="width:100%;height:auto;max-width:780px;display:block;margin-top:2px" xmlns="http://www.w3.org/2000/svg" font-family="Plus Jakarta Sans, Inter, Segoe UI, system-ui, sans-serif">';
  for (let v = 0; v <= top + top * 1e-6; v += nt.step) {
    const y = yB - PH * (v / top);
    g += '<line x1="' + x0 + '" y1="' + y.toFixed(1) + '" x2="' + (x0 + PW) + '" y2="' + y.toFixed(1) + '" stroke="#8b93a3" stroke-width="1" stroke-dasharray="3 4" opacity="0.25"/>';
    g += '<text x="' + (x0 - 7) + '" y="' + (y + 3.4).toFixed(1) + '" fill="#8b93a3" font-size="10" text-anchor="end">' + esc(fmt(v)) + '</text>';
  }
  g += '<line x1="' + x0 + '" y1="' + mT + '" x2="' + x0 + '" y2="' + yB + '" stroke="#4a5160" stroke-width="1.3"/>';
  g += '<line x1="' + x0 + '" y1="' + yB + '" x2="' + (x0 + PW) + '" y2="' + yB + '" stroke="#4a5160" stroke-width="1.3"/>';
  const slot = PW / items.length, bw = Math.max(6, Math.min(70, slot * 0.6));
  const maxc = Math.max(3, Math.floor(slot / 6.2));
  items.forEach((it, i) => {
    const cx = x0 + slot * (i + 0.5), bx = cx - bw / 2;
    const h = PH * ((it.value || 0) / top), by = yB - h;
    g += '<line x1="' + cx.toFixed(1) + '" y1="' + mT + '" x2="' + cx.toFixed(1) + '" y2="' + yB + '" stroke="#8b93a3" stroke-width="1" stroke-dasharray="2 5" opacity="0.12"/>';
    g += '<rect x="' + bx.toFixed(1) + '" y="' + by.toFixed(1) + '" width="' + bw.toFixed(1) + '" height="' + Math.max(0.6, h).toFixed(1) + '" rx="3" fill="' + it.color + '"/>';
    g += '<text x="' + cx.toFixed(1) + '" y="' + (by - 4.5).toFixed(1) + '" fill="#eef1f6" font-size="10" text-anchor="middle">' + esc(fmt(it.value)) + '</text>';
    if (opt.emoji) {
      const eTxt = '<text x="' + cx.toFixed(1) + '" y="' + (yB + 24) + '" font-size="15" text-anchor="middle" class="stat-emoji" data-tip="' + esc(it.full || it.label) + '">' + esc(it.label) + '</text>';
      g += opt.click
        ? '<g data-act="provStat" data-pid="' + esc(it.pid || "") + '" style="cursor:pointer">' + eTxt + '</g>'
        : eTxt;
    } else {
      const lbl = it.label.length > maxc ? it.label.slice(0, maxc - 1) + EOL : it.label;
      g += '<text x="' + cx.toFixed(1) + '" y="' + (yB + 14) + '" fill="#c4c9d4" font-size="10" text-anchor="middle" data-tip="' + esc(it.full || it.label) + '">' + esc(lbl) + '</text>';
    }
  });
  g += '</svg>';
  return g;
}
function statCard(title, sub, items, fmt, opt, extra) {
  return '<div class="stcard"><div class="stcard-h">' + esc(title) + '<span class="stcard-sub">' + esc(sub) + '</span></div>'
    + statChart(items, fmt, opt) + (extra || "") + '</div>';
}
// item 3: timings for the provider whose emoji was last clicked on the Generation time chart
function provStatLine() {
  const pid = window.__provStatPid;
  if (!pid) return '<div class="hint" style="margin-top:8px">Click a provider emoji under the bars for its generation, prefill and decode times, and how fast each ran.</div>';
  const p = ((statsData && statsData.providers) || []).filter(x => x.id === pid)[0];
  if (!p) return '<div class="hint" style="margin-top:8px">That provider has no recorded data yet.</div>';
  const cell = (lbl, v, rate) => '<span style="margin-right:14px"><span style="color:var(--dim)">' + lbl + '</span> '
    + '<b style="color:var(--ok)">' + esc(v > 0 ? stMs(v) : "n/a") + '</b>'
    + (rate ? ' <span style="color:var(--dim)">at</span> <b style="color:var(--ok)">' + esc(rate) + '</b>' : '')
    + '</span>';
  // how fast, not only how long: the tokens divided by the time they took
  const tps = (tokens, ms) => (tokens > 0 && ms > 0)
    ? (tokens / (ms / 1000)).toFixed(1) + " tok/s" : "";
  return '<div style="margin-top:8px;padding:8px 10px;background:var(--bg);border:none;'
    + 'box-shadow:0 0 12px -2px rgba(0,0,0,.85);border-radius:8px;font-size:12px">'
    + '<span style="margin-right:14px">' + esc((p.emoji || "\u2022") + " " + (p.title || p.id)) + '</span>'
    + cell("generation", p.gen || 0, "")
    + cell("prefill", p.pfMs || 0, tps(p["in"] || 0, p.pfMs || 0))
    + cell("decode", p.dcMs || 0, tps(p.out || 0, p.dcMs || 0)) + '</div>';
}
function statsHeader() {
  const on = !!(statsData && statsData.monitoring);
  return '<div class="card"><div class="row" style="gap:8px;flex-wrap:wrap">'
    + '<div class="row" style="gap:8px" data-hostonly>'
    + '<button class="' + (on ? "" : "stop") + '" data-act="statsToggle">' + (on ? "Monitoring: on" : "Monitoring: off") + '</button>'
    + '<button class="stop" data-act="statsReset">Reset stats</button></div>'
    + '</div></div>';
}
function renderServerStats() {
  const servers = (statsData && statsData.servers) || [];
  servers.forEach(s => { s._lbl = modelBase(s.model) || s.label || ("port " + s.port); });
  const row = (title, sub, key, fmt) => {
    const items = servers.map((s, i) => ({ label: s._lbl, value: s[key] || 0, color: stColor(i) })).filter(x => x.value > 0);
    return items.length ? statCard(title, sub, items, fmt) : "";
  };
  let h = "";
  h += row("Prefill speed", "prompt processing, avg t/s", "pp", stTps);
  h += row("Decode speed", "token generation, avg t/s", "tg", stTps);
  h += row("Response time", "avg round-trip per generation", "resp", stMs);
  h += row("Token usage", "total tokens processed, input + output", "tokTot", stK);
  h += row("Thinking tokens (est)", "total reasoning tokens", "thinkTot", stK);
  h += row("Generations", "completed requests", "gens", stNum);
  h += row("Times loaded", "server launches this session", "loads", stNum);
  h += row("Queue time", "accumulated GPU-gate wait", "queueTot", stMs);
  h += row("Cached tokens", "prompt tokens served from cache", "cacheTok", stK);
  h += row("Cache time saved", "estimated prefill time avoided", "cacheSavedMs", stMs);
  h += row("MTP acceptance", "draft tokens accepted, avg", "mtpAcc", stPct);
  h += row("MTP draft size", "drafted tokens per step, avg", "mtpAmt", st1);
  h += row("Errors", "load / stop / parse failures", "errors", stNum);
  return h || '<div class="stempty">No server activity recorded yet.<br>Launch a server and run some generations - charts appear here as data arrives.</div>';
}
function renderProviderStats() {
  const provs = (statsData && statsData.providers) || [];
  provs.forEach(p => { p._emoji = p.emoji || "\u2022"; p._full = p.title || p.id; });
  const row = (title, sub, key, fmt, click) => {
    const items = provs.map(p => ({ label: p._emoji, full: p._full, pid: p.id, value: p[key] || 0, color: dashColor(p._full) })).filter(x => x.value > 0);
    if (!items.length) return "";
    return statCard(title, sub, items, fmt, { emoji: true, click: !!click }, click ? provStatLine() : "");
  };
  let h = "";
  h += row("Generation time", "avg round-trip per request - click an emoji for its breakdown", "gen", stMs, true);
  h += row("Input tokens", "avg prompt tokens per request", "in", stNum);
  h += row("Output tokens", "avg completion tokens per request", "out", stNum);
  h += row("Thinking tokens (est)", "avg reasoning tokens per request", "think", stNum);
  h += row("Errors", "provider request failures", "errors", stNum);
  return h || '<div class="stempty">No provider activity recorded yet.<br>Once SkyrimNet sends requests through the proxy, charts appear here as data arrives.</div>';
}
async function renderStats() {
  const onServers = (curTab === "servers" && curSsub === "stats");
  const onProv = (curTab === "provmgmt" && curPmSub === "stats");
  if (!onServers && !onProv) return;
  try { statsData = await (await fetch("/api/stats")).json(); } catch (e) { return; }
  const sh = $("stats-header"), ph = $("pstats-header");
  if (sh) sh.innerHTML = statsHeader();
  if (ph) ph.innerHTML = statsHeader();
  const sp = $("stpane-server"), pp = $("stpane-provider");
  if (onServers && sp) sp.innerHTML = renderServerStats();
  if (onProv && pp) pp.innerHTML = renderProviderStats();
}
function queueStats() {
  if (!((curTab === "servers" && curSsub === "stats") || (curTab === "provmgmt" && curPmSub === "stats"))) return;
  clearTimeout(statsTimer); statsTimer = setTimeout(renderStats, 400);
}

// header chrome (version, stack line, elevation banner, profiles) is global page state -
// it repaints on every load() regardless of tab, in exactly one place
let updInfo = null;                    // {state, tag, url} once GitHub has answered
function paintVersion() {
  const el = $("ver");
  if (!el || !state) return;
  const behind = updInfo && updInfo.state === "behind";
  const current = updInfo && (updInfo.state === "current" || updInfo.state === "ahead");
  el.className = "ver" + (behind ? " behind" : (current ? " uptodate" : ""));
  el.title = behind ? ("a newer release is on GitHub: " + updInfo.tag)
           : (current ? ((updInfo.state === "ahead") ? ("newer than the newest release on GitHub (" + updInfo.tag + ")")
                                                     : "this is the newest release")
                      : "click to check GitHub for a newer release");
  el.innerHTML = esc(state.version) + (behind ? '<span class="upd">Update available!</span>' : "");
}
async function checkAppUpdate() {
  try {
    const r = await post("/api/app-update", {});   // host-only, like every other POST
    updInfo = r && r.state ? r : null;
  } catch (e) { updInfo = null; }
  paintVersion();
}
function verClick() {
  const u = (updInfo && updInfo.url) || "https://github.com/Pt0l3my/PandorumLLM/releases";
  const head = (updInfo && updInfo.state === "behind")
      ? ("A newer release is on GitHub: <b>" + esc(updInfo.tag) + "</b>")
      : ((updInfo && updInfo.state === "current")
          ? "This is the newest release."
          : (updInfo && updInfo.state === "ahead")
          ? ("This build is newer than the newest release on GitHub (<b>" + esc(updInfo.tag) + "</b>).")
          : "GitHub has not been asked yet, or could not be reached.");
  showModal('<h2 style="margin:2px 0 6px">Releases</h2>'
    + '<p style="line-height:1.6;margin:8px 0 16px">' + head
    + '<br>Open the releases page on github.com in a new tab?</p>'
    + '<div class="row" style="justify-content:flex-end;gap:8px">'
    + '<button class="stop" onclick="closeModal()">No</button>'
    + '<button onclick="closeModal(); window.open(' + String.fromCharCode(39) + u
    + String.fromCharCode(39) + ', ' + String.fromCharCode(39) + "_blank"
    + String.fromCharCode(39) + ')">Yes</button></div>');
}
function paintChrome() {
  if (!state) return;
  paintVersion();
  const sc = $("slotcount");
  if (sc) sc.textContent = "slots: " + (state.slots || []).length + "/20";
  const bi = state.build || {};
  $("ver").title = bi.path ? (bi.path + String.fromCharCode(10) + "build " + bi.sha
      + "  -  " + bi.kb + " KB  -  modified " + bi.mtime) : "";
  const hp = $("hdr-prof");
  if (hp && !window.__profOpen) { const nh = profRow(); if (hp.innerHTML !== nh) hp.innerHTML = nh; }
}
function renderSlots(force) {
  if (!state) return;
  const ae = document.activeElement;
  if (!force && (curTab !== "servers" || curSsub !== "slots" || paramBusy()
      || (ae && ["SELECT","INPUT","TEXTAREA"].includes(ae.tagName)))) {
    trace("draw", "server cards not redrawn",
          paramBusy() ? "a parameter is being adjusted"
                      : (ae && ae.tagName !== "BODY" ? "a field has focus" : "not the page in view"));
    renderHist(); return;
  }
  trace("draw", "server cards" + (force ? " (asked for)" : ""));
  $("slots").innerHTML = '<div class="slotgrid">'
    + state.slots.map(s => {
    const off = !(s.params && s.params.model);
    const running = s.status.state === "serving" || s.status.state === "loading";
    const spd = (running && s.speeds)
      ? '<span class="spd">PP '+(s.speeds.pp ?? "-")+' t/s &middot; TG '+(s.speeds.tg ?? "-")+' t/s</span>' : "";
    const mm = (!off && s.actualPort && s.port && s.actualPort !== s.port)
      ? '<span class="mismatch">&#9888; launcher binds :'+s.actualPort+', slot expects :'+s.port+'</span>' : "";
    const missing = (window.__slotBusy && window.__slotBusy[s.id])
      ? '<span class="mismatch">Loading model...</span>'
      : ((!off && !s.scriptExists)
          ? '<span class="mismatch" style="color:#ff5d5d">Model could not be loaded</span>' : "");
    const rm = state.slots.length > 1
      ? '<button class="x" title="remove this slot" onclick="removeSlot(\\''+s.id+'\\')">&#10005;</button>' : "";
    const term = running
      ? '<button class="stop" onclick="act(\\''+s.id+'\\',\\'show-terminal\\',this)">&#128421;&#65039; Terminal</button>' : "";
    return '<div class="card svr-row">'
      + '<div class="row"><span class="label" id="label-'+s.id+'">'+esc(s.label)+'</span>'
      + '<button class="icon" title="rename" onclick="startEdit(\\''+s.id+'\\',\\'label\\')">&#9998;</button>'
      + '<span class="chip clickable" id="port-'+s.id+'" title="expected port - click to edit" '+(portProblem(s)?'style="color:var(--err);border-color:var(--err);font-weight:700" ':'')+' '
      + 'onclick="startEdit(\\''+s.id+'\\',\\'port\\')">Port '+esc(s.port)+'</span>'
      + (portProblem(s) ? '<span class="mismatch">&#9888; '+portProblem(s)+'</span>' : "")
      + (running ? pill(s.status) : "") + spd
      + mm + missing + rm + '</div>'
      + '<div class="path">' + allocLine(s) + '</div>'
      + (slotMsg[s.id] ? '<div class="path" style="color:var(--warn)">' + esc(slotMsg[s.id]) + '</div>' : '')
      + paramEditor(s)
      + '<div class="row" style="margin-top:16px">'
      + srvButtons(s, off, running) + term + '</div>'
      + '<pre class="log" id="log-'+s.id+'"></pre></div>';
  }).join("")
  + '</div>'
  + (state.slots.length < 20
      ? '<div class="card addcard" style="margin-top:22px"><button class="stop" onclick="addSlot()">&#10133; Add server</button></div>' : "");
  renderHist();
}
function renderHist() {
  $("histbody").innerHTML = (state.history||[]).map(h =>
    "<tr><td>"+esc(h.time)+"</td><td>"+esc(h.slot)+"</td><td>"+esc(h.port)+"</td>"
    + "<td>"+esc((h.script||"").split("\\\\").pop())+'<div class="p">'+esc(h.script)+"</div>"
    + (h.model ? '<div class="hint" style="color:#8fd48f">'+esc(h.model)+'</div>' : "")+"</td></tr>"
  ).join("") || '<tr><td colspan="4" style="color:var(--dim)">no launches recorded yet</td></tr>';
}

function startEdit(sid, field) {
  const span = $(field + "-" + sid);
  const s = state.slots.find(x => x.id === sid);
  if (!span || !s) return;
  const inp = document.createElement("input");
  inp.className = "edit";
  inp.value = field === "label" ? (s.label || "") : (s.port || "");
  if (field === "port") inp.style.maxWidth = "90px";
  span.replaceWith(inp);
  inp.focus(); inp.select();
  let done = false;
  const finish = save => {
    if (done) return; done = true;
    if (save && String(inp.value).trim() !== "") {
      const body = { slot: sid }; body[field] = inp.value;
      post("/api/edit", body).then(r => { if (r.error) uiAlert(r.error); load(); });
    } else load();
  };
  inp.addEventListener("keydown", e => {
    if (e.key === "Enter") finish(true);
    if (e.key === "Escape") finish(false);
  });
  inp.addEventListener("blur", () => finish(true));
}

/* ---------- setup ---------- */
const SET_FIELDS = [
  ["llamacppPath","llama.cpp Folder (contains llama-server.exe)","folder"],
  ["modelsDir","Models Folder (.gguf scan for server parameters)","folder"],
  ["launcherDir","PS1 Launcher Folder (also the Launcher Creator output folder)","folder"],
  ["logDir","Log File Folder","folder"],
  ["yamlOutDir","providers.yaml Output Folder","folder"]];
const MANDATORY_DIRS = ["llamacppPath", "modelsDir"];
function renderSetup() {
  const st = state ? state.settings : {};
  // Preserve any values the user has typed/pasted but not yet saved, so a re-render
  // (e.g. triggered by the folder picker saving a different field) can't wipe them.
  const _keep = {};
  SET_FIELDS.forEach(([k]) => { const el = $("set-"+k); if (el) _keep[k] = el.value; });
  const firstRun = !(st.llamacppPath || st.launcherDir);
  $("tab-setup").innerHTML = (firstRun ? '<div class="banner" style="display:block;margin:0 0 12px">First run: point PandorumLLM at your llama.cpp folder, launcher folder and models folder below.</div>' : "")
    + '<div class="card set" style="max-width:820px">'
    + SET_FIELDS.map(([k, lab, mode]) => {
        const pickLab = mode === "file" ? "Set file path" : "Set folder path";
        let extra = "";
        if (k === "llamacppPath") extra = '<div class="hint" style="margin-top:8px;line-height:1.6">Check for newer llama.cpp builds at this address (copy &amp; paste into your browser):'
          + '<div style="margin-top:4px;display:flex;gap:8px;align-items:center;flex-wrap:wrap">'
          + '<code id="llrel-url" onclick="copyRelUrl(this)" title="click to copy" style="background:#12161d;border:1px solid var(--edge);border-radius:6px;padding:4px 9px;color:var(--dim);user-select:all;cursor:pointer">https://github.com/ggml-org/llama.cpp/releases</code>'
          + '<button class="stop" onclick="copyRelUrl(this)">\u29C9 Copy</button>'
          + '<button class="stop" onclick="checkLlamaUpdate(this)" title="asks github.com for the newest llama.cpp release - the only outbound request this app makes, and only when you press it">Check for update</button>'
          + '</div><div class="hint" id="llupd" style="margin-top:6px;min-height:1.2em"></div></div>';
        // a warning sits directly beneath the box it is about, ahead of anything else
        let warn = "";
        if (k === "llamacppPath") warn = '<div class="hint chkmsg" id="llchk" style="color:var(--err);display:none">llama-server.exe not found in this folder</div>';
        if (k === "modelsDir") warn = '<div class="hint chkmsg" id="mdlchk" style="color:var(--err);display:none">no .gguf model files found in this folder</div>';
        if (k === "launcherDir") warn = '<div class="hint chkmsg" id="lnchk" style="color:var(--warn);display:none">no .ps1 launchers in this folder yet</div>';
        if (k === "launcherDir") extra = '<div class="hint" style="margin-top:8px;line-height:1.6">'
          + 'A launcher is a script, and running one runs whatever is in it. Sweep reads every .ps1 here '
          + 'and reports anything that does not belong in a file whose only job is to start llama-server.'
          + '<div style="margin-top:6px"><button class="stop" data-act="sweepLaunchers">Sweep launcher folder</button></div>'
          + '<div class="hint" id="sweepout" style="margin-top:6px;white-space:pre-wrap"></div></div>';
        return '<label>'+esc(lab)+(MANDATORY_DIRS.indexOf(k) >= 0 ? ' <span class="mand">Mandatory</span>' : '')+'</label><div class="row" style="flex-wrap:nowrap">'
          + '<input class="txt" id="set-'+k+'" onchange="saveSetup()" value="'+esc(st[k]||"").replace(/"/g,"&quot;")+'"'
          + (k === "llamacppPath" ? ' placeholder="enter path e.g. C:&#92;llama.cpp-cuda"' : "") + '>'
          + '<button class="stop" onclick="pickPath(\\''+k+'\\')">'+pickLab+'</button>'
          + (FOLDER_KEY[k]                            // no viewer, no button - but keep
               ? '<button class="stop" onclick="openFolder(\\''+k+'\\')">Open folder</button>'   // the space so every row lines up
               : '<button class="stop" style="visibility:hidden" tabindex="-1" aria-hidden="true">Open folder</button>')
          + '</div>'
          + warn + '<div class="setnote" id="setnote-'+k+'"></div>' + extra;
      }).join("")
    + '<div id="set-feedback" style="margin-top:12px;font-weight:600;min-height:1.2em"></div></div>'
    + '<div class="hint" style="max-width:820px;margin-top:10px">Installed at '
    + esc((state && state.stack) || "") + '</div>';
  // restore unsaved edits the user had typed/pasted before this re-render
  SET_FIELDS.forEach(([k]) => {
    const el = $("set-"+k);
    if (el && _keep[k] !== undefined && _keep[k] !== "" && _keep[k] !== (st[k] || "")) el.value = _keep[k];
  });
}
async function saveSetup() {
  // runs when a path field is left or enter is pressed - there is no save button
  const body = {};
  SET_FIELDS.forEach(([k]) => { const el = $("set-"+k); if (el) body[k] = el.value; });
  const prevModelsDir = (state && state.settings && state.settings.modelsDir) || "";
  const prev = (state && state.settings) || {};
  if (SET_FIELDS.every(([k]) => (body[k] || "") === (prev[k] || ""))) return;   // nothing changed
  const r = await post("/api/settings", body);
  if (r.error) { uiAlert(r.error); return; }
  if ((body.modelsDir || "") !== prevModelsDir) { models = null; await loadModels(true); }
  const prevSet = (state && state.settings) || {};
  const changed = SET_FIELDS.map(f => f[0]).filter(k => (body[k] || "") !== (prevSet[k] || ""));
  await load(); renderSetup(); showSetOk(changed);
  wireLlamaCheck(); recheckPaths();          // the fields are new: listen again, and re-check now
}
function showSetOk(keys) {
  // the confirmation sits under the field it belongs to and clears itself
  (keys || []).forEach(function(k) {
    const el = document.getElementById("setnote-" + k);
    if (!el) return;
    el.innerHTML = '<span style="color:var(--ok)">\u2705 Path set</span>';
    clearTimeout(el.__t);
    el.__t = setTimeout(function() { el.innerHTML = ""; }, 3000);
  });
}
async function checkLlamaUpdate(btn) {
  const out = $("llupd");
  if (out) out.innerHTML = '<span style="color:var(--warn)">checking github.com...</span>';
  btn.disabled = true;
  const r = await post("/api/llama-update", {});
  btn.disabled = false;
  if (!out) return;
  if (r.error) { out.innerHTML = '<span style="color:#ff5d5d">' + esc(r.error) + '</span>'; return; }
  if (!r.known) {
    out.innerHTML = '<span style="color:var(--warn)">newest release is ' + esc(r.latest)
      + ' - could not read your build number, so compare it yourself</span>';
  } else if (r.upToDate) {
    out.innerHTML = '<span style="color:var(--ok)">up to date (yours: b' + esc(r.local) + ', newest: ' + esc(r.latest) + ')</span>';
  } else {
    out.innerHTML = '<span style="color:var(--warn)">a newer build is out: ' + esc(r.latest)
      + ' (yours: b' + esc(r.local) + ')</span>';
  }
}
function copyRelUrl(btn) {
  const url = "https://github.com/ggml-org/llama.cpp/releases";
  const isCode = btn && btn.id === "llrel-url";
  const done = () => {
    if (isCode) { btn.classList.add("copied-flash"); setTimeout(() => btn.classList.remove("copied-flash"), 1000); }
    else { const o = btn.textContent; btn.textContent = "\u2713 Copied"; setTimeout(() => { btn.textContent = o; }, 1400); }
  };
  if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(url).then(done, done);
  else {
    const el = document.getElementById("llrel-url");
    if (el) { const r = document.createRange(); r.selectNodeContents(el); const s = window.getSelection(); s.removeAllRanges(); s.addRange(r); try { document.execCommand("copy"); } catch (e) {} }
    done();
  }
}

/* ---------- log tab ---------- */
// which category a log file belongs to, decided from its name
const LOG_CATS = [
  ["error",     "\u26A0 Error",     "load / stop / parse failures and panel exceptions"],
  ["server",    "\U0001F5A5 Server",     "per-server llama.cpp output (srv_<slot>_*.log)"],
  ["thinking",  "\U0001F9E0 Thinking",   "captured reasoning content per request"],
  ["dashboard", "\U0001F4DF Dashboard",  "the proxy request/response feed"],
  ["panel",     "\U0001F4CB Panel",      "panel lifecycle and proxy listener events"],
  ["other",     "\U0001F4C4 Other",      "anything else in the log folder"]
];
function logCat(name) {
  const n = String(name || "").toLowerCase();
  if (n.indexOf("error") === 0 || n.indexOf("error_") >= 0) return "error";
  if (n.indexOf("srv_") === 0) return "server";
  if (n.slice(-13) === "_thinking.log" || n === "thinking.log") return "thinking";
  if (n.slice(-14) === "_dashboard.log" || n === "dashboard.log") return "dashboard";
  if (n.indexOf("panel") === 0) return "panel";
  return "other";
}
function logCard(f) {
  return '<div class="logcard">'
    + '<div style="display:flex;align-items:center;gap:8px"><span style="flex-shrink:0">\U0001F4C4</span>'
    +   '<b style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="' + esc(f.name) + '">' + esc(f.name) + '</b></div>'
    + '<div class="row" style="gap:6px;margin-top:8px"><button class="stop" data-act="logView" data-f="' + esc(f.name) + '">View</button>'
    +   '<a class="btnlink" download href="/api/log-download?f=' + encodeURIComponent(f.name) + '">Download</a></div>'
    + '<div class="hint" style="margin-top:8px">' + esc(f.size) + '</div>'
    + '<div class="hint">created: ' + esc(f.created) + '</div>'
    + '<div class="hint">last edit: ' + esc(f.modified) + '</div>'
    + '</div>';
}
async function renderLog() {
  const r = await (await fetch("/api/logs")).json();
  const files = r.files || [];
  const byCat = {};
  files.forEach(function(f) { (byCat[logCat(f.name)] = byCat[logCat(f.name)] || []).push(f); });
  let body = "";
  LOG_CATS.forEach(function(c) {
    const list = byCat[c[0]] || [];
    if (!list.length) return;
    body += '<div style="margin-top:14px"><div class="row" style="gap:8px;align-items:baseline">'
      + '<b>' + c[1] + '</b><span class="chip">' + list.length + '</span>'
      + '<span class="hint" style="width:auto">' + esc(c[2]) + '</span></div>'
      + '<div class="logcardgrid">' + list.map(logCard).join("") + '</div></div>';
  });
  if (!files.length) body = '<div class="hint">no log files yet</div>';
  $("lpane-files").innerHTML =
    '<h2 style="margin:4px 0 2px">Logs</h2>'
    + '<div class="hint" style="margin-bottom:10px">' + esc(r.dir) + '</div>'
    + '<div class="card"><b class="hint">LOG FILES</b>' + body + '</div>'
    + '<pre class="tail" id="logview" style="display:none;height:55vh;margin-top:14px"></pre>';
}
function showLsub(s) {
  curLsub = s;
  ["files", "errors", "debug"].forEach(function(k) {
    $("lpane-" + k).style.display = s === k ? "" : "none";
    $("lsub-" + k).classList.toggle("on", s === k);
  });
  if (s === "files") renderLog();
  else if (s === "errors") renderErrors();
  else renderDebug();
}
// A short account of this build and this setup, meant to be handed over with a bug
// report. It carries no paths, no IP addresses, no card serial numbers and no model
// filenames - a folder is reported as set or not, and a model as what kind it is.
function renderDebug() {
  const pane = $("lpane-debug");
  if (!pane || pane.dataset.built) return;
  pane.dataset.built = "1";
  pane.innerHTML = '<div class="card">'
    + '<div class="row" style="gap:8px">'
    + '<button class="stop" id="dbg-rec" data-act="dbgRec">' + (traceOn ? "Stop recording" : "Start recording") + '</button>'
    + '<button class="stop" data-act="dbgClear">Clear</button>'
    + '<button class="stop" data-act="dbgCopy">Copy</button>'
    + '<button class="stop" data-act="dbgSave">Save to a file</button>'
    + '</div>'
    + '<div class="hint" style="margin-top:8px">Records what the page does, and what it '
    + 'declines to do and why &#8212; an effect standing down, a redraw refused, a reload '
    + 'put off. Recording costs nothing while it is off. Nothing here names a folder, an '
    + 'IP address or a model file.</div>'
    + '<pre class="log" id="dbg-out" style="display:block;margin-top:10px;max-height:52vh;overflow:auto">'
    + '(not recording)</pre></div>';
  traceDraw();
}
function traceDraw() {
  const out = $("dbg-out");
  if (!out) return;
  out.textContent = traceLog.length ? traceText() : (traceOn ? "recording..." : "(not recording)");
  if (traceOn) out.scrollTop = out.scrollHeight;
}
function traceToggle(quiet) {
  traceOn = !traceOn;
  if (!quiet) post("/api/settings", { observerOn: traceOn });
  if (traceOn) {
    traceLog = []; traceT0 = performance.now();
    if (!traceRaf) traceRaf = setInterval(traceTick, 250);
  } else if (traceRaf) { clearInterval(traceRaf); traceRaf = 0; }
  const b = $("dbg-rec");
  if (b) b.textContent = traceOn ? "Stop recording" : "Start recording";
  trace("observer", traceOn ? "recording started" : "");
  traceDraw();
}

async function renderErrors() {
  if (curTab !== "log" || curLsub !== "errors") return;
  try { errData = await (await fetch("/api/errors")).json(); } catch (e) { return; }
  paintErrors();
}
function queueErrors() {
  if (curTab !== "log" || curLsub !== "errors") return;
  clearTimeout(errTimer); errTimer = setTimeout(renderErrors, 500);
}
function errSetRetain(v) { errRetain = parseInt(v) || 50; errPage = 1; paintErrors(); }
function errSetPerPage(v) { errPerPage = parseInt(v) || 10; errPage = 1; paintErrors(); }
function errPager(cur, total) {
  const btn = (p, label, on, dis) => '<button class="errpg' + (on ? " on" : "") + (dis ? " dis" : "") + '"' + (dis ? " disabled" : "") + ' data-act="errPage" data-page="' + p + '">' + label + '</button>';
  const pages = [];
  const add = p => { if (p >= 1 && p <= total && pages.indexOf(p) < 0) pages.push(p); };
  add(1); add(total);
  for (let p = cur - 2; p <= cur + 2; p++) add(p);
  pages.sort((a, b) => a - b);
  let h = '<div class="errpager">' + btn(cur - 1, "&lt;", false, cur <= 1);
  let prev = 0;
  pages.forEach(p => {
    if (p - prev > 1) h += '<span class="errpg-gap">...</span>';
    h += btn(p, String(p), p === cur, false);
    prev = p;
  });
  return h + btn(cur + 1, "&gt;", false, cur >= total) + '</div>';
}
function paintErrors() {
  if (!errData) return;
  const byType = errData.byType || {}, byLevel = errData.byLevel || {};
  let chips = '<span class="errstat-total">' + (errData.total || 0) + ' total this session</span>';
  ["ERROR", "WARN"].forEach(k => { if (byLevel[k]) chips += '<span class="errchip errchip-' + k + '">' + k + ': ' + byLevel[k] + '</span>'; });
  Object.keys(byType).sort().forEach(k => { chips += '<span class="errchip">' + esc(k) + ': ' + byType[k] + '</span>'; });
  const statRow = '<div class="card errstat">' + chips + '</div>';
  const retOpts = [10, 25, 50, 100, 250].map(n => '<option value="' + n + '"' + (n === errRetain ? " selected" : "") + '>' + n + '</option>').join("");
  const ppOpts = [10, 20, 30, 40, 50].map(n => '<option value="' + n + '"' + (n === errPerPage ? " selected" : "") + '>' + n + '</option>').join("");
  const ctrl = '<div class="row errctrl" style="gap:16px;flex-wrap:wrap;align-items:center;margin-bottom:12px">'
    + '<label class="hint" style="width:auto">Show Most Recent <select onchange="errSetRetain(this.value)">' + retOpts + '</select></label>'
    + '<label class="hint" style="width:auto">Per Page <select onchange="errSetPerPage(this.value)">' + ppOpts + '</select></label>'
    + '<span style="margin-left:auto"></span>'
    + '<button class="stop" data-hostonly data-act="errClear"'
    + (errData.total ? "" : " disabled")
    + ' title="empty the list and the error log for this session">Clear All</button></div>';
  const all = (errData.errors || []).slice(0, errRetain);
  const totalPages = Math.max(1, Math.ceil(all.length / errPerPage));
  if (errPage > totalPages) errPage = totalPages;
  if (errPage < 1) errPage = 1;
  const start = (errPage - 1) * errPerPage;
  const rows = all.slice(start, start + errPerPage).map(e =>
    '<div class="errrow"><div class="errrow-h">'
    + '<span class="errchip errchip-' + (e.level || "ERROR") + '">' + esc(e.type || "?") + '</span>'
    + '<span class="errrow-title" title="' + esc(e.title || "") + '">' + esc(e.title || "(no title)") + '</span>'
    + '<span class="errrow-time">' + esc(e.ts || "") + '</span></div>'
    + '<textarea class="errrow-text" readonly rows="3">' + esc(e.text || "") + '</textarea></div>'
  ).join("") || '<div class="hint" style="padding:26px;text-align:center">no errors or warnings recorded this session</div>';
  const pag = all.length > errPerPage ? errPager(errPage, totalPages) : "";
  $("lpane-errors").innerHTML = statRow + ctrl + '<div class="errlist">' + rows + '</div>' + pag;
}
async function viewLog(name) {
  const r = await post("/api/tail", { kind: "file", name: name });
  const v = $("logview");
  if (!v) return;
  v.style.display = "";
  paintTail("dashboard", r.text || r.error || "", v);
  v.scrollTop = v.scrollHeight;
  v.scrollIntoView({ behavior: "smooth", block: "nearest" });
}
const DASH_PAL = ["#ff5dc8", "#f0883e", "#3fdd78", "#4da3ff", "#e0c23c", "#e05fd0", "#5ad0c0", "#d97b6c", "#8fb4ff", "#c9a227", "#7ee081", "#ff8ac2"];
// fixed colors matched to the chips SkyrimNet itself shows for these roles, so both UIs
// speak the same color language; every other title falls through to the vivid hash palette
const PROV_COL = { "Dialogue":"#10b981", "GM":"#f59e0b", "Combat":"#dc2626", "Meta":"#64748b",
  "Vision":"#06b6d4", "Memory":"#d946ef", "Diary":"#f97316", "Charbio":"#14b8a6", "Bio":"#14b8a6",
  "ActionEval":"#7c3aed", "Action":"#7c3aed", "AI-Assistant":"#9333ea", "Agent":"#9333ea",
  "Vanilla":"#a8a29e" };
function dashColor(name) {
  if (PROV_COL[name]) return PROV_COL[name];
  let h = 0; for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) >>> 0;
  return DASH_PAL[h % DASH_PAL.length];
}
function paintThink(el, text) {
  const NL = String.fromCharCode(10);
  const stick = el.scrollTop + el.clientHeight >= el.scrollHeight - 40;
  const keep = el.scrollTop;
  const CY = "#4dd8e6", MG = "#ff5dc8", GOLD = "#f0c674";
  const DQ = String.fromCharCode(34), SQ = String.fromCharCode(39);
  const provs = {};
  (state && state.routing || []).forEach(s => (s.providers || []).forEach(p => { if (p.title) provs[p.title] = p.emoji || ""; }));
  const sepRx = new RegExp("^[=]{6,}");
  const timeRx = new RegExp("^[[][0-9]{2}:[0-9]{2}:[0-9]{2}[^\\]]*[]]");
  const portRx = new RegExp("^[[][0-9]{4}[]]$");
  const tokEstRx = new RegExp("^[(]~[0-9]+ tok est[)]$");
  function paintLine(line) {
    if (sepRx.test(line.trim())) return '<span style="color:' + CY + '">' + esc(line) + '</span>';
    // build colored segments over the RAW line, escaping each piece exactly once
    const segs = [];  // {t:text, c:color|null}
    let rest = line;
    // leading [time]
    const tm = rest.match(timeRx);
    if (tm) { segs.push({ t: tm[0], c: CY }); rest = rest.slice(tm[0].length); }
    // tokenizer: walk chars, split out *..*, "..", '..', [port], (~N tok est), provider names
    let i = 0, buf = "";
    const flush = () => { if (buf) { segs.push({ t: buf, c: null }); buf = ""; } };
    while (i < rest.length) {
      const ch = rest[i];
      // quoted double
      if (ch === DQ) {
        const j = rest.indexOf(DQ, i + 1);
        if (j > i) { flush(); segs.push({ t: rest.slice(i, j + 1), c: GOLD }); i = j + 1; continue; }
      }
      // quoted single (guarded: preceded by start/space/paren, closed before space/punct)
      if (ch === SQ && (i === 0 || " (".indexOf(rest[i - 1]) >= 0)) {
        const j = rest.indexOf(SQ, i + 1);
        if (j > i && (j + 1 >= rest.length || " .,)!?".indexOf(rest[j + 1]) >= 0)) {
          flush(); segs.push({ t: rest.slice(i, j + 1), c: GOLD }); i = j + 1; continue;
        }
      }
      // *starred*
      if (ch === "*") {
        const j = rest.indexOf("*", i + 1);
        if (j > i + 1 && rest[i + 1] !== " ") {
          flush();
          segs.push({ t: "*", c: null });
          segs.push({ t: rest.slice(i + 1, j), c: CY });
          segs.push({ t: "*", c: null });
          i = j + 1; continue;
        }
      }
      // [port] or (~N tok est) - only as standalone tokens
      if (ch === "[") {
        const j = rest.indexOf("]", i);
        if (j > i && portRx.test(rest.slice(i, j + 1))) { flush(); segs.push({ t: rest.slice(i, j + 1), c: "#8b93a3" }); i = j + 1; continue; }
      }
      if (ch === "(") {
        const j = rest.indexOf(")", i);
        if (j > i && tokEstRx.test(rest.slice(i, j + 1))) { flush(); segs.push({ t: rest.slice(i, j + 1), c: MG }); i = j + 1; continue; }
      }
      // provider name at this position
      let matched = false;
      for (const nm in provs) {
        if (nm && rest.substr(i, nm.length) === nm) {
          flush();
          segs.push({ t: (provs[nm] ? provs[nm] + " " : "") + nm, c: dashColor(nm) });
          i += nm.length; matched = true; break;
        }
      }
      if (matched) continue;
      buf += ch; i++;
    }
    flush();
    return segs.map(s => s.c ? '<span style="color:' + s.c + '">' + esc(s.t) + '</span>' : esc(s.t)).join("");
  }
  el.innerHTML = String(text).split(NL).map(paintLine).join(NL);
  el.classList.toggle("blackbg", !!window.__termBlack);
  el.scrollTop = stick ? el.scrollHeight : keep;
}

// terminal fonts - all locally installed families, so nothing is fetched over the network
const // The third value says whether every character is the same width. The terminals line
// their columns up with spaces, so only a fixed-width font can hold them straight.
TERM_FONTS = [
  ["Cascadia Code", '"Cascadia Code", Consolas, monospace', true],
  ["Cascadia Mono", '"Cascadia Mono", Consolas, monospace', true],
  ["Consolas", 'Consolas, monospace', true],
  ["Courier New", '"Courier New", Courier, monospace', true],
  ["Lucida Console", '"Lucida Console", Monaco, monospace', true],
  ["Plus Jakarta Sans (UI)", '"Plus Jakarta Sans", Inter, "Segoe UI", sans-serif', false],
  ["Inter", 'Inter, system-ui, sans-serif', false],
  ["Segoe UI", '"Segoe UI", system-ui, sans-serif', false],
  ["Calibri", 'Calibri, "Segoe UI", sans-serif', false],
  ["Arial", 'Arial, Helvetica, sans-serif', false],
  ["Verdana", 'Verdana, Geneva, sans-serif', false],
  ["Tahoma", 'Tahoma, Geneva, sans-serif', false],
  ["Trebuchet MS", '"Trebuchet MS", Tahoma, sans-serif', false],
  ["Georgia", 'Georgia, "Times New Roman", serif', false],
  ["Times New Roman", '"Times New Roman", Times, serif', false],
  ["System default", 'system-ui, sans-serif', false]
];
const TERM_FONT_DEFAULT = "Cascadia Code";
function termFontStack(label) {
  for (let i = 0; i < TERM_FONTS.length; i++) if (TERM_FONTS[i][0] === label) return TERM_FONTS[i][1];
  return TERM_FONTS[0][1];
}
const TS_KINDS = __TSKINDS__;   // injected from TERM_SCALE_KINDS - one list, not two
let termScales = {};
TS_KINDS.forEach(function(k) { termScales[k] = { mode: "manual", size: 12, on: true, font: TERM_FONT_DEFAULT }; });
let tailNormalW = { dashboard: 0, thinking: 0, split: 0, tts: 0 };   // keyed by Full Window wrapper
const TSUB_KIND = { think: "thinking", split: "splitd", tts: "tts" };   // sub-tab -> scale kind
function tKind() { return TSUB_KIND[curTsub] || "dashboard"; }
function tsForId(id) {                       // "tail-<kind>" is the naming rule; honour it
  return termScales[String(id || "").replace("tail-", "")] || termScales.dashboard;
}
const MAXGROUP = { thinking: "thinking", splitd: "split", splitt: "split", tts: "tts" };
function maxKindForId(id) { return MAXGROUP[String(id || "").replace("tail-", "")] || "dashboard"; }
function maxScaleRatio(el) {
  const normal = tailNormalW[maxKindForId(el.id)] || 0, full = el.clientWidth || 0;
  if (normal <= 0 || full <= 0) return 1;
  return Math.max(1, Math.min(3, full / normal));   // scale text by how much wider Full Window is vs normal
}
function autoFitTail(el, txt) {
  if (!el) return;
  const cs = window.getComputedStyle(el);
  const padL = parseFloat(cs.paddingLeft) || 0, padR = parseFloat(cs.paddingRight) || 0;
  const avail = el.clientWidth - padL - padR;                // usable width, padding excluded
  if (avail <= 0) return;                                    // hidden / not laid out yet -> skip
  const text = (txt != null ? String(txt) : (el.textContent || ""));
  let longest = "";                                          // monospace -> char count tracks width
  const lines = text.split(String.fromCharCode(10));
  for (let i = 0; i < lines.length; i++) if (lines[i].length > longest.length) longest = lines[i];
  if (!longest) { el.style.fontSize = "13px"; return; }
  const ctx = autoFitTail._ctx || (autoFitTail._ctx = document.createElement("canvas").getContext("2d"));
  const REF = 200;                                           // measure the longest line at a big ref size
  ctx.font = REF + "px " + (cs.fontFamily || "monospace");
  const wRef = ctx.measureText(longest).width || 1;
  const inMax = !!(el.closest && el.closest(".tmax"));
  let fs = (avail - 2) * REF / wRef;                         // size so the longest line spans the width (-2px slack)
  fs = Math.max(7, Math.min(inMax ? 42 : 28, fs));           // Full Window fills at full (100%) scale, not halved
  el.style.fontSize = fs.toFixed(1) + "px";
}
function sizeTailEl(el, txt) {
  if (!el) return;
  const ts = tsForId(el.id), inMax = !!(el.closest && el.closest(".tmax"));
  // the .tail font-family rule carries !important, so the per-terminal choice must too
  el.style.setProperty("font-family", termFontStack(ts.font || TERM_FONT_DEFAULT), "important");
  if (ts.on && ts.mode === "auto") { autoFitTail(el, txt); return; }     // scaling on + auto -> fit to content
  let fs = ts.size;                                                       // off, or manual -> fixed size
  if (inMax) fs = fs * maxScaleRatio(el);                                // Full Window scales the text with the window
  el.style.fontSize = fs.toFixed(1) + "px";
}
function applyTermScale() {
  ["tail-dashboard", "tail-thinking", "tail-splitd", "tail-splitt", "tail-tts"].forEach(function(id) { sizeTailEl(document.getElementById(id)); });
}
function fillFsSel(sel) {
  if (!sel || sel.options.length) return;
  let o = "";
  for (let n = 8; n <= 24; n++) o += '<option value="' + n + '">' + n + ' px</option>';
  sel.innerHTML = o;
}
function fillFontSel(sel) {
  if (!sel || sel.options.length) return;
  let o = "";
  for (let i = 0; i < TERM_FONTS.length; i++) {
    const nm = TERM_FONTS[i][0], fixed = TERM_FONTS[i][2];
    // say which ones will hold the columns straight, rather than letting you find out
    o += '<option value="' + esc(nm) + '" style="font-family:' + TERM_FONTS[i][1]
       + ';color:' + (fixed ? "var(--ok)" : "var(--warn)") + '">' + esc(nm)
       + esc(fixed ? "" : "  [columns will not line up]") + '</option>';
  }
  sel.innerHTML = o;
}
function setTermFont(label, kind) {
  const k = kind || tKind();
  termScales[k].font = label;
  applyTermScale();
  syncTermScaleUI();
  post("/api/settings", { termScales: termScales });
}
function initTermScaleSelect() {
  TS_KINDS.map(function(k) { return "-" + k; }).forEach(function(sfx) {
    fillFsSel(document.getElementById("termfs-sel" + sfx));
    fillFontSel(document.getElementById("termfont-sel" + sfx));
  });
}
function syncScaleRow(kind, sfx) {
  const ts = termScales[kind], man = ts.mode === "manual";
  const ba = document.getElementById("termscale-auto" + sfx), bm = document.getElementById("termscale-manual" + sfx);
  if (ba) ba.classList.toggle("on", !man);
  if (bm) bm.classList.toggle("on", man);
  const sel = document.getElementById("termfs-sel" + sfx);
  if (sel) sel.value = String(ts.size);
  const wrap = document.getElementById("termfs-wrap" + sfx);
  if (wrap) wrap.style.display = man ? "inline-flex" : "none";   // size only applies in manual
  const fsel = document.getElementById("termfont-sel" + sfx);
  if (fsel) { fillFontSel(fsel); fsel.value = ts.font || TERM_FONT_DEFAULT; }
  const msg = document.getElementById("termscale-msg" + sfx);
  if (msg) msg.innerHTML = "";
  const rst = document.getElementById("tscalebtn" + sfx);
  if (rst) rst.disabled = !man;                    // only meaningful once a size is set
}
function syncTermScaleUI() {
  TS_KINDS.forEach(function(k) { syncScaleRow(k, "-" + k); });
  syncTextScalingButtons();
}
function setTermScaleMode(mode, kind) {
  const k = termScales[kind] ? kind : tKind();
  termScales[k].mode = (mode === "manual") ? "manual" : "auto";
  syncTermScaleUI();
  applyTermScale();
  post("/api/settings", { termScales: termScales });
}
function setTermFontSize(px, kind) {
  const k = termScales[kind] ? kind : tKind();
  termScales[k].size = Math.max(8, Math.min(24, parseInt(px, 10) || 12));
  applyTermScale();
  post("/api/settings", { termScales: termScales });
}
function syncTextScalingButtons() {
  TS_KINDS.forEach(function(k) {
    const b = document.getElementById("tscalebtn-" + k);
    if (b) b.disabled = termScales[k].mode !== "manual";
  });
}
let __termResizeT;
window.addEventListener("resize", function() { clearTimeout(__termResizeT); __termResizeT = setTimeout(applyTermScale, 150); });
window.addEventListener("resize", function() { if (curTab === "network") setTimeout(drawNetLines, 120); });
/* ---------- terminal display toggles ---------- */
// which pane may splice. splitd/splitt are panes, not feeds - each can be set to
// the proxy, and syncSplitUI hides the button when it is not.
const TERM_INS_KINDS = ["dashboard", "splitd", "splitt"];
let lastTtsTail = "";
// per terminal: one pane hiding the time should not silence the other
function stampsOffList() {
  return String(((state && state.settings) || {}).termStampsOff || "")
         .split(",").map(s => s.trim()).filter(Boolean);
}
function termStampsOn(which) {
  if (!which) return true;
  return stampsOffList().indexOf(which) < 0;
}
function termInsTtsOn() {
  return String(((state && state.settings) || {}).termInsTts || "off").toLowerCase() === "on";
}
async function termToggle(key, onValue, offValue) {
  const st = (state && state.settings) || {};
  const now = String(st[key] || offValue).toLowerCase() === onValue ? offValue : onValue;
  if (state && state.settings) state.settings[key] = now;
  const body = {}; body[key] = now;
  await post("/api/settings", body);
  await load();
  syncTermToggleUI();
  refreshCurTerm();
}
async function termStampsToggle(which) {
  const off = stampsOffList();
  const at = off.indexOf(which);
  if (at >= 0) off.splice(at, 1); else off.push(which);
  const now = off.join(",");
  if (state && state.settings) state.settings.termStampsOff = now;
  await post("/api/settings", { termStampsOff: now });
  await load();
  syncTermToggleUI();
  refreshCurTerm();
}
// the buttons are shared markup, so the lit state is applied rather than rendered
// ": On" in blue, ": Off" plain - the same reading as Remote Access and Fullscreen in
// the header, so a state you can toggle looks the same wherever it appears.
function onOffLabel(name, on) {
  return esc(name) + ": " + (on ? '<span class="blueglow">On</span>' : "Off");
}
function syncTermToggleUI() {
  document.querySelectorAll('[data-act="termStamps"]').forEach(b => {
    const on = termStampsOn(b.dataset.kind || "");
    b.classList.toggle("on", on);
    b.innerHTML = onOffLabel("Timestamps", on);
  });
  document.querySelectorAll('[data-act="termInsTts"]').forEach(b => {
    const on = termInsTtsOn();
    b.classList.toggle("on", on);
    b.innerHTML = onOffLabel("Insert TTS", on);
  });
}
// [20:45:12.86] at the start of a line, and nowhere else
const TSTAMP_RX = /^\\[\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?\\]\\s?/;
function stripStamps(text) {
  const NL = String.fromCharCode(10);
  return String(text).split(NL).map(l => l.replace(TSTAMP_RX, "")).join(NL);
}
// A spoken line is identified by the WAVE markers around what was said, not by the
// leading icon - that now varies with the mood the line asks for.
const SAID = String.fromCharCode(12336) + String.fromCharCode(65039);
const BOLT = String.fromCodePoint(9889);
// a channel tree hanging off the completion above, as Discord draws one
const TREE_MID = String.fromCodePoint(9500) + String.fromCodePoint(9472);   // |-
const TREE_END = String.fromCodePoint(9492) + String.fromCodePoint(9472);   // L-
const TREE_PAD = "   ";                          // sits in from the parent row
// a player line is the user speaking, not something a reply produced, so it hangs
// off nothing and gets a plain marker instead of a branch
// the same indent as a branch, so a player line starts where an NPC line does
const LONE_MARK = TREE_PAD + String.fromCodePoint(10148);
// [23:26:34.67] -> seconds past midnight, so two logs can be lined up
function stampSecs(line) {
  const m = String(line).match(/^\\[(\\d{2}):(\\d{2}):(\\d{2})(?:\\.(\\d+))?\\]/);
  if (!m) return null;
  return (+m[1]) * 3600 + (+m[2]) * 60 + (+m[3]) + (m[4] ? ("0." + m[4]) * 1 : 0);
}
// Every spoken line in the TTS log, with when it was said and how fast it came out.
function ttsSpokenLines() {
  const NL = String.fromCharCode(10);
  const lines = String(lastTtsTail || "").split(NL);
  const out = [];
  for (let i = 0; i < lines.length; i++) {
    if (lines[i].indexOf(SAID) < 0) continue;
    const at = stampSecs(lines[i]);
    let rt = "";
    for (let j = i + 1; j < lines.length && j < i + 12; j++) {
      if (lines[j].indexOf(SAID) >= 0) break;         // the next request started
      const m = lines[j].match(/([0-9.]+)x realtime/);
      if (m) { rt = m[1]; break; }
    }
    const raw = lines[i].trim();
    const sm = raw.match(TSTAMP_RX);
    out.push({ at: at,
               stamp: sm ? sm[0].trim() : "",
               who: ((raw.match(/[^ ]+:/g) || []).slice(-1)[0] || "").replace(":", ""),
               body: (sm ? raw.slice(sm[0].length) : raw).replace(/^\\s+/, "")
                     + (rt ? ("  (" + BOLT + " " + rt + "x)") : "") });
  }
  return out;
}
// A completion line: it carries token and rate columns and ends in seconds.
function isCompletion(l) {
  return l.indexOf(" tok ") > 0 && l.indexOf(" tps ") > 0 && l.indexOf("sec") > 0;
}
// Place each spoken line beside the completion it belongs to.
//
// Two things measured from real logs. A spoken line lands 0.2-0.5s BEFORE its dialogue
// completion, because SkyrimNet fires TTS on the final token and llama.cpp writes its
// timing line a moment later. And a streamed reply produces SEVERAL spoken lines a
// second or so apart - matching each one on its own time scattered them among the Meta
// and Vision calls that landed in between. So group them into bursts first and attach
// the whole burst where its first line belongs.
// A turn's chunks share a SPEAKER as well as being close together. Grouping on the gap
// alone merged the player's own line with the reply that followed it 3.7s later, which
// is a different event entirely - so require both.
const TTS_BURST_GAP = 6.0;
const TTS_NEAR_DLG = 3.0;       // and a burst starts within this of its completion

function ttsBursts() {
  const said = ttsSpokenLines().filter(s => s.at !== null).sort((a, b) => a.at - b.at);
  const out = [];
  said.forEach(s => {
    const last = out.length ? out[out.length - 1] : null;
    const near = last && s.at - last.at[last.at.length - 1] <= TTS_BURST_GAP;
    if (near && last.who === s.who) {
      last.said.push(s);
      last.at.push(s.at);
    } else {
      out.push({ said: [s], at: [s.at], who: s.who });
    }
  });
  return out;
}

function spliceTts(text) {
  const NL = String.fromCharCode(10);
  const bursts = ttsBursts();
  if (!bursts.length) return text;
  const lines = String(text).split(NL);
  const spots = [];
  for (let i = 0; i < lines.length; i++) {
    const at = stampSecs(lines[i]);
    if (at !== null) spots.push({ i: i, at: at, dlg: /dialogue/i.test(lines[i]) });
  }
  if (!spots.length) return text;
  const groups = new Map();
  bursts.forEach(b => {
    const first = b.at[0];
    let target = null, bestGap = TTS_NEAR_DLG, anchored = false;
    for (const sp of spots) {              // the dialogue completion nearest its start
      if (!sp.dlg) continue;
      const gap = Math.abs(sp.at - first);
      if (gap <= bestGap) { bestGap = gap; target = sp.i; anchored = true; }
    }
    if (target === null) {                 // no reply nearby: place it in time order
      for (const sp of spots) {
        if (sp.at <= first) target = sp.i; else break;
      }
    }
    if (target === null) return;           // it predates the visible window
    if (!groups.has(target)) groups.set(target, []);
    // a branch when it hangs off a reply; a plain arrow when it hangs off nothing
    const drawn = b.said.map((s, k) => {
      const mark = anchored
        ? TREE_PAD + ((k === b.said.length - 1) ? TREE_END : TREE_MID)
        : LONE_MARK;
      return (s.stamp ? s.stamp + " " : "") + mark + " " + s.body;
    });
    groups.get(target).push(...drawn);
  });
  [...groups.keys()].sort((a, b) => b - a).forEach(at =>
    lines.splice(at + 1, 0, ...groups.get(at)));
  return lines.join(NL);
}

/* One spoken line, painted: magenta speaker, gold dialogue, cyan tags between white
   stars. Shared, so a line spliced into the proxy terminal looks the same as it does
   in the TTS terminal - it used to arrive there unpainted. */
// Columns a string occupies in the terminal: an astral character (every emoji here) is
// two cells wide, so counting JS characters would under-measure the indent.
// A spoken line is rendered as a block so it can hang-indent when it wraps, and a block
// ends its own line - adding a newline after it too would leave a blank row.
function joinLines(lines, fn) {
  const NL = String.fromCharCode(10);
  const out = [];
  lines.forEach(function(line, i) {
    const html = fn(line);
    out.push(html);
    const isBlock = html.slice(0, 20).indexOf("display:block") >= 0;
    if (!isBlock && i < lines.length - 1) out.push(NL);
  });
  return out.join("");
}

function termCols(s) {
  let n = 0;
  for (const ch of String(s)) n += (ch.codePointAt(0) > 0xFFFF ? 2 : 1);
  return n;
}
function paintSpoken(line) {
  const WAVE = String.fromCharCode(12336) + String.fromCharCode(65039);
  // everything before what was said: stamp, branch, icon, speaker. A wrapped line hangs
  // under that rather than starting back at the tree column and cutting through it.
  const upto = line.indexOf(WAVE);
  const indent = upto > 0 ? termCols(line.slice(0, upto)) : 0;
  // LITERALS, not new RegExp("..."): the PAGE string and the JS string literal each
  // eat a backslash, so a quoted "\\*" would arrive as a bare quantifier
  const tagRx = /\\*([^*]{1,24})\\*|\\[pause [0-9.]+s\\]/g;
  const MK = String.fromCodePoint(127917);           // the mask starts a spoken line
  const CY = "#2ef2ff", WH = "#ffffff", MAG = "#ff5dc8", SAY = "#f2c14e";   // gold
  const tint = (c, s, b) => '<span style="color:' + c + (b ? ";font-weight:600" : "") + '">'
                          + esc(s) + '</span>';
  const marked = (s, base) => {
    const plain = (x) => (base ? tint(base, x, false) : esc(x));
    let out = "", last = 0, m;
    tagRx.lastIndex = 0;
    while ((m = tagRx.exec(s)) !== null) {
      out += plain(s.slice(last, m.index));
      out += (m[1] === undefined)
           ? tint(CY, m[0], true)                          // [pause 2.5s], MOSS's own
           : tint(WH, "*", true) + tint(CY, m[1], true) + tint(WH, "*", true);
      last = m.index + m[0].length;
    }
    return out + plain(s.slice(last));
  };
  // an inserted line carries a tree glyph; paint it accent with a glow and keep the
  // rest of the line as it is
  const G_MID = String.fromCodePoint(9500), G_END = String.fromCodePoint(9492);
  const G_LONE = String.fromCodePoint(10148);
  const GLOW = "color:var(--acc);font-weight:700;text-shadow:0 0 4px var(--acc),0 0 10px var(--acc),0 0 20px var(--acc)";
  let pre = "";
  const gi = line.search(new RegExp("[" + G_MID + G_END + G_LONE + "]"));
  if (gi >= 0) {
    const ch = line.charAt(gi);
    if (ch === G_LONE) {                                   // hangs off nothing
      // 2ch wide, matching the drawn branch, so both start in the same column
      pre = esc(line.slice(0, gi))
          + '<span style="' + GLOW + ';display:inline-block;width:2ch">'
          + esc(ch) + '</span>';
      line = line.slice(gi + 1);
    } else {
      // DRAWN, not typed: a stretched glyph overlapped the row below and the glow
      // doubled up where they met
      pre = esc(line.slice(0, gi))
          + '<span class="' + (ch === G_END ? "tbrend" : "tbr") + '"></span>';
      line = line.slice(gi + 2);
    }
  }
  const a = line.indexOf(WAVE), b = line.lastIndexOf(WAVE);
  if (a < 0 || b <= a) return pre + marked(line, null);    // not a spoken line
  const head = line.slice(0, a), said = line.slice(a + WAVE.length, b);
  // the speaker is between the mask and the FIRST colon after it. Matching on the last
  // colon instead swallowed the timestamp, which is full of them.
  // The icon now varies with the mood, so the speaker is read structurally instead:
  // the head is "<icon> Name: ", so it is the first token, then the name to the colon.
  let lead = esc(head);
  const bare = head.replace(/^\\s+/, "");
  const off = head.length - bare.length;
  const sp = bare.indexOf(" "), c = bare.indexOf(":");
  if (sp > 0 && c > sp) {
    // a fixed cell for the icon: emoji widths differ between faces, so without this the
    // names below each other do not line up
    lead = esc(head.slice(0, off))
         + '<span style="display:inline-block;width:2ch;text-align:center">'
         + esc(bare.slice(0, sp)) + '</span>' + esc(" ")
         + tint(MAG, bare.slice(sp + 1, c).trim(), true)
         + esc(": ");
  }
  const body = pre + lead + esc(WAVE) + marked(said, SAY) + esc(WAVE)
             + esc(line.slice(b + WAVE.length));
  return '<span style="display:block;padding-left:' + indent + 'ch;text-indent:-'
       + indent + 'ch">' + body + '</span>';
}

// `which` is the FEED being shown; `pane` is the terminal it is shown IN. In split view
// they differ - the left pane may be showing the proxy feed - and a per-terminal setting
// has to follow the pane, not the feed, or the button toggles something else.
function paintTail(which, text, elOv, pane) {
  const el = elOv || $("tail-" + which);
  if (!el) return;
  const who = pane || which;
  // splice FIRST: it places lines by timestamp, so stripping them first left it
  // nothing to match on and the insertions silently vanished
  if (termInsTtsOn() && TERM_INS_KINDS.indexOf(which) >= 0) text = spliceTts(text);
  if (!termStampsOn(who)) text = stripStamps(text);
  sizeTailEl(el, text);
  if (which === "thinking") { paintThink(el, text); return; }
  if (which === "tts") {
    const NLT = String.fromCharCode(10);
    el.innerHTML = joinLines(String(text).split(NLT), paintSpoken);
    return;
  }
  if (which !== "dashboard") { el.textContent = text; return; }
  const NL = String.fromCharCode(10);
  const numRx = new RegExp("^[0-9][0-9.,]*(ms)?$");
  const thinkRx = new RegExp("^[(]~[0-9]+[)]$");
  const holdRx = new RegExp("^[+][0-9]+(ms)?$");   // priority-queue wait, e.g. +2922 (ms follows as its own token)
  const portRx = new RegExp("^[[][0-9]{4}[]]$");
  const errRx = new RegExp("error|fail|timeout|refused", "i");
  const names = new Set((state && state.routing || []).flatMap(s => (s.providers || []).map(p => p.title)).filter(Boolean));
  const stick = el.scrollTop + el.clientHeight >= el.scrollHeight - 40;
  const keep = el.scrollTop;
  el.innerHTML = joinLines(String(text).split(NL), line => {
    if (line.indexOf(SAID) >= 0) return paintSpoken(line);   // an inserted spoken line
    if (errRx.test(line)) return '<span style="color:var(--err)">' + esc(line) + '</span>';
    return line.split(new RegExp("( +)")).map(tk => {
      if (!tk || tk.indexOf(" ") >= 0) return esc(tk);
      if (tk[0] === "[" && tk.indexOf(":") > 0) return '<span style="color:#7fd4ff">' + esc(tk) + '</span>';
      if (portRx.test(tk)) return '<span style="color:#8b93a3">' + esc(tk) + '</span>';
      if (thinkRx.test(tk)) return '<span style="color:#ff5dc8">' + esc(tk) + '</span>';
      if (holdRx.test(tk)) {
        let body = tk.slice(1), tailMs = "";
        if (body.slice(-2) === "ms") { body = body.slice(0, -2); tailMs = ' <span style="color:#e8ecf2">ms</span>'; }
        return '<span style="color:#e8ecf2">+</span><span style="color:var(--ok)">' + esc(body) + '</span>' + tailMs;
      }
      if (numRx.test(tk)) {
        if (tk.slice(-2) === "ms") return '<span style="color:var(--ok)">' + esc(tk.slice(0, -2)) + '</span> <span style="color:#e8ecf2">ms</span>';
        return '<span style="color:var(--ok)">' + esc(tk) + '</span>';
      }
      if (names.has(tk)) return '<span style="color:' + dashColor(tk) + '">' + esc(tk) + '</span>';
      return '<span style="color:#e8ecf2">' + esc(tk) + '</span>';
    }).join("");
  });
  el.classList.toggle("blackbg", !!window.__termBlack);
  el.scrollTop = stick ? el.scrollHeight : keep;
}


// A step is known by what it is, never by where it sits: inserting one must not
// silently re-point the code that singles out the launch step or the manual yaml step.
function stepAt(name) { return HELPER_STEPS.findIndex(s => s.id === name); }
// the side step about doing the providers by hand belongs to the two yaml steps
function gBranchSel() {
  return "#gstep-" + stepAt("yamlmade") + ", #gstep-" + stepAt("yamlsent") + ", #gbranch";
}
// doing the providers by hand stands in for both yaml steps - said once, so the box
// colour and the requirement behind it cannot disagree
function manualCovers(manual, i) {
  return !!manual && (i === stepAt("yamlmade") || i === stepAt("yamlsent"));
}
// while the guide is on screen, keep it honest: servers come up seconds after Launch
let guideT = 0;
function guideWatch(on) {
  if (!on) { clearInterval(guideT); guideT = 0; return; }
  if (guideT) return;
  guideT = setInterval(async function() {
    if (curTab !== "helper") { clearInterval(guideT); guideT = 0; return; }
    if (uiBusy()) return;
    await load();
    renderHelper();
  }, 3000);
}
// what a chosen file actually is, from the scan the panel already did. Anything it has
// not seen counts as a usable model, so an unknown path is never held against a server.
function modelKindOf(path) {
  const m = (models || []).filter(function(x) { return (x.path || x) === path; })[0];
  return (m && m.kind) || "main";
}
const HELPER_STEPS = [
{ id: "folders", label: "Set folder paths", page: "setup", el: "#set-llamacppPath,#set-modelsDir",
    ok: st => !!(st.llamaOk && st.settings && st.settings.modelsDir) },
  { id: "ips", label: "IP addresses set", page: "proxy", el: "#card-ips",
    ok: st => { const s = (st && st.settings) || {}; return s.onePC === false ? !!(s.panelIp && s.remoteIp) : !!s.panelIp; } },
  { id: "gpus", label: "GPUs detected + enabled", page: "network", el: ".gputitle",
    ok: st => (st.gpus || []).some(g => g.enabled !== false && g.uuid) },
  { id: "server", label: "Server set up with a model", page: "slots", el: ".slotgrid",
    ok: st => (st.slots || []).some(s => s.params && s.params.model && s.scriptExists
                                         && modelKindOf(s.params.model) === "main") },
  // one step now covers the whole wiring job: a server on a GPU, with a model, and
  // at least one provider connected to it - all of which is done in Live Network.
  { id: "network", label: "Live Network complete", page: "network", el: ".netlabel",
    ok: st => {
      const wired = (st.slots || []).filter(s => s.gpuId && s.params && s.params.model).map(s => s.id);
      if (!wired.length) return false;
      return (st.routing || []).some(s => wired.indexOf(s.id) >= 0 && (s.providers || []).length);
    } },
  { id: "yamlmade", label: "providers.yaml generated", page: "proxy", el: "#card-yaml",
    ok: st => !!(st.settings && st.settings.yamlGenerated) },
  { id: "yamlsent", label: "yaml delivered to SkyrimNet", page: "proxy", el: "#card-yaml", ok: st => false },
  { id: "launched", label: "Servers launched", page: "launch", el: "#launchBtn",
    ok: st => (st.slots || []).some(x => x.status && x.status.state === "serving") }
];
function gsCopyLink(url, el) {
  const done = () => { if (el) { const o = el.textContent; el.textContent = "\u2713 copied"; setTimeout(() => { el.textContent = o; }, 1400); } };
  if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(url).then(done, done);
  else { try { const ta = document.createElement("textarea"); ta.value = url; document.body.appendChild(ta); ta.select(); document.execCommand("copy"); document.body.removeChild(ta); } catch (e) {} done(); }
}
function gotoHelperStep(i) {
  showTab("helper");
  setTimeout(() => {
    const g = document.querySelector("#hstep-" + i);
    if (!g) return;
    g.classList.remove("hstep-flash"); void g.getBBox();
    g.classList.add("hstep-flash");
    if (g.scrollIntoView) g.scrollIntoView({ behavior: "smooth", block: "center" });
    setTimeout(() => g.classList.remove("hstep-flash"), 2800);
  }, 140);
}
function helperGo(page, sel) {
  if (page === "setup") showTab("setup");
  else if (page === "proxy") { showTab("dashboard"); showDsub(sel === "#card-yaml" ? "yaml" : "setup"); }
  else if (page === "slots") { showTab("servers"); showSsub("slots"); }
  else if (page === "providers") { showTab("provmgmt"); showPmSub("providers"); }
  else if (page === "network") { showTab("network"); }
  else if (page === "guide") { showTab("helper"); showUgSub("params"); }
  else if (page !== "launch") showTab("servers");
  if (!sel) return;
  setTimeout(() => { flashTargets(sel); }, 200);
}
// step status as a drawn mark rather than an emoji: a tick when done, a cross when
// not, a forward bar when skipped - each with a faint glow in the step's own colour
// Demonstrates the Launch button without launching: full glow and arcs straight away,
// holding for two seconds, then easing back over the last one.
function launchDemo() {
  const lb = $("launchBtn");
  if (!lb) return;
  // With the lightning switched off the step had nothing to point at: helperGo is
  // called without a selector here because the arc was meant to do the pointing. Fall
  // back to the guide's own highlight, the same one every other step uses.
  if (state && state.settings && state.settings.launchArc === false) {
    flashTargets("#launchBtn");
    return;
  }
  lb.classList.remove("lbdemo");
  void lb.getBoundingClientRect();
  lb.classList.add("lbdemo");
  const iv = setInterval(function() {
    const el = $("launchBtn");
    if (!el || !el.isConnected) { clearInterval(iv); return; }
    arcFire(el, true, false);
    arcFire(el, true, true);
  }, 95);
  setTimeout(function() { clearInterval(iv); }, 3000);
  setTimeout(function() { lb.classList.remove("lbdemo"); }, 3050);
}
// the small control in a step's corner: skip ahead, confirm, or undo
function flashTargets(sel) {
  // One highlight for every step. It is drawn around the target and touches nothing
  // inside it, so a folder field, a panel and a heading all light the same way - and a
  // heading lights its symbol and its title together, because they are one element.
  const nodes = document.querySelectorAll(sel);
  if (!nodes.length) return;
  nodes[0].scrollIntoView({ behavior: "smooth", block: "center" });
  nodes.forEach(function(n) {
    n.classList.remove("guidehl");
    void n.offsetWidth;                            // restart cleanly if it is re-clicked
    n.classList.add("guidehl");
    setTimeout(function() { n.classList.remove("guidehl"); }, 2000);
  });
}
function helperSkipped() {
  return (state && state.settings && state.settings.helperSkipped) || [];
}
function helperMissing() {
  if (!state) return [];
  const sk = helperSkipped();
  const manual = !!(state.settings && state.settings.helperManualSN);
  return HELPER_STEPS.slice(0, stepAt("launched")).filter((s, i) => !s.ok(state) && !sk.includes(i) && !manualCovers(manual, i)).map(s => s.label);
}
window.__helperPrev = {}; window.__helperLines = [];
function stepMarkEl(col, kind) {
  const s = '<svg class="gmarksvg" viewBox="0 0 16 16" fill="none" stroke="' + col
    + '" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">';
  if (kind === "done") return s + '<path d="M3.6 8.4l3.1 3.2L12.6 5"/></svg>';
  if (kind === "skip") return s + '<path d="M4.2 4l4.6 4-4.6 4"/><path d="M11.6 4v8"/></svg>';
  return s + '<path d="M4.6 4.6l6.8 6.8M11.4 4.6l-6.8 6.8"/></svg>';
}
function cornerMarkEl(kind) {
  const s = '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.9" '
    + 'stroke-linecap="round" stroke-linejoin="round">';
  if (kind === "tick") return s + '<path d="M3.6 8.4l3 3.1L12.4 5.2"/></svg>';
  if (kind === "undo") return s + '<path d="M4 7.6a4.4 4.4 0 1 0 1.7-3.4"/><path d="M3.2 3.2v3.9h3.9"/></svg>';
  return s + '<path d="M4.5 4l4.6 4-4.6 4"/><path d="M11.4 4v8"/></svg>';
}
// Connectors are drawn from the boxes' measured positions, the same way Live Network
// draws its links - so the diagram is ordinary page content that zooms and reflows
// with everything else instead of a fixed-size picture laid over the interface.
function serpentine() {
  const grid = document.querySelector(".ggrid");
  if (!grid) return 0;
  const items = Array.prototype.slice.call(grid.children);
  if (!items.length) return 0;
  items.forEach(function(el) { el.style.gridColumn = ""; el.style.gridRow = ""; });
  const top0 = items[0].getBoundingClientRect().top;
  let cols = 0;
  items.forEach(function(el) {
    if (Math.abs(el.getBoundingClientRect().top - top0) < 4) cols++;
  });
  if (cols < 2) return cols;
  items.forEach(function(el, i) {
    const r = Math.floor(i / cols), k = i % cols;
    // even rows run to the right, odd rows back to the left, so each row starts
    // directly beneath the step that ended the one above it
    el.style.gridColumn = String(r % 2 === 0 ? k + 1 : cols - k);
    el.style.gridRow = String(r + 1);
  });
  return cols;
}
function drawHelperLines() {
  const wrap = document.getElementById("gwrap"), svg = document.getElementById("glines");
  if (!wrap || !svg) return;
  const W = wrap.getBoundingClientRect();
  svg.setAttribute("viewBox", "0 0 " + Math.max(1, W.width) + " " + Math.max(1, W.height));
  svg.setAttribute("width", W.width);
  svg.setAttribute("height", W.height);
  const box = i => {
    const el = document.getElementById("gstep-" + i);
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { l: r.left - W.left, r: r.right - W.left, t: r.top - W.top, b: r.bottom - W.top,
             cx: r.left - W.left + r.width / 2, cy: r.top - W.top + r.height / 2 };
  };
  let out = '<defs><marker id="gha" markerWidth="5.4" markerHeight="5.4" refX="4.4" refY="2.7" '
    + 'orient="auto"><path d="M0,0 L5.4,2.7 L0,5.4 z" fill="currentColor"/></marker></defs>';
  const line = (d, col, dash) => {
    out += '<path d="' + d + '" stroke="' + col + '" stroke-width="2.5" fill="none" color="' + col + '"'
      + (dash ? ' stroke-dasharray="6 4"' : '') + ' marker-end="url(#gha)"/>';
  };
  const done = window.__helperRes || [];
  for (let i = 1; i < HELPER_STEPS.length; i++) {
    const a = box(i - 1), b = box(i);
    if (!a || !b) continue;
    const col = done[i - 1] ? "var(--ok)" : "#ff5d5d";
    if (Math.abs(a.t - b.t) < 4) {
      // the rows alternate direction, so leave by the edge that faces the next box
      const back = b.cx < a.cx;
      line(back ? "M " + (a.l - 2) + " " + a.cy + " L " + (b.r + 7) + " " + b.cy
                : "M " + (a.r + 2) + " " + a.cy + " L " + (b.l - 7) + " " + b.cy, col);
    }
    else line("M " + a.cx + " " + (a.b + 2) + " C " + a.cx + " " + (a.b + 34) + " "
              + b.cx + " " + (b.t - 34) + " " + b.cx + " " + (b.t - 7), col);
  }
  svg.innerHTML = out;
}
// The manual-providers note is not part of the run of steps, so it only appears while
// the pointer rests on the two steps it bypasses, with its arrows drawn to them.
let branchHide = null;
function showBranch(fromStep) {
  const wrap = document.getElementById("gwrap"), br = document.getElementById("gbranch");
  const bl = document.getElementById("gblines");
  if (!wrap || !br || !bl) return;
  if (fromStep === null) {
    br.classList.remove("gvis");                 // fade out, then take it away
    bl.style.opacity = "0";
    setTimeout(function() {
      if (!br.classList.contains("gvis")) { br.classList.remove("gshow"); bl.innerHTML = ""; }
    }, 520);
    return;
  }
  const W = wrap.getBoundingClientRect();
  const el = document.getElementById("gstep-" + fromStep);
  if (!el) return;
  const r0 = el.getBoundingClientRect();
  const a = { cx: r0.left - W.left + r0.width / 2, b: r0.bottom - W.top };
  br.classList.add("gshow");
  bl.style.opacity = "1";
  requestAnimationFrame(function() { br.classList.add("gvis"); });
  br.style.left = Math.max(4, Math.min(W.width - br.offsetWidth - 4, a.cx - br.offsetWidth / 2)) + "px";
  br.style.top = (a.b + 30) + "px";
  const r = br.getBoundingClientRect();
  const bx = { cx: r.left - W.left + r.width / 2, t: r.top - W.top };
  const col = (state.settings && state.settings.helperManualSN) ? "var(--ok)" : "var(--acc)";
  bl.setAttribute("viewBox", "0 0 " + Math.max(1, W.width) + " " + Math.max(1, W.height));
  bl.setAttribute("width", W.width); bl.setAttribute("height", W.height);
  // a single line, from the step you are pointing at down to the note
  bl.innerHTML = '<defs><marker id="gbh" markerWidth="5.4" markerHeight="5.4" refX="4.4" refY="2.7"'
    + ' orient="auto"><path d="M0,0 L5.4,2.7 L0,5.4 z" fill="' + col + '"/></marker></defs>'
    + '<path d="M ' + a.cx + ' ' + (a.b + 2) + ' C ' + a.cx + ' ' + (a.b + 16) + ' '
      + bx.cx + ' ' + (bx.t - 16) + ' ' + bx.cx + ' ' + (bx.t - 5) + '" stroke="' + col
      + '" stroke-width="2.5" fill="none" stroke-dasharray="6 4" marker-end="url(#gbh)"/>';
}
document.addEventListener("mouseover", function(e) {
  if (!e.target.closest) return;
  const s = e.target.closest(gBranchSel());
  if (!s) return;
  clearTimeout(branchHide); branchHide = null;
  if (s.id !== "gbranch") showBranch(parseInt(s.id.slice(6), 10));
});
document.addEventListener("mouseout", function(e) {
  if (!e.target.closest) return;
  const s = e.target.closest(gBranchSel());
  if (!s) return;
  const to = e.relatedTarget;
  if (to && to.closest && to.closest(gBranchSel())) return;
  // leave it up long enough to reach and press
  clearTimeout(branchHide);
  branchHide = setTimeout(function() { showBranch(null); }, 2000);
});
function renderHelper() {
  const pane = $("ugpane-main");
  if (!pane || !state) return;
  const sk = helperSkipped();
  const manual = !!(state.settings && state.settings.helperManualSN);
  const forced = (state.settings && state.settings.helperForceReset) || [];
  const res = HELPER_STEPS.map((s, i) => (i === stepAt("gpus") || !forced.includes(i))
    && (s.ok(state) || sk.includes(i) || manualCovers(manual, i)));
  window.__helperRes = res;
  HELPER_STEPS.forEach((s, i) => {
    if (res[i] && window.__helperPrev[i] === false)
      window.__helperLines.push("[" + new Date().toTimeString().slice(0, 8) + "] " + s.label + " completed");
    window.__helperPrev[i] = res[i];
  });
  if (window.__helperLines.length > 60) window.__helperLines = window.__helperLines.slice(-60);

  const cards = HELPER_STEPS.map((s, i) => {
    const col = res[i] ? "var(--ok)" : "#ff5d5d";
    const skp = sk.includes(i);
    const kind = (skp && !(i === stepAt("yamlmade") || i === stepAt("yamlsent"))) ? "skip" : (res[i] ? "done" : "todo");
    const showBtn = !s.ok(state) || forced.includes(i);
    return '<div class="gstep' + (res[i] ? " gok" : " gbad") + (skp ? " gskipped" : "") + '"'
      + ' id="gstep-' + i + '" data-act="helperGo" data-step="' + i + '"'
      + ' data-el="' + esc(s.el || "") + '" data-page="' + s.page + '">'
      + '<div class="gtop">' + stepMarkEl(col, kind)
      + '<span class="gnum" style="color:' + col + '">step ' + (i + 1) + '</span>'
      + (showBtn
          ? '<span class="gbtn gstepbtn' + (res[i] ? " gdone" : "") + '" data-act="helperSkip" data-step="' + i + '"'
            + ' title="' + (skp ? "put this step back" : "mark this step done") + '">'
            + cornerMarkEl(skp ? "undo" : ((i === stepAt("yamlmade") || i === stepAt("yamlsent")) ? "tick" : "skip")) + '</span>'
          : '')
      + '</div><div class="glabel">' + esc(s.label) + '</div>'
      // this one has ok: () => false - nothing can ever satisfy it but the tick, so it
      // sat red for ever on people who did not realise
      + ((i === stepAt("yamlsent") && !res[i])
          ? '<div class="gmanual">Manual step - click the tick</div>' : "")
      + '</div>';
  }).join("");

  const branch = '<div class="gbranch' + (manual ? " gon" : "") + '" id="gbranch">'
    + '<span class="gbtext">I manually set up providers in SkyrimNet UI</span>'
    + '<span class="gbtn gstepbtn' + (manual ? " gdone" : "") + '" data-act="helperManual"'
    + ' title="' + (manual ? "undo this" : "I did this myself") + '">'
    + cornerMarkEl(manual ? "undo" : "tick") + '</span></div>'
    + '<svg class="gblines" id="gblines" xmlns="http://www.w3.org/2000/svg"></svg>';

  const HB = String.fromCharCode(92);
  const YCFG = ["overwrite","SKSE","Plugins","SkyrimNet","config"].join(HB);
  const HELPER_DESC = [
    "open [Folder Settings] and set the three required folders: your llama.cpp folder (contains llama-server.exe, e.g. C:" + HB + "llama.cpp-cuda), your ps1 launcher folder, and your models folder",
    ((state.settings && state.settings.onePC === false)
      ? "open [Proxy > Proxy Setup] and fill in BOTH IPs - this PandorumLLM PC and the remote gaming PC - pressing [Set] on each (green tick confirms)"
      : "open [Proxy > Proxy Setup] and set this PandorumLLM PC IP address, pressing [Set] (green tick confirms) - 1 PC Setup only needs this one; switch to 2 PC Setup to also set the remote gaming PC"),
    "in [Live Network] open PC GPUs, press Detect GPUs, then make sure every card you want to use is enabled (they are pinned by UUID)",
    "open [Server > Servers] and set at least one server up: pick its model and let it build its launcher. Only one server needs a model to move on - any others can be left without one until you want them",
    "link every server to a GPU and drop providers into it in [Live Network], or just press Recommended setup",
    "in [Proxy > SkyrimNet YAML] press Generate providers.yaml (it refuses until the panel IP is set)",
    "place providerYAML" + HB + "Providers.yaml into your Modlist at <Modlist>" + HB + YCFG + HB + "Providers.yaml - or click [Create Providers.yaml] and pick that config folder so it lands there directly",
    "press [Launch] at the top - each server opens its own window and its box turns green here once it is serving"
  ];
  const nxt = HELPER_STEPS.findIndex((s, i) => !res[i]);
  const tail = nxt < 0 ? "all steps complete - Launch away"
    : "next: " + HELPER_STEPS[nxt].label + "  (click its box to go there)" + String.fromCharCode(10) + "   how: " + HELPER_DESC[nxt];
  pane.innerHTML = '<div class="card"><div class="row" style="gap:8px"><b style="font-size:1.2em;margin-right:22px">Setup Helper</b>'
    + '<button class="stop" data-act="helperCheck" title="check what is actually done and summarize it below">Check completion status</button>'
    + '<button class="stop" data-act="helperReset" title="clear all skipped steps and the helper log">Reset steps</button>'
    + '<button class="stop" data-act="helperRevert" title="restore the step flags saved by the last Reset">Revert reset</button>'
    + '<span class="hint" style="margin-left:auto">click any box to jump to that setting - boxes and arrows go green as you complete them</span></div>'
    + '<div class="gwrap" id="gwrap"><svg class="glines" id="glines" xmlns="http://www.w3.org/2000/svg"></svg>'
    + '<div class="ggrid">' + cards + '</div>' + branch + '</div>'
    + '<pre class="tail" id="helper-log" style="height:300px;min-height:120px;margin-top:10px;white-space:pre-wrap;resize:vertical;overflow:auto">'
    + esc(window.__helperLines.join(String.fromCharCode(10)) + (window.__helperLines.length ? String.fromCharCode(10) : "") + tail) + '</pre></div>';
  requestAnimationFrame(function() { serpentine(); drawHelperLines(); });
}
const THEME_VARS = ["bg","card","edge","txt","dim","acc","ok","warn","err","selglow"];
const THEMES = {
  "Pandorum":    { bg:"#0f1115", card:"#171a21", edge:"#262b36", txt:"#d7dce5", dim:"#8b93a3", acc:"#4da3ff", ok:"#3fd68f", warn:"#f0b429", err:"#ff5d5d", selglow:"#000000" },
"OpenRouter":  { bg:"#0d0e10", card:"#151619", edge:"#26282d", txt:"#ececf1", dim:"#9aa0a8", acc:"#b5f320", ok:"#3fdd78", warn:"#eab308", err:"#ef4444", selglow:"#000000" },
  "Dragonborn":  { bg:"#141210", card:"#1c1915", edge:"#33291c", txt:"#efe6d2", dim:"#a3947c", acc:"#d9a92f", ok:"#7dbb5e", warn:"#e0a520", err:"#d9534f", selglow:"#000000" },
  "Parchment":   { bg:"#e8e0cd", card:"#f4eee0", edge:"#c9bfa5", txt:"#2c2417", dim:"#6d6350", acc:"#a8842c", ok:"#3f7d3a", warn:"#b07a1f", err:"#b03a30", selglow:"#000000" },
  "Silver-Blood":{ bg:"#101318", card:"#171c24", edge:"#2a3242", txt:"#dfe5ef", dim:"#93a0b4", acc:"#b9c6e2", ok:"#69c78e", warn:"#d9b23c", err:"#e06060", selglow:"#000000" },
  "Stormcloak":  { bg:"#0d1219", card:"#131a24", edge:"#233144", txt:"#dbe4f0", dim:"#8b9bb1", acc:"#4f7fbf", ok:"#4fbf7f", warn:"#d9a53c", err:"#e05555", selglow:"#000000" },
  "Imperial":    { bg:"#130f0f", card:"#1b1414", edge:"#332020", txt:"#efe0dc", dim:"#a58a84", acc:"#c03434", ok:"#6fae5c", warn:"#d9a53c", err:"#ff6b5e", selglow:"#000000" },
  "Terminal":    { bg:"#050705", card:"#0a0f0a", edge:"#1c2e1c", txt:"#c9f2c9", dim:"#6fae6f", acc:"#33ff66", ok:"#33ff66", warn:"#d9d94a", err:"#ff5555", selglow:"#000000" },
  "Dwemer":      { bg:"#12100c", card:"#1a1712", edge:"#332a1c", txt:"#ead9c0", dim:"#a08c6c", acc:"#d08a3e", ok:"#8fae5c", warn:"#e0a520", err:"#d95f4f", selglow:"#000000" },
  "Nightingale": { bg:"#0e0c14", card:"#151221", edge:"#2a2342", txt:"#e2dcf2", dim:"#9a90b8", acc:"#8b6ff0", ok:"#5fc78e", warn:"#d9a53c", err:"#e05f7a", selglow:"#000000" },
  "Aurora":      { bg:"#0a1013", card:"#101a1e", edge:"#1e3238", txt:"#d8ecef", dim:"#84a5ab", acc:"#2dd4bf", ok:"#3fdd78", warn:"#e0c23c", err:"#ef5350", selglow:"#000000" }
};
function applyTheme(vars) {
  const r = document.documentElement.style;
  THEME_VARS.forEach(k => { if (vars && vars[k]) r.setProperty("--" + k, vars[k]); });
  const cv = currentVars();
  document.querySelectorAll('input[type="color"][data-var]').forEach(function(el) {
    const v = cv[el.dataset.var];                 // keep the swatches showing the truth
    if (v) el.value = v;
  });
  syncFieldInk();
}
// ITEM 1: a text box carries its own background, so its text has to contrast with that
// rather than with whatever lies behind the panel. Measure the real background and pick
// ink to suit, so a light theme does not leave pale text on a pale field.
function syncFieldInk() {
  const probe = document.querySelector("input.edit, input.txt, select");
  if (!probe) return;
  const bg = getComputedStyle(probe).backgroundColor || "";
  const nums = [];                                 // pulled out by hand: the PAGE string
  let cur = "";                                    // cannot carry regex backslashes
  for (let i = 0; i < bg.length; i++) {
    const ch = bg.charAt(i);
    if (ch >= "0" && ch <= "9") cur += ch;
    else { if (cur) nums.push(parseInt(cur, 10)); cur = ""; }
  }
  if (cur) nums.push(parseInt(cur, 10));
  if (nums.length < 3) return;
  const f = function(v) { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
  const lum = 0.2126 * f(nums[0]) + 0.7152 * f(nums[1]) + 0.0722 * f(nums[2]);
  document.documentElement.style.setProperty("--fieldtxt", lum > 0.42 ? "#0b0d11" : "#eef2f7");
}
function currentVars() {
  const cs = getComputedStyle(document.documentElement);
  const o = {};
  THEME_VARS.forEach(k => { o[k] = cs.getPropertyValue("--" + k).trim(); });
  return o;
}
let customT = null;
function customVar(inp) {
  document.documentElement.style.setProperty("--" + inp.dataset.var, inp.value);
  clearTimeout(customT);
  customT = setTimeout(() => {
    const vars = {};
    document.querySelectorAll("#tab-custom input[type=color]").forEach(x => vars[x.dataset.var] = x.value);
    post("/api/settings", { themeName: "Custom", themeVars: vars });
  }, 400);
}
const XICO_SVG = '<svg viewBox="0 0 16 16" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round"><path d="M3.6 3.6 12.4 12.4M12.4 3.6 3.6 12.4"/></svg>';
function renderCustom() {
  const pane = $("tab-custom");
  if (!pane) return;
  const cur = (state && state.settings && state.settings.themeName) || "OpenRouter";
  const VAR_LABELS = { bg: "background", card: "cards", edge: "borders", txt: "text", dim: "secondary text", acc: "accent (Launch)", ok: "success / stats", warn: "warnings", err: "errors", selglow: "dropdown menu glow" };
  const mine = (state && state.settings && state.settings.customThemes) || {};
  const arcOn = !(state && state.settings && state.settings.launchArc === false);
  const card = function(name, v, own) {
    return '<div class="card themecard' + (name === cur ? " on" : "") + '" data-act="themePick" data-name="' + esc(name) + '" style="width:150px;cursor:pointer;padding:8px;position:relative">'
      + '<div style="background:' + v.bg + ';border:1px solid ' + v.edge + ';border-radius:8px;height:46px;padding:7px">'
      + '<div style="background:' + v.acc + ';height:9px;border-radius:4px;width:72%"></div>'
      + '<div style="background:' + v.txt + ';height:5px;width:46%;border-radius:3px;margin-top:7px;opacity:.75"></div>'
      + '</div><div style="text-align:center;margin-top:7px;font-weight:600">' + esc(name) + '</div>'
      + (own ? '<span class="themedel" data-act="themeDel" data-name="' + esc(name) + '" title="delete this preset">' + XICO_SVG + '</span>' : '')
      + '</div>';
  };
  let cards = Object.keys(THEMES).map(n => card(n, THEMES[n], false)).join("")
    + Object.keys(mine).map(n => card(n, Object.assign({}, THEMES.OpenRouter, mine[n]), true)).join("");
  const cv = currentVars();
  let pickers = THEME_VARS.map(k =>
    '<div class="row" style="gap:10px;align-items:center;margin-top:6px">'
    + '<input type="color" data-var="' + k + '" value="' + (cv[k] || "#000000") + '" oninput="customVar(this)" style="width:44px;height:30px;border:none;background:none;cursor:pointer">'
    + '<span style="min-width:150px;font-weight:600">' + VAR_LABELS[k] + '</span><span class="hint">--' + k + '</span></div>').join("");
  pane.innerHTML = '<div class="card"><div class="row" style="justify-content:space-between"><b style="font-size:1.2em">Theme Presets</b></div>'
    + '<div class="row" style="flex-wrap:wrap;gap:12px;margin-top:12px">' + cards + '</div></div>'
    + '<div class="card" style="margin-top:14px"><div class="row"><b>Custom Colors</b>'
    + '<button class="stop" data-act="themeSave" title="store the colours below as a preset of your own">Save as preset</button></div>'
    + pickers + '</div>'
    + '<div class="card" style="margin-top:14px"><div class="row"><b>Effects</b></div>'
    + '<div class="row" style="gap:10px;align-items:center;margin-top:8px">'
    + swToggle(arcOn, 'data-act="launchArcToggle" title="the lightning that plays across the Launch button"',
               "Lightning on the Launch button")
    + '</div>'
    + '<div class="hint" style="margin-top:6px;line-height:1.6">With this off the Launch button still '
    + 'changes colour and still shows the running count - only the animation stops.</div></div>';
}
// each folder that has something checkable, and where to say so
const PATH_CHECKS = [["llamacppPath", "llchk"], ["modelsDir", "mdlchk"], ["launcherDir", "lnchk"]];
// Ask about every folder now, rather than waiting for someone to type in one.
async function recheckPaths() {
  for (const c of PATH_CHECKS) {
    const inp = $("set-" + c[0]), msg = $(c[1]);
    if (!inp || !msg) continue;
    const v = inp.value.trim();
    if (!v) { msg.style.display = "none"; continue; }
    const r = await post("/api/path-check", { path: v, kind: c[0] });
    msg.style.display = r.ok ? "none" : "block";
  }
}
function wireLlamaCheck() {
  PATH_CHECKS.forEach(function(c) {
    const inp = $("set-" + c[0]), msg = $(c[1]);
    if (!inp || !msg || inp.dataset.chkwired) return;
    inp.dataset.chkwired = "1";
    let timer = null;
    const run = () => {
      clearTimeout(timer);
      timer = setTimeout(async () => {
        const v = inp.value.trim();
        if (!v) { msg.style.display = "none"; return; }
        const r = await post("/api/path-check", { path: v, kind: c[0] });
        msg.style.display = r.ok ? "none" : "block";
      }, 350);
    };
    inp.addEventListener("input", run);
    inp.addEventListener("change", run);       // also when the field is left or Enter pressed
    run();
  });
}
function nowStamp() {
  const d = new Date(), p = n => ("0" + n).slice(-2);
  return "[" + p(d.getHours()) + ":" + p(d.getMinutes()) + ":" + p(d.getSeconds()) + "] ";
}
function stackPaint() {
  const el = $("stacklog");
  if (!el) return;
  const NL = String.fromCharCode(10);
  el.innerHTML = String(window.__stackTxt || "").split(NL).map(function(ln) {
    // a stamp is exactly "[HH:MM:SS]" - 10 chars, colons at 3 and 6
    if (ln.charAt(0) === "[" && ln.charAt(3) === ":" && ln.charAt(6) === ":" && ln.charAt(9) === "]")
      return '<span style="color:#4da3ff">' + esc(ln.slice(0, 10)) + '</span>' + esc(ln.slice(10));
    return esc(ln);
  }).join(NL);
  if (window.__stackOpen) el.style.display = "block";
}
function stackSet(txt) { window.__stackTxt = String(txt || ""); stackPaint(); }
function stackAdd(line) {
  const NL = String.fromCharCode(10);
  window.__stackTxt = (window.__stackTxt ? window.__stackTxt + NL : "") + nowStamp() + line;
  stackPaint();
  const el = $("stacklog"); if (el) el.scrollTop = el.scrollHeight;
}
function fleetWatch() {
  if (!state) return;
  const dot = $("fleet-dot");
  const targets = (state.routing || []).filter(s => s.hasScript);
  const stmap = {};
  (state.slots || []).forEach(x => stmap[x.id] = x.status && x.status.state);
  const serving = targets.filter(s => stmap[s.id] === "serving");
  if (window.__terminating && !serving.length) window.__terminating = false;   // shutdown finished
  if (dot) {
    let emoji, title, glow;
    if (window.__terminating) { emoji = "🔴"; title = "fleet status: shutting down..."; glow = "red"; }
    else if (!targets.length) { emoji = "⚫"; title = "fleet status: no launchers assigned"; glow = ""; }
    else if (serving.length === targets.length) { emoji = "🟢"; title = "fleet status: all " + targets.length + " servers running"; glow = "green"; }
    else if (window.__launching) { emoji = "🟡"; title = "fleet status: launching... " + serving.length + "/" + targets.length; glow = "yellow"; }
    else if (serving.length) { emoji = "🟠"; title = "fleet status: " + serving.length + "/" + targets.length + " serving"; glow = ""; }
    else { emoji = "⚫"; title = "fleet status: not running"; glow = ""; }
    dot.textContent = emoji; dot.title = title;
    if (window.__dotGlow !== glow) {
      window.__dotGlow = glow;
      dot.style.filter = "";
      dot.classList.remove("fleet-dot-yellow", "fleet-dot-green", "fleet-dot-red");
      if (glow === "red") dot.classList.add("fleet-dot-red");
      else if (glow === "green") dot.classList.add("fleet-dot-green");
      else if (glow === "yellow") dot.classList.add("fleet-dot-yellow");
    }
  }
  const tb = $("termBtn");
  if (tb) {
    const lit = serving.length > 0;
    if (lit !== !!window.__termLit) {
      window.__termLit = lit;
      if (lit) { tb.classList.remove("fadered"); tb.classList.add("livered"); }
      else {
        tb.classList.remove("livered");
        tb.classList.add("fadered");                 // ease the red away rather than cut it
        setTimeout(function() { tb.classList.remove("fadered"); }, 1200);
      }
    }
  }
  syncTtsButton();
  const lb = $("launchBtn");
  if (lb) {
    let lbs;
    if (window.__terminating) lbs = "term";
    else if (serving.length) lbs = "run";
    else if (window.__launching) lbs = "launching";
    else lbs = "idle";
    // how many came up out of how many were meant to: a server counts as expected once
    // it has a model to load and a provider pointed at it. Worked out every time, since
    // servers answer one after another over several seconds.
    const want = (state.routing || []).filter(function(s) {
      const sl = (state.slots || []).filter(x => x.id === s.id)[0] || {};
      return (sl.params && sl.params.model) && (s.providers || []).length;
    }).length;
    const tally = want ? "  (" + serving.length + "/" + want + ")" : "";
    const moved = window.__lbTally !== tally;
    if (moved && lbs === "run" && serving.length < want) {
      stackAdd(serving.length + " of " + want + " server(s) up");   // still arriving
    }
    window.__lbTally = tally;
    if (window.__lbState !== lbs || (moved && (lbs === "run" || lbs === "launching"))) {
      if (window.__lbState !== lbs) { clearInterval(window.__runArc); window.__runArc = null; }
      const wasState = window.__lbState;
      window.__lbState = lbs;
      if (lbs === "term") { lb.innerHTML = arcLabel("Shutting down..."); }
      else if (lbs === "run") { lb.innerHTML = arcLabel("Running..." + tally); }
      else if (lbs === "launching") { lb.innerHTML = arcLabel("Launching..." + tally); }
      else { lb.innerHTML = arcLabel("Launch LLM"); }
      lb.classList.remove("lbload", "lbrun", "lbbusy");
    if (lbs !== "idle") lb.classList.add("lbbusy");    // not disabled: that kills hover
      if (wasState === lbs && window.__runArc) { /* only the count moved: leave the arcs */ }
      else if (lbs === "launching" || lbs === "term") {
        lb.classList.add("lbload");               // coming up: full strength while it works
        window.__runArc = setInterval(function() {
          if (!lb.isConnected) { clearInterval(window.__runArc); window.__runArc = null; return; }
          arcFire(lb, true);
        }, 130);
      } else if (lbs === "run") {                 // up: keep it crackling, and hold the light
        lb.classList.add("lbrun");
        window.__runArc = setInterval(function() {
          if (!lb.isConnected) { clearInterval(window.__runArc); window.__runArc = null; return; }
          arcFire(lb, false);
        }, 150);
      }
    }
  }
  if (window.__prevServing) {
    serving.forEach(s => {
      if (!window.__prevServing.has(s.id)) stackAdd("✅ " + (s.label || s.id) + " serving on :" + s.port);
    });
    if (serving.length === targets.length && targets.length && !window.__allAnnounced) {
      stackAdd("✅ all servers running (" + targets.length + "/" + targets.length + ") - fleet ready");
      window.__allAnnounced = true;
      window.__launching = false;
    }
  }
  window.__prevServing = new Set(serving.map(s => s.id));
}
let autoRefT = null;
function paintAutoRef(s) {
  const el = $("ref-now");
  if (!el) return;
  el.innerHTML = s > 0 ? ('- <span class="blueglow">' + s + 's</span>') : "";
}
function setAutoRef(v, quiet) {
  if (autoRefT) { clearInterval(autoRefT); autoRefT = null; }
  const s = parseInt(v) || 0;
  paintAutoRef(s);
  if (!quiet) post("/api/settings", { autoRefresh: s });
  if (s > 0) autoRefT = setInterval(() => {
    const busy = uiBusy();
    if (busy) { trace("refresh", "tick skipped", busy); return; }
    trace("refresh", "tick");
    liveRefresh("tick");
  }, s * 1000);
}
function paintProfiles() {
  const hp = $("hdr-prof");
  if (hp) hp.innerHTML = profRow();
}
// clicking anywhere outside the panel retracts it
// every drop-out panel closes through here, so opening one always shuts the others
function closeMenus(keep) {
  // only worth a line when something was actually open: a click anywhere calls this,
  // and logging every one of them buried the useful entries
  const rw = $("refwrap"), bw = $("bgwrap");
  const wasOpen = !!(window.__profOpen || window.__gpuOpen
      || (rw && rw.classList.contains("on")) || (bw && bw.classList.contains("on")));
  if (keep || wasOpen) trace("menu", keep ? ("opening " + keep + ", closing the rest") : "closing all");
  if (keep) uiTipHide();                          // a panel is opening; drop any note
  if (keep !== "prof" && window.__profOpen) { window.__profOpen = false; paintProfiles(); }
  if (keep !== "ref") {
    const w = $("refwrap");
    if (w && w.classList.contains("on")) {
      w.classList.remove("on");
      const ic = w.querySelector(".hdr-ico"); if (ic) ic.classList.remove("on");
    }
  }
  if (keep !== "bg") { const b = $("bgwrap"); if (b) b.classList.remove("on"); }
  if (keep !== "gpu" && window.__gpuOpen) {
    window.__gpuOpen = false;
    if (curTab === "network") renderNetwork();
  }
}
document.addEventListener("pointerdown", function(e) {
  const gb = e.target.closest && e.target.closest(".gstepbtn");
  if (gb) {
    gb.classList.remove("gbtnpulse");
    void gb.getBoundingClientRect();              // restart the animation cleanly
    gb.classList.add("gbtnpulse");
    setTimeout(function() { gb.classList.remove("gbtnpulse"); }, 460);
  }
  const btn = e.target.closest && e.target.closest("button, a.btnlink");
  if (btn && btn.id === "launchBtn" && !btn.disabled) {
    for (let i = 0; i < 6; i++) setTimeout(function() {
      arcFire(btn, true, false); arcFire(btn, true, true);
    }, i * 55);
  }
  if (btn && !btn.disabled) {
    btn.classList.remove("btnpulse");
    void btn.offsetWidth;                          // restart the animation cleanly
    btn.classList.add("btnpulse");
    setTimeout(function() { btn.classList.remove("btnpulse"); }, 420);
  }
  const hit = e.target.closest && e.target.closest("[data-act]");
  const act = hit && hit.dataset.act;
  if (act) trace("you", "pressed " + act);
  if (act === "profToggle") {
    e.preventDefault();
    const want = !window.__profOpen;
    closeMenus("prof");
    window.__profOpen = want;
    paintProfiles();
    return;
  }
  if (act === "gpuToggle") {
    e.preventDefault();
    const want = !window.__gpuOpen;
    closeMenus("gpu");
    window.__gpuOpen = want;
    if (curTab === "network") renderNetwork();
    return;
  }
  if (act === "navBack") { e.preventDefault(); navGo(-1); return; }
  if (act === "navFwd")  { e.preventDefault(); navGo(1); return; }
  if (act === "stackToggle") { e.preventDefault(); stackToggle(); return; }
  if (act === "refToggle") {
    e.preventDefault();
    const w = $("refwrap");
    const want = !!(w && !w.classList.contains("on"));
    closeMenus("ref");
    if (w) { w.classList.toggle("on", want); hit.classList.toggle("on", want); }
    return;
  }
  if (act === "bgToggle") {
    e.preventDefault();
    const w = $("bgwrap");
    const want = !!(w && !w.classList.contains("on"));
    closeMenus("bg");
    if (w) w.classList.toggle("on", want);
    return;
  }
  if (act === "bgPick") {
    e.preventDefault();
    window.__termBlack = hit.dataset.v === "1";
    ["tail-dashboard","tail-thinking","tail-splitd","tail-splitt","tail-tts"].forEach(function(id) {
      const p = $(id); if (p) p.classList.toggle("blackbg", !!window.__termBlack); });
    post("/api/settings", { termBlack: window.__termBlack });
    document.querySelectorAll(".bgopt").forEach(function(b) {
      b.classList.toggle("on", (b.dataset.v === "1") === !!window.__termBlack); });
    const w = $("bgwrap"); if (w) w.classList.remove("on");
    return;
  }
  const inMenu = e.target.closest && e.target.closest(".bgwrap, .gpuwrap, .refwrap, .profwrap");
  if (!inMenu) closeMenus("");
  if (!(e.target.closest && e.target.closest(".tpanel, .adjbtn")))
    document.querySelectorAll(".adjopen").forEach(w => w.classList.remove("adjopen"));
}, true);
async function profSel(sel) {
  window.__profPick = sel.value;
  const n = sel.value;
  if (!n) return;
  const Q = String.fromCharCode(34);
  if (!await uiConfirm("Load profile " + Q + n + Q + "? This overwrites the current Proxy Setup.")) { sel.value = ""; return; }
  const r = await post("/api/profile-load", { name: n });
  recoMsg = r.error ? ("⚠ " + r.error) : ("✅ profile loaded: " + n);
  await load(); renderCurrent(true);
}
async function refreshTail(which) {
  const r = await post("/api/tail", { kind: which });
  if (termInsTtsOn() && TERM_INS_KINDS.indexOf(which) >= 0) {
    try {                                   // the spoken line lives in the other log
      const tr = await post("/api/tail", { kind: "tts" });
      lastTtsTail = (tr && tr.text) || "";
    } catch (e) { /* leave the previous one */ }
  }
  const pre = $("tail-" + which), src = $(which === "dashboard" ? "dash-src" : which === "tts" ? "tts-src" : "think-src");
  if (!pre) return;
  const stick = pre.scrollTop + pre.clientHeight >= pre.scrollHeight - 30;
  paintTail(which, r.text || r.error || "");
  { const t = new Date().toTimeString().slice(0, 8);
    const x = r.file ? ("source: " + r.file + " (live tail, ANSI stripped) - refreshed " + t) : "";
    if (src) { src.textContent = x; src.title = x; } }
  if (stick) pre.scrollTop = pre.scrollHeight;
}

/* ---------- TTS ---------- */
let ttsBusy = "";        // "" | "start" | "stop"
// A ["##", "Title"] row is a section heading with a rule above it, so the page reads as
// groups rather than one long column of fields.
const TTS_FIELDSETS = {
  moss: [
    ["##", "Files"],
    ["ttsServerExe", "TTS Server Binary (moss-tts-server.exe)", [".exe"]],
    ["ttsModel", "TTS Model (.gguf)", [".gguf"]],
    ["ttsPython", "Python Executable (the venv that runs the wrapper)", [".exe"]],
    ["ttsWrapper", "Wrapper Script (.py)", [".py"]],
    ["##", "Voice"],
    ["ttsOutDir", "Saved Audio Folder (blank = a temporary folder)", "folder"],
    ["ttsVoiceDir", "Local Voice Clips (a .wav named after the voicetype replaces the upload)", "folder"],
    ["##", "Ports"],
    ["ttsServerPort", "TTS Server Port", null],
    ["ttsWrapperPort", "Proxy TTS Port (point the SkyrimNet TTS endpoint here)", null]
  ],
  audiocpp: [
    ["##", "Folders & Model"],
    ["ttsAcppDir", "audio.cpp Folder (the panel finds audiocpp_server.exe inside)", "folder"],
    ["ttsAcppModelsDir", "TTS Models Folder (scanned for .gguf and safetensors)", "folder"],
    ["##", "Voice"],
    ["ttsOutDir", "Saved Audio Folder (blank = a temporary folder)", "folder"],
    ["ttsVoiceDir", "Local Voice Clips (a .wav named after the voicetype replaces the upload)", "folder"],
    ["ttsAcppRefSlots", "Cached Voices (how many speakers stay encoded; raise it if you use many)", null],
    ["##", "Ports & Naming"],
    ["ttsServerPort", "Server Port", null],
    ["ttsWrapperPort", "Proxy TTS Port (point the SkyrimNet TTS endpoint here)", null],
    ["ttsAcppModelId", "Model Id (the name used in requests)", null]
  ]
};
function ttsFields() {
  return TTS_FIELDSETS[String((state && state.settings && state.settings.ttsEngine) || "moss")]
      || TTS_FIELDSETS.moss;
}
const TTS_STEPS = [
  ["Get the pieces", "You need <b>moss-tts-server.exe</b> and a MOSS GGUF model. The panel supplies neither - it starts them and talks to them, but it does not ship or download them."],
  ["Set the log folder", "<b>Folder Settings</b> - only the log folder matters here. Everything else on that page belongs to the LLM fleet."],
  ["Point at the binary and the model", "<b>Proxy</b> then <b>TTS</b>. Fill in <b>TTS Server Binary</b> and <b>TTS Model</b>. Paste the paths, use <b>Choose file</b>, or - if you already run a working TTS launcher - press <b>Import from a launcher</b> and it reads them straight out of it."],
  ["Pick the GPU", "Leave it blank and every visible card is offered to the server. Pick one and it is pinned by its UUID, so a reboot or a reseated card cannot move it onto a different GPU."],
  ["Choose who translates", "Set <b>Who translates for SkyrimNet</b> to <b>The panel</b>. It takes the wrapper port straight away and the line underneath says whether that succeeded. If it did not, something else is already on that port - usually a wrapper of your own still running."],
  ["Start the server", "Press <b>Start TTS</b> and wait for <b>ready</b>. The model takes a few seconds to load and the server does not answer until it has, so the button reads <b>Launching</b> in the meantime."],
  ["Point SkyrimNet at the panel", "In SkyrimNet: <b>Voice</b> then <b>Text-to-Speech</b>, engine <b>Zonos</b>, and set the endpoint to this machine on the wrapper port."],
  ["Test it", "Press SkyrimNet's own <b>Test</b> button. The line appears in <b>Proxy</b> then <b>TTS Terminal</b> within a second or two, with its timings."]
];
let curTtsGuide = "higgs";
function showTtsGuide(k) {
  curTtsGuide = k;
  ["higgs", "moss"].forEach(x => {
    const p = $("tgpane-" + x), b = $("tgsub-" + x);
    if (p) p.style.display = x === k ? "" : "none";
    if (b) b.classList.toggle("on", x === k);
  });
}
function renderTtsGuide() {
  const pane = $("ugpane-tts");
  if (!pane) return;
  pane.innerHTML =
      '<div class="subtabs" style="margin-bottom:14px">'
    + '<button id="tgsub-higgs" onclick="showTtsGuide(' + String.fromCharCode(39) + 'higgs'
    + String.fromCharCode(39) + ')">Higgs v3</button>'
    + '<button id="tgsub-moss" onclick="showTtsGuide(' + String.fromCharCode(39) + 'moss'
    + String.fromCharCode(39) + ')">MOSS-TTS</button></div>'
    + '<div id="tgpane-higgs"></div><div id="tgpane-moss" style="display:none"></div>';
  renderHiggsGuide();
  renderMossGuide();
  showTtsGuide(curTtsGuide);
}

function hgStep(n, title, body) {
  return '<div class="card" style="margin-bottom:12px"><div class="row" style="gap:10px;align-items:baseline">'
       + '<b style="font-size:1.15em">' + n + '</b><b>' + title + '</b></div>'
       + '<div class="hint" style="margin-top:8px;line-height:1.75">' + body + '</div></div>';
}
function hgCode(s) {
  return '<div class="gcode" onclick="copyCode(this)" title="click to copy">'
       + '<span class="gcopy">' + ICO.copy + '</span>' + esc(s) + '</div>';
}
function renderHiggsGuide() {
  const pane = $("tgpane-higgs");
  if (!pane) return;
  const BS = String.fromCharCode(92);            // a backslash, built rather than escaped
  const mroot = "C:" + BS + "PandorumLLM" + BS + "Models" + BS + "TTS";
  const root = mroot + BS + "Higgs-v3-4b";
  pane.innerHTML =
      '<div class="card"><div class="row"><b style="font-size:1.25em">Higgs Audio v3 TTS (4B)</b></div>'
    + '<div class="hint" style="margin-top:8px;line-height:1.75">'
    + 'Expressive speech with zero-shot voice cloning, run by <b>audio.cpp</b> - one binary, no '
    + 'python and no virtual environment. The panel starts it, pins it to a card and translates '
    + 'for SkyrimNet, so nothing changes on the SkyrimNet side beyond the endpoint.<br><br>'
    + '<b>Licence:</b> the Higgs weights are research / non-commercial, with a Creator Use Grant '
    + 'for monetised creator content if you credit Boson AI. Cloning a voice without the '
    + 'speaker&#39;s consent is not permitted. audio.cpp itself is Apache-2.0.</div></div>'

    + hgStep("1", "Get audio.cpp - no compiler needed",
        'Download the Windows prebuilt binaries. Take <b>two</b> archives and unzip them into '
        + '<b>the same folder</b>:<br><br>'
        + '&bull; <b>audiocpp-windows-cuda-runtime.zip</b> - the shared CUDA libraries<br>'
        + '&bull; <b>audiocpp-windows-cuda-balance.zip</b> - the AVX2 build, right for almost every PC'
        + hgCode("https://github.com/0xShug0/audio.cpp/releases")
        + 'Needs an NVIDIA card of <b>compute capability 7.5 or newer</b> - that is RTX 20 series '
        + 'and up - and <b>driver 580 or newer</b>. No CUDA Toolkit, no Visual Studio.<br><br>'
        + 'GTX 10 series and older are not covered by these packages; they need a CPU package or a '
        + 'build against an older CUDA Toolkit. Use the <b>portable</b> CPU archive if your processor '
        + 'is old or you are unsure, and <b>fast</b> only on a recent high-end one.')

    + hgStep("2", "Download a model",
        'Two builds are published. Both are a single file - put them in one folder so the panel '
        + 'can list them together.'
        + hgCode('New-Item -ItemType Directory -Force "' + root + '"')
        + '<b>Q8_0 - 5.1 GB - start here.</b> Close to full precision by ear, and the build audio.cpp '
        + 'validated Higgs against.'
        + hgCode('hf download audio-cpp/audio.cpp-gguf '
                 + '--include "Higgs-Audio-v3-TTS-4B-GGUF/higgs-audio-v3-tts-4b-q8_0.gguf" '
                 + '--local-dir "' + root + '"')
        + '<b>BF16 - 8.5 GB - cleaner, heavier.</b> Worth it only if you have VRAM to spare.'
        + hgCode('hf download audio-cpp/audio.cpp-gguf '
                 + '--include "Higgs-Audio-v3-TTS-4B-GGUF/higgs-audio-v3-tts-4b-bf16.gguf" '
                 + '--local-dir "' + root + '"')
        + 'Those are the only two published - there is no smaller quantisation. If <code>hf</code> is '
        + 'not installed, the files can be downloaded from the page directly:'
        + hgCode("https://huggingface.co/audio-cpp/audio.cpp-gguf/tree/main/Higgs-Audio-v3-TTS-4B-GGUF"))

    + hgStep("3", "Point the panel at both",
        'On <b>Proxy &rarr; TTS</b>, set <b>TTS</b> to <b>Higgs Audio v3</b>, then:<br><br>'
        + '&bull; <b>audio.cpp Folder</b> - the folder you unzipped into. The panel finds '
        + '<code>audiocpp_server.exe</code> itself, in that folder or below it.<br>'
        + '&bull; <b>TTS Models Folder</b> - <code>' + esc(mroot) + '</code> '
        + 'or wherever you put the files, then press <b>Rescan</b> and pick a model.<br>'
        + '&bull; <b>GPU</b> - the card to use. Pick one your language models are not on.<br>'
        + '&bull; <b>Proxy TTS Port</b> - what SkyrimNet will talk to; 7860 by default.<br><br>'
        + 'Press <b>Start TTS</b>. The terminal should show one CUDA device, then the model loading, '
        + 'then a line saying it is listening.')

    + hgStep("4", "Point SkyrimNet at the panel",
        'In SkyrimNet, <b>Voice &rarr; Text-to-Speech</b>, endpoint '
        + '<code>http://&lt;this-pc&gt;:7860</code>. Then pick the backend, and there is a real '
        + 'trade-off:<br><br>'
        + '&bull; <b>Zonos</b> - SkyrimNet sends the reference voice at 22050 Hz, so the clone is '
        + 'closer. No audio tags.<br>'
        + '&bull; <b>Chatterbox</b> - 16000 Hz, so a slightly coarser clone, but it is the <b>only</b> '
        + 'backend with audio tags. Pick this if you want emotion and pauses.<br><br>'
        + 'XTTS will not work either way: it speaks its own protocol, not the one the panel serves.')

    + hgStep("5", "Audio tags, if you want them",
        'Higgs acts on tags written into a line - fear, whispering, a pause, a laugh. Getting them '
        + 'there needs <b>three</b> things, and it does nothing with any one missing.<br><br>'
        + '<b>1. Chatterbox as the TTS system,</b> as above. It is the only backend with an audio-tag '
        + 'feature and an allowed list.<br><br>'
        + '<b>2. Turn audio tags on</b> in the Chatterbox settings, and paste the allowed tags into '
        + 'Advanced settings, one per line. Anything not on that list is dropped by SkyrimNet before '
        + 'it reaches the panel.<br><br>'
        + '<b>3. Tell your dialogue model to write them,</b> via a final-instructions prompt.<br><br>'
        + 'Then set <b>Audio Tags</b> on the TTS page to <i>Pass them to the engine</i>. SkyrimNet '
        + 'removes angle brackets and pipes from every line, so the model writes '
        + '<code>[EMOTION-FEAR]</code> and the panel turns that back into what Higgs expects. '
        + 'The panel invents nothing - if your prompt writes no tags, this setting changes nothing.'
        + '<br><br>A worked set of the allowed list and the prompt is published here:'
        + hgCode("https://github.com/cleanestpoison/higgs3-tts-skyrimnet"))

    + hgStep("6", "Getting a good voice",
        '<b>Keep the reference short.</b> Six to ten seconds clones as well as a minute and uses far '
        + 'less memory - a 57 second sample needed 17 GB and failed on a 24 GB card. Longer is not '
        + 'better.<br><br>'
        + '<b>Expect roughly 2-4x faster than real time</b> for a line of dialogue, quicker once the '
        + 'model has warmed up. The first line after starting is always the slowest.<br><br>'
        + '<b>Saved Audio Folder</b> keeps a copy of every line, named after the speaker and the time. '
        + 'The panel never deletes anything from it.')

    + hgStep("?", "When something goes wrong",
        '<b>Nothing happens and the terminal mentions the GPU.</b> The binary has no support for that '
        + 'card. The prebuilt CUDA package covers RTX 20 series and newer.<br><br>'
        + '<b>&quot;missing model file&quot;.</b> Choose the model from the dropdown rather than typing a '
        + 'folder - the panel stores the exact file.<br><br>'
        + '<b>Out of memory.</b> Shorten the reference voice, or use Q8 instead of BF16.<br><br>'
        + '<b>It worked and then stopped.</b> Open the <b>TTS Terminal</b>; the panel reads the '
        + 'server&#39;s own log and says what happened in plain words.');
}

function renderMossGuide() {
  const pane = $("tgpane-moss");
  if (!pane) return;
  const st = (state && state.settings) || {};
  const wp = esc(st.ttsWrapperPort || "7860");
  pane.innerHTML =
      '<div class="banner" style="display:block;margin:0 0 14px;line-height:1.6">'
    + '<b>Experimental, and engine-specific.</b> This page describes the alpha TTS support, '
    + 'which was built and tested against one particular build of MOSS-TTS: '
    + '<code onclick="copyCode(this)" title="click to copy" style="background:#12161d;border:1px solid var(--edge);border-radius:6px;padding:2px 7px;user-select:all;cursor:pointer">https://github.com/sammcj/openmoss</code> '
    + '. The request shape, the response headers and the server flags all follow that build, '
    + 'so a different TTS server will not work here even if it also loads a GGUF.</div>'

    + '<div class="card" style="max-width:900px;line-height:1.65">'
    + '<h2 style="margin:0 0 8px">Why this exists at all</h2>'
    + '<div class="hint" style="line-height:1.65">SkyrimNet speaks to its supported voices directly - '
    + 'Piper, XTTS, Chatterbox, ElevenLabs and the rest need nothing from this page. MOSS-TTS is not one of them. '
    + 'What SkyrimNet does support is <b>Zonos</b>, so something has to sit in the middle and present MOSS-TTS as if it were Zonos. '
    + 'That translator is what the panel can now be.</div></div>'

    + '<div class="card" style="max-width:900px;margin-top:14px">'
    + '<h2 style="margin:0 0 10px">Setting it up from scratch</h2>'
    + TTS_STEPS.map((s, i) =>
        '<div style="display:flex;gap:12px;margin-bottom:14px;align-items:flex-start">'
        + '<div style="flex:none;width:26px;height:26px;border-radius:50%;background:#12161d;'
        + 'border:1px solid var(--edge);display:flex;align-items:center;justify-content:center;'
        + 'color:var(--ok);font-size:12.5px">' + (i + 1) + '</div>'
        + '<div style="flex:1;min-width:0"><div style="color:var(--txt);margin-bottom:2px">' + s[0] + '</div>'
        + '<div class="hint" style="line-height:1.6">' + s[1] + '</div></div></div>').join("")
    + '<div class="hint" style="line-height:1.6;margin-top:4px">Steps 3 to 5 are the only real configuration. '
    + 'There is no launcher to run, no python environment to build and no wrapper to install.</div></div>'

    + '<div class="card" style="max-width:900px;margin-top:14px;line-height:1.65">'
    + '<h2 style="margin:0 0 8px">The two modes</h2>'
    + '<div class="hint" style="line-height:1.65"><b>Your own wrapper</b> - the panel writes a launcher that starts '
    + 'the server and your wrapper together, then reads the log the wrapper produces. Nothing passes through the panel, '
    + 'so voices keep working whether or not it is open. This is the default.<br><br>'
    + '<b>The panel</b> - no separate wrapper at all. The panel answers SkyrimNet on port ' + wp + ' itself and '
    + 'translates for it. Simpler to set up, but voices then depend on the panel running: close it and speech stops.</div></div>'

    + '<div class="card" style="max-width:900px;margin-top:14px;line-height:1.65">'
    + '<h2 style="margin:0 0 8px">When something is wrong</h2>'
    + '<div class="hint" style="line-height:1.65">'
    + '<b>The state never reaches ready.</b> The server did not come up. Its own output is in '
    + '<code>tts-server.log</code>, under <b>Log</b> then <b>Files</b>.<br><br>'
    + '<b>Not listening on the wrapper port.</b> Something else holds it - most often a wrapper of your own '
    + 'still running from a launcher. Stop it and switch the mode again.<br><br>'
    + '<b>A line fails in the TTS terminal.</b> The message carries whatever the TTS server itself said, '
    + 'not just a status code, so read it before changing anything.<br><br>'
    + '<b>SkyrimNet reports a TTS failure but the terminal is empty.</b> SkyrimNet is not reaching the panel at all. '
    + 'Check the endpoint address and that it names this machine on port ' + wp + '.</div></div>';
}

let ttsModels = null;                  // {models,dir,selected} once loaded
let ttsAcppMsg = "";
async function ttsLoadModels(force) {
  if (ttsModels && !force) return ttsModels;
  ttsModels = await post("/api/tts-models", {});
  return ttsModels;
}
// The audio.cpp folder gets what the llama.cpp folder has: a warning when the binary is
// not there, the releases address to copy, and a version check.
// The panel downloading and unpacking executables is the biggest thing it ever
// does for you, so it asks plainly, once, and says exactly what it will fetch.
function higgsInstallRow() {
  const g = (state && state.higgsInstall) || {};
  if (g.running) {
    return '<div class="tsect">Install</div><div class="tgroup" style="border-top:none;padding-top:0;margin-top:0"><div class="row" style="gap:10px;align-items:center">'
         + '<b>Installing Higgs v3</b>'
         + '<button class="stop" data-act="higgsCancel">Stop</button></div>'
         + '<div class="hint" style="margin-top:7px;line-height:1.7">' + esc(g.step || "starting...")
         + '</div><div style="height:6px;border-radius:3px;background:rgba(255,255,255,.07);'
         + 'margin-top:8px;overflow:hidden"><div style="height:100%;width:'
         + (g.pct || 0).toFixed(1) + '%;background:var(--acc);transition:width .3s"></div></div>'
         + '<div class="hint" style="margin-top:6px">Watch the TTS Terminal for the detail. '
         + 'Stopping keeps what has downloaded, so starting again resumes.</div></div>';
  }
  if (g.error) {
    return '<div class="tsect">Install</div><div class="tgroup" style="border-top:none;padding-top:0;margin-top:0"><div class="hint" style="color:#ff5d5d;line-height:1.7">'
         + 'Install ' + esc(g.error) + '</div>'
         + '<div class="hint" style="margin-top:6px;line-height:1.7">Anything already '
         + 'downloaded is kept, so trying again resumes rather than starting over.</div>'
         + '<button class="stop" data-act="higgsInstall" style="margin-top:8px">Try again</button>'
         + '<button class="stop" data-act="higgsDismiss" style="margin-top:8px">Dismiss</button></div>';
  }
  if (g.done) {
    // without this the row falls back to the install button and a finished install
    // looks exactly like one that never ran
    return '<div class="tsect">Install</div><div class="tgroup" style="border-top:none;padding-top:0;margin-top:0"><div class="hint" style="color:var(--ok);line-height:1.7">'
         + '\u2705 Higgs Audio v3 installed' + (g.model ? (' - ' + esc(g.model)) : '') + '.</div>'
         + (g.warn ? '<div class="hint" style="color:var(--warn);margin-top:6px;line-height:1.7">'
                     + esc(g.warn) + '</div>' : '')
         + '<div class="hint" style="margin-top:6px;line-height:1.7">'
         + (g.engine ? ('Engine in <code>' + esc(g.engine) + '</code>. ') : '')
         + 'The fields below are set for you - press <b>Start TTS</b>.</div>'
         + '<button class="stop" data-act="higgsDismiss" style="margin-top:8px">Dismiss</button></div>';
  }
  const f = (state && state.higgsFound) || {};
  // already here AND selected: the button stays, but stop making people wonder
  const done = f.exe && (f.models || []).length && !f.adoptable;
  const badge = done ? ' <span class="mand">Installed</span>' : "";
  if (f.adoptable) {
    // the files are there but the settings are not - a config save failing at the last
    // step of an install did exactly this, and so does installing by hand
    return '<div class="tsect">Install</div><div class="tgroup" style="border-top:none;padding-top:0;margin-top:0"><div class="hint" style="color:var(--ok);line-height:1.7">'
         + '\u2705 Higgs is already installed here, but not selected.</div>'
         + '<div class="hint" style="margin-top:6px;line-height:1.7">Found '
         + '<code>' + esc(f.exe || "") + '</code> and ' + (f.models || []).length
         + ' model file(s).</div>'
         + '<button class="stop" data-act="higgsAdopt" style="margin-top:8px">Use it</button>'
         + '<button class="stop" data-act="higgsInstall" style="margin-top:8px">Reinstall</button></div>';
  }
  return '<div class="tsect">Install</div><div class="tgroup" style="border-top:none;padding-top:0;margin-top:0"><div class="row" style="gap:10px;align-items:center;flex-wrap:wrap">'
       + '<button class="stop bigbtn" data-act="higgsInstall">Install Higgs v3</button>' + badge
       + '<span class="hint" style="width:auto">1 click install into the PandorumLLM '
       + 'directory</span></div></div>';
}

async function higgsInstall() {
  const ok = await uiConfirm(
      "Install Higgs Audio v3 TTS into PandorumLLM?" + String.fromCharCode(10) + String.fromCharCode(10)
    + "The panel will download, into its own folder:" + String.fromCharCode(10)
    + "  \u2022 the audio.cpp engine (about 60 MB) from github.com/0xShug0/audio.cpp" + String.fromCharCode(10)
    + "  \u2022 the Higgs v3 4B model, Q8 (about 5.1 GB) from huggingface.co/audio-cpp" + String.fromCharCode(10) + String.fromCharCode(10)
    + "It will unpack them, then select them on this page. Nothing about your setup "
    + "is sent anywhere - these are two ordinary downloads." + String.fromCharCode(10) + String.fromCharCode(10)
    + "You need an NVIDIA card of compute capability 7.5 or newer (RTX 20 series and "
    + "up) on driver 580 or newer, and about 8 GB free. No CUDA toolkit needed." + String.fromCharCode(10) + String.fromCharCode(10)
    + "Progress appears in the TTS Terminal. Continue?");
  if (!ok) return;
  await post("/api/higgs-install", { confirm: true });
  showTsub("tts");                        // the install narrates itself there
  await load(); renderTts();
}
async function higgsCancel() {
  if (!await uiConfirm("Stop the download? A part-finished file is kept, so starting "
                       + "again resumes rather than restarting.")) return;
  await post("/api/higgs-install", { action: "cancel" });
}

function ttsFieldExtra(k) {
  if (k !== "ttsAcppDir") return "";
  return '<div class="hint chkmsg" id="acppchk" style="color:var(--err);display:none">'
       + 'audiocpp_server.exe not found in this folder or below it</div>'
       + '<div class="hint" style="margin-top:8px;line-height:1.6">'
       + 'Prebuilt binaries and newer releases are here (click to copy):'
       + '<div style="margin-top:5px;display:flex;gap:8px;align-items:center;flex-wrap:wrap">'
       + '<code class="gcode" style="margin:0;padding:5px 30px 5px 10px" onclick="copyCode(this)" '
       + 'title="click to copy"><span class="gcopy">' + ICO.copy + '</span>'
       + 'https://github.com/0xShug0/audio.cpp/releases</code>'
       + '<button class="stop" data-act="acppCheck" title="asks github.com for the newest '
       + 'audio.cpp release - only when you press it, and nothing about your setup is sent">'
       + 'Check for update</button></div>'
       + '<div class="hint" id="tts-acpp" style="margin-top:6px;min-height:1.2em">'
       + ttsAcppMsg + '</div></div>';
}
async function recheckAcpp() {
  const inp = $("tts-ttsAcppDir"), msg = $("acppchk");
  if (!inp || !msg) return;
  const v = inp.value.trim();
  if (!v) { msg.style.display = "none"; return; }
  const r = await post("/api/path-check", { path: v, kind: "ttsAcppDir" });
  msg.style.display = (r && r.ok) ? "none" : "block";
  if (r && r.ok && r.exe) { msg.style.display = "none"; }
}

function ttsModelOptions() {
  const st = (state && state.settings) || {};
  const sel = st.ttsAcppModel || "";
  const list = (ttsModels && ttsModels.models) || [];
  if (!list.length) return '<option value="">(set a models folder above, then Rescan)</option>';
  return '<option value="">(none selected)</option>' + list.map(m =>
      '<option value="' + esc(m.path) + '"' + (m.path === sel ? " selected" : "")
      + (m.shadowed ? " disabled" : "") + '>' + esc(m.name)
      + (m.shadowed ? "  - unavailable, a .gguf here loads instead" : "") + '</option>').join("");
}
function ttsModelHint() {
  const list = (ttsModels && ttsModels.models) || [];
  if (!ttsModels) return "not scanned yet - press Rescan";
  if (!list.length) return "nothing loadable found. audio.cpp takes a .gguf file, or a folder holding config.json and model.safetensors";
  const sh = list.filter(m => m.shadowed).length;
  return list.length + " found" + (sh ? ("  -  " + sh + " safetensors folder(s) hidden because a .gguf sits alongside and wins") : "");
}

function renderTts() {
  const pane = $("dpane-tts");
  if (!pane || !state) return;
  const st = state.settings || {};
  const mode = String(st.ttsWrapMode || "off").toLowerCase();
  const ping = String(st.ttsAnswerPing || "on").toLowerCase();
  const tags = String(st.ttsTags || "off").toLowerCase();
  const w = state.ttsWrap || {};
  const eng = String(st.ttsEngine || "moss").toLowerCase();
  if (eng === "audiocpp" && ttsModels === null) ttsLoadModels(false).then(() => renderTts());
  if (eng === "audiocpp") setTimeout(recheckAcpp, 0);       // after the pane exists
  const sv = state.ttsServer || {};
  const svUp = sv.state === "serving", svLoad = sv.state === "loading";
  const svGoing = !!sv.stopping || sv.state === "wedged";   // reported, or port held and silent
  const busy = ttsBusy;
  const ready = svUp && !busy && (mode === "on" ? w.on : true);
  const keep = {};                       // never wipe a path mid-paste (same rule as Folder Settings)
  ttsFields().forEach(f => { const el = $("tts-" + f[0]); if (el) keep[f[0]] = el.value; });
  const gsel = (state.gpus || []).map(g =>
      '<option value="' + esc(g.id) + '"' + (st.ttsGpuId === g.id ? " selected" : "") + '>'
      + esc((g.name || g.id) + "   " + (g.uuid || "")) + '</option>').join("");
  pane.innerHTML = '<div class="card set" style="max-width:860px">'
    // Choose the TTS, not the engine: the engine follows from it. Kept keyed on the
    // engine value so no existing config needs migrating - a second TTS on the same
    // engine would add an option here rather than a new setting.
    + '<div class="tsect">TTS</div><div class="row" style="flex-wrap:nowrap">'
    + '<select class="txt" id="tts-ttsEngine" data-act="ttsEngineSel">'
    + '<option value="audiocpp"' + (eng === "audiocpp" ? " selected" : "") + '>Higgs Audio v3 (4B) - runs on audio.cpp</option>'
    + '<option value="moss"' + (eng === "moss" ? " selected" : "") + '>MOSS-TTS Local - runs on the MOSS server</option>'
    + '</select></div>'
    + '<div class="hint" style="margin:-4px 0 14px;line-height:1.6">'
    + (eng === "audiocpp"
        ? ''
        : '')
    + '</div>'
    + (eng === "audiocpp" ? higgsInstallRow() : '')
    + (eng === "moss"
        ? ('<div class="row" style="gap:8px;margin-bottom:14px;align-items:center">'
           + '<button class="stop" data-act="ttsImport" title="read the paths straight out of a launcher you already use - nothing else is read from the file">'
    + ICO.file + ' Import from a launcher</button>'
    + '<span class="hint" id="tts-imp" style="width:auto">points at your existing .bat and fills these in</span></div>')
        : '')
    + ttsFields().map(f =>
        f[0] === "##"
          ? '<div class="tsect">' + esc(f[1]) + '</div>'
          : '<label>' + esc(f[1]) + '</label><div class="row" style="flex-wrap:nowrap">'
            + '<input class="txt" id="tts-' + f[0] + '" onchange="saveTts()" value="'
            + esc(st[f[0]] || "").replace(/"/g, "&quot;") + '">'
            + (f[2] === "folder"
                 ? '<button class="stop" data-act="ttsPickDir" data-k="' + f[0] + '">Choose folder</button>'
                 : (f[2] ? '<button class="stop" data-act="ttsPick" data-k="' + f[0] + '">Choose file</button>' : ''))
            + '</div>' + ttsFieldExtra(f[0])).join("")
    + '<label>Who translates for SkyrimNet</label><div class="row" style="flex-wrap:nowrap">'
    + '<select class="txt" id="tts-ttsWrapMode" onchange="saveTtsMode()">'
    + '<option value="off"' + (mode === "on" ? "" : " selected") + '>Your own wrapper (the panel only writes the launcher)</option>'
    + '<option value="on"' + (mode === "on" ? " selected" : "") + '>The panel (no separate wrapper process)</option>'
    + '</select></div>'
    + '<div class="hint" style="margin:-4px 0 12px;line-height:1.6">'
    + (mode === "on"
        ? (w.on ? '<span style="color:var(--ok)">Listening on ' + esc(String(w.port)) + '.</span>'
                : '<span style="color:var(--err)">Not listening - the port may be in use.</span>')
        : '')
    + '</div>'
    + '<label>Answer SkyrimNet startup ping locally</label><div class="row" style="flex-wrap:nowrap">'
    + '<select class="txt" id="tts-ttsAnswerPing" onchange="saveTts()">'
    + '<option value="on"' + (ping === "off" ? "" : " selected") + '>Yes - return silence, never touch the GPU</option>'
    + '<option value="off"' + (ping === "off" ? " selected" : "") + '>No - generate it like any other line</option>'
    + '</select></div>'
    + '<div class="tsect">Audio Tags</div><div class="row" style="flex-wrap:nowrap">'
    + '<select class="txt" id="tts-ttsTags" onchange="saveTts()">'
    + '<option value="off"' + (tags === "on" ? "" : " selected") + '>Strip them - speak the words only</option>'
    + '<option value="on"' + (tags === "on" ? " selected" : "") + '>Pass them to the engine</option>'
    + '</select></div>'
    + (eng === "audiocpp"
        ? ('<label>Model</label><div class="row" style="flex-wrap:nowrap">'
           + '<select class="txt" id="tts-ttsAcppModel" data-act="ttsModelSel">'
           + ttsModelOptions() + '</select>'
           + '<button class="stop" data-act="ttsModelRescan" title="rescan the models folder">Rescan</button></div>'
           + '<div class="hint" id="tts-mdl" style="margin:-4px 0 12px;line-height:1.6">'
           + ttsModelHint() + '</div>')
        : '')
    + '<label>GPU (pinned by UUID, so a reboot cannot move it)</label>'
    + '<div class="row" style="flex-wrap:nowrap"><select class="txt" id="tts-ttsGpuId" onchange="saveTts()">'
    + '<option value="">(no pin - every visible card is offered)</option>' + gsel + '</select></div>'
    + (mode === "on"
        ? ('<div class="card" style="margin:4px 0 16px;padding:14px 16px">'
           + '<div class="row" style="gap:10px;align-items:center">'
           + '<button data-act="ttsStart"' + (busy || svUp || svLoad || svGoing ? " disabled" : "")
           + ' title="start the TTS server; the panel is already answering SkyrimNet">'
           + (busy === "start" ? "Launching\u2026" : svLoad ? "Loading the model\u2026" : "\u25B6 Start TTS")
           + '</button>'
           + '<button class="stop" data-act="ttsStop"'
           // enabled while starting too: a model that takes minutes to load, or one that
           // is never going to answer, is precisely when you want to stop it
           + (busy === "stop" || svGoing || !(svUp || svLoad || busy === "start") ? " disabled" : "")
           + ' title="stop the TTS server">' + (busy === "stop" ? "Stopping\u2026" : "\u25A0 Stop") + '</button>'
           + '<span class="pill ' + (ready ? "serving" : (busy || svLoad || svGoing) ? "loading" : "down") + '">'
           + (ready ? "ready" : busy === "start" ? "starting" : busy === "stop" ? "shutting down"
              : svGoing ? "shutting down" : svLoad ? "model loading" : "stopped") + '</span>'
           + '<span class="hint" id="tts-run" style="width:auto">'
           + (sv.died
               ? '<span style="color:#ff5d5d">' + esc(sv.died) + '</span>'
               : busy === "start"
               ? "started the server - waiting for it to answer on " + esc(String(sv.port || ""))
                 + " (the model takes a moment to load)"
               : busy === "stop" ? "shutting the server down\u2026"
               : ('server ' + (svUp ? "up" : svLoad ? "loading" : svGoing ? "shutting down" : "down") + ' on ' + esc(String(sv.port || ""))
                  + ' \u00B7 panel ' + (w.on ? "answering on " + esc(String(w.port)) : "not listening")))
           + '</span></div></div>')
        : '')
    + (eng === "moss"
        ? ('<div class="row" style="gap:8px;margin-top:16px;align-items:center">'
           + '<button class="stop" data-act="ttsGen" title="build the launcher from these settings without writing it">Preview launcher</button>'
    + '<button class="stop" data-act="ttsSave" title="write start-tts.bat into the launcher folder">Write start-tts.bat</button>'
    + '<button class="stop" data-act="ttsOpenDir" title="show the launcher folder this is written to">'
    + ICO.folder + ' Open launcher folder</button>'
    + '<span class="hint" id="tts-msg" style="width:auto"></span></div>'
           + '<textarea id="tts-view" class="edit" spellcheck="false" readonly style="width:100%;height:42vh;'
           + 'margin-top:10px;font-family:Consolas,monospace;font-size:12.5px;line-height:1.5;white-space:pre;overflow:auto"></textarea>')
        : '')
    + '</div>';
  ttsFields().forEach(f => { const el = $("tts-" + f[0]); if (el && keep[f[0]] !== undefined) el.value = keep[f[0]]; });
}
async function saveTtsMode() { saveTts(); await load(); renderTts(); }
function saveTts() {
  const body = {};
  ttsFields().forEach(f => { const el = $("tts-" + f[0]); if (el) body[f[0]] = el.value; });
  const tg = $("tts-ttsTags"); if (tg) body.ttsTags = tg.value;   // not a path field
  const g = $("tts-ttsGpuId");
  if (g) body.ttsGpuId = g.value;
  ["ttsWrapMode", "ttsAnswerPing"].forEach(k => { const e = $("tts-" + k); if (e) body[k] = e.value; });
  post("/api/settings", body);
}
async function ttsServer(action) {
  if (ttsBusy) return;                     // one press at a time
  ttsBusy = action;
  renderTts();                             // disable and relabel before the request goes out
  try {
    const r = await post("/api/tts-server", { action: action });
    if (r && r.error) {
      ttsBusy = ""; renderTts();
      const m = $("tts-run"); if (m) m.textContent = r.error;
      return;
    }
    if (action === "stop") { await load(); return; }
    // the server does not bind until the model is loaded, so "down" right after the
    // start is normal - keep looking rather than reporting failure
    for (let i = 0; i < 90; i++) {
      await new Promise(z => setTimeout(z, 2000));
      await load();
      const s = (state && state.ttsServer) || {};
      if (s.state === "serving") return;
      if (curTab === "dashboard" && curDsub === "tts") renderTts();
    }
    const m = $("tts-run");
    if (m) m.textContent = "the server did not answer within 3 minutes - check tts-server.log";
  } finally {
    ttsBusy = "";
    if (curTab === "dashboard" && curDsub === "tts") renderTts();
  }
}
async function ttsLauncher(save) {
  saveTts();                                    // generate from what is on screen, not last save
  const r = await post("/api/tts-launcher", { save: !!save });
  const v = $("tts-view"), m = $("tts-msg");
  if (!v) return;
  if (r.error) { v.value = r.error; if (m) m.textContent = ""; return; }
  v.value = r.content || "";
  let msg = r.path ? ("written: " + r.path) : "preview only - nothing written yet";
  if ((r.missing || []).length) msg += "   still empty: " + r.missing.join(", ");
  if (m) m.textContent = msg;
}

/* ---------- dashboard sub-tabs + SN routing editor ---------- */
let curDsub = "term";
let curTsub = "proxy";
function showDsub(s) {
  if ((s === "setup" || s === "yaml") && state && state.scope === "remote") s = "term";
  curDsub = s;
  ["term","setup","yaml"].forEach(x => {
    const p = $("dpane-"+x), b = $("dsub-"+x);
    if (p) p.style.display = x === s ? "" : "none";
    if (b) b.classList.toggle("on", x === s);
  });
  if (s === "term") showTsub(curTsub);
  if (s === "setup") renderRouting();
  if (s === "yaml") { renderYaml(); loadYamlData(); }
  if (s === "tts") renderTts();
}
function showTsub(v) {
  curTsub = v;
  ["proxy","think","split","tts"].forEach(x => {
    const p = $("tpane-"+x), b = $("tsub-"+x);
    if (p) p.style.display = x === v ? "" : "none";
    if (b) b.classList.toggle("on", x === v);
  });
  syncTermScaleUI();
  refreshCurTerm();
}
// The ONE mapping from the open terminal to its feed. showTsub (on open) and
// liveRefresh (every tick) both call this - do not spell it out anywhere else.
function refreshCurTerm() {
  syncTermToggleUI();          // shared markup: the lit state is applied, not rendered
  if (curTsub === "proxy") refreshTail("dashboard");
  else if (curTsub === "think") refreshTail("thinking");
  else if (curTsub === "split") refreshSplit();
  else if (curTsub === "tts") refreshTail("tts");
}
const SPLIT_FEEDS = [["dashboard", "Proxy"], ["thinking", "Thinking Content"],
                     ["tts", "TTS"]];
function splitFeed(side) {
  const st = (state && state.settings) || {};
  const want = String(st[side === "d" ? "splitSrcD" : "splitSrcT"]
                      || (side === "d" ? "dashboard" : "thinking")).toLowerCase();
  return SPLIT_FEEDS.some(f => f[0] === want) ? want
                                              : (side === "d" ? "dashboard" : "thinking");
}
function splitFeedOptions(side) {
  const cur = splitFeed(side);
  return SPLIT_FEEDS.map(f => '<option value="' + f[0] + '"'
      + (f[0] === cur ? " selected" : "") + '>' + esc(f[1]) + '</option>').join("");
}
// Insert TTS only belongs on a pane showing the proxy - it had been put on both
function syncSplitUI() {
  ["d", "t"].forEach(side => {
    const sel = $("splitsel-" + side);
    if (sel) sel.innerHTML = splitFeedOptions(side);
    // the right pane has a second copy in the outer bar for full window
    [$("splitins-" + side), side === "t" ? $("splitins-t-max") : null].forEach(btn => {
      if (btn) btn.style.display = (splitFeed(side) === "dashboard") ? "" : "none";
    });
  });
}
async function setSplitFeed(side, kind) {
  const key = side === "d" ? "splitSrcD" : "splitSrcT";
  if (state && state.settings) state.settings[key] = kind;
  const body = {}; body[key] = kind;
  await post("/api/settings", body);
  await load();
  syncSplitUI();
  refreshSplit();
}
async function refreshSplit() {
  syncSplitUI();
  const kd = splitFeed("d"), kt = splitFeed("t");
  const d = await post("/api/tail", { kind: kd });
  const th = await post("/api/tail", { kind: kt });
  if (termInsTtsOn() && (kd === "dashboard" || kt === "dashboard")) {
    try {
      const tr = await post("/api/tail", { kind: "tts" });
      lastTtsTail = (tr && tr.text) || "";
    } catch (e) { /* keep the previous one */ }
  }
  paintTail(kd, d.text || d.error || "", $("tail-splitd"), "splitd");
  paintTail(kt, th.text || th.error || "", $("tail-splitt"), "splitt");
  const sd = $("split-src-d"), st = $("split-src-t");
  if (sd) { const x = d.file ? "source: " + d.file : ""; sd.textContent = x; sd.title = x; }
  if (st) { const x = th.file ? "source: " + th.file : ""; st.textContent = x; st.title = x; }
}
function provCard(p, s) {
  const emos = ["","💬","🎲","⚔️","🧪","🌐","🤖","🏃","🎭","✍️","🧠","👁️","🛰️","🔧","🗡️","🛡️","📜","🔮","🐉","🏰","🎵","⭐","🔥","⚡"];
  const cur = p.emoji || "";
  let eopts = emos.map(e => '<option value="'+e+'"'+(e===cur?" selected":"")+'>'+(e||"(none)")+'</option>').join("");
  if (cur && emos.indexOf(cur) < 0) eopts = '<option value="'+esc(cur)+'" selected>'+esc(cur)+'</option>' + eopts;
  const pv = (p.priority === 0 || p.priority === 2) ? p.priority : 1;
  const prio = [0,1,2].map(n => '<option value="'+n+'"'+(n===pv?" selected":"")+'>'+n+" - "+["High","Normal","Low"][n]+'</option>').join("");
  const st = p.stats ? ' <span class="chip">reqs '+p.stats.n+' &middot; '+esc(p.stats.last)+'</span>' : "";
  const src = (p.samplerSource || "server");
  return '<div class="prov" data-pid="'+p.id+'" id="prov-'+p.id+'" style="border-left:3px solid '+dashColor(p.title||p.id)+';border-radius:6px'+'">'
    + '<select class="edit" style="width:62px;min-width:62px;padding:7px 22px 7px 8px;background-position:right 6px center" title="emoji (shown in dashboard + thinking logs)" data-act="provField" data-field="emoji" data-id="'+p.id+'">'+eopts+'</select>'
    + '<input class="edit" style="max-width:150px" value="'+esc(p.title).replace(/"/g,"&quot;")+'" data-act="provField" data-field="title" data-id="'+p.id+'">'
    + '<input class="edit" style="max-width:68px" value="'+esc(p.port)+'" title="SN provider port (4 digits)" data-act="provField" data-field="port" data-id="'+p.id+'">'
    + '<select class="edit" style="width:auto;min-width:0;max-width:118px" title="priority - per GPU: 0 makes lower tiers on the SAME GPU wait (max 8s)" data-act="provField" data-field="priority" data-id="'+p.id+'">'+prio+'</select>'
    + '<select class="edit" style="width:auto;min-width:0;max-width:138px" title="which side decides the sampler values actually sent to the model" data-act="provField" data-field="samplerSource" data-id="'+p.id+'">'
    + '<option value="server"'+(src==="server"?" selected":"")+'>Server Side</option>'
    + '<option value="skyrimnet"'+(src==="skyrimnet"?" selected":"")+'>SkyrimNet Side</option></select>'
    + swToggle(p.thinking, 'data-act="provField" data-field="thinking" data-id="'+p.id+'"', "Thinking")
    + swToggle(p.detectSN, 'data-act="provField" data-field="detectSN" data-id="'+p.id+'" title="show the value SkyrimNet sends in brackets beside each set value"', "Show SkyrimNet sampler values")
    + (p.thinking && s.reasoning === "off" ? '<span title="this server was launched with reasoning OFF - the thinking toggle cannot engage until the launcher enables --reasoning" style="color:var(--warn);cursor:help">⚠</span>' : "")
    + (p.thinking && p.diaryGrammar ? '<span title="grammar rail active (GBNF) - the grammar constrains output from the first token, so thinking cannot appear on this provider even when enabled" style="color:var(--warn);cursor:help">🧩</span>' : "")
    + st
    + (p.custom ? '<button class="x" title="remove this added provider" data-act="provDel" data-id="'+p.id+'">&#10005;</button>' : '')
    + '<button class="provpow' + (p.enabled === false ? ' off' : '') + '" data-act="provPower" data-id="'+p.id+'"'
        + ' title="Provider state - ' + (p.enabled === false ? 'Disabled' : 'Enabled') + '">&#9211;</button>'
    + '<div class="row" style="flex-basis:100%;gap:6px;margin-top:4px;align-items:center">' + provSampChips(p)
    + (Object.keys(p.samplerOverrides || {}).length
        ? ' <button class="stop" style="padding:4px 10px;font-size:11.5px" data-act="provSampRevert" data-id="'+p.id+'" title="clear all forced overrides for this provider - each param falls back to whatever SkyrimNet / the server sends">\u21BA Revert Params</button>'
        : '')
    + '</div></div>';
}
const PSAMP_EMO = { temp: "🌡️", top_p: "🎯", min_p: "🧹", top_k: "🔢", n_sigma: "📊", typ_p: "🎲", xtc_p: "✂", xtc_t: "📏", dry: "🚱", freq: "🔁", pres: "👤" };
function provSampChips(p) {
  const obs = p.obsSamplers || {};       // what SkyrimNet actually sent for THIS provider (proxy-observed)
  const srv = p.srvSamplers || {};       // what the server itself is using, read from its log
  const ov = p.samplerOverrides || {};   // the values set here, which are what gets sent
  const snSide = (p.samplerSource || "server") === "skyrimnet";
  const detect = !!p.detectSN;
  return ["temp","top_p","min_p","top_k","n_sigma","typ_p","xtc_p","xtc_t","dry","freq","pres"].map(k => {
    const set = ov[k] !== undefined && ov[k] !== "";
    const seen = obs[k] !== undefined;
    // not in the request means the server decides it - show what the server reports
    const fromSrv = !seen && srv[k] !== undefined && srv[k] !== "";
    // on Server Side the value set here is what the model receives; on SkyrimNet Side
    // the incoming value wins and anything set here is only kept for later
    const v = snSide ? (seen ? obs[k] : (fromSrv ? srv[k] : "-"))
                     : (set ? ov[k] : (seen ? obs[k] : (fromSrv ? srv[k] : "-")));
    const forced = set && !snSide;
    // the server's own value is shown quieter than one that came in on the request
    const col = forced ? "var(--acc)" : (seen ? "var(--ok)" : (fromSrv ? "var(--txt)" : "var(--dim)"));
    const bracket = (detect && seen && !snSide) ? " (" + esc(obs[k]) + ")" : "";
    const tip = snSide
      ? "Sampler Source is SkyrimNet Side, so whatever SkyrimNet sends for " + k + " is used. Set a value here and switch to Server Side to send it instead."
      : set
        ? k + " = " + ov[k] + " is sent to the model on every request for " + esc(p.title)
            + (seen ? " (SkyrimNet last sent " + obs[k] + ")" : "") + "; click to change, empty to clear"
        : "nothing set - SkyrimNet's own " + k + " passes through"
            + (seen ? " (last sent " + obs[k] + ")" : "") + "; click to set a value";
    return '<span class="chip clickable sampchip" style="color:' + col + ';--sgl:' + col + (forced ? ';font-weight:700' : '') + '" '
      + 'title="' + tip + '" data-act="provSampChip" data-id="' + p.id + '" data-key="' + k + '" '
      + 'data-cur="' + (set ? esc(ov[k]) : "") + '">'
      + PSAMP_EMO[k] + " " + k + " " + esc(v) + bracket + '</span>';
  }).join("");
}
const SAMP_EMO = { temp: "🌡️", top_p: "🎯", min_p: "🧹", top_k: "🔢", n_sigma: "📊", typ_p: "🎲", xtc_p: "✂", xtc_t: "📏", dry: "🚱", freq: "🔁", pres: "👤" };


function sampEdit(el) {
  if (el.dataset.has !== "1") return;
  const inp = document.createElement("input");
  inp.className = "edit"; inp.style.maxWidth = "84px";
  inp.value = el.dataset.cur;
  const slot = el.dataset.slot, key = el.dataset.key;
  el.replaceWith(inp); inp.focus(); inp.select();
  let done = false;
  const commit = async () => {
    if (done) return; done = true;
    const r = await post("/api/sampler-edit", { slot: slot, key: key, value: inp.value.trim() });
    if (r.error) { uiAlert(r.error); await load(); renderCurrent(true); return; }
    await load();
    renderCurrent(true);                              // the chip returns with the new value on it
  };
  inp.addEventListener("keydown", e => {
    if (e.key === "Enter") commit();
    if (e.key === "Escape") { done = true; load().then(renderCurrent); }
  });
  inp.addEventListener("blur", commit);
}
function provSampEdit(el) {
  const id = el.dataset.id, key = el.dataset.key;
  const inp = document.createElement("input");
  inp.className = "edit"; inp.style.maxWidth = "84px";
  inp.value = el.dataset.cur;
  inp.placeholder = "empty = clear";
  el.replaceWith(inp); inp.focus(); inp.select();
  let done = false;
  const commit = async () => {
    if (done) return; done = true;
    const r = await post("/api/provider-sampler", { id: id, key: key, value: inp.value.trim() });
    if (r.error) { netLog("could not set " + key + ": " + r.error); await load(); renderCurrent(true); return; }
    await load();
    renderCurrent(true);                              // always restores the chip row
  };
  inp.addEventListener("keydown", e => {
    if (e.key === "Enter") commit();
    if (e.key === "Escape") { done = true; renderCurrent(true); }
  });
  inp.addEventListener("blur", commit);
}
function gpusCard() {
  const rows = (state.gpus||[]).map(g =>
    '<div class="row'+(g.enabled===false?" off":"")+'" style="margin:4px 0">'
    + '<span class="gputog">'
    + swToggle(g.enabled !== false, 'data-act="gpuSwitch" data-id="'+g.id+'"'
        + ' title="' + (g.enabled === false ? "disabled - servers cannot be allocated to it" : "enabled") + '"')
    + '</span>'
    + '<span class="chip">#'+esc(g.index??"?")+'</span>'
    + (g.brand ? '<span class="chip">'+esc(g.brand)+'</span>' : "")
    + '<b>'+esc(g.name||"GPU")+'</b>'
    + '<span class="hint">'+esc(g.mem||"")+'</span>'
    + '<span class="hint uuid" data-act="revealUuid" title="click to reveal">'+esc(g.uuid||"")+'</span>'
    + '</div>').join("")
    || '<div class="hint" style="margin-top:6px">no GPUs on record - hit Detect (needs nvidia-smi on PATH)</div>';
  const open = !!window.__gpuOpen;
  return '<div class="card" id="card-gpus"><div class="row"><span class="gpuwrap">'
    + '<span class="label hdg gputitle' + (open ? " on" : "") + '" data-act="gpuToggle" role="button" tabindex="0"'
    + ' title="show or hide the graphics cards on this PC"><svg viewBox="0 0 24 14" fill="none" stroke="currentColor" stroke-width="1.15"><path d="M0.4 0.7h1.4v12.6" stroke-linecap="round"/><rect x="3.4" y="1.7" width="19" height="9.2" rx="1.2"/><circle cx="8.2" cy="6.3" r="2.4"/><circle cx="13.4" cy="6.3" r="2.4"/><circle cx="18.6" cy="6.3" r="2.4"/><path d="M6.2 10.9v1.7h7.2v-1.7"/></svg><span>PC GPUs</span></span>'
    + (open
        ? '<span class="gpupop" id="gpupop">'
          + '<div class="row" style="margin-bottom:8px"><button class="stop" data-act="detectGpus">Detect GPUs</button></div>'
          + rows + '</span>'
        : '')
    + '</span></div></div>';
}
function yamlCard() {
  const st = state.settings || {};
  return '<div class="card" id="card-yaml"><div class="row"><span class="label">📄 Yaml File Handler</span>'
    + '<button class="stop" data-act="yamlOpenNative">📂 Open yaml folder</button>'
    + '</div>'
    + '<div class="row" style="margin-top:10px">'
    + '<input type="file" id="yaml-file" accept=".yaml,.yml" style="display:none">'
    + '<button class="stop" data-act="yamlPick">📥 Add providers.yaml</button>'
    + '<button class="stop" data-act="yamlGen">🧬 Generate providers.yaml</button>' 
    + '<button class="stop" data-act="yamlCreate">💾 Create providers.yaml file</button>'
    + '</div>'
    + '<pre class="log resizable" id="yaml-log" style="margin-top:8px"></pre>'
    + '<div class="hint" style="margin-top:8px;line-height:1.6">'
    + 'Builds the PandorumLLM providers for SkyrimNet. Every provider password is '
    + '<span class="bluetag">1234</span>.<br>'
    + 'Base: ' + esc(st.yamlBase || "builtin default (a fresh SkyrimNet skeleton)") + '. '
    + '<b>Add</b> reads your current Providers.yaml so the PandorumLLM entries are appended below it. '
    + '<b>Create</b> writes Providers.yaml to the output folder set in [Folder Settings].<br>'
    + 'It belongs at <span class="bluetag">&lt;modlist&gt;&#92;overwrite&#92;SKSE&#92;Plugins'
    + '&#92;SkyrimNet&#92;config&#92;Providers.yaml</span>'
    + '</div></div>';
}
/* ---------- SkyrimNet YAML editor (VS Code style) ---------- */
let yamlData = null, yamlDataLoading = false;
async function loadYamlData() {
  if (yamlDataLoading) return;
  yamlDataLoading = true;
  try { yamlData = await post("/api/yaml-get", {}); }
  catch (e) { yamlData = { error: "could not load SkyrimNet YAML" }; }
  yamlDataLoading = false;
  if (curTab === "dashboard" && curDsub === "yaml") renderYaml();
}
function yamlHi(text) {
  const NL = String.fromCharCode(10);
  return String(text == null ? "" : text).split(NL).map(yamlHiLine).join(NL);
}
function yamlHiLine(line) {
  const DQ = String.fromCharCode(34), SQ = String.fromCharCode(39);
  let i = 0; while (i < line.length && line.charAt(i) === " ") i++;
  let out = line.slice(0, i);
  let rest = line.slice(i);
  if (rest.charAt(0) === "-" && (rest.length === 1 || rest.charAt(1) === " ")) {
    out += '<span class="vt-punct">-</span>';
    rest = rest.slice(1);
    if (rest.charAt(0) === " ") { out += " "; rest = rest.slice(1); }
  }
  if (rest.charAt(0) === "#") return out + '<span class="vt-com">' + esc(rest) + '</span>';
  let ci = -1, q = "";
  for (let j = 0; j < rest.length; j++) {
    const c = rest.charAt(j);
    if (q) { if (c === q) q = ""; continue; }
    if (c === DQ || c === SQ) { q = c; continue; }
    if (c === ":" && (j + 1 >= rest.length || rest.charAt(j + 1) === " ")) { ci = j; break; }
  }
  if (ci >= 0) {
    out += '<span class="vt-key">' + esc(rest.slice(0, ci)) + '</span><span class="vt-punct">:</span>';
    out += yamlHiValue(rest.slice(ci + 1));
    return out;
  }
  return out + yamlHiValue(rest);
}
function yamlHiValue(v) {
  const DQ = String.fromCharCode(34), SQ = String.fromCharCode(39);
  if (v === "") return "";
  let i = 0; while (i < v.length && v.charAt(i) === " ") i++;
  const lead = v.slice(0, i);
  let val = v.slice(i);
  if (val === "") return lead;
  let cut = -1, q = "";
  for (let j = 0; j < val.length; j++) {
    const c = val.charAt(j);
    if (q) { if (c === q) q = ""; continue; }
    if (c === DQ || c === SQ) { q = c; continue; }
    if (c === "#" && j > 0 && val.charAt(j - 1) === " ") { cut = j; break; }
  }
  let comment = "";
  if (cut >= 0) { comment = val.slice(cut); val = val.slice(0, cut); }
  let k = val.length; while (k > 0 && val.charAt(k - 1) === " ") k--;
  const trail = val.slice(k); val = val.slice(0, k);
  const cls = classifyVal(val);
  let html = lead + (cls ? '<span class="' + cls + '">' + esc(val) + '</span>' : esc(val)) + trail;
  if (comment) html += '<span class="vt-com">' + esc(comment) + '</span>';
  return html;
}
function classifyVal(v) {
  const DQ = String.fromCharCode(34), SQ = String.fromCharCode(39);
  if (v === "") return "";
  const c0 = v.charAt(0);
  if (c0 === DQ || c0 === SQ) return "vt-str";
  if (c0 === "&" || c0 === "*" || c0 === "!") return "vt-anc";
  const low = v.toLowerCase();
  if (low === "true" || low === "false" || low === "null" || low === "~" || low === "yes" || low === "no") return "vt-bool";
  if (yamlIsNum(v)) return "vt-num";
  return "";
}
function yamlIsNum(v) {
  let s = v; if (s.charAt(0) === "-") s = s.slice(1);
  if (s === "") return false;
  let dot = 0;
  for (let i = 0; i < s.length; i++) {
    const c = s.charAt(i);
    if (c === ".") { dot++; if (dot > 1) return false; continue; }
    if (c < "0" || c > "9") return false;
  }
  return true;
}
function vscGutter(s) {
  const NL = String.fromCharCode(10);
  const n = String(s == null ? "" : s).split(NL).length;
  let g = "";
  for (let i = 1; i <= n; i++) g += (i > 1 ? NL : "") + i;
  return g;
}
function vscEditor(uid, content, editable) {
  const s = String(content == null ? "" : content);
  return '<div class="vsc-wrap' + (editable ? '' : ' vsc-ro') + '"><div class="vsc-inner">'
    + '<div class="vsc-gutter" id="vscg-' + uid + '">' + vscGutter(s) + '</div>'
    + '<div class="vsc-code"><pre class="vsc-hi" id="vsch-' + uid + '">' + yamlHi(s) + '</pre>'
    + (editable ? '<textarea class="vsc-ta" data-vsc spellcheck="false" id="vscta-' + uid + '">' + esc(s) + '</textarea>' : '')
    + '</div></div></div>';
}
function vscWire(uid) {
  const ta = document.getElementById("vscta-" + uid);
  if (!ta) return;
  const hi = document.getElementById("vsch-" + uid);
  const gut = document.getElementById("vscg-" + uid);
  const sync = () => { const v = ta.value; if (hi) hi.innerHTML = yamlHi(v); if (gut) gut.textContent = vscGutter(v); };
  ta.addEventListener("input", sync);
  ta.addEventListener("keydown", ev => {
    if (ev.key === "Tab") {
      ev.preventDefault();
      const a = ta.selectionStart, b = ta.selectionEnd;
      ta.value = ta.value.slice(0, a) + "  " + ta.value.slice(b);
      ta.selectionStart = ta.selectionEnd = a + 2;
      sync();
    }
  });
  sync();
}
function wireAllVsc() {
  const tas = document.querySelectorAll('#dpane-yaml textarea[data-vsc]');
  for (let i = 0; i < tas.length; i++) vscWire(tas[i].id.slice(6));
}
function renderYaml() {
  if (!state) return;
  const pane = $("dpane-yaml");
  if (!pane) return;
  if (!yamlData) { pane.innerHTML = '<div class="hint" style="padding:10px">Loading SkyrimNet YAML...</div>'; loadYamlData(); return; }
  if (yamlData.error) { pane.innerHTML = yamlCard() + '<div class="hint" style="color:var(--err);padding:8px">' + esc(yamlData.error) + '</div>'; return; }
  const keep = {};
  pane.querySelectorAll('textarea[data-vsc]').forEach(ta => { keep[ta.id] = ta.value; });
  const logEl = $("yaml-log");
  const logHtml = logEl ? logEl.innerHTML : "";
  const logShown = !!(logEl && logEl.style.display === "block");
  let h = yamlCard();
  h += '<div class="card"><div class="row"><span class="label">📄 Base YAML</span>'
    + '<span class="chip">' + (yamlData.builtin ? "builtin default" : esc(yamlData.baseLabel || "custom base")) + '</span>'
    + '<button data-act="yamlBaseSave">💾 Save base</button>'
    + '<button class="stop" data-act="yamlBaseReset" title="delete your edited base and return to the builtin SkyrimNet skeleton">↺ Reset to builtin</button>'
    + '</div>'
    + '<div class="hint" style="margin:6px 0 2px;line-height:1.5">This persistent file sits at the top of your Providers.yaml. The auto-generated PandorumLLM providers are appended below it on Generate.</div>'
    + vscEditor("yamlbase", yamlData.base || "", true) + '</div>';
  h += '<div class="card"><div class="row"><span class="label">👁 Generated Preview</span>'
    + '<span class="hint">' + (yamlData.generated ? "read-only - the last generated Providers.yaml (base + PandorumLLM providers)" : "nothing generated yet - press Generate providers.yaml above") + '</span></div>'
    + (yamlData.generated ? vscEditor("yamlgen", yamlData.generated, false) : "") + '</div>';
  pane.innerHTML = h;
  const l2 = $("yaml-log");
  if (l2 && logHtml) { l2.innerHTML = logHtml; if (logShown) l2.style.display = "block"; }
  Object.keys(keep).forEach(id => { const ta = document.getElementById(id); if (ta) ta.value = keep[id]; });
  wireAllVsc();
}
async function yamlBaseSave(el) {
  const ta = document.getElementById("vscta-yamlbase");
  if (!ta) return;
  el.disabled = true;
  const r = await post("/api/yaml-base-save", { content: ta.value });
  el.disabled = false;
  if (r.error) { yamlLog(r.error); return; }
  await loadYamlData();
  yamlLog("✅ base saved (" + r.count + " providers)");
}
async function yamlBaseReset(el) {
  if (!await uiConfirm("Reset the base YAML to the builtin SkyrimNet skeleton? Your edited base file will be deleted.")) return;
  const r = await post("/api/yaml-base-reset", {});
  if (r.error) { yamlLog(r.error); return; }
  await loadYamlData();
  yamlLog("✅ base reset to builtin default");
}
async function yamlOpenNative(el) {
  const r = await post("/api/yaml-open-native", {});
  if (r && r.error) { yamlLog(r.error); }
}
function yamlLog(msg) {
  const l = $("yaml-log");
  if (l) { l.textContent = nowStamp() + msg; l.style.display = "block"; }
}
async function yamlAction(url, el) {
  el.disabled = true;
  const r = await post(url, {});
  el.disabled = false;
  if (r.error) { yamlLog(r.error); return; }
  let m = "";
  if (url.endsWith("generate")) m = "\u2705 generated " + r.count + " PandorumLLM providers on " + r.ip + " (base: " + r.base + ")"
    + ((r.warnings||[]).length ? String.fromCharCode(10) + r.warnings.join(String.fromCharCode(10)) : "");
  else m = "\u2705 written: " + (r.path || "ok");
  await load();
  await loadYamlData();
  const l = $("yaml-log"), B = String.fromCharCode(92);
  if (l) {
    if (url.endsWith("generate")) {
      l.innerHTML = nowStamp() + esc(m) + '<br><span style="color:var(--warn)">now place providerYAML' + B + 'Providers.yaml into your Modlist: &lt;Modlist&gt;' + B + 'overwrite' + B + 'SKSE' + B + 'Plugins' + B + 'SkyrimNet' + B + 'config' + B + 'Providers.yaml &mdash; or click [Create providers.yaml File] and pick that config folder directly</span>';
    } else {
      l.textContent = nowStamp() + m;
    }
    l.style.display = "block";
  }
}
function fullWinOn() {
  return !!(document.fullscreenElement || document.webkitFullscreenElement);
}
function toggleFullWin() {
  const el = document.documentElement;
  try {
    if (fullWinOn()) {
      const off = document.exitFullscreen || document.webkitExitFullscreen;
      if (off) off.call(document);
    } else {
      const on = el.requestFullscreen || el.webkitRequestFullscreen;
      if (on) on.call(el);
    }
  } catch (e) { trace("you", "full window refused", String(e).slice(0, 60)); }
}
// the browser can leave full screen on its own (Escape), so follow the event
document.addEventListener("fullscreenchange", function() { paintProfiles(); });
document.addEventListener("webkitfullscreenchange", function() { paintProfiles(); });
function profRow() {
  const open = !!window.__profOpen;
  const act = ((state && state.settings) || {}).activeProfile || "";
  if (window.__profPick === undefined && act) window.__profPick = act;
  const rem = (((state && state.settings) || {}).networkMode === "lan");
  return '<span class="hdr-note" data-hostonly data-act="remJump" role="button" tabindex="0" title="open Permissions > Remote Access">Remote Access - '
    + (rem ? '<span class="blueglow">On</span>' : 'Off') + '</span>'
    + '<span class="hdr-note" data-act="fullWin" role="button" tabindex="0" title="fill the screen, the same as F11">Fullscreen - '
    + (fullWinOn() ? '<span class="blueglow">On</span>' : 'Off') + '</span>'
    + '<span class="profwrap" data-hostonly>'
    + '<span class="hdr-link' + (open ? " on" : "") + '" data-act="profToggle" role="button" tabindex="0" title="save, load or delete a full setup">Profiles' + (act ? ' - <span class="blueglow">' + esc(act) + '</span>' : "") + '</span>'
    + (open
        ? '<span class="profpop" id="profpop">'
          + '<select class="prof-sel" onchange="profSel(this)"><option value="">&#8212; pick a profile &#8212;</option>'
          + (state.profiles || []).map(p => '<option value="' + esc(p) + '"' + (p === window.__profPick ? " selected" : "") + '>' + esc(p) + '</option>').join("")
          + '</select>'
          + '<span class="profbtns">'
          + '<button class="stop" data-act="profSaveOver" title="overwrite the selected profile with the current setup">Save</button>'
          + '<button class="stop" data-act="profSave" title="store the current setup under a new name">New</button>'
          + '<button class="stop" data-act="profDel" title="delete the selected profile">Delete</button>'
          + '</span></span>'
        : '')
    + '</span>';
}
function netCard() {
  return '<div class="card" id="card-net"><div class="row"><span class="label hdg netlabel"><svg class="netlabel-ico" viewBox="0 0 24 20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"><rect x="9" y="0.9" width="6" height="6" rx="1"/><path d="M12 6.9v3.1M4 10h16M4 10v3M12 10v3M20 10v3" stroke-linecap="round"/><rect x="1" y="13" width="6" height="6" rx="1"/><rect x="9" y="13" width="6" height="6" rx="1"/><rect x="17" y="13" width="6" height="6" rx="1"/></svg><span>Live Network</span></span>'
    + '<span data-hostonly style="display:contents">'
    + '<button data-act="reco"><svg viewBox="0 0 24 24" width="16" height="16" style="vertical-align:-3px;margin-right:6px"><path d="M3.9 20.3 13.2 11" stroke="currentColor" stroke-width="3.4" stroke-linecap="round" fill="none"/><path d="M15 9.2 17.6 6.6" stroke="currentColor" stroke-width="3.4" stroke-linecap="round" fill="none"/><path fill="currentColor" d="M8.5 1.9Q9.29 4.71 12.1 5.5Q9.29 6.29 8.5 9.1Q7.71 6.29 4.9 5.5Q7.71 4.71 8.5 1.9Z"/><path fill="currentColor" d="M15.5 0.4Q16.12 2.58 18.3 3.2Q16.12 3.82 15.5 6Q14.88 3.82 12.7 3.2Q14.88 2.58 15.5 0.4Z"/><path fill="currentColor" d="M16.8 13.7Q17.64 16.66 20.6 17.5Q17.64 18.34 16.8 21.3Q15.96 18.34 13 17.5Q15.96 16.66 16.8 13.7Z"/></svg>Recommended setup</button>'
    + '</span>'
    + '</div>'
    + '<div style="margin-top:10px">' + gpusCard() + '</div>'
    + '<div id="netgraph" style="margin-top:10px">'+buildNet()+'</div>'
    + '<pre class="log" id="reco-log"' + (recoMsg ? ' style="display:block"' : '') + '>' + esc(recoMsg) + '</pre></div>';
}
function netBox(kind, id, title, sub, right, col) {
  return '<div class="netbox ' + kind + '" data-nb="' + kind + ':' + id + '" data-kind="' + kind + '" data-id="' + esc(id) + '"'
    + ' draggable="' + (kind === "gpu" ? "false" : "true") + '"'
    + (col ? ' style="--nbc:' + col + ';box-shadow:0 0 0 1px ' + col + '3d, 0 0 14px -3px ' + col + '"' : '')
    + '><div class="nb-t">' + title + '</div>'
    + (sub ? '<div class="nb-s">' + sub + '</div>' : '')
    + (right ? '<div class="nb-r">' + right + '</div>' : '')
    + '</div>';
}
// every box can be linked or detached at any time - a server needs no model to be
// dragged onto a GPU, and a provider needs no GPU-backed server to be dropped into.
function buildNet() {
  const CH = ["#4da3ff","#3fd68f","#ff5dc8","#f0d429","#ffa94d","#b78bff"];
  const gpus = (state.gpus || []).filter(g => g.enabled !== false);
  const gcol = {};
  gpus.forEach(function(g, i) { gcol[g.id] = CH[i % CH.length]; });
  const servers = state.routing || [];
  const slotById = {};
  (state.slots || []).forEach(x => slotById[x.id] = x);
  let h = '<div class="netwrap' + (netBusy ? " netbusy" : "") + '" id="netwrap"><svg class="netlines" id="netlines"></svg>';

  h += '<div class="netband" id="netband-gpu">';
  if (!gpus.length) h += '<div class="hint">no GPUs detected</div>';
  gpus.forEach(function(g) {
    const nm = (g.brand ? g.brand + " " : "") + (g.name || g.id);
    const n = servers.filter(s => s.gpuId === g.id).length;
    h += '<div class="netdock" data-drop="gpu" data-id="' + esc(g.id) + '">'
      + netBox("gpu", g.id, esc(nm), esc(g.mem || ""), "#" + esc(g.index), gcol[g.id])
      + '</div>';
  });
  h += '</div>';

  h += '<div class="netband" id="netband-srv">';
  if (!servers.length) h += '<div class="hint">no servers configured</div>';
  servers.forEach(function(s) {
    const sl = slotById[s.id] || {};
    const mdl = (sl.params && sl.params.model) ? modelBase(sl.params.model) : "";
    const run = sl.status && sl.status.state === "serving";
    const sub = mdl ? esc(mdl) : (run ? '<span style="color:var(--ok)">running</span>' : "");
    h += '<div class="netcol">'
      + netBox("srv", s.id, esc(s.label || s.id), sub, ":" + esc(s.port), s.gpuId ? gcol[s.gpuId] : "")
      + '<div class="netdrop" data-nb="drop:' + s.id + '" data-drop="slot" data-id="' + esc(s.id) + '">'
      + ((s.providers || []).length
          ? (s.providers || []).map(function(p) {
              return netBox("prov", p.id, esc((p.emoji || "\u2022") + " " + (p.title || p.id)), "", ":" + esc(p.port), dashColor(p.title || p.id));
            }).join("")
          : '<div class="nd-e">drop providers here</div>')
      + '</div></div>';
  });
  h += '</div>';

  const parked = state.unallocated || [];
  h += '<div class="netband netpark" id="netpark" data-drop="none">'
    + parked.map(function(p) {
        return netBox("prov", p.id, esc((p.emoji || "\u2022") + " " + (p.title || p.id)), "", ":" + esc(p.port), dashColor(p.title || p.id));
      }).join("")
    + '</div></div>';
  return h;
}
// lines are drawn after layout, from real box positions, so they track any wrapping
// every GPU box the width of the widest GPU box, and the same for servers and providers,
// so a long card or server name does not leave the column ragged
function netEqualize() {
  const wrap = document.getElementById("netwrap");
  if (!wrap) return;
  ["gpu", "srv", "prov"].forEach(function(kind) {
    const boxes = wrap.querySelectorAll(".netbox." + kind);
    if (!boxes.length) return;
    let w = 0;
    boxes.forEach(function(b) { b.style.width = ""; });
    boxes.forEach(function(b) { w = Math.max(w, Math.ceil(b.getBoundingClientRect().width)); });
    boxes.forEach(function(b) { b.style.width = w + "px"; });
    if (kind === "prov") {                          // the drop boxes hold the provider column
      wrap.querySelectorAll(".netdrop").forEach(function(z) { z.style.minWidth = (w + 20) + "px"; });
    }
  });
}
function drawNetLines() {
  const wrap = document.getElementById("netwrap"), svg = document.getElementById("netlines");
  if (!wrap || !svg) return;
  const W = wrap.scrollWidth, H = wrap.scrollHeight;
  svg.setAttribute("viewBox", "0 0 " + W + " " + H);
  svg.setAttribute("width", W); svg.setAttribute("height", H);
  const base = wrap.getBoundingClientRect();
  const at = function(sel) {
    const el = wrap.querySelector('[data-nb="' + sel + '"]');
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { x: r.left - base.left + r.width / 2, top: r.top - base.top, bot: r.bottom - base.top };
  };
  let out = "";
  const CH = ["#4da3ff","#3fd68f","#ff5dc8","#f0d429","#ffa94d","#b78bff"];
  const gcol = {};
  (state.gpus || []).filter(g => g.enabled !== false).forEach(function(g, i) { gcol[g.id] = CH[i % CH.length]; });
  const vlink = function(a, b, col) {
    const p = at(a), q = at(b);
    if (!p || !q) return;
    const x = p.x;                                  // centred on the server box
    out += '<path class="netline" data-a="' + a + '" data-b="' + b + '" fill="none" stroke="' + (col || "#3a4152") + '" stroke-width="2" opacity="0.75" '
      + 'd="M ' + x.toFixed(1) + ' ' + p.bot.toFixed(1) + ' L ' + x.toFixed(1) + ' ' + q.top.toFixed(1) + '"/>';
  };
  const link = function(a, b, col) {
    const p = at(a), q = at(b);
    if (!p || !q) return;
    const y1 = p.bot, y2 = q.top, mid = (y1 + y2) / 2;
    out += '<path class="netline" data-a="' + a + '" data-b="' + b + '" fill="none" stroke="' + (col || "#3a4152") + '" stroke-width="2" opacity="0.75" '
      + 'd="M ' + p.x.toFixed(1) + ' ' + y1.toFixed(1) + ' C ' + p.x.toFixed(1) + ' ' + mid.toFixed(1)
      + ' ' + q.x.toFixed(1) + ' ' + mid.toFixed(1) + ' ' + q.x.toFixed(1) + ' ' + y2.toFixed(1) + '"/>';
  };
  (state.routing || []).forEach(function(s) {
    const c = gcol[s.gpuId] || "";
    if (s.gpuId) link("gpu:" + s.gpuId, "srv:" + s.id, c);
    // a single perpendicular drop line, and only once something is actually in the box
    if ((s.providers || []).length) vlink("srv:" + s.id, "drop:" + s.id, c);
  });
  svg.innerHTML = out;
}
// click any box: light up everything it is wired to, backwards and forwards
function netTrace(kind, id) {
  const wrap = document.getElementById("netwrap");
  if (!wrap) return;
  const servers = state.routing || [];
  const keys = {};
  const add = function(k) { keys[k] = true; };
  const withServer = function(s) {
    add("srv:" + s.id);
    add("drop:" + s.id);                          // the drop box shares the server's chain
    if (s.gpuId) add("gpu:" + s.gpuId);
    (s.providers || []).forEach(function(p) { add("prov:" + p.id); });
  };
  if (kind === "gpu") {
    add("gpu:" + id);
    servers.filter(function(s) { return s.gpuId === id; }).forEach(withServer);
  } else if (kind === "srv") {
    const s = servers.filter(function(x) { return x.id === id; })[0];
    if (s) withServer(s);
  } else {
    add("prov:" + id);
    servers.forEach(function(s) {
      if ((s.providers || []).some(function(p) { return p.id === id; })) {
        add("srv:" + s.id);
        add("drop:" + s.id);
        if (s.gpuId) add("gpu:" + s.gpuId);
      }
    });
  }
  clearTimeout(window.__netTraceT);
  wrap.querySelectorAll(".trace").forEach(function(el) { el.classList.remove("trace"); });
  void wrap.offsetWidth;                                   // restart the animation cleanly
  Object.keys(keys).forEach(function(k) {
    const el = wrap.querySelector('[data-nb="' + k + '"]');
    if (el) el.classList.add("trace");
  });
  wrap.querySelectorAll(".netline").forEach(function(ln) {
    if (keys[ln.dataset.a] && keys[ln.dataset.b]) ln.classList.add("trace");
  });
  window.__netTraceT = setTimeout(function() {
    wrap.querySelectorAll(".trace").forEach(function(el) { el.classList.remove("trace"); });
  }, 7500);
}
// Live Network dragging uses pointer events rather than HTML5 drag-and-drop:
// the same approach the old graph used, and it works regardless of drag quirks.
let netDrag = null;
let netBusy = false;
function netMoveLocal(kind, id, zone, zoneId) {
  if (kind === "srv") {
    const gid = (zone === "gpu") ? zoneId : "";
    ((state.routing || []).filter(x => x.id === id)[0] || {}).gpuId = gid;
    ((state.slots || []).filter(x => x.id === id)[0] || {}).gpuId = gid;
    return;
  }
  let prov = null;
  (state.routing || []).forEach(function(s) {
    const pr = s.providers || [];
    for (let i = 0; i < pr.length; i++) if (pr[i].id === id) { prov = pr.splice(i, 1)[0]; break; }
  });
  state.unallocated = state.unallocated || [];
  if (!prov) {
    for (let i = 0; i < state.unallocated.length; i++)
      if (state.unallocated[i].id === id) { prov = state.unallocated.splice(i, 1)[0]; break; }
  }
  if (!prov) return;
  if (zone === "slot") {
    const dst = (state.routing || []).filter(x => x.id === zoneId)[0];
    if (dst) { dst.providers = dst.providers || []; dst.providers.push(prov); }
    else state.unallocated.push(prov);
  } else state.unallocated.push(prov);
}
function netZoneAt(x, y) {
  const under = document.elementFromPoint(x, y);
  return (under && under.closest) ? under.closest("#netgraph [data-drop]") : null;
}
function netDragEnd(el) {
  if (netDrag && netDrag.ph && netDrag.ph.parentNode) netDrag.ph.remove();
  if (el) {
    el.style.position = ""; el.style.left = ""; el.style.top = "";
    el.style.width = ""; el.style.zIndex = ""; el.style.pointerEvents = "";
    el.classList.remove("dragging");
  }
  document.querySelectorAll("#netgraph .over").forEach(x => x.classList.remove("over"));
}
document.addEventListener("pointerdown", e => {
  const b = e.target.closest && e.target.closest("#netgraph .netbox");
  if (!b || b.dataset.kind === "gpu" || e.button !== 0 || netBusy) return;
  e.preventDefault();
  const r = b.getBoundingClientRect();
  netDrag = { el: b, kind: b.dataset.kind, id: b.dataset.id,
              dx: e.clientX - r.left, dy: e.clientY - r.top,
              w: r.width, h: r.height, moved: false, ph: null };
});
document.addEventListener("pointermove", e => {
  if (!netDrag) return;
  if (!netDrag.moved) {
    netDrag.moved = true;
    const el = netDrag.el;
    const ph = document.createElement("div");     // holds the gap open so nothing shifts
    ph.className = "netghost";
    ph.style.width = netDrag.w + "px";
    ph.style.height = netDrag.h + "px";
    el.parentNode.insertBefore(ph, el);
    netDrag.ph = ph;
    el.classList.add("dragging");
    el.style.width = netDrag.w + "px";
    el.style.position = "fixed";
    el.style.zIndex = "999";
    el.style.pointerEvents = "none";
  }
  netDrag.el.style.left = (e.clientX - netDrag.dx) + "px";
  netDrag.el.style.top = (e.clientY - netDrag.dy) + "px";
  document.querySelectorAll("#netgraph .over").forEach(x => x.classList.remove("over"));
  const z = netZoneAt(e.clientX, e.clientY);
  if (z) z.classList.add("over");
});
document.addEventListener("pointerup", async e => {
  if (!netDrag) return;
  const d = netDrag;
  if (!d.moved) { netDrag = null; netDragEnd(d.el); netTrace(d.kind, d.id); return; }
  const z = netZoneAt(e.clientX, e.clientY);
  let zone = z ? z.dataset.drop : "";
  if (d.kind === "srv" && zone === "slot") zone = "";   // drop boxes hold providers only
  netDragEnd(d.el);
  netDrag = null;
  // nothing would change, so just let the box settle back where it came from
  const cur = (d.kind === "srv")
    ? ((state.routing || []).filter(x => x.id === d.id)[0] || {}).gpuId || ""
    : (((state.routing || []).filter(s => (s.providers || []).some(p => p.id === d.id))[0] || {}).id || "");
  const want = (zone === "gpu" || zone === "slot") ? (z ? z.dataset.id : "") : "";
  if (String(cur) === String(want)) { renderNetwork(); return; }
  let r = null;
  let note = "", req = null;
  if (d.kind === "srv" && zone === "gpu") {
    note = netName("gpu", z.dataset.id) + "  <-  " + netName("srv", d.id);
    req = ["/api/edit", { slot: d.id, gpuId: z.dataset.id }];
  } else if (d.kind === "prov" && zone === "slot") {
    note = netName("srv", z.dataset.id) + "  <-  " + netName("prov", d.id) + "  (Priority " + provPrio(d.id) + ")";
    req = ["/api/provider-move", { id: d.id, toSlot: z.dataset.id }];
  } else if (d.kind === "srv") {
    note = netName("srv", d.id) + "  ->  unallocated";
    req = ["/api/edit", { slot: d.id, gpuId: "" }];
  } else {
    note = netName("prov", d.id) + "  ->  unallocated";
    req = ["/api/provider-move", { id: d.id, toSlot: "" }];
  }
  netMoveLocal(d.kind, d.id, zone, z ? z.dataset.id : "");
  netBusy = true;
  renderNetwork();                                // the box lands where you dropped it
  netLog(note);
  r = await post(req[0], req[1]);
  netBusy = false;
  if (r && r.error) { netLog("could not move that: " + r.error); }
  await load();
  renderNetwork();
});
function applyPcMode(one) {
  // directly reflect 1-PC / 2-PC in the DOM immediately, independent of any re-render
  window.__pcModeSet = { one: !!one, at: Date.now() };   // authoritative user choice, guards stale loads
  const rr = document.getElementById("remote-row");
  if (rr) rr.style.display = one ? "none" : "";
  const b1 = document.querySelector('[data-act="ipOne"]'), b2 = document.querySelector('[data-act="ipTwo"]');
  if (b1) b1.classList.toggle("on", !!one);
  if (b2) b2.classList.toggle("on", !one);
  if (state && state.settings) state.settings.onePC = !!one;
}
// If a state refresh lands within a moment of the user toggling PC mode, keep the user's
// choice rather than a possibly-stale server value that hasn't caught up yet.
function reconcilePcMode() {
  const g = window.__pcModeSet;
  if (g && (Date.now() - g.at) < 4000 && state && state.settings) {
    state.settings.onePC = g.one;
  }
}
function ipCard() {
  const st = state.settings || {};
  const oneOn = !!st.onePC;
  return '<div class="card" id="card-ips"><div class="row"><span class="label">\U0001F310 PC IP Addresses</span>'
    + ' <button class="stop' + (oneOn ? ' on' : '') + '" data-act="ipOne">🖥 1 PC setup</button><button class="stop' + (oneOn ? '' : ' on') + '" data-act="ipTwo">🖧 2 PC setup</button>'
    + '<span style="display:inline-block;width:26px"></span>'
    + '<button class="stop" data-act="ipDetect">\U0001F50D Detect IP address</button>'
    + '</div>'
    + (pcModeMsg ? '<div class="row" style="margin-top:8px"><span class="hint" style="color:' + (pcModeMsg.err ? 'var(--err)' : 'var(--ok)') + '">' + esc(pcModeMsg.msg) + '</span></div>' : '')
    + '<div class="row" style="margin-top:10px"><span class="hint" style="width:230px">PandorumLLM PC (this machine)</span>'
    + '<input class="edit hb" id="ip-panel" onfocus="this.classList.add(&quot;show&quot;)" style="max-width:160px" value="'+esc(st.panelIp||"")+'" placeholder="enter IP address">'
    + '<button data-act="ipSet" data-key="panelIp" data-input="ip-panel">\U0001F4BE Set IP address</button>'
    + '<span id="ipstat-panelIp"></span>' 
    + '<span class="hint" id="ip-sugg"></span></div>'
    + '<div class="row" id="remote-row" style="margin-top:8px' + (oneOn ? ';display:none' : '') + '"><span class="hint" style="width:230px">Remote PC (SkyrimNet PC)</span>'
    + '<input class="edit hb" id="ip-remote" onfocus="this.classList.add(&quot;show&quot;)" style="max-width:160px" value="'+esc(st.remoteIp||"")+'" placeholder="enter IP address">'
    + '<button data-act="ipSet" data-key="remoteIp" data-input="ip-remote">\U0001F4BE Set IP address</button>'
    + '<span id="ipstat-remoteIp"></span>' + '</div></div>';
}
async function detectIp(el) {
  el.disabled = true;
  const r = await post("/api/detect-ip", {});
  el.disabled = false;
  const box = $("ip-sugg");
  box.innerHTML = (r.ips||[]).map(ip =>
    '<span class="chip clickable" data-act="ipUse" data-ip="'+esc(ip)+'"><span class="hb">'+esc(ip)+'</span></span>').join(" ") || "none found";
}
let slotMsg = {};
let recoMsg = "";
let netLines = [];
// reports the action the user just performed, rather than a canned result message
function netLog(msg) {
  netLines.push(nowStamp() + msg);
  if (netLines.length > 80) netLines = netLines.slice(-80);
  recoMsg = netLines.join(String.fromCharCode(10));
  const el = $("reco-log");
  if (el) { el.textContent = recoMsg; el.style.display = "block"; el.scrollTop = el.scrollHeight; }
}
function netAllProvs() {
  return (state.routing || []).reduce(function(a, s) { return a.concat(s.providers || []); },
                                      (state.unallocated || []).slice());
}
function netName(kind, id) {
  if (kind === "gpu") {
    const g = (state.gpus || []).filter(x => x.id === id)[0];
    return g ? ((g.brand ? g.brand + " " : "") + (g.name || g.id)) : id;
  }
  if (kind === "srv") {
    const s = (state.routing || []).filter(x => x.id === id)[0];
    return s ? (s.label || s.id) : id;
  }
  const p = netAllProvs().filter(x => x.id === id)[0];
  return p ? (p.title || p.id) : id;
}
function provPrio(id) {
  const p = netAllProvs().filter(x => x.id === id)[0];
  const n = (p && (p.priority === 0 || p.priority === 2)) ? p.priority : 1;
  return n + " - " + ["High", "Normal", "Low"][n];
}
const UI_VERSION = "__UIV__";
let tailMaxState = { dashboard: false, thinking: false, split: false, tts: false };
// Full-window chrome reveal - the ONE mechanism for all three terminal views.
// Controls start hidden; any mouse move (or key) shows them; 2.5s of stillness hides
// them again, unless a control inside the full-window pane holds focus.
let tmaxT = null;
function tmaxHide() {
  document.querySelectorAll(".tmax").forEach(w => {
    if (w.querySelector && w.querySelector(".adjopen")) return;   // an open Adjust menu persists until closed
    const ae = document.activeElement;
    if (ae && w.contains(ae) && ["INPUT","SELECT","TEXTAREA"].includes(ae.tagName)) return;
    w.classList.add("hidechrome");
  });
  const panes = document.querySelectorAll(".tmax");
  if (panes.length && [...panes].every(w => w.classList.contains("hidechrome")))
    document.body.classList.add("tmaxidle");   // the floating nav arrows follow the chrome
}
function tmaxWake() {
  document.body.classList.remove("tmaxidle");
  document.querySelectorAll(".tmax.hidechrome").forEach(w => w.classList.remove("hidechrome"));
  clearTimeout(tmaxT); tmaxT = setTimeout(tmaxHide, 2500);
}
function tmaxChrome(on) {
  clearTimeout(tmaxT); tmaxT = null;
  if (on) {
    if (!window.__tmaxWake) {
      window.__tmaxWake = tmaxWake;
      window.addEventListener("mousemove", window.__tmaxWake);
      window.addEventListener("keydown", window.__tmaxWake);
    }
    tmaxHide();
  } else if (window.__tmaxWake) {
    window.removeEventListener("mousemove", window.__tmaxWake);
    window.removeEventListener("keydown", window.__tmaxWake);
    window.__tmaxWake = null;
    document.body.classList.remove("tmaxidle");
    document.querySelectorAll(".hidechrome").forEach(w => w.classList.remove("hidechrome"));
  }
}
window.addEventListener("keydown", e => {
  if (e.key !== "Escape") return;
  const kind = Object.keys(tailMaxState).find(k => tailMaxState[k]);
  if (kind) { const b = $("tmaxbtn-" + kind); if (b) b.click(); }
});
let ipMsg = {};
let pcModeMsg = null;
function ipNote(m, err) {
  pcModeMsg = { msg: m, err: !!err };
  if (typeof renderRouting === "function") renderRouting(true); else uiAlert(m);
}
function ipStatusFor(key, cur) {
  // Reactive status for an IP row: derived from the field value vs the saved setting, so it
  // never goes stale. Editing the field (value diverges from saved) prompts the user to Set.
  const st = (state && state.settings) || {};
  const saved = (st[key] || "").trim();
  if (saved && cur !== saved)
    return '<span class="hint" style="color:var(--warn)">\u270F unsaved \u2014 click "Set IP Address" to save</span>';
  if (!saved && cur)
    return '<span class="hint" style="color:var(--warn)">\u270F click "Set IP Address" to save</span>';
  const msg = ipMsg[key];
  if (msg) return '<span class="hint" style="color:var(--ok)">' + esc(msg) + '</span>';
  if (saved) return '<span class="hint" style="color:var(--ok)">\u2705 set: <span class="hb">' + esc(saved) + '</span></span>';
  return "";
}
function updateIpStatus(key, inputId) {
  const span = document.getElementById("ipstat-" + key);
  if (!span) return;
  const inp = document.getElementById(inputId);
  span.innerHTML = ipStatusFor(key, inp ? inp.value.trim() : "");
}
async function setIp(key, inputId, el) {
  const v = $(inputId).value.trim();
  if (!v) {
    const sp = document.getElementById("ipstat-" + key);
    if (sp) sp.innerHTML = '<span class="hint" style="color:var(--err)">\u26D4 enter an IP address first</span>';
    return;
  }
  const b = {}; b[key] = v;
  const wasOne = !!(state && state.settings && state.settings.onePC);   // preserve current PC mode
  el.disabled = true;
  const r = await post("/api/settings", b);
  el.disabled = false;
  if (r.error) { uiAlert(r.error); return; }
  let msg = "\u2705 set: " + v;
  const st = state && state.settings || {};
  if (key === "panelIp" && st.yamlGenerated && st.yamlGeneratedIp && st.yamlGeneratedIp !== v)
    msg += "  \u26A0 regenerate providers.yaml (it was built on " + st.yamlGeneratedIp + ")";
  ipMsg[key] = msg;
  applyPcMode(wasOne);              // an IP action must never change 1-PC / 2-PC mode
  await load(); renderCurrent(true);
}
// ITEM 5: Launch mirrors the fleet button's states, and Stop only exists once running
function srvButtons(s, off, running) {
  const A = String.fromCharCode(39);
  const call = function(act) { return "act(" + A + s.id + A + "," + A + act + A + ",this)"; };
  let h = "";
  if (off) h += '<button disabled title="pick a model first">Launch</button>';
  else if (running) h += '<button disabled><span class="spin-emoji">&#9881;&#65039;</span> Running...</button>';
  else h += '<button onclick="' + call("launch") + '">Launch</button>';
  if (running) h += ' <button class="stop" onclick="' + call("stop") + '">&#9209;&#65039; Stop</button>';
  return h;
}
// ITEM 9: the runtime parameters a server launches with. These replace the .ps1
// launcher entirely - saving one rewrites the hidden generated launcher.
function paramEditor(s) {
  const p = s.params || {};
  const defs = state.paramDefs || [];
  const mlist = models || [];
  const cur = p.model || "";
  const KIND = { vision: "vision projector", draft: "draft model" };
  // what each picker is for, and how a file that does not fit should read
  const FITS = { model: "main", vision: "vision", draft: "draft" };
  function optFor(m, wantKey, cur2) {
    const path = m.path || m, kind = m.kind || "main";
    const want = FITS[wantKey];
    // a plain model is a fair drafter, so only mark it as unusual rather than wrong
    const ok = kind === want;                  // only a real drafter belongs there
    const col = ok ? "var(--ok)" : "var(--err)";
    const tag = KIND[kind] ? "  [" + KIND[kind] + "]" : "";
    return '<option value="' + esc(path) + '" style="color:' + col + '"'
         + (path === cur2 ? " selected" : "") + '>' + esc(modelBase(path)) + esc(tag) + '</option>';
  }
  let mopts = '<option value="">&#8212; pick a model &#8212;</option>';
  mlist.forEach(function(m) { mopts += optFor(m, "model", cur); });
  if (cur && !mlist.some(function(m) { return (m.path || m) === cur; }))
    mopts += '<option value="' + esc(cur) + '" selected>' + esc(modelBase(cur)) + ' (not in models folder)</option>';
  const mstate = function(val) {
    if (!val || val === "N/A") return "";
    if (window.__slotBusy && window.__slotBusy[s.id]) return " mload";
    return s.scriptExists === false ? " mfail" : " mok";
  };
  const pick = function(key, cur2, label, guide, flag) {   // optional model pickers
    let o = '<option value="N/A"' + ((!cur2 || cur2 === "N/A") ? " selected" : "") + '>Disabled</option>';
    mlist.forEach(function(m) { o += optFor(m, key, cur2); });
    return '<div class="pcell stack"><span class="plab hint">' + label
      + ' <span class="pref" data-act="paramGuide" data-t="' + pgSlug(guide) + '" title="open this setting in the Sampler Guide">[' + esc(flag) + ']</span></span>'
      + '<span class="pctl"><select class="msel' + mstate(cur2) + '" data-act="slotParam" data-id="' + s.id + '" data-key="' + key + '">' + o + '</select></span>'
      + wrongFor(key, cur2, key === "vision" ? "a vision projector" : "a draft model") + '</div>';
  };
  const chosen = mlist.filter(function(m) { return (m.path || m) === cur; })[0];
  const wrongKind = chosen && KIND[chosen.kind]
    ? '<div class="hint chkmsg" style="color:var(--err)">this is a ' + KIND[chosen.kind]
      + ', not a model a server can run &#8212; pick it under '
      + (chosen.kind === "vision" ? "Vision (mmproj)" : "Speculative decoding") + ' instead</div>'
    : "";
  // and the same said plainly under the two optional pickers
  function wrongFor(key, cur2, label) {
    if (!cur2 || cur2 === "N/A") return "";
    const m2 = mlist.filter(function(x) { return (x.path || x) === cur2; })[0];
    if (!m2) return "";
    const want = FITS[key];
    if (m2.kind === want) return "";
    return '<div class="hint chkmsg" style="color:var(--err)">this is a '
         + (KIND[m2.kind] || "plain model") + ', not ' + label + '</div>';
  }
  let h = '<div class="pgrid">'
    + '<div class="pcell stack"><span class="plab hint">Model <span class="mand">Mandatory</span></span>'
    + '<span class="pctl"><select class="msel' + mstate(p.model) + '" data-act="slotParam" data-id="' + s.id + '" data-key="model">' + mopts + '</select></span>'
    + wrongKind + '</div>'
    + pick("vision", p.vision, "Vision (mmproj)", "Vision projector", "--mmproj")
    + pick("draft", p.draft, "Speculative decoding", "Draft model", "--model-draft");
  // a setting the rest of the configuration makes moot stays visible but is not
  // editable, with the reason on hover, so nothing silently vanishes from the card
  const pval = function(k) {
    const dd = defs.filter(x => x.key === k)[0];
    return String((p[k] !== undefined && p[k] !== "") ? p[k] : (dd ? dd.def : ""));
  };
  const maxNgl = parseInt(pval("ngl"), 10) >= 99;
  const OFF = {
    ngl:       pval("fit") === "on" ? "auto fit chooses the layer count, so this is ignored" : "",
    threads:   maxNgl ? "every layer is on the GPU, so CPU threads barely matter" : "",
    nommap:    maxNgl ? "every layer is on the GPU, so nothing is memory-mapped into RAM" : "",
    cacheK:    pval("flash") === "off" ? "KV cache quantization needs flash attention on" : "",
    cacheV:    pval("flash") === "off" ? "KV cache quantization needs flash attention on" : "",
    nocontbat: parseInt(pval("parallel"), 10) <= 1 ? "continuous batching only applies with more than one parallel slot" : ""
  };
  let seenMmap = false;
  defs.forEach(function(d) {
    const v = (p[d.key] !== undefined && p[d.key] !== "") ? p[d.key] : d.def;
    if (d.key === "nommap") seenMmap = true;
    const tight = seenMmap;                       // the gap under Disable mmap and below
    const why = OFF[d.key] || "";
    const dis = why ? " disabled" : "";
    let ctl;
    const onoff = d.kind === "sel" && (d.opt.opts || []).length === 2
      && (d.opt.opts || []).every(function(o) { return o === "on" || o === "off"; });
    if (onoff) {
      ctl = swToggle(String(v) === "on",
        'data-act="slotParamSwitch" data-id="' + s.id + '" data-key="' + d.key + '"' + dis);
    } else if (d.kind === "sel") {
      ctl = '<select data-act="slotParam" data-id="' + s.id + '" data-key="' + d.key + '"' + dis + '>'
        + (d.opt.opts || []).map(function(o) {
            return '<option value="' + esc(o) + '"' + (String(o) === String(v) ? " selected" : "") + '>' + esc(o) + '</option>';
          }).join("") + '</select>';
    } else {
      ctl = '<input class="edit pnum" type="number" min="' + d.opt.min + '" max="' + d.opt.max + '" step="1" value="' + esc(v) + '" '
          + 'data-act="slotParam" data-id="' + s.id + '" data-key="' + d.key + '" id="pnum-' + s.id + '-' + d.key + '"' + dis + '>'
          + '<span class="rngpop"><input class="prng" type="range" min="' + d.opt.min + '" max="' + d.opt.max + '" step="1" value="' + esc(v) + '" '
          + 'data-act="slotParamRange" data-id="' + s.id + '" data-key="' + d.key + '"' + dis + '></span>';
    }
    const ref = d.ref
      ? ' <span class="pref" data-act="paramGuide" data-t="' + pgSlug(d.ref) + '" title="open this setting in the Sampler Guide">[' + esc(d.flag) + ']</span>'
      : "";
    h += '<div class="pcell' + (why ? " pdim" : "") + (tight ? " ptight" : "") + '"' + (why ? ' title="' + esc(why) + '"' : "")
      + '><span class="plab hint">' + esc(d.label) + ref + '</span>'
      + '<span class="pctl">' + ctl + '</span></div>';
  });
  h += '</div>';
  return h;
}
// ITEM 8: a server slot is "allocated" to a GPU, not to a launcher file
function allocLine(s) {
  const g = (state.gpus || []).filter(x => x.id === s.gpuId)[0];
  const go = ' data-act="gotoNet" data-id="' + esc(s.id) + '" title="show this server in Live Network"';
  if (!g) return '<span class="alloclink" style="color:var(--dim)"' + go + '>Unallocated</span>';
  const nm = (g.brand ? g.brand + " " : "") + (g.name || g.id);
  return '<span class="alloclink" style="color:var(--ok);font-weight:600"' + go + '>Allocated to ' + esc(nm) + '</span>'
    + ' <span class="hint" style="width:auto">' + esc(g.id) + '</span>';
}
const slotLiveT = {}, slotLivePend = {}, slotLiveKeys = {};
let slotDirty = false;
function paramBusy() {
  if (hoverCell && hoverCell.isConnected) return true;
  const ae = document.activeElement;
  if (ae && ae.classList && (ae.classList.contains("pnum") || ae.classList.contains("prng"))) return true;
  for (const k in slotLiveKeys) if (slotLiveKeys[k]) return true;
  return false;
}
function saveSlotParamLive(sid, key, val) {
  const k = sid + "|" + key;
  slotLivePend[k] = val;
  slotLiveKeys[k] = true;
  const slot = (state.slots || []).filter(x => x.id === sid)[0];
  if (slot) { slot.params = slot.params || {}; slot.params[key] = val; }
  clearTimeout(slotLiveT[k]);
  slotLiveT[k] = setTimeout(async function() {
    const body = { slot: sid };
    body[key] = slotLivePend[k];
    const r = await post("/api/slot-params", body);
    slotLiveKeys[k] = false;
    if (r && r.error) { uiAlert(r.error); return; }
    // only redraw once the user has let go, or the card would fight them mid-adjust
    if (paramBusy()) { slotDirty = true; return; }
    await load(); renderSlots();
  }, 420);
}
async function saveSlotParam(sid, key, val) {
  window.__slotBusy = window.__slotBusy || {};
  if (key === "model") window.__slotBusy[sid] = true;
  const slot = (state.slots || []).filter(x => x.id === sid)[0];
  if (slot) {                                   // paint the change straight away
    slot.params = slot.params || {};
    slot.params[key] = val;
    if (document.activeElement && document.activeElement.blur) document.activeElement.blur();
    renderSlots(true);                          // the user asked for this: show it now
  }
  const body = { slot: sid };
  body[key] = val;
  const r = await post("/api/slot-params", body);
  if (r && r.error) { uiAlert(r.error); }
  await load();                                 // then reconcile with the server
  if (window.__slotBusy) delete window.__slotBusy[sid];
  if (key === "model" && val && val !== "N/A") {
    const sl = (state.slots || []).filter(x => x.id === sid)[0];
    const nm = (sl && sl.label) || sid;
    if (sl && sl.scriptExists === false) stackAdd(nm + ": model could not be loaded - " + modelBase(val));
    else stackAdd(nm + ": model loaded - " + modelBase(val));
  }
  renderSlots(true);
  if (curTab === "network") renderNetwork();
}
let curNsub = "host", peerData = null;
function showNsub(x) {
  curNsub = x;
  ["host", "client"].forEach(function(k) {
    const bt = $("nsub-" + k);
    if (bt) bt.classList.toggle("on", k === x);
  });
  const pn = $("nsub-pane");
  if (!pn) return;
  // only one pane exists at a time: the graph uses fixed element ids, so two copies
  // on the page at once would have the line drawing pointing at the wrong one
  pn.className = x === "client" ? "peerview" : "";
  if (x === "host") {
    pn.innerHTML = netCard();
    requestAnimationFrame(function() { netEqualize(); drawNetLines(); });
    return;
  }
  pn.innerHTML = '<div class="hint">reading the client...</div>';
  post("/api/peer", {}).then(function(r) {
    if (curNsub !== "client" || !$("nsub-pane")) return;
    drawPeer(r);
  }).catch(function() { drawPeer(null); });
}
function drawPeer(r) {
  const pn = $("nsub-pane");
  if (!pn) return;
  const addr = (r && r.addr) || "";
  if (!addr) {
    pn.innerHTML = '<div class="card"><div class="hint">No client set. Add its address in '
      + 'Proxy &gt; Proxy Setup, and switch Remote Access on over there.</div></div>';
    return;
  }
  if (!r || !r.fresh) {
    pn.innerHTML = '<div class="card"><div class="hint" style="color:var(--warn)">Client not reachable at '
      + esc(addr) + ((r && r.err) ? ' - ' + esc(r.err) : "")
      + '</div><div class="hint" style="margin-top:6px">It needs PandorumLLM running with Remote Access on.</div></div>';
    return;
  }
  let note = '<div class="hint" style="margin-bottom:8px">' + esc(addr)
    + ' &middot; seen ' + (r.age === null ? "-" : (r.age + "s ago")) + '</div>';
  if (r.version && r.mine && r.version !== r.mine)
    note += '<div class="hint" style="color:var(--warn);margin-bottom:8px">Client is running '
      + esc(r.version) + ', this panel is ' + esc(r.mine) + ' - what it reports may not line up.</div>';
  // the Host page, drawn from the client' + String.fromCharCode(39) + 's state instead of ours
  const keep = state;
  try {
    state = r.state;
    pn.innerHTML = note + netCard();
  } finally {
    state = keep;
  }
  requestAnimationFrame(function() { netEqualize(); drawNetLines(); });
}
function peerSetupCard() {
  const addr = ((state && state.settings) || {}).peerAddr || "";
  return '<div class="card" data-hostonly><div class="row" style="gap:8px;align-items:center;flex-wrap:wrap">'
    + '<span class="hint" style="width:auto">Client panel address</span>'
    + '<input class="edit hb" id="peer-addr" onfocus="this.classList.add(&quot;show&quot;)" style="max-width:260px" placeholder="192.168.1.20:50607" value="'
    + esc(addr).replace(/"/g, "&quot;") + '">'
    + '<button class="stop" data-act="peerSave">Save</button></div>'
    + '<div class="hint" style="margin-top:6px">A second PC running PandorumLLM with Remote Access on. '
    + 'Its cards, servers and providers then appear under Live Network &gt; Client. Nothing is sent to it '
    + 'and it is never controlled from here - it only has to be switched on and reachable.</div></div>';
}
function renderNetwork() {
  if (!state) return;
  const pane = $("tab-network");
  if (!pane) return;
  pane.innerHTML = '<div class="subtabs" style="margin-bottom:10px">'
    + '<button id="nsub-host" class="on" onclick="showNsub(' + String.fromCharCode(39) + 'host' + String.fromCharCode(39) + ')">Host</button>'
    + '<button id="nsub-client" onclick="showNsub(' + String.fromCharCode(39) + 'client' + String.fromCharCode(39) + ')">Client</button>'
    + '</div>'
    + '<div id="nsub-pane"></div>';
  showNsub(curNsub);
}
function renderProviders(force) {
  if (!state) return;
  const pane = $("pmpane-providers");
  if (!pane) return;
  if (!force) {
    if (curTab !== "provmgmt" || curPmSub !== "providers") return;
    const ae = document.activeElement;
    if (ae && pane.contains(ae) && ["INPUT","SELECT","TEXTAREA"].includes(ae.tagName)) return;
  }
  const servers = state.routing || [];
  const rows = [];
  servers.forEach(function(s) { (s.providers || []).forEach(function(p) { rows.push({ p: p, s: s }); }); });
  (state.unallocated || []).forEach(function(p) { rows.push({ p: p, s: null }); });
  rows.sort(function(a, b) { return (a.p.port || 0) - (b.p.port || 0); });
  let h = '<div class="row" style="margin-bottom:10px">'
    + '<button class="stop" data-act="restoreProv" title="reset the shipped default providers to their original state">Restore default providers</button>'
    + '<button class="stop" data-act="provSampResetAll" title="clear every sampler value forced on every provider - nothing else about them is touched">↺ Reset all sampler parameters</button>'
    + '</div>'
    ;
  if (!rows.length) h += '<div class="hint">no providers configured</div>';
  rows.forEach(function(e) {
    const alloc = e.s
      ? '<span style="color:var(--ok);font-weight:600">\u2705 Allocated to ' + esc(e.s.label || e.s.id) + '</span>'
      : '<span style="color:var(--dim)">Unallocated</span>';
    h += '<div class="card' + (e.p.enabled === false ? ' provoff' : '') + '">'
      + '<div class="row" style="gap:10px">'
      + '<span class="label provlink" data-act="gotoProv" data-id="' + esc(e.p.id) + '"'
      + ' style="--pgl:' + dashColor(e.p.title || e.p.id) + '" title="show this provider in Live Network">'
      + '<span class="pemoji">' + esc(e.p.emoji || "\u2022") + '</span>'
      + '<span class="ptitle">' + esc(e.p.title || e.p.id) + '</span></span>'
      + '<span class="portchip">Port ' + esc(e.p.port) + '</span>' + alloc
      + '</div>'
      + '<div class="provs">' + provCard(e.p, e.s) + '</div></div>';
  });
  pane.innerHTML = h;
}
// Native title tooltips cannot be styled, so the attribute is lifted off the element
// while hovered and rendered as our own box instead, then put straight back.
function uiTipHide() {
  clearTimeout(uiTipT);
  uiTipHost = null;                              // nothing on the page is touched here
  if (uiTipEl) { uiTipEl.remove(); uiTipEl = null; }
}
// ---------------------------------------------------------------- observer
// A rolling account of what the page did, kept only while recording. The reasons
// matter as much as the events: most of what goes wrong here is something happening
// at a moment it should have held back, so a line saying an effect stood down, and
// why, is worth more than a line saying it ran.
let traceOn = false, traceLog = [], traceT0 = 0;
const TRACE_MAX = 600;
function trace(kind, what, why) {
  if (!traceOn) return;
  const at = Math.round(performance.now() - traceT0);
  traceLog.push({ at: at, kind: kind, what: what, why: why || "" });
  if (traceLog.length > TRACE_MAX) traceLog.shift();
  traceDirty = true;                             // redrawn on the next frame, not per line
}
let traceDirty = false, traceRaf = 0;
function traceTick() {
  traceRaf = 0;
  if (!traceDirty) return;
  const pane = document.getElementById("lpane-debug");
  if (pane && pane.style.display !== "none") { traceDirty = false; traceDraw(); }
}
function traceText() {
  const NL = String.fromCharCode(10);            // the PAGE string cannot carry a newline
  const head = "PandorumLLM " + ((state && state.version) || "") + " - observer trace" + NL
    + traceLog.length + " entries, "
    + (traceLog.length ? traceLog[traceLog.length - 1].at + "ms covered" : "nothing recorded")
    + NL + NL;
  return head + traceLog.map(function(e) {
    return String(e.at).padStart(6) + "ms  " + e.kind.padEnd(9) + "  " + e.what
         + (e.why ? "   (" + e.why + ")" : "");
  }).join(NL) + NL;
}

let uiTipEl = null, uiTipT = null, uiTipHost = null;
function uiTipShow(host, text) {
  if (!host.isConnected || uiTipBlocked()) return;
  uiTipEl = document.createElement("div");
  uiTipEl.className = "uitip";
  uiTipEl.textContent = text;
  document.body.appendChild(uiTipEl);
  const r = host.getBoundingClientRect(), b = uiTipEl.getBoundingClientRect();
  let left = r.left, top = r.bottom + 8;
  if (left + b.width > window.innerWidth - 10) left = window.innerWidth - b.width - 10;
  if (top + b.height > window.innerHeight - 10) top = r.top - b.height - 8;
  uiTipEl.style.left = Math.max(8, left) + "px";
  uiTipEl.style.top = Math.max(8, top) + "px";
  requestAnimationFrame(function() { if (uiTipEl) uiTipEl.classList.add("on"); });
}
// A note must never disturb what is already on screen. This reports anything that
// counts as open - a drop-out panel, a slider, the guide's side note, a dialog, or a
// focused dropdown whose list the browser may be showing.
function uiTipBlocked() {
  if (window.__profOpen || window.__gpuOpen) return true;
  const ae = document.activeElement;
  if (ae && ae.tagName === "SELECT") return true;
  if (document.querySelector(".refwrap.on, .bgwrap.on, .rngpop.on, .gbranch.gshow")) return true;
  const mr = document.getElementById("modal-root");
  if (mr && mr.children.length) return true;
  return false;
}
// Move note text off the title attribute as soon as an element is drawn, so the browser
// never shows its own box and nothing has to be changed later while the pointer is on it.
// Turn each real select into a hidden driver behind a control we draw. The select
// keeps its value and still emits change, so every handler written against it carries
// on working; all that goes away is the browser-drawn list and its frame.
function enhanceSelects(root) {
  (root || document).querySelectorAll("select:not([data-enh])").forEach(function(sel) {
    sel.setAttribute("data-enh", "1");
    const wrap = document.createElement("div");
    wrap.className = "selwrap";
    // read the width this particular select was given, while it is still where it was
    const cs = window.getComputedStyle(sel);
    const mw = cs.minWidth, fixed = sel.style.width || "";
    sel.parentNode.insertBefore(wrap, sel);
    wrap.appendChild(sel);
    if (mw && mw !== "0px") wrap.style.minWidth = mw;
    if (fixed) wrap.style.width = fixed;
    const btn = document.createElement("div");
    btn.className = "selbtn";
    btn.setAttribute("role", "button");
    btn.setAttribute("tabindex", "0");
    // the width and spacing rules are written against the select's own classes, so the
    // stand-in has to carry them too or it will not sit where the select did
    if (sel.className) wrap.className = "selwrap " + sel.className;
    const list = document.createElement("div");
    list.className = "sellist";
    wrap.appendChild(btn);
    wrap.appendChild(list);
    selSync(wrap);
  });
}
function selSync(wrap) {
  const sel = wrap.querySelector("select");
  const btn = wrap.querySelector(".selbtn");
  const list = wrap.querySelector(".sellist");
  if (!sel || !btn || !list) return;
  const opts = [].slice.call(sel.options);
  const cur = opts[sel.selectedIndex] || opts[0];
  btn.textContent = cur ? cur.textContent : "";
  btn.style.color = (cur && cur.style.color) || "";
  btn.classList.toggle("off", !!sel.disabled);
  if (sel.title) btn.title = sel.title;
  list.innerHTML = "";
  opts.forEach(function(o, i) {
    const d = document.createElement("div");
    d.className = "selopt" + (i === sel.selectedIndex ? " on" : "") + (o.disabled ? " off" : "");
    d.textContent = o.textContent;
    if (o.style.color) d.style.color = o.style.color;
    d.dataset.i = i;
    list.appendChild(d);
  });
}
function selSyncAll() {
  document.querySelectorAll(".selwrap").forEach(function(w) {
    if (w.classList.contains("on")) return;      // open: leave it alone
    const sel = w.querySelector("select"), btn = w.querySelector(".selbtn");
    if (!sel || !btn) return;
    const cur = sel.options[sel.selectedIndex];
    const want = cur ? cur.textContent : "";
    const drawn = w.querySelectorAll(".selopt").length;
    if (btn.textContent !== want || drawn !== sel.options.length) selSync(w);
  });
}
function selClose(except) {
  document.querySelectorAll(".selwrap.on").forEach(function(w) {
    if (w !== except) w.classList.remove("on");
  });
}
document.addEventListener("pointerdown", function(e) {
  const opt = e.target.closest && e.target.closest(".selopt");
  if (opt) {
    const wrap = opt.closest(".selwrap"), sel = wrap.querySelector("select");
    if (opt.classList.contains("off")) return;
    e.preventDefault();
    wrap.classList.remove("on");
    const i = parseInt(opt.dataset.i, 10);
    if (sel.selectedIndex !== i) {
      sel.selectedIndex = i;
      selSync(wrap);
      trace("you", "chose " + (sel.options[i] ? sel.options[i].textContent : "?"));
      sel.dispatchEvent(new Event("change", { bubbles: true }));
    }
    return;
  }
  const btn = e.target.closest && e.target.closest(".selbtn");
  if (btn) {
    const wrap = btn.closest(".selwrap");
    if (btn.classList.contains("off")) return;
    e.preventDefault();
    const open = wrap.classList.contains("on");
    selClose(null);
    if (!open) { selSync(wrap); wrap.classList.add("on"); trace("you", "opened a dropdown"); }
    return;
  }
  if (!(e.target.closest && e.target.closest(".selwrap"))) selClose(null);
});
document.addEventListener("keydown", function(e) {
  if (e.key === "Escape") selClose(null);
});
function tipHarvest() {
  document.querySelectorAll("[title]").forEach(function(el) {
    const v = el.getAttribute("title");
    if (v) el.setAttribute("data-tip", v);
    el.removeAttribute("title");
  });
}
let harvestQ = 0;
new MutationObserver(function() {
  if (harvestQ) return;
  harvestQ = requestAnimationFrame(function() { harvestQ = 0; tipHarvest(); enhanceSelects(); selSyncAll(); });
}).observe(document.documentElement, { childList: true, subtree: true });
tipHarvest();
enhanceSelects();
document.addEventListener("mouseover", function(e) {
  if (uiTipBlocked()) {
    if (e.target.closest && e.target.closest("[data-tip]")) trace("note", "held back", "something is open");
    return;
  }
  const host = e.target.closest && e.target.closest("[data-tip]");
  if (!host || host === uiTipHost) return;
  const text = host.getAttribute("data-tip");
  if (!text) return;
  uiTipHide();
  uiTipHost = host;
  uiTipT = setTimeout(function() {
    if (uiTipBlocked()) { uiTipHide(); return; }  // something opened while we waited
    uiTipShow(host, text);
  }, 1500);
});
document.addEventListener("mouseout", function(e) {
  if (!uiTipHost) return;
  if (e.relatedTarget && uiTipHost.contains(e.relatedTarget)) return;
  uiTipHide();
});
window.addEventListener("scroll", uiTipHide, true);
window.addEventListener("resize", function() {
  if (document.getElementById("gwrap")) requestAnimationFrame(function() { serpentine(); drawHelperLines(); });
});
// one on/off control, so every toggle in the app looks and behaves the same
function swToggle(on, attrs, label, labelFirst) {
  const sw = '<span class="sw"><input type="checkbox"' + (on ? " checked" : "") + " " + attrs + '><span></span></span>';
  const tx = label ? '<span>' + label + '</span>' : '';
  return '<label class="swlab hint">' + (labelFirst ? tx + sw : sw + tx) + '</label>';
}
// ---- Launch button lightning ----
const STOP_ICO = '<svg viewBox="0 0 16 16" width="14" height="14" style="vertical-align:-2px;margin-right:6px"><path fill="currentColor" fill-rule="evenodd" d="M3.2 1.3h9.6c1.05 0 1.9.85 1.9 1.9v9.6c0 1.05-.85 1.9-1.9 1.9H3.2c-1.05 0-1.9-.85-1.9-1.9V3.2c0-1.05.85-1.9 1.9-1.9Zm2.6 4.5v4.4h4.4V5.8H5.8Z"/></svg>';
function termLabel(text) { return STOP_ICO + text; }
function arcLabel(text) {
  return text.split("").map(function(c) {
    return '<span class="alt">' + (c === " " ? "&nbsp;" : esc(c)) + '</span>';
  }).join("") + '<svg class="arcsvg" xmlns="http://www.w3.org/2000/svg"></svg>';
}
function arcPath(x1, y1, x2, y2, spread) {
  const segs = 4 + Math.floor(Math.random() * 3);
  let d = "M " + x1.toFixed(1) + " " + y1.toFixed(1);
  for (let i = 1; i < segs; i++) {
    const f = i / segs;
    const mx = x1 + (x2 - x1) * f + (Math.random() - 0.5) * spread;
    const my = y1 + (y2 - y1) * f + (Math.random() - 0.5) * spread * 1.3;
    d += " L " + mx.toFixed(1) + " " + my.toFixed(1);
  }
  return d + " L " + x2.toFixed(1) + " " + y2.toFixed(1);
}
// Decoration must never touch the page while someone is using it: with a menu open, a
// dropdown in use, a field focused or a dialog up, effects skip their turn entirely.
function fxQuiet() {
  if (window.__profOpen) return "the Profiles menu is open";
  if (window.__gpuOpen) return "the GPU panel is open";
  if (document.querySelector(".refwrap.on")) return "the auto refresh menu is open";
  if (document.querySelector(".bgwrap.on")) return "the terminal background menu is open";
  if (document.querySelector(".rngpop.on")) return "a slider is showing";
  if (document.querySelector(".selwrap.on")) return "a dropdown is open";
  const mr = document.getElementById("modal-root");
  if (mr && mr.children.length) return "a dialog is open";
  // A field being typed into is protected by the redraw guard, not by this one: the
  // effects only ever draw inside their own button and cannot reach it.
  return "";
}
function arcFire(btn, strong, side) {
  // guarded here rather than at each call site: both launch buttons use it
  if (state && state.settings && state.settings.launchArc === false) return;
  const held = fxQuiet();
  if (held) { trace("effect", "arc held back", held); return; }
  trace("effect", "arc drawn");
  const svg = btn.querySelector(".arcsvg");
  const letters = btn.querySelectorAll(".alt");
  if (!svg || letters.length < 2) return;
  const b = btn.getBoundingClientRect();
  const n = letters.length;
  const a = Math.floor(Math.random() * n);
  let c = Math.floor(Math.random() * n);
  if (c === a) c = (a + 1) % n;                     // never arc a letter to itself
  const ra = letters[a].getBoundingClientRect(), rc = letters[c].getBoundingClientRect();
  const low = (side === undefined) ? (Math.random() < 0.5) : !!side;   // over or under the word
  const yA = low ? (ra.bottom - b.top - 3) : (ra.top - b.top + 3);
  const yC = low ? (rc.bottom - b.top - 3) : (rc.top - b.top + 3);
  const p = document.createElementNS("http://www.w3.org/2000/svg", "path");
  p.setAttribute("d", arcPath(ra.left - b.left + ra.width / 2, yA,
                              rc.left - b.left + rc.width / 2, yC,
                              strong ? 13 : 7));
  p.setAttribute("class", "arcbolt" + (strong ? " strong" : ""));
  svg.appendChild(p);
  const drop = function() {
    if (!p.parentNode) return;
    const held = fxQuiet();
    if (held) { trace("effect", "arc cleanup held back", held); setTimeout(drop, 150); return; }
    p.remove();
  };
  setTimeout(drop, strong ? 340 : 200);
}
let arcTimer = null;
document.addEventListener("pointerover", function(e) {
  const b = e.target.closest && e.target.closest("#launchBtn, #launchTtsBtn");
  if (!b || arcTimer) return;
  arcTimer = setInterval(function() {
    if (!b.isConnected) { clearInterval(arcTimer); arcTimer = null; return; }
    arcFire(b, false);
  }, 105);
});
document.addEventListener("pointerout", function(e) {
  const b = e.target.closest && e.target.closest("#launchBtn, #launchTtsBtn");
  if (!b || (e.relatedTarget && b.contains(e.relatedTarget))) return;
  clearInterval(arcTimer); arcTimer = null;
});
function renderCurrent(force) {
  if (curTab === "network") { renderNetwork(); return; }
  if (curTab === "provmgmt") { if (curPmSub === "stats") renderStats(); else renderProviders(force); return; }
  if (curTab === "servers") {
    if (curSsub === "stats") renderStats();
    else if (curSsub === "inspect") { if (force) renderSrvInspector(); }   // never redraw the editor under a live event
    else renderSlots(force);
    return;
  }
  if (curTab === "dashboard" && curDsub === "tts") {
    const ae = document.activeElement, pane = $("dpane-tts");
    if (!(ae && pane && pane.contains(ae) && ["INPUT","SELECT","TEXTAREA"].includes(ae.tagName)))
      renderTts();
    return;
  }
  renderRouting(force);
}
function renderRouting(force) {
  if (!state) return;
  if (!force) {
    if (curTab !== "dashboard" || curDsub !== "setup") return;
    const ae = document.activeElement, pane = $("dpane-setup");
    if (ae && pane && pane.contains(ae) && ["INPUT","SELECT","TEXTAREA"].includes(ae.tagName)) return;
  }
  reconcilePcMode();
  const keepP = $("ip-panel") ? $("ip-panel").value : null;
  const keepR = $("ip-remote") ? $("ip-remote").value : null;
  const live = state.listening || [];
  const gpus = state.gpus || [];
  const byGpu = {};
  (state.routing||[]).forEach(s => {
    const k = (s.gpuId && gpus.some(g => g.id === s.gpuId)) ? s.gpuId : "";
    (byGpu[k] = byGpu[k] || []).push(s);
  });
  const h = ''
    + ipCard()
    + peerSetupCard();
  $("dpane-setup").innerHTML = h;
  if (keepP !== null && $("ip-panel")) $("ip-panel").value = keepP;
  if (keepR !== null && $("ip-remote")) $("ip-remote").value = keepR;
  updateIpStatus("panelIp", "ip-panel");
  updateIpStatus("remoteIp", "ip-remote");
}
async function detectGpus(el) {
  el.disabled = true;
  const r = await post("/api/detect-gpus", {});
  el.disabled = false;
  if (r.error) { netLog("GPU detection failed: " + r.error); return; }
  await load(); renderCurrent(true);
  const gs = state.gpus || [];
  netLog("detected " + gs.length + " GPU" + (gs.length === 1 ? "" : "s"));
  gs.forEach(function(g) {
    netLog("   #" + g.index + "  " + ((g.brand ? g.brand + " " : "") + (g.name || g.id))
      + (g.mem ? "  " + g.mem : "") + (g.enabled === false ? "  (disabled)" : ""));
  });
}
document.addEventListener("input", ev => {
  const t = ev.target;
  if (t && t.id === "ip-panel") updateIpStatus("panelIp", "ip-panel");
  else if (t && t.id === "ip-remote") updateIpStatus("remoteIp", "ip-remote");
});
function fieldDone(el) {
  if (el && el.blur) setTimeout(function() { el.blur(); }, 0);
}
// a native select fires no change when the same option is re-picked, so count clicks:
// the first opens the list, the second closes it either way
document.addEventListener("click", function(e) {
  const s = e.target.closest && e.target.closest("select");
  if (!s) return;
  s.__opens = (s.__opens || 0) + 1;
  if (s.__opens % 2 === 0) { s.__opens = 0; fieldDone(s); }
});
document.addEventListener("change", function(e) {
  const el = e.target;
  if (!el || !el.tagName) return;
  if (el.tagName === "SELECT") { el.__opens = 0; fieldDone(el); }
  else if (el.tagName === "INPUT" && el.type !== "range" && el.type !== "checkbox") fieldDone(el);
});
document.addEventListener("keydown", function(e) {
  if (e.key !== "Enter" && e.key !== "Escape") return;
  const el = e.target;
  if (!el || !el.tagName) return;
  if (el.tagName === "SELECT" || (el.tagName === "INPUT" && el.type !== "range")) {
    el.__opens = 0;
    fieldDone(el);
  }
});
// ---- fleet stack terminal, shown only on request ----
const TGLYPHS = "0123456789#$%&@*+=<>/|~^?!";
let tglyphTimer = null;
function tglyphRoll(on) {
  clearInterval(tglyphTimer); tglyphTimer = null;
  const g = document.querySelector("#stackBtn .tglyph");
  if (!g) return;
  if (!on) { g.textContent = "_"; return; }
  tglyphTimer = setInterval(function() {
    const el = document.querySelector("#stackBtn .tglyph");
    if (!el) { clearInterval(tglyphTimer); tglyphTimer = null; return; }
    if (fxQuiet()) return;                          // purely visual: never interrupt
    el.textContent = TGLYPHS.charAt(Math.floor(Math.random() * TGLYPHS.length));
  }, 110);
}
function stackToggle() {
  const el = $("stacklog");
  if (!el) return;
  window.__stackOpen = !window.__stackOpen;
  el.style.display = window.__stackOpen ? "block" : "none";
  const b = $("stackBtn");
  if (b) b.classList.toggle("on", !!window.__stackOpen);
  tglyphRoll(!!window.__stackOpen);
  if (window.__stackOpen) { stackPaint(); el.scrollTop = el.scrollHeight; }
}
document.addEventListener("pointerover", function(e) {
  if (e.target.closest && e.target.closest("#stackBtn")) tglyphRoll(true);
});
document.addEventListener("pointerout", function(e) {
  const b = e.target.closest && e.target.closest("#stackBtn");
  if (!b || (e.relatedTarget && b.contains(e.relatedTarget))) return;
  if (!window.__stackOpen) tglyphRoll(false);
});
function nudgeSlider(rng, delta) {
  const lo = parseFloat(rng.min), hi = parseFloat(rng.max);
  let v = (parseFloat(rng.value) || 0) + delta;
  if (!isNaN(lo)) v = Math.max(lo, v);
  if (!isNaN(hi)) v = Math.min(hi, v);
  if (String(v) === String(rng.value)) return;
  rng.value = v;
  const cell = rng.closest(".pcell");
  const num = cell && cell.querySelector(".pnum");
  if (num) num.value = v;
  const rd = rng.dataset || {};
  if (rd.id && rd.key) saveSlotParamLive(rd.id, rd.key, String(v));
}
// Holding an arrow moves at a steady base rate from the outset; after a second the
// rate climbs by 1% of this slider's range per second, topping out at 5% per second.
// Context size is different: it steps in whole 1024s on a tap and creeps in 128s while
// held, from one every half second up to one every tenth of a second after five.
const HOLD_BASE = 22;                             // units per second before the ramp
const HOLD_DELAY = 0.3;                           // a press shorter than this is just a tap
const CTX_TAP = 1024, CTX_HOLD = 128;
let hold = null;
function holdTick(ts) {
  if (!hold) return;
  if (!hold.t0) { hold.t0 = ts; hold.last = ts; }
  const held = (ts - hold.t0) / 1000;
  const dt = Math.min(0.1, (ts - hold.last) / 1000);
  hold.last = ts;
  if (hold.ctx) {
    if (held < 0.5) { hold.raf = requestAnimationFrame(holdTick); return; }   // still a tap
    hold.crept = true;                            // release will not add a 1024 step
    const since = held - 0.5;
    const gap = Math.max(0.1, 0.5 - (since / 5) * 0.4);
    if (ts - hold.fired >= gap * 1000) {
      hold.fired = ts;
      nudgeSlider(hold.rng, CTX_HOLD * hold.dir);
    }
  } else {
    if (held < HOLD_DELAY) { hold.raf = requestAnimationFrame(holdTick); return; }  // still a tap
    const pct = Math.min(5, Math.max(0, held - 1));
    const rate = Math.max(HOLD_BASE, hold.range * pct / 100);
    hold.acc += rate * dt;
    if (hold.acc >= 1) {
      const whole = Math.floor(hold.acc);
      hold.acc -= whole;
      nudgeSlider(hold.rng, whole * hold.dir);
    }
  }
  hold.raf = requestAnimationFrame(holdTick);
}
function holdStart(rng, dir) {
  holdStop();
  const lo = parseFloat(rng.min) || 0, hi = parseFloat(rng.max) || 0;
  hold = { rng: rng, dir: dir, range: Math.max(1, hi - lo), acc: 0, t0: 0, last: 0,
           fired: 0, crept: false, ctx: (rng.dataset || {}).key === "ctx" };
  hold.raf = requestAnimationFrame(holdTick);
}
// a tap on context size lands on a clean multiple of 1024
function tapSlider(rng, dir) {
  if ((rng.dataset || {}).key !== "ctx") { nudgeSlider(rng, dir); return; }
  const cur = parseFloat(rng.value) || 0;
  // off the grid: move to the next clean multiple in that direction. On it: step a whole one.
  const target = (cur % CTX_TAP === 0)
    ? cur + CTX_TAP * dir
    : (dir > 0 ? Math.ceil(cur / CTX_TAP) * CTX_TAP : Math.floor(cur / CTX_TAP) * CTX_TAP);
  nudgeSlider(rng, target - cur);
}
function holdStop() {
  if (hold) {
    if (hold.raf) cancelAnimationFrame(hold.raf);
    if (hold.ctx && !hold.crept) tapSlider(hold.rng, hold.dir);   // a plain tap after all
  }
  hold = null;
}
document.addEventListener("keyup", holdStop);
window.addEventListener("blur", holdStop);
// the slider lives in a panel under its value box: it appears while the pointer is on
// either one, and waits a second afterwards so it can be reached
let rngPopT = null, rngPopEl = null;
function rngPop(pop) {
  clearTimeout(rngPopT); rngPopT = null;
  if (rngPopEl && rngPopEl !== pop) rngPopEl.classList.remove("on", "vis");
  rngPopEl = pop;
  if (pop) {
    pop.classList.add("on");
    requestAnimationFrame(function() { pop.classList.add("vis"); });
  }
}
document.addEventListener("mouseover", function(e) {
  if (!e.target.closest) return;
  const cell = e.target.closest(".pcell");
  const near = e.target.closest(".pnum, .rngpop");
  if (cell && near && !cell.classList.contains("pdim")) {
    const pop = cell.querySelector(".rngpop");
    if (pop) rngPop(pop);
  }
});
document.addEventListener("mouseout", function(e) {
  if (!e.target.closest) return;
  if (!e.target.closest(".pnum, .rngpop")) return;
  const to = e.relatedTarget;
  if (to && to.closest && to.closest(".pnum, .rngpop")) return;
  clearTimeout(rngPopT);
  rngPopT = setTimeout(function() {
    const p = rngPopEl;
    rngPopEl = null;
    if (!p) return;
    p.classList.remove("vis");                     // fade, then take it out of the way
    setTimeout(function() { if (!p.classList.contains("vis")) p.classList.remove("on"); }, 200);
  }, 500);
});
let hoverCell = null;
document.addEventListener("mouseover", function(e) {
  const c = e.target.closest && e.target.closest(".pcell");
  if (c) hoverCell = c;
});
document.addEventListener("mouseout", function(e) {
  if (!hoverCell || !e.relatedTarget || hoverCell.contains(e.relatedTarget)) return;
  hoverCell = null;
  if (slotDirty && !paramBusy()) {
    slotDirty = false;
    setTimeout(function() { if (!paramBusy()) load().then(renderSlots); }, 250);
  }
});
document.addEventListener("keydown", function(e) {
  const k = e.key;
  if (k !== "ArrowLeft" && k !== "ArrowRight" && k !== "ArrowUp" && k !== "ArrowDown") return;
  let ae = document.activeElement;
  const focused = ae && ae.classList && (ae.classList.contains("pnum") || ae.classList.contains("prng"));
  if (!focused && hoverCell && hoverCell.isConnected) {
    // nothing relevant focused, but the pointer is over a row - drive that row's slider
    const rng = hoverCell.querySelector(".prng:not([disabled])");
    if (rng) {
      e.preventDefault();
      if (e.repeat) return;                       // the ramp below drives the repeat
      const up = (k === "ArrowRight" || k === "ArrowUp");
      if ((rng.dataset || {}).key !== "ctx") tapSlider(rng, up ? 1 : -1);
      holdStart(rng, up ? 1 : -1);
      return;
    }
  }
  if (!ae || !ae.classList) return;
  // the slider handles all four keys natively; the value box only handles up/down, so
  // add left/right there, and keep the pair in step whichever one has focus
  const isNum = ae.classList.contains("pnum"), isRng = ae.classList.contains("prng");
  if (!isNum && !isRng) return;
  if (isRng) {
    e.preventDefault();
    if (e.repeat) return;
    const up = (k === "ArrowRight" || k === "ArrowUp");
    if ((ae.dataset || {}).key !== "ctx") tapSlider(ae, up ? 1 : -1);
    holdStart(ae, up ? 1 : -1);
    return;
  }
  const d = ae.dataset || {};
  if (isNum && (k === "ArrowLeft" || k === "ArrowRight")) {
    e.preventDefault();
    const step = parseFloat(ae.step) || 1;
    const lo = parseFloat(ae.min), hi = parseFloat(ae.max);
    let v = (parseFloat(ae.value) || 0) + (k === "ArrowRight" ? step : -step);
    if (!isNaN(lo)) v = Math.max(lo, v);
    if (!isNaN(hi)) v = Math.min(hi, v);
    ae.value = v;
    ae.dispatchEvent(new Event("change", { bubbles: true }));
  }
  setTimeout(function() {
    const cell = ae.closest && ae.closest(".pcell");
    const twin = isRng
      ? document.getElementById("pnum-" + d.id + "-" + d.key)
      : (cell && cell.querySelector(".prng"));
    if (twin) twin.value = ae.value;
  }, 0);
});
document.addEventListener("input", ev => {
  if (ev.target && ev.target.id === "srvinsp-view") { srvEdPush(); return; }
  const rd = (ev.target && ev.target.dataset) || {};
  if (rd.act === "slotParamRange") {
    const twin = document.getElementById("pnum-" + rd.id + "-" + rd.key);
    if (twin) twin.value = ev.target.value;
  } else if (rd.act === "slotParam" && ev.target.classList.contains("pnum")) {
    const cell = ev.target.closest(".pcell");
    const rng = cell && cell.querySelector(".prng");
    if (rng) rng.value = ev.target.value;
  }
});
document.addEventListener("change", ev => {
  const d = ev.target.dataset || {};
  if (ev.target && ev.target.id && ev.target.id.indexOf("termfs-sel") === 0) { setTermFontSize(ev.target.value, d.fskind); return; }
  if (ev.target && ev.target.id && ev.target.id.indexOf("termfont-sel") === 0) { setTermFont(ev.target.value, d.fontkind); return; }
  if (d.act === "slotParam" || d.act === "slotParamRange") {
    const cl = ev.target.classList;
    if (cl && (cl.contains("prng") || cl.contains("pnum"))) saveSlotParamLive(d.id, d.key, ev.target.value);
    else saveSlotParam(d.id, d.key, ev.target.value);
    return;
  }
  if (d.act === "slotParamSwitch") { saveSlotParam(d.id, d.key, ev.target.checked ? "on" : "off"); return; }
  if (d.act === "gpuSwitch") {
    const gname = netName("gpu", d.id), on = !!ev.target.checked;
    post("/api/gpu-edit", { id: d.id, enabled: on }).then(r => {
      if (r.error) { netLog("could not change that GPU: " + r.error); return; }
      netLog(gname + "  " + (on ? "enabled" : "disabled"));
      load().then(renderCurrent);
    });
    return;
  }
  if (d.act === "splitFeed") {          // a select: change, not click
    setSplitFeed(ev.target.dataset.side, ev.target.value);
    return;
  }
  if (d.act === "ttsModelSel") {
    const v = ev.target.value;
    if (state && state.settings) state.settings.ttsAcppModel = v;
    post("/api/settings", { ttsAcppModel: v });
    return;
  }
  if (d.act === "ttsEngineSel") {
    const v = ev.target.value;
    if (state && state.settings) state.settings.ttsEngine = v;   // redraw with the new field set
    post("/api/settings", { ttsEngine: v }).then(async () => { await load(); renderTts(); });
    return;
  }
  if (d.act === "launchArcToggle") {
    const on = !!ev.target.checked;
    if (state && state.settings) state.settings.launchArc = on;   // apply before the round trip
    post("/api/settings", { launchArc: on });
    return;
  }
  if (d.act === "provField") {
    const patch = {};
    patch[d.field] = ev.target.type === "checkbox" ? ev.target.checked : ev.target.value;
    provEdit(d.id, patch);
  } else if (d.act === "slotGpu") {
    post("/api/edit", { slot: d.id, gpuId: ev.target.value }).then(r => {
      if (r.error) uiAlert(r.error);
      load().then(renderCurrent);
    });
  } else if (d.act === "srvEdOpen") {
    if (ev.target.value) { window.__srvEdPath = ev.target.value; srvEdAction("open"); }
  } else if (d.act === "srvInspSel") {
    srvInspect();
  } else if (d.act === "inspSel") {
    inspect();
  } else if (ev.target.id && ev.target.id.length > 4) {
    const pre = ev.target.id.slice(0, 4);
    const map = { "mdl-": "model", "vis-": "vision", "drf-": "draft" };
    if (map[pre]) creatorSync(ev.target.id.slice(4), map[pre], ev.target.value);
    else if (pre === "ttl-") creatorTitle(ev.target.id.slice(4), ev.target);
  }
});
document.addEventListener("change", ev => {
  if (ev.target && ev.target.id === "yaml-file" && ev.target.files && ev.target.files[0]) {
    const fr = new FileReader();
    fr.onload = async () => {
      const r = await post("/api/yaml-load", { content: String(fr.result) });
      ev.target.value = "";
      await load();
      await loadYamlData();
      yamlLog(r.error ? r.error : ("\u2705 base loaded: " + r.count + " providers"));
    };
    fr.readAsText(ev.target.files[0]);
  }
});
document.addEventListener("mousedown", ev => {
  const g = ev.target.closest ? ev.target.closest("[data-act]") : null;
  if (g && g.dataset.act === "grip") { const c = g.closest(".prov"); if (c) c.draggable = true; }
});
document.addEventListener("mouseup", () => {
  document.querySelectorAll(".prov").forEach(p => { p.draggable = false; });
});
document.addEventListener("click", ev => {
  const hbEl = ev.target && ev.target.closest ? ev.target.closest(".hb") : null;
  // a revealed value covers itself again as soon as you look elsewhere; a field you
  // are typing in keeps its own reveal until it loses focus
  document.querySelectorAll(".hb.show").forEach(function(x) {
    if (x !== hbEl && x !== document.activeElement) x.classList.remove("show");
  });
  if (hbEl) { hbEl.classList.toggle("show"); return; }
  const el = ev.target.closest ? ev.target.closest("[data-act]") : null;
  if (!el) return;
  const d = el.dataset;
  if (d.act === "revealUuid") { el.classList.toggle("show"); return; }
  if (d.act === "sampChip") { sampEdit(el); return; }
  if (d.act === "provSampChip") { provSampEdit(el); return; }
  if (d.act === "srvEdLock") { srvEd.locked = !srvEd.locked; post("/api/settings", { srvEdOpen: !srvEd.locked }); renderSrvInspector(); return; }
  if (d.act === "srvEdUndo") { srvEdStep(-1); return; }
  if (d.act === "srvEdRedo") { srvEdStep(1); return; }
  if (d.act === "srvEdValidate") { srvEdValidate(); return; }
  if (d.act === "srvEdSave") { srvEdAction("save"); return; }
  if (d.act === "srvEdRevert") { srvEdAction("revert"); return; }
  if (d.act === "srvEdDefault") { srvEdAction("default"); return; }
  if (d.act === "errPage") { const p = parseInt(d.page); if (!isNaN(p)) { errPage = p; paintErrors(); } return; }
  if (d.act === "gotoHelper") { const p = parseInt(d.step); if (!isNaN(p)) gotoHelperStep(p); return; }
  if (d.act === "gsCopyLink") { gsCopyLink(d.url, el); return; }
  if (d.act === "gsCreator") { showSub("creator"); return; }
  if (d.act === "pgJump") { pgJump(d.t); return; }
  if (d.act === "paramGuide") {
    showTab("helper"); showUgSub("params");
    setTimeout(function() { pgJump(d.t); }, 120);
    return;
  }
  if (d.act === "statsToggle") {
    const on = !(statsData && statsData.monitoring);
    post("/api/settings", { statsMonitoring: on }).then(() => renderStats());
    return;
  }
  if (d.act === "statsReset") {
    uiConfirm("Reset all collected statistics? This clears the running figures for every server and provider.", { okLabel: "Reset", title: "Reset Statistics" }).then(ok => {
      if (!ok) return;
      post("/api/stats-reset", {}).then(() => renderStats());
    });
    return;
  }
  if (d.act === "sweepLaunchers") {
    (async () => {
      const out = $("sweepout");
      if (out) out.textContent = "reading every .ps1 in that folder...";
      const r = await post("/api/sweep-launchers", {});
      if (!out) return;
      if (r.error) { out.innerHTML = '<span style="color:var(--err)">' + esc(r.error) + '</span>'; return; }
      const sw = (state.settings && state.settings.launcherSweep) || {};
      let h = r.swept + " launcher(s) read, " + r.flagged + " worth a look.";
      Object.keys(sw).forEach(function(fn) {
        const v = sw[fn] || {};
        if (!(v.findings || []).length) return;
        h += String.fromCharCode(10) + esc(fn) + ":";
        (v.findings || []).forEach(function(f) {
          h += String.fromCharCode(10) + "   line " + f.at + "  " + esc(f.why) + "  (" + esc(f.saw) + ")";
        });
      });
      h += String.fromCharCode(10) + String.fromCharCode(10)
         + "A clean sweep means nothing alarming was found, not that a file is safe: "
         + "PowerShell can be written to hide what it does. Only run launchers you wrote or trust.";
      out.innerHTML = '<span style="color:' + (r.flagged ? "var(--warn)" : "var(--ok)") + '">' + h + '</span>';
      await load();
    })();
    return;
  }
  if (d.act === "provSampResetAll") {
    (async () => {
      const all = (state.routing || []).reduce(function(a, s) { return a.concat(s.providers || []); },
                                               (state.unallocated || []).slice());
      const forced = all.filter(function(p) { return Object.keys(p.samplerOverrides || {}).length; });
      if (!forced.length) { uiAlert("No provider has a sampler value forced on it."); return; }
      if (!await uiConfirm("Clear every forced sampler value on " + forced.length
                           + " provider(s)? Nothing else about them is changed.")) return;
      for (const p of forced) {
        const r = await post("/api/provider-sampler", { id: p.id, clearAll: true });
        if (r && r.error) { uiAlert(r.error); break; }
      }
      await load(); renderCurrent(true);
    })();
    return;
  }
  if (d.act === "provSampRevert") {
    (async () => {
      const r = await post("/api/provider-sampler", { id: d.id, clearAll: true });
      if (r && r.error) { uiAlert(r.error); }
      await load(); renderCurrent(true);
    })();
    return;
  }
  if (d.act === "helperGo") {
    const fr = (state.settings && state.settings.helperForceReset) || [];
    const stepIdx = parseInt(el.dataset.step);
    if (fr.length && !isNaN(stepIdx) && fr.includes(stepIdx)) {
      post("/api/helper-unforce", { step: stepIdx }).then(async () => { await load(); renderHelper(); });
    }
    if (stepIdx === stepAt("launched")) {
      helperGo(el.dataset.page, "");                 // no highlight; the button speaks for itself
      setTimeout(launchDemo, 160);
    } else {
      helperGo(el.dataset.page, el.dataset.el || "");
    }
    return;
  }
  if (d.act === "dbgRec") { traceToggle(); return; }
  if (d.act === "dbgClear") { traceLog = []; traceDraw(); return; }
  if (d.act === "dbgCopy" || d.act === "dbgSave") {
    const save = d.act === "dbgSave";
    (async () => {
      const NL = String.fromCharCode(10);
      const r = await post("/api/debug-report", {});
      const txt = (r && r.text ? r.text + NL : "") + traceText();
      if (save) {
        const a = document.createElement("a");
        a.href = URL.createObjectURL(new Blob([txt], { type: "text/plain" }));
        a.download = "pandorumllm-trace.txt";
        a.click();
        setTimeout(function() { URL.revokeObjectURL(a.href); }, 2000);
      } else {
        await navigator.clipboard.writeText(txt);
        el.textContent = "Copied"; setTimeout(function() { el.textContent = "Copy"; }, 1400);
      }
    })();
    return;
  }
  if (d.act === "helperSkip") {
    const st2 = parseInt(el.dataset.step), on = !helperSkipped().includes(st2);
    post("/api/helper-skip", { step: st2, on: on }).then(async () => { await load(); renderHelper(); });
    return;
  }
  if (d.act === "profSaveOver") {
    const n = window.__profPick;
    if (!n) { netLog("pick a profile first, or use New"); return; }
    post("/api/profile-save", { name: n }).then(async r => {
      recoMsg = r.error ? ("⚠ " + r.error) : ("✅ profile saved: " + n);
      window.__profOpen = false;
      await load(); renderCurrent(true); paintProfiles();
    });
    return;
  }
  if (d.act === "profSave") {
    uiPrompt("Enter a name for this profile:", "", "Save Profile").then(n => {
      if (!(n && n.trim())) return;
      post("/api/profile-save", { name: n.trim() }).then(async r => {
        recoMsg = r.error ? ("⚠ " + r.error) : ("✅ profile saved: " + n.trim());
        if (!r.error) { window.__profPick = n.trim(); window.__profOpen = false; }
        await load(); renderCurrent(true); paintProfiles();
      });
    });
    return;
  }
  if (d.act === "profDel") {
    const sel = document.querySelector("select.prof-sel"), n = (sel && sel.value) || window.__profPick;
    if (!n) { netLog("pick a profile in the dropdown first"); return; }
    uiConfirm("Delete profile " + String.fromCharCode(34) + n + String.fromCharCode(34) + "?", { okLabel: "Delete", title: "Delete Profile" }).then(ok => {
      if (!ok) return;
      post("/api/profile-delete", { name: n }).then(async r => {
        recoMsg = r.error ? ("⚠ " + r.error) : ("✅ profile deleted: " + n);
        window.__profPick = ""; window.__profOpen = false;
        await load(); renderCurrent(true); paintProfiles();
      });
    });
    return;
  }
  if (d.act === "themeSave") {
    uiPrompt("Name this preset:", "", "Save as preset").then(function(n) {
      if (!(n && n.trim())) return;
      const own = Object.assign({}, (state.settings && state.settings.customThemes) || {});
      own[n.trim()] = currentVars();
      state.settings.customThemes = own;
      post("/api/settings", { customThemes: own, themeName: n.trim() }).then(function() {
        load().then(renderCustom);
      });
    });
    return;
  }
  if (d.act === "themeDel") {
    const name = el.dataset.name;
    const box = el.closest(".themecard");
    if (!box) return;
    box.classList.add("themegone");               // pulse red, then fade out over a second
    setTimeout(function() {
      const own = Object.assign({}, (state.settings && state.settings.customThemes) || {});
      delete own[name];
      state.settings.customThemes = own;
      post("/api/settings", { customThemes: own }).then(function() { load().then(renderCustom); });
    }, 1000);
    return;
  }
  if (d.act === "themePick") {
    const name = el.dataset.name;
    const own = (state.settings && state.settings.customThemes) || {};
    applyTheme(own[name] ? Object.assign({}, THEMES.OpenRouter, own[name]) : THEMES[name]);
    // move the marker straight away; the save can catch up on its own
    document.querySelectorAll(".themecard").forEach(function(c) {
      c.classList.toggle("on", c.dataset.name === name);
    });
    if (state && state.settings) state.settings.themeName = name;
    const vars = own[name] ? Object.assign({}, THEMES.OpenRouter, own[name]) : THEMES[name];
    post("/api/settings", { themeName: name, themeVars: vars }).then(function() { load(); });
    return;
  }
  if (d.act === "helperManual") {
    const on = !(state && state.settings && state.settings.helperManualSN);
    post("/api/helper-manual", { on: on }).then(async () => { await load(); renderHelper(); });
    return;
  }

  if (d.act === "sampToggle") { crSampToggle(d.tid, d.sid); return; }
  if (d.act === "crValidate") { crValidate(d.tid); return; }
  if (d.act === "provStat") {
    window.__provStatPid = d.pid;
    const sp = $("stpane-provider"); if (sp) sp.innerHTML = renderProviderStats();
    return;
  }
  if (d.act === "ttsPick") {
    const f = ttsFields().find(x => x[0] === d.k);
    if (f && f[2] && f[2] !== "folder") pickTtsFile(f[0], f[2]);
    return;
  }
  if (d.act === "ttsPickDir") { pickTtsFolder(d.k); return; }
  if (d.act === "higgsInstall") { higgsInstall(); return; }
  if (d.act === "termStamps") {
    termStampsToggle(ev.target.dataset.kind || "dashboard");
    return;
  }
  if (d.act === "termInsTts") { termToggle("termInsTts", "on", "off"); return; }
  if (d.act === "higgsCancel") { higgsCancel(); return; }
  if (d.act === "errClear") {
    if (!confirm("Clear all collected issues and the error log for this session?")) return;
    post("/api/errors-clear", {}).then(async () => {
      errData = null; errPage = 1;
      await renderErrors();
    });
    return;
  }
  if (d.act === "higgsAdopt") {
    post("/api/higgs-adopt", {}).then(async r => {
      if (r && r.error) { uiAlert(r.error); return; }
      ttsModels = null;
      await load(); renderTts();
    });
    return;
  }
  if (d.act === "higgsDismiss") {
    post("/api/higgs-install", { action: "dismiss" }).then(async () => {
      await load(); renderTts();
    });
    return;
  }
  if (d.act === "acppCheck") {
    const ACPP_MSG = "#f2c14e";        // one yellow for the whole report
    const tint = (c, s) => '<span style="color:' + c + '">' + esc(s) + '</span>';
    ttsAcppMsg = tint(ACPP_MSG, "checking github.com..."); renderTts();
    post("/api/acpp-update", {}).then(r => {
      if (!r || r.error) ttsAcppMsg = tint("#ff5d5d", (r && r.error) || "no answer");
      else if (!r.exe) ttsAcppMsg = tint(ACPP_MSG,
               "newest release is " + r.tag + " - no server found in the folder above");
      else if (r.local && r.tag.indexOf(r.local) >= 0)
        ttsAcppMsg = tint(ACPP_MSG, "up to date (yours: " + r.local + ", newest: " + r.tag + ")");
      else if (r.local) ttsAcppMsg = tint(ACPP_MSG,
               "a newer build is out: " + r.tag + " (yours: " + r.local + ")");
      else ttsAcppMsg = tint(ACPP_MSG, "newest release is " + r.tag
               + (r.published ? (" (" + r.published + ")") : ""));
      renderTts();
    });
    return;
  }
  if (d.act === "ttsModelRescan") {
    const h = $("tts-mdl"); if (h) h.textContent = "scanning\u2026";
    ttsLoadModels(true).then(() => renderTts());
    return;
  }
  if (d.act === "ttsImport") { _pickField = "__ttsimport"; _pickPrefix = "tts-"; _pickExts = [".bat", ".cmd", ".ps1"]; browseTo(""); return; }
  if (d.act === "ttsStart" || d.act === "ttsStop") { ttsServer(d.act === "ttsStart" ? "start" : "stop"); return; }
  if (d.act === "ttsOpenDir") { openFolder("launcherDir"); return; }
  if (d.act === "ttsGen") { ttsLauncher(false); return; }
  if (d.act === "ttsSave") { ttsLauncher(true); return; }
  if (d.act === "termScaleMode") { setTermScaleMode(d.mode, d.kind); return; }
  if (d.act === "termSizeReset") {
    const k = d.kind;
    if (!k || termScales[k].mode !== "manual") return;
    termScales[k].size = 12;                       // the shipped default
    post("/api/settings", { termScales: termScales });
    applyTermScale(k);
    syncTermScaleUI();
    return;
  }
  if (d.act === "logView") { viewLog(d.f); return; }
  if (d.act === "helperCheck") {
    const now = "[" + new Date().toTimeString().slice(0, 8) + "] ";
    const lines = [];
    lines.push(now + "\u2500\u2500 Completion status check \u2500\u2500");
    const sset = state.settings || {};
    const sk = (sset.helperSkipped || []);
    const forced = (sset.helperForceReset || []);
    const manual = !!sset.helperManualSN;
    // the steps are the single list of what has to be done - ask them
    let done = 0;
    const checks = HELPER_STEPS.map(function(s, i){
      const skipped = sk.indexOf(i) >= 0;
      const isForced = forced.indexOf(i) >= 0;
      const real = !!s.ok(state);
      const ok = !isForced && (real || skipped || manualCovers(manual, i));
      return [s.label, ok, skipped && !real, isForced];
    });
    checks.forEach(function(c) {
      if (c[1]) done++;
      const mark = c[1] ? (c[2] ? "\u2705" : "\u2705") : "\u2B1C";
      const note = c[2] ? " (skipped)" : "";
      lines.push("   " + mark + " " + c[0] + note);
    });
    const gpus = (state.gpus || []).filter(g => g.enabled !== false && g.uuid).length;
    const provs = (state.routing || []).reduce(function(a, s){ return a + ((s.providers || []).filter(p => p.enabled !== false).length); }, 0);
    const serving = (state.slots || []).filter(x => x.status && x.status.state === "serving").length;
    lines.push("   \u2022 " + gpus + " GPU(s) enabled, " + provs + " provider(s) active, " + serving + " server(s) serving");
    lines.push("   \u2139 providers.yaml PLACEMENT into your Modlist is manual - the panel generates the file but cannot verify you copied it into the SkyrimNet config folder.");
    lines.push(now + done + " / " + checks.length + " automated checks complete.");
    window.__helperLines = window.__helperLines.concat(lines);
    if (window.__helperLines.length > 80) window.__helperLines = window.__helperLines.slice(-80);
    renderHelper();
    const log = document.getElementById("helper-log"); if (log) log.scrollTop = log.scrollHeight;
    return;
  }
  if (d.act === "wrapToggle") {
    const tgt = document.getElementById(d.tgt);
    if (tgt) {
      const on = tgt.classList.toggle("wrap");
      const inner = tgt.querySelector(".pswrap"); if (inner) inner.classList.toggle("wrap", on);
      const lbl = document.getElementById("wraplbl-" + d.tgt); if (lbl) lbl.textContent = on ? "on" : "off";
    }
    return;
  }
  if (d.act === "gotoProv") {
    showTab("network");
    setTimeout(function() { netTrace("prov", d.id); }, 140);
    return;
  }
  if (d.act === "gotoNet") {
    showTab("network");
    setTimeout(function() { netTrace("srv", d.id); }, 140);   // wait for the pane to draw
    return;
  }
  if (d.act === "restoreSrv") {
    uiConfirm("Restore the shipped servers with their default parameters? Providers stay, moved to the unallocated row.").then(function(ok) {
      if (!ok) return;
      post("/api/restore-servers", {}).then(async function(r) {
        if (r.error) { uiAlert(r.error); return; }
        await load(); renderCurrent(true);
      });
    });
    return;
  }
  if (d.act === "restoreProv") {
    uiConfirm("This resets the shipped default providers back to their original state (title, port, priority, thinking, On/Off, and which server they sit on)." + String.fromCharCode(10) + String.fromCharCode(10) + "Any custom providers you added are kept as-is.", { okLabel: "Restore", title: "Restore Default Providers" }).then(ok => {
      if (!ok) return;
      post("/api/provider-restore-defaults", {}).then(async r => {
        if (r && r.error) { uiAlert(r.error); return; }
        await load(); renderCurrent(true);
      });
    });
    return;
  }
  if (d.act === "helperRevert") {
    post("/api/helper-revert", {}).then(async r => {
      if (r && r.error) { uiAlert(r.error); return; }
      await load(); renderHelper();
    });
    return;
  }
  if (d.act === "helperReset") {
    post("/api/helper-reset", {}).then(async () => { window.__helperLines = []; window.__helperPrev = {}; await load(); renderHelper(); });
    return;
  }
  if (d.act === "fullWin") { toggleFullWin(); return; }
  if (d.act === "peerSave") {
    const el = $("peer-addr");
    post("/api/settings", { peerAddr: el ? el.value.trim() : "" }).then(async function() {
      await load(); renderRouting(true);
    });
    return;
  }
  if (d.act === "provPower") { provEdit(d.id, { enabled: el.classList.contains("off") }); return; }
  if (d.act === "verClick") { verClick(); return; }
  if (d.act === "remJump") { showTab("perms"); showPsub("settings"); return; }
  if (d.act === "tmaxAdjust") {
    const c = d.tc ? $(d.tc) : el.closest(".tchrome");   // each terminal owns its menu; data-tc lets a stand-in button reach it
    if (c) c.classList.toggle("adjopen");
    if (document.activeElement && document.activeElement.blur) document.activeElement.blur();
    if (Object.values(tailMaxState).some(x=>x)) tmaxWake();
    return;
  }
  if (d.act === "tailMax") {
    const w = $("twrap-" + d.kind), b = $("tmaxbtn-" + d.kind);
    if (w) {
      if (!w.classList.contains("tmax")) {
        const te = d.kind === "split" ? $("tail-splitd") : $("tail-" + d.kind);
        tailNormalW[d.kind] = te ? te.clientWidth : 0;
      }
      const on = w.classList.toggle("tmax"); tailMaxState[d.kind] = on; if (!on) w.querySelectorAll(".adjopen").forEach(c => c.classList.remove("adjopen")); if (on && document.activeElement && document.activeElement.blur) document.activeElement.blur(); tmaxChrome(Object.values(tailMaxState).some(x=>x)); applyTermScale(); if (b) b.textContent = on ? "🗗 Normal Size" : "⛶ Full Window";
    }
    return;
  }
  if (d.act === "reco") {
    el.disabled = true;
    const back = el.textContent;
    el.textContent = "Working...";
    const done = function() { el.disabled = false; el.textContent = back; };
    post("/api/recommend", {}).then(async r => {
      recoMsg = r.error ? ("⚠ " + r.error) : ("✅ " + (r.summary || "done"));
      await load();
      done();
      renderCurrent(true);
    }).catch(e => {
      done();
      recoMsg = "request failed: " + e;
      renderCurrent(true);
    });
    return;
  }
  if (d.act === "yamlPick") { const f = $("yaml-file"); if (f) f.click(); return; }
  if (d.act === "yamlOpenNative") { yamlOpenNative(el); return; }
  if (d.act === "yamlGen") { yamlAction("/api/yaml-generate", el); return; }
  if (d.act === "yamlCreate") { yamlAction("/api/yaml-create", el); return; }
  if (d.act === "yamlBaseSave") { yamlBaseSave(el); return; }
  if (d.act === "yamlBaseReset") { yamlBaseReset(el); return; }
  if (d.act === "detectGpus") detectGpus(el);
  else if (d.act === "ipDetect") detectIp(el);
  else if (d.act === "ipOne") {
    (async () => {
      const ip = ($("ip-panel") && $("ip-panel").value.trim()) || "";
      if (!ip) { ipNote("enter this PC's IP in the field, then press 1 PC Setup", true); return; }
      applyPcMode(true);
      const r = await post("/api/settings", { panelIp: ip, remoteIp: ip, onePC: true });
      if (r && r.error) { uiAlert(r.error); return; }
      await load(); renderCurrent(true);
      ipNote("1 PC setup: SkyrimNet and PandorumLLM share this machine (" + ip + ")");
    })();
  }
  else if (d.act === "ipTwo") {
    (async () => {
      // switch to 2-PC mode only; do NOT auto-detect or auto-fill any IP - the user enters it manually
      const ip = ($("ip-panel") && $("ip-panel").value.trim()) || "";
      applyPcMode(false);
      const r = await post("/api/settings", { onePC: false });
      if (r && r.error) { uiAlert(r.error); return; }
      await load(); renderCurrent(true);
      const inp = $("ip-remote");
      if (inp) flashTargets("#ip-remote");
    })();
  }
  else if (d.act === "ipSet") setIp(d.key, d.input, el);
  else if (d.act === "ipUse") {
    const i = $("ip-panel");
    if (i) i.value = d.ip;
    const box = $("ip-sugg");
    if (box) box.innerHTML = "";                 // the list has done its job
  }
  else if (d.act === "provDel") provRemove(d.id);
  else if (d.act === "provAdd") provAdd(d.id);
  else if (d.act === "slotEdit") startEditR(d.id, d.field);
  else if (d.act === "inspFolder") { openFolder("launcherDir"); }
  else if (d.act === "inspFile") {
    const sel = $("insp-sel");
    if (sel && sel.value) post("/api/open-file", { path: sel.value }).then(r => { if (r.error) uiAlert(r.error); });
  }

});
function startEditR(sid, field) {
  const span = $("r"+field+"-"+sid);
  const s = state.routing.find(x => x.id === sid);
  if (!span || !s) return;
  const inp = document.createElement("input");
  inp.className = "edit";
  inp.value = field === "label" ? (s.label||"") : (s.port||"");
  if (field !== "label") inp.style.maxWidth = "100px";
  span.replaceWith(inp); inp.focus(); inp.select();
  let done = false;
  const fin = save => {
    if (done) return; done = true;
    if (save && String(inp.value).trim() !== "") {
      const b = { slot: sid }; b[field] = inp.value;
      post("/api/edit", b).then(r => { if (r.error) uiAlert(r.error); load().then(renderCurrent); });
    } else renderCurrent(true);
  };
  inp.addEventListener("keydown", e => { if (e.key === "Enter") fin(true); if (e.key === "Escape") fin(false); });
  inp.addEventListener("blur", () => fin(true));
}
async function provAdd(sid) { const r = await post("/api/provider-add", { slot: sid }); if (r.error) uiAlert(r.error); await load(); renderCurrent(true); }
async function provRemove(id) {
  if (!await uiConfirm("Remove this added provider?")) return;
  const r = await post("/api/provider-remove", { id }); if (r.error) uiAlert(r.error); await load(); renderCurrent(true);
}
async function provEdit(id, patch) {
  const r = await post("/api/provider-edit", { id, ...patch }); if (r.error) uiAlert(r.error);
  await load(); renderCurrent(true);
}

/* ---------- setup path buttons ---------- */
// ---- in-UI directory picker (folders only, jailed by the server) ----
let _pickField = null, _pickCur = "";
let _pickPrefix = "set-", _pickExts = null;
function pickPath(k) {
  _pickField = k; _pickPrefix = "set-"; _pickExts = null;
  const start = ($("set-"+k) && $("set-"+k).value) || "";
  browseTo(start);
}
function pickTtsFolder(k) {
  _pickField = k; _pickPrefix = "tts-"; _pickExts = null;   // null exts = folders only
  const cur = ($("tts-"+k) && $("tts-"+k).value) || "";
  browseTo(cur);
}
// file mode: same browser, plus files of the given types. Clicking one picks it.
function pickTtsFile(k, exts) {
  _pickField = k; _pickPrefix = "tts-"; _pickExts = exts;
  const cur = ($("tts-"+k) && $("tts-"+k).value) || "";
  browseTo(cur ? cur.replace(/[\\/][^\\/]*$/, "") : "");
}
async function browseTo(path) {
  let r = await post("/api/browse-dirs", { path: path || "", exts: _pickExts || [] });
  if (r && r.error && path) {          // a stale or half-typed path: fall back to the drives
    r = await post("/api/browse-dirs", { path: "", exts: _pickExts || [] });
  }
  if (r && r.error) { uiAlert(r.error); return; }
  _pickCur = r.path || "";
  let rows = "";
  if (!r.path) {
    (r.drives || []).forEach(d => { rows += '<div class="pickrow" data-nav="' + esc(d) + '"><span style="color:var(--dim)">' + ICO.drive + '</span> ' + esc(d) + '</div>'; });
  } else {
    if (r.parent !== null && r.parent !== undefined)
      rows += '<div class="pickrow" data-nav="' + esc(r.parent) + '"><span style="color:var(--dim)">\u2191</span> .. (up)</div>';
    if (!(r.dirs || []).length) rows += '<div class="hint" style="padding:8px">(no subfolders here)</div>';
    const base = r.path.replace(/[\\/]+$/, "");
    (r.dirs || []).forEach(d => {
      const full = base + String.fromCharCode(92) + d;
      rows += '<div class="pickrow" data-nav="' + esc(full) + '"><span style="color:#d9b04a">' + ICO.folder + '</span> ' + esc(d) + '</div>';
    });
    (r.files || []).forEach(f => {
      const full = base + String.fromCharCode(92) + f.name;
      rows += '<div class="pickrow" data-file="' + esc(full) + '"><span style="color:var(--dim)">' + ICO.file
            + '</span> ' + esc(f.name) + ' <span class="hint" style="width:auto;margin-left:6px">' + esc(f.size) + '</span></div>';
    });
    if (_pickExts && !(r.files || []).length && !(r.dirs || []).length)
      rows += '<div class="hint" style="padding:8px">(nothing of that type here)</div>';
  }
  const fileMode = !!_pickExts;
  let html = '<h2 style="margin:0 0 4px">' + (fileMode ? 'Pick A File' : 'Pick A Folder') + '</h2>'
    + '<div class="hint" style="margin-bottom:8px">'
    + (fileMode
        ? ('Click a folder to open it, then click the file itself. Showing ' + _pickExts.join(" ") + ' only.')
        : 'Only folders are shown. Click to open a folder, then choose it below.')
    + ' Drag the bottom-right corner to resize.</div>'
    + '<div class="hint" style="word-break:break-all;margin-bottom:8px"><b>' + (r.path ? esc(r.path) : "(this PC - pick a drive)") + '</b></div>'
    + '<div id="pickrows" style="flex:1;min-height:120px;overflow:auto;border:1px solid var(--edge);border-radius:8px;padding:6px;background:#0f1319">' + rows + '</div>'
    + '<div class="row" style="justify-content:space-between;gap:8px;margin-top:14px">'
    + '<button class="stop" onclick="browseTo(' + String.fromCharCode(39) + String.fromCharCode(39) + ')"' + (r.path ? '' : ' disabled') + '>\u2B05 Drives</button>'
    + '<div class="row" style="gap:8px">'
    + '<button class="stop" onclick="closeModal()">Cancel</button>'
    + (r.path && !fileMode ? '<button onclick="pickChoose()">\u2713 Choose This Folder</button>' : '')
    + '</div></div>';
  showModal(html, true);
  const rowsEl = document.getElementById("pickrows");
  if (rowsEl) rowsEl.addEventListener("click", ev => {
    const frow = ev.target.closest("[data-file]");
    if (frow) { pickFileChoose(frow.getAttribute("data-file")); return; }
    const row = ev.target.closest("[data-nav]");
    if (row) browseTo(row.getAttribute("data-nav"));
  });
}
async function pickFileChoose(full) {
  if (_pickField === "__ttsimport") {
    closeModal();
    const r = await post("/api/tts-import", { path: full });
    const m = $("tts-imp");
    if (r && r.error) { if (m) m.textContent = r.error; return; }
    await load(); renderTts();
    const got = Object.keys(r.found || {});
    const msg = $("tts-imp");
    if (msg) msg.textContent = got.length
      ? ("filled " + got.length + " of 6 from " + full.split(String.fromCharCode(92)).pop())
      : "nothing recognised in that file";
    return;
  }
  const el = $(_pickPrefix + _pickField);
  if (el) el.value = full;
  closeModal();
  const body = {}; body[_pickField] = full;
  const r = await post("/api/settings", body);
  if (r && r.error) { uiAlert(r.error); return; }
  await load();
  if (_pickPrefix === "tts-") renderTts(); else renderSetup();
}
async function pickChoose() {
  if (_pickField && _pickCur) {
    if (_pickPrefix === "tts-") {                 // TTS page: folder fields live there too
      const t = $("tts-" + _pickField); if (t) t.value = _pickCur;
      closeModal();
      const p = {}; p[_pickField] = _pickCur;
      const rr = await post("/api/settings", p);
      if (rr && rr.error) { uiAlert(rr.error); return; }
      await load(); renderTts();
      return;
    }
    const el = $("set-"+_pickField); if (el) el.value = _pickCur;
    // save straight away so folder validation (e.g. llama.cpp exe check) runs immediately
    const body = {}; body[_pickField] = _pickCur;
    closeModal();
    const r = await post("/api/settings", body);
    if (r && r.error) { uiAlert(r.error); return; }
    if (_pickField === "modelsDir") { models = null; await loadModels(true); }
    await load(); renderSetup(); showSetOk();
  wireLlamaCheck(); recheckPaths();
    return;
  }
  closeModal();
}
// ---- in-UI folder viewer (extension-filtered, jailed) ----
const FOLDER_KEY = { modelsDir:"models", launcherDir:"launcher", outputDir:"output", logDir:"log", yamlOutDir:"yaml" };
async function openFolder(k) {
  const which = FOLDER_KEY[k];
  if (!which) { uiAlert("This folder has no viewer."); return; }
  const r = await post("/api/folder-view", { which });
  if (r && r.error) { uiAlert(r.error); return; }
  const extLabel = { models:".gguf", launcher:".ps1 and .bat", output:".ps1 and .bat", log:".log", yaml:".yaml" }[which] || "";
  let html = '<h2 style="margin:0 0 4px">Folder Contents</h2>'
    + '<div class="hint" style="margin-bottom:8px">Showing only ' + extLabel + ' files' + (r.capped ? ' (first ' + r.count + ')' : '') + ' - ' + r.count + ' file(s).</div>'
    + '<div style="max-height:48vh;overflow:auto;border:1px solid var(--edge);border-radius:8px;background:#0f1319">';
  if (!(r.files || []).length) html += '<div class="hint" style="padding:10px">(no ' + extLabel + ' files found here)</div>';
  (r.files || []).forEach(f => {
    html += '<div style="display:flex;justify-content:space-between;gap:10px;padding:7px 11px;border-bottom:1px solid #1a1f27">'
      + '<span style="word-break:break-all"><span style="color:var(--dim)">' + ICO.file + '</span> ' + esc(f.rel) + '</span><span class="hint" style="flex-shrink:0">' + esc(f.size) + '</span></div>';
  });
  html += '</div><div class="row" style="justify-content:flex-end;margin-top:14px"><button class="stop" onclick="closeModal()">Close</button></div>';
  showModal(html);
}

/* ---------- launcher creator ---------- */
function edHtml(id, content) {
  return '<div class="row" style="justify-content:flex-end;margin-bottom:6px"><button class="stop" data-act="wrapToggle" data-tgt="edwrap-'+id+'" title="toggle text wrapping">\u21A9 Wrap: <span id="wraplbl-edwrap-'+id+'">off</span></button></div>'
    + '<div class="ed" id="edwrap-'+id+'"><pre class="gut" id="gut-'+id+'"></pre>'
    + '<div class="pswrap"><pre class="pshl" id="hl-'+id+'"></pre><textarea class="psta" wrap="off" id="ta-'+id+'" spellcheck="false" oninput="gut(\\''+id+'\\')" onscroll="gsync(\\''+id+'\\')"></textarea></div></div>';
}
function gut(id) {
  const ta = $("ta-"+id), g = $("gut-"+id);
  if (!ta || !g) return;
  const n = ta.value.split("\\n").length;
  g.textContent = Array.from({length:n}, (_,i)=>i+1).join("\\n");
  const h = $("hl-"+id);
  if (h) h.innerHTML = psHl(ta.value) + String.fromCharCode(10);
  gsync(id);
}
function gsync(id) {
  const ta = $("ta-"+id), g = $("gut-"+id), h = $("hl-"+id);
  if (ta && g) g.scrollTop = ta.scrollTop;
  if (ta && h) { h.scrollTop = ta.scrollTop; h.scrollLeft = ta.scrollLeft; }
}
const PS_KW = new Set("if,else,elseif,foreach,for,while,function,param,return,try,catch,finally,switch,break,continue,in,do,until,throw,begin,process,end,elseif".split(","));
function psHl(src) {
  const NL = String.fromCharCode(10);
  const master = new RegExp('GPU-[0-9a-fA-F][0-9a-fA-F-]{5,}|#[^' + NL + ']*|"[^"' + NL + ']*"|' + "'[^'" + NL + "]*'|" + '[$][{]?[A-Za-z_][A-Za-z0-9_:]*[}]?|[[][A-Za-z][A-Za-z0-9.]*[]]|[0-9]+([.][0-9]+)?|[A-Za-z]+-[A-Za-z][A-Za-z0-9-]*|[A-Za-z_][A-Za-z0-9_]*', "g");
  let out = "", last = 0, m;
  while ((m = master.exec(src)) !== null) {
    out += esc(src.slice(last, m.index));
    const s = m[0], c0 = s[0];
    let cls = "";
    if (s.slice(0, 4) === "GPU-") cls = "hs hb";
    else if (c0 === "#") cls = "hc";
    else if (c0 === String.fromCharCode(34) || c0 === String.fromCharCode(39)) cls = "hs";
    else if (c0 === "$") cls = "hv";
    else if (c0 === "[") cls = "ht";
    else if (c0 >= "0" && c0 <= "9") cls = "hn";
    else if (s.indexOf("-") > 0) cls = "hf";
    else if (PS_KW.has(s.toLowerCase())) cls = "hk";
    let body = esc(s);
    if (cls === "hs" && s.indexOf("GPU-") >= 0)
      body = body.replace(new RegExp("GPU-[0-9a-fA-F][0-9a-fA-F-]{5,}", "g"), mm2 => '<span class="hb">' + mm2 + '</span>');
    out += cls ? '<span class="' + cls + '">' + body + '</span>' : body;
    last = m.index + s.length;
  }
  return out + esc(src.slice(last));
}
function mSel(id, kind, val, mandatory) {
  const all = models || [];
  let o = mandatory ? '<option value="">&#8212; pick a model (mandatory) &#8212;</option>'
                    : '<option value=""'+((!val||val==="Disabled"||val==="N/A")?" selected":"")+'>Disabled</option>';
  // what belongs in this picker, judged by what each file is rather than its name
  const want = { model: "main", vision: "vision", draft: "draft" }[kind] || "main";
  const NAME = { vision: "vision projector", draft: "draft model" };
  o += all.map(function(m) {
    const k = m.kind || "main";
    const fits = k === want;                   // only a real drafter belongs there
    const tag = NAME[k] ? "  [" + NAME[k] + "]" : "";
    return '<option value="'+esc(m.path)+'" style="color:'+(fits ? "var(--ok)" : "var(--err)")+'"'
         + (m.path===val?" selected":"")+'>'+esc(m.name)+esc(tag)+'</option>';
  }).join("");
  if (!all.length) o += '<option value="" disabled>(no models found - set the models folder in Folder Setup)</option>';
  return '<select id="'+id+'" style="max-width:420px">'+o+'</select>';
}
async function loadModels(force) {
  if (models && models.length && !force) return models;
  try {
    const r = await (await fetch("/api/models")).json();
    models = (r && r.models) || [];
  } catch (e) { models = models || []; }
  return models;
}
// Sampler Guide cross-references: stable card ids, in-text links, and the jump/flash action.
const PG_REFS = [
  ["dynamic temperature", "Dynamic temperature"],
  ["kv cache quantization", "KV cache quantization"],
  ["kv cache offload", "KV cache (offload)"],
  ["prompt batching", "Prompt batching"],
  ["flash attention", "Flash attention"],
  ["context size", "Context size"],
  ["concurrency", "Concurrency (parallel slots)"],
  ["gpu layers", "GPU layers"],
  ["kv cache", "KV cache (offload)"],
  ["adaptive-p", "Adaptive-P (adaptive min-p)"],
  ["adaptive_p", "Adaptive-P (adaptive min-p)"],
  ["temperature", "Temperature"],
  ["mirostat", "Mirostat"],
  ["top_n_sigma", "N-sigma"],
  ["n-sigma", "N-sigma"],
  ["typical", "Typical (typ_p)"],
  ["typ_p", "Typical (typ_p)"],
  ["min-p", "Min-p"],
  ["min_p", "Min-p"],
  ["top-p", "Top-p (nucleus)"],
  ["top-k", "Top-k"],
  ["xtc", "XTC (Exclude Top Choices)"],
  ["dry", "DRY penalty"]
].sort(function(a, b) { return b[0].length - a[0].length; });
function pgSlug(name) {
  let s = "";
  for (let i = 0; i < name.length; i++) {
    const c = name.charAt(i).toLowerCase();
    if ((c >= "a" && c <= "z") || (c >= "0" && c <= "9")) s += c;
    else if (s && s.charAt(s.length - 1) !== "-") s += "-";
  }
  while (s && s.charAt(s.length - 1) === "-") s = s.slice(0, -1);
  return "pg-" + s;
}
function pgWordCh(ch) {
  return (ch >= "a" && ch <= "z") || (ch >= "A" && ch <= "Z") || (ch >= "0" && ch <= "9") || ch === "-" || ch === "_";
}
function pgLink(html, selfId) {
  const s = String(html || "");
  let out = "", i = 0;
  while (i < s.length) {
    const c = s.charAt(i);
    if (c === "<") {                                    // copy markup through untouched
      const j = s.indexOf(">", i);
      if (j < 0) { out += s.slice(i); break; }
      out += s.slice(i, j + 1); i = j + 1; continue;
    }
    let hit = null;
    for (let k = 0; k < PG_REFS.length; k++) {
      const a = PG_REFS[k][0], id = pgSlug(PG_REFS[k][1]);
      if (id === selfId) continue;                      // never link a card to itself
      if (s.slice(i, i + a.length).toLowerCase() !== a) continue;
      if (i > 0 && pgWordCh(s.charAt(i - 1))) continue; // whole-word only, so --top-p stays intact
      if (pgWordCh(s.charAt(i + a.length) || " ")) continue;
      hit = [a, id]; break;
    }
    if (hit) {
      out += '<span class="pg-ref" data-act="pgJump" data-t="' + hit[1] + '">' + s.slice(i, i + hit[0].length) + '</span>';
      i += hit[0].length;
    } else { out += c; i++; }
  }
  return out;
}
function pgJump(id) {
  const el = document.getElementById(id);
  if (!el) return;
  el.scrollIntoView({ behavior: "smooth", block: "center" });
  el.classList.remove("pg-hit");
  void el.offsetWidth;                                  // restart the flash
  el.classList.add("pg-hit");
  clearTimeout(window.__pgHitT);
  window.__pgHitT = setTimeout(function() { el.classList.remove("pg-hit"); }, 2200);
}
function renderParams() {
  const S = [
    { name:"Temperature", flag:"--temp N", def:"N = 0.0 - 2.0", lo:"0 = rigid", hi:"2 = wild",
      what:"The master creativity dial - how random each next-word choice is.",
      how:"Low values push the model toward its single most likely next word (safe, consistent, can loop). High values flatten the odds so rarer words get a chance (surprising, but can wander). With N-sigma active you can push it much higher without losing the plot.",
      sky:"Higher makes NPCs colourful but prone to rambling; lower keeps them steady but flat. <b>0.7 to 0.9</b> is a good roleplay range - go higher if you add N-sigma." },
    { name:"Top-p (nucleus)", flag:"--top-p N", def:"N = 0.0 - 1.0", lo:"0 = top word only", hi:"1 = off",
      what:"Keeps only the smallest group of words that together cover p of the probability.",
      how:"Trims the long tail of unlikely words. At 0.95 it samples from the words making up the top 95 percent of likelihood; 1.0 disables it. Runs late in the chain, after the other truncators.",
      sky:"Stops NPCs reaching for bizarre words while allowing variety. <b>0.9 to 0.95</b> keeps dialogue natural." },
    { name:"Min-p", flag:"--min-p N", def:"N = 0.0 - 1.0", lo:"0 = off", hi:"stricter",
      what:"Drops any word less likely than a set fraction of the top word.",
      how:"A relative floor: a word must be at least min-p times as likely as the best candidate to survive. 0.05 means roughly five percent as likely as the top pick. It adapts to the model confidence and pairs well with a higher temperature.",
      sky:"Prunes odd outliers while leaving room for creativity - a good partner to temperature for expressive but sane NPCs. <b>0.02 to 0.08</b> is a common range." },
    { name:"Top-k", flag:"--top-k N", def:"N = 0 - vocab size", lo:"1 = focused", hi:"0 = off",
      what:"Only ever consider the k most likely words.",
      how:"A hard cap on how many candidates are on the table. At 40 only the 40 highest-probability words can be chosen; 0 disables it. Coarser than min-p or top-p.",
      sky:"A gentle guardrail - a value near <b>40</b> rarely hurts and quietly blocks the truly unlikely choices. Many setups leave it off and lean on min-p instead." },
    { name:"DRY penalty", flag:"--dry-multiplier N", def:"N = 0.0 - 2.0", lo:"0 = off", hi:"stronger",
      what:"Don't Repeat Yourself - discourages repeating phrases the model already said.",
      how:"Scales a penalty against sequences that echo earlier output. 0 is off; raise it to break loops and stock phrases. Three companions tune it: <b>--dry-base</b> (how sharply the penalty grows), <b>--dry-allowed-length</b> (repeats allowed before it bites) and <b>--dry-penalty-last-n</b> (how far back it looks). Too high makes speech stilted.",
      sky:"Turn it up if NPCs start repeating lines over a long session - it keeps conversations from looping. A multiplier around <b>0.8</b> is a common starting point; only push higher if repetition persists." },
    { name:"N-sigma", flag:"--top-n-sigma N", def:"N = -1 to 5", lo:"tight", hi:"looser",
      what:"A newer, powerful filter that keeps only tokens within n standard deviations of the most likely one - working on the raw logits before softmax.",
      how:"It measures the spread (sigma) of the model logits and keeps the words whose score is within n times sigma of the top. The paper recommends n = 1.0; -1 disables it. Its headline property is temperature-invariance: the candidate set stays the same no matter how high temperature goes, so you get temperature-driven creativity without the usual slide into gibberish. It is widely regarded as one of the best general-purpose samplers.",
      sky:"This is the one that lets you crank temperature for wild, characterful NPC speech while staying coherent. If you want more variety than min-p and top-p give, add <b>--top-n-sigma 1.0</b> and raise temperature." }
  ];
  const RT = [
    { name:"Context size", flag:"--ctx-size N", range:"N = 2048 - model max",
      how:"How many tokens of history the model holds at once - the scene, character bios, memories and recent events SkyrimNet feeds it. Bigger remembers more but costs VRAM and can slow generation. Size it to your usual scene length and the VRAM you have spare." },
    { name:"GPU layers", flag:"--n-gpu-layers N", range:"N = 0 - model layer count",
      how:"How many model layers run on the GPU. Any N at or above the model's real layer count (99 is the usual shorthand) puts every layer on the GPU for maximum speed; 0 keeps them all on the CPU. Lower it only if VRAM runs out - the overflow moves to the CPU and slows down." },
    { name:"Flash attention", flag:"--flash-attn on|off", range:"on | off | auto",
      how:"A faster, more memory-efficient attention, especially at large context. On means quicker responses and less VRAM." },
    { name:"KV cache (offload)", flag:"--cache-ram N  --ctx-checkpoints N", range:"N = 0 or more (MiB / count)",
      how:"The KV cache holds the attention keys and values for every token in context (the scene, bios, memories and recent turns SkyrimNet sends). It grows with context and normally lives in VRAM next to the weights. <b>--cache-ram N</b> lets part of it spill to system RAM (N in MiB) so you can hold more context than VRAM alone allows, at slower access for the spilled part; <b>--ctx-checkpoints N</b> keeps N rollback points so context can be rewound cheaply. Setting both to 0 keeps the cache GPU-only with no RAM spill and no checkpoints - and the zeros must be explicit, or the server falls back to an 8192 MiB RAM cache. This flag is about <b>where</b> the cache lives; see KV cache quantization for making it smaller. Correlates with Context size (bigger context = bigger cache) and Concurrency (each parallel slot gets its own slice)." },
    { name:"KV cache quantization", flag:"--cache-type-k  --cache-type-v", range:"f16 | q8_0 | q4_0",
      how:"Separately from where the cache lives, you can shrink how big it is by storing the keys and values at lower precision. <b>--cache-type-k</b> and <b>--cache-type-v</b> set the datatype of the K and V caches - the default is f16; <b>q8_0</b> roughly halves KV memory and <b>q4_0</b> roughly quarters it, letting you hold far more context, or free VRAM for more GPU layers, at a small and usually minor quality cost. Quantized KV normally needs <b>Flash attention</b> on, and the V cache is more sensitive than K, so common frugal picks are q8_0 for both, or q8_0 for K with f16 for V. Pairs directly with Context size and KV cache offload - quantize first, then decide how much (if any) still needs to spill to RAM." },
    { name:"Concurrency (parallel slots)", flag:"--parallel N  --no-cont-batching", range:"N = 1 or more",
      how:"<b>--parallel N</b> is how many requests the server works on at once, and it is biased to <b>1</b> on purpose: with one slot every request gets the whole GPU and the entire KV cache, so a single Skyrim conversation gets the lowest latency. With N slots the context window and KV cache are split N ways and compute is shared, which only pays off when several clients hit the server together. <b>--no-cont-batching</b> turns off continuous batching (the scheduler that interleaves several in-flight requests token by token) - pointless with one slot, and it keeps timing simple and predictable. For a single-player SkyrimNet setup one slot is almost always right; raise --parallel and drop --no-cont-batching only if you serve several players or tools from the same server. Correlates with Context size and the KV cache - the per-slot share of both shrinks as --parallel grows." },
    { name:"Prompt batching", flag:"--batch-size N  --ubatch-size N", range:"ubatch <= batch",
      how:"These size <b>prefill</b> only - how the prompt is chewed through before the first token appears; they do not change generation speed. <b>--batch-size</b> (logical batch) is how many prompt tokens are submitted together; <b>--ubatch-size</b> (physical micro-batch) is how many are actually computed on the GPU at once, and it must be no larger than the batch size. Bigger values prefill long scenes faster but use more compute-buffer VRAM. On a tight VRAM budget lower ubatch; if prefill of big scenes feels slow and you have headroom, raise both. Independent of the KV cache and the samplers." },
    { name:"Threads / mmap / fit", flag:"--threads N  --no-mmap  --fit off", range:"N = 1 - CPU cores",
      how:"threads sets the CPU threads for parts that touch the CPU; --no-mmap loads weights straight into memory instead of memory-mapping the file; --fit off skips llama.cpp auto layer-fitting when you set the layer count yourself." },
    { name:"Generation cap", flag:"--n-predict N", range:"N = -1 (off) or 1 or more",
      how:"A server-side backstop so a runaway generation cannot hold the slot forever. A per-request max_tokens still overrides it." },
    { name:"Vision projector", flag:"--mmproj",
      how:"Enables image input for multimodal models; text-only servers use --no-mmproj." },
    { name:"GPU pinning", flag:"CUDA_VISIBLE_DEVICES",
      how:"Locks a server to one physical card so GPUs never swap across reboots. Pin by <b>UUID</b> (from nvidia-smi -L) for stability, or by <b>index</b> if your card order never changes." }
  ];
  const RE = [
    { name:"Reasoning on/off", flag:"--reasoning on|off", range:"on | off",
      how:"Turns the model hidden think-first pass on or off. Thinking sharpens complex decisions but adds latency, so it suits reasoning/utility roles more than fast back-and-forth dialogue." },
    { name:"Reasoning budget", flag:"--reasoning-budget N", range:"N = -1 (unlimited) or 0 or more",
      how:"Caps how many tokens the model may spend thinking before it must answer." },
    { name:"Budget message", flag:"--reasoning-budget-message",
      how:"The nudge injected if the thinking budget runs out, telling the model to stop and respond." },
    { name:"Reasoning format", flag:"--reasoning-format <fmt>", range:"deepseek | none | auto",
      how:"How the think block is delimited and parsed in the response (for example the deepseek format), so SkyrimNet and the proxy can separate the hidden reasoning from the spoken answer." }
  ];
  const SP = [
    { name:"Draft model", flag:"--spec-draft-model",
      how:"A small, fast instruct model proposes several tokens that the big model verifies in one pass, speeding up generation. Most useful where a small matching model can draft ahead; skip it on already-tiny models." },
    { name:"Spec type", flag:"--spec-type <type>", range:"draft-mtp | separate drafter",
      how:"Uses the model Multi-Token-Prediction head as the drafter rather than a fully separate model." },
    { name:"Draft n-max", flag:"--spec-draft-n-max N", range:"N = 1 - 16",
      how:"How many tokens the drafter proposes per step. More can speed things up if acceptance stays high." },
    { name:"Acceptance", flag:"draft acceptance %",
      how:"Whether spec-decode earns its place depends on how many drafted tokens the big model accepts; low acceptance wastes work. As a rule of thumb it is worth keeping above roughly <b>60 percent</b>, and usually costs more than it saves below about <b>35 percent</b> - the Statistics tab tracks this per server." }
  ];
  const ADP = [
    { name:"Dynamic temperature", flag:"--dynatemp-range / --dynatemp-exp", range:"range 0.0 - 1.0 (0 = off)",
      how:"Varies temperature per token by the model confidence: the applied value swings within [temp - range, temp + range] - lower when the distribution is flat (uncertain), higher when it is peaked. An adaptive alternative to a fixed temperature. Range 0 = off; the exponent shapes how sharply it swings.",
      fleet:"Off by default. In the Creator, the Dyn-temp card inserts both flags." },
    { name:"Typical (typ_p)", flag:"--typical N", range:"N = 0.0 - 1.0 (1.0 = off)",
      how:"Locally typical sampling: keeps tokens whose surprise is close to the distribution expected surprise, rather than simply the most probable ones. Promotes coherent yet varied text. 1.0 = off; it sits in the default chain but is inactive until lowered.",
      fleet:"In the default chain but off (1.0). The Creator Typical card adds it at a mild 0.95." },
    { name:"XTC (Exclude Top Choices)", flag:"--xtc-probability / --xtc-threshold", range:"probability 0.0 - 1.0 · threshold 0.0 - 0.5",
      how:"With a set probability it removes the most likely tokens (those above the threshold) except the least probable among them, nudging the model off cliches and repetition while keeping grammar intact. Probability 0 = off; the common creative setting is probability 0.5, threshold 0.1. Built for creative writing.",
      fleet:"In the default chain but off. The Creator XTC card adds both flags at the recommended values." },
    { name:"Adaptive-P (adaptive min-p)", flag:"--adaptive-target / --adaptive-decay", range:"target -1 (off) or 0.0 - 1.0",
      how:"The adaptive cousin of min-p and top-p - what you might picture as an adaptive min_p. It aims for a target probability mass and, via an exponential moving average of the tokens it recently picked, steers toward that target over time: if recent choices were more likely than intended it favours lower-probability tokens next, and vice versa. It selects the token itself, so it must be <b>last</b> in the chain. Target -1 = off; recommended target 0.55, decay 0.9, with only mild truncation (min-p) before it.",
      fleet:"Not in the default chain - add <b>adaptive_p</b> at the end of --samplers to use it. The Creator Adaptive-P card inserts both flags at the recommended values, and blocks adding it alongside Top-p, Top-k, Typical, N-sigma or XTC (only a mild Min-p belongs before it)." },
    { name:"Mirostat", flag:"--mirostat 0|1|2 / --mirostat-lr / --mirostat-ent", range:"mode 0 (off) | 1 | 2",
      how:"An older adaptive controller that targets a constant surprise (perplexity) level and adjusts as it generates. When on (mode 1 or 2) it <b>replaces</b> the top-k, top-p and typical stages and drives truncation itself; set the target entropy and a learning rate. 0 = off. Largely superseded by N-sigma, XTC and Adaptive-P, but still available.",
      fleet:"Off by default. If you enable it, set top-k 0, top-p 1.0 and min-p 0 so it controls sampling alone." }
  ];
  const sec = (a, b) => '<div class="pg-sec">' + a + '<span class="pg-sub">' + b + '</span></div>';
  const grid = arr => '<div class="pg-grid">' + arr.join("") + '</div>';
  const fleetBox = (p, sid) => p.fleet ? '<div class="pg-fleet"><b>Note:</b> ' + pgLink(p.fleet, sid) + '</div>' : '';
  const samplerCard = p => {
    const sid = pgSlug(p.name);
    return '<div class="pg-card" id="' + sid + '"><div class="pg-h"><span class="pg-name">' + esc(p.name) + '</span>'
      + '<span class="pg-flag">' + esc(p.flag) + '</span><span class="pg-def">' + esc(p.def) + '</span></div>'
      + '<div class="pg-what">' + pgLink(p.what, sid) + '</div>'
      + '<div class="pg-gauge"></div>'
      + '<div class="pg-lohi"><span>' + esc(p.lo) + '</span><span>' + esc(p.hi) + '</span></div>'
      + '<div class="pg-how">' + pgLink(p.how, sid) + '</div>'
      + '<div class="pg-sky">' + pgLink(p.sky, sid) + '</div>' + fleetBox(p, sid) + '</div>';
  };
  const infoCard = p => {
    const sid = pgSlug(p.name);
    return '<div class="pg-card" id="' + sid + '"><div class="pg-h"><span class="pg-name">' + esc(p.name) + '</span>'
      + '<span class="pg-flag">' + esc(p.flag) + '</span>'
      + (p.range ? '<span class="pg-def">' + esc(p.range) + '</span>' : '')
      + '</div>'
      + '<div class="pg-how"' + (p.fleet ? '' : ' style="margin-bottom:0"') + '>' + pgLink(p.how, sid) + '</div>' + fleetBox(p, sid) + '</div>';
  };
  const chain = '<div class="pg-chain">' + ["penalties","dry","top_k","top_p","min_p","temperature"]
    .map((s, i) => (i ? '<span class="pg-arrow">&rarr;</span>' : '') + '<span class="pg-pill">' + s + '</span>').join("") + '</div>';
  let h = sec("The sampler &amp; runtime guide", "what every launcher flag does");
  h += '<div class="pg-intro">These are the knobs that shape how your local models talk in SkyrimNet. '
    + 'Each launcher sets a sampler <b>chain</b> - which filters run, and in what order. Any sampler left without a value simply runs at whatever SkyrimNet sends per request, and the embedded proxy is what observes and can override those live. '
    + 'Each card below explains what a flag does and how it works; the creativity dials also say what to expect from NPCs in Skyrim with a suggested roleplay range. '
    + 'Each card shows the <b>usable value range</b> for its flag rather than a fixed default, so nothing here is prescribed - any suggested figure is a starting point for roleplay, not a setting you must adopt. Sampler names mentioned in a description are clickable and jump to that card.</div>';
  h += sec("Sampler parameters", "the creativity vs. coherence dials");
  h += grid(S.map(samplerCard));
  h += sec("The sampler chain", "order matters - each stage filters before the next");
  const chainTxt = 'Each stage filters or reshapes the candidate word list before the next one runs, so order changes the result. This is one common order; the llama.cpp default also slots <b>top_n_sigma</b> and <b>xtc</b> in. Reorder or swap samplers with <b>--samplers</b>. A sampler that is in the chain but never given a value simply runs at whatever SkyrimNet sends. <b>Not every sampler mixes:</b> <b>Adaptive-P</b> and <b>Mirostat</b> are self-contained selectors that replace the usual truncators (top-k, top-p, typical, N-sigma, XTC) rather than stacking with them - in the Launcher Creator, clicking a clashing sampler is blocked with a note on what to remove.';
  h += '<div class="pg-card">' + chain
    + '<div class="pg-how" style="margin:8px 0 0">' + pgLink(chainTxt, "") + '</div></div>';
  h += sec("Adaptive &amp; newer samplers", "extra dials, mostly off by default");
  h += grid(ADP.map(infoCard));
  h += sec("Runtime &amp; context", "speed, memory and hardware");
  h += grid(RT.map(infoCard));
  h += sec("Reasoning (thinking)", "the hidden think-first pass");
  h += grid(RE.map(infoCard));
  h += sec("Speculative decoding (MTP)", "drafting ahead for speed");
  h += grid(SP.map(infoCard));
  $("ugpane-params").innerHTML = h;
}
async function renderCreator() {
  await loadModels(false);
  if (!tplBase) tplBase = await (await fetch("/api/template")).json();
  if (!window.__tplDefault) window.__tplDefault = await (await fetch("/api/template?name=single-gpu")).json();
  if (!window.__tplList) window.__tplList = ((await (await fetch("/api/templates")).json()).templates || []);
  const tpls = state.creatorSlots || [];
  $("pane-creator").innerHTML =
    '<div class="card"><div class="row"><span class="label">Base Launcher</span>'
    + '<span class="chip">persistent templates</span>'
    + '<button id="baseplate-default" class="stop" onclick="showBasePlate('+String.fromCharCode(39)+'default'+String.fromCharCode(39)+')">Default</button>'
    + '<button id="baseplate-gpu" class="stop" onclick="showBasePlate('+String.fromCharCode(39)+'gpu'+String.fromCharCode(39)+')">GPU pin</button>'
    + '<button class="stop" onclick="copyBase(this)">&#128203; Copy to clipboard</button>'
    + '<span class="hint" id="baseplate-path"></span></div>'
    + '<div class="hint" id="baseplate-desc" style="margin:8px 0;line-height:1.5"></div>'
    + '<pre class="tail" style="height:230px;min-height:120px;resize:vertical;overflow:auto" id="basepre"></pre></div>'
    + tpls.map(t =>
      '<div class="card"><div class="row">'
      + '<input class="edit" id="ttl-'+t.id+'" style="max-width:340px" data-prev="'+esc(t.title).replace(/"/g,"&quot;")+'" value="'+esc(t.title).replace(/"/g,"&quot;")+'">'
      + '<span class="chip">'+t.id+'</span>'
      + (tpls.length > 1 ? '<button class="x" onclick="tplRemove(\\''+t.id+'\\')">&#10005;</button>' : "")
      + '</div>'
      + '<div class="row" style="margin:8px 0"><span class="hint" style="width:110px">Template</span><select id="tpb-'+t.id+'" style="max-width:460px" onchange="tplPick(\\''+t.id+'\\',this)">'
      + (window.__tplList || []).map(x => '<option value="'+x.id+'"'+(x.id===(t.template||"")?" selected":"")+'>'+esc(x.name)+'</option>').join("")
      + '</select></div>'
      + '<div class="row" style="margin:8px 0"><span class="hint" style="width:110px">Model *</span>'+mSel("mdl-"+t.id,"model",t.model,true)+'</div>'
      + '<div class="row gpurow" id="gpurow-'+t.id+'" style="margin:8px 0"><span class="hint" style="width:110px">GPU (Server Pin)</span><select id="gpu-'+t.id+'" style="max-width:420px">'
      + '<option value="N/A"'+((!t.gpu||t.gpu==="N/A")?" selected":"")+'>N/A - all GPUs visible</option>'
      + (state.gpus || []).map(g => '<option value="'+esc(g.uuid||"")+'"'+((g.uuid===t.gpu)?" selected":"")+'>'+esc((g.brand?g.brand+" ":"")+(g.name||"GPU")+"  #"+(g.index??""))+'</option>').join("")
      + '</select></div>'
      + '<div class="row" style="margin:8px 0"><span class="hint" style="width:110px">Port</span><input class="edit" id="prt-'+t.id+'" style="max-width:110px" placeholder="e.g. 1236" value="'+esc(t.port||"")+'"></div>' 
      + '<div class="row" style="margin:8px 0"><span class="hint" style="width:110px">Vision (mmproj)</span>'+mSel("vis-"+t.id,"vision",t.vision,false)+'</div>'
      + '<div class="row" style="margin:8px 0"><span class="hint" style="width:110px">MTP Drafter</span>'+mSel("drf-"+t.id,"draft",t.draft,false)+'</div>'
      + '<div class="row" style="margin:8px 0"><span class="hint" style="width:110px">Sampler Chain</span><select id="samchain-'+t.id+'" style="max-width:520px">' + SAMP_CHAINS.map(c => '<option value="'+esc(c.value)+'">'+esc(c.label)+'</option>').join("") + '</select></div>'
      + '<div class="row" style="margin:8px 0;align-items:flex-start"><span class="hint" style="width:110px">Samplers</span><div class="sampcards" id="sampcards-'+t.id+'">' + SAMP_DEFS.map(s => '<button class="sampcard" data-act="sampToggle" data-tid="'+t.id+'" data-sid="'+s.id+'" id="sc-'+t.id+'-'+s.id+'">'+esc(s.title)+'</button>').join("") + '</div></div>'
      + '<div class="hint" id="sampnote-'+t.id+'" style="display:none;margin:-4px 0 10px 110px;line-height:1.5"></div>'
      + edHtml(t.id)
      + '<div class="row" style="margin-top:10px">'
      + '<button class="stop" onclick="tplSave(\\''+t.id+'\\',this,false)">&#128190; Save</button>'
      + '<button onclick="tplSave(\\''+t.id+'\\',this,true)">&#128736;&#65039; Create launcher</button>'
      + '<button class="stop" data-act="crValidate" data-tid="'+t.id+'" title="check the whole template for errors, duplicates and incompatible samplers">&#10003; Validate</button>'
      + '<button class="stop" onclick="crReset(\\''+t.id+'\\')" title="reset this template to the base defaults">Reset</button>'
      + '<span class="hint" id="tplres-'+t.id+'"></span></div>'
      + '<div id="valout-'+t.id+'" style="display:none;margin-top:8px"></div></div>'
    ).join("")
    + (tpls.length < 20 ? '<div class="card addcard"><button class="stop" onclick="tplAdd()">&#10133; Add template</button></div>' : "");
  showBasePlate(window.__basePlate || "default");
  tpls.forEach(t => { $("ta-"+t.id).value = t.content || ""; crSeed(t.id); gpuRowVis(t.id); crSampSyncCards(t.id); crChainSync(t.id); });
}
function gpuRowVis(id) {
  const sel = document.getElementById("tpb-" + id);
  const row = document.getElementById("gpurow-" + id);
  if (!row) return;
  const isSingle = (sel ? sel.value : "") === "single-gpu";
  row.style.display = isSingle ? "none" : "";
}
function currentBasePlate() {
  return (window.__basePlate === "gpu") ? (tplBase || {}) : (window.__tplDefault || {});
}
function showBasePlate(which) {
  window.__basePlate = which;
  const plate = currentBasePlate();
  const pre = document.getElementById("basepre"); if (pre) pre.textContent = plate.content || "";
  const pathEl = document.getElementById("baseplate-path");
  if (pathEl) { pathEl.textContent = (which === "gpu") ? "Multi GPU" : "Single GPU"; pathEl.style.color = "var(--ok)"; }
  const bd = document.getElementById("baseplate-default"), bg = document.getElementById("baseplate-gpu");
  if (bd) bd.classList.toggle("on", which === "default");
  if (bg) bg.classList.toggle("on", which === "gpu");
  const desc = document.getElementById("baseplate-desc");
  if (desc) desc.innerHTML = (which === "gpu")
    ? '<b>GPU pin</b> - for a PC with <b>multiple GPUs</b> (or a dedicated inference PC). Pins each server to a specific card by GPU ID so cards stay put across reboots. Choose the card in the <b>GPU (Server Pin)</b> dropdown when you build a launcher from this.'
    : '<b>Default</b> - for a <b>single-GPU PC</b>. GPU-agnostic: no card pinning, llama.cpp just uses your only GPU. Simplest choice for most people. Reference format - copy into a template below and edit; dropdown selections rewrite the text live; the llama-server.exe path comes from Folder Setup.';
}
function copyBase(btn) {
  navigator.clipboard.writeText((currentBasePlate().content) || "").then(() => { btn.textContent = "Copied!"; setTimeout(()=>btn.textContent="\uD83D\uDCCB Copy To Clipboard", 1500); });
}
function tplBody(id) {
  return { id, title: $("ttl-"+id).value, content: $("ta-"+id).value,
           model: $("mdl-"+id).value, vision: $("vis-"+id).value, draft: $("drf-"+id).value,
           gpu: ($("gpu-"+id) ? $("gpu-"+id).value : ""), template: ($("tpb-"+id) ? $("tpb-"+id).value : ""),
           port: ($("prt-"+id) ? $("prt-"+id).value.trim() : "") };
}
const CR_PH = { model: "<MODEL_PATH>", vision: "<MMPROJ_PATH>", draft: "<DRAFT_PATH>", gpu: "<GPU_ID>", port: "<PORT>" };
const CR_FIELDS = [["mdl","model"],["vis","vision"],["drf","draft"],["gpu","gpu"],["prt","port"]];
function llamaExePath() {
  const B = String.fromCharCode(92);
  return (((state && state.settings && state.settings.llamacppPath) || ("C:" + B + "llama.cpp-cuda")) + B + "llama-server.exe");
}
// vision -> "--mmproj", draft -> "--model-draft" : these are conditional lines
const CR_ARG = { vision: "--mmproj", draft: "--model-draft" };
function crFlagLine(flag, path) {
  const Q = String.fromCharCode(34);
  return "    " + Q + flag + Q + ", " + Q + path + Q + ",";
}
function crStripFlag(text, flag) {
  const NL = String.fromCharCode(10);
  return text.split(NL).filter(ln => ln.indexOf(String.fromCharCode(34) + flag + String.fromCharCode(34)) < 0).join(NL);
}
function crEnsureFlag(text, flag, path) {
  // remove any existing flag line, then insert a fresh one right after the --model line
  const NL = String.fromCharCode(10);
  const Q = String.fromCharCode(34);
  const lines = crStripFlag(text, flag).split(NL);
  let mi = -1;
  for (let i = 0; i < lines.length; i++) {
    if (lines[i].indexOf(Q + "--model" + Q) >= 0) { mi = i; break; }
  }
  const ins = crFlagLine(flag, path);
  if (mi >= 0) lines.splice(mi + 1, 0, ins);
  else lines.push(ins);
  return lines.join(NL);
}
function crLive(tid, field, el) {
  const ta = $("ta-" + tid);
  if (!ta) return;
  const v = (el.value || "").trim();
  const isNone = (!v || v === "N/A" || v === "Disabled");
  // vision/draft: add/remove the whole line instead of substituting a placeholder
  if (field === "vision" || field === "draft") {
    const flag = CR_ARG[field];
    ta.value = isNone ? crStripFlag(ta.value, flag) : crEnsureFlag(ta.value, flag, v);
    el.dataset.prev = isNone ? CR_PH[field] : v;
    gut(tid);
    return;
  }
  const ph = CR_PH[field];
  const nv = isNone ? ph : v;
  const prev = el.dataset.prev || ph;
  if (prev === nv) return;
  if (field === "port") {
    const toks = ['"--port", "' + prev + '"', '"--port","' + prev + '"'];
    let done = false;
    for (const tk of toks) {
      if (ta.value.indexOf(tk) >= 0) { ta.value = ta.value.split(tk).join('"--port", "' + nv + '"'); done = true; break; }
    }
    if (!done && prev.charAt(0) === "<" && ta.value.indexOf(prev) >= 0) ta.value = ta.value.split(prev).join(nv);
  } else {
    ta.value = ta.value.split(prev).join(nv);
  }
  el.dataset.prev = nv;
  gut(tid);
}
function crSeed(tid) {
  const ta = $("ta-" + tid);
  if (!ta) return;
  const B2 = String.fromCharCode(92);
  ta.value = ta.value.split("<LLAMA_EXE>").join(llamaExePath())
                     .split("C:" + B2 + "llama.cpp-cuda" + B2 + "llama-server.exe").join(llamaExePath());
  CR_FIELDS.forEach(([p, f]) => {
    const el = $(p + "-" + tid);
    if (!el) return;
    const cur = (el.value || "").trim();
    // conditional flags: drop any placeholder line up front; crLive re-adds when a model is chosen
    if (f === "vision" || f === "draft") {
      ta.value = crStripFlag(ta.value, CR_ARG[f]);
      el.dataset.prev = CR_PH[f];
    } else {
      const probe = f === "port" ? ('"--port", "' + cur + '"') : cur;
      el.dataset.prev = (cur && cur !== "N/A" && cur !== "Disabled" && ta.value.indexOf(probe) >= 0) ? cur : CR_PH[f];
    }
    if (!el.dataset.wired) {
      el.dataset.wired = "1";
      el.addEventListener("change", () => { crLive(tid, f, el); post("/api/creator-save", tplBody(tid)); });
      if (f === "port") el.addEventListener("input", () => crLive(tid, f, el));
    }
    crLive(tid, f, el);
  });
  gut(tid);
}
async function tplPick(id, sel) {
  const name = sel.value;
  gpuRowVis(id);
  const ta = $("ta-" + id);
  // capture the current sampler selection + values + chain so they survive the switch
  const keepCards = crSamplerSel(id);
  const keepChain = ta ? crArgVal(ta.value, "--samplers") : null;
  const keepVals = {};
  if (ta) SAMP_DEFS.forEach(s => s.args.forEach(x => { const v = crArgVal(ta.value, x.flag); if (v !== null) keepVals[x.flag] = v; }));
  const r = await (await fetch("/api/template" + (name ? "?name=" + encodeURIComponent(name) : ""))).json();
  if (ta && r && typeof r.content === "string") {
    ta.value = r.content.split("<LLAMA_EXE>").join(llamaExePath());
    CR_FIELDS.forEach(([p, f]) => {
      const el = $(p + "-" + id);
      if (el) { el.dataset.prev = CR_PH[f]; crLive(id, f, el); }
    });
    gut(id);
    // re-apply the captured samplers onto the new base template (persists selection)
    crRebuildRegion(id, { cards: keepCards, chain: (keepChain === null || keepChain === undefined) ? "" : keepChain, vals: keepVals });
  }
}
async function crReset(id) {
  if (!await uiConfirm("Reset this template to the base defaults? The samplers you selected here, and the model, GPU, port, vision and drafter choices in this template, will be cleared.", { okLabel: "Reset", title: "Reset Template" })) return;
  const sel = $("tpb-" + id), name = sel ? sel.value : "";
  const r = await (await fetch("/api/template" + (name ? "?name=" + encodeURIComponent(name) : ""))).json();
  const ta = $("ta-" + id);
  if (!ta || !r || typeof r.content !== "string") return;
  ["mdl", "vis", "drf"].forEach(p => { const el = $(p + "-" + id); if (el) el.value = ""; });
  const gpu = $("gpu-" + id); if (gpu) gpu.value = "N/A";
  const prt = $("prt-" + id); if (prt) prt.value = "";
  ta.value = r.content.split("<LLAMA_EXE>").join(llamaExePath());
  CR_FIELDS.forEach(([p, f]) => { const el = $(p + "-" + id); if (el) { el.dataset.prev = CR_PH[f]; crLive(id, f, el); } });
  gut(id);
  crSampSyncCards(id);
  crChainSync(id);
  crSampNote(id, "");
  const res = $("tplres-" + id); if (res) { res.textContent = "reset to defaults"; res.style.color = "var(--dim)"; }
  post("/api/creator-save", tplBody(id));
}
async function tplSave(id, btn, create) {
  btn.disabled = true;
  const r = await post(create ? "/api/creator-create" : "/api/creator-save", tplBody(id));
  btn.disabled = false;
  const res = $("tplres-"+id);
  if (r.error) { res.textContent = r.error; res.style.color = "var(--err)"; }
  else { res.textContent = create ? ("created: " + r.path) : "saved"; res.style.color = "var(--ok)"; await load(); }
}
async function tplAdd() { const r = await post("/api/creator-add", {}); if (r.error) uiAlert(r.error); await load(); renderCreator(); }
async function tplRemove(id) {
  if (!await uiConfirm("Remove this template? (does not delete any created .ps1 files)")) return;
  const r = await post("/api/creator-remove", { id }); if (r.error) uiAlert(r.error); await load(); renderCreator();
}

const CR_FLAGS = { model: "--model", vision: "--mmproj", draft: "--model-draft" };
const CR_TOKENS = { model: "<MODEL_PATH>", vision: "<MMPROJ_PATH>", draft: "<DRAFT_PATH>" };
const SAMP_MARK_START = "    # >>> PandorumLLM samplers >>>";
const SAMP_MARK_END   = "    # <<< PandorumLLM samplers <<<";
const SAMP_TAG = "PandorumLLM samplers";
const SAMP_DEFS = [
  { id:"temp",   title:"Temperature", args:[{ flag:"--temp", def:"0.8" }] },
  { id:"topp",   title:"Top-p",       args:[{ flag:"--top-p", def:"0.95" }] },
  { id:"minp",   title:"Min-p",       args:[{ flag:"--min-p", def:"0.05" }] },
  { id:"topk",   title:"Top-k",       args:[{ flag:"--top-k", def:"40" }] },
  { id:"dry",    title:"DRY",         args:[{ flag:"--dry-multiplier", def:"0.8" }, { flag:"--dry-base", def:"1.75" }, { flag:"--dry-allowed-length", def:"2" }, { flag:"--dry-penalty-last-n", def:"2048" }] },
  { id:"nsigma", title:"N-sigma",     args:[{ flag:"--top-n-sigma", def:"1.0" }] },
  { id:"typ_p",  title:"Typical",     args:[{ flag:"--typical", def:"0.95" }] },
  { id:"xtc",    title:"XTC",         args:[{ flag:"--xtc-probability", def:"0.5" }, { flag:"--xtc-threshold", def:"0.1" }] },
  { id:"adaptivep", title:"Adaptive-P", args:[{ flag:"--adaptive-target", def:"0.55" }, { flag:"--adaptive-decay", def:"0.9" }] },
  { id:"dyntemp", title:"Dyn-temp",   args:[{ flag:"--dynatemp-range", def:"0.3" }, { flag:"--dynatemp-exp", def:"1.0" }] },
  { id:"penalties", title:"Penalties", args:[{ flag:"--frequency-penalty", def:"0.3" }, { flag:"--presence-penalty", def:"0.3" }] }
];
const SAMP_CHAINS = [
  { value:"", label:"Disabled (use llama.cpp default order)" },
  { value:"penalties;dry;top_k;top_p;min_p;temperature", label:"Standard - penalties;dry;top_k;top_p;min_p;temperature" },
  { value:"penalties;top_k;top_p;min_p;temperature", label:"No DRY - penalties;top_k;top_p;min_p;temperature" },
  { value:"penalties;dry;top_n_sigma;top_k;top_p;min_p;temperature", label:"With N-sigma - penalties;dry;top_n_sigma;top_k;top_p;min_p;temperature" },
  { value:"penalties;dry;top_n_sigma;top_k;typ_p;top_p;min_p;xtc;temperature", label:"llama.cpp full default order" }
];
const SAMP_CONFLICTS = {
  adaptivep: { with: ["topp","topk","typ_p","nsigma","xtc"],
    why: "Adaptive-P selects the token itself and must run last as the sole truncator - only a mild Min-p is meant to run before it, so it cannot share the chain with the other truncation samplers." }
};
function crArgVal(text, flag) {
  const Q = String.fromCharCode(34);
  const i = text.indexOf(Q + flag + Q);
  if (i < 0) return null;
  const q1 = text.indexOf(Q, i + flag.length + 2);
  if (q1 < 0) return null;
  const q2 = text.indexOf(Q, q1 + 1);
  if (q2 < 0) return null;
  return text.slice(q1 + 1, q2);
}
function crStripSamplers(text) {
  const NL = String.fromCharCode(10), Q = String.fromCharCode(34);
  let lines = text.split(NL);
  let a = -1, b = -1;
  for (let i = 0; i < lines.length; i++) { if (lines[i].indexOf(SAMP_TAG) >= 0) { if (a < 0) a = i; b = i; } }
  if (a >= 0 && b >= a) lines.splice(a, b - a + 1);
  const flags = [Q + "--samplers" + Q], titles = ["# --- Sampler chain ---"];
  SAMP_DEFS.forEach(s => { titles.push("# --- " + s.title + " ---"); s.args.forEach(x => flags.push(Q + x.flag + Q)); });
  lines = lines.filter(ln => !flags.some(f => ln.indexOf(f) >= 0) && !titles.some(tt => ln.indexOf(tt) >= 0));
  return lines.join(NL);
}
function crBuildSamplers(selSet, vals, chainVal) {
  const Q = String.fromCharCode(34);
  const paras = [];
  if (chainVal) paras.push([ "# --- Sampler chain ---", Q + "--samplers" + Q + ", " + Q + chainVal + Q + "," ]);
  SAMP_DEFS.forEach(s => {
    if (!selSet.has(s.id)) return;
    const p = [ "# --- " + s.title + " ---" ];
    s.args.forEach(x => p.push(Q + x.flag + Q + ", " + Q + (vals[x.flag] !== undefined ? vals[x.flag] : x.def) + Q + ","));
    paras.push(p);
  });
  if (!paras.length) return null;
  const out = [SAMP_MARK_START];
  paras.forEach((p, i) => { if (i) out.push(""); p.forEach(l => out.push("    " + l)); });
  out.push(SAMP_MARK_END);
  return out;
}
function crInsertSamplers(text, block) {
  const NL = String.fromCharCode(10);
  let lines = text.split(NL);
  let open = -1;
  for (let i = 0; i < lines.length; i++) { if (lines[i].indexOf("= @(") >= 0) { open = i; break; } }
  if (open < 0) return text;
  let close = -1;
  for (let i = open + 1; i < lines.length; i++) { if (lines[i].trim() === ")") { close = i; break; } }
  if (close < 0) return text;
  let last = -1;
  for (let i = close - 1; i > open; i--) { const tt = lines[i].trim(); if (tt && tt.charAt(0) !== "#") { last = i; break; } }
  if (last < 0) last = close;
  lines.splice(last, 0, ...block);
  return lines.join(NL);
}
function crSamplerSel(tid) {
  const ta = $("ta-" + tid), Q = String.fromCharCode(34), set = new Set();
  if (!ta) return set;
  SAMP_DEFS.forEach(s => { if (ta.value.indexOf(Q + s.args[0].flag + Q) >= 0) set.add(s.id); });
  return set;
}
function crSampSyncCards(tid) {
  const sel = crSamplerSel(tid);
  SAMP_DEFS.forEach(s => { const b = $("sc-" + tid + "-" + s.id); if (b) b.classList.toggle("on", sel.has(s.id)); });
}
function crRebuildRegion(tid, opts) {
  opts = opts || {};
  const ta = $("ta-" + tid);
  if (!ta) return;
  let chainVal = (opts.chain !== undefined) ? opts.chain : crArgVal(ta.value, "--samplers");
  if (chainVal === null || chainVal === undefined) chainVal = "";
  const selCards = (opts.cards !== undefined) ? opts.cards : crSamplerSel(tid);
  const vals = Object.assign({}, opts.vals || {});
  SAMP_DEFS.forEach(s => s.args.forEach(x => { if (vals[x.flag] === undefined) { const v = crArgVal(ta.value, x.flag); if (v !== null) vals[x.flag] = v; } }));
  let text = crStripSamplers(ta.value);
  const block = crBuildSamplers(selCards, vals, chainVal);
  if (block) text = crInsertSamplers(text, block);
  ta.value = text;
  gut(tid);
  crSampSyncCards(tid);
  crChainSync(tid);
  post("/api/creator-save", tplBody(tid));
}
function sampTitle(sid) { const d = SAMP_DEFS.find(x => x.id === sid); return d ? d.title : sid; }
function crSampConflict(sid, selSet) {
  const hits = [];
  const mine = SAMP_CONFLICTS[sid];
  if (mine) mine.with.forEach(o => { if (selSet.has(o) && hits.indexOf(o) < 0) hits.push(o); });
  Object.keys(SAMP_CONFLICTS).forEach(k => {
    if (selSet.has(k) && SAMP_CONFLICTS[k].with.indexOf(sid) >= 0 && hits.indexOf(k) < 0) hits.push(k);
  });
  if (!hits.length) return null;
  const why = (mine && mine.why) || (SAMP_CONFLICTS[hits[0]] && SAMP_CONFLICTS[hits[0]].why) || "";
  const names = hits.map(sampTitle);
  const msg = "Cannot add " + sampTitle(sid) + " - it collides with " + names.join(" and ")
    + " (already selected). " + why + " Remove " + names.join(" and ") + " first to add " + sampTitle(sid) + ".";
  return { hits: hits, msg: msg };
}
function crSampNote(tid, msg, isErr) {
  const el = $("sampnote-" + tid);
  if (!el) return;
  el.textContent = msg || "";
  el.style.display = msg ? "block" : "none";
  el.style.color = isErr ? "var(--err)" : "var(--dim)";
}
function crSampReject(tid, sid, msg) {
  const b = $("sc-" + tid + "-" + sid);
  if (b) { b.classList.remove("reject"); void b.offsetWidth; b.classList.add("reject"); setTimeout(() => b.classList.remove("reject"), 900); }
  crSampNote(tid, msg, true);
}
function crSampToggle(tid, sid) {
  const sel = crSamplerSel(tid);
  if (!sel.has(sid)) {
    const c = crSampConflict(sid, sel);
    if (c) { crSampReject(tid, sid, c.msg); return; }
  }
  if (sel.has(sid)) sel.delete(sid); else sel.add(sid);
  crSampNote(tid, "");
  crRebuildRegion(tid, { cards: sel });
}
function crSetChain(tid, value) {
  crRebuildRegion(tid, { chain: value });
}
function crChainSync(tid) {
  const ta = $("ta-" + tid), sel = $("samchain-" + tid);
  if (!ta || !sel) return;
  const cur = crArgVal(ta.value, "--samplers");
  const want = (cur === null) ? "" : cur;
  const presetVals = SAMP_CHAINS.map(c => c.value);
  const customOpt = sel.querySelector('option[data-custom="1"]');
  if (want && presetVals.indexOf(want) < 0) {
    const opt = customOpt || document.createElement("option");
    opt.dataset.custom = "1"; opt.value = want; opt.textContent = "Custom - " + want;
    if (!customOpt) sel.insertBefore(opt, sel.firstChild);
  } else if (customOpt) { customOpt.remove(); }
  sel.value = want;
  if (!sel.dataset.wired) { sel.dataset.wired = "1"; sel.addEventListener("change", () => crSetChain(tid, sel.value)); }
}
function crValidateText(txt) {
  const Q = String.fromCharCode(34), NL = String.fromCharCode(10);
  const lines = txt.split(NL);
  const items = [];
  const add = (sev, msg) => items.push({ sev: sev, msg: msg });
  const val = f => crArgVal(txt, f);

  // array bounds
  let open = -1, close = -1;
  for (let i = 0; i < lines.length; i++) if (lines[i].indexOf("= @(") >= 0) { open = i; break; }
  if (open >= 0) for (let i = open + 1; i < lines.length; i++) if (lines[i].trim() === ")") { close = i; break; }
  if (open < 0 || close < 0) add("error", "Could not find the argument array ( = @( ... ) ) - the launcher body looks malformed.");

  // unbalanced quotes per line
  lines.forEach((ln, i) => { if (((ln.match(/"/g) || []).length) % 2 !== 0) add("error", "Line " + (i + 1) + ": unbalanced quote - a string is not closed on this line."); });

  // trailing comma on the last array element
  if (open >= 0 && close > open) {
    let last = -1;
    for (let i = close - 1; i > open; i--) { const tt = lines[i].trim(); if (tt && tt.charAt(0) !== "#") { last = i; break; } }
    if (last >= 0 && lines[last].trim().slice(-1) === ",") add("error", "Line " + (last + 1) + ": the last array item ends with a comma - PowerShell rejects a trailing comma before ). Remove it.");
  }

  // duplicate flags
  const flagRe = /"(--[a-z0-9-]+)"/gi;
  const counts = {}; let m;
  while ((m = flagRe.exec(txt)) !== null) counts[m[1]] = (counts[m[1]] || 0) + 1;
  Object.keys(counts).forEach(f => { if (counts[f] > 1) add("warn", "Duplicate flag " + f + " appears " + counts[f] + " times - keep only one (llama.cpp uses just one, usually the last)."); });

  // unfilled placeholders - only flag them in real (non-comment) lines. Placeholders that
  // appear in the header comment are documentation, not unfilled inputs; vision/draft lines
  // are removed entirely when Disabled, and <TITLE> is always filled with the template's own
  // title at create time, so it is not checked here.
  const codeOnly = lines.filter(ln => ln.trim().charAt(0) !== "#").join(NL);
  const PH = { "<MODEL_PATH>": ["error","model"], "<PORT>": ["warn","port"], "<GPU_ID>": ["warn","GPU id"], "<MMPROJ_PATH>": ["warn","vision projector"], "<DRAFT_PATH>": ["warn","draft model"], "<LLAMA_EXE>": ["warn","llama-server.exe path"] };
  Object.keys(PH).forEach(p => { if (codeOnly.indexOf(p) >= 0) add(PH[p][0], "Unfilled placeholder " + p + " (" + PH[p][1] + ") - set it before creating the launcher."); });

  // required flags
  if (txt.indexOf(Q + "--model" + Q) < 0 && txt.indexOf("<MODEL_PATH>") < 0) add("error", "No --model flag - a model is required.");
  if (txt.indexOf(Q + "--port" + Q) < 0 && txt.indexOf("<PORT>") < 0) add("warn", "No --port flag - the server needs a port.");

  // port must be a real, usable, non-ephemeral number
  const portV = val("--port");
  if (portV !== null && portV.indexOf("<") < 0) {
    const ptrim = portV.trim(), pn = Number(ptrim);
    if (!/^[0-9]+$/.test(ptrim) || pn < 1 || pn > 65535)
      add("error", "Port value " + portV + " is not a valid port - use a whole number from 1 to 65535.");
    else if (pn < 1024)
      add("warn", "Port " + pn + " is a system / privileged port (1-1023) - it may need admin rights or clash with a Windows service. A port in 1024-49151 is safer.");
    else if (pn >= 49152)
      add("warn", "Port " + pn + " is in the dynamic / ephemeral range (49152-65535) that Windows hands out for outgoing connections - it can clash unpredictably. Use a port in 1024-49151.");
  }

  // sampler value flags present
  const present = {};
  SAMP_DEFS.forEach(s => { if (val(s.args[0].flag) !== null) present[s.id] = true; });
  const selSet = new Set(Object.keys(present));

  // sampler collisions (reuse SAMP_CONFLICTS, both directions, dedup)
  const reported = {};
  Object.keys(SAMP_CONFLICTS).forEach(k => {
    if (!selSet.has(k)) return;
    SAMP_CONFLICTS[k].with.forEach(o => {
      if (selSet.has(o)) {
        const key = [k, o].sort().join("|");
        if (!reported[key]) { reported[key] = 1; add("warn", sampTitle(k) + " and " + sampTitle(o) + " are both set but collide - " + SAMP_CONFLICTS[k].why); }
      }
    });
  });

  // chain vs value consistency
  const CHAINMAP = { temp:"temperature", dyntemp:"temperature", topp:"top_p", minp:"min_p", topk:"top_k", nsigma:"top_n_sigma", typ_p:"typ_p", xtc:"xtc", dry:"dry", penalties:"penalties", adaptivep:"adaptive_p" };
  const chain = val("--samplers");
  if (chain !== null) {
    const parts = chain.split(";").map(x => x.trim());
    Object.keys(present).forEach(id => {
      const nm = CHAINMAP[id];
      if (nm && parts.indexOf(nm) < 0) add("warn", sampTitle(id) + " has a value set but " + nm + " is not in the --samplers chain, so it will have no effect. Add " + nm + " to --samplers or remove the flag.");
    });
    if (parts.indexOf("adaptive_p") >= 0 && parts[parts.length - 1] !== "adaptive_p") add("warn", "adaptive_p is in the --samplers chain but not last - it selects the token itself and must run last.");
  } else if (present.adaptivep) {
    add("warn", "Adaptive-P is set but there is no --samplers line; the default chain does not include adaptive_p, so it will not run. Add a --samplers chain ending in adaptive_p.");
  }

  // mirostat incompatibility (text-based)
  const miro = val("--mirostat");
  if (miro !== null && miro.trim() !== "0") {
    ["--top-k","--top-p","--typical"].forEach(f => { if (val(f) !== null) add("warn", "Mirostat is on and " + f.replace("--","") + " is also set - Mirostat replaces top-k / top-p / typical, so those are ignored while it runs."); });
  }

  // disabled-value info
  const OFF = [["--top-k","0","Top-k"],["--top-p","1.0","Top-p"],["--typical","1.0","Typical"],["--min-p","0","Min-p"],["--top-n-sigma","-1","N-sigma"],["--xtc-probability","0","XTC"],["--dry-multiplier","0","DRY"]];
  OFF.forEach(o => { const v = val(o[0]); if (v !== null && parseFloat(v) === parseFloat(o[1])) add("info", o[2] + " is present but set to its off value (" + v + ") - it currently has no effect (this may be intentional)."); });

  return items;
}
function crValidate(tid) {
  const ta = $("ta-" + tid);
  if (!ta) return;
  crRenderValidation(tid, crValidateText(ta.value));
}
function crRenderValidation(tid, items) {
  const el = $("valout-" + tid);
  if (!el) return;
  const ord = { error: 0, warn: 1, info: 2 };
  items.sort((a, b) => ord[a.sev] - ord[b.sev]);
  const nE = items.filter(x => x.sev === "error").length;
  const nW = items.filter(x => x.sev === "warn").length;
  const nI = items.length - nE - nW;
  const col = { error: "var(--err)", warn: "var(--warn)", info: "var(--dim)" };
  const lab = { error: "ERROR", warn: "WARN", info: "note" };
  let head;
  if (!items.length) head = '<div style="color:var(--ok);font-weight:600">OK - no problems found.</div>';
  else {
    const parts = [];
    if (nE) parts.push(nE + " error" + (nE > 1 ? "s" : ""));
    if (nW) parts.push(nW + " warning" + (nW > 1 ? "s" : ""));
    if (nI) parts.push(nI + " note" + (nI > 1 ? "s" : ""));
    head = '<div style="font-weight:600;margin-bottom:6px">Validation: ' + parts.join(", ") + '</div>';
  }
  const rows = items.map(x => '<div style="margin:3px 0;line-height:1.45"><b style="color:' + col[x.sev] + '">' + lab[x.sev] + '</b> <span style="color:var(--txt)">' + esc(x.msg) + '</span></div>').join("");
  el.innerHTML = '<div class="card" style="margin:0;padding:10px 12px">' + head + rows + '</div>';
  el.style.display = "block";
}
function creatorSync(tid, field, value) {
  const ta = $("ta-" + tid);
  if (!ta) return;
  const NL = String.fromCharCode(10), Q = String.fromCharCode(34);
  const flag = Q + CR_FLAGS[field] + Q;
  const lines = ta.value.split(NL);
  let idx = -1;
  for (let i = 0; i < lines.length; i++) {
    if (lines[i].indexOf(flag) >= 0 || lines[i].indexOf(CR_TOKENS[field]) >= 0) { idx = i; break; }
  }
  if (value === "N/A" || value === "") {
    if (field !== "model" && idx >= 0) lines.splice(idx, 1);
  } else if (idx >= 0) {
    let ln = lines[idx];
    const f = ln.indexOf(flag);
    if (f >= 0) {
      const v1 = ln.indexOf(Q, f + flag.length + 1);
      const v2 = v1 >= 0 ? ln.indexOf(Q, v1 + 1) : -1;
      if (v1 >= 0 && v2 > v1) ln = ln.slice(0, v1 + 1) + value + ln.slice(v2);
      else ln = ln.split(CR_TOKENS[field]).join(value);
    } else {
      ln = ln.split(CR_TOKENS[field]).join(value);
    }
    lines[idx] = ln;
  } else {
    let anchor = -1;
    for (let i = 0; i < lines.length; i++) {
      if (lines[i].indexOf(Q + CR_FLAGS.model + Q) >= 0) anchor = i;
      if (field === "draft" && lines[i].indexOf(Q + CR_FLAGS.vision + Q) >= 0) anchor = i;
    }
    if (anchor < 0) for (let i = 0; i < lines.length; i++) if (lines[i].indexOf("@(") >= 0) { anchor = i; break; }
    let indent = "";
    const srcLn = anchor >= 0 ? lines[anchor] : "    ";
    for (const ch of srcLn) { if (ch === " " || ch === String.fromCharCode(9)) indent += ch; else break; }
    const ins = indent + flag + ", " + Q + value + Q + ",";
    lines.splice(anchor >= 0 ? anchor + 1 : 0, 0, ins);
  }
  ta.value = lines.join(NL);
  gut(tid);
}
function creatorTitle(tid, el) {
  const ta = $("ta-" + tid);
  if (!ta) return;
  const prev = el.dataset.prev || "<TITLE>";
  const NL = String.fromCharCode(10);
  ta.value = ta.value.split(NL).map(l =>
    (l.indexOf("<TITLE>") >= 0 || (l.indexOf("generated by PandorumLLM Launcher Creator") >= 0 && prev && l.indexOf(prev) >= 0))
      ? l.split("<TITLE>").join(el.value).split(prev).join(el.value) : l).join(NL);
  el.dataset.prev = el.value;
  gut(tid);
}

/* ---------- launcher inspector ---------- */
function renderInspector() {
  const opts = state.launchers.map(l =>
    '<option value="'+esc(l.path)+'">'+esc(l.name)+(l.source!=="primary"?" ["+l.source+"]":"")+'</option>').join("");
  $("pane-inspector").innerHTML = '<div class="card"><div class="row">'
    + '<select id="insp-sel" style="min-width:420px" data-act="inspSel">'+opts+'</select>'
    + '<button class="stop" data-act="inspFolder">📂 Open folder</button>'
    + '<button class="stop" data-act="inspFile">📄 Open file</button>'
    + '<button class="stop" data-act="wrapToggle" data-tgt="insp-view" style="margin-left:auto" title="toggle text wrapping">\u21A9 Wrap: <span id="wraplbl-insp-view">off</span></button>'
    + '<span class="hint" id="insp-path"></span></div>'
    + '<pre class="tail" style="height:60vh;margin-top:12px" id="insp-view">(loading&hellip;)</pre></div>';
  inspect();
}
async function inspect() {
  const sel = $("insp-sel");
  if (!sel || !sel.value) { const v = $("insp-view"); if (v) v.textContent = "(no launchers found)"; return; }
  const r = await post("/api/launcher-content", { path: sel.value });
  if (r.error) { $("insp-view").textContent = r.error; return; }
  $("insp-path").textContent = r.path;
  const NL = String.fromCharCode(10);
  const lines = r.content.split(NL);
  const w = String(lines.length).length;
  $("insp-view").innerHTML = lines.map((l, i) =>
    '<span style="color:#5b6472">' + String(i+1).padStart(w, " ") + '</span>  ' + psHl(l)).join(NL);
  $("insp-view").style.color = "#d4d4d4";
}

/* ---------- actions / polling ---------- */
function applyScopeUI() {
  const remote = state && state.scope === "remote";
  document.body.classList.toggle("remoteview", !!remote);
  if (remote && (curDsub === "setup" || curDsub === "yaml")) showDsub("term");
  if (remote && typeof curPmSub !== "undefined" && curPmSub === "stats") showPmSub("providers");
  // hide host-only nav tabs for a clean read-only view (server also blocks their actions)
  const hostOnlyNav = ["nav-servers","nav-launcher","nav-setup","nav-custom","nav-helper","nav-log","nav-perms"];
  hostOnlyNav.forEach(id => { const b = document.getElementById(id); if (b) b.style.display = remote ? "none" : ""; });
  // top-bar action buttons that mutate the host
  ["Launch","Terminate","Exit","launchBtn","btn-launch","btn-terminate","btn-exit"].forEach(id => {
    const b = document.getElementById(id); if (b) b.style.display = remote ? "none" : "";
  });
  if (remote) {
    // send a viewer to the terminals when the view first opens, and only then - doing
    // it on every refresh dragged them off whatever they were reading
    const HOSTONLY_TABS = ["servers","launcher","setup","custom","helper","log","perms"];
    if (!window.__remoteSettled) {
      window.__remoteSettled = true;
      if (typeof curTab !== "undefined" && curTab !== "dashboard") { try { showTab("dashboard"); } catch (e) {} }
    } else if (typeof curTab !== "undefined" && HOSTONLY_TABS.indexOf(curTab) >= 0) {
      try { showTab("dashboard"); } catch (e) {}   // only if they are somewhere they cannot be
    }
    const badge = document.getElementById("scopebadge");
    if (!badge) {
      const h = document.querySelector("header");
      if (h) {
        const s = document.createElement("span");
        s.id = "scopebadge"; s.className = "ver";
        s.style.cssText = "border-color:#5aa9e6;color:#5aa9e6";
        s.innerHTML = ICO.eye + " read-only remote view";
        h.appendChild(s);
      }
    }
  }
}
async function load() {
  try {
    state = await (await fetch("/api/state")).json();
    reconcilePcMode();
    paintChrome();
    renderCurrent();
    applyScopeUI();
    fleetWatch();
    if (!window.__themed) {
      const sset = state.settings || {};
      const tv = (sset.themeVars && Object.keys(sset.themeVars).length) ? sset.themeVars : THEMES[sset.themeName];
      if (tv) applyTheme(tv);
      window.__termBlack = !!(sset.termBlack);
      document.querySelectorAll(".bgopt").forEach(function(b) {
        b.classList.toggle("on", (b.dataset.v === "1") === !!window.__termBlack); });
      const legacy = { mode: (sset.termScaleMode === "auto") ? "auto" : "manual", size: Math.max(8, Math.min(24, parseInt(sset.termFontSize, 10) || 12)), on: (sset.termScaleOn !== false) };
      const savedTS = sset.termScales || {};
      TS_KINDS.forEach(function(k) {
        const s = savedTS[k] || ((k === "splitd" || k === "splitt") ? savedTS.split : null);
        termScales[k] = (s && typeof s === "object")
          ? { mode: (s.mode === "auto") ? "auto" : "manual", size: Math.max(8, Math.min(24, parseInt(s.size, 10) || 12)), on: (s.on !== false), font: s.font || TERM_FONT_DEFAULT }
          : { mode: legacy.mode, size: legacy.size, on: legacy.on, font: TERM_FONT_DEFAULT };
      });
      initTermScaleSelect(); syncTermScaleUI(); syncTextScalingButtons(); applyTermScale();
      window.__themed = true;
    }
    if (UI_VERSION !== ("__" + "UIV__") && state.version && state.version !== UI_VERSION) {
      const sb = $("sub");
      if (sb) { sb.textContent = "⚠ this browser tab is showing a cached old UI (" + UI_VERSION + ") - press Ctrl+F5 to load " + state.version; sb.style.color = "var(--warn)"; }
    }
  }
  catch (e) {
    // guarded: "sub" is rendered by JS and may not exist yet. Unguarded, the handler
    // threw and replaced the real failure with a TypeError, losing the cause.
    const sb = $("sub");
    if (sb) sb.textContent = "panel unreachable - retrying...";
    trace("load", "failed", String(e));
  }
}
let writesInFlight = 0;
async function post(u, b) {
  writesInFlight++;
  const t0 = performance.now();
  trace("call", u);
  try {
    const r = await (await fetch(u, { method:"POST", headers:{"Content-Type":"application/json"},
                                      body: JSON.stringify(b) })).json();
    trace("call", u + " came back", Math.round(performance.now() - t0) + "ms"
          + (r && r.error ? ", error: " + r.error : ""));
    if (r && r.error && String(r.error).indexOf("host-only") >= 0) {
      r.__refused = true;                        // callers: do not act on this
      if (!window.__roMsgAt || Date.now() - window.__roMsgAt > 1200) {
        window.__roMsgAt = Date.now();
        uiAlert("This is a read-only remote view. Changes have to be made on the PandorumLLM PC.");
      }
    }
    return r;
  } finally { writesInFlight--; }
}
// A refresh must never redraw the page out from under someone. This reports anything a
// redraw would disturb: a write that has not landed, an open menu or dialog, a field
// being typed in, a slider being used, or something being dragged.
function uiBusy() {
  if (writesInFlight > 0) return "a save has not come back yet";
  if (document.querySelector(".dragging")) return "something is being dragged";
  if (paramBusy()) return "a parameter is being adjusted";
  const why = fxQuiet();
  if (why) return why;
  if (document.querySelector(".gbranch.gshow")) return "the guide note is showing";
  return "";
}
async function assign(sid, path) {
  const r = await post("/api/assign", { slot: sid, script: path });
  if (r && !r.error && r.oldPort && r.newPort && r.oldPort !== r.newPort)
    slotMsg[sid] = "server port changed " + r.oldPort + " >> " + r.newPort;
  else if (r && !r.error) delete slotMsg[sid];
  queueRouting();
  if (r.error) { uiAlert(r.error); return; }
  // release the <select> so renderSlots (which skips re-rendering while a select/input is
  // focused) updates this slot's status immediately instead of on a later refresh
  if (document.activeElement && document.activeElement.blur) document.activeElement.blur();
  load();
}
async function addSlot() { const r = await post("/api/add", {}); if (r.error) uiAlert(r.error); load(); }
async function removeSlot(sid) {
  const s = state.slots.find(x => x.id === sid);
  if (!await uiConfirm('Remove slot "' + (s ? s.label : sid) + '"?\\nA running server is NOT stopped by this - use Stop first if needed.')) return;
  const r = await post("/api/remove", { slot: sid });
  if (r.error) uiAlert(r.error);
  load();
}
async function act(sid, kind, btn) {
  const old = btn.textContent;
  btn.disabled = true; btn.textContent = "working...";
  const r = await post("/api/" + kind, { slot: sid });
  const log = $("log-" + sid);
  if (log && kind !== "show-terminal") { log.textContent = r.log || r.error || ""; log.style.display = "block"; }
  btn.disabled = false; btn.textContent = old;
  load();
}
let exitArmed = false;
const HB_UID = Math.random().toString(36).slice(2) + Date.now().toString(36);
setInterval(async () => {
  if (exitArmed) return;
  try {
    const hb = await (await fetch("/api/heartbeat", { method:"POST", body: JSON.stringify({uid: HB_UID}) })).json();
    // the server bumps seq on every notify; if it moved and this page saw nothing, the
    // stream is dead - catch up once and rebuild the EventSource
    if (hb && hb.seq && hb.seq > (window.__sseSeq || 0)) {
      trace("refresh", "SSE gap - heartbeat fallback", (window.__sseSeq || 0) + " -> " + hb.seq);
      window.__sseSeq = hb.seq;
      liveRefresh("tail");
      connectES();
    }
  } catch (e) {}
}, 5000);
fetch("/api/heartbeat", { method:"POST", body: JSON.stringify({uid: HB_UID}) }).catch(()=>{});
window.addEventListener("pagehide", () => { if (!exitArmed) navigator.sendBeacon("/api/bye", HB_UID); });
window.addEventListener("beforeunload", e => {
  if (exitArmed || !state) return;                // shutting down on close is always on
  e.preventDefault(); e.returnValue = "";
});
function goodbye() {
  exitArmed = true;
  document.body.innerHTML = '<div style="display:flex;height:100vh;align-items:center;justify-content:center">'
    + '<div class="card" style="max-width:420px;text-align:center"><h1>PandorumLLM</h1>'
    + '<p>Panel and servers are shutting down.<br>You can close this tab now.</p></div></div>';
  setTimeout(() => window.close(), 400);
}
async function terminateAll(btn) {
  if (!await uiConfirm("Terminate ALL LLM servers? (panel keeps running)")) return;
  window.__terminating = true; window.__launching = false;
  fleetWatch();
  btn.disabled = true; btn.innerHTML = termLabel("Working...");
  // Terminate stops the TTS server too, but it is one long write and queueLoad defers
  // every reload while a write is in flight - so the pane could never see the state
  // between running and stopped. Mark it here, exactly as the Stop button does.
  const hadTts = !!(state && state.ttsServer
                    && ["serving", "loading"].indexOf(state.ttsServer.state) >= 0);
  if (hadTts && !ttsBusy) { ttsBusy = "stop"; if (curTab === "dashboard" && curDsub === "tts") renderTts(); }
  try {
    const r = await post("/api/terminate", {});
    stackSet(r.log || r.error || "");
  } finally {
    if (hadTts && ttsBusy === "stop") ttsBusy = "";
    btn.disabled = false; btn.innerHTML = termLabel("Terminate");
    await load();
  }
}
async function exitPanel(btn) {
  if (!await uiConfirm("Exit PandorumLLM?\\nThis shuts down the panel AND terminates all LLM servers.")) return;
  btn.disabled = true;
  await post("/api/exit", {}).catch(()=>{});
  goodbye();
}
/* The TTS server's own launch button. Same shape as the fleet one - label, arcs, the
   loading and running glows - driven by whether the server is answering rather than by
   how many are. Stopping stays on the TTS page; this only starts. */
async function launchTts(btn) {
  if (btn && btn.classList.contains("lbbusy")) return;
  const eng = String(((state && state.settings) || {}).ttsEngine || "moss").toLowerCase();
  const st = (state && state.settings) || {};
  const need = (eng === "audiocpp")
    ? [["ttsAcppDir", "the audio.cpp folder"], ["ttsAcppModel", "a model"]]
    : [["ttsServerExe", "the MOSS server"], ["ttsModel", "a model"]];
  const miss = need.filter(k => !String(st[k[0]] || "").trim()).map(k => k[1]);
  const NL = String.fromCharCode(10);
  if (miss.length) {
    uiAlert("Set these on the TTS page first:" + NL + NL + "- " + miss.join(NL + "- "));
    showTab("tts");            // its own tab since v3.73
    return;
  }
  window.__ttsLaunching = true;
  const r = await post("/api/tts-server", { action: "start" });
  if (r && r.error) { window.__ttsLaunching = false; uiAlert(r.error); }
  await load();
}
function syncTtsButton() {
  const tb = $("launchTtsBtn");
  if (!tb || !state) return;
  const srv = state.ttsServer || {};
  let s;
  // Terminate stops the TTS server too, but unloading a model is not instant - without a
  // state for it the button kept reading "TTS running..." and looked ignored.
  if (srv.stopping) s = "term";
  else if (String(srv.state || "") === "serving") s = "run";
  else if (window.__ttsLaunching && srv.pid && !srv.died) s = "launching";
  else s = "idle";
  // The panel tells us whether it still has a process. Without that, terminating before
  // the server ever answered left this stuck on "Starting TTS..." with nothing to clear
  // the flag - there was no state that said "it is gone".
  if (s !== "launching") window.__ttsLaunching = false;
  if (window.__tbState === s) return;
  const was = window.__tbState;
  window.__tbState = s;
  clearInterval(window.__ttsArc); window.__ttsArc = null;
  if (s === "term") { tb.innerHTML = arcLabel("Stopping TTS..."); }
  else if (s === "run") { tb.innerHTML = arcLabel("TTS running..."); }
  else if (s === "launching") { tb.innerHTML = arcLabel("Starting TTS..."); }
  else { tb.innerHTML = arcLabel("Launch TTS"); }
  tb.classList.remove("lbload", "lbrun", "lbbusy");
  if (s !== "idle") tb.classList.add("lbbusy");
  if (s === "launching" || s === "term") {
    tb.classList.add("lbload");
    window.__ttsArc = setInterval(function() {
      if (!tb.isConnected) { clearInterval(window.__ttsArc); window.__ttsArc = null; return; }
      arcFire(tb, true);
    }, 130);
  } else if (s === "run") {
    tb.classList.add("lbrun");
    window.__ttsArc = setInterval(function() {
      if (!tb.isConnected) { clearInterval(window.__ttsArc); window.__ttsArc = null; return; }
      arcFire(tb, false);
    }, 150);
  }
}

async function launchStack(btn) {
  if (btn && btn.classList.contains("lbbusy")) return;   // busy, not disabled
  const miss = helperMissing();
  const NL = String.fromCharCode(10);
  if (miss.length && !await uiConfirm("Not everything is set up yet:" + NL + NL + "- " + miss.join(NL + "- ") + NL + NL + "Launch anyway?")) return;
  window.__launching = true; window.__allAnnounced = false;
  window.__terminating = false;
  window.__prevServing = new Set();
  stackSet(nowStamp() + "=== PandorumLLM " + ((state && state.version) || "") + " - launch stack ===" + NL
           + nowStamp() + ">> launching servers, please wait...");
  fleetWatch();
  const r = await post("/api/launch-stack", {});
  stackSet(r.log || r.error || window.__stackTxt);
  load();
}
let loadTimer = null, routeTimer = null;
function queueLoad() {
  clearTimeout(loadTimer);
  loadTimer = setTimeout(function() {
    const busy = uiBusy();
    if (busy) { trace("refresh", "queued reload put off", busy); queueLoad(); return; }
    trace("refresh", "queued reload");
    load();
  }, 150);
}
function queueRouting() {
  clearTimeout(routeTimer);
  routeTimer = setTimeout(() => renderRouting(), 250);   // the tab/focus guard lives inside renderRouting
}
// The ONE per-tab live-refresh rule. SSE events, the auto-refresh tick and the
// heartbeat fallback all come through here - nothing else may spell this out again.
function liveRefresh(src) {
  if (curTab === "dashboard" && curDsub === "term" && src !== "state") {
    refreshCurTerm();
  }
  if (curTab === "dashboard" && curDsub === "yaml" && !(document.activeElement && document.activeElement.closest && document.activeElement.closest("#dpane-yaml"))) renderYaml();
  if (curTab === "helper") renderHelper();
  queueStats(); queueErrors(); queueLoad(); queueRouting();
}
function connectES() {
  if (window.__es) { try { window.__es.close(); } catch (e) {} }
  const es = new EventSource("/api/events");
  es.onmessage = e => {
    let ev = {}; try { ev = JSON.parse(e.data); } catch (x) { return; }
    if (ev.seq) window.__sseSeq = ev.seq;
    if (ev.t === "state") liveRefresh("state");
    if (ev.t === "tail") liveRefresh("tail");
  };
  window.__es = es;
}
connectES();

function showModal(html, resizable) {
  let ov = document.getElementById("pl-modal");
  if (!ov) {
    ov = document.createElement("div");
    ov.id = "pl-modal";
    ov.style.cssText = "position:fixed;inset:0;background:rgba(4,6,10,.66);display:flex;align-items:center;justify-content:center;z-index:9999";
    document.body.appendChild(ov);
  }
  const box = resizable
    ? 'background:var(--card);border:none;border-radius:14px;padding:22px 24px;box-shadow:0 18px 60px rgba(0,0,0,.5);width:560px;max-width:94vw;height:auto;min-width:360px;min-height:260px;max-height:92vh;resize:both;overflow:auto;display:flex;flex-direction:column'
    : 'background:var(--card);border:none;border-radius:14px;max-width:520px;padding:22px 24px;box-shadow:0 18px 60px rgba(0,0,0,.5)';
  ov.innerHTML = '<div style="' + box + '">' + html + '</div>';
  ov.style.display = "flex";
}
function closeModal() { const ov = document.getElementById("pl-modal"); if (ov) { ov.style.display = "none"; ov.innerHTML = ""; } }
function uiDialog(opts) {
  return new Promise(resolve => {
    let ov = document.getElementById("pl-modal");
    if (!ov) {
      ov = document.createElement("div");
      ov.id = "pl-modal";
      ov.style.cssText = "position:fixed;inset:0;background:rgba(4,6,10,.66);display:flex;align-items:center;justify-content:center;z-index:9999";
      document.body.appendChild(ov);
    }
    const boxCss = "background:var(--card);border:none;border-radius:14px;max-width:480px;min-width:300px;padding:20px 22px;box-shadow:0 18px 60px rgba(0,0,0,.5)";
    let h = '<div style="' + boxCss + '">';
    if (opts.title) h += '<h2 style="margin:2px 0 10px;font-size:17px">' + esc(opts.title) + '</h2>';
    if (opts.body) h += '<div style="line-height:1.55;margin-bottom:16px;white-space:pre-line">' + opts.body + '</div>';
    if (opts.input) h += '<input id="pl-dlg-input" class="edit" style="width:100%;box-sizing:border-box;margin-bottom:16px" placeholder="' + esc(opts.input.placeholder || "") + '" value="' + esc(opts.input.value || "") + '">';
    h += '<div class="row" style="justify-content:flex-end;gap:8px" id="pl-dlg-btns"></div></div>';
    ov.innerHTML = h;
    ov.style.display = "flex";
    const inp = document.getElementById("pl-dlg-input");
    const btnRow = document.getElementById("pl-dlg-btns");
    let done = false, keyH = null;
    const finish = v => {
      if (done) return;
      done = true;
      const it = inp ? inp.value : null;
      if (keyH) document.removeEventListener("keydown", keyH, true);
      closeModal();
      resolve({ value: v, input: it });
    };
    const btns = opts.buttons || [];
    const okBtn = btns.find(b => b.value !== false && b.value !== null);
    const okVal = okBtn ? okBtn.value : true;
    btns.forEach(b => {
      const el = document.createElement("button");
      if (b.kind === "secondary") el.className = "stop";
      el.textContent = b.label;
      el.addEventListener("click", () => finish(b.value));
      btnRow.appendChild(el);
    });
    keyH = e => {
      if (e.key === "Enter") { e.preventDefault(); finish(okVal); }
      else if (e.key === "Escape") { e.preventDefault(); finish(opts.cancelValue !== undefined ? opts.cancelValue : false); }
    };
    document.addEventListener("keydown", keyH, true);
    if (inp) { inp.focus(); inp.select(); }
    else { const lb = btnRow.querySelector("button:last-child"); if (lb) lb.focus(); }
  });
}
function uiAlert(msg, title) {
  return uiDialog({ title: title || "", body: esc(String(msg)), buttons: [{ label: "OK", value: true }] }).then(() => {});
}
function uiConfirm(msg, opts) {
  opts = opts || {};
  return uiDialog({ title: opts.title || "", body: esc(String(msg)),
    buttons: [{ label: opts.cancelLabel || "Cancel", kind: "secondary", value: false }, { label: opts.okLabel || "OK", value: true }],
    cancelValue: false }).then(r => r.value === true);
}
function uiPrompt(msg, def, title) {
  return uiDialog({ title: title || "", body: esc(String(msg)), input: { value: def || "" },
    buttons: [{ label: "Cancel", kind: "secondary", value: false }, { label: "OK", value: true }],
    cancelValue: false }).then(r => r.value === true ? (r.input || "") : null);
}
function welcomeGoHelper() { closeModal(); post("/api/settings", { welcomeSeen: true }); showTab("helper"); }
function welcomeDismiss() { closeModal(); post("/api/settings", { welcomeSeen: true }); }
function maybeWelcome() {
  if (!state || !state.settings || state.settings.welcomeSeen) return;
  showModal(
    '<h2 style="margin:2px 0 4px">Welcome To PandorumLLM!</h2>'
    + '<p style="line-height:1.6;margin:8px 0 16px">Head to the <b>User Guide</b> page to get set up - the <b>Main Guide</b> walks you through every step, and the <b>Sampler Guide</b> explains every runtime setting. Want to go there now?</p>'
    + '<div class="row" style="justify-content:flex-end;gap:8px">'
    + '<button class="stop" onclick="welcomeDismiss()">Maybe later</button>'
    + '<button onclick="welcomeGoHelper()">\u2728 Take me to the user guide</button></div>'
  );
}
showTab("network");        // the start page, matching the nav item that starts selected
load().then(maybeWelcome).then(syncFieldInk).then(function() {
  // the Observer was left running last session: pick it up again, without
  // writing the setting back (that would be a no-op write on every page load)
  if (state && state.settings && state.settings.observerOn && !traceOn) traceToggle(true);
  // pick the auto refresh interval back up, without writing the setting again
  const ar = ((state && state.settings) || {}).autoRefresh || 0;
  setTimeout(checkAppUpdate, 1500);   // after the page is up, once per session
  if (ar > 0) {
    const sel = $("auto-ref");
    if (sel) sel.value = String(ar);
    setAutoRef(ar, true);
  }
});
</script></body></html>
"""

# ---- self-timing: /api/state and the debug report name their own slow phases ----
_PH = threading.local()
def _ph_reset():
    _PH.t = {}
def _ph_add(name, dt):
    d = getattr(_PH, "t", None)
    if d is not None:
        d[name] = d.get(name, 0.0) + dt
def _timed(name, fn):
    def w(*a, **k):
        t0 = time.time()
        try:
            return fn(*a, **k)
        finally:
            _ph_add(name, time.time() - t0)
    return w
slot_status = _timed("port-probes", slot_status)
prime_slot_status = _timed("port-probes", prime_slot_status)
list_launchers = _timed("launcher-folder-scan", list_launchers)
_MODELS_LOCK = threading.Lock()
_list_models_once = list_models
def list_models(cfg):
    """Single-flight. The startup warm-up and the first page load used to scan at the
    same moment and read every header twice; now the second caller waits for the
    first and takes its result from the cache."""
    with _MODELS_LOCK:
        return _list_models_once(cfg)
list_models = _timed("model-folder-scan", list_models)
_model_kind_read = _timed("model-header-reads", _model_kind_read)
api_path_check = _timed("folder-checks", api_path_check)
list_templates = _timed("template-scan", list_templates)
parse_ps1_port = _timed("launcher-parse", parse_ps1_port)
parse_ps1_model = _timed("launcher-parse", parse_ps1_model)
parse_ps1_reasoning = _timed("launcher-parse", parse_ps1_reasoning)
parse_log_reasoning = _timed("log-samplers", parse_log_reasoning)
load_config = _timed("config-read", load_config)
_local_ips = _timed("address-lookup", _local_ips)
network_is_down = _timed("address-lookup", network_is_down)
speeds_for_slot = _timed("log-speeds", speeds_for_slot)
parse_log_samplers = _timed("log-samplers", parse_log_samplers)
parse_ps1_samplers = _timed("launcher-parse", parse_ps1_samplers)
_api_state_raw = api_state
def _ph_parts(dt_ms):
    """Phase list with the leftover named, so a slow call is never unexplained."""
    ph = dict(getattr(_PH, "t", {}) or {})
    named = sum(ph.values()) * 1000
    rest = dt_ms - named
    if rest > 1:
        ph["everything-else"] = rest / 1000.0
    return sorted(ph.items(), key=lambda x: -x[1])

def state_probe_ports(cfg=None):
    """Exactly the ports a state read is about to probe.

    Priming used the slot's STORED port while the read uses the one parsed out of the
    launcher script - so whenever a launcher set a different port, the primed entry was
    for the wrong one and the read fell through to a serial probe. The TTS port was not
    primed at all. Both then cost a full timeout each, one after the other, which is
    where 700ms of a 750ms state read was going.
    """
    cfg = cfg or load_config()
    ports = []
    for s in (cfg.get("slots") or []):
        script = s.get("script") or ""
        ports.append((parse_ps1_port(script) if script else None) or s.get("port"))
    st = cfg.get("settings", {})
    if (st.get("ttsServerExe") or st.get("ttsAcppDir") or "").strip():
        ports.append(tts_server_port(cfg))
    return [p for p in ports if p]


def api_state(*a, **k):
    _ph_reset(); t0 = time.time()
    try:
        prime_slot_status(state_probe_ports())
    except Exception:
        pass
    out = _api_state_raw(*a, **k)
    dt = (time.time() - t0) * 1000
    if dt > 500:
        parts = ", ".join("%s=%dms" % (k2, v * 1000) for k2, v in _ph_parts(dt))
        # an observation, not a failure: the read still returned the right answer
        log_warn("panel", "slow /api/state: %dms (%s)" % (dt, parts))
    return out
_debug_report_raw = debug_report
def debug_report():
    _ph_reset(); t0 = time.time()
    try:
        prime_slot_status(state_probe_ports())
    except Exception:
        pass
    txt = _debug_report_raw()
    dt = (time.time() - t0) * 1000
    parts = "\n".join("    %-21s: %dms" % (k2, v * 1000) for k2, v in _ph_parts(dt))
    return (txt.rstrip("\n")
            + "\n\n-- report internals --------------------------------------------\n"
            + "  built in %dms\n" % dt + (parts + "\n" if parts else ""))

def _connect_verdict(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.4)
    try:
        s.connect(("127.0.0.1", port)); s.close(); return "answers"
    except ConnectionRefusedError:
        return "refused"
    except OSError:
        return "timeout/blocked"

def _bind_ok(port, reuse):
    pr = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if reuse:
            pr.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        pr.bind(("0.0.0.0", port)); pr.close(); return True, ""
    except OSError as e:
        return False, str(getattr(e, "winerror", None) or getattr(e, "errno", "") or e)

PORT_DIAGS = []

def _port_bindable(port):
    # used by the handoff wait: "nobody listening" means the old instance is gone
    return _connect_verdict(port) != "answers"

def write_porterror():
    try:
        ld = log_dir()
    except Exception:
        ld = os.path.join(STACK, "logs")
        try: os.makedirs(ld, exist_ok=True)
        except Exception: pass
    p = os.path.join(ld, "PORTERROR.log")
    cands = ", ".join(str(x) for x in PORT_CANDIDATES)
    try:
        with open(p, "w", encoding="utf-8") as f:
            f.write("PandorumLLM could not claim any of its panel ports: %s\n\n" % cands)
            f.write("WHAT EACH PORT REPORTED\n")
            for d in (PORT_DIAGS or ["(no diagnostics collected)"]):
                f.write("  %s\n" % d)
            f.write("\nWHAT TO DO\n")
            f.write("1) See what is using them:\n")
            f.write("     netstat -ano | findstr \"%s\"\n" % " ".join(str(x) for x in PORT_CANDIDATES))
            f.write("   look PIDs up in Task Manager > Details and close that program.\n")
            f.write("2) If netstat shows NOTHING, Windows has likely reserved the range\n")
            f.write("   (Hyper-V / WSL / WinNAT). Check with:\n")
            f.write("     netsh int ipv4 show excludedportrange protocol=tcp\n")
            f.write("3) Or give PandorumLLM different ports: open\n")
            f.write("     %s\n" % os.path.join(STACK, "fleet-panel.py"))
            f.write("   and change the numbers on the marked line near the top:\n")
            f.write("     PORT_CANDIDATES = [%s]\n" % cands)
            f.write("   if you use the bat instead of the exe.\n")
    except Exception:
        pass
    return p

def _kill_port_owner(port):
    try:
        subprocess.run(["pwsh", "-NoProfile", "-Command",
            "$c = Get-NetTCPConnection -LocalPort %d -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1; "
            "if ($c) { Stop-Process -Id $c.OwningProcess -Force }" % port],
            capture_output=True, timeout=15, **NOWIN)
    except Exception:
        pass

def choose_port(deadline_s=6.5):
    """Bind is the ground truth: transparent proxies and phantom answerers can't
    fake it, and Windows reserved/excluded ranges fail it honestly. The connect
    probe is only used to spot our OWN instance for a graceful handoff."""
    del PORT_DIAGS[:]
    t0 = time.time()
    for cand in PORT_CANDIDATES:
        if time.time() - t0 > deadline_s:
            PORT_DIAGS.append("%d: not checked (time budget)" % cand)
            continue
        conn = _connect_verdict(cand)
        if conn == "answers":
            ours = False
            try:
                r = _ureq.urlopen("http://127.0.0.1:%d/" % cand, timeout=0.9)
                hdr = r.headers.get("X-App", "") or ""
                body = r.read(4096).decode("utf-8", "replace")
                ours = (APP_NAME in hdr) or (APP_NAME in body)
            except Exception:
                pass
            if ours:
                try:
                    was = hdr.split(APP_NAME, 1)[1].strip() if APP_NAME in hdr else ""
                    if was and was != APP_VER_UI:
                        TAKEOVER.append("took over a running %s - this one is %s" % (was, APP_VER_UI))
                except Exception:
                    pass
                try:
                    _ureq.urlopen(_ureq.Request("http://127.0.0.1:%d/api/handoff" % cand,
                                  data=b"{}", method="POST"), timeout=2).read()
                except Exception:
                    pass
                waited = 0.0
                while waited < 2.2 and not _port_bindable(cand):
                    time.sleep(0.25); waited += 0.25
                if _port_bindable(cand):
                    return cand
                _kill_port_owner(cand)          # stuck instance of OURS - force it down
                waited = 0.0
                while waited < 3.0 and not _port_bindable(cand):
                    time.sleep(0.25); waited += 0.25
                if _port_bindable(cand):
                    return cand
                PORT_DIAGS.append("%d: a stuck PandorumLLM would not die" % cand)
                continue
            try:
                st = json.loads(_ureq.urlopen("http://127.0.0.1:%d/api/state" % cand, timeout=0.7).read() or b"{}")
                if st.get("app") == APP_NAME:
                    _ureq.urlopen(_ureq.Request("http://127.0.0.1:%d/api/handoff" % cand,
                                  data=b"{}", method="POST"), timeout=2).read()
                    waited = 0.0
                    while waited < 2.2 and not _port_bindable(cand):
                        time.sleep(0.25); waited += 0.25
                    if _port_bindable(cand):
                        return cand
                    PORT_DIAGS.append("%d: our old instance would not release it" % cand)
                else:
                    PORT_DIAGS.append("%d: another program answers connections here" % cand)
            except Exception:
                PORT_DIAGS.append("%d: something answers connections but not as PandorumLLM" % cand)
            continue
        ok, err = _bind_ok(cand, reuse=False)
        if ok:
            return cand
        ok2, err2 = _bind_ok(cand, reuse=True)
        if ok2:
            return cand   # plain bind blocked only by TIME_WAIT; the real server binds with reuse
        PORT_DIAGS.append("%d: Windows refused the bind (in use or in a reserved/excluded range) [%s] - connect probe said: %s"
                          % (cand, err2 or err, conn))
    return None

# ---------------------------------------------------------------- main
def main():
    try:
        import threading as _th
        clear_download_mark()          # so SmartScreen only ever has to be answered once
        chosen = choose_port()
        if chosen is None:
            p = write_porterror()
            msg = ("No free panel port - tried %s.\nSee instructions in:\n%s"
                   % (", ".join(str(x) for x in PORT_CANDIDATES), p))
            print(msg)
            try:
                ctypes.windll.user32.MessageBoxW(None, msg, "%s %s" % (APP_NAME, APP_VERSION), 0x30)
            except Exception:
                pass
            return
        # 7. the TTS log is one fixed file, so it would otherwise carry every past
        # session forward. The fleet logs already start fresh per run.
        try:
            _tl = os.path.join(log_dir(), TTS_LOG_NAME)
            if os.path.isfile(_tl):
                with open(_tl, "w", encoding="utf-8"):
                    pass
        except Exception:
            pass
        globals()["PORT"] = chosen
        try:
            with open(os.path.join(STACK, "panel-port.txt"), "w", encoding="utf-8") as f:
                f.write(str(PORT))
        except Exception:
            pass

        def _background_init():
            try:
                cfg0 = load_config()   # migrate/seed config + settings on first run
                for k in ("launcherDir", "outputDir", "logDir", "modelsDir", "yamlOutDir"):
                    d = cfg0.get("settings", {}).get(k)
                    if d:
                        try:
                            os.makedirs(d, exist_ok=True)
                        except Exception:
                            pass
                ld = log_dir()
                prune_keep_newest(ld, "*_dashboard.log", 4)   # this session's file makes 5
                prune_keep_newest(ld, "*_thinking.log", 4)
                # not an error: this used to create an error_N.log on every clean
                # run. The file writes its own header naming the version when a
                # real error first arrives, so nothing is lost.
                panel_log("[panel] session start %s" % APP_VER_UI)
                PROXY.sync()    # embedded SN proxy listeners come up with the panel
                try:
                    TTSW.sync()     # embedded TTS wrapper, only if it has been switched on
                except Exception:
                    log_error("tts", "wrapper sync at startup failed")
                try:
                    api_detect_gpus({})
                except Exception:
                    pass
                _th.Thread(target=watchdog_loop, daemon=True).start()
                _th.Thread(target=status_watch_loop, daemon=True).start()
            except Exception:
                log_error("panel", "background init failed: %s" % traceback.format_exc(limit=3))

        _th.Thread(target=_background_init, daemon=True).start()
        srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
        print("%s %s   : http://localhost:%d/" % (APP_NAME, APP_VER_UI, PORT))
        print("file         : %s" % BUILD_ID.get("path", "?"))
        print("build        : %s  (%s KB, %s)" % (BUILD_ID.get("sha", "?"), BUILD_ID.get("kb", 0), BUILD_ID.get("mtime", "?")))
        for _t in TAKEOVER:
            print("NOTE         : %s" % _t)
        # the first model scan reads a header per file; do it now, off the request
        # path, so the first page load is not the thing that waits for it
        _th.Thread(target=lambda: list_models(load_config()), daemon=True).start()
        _th.Thread(target=_peer_loop, daemon=True).start()
        print("From the LAN : http://<this-machine-ip>:%d/" % PORT)
        print("Config       : %s" % CONFIG)
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            pass
        except Exception:
            traceback.print_exc()
            time.sleep(30)
    except SystemExit:
        raise
    except Exception:
        tb = traceback.format_exc()
        try:
            ld = os.path.join(STACK, "logs")
            os.makedirs(ld, exist_ok=True)
            with open(os.path.join(ld, "STARTUP-CRASH.log"), "w", encoding="utf-8") as f:
                f.write("PandorumLLM %s failed to start\n\n%s" % (APP_VERSION, tb))
        except Exception:
            pass
        try:
            ctypes.windll.user32.MessageBoxW(None,
                "PandorumLLM failed to start.\nDetails: logs\\STARTUP-CRASH.log",
                "%s %s" % (APP_NAME, APP_VERSION), 0x10)
        except Exception:
            pass

if __name__ == "__main__":
    main()
