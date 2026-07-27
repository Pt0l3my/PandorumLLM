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
           "force-stop.bat", "launch-llm-fleet.ps1", "launcher-template.ps1",
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
         "TTS [Alpha]": "dsub-tts", "Provider Statistics": "pmsub-stats"}
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
check(JS.count('refreshCurTerm();') == 2,
      "refreshCurTerm called from both showTsub and liveRefresh",
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
    w.fetch = () => Promise.resolve({ json: () => Promise.resolve({}), text: () => Promise.resolve('') });
    w.EventSource = function () { this.close = () => {}; };
    w.matchMedia = () => ({ matches: false, addEventListener(){}, removeEventListener(){} });
    w.onerror = (m) => errors.push(String(m));
  }});
const w = dom.window, d = w.document;
const need = ['tab-dashboard','dsub-tts','dpane-tts','tsub-tts','tpane-tts','tail-tts','tts-src'];
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
      return { followsState: up && dn, followsState2: 'up=' + up + ' down=' + dn, keepsEdit: kept,
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
