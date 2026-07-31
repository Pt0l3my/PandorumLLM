#!/usr/bin/env python3
"""PandorumLLM release gate - run on the staging copy, blocks packaging.

    python3 gate.py [tree]

Implements DEVELOPMENT.md section 8. Every check here must be capable of failing:
a check that confirms a function *exists* is not a check (section 8), and a check
built from the thing it tests cannot fail (gotcha 17). Where a check cannot be run
in this environment it is reported as SKIP, never as a pass.

Line-ending and per-line checks read bytes, never text mode - universal newlines
collapse CRLF on read and make such a check silently examine nothing (gotcha 18).
"""
import io
import os
import re
import sys
import ast
import json
import shutil
import string
import subprocess
import tempfile
import importlib.util
import collections

ROOT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
FAIL, SKIP = [], []
_section = ""


def section(name):
    global _section
    _section = name
    print("\n== %s ==" % name)


def check(ok, label, detail=""):
    if ok is None:
        SKIP.append((_section, label, detail))
        print("  SKIP %s %s" % (label, detail))
    elif ok:
        print("  ok   %s" % label)
    else:
        FAIL.append((_section, label, detail))
        print("  FAIL %s %s" % (label, detail))


def rd(rel):
    with open(os.path.join(ROOT, rel), "rb") as f:
        return f.read()


# --------------------------------------------------------------- 1. file set
section("file set")

SHIPPED = ["fleet-panel.py", "README.txt", "PandorumLLM.exe", "PandorumLLM.ico",
           "force-stop.bat", "StartPandorumLLM.bat", "launch-llm-fleet.ps1", "launcher-template.ps1",
           "fleet-config.default.json", "templates/single-gpu.ps1",
           "ps1-launchers/README.txt", "launcher-src/launcher.cpp",
           "launcher-src/app.rc", "launcher-src/app.manifest",
           "launcher-src/PandorumLLM.ico"]
# a source tree has no exe - it is gitignored and built at release time. Report which
# kind of tree this is rather than failing on the difference.
IS_REPO = os.path.isfile(os.path.join(ROOT, ".gitignore")) and \
          "PandorumLLM.exe" in rd(".gitignore").decode("utf-8", "replace")
print("  (%s tree)" % ("source" if IS_REPO else "release"))
for rel in SHIPPED:
    there = os.path.isfile(os.path.join(ROOT, rel))
    if rel.endswith(".exe") and IS_REPO and not there:
        check(None, "present: %s" % rel, "source tree - built at release time")
    else:
        check(there, "present: %s" % rel)

for junk in ("__pycache__", "logs", "models", "providerYAML", "panel-port.txt",
             "fleet-config.json", "model-kinds.json", "profiles",
             "generated-launchers"):
    check(not os.path.exists(os.path.join(ROOT, junk)), "absent: %s" % junk)


# --------------------------------------------------------------- 2. encoding
section("encoding (section 6)")

RULES = {".py": ("nobom", "crlf"), ".bat": ("nobom", "crlf"),
         ".ps1": ("bom", "crlf"), ".rc": ("nobom", "lf"),
         ".manifest": ("nobom", "lf"), ".md": ("nobom", "lf")}
LF_PS1 = {"launch-llm-fleet.ps1"}          # documented exception: BOM + LF

for dirpath, dirnames, filenames in os.walk(ROOT):
    dirnames[:] = [d for d in dirnames if d not in (".git", "__pycache__")]
    for fn in sorted(filenames):
        ext = os.path.splitext(fn)[1].lower()
        if ext not in RULES:
            continue
        rel = os.path.relpath(os.path.join(dirpath, fn), ROOT).replace("\\", "/")
        raw = rd(rel)
        want_bom, want_eol = RULES[ext]
        has_bom = raw[:3] == b"\xef\xbb\xbf"
        check(has_bom == (want_bom == "bom"), "%s BOM" % rel,
              "got %s want %s" % (has_bom, want_bom == "bom"))
        crlf = raw.count(b"\r\n")
        bare = raw.count(b"\n") - crlf
        lone = raw.count(b"\r") - crlf
        if fn in LF_PS1 or want_eol == "lf":
            check(crlf == 0 and lone == 0, "%s LF-only" % rel, "crlf=%d" % crlf)
        else:
            check(bare == 0 and lone == 0, "%s CRLF-only" % rel,
                  "bareLF=%d loneCR=%d" % (bare, lone))

check(b"^" not in rd("force-stop.bat"), "force-stop.bat has no carets")


# --------------------------------------------------------- 3. version agreement
section("version agreement (BUILD.md)")

py = rd("fleet-panel.py").decode("utf-8")
ver = re.search(r'APP_VERSION\s*=\s*"v([\d.]+) Beta"', py).group(1)
tag = re.search(r'APP_RELEASE_TAG\s*=\s*"([^"]+)"', py).group(1)
patch = int(re.search(r"APP_PATCH\s*=\s*(\d+)", py).group(1))
rc = rd("launcher-src/app.rc").decode("utf-8")
mf = rd("launcher-src/app.manifest").decode("utf-8")
dotted, commad = "%s.0.0" % ver, "%s,0,0" % ver.replace(".", ",")

check(rc.count("FILEVERSION " + commad) == 1, "app.rc FILEVERSION", commad)
check(rc.count("PRODUCTVERSION " + commad) == 1, "app.rc PRODUCTVERSION", commad)
check(rc.count('"FileVersion", "%s"' % dotted) == 1, "app.rc FileVersion string")
check(rc.count('"ProductVersion", "%s"' % dotted) == 1, "app.rc ProductVersion string")
check(('version="%s"' % dotted) in mf, "app.manifest assemblyIdentity")
check(tag.startswith("v" + ver), "APP_RELEASE_TAG matches version", tag)
check((patch > 0) == ("patch" in tag), "APP_PATCH agrees with tag",
      "patch=%d tag=%s" % (patch, tag))
check(("v%s Beta" % ver) in rd("README.txt").decode("utf-8", "replace")[:200],
      "README.txt title version")
if os.path.isfile(os.path.join(ROOT, "PandorumLLM.exe")):
    try:
        blob = rd("PandorumLLM.exe")
        want = dotted.encode("utf-16-le")
        check(want in blob, "exe version resource", dotted)
    except Exception as e:
        check(None, "exe version resource", str(e))
else:
    check(None, "exe version resource", "no exe in tree")


# ------------------------------------------------------------- 4. syntax
section("syntax")

check(bool(ast.parse(py)), "fleet-panel.py parses")

m = re.search(r'^PAGE = """', py, re.M)
lit = py[m.start():py.index('"""', m.end()) + 3]
ns = {}
exec(compile(lit, "page", "exec"), ns)
PAGE = ns["PAGE"]
PAGE_RAW = PAGE
PAGE = PAGE.replace("__TSKINDS__", json.dumps(list(
    re.findall(r'"(\w+)"', re.search(r"TERM_SCALE_KINDS = \(([^)]*)\)", py).group(1)))))
scripts = re.findall(r"<script>(.*?)</script>", PAGE, re.S)
JS = "\n;\n".join(scripts)
jsf = os.path.join(tempfile.mkdtemp(), "page.js")
open(jsf, "wb").write(JS.encode("utf-8", "surrogatepass"))
r = subprocess.run(["node", "--check", jsf], capture_output=True, text=True)
check(r.returncode == 0, "node --check on the page script", r.stderr[:200])


# ------------------------------------------------------------- 5. privacy
section("privacy (redact_state)")

spec = importlib.util.spec_from_file_location("fp", os.path.join(ROOT, "fleet-panel.py"))
fp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fp)

# Fixtures are documentation-reserved values ONLY - RFC 5737 TEST-NET-1 for addresses,
# an all-zero UUID, a drive letter and folders that exist on no real machine. A fixture
# copied from a real setup puts that setup in the repository, and this file is committed.
SECRETS = {
    "model filename": "fixture-model.gguf",
    "projector": "fixture-mmproj.gguf",
    "draft": "fixture-draft.gguf",
    "launcher path": r"Z:\fixture\launchers\slot.ps1",
    "llamacpp path": r"Z:\fixture\llamacpp",
    "models dir": r"Z:\fixture\models",
    "panel IP": "192.0.2.11",
    "remote IP": "192.0.2.12",
    "peer address": "192.0.2.99",
    "GPU serial": "GPU-00000000-0000-0000-0000-000000000000",
}
slot = {"id": "s1", "gpuId": "g1", "gpu": SECRETS["GPU serial"],
        "script": SECRETS["launcher path"], "model": SECRETS["model filename"],
        "params": {"model": SECRETS["model filename"], "vision": SECRETS["projector"],
                   "draft": SECRETS["draft"]},
        "providers": [{"id": "p1", "title": "Dialogue", "port": "1251"}]}
state = {
    "settings": {"panelIp": SECRETS["panel IP"], "remoteIp": SECRETS["remote IP"],
                 "peerAddr": SECRETS["peer address"],
                 "llamacppPath": SECRETS["llamacpp path"], "modelsDir": SECRETS["models dir"],
                 "outputDir": r"Z:\fixture\out", "logDir": r"Z:\fixture\logs"},
    "gpus": [{"id": "g1", "uuid": SECRETS["GPU serial"], "index": "0",
              "name": "Fixture Card"}],
    "slots": [json.loads(json.dumps(slot))],
    # routing entries are built separately and carry no "params" - mirror that exactly,
    # or the fixture invents a leak the product does not have
    "routing": [{"id": "s1", "label": "dialogue", "port": "1236", "gpuId": "g1",
                 "gpu": SECRETS["GPU serial"], "model": SECRETS["model filename"],
                 "providers": [{"id": "p1", "title": "Dialogue", "port": "1251"}]}],
}
red = json.dumps(fp.redact_state(json.loads(json.dumps(state))))
for label, secret in SECRETS.items():
    check(secret not in red, "redacted: %s" % label, secret)
check('"gpuId": "g1"' in red, "gpuId NOT masked (remote graph needs it)")
check('"scope": "remote"' in red, "scope set to remote")
check("Dialogue" in red, "provider titles kept (routing info, not secret)")

# the same state must survive the round trip unharmed for a host reader
host = json.dumps(state)
check(SECRETS["model filename"] in host, "host state still complete (control)")

section("privacy (shipped files)")
LEAKS = [(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "email address"),
         (r"GPU-[0-9a-f]{8}-[0-9a-f]{4}", "GPU serial"),
         (r"C:\\Users\\[A-Za-z]", "a personal user folder"),
         (r"\balucard\b", "a machine name")]
# every file in the tree, this gate included. Reserved forms below are the only
# values a fixture may use, so scanning its own fixtures costs nothing.
RESERVED = ("192.0.2.", "198.51.100.", "203.0.113.",
            "GPU-00000000-0000", r"Z:\fixture")
for dirpath, dirnames, filenames in os.walk(ROOT):
    dirnames[:] = [d for d in dirnames if d not in (".git", "__pycache__")]
    for fn in sorted(filenames):
        if os.path.splitext(fn)[1].lower() in (".exe", ".ico", ".o"):
            continue
        rel = os.path.relpath(os.path.join(dirpath, fn), ROOT).replace("\\", "/")
        txt = rd(rel).decode("utf-8", "replace")
        for pat, what in LEAKS:
            hits = [h for h in re.findall(pat, txt)
                    if not any(r in h or h in r for r in RESERVED)]
            if hits:
                check(False, "%s contains %s" % (rel, what), str(hits[:2]))
check(True, "personal-data scan completed")

# A repo-wide sweep for concrete identifiers. The allowlist is the app's OWN public
# values - its install folder, the placeholder it ships, the peer-address example a
# user must be able to recognise, and the loopback route-lookup target. Anything
# else matching these shapes is a real machine's details in a published repository.
IDENT_ALLOW = ("C:\\PandorumLLM C:\\llama.cpp-cuda 192.168.1.20 10.255.255.255 192.0.2. 198.51.100. 203.0.113. GPU-00000000 Z:\\fixture sammcj/openmoss".split())  # one line: every continuation would need the same exemption marker
IDENT = {
    "a private IPv4": r"\b(?:10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(?:1[6-9]|2\d|3[01])\.\d+\.\d+)\b",
    "a GPU serial": r"GPU-[0-9a-f]{8}-[0-9a-f]{4}",
    "an email address": r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
    "a user profile folder": r"C:\\+Users\\+[A-Za-z]",
    "a windows drive path": r"\b[C-Y]:\\+[A-Za-z][\w.-]*",
}
_ident_hits = []
for _dp, _dns, _fns in os.walk(ROOT):
    _dns[:] = [d for d in _dns if d not in (".git", "__pycache__")]
    for _fn in sorted(_fns):
        if os.path.splitext(_fn)[1].lower() in (".exe", ".ico", ".o", ".png", ".zip"):
            continue
        _rel = os.path.relpath(os.path.join(_dp, _fn), ROOT).replace("\\", "/")
        _t = rd(_rel).decode("utf-8", "replace")
        _keep = [l for l in _t.split("\n") if not re.match(r'\s*\(r"', l)
                 and "IDENT_ALLOW" not in l and '"a windows drive path"' not in l
                 and '"a user profile folder"' not in l]
        _body = "\n".join(_keep)
        _flat = lambda s: re.sub(r"\\\\+", "\\\\", s)
        for _what, _pat in IDENT.items():
            for _h in set(re.findall(_pat, _body)):
                _hf = _flat(_h)
                if not any(_flat(a) in _hf or _hf in _flat(a) for a in IDENT_ALLOW):
                    _ident_hits.append((_rel, _what, _h))
check(not _ident_hits, "no machine-specific identifier anywhere in the tree",
      str(_ident_hits[:3]))

# a fixture lifted from a real machine is how private data reaches a public repo
_priv = re.compile(r"\b(?:10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(?:1[6-9]|2\d|3[01])\.\d+\.\d+)\b")
# the FILE BEING RUN, not a name looked up in the tree: reading "gate.py" from ROOT
# meant a copy run from elsewhere checked a different file and always passed
_selves = {os.path.abspath(__file__)}
if os.path.isfile(os.path.join(ROOT, "gate.py")):
    _selves.add(os.path.abspath(os.path.join(ROOT, "gate.py")))
for _self in sorted(_selves):
    _rel = os.path.basename(_self)
    if True:
        _t = open(_self, "rb").read().decode("utf-8", "replace")
        _f = sorted(set(_priv.findall("\n".join(
            l for l in _t.split("\n") if "ALLOW" not in l and "RESERVED" not in l))))
        check(not _f, "%s uses reserved addresses, not real private ones" % _rel, str(_f[:3]))
        # skip the LEAKS tuples: a detector has to contain the very string it looks
        # for, so scanning it would make this check impossible to satisfy
        _lines = [l for l in _t.split("\n")
                  if not re.match(r'\s*\(r"', l) and "ALLOW" not in l and "RESERVED" not in l]
        _d = sorted(set(re.findall(r"[A-Y]:\\\\[A-Za-z][\w.-]*", "\n".join(_lines))))
        check(not _d, "%s uses no real-looking drive paths" % _rel, str(_d[:3]))


# --------------------------------------------------------- 6. remote boundary
section("terminal scale kinds")
# The kind list lived in Python (api_settings) and JS (TS_KINDS) separately, so a kind
# the page knew about was silently dropped on save. One list now, injected into the page.
_pk = re.findall(r'"(\w+)"', re.search(r"TERM_SCALE_KINDS = \(([^)]*)\)", py).group(1))
check("__TSKINDS__" in PAGE_RAW, "the page takes its kind list from Python, not a copy")
check("TERM_SCALE_KINDS" in py[py.index("def api_settings"):py.index("def api_settings") + 6000],
      "api_settings validates against the same list")
check("tts" in _pk, "tts is a registered scale kind", str(_pk))
for _k in _pk:
    for _pre in ("termscale-auto-", "termscale-manual-", "tscalebtn-", "termfs-sel-",
                 "termfont-sel-", "termfs-wrap-", "termscale-msg-"):
        if _k in ("splitd", "splitt", "dashboard", "thinking", "tts"):
            check(('id="%s%s"' % (_pre, _k)) in PAGE,
                  "control exists: %s%s" % (_pre, _k))
    check(('id="tail-%s"' % _k) in PAGE or _k in ("splitd", "splitt"),
          "tail element exists for %s" % _k)
check(('data-act="tmaxAdjust"' in PAGE[PAGE.index('id="twrap-tts"'):PAGE.index('id="twrap-tts"') + 900]),
      "the TTS terminal has an Adjust menu like the others")

# a terminating server holds its port without answering; that is not "stopped"
# unloading a large model is not instant, and a synchronous stop blocks the very
# response that would report it - the shutdown was real but unobservable
_ss2 = py[py.index("def stop_tts_server"):py.index("def api_tts_server")]
check("wait=True" in _ss2 and "wait=False" not in _ss2.split("def _finish")[0].split("\n")[0],
      "stop can report progress instead of blocking")
check("threading.Thread" in _ss2, "the non-blocking path terminates off the request thread")
check(_ss2.index('sse_notify("state")') < _ss2.index("_finish"),
      "it announces the stop BEFORE blocking, not after")
check('stop_tts_server("terminate button", wait=False)' in py, "Terminate reports progress")
_ta = JS[JS.index("async function terminateAll"):JS.index("async function exitPanel")]
check("ttsBusy" in _ta,
      "terminateAll marks the TTS pane - queueLoad defers reloads while a write is in flight")
check("finally" in _ta, "and clears the mark even if the request fails")
check(JS.count('"stopping"') == 0 or "shutting down" in JS,
      "one phrase for the shutting-down state, not two")
check('stop_tts_server("stop button", wait=False)' in py, "the Stop button reports progress")
_fe2 = py[py.index("def full_exit"):py.index("def watchdog_loop")]
check("wait=False" not in _fe2, "the exit path still waits - the process is about to end")
check('out["stopping"]' in py, "status carries a stopping flag")
check("sv.stopping" in JS, "the pane reads the reported flag, not only an inferred port state")
check('svGoing' in JS and '"wedged"' in JS, "a port held but silent also reads as shutting down")
check('shutting down' in JS, "the pane says so rather than jumping straight to stopped")


section("launch button arc toggle")
# a boolean that reaches the catch-all is str()'d, and JS reads "False" as truthy -
# the bug that made 2-PC mode keep reverting (gotcha 5)
check('"launchArc": True' in py or '"launchArc": False' in py,
      "launchArc is seeded as a real bool, not a string")
_as = py[py.index("def api_settings"):py.index("def api_settings") + 6000]
check('"exitOnClose", "launchArc"' in _as or '"launchArc", "exitOnClose"' in _as,
      "launchArc is coerced to bool rather than stringified by the catch-all")
_af = JS[JS.index("function arcFire"):JS.index("function arcFire") + 500]
check("launchArc === false" in _af, "the effect is guarded inside arcFire itself")
# the property is "no arcFire call site guards itself", not "the string appears twice":
# reading the setting to render the switch, or to pick the guide fallback, is not a guard
_sites = [m.start() for m in re.finditer(r"\barcFire\(", JS)]
_selfguarded = [JS[max(0, s - 200):s] for s in _sites
                if "launchArc" in JS[max(0, s - 200):s]]
check(not _selfguarded, "no arcFire call site guards itself - the guard is inside arcFire",
      "%d of %d sites carry their own check" % (len(_selfguarded), len(_sites)))
check(len(_sites) >= 6, "all the arc call sites are covered by that one guard",
      "%d sites" % len(_sites))
check('data-act="launchArcToggle"' in PAGE or "launchArcToggle" in JS,
      "the toggle exists on the Customization page")
check('d.act === "launchArcToggle"' in JS, "and has a handler")
_rc2 = JS[JS.index("function renderCustom"):JS.index("function renderCustom") + 3000]
check("swToggle(arcOn" in _rc2, "it uses the shared switch control, not a bespoke one")
# step 8 calls helperGo with no selector because the arc was meant to do the pointing;
# with the arc off the step had nothing to point at
_ld = JS[JS.index("function launchDemo"):JS.index("function flashTargets")]
check("launchArc === false" in _ld and "flashTargets" in _ld,
      "the guide step falls back to the standard highlight when the arc is off")
check(_ld.index("launchArc === false") < _ld.index("lbdemo"),
      "and returns before the arc loop rather than running both")
# a checkbox sits inside a label, so a click lands on the styling span where .checked is
# undefined. Switches belong on "change", where every other one already is.
_clickblk = JS[JS.rindex('document.addEventListener("click"'):]
check("launchArcToggle" not in _clickblk,
      "the switch is not handled on click, where the target is the label")
_chg = JS[JS.index('d.act === "provField"') - 900:JS.index('d.act === "provField"')]
check("launchArcToggle" in _chg, "it is handled on change, beside the other switches")


section("TTS engine adapter")
check('"ttsEngine": "moss"' in py, "engine defaults to moss - an existing install is unchanged")

_sp = py[py.index("def tts_acpp_speak"):py.index("def tts_server_port")]
check('"/v1/audio/speech"' in _sp, "audio.cpp adapter targets the OpenAI speech route")
check('"voice_ref"' in _sp and "b64" not in _sp,
      "reference passed as a path, never base64 - the server takes a local path")
check("reference_text" in _sp, "reference transcript is forwarded when present")
check("HTTPError" in _sp and "e.read()" in _sp,
      "upstream failures surface the server's own body, as the MOSS path does")

_cf = py[py.index("def tts_acpp_config"):py.index("def tts_acpp_speak")]
check('"device": 0' in _cf and "CUDA_VISIBLE_DEVICES" in _cf,
      "config pins by env mask with device 0, not by index",
      "an index reorders across driver updates; the UUID does not")
check("lazy_load" not in _cf.split('"""')[2] if '"""' in _cf else True,
      "lazy_load is off so /health answering means the model is really loaded")
check("busy_timeout_ms" in _cf,
      "a bound on queued requests - the server serializes per model")
check("reference_cache_slots" in _cf,
      "the encoded-reference cache is raised from its default of one")
check("min(int(" in _cf and "1024" in _cf, "and a typo cannot ask for an absurd number")
check("ttsAcppRefSlots" in JS, "the cache size is the user's to set, not a fixed guess")

_run = py[py.index("def _run"):py.index("def _silence")]
check('tts_engine(cfg) == "audiocpp"' in _run, "the generate path branches on engine")
check(_run.index("ttsAnswerPing") < _run.index('tts_engine(cfg) == "audiocpp":'),
      "the local ping answer runs before either engine arm, not once per engine")
_acpp_arm = _run[_run.index('== "audiocpp"'):_run.index("ref_b64, cached")]
check("tts_chunks" not in _acpp_arm and "ThreadPoolExecutor" not in _acpp_arm,
      "no chunking or concurrency on the audio.cpp arm - the server does both itself")
check("tts_wav_join" not in _acpp_arm, "and no WAV stitching, since one request returns one file")

_srv = py[py.index("def api_tts_server"):py.index("def api_launcher_content")]
check('eng == "audiocpp"' in _srv, "starting the server branches on engine")
check('"--config"' in _srv, "audio.cpp is started from a config the panel writes")
check("os.path.isdir" in _srv, "the audio.cpp model is validated as a folder, not a file")

_fs = JS[JS.index("const TTS_FIELDSETS"):JS.index("function ttsFields")]
check('"ttsPython"' not in _fs.split("audiocpp:")[1], "audio.cpp field set has no python path")
check('"ttsWrapper"' not in _fs.split("audiocpp:")[1], "and no wrapper script path")
check("ttsPickDir" in JS and "pickTtsFolder" in JS, "the model folder can be picked, not only typed")

# generated lines used to land in a temp folder with an opaque name
_sn = py[py.index("def tts_save_named"):py.index("def tts_diagnose")]
check("%Y%m%d_%H%M%S" in _sn, "saved lines are named as the reference wrapper named them")
check("[^A-Za-z0-9_-]" in _sn, "the speaker name is made filesystem-safe")
check("os.path.exists(path)" in _sn, "two lines in the same second do not overwrite each other")
# check the code, not the prose - the docstring says "nothing is pruned" and a
# substring test on the whole function matched its own comment
_sn_code = re.sub(r'""".*?"""', "", _sn, flags=re.S)
check(not re.search(r"os\.(remove|unlink)|rmtree|\.prune\(", _sn_code),
      "nothing is deleted from the user's own folder", _sn_code[:120])
_acpp2 = py[py.index('== "audiocpp"'):py.index("ref_b64, cached")]
check('os.path.join(self.dir(), "out-%s.wav" % eid)' in _acpp2,
      "the SERVED file stays in the jail; the named copy is alongside")
check("tts_save_named" in _acpp2, "and the audio.cpp arm keeps one")
check('"ttsOutDir"' in JS.split("moss:")[1].split("audiocpp:")[0]
      and '"ttsOutDir"' in JS.split("audiocpp:")[1][:900],
      "the output folder is offered for both engines")
check("gen_s or dec_s" in _acpp2,
      "the time is split only when the server reports it, not invented")
check("srv_s = time.time() - _t_post" in py,
      "the request is timed, so server time and panel overhead are measured not guessed")
check("audio.cpp response headers seen" in py,
      "unrecognised response headers are logged once, so the real names can be learned")
check("TTS_ACPP_FRAME_RATE" in py, "token counts use Higgs' own frame rate, not MOSS'")

# the LLM side scans a models folder and offers a dropdown; TTS now works the same way
_ls = py[py.index("def list_tts_models"):py.index("def api_tts_models")]
check(".gguf" in _ls and "model.safetensors" in _ls,
      "the scanner finds both shapes audio.cpp loads: a .gguf file and a safetensors folder")
check("PART_RX" in _ls, "sharded models appear once, not once per part")
check("shadowed" in _ls,
      "a safetensors folder holding a .gguf is marked - audio.cpp silently loads the gguf")
check("count(os.sep) > 3" in _ls, "walk is depth-bounded like list_models")
check("_tts_models_cache" in _ls, "and cached, so opening the page does not rescan every time")
_ro = set(re.findall(r'"(/[^"]+)"', re.search(r"REMOTE_READ_OK = \{(.*?)\}", py, re.S).group(1)))
_po = set(re.findall(r'"(/[^"]+)"', re.search(r"REMOTE_POST_OK = \{(.*?)\}", py, re.S).group(1)))
check("/api/tts-models" not in (_ro | _po), "the model list is host-only - it discloses paths")

_sg = py[py.index("def api_tts_server"):py.index("def api_launcher_content")]
check("os.path.exists" in _sg, "a selected model may be a file or a folder")
check("loads instead of the" in _sg,
      "starting refuses a safetensors folder shadowed by a gguf rather than loading the wrong one")
check("ttsModelSel" in JS and "ttsModelRescan" in JS, "the page offers selection and a rescan")


section("error handlers do not throw")
# an error handler that throws replaces the real failure with its own, which is how a
# connection blip surfaced as "can't access property textContent"
for _m in re.finditer(r"catch\s*\([^)]*\)\s*\{([^{}]*)\}", JS):
    _body = _m.group(1)
    _bad = re.findall(r'\$\("([^"]+)"\)\s*\.\w+\s*=', _body)
    check(not _bad, "catch block does not assign through an unguarded $()", str(_bad))


section("audio.cpp folder + guide")
_fa = py[py.index("def find_acpp_exe"):py.index("def api_acpp_update")]
check("os.walk" in _fa and "count(os.sep) > 4" in _fa,
      "the server is found under a folder, prebuilt (flat) or source build (nested)")
check('"ttsAcppDir"' in JS, "the user names a folder, not an executable")
check('["ttsAcppExe"' not in JS, "and cannot point the field at an arbitrary .exe")
_bt = JS[JS.index("async function browseTo"):JS.index("async function browseTo") + 700]
check("path: \"\"" in _bt,
      "a browse that lands on a non-folder falls back rather than dead-ending")
check("Proxy TTS Port" in PAGE and "Wrapper Port (point" not in PAGE,
      "the port is named for what it is, not for the wrapper that may not exist")
check("/api/acpp-update" in py and "0xShug0/audio.cpp" in py,
      "audio.cpp has an update check, on the same terms as the llama.cpp one")
_au = py[py.index("def api_acpp_update"):py.index("def tts_save_named")]
check("body=None" in _au and "urlopen" in _au, "it runs only when asked")
_hg = JS[JS.index("function renderHiggsGuide"):JS.index("function renderMossGuide")]
for _n in ("audio.cpp/releases", "audio.cpp-gguf", "q8_0", "bf16", "Models"):
    check(_n in _hg, "the Higgs guide names %s" % _n)
check("String.fromCharCode(92)" in _hg,
      "backslashes are built, not escaped - the PAGE string eats them otherwise")
# the engines are pages WITHIN the TTS guide, not siblings of it
_us = JS[JS.index("function showUgSub"):JS.index("function showUgSub") + 400]
check('"higgs"' not in _us, "Higgs is not a top-level guide tab")
check("tgpane-higgs" in JS and "tgpane-moss" in JS, "both engines live inside the TTS guide")
check('class="subtabs"' in JS[JS.index("function renderTtsGuide"):JS.index("function hgStep")],
      "and use the same tab styling as everywhere else")

# a copyable block should look copyable, and say so when it worked
check("copy:" in PAGE and "<svg" in PAGE[PAGE.index("copy:"):PAGE.index("copy:") + 200],
      "the copy affordance is an SVG - emoji render as ?? on the target font")
_css = "\n".join(re.findall(r"<style>(.*?)</style>", PAGE, re.S))
check(".gcode" in _css and "gcodePulse" in _css, "clicking one pulses in the accent colour")
_cc = JS[JS.index("function copyCode"):JS.index("function copyCode") + 600]
check("gcopy" in _cc, "the icon does not travel to the clipboard with the text")
check(":not(.gcode)" in _css,
      "the old outline flash does not fire on top of the pulse - one effect, not two")

# the audio.cpp folder gets what the llama.cpp folder has
_fe = JS[JS.index("function ttsFieldExtra"):JS.index("async function recheckAcpp")]
check("acppchk" in _fe, "a warning when no server is found under the folder")
check("audio.cpp/releases" in _fe, "the releases address, copyable")
check("acppCheck" in _fe, "and an update check beside it")
# "function renderTts" also matches renderTtsGuide - be exact
_rt = JS.index("function renderTts()")
check("recheckAcpp" in JS[_rt:_rt + 1600],
      "the folder is re-checked whenever the pane is drawn")

# the terminal should say what it is doing, as the reference wrapper did
check("Loading %s..." in py and "Using device: cuda" in py,
      "starting the server announces itself in the terminal")
check("ready for voice synthesis" in py, "and says when it is actually ready")
check("Stopping the TTS server" in py and "TTS server stopped" in py,
      "stopping says so too - the reference wrapper never did")
check("said_ready" in py, "ready is announced once per start, not once per poll")
_el = py[py.index("def tts_engine_label"):py.index("def tts_gpu_label")]
check("ttsAcppModel" in _el, "the banner names the model actually loaded")

# the saved line repeats a folder the user chose; the filename is the new information
# built once now and called from both arms, so one occurrence is correct
check(py.count("os.path.basename(kept or out)") == 1,
      "both engines log the filename, not the whole path")

# Higgs reads inline tags out of the line and acts on them
_tg = py[py.index("def tts_apply_tags"):py.index("def tts_normalize")]
for _fam in ("emotion", "style", "prosody", "sfx"):
    check('"%s"' % _fam in py[py.index("TTS_TAGS = {"):py.index("TTS_TAG_ANY_RX")],
          "the %s tag family is known" % _fam)
check("TTS_TAG_ANY_RX" in _tg,
      "an unrecognised tag is removed, not forwarded - the model would read it aloud")
# SkyrimNet strips < | > from every line, so the native shape never arrives. Watching
# for it alone would have passed through nothing, forever, while looking correct.
check("TTS_CAPS_RX" in py,
      "the [FAMILY-VALUE] form is translated - that is what actually survives SkyrimNet")
# a bare sfx token is inert; the model card's onomatopoeia has to abut it
check("TTS_ONOMATOPOEIA" in py and '"sigh": "Ahh"' in py,
      "sound effects get the onomatopoeia the model was trained on")
check(len(TTS_SFX := re.findall(r'"sfx": \(([^)]*)\)', py)) == 1
      and len(re.findall(r'"[a-z_]+"', TTS_SFX[0])) == 9,
      "all nine sound effects are known, and only those nine")
# a long_pause on a line edge runs the decoder to its cap and returns nothing
check("_tts_drop_edge_pauses" in py,
      "a pause with no speech beside it is dropped - it can hang the engine")
check("TTS_SENT_RX" in py and "_tts_render(tags) + body" in py,
      "sentence-level tags are moved to the front of their sentence")
check("kept.setdefault" in py, "competing tags are deduped rather than stacked")
check("TTS_ORDER" in py, "and emitted in the model card's stacking order")

# SkyrimNet's own vocabularies, so its stock prompt works without being edited
check("TTS_ALIAS" in py and '"angry": ("emotion", "anger")' in py,
      "SkyrimNet's own [angry] / [sigh] tags map onto Higgs where they can")
check("TTS_ALIAS_DROP" in py,
      "and the ones with no counterpart are named rather than guessed at")
_al = py[py.index("    def alias(m):"):py.index("    text = TTS_PAUSE_ANY_RX.sub(pause, text)")]
check("return m.group(0)" in _al,
      "unrecognised brackets are left alone - dialogue may contain [something]")
check("if hit or word in TTS_ALIAS_DROP" in _al,
      "a recognised tag is removed even when tags are off, never read aloud")
check(py.index("text = TTS_ALIAS_RX.sub(alias, text)")
      < py.index("text = TTS_PAUSE_ANY_RX.sub(pause, text)"),
      "the alias pass runs first, or the MOSS matcher swallows a bare [pause]")
check("spoken = TTS_TAG_ANY_RX.sub" in py,
      "the spoken line still ends in punctuation after tags are rewritten")
_i = py.index("TTS_CAPS_RX = re.compile")
_caps = py[_i:_i + 400]                    # the file is CRLF; do not anchor on \n
for _f in ("EMOTION", "PROSODY", "STYLE", "SFX"):
    check(_f in _caps, "the %s family is translated" % _f)
_hgg = JS[JS.index("function renderHiggsGuide"):JS.index("function renderMossGuide")]
check("Chatterbox" in _hgg and "allowed" in _hgg,
      "the guide says tags need Chatterbox and its allowed list, not just the switch")
# a tag must abut the thing it affects - checked as the property, since the
# implementation moved from a regex to building the string that way
check("_tts_render(tags) + body" in py,
      "a sentence-level tag is emitted flush against its sentence")
check('"<|sfx:%s|>%s" % (value, word)' in py,
      "and a sound effect flush against its onomatopoeia")
# this check used to assert MOSS understood no tags. It does: [pause 3.2s]. The engine
# is passed in now so each catalogue is applied to its own engine.
check("tts_engine(cfg))" in py[py.index("processed = tts_apply_tags"):
                               py.index("processed = tts_apply_tags") + 300],
      "the engine decides which catalogue applies, rather than being assumed")
check('"ttsTags": "off"' in py, "and off by default, so nothing changes uninvited")
check('id="tts-ttsTags"' in JS and "body.ttsTags" in JS, "the switch exists and saves")

# MOSS has one marker of its own; the two catalogues must not bleed into each other
check("TTS_PAUSE_RX" in py and "pause" in py[py.index("TTS_PAUSE_RX"):py.index("TTS_PAUSE_RX") + 120],
      "MOSS's [pause Ns] marker is known")
check("TTS_PAUSE_MAX_S" in _tg, "and a runaway pause is clamped rather than obeyed")
check('engine == "audiocpp"' in _tg and "moss = keep and engine" in _tg,
      "each engine keeps only the tags it understands")
# the on-page tag explanation was removed by request; the guide carries it
check("Audio Tags" in JS, "the setting is present without the explanation beside it")

# the update result reads like the llama.cpp one
_ac = JS[JS.index('d.act === "acppCheck"'):JS.index('d.act === "acppCheck"') + 1400]
# one yellow throughout now, by request, rather than the llama.cpp scheme
check("ACPP_MSG" in _ac and "#f2c14e" in _ac,
      "the audio.cpp update result is yellow throughout")

check("#dpane-tts .set > label" in _css, "the TTS settings have room between them")


section("launcher trust surface")
# Defender's ML classifier flagged v3.72 as Wacatac.B!ml. The strongest signal was a
# program that silently relaunched itself elevated and hidden - what droppers do. The
# panel never needed administrator rights; the manifest always said so.
_cpp = rd("launcher-src/launcher.cpp").decode("utf-8", "replace")
check('lpVerb = L"runas"' not in _cpp, "the launcher does not relaunch itself elevated")
# and nothing may still tell the user that not being elevated is a problem
check("NOT elevated" not in PAGE and "not elevated" not in py.split("def main")[0],
      "no leftover warning that the panel should be elevated - it never is now")
check(".banner" not in "\n".join(re.findall(r"<style>(.*?)</style>", PAGE, re.S)),
      "and no orphaned styling for it")
# an unsigned launcher has only its behaviour to argue with. Every API it imports that a
# text editor would not need is a point against it.
check("winsock" not in _cpp.lower() and "WSAStartup" not in _cpp,
      "no networking - it reads the port the panel wrote, rather than probing for one")
check("socket(" not in _cpp, "no sockets at all")
check("pythonw.exe" in _cpp,
      "pythonw is preferred, so no process has to be started hidden")
_code = re.sub(r"//[^\n]*", "", _cpp)          # comments explain the change; check the code
check("CREATE_NO_WINDOW" in _code and "flags = 0" in _code
      and _code.index("flags = 0") < _code.index("CREATE_NO_WINDOW"),
      "CREATE_NO_WINDOW is a fallback for console builds, not the default")
_rc = rd("launcher-src/app.rc").decode("utf-8", "replace")
for _f in ("CompanyName", "FileDescription", "InternalName", "OriginalFilename",
           "LegalCopyright", "ProductName"):
    check(_f in _rc, "the version resource declares %s - sparse metadata is itself a signal" % _f)
check("supportedOS" in rd("launcher-src/app.manifest").decode("utf-8", "replace"),
      "the manifest declares which Windows versions it supports")
check("SEE_MASK_NOASYNC" not in _cpp, "and does not hide a self-launch behind UAC")
check("asInvoker" in rd("launcher-src/app.manifest").decode("utf-8", "replace"),
      "the manifest still asks for no more rights than the user has")
check(os.path.isfile(os.path.join(ROOT, "StartPandorumLLM.bat")),
      "a plain-text launcher exists, so an antivirus block cannot lock anyone out")
_bat = rd("StartPandorumLLM.bat")
check(not _bat.startswith(b"\xef\xbb\xbf"), "the .bat is BOM-less, as cmd requires")
check(b"panel-port.txt" in _bat, "it waits for the port the panel actually chose")
check(b"powershell" not in _bat.lower() and b"Invoke-WebRequest" not in _bat,
      "and does nothing an antivirus would reasonably object to")


section("higgs installer")
# the panel fetching and unpacking executables is the largest thing it does for a
# user, so the constraints are checked rather than trusted
_hi = py[py.index("def higgs_install_worker"):py.index("def api_higgs_install")]
_ha = py[py.index("def api_higgs_install"):py.index("def api_higgs_install") + 900]
check("/api/higgs-install" not in (_ro | _po), "the installer is host-only")
check('body or {}).get("confirm")' in _ha, "and refuses without an explicit confirmation")
check("cancel" in _ha and "HIGGS_INSTALL[\"cancel\"] = True" in _ha, "it can be stopped")
_uz = py[py.index("def _hi_unzip"):py.index("def _hi_free_bytes")]
check("refusing an archive entry outside" in _uz and "os.path.realpath" in _uz,
      "an archive entry that would land outside the folder is refused")
check("refusing an absolute path" in _uz, "and so is an absolute path inside an archive")
check('if p not in ("", ".", "..")' not in _uz,
      "hostile entries are refused, not silently flattened into the folder")
_dl = py[py.index("def _hi_download"):py.index("def _hi_unzip")]
check("Range" in _dl and ".part" in _dl, "a part-finished download resumes rather than restarts")
check("HIGGS_INSTALL[\"cancel\"]" in _dl, "and notices a cancel mid-stream")
check("disk_usage" in py, "free space is checked before 5 GB is fetched")
check("could not be saved" in _hi and "Set these by hand" in _hi,
      "a locked config at the last step does not report the whole install as failed")
# a finished install that looks identical to one that never ran is not feedback
_row = JS[JS.index("function higgsInstallRow"):JS.index("async function higgsInstall")]
check("g.done" in _row, "a finished install says so, rather than falling back to the button")
check("higgsDismiss" in _row and '"dismiss"' in py, "and can be dismissed")
# the skip is now conditional on the marker - see the install section - so retrying is
# still cheap, but only for an engine we put there at this release
check("resuming" in _hi.lower() or "resume" in _hi.lower(),
      "a retry resumes the model rather than starting it over")
_sc = py[py.index("def save_config(cfg):"):py.index("DEFAULT_PROVIDER_SEED")]
check("PermissionError" in _sc and "time.sleep" in _sc,
      "an atomic write retries a transient Windows lock rather than losing the settings")
check("os.remove(tmp)" in _sc, "and never leaves a .tmp file behind when it gives up")
check("api.github.com" in _hi and "huggingface.co" in _hi,
      "both sources are the published ones")
# the profile archives carry a commit hash; the shared runtime does not
_ea = py[py.index("HIGGS_ENGINE_ASSETS = ("):py.index("HIGGS_GGUF_REPO")]
check(".zip" not in _ea and "audiocpp-" not in _ea,
      "engine assets are matched by WORDS, not filenames - names carry a build hash")
check('"win"' in _ea, "win not windows, so a win64 archive still matches")
check("balance" in _ea and "portable" in _ea,
      "the profile is a preference with fallbacks, not a requirement")
check("avoid" in _hi, "the runtime is excluded from the build match, not colliding with it")
check("for w in need)" in _hi, "so a rename or reordering does not break the install")
check("It has:" in _hi,
      "and a mismatch lists what the release actually carries, not just what is missing")
_cf = JS[JS.index("async function higgsInstall"):JS.index("async function higgsCancel")]
for _s in ("github.com", "huggingface.co", "5.1 GB", "Nothing about your setup"):
    check(_s in _cf, "the confirmation states: %s" % _s)


section("tts terminal tags")
check("def tts_tags_display" in py,
      "the terminal shows tags as the model wrote them, not as Higgs takes them")
_pt = JS[JS.index("function paintTail"):JS.index("function stepAt")]
check('which === "tts"' in _pt, "the TTS terminal is painted, not dumped as plain text")
_ps = JS[JS.index("function paintSpoken"):JS.index("function paintTail")]
check("#2ef2ff" in _ps, "and tags are picked out in cyan")
check("#ffffff" in _ps and "#ff5dc8" in _ps and "#f2c14e" in _ps,
      "with white stars, a magenta speaker and the line in gold")
# every tag needs a word, or the terminal shows a raw identifier
_tw = py[py.index("TTS_TAG_WORDS = {"):py.index("def tts_tags_display")]
_names = set(re.findall(r'\("(\w+)", "(\w+)"\)', _tw))
_all = set()
_cat = py[py.index("TTS_TAGS = {"):py.index("# The model card's own spellings")]
for _fam, _vals in re.findall(r'"(\w+)": \(([^)]*)\)', _cat):
    for _v in re.findall(r'"(\w+)"', _vals):
        _all.add((_fam, _v))
check(_all and not (_all - _names),
      "every tag has a word for the terminal", str(sorted(_all - _names))[:120])
# Static analysis cannot tell a correct "\\]" from a broken one here - it flagged a
# valid [^\\]] class. The property is that the terminal paints the right spans, so it
# is tested by painting one (in the jsdom section below), not by reading the source.
check(_pt.count("esc(") >= 6 and "innerHTML" in _pt,
      "every part of a log line is escaped - it carries NPC dialogue")
# the PAGE string swallows an unescaped backslash, and python warns about it
import warnings
with warnings.catch_warnings():
    warnings.simplefilter("error", SyntaxWarning)
    try:
        compile(py, "fleet-panel.py", "exec")
        _clean = True
    except SyntaxWarning:
        _clean = False
    except SyntaxError as _e:
        _clean = "invalid escape" not in str(_e)
check(_clean, "no invalid escape sequences - they warn today and fail tomorrow")


section("local voice clips")
# SkyrimNet resamples every reference to 16 kHz before uploading, including its own
# 44.1 kHz voice-samples. A clip read off disk keeps what Higgs has room for.
_vi = py[py.index("def tts_voice_index"):py.index("def tts_ref_canonical")]
check("st_mtime" in _vi, "the folder is indexed once and rebuilt only when it changes")
check('re.split(r"[\\\\/]"' in _vi,
      "the upload name is split on BOTH separators - os.path.basename ignores backslash off Windows")
check('.endswith(".wav")' in _vi,
      "only .wav is accepted - this panel has no converter and MOSS is handed the bytes")
check("local = tts_local_sample(ref_path, cfg)" in py,
      "a local clip replaces the upload before the reference is used")
check('"  [local clip]"' in py,
      "and the terminal says when one was used - on the Saved line, not the speaker")
check('"ttsVoiceDir"' in JS, "the folder is a setting on the TTS page")


section("child processes and terminal toggles")
# pythonw has NO console, so a console child spawned with no flags gets a NEW visible
# one. python.exe with CREATE_NO_WINDOW had a hidden console children inherited.
check("NOWIN = {" in py and "0x08000000" in py, "a no-window flag set exists for children")
_spawns, _bare = [], []
for _m in re.finditer(r"subprocess\.(run|Popen|check_output)\(", py):
    _seg, _d, _e = py[_m.start():_m.start() + 900], 0, None
    for _i, _ch in enumerate(_seg):
        if _ch == "(":
            _d += 1
        elif _ch == ")":
            _d -= 1
            if _d == 0:
                _e = _i
                break
    _call = _seg[:(_e or 400) + 1]
    _spawns.append(_call)
    if "NOWIN" not in _call and "creationflags" not in _call and "xdg-open" not in _call:
        _bare.append(_call.split("\n")[0][:70])
check(len(_spawns) >= 8, "every spawn is accounted for", "%d found" % len(_spawns))
check(not _bare, "none of them can pop a console window", str(_bare))

check('"termStamps": "on"' in py and '"termInsTts": "on"' in py,
      "the terminal toggles are settings, so they survive a reload")
# count BUTTONS: the sync function selects on the same attribute, so counting every
# mention counts my own querySelectorAll as a sixth terminal
# 5 panes plus one copy in the outer bar for full-window split view
check(PAGE.count(">Timestamps</button>") == 6, "Timestamps is on all five terminals",
      str(PAGE.count(">Timestamps</button>")))
check(PAGE.count(">Insert TTS</button>") == 4,
      "Insert TTS only on the three that show a dialogue completion",
      str(PAGE.count(">Insert TTS</button>")))
check("function onOffLabel" in JS,
      "a toggle reads its own state, the same way Remote Access and Fullscreen do")
_ool = JS[JS.index("function onOffLabel"):JS.index("function syncTermToggleUI")]
check('"blueglow"' in _ool, "with On in blue and Off plain")
_stu = JS[JS.index("function syncTermToggleUI"):JS.index("function syncTermToggleUI") + 700]
check(_stu.count("b.innerHTML = onOffLabel") == 2,
      "both toggles are labelled, not just one", str(_stu.count("b.innerHTML = onOffLabel")))
check('onOffLabel("Timestamps", on)' in _stu and 'b.dataset.kind' in _stu,
      "and Timestamps reads the terminal it belongs to, not a global")
check("syncTermToggleUI" in JS[JS.index("function refreshCurTerm"):
                               JS.index("function refreshCurTerm") + 400],
      "the lit state is applied on every draw, not only after a click")
check("#f2c14e" in JS, "the spoken line is gold, not the theme accent")
check('"launchArc": False' in py, "the launch arc is off by default")
# the engine needs the tag flush against its word; a reader needs a space
_dp = py[py.index("def tts_tags_display"):py.index("def tts_normalize")]
check('"*%s* "' in _dp, "the terminal spaces a tag from the word after it")
_ap = py[py.index("def tts_apply_tags"):py.index("def tts_apply_tags") + 2200]
check('"*%s* "' not in _ap, "but the engine still gets it flush, as Boson require")
_lg = py[py.index("    def log(self, line):"):py.index("    def save_upload")]
check("%H:%M:%S" in _lg,
      "the TTS log is stamped, so a spoken line can be placed beside its completion")
_sp = JS[JS.index("function spliceTts"):JS.index("function spliceTts") + 2200]
check("stampSecs" in _sp, "spoken lines are paired to a completion by time")
check("TTS_BURST_GAP" in JS and "ttsBursts()" in _sp,
      "a streamed reply's chunks are grouped into one burst, not matched line by line")
check("TTS_NEAR_DLG" in _sp,
      "and the burst attaches where it STARTS - TTS fires before the timing line lands")
check("dialogue/i.test" in _sp, "and to a dialogue completion, not any completion")
_at = py[py.index("def api_tail"):py.index("def api_tail") + 1600]
check("PANEL_START" in _at,
      "a fleet log from a previous run of the panel is not shown as if it were this one")
check("waiting for this session" in _at, "and says so plainly instead of looking stale")
check("a.at - b.at" in JS,
      "spoken lines are read in time order rather than reversing")
check("b - a" in _sp, "inserted bottom-up, so earlier positions stay valid")
check("paintSpoken" in JS[JS.index("if (which !== \"dashboard\")"):
                          JS.index("if (which !== \"dashboard\")") + 2000],
      "a spliced line is painted like it is in the TTS terminal, not left plain")
check(JS.count("function paintSpoken") == 1, "one painter, shared by both terminals")


section("spoken line in the proxy log")
_lg2 = py[py.index("def _run"):py.index("def _silence")]
check("(local clip)" not in _lg2,
      "no suffix on the speaker - it broke the name and was not wanted")
check('"  [local clip]"' in py, "the fact is reported on the Saved line instead")
_ps2 = JS[JS.index("function paintSpoken"):JS.index("function paintTail")]
# the mask is gone: the icon varies, so the read is structural - checked in the mood
# section below
check("bare.indexOf" in _ps2, "the speaker is read without depending on which icon leads")
check("sayRx" not in _ps2,
      "not by a regex whose colon class swallowed the timestamp")
check(TTS_LOG_CLEAR := ("TTS_LOG_NAME)" in py and 'with open(_tl, "w"' in py),
      "the TTS log starts empty each session, like the fleet logs do")


section("split panes and insertion marker")
_pt2 = JS[JS.index("function paintTail"):JS.index("function stepAt")]
# the splice places lines BY timestamp, so stripping them first left it nothing to work
# with and the insertions silently vanished
check(_pt2.index("spliceTts(text)") < _pt2.index("stripStamps(text)"),
      "the splice runs before stamps are stripped, or insertions disappear with them")
# the arrow became a channel tree; the marker checks live in the tree section below
check("TREE_MID" in JS, "an inserted line is marked")
_st = JS[JS.index("function stripStamps"):JS.index("function ttsSpokenLines")]
check("TSTAMP_RX" in _st,
      "hiding stamps keeps the marker - the glyph sits after the stamp, so removing "
      "the stamp leaves it alone")
# strip comments: the note explaining "No new RegExp(...)" matched the test itself
check("new RegExp(" not in re.sub(r"//[^\n]*", "", _st),
      "and reuses the working literal rather than rebuilding it")

_sf = JS[JS.index("const SPLIT_FEEDS"):JS.index("async function refreshSplit")]
check('"dashboard", "Proxy"' in _sf and '"tts", "TTS"' in _sf,
      "each split pane can show the proxy, thinking content or TTS")
check("splitins-" in _sf and 'display = (splitFeed(side) === "dashboard")' in _sf,
      "Insert TTS is hidden on a pane not showing the proxy - it was on both before")
check('"splitSrcD": "dashboard"' in py, "the choice is a setting, so it survives a reload")
_chg = JS[JS.index('d.act === "ttsModelSel"') - 400:JS.index('d.act === "ttsModelSel"')]
check("splitFeed" in _chg, "the selector is handled on change, not click")


section("tts tree and existing install")
_sl = JS[JS.index("function spliceTts"):JS.index("function spliceTts") + 2600]
check("TREE_MID" in JS and "TREE_END" in JS,
      "an inserted burst is drawn as a tree, the last chunk closing it")
check("TREE_PAD" in JS, "and sits in from the row it hangs off")
check("LONE_MARK = TREE_PAD" in JS,
      "a line hanging off nothing starts in the SAME column as one that does")
check("width:2ch" in JS, "the marker takes the width of the drawn branch")
check("LONE_MARK" in JS and "anchored" in _sl,
      "a line hanging off nothing - the player speaking - gets a plain arrow, not a branch")
check("last.who === s.who" in JS,
      "a burst requires the same SPEAKER: gap alone merged the player's line with the reply")
# a stretched glyph overlapped the row below and the glow doubled at the join
check("scaleY" not in JS, "the branch is not a stretched glyph")
check(".tbr::before" in _css and "height:100%" in _css,
      "it is DRAWN one row tall, so it meets the next one and no more")
check(_css.count("0 0 20px var(--acc)") >= 2, "with a three-layer glow")
check(".tbrend::before" in _css and "height:50%" in _css,
      "and the last one stops at the elbow")
check("s.stamp" in _sl, "the glyph comes AFTER the timestamp, not before it")
_ps3 = JS[JS.index("function paintSpoken"):JS.index("function paintTail")]
check("var(--acc)" in _ps3 and "text-shadow" in _ps3,
      "the marker glows in the accent colour")

# the binary reports no version of its own, so the tag is recorded when installed
check('"ttsAcppVersion"' in py, "the audio.cpp release tag is a setting")
check('st["ttsAcppVersion"] = tag' in py, "written at install time")
check('out["local"] = acpp_local_version' in py,
      "and reported by the version check, which the binary cannot answer")

# files can be present while the settings are not - a failed config save did exactly that
_hp = py[py.index("def higgs_present"):py.index("def api_higgs_adopt")]
check(".gguf" in _hp and "find_acpp_exe" in _hp,
      "an install already on disk is detected: server plus at least one model")
check('"adoptable": bool(exe and models and not wired)' in _hp,
      "and only offered when the settings are not already pointing somewhere")
check("/api/higgs-adopt" not in (_ro | _po), "adopting is host-only")
check("higgsAdopt" in JS, "the page offers to use it rather than asking for four paths")


section("npc name from the prompt")
# the voice sample is named after the voicetype; the character's name is in the dialogue
# prompt the proxy already forwards
_ns = py[py.index("def note_speaker"):py.index("def speaker_for_voice")]
check("SPEAKER_SCAN" in _ns and "[:SPEAKER_SCAN]" in _ns,
      "only the first few KB of a request is scanned, not 45 KB of prompt")
check("json" not in _ns, "and it is not JSON-parsed on every request")
check("_spk_recent.append((time.time(), name))" in _ns,
      "only the NAME is kept - never the prompt")
_sv = py[py.index("def speaker_for_voice"):py.index("def tts_voice_name")]
check("del _spk_recent[idx]" in _sv,
      "a paired request is CONSUMED, so a second voice cannot inherit the same name")
check("if known:" in _sv and "return known" in _sv,
      "and a learned pairing is never relearned, so one wrong guess cannot spread")
check("note_speaker(body)" in py[py.index("def _mk_handler"):py.index("def _mk_handler") + 4000],
      "read from the request the proxy is already carrying, with no extra model call")
check("def tts_speaker_label" in py and "or tts_voice_name(path)" in py,
      "the terminal shows the character where known and the voicetype otherwise")


section("player vs npc naming")
# the player's line is spoken when THEY speak, before the next dialogue request - so it
# was pairing with the previous turn's character and stealing that name
check("PLAYER_VOICES" in py, "the player's own voice is named apart from the learned ones")
check("Party's" in py,
      "the player is named by the PARTY, which is always theirs")
check('You are speaking to' not in py.split("PLAYER_RX")[1][:200],
      "NOT by 'speaking to', which names the LISTENER - one NPC addressing another put "
      "that NPC's name on the player's own line")
check('or "Player"' in py, "and falls back to Player rather than borrowing a name")
check("PLAYER_SCAN" in py, "the party marker sits far into the body, so it is scanned wider")
check("if not _spk_player[0]:" in py, "but only until it is found once")
_sv2 = py[py.index("def speaker_for_voice"):py.index("def acpp_local_version")]
check("if key in PLAYER_VOICES" in _sv2 and "return _spk_player[0]" in _sv2,
      "so it never enters the learned map and cannot take an NPC's name")

# the binary answers no --version; a hand install has no recorded tag either
_lv = py[py.index("def acpp_local_version"):py.index("def api_acpp_update")]
check("README" in _lv, "a version is read off disk when the panel did not install it")
# the README turned out to carry no version, so try what else might answer
check("/health" in _lv and "/v1/models" in _lv,
      "a running server is asked, since the binary itself answers no --version")
check("TTS_SERVER_LOG_NAME" in _lv,
      "and its own startup output, which the panel already captures")
check("VersionInfo" in _lv, "and the file's own Windows version resource")
check('return ""' in _lv,
      "returning nothing is a valid answer - better than inventing a number")
check("CHANGELOG.md" in _lv, "and a changelog shipped beside it counts too")
check('st.get("ttsAcppVersion")' in _lv, "with a recorded tag preferred over a guess")
check("acpp_local_version(c)" in py, "and recorded when an existing install is adopted")


section("mood icon on a spoken line")
_mi = py[py.index("def tts_mood_icon"):py.index("def tts_tags_display")]
check("for want in (\"emotion\", \"style\", \"sfx\")" in _mi,
      "an emotion colours the sentence, so it outranks a one-moment sound")
_missing = []
_cat = py[py.index("TTS_TAGS = {"):py.index("# The model card's own spellings")]
_mood = py[py.index("TTS_MOOD = {"):py.index("TTS_MOOD_PLAIN")]
for _fam, _vals in re.findall(r'"(\w+)": \(([^)]*)\)', _cat):
    if _fam == "prosody":
        continue
    for _v in re.findall(r'"(\w+)"', _vals):
        if ('("%s", "%s")' % (_fam, _v)) not in _mood:
            _missing.append("%s:%s" % (_fam, _v))
check(not _missing, "every emotion, style and sound has an icon", str(_missing)[:120])
check("TTS_MOOD_PLAIN" in py, "and a plain line has one too")
# the icon varies now, so nothing may key off which one it is
check("MASK" not in JS, "a spoken line is found by the wave markers, not by the icon")
check("const SAID" in JS, "which do not change with the mood")
_ps4 = JS[JS.index("function paintSpoken"):JS.index("function paintTail")]
check("bare.indexOf(\" \")" in _ps4,
      "and the speaker is read structurally: first token is the icon, then the name")


section("launch buttons")
check('arcLabel("Launch LLM")' in JS, "the fleet button says what it launches")
check('id="launchTtsBtn"' in PAGE, "and there is a second one for the TTS server")
check("function launchTts" in JS and "function syncTtsButton" in JS,
      "with its own start and its own state")
_tb = JS[JS.index("function syncTtsButton"):JS.index("async function launchStack")]
for _cls in ("lbload", "lbrun"):
    check(_cls in _tb, "it uses the same %s effect as the fleet button" % _cls)
check("arcFire(tb" in _tb, "and the same arcs")
# every launch rule was keyed on one id, so the TTS button matched none of them
_lone = [" ".join(s.split())[:60] for s, _ in
         re.findall(r"([^{}]*launchBtn[^{}]*)\{([^{}]*)\}", _css)
         if "launchTtsBtn" not in s and "button.go" not in s]
check(not _lone, "every launch style covers both buttons", str(_lone))
# a disabled button emits no pointer events, so it lost its hover crackle when running
check("lb.disabled" not in JS and "tb.disabled" not in JS,
      "neither button is disabled - that killed hover the moment it was running")
check("lbbusy" in JS and "lbbusy" in _css,
      "they are marked busy instead, and the click is refused in the handler")
# the crackle rides on the arc effect, which is off by default - so hover needs its own
check("#launchBtn:hover, #launchTtsBtn:hover" in _css,
      "hover lifts the glow without depending on the arc effect being on")
check("srv.stopping" in JS,
      "Terminate stops the TTS server, and the button says so while it unloads")
check("NO_CFG_LOCK" in py and "/api/launch-stack" in py.split("NO_CFG_LOCK")[1][:200],
      "a launch does not hold the config lock, so one button cannot block the other")
check("class _NullLock" in py, "with a stand-in lock rather than a branch around the body")
check("[Alpha]" not in PAGE, "the TTS tab is no longer labelled Alpha")
_row2 = JS[JS.index("function higgsInstallRow"):JS.index("async function higgsInstall")]
check("1 click install into the PandorumLLM" in _row2, "the install hint says what it is")
check("Prefer to do it yourself" not in JS, "and the page carries less prose")
check("ACPP_MSG" in JS, "the version report is one colour throughout")
check('closest("#launchBtn, #launchTtsBtn")' in JS,
      "the hover arcs cover both, not only the first")
check(JS.count("syncTtsButton()") >= 2,
      "and it is called on a refresh pass, not only defined")
check("Set these on the TTS page first" in JS,
      "pressing it with nothing configured says what is missing rather than failing")
check('<div class="tsect">TTS</div>' in JS and "Higgs Audio v3 (4B) - runs on audio.cpp" in JS,
      "the setting names the TTS; the engine follows from it")
check("ttsEngineSel" in JS,
      "and it is still keyed on the engine value, so no config needs migrating")


section("wrapping and per-terminal stamps")
_ps5 = JS[JS.index("function paintSpoken"):JS.index("function paintTail")]
check("text-indent:-" in _ps5 and "padding-left:" in _ps5,
      "a wrapped spoken line hangs under the dialogue, not back at the tree column")
check("function termCols" in JS,
      "the indent is measured in COLUMNS - an emoji is two cells, so counting characters "
      "would under-measure it")
check("function joinLines" in JS and "display:block" in JS,
      "a block ends its own line, so no newline is added after one")
check("row-gap" in _css and "flex-wrap: wrap" in _css,
      "the terminal bar wraps rather than stacking its buttons on each other")
check(".tbar > button { flex: 0 0 auto; }" in _css, "and no button is squeezed to nothing")
# in full window, split view stacks an outer chrome (Full Window / Normal Size) over one
# chrome per pane (Timestamps / Adjust) - both absolute at top:0, so they overlapped
# in full window the right pane's controls belong in the outer bar, where its Adjust
# already went - pushing the pane bar down left them orphaned a row below their Adjust
check(".tmax #tchrome-splitt .tbar > button { display: none; }" in _css,
      "the right pane's own buttons are hidden in full window")
check(PAGE.count(">Timestamps</button>") == 6,
      "and a copy lives in the outer bar, as its Adjust does",
      str(PAGE.count(">Timestamps</button>")))
check("splitins-t-max" in JS, "including Insert TTS, kept in step with the feed")
check("srv.pid" in JS,
      "the TTS button clears itself when the process is gone - terminating before it "
      "served left it reading Starting TTS for ever")
check('"termStampsOff"' in py, "timestamps are remembered per terminal")
check("function termStampsOn(which)" in JS, "and each terminal is asked about itself")
# in split view the feed shown and the pane showing it are different names; a per-pane
# setting has to follow the PANE or the button toggles something else
check('paintTail(kd, d.text || d.error || "", $("tail-splitd"), "splitd")' in JS,
      "a split pane tells paintTail which pane it is, not only which feed")
check("const who = pane || which;" in JS, "and the timestamps follow the pane")
check(PAGE.count('data-act="termStamps" data-kind=') == 6,
      "every button says which terminal it belongs to",
      str(PAGE.count('data-act="termStamps" data-kind=')))


section("v3.73 sweep")
# NO_CFG_LOCK removed the serialization these two had been relying on
check("_FLEET_LOCK" in py and "_TTSSRV_LOCK" in py,
      "launching and starting TTS each have their own lock, so neither can double-start")
check("acquire(blocking=False)" in py,
      "and a second press is told so rather than queued behind the first")
for _e in ("/api/launch-stack", "/api/tts-server"):
    _seg = py[py.index("NO_CFG_LOCK = frozenset"):py.index("NO_CFG_LOCK = frozenset") + 400]
    check(_e in _seg, "%s runs outside the config lock" % _e)
# one pattern for a rendered control token, not one per caller
check("TTS_TOKEN_RX" in py and py.count('r"<\\|([a-z]+):([a-z_]+)\\|>"') == 1,
      "there is one pattern for a control token, not a copy per caller")
# the spoken line and the saved line were each written once per engine arm
check(py.count("def say_line") == 1 and py.count("self.say_line(") == 2,
      "the spoken line is built in one place and called from both engines")
check(py.count("def saved_line") == 1 and py.count("self.saved_line(") == 2,
      "and so is the saved line")
# the tree must describe what the code does, not what it used to
_pt3 = JS[JS.index("const hostItems"):JS.index("let svg")]
check("fetches audio.cpp and a model from the internet" in _pt3,
      "the tree names the installer, which reaches the internet")
check("asks github.com only when pressed" in _pt3, "and the update check")
check("filenames are stripped" not in _pt3,
      "and no longer claims filenames are stripped - the Saved line is a bare filename now")
check("dialogue, reasoning and character names show" in _pt3,
      "it says plainly that terminal text reaches a remote reader")


section("no third-party page loads")
# the page pulled Plus Jakarta Sans from fonts.googleapis.com on every open, which told
# Google the IP and referer of a panel documented as LAN-only
_ext = re.findall(r'(?:href|src)="(https?://[^"]+)"', PAGE)
check(not _ext, "the page loads nothing from a third party", str(_ext)[:120])
# the comment explaining the removal names the host, so look for an actual element:
# every <link> in the head must point at something the panel serves itself
_links = re.findall(r"<link[^>]*>", PAGE.split("</head>")[0])
check(not [l for l in _links if "http" in l], "no webfont link", str(_links)[:120])
check("Plus Jakarta Sans" in PAGE,
      "the family is still declared, so a local install is still used")
check("Segoe UI" in PAGE, "and the fallback is a font every Windows install has")


section("TTS as its own tab")
check('id="nav-tts"' in PAGE and 'id="tab-tts"' in PAGE, "TTS has a nav entry and a tab")
_nav = re.findall(r'<button id="nav-(\w+)"', PAGE)
check(_nav.index("tts") == _nav.index("servers") + 1, "sitting under Server", str(_nav))
check("dsub-tts" not in PAGE, "and is no longer a sub-tab of Proxy")
check('"tts"' in JS[JS.index('["servers"'):JS.index('["servers"') + 160],
      "showTab knows about it, or the pane would never be shown")
check('showDsub("tts")' not in JS, "nothing still navigates to the old place")
check('data-hostonly' in PAGE[PAGE.index('id="nav-tts"') - 60:PAGE.index('id="nav-tts"') + 60],
      "host-only, as the sub-tab was")
check('"termInsTts": "on"' in py, "spoken lines show in the proxy terminal by default")
check(">Install Higgs v3</button>" in JS, "the install button is not chatty about it")


section("tree wrapping and TTS sections")
# SVG text does not wrap: a long bullet ran straight across into the next column
_liw = JS[JS.index("function li(x, y, mark"):JS.index("const hostItems")]
check("LI_CHARS" in _liw and "rows.push" in _liw, "a long bullet wraps inside its column")
check("h: LI_STEP" in _liw, "and reports its height, so the next one starts below it")
check("__H__" in JS and "Math.max(650" in JS,
      "the box is sized to the wrapped content rather than a fixed height")
# the page reads as groups now
check('["##", "Folders & Model"]' in JS and '["##", "Voice"]' in JS,
      "the TTS fields are grouped under headings")
check('f[0] === "##"' in JS, "and a heading row is rendered as one, not as a field")
check("#dpane-tts .tsect" in _css and "border-top" in _css,
      "with a rule separating it from the section before")
check(JS.count('<div class="tsect">Install</div>') == 5,
      "the install row is headed in every state it can be in",
      str(JS.count('<div class="tsect">Install</div>')))
check(".bigbtn" in _css and "bigbtn" in JS,
      "and the install button is the size of what it does")


section("errors: what counts, and clearing them")
# a clean run should leave no error log at all
check('log_error("panel", "session start' not in py,
      "session start is not an error - it created an error_N.log on every clean run")
check('panel_log("[panel] session start' in py, "it goes in the ordinary log")
# every remaining call must be describing a failure
_bad = []
for _l in py.split("\n"):
    if ('log_error("' in _l or "log_error('" in _l) and not _l.strip().startswith("#"):
        if not re.search(r"fail|error|could not|cannot|refus|reject|unreach|unparse|"
                         r"crash|invalid|denied|timeout|unable|missing|\be\b|\bln\b|"
                         r"\bline\b|traceback", _l, re.I):
            _bad.append(_l.strip()[:70])
check(not _bad, "every log_error call describes something that failed", str(_bad)[:150])

check("def api_errors_clear" in py, "collected issues can be cleared")
_ec = py[py.index("def api_errors_clear"):py.index("def log_error")]
for _n in ("ERR_LOG", "ERR_TOTAL", "ERR_BY_TYPE", "ERR_BY_LEVEL", "ERRTRACK"):
    check(_n in _ec, "clearing resets %s" % _n)
check("ERR_FILE[0]" in _ec, "and empties the log file, not just the list")
check("/api/errors-clear" not in (_ro | _po), "clearing is host-only")
check('data-act="errClear"' in JS and "data-hostonly" in JS, "the button is host-only too")
check("confirm(" in JS[JS.index('d.act === "errClear"'):JS.index('d.act === "errClear"') + 260],
      "and asks first, since it cannot be undone")


section("the GPU row tells the truth")
# it said "every visible card is offered" while the config carries "device": 0 - which
# means the FIRST card and nothing else
# the fleet launchers DO offer every card when unpinned - that wording is correct there.
# Only the TTS row was wrong, so check the TTS row.
_gpurow = JS[JS.index("GPU (pinned by UUID"):JS.index("GPU (pinned by UUID") + 900]
check("every visible card is offered" not in _gpurow,
      "the TTS row makes no claim that an unpinned server uses every card")
check("function gpuAutoLabel" in JS, "the empty choice names what will actually be used")
_gal = JS[JS.index("function gpuAutoLabel"):JS.index("function ttsModelOptions")]
check("your only card" in _gal, "one card: says so, so nobody wonders if they missed a step")
check("the first card" in _gal, "several: says which one it will take")
check("pin the one you want" in JS,
      "and with several cards unpinned, it says why that matters")
# "def tts_engine" also matches def tts_engine_label, which sits EARLIER
_tgl = py[py.index("def tts_gpu_label"):py.index("def tts_engine(cfg")]
check('"default device"' not in _tgl, "the terminal names the card rather than 'default'")
check("(automatic)" in _tgl, "while still saying the choice was not made by hand")


section("install leaves nothing to chance")
_hw = py[py.index("def higgs_install_worker"):py.index("def api_higgs_install")]
# "is there any audiocpp_server.exe here" adopted a CPU build someone unpacked by hand,
# and then installed nothing at all
# nothing already in the folder is trusted, ours or not: a marker still vouched for an
# install antivirus had gutted
check("ALWAYS replace" in _hw, "the engine folder is cleared on every install")
check("have == tag" not in _hw, "no condition keeps what is already there")
check("the engine is always installed fresh" in _hw, "and the log says so plainly")
check("os.path.getsize(gguf) > 4e9" in _hw,
      "the 5 GB model is still kept when whole - that is the expensive one")
check("could not clear" in _hw, "and a folder that will not clear stops the install loudly")
# an install that does not finish the job is worse than one that fails
for _k in ('st["ttsWrapMode"] = "on"', 'st["ttsAcppVersion"] = tag',
           'st["ttsEngine"] = "audiocpp"', 'ttsWrapperPort'):
    check(_k in _hw, "a finished install sets %s" % _k.split("=")[0].strip())
check('HIGGS_INSTALL["warn"]' in _hw,
      "and a settings write that failed is reported, not passed off as success")
check("g.warn" in JS, "shown under the button in amber")
_row3 = JS[JS.index("function higgsInstallRow"):JS.index("async function higgsInstall")]
check("#ff5d5d" in _row3, "with an outright failure in red")

# the only guide step nothing can detect
check('stepAt("yamlsent") && !res[i]' in JS,
      "the step that can never satisfy itself says it is manual")
check(".gmanual" in _css and "gmanualPulse" in _css, "and pulses so it reads as waiting")
check("prefers-reduced-motion" in _css, "unless the system asks for no motion")


section("stale diagnosis, stop, installed")
# the server log spans every run, so a blind tail reported a failure that had been fixed
_td = py[py.index("def tts_diagnose"):py.index("def tts_pick_fields")]
check("since=None" in _td, "the diagnosis can be scoped to one run")
check("min(max(0, since), end)" in _td, "reading only from where that run began")
# it must be the DEATH path that uses it - that is the one people see
_tss = py[py.index("def tts_server_status"):py.index("TTS_PROC = {")]
check('tts_diagnose(cfg, TTS_PROC.get("log_at"))' in _tss,
      "the startup-death hint reads this run, not a blind tail")
check('TTS_PROC.get("log_at")' in py, "and the start position is recorded when it spawns")
check('TTS_PROC["log_at"] = os.path.getsize' in py, "from the log size at that moment")
# stopping is most wanted exactly while it is starting
_stop = JS[JS.index('data-act="ttsStop"'):JS.index('data-act="ttsStop"') + 400]
check('busy === "start"' in _stop, "Stop works during startup, not only once it is up")
check('busy === "stop"' in _stop, "and is only dead while a stop is already running")
# and say plainly when it is already there
check(">Installed</span>" in JS and "f.adoptable" in JS,
      "an install that is present and selected says so")
check('"wired": wired' in py, "which needs the settings state, not just the files")


section("a server that dies while loading")
# it never opens the port, so waiting for the port waits for ever
_ts = py[py.index("def tts_server_status"):py.index("TTS_PROC = {")]
check("proc.poll()" in _ts, "the process is polled, not just the port")
check("tts_diagnose(cfg," in _ts, "and its log is read to say why")
check('TTS_PROC["pid"], TTS_PROC["proc"] = None, None' in _ts,
      "the dead process is reaped, so nothing reads a stale pid")
check('not TTS_PROC.get("stopping")' in _ts, "a deliberate stop is not reported as a death")
check("sv.died" in JS, "the page shows it instead of waiting for it to answer")
check("!srv.died" in JS, "and the button stops saying it is starting")
# the two failures this GGUF actually produced
_hints = py[py.index("TTS_HINTS = ("):py.index("TTS_HINTS = (") + 1400]
check("missing model file 'config'" in _hints,
      "a tensor-only GGUF is named as such, with what it needs beside it")
check("exact tensor shape metadata is invalid" in _hints,
      "and a GGUF from another converter is too")
# an <a href> is a navigation, which armed the leave-page guard
check('class="btnlink" download href="/api/log-download' in JS,
      "downloading a log does not prompt to leave the page")


section("warnings are not errors")
# log_error also raises a UI issue, so an observation logged that way told the user
# something was broken when nothing was
check("def log_warn" in py, "there is a level for something that did not fail")
_lw = py[py.index("def log_warn"):py.index("def log_warn") + 700]
check("_record_issue" not in _lw, "and it raises no UI issue")
check("panel_log(" in _lw, "writing to panel.log rather than the error log")
_slow = [l for l in py.split("\n") if "slow /api/state" in l and "log_" in l]
check(_slow and all("log_warn" in l for l in _slow),
      "a slow state read is a warning", str(_slow)[:100])
_scan = [l for l in py.split("\n") if "model folder scan:" in l and "log_" in l]
check(_scan and all("log_warn" in l for l in _scan), "so is a slow model scan")
# nothing else timing-shaped should still be an error
# match a CALL - log_error with its opening quote - not a mention. Prose ABOUT
# log_error matched the very check meant to police it.
_timing = [l.strip()[:70] for l in py.split("\n")
           if ('log_error("' in l or "log_error('" in l)
           and re.search(r"\bslow\b|\btook\b|elapsed", l, re.I)]
check(not _timing, "no timing observation is logged as an error", str(_timing)[:120])


section("state read probes")
# 700ms of a 750ms state read was two dead ports timing out one after the other, because
# priming and reading disagreed about WHICH ports
_sp = py[py.index("def state_probe_ports"):py.index("def api_state(*a")]
check("parse_ps1_port" in _sp,
      "priming resolves the port the same way the read does - from the launcher script")
check("tts_server_port" in _sp, "and includes the TTS port, which was never primed")
_pr = py[py.index("def prime_slot_status"):py.index("def slot_status")]
check("threading.Thread" in _pr, "probes run together, not one after another")
check("if not todo:" in _pr,
      "and a single uncached port is primed too - the old guard left it serial")
for _c in ("prime_slot_status(state_probe_ports())",):
    check(py.count(_c) == 2, "both the state read and the debug report prime the same way",
          str(py.count(_c)))


section("permission tree claims")
# Section 8: every claim the tree makes is checked against the code enforcing it.
# Without this the tree quietly goes stale - it named three terminals for a build that
# had four, and said nothing about TTS at all.
_tree = JS[JS.index("function permTreeHtml"):JS.index("function permSettingsHtml")]
_TERMNAME = {"proxy": "Proxy", "think": "Thinking", "split": "Split", "tts": "TTS"}
_tsubs = re.findall(r'"(\w+)"', re.search(r'\["proxy","think","split"[^\]]*\]', JS).group(0))
_claim = re.search(r'"View all terminals \(([^)]*)\)"', _tree)
check(bool(_claim), "the tree states which terminals a remote viewer sees")
_named = [s.strip() for s in _claim.group(1).split("/")] if _claim else []
for _t in _tsubs:
    check(_TERMNAME.get(_t, _t) in _named,
          "tree names the '%s' terminal it can actually see" % _t, str(_named))
check(len(_named) == len(_tsubs), "tree names no terminal that does not exist",
      "%d claimed vs %d real" % (len(_named), len(_tsubs)))

# anything the tree says is "not offered" must actually be marked host-only
_off = re.search(r'"([^"]*are not offered)"', _tree)
_PANE = {"Proxy Setup": "dsub-setup", "SkyrimNet YAML": "dsub-yaml",
         "TTS": "nav-tts", "Provider Statistics": "pmsub-stats"}
check(bool(_off), "the tree states which pages are withheld from remote")
# withheld can be enforced two ways: the data-hostonly attribute, or a redirect in
# applyScopeUI / the show* guard. Either satisfies the claim; neither does not.
_scope = JS[JS.index("function applyScopeUI"):JS.index("function applyScopeUI") + 2500]
_dsub = JS[JS.index("function showDsub"):JS.index("function showDsub") + 700]
for _label, _id in _PANE.items():
    if not (_off and _label in _off.group(1)):
        continue
    _tag = re.search(r'<button id="%s"([^>]*)>' % re.escape(_id), PAGE)
    _attr = bool(_tag) and "data-hostonly" in _tag.group(1)
    _key = _id.split("-", 1)[1]
    _redir = ('"%s"' % _key) in _scope or ('"%s"' % _key) in _dsub
    check(_attr or _redir, "'%s' is withheld from remote as the tree claims" % _label,
          "no data-hostonly and no redirect for %s" % _id)

check("TTS" in _tree, "the tree mentions TTS at all")


section("remote boundary")

read_ok = set(re.findall(r'"(/[^"]+)"', re.search(r"REMOTE_READ_OK = \{(.*?)\}", py, re.S).group(1)))
post_ok = set(re.findall(r'"(/[^"]+)"', re.search(r"REMOTE_POST_OK = \{(.*?)\}", py, re.S).group(1)))
MUTATING = ("add", "edit", "remove", "move", "save", "create", "delete", "launch",
            "stop", "restore", "revert", "reset", "settings", "sampler", "launcher")
for ep in sorted(read_ok | post_ok):
    bad = [w for w in MUTATING if w in ep]
    check(not bad, "not remotely reachable: %s" % ep, str(bad))
check("/api/tts-launcher" not in (read_ok | post_ok), "TTS launcher write is host-only")
check('body or {}).get("kind", "")) == "file"' in py.replace("(", "(") or
      'get("kind", "")) == "file"' in py, "kind=file blocked for remote")


# ------------------------------------------------------------ 7. duplication
section("duplication (gotcha 1)")

ids = re.findall(r'id="([A-Za-z0-9_-]+)"', PAGE)
dupe_ids = [i for i, n in collections.Counter(ids).items() if n > 1]
check(not dupe_ids, "no duplicate static element ids", str(dupe_ids[:5]))

fns = re.findall(r"^(?:async )?function ([A-Za-z0-9_]+)", JS, re.M)
dupe_fns = [f for f, n in collections.Counter(fns).items() if n > 1]
check(not dupe_fns, "no duplicate JS functions", str(dupe_fns[:5]))

for name in ("ProxyManager", "api_settings", "_mk_handler", "api_provider_add",
             "load_config", "save_config", "redact_state", "api_tail"):
    n = len(re.findall(r"^(?:class|def) %s\b" % name, py, re.M))
    check(n == 1, "single definition: %s" % name, "found %d" % n)

# every terminal showTsub can open must have a live-refresh branch, or it renders once
# on open and then goes stale until the page is reloaded
_tsubs = re.search(r'\["proxy","think","split"[^\]]*\]', JS)
_names = re.findall(r'"(\w+)"', _tsubs.group(0)) if _tsubs else []
_cur = re.search(r"function refreshCurTerm\(\)\s*\{(.*?)\n\}", JS, re.S)
_body = _cur.group(1) if _cur else ""
check(bool(_cur), "refreshCurTerm exists (single terminal->feed mapping)")
for _t in _names:
    check(('curTsub === "%s"' % _t) in _body, "terminal '%s' has a live-refresh branch" % _t)
# showTsub, liveRefresh, and termToggle after a display switch
check(JS.count('refreshCurTerm();') >= 2,
      "refreshCurTerm called from showTsub and liveRefresh at least",
      "found %d call sites" % JS.count('refreshCurTerm();'))
check(len(re.findall(r'refreshTail\("tts"\)', JS)) == 1,
      "tts feed named in exactly one place")

# tts.log is written by another process, so nothing fires sse_notify for it. Without a
# watcher the terminal renders once and then sits still until an unrelated event.
_wd = tempfile.mkdtemp()
_ol = fp.log_dir
fp.log_dir = lambda c=None: _wd
_s0 = fp.tail_watch_sig()
_p = os.path.join(_wd, "tts.log")
open(_p, "w").write("one\n")
_s1 = fp.tail_watch_sig()
open(_p, "a").write("two\n")
_s2 = fp.tail_watch_sig()
_s3 = fp.tail_watch_sig()
os.remove(_p)
_s4 = fp.tail_watch_sig()
fp.log_dir = _ol
check(_s0 is None, "watcher: no signature when the log is absent")
check(_s1 is not None and _s1 != _s0, "watcher: sees the log appear")
check(_s2 != _s1, "watcher: sees an append (mtime+size, not mtime alone)")
check(_s3 == _s2, "watcher: stable when nothing changed (no notify storm)")
check(_s4 is None, "watcher: sees the log deleted")
check("sse_notify(\"tail\")" in py.split("def status_watch_loop")[1].split("def ")[0],
      "watcher notifies through the existing SSE tail path")

acts = set(re.findall(r'data-act="([A-Za-z0-9_]+)"', PAGE))
handled = set(re.findall(r'd\.act === "([A-Za-z0-9_]+)"', JS))
orphans = sorted(a for a in acts - handled
                 if a not in {"bgPick", "bgToggle", "gpuToggle", "navBack", "navFwd",
                              "profToggle", "refToggle", "stackToggle"})
check(not orphans, "every new data-act has a handler", str(orphans))


# ------------------------------------------------------ 8. visual invariants
section("visual invariants (gotchas 5 and 6)")

css = "\n".join(re.findall(r"<style>(.*?)</style>", PAGE, re.S)) or PAGE
check(css.count("{") == css.count("}"), "CSS braces balance",
      "%d vs %d" % (css.count("{"), css.count("}")))

rules = re.findall(r"([^{}]+)\{([^{}]*)\}", css)
rest_rings = []
for sel, body in rules:
    s = sel.strip()
    if any(k in s for k in (":hover", ":focus", ":active", "[open]", ".on", ".open",
                            ".over", ".dragging", ".sel", ".active", "@keyframes",
                            # guide steps use a coloured ring AS the state indicator,
                            # not as a border imitation - deliberate, confirm before removing
                            ".gstep", ".gbranch")):
        continue
    if re.match(r"^[\d.%,\s]+$", s) or re.match(r"^(from|to)[\s,]*$", s):
        continue                      # keyframe stop ("0%", "0%,100%"), not a rule
    for decl in re.findall(r"box-shadow\s*:([^;]+)", body):
        if re.search(r"(^|\s)0(px)?\s+0(px)?\s+0(px)?\s+\d", decl):
            rest_rings.append(s[:60])
check(not rest_rings, "nothing at rest draws a zero-blur ring", str(rest_rings[:3]))

# an !important declaration overrides an animation, so any highlight aimed at a button
# must not animate a property that a button rule kills with !important
_dead = set()
def _selclean(s):
    # the capture carries any comment that preceded the rule; the selector is what
    # follows the last one
    s = re.sub(r"/\*.*?\*/", " ", s, flags=re.S)
    return " ".join(s.split())
for _sel, _body in rules:
    _s = _selclean(_sel)
    if re.match(r"^(button|a\.btnlink)\s*(,|$)", _s):
        for _d in re.findall(r"([a-z-]+)\s*:[^;]*!important", _body):
            _dead.add(_d)
check(bool(_dead), "found the !important properties a button rule suppresses", str(sorted(_dead)))
_btnhl = [b for s, b in rules if "guidehl" in s and ("button" in s or "btnlink" in s)]
check(bool(_btnhl), "buttons have their own guide-highlight variant")
_anim = re.search(r"animation:\s*(\w+)", _btnhl[0]) if _btnhl else None
_kf = re.search(r"@keyframes %s\b(.*?)\n\s*\}" % _anim.group(1), css, re.S) if _anim else None
_props = set(re.findall(r"([a-z-]+)\s*:", _kf.group(1))) if _kf else set()
check(bool(_kf), "and it names a real keyframe", _anim.group(1) if _anim else "none")
check(not (_props & _dead),
      "the button highlight animates nothing an !important button rule suppresses",
      "clash: %s" % sorted(_props & _dead))


# ------------------------------------------------------- 9. emoji spacing
section("emoji spacing (gotcha 4)")

import unicodedata
bad = []
for i, ch in enumerate(PAGE):
    if ord(ch) > 0x2100 and not unicodedata.category(ch).startswith("L"):
        for nb in (PAGE[i - 1:i], PAGE[i + 1:i + 2]):
            if nb and nb.isalnum():
                bad.append(PAGE[max(0, i - 20):i + 20].replace("\n", " "))
check(not bad, "no icon sits against an alphanumeric", str(bad[:2]))


# --------------------------------------------------- 10. generated TTS launcher
section("generated TTS launcher (.bat rules)")

cfg = {"gpus": [{"id": "g1", "uuid": "GPU-00000000-0000", "name": "Test Card"}],
       "settings": {"ttsServerExe": "s.exe", "ttsModel": "m.gguf", "ttsWrapper": "w.py",
                    "ttsPython": "p.exe", "ttsServerPort": "1245",
                    "ttsWrapperPort": "7861", "ttsGpuId": "g1"}}
fp.log_dir = lambda c=None: r"C:\PandorumLLM\logs"
bat = fp.tts_launcher_text(cfg)
lines = bat.split("\r\n")


def caret_in_quotes(line):
    inq = False
    for chx in line:
        if chx == '"':
            inq = not inq
        elif chx == "^" and inq:
            return True
    return False


check(bat.count("\n") == bat.count("\r\n"), "CRLF only")
check(not bat.startswith("\ufeff"), "no BOM")
check(not any(caret_in_quotes(l) for l in lines), "no caret inside a quoted span")
check(not any(l.count('"') % 2 for l in lines), "quotes balance on every line")
check("--main-gpu 0" in bat, "--main-gpu 0 after masking")
check("set CUDA_VISIBLE_DEVICES=GPU-00000000-0000" in bat, "GPU pinned by UUID")
check("-X utf8 -u" in bat, "python forced to UTF-8 and unbuffered")
check("set MOSS_TTS_URL=http://127.0.0.1:%PORT%/tts" in bat,
      "wrapper pointed at the configured server port")
check(r"set LOG=%LOGDIR%\tts.log" in bat, "log written into the panel log folder")
check("CUDA_VISIBLE_DEVICES" not in fp.tts_launcher_text(
      {"gpus": [], "settings": dict(cfg["settings"], ttsGpuId="")}),
      "no GPU pinned -> no mask line")

# when the panel is the wrapper it already holds the wrapper port; a launcher that
# started one too would collide on every run
_srv_only = fp.tts_launcher_text({"gpus": cfg["gpus"],
                                  "settings": dict(cfg["settings"], ttsWrapMode="on")})
_both = fp.tts_launcher_text({"gpus": cfg["gpus"],
                              "settings": dict(cfg["settings"], ttsWrapMode="off")})
check("TTS Wrapper" in _both, "wrapper mode off -> launcher starts the wrapper")
check("TTS Wrapper" not in _srv_only, "panel wraps -> launcher does NOT start a wrapper")
check("%PYTHON%" not in _srv_only, "panel wraps -> no dangling python reference")
check("TTS Server" in _srv_only, "panel wraps -> launcher still starts the server")
check("--main-gpu 0" in _srv_only, "panel wraps -> GPU pinning still applied")
_sl = _srv_only.split("\r\n")
check(not any(caret_in_quotes(l) for l in _sl), "server-only launcher: no caret in quotes")
check(not any(l.count(chr(34)) % 2 for l in _sl), "server-only launcher: quotes balance")
check(_srv_only.count("\n") == _srv_only.count("\r\n"), "server-only launcher: CRLF only")


# ------------------------------------------------- 10b. path picking and import
section("path picking / launcher import")

_d = tempfile.mkdtemp()
for _n in ("a.gguf", "b.gguf", "notes.txt"):
    open(os.path.join(_d, _n), "w").write("x")
os.makedirs(os.path.join(_d, "sub"), exist_ok=True)
_plain = fp.api_browse_dirs({"path": _d})
_filt = fp.api_browse_dirs({"path": _d, "exts": [".gguf"]})
check(not _plain.get("files"), "no exts -> still directories-only (unchanged default)")
check(sorted(f["name"] for f in _filt["files"]) == ["a.gguf", "b.gguf"],
      "exts filter lists matching files only")
check(_filt["dirs"] == ["sub"], "folders still listed in file mode")

# Windows paths must classify correctly wherever the gate runs: os.path.basename does
# not split on a backslash off Windows, which silently mis-filed every path.
_bat = os.path.join(_d, "ref.bat")
open(_bat, "w").write(
    "@echo off\r\n"
    "set SERVER=Z:\\fixture\\tts\\server.exe\r\n"
    "set MODEL=Z:\\fixture\\tts\\model.gguf\r\n"
    "set WRAPPER=Z:\\fixture\\tts\\wrapper.py\r\n"
    "set PYTHON=Z:\\fixture\\tts\\python.exe\r\n"
    "set PORT=1240\r\n"
    "echo Wrapper: http://localhost:7860\r\n")
_saved = {}
_real_load, _real_save = fp.load_config, fp.save_config
fp.load_config = lambda: {"settings": _saved}
fp.save_config = lambda c: _saved.update(c.get("settings", {}))
_imp = fp.api_tts_import({"path": _bat})
fp.load_config, fp.save_config = _real_load, _real_save
_found = _imp.get("found", {})
for _k, _want in [("ttsServerExe", ".exe"), ("ttsModel", ".gguf"),
                  ("ttsWrapper", ".py"), ("ttsPython", "python.exe")]:
    check(_found.get(_k, "").lower().endswith(_want), "import classified %s" % _k,
          _found.get(_k, "(missing)"))
check(_found.get("ttsServerPort") == "1240", "import read the server port")
check(_found.get("ttsWrapperPort") == "7860", "import read the wrapper port from a URL")
check(len(_found) == 6, "import filled all six fields", "got %d" % len(_found))
check("found" not in fp.api_tts_import({"path": os.path.join(_d, "notes.txt")}),
      "import refuses a non-launcher")

# the panel must be able to display every file type it writes
_ld = tempfile.mkdtemp()
open(os.path.join(_ld, "start-tts.bat"), "w").write("x")
open(os.path.join(_ld, "a.ps1"), "w").write("x")
_rl, _rs = fp.load_config, fp.save_config
fp.load_config = lambda: {"settings": {"launcherDir": _ld, "outputDir": _ld}, "launcherDirs": [_ld]}
_seen = sorted(f["name"] for f in fp.api_folder_view({"which": "launcher"}).get("files", []))
fp.load_config, fp.save_config = _rl, _rs
check("start-tts.bat" in _seen, "launcher folder viewer lists the .bat the panel writes", str(_seen))
check("a.ps1" in _seen, "launcher folder viewer still lists .ps1", str(_seen))

# the launcher must land in the folder Folder Settings shows. outputDir is seeded with a
# default and only mirrors launcherDir on save, so the two can disagree - and preferring
# the wrong one writes the file somewhere the user was never shown.
_A, _B = tempfile.mkdtemp(), tempfile.mkdtemp()
_tts = {"ttsServerExe": "s.exe", "ttsModel": "m.gguf", "ttsWrapper": "w.py", "ttsPython": "p.exe"}
_ol, _os_, _olog, _oplog = fp.load_config, fp.save_config, fp.log_dir, fp.panel_log
fp.log_dir = lambda c=None: _A
fp.panel_log = lambda *a, **k: None
fp.load_config = lambda: {"gpus": [], "settings": dict(_tts, launcherDir=_A, outputDir=_B)}
_where = os.path.dirname(fp.api_tts_launcher({"save": True}).get("path", ""))
fp.load_config, fp.save_config, fp.log_dir, fp.panel_log = _ol, _os_, _olog, _oplog
check(_where == _A, "launcher written to launcherDir when it differs from outputDir",
      "went to outputDir" if _where == _B else _where)


# --------------------------------------------- 10c. embedded TTS wrapper (translation)
section("embedded TTS wrapper")

# the trailing full stop is why SkyrimNet's "ping" arrives as "ping." - a ping check
# comparing against the literal never fires
check(fp.tts_normalize("ping") == "ping.", "normalize appends the full stop")
check(fp.tts_normalize("already.") == "already.", "normalize leaves existing punctuation")
check(fp.tts_normalize("  a   b  ") == "a b.", "normalize collapses whitespace")

_long = ("One sentence here. " * 30).strip()
_ch = fp.tts_chunks(fp.tts_normalize(_long))
check(len(_ch) > 1, "long text splits into chunks", "got %d" % len(_ch))
check(all(len(c) <= fp.TTS_CHUNK_CHARS for c in _ch), "no chunk exceeds the cap",
      str(max(len(c) for c in _ch)))
check(fp.tts_chunks("short.") == ["short."], "short text stays one chunk")

def _mkwav(ms, rate=24000):
    _b = io.BytesIO()
    import wave as _w
    with _w.open(_b, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes(b"\x01\x00" * int(rate * ms / 1000))
    return _b.getvalue()

_body, _rate, _n = fp.tts_wav_join([_mkwav(300), _mkwav(300)], gap_ms=100)
check(_body is not None and abs(_n / _rate - 0.70) < 0.02,
      "wav join = parts + gaps", "%.3fs" % (_n / _rate if _rate else 0))
_b1, _r1, _n1 = fp.tts_wav_join([_mkwav(300)], gap_ms=100)
check(abs(_n1 / _r1 - 0.30) < 0.02, "single chunk gets no gap")
check(fp.tts_wav_join([])[0] is None, "empty input returns nothing rather than a bad wav")
_mixed = fp.tts_wav_join([_mkwav(300), _mkwav(300, rate=16000)], gap_ms=0)
check(abs(_mixed[2] / _mixed[1] - 0.30) < 0.02, "a mismatched part is skipped, not garbled")

# the request body is never logged, so the speaker_audio shape is unconfirmed: all
# three plausible forms must resolve
check(fp.tts_speaker_path("C:/x/a.wav") == "C:/x/a.wav", "speaker_audio as a bare string")
check(fp.tts_speaker_path({"path": "C:/x/a.wav"}) == "C:/x/a.wav", "speaker_audio as FileData")
check(fp.tts_speaker_path({"name": "C:/x/a.wav"}) == "C:/x/a.wav", "speaker_audio as a name key")
check(fp.tts_speaker_path(None) is None, "speaker_audio absent")

_mp = (b'--B\r\nContent-Disposition: form-data; name="f"; filename="v.wav"\r\n\r\n'
       b'RIFFDATA\r\n--B--\r\n')
_parts = fp.tts_parse_multipart(_mp, "multipart/form-data; boundary=B")
check(_parts and _parts[0][0] == "v.wav" and _parts[0][1] == b"RIFFDATA",
      "multipart parsed without cgi (removed in 3.13)", str(_parts)[:60])
check(fp.tts_parse_multipart(b"x", "text/plain") == [], "non-multipart yields nothing")

# the listener binds 0.0.0.0 and /gradio_api/file= takes a caller-supplied absolute
# path, so anything outside its own folder must be refused
_own = fp.TTSW.dir()
check(fp.TTSW.owns(os.path.join(_own, "a.wav")), "serves a file it owns")
check(not fp.TTSW.owns("/etc/passwd"), "refuses an absolute path outside its folder")
check(not fp.TTSW.owns(os.path.join(_own, "..", "..", "etc", "passwd")),
      "refuses traversal out of its folder")
_saved = fp.TTSW.save_upload("../../evil.wav", b"x")
check(fp.TTSW.owns(_saved), "an upload with a traversal name still lands inside the folder", _saved)

check(str(DEF := re.search(r'"ttsWrapMode":\s*"(\w+)"', py).group(1)) == "off",
      "embedded wrapper ships OFF by default", DEF)

# both listeners bind 0.0.0.0 for 2-PC mode, so the TTS one must filter clients exactly
# as the proxy does - otherwise the panel refuses a stranger on one port and serves them
# on the next
_th = py[py.index("def _mk_tts_handler"):py.index("TTSW = TtsWrapper()")]
check("PROXY" in _th and "allow" in _th and "client_address" in _th,
      "TTS listener applies the proxy's client-IP allowlist")
check("403" in _th, "TTS listener refuses a client outside the allowlist")
check("MAX_BODY" in _th and "413" in _th,
      "TTS listener caps the request body rather than allocating what is claimed")
check("_allowed()" in _th and _th.count("if not self._allowed(): return") >= 3,
      "every TTS verb is gated, not just POST",
      "%d gated" % _th.count("if not self._allowed(): return"))

_tw = py[py.index("class TtsWrapper"):py.index("def tts_voice_name")]
check("def prune" in _tw and "os.remove" in _tw,
      "generated audio is pruned rather than accumulating forever")
check("rmtree" in _tw, "uploaded reference voices are pruned too")

# SkyrimNet's references come from FFmpeg with extra RIFF chunks. moss-tts-server
# answered those with 400 and audio.cpp with "failed to read WAV data chunk" - the same
# fault through two parsers, so it is normalised once at the upload, not per engine.
_su = _tw[_tw.index("def save_upload"):_tw.index("def submit")]
check("tts_wav_normalize" in _su,
      "an uploaded reference is normalised on the way in, for every engine")
check('b"RIFF"' in _su, "and only when it is actually a WAV")
_acpp = py[py.index('== "audiocpp"'):py.index("ref_b64, cached")]
# normalising on the way in is not enough: SkyrimNet HEADs the path first and skips the
# upload on a 200, so a file cached by an older build is never re-sent
_rc = py[py.index("def tts_ref_canonical"):py.index("def tts_engine")]
check('b"data"' in _rc and "36:40" in _rc,
      "a cached reference is checked cheaply before being trusted")
check("f.write(clean)" in _rc, "and repaired in place, so it is fixed once and stays fixed")
check("tts_ref_canonical(ref_path)" in _acpp,
      "the audio.cpp arm repairs a stale reference rather than failing on it")

# a crashed server closes the socket and says nothing; its own log says why one line up
_dg = py[py.index("def tts_diagnose"):py.index("def tts_pick_fields")]
check("no kernel image" in py and "TTS_HINTS" in py,
      "a crash is translated into something a person can act on")
check("f.seek(0, 2)" in _dg, "only the tail of the server log is read, not all of it")
check("tts_diagnose(" in py[py.index("def _run"):py.index("def _silence")],
      "and the hint is attached to the failure the user sees")

# Zonos and Chatterbox both speak Gradio but send different argument lists
_pf = py[py.index("def tts_pick_fields"):py.index("def tts_ref_canonical")]
check("fields[3]" in _pf and "isinstance" in _pf,
      "the proven Zonos positions are kept when they hold")
check('f.get("path")' in _pf,
      "and the reference is found by shape when they do not - any Gradio engine works")
check("_TTS_LANG_RX" in _pf, "a language tag is never mistaken for the line to speak")
check("fields[1] if len(fields)" not in py[py.index("def submit"):py.index("def result")],
      "submit no longer indexes the array blind")
check("PROXY_MAX_BODY" in py, "the proxy caps its request body as the TTS listener does")
_ph = py[py.index("def _mk_handler"):py.index("def _mk_handler") + 4000]
check("PROXY_MAX_BODY" in _ph and "413" in _ph,
      "and refuses an oversized claim rather than allocating it")
_sv = py[py.index("def api_tts_server"):py.index("def api_launcher_content")]
check(_sv.count("logf.close()") >= 2,
      "the child's log handle is closed in the parent on both paths",
      "%d close sites" % _sv.count("logf.close()"))

# the reference wrapper round-trips the voice through soundfile before base64, which
# strips stray RIFF chunks. Passing the original bytes through is what drew a 400.
import struct as _struct
def _mkwav(ms, ch=1, rate=22050, extra=False):
    _b = io.BytesIO()
    import wave as _w
    with _w.open(_b, "wb") as w:
        w.setnchannels(ch); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes(b"\x01\x00" * int(rate * ms / 1000) * ch)
    raw = _b.getvalue()
    if extra:
        raw = raw + b"LIST" + _struct.pack("<I", 10) + b"INFOIART\x00\x00"
        raw = raw[:4] + _struct.pack("<I", len(raw) - 8) + raw[8:]
    return raw

_norm = fp.tts_wav_normalize(_mkwav(200, extra=True))
check(b"LIST" not in _norm, "reference re-encode strips stray RIFF chunks")
import wave as _w2
with _w2.open(io.BytesIO(fp.tts_wav_normalize(_mkwav(200, ch=2))), "rb") as _w3:
    check(_w3.getnchannels() == 1, "reference re-encode downmixes to mono (no audioop)")
check(fp.tts_wav_normalize(b"not a wav") == b"not a wav",
      "unreadable reference passes through rather than being destroyed")

# "HTTP Error 400: Bad Request" says nothing; the server's body says what it objected to
_src = py.split("def _post_chunk")[1].split("def ")[0]
check("HTTPError" in _src and "e.read()" in _src,
      "upstream failures surface the server's own response body")


# --------------------------------------------------- 10d. TTS server start / stop
section("TTS server control")

_sd = tempfile.mkdtemp()
_model = os.path.join(_sd, "m.gguf")
open(_model, "wb").write(b"x")
_exe = os.path.join(_sd, "moss-tts-server.exe")
open(_exe, "wb").write(b"x")
_ol2, _olog2, _oplog2 = fp.load_config, fp.log_dir, fp.panel_log
fp.log_dir = lambda c=None: _sd
fp.panel_log = lambda *a, **k: None

def _cfg(**over):
    s = {"ttsServerExe": _exe, "ttsModel": _model, "ttsServerPort": "59999",
         "ttsGpuId": "", "ttsWrapMode": "on"}
    s.update(over)
    return {"gpus": [{"id": "g1", "uuid": "GPU-00000000-0000", "name": "Card"}], "settings": s}

for _label, _over, _want in [("binary missing", {"ttsServerExe": "/nope.exe"}, "binary not found"),
                             ("binary unset", {"ttsServerExe": ""}, "binary not found"),
                             ("model missing", {"ttsModel": "/nope.gguf"}, "model not found"),
                             ("model unset", {"ttsModel": ""}, "model not found")]:
    fp.load_config = lambda o=_over: _cfg(**o)
    _e = fp.api_tts_server({"action": "start"}).get("error", "")
    check(_want in _e, "start refuses when the %s" % _label, _e or "(no error)")

fp.load_config = lambda: _cfg()
check("unknown action" in fp.api_tts_server({"action": "wibble"}).get("error", ""),
      "unknown action refused")

# arg assembly, without spawning anything
_seen = {}
class _FakeProc:
    pid = 4242
    returncode = None
    def poll(self):
        return None          # a real Popen always has this; alive means None
def _fake_popen(args, **kw):
    _seen["args"] = list(args); _seen["kw"] = kw
    return _FakeProc()
_realpopen = fp.subprocess.Popen
fp.subprocess.Popen = _fake_popen
try:
    fp.load_config = lambda: _cfg(ttsGpuId="g1")
    fp.api_tts_server({"action": "start"})
    _a, _kw = _seen.get("args", []), _seen.get("kw", {})
    check(_a and _a[0] == _exe, "server started from the configured binary")
    check("--main-gpu" in _a and _a[_a.index("--main-gpu") + 1] == "0",
          "--main-gpu 0 after masking (not the physical index)")
    check("--no-webui" in _a, "--no-webui passed")
    check("--port" in _a and _a[_a.index("--port") + 1] == "59999", "configured port passed")
    check(_kw.get("env", {}).get("CUDA_VISIBLE_DEVICES") == "GPU-00000000-0000",
          "GPU pinned by UUID in the child environment")
    check(not _kw.get("shell"), "no shell=True (section 10)")
    check(isinstance(_a, list), "argument list, never a command string")
    _seen.clear()
    fp.load_config = lambda: _cfg(ttsGpuId="")
    fp.api_tts_server({"action": "start"})
    check("CUDA_VISIBLE_DEVICES" not in (_seen.get("kw", {}).get("env") or {})
          or os.environ.get("CUDA_VISIBLE_DEVICES") is not None,
          "no GPU pinned -> the variable is not forced")
finally:
    fp.subprocess.Popen = _realpopen
    fp.load_config, fp.log_dir, fp.panel_log = _ol2, _olog2, _oplog2

check("/api/tts-server" not in (read_ok | post_ok), "server control is host-only")

# closing the last browser tab runs full_exit, which stops the fleet. A TTS server the
# panel started must go with it or it holds the model in VRAM with nothing able to reach it
_fe = py[py.index("def full_exit"):py.index("def watchdog_loop")]
check("stop_tts_server" in _fe, "exit stops a panel-started TTS server")
check("TTSW" in _fe and "shutdown" in _fe, "exit shuts the TTS listener down with the proxy's")
check("stop_tts_server" in py[py.index("def api_terminate"):py.index("def api_exit")],
      "Terminate stops the TTS server too")
_ss = py[py.index("def stop_tts_server"):py.index("def api_tts_server")]
check("TTS_PROC" in _ss and "_kill_port_owner" not in _ss,
      "exit stops only what the panel started, never whatever holds the port")
check(len(re.findall(r"def stop_tts_server", py)) == 1,
      "one stop implementation shared by exit, terminate and the button")

# a page that never redraws shows yesterday's state. The TTS pane was only redrawn by
# the Start button's own poll, so anything that changed the server from elsewhere -
# Terminate, exit, a crash - left it claiming the server was still up.
_rc = JS[JS.index("function renderCurrent"):JS.index("function renderRouting")]
check("renderTts" in _rc,
      "the TTS pane redraws from renderCurrent, which runs AFTER state is fetched")
check("dpane-tts" in _rc, "TTS redraw stands aside for a focused field")
_lr = JS[JS.index("function liveRefresh"):JS.index("function connectES")]
check("renderTts" not in _lr,
      "not redrawn from liveRefresh, which runs BEFORE the state fetch and would use stale data")
check("stop_tts_server" in py and 'sse_notify("state")' in _ss,
      "stopping the server announces the change rather than waiting to be noticed")
check("_ST_CACHE.pop" in _ss, "stopping drops the cached status so it cannot read stale")
_sw = py[py.index("def status_watch_loop"):py.index("def sweep_launcher_shells")]
check('"_tts"' in _sw, "the status watcher tracks the TTS port, not just fleet slots")
check("ttsServerExe" in _sw, "and only probes it when TTS is actually configured")


section("TTS guide page")
_ug = re.search(r'function showUgSub\(s\)\s*\{(.*?)\n\}', JS, re.S)
_names = re.findall(r'"(\w+)"', re.search(r'\["main",\s*"params"[^\]]*\]', JS).group(0))
check("tts" in _names, "TTS guide is in the sub-tab list", str(_names))
for _n in _names:
    check(('id="ugsub-%s"' % _n) in PAGE, "guide button exists: %s" % _n)
    check(('id="ugpane-%s"' % _n) in PAGE, "guide pane exists: %s" % _n)
check("renderTtsGuide" in (_ug.group(1) if _ug else ""), "showUgSub routes to the TTS guide")
check(len(re.findall(r"function renderTtsGuide", JS)) == 1, "one renderTtsGuide")
_steps = re.search(r"const TTS_STEPS = \[(.*?)\n\];", JS, re.S)
check(bool(_steps) and _steps.group(1).count("],") + 1 == 8, "guide lists all eight steps",
      str(_steps.group(1).count("],") + 1) if _steps else "none")
check("github.com/sammcj/openmoss" in JS, "guide names the specific MOSS build it targets")
check("Experimental" in JS, "guide is marked experimental")
check("copyCode" in JS and "clipboard" in JS,
      "the repo URL is copy-to-clipboard, not an outbound request")
check("<a href" not in (_steps.group(1) if _steps else ""),
      "no outbound link in the guide steps (section 10: no automatic outbound calls)")


# ------------------------------------------------------- 11. behaviour (jsdom)
section("behaviour (jsdom)")

JSDOM = "/tmp/node_modules/jsdom"
if not os.path.isdir(JSDOM):
    check(None, "jsdom behaviour tests", "jsdom not installed")
else:
    harness = os.path.join(tempfile.mkdtemp(), "h.js")
    htmlf = harness.replace("h.js", "page.html")
    open(htmlf, "wb").write(PAGE.encode("utf-8", "surrogatepass"))
    open(harness, "w").write(r"""
const { JSDOM } = require(%r);
const fs = require('fs');
const html = fs.readFileSync(%r, 'utf8');
const errors = [];
const dom = new JSDOM(html, { runScripts: 'dangerously', pretendToBeVisual: true,
  beforeParse(w) {
    w.__posts = [];
    w.fetch = (url, opt) => {
      if (String(url).indexOf('/api/settings') >= 0 && opt && opt.body) w.__posts.push(opt.body);
      return Promise.resolve({ json: () => Promise.resolve({}), text: () => Promise.resolve('') });
    };
    w.EventSource = function () { this.close = () => {}; };
    w.matchMedia = () => ({ matches: false, addEventListener(){}, removeEventListener(){} });
    w.onerror = (m) => errors.push(String(m));
  }});
const w = dom.window, d = w.document;
const need = ['tab-tts','nav-tts','dpane-tts','tsub-tts','tpane-tts','tail-tts','tts-src'];
const missing = need.filter(id => !d.getElementById(id));
let threw = '';
// top-level `let state` is a script-scope binding, NOT a window property: assigning
// w.state makes a second variable the page never reads. eval reaches the real one.
w.eval("state = { settings: {}, gpus: [{id:'g1',uuid:'GPU-test',name:'Test Card'}],"
     + " slots: [], routing: [], scope: 'host' };");
try { w.showDsub('tts'); w.showTsub('tts'); w.showDsub('term'); }
catch (e) { threw = String(e && e.message || e); }
const pane = d.getElementById('dpane-tts');
console.log(JSON.stringify({
  missing, threw, errors: errors.slice(0, 3),
  ttsPaneRendered: !!(pane && pane.innerHTML.length > 300),
  ttsFields: need.length,
  blankControls: [...d.querySelectorAll('button')].filter(b => !b.textContent.trim() && !b.querySelector('svg')).length,
  ...(function () {
    // the pane must track the server even when it is stopped from somewhere else
    const mk = (s) => JSON.stringify({ settings: { ttsWrapMode: 'on', ttsWrapperPort: '7860', ttsServerExe: 'x' },
      gpus: [], slots: [], routing: [], scope: 'host',
      ttsServer: { state: s, port: 1240 }, ttsWrap: { on: true, port: 7860 } });
    const pane = () => (d.getElementById('dpane-tts').textContent || '').replace(/\s+/g, ' ');
    try {
      w.showTab('dashboard'); w.showDsub('tts');
      w.eval('state = ' + mk('serving') + ';'); w.renderCurrent();
      const up = /ready/.test(pane());
      w.eval('state = ' + mk('down') + ';'); w.renderCurrent();
      const dn = /stopped/.test(pane());
      w.eval('state = ' + mk('serving') + ';'); w.renderCurrent();
      const inp = d.getElementById('tts-ttsServerPort');
      if (inp) { inp.value = 'MIDEDIT'; inp.focus(); }
      w.eval('state = ' + mk('down') + ';'); w.renderCurrent();
      const kept = (d.getElementById('tts-ttsServerPort') || {}).value === 'MIDEDIT';
      // a shutting-down server must look different from a stopped one, and neither
      // button may be pressed while it is between the two
      const mk2 = (s, stopping) => JSON.stringify({ settings: { ttsWrapMode: 'on', ttsWrapperPort: '7860', ttsServerExe: 'x' },
        gpus: [], slots: [], routing: [], scope: 'host',
        ttsServer: { state: s, port: 1240, stopping: !!stopping }, ttsWrap: { on: true, port: 7860 } });
      if (inp && inp.blur) inp.blur();      // release focus, or the guard (correctly)
      if (d.activeElement && d.activeElement.blur) d.activeElement.blur();  // skips the redraw
      w.eval('state = ' + mk2('wedged', true) + ';'); w.renderCurrent();
      const going = /shutting down/.test(pane());
      const bq = (a) => { const b = [...d.querySelectorAll('[data-act="' + a + '"]')][0]; return b ? b.disabled : null; };
      const locked = bq('ttsStart') === true && bq('ttsStop') === true;
      // Terminate is one long write, and queueLoad defers every reload while a write is
      // in flight - so the pane can only show the gap if the caller marks it
      let tShows = false, tDetail = '';
      try {
        w.eval('state = ' + mk2('serving', false) + ';'); w.renderCurrent();
        w.eval('ttsBusy = "stop";'); w.renderCurrent();
        tShows = /shutting down/.test(pane());
        tDetail = 'pill=' + (pane().match(/shutting down|stopped|ready/) || [''])[0];
        w.eval('ttsBusy = "";');
      } catch (e) { tDetail = String(e); }
      let aPost = 'none', aSticks = false, aOff = false, aOn = false, aDet = '';
      let dArc = false, dHl = false, dDet = '', paintRoles = '';
      try {
        const W = String.fromCharCode(12336) + String.fromCharCode(65039);
        const pre = d.getElementById('tail-tts');
        w.paintTail('tts', '\u{1F3AD} Aurivoice: ' + W + ' *whispering*Keep quiet. ' + W, pre);
        const NAME = { '#ff5dc8': 'magenta', '#ffffff': 'white', '#2ef2ff': 'cyan',
                       '#f2c14e': 'say' };
        paintRoles = [...pre.querySelectorAll('span')]
          .map(s => { const m = (s.getAttribute('style') || '').match(/color:([^;]+)/);
                      return m ? (NAME[m[1]] || '?') : ''; })
          .filter(x => x)
          .join('|');
      } catch (e) { paintRoles = String(e); }
      try {
        const mkc = (arc) => JSON.stringify({ settings: Object.assign({ themeName: 'OpenRouter' },
          arc === undefined ? {} : { launchArc: arc }), gpus: [], slots: [], routing: [], scope: 'host' });
        w.eval('state = ' + mkc(undefined) + ';'); w.showTab('custom');
        const bx = () => d.querySelector('#tab-custom [data-act="launchArcToggle"]');
        const before = w.__posts.length;
        bx().closest('label').click();
        const sent = w.__posts.slice(before).map(x => { try { return JSON.parse(x); } catch (e) { return {}; } })
                              .filter(x => 'launchArc' in x);
        aPost = sent.length ? String(sent[sent.length - 1].launchArc) : 'none';
        w.eval('state = ' + mkc(false) + ';'); w.renderCustom();
        aSticks = bx().checked === false;
        const lb = d.getElementById('launchBtn');
        const drew = () => { const s = lb && lb.querySelector('.arcsvg'); return !!(s && s.children.length); };
        if (lb) { w.arcFire(lb, true, false); aOff = !drew(); }
        w.eval('state = ' + mkc(true) + ';'); w.renderCustom();
        if (lb) { w.arcFire(lb, true, false); aOn = drew(); }
        aDet = 'off=' + aOff + ' on=' + aOn;
        // the Main Guide's launch step, with the effect on and off
        if (lb) {
          lb.scrollIntoView = () => {};
          w.eval('state = ' + mkc(true) + ';');
          lb.classList.remove('guidehl', 'lbdemo');
          w.launchDemo();
          dArc = lb.classList.contains('lbdemo') && !lb.classList.contains('guidehl');
          w.eval('state = ' + mkc(false) + ';');
          lb.classList.remove('guidehl', 'lbdemo');
          w.launchDemo();
          dHl = lb.classList.contains('guidehl') && !lb.classList.contains('lbdemo');
          dDet = 'on=' + dArc + ' off=' + dHl;
        }
      } catch (e) { aDet = String(e); }
      return { paintRoles: paintRoles,
               arcPost: aPost, arcSticks: aSticks, arcOffNoDraw: aOff, arcOnDraws: aOn, arcDetail: aDet,
               demoArc: dArc, demoHl: dHl, demoDetail: dDet,
               followsState: up && dn, followsState2: 'up=' + up + ' down=' + dn, keepsEdit: kept,
               showsStopping: going, bothDisabledMidStop: locked,
               terminateShows: tShows, terminateDetail: tDetail,
               stopDetail: 'shows=' + going + ' start=' + bq('ttsStart') + ' stop=' + bq('ttsStop') };
    } catch (e) { return { followsState: false, followsState2: String(e), keepsEdit: false }; }
  })()
}));
w.close();
process.exit(0);          // the page's interval loop never lets node exit (section 9)
""" % (JSDOM, htmlf))
    r = subprocess.run(["node", harness], capture_output=True, text=True, timeout=90)
    try:
        out = json.loads(r.stdout.strip().splitlines()[-1])
        check(not out["missing"], "TTS elements present in the DOM", str(out["missing"]))
        check(not out["threw"], "showDsub/showTsub run without throwing", out["threw"])
        check(not out["errors"], "no window errors during load", str(out["errors"]))
        check(out["ttsPaneRendered"], "TTS setup pane renders content")
        check(out["followsState"],
              "TTS pane follows a server state change (Terminate from elsewhere)",
              out["followsState2"])
        check(out["keepsEdit"], "TTS pane does not redraw over a field being typed in")
        check(out["showsStopping"], "TTS pane shows a shutting-down state", out["stopDetail"])
        check(out["bothDisabledMidStop"],
              "neither Start nor Stop can be pressed mid-shutdown", out["stopDetail"])
        check(out["terminateShows"],
              "Terminate shows the TTS pane shutting down while it runs", out["terminateDetail"])
        check(out["arcPost"] == "false", "clicking the arc switch posts launchArc:false",
              "posted " + str(out["arcPost"]))
        check(out["arcSticks"], "and it stays off after a re-render")
        check(out["arcOffNoDraw"] and out["arcOnDraws"],
              "the effect follows the switch", out["arcDetail"])
        # exact sequence is brittle (incidental spans for spacing); check the roles
        _pr = str(out["paintRoles"])
        check(_pr.startswith("magenta"), "the speaker is magenta", _pr)
        check("white|cyan|white" in _pr, "a tag is cyan between white stars", _pr)
        check("say" in _pr, "and the spoken line is highlighted", _pr)
        check(out["demoHl"], "guide step 8 highlights the button when the arc is off",
              out["demoDetail"])
        check(out["demoArc"], "and still demonstrates it when the arc is on", out["demoDetail"])
        check(out["blankControls"] == 0, "no blank buttons",
              "%d blank" % out["blankControls"])
    except Exception as e:
        check(False, "jsdom harness ran", (r.stderr or r.stdout)[:300] or str(e))


# ------------------------------------------------------------------- verdict
print("\n" + "=" * 62)
if SKIP:
    print("SKIPPED (%d) - not run, not passed:" % len(SKIP))
    for s, l, d in SKIP:
        print("   [%s] %s %s" % (s, l, d))
if FAIL:
    print("GATE FAILED - %d check(s):" % len(FAIL))
    for s, l, d in FAIL:
        print("   [%s] %s %s" % (s, l, d))
    sys.exit(1)
print("GATE PASSED")
